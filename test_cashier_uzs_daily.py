import time
import unittest
from datetime import datetime
from unittest.mock import patch

import bot
import cashier_daily
import core


class CashierUzsDailyTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Admin'),(2,'agent','Ikbol Agent'),(3,'cashier','Cashier'),
        ])
        self.db.execute("INSERT INTO clients(id,agent,name,shop_name) VALUES(1,2,'Client','Shop')")
        core.record(self.db,2,2,1,'payment',value=core.money('169.40'),
                    source=1001,currency='USD')
        core.handover(self.db,2,core.money('169.40'),1002,currency='USD')
        self.hid=int(self.db.execute("SELECT id FROM handovers").fetchone()[0])

    def tearDown(self):
        self.db.close()

    def message(self,txt,mid,user=3):
        return {'update_id':mid,'message':{'message_id':mid,'date':int(time.time()),
            'from':{'id':user},'chat':{'id':user,'type':'private'},'text':txt}}

    def test_pending_handover_stays_pending_and_expense_blocked_until_cashier_accepts(self):
        self.assertEqual(core.cashier_balance_usd(self.db),0)
        self.assertEqual(self.db.execute('SELECT status FROM handovers').fetchone()[0],'pending')
        with self.assertRaisesRegex(ValueError,'Кассада'):
            core.add_cashier_expense_uzs(self.db,3,62500,core.CASHIER_EXPENSE_CATEGORIES[1],
                                         'Fuel','',3001)
        with patch.object(bot,'send'):
            bot.handle(self.db,self.message('/review 1',3002))
            bot.handle(self.db,self.message('✅ Қабул қилиш #1',3003))
        self.assertEqual(core.cashier_balance_usd(self.db),16940)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events WHERE kind=\'payment\'').fetchone()[0],1)

    def test_rate_and_uzs_expenses_preserve_original_and_snapshot(self):
        self.assertIn('🍽 Тушлик',core.CASHIER_EXPENSE_CATEGORIES)
        self.assertTrue(bot.allowed(self.db,3,'cashier_rate'))
        self.assertTrue(bot.allowed(self.db,3,'cashier_expense_uzs'))
        self.assertFalse(bot.allowed(self.db,1,'cashier_rate'))
        self.assertFalse(bot.allowed(self.db,2,'cashier_expense_uzs'))
        self.assertIsNone(core.cashier_rate(self.db))
        self.assertEqual(core.set_cashier_rate(self.db,3,12500,3005),12500)
        self.assertEqual(core.cashier_rate(self.db),12500)
        core.accept(self.db,3,self.hid,True)
        fuel=core.CASHIER_EXPENSE_CATEGORIES[1]
        lunch=core.CASHIER_EXPENSE_CATEGORIES[2]
        first,first_usd,rate=core.add_cashier_expense_uzs(self.db,3,62500,fuel,'Fuel','',3006,12500)
        self.assertEqual((first_usd,rate),(500,12500))
        self.assertEqual(core.cashier_balance_usd(self.db),16440)
        core.set_cashier_rate(self.db,3,10000,3007)
        second,second_usd,rate=core.add_cashier_expense_uzs(self.db,3,25000,lunch,'Lunch','',3008,10000)
        self.assertEqual((second_usd,rate),(250,10000))
        old=self.db.execute('SELECT currency,amount_usd,amount_uzs,rate_uzs_per_usd FROM cashier_expenses WHERE id=?',(first,)).fetchone()
        self.assertEqual(tuple(old),('UZS',500,62500,12500))
        self.assertEqual(core.cashier_balance_usd(self.db),16190)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cashier_fx_rates').fetchone()[0],2)
        with self.assertRaisesRegex(ValueError,'аллақачон'):
            core.add_cashier_expense_uzs(self.db,3,25000,lunch,'Lunch','',3008,10000)
        with self.assertRaisesRegex(ValueError,'Курс ўзгарган'):
            core.add_cashier_expense_uzs(self.db,3,25000,lunch,'Lunch','',3009,12500)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cashier_expenses').fetchone()[0],2)

    def test_uzs_wizard_notifies_admin_and_daily_totals(self):
        with patch.object(bot,'send') as send,patch.object(bot,'ADMINS',{1}):
            bot.handle(self.db,self.message('💱 Касса курси',4100))
            bot.handle(self.db,self.message('12500',4101))
            bot.handle(self.db,self.message('✅ Тасдиқлаш',4102))
            self.assertTrue(any(c.args[0]==1 and 'КАССА КУРСИ' in c.args[1] for c in send.call_args_list))
            bot.handle(self.db,self.message('⏳ Тасдиқланмаган пуллар',4103))
            self.assertIn('169.40 USD',send.call_args.args[1])
            bot.handle(self.db,self.message('/review 1',4104))
            bot.handle(self.db,self.message('✅ Қабул қилиш #1',4105))
            self.assertEqual(core.cashier_balance_usd(self.db),16940)
            inputs=['🧾 Сўмда харажат',core.CASHIER_EXPENSE_CATEGORIES[1],
                    '62500','АЗС','Бензин','✅ Тасдиқлаш']
            for index,item in enumerate(inputs):
                bot.handle(self.db,self.message(item,4200+index))
            self.assertTrue(any(c.args[0]==1 and '62,500 сўм' in c.args[1] and
                                '5.00 USD' in c.args[1] for c in send.call_args_list))
            bot.handle(self.db,self.message('📊 Кунлик касса',4300))
            daily=send.call_args.args[1]
        self.assertIn('Кунлик касса'.upper(),daily)
        self.assertIn('169.40 USD',daily)
        self.assertIn('62 500 сўм',daily)
        self.assertIn('5.00 USD',daily)
        self.assertIn('164.40 USD',daily)
        self.assertIn('1 USD = 12 500 сўм',daily)
        self.assertEqual(core.cashier_balance_usd(self.db),16440)
        with patch.object(bot,'send') as send:
            bot.cashier_expenses_report(self.db,3)
            self.assertIn('62,500 сўм',send.call_args.args[1])
            self.assertIn('12,500 сўм',send.call_args.args[1])

    def test_old_usd_expense_and_daily_not_mix_original_currencies(self):
        core.set_cashier_rate(self.db,3,12000,5000)
        core.accept(self.db,3,self.hid,True)
        core.add_cashier_expense(self.db,3,300,core.CASHIER_EXPENSE_CATEGORIES[4],'Office','',5001)
        core.add_cashier_expense_uzs(self.db,3,12000,core.CASHIER_EXPENSE_CATEGORIES[1],
                                     'Gas','',5002)
        daily=cashier_daily.report(self.db)
        self.assertIn('Бугун сўмдаги харажат: 12 000 сўм',daily)
        self.assertIn('Бугун USD харажати: 3.00 USD',daily)
        self.assertIn('жами USD эквиваленти: 4.00 USD',daily)
        self.assertIn('165.40 USD',daily)

    def test_notification_outage_after_cashier_click_does_not_rollback_confirmation(self):
        with patch.object(bot,'send'):
            bot.handle(self.db,self.message('/review 1',6001))
        with patch.object(bot,'send',side_effect=RuntimeError('Telegram unavailable')),patch.object(bot,'ADMINS',{1}):
            bot.process_update(self.db,self.message('✅ Қабул қилиш #1',6002))
        self.assertEqual(self.db.execute('SELECT status FROM handovers').fetchone()[0],'accepted')
        self.assertEqual(core.cashier_balance_usd(self.db),16940)


if __name__=='__main__':
    unittest.main()
