import time
import unittest
from unittest.mock import patch

import bot
import cashier_daily
import core


class CashierIncomePolicyTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Admin'),(2,'agent','Agent'),(3,'cashier','Kassir')])
        self.db.execute("INSERT INTO clients(id,agent,name,shop_name) VALUES(1,2,'Client','Shop')")

    def tearDown(self):
        self.db.close()

    def message(self,text,mid,user=3):
        return {'update_id':mid,'message':{
            'message_id':mid,'date':int(time.time()),'from':{'id':user},
            'chat':{'id':user,'type':'private'},'text':text}}

    def test_cashier_menu_has_no_manual_income(self):
        main=sum(bot.menu(self.db,3),[])
        self.assertIn('💰 Кассир бўлими',main)
        with patch.object(bot,'send') as send:
            bot.handle(self.db,self.message('💰 Кассир бўлими',2000))
        flat=sum(send.call_args.args[2],[])
        self.assertNotIn('➕ Кирим USD',flat)
        self.assertNotIn('➕ Кирим UZS',flat)
        self.assertIn('➖ Расход USD',flat)
        self.assertIn('⏳ Тасдиқланмаган пуллар',flat)
        self.assertFalse(bot.allowed(self.db,3,'cashier_income'))
        self.assertFalse(bot.allowed(self.db,3,'cashier_income_uzs'))

    def test_manual_income_functions_are_blocked(self):
        with self.assertRaisesRegex(ValueError,'қўлда кирим қила олмайди'):
            core.add_cashier_income(
                self.db,3,core.money('100'),core.CASHIER_INCOME_CATEGORIES[0],
                'Rahbar','',1001)
        core.set_cashier_rate(self.db,3,12500,1002)
        with self.assertRaisesRegex(ValueError,'қўлда кирим қила олмайди'):
            core.add_cashier_income_uzs(
                self.db,3,125000,core.CASHIER_INCOME_CATEGORIES[0],
                'Rahbar','',1003,12500)
        self.assertEqual(core.cashier_balance_usd(self.db),0)

    def test_legacy_manual_income_does_not_fund_cashbox(self):
        self.db.execute("""INSERT INTO cashier_incomes
            (cashier,amount_usd,category,source_name,note,source,ts)
            VALUES(?,?,?,?,?,?,?)""",
            (3,core.money('500'),core.CASHIER_INCOME_CATEGORIES[0],
             'Legacy','old',1999,int(time.time())))
        self.assertEqual(core.cashier_balance_usd(self.db),0)
        daily=cashier_daily.report(self.db)
        self.assertNotIn('қўлда кирим',daily)

    def test_only_accepted_agent_handover_funds_cashbox(self):
        core.record(self.db,2,2,1,'payment',value=core.money('100'),
                    source=3001,currency='USD')
        core.handover(self.db,2,core.money('80'),3002,currency='USD')
        hid=int(self.db.execute('SELECT id FROM handovers').fetchone()[0])
        self.assertEqual(core.cashier_balance_usd(self.db),0)

        with patch.object(bot,'send'):
            bot.handle(self.db,self.message(f'/review {hid}',3003))
            bot.handle(self.db,self.message(f'✅ Қабул қилиш #{hid}',3004))

        self.assertEqual(core.cashier_balance_usd(self.db),core.money('80'))
        core.add_cashier_expense(
            self.db,3,core.money('10'),core.CASHIER_EXPENSE_CATEGORIES[0],
            'Transport','',3005)
        self.assertEqual(core.cashier_balance_usd(self.db),core.money('70'))

    def test_admin_cashier_section_remains_read_only(self):
        self.assertTrue(bot.allowed(self.db,1,'cashier_menu'))
        with patch.object(bot,'send') as send:
            bot.show_cashier_menu(self.db,1)
        flat=sum(send.call_args.args[2],[])
        self.assertNotIn('➕ Кирим USD',flat)
        self.assertIn('📊 Кунлик касса',flat)


if __name__=='__main__':
    unittest.main()
