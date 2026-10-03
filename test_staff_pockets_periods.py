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
        self.assertEqual(summary['wallets'], {'cashUzs': 1000000, 'cashUsd': 5000, 'cardUzs': 240000, 'cardUsd': 0})
        rep = cashier_api.period_report(self.db, 3, {'period': 'today'})
        self.assertEqual(rep['flows']['in_cash_uzs'], 1200000)
        self.assertEqual(rep['flows']['out_expense_uzs'], 200000)
        self.assertEqual({r['kind'] for r in rep['rows']}, {'in_cash', 'in_card', 'out_expense'})
        dash = manager_api.dashboard(self.db)
        self.assertEqual(dash['cash']['wallets']['cashUzs'], 1000000)

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
