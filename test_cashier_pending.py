import unittest
from datetime import datetime
from unittest.mock import patch

import bot
import cashier_pending
import core


class CashierUnconfirmedTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [
            (1,'admin','Admin'),(2,'agent','Agent A'),
            (3,'cashier','Cashier'),(4,'agent','Agent B'),
        ])
        base = int(datetime(2026,9,23,10,0,tzinfo=cashier_pending.TZ).timestamp())
        self.base = base
        amounts = (6640,1320,3000,4280,1700)
        self.db.executemany('INSERT INTO clients(id,agent,name,phone,shop_name) VALUES(?,?,?,?,?)',[
            (i,2,f'Customer {i}',f'+9989000000{i:02d}',f'Shop {i}') for i in range(1,8)
        ])
        for n,cents in enumerate(amounts,1):
            self.db.execute("""INSERT INTO events(actor,agent,client,kind,amount_usd,ts,source)
                     VALUES(2,2,?,'payment',?,?,?)""",
                     (n,cents,base+n*100,1000+n))
        self.db.execute("""INSERT INTO handovers(agent,amount,amount_usd,status,ts,source)
                       VALUES(2,0,16940,'pending',?,2000)""",(base+1000,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,amount_usd,ts,source)
                      VALUES(2,2,6,'payment',4640,?,2001)""",(base+2000,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,amount_usd,ts,source)
                      VALUES(2,2,6,'payment',6640,?,2002)""",(base+2100,))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,amount_usd,ts,source)
                      VALUES(4,4,7,'payment',6240,?,3000)""",(base+3000,))

    def tearDown(self):
        self.db.close()

    def test_existing_pending_handover_shows_five_customer_payments_but_does_not_auto_accept(self):
        row=self.db.execute("SELECT * FROM handovers WHERE id=1").fetchone()
        details=cashier_pending.handover_context(self.db,row)
        for n in range(1,6):
            self.assertIn(f'Shop {n}',details)
        self.assertIn('169.40 USD',details)
        self.assertNotIn('Shop 6',details)
        self.assertIn('боғланмаган',details)
        with patch.object(bot,'send') as send:
            bot.review_handover(self.db,3,1)
        self.assertIn('Shop 1',send.call_args.args[1])
        self.assertIn('169.40 USD',send.call_args.args[1])
        self.assertEqual(self.db.execute("SELECT status FROM handovers WHERE id=1").fetchone()[0],"pending")
        self.assertEqual(core.cashier_balance_usd(self.db),0)

    def test_cashier_and_admin_see_unconfirmed_and_unsubmitted_distinctly_with_customer_names(self):
        self.assertTrue(bot.allowed(self.db,3,'cashier_pending'))
        self.assertTrue(bot.allowed(self.db,1,'cashier_pending'))
        self.assertFalse(bot.allowed(self.db,2,'cashier_pending'))
        before=self.db.execute('SELECT COUNT(*) FROM handovers').fetchone()[0]
        with patch.object(bot,'send') as send:
            bot.handle(self.db,{'update_id':4000,'message':{
                'message_id':4000,'date':self.base+4000,'from':{'id':3},
                'chat':{'id':3,'type':'private'},'text':'⏳ Тасдиқланмаган пуллар'}})
        report=send.call_args.args[1]
        keys=send.call_args.args[2]
        self.assertIn('169.40 USD',report)
        self.assertIn('🔎 Кўриб чиқиш #1',str(keys))
        self.assertIn('💰 Кассир бўлими',str(keys))
        self.assertIn('112.80 USD',report)
        self.assertIn('62.40 USD',report)
        self.assertIn('175.20 USD',report)
        self.assertIn('Agent A',report)
        self.assertIn('Agent B',report)
        self.assertIn('Shop 5',report)
        self.assertIn('Shop 6',report)
        self.assertIn('Shop 7',report)
        self.assertIn('касса қолдиғига киритилмаган',report)
        self.assertIn('/review 1',report)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM handovers').fetchone()[0],before)
        self.assertEqual(core.cashier_balance_usd(self.db),0)

    def test_review_button_opens_confirmation_and_accepts(self):
        with patch.object(bot,'send') as send:
            bot.handle(self.db,{'update_id':4100,'message':{
                'message_id':4100,'date':self.base+4100,'from':{'id':3},
                'chat':{'id':3,'type':'private'},'text':'🔎 Кўриб чиқиш #1'}})
        self.assertIn('✅ Қабул қилиш #1',str(send.call_args.args[2]))
        self.assertIn('❌ Рад этиш #1',str(send.call_args.args[2]))
        with patch.object(bot,'send'):
            bot.handle(self.db,{'update_id':4101,'message':{
                'message_id':4101,'date':self.base+4101,'from':{'id':3},
                'chat':{'id':3,'type':'private'},'text':'✅ Қабул қилиш #1'}})
        row=self.db.execute("SELECT status,cashier FROM handovers WHERE id=1").fetchone()
        self.assertEqual(row['status'],'accepted')
        self.assertEqual(row['cashier'],3)

    def test_after_accepting_money_report_removes_pending_without_creating_another_payment(self):
        core.accept(self.db,3,1,True)
        report=cashier_pending.report(self.db)
        self.assertIn('Кассир тасдиғини кутаётган топшириқлар: 0.00 USD',report)
        self.assertIn('Касса қабул қилган 169.40 USD',report)
        self.assertIn('Топшириш сўровисиз қолган ҳисобий сумма: 112.80 USD',report)
        self.assertNotIn('🔎 Кўриб чиқиш: /review 1',report)
        self.assertEqual(core.cashier_balance_usd(self.db),16940)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events WHERE kind='payment'").fetchone()[0],8)

    def test_cashier_menu_contains_pending_button(self):
        self.assertIn('⏳ Тасдиқланмаган пуллар',str(bot.menu(self.db,3)))
        self.assertNotIn('⏳ Тасдиқланмаган пуллар',str(bot.menu(self.db,2)))


if __name__ == '__main__':
    unittest.main()
