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
        core.fund_agent_expense(self.db,3,2,core.money('40'),'Yo‘l uchun',91003)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_snapshot_exposes_wallet_balance_categories_and_history(self):
        snap=agent_api.snapshot(self.db,2)
        wallet=snap['expenseWallet']
        self.assertEqual(wallet['balanceUsd'],40.0)
        self.assertIn('⛽ Ёқилғи',wallet['categories'])
        self.assertEqual(wallet['history'][0]['kind'],'topup')
        self.assertEqual(wallet['history'][0]['amountUsd'],40.0)
        self.assertEqual(wallet['history'][0]['actor'],'Kassir')

    def test_agent_expense_mutation_spends_wallet_without_double_reducing_cashbox(self):
        cashbox_before=core.cashier_balance_usd(self.db)
        out=agent_api.mutate(self.db,2,'agent_expense',{
            'category':'⛽ Ёқилғи','amount':'15','note':'Benzin'
        },'expense_req_12345')
        self.assertTrue(out['ok'])
        self.assertEqual(out['balanceUsd'],25.0)
        self.assertEqual(out['_notify']['kind'],'agent_expense')
        self.assertEqual(core.agent_fund_balance_usd(self.db,2),core.money('25'))
        self.assertEqual(core.cashier_balance_usd(self.db),cashbox_before)

    def test_agent_expense_is_idempotent_and_requires_note_and_balance(self):
        first=agent_api.mutate(self.db,2,'agent_expense',{
            'category':'🚚 Йўл харажати','amount':'10','note':'Taksi'
        },'expense_req_99999')
        self.db.commit()
        duplicate=agent_api.mutate(self.db,2,'agent_expense',{
            'category':'🚚 Йўл харажати','amount':'10','note':'Taksi'
        },'expense_req_99999')
        self.assertTrue(first['ok'])
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM agent_funds WHERE kind='expense'").fetchone()[0],1)
        with self.assertRaisesRegex(ValueError,'izoh'):
            agent_api.mutate(self.db,2,'agent_expense',{
                'category':'🚚 Йўл харажати','amount':'1','note':''
            },'expense_req_nonote')
        self.db.rollback()
        with self.assertRaisesRegex(ValueError,'етарли|yetarli'):
            agent_api.mutate(self.db,2,'agent_expense',{
                'category':'🚚 Йўл харажати','amount':'1000','note':'Juda katta'
            },'expense_req_large1')


if __name__=='__main__':
    unittest.main()
