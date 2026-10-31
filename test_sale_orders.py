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
        self.assertEqual((o['payment'], o['due'], o['status']), ('paid', 0, 'closed'))   # to'liq yetkazildi + to'landi → yopildi
        self.assertEqual([x['action'] for x in o['log']][::-1], ['create', 'deliver', 'pay', 'deliver', 'return', 'pay', 'close'])

    def test_list_date_range(self):
        a, b = self.order(qty1=1, qty2=1), self.order(qty1=1, qty2=1)
        for o, ts in ((a, 1000), (b, 5000)):
            self.db.execute('UPDATE sale_orders SET ts=? WHERE id=?', (ts, o['id']))
        ids = lambda **kw: [x['id'] for x in self.op(S1, 'list', **kw)['orders']]
        self.assertEqual(ids(**{'from': 2000}), [b['id']])
        self.assertEqual(ids(to=5000), [a['id']])                             # to — chegara kirmaydi
        self.assertEqual(ids(**{'from': '', 'to': ''}), [b['id'], a['id']])

    def test_closed_orders_leave_open_list_and_can_still_be_returned(self):
        o = self.order(qty1=2, qty2=1)
        self.op(S1, 'pay', orderId=o['id'], payments=[{'method': 'cash_usd', 'amount': '25'}])
        o = self.op(S1, 'deliver', orderId=o['id'], items={str(self.p1): 2, str(self.p2): 1})['order']
        self.assertEqual(o['status'], 'closed')
        self.assertEqual(self.op(S1, 'list')['orders'], [])                   # «Ochiq» ro'yxat tozalanadi
        self.assertEqual([x['id'] for x in self.op(S1, 'list', status='closed')['orders']], [o['id']])
        o = self.op(S1, 'return', orderId=o['id'], pack=self.p2, qty=1, reason='Yaroqsiz')['order']
        self.assertEqual((o['status'], o['due']), ('closed', -500))           # ortiqcha to'lov ko'rinadi, buyurtma yopiq qoladi
        with self.assertRaisesRegex(ValueError, 'ochiq emas'):
            self.op(S1, 'cancel', orderId=o['id'], reason='x')

    def test_delivery_on_credit_needs_credit_permission(self):
        shop.set_staff(self.db, ADMIN, S2, ['retail', 'collect'], 0)          # qarzga berish ruxsati yo'q
        o = self.order(actor=S2, qty1=2, qty2=1)
        with self.assertRaisesRegex(ValueError, 'Qarzga berish'):
            self.op(S2, 'deliver', orderId=o['id'], items={str(self.p1): 1})
        self.assertEqual(wh.stock(self.db, self.p1), 100)                     # hech narsa yozilmadi
        self.op(S2, 'pay', orderId=o['id'], payments=[{'method': 'cash_usd', 'amount': '10'}])
        o = self.op(S2, 'deliver', orderId=o['id'], items={str(self.p1): 1})['order']   # to'langan qismigacha — mumkin
        self.assertEqual(o['delivered'], 1000)
        with self.assertRaisesRegex(ValueError, 'Qarzga berish'):
            self.op(S2, 'deliver', orderId=o['id'], items={str(self.p1): 1})
        self.assertEqual(core.client_debt_usd(self.db, self.client), 0)

    def test_dashboard_stock_excludes_reserved(self):
        self.op(S1, 'create', clientId=self.client, items=[{'pack': self.p1, 'qty': 30}])
        p = next(x for x in shop.dashboard(self.db, S1)['products'] if x['pack'] == self.p1)
        self.assertEqual((p['stock'], p['onHand'], p['reserved']), (70, 100, 30))

    def test_bad_return_input_has_clear_message(self):
        o = self.order()
        with self.assertRaisesRegex(ValueError, 'to‘g‘ri tanlang'):
            self.op(S1, 'return', orderId=o['id'], pack='abc', qty='', reason='x')

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

    def test_admin_sells_in_own_name_money_goes_to_cashbox(self):
        import cashbook
        self.db.execute("INSERT INTO meta(key,value) VALUES('cashier_uzs_per_usd','12500')")
        before = cashbook.balances(self.db)
        sellers = shop.dashboard(self.db, ADMIN)['sellers']
        self.assertEqual(sellers[0]['id'], ADMIN)
        r = shop.sell(self.db, ADMIN, {'requestId': self.req(), 'clientId': self.client, 'sellerId': ADMIN,
                                       'items': [{'pack': self.p1, 'qty': 3}], 'paid': '20', 'method': 'cash_usd'})
        self.db.commit()
        self.assertEqual((r['totalUsd'], r['debtUsd']), (30, 10))
        self.assertEqual(core.client_debt_usd(self.db, self.client), 1000)
        self.assertEqual(cashbook.balances(self.db)['cash_usd'], before['cash_usd'] + 2000)   # kassada
        self.assertEqual(core.cash_usd(self.db, ADMIN), 0)                                     # hech kim qo'lida emas
        self.assertEqual(wh.stock(self.db, self.p1), 97)
        # buyurtma to'lovi ham kassaga
        o = self.op(ADMIN, 'create', clientId=self.client, sellerId=ADMIN, items=[{'pack': self.p1, 'qty': 1}])['order']
        self.op(ADMIN, 'deliver', orderId=o['id'], items={str(self.p1): 1})
        self.op(ADMIN, 'pay', orderId=o['id'], payments=[{'method': 'card', 'amount': '10'}])
        self.assertEqual(cashbook.balances(self.db)['card_usd'], before['card_usd'] + 1000)


if __name__ == '__main__':
    unittest.main()
