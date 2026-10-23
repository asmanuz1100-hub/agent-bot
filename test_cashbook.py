"""Kassa kengaytmasi: kirim, o'tkazma, bank, bekor qilish, kun yopish, jurnal. Eski tarix qayta hisoblanmaydi."""
import unittest

import cashbook
import core
import hr
from test_modules import HttpBase


class CashbookTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'Admin'), (2, 'agent', 'Ali'), (3, 'cashier', 'Kassir')])
        self.db.execute("INSERT INTO meta(key,value) VALUES('cashier_uzs_per_usd','12500')")
        core.pockets_since(self.db)   # yangi korxona: hamyonlar boshidan alohida sanaladi
        # eski tarix: agent 100$ va 1 250 000 so'm topshirgan, kassir 20$ xarajat qilgan
        self.db.execute("INSERT INTO handovers(agent,amount,amount_usd,status,ts,cashier) VALUES(2,0,10000,'accepted',100,3)")
        self.db.execute("INSERT INTO handovers(agent,amount,amount_usd,status,ts,cashier) VALUES(2,125000000,10000,'accepted',101,3)")
        core.add_cashier_expense(self.db, 3, 2000, '📦 Бошқа харажат', 'Do‘kon', '', 11)
        self.db.commit()
        self.n = 0

    def tearDown(self):
        self.db.close()

    def src(self):
        self.n += 1
        return 7000 + self.n

    def snapshot(self):
        return (core.cashier_flows(self.db), core.cashier_balance_usd(self.db),
                core.cashier_source_balance_usd(self.db, 'cash'), core.cashier_source_balance_usd(self.db, 'card'))

    def test_history_unchanged_without_new_moves(self):
        f, bal, cash, card = self.snapshot()
        self.assertEqual((bal, f['bank_uzs'], f['bank_usd']), (18000, 0, 0))
        b = cashbook.balances(self.db)
        self.assertEqual(b['bank_uzs'], 0)
        # yangi yozuv bekor qilinsa ham natija yana avvalgidek
        mid = cashbook.add_income(self.db, 1, 'cash', 'UZS', '500000', 'Boshqa kirim', 'Ta’sischi', '', self.src())
        cashbook.cancel(self.db, 1, mid, 'xato kiritildi')
        self.assertEqual(self.snapshot(), (f, bal, cash, card))

    def test_income_adds_to_pocket_and_legacy_usd(self):
        before = cashbook.balances(self.db)
        cashbook.add_income(self.db, 1, 'cash', 'UZS', '1 000 000', 'Ta’sischi mablag‘i', 'Ta’sischi', 'ustav', self.src())
        cashbook.add_income(self.db, 1, 'bank', 'USD', '250.50', 'Boshqa kirim', 'Mijoz X', '', self.src())
        after = cashbook.balances(self.db)
        self.assertEqual(after['cash_uzs'] - before['cash_uzs'], 1000000)
        self.assertEqual(after['bank_usd'], 25050)
        self.assertEqual(core.cashier_balance_usd(self.db), 18000 + 8000)      # 1 mln so'm / 12 500 = 80 $
        row = self.db.execute("SELECT usd_eq,rate FROM cash_moves WHERE currency='UZS'").fetchone()
        self.assertEqual(tuple(row), (8000, 12500))

    def test_transfer_moves_money_without_income_or_expense(self):
        cashbook.add_transfer(self.db, 1, 'cash', 'bank', 'UZS', '1000000', 'bankka topshirildi', self.src())
        b = cashbook.balances(self.db)
        self.assertEqual((b['cash_uzs'], b['bank_uzs']), (250000, 1000000))
        s = cashbook.summary(self.db, 0, 2**62)
        self.assertEqual(s['internal']['UZS'], 1000000)
        self.assertNotIn('income', s)                                           # o'tkazma daromad emas
        self.assertEqual(s['expense']['USD'], 2000)
        # eski USD hisobida naqd -> bank: umumiy kassa kamaydi, lekin pul yo'qolmadi (bank ichida)
        self.assertEqual(core.cashier_balance_usd(self.db) + cashbook.legacy_usd(self.db, 'bank'), 18000)

    def test_insufficient_and_validation(self):
        with self.assertRaisesRegex(ValueError, 'yetarli'):
            cashbook.add_transfer(self.db, 1, 'card', 'cash', 'USD', '1', '', self.src())
        with self.assertRaises(ValueError):
            cashbook.add_transfer(self.db, 1, 'cash', 'cash', 'UZS', '1', '', self.src())
        with self.assertRaises(ValueError):
            cashbook.add_income(self.db, 1, 'cash', 'USD', '1.001', 'Boshqa kirim', 'x', '', self.src())
        with self.assertRaises(ValueError):
            cashbook.add_income(self.db, 1, 'cash', 'UZS', '10', 'Noma’lum tur', 'x', '', self.src())
        with self.assertRaises(ValueError):
            cashbook.add_income(self.db, 1, 'safe', 'UZS', '10', 'Boshqa kirim', 'x', '', self.src())

    def test_duplicate_request_creates_one_record(self):
        for _ in range(2):
            cashbook.add_income(self.db, 1, 'card', 'USD', '10', 'Boshqa kirim', 'x', '', 4242)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cash_moves').fetchone()[0], 1)

    def test_cancel_keeps_history_and_blocks_negative(self):
        mid = cashbook.add_income(self.db, 1, 'bank', 'USD', '100', 'Boshqa kirim', 'x', '', self.src())
        cashbook.add_transfer(self.db, 1, 'bank', 'card', 'USD', '100', '', self.src())
        with self.assertRaisesRegex(ValueError, 'yetarli'):                      # pul kartaga o'tib ketgan
            cashbook.cancel(self.db, 1, mid, 'xato')
        with self.assertRaises(ValueError):
            cashbook.cancel(self.db, 1, mid, '')                                 # sababsiz yo'q
        tid = self.db.execute("SELECT id FROM cash_moves WHERE kind='transfer'").fetchone()[0]
        cashbook.cancel(self.db, 1, tid, 'qaytarildi')
        cashbook.cancel(self.db, 1, mid, 'xato')
        with self.assertRaises(ValueError):
            cashbook.cancel(self.db, 1, mid, 'yana')
        j = [x for x in cashbook.journal(self.db) if x['type'] in ('income', 'transfer')]
        self.assertEqual({x['status'] for x in j}, {'cancelled'})
        self.assertEqual(j[0]['cancel']['who'], 'Admin')
        self.assertEqual(cashbook.balances(self.db)['bank_usd'], 0)

    def _client_with_debt(self, usd_cents=50000):
        self.db.execute("INSERT INTO clients(id,agent,name,phone) VALUES(77,2,'Do‘kon A','+998900000077')")
        self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,ts,source) VALUES(2,2,77,'delivery',1,1,0,?,50,900001)", (usd_cents,))
        self.db.commit()

    def test_client_payment_reduces_debt_once_and_cancel_restores(self):
        self._client_with_debt(50000)                                   # $500 qarz
        agent_cash = (core.cash_usd(self.db, 2), core.cash(self.db, 2))
        before = cashbook.balances(self.db)
        src = self.src()
        for _ in range(2):                                              # takroriy so'rov — bitta yozuv
            mid = cashbook.add_income(self.db, 1, 'cash', 'USD', '100', cashbook.CLIENT_PAYMENT, '', '', src, client=77)
        self.db.commit()
        self.assertEqual(core.client_debt_usd(self.db, 77), 40000)
        self.assertEqual(cashbook.balances(self.db)['cash_usd'], before['cash_usd'] + 10000)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events WHERE kind='payment'").fetchone()[0], 1)
        self.assertEqual((core.cash_usd(self.db, 2), core.cash(self.db, 2)), agent_cash)   # agent hisobiga tegmaydi
        # so'mda: 1 250 000 / 12 500 = $100
        cashbook.add_income(self.db, 1, 'bank', 'UZS', '1250000', cashbook.CLIENT_PAYMENT, '', '', self.src(), client=77)
        self.assertEqual(core.client_debt_usd(self.db, 77), 30000)
        with self.assertRaises(ValueError):                             # qarzdan ko'p emas
            cashbook.add_income(self.db, 1, 'cash', 'USD', '301', cashbook.CLIENT_PAYMENT, '', '', self.src(), client=77)
        with self.assertRaises(ValueError):                             # mijoz tanlanmagan
            cashbook.add_income(self.db, 1, 'cash', 'USD', '1', cashbook.CLIENT_PAYMENT, 'Kimdir', '', self.src())
        cashbook.cancel(self.db, 1, mid, 'Noto‘g‘ri mijoz')
        self.db.commit()
        self.assertEqual(core.client_debt_usd(self.db, 77), 40000)    # qarz qaytdi
        self.assertEqual(cashbook.balances(self.db)['cash_usd'], before['cash_usd'])
        row = self.db.execute('SELECT status,reversal FROM cash_moves WHERE id=?', (mid,)).fetchone()
        self.assertEqual(row['status'], 'cancelled')
        self.assertIsNotNone(row['reversal'])                           # asl to'lov va teskari yozuv saqlanadi
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events WHERE kind='payment' AND client=77").fetchone()[0], 3)
        with self.assertRaises(ValueError):cashbook.cancel(self.db, 1, mid, 'yana')
        self.assertEqual(core.client_debt_usd(self.db, 77), 40000)

    def test_other_income_does_not_touch_client_debt(self):
        self._client_with_debt(50000)
        cashbook.add_income(self.db, 1, 'cash', 'USD', '100', 'Ta’sischi mablag‘i', 'Ta’sischi', '', self.src())
        self.assertEqual(core.client_debt_usd(self.db, 77), 50000)
        with self.assertRaises(ValueError):
            cashbook.add_income(self.db, 1, 'cash', 'USD', '1', 'Qarz olindi', 'Bank', '', self.src(), client=77)
        self.assertEqual([c['id'] for c in cashbook.debtors(self.db)], [77])

    def test_close_day_records_difference_without_fixing(self):
        before = cashbook.balances(self.db)
        c = cashbook.close_day(self.db, 1, {'cash_uzs': '1200000', 'cash_usd': str(before['cash_usd'] / 100)}, 'kechki sanoq')
        diff = {x['currency']: x['diff'] for x in c}
        self.assertEqual(diff, {'UZS': -50000, 'USD': 0})
        self.assertEqual(cashbook.balances(self.db), before)                    # yashirin tuzatish yo'q
        with self.assertRaisesRegex(ValueError, 'yopilgan'):
            cashbook.close_day(self.db, 1, {'cash_uzs': '1250000'})

    def test_journal_separates_payroll_dividend_and_expenses(self):
        wid = hr.add_worker(self.db, 1, {'name': 'Usta', 'salary': '1000000'})
        hr.add_pay(self.db, 1, wid, 'advance', '125000', source=99, expected_rate=12500)
        core.add_cashier_expense(self.db, 1, 1000, '💰 Дивиденд', 'Ta’sischi', '', 12)
        types = {x['type'] for x in cashbook.journal(self.db)}
        self.assertTrue({'handover', 'expense', 'payroll', 'dividend'} <= types)
        s = cashbook.summary(self.db, 0, 2**62)
        self.assertEqual((s['payroll']['UZS'], s['dividend']['USD'], s['expense']['USD']), (125000, 1000, 2000))


