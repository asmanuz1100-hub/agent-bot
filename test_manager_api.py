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
    def test_dashboard_cash_pending_and_expense_details(self):
        self.db.execute("""INSERT INTO handovers(agent,amount_usd,status,ts)
                         VALUES(2,4000,'pending',?)""",(self.now-120,))
        self.db.execute("""INSERT INTO handovers(agent,amount_usd,status,ts,accepted_ts,cashier)
                         VALUES(2,6000,'accepted',?,?,3)""",(self.now-110,self.now-90))
        self.db.execute("""INSERT INTO cashier_expenses(cashier,amount_usd,category,recipient,note,source,ts,
                         currency,amount_uzs,rate_uzs_per_usd)
                         VALUES(3,1000,'⛽ Ёқилғи','АЗС','Chek bor',88001,?,'UZS',125000,12500)""",
                        (self.now-80,))
        snap=manager_api.dashboard(self.db,self.now)
        self.assertEqual(snap['cash']['balanceUsd'],50)
        self.assertEqual(snap['cash']['acceptedTodayUsd'],60)
        self.assertEqual(snap['cash']['expensesTodayUsd'],10)
        self.assertEqual(snap['cash']['netTodayUsd'],50)
        self.assertEqual(snap['cash']['pendingUsd'],40)
        self.assertEqual(snap['cash']['pendingCount'],1)
        pending=next(t for t in snap['transactions'] if t['type']=='handover' and t['state']=='pending')
        self.assertEqual(pending['amountUsd'],40)
        expense=next(t for t in snap['transactions'] if t['type']=='expense')
        self.assertEqual(expense['cashier'],'Kassir')
        self.assertEqual(expense['currency'],'UZS')
        self.assertEqual(expense['amountUzs'],125000)
        self.assertEqual(expense['rateUzsPerUsd'],12500)
        self.assertEqual(expense['recipient'],'АЗС')

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
        self.assertEqual(snap['cash']['acceptedTodayUsd'],25)
        self.assertEqual(snap['cash']['expensesTodayUsd'],5)
        self.assertEqual(snap['cash']['netTodayUsd'],20)
        self.assertEqual(snap['cash']['balanceUsd'],20)
        self.assertEqual(snap['cash']['pendingUsd'],0)
        self.assertEqual(snap['cash']['pendingCount'],0)
        self.assertTrue(any(t['type']=='handover' and t['state']=='accepted' for t in snap['transactions']))
        self.assertTrue(any(t['type']=='expense' and t['amountUsd']==5 for t in snap['transactions']))
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

    def test_general_analysis_has_previous_period_receivable_and_customer_status(self):
        yesterday=self.today-86400
        self.db.execute("""INSERT INTO clients(id,agent,name,phone,created_ts,map_only)
                         VALUES(250,2,'Fresh','+998900000250',?,0)""",(self.today+100,))
        self.db.execute("""INSERT INTO clients(id,agent,name,phone,created_ts,map_only)
                         VALUES(251,2,'Previous buyer','+998900000251',?,0)""",(self.today-7*86400,))
        self.db.execute("""INSERT INTO clients(id,agent,name,phone,created_ts,map_only)
                         VALUES(252,2,'Overdue untouched','+998900000252',?,0)""",(self.today-7*86400,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,amount_usd,ts)
                         VALUES(2,2,250,'delivery',10000,?)""",(self.today+200,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,amount_usd,ts)
                         VALUES(2,2,250,'payment',4000,?)""",(self.today+300,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,amount_usd,ts)
                         VALUES(2,2,251,'delivery',5000,?)""",(yesterday+200,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,amount_usd,ts)
                         VALUES(2,2,251,'payment',1000,?)""",(yesterday+300,))
        snap=manager_api.dashboard(self.db,self.now)
        day=snap['reports']['today']
        self.assertEqual(day['netReceivableChangeUsd'],60)
        self.assertEqual(day['paymentToDeliveryPct'],40.0)
        self.assertEqual(day['previous']['deliveredUsd'],50)
        self.assertEqual(day['previous']['paymentsUsd'],10)
        self.assertEqual(day['previous']['netReceivableChangeUsd'],40)
        self.assertGreaterEqual(snap['summary']['freshClients'],1)
        self.assertGreaterEqual(snap['summary']['overdueClients'],1)
        self.assertEqual(
            snap['summary']['freshClients']+snap['summary']['yellowClients']+
            snap['summary']['overdueClients']+snap['summary']['scheduledClients']+
            snap['summary']['unknownClients'],
            len(snap['clients'])
        )

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
    def test_customer_detail_contains_stock_money_visits_and_edit_audit(self):
        self.db.execute("""INSERT INTO clients(id,agent,name,shop_name,phone,address,comment,payment_due,lat,lon,created_ts,map_only)
                         VALUES(401,2,'Person','Shop 401','+998904010000','Qo‘qon','Izoh','Dushanba',40.55,70.95,?,0)""",
                        (self.today+100,))
        self.db.executemany("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts,note)
                             VALUES(2,2,401,?,?,?,?,?,?)""",[
            ('delivery',1,10,2000,self.today+200,''),
            ('sold',1,3,600,self.today+300,''),
            ('payment',0,0,500,self.today+400,'paid'),
            ('return',1,1,200,self.today+500,'back'),
        ])
        self.db.execute("""INSERT INTO client_visits(client,actor,status,note,followup,ts)
                         VALUES(401,2,'active','Ko‘rildi','Ertaga',?)""",(self.today+600,))
        core.edit_client(self.db,1,401,{'comment':'Yangi izoh'})
        detail=manager_api.client_detail(self.db,401)
        self.assertEqual(detail['name'],'Shop 401')
        self.assertEqual(detail['person'],'Person')
        self.assertEqual(detail['debtUsd'],13)
        self.assertEqual(detail['stocks'][0]['qty'],6)
        self.assertEqual(detail['totals']['deliveredUsd'],20)
        self.assertEqual(detail['totals']['paidUsd'],5)
        self.assertEqual(detail['totals']['returnedUsd'],2)
        self.assertEqual(detail['events'][0]['kind'],'return')
        self.assertEqual(detail['events'][1]['kind'],'payment')
        self.assertEqual(detail['visits'][0]['note'],'Ko‘rildi')
        self.assertEqual(detail['edits'][0]['field'],'comment')
        self.assertEqual(detail['edits'][0]['actor'],'Rahbar')

    def test_customer_edit_preview_whitelists_fields_and_normalizes_values(self):
        self.db.execute("""INSERT INTO clients(id,agent,name,shop_name,phone,address,comment,created_ts,map_only)
                         VALUES(402,2,'Old','Shop','+99890000402','Old address','old',?,0)""",(self.today,))
        preview=manager_api.client_edit_preview(self.db,402,{
            'name':' New person ','shop_name':' New shop ','phone':' +998901112233 ',
            'address':' New address ','comment':' New note ','payment_due':' Friday '
        })
        self.assertEqual(preview['clientId'],402)
        self.assertEqual(preview['values']['name'],'New person')
        self.assertEqual(preview['values']['shop_name'],'New shop')
        self.assertEqual(len(preview['changes']),6)
        self.assertEqual(self.db.execute("SELECT name FROM clients WHERE id=402").fetchone()[0],'Old')
        with self.assertRaises(ValueError):
            manager_api.client_edit_preview(self.db,402,{'agent':'3'})
        with self.assertRaises(ValueError):
            manager_api.client_edit_preview(self.db,402,{'name':'Old'})

    def test_agent_detail_combines_gps_stock_cash_permissions_and_periods(self):
        self.db.execute("""INSERT INTO clients(id,agent,name,phone,created_ts,map_only)
                         VALUES(501,2,'Agent buyer','+998905010000',?,0)""",(self.today+100,))
        self.db.execute("""INSERT INTO shifts(id,agent,start,live_id) VALUES(51,2,?,555)""",
                        (self.today+1000,))
        self.db.execute("INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(51,?,40.51,70.91,7)",
                        (self.today+1100,))
        self.db.execute("INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(51,?,40.512,70.912,7)",
                        (self.today+1300,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts)
                         VALUES(1,2,0,'load',1,20,0,?)""",(self.today+100,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts)
                         VALUES(2,2,501,'delivery',1,5,1000,?)""",(self.today+1400,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,amount_usd,ts)
                         VALUES(2,2,501,'payment',600,?)""",(self.today+1500,))
        self.db.execute("""INSERT INTO handovers(agent,amount_usd,status,ts)
                         VALUES(2,400,'pending',?)""",(self.today+1600,))
        self.db.execute("""INSERT INTO client_visits(client,actor,status,note,ts)
                         VALUES(501,2,'active','ok',?)""",(self.today+1700,))
        core.set_agent_feature(self.db,1,2,'payment',False)
        detail=manager_api.agent_detail(self.db,2,self.now)
        self.assertTrue(detail['active'])
        self.assertTrue(detail['shiftOpen'])
        self.assertEqual(detail['clients'],1)
        self.assertEqual(detail['lastGpsTs'],self.today+1300)
        self.assertEqual(detail['stocks'][0]['qty'],15)
        self.assertEqual(detail['cashUsd'],6)
        self.assertEqual(detail['pendingHandoverUsd'],4)
        payment=next(f for f in detail['features'] if f['key']=='payment')
        self.assertFalse(payment['enabled'])
        self.assertEqual(detail['periods']['today']['deliveredUsd'],10)
        self.assertEqual(detail['periods']['today']['paymentsUsd'],6)
        self.assertEqual(detail['periods']['today']['visits'],1)
        self.assertEqual(detail['periods']['today']['newClients'],1)
        self.assertGreater(detail['periods']['today']['distanceKm'],0)

    def test_agent_management_helpers_are_audited_and_previews_do_not_mutate(self):
        preview=manager_api.agent_add_preview(self.db,900001,' New Agent ')
        self.assertEqual(preview,{'id':900001,'name':'New Agent'})
        self.assertIsNone(self.db.execute("SELECT 1 FROM users WHERE id=900001").fetchone())
        core.add_agent(self.db,1,preview['id'],preview['name'])
        self.assertEqual(self.db.execute("SELECT role FROM users WHERE id=900001").fetchone()[0],'agent')
        self.assertEqual(self.db.execute("""SELECT action FROM role_audit
            WHERE new_id=900001 ORDER BY id DESC LIMIT 1""").fetchone()[0],'agent_created')
        rename=manager_api.agent_rename_preview(self.db,900001,'Agent Yangilandi')
        self.assertEqual(rename['oldName'],'New Agent')
        core.rename_agent(self.db,1,900001,rename['newName'])
        self.assertEqual(self.db.execute("SELECT name FROM users WHERE id=900001").fetchone()[0],
                         'Agent Yangilandi')
        self.assertEqual(self.db.execute("""SELECT action FROM role_audit
            WHERE new_id=900001 ORDER BY id DESC LIMIT 1""").fetchone()[0],'agent_renamed')
        transfer=manager_api.agent_transfer_preview(self.db,900001,900002)
        self.assertEqual(transfer['newId'],900002)
        self.assertIsNone(self.db.execute("SELECT 1 FROM users WHERE id=900002").fetchone())
        deactivate=manager_api.agent_deactivate_preview(self.db,900001)
        self.assertIn('o‘chirilmaydi',deactivate['warning'])
        self.assertEqual(self.db.execute("SELECT role FROM users WHERE id=900001").fetchone()[0],'agent')

    def test_agent_transfer_preview_rejects_open_shift_and_existing_identity(self):
        self.db.execute("""INSERT INTO shifts(id,agent,start,live_id) VALUES(92,2,?,1)""",(self.today,))
        with self.assertRaisesRegex(ValueError,'smenasini'):
            manager_api.agent_transfer_preview(self.db,2,999)
        self.db.execute('UPDATE shifts SET "end"=? WHERE id=92',(self.today+100,))
        with self.assertRaisesRegex(ValueError,'ro‘yxatdan'):
            manager_api.agent_transfer_preview(self.db,2,3)

    def test_agent_management_lists_active_and_disabled_accounts(self):
        self.db.execute("INSERT INTO users(id,role,name) VALUES(?,?,?)",(77,'disabled','Old Agent'))
        rows=manager_api.agent_management(self.db)['agents']
        active=next(x for x in rows if x['id']==2)
        disabled=next(x for x in rows if x['id']==77)
        self.assertTrue(active['active'])
        self.assertFalse(disabled['active'])
        self.assertEqual(disabled['role'],'disabled')

    def test_agent_period_route_and_customer_visits_only_from_selected_day(self):
        yesterday=self.today-86400
        self.db.execute("""INSERT INTO clients(id,agent,name,shop_name,address,phone,lat,lon,created_ts,map_only)
             VALUES(601,2,'Contact','New shop','Qo‘qon','+998906010000',40.5,71.0,?,0)""",
             (self.today+300,))
        self.db.execute("""INSERT INTO clients(id,agent,name,shop_name,address,phone,lat,lon,created_ts,map_only)
             VALUES(602,2,'Older','Older shop','Qo‘qon','+998906020000',40.6,71.1,?,0)""",
             (yesterday+200,))
        self.db.execute("""INSERT INTO shifts(id,agent,start,"end") VALUES(65,2,?,?)""",
             (yesterday+200,yesterday+1800))
        self.db.execute("""INSERT INTO shifts(id,agent,start,"end") VALUES(66,2,?,?)""",
             (self.today+100,self.today+6000))
        self.db.executemany("""INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,?)""",[
            (65,yesterday+300,40.1,70.1,5),
            (65,yesterday+400,40.2,70.2,5),
            (66,self.today+200,40.5,70.9,5),
            (66,self.today+280,40.501,70.901,5),
            (66,self.today+3500,40.502,70.902,5),
        ])
        self.db.executemany("""INSERT INTO client_visits(client,actor,status,note,ts)
             VALUES(?,?,?,?,?)""",[
            (602,2,'active','Kecha',yesterday+700),
            (601,2,'active','Bugun',self.today+600),
            (602,2,'waiting','Qayta tashrif',self.today+700),
        ])
        day=manager_api.agent_period_detail(self.db,2,'today',self.now)
        self.assertEqual(day['newClientsTotal'],1)
        self.assertEqual(day['visitsTotal'],2)
        self.assertEqual(day['newClients'][0]['id'],601)
        self.assertEqual({v['clientId'] for v in day['visits']},{601,602})
        self.assertEqual(day['route']['gpsTotal'],3)
        self.assertEqual(day['route']['segments'][0][0]['ts'],self.today+200)
        self.assertTrue(all(p['ts']>=self.today for seg in day['route']['segments'] for p in seg))
        self.assertEqual(len(day['route']['segments']),2)  # GPS gap: no invented line.
        self.assertEqual(day['visits'][0]['note'],'Qayta tashrif')
        week=manager_api.agent_period_detail(self.db,2,'week',self.now)
        self.assertEqual(week['newClientsTotal'],2)
        self.assertEqual(week['visitsTotal'],3)
        self.assertEqual(week['route']['gpsTotal'],5)
        self.assertTrue(len(week['route']['segments'])>=3)  # shifts stay separate
        self.assertEqual(week['newClients'][0]['name'],'New shop')
        self.assertIsNone(self.db.execute("SELECT 1 FROM events WHERE client=601").fetchone())

    def test_agent_period_route_samples_entire_range_and_validates_period(self):
        base=self.today+100
        self.db.execute("""INSERT INTO shifts(id,agent,start,"end") VALUES(77,2,?,?)""",
             (base,base+2000))
        rows=[(77,base+i,40.51,70.91,5) for i in range(1800)]
        self.db.executemany("""INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,?)""",rows)
        day=manager_api.agent_period_detail(self.db,2,'today',self.today+2500)
        self.assertEqual(day['route']['gpsTotal'],1800)
        self.assertLessEqual(day['route']['gpsShown'],1001)
        self.assertTrue(day['route']['sampled'])
        stamps=[p['ts'] for seg in day['route']['segments'] for p in seg]
        self.assertEqual(stamps[0],base)
        self.assertEqual(stamps[-1],base+1799)
        with self.assertRaisesRegex(ValueError,'Davr'):
            manager_api.agent_period_detail(self.db,2,'invalid',self.now)
        with self.assertRaisesRegex(ValueError,'topilmadi'):
            manager_api.agent_period_detail(self.db,999,'today',self.now)

    def test_agent_period_sampling_sql_has_no_unescaped_psycopg_percent(self):
        class Recorder:
            def __init__(self,db):
                self.db=db
                self.gps_sql=None
            def execute(self,sql,params=()):
                if "WITH numbered AS" in sql:
                    self.gps_sql=sql
                return self.db.execute(sql,params)
        recorder=Recorder(self.db)
        detail=manager_api.agent_period_detail(recorder,2,'today',self.now)
        self.assertEqual(detail['route']['gpsTotal'],0)
        self.assertIsNotNone(recorder.gps_sql)
        postgres_sql=core._pg_sql(recorder.gps_sql)
        self.assertNotIn('%',postgres_sql.replace('%s',''))
        self.assertIn('((rn-1) / ((total+999)/1000))',postgres_sql)

    def test_unknown_agent_route_is_rejected(self):
        with self.assertRaises(ValueError):
            manager_api.route(self.db,999,self.now)


if __name__=='__main__':
    unittest.main()
