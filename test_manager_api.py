"""Security, financial-unit and data-source tests for the real manager dashboard."""
import hashlib
import hmac
import json
import time
import unittest
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import core
import manager_api


def signed_data(token,uid,now=None):
    now=int(time.time()) if now is None else int(now)
    data={'auth_date':str(now),'query_id':'AAExample',
          'user':json.dumps({'id':uid,'first_name':'Admin'},separators=(',',':'))}
    key=hmac.new(b'WebAppData',token.encode(),hashlib.sha256).digest()
    check='\n'.join(k+'='+v for k,v in sorted(data.items()))
    data['hash']=hmac.new(key,check.encode(),hashlib.sha256).hexdigest()
    return urlencode(data)


class ManagerApiTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1,'admin','Rahbar'),(2,'agent','Alisher'),(3,'cashier','Kassir')])
        self.now=int(datetime(2026,9,25,15,0,tzinfo=ZoneInfo('Asia/Tashkent')).timestamp())
        self.today=manager_api._midnight(self.now)
    def tearDown(self):
        self.db.close()
    def test_signed_init_data_tampering_expiry_and_missing_fields(self):
        raw=signed_data('secret',1,self.now)
        self.assertEqual(manager_api.verify_init_data(raw,'secret',self.now),1)
        for bad in (raw.replace('Admin','Other'),raw+'&id=2',raw.replace('auth_date','auth_date2'),
                    '',None,'user=%7B%7D'):
            with self.assertRaises(ValueError):
                manager_api.verify_init_data(bad,'secret',self.now)
        with self.assertRaises(ValueError):
            manager_api.verify_init_data(raw,'other-token',self.now)
        with self.assertRaisesRegex(ValueError,'muddati'):
            manager_api.verify_init_data(raw,'secret',self.now+3601)
    def test_telegram_signature_field_keeps_hmac_authentication(self):
        from urllib.parse import parse_qsl
        data=dict(parse_qsl(signed_data('secret',1,self.now)))
        data['signature']='ed25519_example'
        self.assertEqual(manager_api.verify_init_data(urlencode(data),'secret',self.now),1)
        data['user']=json.dumps({'id':2})
        with self.assertRaises(ValueError):
            manager_api.verify_init_data(urlencode(data),'secret',self.now)

    def test_dashboard_reads_real_clients_shifts_gps_and_does_not_mutate(self):
        self.db.execute("""INSERT INTO clients(id,agent,name,shop_name,phone,address,lat,lon,created_ts,map_only)
                         VALUES(101,2,'Buyer','Real shop','+998900000001','Qo‘qon',40.54,70.94,?,1)""",
                        (self.today-6*86400,))
        self.db.execute("INSERT INTO shifts(id,agent,start,live_id) VALUES(15,2,?,123)",
                        (self.today+3600,))
        self.db.execute("INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(15,?,40.541,70.941,8)",
                        (self.now-120,))
        self.db.execute("""INSERT INTO client_visits(client,actor,status,note,ts)
                         VALUES(101,2,'active','New goods',?)""",(self.now-200,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,amount_usd,ts)
                         VALUES(2,2,101,'delivery',12500,?)""",(self.now-180,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,amount_usd,ts)
                         VALUES(2,2,101,'payment',3000,?)""",(self.now-170,))
        self.db.execute("""INSERT INTO handovers(agent,amount_usd,status,ts,accepted_ts)
                         VALUES(2,3000,'accepted',?,?)""",(self.now-150,self.now-100))
        self.db.commit()
        before=self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        snap=manager_api.dashboard(self.db,self.now)
        self.assertEqual(snap['summary']['agentCount'],1)
        self.assertEqual(snap['summary']['workingAgents'],1)
        self.assertEqual(snap['summary']['visitsToday'],1)
        self.assertEqual(snap['summary']['acceptedTodayUsd'],30)
        self.assertEqual(snap['agents'][0]['status'],'active')
        self.assertEqual(snap['agents'][0]['lat'],40.541)
        self.assertEqual(snap['clients'][0]['name'],'Real shop')
        self.assertEqual(snap['clients'][0]['debtUsd'],95)
        self.assertEqual(snap['clients'][0]['age'],'fresh')
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],before)
        route=manager_api.route(self.db,2,self.now)
        self.assertEqual(len(route['points']),1)
        self.assertEqual(route['points'][0]['lat'],40.541)
    def test_period_reports_include_sales_cash_route_work_and_agent_metrics(self):
        self.db.execute("""INSERT INTO clients(id,agent,name,shop_name,phone,address,lat,lon,created_ts,map_only)
                         VALUES(201,2,'New buyer','New shop','+998900000201','Qo‘qon',40.54,70.94,?,0)""",
                        (self.today+1800,))
        self.db.execute("""INSERT INTO shifts(id,agent,start,"end") VALUES(21,2,?,?)""",
                        (self.today+3600,self.today+7200))
        self.db.execute("INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(21,?,40.5400,70.9400,8)",
                        (self.today+3700,))
        self.db.execute("INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(21,?,40.5410,70.9410,8)",
                        (self.today+4000,))
        self.db.execute("""INSERT INTO client_visits(client,actor,status,note,ts)
                         VALUES(201,2,'active','Visit',?)""",(self.today+5000,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts)
                         VALUES(2,2,201,'delivery',1,10,10000,?)""",(self.today+5100,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,amount_usd,ts)
                         VALUES(2,2,201,'payment',2500,?)""",(self.today+5200,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts)
                         VALUES(2,2,201,'return',1,1,1000,?)""",(self.today+5300,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts)
                         VALUES(2,2,201,'sold',1,2,2000,?)""",(self.today+5400,))
        self.db.execute("""INSERT INTO handovers(agent,amount_usd,status,ts,accepted_ts)
                         VALUES(2,2500,'accepted',?,?)""",(self.today+5500,self.today+5600))
        self.db.execute("""INSERT INTO cashier_expenses(cashier,amount_usd,category,recipient,note,source,ts)
                         VALUES(3,500,'⛽ Ёқилғи','АЗС','',99001,?)""",(self.today+5700,))
        snap=manager_api.dashboard(self.db,self.now)
        day=snap['reports']['today']
        self.assertEqual(day['visits'],1)
        self.assertEqual(day['newClients'],1)
        self.assertEqual(day['deliveredUsd'],100)
        self.assertEqual(day['paymentsUsd'],25)
        self.assertEqual(day['returnsUsd'],10)
        self.assertEqual(day['deliveredQty'],10)
        self.assertEqual(day['soldQty'],2)
        self.assertEqual(day['acceptedCashUsd'],25)
        self.assertEqual(day['cashierExpensesUsd'],5)
        self.assertEqual(day['workSeconds'],3600)
        self.assertGreater(day['distanceKm'],0)
        self.assertEqual(day['agents'][0]['agent'],'Alisher')
        self.assertEqual(day['agents'][0]['deliveredUsd'],100)
        self.assertEqual(day['agents'][0]['paymentsUsd'],25)
        self.assertEqual(day['agents'][0]['visits'],1)
        self.assertEqual(day['agents'][0]['newClients'],1)
        self.assertGreater(day['agents'][0]['distanceKm'],0)
        self.assertEqual(snap['summary']['debtUsd'],65)
        self.assertEqual(snap['reports']['week']['deliveredUsd'],100)
        self.assertEqual(snap['reports']['month']['paymentsUsd'],25)
        self.assertEqual(snap['reports']['series'][-1]['deliveredUsd'],100)
        self.assertEqual(snap['reports']['series'][-1]['paymentsUsd'],25)

    def test_product_breakdown_uses_delivery_for_revenue_and_sold_only_for_units(self):
        self.db.execute("""INSERT INTO clients(id,agent,name,phone,created_ts,map_only)
                         VALUES(301,2,'P buyer','+998900000301',?,0)""",(self.today,))
        rows=[
            (2,2,301,'delivery',1,10,10000,self.today+100),
            (2,2,301,'sold',1,4,4000,self.today+110),
            (2,2,301,'return',1,1,1000,self.today+120),
            (2,2,301,'delivery',3,6,9000,self.today+130),
            (2,2,301,'sold',3,2,3000,self.today+140),
            (2,2,301,'delivery',5,2,8000,self.today+150),
        ]
        self.db.executemany("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts)
                             VALUES(?,?,?,?,?,?,?,?)""",rows)
        snap=manager_api.dashboard(self.db,self.now)
        day=snap['reports']['today']
        self.assertEqual(day['deliveredUsd'],270)
        self.assertEqual(day['soldQty'],6)
        self.assertEqual(len(day['products']),3)
        first=day['products'][0]
        self.assertEqual(first['pack'],1)
        self.assertEqual(first['name'],'Грунтовка 7/1 — 1 кг')
        self.assertEqual(first['deliveredQty'],10)
        self.assertEqual(first['deliveredUsd'],100)
        self.assertEqual(first['soldQty'],4)
        self.assertEqual(first['returnedQty'],1)
        self.assertEqual(first['returnedUsd'],10)
        self.assertAlmostEqual(first['sharePct'],37.0,places=1)
        self.assertEqual(day['topProduct'],'Грунтовка 7/1 — 1 кг')
        # "sold" amount is intentionally not added to financial realization.
        self.assertEqual(sum(p['deliveredUsd'] for p in day['products']),270)

    def test_closed_shift_keeps_last_known_gps_but_never_marks_it_live(self):
        self.db.execute("""INSERT INTO shifts(id,agent,start,"end",live_id)
                         VALUES(88,2,?,?,123)""",(self.today+1000,self.today+4000))
        self.db.execute("""INSERT INTO points(shift,ts,lat,lon,accuracy)
                         VALUES(88,?,40.444,71.222,6)""",(self.today+3900,))
        snap=manager_api.dashboard(self.db,self.now)
        agent=snap['agents'][0]
        self.assertFalse(agent['shiftOpen'])
        self.assertEqual(agent['status'],'offline')
        self.assertEqual(agent['locationSource'],'last')
        self.assertEqual(agent['lat'],40.444)
        self.assertEqual(agent['lon'],71.222)
        self.assertEqual(agent['lastGpsTs'],self.today+3900)
        self.assertEqual(snap['summary']['workingAgents'],0)

    def test_no_fake_gps_no_usd_uzs_mixing_and_pending_separate(self):
        self.db.execute("""INSERT INTO handovers(agent,amount_usd,amount,status,ts)
                         VALUES(2,1000,0,'pending',?)""",(self.now,))
        self.db.execute("""INSERT INTO handovers(agent,amount_usd,amount,status,ts,accepted_ts)
                         VALUES(2,0,500000,'accepted',?,?)""",(self.now,self.now))
        snap=manager_api.dashboard(self.db,self.now)
        self.assertIsNone(snap['agents'][0]['lat'])
        self.assertEqual(snap['agents'][0]['status'],'offline')
        self.assertEqual(snap['summary']['acceptedTodayUsd'],0)
        self.assertEqual(snap['summary']['pendingUsd'],10)
        self.assertEqual(snap['transactions'][0]['amountUzs'],5000)
        self.assertEqual(snap['summary']['newClientsToday'],0)
        self.assertEqual(snap['reports']['week']['visits'],0)
    def test_unknown_agent_route_is_rejected(self):
        with self.assertRaises(ValueError):
            manager_api.route(self.db,999,self.now)


if __name__=='__main__':
    unittest.main()
