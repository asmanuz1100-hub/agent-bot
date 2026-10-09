"""So'm payments at an agreed rate, card payments confirmed by the cashier,
separate so'm / dollar handovers, and how all of it shows in the act sverka."""
import time
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import agent_api
import cashier_api
import client_ledger
import core
import reports

TZ = ZoneInfo('Asia/Tashkent')


class UzsAndCardPaymentTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [
            (1, 'admin', 'Admin'), (2, 'agent', 'Ali'), (3, 'cashier', 'Kassir'), (4, 'agent', 'Other')])
        self.now = int(time.time()) - 120
        self.db.execute('UPDATE products SET price=? WHERE pack=1', (10000,))  # 100.00 USD per pack
        core.record(self.db, 1, 2, None, 'load', 1, 50, source=7001, currency='USD')
        out = agent_api.mutate(self.db, 2, 'add_client', {
            'shopName': 'Baraka', 'name': 'Vali', 'phone': '+998901234567', 'address': 'Qo‘qon',
            'lat': 40.54, 'lon': 70.94, 'status': 'interested', 'note': 'x'}, 'client_create_1', self.now)
        self.cid = out['clientId']
        core.record(self.db, 2, 2, self.cid, 'delivery', 1, 10, 0, '', 8001, currency='USD')  # debt 1000 USD
        core.set_cashier_rate(self.db, 3, 12000, 9001)
        self.db.execute('INSERT INTO shifts(id,agent,start,live_id) VALUES(99,2,?,777)', (self.now - 600,))
        self.db.execute('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(99,?,40.54,70.94,8)', (self.now - 30,))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def pay(self, rid, **kw):
        payload = {'clientId': self.cid}
        if kw.get('method') == 'card':
            payload['photoFileId'] = 'AgACAgIAAxkBAAEreceipt01'   # card payments carry a receipt photo
        payload.update(kw)
        return agent_api.mutate(self.db, 2, 'payment', payload, 'req_' + rid + '_000000', self.now)

    # --- so'm cash at the rate agreed with the client -------------------------------------
    def test_uzs_cash_uses_agent_rate_and_stays_as_som_with_agent(self):
        out = self.pay('pay_uzs_1', currency='UZS', amount='1185000', rate='11850', method='cash')
        self.assertTrue(out['ok'])
        self.assertEqual(core.client_debt_usd(self.db, self.cid), 100000 - 10000)  # 100.00 USD credited
        self.assertEqual(core.cash_som(self.db, 2), 1185000)                          # agent holds so'm
        self.assertEqual(core.cash_usd(self.db, 2), 0)                           # not dollars
        ev = self.db.execute("SELECT amount,amount_usd,paid_uzs,fx_rate,pay_method FROM events WHERE kind='payment'").fetchone()
        self.assertEqual(tuple(ev), (0, 10000, 1185000, 11850, 'cash'))       # legacy UZS column untouched

    def test_rate_typo_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'juda farq'):
            self.pay('pay_uzs_typo', currency='UZS', amount='1185000', rate='1185', method='cash')
        self.assertEqual(core.client_debt_usd(self.db, self.cid), 100000)

    def test_usd_cash_unchanged(self):
        self.pay('pay_usd_1', currency='USD', amount='50', method='cash')
        self.assertEqual(core.client_debt_usd(self.db, self.cid), 95000)
        self.assertEqual(core.cash_usd(self.db, 2), 5000)
        self.assertEqual(core.cash_som(self.db, 2), 0)

    def test_old_cached_app_without_rate_still_works(self):
        out = self.pay('pay_uzs_old', currency='UZS', amount='120000', expectedRate='12000')
        self.assertTrue(out['ok'])
        self.assertEqual(core.client_debt_usd(self.db, self.cid), 100000 - 1000)

    # --- separate handovers ----------------------------------------------------------------
    def test_som_and_dollar_handovers_are_separate_and_cashbook_exact(self):
        self.pay('p1', currency='UZS', amount='1185000', rate='11850', method='cash')   # 100.00 USD
        self.pay('p2', currency='UZS', amount='600000', rate='12000', method='cash')    # 50.00 USD
        self.pay('p3', currency='USD', amount='30', method='cash')                     # 30.00 USD
        self.assertEqual((core.cash_som(self.db, 2), core.cash_usd(self.db, 2)), (1785000, 3000))
        with self.assertRaisesRegex(ValueError, 'эркин пулдан'):
            agent_api.mutate(self.db, 2, 'handover', {'currency': 'USD', 'amount': '31'}, 'req_h_usd_big_000000', self.now)
        agent_api.mutate(self.db, 2, 'handover', {'currency': 'USD', 'amount': '30'}, 'req_h_usd_000000', self.now)
        out = agent_api.mutate(self.db, 2, 'handover', {'currency': 'UZS', 'amount': '1785000'}, 'req_h_uzs_000000', self.now)
        h = self.db.execute('SELECT amount,amount_usd FROM handovers WHERE id=?', (out['handoverId'],)).fetchone()
        self.assertEqual(tuple(h), (178500000, 15000))   # so'm kept in tiyin (legacy unit); exactly the USD credited
        for hid in [r[0] for r in self.db.execute("SELECT id FROM handovers WHERE status='pending'").fetchall()]:
            core.accept(self.db, 3, hid, True)
        self.assertEqual((core.cash_som(self.db, 2), core.cash_usd(self.db, 2)), (0, 0))
        self.assertEqual(core.cashier_balance_usd(self.db), 18000)   # 150 + 30 USD
        s = cashier_api._cashier_summary(self.db)
        self.assertEqual(s['cashUzsFromAgents'], 1785000)

    def test_partial_som_handover_uses_average_agreed_rate(self):
        self.pay('p1', currency='UZS', amount='1185000', rate='11850', method='cash')
        self.pay('p2', currency='UZS', amount='600000', rate='12000', method='cash')
        out = agent_api.mutate(self.db, 2, 'handover', {'currency': 'UZS', 'amount': '892500'}, 'req_h_half_000000', self.now)
        h = self.db.execute('SELECT amount_usd FROM handovers WHERE id=?', (out['handoverId'],)).fetchone()[0]
        self.assertEqual(h, 7500)   # half the so'm -> half the USD value
        out = agent_api.mutate(self.db, 2, 'handover', {'currency': 'UZS', 'amount': '892500'}, 'req_h_rest_000000', self.now)
        h2 = self.db.execute('SELECT amount_usd FROM handovers WHERE id=?', (out['handoverId'],)).fetchone()[0]
        self.assertEqual(h + h2, 15000)   # no cents lost

    def test_snapshot_shows_both_wallets(self):
        self.pay('p1', currency='UZS', amount='1185000', rate='11850', method='cash')
        self.pay('p3', currency='USD', amount='30', method='cash')
        agent_api.mutate(self.db, 2, 'handover', {'currency': 'UZS', 'amount': '185000'}, 'req_h_part_000000', self.now)
        s = agent_api.quick_snapshot(self.db, 2, self.now)['summary']
        self.assertEqual((s['cashOnHandUzs'], s['cashAvailableUzs'], s['cashAvailableUsd']), (1185000, 1000000, 30.0))

    def test_som_handover_is_shown_in_som(self):
        self.pay('p1', currency='UZS', amount='1185000', rate='11850', method='cash')
        out = agent_api.mutate(self.db, 2, 'handover', {'currency': 'UZS', 'amount': '1185000'}, 'req_h_show_000000', self.now)
        row = self.db.execute('SELECT * FROM handovers WHERE id=?', (out['handoverId'],)).fetchone()
        self.assertEqual(core.handover_value_text(row), '1 185 000 сўм (≈ 100.00 USD)')
        import cashier_pending
        self.assertIn('1 185 000 сўм (≈ 100.00 USD)', cashier_pending.report(self.db))
        html = open('cashier-miniapp.html', encoding='utf-8').read()
        self.assertIn("som(Math.round(Number(h.amount)/100))+' сўм'", html)

    def test_legacy_tiyin_cash_and_new_som_add_up(self):
        core.record(self.db, 2, 2, self.cid, 'payment', value=core.money('15000'), source=8100, currency='UZS')
        self.pay('p1', currency='UZS', amount='1185000', rate='11850', method='cash')
        self.assertEqual(core.cash_som(self.db, 2), 1200000)
        out = agent_api.mutate(self.db, 2, 'handover', {'currency': 'UZS', 'amount': '1200000'}, 'req_h_all_000000', self.now)
        core.accept(self.db, 3, out['handoverId'], True)
        self.assertEqual(core.cash(self.db, 2), 0)

    # --- card / bank transfer --------------------------------------------------------------
    def test_card_payment_waits_for_cashier_then_goes_to_bank(self):
        out = self.pay('card_1', currency='UZS', amount='2400000', rate='12000', method='card')
        self.assertTrue(out['pendingConfirmation'])
        self.assertEqual(core.client_debt_usd(self.db, self.cid), 100000)      # not yet
        self.assertEqual((core.cash_som(self.db, 2), core.cash_usd(self.db, 2)), (0, 0))  # never agent cash
        dash = cashier_api.dashboard(self.db, 3)
        self.assertEqual(len(dash['cardPending']), 1)
        res = cashier_api.mutate(self.db, 3, 'card_confirm', {'paymentId': out['cardPaymentId'], 'requestId': 'cashier_card_1'})
        self.assertIn('ТАСДИҚЛАНДИ', res['_notify']['text'])
        self.assertEqual(core.client_debt_usd(self.db, self.cid), 100000 - 20000)
        self.assertEqual((core.cash_som(self.db, 2), core.cash_usd(self.db, 2)), (0, 0))
        bank = self.db.execute('SELECT amount_usd,amount_uzs,currency FROM cashier_incomes').fetchone()
        self.assertEqual(tuple(bank), (20000, 2400000, 'UZS'))
        self.assertEqual(cashier_api._cashier_summary(self.db)['bankTotalUzs'], 2400000)
        self.assertEqual(core.cashier_balance_usd(self.db), 0)               # cash box untouched
        with self.assertRaisesRegex(ValueError, 'avval'):
            core.decide_card_payment(self.db, 3, out['cardPaymentId'], True)

    def test_rejected_card_payment_changes_nothing(self):
        out = self.pay('card_2', currency='USD', amount='200', method='card')
        cashier_api.mutate(self.db, 3, 'card_reject', {'paymentId': out['cardPaymentId'], 'requestId': 'cashier_card_2'})
        self.assertEqual(core.client_debt_usd(self.db, self.cid), 100000)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cashier_incomes').fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT status FROM card_payments").fetchone()[0], 'rejected')

    def test_only_cashier_or_admin_confirms_card(self):
        out = self.pay('card_3', currency='USD', amount='10', method='card')
        with self.assertRaisesRegex(ValueError, 'kassir'):
            core.decide_card_payment(self.db, 2, out['cardPaymentId'], True)

    def test_card_payment_is_idempotent(self):
        a = self.pay('card_same', currency='USD', amount='10', method='card')
        b = self.pay('card_same', currency='USD', amount='10', method='card')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM card_payments').fetchone()[0], 1)
        self.assertTrue(a['ok'] and b['ok'])

    # --- act sverka / client card ----------------------------------------------------------
    def test_act_sverka_shows_som_rate_and_method(self):
        self.pay('p1', currency='UZS', amount='1185000', rate='11850', method='cash')
        out = self.pay('card_4', currency='UZS', amount='600000', rate='12000', method='card')
        core.decide_card_payment(self.db, 3, out['cardPaymentId'], True)
        r = reports.reconciliation(self.db, 1, self.cid)
        pays = [x for x in r['rows'] if x['usd_credit']]
        self.assertEqual(len(pays), 2)
        self.assertIn('1 185 000 сўм', pays[0]['kind']); self.assertIn('курс 11 850', pays[0]['kind']); self.assertIn('нақд', pays[0]['kind'])
        self.assertIn('карта', pays[1]['kind'])
        self.assertEqual(r['usd_closing'], 100000 - 10000 - 5000)
        self.assertEqual((r['opening'], r['payments']), (0, 0))   # legacy so'm ledger not polluted
        self.assertTrue(reports.reconciliation_xlsx(r)[:2] == b'PK')
        self.assertIn('1 185 000', reports.reconciliation_html(r).decode())
        text = client_ledger.recent_text(self.db, self.cid)
        self.assertIn('1 185 000 сўм', text)


