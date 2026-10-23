"""Ombordan savdo buyurtmasi: band qilish, qisman yetkazish, aralash to'lov, qaytarish, bekor qilish va hisoblar mosligi."""
import json
import unittest

import core
import sale_orders as so
import shop
import warehouse as wh
import test_shop
from test_shop import HEAD, S1, S2, ADMIN, KEEPER


class SaleOrderTests(unittest.TestCase):
    setUp = test_shop.ShopTests.setUp
    req = test_shop.ShopTests.req

    def tearDown(self):
        self.db.close()

    def op(self, actor, op, **kw):
        kw.setdefault('requestId', self.req())
        d = shop.handle(self.db, actor, 'orders', {'orderOp': op, **kw})
        self.db.commit()
        json.dumps(d)
        return d

    def order(self, actor=S1, qty1=10, qty2=4, **kw):
        return self.op(actor, 'create', clientId=self.client, items=[{'pack': self.p1, 'qty': qty1}, {'pack': self.p2, 'qty': qty2}], **kw)['order']

    def test_create_only_reserves(self):
        o = self.order()
        self.assertEqual((o['total'], o['delivery'], o['payment']), (12000, 'none', 'unpaid'))   # 10×10 + 4×5
        self.assertEqual(wh.stock(self.db, self.p1), 100)                     # ombordan chiqmadi
        self.assertEqual(so.available(self.db, self.p1), 90)                  # band
        self.assertEqual(core.client_debt_usd(self.db, self.client), 0)       # qarz yo'q — yetkazilmagan
        q = shop.quote(self.db, S1, {'clientId': self.client, 'items': [{'pack': self.p1, 'qty': 91}]})
        self.assertTrue(q['stockShort'])                                      # band qism sotilmaydi

    def test_partial_delivery_mixed_payment_and_return(self):
        o = self.order()
        o = self.op(S1, 'deliver', orderId=o['id'], items={str(self.p1): 4})['order']
        self.assertEqual((o['delivery'], o['delivered']), ('partial', 4000))
        self.assertEqual(wh.stock(self.db, self.p1), 96)
        self.assertEqual(so.available(self.db, self.p1), 90)                  # 6 hali band
        self.assertEqual(core.client_debt_usd(self.db, self.client), 4000)
        o = self.op(S1, 'pay', orderId=o['id'], payments=[{'method': 'cash_usd', 'amount': '20'},
                                                          {'method': 'cash_uzs', 'amount': '125000', 'rate': '12500'},
                                                          {'method': 'card', 'amount': '5'}])['order']
        self.assertEqual((o['paid'], o['payment']), (3500, 'partial'))
        self.assertEqual(core.client_debt_usd(self.db, self.client), 500)
        self.assertEqual(core.cash_usd(self.db, S1), 2000)                    # naqd $ sotuvchida, karta/so'm alohida
        o = self.op(S1, 'deliver', orderId=o['id'], items={str(self.p1): 6, str(self.p2): 4})['order']
        self.assertEqual(o['delivery'], 'full')
        self.assertEqual(so.available(self.db, self.p1), 90)
        o = self.op(S1, 'return', orderId=o['id'], pack=self.p2, qty=2, reason='Shikastlangan')['order']
        self.assertEqual(o['returned'], 1000)
        self.assertEqual(wh.stock(self.db, self.p2), 98)
        self.assertEqual(core.client_debt_usd(self.db, self.client), 12000 - 1000 - 3500)
        self.assertEqual(o['due'], 12000 - 1000 - 3500)
        with self.assertRaises(ValueError):                                   # ortiqcha to'lov yo'q
            self.op(S1, 'pay', orderId=o['id'], payments=[{'method': 'cash_usd', 'amount': '75.01'}])
        o = self.op(S1, 'pay', orderId=o['id'], payments=[{'method': 'cash_usd', 'amount': '75'}])['order']
        self.assertEqual((o['payment'], o['due']), ('paid', 0))
        self.assertEqual([x['action'] for x in o['log']][::-1], ['create', 'deliver', 'pay', 'deliver', 'return', 'pay'])

    def test_repeated_requests_do_not_duplicate(self):
        o = self.order()
        rid = self.req()
        for _ in range(2):
            self.op(S1, 'deliver', orderId=o['id'], items={str(self.p2): 0, str(self.p1): 3}, requestId=rid)
            self.op(S1, 'pay', orderId=o['id'], payments=[{'method': 'cash_usd', 'amount': '10'}], requestId=rid + 'p')
        o = self.op(S1, 'view', orderId=o['id'])['order']
        self.assertEqual((o['lines'][0]['delivered'], o['paid']), (3, 1000))
        self.assertEqual(wh.stock(self.db, self.p1), 97)
        rid = self.req()
        a = self.op(S1, 'create', clientId=self.client, items=[{'pack': self.p1, 'qty': 1}], requestId=rid)['order']
        b = self.op(S1, 'create', clientId=self.client, items=[{'pack': self.p1, 'qty': 1}], requestId=rid)['order']
        self.assertEqual(a['id'], b['id'])

    def test_cancel_rules(self):
        o = self.order()
        with self.assertRaises(ValueError):self.op(S1, 'cancel', orderId=o['id'], reason='')
        self.op(S1, 'cancel', orderId=o['id'], reason='Mijoz voz kechdi')
        self.assertEqual(so.available(self.db, self.p1), 100)                 # band bo'shadi
        o = self.order()
        self.op(S1, 'deliver', orderId=o['id'], items={str(self.p1): 1})
        with self.assertRaisesRegex(ValueError, 'qaytarish'):
            self.op(S1, 'cancel', orderId=o['id'], reason='x')

    def test_permissions_and_scope(self):
        o = self.order()
        with self.assertRaisesRegex(ValueError, 'Qarz undirish'):             # S2: faqat chakana, to'lov olish yo'q
            shop.set_staff(self.db, ADMIN, S2, ['retail', 'all_sales'], 0)
            self.op(S2, 'pay', orderId=o['id'], payments=[{'method': 'cash_usd', 'amount': '1'}])
        shop.set_staff(self.db, ADMIN, S2, ['retail'], 0)
        with self.assertRaisesRegex(ValueError, 'sizniki emas'):
            self.op(S2, 'view', orderId=o['id'])
        self.assertEqual(self.op(S2, 'list')['orders'], [])
        self.assertEqual(len(self.op(HEAD, 'list')['orders']), 1)
        d = self.op(ADMIN, 'create', clientId=self.client, items=[{'pack': self.p1, 'qty': 1}], sellerId=S1)['order']
        self.assertEqual((d['seller'], d['createdBy']), ('Sotuvchi1', 'Rahbar'))   # admin kiritgani belgilanadi
        with self.assertRaises(ValueError):
            self.op(KEEPER, 'list')


if __name__ == '__main__':
    unittest.main()
