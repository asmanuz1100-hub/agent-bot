"""Ta'minot: ta'minotchilar, xarid, xom ashyo, ishlab chiqarish (rahbar web paneli)."""
import unittest

import core
import purchases
import warehouse


class PurchasesTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1,'admin','Rahbar'),(2,'agent','Ali'),(3,'cashier','Kassir'),(5,'warehouse','Omborchi')])
        self.db.commit()
        self.pack=next(iter(core.PRODUCTS))
        self.n=0

    def tearDown(self):self.db.close()

    def call(self,actor,op,**payload):
        self.n+=1
        try:
            data=purchases.handle(self.db,actor,op,payload,source=1000+self.n)
            self.db.commit()
            return data
        except Exception:
            self.db.rollback()
            raise

    def supplier(self,name='Kimyo zavod'):
        return self.call(1,'supplier_add',name=name,phone='+998901112233')['supplierId']

    def material(self,name='Bo‘r',unit='kg',min_qty=''):
        return self.call(1,'material_add',name=name,unit=unit,minQty=min_qty)['materialId']

    def fund_cashbox(self,cents):
        self.db.execute("INSERT INTO handovers(agent,amount,amount_usd,status,ts,cashier) VALUES(2,0,?,'accepted',1,3)",(cents,))
        self.db.commit()

    def test_product_purchase_adds_stock_and_supplier_debt(self):
        sid=self.supplier()
        d=self.call(5,'purchase',supplierId=sid,lines=[{'pack':self.pack,'qty':10,'price':'2.50'}],note='1-partiya')
        self.assertEqual(warehouse.stock(self.db,self.pack),10)
        self.assertEqual(purchases.balance(self.db,sid),2500)
        self.assertEqual(d['summary']['totalDebt'],2500)
        self.assertEqual(d['summary']['monthBought'],2500)
        note=self.db.execute("SELECT note FROM warehouse_moves WHERE kind='in'").fetchone()[0]
        self.assertIn(f"Xarid #{d['purchaseId']}",note)

    def test_material_purchase_with_fractional_quantity(self):
        sid=self.supplier();mid=self.material(min_qty='100')
        d=self.call(1,'purchase',supplierId=sid,lines=[{'material':mid,'qty':'2.5','price':'0.33'}])
        # 2.5 kg * 0.33 = 0.825 USD -> 83 cent (yarim yuqoriga)
        self.assertEqual(purchases.balance(self.db,sid),83)
        m=next(x for x in d['materials'] if x['id']==mid)
        self.assertEqual((m['stock'],m['unitLabel'],m['low']),('2.5','kg',True))
        line=d['purchases'][0]['lines'][0]
        self.assertEqual((line['kind'],line['qty'],line['total']),('material','2.5',83))

    def test_mixed_purchase_and_idempotent_retry(self):
        sid=self.supplier();mid=self.material()
        args=dict(supplierId=sid,lines=[{'pack':self.pack,'qty':4,'price':'1'},{'material':mid,'qty':'10','price':'2'}])
        for _ in range(2):
            purchases.handle(self.db,5,'purchase',args,source=777);self.db.commit()
        self.assertEqual(purchases.balance(self.db,sid),2400)
        self.assertEqual(warehouse.stock(self.db,self.pack),4)
        self.assertEqual(purchases.material_stock(self.db,mid),10000)

    def test_roles(self):
        sid=self.supplier()
        for actor in (2,3):
            with self.assertRaises(ValueError):
                self.call(actor,'purchase',supplierId=sid,lines=[{'pack':self.pack,'qty':1,'price':'1'}])
        with self.assertRaises(ValueError):
            self.call(2,'dashboard')
        self.assertIn('suppliers',self.call(3,'dashboard'))
        self.assertIsNone(warehouse.WEB_PRIMARY_OPERATOR.get())

    def test_bad_line_rolls_back_whole_purchase(self):
        sid=self.supplier()
        with self.assertRaises(ValueError):
            self.call(5,'purchase',supplierId=sid,lines=[{'pack':self.pack,'qty':3,'price':'1'},{'pack':self.pack,'qty':3,'price':'-1'}])
        with self.assertRaises(ValueError):
            self.call(5,'purchase',supplierId=sid,lines=[{'material':999,'qty':'1','price':'1'}])
        with self.assertRaises(ValueError):
            self.call(5,'purchase',supplierId=999,lines=[{'pack':self.pack,'qty':1,'price':'1'}])
        self.assertEqual(warehouse.stock(self.db,self.pack),0)
        self.assertEqual(purchases.balance(self.db,sid),0)

    def test_duplicate_names_rejected(self):
        self.supplier('Bir');self.material('Gips')
        with self.assertRaises(ValueError):self.call(1,'supplier_add',name='bir')
        with self.assertRaises(ValueError):self.call(1,'material_add',name='GIPS',unit='kg')
        with self.assertRaises(ValueError):self.call(1,'material_add',name='Boshqa',unit='tonna')

    def test_pay_supplier_from_cashbox(self):
        sid=self.supplier()
        self.call(5,'purchase',supplierId=sid,lines=[{'pack':self.pack,'qty':10,'price':'3'}])
        self.fund_cashbox(10000)
        d=self.call(1,'pay',supplierId=sid,amount='12.50',note='naqd')
        self.assertEqual(d['summary']['totalDebt'],1750)
        self.assertEqual(d['summary']['monthPaid'],1250)
        exp=self.db.execute('SELECT amount_usd,category,recipient FROM cashier_expenses').fetchone()
        self.assertEqual(tuple(exp),(1250,purchases.SUPPLIER_PAY_CATEGORY,'Kimyo zavod'))
        led=self.call(3,'ledger',supplierId=sid)
        self.assertEqual([i['type'] for i in led['items']],['payment','purchase'])
        self.assertEqual(led['debt'],1750)

    def test_cannot_overpay_or_pay_without_cash(self):
        sid=self.supplier()
        self.call(5,'purchase',supplierId=sid,lines=[{'pack':self.pack,'qty':1,'price':'5'}])
        with self.assertRaises(ValueError):   # kassada pul yo'q
            self.call(1,'pay',supplierId=sid,amount='5')
        self.fund_cashbox(100000)
        with self.assertRaises(ValueError):   # qarzdan ko'p
            self.call(1,'pay',supplierId=sid,amount='6')
        with self.assertRaises(ValueError):   # omborchi to'lay olmaydi
            self.call(5,'pay',supplierId=sid,amount='1')
        self.assertEqual(purchases.balance(self.db,sid),500)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cashier_expenses').fetchone()[0],0)

    def test_produce_consumes_materials_and_adds_product(self):
        sid=self.supplier();chalk=self.material('Bo‘r');glue=self.material('Yelim',unit='l')
        self.call(5,'purchase',supplierId=sid,lines=[{'material':chalk,'qty':'100','price':'0.1'},{'material':glue,'qty':'5','price':'2'}])
        d=self.call(5,'produce',pack=self.pack,qty=20,inputs=[{'material':chalk,'qty':'40.5'},{'material':glue,'qty':'1.25'}],note='smena 1')
        self.assertEqual(warehouse.stock(self.db,self.pack),20)
        self.assertEqual(purchases.material_stock(self.db,chalk),59500)
        self.assertEqual(purchases.material_stock(self.db,glue),3750)
        self.assertEqual(d['productions'][0]['qty'],20)
        self.assertEqual(self.db.execute('SELECT move FROM productions').fetchone()[0] is not None,True)

    def test_produce_fails_atomically_when_material_short(self):
        sid=self.supplier();chalk=self.material()
        self.call(5,'purchase',supplierId=sid,lines=[{'material':chalk,'qty':'1','price':'1'}])
        with self.assertRaisesRegex(ValueError,'yetarli emas'):
            self.call(5,'produce',pack=self.pack,qty=5,inputs=[{'material':chalk,'qty':'2'}])
        self.assertEqual(warehouse.stock(self.db,self.pack),0)
        self.assertEqual(purchases.material_stock(self.db,chalk),1000)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM productions').fetchone()[0],0)

    def test_material_use_and_writeoff(self):
        sid=self.supplier();mid=self.material()
        self.call(5,'purchase',supplierId=sid,lines=[{'material':mid,'qty':'10','price':'1'}])
        self.call(5,'material_use',materialId=mid,qty='1.5')
        with self.assertRaises(ValueError):   # sababsiz brak yo'q
            self.call(5,'material_writeoff',materialId=mid,qty='1')
        d=self.call(5,'material_writeoff',materialId=mid,qty='0.5',note='namlangan')
        self.assertEqual(purchases.material_stock(self.db,mid),8000)
        self.assertEqual([m['kind'] for m in d['materialMoves']],['writeoff','use','in'])
        with self.assertRaises(ValueError):
            self.call(5,'material_use',materialId=mid,qty='9')

    def test_parsers(self):
        self.assertEqual(purchases.parse_milli('2,125'),2125)
        self.assertEqual(purchases.milli_text(2500),'2.5')
        self.assertEqual(purchases.milli_text(3000),'3')
        for bad in ('0','-1','1.0001','abc','NaN'):
            with self.assertRaises(ValueError):purchases.parse_milli(bad)
        self.assertEqual(purchases.parse_cents('0'),0)
        with self.assertRaises(ValueError):purchases.parse_cents('0',allow_zero=False)
        with self.assertRaises(ValueError):purchases.parse_cents('1.001')

    def test_supplier_category_not_in_manual_expense_list(self):
        self.assertNotIn(purchases.SUPPLIER_PAY_CATEGORY,core.cashier_expense_categories())
        self.fund_cashbox(100000)
        with self.assertRaises(ValueError):
            core.add_cashier_expense(self.db,3,100,purchases.SUPPLIER_PAY_CATEGORY,'x','',123)


if __name__=='__main__':
    unittest.main()