if __name__ == '__main__':
    unittest.main()


class CardReceiptTests(unittest.TestCase):
    def test_card_payment_needs_receipt_and_cashier_gets_link(self):
        from unittest.mock import patch
        import bot
        t = UzsAndCardPaymentTests('test_card_payment_is_idempotent');t.setUp()
        try:
            with self.assertRaisesRegex(ValueError, 'chek'):
                agent_api.mutate(t.db, 2, 'payment', {'clientId': t.cid, 'currency': 'USD', 'amount': '10', 'method': 'card'},
                                 'req_norcpt_000000', t.now)
            out = t.pay('rcpt_1', currency='USD', amount='10', method='card')
            self.assertEqual(t.db.execute('SELECT photo FROM card_payments WHERE id=?', (out['cardPaymentId'],)).fetchone()[0],
                             'AgACAgIAAxkBAAEreceipt01')
            data = cashier_api.dashboard(t.db, 3)
            with patch.dict(bot.os.environ, {'RENDER_EXTERNAL_URL': 'https://example.test', 'WEBHOOK_BASE_URL': ''}):
                bot.attach_card_photo_urls(data)
            p = data['cardPending'][0]
            self.assertIn('/map/card-photo/%d/' % out['cardPaymentId'], p['photoUrl'])
            self.assertTrue(p['thumbUrl'].endswith('?t=1'))
        finally:
            t.tearDown()
