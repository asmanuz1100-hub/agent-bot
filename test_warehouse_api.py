import time
import unittest
from unittest.mock import patch

import core
import bot
import warehouse
import warehouse_api as api


def msg(i,uid,text):
    return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),'from':{'id':uid},
            'chat':{'id':uid,'type':'private'},'text':text}}


class WarehouseApiTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1,'admin','Rahbar'),(2,'agent','Ali'),(3,'cashier','Kassir'),(5,'warehouse','Omborchi'),(6,'agent','Vali')])
        self.db.commit()
        self.block=next(p for p in core.PRODUCTS if core.block_units(p))
        self.plain=next(p for p in core.PRODUCTS if not core.block_units(p))

    def tearDown(self):self.db.close()

    def call(self,actor,action,**payload):
        try:
            data=api.handle(self.db,actor,action,payload)
            self.db.commit()
            return data
        except Exception:
            self.db.rollback()
            raise

    def test_dashboard_and_report_work_with_products_without_block(self):
        # Regression: snapshot/report_text used to crash on emulsions (no block size).
        self.call(5,'receive',pack=self.plain,qty=7,requestId='recv-plain-01')
        d=self.call(5,'dashboard')
        self.assertEqual(d['mode'],'keeper')
        plain=next(p for p in d['products'] if p['pack']==self.plain)
        self.assertEqual((plain['stock'],plain['block']),(7,0))
        self.assertIn('7 дона',warehouse.report_text(self.db))

    def test_only_keeper_admin_and_agent_can_use_it(self):
        for actor in (3,99):
            with self.assertRaises(ValueError):self.call(actor,'dashboard')
        with self.assertRaises(ValueError):self.call(2,'receive',pack=self.plain,qty=5)
        with self.assertRaises(ValueError):self.call(5,'request',kind='need',pack=self.plain,qty=5)
        self.assertEqual(self.call(1,'dashboard')['mode'],'keeper')
        self.assertEqual(self.call(2,'dashboard')['mode'],'agent')
        # Rahbar panelni ko‘radi, lekin tovar harakatini faqat omborchi kiritadi.
        for action,payload in (('receive',{'pack':self.plain,'qty':1}),('issue',{'agent':2,'pack':self.plain,'qty':1}),
                               ('writeoff',{'pack':self.plain,'qty':1,'note':'x'}),('take_back',{'agent':2,'pack':self.plain,'qty':1})):
            with self.assertRaisesRegex(ValueError,'faqat omborchi'):self.call(1,action,**payload)

    def test_receive_many_products_at_once(self):
        block=core.block_units(self.block)
        items=[{'pack':self.plain,'qty':4},{'pack':self.block,'qty':2,'unit':'Блок'}]
        d=self.call(5,'receive',items=items,note='Partiya',requestId='recv-multi-01')
        self.assertEqual(len(d['moves']),2)
        self.call(5,'receive',items=items,requestId='recv-multi-01')  # double tap
        self.assertEqual((warehouse.stock(self.db,self.plain),warehouse.stock(self.db,self.block)),(4,2*block))
        # Bitta qator xato bo'lsa, hech narsa yozilmaydi.
        with self.assertRaises(ValueError):
            self.call(5,'receive',items=[{'pack':self.plain,'qty':1},{'pack':self.plain,'qty':0}],requestId='recv-multi-02')
        self.assertEqual(warehouse.stock(self.db,self.plain),4)
        with self.assertRaises(ValueError):self.call(5,'receive',items=[],requestId='recv-multi-03')

    def test_receive_issue_writeoff_with_blocks_and_idempotency(self):
        block=core.block_units(self.block)
        self.call(5,'receive',pack=self.block,qty=3,unit='Блок',requestId='recv-block-01')
        self.call(5,'receive',pack=self.block,qty=3,unit='Блок',requestId='recv-block-01')  # double tap
        self.assertEqual(warehouse.stock(self.db,self.block),3*block)
        d=self.call(5,'issue',agent=2,pack=self.block,qty=block,requestId='issue-blk-01')
        self.assertEqual(d['_notify'][0][0],{2})
        self.assertEqual(warehouse.stock(self.db,self.block),2*block)
        self.assertEqual(core.agent_stock(self.db,2,self.block),block)
        with self.assertRaises(ValueError):self.call(5,'writeoff',pack=self.block,qty=1,requestId='off-nonote-1')
        self.call(5,'writeoff',pack=self.block,qty=1,note='Синган',requestId='off-note-001')
        self.assertEqual(warehouse.stock(self.db,self.block),2*block-1)
        with self.assertRaises(ValueError):self.call(5,'issue',agent=2,pack=self.block,qty=10**5,requestId='issue-big-01')
        with self.assertRaises(ValueError):self.call(5,'issue',agent=3,pack=self.block,qty=1,requestId='issue-cash-1')
        with self.assertRaises(ValueError):self.call(5,'receive',pack=self.plain,qty=1,unit='Блок',requestId='blk-plain-01')

    def test_agent_request_need_and_return_flow_with_notifications(self):
        self.call(5,'receive',pack=self.plain,qty=20,requestId='recv-0000001')
        d=self.call(2,'request',kind='need',pack=self.plain,qty=8,note='Эртага',requestId='need-0000001')
        again=self.call(2,'request',kind='need',pack=self.plain,qty=8,requestId='need-0000001')
        self.assertEqual(d['created'],again['created'])
        self.assertIn(5,d['_notify'][0][0]);self.assertIn(1,d['_notify'][0][0])
        k=self.call(5,'dashboard')
        self.assertEqual([r['id'] for r in k['requests']],[d['created']])
        res=self.call(5,'decide',id=d['created'],accepted=True,qty=6)
        self.assertEqual(res['_notify'][0][0],{2})
        self.assertEqual(core.agent_stock(self.db,2,self.plain),6)
        self.assertEqual(warehouse.stock(self.db,self.plain),14)
        with self.assertRaises(ValueError):self.call(5,'decide',id=d['created'],accepted=True)
        # return: cannot reserve more than free stock
        with self.assertRaises(ValueError):self.call(2,'request',kind='return',pack=self.plain,qty=7,requestId='ret-too-many')
        r=self.call(2,'request',kind='return',pack=self.plain,qty=4,requestId='ret-0000001')['created']
        self.assertEqual(next(p for p in self.call(2,'my')['products'] if p['pack']==self.plain)['free'],2)
        self.call(5,'decide',id=r,accepted=True)
        self.assertEqual(core.agent_stock(self.db,2,self.plain),2)
        self.assertEqual(warehouse.stock(self.db,self.plain),18)
        rej=self.call(2,'request',kind='need',pack=self.plain,qty=1,requestId='need-0000002')['created']
        self.call(5,'decide',id=rej,accepted=False)
        statuses={x['id']:x['status'] for x in self.call(2,'my')['requests']}
        self.assertEqual(statuses[rej],'rejected')

    def order(self,items,source):
        cid=self.db.execute("SELECT id FROM clients WHERE phone='+998900000777'").fetchone()
        if not cid:
            self.db.execute("INSERT INTO clients(agent,name,shop_name,phone,address,created_ts) VALUES(2,'Vali','Baraka','+998900000777','Qo‘qon',?)",
                            (int(time.time()),))
            cid=self.db.execute("SELECT id FROM clients WHERE phone='+998900000777'").fetchone()
        oid,_=core.create_order(self.db,2,int(cid[0]),items,source=source)
        self.db.commit()
        return oid

    def test_keeper_prepares_and_loads_orders_from_warehouse_stock(self):
        oid=self.order([{'pack':self.plain,'qty':6}],-501)
        d=self.call(5,'dashboard')
        o=d['orders']['list'][0]
        self.assertEqual((o['id'],o['status'],o['client_name'],o['ready']),(oid,'new','Baraka',False))
        self.assertNotIn('totalCents',o)                       # omborchi narxlarni ko‘rmaydi
        self.assertEqual(next(p for p in d['products'] if p['pack']==self.plain)['demand'],6)
        r=self.call(5,'order_status',id=oid,to='preparing')
        self.assertEqual(r['_orders'],[oid])
        with self.assertRaisesRegex(ValueError,'yetarli emas'):self.call(5,'order_status',id=oid,to='loaded')
        self.assertEqual(core.agent_stock(self.db,2,self.plain),0)
        self.call(5,'receive',pack=self.plain,qty=10,requestId='recv-order-1')
        self.assertTrue(self.call(5,'dashboard')['orders']['list'][0]['ready'])
        self.call(5,'order_status',id=oid,to='loaded')
        self.assertEqual((warehouse.stock(self.db,self.plain),core.agent_stock(self.db,2,self.plain)),(4,6))
        self.assertEqual(self.call(5,'orders',status='loaded')['orders']['list'][0]['id'],oid)
        self.assertEqual(self.call(5,'dashboard')['orders']['list'],[])
        with self.assertRaises(ValueError):self.call(5,'order_status',id=oid,to='loaded')
        self.assertEqual(warehouse.stock(self.db,self.plain),4)
        rej=self.order([{'pack':self.plain,'qty':1}],-502)
        with self.assertRaisesRegex(ValueError,'sababini'):self.call(5,'order_status',id=rej,to='rejected')
        self.call(5,'order_status',id=rej,to='rejected',note='Mahsulot yo‘q')
        self.assertEqual(self.call(5,'orders',status='rejected')['orders']['list'][0]['admin_note'],'Mahsulot yo‘q')
        with self.assertRaises(ValueError):self.call(2,'order_status',id=rej,to='new')
        with self.assertRaises(ValueError):self.call(5,'order_status',id=rej,to='delivered')

    def test_take_back_respects_pending_returns_and_moves_filter(self):
        self.call(5,'receive',pack=self.plain,qty=10,requestId='recv-take-01')
        self.call(5,'issue',agent=2,pack=self.plain,qty=5,requestId='issue-take-1')
        self.call(2,'request',kind='return',pack=self.plain,qty=3,requestId='ret-take-001')
        with self.assertRaisesRegex(ValueError,'2 dona'):
            self.call(5,'take_back',agent=2,pack=self.plain,qty=3,requestId='take-000001')
        d=self.call(5,'take_back',agent=2,pack=self.plain,qty=2,requestId='take-000002')
        self.call(5,'take_back',agent=2,pack=self.plain,qty=2,requestId='take-000002')  # double tap
        self.assertEqual(d['_notify'][0][0],{2})
        self.assertEqual((warehouse.stock(self.db,self.plain),core.agent_stock(self.db,2,self.plain)),(7,3))
        moves=self.call(5,'moves',kind='agent_return')['moves']
        self.assertEqual([(m['kind'],m['qty'],m['agent']) for m in moves],[('agent_return',2,2)])
        self.assertEqual(len(self.call(5,'moves',pack=self.plain)['moves']),3)
        self.assertEqual(self.call(5,'moves',agent=6)['moves'],[])
        first=self.call(5,'moves')['moves']
        self.assertEqual([m['id'] for m in self.call(5,'moves',before=first[0]['id'])['moves']],[m['id'] for m in first[1:]])
        with self.assertRaises(ValueError):self.call(5,'moves',kind='bad')
        with self.assertRaises(ValueError):self.call(2,'moves')

    def test_today_totals_use_tashkent_calendar_day(self):
        start=warehouse.day_start()
        self.call(5,'receive',pack=self.plain,qty=3,requestId='recv-today-1')
        self.db.execute('UPDATE warehouse_moves SET ts=?',(start-60,));self.db.commit()
        self.call(5,'receive',pack=self.plain,qty=2,requestId='recv-today-2')
        self.assertEqual(self.call(5,'dashboard')['today'],{'in':2})
        self.assertEqual(warehouse.day_start(1760650000),1760641200)   # 2025-10-17 00:00 Asia/Tashkent

    def test_launch_resets_old_agent_stock_to_zero_once(self):
        # Eski tarix: agentga tovar berilgan va minusga topshirilgan (eski qoida).
        self.db.execute("INSERT INTO clients(id,agent,name,phone,address,created_ts) VALUES(70,2,'X','+998900000780','X',0)")
        self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,ts) VALUES(1,2,NULL,'load',?,5,0,0,1)",(self.plain,))
        self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,ts) VALUES(2,2,70,'delivery',?,8,0,800,2)",(self.plain,))
        self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,ts) VALUES(1,6,NULL,'load',?,4,0,0,3)",(self.block,))
        self.db.execute("DELETE FROM meta WHERE key=?",(warehouse.STOCK_RESET_KEY,))
        debt=core.client_debt_usd(self.db,70)
        self.assertEqual((core.agent_stock(self.db,2,self.plain),core.agent_stock(self.db,6,self.block)),(-3,4))
        self.assertEqual(warehouse.reset_agent_stock_once(self.db),2)
        self.assertEqual((core.agent_stock(self.db,2,self.plain),core.agent_stock(self.db,6,self.block)),(0,0))
        self.assertEqual(core.client_debt_usd(self.db,70),debt)
        self.assertEqual(warehouse.reset_agent_stock_once(self.db),0)   # faqat bir marta
        self.call(5,'receive',pack=self.plain,qty=5,requestId='recv-reset-01')
        self.call(5,'issue',agent=2,pack=self.plain,qty=5,requestId='issue-reset-1')
        self.assertEqual(core.agent_stock(self.db,2,self.plain),5)
        self.assertEqual(next(p for p in self.call(2,'my')['products'] if p['pack']==self.plain)['stock'],5)

    def test_manager_sees_warehouse_stock_and_issued_goods(self):
        import manager_api
        self.call(5,'receive',pack=self.plain,qty=20,requestId='recv-mgr-0001')
        self.call(5,'issue',agent=2,pack=self.plain,qty=6,requestId='issue-mgr-001')
        self.call(5,'issue',agent=6,pack=self.plain,qty=3,requestId='issue-mgr-002')
        self.db.execute("UPDATE warehouse_moves SET ts=? WHERE source=(SELECT MAX(source) FROM warehouse_moves WHERE kind='issue' AND qty=3)",
                        (warehouse.day_start()-60,))
        self.db.commit()
        st=manager_api.warehouse(self.db)['stock']
        row=next(p for p in st['products'] if p['pack']==self.plain)
        self.assertEqual((row['stock'],row['issuedToday']),(11,6))
        self.assertEqual(st['stockTotal'],11)
        if warehouse.day_start()-60>=warehouse.month_start():   # kecha ham shu oyda bo‘lsa
            self.assertEqual((row['issuedMonth'],st['issuedMonth']),(9,9))

    def test_bad_input_is_rejected(self):
        for payload in ({'pack':'x','qty':1},{'pack':self.plain,'qty':0},{'pack':self.plain,'qty':1.5},
                        {'pack':self.plain,'qty':True},{'pack':self.plain,'qty':1,'requestId':'bad id!'}):
            with self.assertRaises(ValueError):self.call(5,'receive',**payload)


class WarehouseBotTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1,'admin','A'),(2,'agent','B'),(3,'cashier','C'),(5,'warehouse','W')])
    def tearDown(self):self.db.close()

    def buttons(self,uid):
        return [b for row in bot.menu(self.db,uid) for b in row]

    def test_menu_buttons_per_role(self):
        self.assertIn('📱 Омбор Mini App',self.buttons(1))
        self.assertIn('📱 Омбор Mini App',self.buttons(5))
        self.assertIn('📦 Омбор сўрови',self.buttons(2))
        self.assertFalse({'📱 Омбор Mini App','📦 Омбор сўрови'}&set(self.buttons(3)))
        self.assertEqual(bot.menu_button_for('warehouse')['web_app']['url'],bot.WAREHOUSE_MINIAPP_URL)
        self.assertIn('/app/ombor/',bot.WAREHOUSE_MINIAPP_URL)

    def test_launch_buttons_send_signed_inline_webapp(self):
        with patch.object(bot,'api') as tg:
            bot.handle(self.db,msg(1,5,'📱 Омбор Mini App'))
            bot.handle(self.db,msg(2,2,'📦 Омбор сўрови'))
        urls=[c.kwargs['reply_markup']['inline_keyboard'][0][0]['web_app']['url'] for c in tg.call_args_list]
        self.assertEqual(urls,[bot.WAREHOUSE_MINIAPP_URL]*2)
        with patch.object(bot,'api'),self.assertRaises(ValueError):
            bot.handle(self.db,msg(3,3,'📱 Омбор Mini App'))

    def test_http_endpoint_auth_roles_and_notify_after_commit(self):
        import io,json
        from unittest.mock import MagicMock
        from test_manager_api import signed_data
        captured={}
        def server(address,handler):
            captured['handler']=handler
            return MagicMock()
        with patch.object(bot,'HTTPServer',side_effect=server),patch.object(bot,'api'),patch.object(bot,'TOKEN','test-token'):
            bot.serve_webhook(self.db,'https://example.test')
        def post(payload):
            raw=json.dumps(payload).encode()
            h=object.__new__(captured['handler'])
            h.path='/api/warehouse';h.headers={'Content-Length':str(len(raw))};h.rfile=io.BytesIO(raw)
            result={}
            h._reply=lambda code,body,ctype=None,extra_headers=None:result.update(code=code,data=json.loads(body))
            with patch.object(bot,'TOKEN','test-token'):h.do_POST()
            return result
        pack=next(iter(core.PRODUCTS))
        self.assertEqual(post({'action':'dashboard'})['code'],401)
        self.assertEqual(post({'initData':signed_data('test-token',3)})['code'],403)
        keeper={'initData':signed_data('test-token',5)}
        self.assertEqual(post(keeper)['data']['mode'],'keeper')
        self.assertEqual(post({**keeper,'action':'receive','pack':pack,'qty':5,'requestId':'http-recv-01'})['code'],200)
        self.assertEqual(post({**keeper,'action':'issue','agent':2,'pack':pack,'qty':99,'requestId':'http-issue-9'})['code'],400)
        sent=[]
        def notify(ids,text):
            self.assertFalse(self.db.in_transaction)
            sent.append(set(ids))
        with patch.object(bot,'_safe_send_many',side_effect=notify):
            r=post({**keeper,'action':'issue','agent':2,'pack':pack,'qty':2,'requestId':'http-issue-1'})
        self.assertEqual(r['code'],200);self.assertNotIn('_notify',r['data'])
        self.assertEqual(sent,[{2}])
        self.assertEqual(core.agent_stock(self.db,2,pack),2)
        agent=post({'initData':signed_data('test-token',2)})
        self.assertEqual(agent['data']['mode'],'agent')
        # Order status from the keeper: the agent is told only after the commit.
        self.db.execute("INSERT INTO clients(agent,name,phone,address,created_ts) VALUES(2,'Vali','+998900000778','X',0)")
        cid=self.db.execute("SELECT id FROM clients WHERE phone='+998900000778'").fetchone()[0]
        oid,_=core.create_order(self.db,2,cid,[{'pack':pack,'qty':1}],source=-601);self.db.commit()
        told=[]
        def order_notify(db,order_id):
            self.assertFalse(self.db.in_transaction)
            told.append(order_id)
        with patch.object(bot,'notify_agent_order_status',side_effect=order_notify):
            r=post({**keeper,'action':'order_status','id':oid,'to':'loaded','requestId':'http-order-1'})
        self.assertEqual(r['code'],200);self.assertNotIn('_orders',r['data'])
        self.assertEqual(told,[oid])
        self.assertEqual(core.agent_stock(self.db,2,pack),3)

    def test_new_order_reaches_keepers_with_ombor_hint(self):
        self.db.execute("INSERT INTO clients(agent,name,phone,address,created_ts) VALUES(2,'Vali','+998900000779','X',0)")
        cid=self.db.execute("SELECT id FROM clients WHERE phone='+998900000779'").fetchone()[0]
        oid,_=core.create_order(self.db,2,cid,[{'pack':next(iter(core.PRODUCTS)),'qty':2}],source=-602)
        sent=[]
        with patch.object(bot,'_safe_send_many',side_effect=lambda ids,text:sent.append((list(ids),text))):
            bot.notify_admins_order(self.db,2,oid)
        # Adminlar ro‘yxatiga ADMIN_IDS muhit o‘zgaruvchisidagi adminlar ham qo‘shiladi (Render build).
        self.assertEqual(len(sent),2)
        self.assertIn(1,sent[0][0]);self.assertNotIn(5,sent[0][0])
        self.assertEqual(sent[1][0],[5])
        self.assertIn('Раҳбар Mini App',sent[0][1])
        self.assertIn('Омбор Mini App',sent[1][1]);self.assertNotIn('Раҳбар',sent[1][1])

    def test_miniapp_is_served(self):
        code,body,ctype,_=bot.miniapp_response('/app/ombor/')
        self.assertEqual(code,200)
        self.assertIn(b'/api/warehouse',body)
        self.assertTrue(ctype.startswith('text/html'))


if __name__=='__main__':
    unittest.main()
