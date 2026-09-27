import time
import unittest
from unittest.mock import patch

import bot
import cashier_api
import core


class AgentExpenseWalletTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Rahbar'),(2,'agent','Ali Agent'),(3,'cashier','Kassir'),(4,'agent','Vali Agent')])
        self.db.execute("INSERT INTO clients(id,agent,name) VALUES(1,2,'Shop')")
        core.record(self.db,2,2,1,'payment',value=core.money('100'),source=1001,currency='USD')
        core.handover(self.db,2,core.money('100'),1002,currency='USD')
        self.hid=int(self.db.execute('SELECT id FROM handovers').fetchone()[0])
        core.accept(self.db,3,self.hid,True)
        core.set_cashier_rate(self.db,3,12500,1901)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_cashier_funds_agent_then_agent_spends_without_double_cashbox_deduction(self):
        self.assertEqual(core.cashier_balance_usd(self.db),core.money('100'))
        fid,fund_usd,rate=core.fund_agent_expense_uzs(self.db,3,2,375000,'Road advance',2001,expected_rate=12500)
        self.assertGreater(fid,0)
        self.assertEqual(rate,12500)
        self.assertEqual(fund_usd,core.money('30'))
        self.assertEqual(core.cashier_balance_usd(self.db),core.money('70'))
        self.assertEqual(core.agent_fund_balance_uzs(self.db,2),375000)

        eid,expense_usd,expense_rate=core.add_agent_expense_uzs(
            self.db,2,156250,core.CASHIER_EXPENSE_CATEGORIES[1],'Fuel',2002,expected_rate=12500)
        self.assertGreater(eid,0)
        self.assertEqual(expense_usd,core.money('12.50'))
        self.assertEqual(expense_rate,12500)
        self.assertEqual(core.agent_fund_balance_uzs(self.db,2),218750)
        self.assertEqual(core.cashier_balance_usd(self.db),core.money('70'))

    def test_permissions_and_balance_limits(self):
        with self.assertRaises(ValueError):
            core.fund_agent_expense_uzs(self.db,2,4,12500,'bad',2101,expected_rate=12500)
        with self.assertRaises(ValueError):
            core.add_agent_expense_uzs(self.db,3,12500,core.CASHIER_EXPENSE_CATEGORIES[0],'bad',2102,expected_rate=12500)
        with self.assertRaisesRegex(ValueError,'етарли'):
            core.add_agent_expense_uzs(self.db,2,12500,core.CASHIER_EXPENSE_CATEGORIES[0],'Fuel',2103,expected_rate=12500)
        with self.assertRaisesRegex(ValueError,'етарли'):
            core.fund_agent_expense_uzs(self.db,3,2,1262500,'too much',2104,expected_rate=12500)

    def test_bot_permissions_and_agent_balance_view(self):
        self.assertTrue(bot.allowed(self.db,3,'agent_fund'))
        self.assertTrue(bot.allowed(self.db,1,'agent_fund'))
        self.assertTrue(bot.allowed(self.db,2,'agent_expense'))
        self.assertTrue(bot.allowed(self.db,2,'agent_expense_balance'))
        self.assertFalse(bot.allowed(self.db,3,'agent_expense'))
        self.assertIn('🧾 Харажат қилиш',sum(bot.menu(self.db,2),[]))
        self.assertIn('💼 Харажат ҳисобим',sum(bot.menu(self.db,2),[]))
        with patch.object(bot,'send') as send:
            bot.show_cashier_menu(self.db,3)
        self.assertIn('💳 Агентга пул',sum(send.call_args.args[2],[]))

        core.fund_agent_expense_uzs(self.db,3,2,250000,'Travel',2201,expected_rate=12500)
        msg={'message':{'message_id':1,'date':int(time.time()),'from':{'id':2},
                       'chat':{'id':2,'type':'private'},'text':'💼 Харажат ҳисобим'}}
        with patch.object(bot,'send') as send:
            bot.handle(self.db,msg)
        self.assertIn('250,000 сўм',send.call_args.args[1])

    def test_cashier_api_funds_agent_and_exposes_wallet_history(self):
        result=cashier_api.mutate(self.db,3,'fund',{
            'action':'fund','requestId':'fund-api-0001','agentId':2,'amount':'312500','expectedRate':'12500','note':'Fuel advance'})
        self.db.commit()
        self.assertEqual(result['_notify']['agent'],2)
        self.assertEqual(core.agent_fund_balance_uzs(self.db,2),312500)
        d=cashier_api.dashboard(self.db,3)
        ali=next(x for x in d['agents'] if x['id']==2)
        self.assertEqual(ali['fund_balance_uzs'],312500)
        self.assertEqual(ali['fund_balance'],core.money('25'))
        self.assertEqual(d['agentFunds'][0]['kind'],'topup')
        self.assertEqual(d['agentFunds'][0]['agent_name'],'Ali Agent')

    def test_cashier_miniapp_contains_agent_funding_ui(self):
        html=open('cashier-miniapp.html',encoding='utf-8').read()
        self.assertIn('Агентга пул',html)
        self.assertIn('agentFundForm',html)
        self.assertIn("action:'fund'",html)
        self.assertIn('Сумма (UZS)',html)
        self.assertIn('expectedRate:data.rate',html)


if __name__=='__main__':
    unittest.main()
