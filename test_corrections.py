"""Rahbar tuzatishlari: ta'minot xaridi va savdo sotuvini bekor qilish/tahrirlash — qoldiq, qarz va pul to'g'ri qaytadi."""
import unittest

import core
import corrections
import purchases
import shop
import warehouse as wh
import test_shop
from test_shop import ADMIN, S1, KEEPER


class PurchaseCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'Rahbar'), (5, 'warehouse', 'Omborchi')])
        self.db.commit()
        self.pack = next(iter(core.PRODUCTS))
        self.n = 0
        self.sid = self.call(1, 'supplier_add', name='Zavod')['supplierId']
        self.mid = self.call(1, 'material_add', name='Bo‘r', unit='kg')['materialId']

    def tearDown(self):
        self.db.close()

    def call(self, actor, op, **payload):
        self.n += 1
        try:
            d = purchases.handle(self.db, actor, op, payload, source=5000 + self.n)
            self.db.commit()
            return d
        except Exception:
            self.db.rollback()
            raise

    def buy(self, qty=10, price='2'):
        return self.call(1, 'purchase', supplierId=self.sid,
                         lines=[{'pack': self.pack, 'qty': qty, 'price': price}, {'material': self.mid, 'qty': '3', 'price': '1'}])['purchaseId']

    def test_cancel_reverses_stock_and_supplier_debt(self):
        pid = self.buy()
        self.assertEqual(purchases.balance(self.db, self.sid), 2300)
        with self.assertRaisesRegex(ValueError, 'faqat rahbar'):
            self.call(5, 'purchase_cancel', purchaseId=pid, reason='xato')     # omborchi o'chira olmaydi
        with self.assertRaisesRegex(ValueError, 'Sababini'):
            self.call(1, 'purchase_cancel', purchaseId=pid, reason='')
        d = self.call(1, 'purchase_cancel', purchaseId=pid, reason='Noto‘g‘ri kiritildi')
        self.assertEqual(wh.stock(self.db, self.pack), 0)
        self.assertEqual(purchases.material_stock(self.db, self.mid), 0)
        self.assertEqual(purchases.balance(self.db, self.sid), 0)
        self.assertEqual(d['summary']['monthBought'], 0)
        p = next(x for x in d['purchases'] if x['id'] == pid)
        self.assertEqual((p['cancelled']['reason'], p['cancelled']['who']), ('Noto‘g‘ri kiritildi', 'Rahbar'))   # yozuv saqlanadi
        with self.assertRaisesRegex(ValueError, 'allaqachon'):
            self.call(1, 'purchase_cancel', purchaseId=pid, reason='yana')

    def test_cannot_cancel_when_goods_already_left(self):
        pid = self.buy(qty=5)
        with _Op(1):
            wh.write_off(self.db, 1, self.pack, 3, 'brak')
        with self.assertRaisesRegex(ValueError, 'omborda 2 dona'):
            self.call(1, 'purchase_cancel', purchaseId=pid, reason='x')
        self.assertEqual(purchases.balance(self.db, self.sid), 1300)                  # hech narsa o'zgarmadi

    def test_edit_replaces_purchase_atomically(self):
        pid = self.buy(qty=10, price='2')
        d = self.call(1, 'purchase_edit', purchaseId=pid, supplierId=self.sid, reason='Narx xato',
                      lines=[{'pack': self.pack, 'qty': 8, 'price': '2.5'}])
        new = d['purchaseId']
        self.assertNotEqual(new, pid)
        self.assertEqual(wh.stock(self.db, self.pack), 8)
        self.assertEqual(purchases.material_stock(self.db, self.mid), 0)
        self.assertEqual(purchases.balance(self.db, self.sid), 2000)
        old = next(x for x in d['purchases'] if x['id'] == pid)
        self.assertEqual(old['cancelled']['replacedBy'], new)
        with self.assertRaises(ValueError):                                            # yangi qator xato — eski ham bekor bo'lmaydi
            self.call(1, 'purchase_edit', purchaseId=new, supplierId=self.sid, reason='x', lines=[{'pack': self.pack, 'qty': 0, 'price': '1'}])
        self.assertFalse(corrections.is_voided(self.db, 'purchase', new))
        self.assertEqual(wh.stock(self.db, self.pack), 8)


