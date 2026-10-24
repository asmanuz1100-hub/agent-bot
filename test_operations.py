"""Amallar jurnali: rahbar agent to'lovini, kassa yozuvini ko'radi, bekor qiladi va tahrirlaydi."""
import time
import unittest
import test_uzs_card_payments as fixture
import core
import operations


class OperationsJournalTests(unittest.TestCase):
    setUp=fixture.UzsAndCardPaymentTests.setUp
    tearDown=fixture.UzsAndCardPaymentTests.tearDown
    pay=fixture.UzsAndCardPaymentTests.pay

    def rows(self,source=None):
        return operations.journal(self.db,0,int(time.time())+10,source)['items']

    def test_agent_payment_listed_cancelled_and_edited(self):
        operations.init(self.db)
        self.pay('op_pay_0001',currency='USD',amount='50',method='cash')
        self.pay('op_pay_0002',currency='USD',amount='50',method='cash')
        pays=[r for r in self.rows('agent') if r['label']=='To‘lov']
        self.assertEqual(len(pays),2);self.assertTrue(all(r['canCancel'] and r['canEdit'] for r in pays))
        with self.assertRaises(ValueError):operations.cancel(self.db,2,'payment',pays[0]['ref'],'ikki marta')
        operations.cancel(self.db,1,'payment',pays[0]['ref'],'ikki marta')
        self.assertEqual(core.client_debt_usd(self.db,self.cid),95000)
        gone=[r for r in self.rows('agent') if r['ref']==pays[0]['ref']][0]
        self.assertEqual(gone['status'],'cancelled');self.assertEqual(gone['cancel']['reason'],'ikki marta')
        self.assertFalse(gone['canCancel'])
        new=operations.edit(self.db,1,'payment',pays[1]['ref'],'30',None,'summa xato',123456789)
        self.assertEqual(core.client_debt_usd(self.db,self.cid),97000)
        self.assertEqual(core.cash_usd(self.db,2),3000)
        self.assertNotEqual(new,pays[1]['ref'])

    def test_som_payment_edit_keeps_rate(self):
        operations.init(self.db)
        self.pay('op_pay_0003',currency='UZS',amount='120000',usd='10',method='cash')
        ref=[r for r in self.rows('agent') if r['label']=='To‘lov'][0]['ref']
        operations.edit(self.db,1,'payment',ref,'60000',None,'yarmi',223456789)
        self.assertEqual(core.client_debt_usd(self.db,self.cid),99500)
        self.assertEqual(core.cash_som(self.db,2),60000)

    def test_all_sources_query_and_expense_archive(self):
        operations.init(self.db)
        import cashbook
        cashbook.init(self.db)
        mid=cashbook.add_income(self.db,1,'cash','USD','40',cashbook.INCOME_CATEGORIES[-1],'Kimdir','',556)
        eid=core.add_cashier_expense(self.db,1,2500,core.cashier_expense_categories()[0],'Test','',555)
        rows=self.rows()
        self.assertTrue({'expense:%d'%eid,'cash_move:%d'%mid}<=set(r['key'] for r in rows))
        operations.cancel(self.db,1,'expense',eid,'test rejim')
        self.assertIsNone(self.db.execute('SELECT 1 FROM cashier_expenses WHERE id=?',(eid,)).fetchone())
        x=[r for r in self.rows('cash') if r['key']=='expense:%d'%eid][0]
        self.assertEqual((x['status'],x['cancel']['reason']),('cancelled','test rejim'))
        new=operations.edit(self.db,1,'cash_move',mid,'25','tuzatildi','summa xato',557)
        self.assertEqual(self.db.execute('SELECT amount FROM cash_moves WHERE id=?',(new,)).fetchone()[0],2500)
        self.assertEqual(self.db.execute('SELECT status FROM cash_moves WHERE id=?',(mid,)).fetchone()[0],'cancelled')

    def test_unknown_kind_rejected(self):
        operations.init(self.db)
        with self.assertRaises(ValueError):operations.cancel(self.db,1,'visit',1,'x')
        with self.assertRaises(ValueError):operations.cancel(self.db,1,'payment',1,'')


if __name__=='__main__':unittest.main()
