"""Real Agent Mini App API tests: live DB reads, write rules and idempotency."""
import time
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import agent_api
import core

TZ=ZoneInfo('Asia/Tashkent')


class AgentApiTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Admin'),(2,'agent','Ali'),(3,'cashier','Cashier'),(4,'agent','Other')])
        self.now=int(datetime(2026,9,25,14,0,tzinfo=TZ).timestamp())
        self.db.execute('UPDATE products SET price=? WHERE pack=1',(250,))
        self.db.execute('UPDATE products SET price=? WHERE pack=3',(500,))
        self.db.execute('UPDATE products SET price=? WHERE pack=5',(800,))
        core.record(self.db,1,2,None,'load',1,30,source=7001,currency='USD')
        core.record(self.db,1,2,None,'load',3,12,source=7002,currency='USD')
        core.record(self.db,1,2,None,'load',5,8,source=7003,currency='USD')
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def payload(self,**kwargs):
        base={'requestId':'req_12345678'}
        base.update(kwargs)
        return base

    def add_client(self,request='client_12345678'):
        return agent_api.mutate(self.db,2,'add_client',{
            'shopName':'Baraka','name':'Vali',
            'phone':'+998901234567','address':'Qo‘qon, markaz',
            'lat':40.54,'lon':70.94,'status':'interested',
            'note':'Katalog berildi'
        },request,self.now)

    def live_shift(self):
        self.db.execute('INSERT INTO shifts(id,agent,start,live_id) VALUES(99,2,?,777)',(self.now-600,))
        self.db.execute('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(99,?,40.54,70.94,8)',(self.now-30,))

    def test_dashboard_has_only_real_rows_and_agent_scope_for_cash(self):
        self.add_client()
        cid=self.db.execute("SELECT id FROM clients WHERE shop_name='Baraka'").fetchone()[0]
        core.record(self.db,2,2,cid,'delivery',1,4,0,'',8001,currency='USD')
        core.record(self.db,2,2,cid,'payment',0,0,500,'',8002,currency='USD')
        # Other agent data must not enter Ali's own cash totals.
        self.db.execute("INSERT INTO clients(agent,name,phone,address,created_ts,map_only) VALUES(4,'X','+998909999999','X',?,1)",(self.now,))
        other=self.db.execute("SELECT id FROM clients WHERE agent=4").fetchone()[0]
        core.record(self.db,4,4,other,'payment',0,0,9900,'',8003,currency='USD')
        # Freeze event timestamps for the explicitly frozen 2026-09-25 test day.
        self.db.execute('UPDATE events SET ts=? WHERE source IN (8001,8002,8003)',(self.now,))
        snap=agent_api.dashboard(self.db,2,self.now)
        self.assertEqual(snap['profile']['name'],'Ali')
        self.assertEqual(snap['summary']['clientCount'],2)  # shared client directory
        self.assertEqual(snap['summary']['paymentsTodayUsd'],5)
        self.assertEqual(snap['summary']['deliveryTodayQty'],4)
        self.assertEqual(snap['products'][0]['agentStock'],26)
        self.assertEqual(len([x for x in snap['cash'] if x['kind']=='payment']),1)
        baraka=next(x for x in snap['clients'] if x['name']=='Baraka')
        self.assertEqual(baraka['debtUsd'],5)
        self.assertEqual(baraka['stock']['1'],4)
        self.assertNotIn('Alibek Karimov',str(snap))

    def test_add_client_is_real_gps_required_and_idempotent(self):
        first=self.add_client()
        self.db.commit()
        self.assertTrue(first['ok'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM clients').fetchone()[0],1)
        duplicate=self.add_client()
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM clients').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM client_visits').fetchone()[0],1)
        with self.assertRaisesRegex(ValueError,'GPS'):
            agent_api.mutate(self.db,2,'add_client',{
                'shopName':'No GPS','phone':'+998901112233','address':'A',
                'status':'interested','note':'Test'
            },'client_no_gps1',self.now)

    def test_delivery_visit_payment_return_and_handover_use_core_rules(self):
        self.add_client();cid=self.db.execute('SELECT id FROM clients').fetchone()[0]
        delivery=agent_api.mutate(self.db,2,'delivery',
            {'clientId':cid,'items':[{'pack':1,'qty':10},{'pack':3,'qty':6}]},
            'delivery_123456',self.now)
        self.assertTrue(delivery['ok'])
        self.assertEqual(core.client_debt_usd(self.db,cid),5500)
        self.assertEqual(core.agent_stock(self.db,2,1),20)
        agent_api.mutate(self.db,2,'visit',
            {'clientId':cid,'status':'waiting','note':'Ertaga kelishildi','followup':'2026-09-26'},
            'visit_12345678',self.now)
        self.live_shift()
        pay=agent_api.mutate(self.db,2,'payment',
            {'clientId':cid,'amount':'20.00'},'payment_123456',self.now)
        self.assertEqual(pay['_notify']['kind'],'payment')
        self.assertEqual(core.client_debt_usd(self.db,cid),3500)
        ret=agent_api.mutate(self.db,2,'return',
            {'clientId':cid,'items':[{'pack':1,'qty':2}]},'return_1234567',self.now)
        self.assertTrue(ret['ok'])
        self.assertEqual(core.client_stock_total(self.db,cid,1),8)
        self.assertEqual(core.client_debt_usd(self.db,cid),3000)
        hand=agent_api.mutate(self.db,2,'handover',
            {'amount':'10.00'},'handover_12345',self.now)
        self.assertEqual(hand['_notify']['kind'],'handover')
        self.assertEqual(self.db.execute("SELECT status FROM handovers").fetchone()[0],'pending')

    def test_payment_and_return_require_recent_live_location(self):
        self.add_client();cid=self.db.execute('SELECT id FROM clients').fetchone()[0]
        core.record(self.db,2,2,cid,'delivery',1,2,0,'',9001,currency='USD')
        self.db.commit()
        with self.assertRaisesRegex(ValueError,'Ishni boshlash'):
            agent_api.mutate(self.db,2,'payment',{'clientId':cid,'amount':'1'},'pay_no_shift1',self.now)
        self.db.rollback()
        self.db.execute('INSERT INTO shifts(id,agent,start,live_id) VALUES(55,2,?,NULL)',(self.now-100,))
        with self.assertRaisesRegex(ValueError,'jonli lokatsiya'):
            agent_api.mutate(self.db,2,'return',{'clientId':cid,'items':[{'pack':1,'qty':1}]},'ret_no_live12',self.now)

    def test_shift_start_end_route_and_disabled_feature(self):
        start=agent_api.mutate(self.db,2,'shift_start',{},'shift_start12',self.now)
        self.db.commit()
        self.assertTrue(start['shiftId'])
        with self.assertRaisesRegex(ValueError,'allaqachon'):
            agent_api.mutate(self.db,2,'shift_start',{},'shift_start13',self.now+1)
        self.db.rollback()
        # Keep the original shift and attach one GPS point.
        shift=self.db.execute('SELECT id FROM shifts WHERE agent=2 AND end IS NULL').fetchone()
        self.db.execute('UPDATE shifts SET live_id=100 WHERE id=?',(shift[0],))
        self.db.execute('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,?)',
                        (shift[0],self.now+5,40.5,70.9,10))
        route=agent_api.route(self.db,2)
        self.assertEqual(route['points'][0]['lat'],40.5)
        end=agent_api.mutate(self.db,2,'shift_end',{},'shift_end_123',self.now+100)
        self.assertIn('Ish tugadi',end['message'])
        self.assertEqual(end['_notify'],{'kind':'shift_end','shiftId':shift[0]})
        self.db.execute("INSERT INTO agent_features(agent,feature,enabled) VALUES(2,'payment',0)")
        with self.assertRaisesRegex(ValueError,'o‘chirilgan'):
            agent_api.mutate(self.db,2,'payment',{'clientId':999,'amount':'1'},'disabled_pay1',self.now)

    def test_snapshot_shape_matches_premium_agent_ui(self):
        self.add_client()
        snap=agent_api.snapshot(self.db,2,self.now)
        self.assertEqual(snap['me']['name'],'Ali')
        self.assertIn('paymentTodayUsd',snap['summary'])
        self.assertIn('cashAvailableUsd',snap['summary'])
        self.assertIn('day',snap['period'])
        self.assertEqual(snap['products'][0]['stock'],30)
        self.assertEqual(snap['clients'][0]['agent'],'Ali')
        self.assertIn('gps',snap['me'])

    def test_client_detail_returns_real_history_and_events(self):
        self.add_client();cid=self.db.execute('SELECT id FROM clients').fetchone()[0]
        core.record(self.db,2,2,cid,'delivery',1,2,0,'',9101,currency='USD')
        detail=agent_api.client_detail(self.db,2,cid,self.now)
        self.assertEqual(detail['client']['name'],'Baraka')
        self.assertGreaterEqual(len(detail['visits']),1)
        self.assertEqual(detail['events'][0]['kind'],'delivery')


if __name__=='__main__':
    unittest.main()
