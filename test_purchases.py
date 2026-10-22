import unittest

import core
import cashier_api
import purchases
import warehouse
import warehouse_api as api


class PurchasesTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1,'admin','Rahbar'),(2,'agent','Ali'),(3,'cashier','Kassir'),(5,'warehouse','Omborchi')])
        self.db.commit()
        self.pack=next(iter(core.PRODUCTS))

    def tearDown(self):self.db.close()

    def call(self,actor,action,**payload):
        try:
            data=api.handle(self.db,actor,action,payload)
            self.db.commit()
            return data
        except Exception:
            self.db.rollback()
            raise

    def supplier(self,name='Kimyo zavod'):
        return self.call(5,'supplier_add',name=name,phone='+998901112233',requestId=f'sup-{len(name)}-add')['supplier']

    def fund_cashbox(self,cents):
        # Kassaga qabul qilingan pul: purchases testlari uchun kassa qoldig'ini to'g'ridan-to'g'ri beramiz.
        self.db.execute("""INSERT INTO handovers(agent,amount,amount_usd,status,ts,cashier)
            VALUES(2,0,?,'accepted',1,3)""",(cents,))
        self.db.commit()

    def test_purchase_adds_stock_and_supplier_debt(self):
        sid=self.supplier()
        before=warehouse.stock(self.db,self.pack)
        d=self.call(5,'purchase',supplier=sid,lines=[{'pack':self.pack,'qty':10,'price':'2.50'}],note='1-partiya',
                    requestId='purchase-0001')
        self.assertEqual(warehouse.stock(self.db,self.pack),before+10)
        self.assertEqual(purchases.balance(self.db,sid),2500)
        self.assertEqual(d['totalDebt'],2500)
        moves=self.db.execute("SELECT kind,qty,note FROM warehouse_moves WHERE kind='in'").fetchall()
        self.assertEqual(len(moves),1)
        self.assertIn(f"Xarid #{d['purchase']}",moves[0]['note'])

    def test_purchase_retry_is_idempotent(self):
        sid=self.supplier()
        for _ in range(2):
            self.call(5,'purchase',supplier=sid,lines=[{'pack':self.pack,'qty':4,'price':'1'}],requestId='purchase-same')
        self.assertEqual(purchases.balance(self.db,sid),400)
        self.assertEqual(warehouse.stock(self.db,self.pack),4)

    def test_only_keeper_or_admin_can_buy(self):
        sid=self.supplier()
        with self.assertRaises(ValueError):
            purchases.record_purchase(self.db,3,sid,[(self.pack,1,100)])
        with self.assertRaises(ValueError):
            api.handle(self.db,2,'purchase',{'supplier':sid,'lines':[]})
        pid=purchases.record_purchase(self.db,1,sid,[(self.pack,2,100)])
        self.assertTrue(pid)
        self.assertEqual(warehouse.stock(self.db,self.pack),2)

    def test_bad_input_rolls_back_everything(self):
        sid=self.supplier()
        with self.assertRaises(ValueError):
            self.call(5,'purchase',supplier=sid,lines=[{'pack':self.pack,'qty':3,'price':'1'},
                                                       {'pack':self.pack,'qty':3,'price':'-1'}],requestId='purchase-bad1')
        self.assertEqual(warehouse.stock(self.db,self.pack),0)
        self.assertEqual(purchases.balance(self.db,sid),0)
        with self.assertRaises(ValueError):
            self.call(5,'purchase',supplier=999,lines=[{'pack':self.pack,'qty':1,'price':'1'}],requestId='purchase-bad2')

    def test_duplicate_supplier_name_rejected(self):
        self.supplier('Bir')
        with self.assertRaises(ValueError):
            self.call(5,'supplier_add',name='bir',requestId='sup-dup-0002')

    def test_cashier_pays_supplier_from_cashbox(self):
        sid=self.supplier()
        self.call(5,'purchase',supplier=sid,lines=[{'pack':self.pack,'qty':10,'price':'3'}],requestId='purchase-0002')
        self.fund_cashbox(10000)
        res=cashier_api.mutate(self.db,3,'supplier_pay',{'supplierId':sid,'amount':'12.50','requestId':'pay-supplier-1'})
        self.db.commit()
        self.assertIn('ТАЪМИНОТЧИГА ТЎЛОВ',res['_notify']['text'])
        self.assertEqual(purchases.balance(self.db,sid),3000-1250)
        exp=self.db.execute('SELECT amount_usd,category,recipient FROM cashier_expenses').fetchone()
        self.assertEqual((exp[0],exp[1],exp[2]),(1250,purchases.SUPPLIER_PAY_CATEGORY,'Kimyo zavod'))
        led=purchases.ledger(self.db,3,sid)
        self.assertEqual([i['type'] for i in led['items']],['payment','purchase'])
        self.assertEqual(led['debt'],1750)

    def test_cannot_overpay_supplier(self):
        sid=self.supplier()
        self.call(5,'purchase',supplier=sid,lines=[{'pack':self.pack,'qty':1,'price':'5'}],requestId='purchase-0003')
        self.fund_cashbox(100000)
        with self.assertRaises(ValueError):
            cashier_api.mutate(self.db,3,'supplier_pay',{'supplierId':sid,'amount':'6','requestId':'pay-supplier-2'})
        self.db.rollback()
        self.assertEqual(purchases.balance(self.db,sid),500)

    def test_supplier_category_not_in_manual_expense_list(self):
        self.assertNotIn(purchases.SUPPLIER_PAY_CATEGORY,core.cashier_expense_categories())
        with self.assertRaises(ValueError):
            core.add_cashier_expense(self.db,3,100,purchases.SUPPLIER_PAY_CATEGORY,'x','',123)


if __name__=='__main__':
    unittest.main()
