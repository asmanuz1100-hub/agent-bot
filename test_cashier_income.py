import time
import unittest
from unittest.mock import patch

import bot
import cashier_daily
import core


class CashierIncomeTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Admin'),(3,'cashier','Kassir')])

    def tearDown(self):
        self.db.close()

    def message(self,text,mid,user=3):
        return {'update_id':mid,'message':{
            'message_id':mid,'date':int(time.time()),'from':{'id':user},
            'chat':{'id':user,'type':'private'},'text':text}}

    def test_manual_income_funds_cashbox_and_expense(self):
        income=core.add_cashier_income(
            self.db,3,core.money('100'),core.CASHIER_INCOME_CATEGORIES[0],
            'Rahbar','Boshlangich kirim',1001)
        self.assertGreater(income,0)
        self.assertEqual(core.cashier_balance_usd(self.db),core.money('100'))
        core.add_cashier_expense(
            self.db,3,core.money('25'),core.CASHIER_EXPENSE_CATEGORIES[0],
            'Transport','',1002)
        self.assertEqual(core.cashier_balance_usd(self.db),core.money('75'))

    def test_cashier_menu_and_usd_income_wizard(self):
        main=sum(bot.menu(self.db,3),[])
        self.assertIn('💰 Кассир бўлими',main)
        self.assertNotIn('➕ Кирим USD',main)
        with patch.object(bot,'send') as send:
            bot.handle(self.db,self.message('💰 Кассир бўлими',2000))
            keys=send.call_args.args[2]
            flat=sum(keys,[])
            self.assertIn('➕ Кирим USD',flat)
            self.assertIn('➖ Расход USD',flat)

        inputs=[
            ('➕ Кирим USD',2100),
            (core.CASHIER_INCOME_CATEGORIES[2],2101),
            ('80.50',2102),('Rahbar',2103),('Test kirim',2104),
            ('✅ Тасдиқлаш',2105),
        ]
        with patch.object(bot,'send') as send,patch.object(bot,'ADMINS',{1}):
            for text,mid in inputs:
                bot.handle(self.db,self.message(text,mid))
        self.assertEqual(core.cashier_balance_usd(self.db),core.money('80.50'))
        row=self.db.execute('SELECT currency,amount_usd,source_name FROM cashier_incomes').fetchone()
        self.assertEqual(tuple(row),('USD',core.money('80.50'),'Rahbar'))
        self.assertTrue(any(c.args[0]==1 and 'КАССА КИРИМИ' in c.args[1] for c in send.call_args_list))

    def test_uzs_income_uses_saved_rate_and_daily_report(self):
        core.set_cashier_rate(self.db,3,12500,3000)
        inputs=[
            ('➕ Кирим UZS',3100),
            (core.CASHIER_INCOME_CATEGORIES[1],3101),
            ('125000',3102),('Bank',3103),('UZS cash',3104),
            ('✅ Тасдиқлаш',3105),
        ]
        with patch.object(bot,'send'),patch.object(bot,'ADMINS',{1}):
            for text,mid in inputs:
                bot.handle(self.db,self.message(text,mid))
        row=self.db.execute('SELECT currency,amount_uzs,rate_uzs_per_usd,amount_usd FROM cashier_incomes').fetchone()
        self.assertEqual(tuple(row),('UZS',125000,12500,1000))
        self.assertEqual(core.cashier_balance_usd(self.db),1000)
        daily=cashier_daily.report(self.db)
        self.assertIn('қўлда кирим: 10.00 USD',daily)
        self.assertIn('10.00 USD',daily)

    def test_admin_is_read_only_in_cashier_section(self):
        self.assertTrue(bot.allowed(self.db,1,'cashier_menu'))
        self.assertFalse(bot.allowed(self.db,1,'cashier_income'))
        with patch.object(bot,'send') as send:
            bot.show_cashier_menu(self.db,1)
        flat=sum(send.call_args.args[2],[])
        self.assertNotIn('➕ Кирим USD',flat)
        self.assertIn('📊 Кунлик касса',flat)


if __name__=='__main__':
    unittest.main()
