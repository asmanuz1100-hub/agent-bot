"""Sex ishchilari (HR): kartochka, davomat, oylik va avans. Tizim foydalanuvchilari bu yerda yo'q."""
import json
import unittest
from datetime import datetime

import core
import hr

# 2026-10-15 12:00 Toshkent
NOW=int(datetime(2026,10,15,12,0,tzinfo=hr.TZ).timestamp())


class HrTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1,'admin','Rahbar'),(2,'agent','Ali'),(3,'cashier','Kassir'),(5,'warehouse','Omborchi')])
        self.db.commit()
        self.n=0

    def tearDown(self):self.db.close()

    def call(self,op,actor=1,**payload):
        self.n+=1
        try:
            d=hr.handle(self.db,actor,op,payload,source=5000+self.n,now=NOW)
            self.db.commit()
            json.dumps(d)
            return d
        except Exception:
            self.db.rollback()
            raise

    def worker(self,name='Karim Usta',salary='3000000',**kw):
        return self.call('worker_add',name=name,salary=salary,**kw)['worker']['id']

    def cash(self,som):
        # kassa kursi 12 500 va kassaga qabul qilingan USD
        self.db.execute("INSERT INTO meta(key,value) VALUES('cashier_uzs_per_usd','12500')")
        self.db.execute("INSERT INTO handovers(agent,amount,amount_usd,status,ts,cashier) VALUES(2,0,?,'accepted',1,3)",(som*100//12500+100,))
        self.db.commit()

    def test_system_users_are_not_workers(self):
        self.worker()
        o=self.call('overview')
        self.assertEqual([w['name'] for w in o['workers']],['Karim Usta'])
        with self.assertRaises(ValueError):self.call('worker',id=2)

    def test_add_edit_and_salary_history(self):
        wid=self.worker(position='Quyuvchi',phone='+998 90 111 22 33',hire_date='2025-03-01',salaryFrom='2026-09')
        w=self.call('worker',id=wid)['worker']
        self.assertEqual((w['card']['position'],w['card']['phone'],w['card']['hire_date'],w['salary']),('Quyuvchi','+998 90 111 22 33','2025-03-01',3000000))
        self.call('worker_save',id=wid,name='Karim Usta',position='Katta usta',salary='3500000',salaryFrom='2026-11')
        self.assertEqual(hr.salary_for(self.db,wid,'2026-10'),3000000)
        self.assertEqual(hr.salary_for(self.db,wid,'2026-11'),3500000)
        self.assertEqual(hr.salary_for(self.db,wid,'2026-08'),0)
        self.assertEqual([h['from'] for h in self.call('worker',id=wid)['worker']['salaryHistory']],['2026-11','2026-09'])
        with self.assertRaises(ValueError):self.call('worker_add',name='karim usta')        # takror ism
        with self.assertRaises(ValueError):self.call('worker_add',name='')
        with self.assertRaises(ValueError):self.call('worker_save',id=wid,name='K',hire_date='15.03.2025')
        with self.assertRaises(ValueError):self.call('worker_save',id=wid,name='K',phone='abc')

    def test_close_and_reopen(self):
        wid=self.worker()
        self.call('worker_close',id=wid)
        self.assertEqual(self.call('overview')['workers'],[])
        o=self.call('overview',closed=True)
        self.assertEqual((len(o['workers']),o['totals']['closed'],o['totals']['count']),(1,1,0))
        with self.assertRaises(ValueError):self.call('pay_add',id=wid,kind='bonus',amount='1000')
        self.call('worker_open',id=wid)
        self.assertEqual(len(self.call('overview')['workers']),1)

    def test_attendance(self):
        a=self.worker('A');b=self.worker('B');c=self.worker('C')
        self.call('attendance_set',id=a,day='2026-10-14',status='late',note='30 daqiqa')
        self.call('attendance_set',id=b,day='2026-10-14',status='absent')
        with self.assertRaises(ValueError):self.call('attendance_set',id=a,day='2026-10-16',status='present')
        with self.assertRaises(ValueError):self.call('attendance_set',id=a,day='2026-10-14',status='party')
        o=self.call('overview',day='2026-10-14')
        self.assertEqual((o['totals']['present'],o['totals']['absent'],o['totals']['unmarked']),(1,1,1))
        o=self.call('attendance_bulk',day='2026-10-15',items=[{'id':a,'status':'present'},{'id':c,'status':'off'}])
        self.assertEqual((o['totals']['present'],o['totals']['unmarked']),(1,1))
        w=self.call('worker',id=a)['worker']
        self.assertEqual(w['attendance']['worked'],2)
        self.assertTrue(next(x for x in w['calendar'] if x['day']=='2026-10-31')['future'])
        self.call('attendance_set',id=a,day='2026-10-14',status='clear')
        self.assertEqual(self.call('worker',id=a)['worker']['attendance']['worked'],1)

    def test_payroll_bonus_penalty_advance_salary(self):
        wid=self.worker()
        self.cash(5000000)
        self.call('pay_add',id=wid,kind='bonus',amount='500000',note='Reja bajarildi')
        with self.assertRaises(ValueError):self.call('pay_add',id=wid,kind='penalty',amount='100000')   # sababsiz
        self.call('pay_add',id=wid,kind='penalty',amount='200 000',note='Kechikish')
        self.call('pay_add',id=wid,kind='advance',amount='1000000',expectedRate='12500')
        p=self.call('worker',id=wid)['worker']['payroll']
        self.assertEqual((p['salary'],p['due'],p['paid'],p['remaining']),(3000000,3300000,1000000,2300000))
        with self.assertRaises(ValueError):self.call('pay_add',id=wid,kind='salary',amount='2300001')
        w=self.call('pay_add',id=wid,kind='salary',amount='2300000')['worker']
        self.assertEqual(w['payroll']['remaining'],0)
        self.assertEqual([x['kind'] for x in w['payments']],['salary','advance','penalty','bonus'])
        exp=self.db.execute("SELECT category,currency,amount_uzs,recipient FROM cashier_expenses ORDER BY id").fetchall()
        self.assertEqual([tuple(r)[:3] for r in exp],[(hr.SALARY_CATEGORY,'UZS',1000000),(hr.SALARY_CATEGORY,'UZS',2300000)])
        self.assertIn('Karim Usta',exp[0]['recipient'])
        self.assertEqual(self.call('overview')['totals']['paid'],3300000)

    def test_pay_needs_cash_and_rate(self):
        wid=self.worker()
        with self.assertRaises(ValueError):   # kassa kursi belgilanmagan
            self.call('pay_add',id=wid,kind='advance',amount='100000')
        self.cash(100000)
        with self.assertRaises(ValueError):   # kassada pul yetmaydi
            self.call('pay_add',id=wid,kind='advance',amount='3000000')
        with self.assertRaises(ValueError):   # kurs o'zgargan
            self.call('pay_add',id=wid,kind='advance',amount='10000',expectedRate='12000')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM hr_pay').fetchone()[0],0)

    def test_pay_is_idempotent_by_source(self):
        wid=self.worker()
        for _ in range(2):
            hr.handle(self.db,1,'pay_add',{'id':wid,'kind':'bonus','amount':'1000'},source=42,now=NOW);self.db.commit()
        self.assertEqual(hr.payroll_row(self.db,wid,'2026-10')['bonus'],1000)

    def test_only_admin_can_write(self):
        wid=self.worker()
        for op,args in (('worker_add',{'name':'X'}),('worker_save',{'id':wid,'name':'X'}),('worker_close',{'id':wid}),
                        ('attendance_set',{'id':wid,'day':'2026-10-14','status':'present'}),
                        ('pay_add',{'id':wid,'kind':'bonus','amount':'1'})):
            with self.assertRaises(ValueError):self.call(op,actor=3,**args)


if __name__=='__main__':
    unittest.main()
