"""Rahbar ikki marta kiritilgan agent naqd to'lovini bekor qiladi: qarz va agent puli qaytadi."""
import unittest
import test_uzs_card_payments as fixture
import core
import corrections


class PaymentVoidTests(unittest.TestCase):
    setUp=fixture.UzsAndCardPaymentTests.setUp
    tearDown=fixture.UzsAndCardPaymentTests.tearDown
    pay=fixture.UzsAndCardPaymentTests.pay

    def last_payment(self):
        return self.db.execute("SELECT id FROM events WHERE kind='payment' ORDER BY id DESC LIMIT 1").fetchone()[0]

    def test_duplicate_som_payment_is_voided(self):
        corrections.init(self.db)
        self.pay('dup_pay_0001',currency='UZS',amount='120000',usd='10',method='cash')
        self.pay('dup_pay_0002',currency='UZS',amount='120000',usd='10',method='cash')
        self.assertEqual(core.client_debt_usd(self.db,self.cid),98000)
        eid=self.last_payment()
        with self.assertRaises(ValueError):corrections.cancel_payment(self.db,2,eid,'ikki marta')
        corrections.cancel_payment(self.db,1,eid,'ikki marta')
        self.assertEqual(core.client_debt_usd(self.db,self.cid),99000)
        self.assertEqual(core.cash_som(self.db,2),120000)
        with self.assertRaises(ValueError):corrections.cancel_payment(self.db,1,eid,'yana')

    def test_usd_payment_void(self):
        corrections.init(self.db)
        self.pay('usd_pay_0001',currency='USD',amount='50',method='cash')
        corrections.cancel_payment(self.db,1,self.last_payment(),'xato')
        self.assertEqual((core.client_debt_usd(self.db,self.cid),core.cash_usd(self.db,2)),(100000,0))


if __name__=='__main__':unittest.main()
