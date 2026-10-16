import unittest

import agent_api
import core


class AgentMiniAppExpenseWalletTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Rahbar'),(2,'agent','Ali'),(3,'cashier','Kassir')])
        self.db.execute("INSERT INTO clients(id,agent,name,shop_name,address,created_ts,map_only) VALUES(1,2,'Mijoz','Baraka','Qo‘qon',1,0)")
        core.record(self.db,2,2,1,'payment',value=core.money('100'),source=91001,currency='USD')
        core.handover(self.db,2,core.money('100'),91002,currency='USD')
        hid=int(self.db.execute('SELECT id FROM handovers').fetchone()[0])
        core.accept(self.db,3,hid,True)
        core.set_cashier_rate(self.db,3,12500,91003)
        core.fund_agent_expense_uzs(self.db,3,2,500000,'Yo‘l uchun',91004,expected_rate=12500)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_snapshot_exposes_wallet_balance_categories_and_history(self):
        snap=agent_api.snapshot(self.db,2)
        wallet=snap['expenseWallet']
        self.assertEqual(wallet['balanceUzs'],500000)
        self.assertEqual(wallet['balanceUsd'],40.0)
        self.assertIn('⛽ Ёқилғи',wallet['categories'])
        self.assertEqual(wallet['history'][0]['kind'],'topup')
        self.assertEqual(wallet['history'][0]['amountUzs'],500000)
        self.assertEqual(wallet['history'][0]['amountUsd'],40.0)
        self.assertEqual(wallet['history'][0]['rateUzsPerUsd'],12500)
        self.assertEqual(wallet['history'][0]['actor'],'Kassir')

    def test_agent_expense_mutation_spends_wallet_without_double_reducing_cashbox(self):
        cashbox_before=core.cashier_balance_usd(self.db)
        out=agent_api.mutate(self.db,2,'agent_expense',{
            'category':'⛽ Ёқилғи','amount':'187500','expectedRate':'12500','note':'Benzin'
        },'expense_req_12345')
        self.assertTrue(out['ok'])
        self.assertEqual(out['balanceUzs'],312500)
        self.assertEqual(out['convertedUsd'],15.0)
        self.assertEqual(out['_notify']['kind'],'agent_expense')
        self.assertEqual(core.agent_fund_balance_uzs(self.db,2),312500)
        self.assertEqual(core.cashier_balance_usd(self.db),cashbox_before)

    def test_agent_expense_is_idempotent_and_requires_note_and_balance(self):
        first=agent_api.mutate(self.db,2,'agent_expense',{
            'category':'🚚 Йўл харажати','amount':'125000','expectedRate':'12500','note':'Taksi'
        },'expense_req_99999')
        self.db.commit()
        duplicate=agent_api.mutate(self.db,2,'agent_expense',{
            'category':'🚚 Йўл харажати','amount':'125000','expectedRate':'12500','note':'Taksi'
        },'expense_req_99999')
        self.assertTrue(first['ok'])
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM agent_funds WHERE kind='expense'").fetchone()[0],1)
        with self.assertRaisesRegex(ValueError,'izoh'):
            agent_api.mutate(self.db,2,'agent_expense',{
                'category':'🚚 Йўл харажати','amount':'12500','expectedRate':'12500','note':''
            },'expense_req_nonote')
        self.db.rollback()
        with self.assertRaisesRegex(ValueError,'етарли|yetarli'):
            agent_api.mutate(self.db,2,'agent_expense',{
                'category':'🚚 Йўл харажати','amount':'10000000','expectedRate':'12500','note':'Juda katta'
            },'expense_req_large1')


if __name__=='__main__':
    unittest.main()
