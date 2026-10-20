"""Savdo bo'limi: Bito formulasi, huquqlar, narxlar, chegirma, qarz, ombor, kassa va boshqa hisobotlar bilan moslik."""
import json
import unittest

import core
import executive
import shop
import warehouse as wh

HEAD, S1, S2, KEEPER, CASHIER, ADMIN, AGENT = 50, 51, 52, 60, 70, 1, 2


class ShopTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [
            (ADMIN, 'admin', 'Rahbar'), (HEAD, 'sales', 'Bosh'), (S1, 'sales', 'Sotuvchi1'), (S2, 'sales', 'Sotuvchi2'),
            (KEEPER, 'warehouse', 'Omborchi'), (CASHIER, 'cashier', 'Kassir'), (AGENT, 'agent', 'Agent')])
        shop.set_staff(self.db, ADMIN, HEAD, 'head')
        shop.set_staff(self.db, HEAD, S1, 'seller', 5, True)
        shop.set_staff(self.db, HEAD, S2, 'seller', 0, False)
        self.p1, self.p2 = list(core.PRODUCTS)[:2]
        shop.set_price(self.db, HEAD, self.p1, '10', '8')
        shop.set_price(self.db, HEAD, self.p2, '5', '4')
        wh.receive(self.db, KEEPER, self.p1, 100, source=1)
        wh.receive(self.db, KEEPER, self.p2, 100, source=2)
        self.client = shop.add_client(self.db, S1, 'Akmal', '+998901112233', 'Akmal dokon')
        self.dealer = shop.add_client(self.db, HEAD, 'Diller', '+998905556677', 'Diller', price_type='dealer')
        self.rid = 0

    def req(self):
        self.rid += 1
        return f'test-request-{self.rid:04d}'

    def sell(self, actor, client, items, **kw):
        return shop.sell(self.db, actor, {'requestId': self.req(), 'clientId': client, 'items': items, **kw})

    def test_bito_formula_discount_split_and_debt(self):
        r = self.sell(S1, self.client, [{'pack': self.p1, 'qty': 3}, {'pack': self.p2, 'qty': 4}],
                      discount='2.5', paid='20', method='cash_usd')
        self.assertEqual(r['subtotalUsd'], 50)                       # 3×10 + 4×5
        self.assertEqual(r['discountUsd'], 2.5)
        self.assertEqual(r['totalUsd'], 47.5)                        # to'lanishi kerak
        self.assertEqual(r['paidUsd'], 20)
        self.assertEqual(r['debtUsd'], 27.5)                         # qoldiq
        self.assertEqual(sum(l['discountUsd'] for l in r['lines']), 2.5)
        self.assertEqual(sum(l['totalUsd'] for l in r['lines']), 47.5)
        self.assertEqual(core.client_debt_usd(self.db, self.client), 2750)
        self.assertEqual(wh.stock(self.db, self.p1), 97)
        self.assertEqual(wh.stock(self.db, self.p2), 96)
        self.assertEqual(core.client_stock_total(self.db, self.client, self.p1), 0)   # sotilgan, mijozda konsignatsiya yo'q
        self.assertEqual(core.cash_usd(self.db, S1), 2000)

    def test_seller_limits(self):
        with self.assertRaisesRegex(ValueError, 'limitingiz 5%'):
            self.sell(S1, self.client, [{'pack': self.p1, 'qty': 10}], discountPct='6', paid='94', method='cash_usd')
        with self.assertRaisesRegex(ValueError, 'faqat bosh savdo'):
            self.sell(S1, self.client, [{'pack': self.p1, 'qty': 1, 'price': '9'}], paid='9', method='cash_usd')
        with self.assertRaisesRegex(ValueError, 'qarzga berish ruxsati yo‘q'):
            self.sell(S2, self.client, [{'pack': self.p1, 'qty': 1}])
        with self.assertRaisesRegex(ValueError, 'Chakana xaridorga qarzga'):
            self.sell(S1, None, [{'pack': self.p1, 'qty': 1}], paid='5', method='cash_usd')
        with self.assertRaisesRegex(ValueError, 'faqat bosh savdo'):
            shop.set_price(self.db, S1, self.p1, '1', '1')
        with self.assertRaisesRegex(ValueError, 'Diller mijozni faqat'):
            shop.add_client(self.db, S1, 'Xasan', '+998909999999', price_type='dealer')
        r = self.sell(S1, self.client, [{'pack': self.p1, 'qty': 10}], discountPct='5', paid='95', method='cash_usd')
        self.assertEqual(r['totalUsd'], 95)

    def test_head_full_rights_dealer_and_special_price(self):
        r = self.sell(HEAD, self.dealer, [{'pack': self.p1, 'qty': 10}])
        self.assertEqual(r['totalUsd'], 80)                           # diller narxi, to'liq qarzga
        shop.set_client_price(self.db, HEAD, self.dealer, self.p1, '7.5')
        r = self.sell(HEAD, self.dealer, [{'pack': self.p1, 'qty': 2}, {'pack': self.p2, 'qty': 1, 'price': '3'}], discountPct='50')
        self.assertEqual(r['subtotalUsd'], 18)
        self.assertEqual(r['totalUsd'], 9)
        self.assertEqual(core.client_debt_usd(self.db, self.dealer), 8900)

    def test_walkin_cash_sale_and_uzs_card(self):
        self.db.execute("INSERT INTO meta(key,value) VALUES(?,?)", (core.CASHIER_RATE_KEY, '12500'))
        r = self.sell(S1, None, [{'pack': self.p2, 'qty': 2}], paidUzs='125000', rate='12500', method='cash_uzs')
        self.assertEqual(r['client'], shop.WALKIN_NAME)
        self.assertEqual(r['debtUsd'], 0)
        self.assertEqual(core.cash(self.db, S1), 125000 * 100)
        r = self.sell(S1, None, [{'pack': self.p2, 'qty': 1}], paid='5', method='card')
        self.assertEqual(core.cash_usd(self.db, S1), 0)               # karta qo'lda emas
        self.assertEqual(r['method'], 'card')

    def test_idempotent_request(self):
        payload = {'requestId': 'same-request-1', 'clientId': self.client, 'items': [{'pack': self.p1, 'qty': 1}]}
        a = shop.sell(self.db, S1, dict(payload))
        b = shop.sell(self.db, S1, dict(payload))
        self.assertEqual(a['id'], b['id'])
        self.assertEqual(wh.stock(self.db, self.p1), 99)

    def test_stock_check(self):
        with self.assertRaisesRegex(ValueError, 'Omborda yetarli emas'):
            self.sell(HEAD, self.client, [{'pack': self.p1, 'qty': 101}])

    def test_collect_and_handover_to_cashier(self):
        self.sell(S1, self.client, [{'pack': self.p1, 'qty': 5}])
        with self.assertRaisesRegex(ValueError, 'ko‘p'):
            shop.collect(self.db, S1, {'requestId': self.req(), 'clientId': self.client, 'paid': '60', 'method': 'cash_usd'})
        shop.collect(self.db, S1, {'requestId': self.req(), 'clientId': self.client, 'paid': '30', 'method': 'cash_usd'})
        self.assertEqual(core.client_debt_usd(self.db, self.client), 2000)
        shop.handover(self.db, S1, {'requestId': self.req(), 'currency': 'USD', 'amount': '30'})
        h = self.db.execute('SELECT id FROM handovers WHERE agent=?', (S1,)).fetchone()
        core.accept(self.db, CASHIER, int(h[0]))
        self.assertEqual(core.cash_usd(self.db, S1), 0)

    def test_matches_executive_and_json_safe(self):
        self.sell(S1, self.client, [{'pack': self.p1, 'qty': 3}], paid='10', method='cash_usd')
        self.sell(HEAD, self.dealer, [{'pack': self.p2, 'qty': 10}])
        e = executive.executive(self.db, 'today')
        k = {x['key']: x['value'] for x in e['kpis']}
        self.assertEqual(k['realization'], 70)                        # 30 + 40
        self.assertEqual(k['collected'], 10)
        self.assertEqual(k['debt'], 60)
        d = shop.handle(self.db, HEAD, 'dashboard', {})
        json.dumps(d)
        self.assertEqual(d['today']['totalUsd'], 70)
        self.assertEqual(len(d['team']), 3)
        self.assertEqual(shop.handle(self.db, S1, 'dashboard', {})['today']['count'], 1)   # sotuvchi faqat o'zinikini

    def test_quote_does_not_write(self):
        q = shop.handle(self.db, S1, 'quote', {'clientId': self.client, 'items': [{'pack': self.p1, 'qty': 2}], 'discountPct': '5'})
        self.assertEqual(q['quote']['totalUsd'], 19)
        self.assertEqual(wh.stock(self.db, self.p1), 100)
        self.assertIsNone(self.db.execute('SELECT 1 FROM shop_sales').fetchone())

    def test_access(self):
        with self.assertRaisesRegex(ValueError, 'ruxsat yo‘q'):
            shop.handle(self.db, AGENT, 'dashboard', {})
        with self.assertRaisesRegex(ValueError, 'Bosh savdo xodimini faqat rahbar'):
            shop.set_staff(self.db, HEAD, S1, 'head')


