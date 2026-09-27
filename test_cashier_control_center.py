import unittest
import time

import cashier_api
import core


class CashierControlCenterTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Rahbar'),(2,'agent','Ali'),(3,'cashier','Kassir'),(4,'agent','Vali')])
        self.db.execute("INSERT INTO clients(id,agent,name) VALUES(1,2,'Shop')")
        core.record(self.db,2,2,1,'payment',value=core.money('100'),source=1001,currency='USD')
        core.handover(self.db,2,core.money('100'),1002,currency='USD')
        hid=int(self.db.execute('SELECT id FROM handovers').fetchone()[0])
        core.accept(self.db,3,hid,True)
        core.fund_agent_expense(self.db,3,2,core.money('20'),'Road',1003)
        core.add_agent_expense(self.db,2,core.money('5'),core.CASHIER_EXPENSE_CATEGORIES[1],'Fuel',1004)
        core.add_cashier_expense(self.db,3,core.money('10'),core.CASHIER_EXPENSE_CATEGORIES[4],'Office','Paper',1005)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_dashboard_summary_matches_cash_and_agent_wallet_ledgers(self):
        data=cashier_api.dashboard(self.db,3)
        s=data['summary']
        self.assertEqual(s['acceptedToday'],core.money('100'))
        self.assertEqual(s['cashExpenseToday'],core.money('10'))
        self.assertEqual(s['fundedToday'],core.money('20'))
        self.assertEqual(s['cashOutToday'],core.money('30'))
        self.assertEqual(s['netToday'],core.money('70'))
        self.assertEqual(s['agentWalletTotal'],core.money('15'))
        self.assertEqual(data['balance'],core.money('70'))
        self.assertEqual(s['pendingCount'],0)

    def test_activity_feed_contains_all_cash_control_events(self):
        data=cashier_api.dashboard(self.db,3)
        kinds={x['kind'] for x in data['activity']}
        self.assertTrue({'handover','cash_expense','agent_topup','agent_expense'} <= kinds)
        self.assertLessEqual(len(data['activity']),80)
        timestamps=[x['ts'] for x in data['activity']]
        self.assertEqual(timestamps,sorted(timestamps,reverse=True))

    def test_agent_wallets_are_exposed_for_control_center(self):
        data=cashier_api.dashboard(self.db,3)
        ali=next(x for x in data['agents'] if x['id']==2)
        vali=next(x for x in data['agents'] if x['id']==4)
        self.assertEqual(ali['fund_balance'],core.money('15'))
        self.assertEqual(vali['fund_balance'],0)
        self.assertEqual(data['agents'][0]['id'],2)

    def test_cashier_html_has_android_safe_contrast_and_debtors_module(self):
        html=open('cashier-miniapp.html',encoding='utf-8').read()
        for term in (
            '--tg-bg:var(--tg-theme-bg-color,#f1f5f2)',
            '.balance{background:#174e3b',
            '.card{background:var(--tg-section);color:var(--tg-text)',
            'data-tab="debtors"',
            'id="debtCount"','id="debtTotal"','id="debtAssigned"',
            'id="debtSearch"','id="debtList"',
            'function renderDebtors()',
            'data-assign-debt',
            "action:'assign_debt'",
            'Агентга қарзни олишни топшириш'
        ):
            self.assertIn(term,html)

    def test_cashier_html_has_overview_metrics_and_activity(self):
        html=open('cashier-miniapp.html',encoding='utf-8').read()
        self.assertIn('Касса бошқарув панели',html)
        self.assertIn('agentWalletTotal',html)
        self.assertIn('todayIn',html)
        self.assertIn('todayOut',html)
        self.assertIn('activityFeed',html)
        self.assertIn('Сўнгги пул ҳаракатлари',html)


if __name__=='__main__':
    unittest.main()
