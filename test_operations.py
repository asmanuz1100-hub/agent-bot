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
        pays=[r for r in self.rows('agent') if r['kind']=='payment']
        self.assertEqual(len(pays),2);self.assertTrue(all(r['canCancel'] and r['canEdit'] for r in pays))
        with self.assertRaises(ValueError):operations.cancel(self.db,2,'payment',pays[0]['ref'],'ikki marta')
        operations.cancel(self.db,1,'payment',pays[0]['ref'],'ikki marta')
        self.assertEqual(core.client_debt_usd(self.db,self.cid),95000)
        gone=[r for r in self.rows('agent') if r['ref']==pays[0]['ref']][0]
        self.assertEqual(gone['status'],'cancelled');self.assertEqual(gone['cancel']['reason'],'ikki marta')
        self.assertFalse(gone['canCancel'])
        new=operations.edit(self.db,1,'payment',pays[1]['ref'],{'amount':'30'},'summa xato',123456789)
        self.assertEqual(core.client_debt_usd(self.db,self.cid),97000)
        self.assertEqual(core.cash_usd(self.db,2),3000)
        self.assertNotEqual(new,pays[1]['ref'])

    def test_som_payment_edit_keeps_rate(self):
        operations.init(self.db)
        self.pay('op_pay_0003',currency='UZS',amount='120000',usd='10',method='cash')
        ref=[r for r in self.rows('agent') if r['kind']=='payment'][0]['ref']
        self.assertEqual(operations.form(self.db,1,'payment',ref)[0]['value'],120000)
        operations.edit(self.db,1,'payment',ref,{'amount':'60000'},'yarmi',223456789)
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
        new=operations.edit(self.db,1,'cash_move',mid,{'amount':'25','note':'tuzatildi'},'summa xato',557)
        self.assertEqual(self.db.execute('SELECT amount FROM cash_moves WHERE id=?',(new,)).fetchone()[0],2500)
        self.assertEqual(self.db.execute('SELECT status FROM cash_moves WHERE id=?',(mid,)).fetchone()[0],'cancelled')

    def test_every_row_is_editable_and_cancellable(self):
        operations.init(self.db)
        self.pay('op_pay_0009',currency='USD',amount='5',method='cash')
        rows=self.rows()
        self.assertTrue(rows and all(r['canCancel'] and r['canEdit'] for r in rows))
        for r in rows:operations.form(self.db,1,r['kind'],r['ref'])

    def test_unknown_kind_rejected(self):
        operations.init(self.db)
        with self.assertRaises(ValueError):operations.cancel(self.db,1,'visit',1,'x')
        with self.assertRaises(ValueError):operations.cancel(self.db,1,'payment',1,'')


if __name__=='__main__':unittest.main()


import shop
import warehouse as wh
import purchases
import test_shop
import test_corrections
from test_shop import ADMIN, S1, KEEPER, AGENT


class SaleAndWarehouseOpsTests(unittest.TestCase):
    setUp=test_shop.ShopTests.setUp
    req=test_shop.ShopTests.req
    sell=test_shop.ShopTests.sell

    def tearDown(self):self.db.close()

    def test_sale_edit_from_journal(self):
        r=self.sell(S1,self.client,[{'pack':self.p1,'qty':3}],paid='20',method='cash_usd')
        row=[x for x in operations.journal(self.db,0,2**40,'sales')['items'] if x['ref']==r['id']][0]
        fields={f['name']:f['value'] for f in operations.form(self.db,ADMIN,'sale',row['ref'])}
        self.assertEqual((fields['qty_0'],fields['paid']),(3,20))
        new=operations.edit(self.db,ADMIN,'sale',r['id'],{'qty_0':'2','price_0':'10','paid':'20','discount':'0'},'miqdor xato',901)
        self.assertNotEqual(new,r['id'])
        self.assertEqual(wh.stock(self.db,self.p1),98)
        self.assertEqual(core.client_debt_usd(self.db,self.client),0)
        self.assertEqual(core.cash_usd(self.db,S1),2000)
        operations.cancel(self.db,ADMIN,'sale',new,'test rejim')
        self.assertEqual((wh.stock(self.db,self.p1),core.cash_usd(self.db,S1)),(100,0))

    def test_warehouse_issue_edit_and_cancel(self):
        with test_corrections._Op(ADMIN):mid=wh.issue(self.db,ADMIN,AGENT,self.p1,10)
        self.assertEqual(core.agent_stock(self.db,AGENT,self.p1),10)
        new=operations.edit(self.db,ADMIN,'wh_move',mid,{'qty':'6'},'ko‘p yozilgan',902)
        self.assertEqual((wh.stock(self.db,self.p1),core.agent_stock(self.db,AGENT,self.p1)),(94,6))
        operations.cancel(self.db,ADMIN,'wh_move',new,'xato')
        self.assertEqual((wh.stock(self.db,self.p1),core.agent_stock(self.db,AGENT,self.p1)),(100,0))
        with self.assertRaises(ValueError):operations.cancel(self.db,S1,'wh_move',mid,'x')   # faqat rahbar


class PurchaseOpsTests(unittest.TestCase):
    setUp=test_corrections.PurchaseCorrectionTests.setUp
    tearDown=test_corrections.PurchaseCorrectionTests.tearDown
    call=test_corrections.PurchaseCorrectionTests.call
    buy=test_corrections.PurchaseCorrectionTests.buy

    def test_purchase_and_supplier_payment_ops(self):
        pid=self.buy(qty=10,price='2')
        f={x['name']:x['value'] for x in operations.form(self.db,1,'purchase',pid)}
        self.assertEqual((f['qty_0'],f['qty_1']),(10,3))
        operations.edit(self.db,1,'purchase',pid,{'qty_0':'8','qty_1':'0'},'xato',903)
        self.assertEqual((wh.stock(self.db,self.pack),purchases.balance(self.db,self.sid)),(8,1600))
        core.add_cashier_expense  # kassaga pul: kirim
        import cashbook
        cashbook.add_income(self.db,1,'cash','USD','100',cashbook.INCOME_CATEGORIES[-1],'Egasi','',904)
        pay=purchases.pay_supplier(self.db,1,self.sid,1000,source=905)
        self.assertEqual(purchases.balance(self.db,self.sid),600)
        operations.edit(self.db,1,'supplier_payment',pay,{'amount':'6'},'summa xato',906)
        self.assertEqual(purchases.balance(self.db,self.sid),1000)
        rows=operations.journal(self.db,0,2**40)['items']
        sp=[x for x in rows if x['kind']=='supplier_payment']
        self.assertEqual(sorted(x['status'] for x in sp),['active','cancelled'])
        self.assertFalse([x for x in rows if x['kind']=='expense'])   # bog'langan xarajat alohida chiqmaydi