class _Op:
    def __init__(self, uid):self.uid = uid
    def __enter__(self):self.tok = wh.WEB_PRIMARY_OPERATOR.set(self.uid)
    def __exit__(self, *a):wh.WEB_PRIMARY_OPERATOR.reset(self.tok)


class SaleCorrectionTests(unittest.TestCase):
    setUp = test_shop.ShopTests.setUp
    req = test_shop.ShopTests.req
    sell = test_shop.ShopTests.sell

    def tearDown(self):
        self.db.close()

    def act(self, actor, action, **kw):
        kw.setdefault('requestId', self.req())
        d = shop.handle(self.db, actor, action, kw)
        self.db.commit()
        return d

    def test_cancel_seller_sale_returns_goods_money_and_debt(self):
        r = self.sell(S1, self.client, [{'pack': self.p1, 'qty': 3}], paid='20', method='cash_usd')   # 30$, 20$ naqd
        self.db.commit()
        self.assertEqual((core.client_debt_usd(self.db, self.client), core.cash_usd(self.db, S1)), (1000, 2000))
        with self.assertRaisesRegex(ValueError, 'faqat rahbar'):
            self.act(S1, 'sale_cancel', saleId=r['id'], reason='x')
        d = self.act(ADMIN, 'sale_cancel', saleId=r['id'], reason='Xato mijoz')
        self.assertEqual(wh.stock(self.db, self.p1), 100)
        self.assertEqual(core.client_debt_usd(self.db, self.client), 0)
        self.assertEqual(core.cash_usd(self.db, S1), 0)
        self.assertEqual(d['receipt']['cancelled']['reason'], 'Xato mijoz')
        self.assertEqual(d['today']['count'], 0)                                       # bugungi jamidan chiqdi

    def test_cancel_blocked_when_cash_already_handed_over(self):
        r = self.sell(S1, self.client, [{'pack': self.p1, 'qty': 1}], paid='10', method='cash_usd')
        self.db.execute("INSERT INTO handovers(agent,amount,amount_usd,status,ts,cashier) VALUES(?,0,1000,'accepted',1,?)", (S1, ADMIN))
        self.db.commit()
        with self.assertRaisesRegex(ValueError, 'topshirib bo‘lgan'):
            self.act(ADMIN, 'sale_cancel', saleId=r['id'], reason='x')
        self.db.rollback()
        self.assertFalse(corrections.is_voided(self.db, 'sale', r['id']))

    def test_cancel_admin_sale_reverses_cashbox(self):
        import cashbook
        self.db.execute("INSERT INTO meta(key,value) VALUES('cashier_uzs_per_usd','12500')")
        r = self.sell(ADMIN, self.client, [{'pack': self.p1, 'qty': 2}], paid='20', method='cash_usd', sellerId=ADMIN)
        self.db.commit()
        before = cashbook.balances(self.db)
        self.act(ADMIN, 'sale_cancel', saleId=r['id'], reason='Qaytarildi')
        after = cashbook.balances(self.db)
        self.assertEqual(sum(after.values()) - sum(before.values()), -2000)
        self.assertEqual(core.client_debt_usd(self.db, self.client), 0)

    def test_edit_sale_replaces_it(self):
        r = self.sell(S1, self.client, [{'pack': self.p1, 'qty': 3}])
        self.db.commit()
        new = self.act(ADMIN, 'sell', clientId=self.client, sellerId=S1, replaceSaleId=r['id'], reason='Miqdor xato',
                       items=[{'pack': self.p1, 'qty': 2}])['receipt']
        self.assertEqual(wh.stock(self.db, self.p1), 98)
        self.assertEqual(core.client_debt_usd(self.db, self.client), 2000)
        old = shop.receipt(self.db, r['id'])
        self.assertEqual(old['cancelled']['replacedBy'], new['id'])
        with self.assertRaisesRegex(ValueError, 'faqat rahbar'):
            self.act(S1, 'sell', clientId=self.client, replaceSaleId=new['id'], items=[{'pack': self.p1, 'qty': 1}])


if __name__ == '__main__':
    unittest.main()
