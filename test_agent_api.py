"""Real Agent Mini App API tests: live DB reads, write rules and idempotency."""
import time
import unittest
from datetime import datetime, timedelta
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

    def test_region_persists_on_create_and_edit_and_appears_in_snapshot(self):
        out=agent_api.mutate(self.db,2,'add_client',{
            'shopName':'Hudud do‘koni','name':'Vali','phone':'+998901234569',
            'lat':40.54,'lon':70.94,'region':'Bag‘dod'
        },'region_create_98765',self.now)
        cid=out['clientId']
        self.assertEqual(next(c for c in agent_api.quick_snapshot(self.db,2,self.now)['clients']
                              if c['id']==cid)['region'],'Bag‘dod')
        agent_api.mutate(self.db,2,'client_edit',{
            'clientId':cid,'shop':'Hudud do‘koni','person':'Vali',
            'phone':'+998901234569','region':'Yapan'
        },'region_edit_98765',self.now+1)
        self.assertEqual(next(c for c in agent_api.quick_snapshot(self.db,2,self.now+1)['clients']
                              if c['id']==cid)['region'],'Yapan')

    def test_legacy_address_regions_are_backfilled_once_without_guessing_test_rows(self):
        self.db.execute("DELETE FROM meta WHERE key='client_regions_from_address_20260928'")
        samples=[(1,'Багдод',''),(2,'Учкўприк тумани',''),(3,'Яйпан, Ўзбекистон тумани',''),
                 (4,'Чиркай',''),(5,'Қушқўноқ',''),(6,'Томоша, Фурқат тумани',''),
                 (7,'Тест',''),(8,'Бувайда','Old Region'),(92,'Бағдод тумани','')]
        self.db.executemany('INSERT INTO clients(id,agent,address,region) VALUES(?,2,?,?)',samples)
        core._backfill_existing_client_regions_once(self.db)
        actual={r['id']:r['region'] for r in self.db.execute('SELECT id,region FROM clients').fetchall()}
        self.assertEqual(actual,{1:'Bag‘dod',2:'Uchko‘prik',3:'Yaypan',4:'Furqat',
                                 5:'O‘zbekiston',6:'Furqat',7:'',8:'Old Region',92:''})
        self.db.execute("UPDATE clients SET region='' WHERE id=1")
        core._backfill_existing_client_regions_once(self.db)
        self.assertEqual(self.db.execute('SELECT region FROM clients WHERE id=1').fetchone()[0],'')

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

    def test_snapshot_report_analytics_are_agent_scoped_and_financially_complete(self):
        self.add_client('report_client_123')
        cid=self.db.execute("SELECT id FROM clients WHERE shop_name='Baraka'").fetchone()[0]
        self.db.execute("INSERT INTO clients(agent,name,phone,address,created_ts,map_only) VALUES(4,'Other Shop','+998909876543','X',?,0)",(self.now,))
        other=self.db.execute("SELECT id FROM clients WHERE agent=4").fetchone()[0]

        core.record(self.db,2,2,cid,'delivery',1,4,0,'',8101,currency='USD')
        core.record(self.db,2,2,cid,'sold',1,1,0,'',8102,currency='USD')
        core.record(self.db,2,2,cid,'payment',0,0,500,'',8103,currency='USD')
        core.record(self.db,2,2,cid,'return',1,1,0,'',8104,currency='USD')
        core.record(self.db,4,4,other,'delivery',1,99,0,'',8199,currency='USD')
        self.db.execute('UPDATE events SET ts=? WHERE source BETWEEN 8101 AND 8199',(self.now,))
        self.db.execute("""INSERT INTO agent_funds(agent,actor,kind,amount_usd,category,note,source,ts)
            VALUES(2,2,'expense',125,'Fuel','Test',9101,?)""",(self.now,))
        self.db.execute("""INSERT INTO handovers(agent,amount,amount_usd,status,cashier,source,ts,accepted_ts)
            VALUES(2,0,300,'accepted',3,9201,?,?)""",(self.now,self.now))
        self.db.commit()

        snap=agent_api.snapshot(self.db,2,self.now)
        day=snap['period']['day']
        self.assertEqual(snap['clientCount'],1)
        self.assertEqual(snap['reportAnalytics']['clients']['total'],1)
        self.assertEqual(day['deliveryQty'],4)
        self.assertEqual(day['deliveryUsd'],10)
        self.assertEqual(day['soldQty'],1)
        self.assertEqual(day['returnQty'],1)
        self.assertEqual(day['returnUsd'],2.5)
        self.assertEqual(day['paymentsUsd'],5)
        self.assertEqual(day['expenseUsd'],1.25)
        self.assertEqual(day['handoverAcceptedUsd'],3)
        product=next(x for x in snap['reportAnalytics']['products']['day'] if x['pack']==1)
        self.assertEqual(product['deliveryQty'],4)
        self.assertEqual(product['soldQty'],1)
        self.assertEqual(product['returnQty'],1)
        self.assertEqual(snap['reportAnalytics']['series'][-1]['deliveryQty'],4)

    def test_quick_snapshot_keeps_first_paint_data_without_heavy_histories(self):
        self.add_client('quick_snapshot_client')
        snap=agent_api.quick_snapshot(self.db,2,self.now)
        self.assertTrue(snap['quick'])
        self.assertEqual(snap['me']['id'],2)
        self.assertIn('clients',snap)
        self.assertIn('products',snap)
        self.assertIn('summary',snap)
        self.assertIn('expenseWallet',snap)
        self.assertIn('cashierRateUzsPerUsd',snap)
        self.assertEqual(snap['events'],[])
        self.assertEqual(snap['handovers'],[])
        self.assertEqual(snap['expenseWallet']['history'],[])
        self.assertEqual(snap['reportAnalytics'],{})
        self.assertIn('cashAvailableUsd',snap['summary'])

    def test_collection_tasks_appear_for_agent_and_close_when_debt_paid(self):
        self.add_client('collection_task_client')
        cid=self.db.execute("SELECT id FROM clients WHERE shop_name='Baraka'").fetchone()[0]
        core.record(self.db,2,2,cid,'delivery',1,2,0,'',9701,currency='USD')
        debt=core.client_debt_usd(self.db,cid)
        self.db.execute("""INSERT INTO collection_tasks(client,agent,cashier,debt_usd,note,status,created_ts)
            VALUES(?,?,?,?,?,'open',?)""",(cid,2,3,debt,'Bugun undirilsin',self.now-10))
        snap=agent_api.quick_snapshot(self.db,2,self.now)
        self.assertEqual(len(snap['collectionTasks']),1)
        task=snap['collectionTasks'][0]
        self.assertEqual(task['clientId'],cid)
        self.assertEqual(task['currentDebtUsd'],debt/100)
        self.assertIn('Bugun undirilsin',task['note'])
        self.live_shift()
        agent_api.mutate(self.db,2,'payment',{'clientId':cid,'currency':'USD','amount':str(debt/100)},
                         'collection_pay_123',self.now)
        row=self.db.execute("SELECT status,completed_ts FROM collection_tasks WHERE client=?",(cid,)).fetchone()
        self.assertEqual(row['status'],'done')
        self.assertTrue(row['completed_ts'])
        self.assertEqual(agent_api.quick_snapshot(self.db,2,self.now)['collectionTasks'],[])

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

    def test_add_client_can_store_camera_photo_file_id(self):
        out=agent_api.mutate(self.db,2,'add_client',{
            'shopName':'Foto Shop','name':'Ali Vali',
            'phone':'+998901112244','address':'Qo‘qon',
            'lat':40.54,'lon':70.94,'status':'interested',
            'note':'Kamera orqali olindi',
            'photoFileId':'AgACAgQAAxkBAA_camera_file_123456789'
        },'camera_client_123',self.now)
        self.assertTrue(out['ok'])
        row=self.db.execute("SELECT photo FROM clients WHERE id=?",(out['clientId'],)).fetchone()
        self.assertEqual(row[0],'AgACAgQAAxkBAA_camera_file_123456789')
        snap=agent_api.snapshot(self.db,2,self.now)
        client=next(x for x in snap['clients'] if x['id']==out['clientId'])
        self.assertTrue(client['hasPhoto'])

    def test_fast_wizard_can_create_client_with_initial_products(self):
        out=agent_api.mutate(self.db,2,'add_client',{
            'shopName':'Fast Shop','name':'Vali',
            'phone':'+998901234568','lat':40.54,'lon':70.94,
            'photoFileId':'AgACAgQAAxkBAA_fast_wizard_photo_123456',
            'items':[{'pack':1,'qty':4},{'pack':3,'qty':2}]
        },'wizard_products_123',self.now)
        self.assertTrue(out['ok'])
        self.assertEqual(out['deliveredItems'],2)
        cid=out['clientId']
        row=self.db.execute('SELECT map_only,address,photo FROM clients WHERE id=?',(cid,)).fetchone()
        self.assertEqual(row['map_only'],0)
        self.assertTrue(row['address'].startswith('GPS: '))
        self.assertEqual(row['photo'],'AgACAgQAAxkBAA_fast_wizard_photo_123456')
        self.assertEqual(core.client_stock_total(self.db,cid,1),4)
        self.assertEqual(core.client_stock_total(self.db,cid,3),2)
        self.assertEqual(core.agent_stock(self.db,2,1),26)
        self.assertEqual(core.agent_stock(self.db,2,3),10)
        self.assertEqual(core.client_debt_usd(self.db,cid),2000)
        visit=self.db.execute('SELECT status,note FROM client_visits WHERE client=? ORDER BY id DESC LIMIT 1',(cid,)).fetchone()
        self.assertEqual(visit['status'],'active')
        self.assertIn('Tovar berildi',visit['note'])

    def test_fast_wizard_can_save_no_product_prospect_with_minimal_fields(self):
        out=agent_api.mutate(self.db,2,'add_client',{
            'shopName':'Prospekt Shop','name':'Anvar',
            'phone':'+998901234569','lat':40.55,'lon':70.95,
            'photoFileId':'AgACAgQAAxkBAA_fast_wizard_photo_987654',
            'status':'waiting','followup':(datetime.now().date()+timedelta(days=1)).isoformat()
        },'wizard_prospect_123',self.now)
        self.assertTrue(out['ok'])
        self.assertEqual(out['deliveredItems'],0)
        cid=out['clientId']
        row=self.db.execute('SELECT map_only,address,comment FROM clients WHERE id=?',(cid,)).fetchone()
        self.assertEqual(row['map_only'],1)
        self.assertTrue(row['address'].startswith('GPS: '))
        self.assertIn('mahsulot hozircha berilmadi',row['comment'])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events WHERE client=? AND kind='delivery'",(cid,)).fetchone()[0],0)

    def test_delivery_can_continue_when_agent_stock_becomes_negative(self):
        self.add_client('negative_stock_client')
        cid=self.db.execute("SELECT id FROM clients WHERE shop_name='Baraka'").fetchone()[0]
        out=agent_api.mutate(self.db,2,'delivery',
            {'clientId':cid,'items':[{'pack':1,'qty':35}]},
            'negative_stock_delivery',self.now)
        self.assertTrue(out['ok'])
        self.assertEqual(core.agent_stock(self.db,2,1),-5)
        self.assertEqual(core.client_stock_total(self.db,cid,1),35)
        self.assertEqual(core.client_debt_usd(self.db,cid),8750)

    def test_admin_override_can_use_disabled_agent_actions_without_live_gps(self):
        self.add_client('admin_override_client')
        cid=self.db.execute("SELECT id FROM clients WHERE shop_name='Baraka'").fetchone()[0]
        core.set_agent_feature(self.db,1,2,'delivery',False)
        core.set_agent_feature(self.db,1,2,'payment',False)
        with self.assertRaisesRegex(ValueError,'o‘chirilgan'):
            agent_api.mutate(self.db,2,'delivery',
                {'clientId':cid,'items':[{'pack':1,'qty':1}]},
                'disabled_delivery_normal',self.now)
        delivered=agent_api.mutate(self.db,2,'delivery',
            {'clientId':cid,'items':[{'pack':1,'qty':31}]},
            'disabled_delivery_admin',self.now,admin_override=True)
        self.assertTrue(delivered['ok'])
        self.assertEqual(core.agent_stock(self.db,2,1),-1)
        paid=agent_api.mutate(self.db,2,'payment',
            {'clientId':cid,'amount':'10.00'},
            'payment_admin_override',self.now,admin_override=True)
        self.assertTrue(paid['ok'])
        self.assertEqual(core.cash_usd(self.db,2),1000)

    def test_agent_can_edit_client_profile_without_touching_financial_history(self):
        self.add_client('edit_client_123')
        cid=self.db.execute("SELECT id FROM clients WHERE shop_name='Baraka'").fetchone()[0]
        core.record(self.db,2,2,cid,'delivery',1,4,0,'',9301,currency='USD')
        before_events=self.db.execute("SELECT COUNT(*) FROM events WHERE client=?",(cid,)).fetchone()[0]
        before_debt=core.client_debt_usd(self.db,cid)

        out=agent_api.mutate(self.db,2,'client_edit',{
            'clientId':cid,'shopName':'Yangi Baraka','name':'Valijon',
            'phone':'+998 90 111 22 33, +998 91 444 55 66',
            'address':'Yangi manzil','note':'Telefon yangilandi'
        },'edit_client_profile_123',self.now)
        self.assertTrue(out['ok'])
        row=self.db.execute("SELECT name,shop_name,phone,address,comment FROM clients WHERE id=?",(cid,)).fetchone()
        self.assertEqual(row['name'],'Valijon')
        self.assertEqual(row['shop_name'],'Yangi Baraka')
        self.assertEqual(row['phone'],'+998901112233 · +998914445566')
        self.assertEqual(row['address'],'Yangi manzil')
        self.assertEqual(row['comment'],'Telefon yangilandi')
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events WHERE client=?",(cid,)).fetchone()[0],before_events)
        self.assertEqual(core.client_debt_usd(self.db,cid),before_debt)
        self.assertGreaterEqual(self.db.execute("SELECT COUNT(*) FROM client_edits WHERE client=?",(cid,)).fetchone()[0],5)

    def test_client_edit_updates_photo_and_gps_without_changing_ledger(self):
        self.add_client('edit_photo_gps_123')
        cid=self.db.execute("SELECT id FROM clients WHERE shop_name='Baraka'").fetchone()[0]
        photo_id='AgACAgQAAxkBAA1234567890'
        before_events=self.db.execute('SELECT COUNT(*) FROM events WHERE client=?',(cid,)).fetchone()[0]
        payload={'clientId':cid,'shop':'Baraka','person':'Ali','phone':'+998901112233',
                 'address':'Yangi mo‘ljal','note':'Yangilandi','lat':40.55123,'lon':70.94123,
                 'photoFileId':photo_id}
        result=agent_api.mutate(self.db,2,'client_edit',payload,'edit_photo_gps_update_123',self.now)
        self.assertTrue(result['ok'])
        row=self.db.execute('SELECT lat,lon,photo FROM clients WHERE id=?',(cid,)).fetchone()
        self.assertAlmostEqual(row['lat'],40.55123)
        self.assertAlmostEqual(row['lon'],70.94123)
        self.assertEqual(row['photo'],photo_id)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events WHERE client=?',(cid,)).fetchone()[0],before_events)
        self.assertTrue({'lat','lon','photo'} <= {r[0] for r in self.db.execute(
            'SELECT field FROM client_edits WHERE client=?',(cid,)).fetchall()})
        with self.assertRaisesRegex(ValueError,'fotosi identifikatori'):
            agent_api.mutate(self.db,2,'client_edit',dict(payload,photoFileId='bad'),
                             'edit_bad_photo_123',self.now)
        self.assertEqual(self.db.execute('SELECT photo FROM clients WHERE id=?',(cid,)).fetchone()[0],photo_id)

    def test_uzs_payment_uses_only_cashier_rate_and_books_usd_equivalent(self):
        self.add_client('uzs_payment_client_123')
        cid=self.db.execute("SELECT id FROM clients WHERE shop_name='Baraka'").fetchone()[0]
        core.record(self.db,2,2,cid,'delivery',1,4,0,'',9401,currency='USD')
        self.live_shift()
        core.set_cashier_rate(self.db,3,12800,9402)

        snap=agent_api.snapshot(self.db,2,self.now)
        self.assertEqual(snap['cashierRateUzsPerUsd'],12800)
        out=agent_api.mutate(self.db,2,'payment',{
            'clientId':cid,'currency':'UZS','amount':'64000','expectedRate':'12800'
        },'uzs_payment_12345',self.now)
        self.assertTrue(out['ok'])
        self.assertEqual(out['convertedUsd'],5.0)
        self.assertEqual(out['rateUzsPerUsd'],12800)
        self.assertEqual(core.client_debt_usd(self.db,cid),500)
        event=self.db.execute("SELECT amount_usd,note FROM events WHERE client=? AND kind='payment' ORDER BY id DESC LIMIT 1",(cid,)).fetchone()
        self.assertEqual(event['amount_usd'],500)
        self.assertIn('64000 UZS',event['note'])
        self.assertIn('12800 UZS',event['note'])

    def test_uzs_payment_rejects_missing_or_changed_cashier_rate(self):
        self.add_client('uzs_rate_guard_client')
        cid=self.db.execute("SELECT id FROM clients WHERE shop_name='Baraka'").fetchone()[0]
        self.live_shift()
        with self.assertRaisesRegex(ValueError,'Kassir hali kurs belgilamagan'):
            agent_api.mutate(self.db,2,'payment',{
                'clientId':cid,'currency':'UZS','amount':'50000'
            },'uzs_no_rate_123',self.now)
        core.set_cashier_rate(self.db,3,12500,9501)
        with self.assertRaisesRegex(ValueError,'kursni o‘zgartirdi'):
            agent_api.mutate(self.db,2,'payment',{
                'clientId':cid,'currency':'UZS','amount':'50000','expectedRate':'12400'
            },'uzs_changed_rate_123',self.now)

    def test_delivery_visit_payment_return_and_handover_use_core_rules(self):
        self.add_client();cid=self.db.execute('SELECT id FROM clients').fetchone()[0]
        delivery=agent_api.mutate(self.db,2,'delivery',
            {'clientId':cid,'items':[{'pack':1,'qty':10},{'pack':3,'qty':6}]},
            'delivery_123456',self.now)
        self.assertTrue(delivery['ok'])
        self.assertEqual(core.client_debt_usd(self.db,cid),5500)
        self.assertEqual(core.agent_stock(self.db,2,1),20)
        agent_api.mutate(self.db,2,'visit',
            {'clientId':cid,'status':'waiting','note':'Ertaga kelishildi','followup':(datetime.now().date()+timedelta(days=1)).isoformat()},
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

    def test_period_gps_report_combines_shifts_distance_hours_and_map_segments(self):
        shifts=[
            (201,self.now-600,self.now),
            (202,self.now-3*86400-600,self.now-3*86400),
            (203,self.now-20*86400-600,self.now-20*86400),
        ]
        for sid,start,end in shifts:
            self.db.execute('INSERT INTO shifts(id,agent,start,"end",live_id) VALUES(?,?,?,?,?)',
                            (sid,2,start,end,700+sid))
            self.db.execute('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,?)',
                            (sid,start+100,40.5400,70.9400,8))
            self.db.execute('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,?)',
                            (sid,start+300,40.5410,70.9410,9))
        self.db.execute('INSERT INTO shifts(id,agent,start,end,live_id) VALUES(?,?,?,?,?)',
                        (299,4,self.now-600,self.now,999))
        self.db.execute('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,?)',
                        (299,self.now-300,41.0,71.0,5))

        day=agent_api.route(self.db,2,'day',self.now)
        week=agent_api.route(self.db,2,'week',self.now)
        month=agent_api.route(self.db,2,'month',self.now)

        self.assertEqual(day['shiftCount'],1)
        self.assertEqual(week['shiftCount'],2)
        self.assertEqual(month['shiftCount'],3)
        self.assertEqual(day['workSeconds'],600)
        self.assertEqual(week['workSeconds'],1200)
        self.assertEqual(month['workSeconds'],1800)
        self.assertEqual(day['gpsPoints'],2)
        self.assertEqual(week['gpsPoints'],4)
        self.assertEqual(month['gpsPoints'],6)
        self.assertGreater(day['km'],0)
        self.assertGreater(week['km'],day['km'])
        self.assertGreater(month['km'],week['km'])
        self.assertTrue(day['segments'])
        self.assertEqual(day['segments'][0][0]['lat'],40.54)
        self.assertEqual(day['period'],'day')

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


    def test_offline_mutation_preserves_original_event_and_visit_time(self):
        self.add_client('offline_time_client')
        cid=self.db.execute("SELECT id FROM clients WHERE shop_name='Baraka'").fetchone()[0]
        offline_ts=self.now-120
        self.db.execute('INSERT INTO shifts(id,agent,start,"end",live_id) VALUES(77,2,?,?,700)',
                        (offline_ts-600,offline_ts+600))
        self.db.execute('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(77,?,40.54,70.94,8)',
                        (offline_ts-20,))
        out=agent_api.mutate(self.db,2,'payment',{
            'clientId':cid,'currency':'USD','amount':'1.00','offlineTs':offline_ts
        },'offline_payment_time_123',self.now)
        self.assertTrue(out['ok'])
        event=self.db.execute("SELECT ts FROM events WHERE client=? AND kind='payment' ORDER BY id DESC LIMIT 1",
                              (cid,)).fetchone()
        self.assertEqual(event['ts'],offline_ts)

        agent_api.mutate(self.db,2,'visit',{
            'clientId':cid,'status':'interested','note':'Offline tashrif','offlineTs':offline_ts+5
        },'offline_visit_time_123',self.now)
        visit=self.db.execute("SELECT ts FROM client_visits WHERE client=? ORDER BY id DESC LIMIT 1",
                              (cid,)).fetchone()
        self.assertEqual(visit['ts'],offline_ts+5)

    def test_offline_payment_uses_historical_shift_and_rejects_too_old_time(self):
        self.add_client('offline_history_client')
        cid=self.db.execute("SELECT id FROM clients WHERE shop_name='Baraka'").fetchone()[0]
        op_ts=self.now-3600
        self.db.execute('INSERT INTO shifts(id,agent,start,"end",live_id) VALUES(78,2,?,?,701)',
                        (op_ts-600,op_ts+600))
        self.db.execute('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(78,?,40.54,70.94,8)',
                        (op_ts-25,))
        out=agent_api.mutate(self.db,2,'payment',{
            'clientId':cid,'currency':'USD','amount':'1.00','offlineTs':op_ts
        },'offline_historical_pay_123',self.now)
        self.assertTrue(out['ok'])
        with self.assertRaisesRegex(ValueError,'7 kundan eski'):
            agent_api.mutate(self.db,2,'visit',{
                'clientId':cid,'status':'interested','note':'Eski offline','offlineTs':self.now-8*86400
            },'offline_too_old_12345',self.now)


    def test_custom_period_report_counts_only_selected_days(self):
        self.add_client()
        cid=self.db.execute("SELECT id FROM clients WHERE shop_name='Baraka'").fetchone()[0]
        d1=int(datetime(2026,9,10,12,0,tzinfo=TZ).timestamp())
        d2=int(datetime(2026,9,20,12,0,tzinfo=TZ).timestamp())
        core.record(self.db,2,2,cid,'delivery',1,4,0,'',8501,currency='USD',ts=d1)
        core.record(self.db,2,2,cid,'delivery',1,2,0,'',8502,currency='USD',ts=d2)
        core.record(self.db,2,2,cid,'payment',0,0,500,'',8503,currency='USD',ts=d2)
        rep=agent_api.period_report(self.db,2,'2026-09-15','2026-09-21',self.now)
        self.assertEqual(rep['label'],'15.09.2026 – 21.09.2026')
        self.assertEqual(rep['period']['deliveryQty'],2)
        self.assertEqual(rep['period']['paymentsUsd'],5.0)
        row=next(x for x in rep['products'] if x['pack']==1)
        self.assertEqual(row['deliveryQty'],2)
        both=agent_api.period_report(self.db,2,'2026-09-21','2026-09-01',self.now)
        self.assertEqual(both['period']['deliveryQty'],6)
        with self.assertRaises(ValueError):
            agent_api.period_report(self.db,2,'bad','2026-09-21',self.now)
        with self.assertRaises(ValueError):
            agent_api.period_report(self.db,2,'2024-01-01','2026-09-21',self.now)


    def test_payments_keep_currency_and_card_payments_are_visible(self):
        self.add_client()
        cid=self.db.execute("SELECT id FROM clients WHERE shop_name='Baraka'").fetchone()[0]
        core.record_client_payment(self.db,2,2,cid,'UZS',1_250_000,'cash',usd_cents=10000,source=9101,ts=self.now-60)
        core.record_client_payment(self.db,2,2,cid,'USD',5000,'cash',source=9102,ts=self.now-50)
        core.submit_card_payment(self.db,2,cid,'UZS',600_000,usd_cents=5000,source=9103,ts=self.now-40)
        snap=agent_api.snapshot(self.db,2,self.now)
        pays=[e for e in snap['events'] if e['kind']=='payment']
        uzs=next(e for e in pays if e['paidUzs'])
        self.assertEqual((uzs['paidUzs'],uzs['payMethod']),(1_250_000,'cash'))
        day=snap['period']['day']
        self.assertEqual((day['paymentsUzs'],day['paymentsUsdCash']),(1_250_000,50.0))
        self.assertEqual((day['cardPendingCount'],day['cardPendingUzs']),(1,600_000))
        self.assertEqual(len(snap['summary']['cardPending']),1)
        detail=agent_api.client_detail(self.db,2,cid,self.now)
        self.assertTrue(any(e.get('paidUzs')==1_250_000 for e in detail['events']))


if __name__=='__main__':
    unittest.main()
