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
        self.assertEqual(snap['transactions'][0]['amountUzs'],500000)
        self.assertEqual(snap['summary']['newClientsToday'],0)
        self.assertEqual(snap['reports']['week']['visits'],0)
    def test_unknown_agent_route_is_rejected(self):
        with self.assertRaises(ValueError):
            manager_api.route(self.db,999,self.now)


if __name__=='__main__':
    unittest.main()
