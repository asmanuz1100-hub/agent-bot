"""Cash and card expenses must consume only their own funding source."""
import unittest

import core
import cashier_api


class CashierSourceBalanceTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.execute("INSERT INTO users(id,role,name) VALUES(3,'cashier','Test')")
        self.db.execute("INSERT INTO meta(key,value) VALUES('cashier_pockets_since','0')")
        self.category = core.CASHIER_EXPENSE_CATEGORIES[0]

    def tearDown(self):
        self.db.close()

    def receipts(self, cash=0, card=0):
        if cash:
            self.db.execute("""INSERT INTO handovers(agent,amount,amount_usd,status,cashier,source,ts,accepted_ts)
                VALUES(2,0,?,'accepted',3,1,1,1)""", (cash,))
        if card:
            self.db.execute("""INSERT INTO cashier_incomes(cashier,amount_usd,category,source_name,source,ts)
                VALUES(3,?,'Test','Test',2,1)""", (card,))

    def spend(self, amount, source, request):
        return core.add_cashier_expense(self.db, 3, amount, self.category, 'Test', '', request, pay_from=source)

    def test_card_expense_does_not_block_remaining_cash(self):
        self.receipts(cash=10000, card=10000)
        self.spend(10000, 'card', 3)
        self.spend(1000, 'cash', 4)
        self.assertEqual(core.cashier_source_balance_usd(self.db, 'cash'), 9000)
        self.assertEqual(core.cashier_source_balance_usd(self.db, 'card'), 0)
        wallets = core.cashier_flows(self.db)
        self.assertEqual((wallets['cash_usd'], wallets['card_usd']), (9000, 0))
        # Existing combined reports subtract each expense exactly once.
        self.assertEqual(core.cashier_balance_usd(self.db) + 10000, 9000)

    def test_card_cannot_spend_cash_receipts(self):
        self.receipts(cash=10000, card=1000)
        with self.assertRaises(ValueError):
            self.spend(1001, 'card', 3)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cashier_expenses').fetchone()[0], 0)

    def test_cash_cannot_spend_card_receipts(self):
        self.receipts(card=10000)
        with self.assertRaises(ValueError):
            self.spend(100, 'cash', 3)
        self.spend(100, 'card', 4)
        self.assertEqual(core.cashier_source_balance_usd(self.db, 'card'), 9900)

    def test_card_limit_uses_remaining_balance(self):
        self.receipts(cash=10000, card=10000)
        self.spend(8000, 'card', 3)
        with self.assertRaises(ValueError):
            self.spend(2001, 'card', 4)
        self.spend(2000, 'card', 5)
        self.assertEqual(core.cashier_source_balance_usd(self.db, 'cash'), 10000)

    def test_uzs_card_expense_does_not_consume_cash(self):
        self.receipts(cash=10000, card=10000)
        core.set_cashier_rate(self.db, 3, 12500, 3)
        core.add_cashier_expense_uzs(self.db, 3, 125000, self.category, 'Test', '', 4,
                                    expected_rate=12500, pay_from='card')
        self.assertEqual(core.cashier_source_balance_usd(self.db, 'cash'), 10000)
        self.assertEqual(core.cashier_source_balance_usd(self.db, 'card'), 9000)
        self.spend(10000, 'cash', 5)

    def test_opening_cash_is_not_reduced_by_card_expenses(self):
        self.receipts(cash=10000, card=10000)
        self.db.execute("UPDATE meta SET value='2' WHERE key='cashier_pockets_since'")
        self.spend(10000, 'card', 3)
        wallets = core.cashier_flows(self.db)
        self.assertEqual(wallets['opening_usd'], 10000)
        self.assertEqual(wallets['cash_usd'], 0)

    def test_dividend_is_available_to_cashier_and_saved_once(self):
        self.receipts(cash=10000)
        category = '💰 Дивиденд'
        self.assertIn(category, cashier_api.dashboard(self.db, 3)['categories'])
        self.assertNotIn(category, core.CASHIER_EXPENSE_CATEGORIES)
        payload = dict(action='expense', requestId='dividend-test-01', payFrom='cash',
                       currency='USD', amount='10.00', category=category, recipient='Test owner')
        cashier_api.mutate(self.db, 3, 'expense', payload)
        self.assertTrue(cashier_api.mutate(self.db, 3, 'expense', payload)['duplicate'])
        row = self.db.execute('SELECT category,amount_usd FROM cashier_expenses').fetchone()
        self.assertEqual(tuple(row), (category, 1000))
        self.assertEqual(core.cashier_source_balance_usd(self.db, 'cash'), 9000)


if __name__ == '__main__':
    unittest.main()
