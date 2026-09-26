import json
import time
import unittest
from unittest.mock import patch
import core
import bot
import cashier_api as api

class CashierMiniAppTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[(1,'admin','Rahbar'),(2,'agent','Ali'),(3,'cashier','Kassir'),(4,'cashier','Other')])
        self.db.execute("INSERT INTO clients(id,agent,name) VALUES(1,2,'Shop')")
        core.record(self.db,2,2,1,'payment',value=10000,source=1,currency='USD')
        core.handover(self.db,2,6000,2,currency='USD')
        self.hid=self.db.execute('SELECT id FROM handovers').fetchone()[0]
        self.db.commit()

    def tearDown(self):self.db.close()

    def mutate(self,action,actor=3,**payload):
        payload={'action':action,'requestId':'request-0001',**payload}
        try:
            result=api.mutate(self.db,actor,action,payload)
            self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            raise

    def fund(self):
        api.review(self.db,3,self.hid);self.db.commit()
        self.mutate('accept',handoverId=self.hid)

    def test_cashier_only_and_read_only_dashboard(self):
        for actor in (1,2,99):
            with self.assertRaises(ValueError):api.dashboard(self.db,actor)
            with self.assertRaises(ValueError):api.review(self.db,actor,self.hid)
            with self.assertRaises(ValueError):self.mutate('rate',actor=actor,rate='12500')
        d=api.dashboard(self.db,3)
        self.assertEqual(d['balance'],0)
        self.assertEqual(len(d['pending']),1)
        self.assertIn('daily',d)

    def test_accept_requires_review_and_cannot_double_count(self):
        with self.assertRaises(ValueError):self.mutate('accept',handoverId=self.hid)
        self.fund()
        self.assertEqual(core.cashier_balance_usd(self.db),6000)
        self.assertTrue(self.mutate('accept',handoverId=self.hid)['duplicate'])
        with self.assertRaises(ValueError):self.mutate('reject',handoverId=self.hid)
        with self.assertRaises(ValueError):api.review(self.db,4,self.hid)
        self.assertEqual(core.cash_usd(self.db,2),4000)

    def test_reject_and_expired_review(self):
        api.review(self.db,3,self.hid)
        self.db.execute("UPDATE meta SET value='1' WHERE key LIKE 'cashier_review:%'");self.db.commit()
        with self.assertRaises(ValueError):self.mutate('reject',handoverId=self.hid)
        api.review(self.db,3,self.hid);self.db.commit()
        result=self.mutate('reject',handoverId=self.hid)
        self.assertEqual(result['_notify']['agent'],2)
        self.assertEqual(core.cashier_balance_usd(self.db),0)
        self.assertEqual(core.cash_usd(self.db,2),10000)

    def test_expense_idempotency_and_balance_limit(self):
        self.fund()
        p=dict(requestId='expense-0001',currency='USD',amount='10.25',category=core.CASHIER_EXPENSE_CATEGORIES[0],recipient='Fuel')
        self.mutate('expense',**p)
        self.assertTrue(self.mutate('expense',**p)['duplicate'])
        self.assertEqual(core.cashier_balance_usd(self.db),4975)
        with self.assertRaises(ValueError):self.mutate('expense',**{**p,'requestId':'expense-0002','amount':'60'})
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cashier_expenses').fetchone()[0],1)
        with self.assertRaises(ValueError):self.mutate('income',amount='100')

    def test_uzs_rate_change_rejected_then_stored_at_confirmed_rate(self):
        self.fund()
        self.mutate('rate',requestId='rate-00001',rate='12500')
        p=dict(requestId='expense-0002',currency='UZS',amount='125000',expectedRate=12000,category=core.CASHIER_EXPENSE_CATEGORIES[0],recipient='Fuel')
        with self.assertRaisesRegex(ValueError,'Курс ўзгарган'):self.mutate('expense',**p)
        self.mutate('expense',**{**p,'expectedRate':12500})
        row=self.db.execute('SELECT * FROM cashier_expenses').fetchone()
        self.assertEqual((row['amount_usd'],row['amount_uzs'],row['rate_uzs_per_usd']),(1000,125000,12500))

    def test_http_authentication_and_commit_before_notification(self):
        import io
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
            h.path='/api/cashier';h.headers={'Content-Length':str(len(raw))};h.rfile=io.BytesIO(raw)
            result={}
            h._reply=lambda code,body,ctype=None,extra_headers=None:result.update(code=code,data=json.loads(body))
            with patch.object(bot,'TOKEN','test-token'):h.do_POST()
            return result
        self.assertEqual(post({'action':'dashboard'})['code'],401)
        self.assertEqual(post({'initData':signed_data('test-token',2)})['code'],403)
        auth={'initData':signed_data('test-token',3)}
        self.assertEqual(post(auth)['code'],200)
        self.assertEqual(post({**auth,'action':'review','handoverId':self.hid})['code'],200)
        def notify(*args):
            self.assertFalse(self.db.in_transaction)
            raise RuntimeError('Notification unavailable')
        with patch.object(bot,'_safe_send_many',side_effect=notify):
            result=post({**auth,'action':'accept','handoverId':self.hid,'requestId':'http-00001'})
        self.assertEqual(result['code'],200)
        self.assertEqual(core.cashier_balance_usd(self.db),6000)

    def test_launcher_uses_signed_inline_button(self):
        self.assertIn('📱 Кассир Mini App',[x for row in bot.menu(self.db,3) for x in row])
        msg={'message':{'from':{'id':3},'chat':{'id':3,'type':'private'},'text':'📱 Кассир Mini App','date':int(time.time())}}
        with patch.object(bot,'api') as send:
            bot.handle(self.db,msg)
            self.assertEqual(send.call_args.kwargs['reply_markup']['inline_keyboard'][0][0]['web_app']['url'],bot.CASHIER_MINIAPP_URL)
        msg['message']['from']['id']=2;msg['message']['chat']['id']=2
        with self.assertRaises(ValueError):bot.handle(self.db,msg)

if __name__=='__main__':unittest.main()