if __name__ == '__main__':
    unittest.main()


class ShopBotTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'A'), (2, 'agent', 'B'), (3, 'cashier', 'C'), (50, 'sales', 'Bosh'), (5, 'warehouse', 'W')])
        shop.set_staff(self.db, 1, 50, 'head')
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_menu_and_launch_button(self):
        import bot
        from unittest.mock import patch
        from test_warehouse_api import msg
        buttons = lambda uid: [b for row in bot.menu(self.db, uid) for b in row]
        self.assertIn('🛒 Savdo Mini App', buttons(50))
        self.assertIn('🛒 Savdo Mini App', buttons(1))
        self.assertNotIn('🛒 Savdo Mini App', buttons(2))
        self.assertIn('/app/savdo/', bot.SHOP_MINIAPP_URL)
        self.assertEqual(bot.menu_button_for('sales')['web_app']['url'], bot.SHOP_MINIAPP_URL)
        with patch.object(bot, 'api') as tg:
            bot.handle(self.db, msg(1, 50, '🛒 Savdo Mini App'))
        self.assertEqual(tg.call_args.kwargs['reply_markup']['inline_keyboard'][0][0]['web_app']['url'], bot.SHOP_MINIAPP_URL)

    def test_http_endpoint(self):
        import io
        import bot
        from unittest.mock import MagicMock, patch
        from test_manager_api import signed_data
        captured = {}

        def server(address, handler):
            captured['handler'] = handler
            return MagicMock()
        with patch.object(bot, 'HTTPServer', side_effect=server), patch.object(bot, 'api'), patch.object(bot, 'TOKEN', 'test-token'):
            bot.serve_webhook(self.db, 'https://example.test')

        def post(payload):
            raw = json.dumps(payload).encode()
            h = object.__new__(captured['handler'])
            h.path = '/api/shop'; h.headers = {'Content-Length': str(len(raw))}; h.rfile = io.BytesIO(raw)
            result = {}
            h._reply = lambda code, body, ctype=None, extra_headers=None: result.update(code=code, data=json.loads(body))
            with patch.object(bot, 'TOKEN', 'test-token'):
                h.do_POST()
            return result
        self.assertEqual(post({'action': 'dashboard'})['code'], 401)
        self.assertEqual(post({'initData': signed_data('test-token', 2)})['code'], 403)
        head = {'initData': signed_data('test-token', 50)}
        r = post(head)
        self.assertEqual(r['code'], 200)
        self.assertEqual(r['data']['me']['level'], 'head')
        pack = next(iter(core.PRODUCTS))
        self.assertEqual(post({**head, 'action': 'set_price', 'pack': pack, 'retail': '10', 'dealer': '8'})['code'], 200)
        bad = post({**head, 'action': 'sell', 'requestId': 'http-sell-0001', 'items': [{'pack': pack, 'qty': 1}]})
        self.assertEqual(bad['code'], 400)                      # omborda yo'q
        self.assertIn('Omborda', bad['data']['error'])
