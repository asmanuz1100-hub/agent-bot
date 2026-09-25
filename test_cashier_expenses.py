import time
import unittest
from unittest.mock import patch

import bot
import core


class CashierExpenseTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [
            (1,'admin','Admin'), (2,'agent','Ali agent'),
            (3,'cashier','Kassir'), (4,'cashier','Second cashier'),
        ])
        self.db.execute("INSERT INTO clients(agent,name,phone) VALUES(?,?,?)",
                        (2,'Client','+998901112233'))

    def tearDown(self):
        self.db.close()

    def message(self, user, text, mid):
        return {'update_id':mid,'message':{
            'message_id':mid, 'date':int(time.time()), 'from':{'id':user},
            'chat':{'id':user,'type':'private'}, 'text':text,
        }}

    def fund_handover(self):
        core.record(self.db,2,2,1,'payment',value=core.money('100'),
                    source=1001,currency='USD')
        core.handover(self.db,2,core.money('60'),1002,currency='USD')
        return self.db.execute('SELECT id FROM handovers').fetchone()[0]

    def test_cash_only_enters_cashbox_after_accept(self):
        hid=self.fund_handover()
        self.assertEqual(core.cashier_balance_usd(self.db),0)
        with patch.object(bot,'send') as send:
            bot.notify_cashiers_handover(self.db,2,hid,core.money('60'))
        self.assertTrue(any(call.args[0]==3 and 'КАССАГА ПУЛ ТОПШИРИШ' in call.args[1]
                            and '🔎 Кўриб чиқиш #' in str(call.args[2])
                            for call in send.call_args_list))
        with patch.object(bot,'send'):
            bot.handle(self.db,self.message(3,f'🔎 Кўриб чиқиш #{hid}',3001))
            bot.handle(self.db,self.message(3,f'✅ Қабул қилиш #{hid}',3002))
        self.assertEqual(core.cashier_balance_usd(self.db),core.money('60'))
        self.assertEqual(core.cash_usd(self.db,2),core.money('40'))
        with self.assertRaises(ValueError):
            core.accept(self.db,4,hid,True)

    def test_reject_does_not_add_cash_and_cannot_double_accept(self):
        hid=self.fund_handover()
        with patch.object(bot,'send'):
            bot.handle(self.db,self.message(3,f'🔎 Кўриб чиқиш #{hid}',3101))
            bot.handle(self.db,self.message(3,f'❌ Рад этиш #{hid}',3102))
        self.assertEqual(core.cashier_balance_usd(self.db),0)
        self.assertEqual(self.db.execute('SELECT status FROM handovers').fetchone()[0],'rejected')
        with self.assertRaises(ValueError):
            core.accept(self.db,4,hid,True)

    def test_only_cashier_can_spend_within_accepted_balance_once(self):
        hid=self.fund_handover()
        category=core.CASHIER_EXPENSE_CATEGORIES[0]
        with self.assertRaisesRegex(ValueError,'етарли'):
            core.add_cashier_expense(self.db,3,core.money('1'),category,'Fuel','',2001)
        core.accept(self.db,3,hid,True)
        with self.assertRaisesRegex(ValueError,'фақат кассир'):
            core.add_cashier_expense(self.db,2,core.money('1'),category,'Fuel','',2002)
        with self.assertRaisesRegex(ValueError,'етарли'):
            core.add_cashier_expense(self.db,3,core.money('61'),category,'Fuel','',2003)
        core.add_cashier_expense(self.db,3,core.money('15.50'),category,'Fuel','',2004)
        self.assertEqual(core.cashier_balance_usd(self.db),core.money('44.50'))
        with self.assertRaisesRegex(ValueError,'аллақачон'):
            core.add_cashier_expense(self.db,3,core.money('15.50'),category,'Fuel','',2004)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cashier_expenses').fetchone()[0],1)

    def test_expense_wizard_sends_admin_notification_and_history(self):
        hid=self.fund_handover()
        core.accept(self.db,3,hid,True)
        messages=[
            ('🧾 Харажат киритиш',4001),
            (core.CASHIER_EXPENSE_CATEGORIES[1],4002),
            ('12.34',4003), ('Fuel for work',4004),
            ('Receipt 15',4005), ('✅ Тасдиқлаш',4006),
        ]
        with patch.object(bot,'send') as send, patch.object(bot,'ADMINS',{1}):
            for txt,mid in messages:
                bot.handle(self.db,self.message(3,txt,mid))
        self.assertTrue(any(c.args[0]==1 and 'КАССА ХАРАЖАТИ' in c.args[1]
                            for c in send.call_args_list))
        self.assertEqual(core.cashier_balance_usd(self.db),core.money('47.66'))
        with patch.object(bot,'send') as send:
            bot.handle(self.db,self.message(1,'📋 Харажатлар тарихи',4010))
        self.assertIn('Fuel for work',send.call_args.args[1])
        self.assertFalse(bot.allowed(self.db,1,'cashier_expense'))