class LegacyOpeningTests(unittest.TestCase):
    """Jonli baza kabi: hamyonlar ajratilishidan oldingi aralash tarix 'opening_usd' da."""
    def test_new_moves_do_not_double_count_opening(self):
        db = core.connect(':memory:')
        db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [(1, 'admin', 'A'), (2, 'agent', 'B'), (3, 'cashier', 'K')])
        db.execute("INSERT INTO meta(key,value) VALUES('cashier_uzs_per_usd','12500')")
        db.execute("INSERT INTO handovers(agent,amount,amount_usd,status,ts,cashier) VALUES(2,0,50000,'accepted',100,3)")
        db.execute("INSERT INTO meta(key,value) VALUES('cashier_pockets_since','1000')")
        db.commit()
        before = core.cashier_flows(db)
        self.assertEqual(before['opening_usd'], 50000)
        cashbook.add_income(db, 1, 'cash', 'UZS', '1250000', 'Boshqa kirim', 'x', '', 501)
        cashbook.add_transfer(db, 1, 'cash', 'bank', 'USD', '100', '', 502)
        after = core.cashier_flows(db)
        self.assertEqual(after['opening_usd'], 50000)                 # eski qoldiq o'zgarmadi
        self.assertEqual((after['cash_uzs'], after['cash_usd'], after['bank_usd']), (1250000, -10000, 10000))
        b = cashbook.balances(db)
        self.assertEqual(b['cash_usd'], 40000)                        # opening ichidan 100$ bankka o'tdi
        db.close()


class CashbookHttpTests(HttpBase):
    def test_permissions_and_flow(self):
        admin, rahbar = self.token(), self.token('second', self.password2)
        code, d = self.post('/api/manager', admin, action='cashbook', op='view')
        self.assertEqual(code, 200, d)
        self.assertTrue(d['can']['income'])
        code, d = self.post('/api/manager', rahbar, action='cashbook', op='income', pocket='cash', currency='USD', amount='5',
                            category='Boshqa kirim', counterparty='x', requestId='cbtest0001')
        self.assertEqual(code, 403, d)                                         # rahbarga standart bo'yicha berilmagan
        code, d = self.post('/api/manager', admin, action='cashbook', op='income', pocket='bank', currency='USD', amount='5',
                            category='Boshqa kirim', counterparty='x', requestId='cbtest0002')
        self.assertEqual(code, 200, d)
        self.assertEqual(d['balances']['bank_usd'], 500)
        code, d = self.post('/api/manager', admin, action='dashboard')
        self.assertEqual(d['cash']['wallets']['bankUsd'], 5)


if __name__ == '__main__':
    unittest.main()
