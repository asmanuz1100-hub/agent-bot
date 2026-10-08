"""So'm + dollar payment entry, cashier pockets, period reports, cashier staff management."""
import time
import unittest

import agent_api
import bot
import cashier_api
import core
import manager_api


class StaffPocketsPeriodsTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [
            (1, 'admin', 'Admin'), (2, 'agent', 'Ali'), (3, 'cashier', 'Kassir'), (4, 'agent', 'Vali')])
        self.now = int(time.time()) - 120
        self.db.execute('UPDATE products SET price=? WHERE pack=1', (10000,))
        core.record(self.db, 1, 2, None, 'load', 1, 50, source=7001, currency='USD')
        out = agent_api.mutate(self.db, 2, 'add_client', {
            'shopName': 'Baraka', 'name': 'Vali', 'phone': '+998901234567', 'address': 'Qo‘qon',
            'lat': 40.54, 'lon': 70.94, 'status': 'interested', 'note': 'x'}, 'client_create_1', self.now)
        self.cid = out['clientId']
        core.record(self.db, 2, 2, self.cid, 'delivery', 1, 10, 0, '', 8001, currency='USD')
        core.set_cashier_rate(self.db, 3, 12000, 9001)
        self.db.execute("INSERT INTO meta(key,value) VALUES('cashier_pockets_since','0')")
        self.db.execute('INSERT INTO shifts(id,agent,start,live_id) VALUES(99,2,?,777)', (self.now - 600,))
        self.db.execute('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(99,?,40.54,70.94,8)', (self.now - 30,))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def pay(self, rid, **kw):
        payload = {'clientId': self.cid}
        payload.update(kw)
        return agent_api.mutate(self.db, 2, 'payment', payload, 'req_' + rid + '_000000', self.now)

    # --- agent enters so'm AND dollars, rate is derived --------------------------------
    def test_som_and_usd_entry_credits_exact_dollars_and_derives_rate(self):
        out = self.pay('both_1', currency='UZS', amount='1250000', usd='100', method='cash')
        self.assertTrue(out['ok'])
        self.assertEqual(core.client_debt_usd(self.db, self.cid), 100000 - 10000)
        ev = self.db.execute("SELECT amount_usd,paid_uzs,fx_rate FROM events WHERE kind='payment'").fetchone()
        self.assertEqual(tuple(ev), (10000, 1250000, 12500))
        self.assertEqual(core.cash_som(self.db, 2), 1250000)

    def test_implausible_pair_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'tekshiring'):
            self.pay('both_bad', currency='UZS', amount='1250000', usd='1000', method='cash')
        self.assertEqual(core.client_debt_usd(self.db, self.cid), 100000)

    def test_card_with_som_and_usd(self):
        out = self.pay('both_card', currency='UZS', amount='600000', usd='50', method='card')
        row = self.db.execute('SELECT amount_uzs,amount_usd,rate_uzs_per_usd FROM card_payments WHERE id=?',
                              (out['cardPaymentId'],)).fetchone()
        self.assertEqual(tuple(row), (600000, 5000, 12000))

    # --- cashier pockets ---------------------------------------------------------------
    def test_pockets_keep_som_dollar_and_card_apart(self):
        self.pay('p_som', currency='UZS', amount='1200000', usd='100', method='cash')
        self.pay('p_usd', currency='USD', amount='50', method='cash')
        card = self.pay('p_card', currency='UZS', amount='240000', usd='20', method='card')
        agent_api.mutate(self.db, 2, 'handover', {'currency': 'UZS', 'amount': '1200000'}, 'req_h1_000000', self.now)
        agent_api.mutate(self.db, 2, 'handover', {'currency': 'USD', 'amount': '50'}, 'req_h2_000000', self.now)
        for hid, in self.db.execute("SELECT id FROM handovers").fetchall():
            core.accept(self.db, 3, hid, True)
        core.decide_card_payment(self.db, 3, card['cardPaymentId'], True)
        core.add_cashier_expense_uzs(self.db, 3, 200000, core.CASHIER_EXPENSE_CATEGORIES[0], 'Yo‘l', '', 5551)
        w = core.cashier_flows(self.db)
        self.assertEqual((w['cash_uzs'], w['cash_usd'], w['card_uzs']), (1000000, 5000, 240000))
        summary = cashier_api.dashboard(self.db, 3)['summary']
        self.assertEqual(summary['wallets'], {'cashUzs': 1000000, 'cashUsd': 5000, 'cardUzs': 240000, 'cardUsd': 0,
                                              'openingUsd': 0, 'since': 0})
        rep = cashier_api.period_report(self.db, 3, {'period': 'today'})
        self.assertEqual(rep['flows']['in_cash_uzs'], 1200000)
        self.assertEqual(rep['flows']['out_expense_uzs'], 200000)
        self.assertEqual({r['kind'] for r in rep['rows']}, {'in_cash', 'in_card', 'out_expense'})
        dash = manager_api.dashboard(self.db)
        self.assertEqual(dash['cash']['wallets']['cashUzs'], 1000000)

    def test_pockets_start_from_cutoff_with_opening_balance(self):
        self.db.execute("DELETE FROM meta WHERE key='cashier_pockets_since'")
        self.pay('old_usd', currency='USD', amount='80', method='cash')
        agent_api.mutate(self.db, 2, 'handover', {'currency': 'USD', 'amount': '80'}, 'req_old_000000', self.now)
        core.accept(self.db, 3, self.db.execute('SELECT id FROM handovers').fetchone()[0], True)
        self.db.execute('UPDATE handovers SET accepted_ts=accepted_ts-100')
        core.add_cashier_expense_uzs(self.db, 3, 120000, core.CASHIER_EXPENSE_CATEGORIES[0], 'Old', '', 6001)
        self.db.execute('UPDATE cashier_expenses SET ts=ts-100')
        w = core.cashier_flows(self.db)          # first call fixes the cutoff at "now"
        self.assertGreater(w['since'], 0)
        self.assertEqual((w['cash_uzs'], w['cash_usd']), (0, 0))   # no negative so'm from old rows
        self.assertEqual(w['opening_usd'], 8000 - 1000)
        self.pay('new_som', currency='UZS', amount='600000', usd='50', method='cash')
        agent_api.mutate(self.db, 2, 'handover', {'currency': 'UZS', 'amount': '600000'}, 'req_new_000000', self.now)
        hid = self.db.execute("SELECT id FROM handovers WHERE status='pending'").fetchone()[0]
        core.accept(self.db, 3, hid, True)
        w = core.cashier_flows(self.db)
        self.assertEqual((w['cash_uzs'], w['cash_usd'], w['opening_usd']), (600000, 0, 7000))

    def test_long_period_series_is_bucketed(self):
        rep = manager_api.period_report(self.db, 'custom', '2026-01-01', '2026-03-31')
        self.assertEqual(rep['seriesUnit'], 'haftalik')
        self.assertLessEqual(len(rep['series']), 14)
        rep = manager_api.period_report(self.db, 'custom', '2025-10-01', '2026-09-30')
        self.assertEqual((rep['seriesUnit'], len(rep['series'])), ('oylik', 12))

    def test_card_expense_leaves_cash_and_reduces_card(self):
        card = self.pay('ce_card', currency='UZS', amount='600000', usd='50', method='card')
        core.decide_card_payment(self.db, 3, card['cardPaymentId'], True)
        self.pay('ce_cash', currency='UZS', amount='1200000', usd='100', method='cash')
        agent_api.mutate(self.db, 2, 'handover', {'currency': 'UZS', 'amount': '1200000'}, 'req_ceh_000000', self.now)
        core.accept(self.db, 3, self.db.execute("SELECT id FROM handovers").fetchone()[0], True)
        cashier_api.mutate(self.db, 3, 'expense', {'currency': 'UZS', 'amount': '100000', 'expectedRate': '12000',
                                        'category': core.CASHIER_EXPENSE_CATEGORIES[0], 'recipient': 'Internet',
                                        'payFrom': 'card', 'requestId': 'cardexp_000001'})
        w = core.cashier_flows(self.db)
        self.assertEqual((w['cash_uzs'], w['card_uzs']), (1200000, 500000))
        self.assertEqual(self.db.execute('SELECT pay_from FROM cashier_expenses').fetchone()[0], 'card')
        with self.assertRaises(ValueError):
            cashier_api.mutate(self.db, 3, 'expense', {'currency': 'UZS', 'amount': '1000', 'expectedRate': '12000',
                                            'category': core.CASHIER_EXPENSE_CATEGORIES[0], 'recipient': 'X',
                                            'payFrom': 'bank', 'requestId': 'cardexp_000002'})

    def test_opening_balance_is_folded_into_one_cashbox(self):
        self.db.execute("DELETE FROM meta WHERE key='cashier_pockets_since'")
        self.pay('fold_usd', currency='USD', amount='80', method='cash')
        agent_api.mutate(self.db, 2, 'handover', {'currency': 'USD', 'amount': '80'}, 'req_fold_000000', self.now)
        core.accept(self.db, 3, self.db.execute('SELECT id FROM handovers').fetchone()[0], True)
        self.db.execute('UPDATE handovers SET accepted_ts=accepted_ts-100')
        core.cashier_flows(self.db)
        wallets = cashier_api.dashboard(self.db, 3)['summary']['wallets']
        self.assertEqual((wallets['cashUsd'], wallets['openingUsd'], wallets['since']), (8000, 0, 0))
        mw = manager_api.dashboard(self.db)['cash']['wallets']
        self.assertEqual((mw['cashUsd'], mw['openingUsd']), (80.0, 0))

    # --- periods -----------------------------------------------------------------------
    def test_period_resolver_and_manager_report(self):
        now = int(time.time())
        s, e, _ = core.resolve_period('today', now=now)
        self.assertTrue(s <= now < e)
        s7, _, _ = core.resolve_period('week', now=now)
        self.assertEqual((s - s7) // 3600, 6 * 24)
        sm, _, label = core.resolve_period('month', now=now)
        self.assertIn('oyi', label)
        s, e, label = core.resolve_period('custom', '2026-09-10', '2026-09-01', now=now)
        self.assertEqual((e - s) // 86400, 10)
        with self.assertRaises(ValueError):
            core.resolve_period('custom', 'x', '2026-09-01', now=now)
        self.pay('rep_1', currency='USD', amount='30', method='cash')
        rep = manager_api.period_report(self.db, 'month')
        self.assertEqual(rep['paymentsUsd'], 30.0)
        self.assertIn('cash', rep)
        self.assertTrue(rep['series'])

    # --- cashier staff -----------------------------------------------------------------
    def test_cashier_add_rename_transfer_close(self):
        core.add_cashier(self.db, 1, '555', 'Yangi kassir')
        self.assertEqual(self.db.execute('SELECT role FROM users WHERE id=555').fetchone()[0], 'cashier')
        with self.assertRaisesRegex(ValueError, 'рўйхатдан'):
            core.add_cashier(self.db, 1, 2, 'Agent emas')
        core.rename_cashier(self.db, 1, 555, 'Dilnoza')
        core.transfer_cashier_account(self.db, 1, 555, 777)
        roles = dict(self.db.execute('SELECT id,role FROM users WHERE id IN (555,777)').fetchall())
        self.assertEqual(roles, {555: 'cashier_disabled', 777: 'cashier'})
        self.assertEqual(self.db.execute('SELECT name FROM users WHERE id=777').fetchone()[0], 'Dilnoza')
        core.deactivate_cashier(self.db, 1, 777)
        with self.assertRaisesRegex(ValueError, 'Охирги'):
            core.deactivate_cashier(self.db, 1, 3)
        core.activate_cashier(self.db, 1, 777)
        staff = manager_api.staff_list(self.db)
        self.assertEqual({c['id']: c['active'] for c in staff['cashiers']}, {3: True, 777: True, 555: False})
        self.assertNotIn(555, [a['id'] for a in staff['agents']])
        with self.assertRaises(ValueError):
            core.add_cashier(self.db, 3, 888, 'Kassir qo‘sha olmaydi')

    def test_disabled_cashier_is_blocked_in_bot(self):
        core.add_cashier(self.db, 1, 555, 'K2')
        core.deactivate_cashier(self.db, 1, 555)
        self.assertEqual(bot.role(self.db, 555), 'cashier_disabled')

    # --- premium photo urls --------------------------------------------------------------
    def test_client_detail_exposes_photo_flags(self):
        self.db.execute("UPDATE clients SET photo='file123' WHERE id=?", (self.cid,))
        d = manager_api.client_detail(self.db, self.cid)
        self.assertTrue(d['hasPhoto'])
        bot.attach_client_photo_urls(d)
        self.assertIn('photoUrl', d)


if __name__ == '__main__':
    unittest.main()
