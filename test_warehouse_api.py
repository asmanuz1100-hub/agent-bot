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

    def test_miniapp_is_served(self):
        code,body,ctype,_=bot.miniapp_response('/app/ombor/')
        self.assertEqual(code,200)
        self.assertIn(b'/api/warehouse',body)
        self.assertTrue(ctype.startswith('text/html'))


if __name__=='__main__':
    unittest.main()
