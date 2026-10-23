"""Mijoz cheki QR havolasi: imzo, ochiq sahifa, QR SVG va HTTP yo'li (login yo'q, boshqa chekni taxmin qilib bo'lmaydi)."""
import os
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import core
import receipt_public as rp
import shop
import test_modules
import test_shop
from test_shop import S1


class ReceiptPublicUnitTests(unittest.TestCase):
    setUp = test_shop.ShopTests.setUp
    req = test_shop.ShopTests.req
    sell = test_shop.ShopTests.sell

    def tearDown(self):
        self.db.close()

    def test_signed_url_page_and_qr(self):
        rp.configure('k1')
        with patch.dict(os.environ, {'WEBHOOK_BASE_URL': 'https://x.test'}):
            r = self.sell(S1, self.client, [{'pack': self.p1, 'qty': 2}], paid='5', method='cash_usd')
            u = r['publicUrl']
            self.assertRegex(u, r'^https://x\.test/c/\d+-[0-9a-f]{16}$')
            path = u[len('https://x.test'):]
            self.assertEqual(rp.parse(path), (r['id'], False))
            self.assertEqual(rp.parse(path + '.svg'), (r['id'], True))
            self.assertIsNone(rp.parse(path.replace(f"/c/{r['id']}-", f"/c/{r['id'] + 1}-")))   # boshqa raqam — imzo mos emas
            rp.configure('k2')
            self.assertIsNone(rp.parse(path))                                                    # boshqa kalit — yaroqsiz
            rp.configure('k1')
        html = rp.page(shop.receipt(self.db, r['id']), {'name': 'Namuna <b>', 'logo': '', 'details': {}})
        self.assertIn(f"Chek № {r['id']}", html)
        self.assertIn('Namuna &lt;b&gt;', html)                                                  # XSS himoyasi
        self.assertIn('Qoldiq (qarz)', html)
        svg = rp.qr_svg('https://x.test/c/1-0123456789abcdef')
        self.assertTrue(svg.startswith('<svg') and len(svg) < 15000)


class ReceiptPublicHttpTests(test_modules.HttpBase):
    def test_get_page_and_svg_without_login(self):
        db = core.connect(self.db_path, initialize=False)
        db.execute("INSERT OR IGNORE INTO users(id,role,name) VALUES(900,'sales','Sotuvchi')")
        shop.set_staff(db, 1, 900, list(shop.SELLER_PERMS), 5)
        cid = shop.add_client(db, 900, 'Akmal', '+998901110099', 'Akmal dokon')
        db.execute("INSERT INTO warehouse_moves(actor,kind,pack,qty,note,ts) VALUES(1,'in',?,10,'',1)", (next(iter(core.PRODUCTS)),))
        shop.set_price(db, 1, next(iter(core.PRODUCTS)), '3', '2')
        sale = shop.sell(db, 900, {'requestId': 'rcpt-test-0001', 'clientId': cid, 'items': [{'pack': next(iter(core.PRODUCTS)), 'qty': 1}]})
        db.commit();db.close()
        rp.configure(bot_token())
        u = rp.url(sale['id'], f'http://127.0.0.1:{self.port}')
        with urllib.request.urlopen(u, timeout=10) as r:
            self.assertEqual(r.status, 200)
            self.assertIn('Akmal dokon', r.read().decode())
        with urllib.request.urlopen(u + '.svg', timeout=10) as r:
            self.assertEqual(r.headers['Content-Type'], 'image/svg+xml')
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(u[:-1] + ('0' if u[-1] != '0' else '1'), timeout=10)
        self.assertEqual(e.exception.code, 404)


def bot_token():
    import bot
    return bot.TOKEN_AT_IMPORT if hasattr(bot, 'TOKEN_AT_IMPORT') else os.getenv('BOT_TOKEN', '')


if __name__ == '__main__':
    unittest.main()
