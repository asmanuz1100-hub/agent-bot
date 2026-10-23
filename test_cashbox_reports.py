"""Kassaga to'g'ridan mijoz to'lovi (events.agent bo'sh) barcha hisobot va panellarni buzmasin."""
import json
import time
import unittest

import analytics
import cashbook
import core
import executive
import manager_api
import sales


class CashboxPaymentReportsTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [(1, 'admin', 'Admin'), (2, 'agent', 'Ali'), (3, 'cashier', 'Kassir')])
        self.db.execute("INSERT INTO meta(key,value) VALUES('cashier_uzs_per_usd','12500')")
        self.db.execute("INSERT INTO clients(id,agent,name,phone,region,created_ts) VALUES(7,2,'Do‘kon','+998900000007','Qo‘qon',1)")
        now = int(time.time())
        self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,ts,source) VALUES(2,2,7,'delivery',1,1,0,50000,?,1)", (now - 60,))
        mid = cashbook.add_income(self.db, 1, 'cash', 'USD', '100', cashbook.CLIENT_PAYMENT, '', '', 77001, client=7)
        cashbook.add_income(self.db, 1, 'cash', 'USD', '50', cashbook.CLIENT_PAYMENT, '', '', 77002, client=7)
        cashbook.cancel(self.db, 1, mid, 'test')
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_dashboards_and_reports_survive(self):
        for fn in (lambda: manager_api.dashboard(self.db),
                   lambda: manager_api.period_report(self.db, 'month', None, None),
                   lambda: executive.executive(self.db, 'today', None, None),
                   lambda: executive.executive(self.db, 'month', None, None),
                   lambda: sales.sales(self.db, 'month', None, None),
                   lambda: analytics.insights(self.db) if hasattr(analytics, 'insights') else {}):
            json.dumps(fn(), default=str)
        import agent_api, client_ledger
        for fn in (lambda: manager_api.client_detail(self.db, 7), lambda: agent_api.client_detail(self.db, 2, 7),
                   lambda: client_ledger.summary(self.db, 7), lambda: client_ledger.recent_text(self.db, 7)):
            json.dumps(fn(), default=str)
        self.assertEqual(core.client_debt_usd(self.db, 7), 45000)


if __name__ == '__main__':
    unittest.main()
