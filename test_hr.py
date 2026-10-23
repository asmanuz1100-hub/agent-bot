"""Xodimlar (HR): kartochka, davomat, oylik/avans, faoliyat tarixi."""
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
                            [(1,'admin','Rahbar'),(2,'agent','Ali'),(3,'cashier','Kassir'),(5,'warehouse','Omborchi'),
                             (6,'disabled','Eski agent'),(7,'sales','Sotuvchi')])
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

    def cash(self,som):
        # kassa kursi 12 500 va kassaga qabul qilingan USD
        self.db.execute("INSERT INTO meta(key,value) VALUES('cashier_uzs_per_usd','12500')")
        self.db.execute("INSERT INTO handovers(agent,amount,amount_usd,status,ts,cashier) VALUES(2,0,?,'accepted',1,3)",(som*100//12500+100,))
        self.db.commit()

    def test_profile_save_and_salary_history(self):
        d=self.call('profile_save',id=5,position='Katta omborchi',phone='+998 90 111 22 33',hire_date='2025-03-01',
                    birth_date='1990-05-20',address='Qo‘qon',passport='AA1234567',emergency='Akasi +998901112233',
                    note='Kalitlar unda',salary='4000000',salaryFrom='2026-09')
        p=d['employee']['profile']
        self.assertEqual((p['position'],p['phone'],p['hire_date'],p['salary']),('Katta omborchi','+998 90 111 22 33','2025-03-01',4000000))
        self.call('profile_save',id=5,position='Katta omborchi',salary='5000000',salaryFrom='2026-11')
        self.assertEqual(hr.salary_for(self.db,5,'2026-10'),4000000)
        self.assertEqual(hr.salary_for(self.db,5,'2026-11'),5000000)
        self.assertEqual(hr.salary_for(self.db,5,'2026-08'),0)
        e=self.call('employee',id=5)['employee']
        self.assertEqual([h['from'] for h in e['salaryHistory']],['2026-11','2026-09'])
        with self.assertRaises(ValueError):self.call('profile_save',id=5,hire_date='15.03.2025')
        with self.assertRaises(ValueError):self.call('profile_save',id=5,phone='abc')
        with self.assertRaises(ValueError):self.call('profile_save',id=999)

    def test_attendance_manual_and_agent_auto(self):
        start=int(datetime(2026,10,14,9,0,tzinfo=hr.TZ).timestamp())
        self.db.execute('INSERT INTO shifts(agent,start,"end") VALUES(2,?,?)',(start,start+3600));self.db.commit()
        self.call('attendance_set',id=3,day='2026-10-14',status='late',note='30 daqiqa')
        self.call('attendance_set',id=5,day='2026-10-14',status='absent')
        with self.assertRaises(ValueError):self.call('attendance_set',id=5,day='2026-10-16',status='present')
        with self.assertRaises(ValueError):self.call('attendance_set',id=5,day='2026-10-14',status='party')
        o=self.call('overview',day='2026-10-14')
        by={e['id']:e for e in o['employees']}
        self.assertNotIn(6,by)   # yopilgan agent ro'yxatda yo'q
        self.assertEqual(by[2]['day']['status'],'present');self.assertTrue(by[2]['day']['auto'])
        self.assertEqual(by[3]['day']['status'],'late')
        self.assertEqual(by[3]['attendance']['worked'],1)
        self.assertEqual(o['totals']['absent'],1)
        # qo'lda belgi avtomatikdan ustun, «auto» esa qaytaradi
        self.call('attendance_set',id=2,day='2026-10-14',status='sick')
        cal=self.call('employee',id=2)['employee']['calendar']
        self.assertEqual(next(c for c in cal if c['day']=='2026-10-14')['status'],'sick')
        self.assertTrue(next(c for c in cal if c['day']=='2026-10-31')['future'])
        self.call('attendance_set',id=2,day='2026-10-14',status='auto')
        cal=self.call('employee',id=2)['employee']['calendar']
        self.assertEqual(next(c for c in cal if c['day']=='2026-10-14')['status'],'present')

    def test_attendance_bulk(self):
        o=self.call('attendance_bulk',day='2026-10-15',items=[{'id':3,'status':'present'},{'id':5,'status':'present'},{'id':7,'status':'off'}])
        self.assertEqual((o['totals']['present'],o['totals']['unmarked']),(2,2))

    def test_payroll_bonus_penalty_advance_salary(self):
        self.call('profile_save',id=5,salary='3000000')
        self.cash(5000000)
        self.call('pay_add',id=5,kind='bonus',amount='500000',note='Reja bajarildi')
        with self.assertRaises(ValueError):self.call('pay_add',id=5,kind='penalty',amount='100000')   # sababsiz
        self.call('pay_add',id=5,kind='penalty',amount='200 000',note='Kechikish')
        self.call('pay_add',id=5,kind='advance',amount='1000000',expectedRate='12500')
        e=self.call('employee',id=5)['employee']
        p=e['payroll']
        self.assertEqual((p['salary'],p['due'],p['paid'],p['remaining']),(3000000,3300000,1000000,2300000))
        with self.assertRaises(ValueError):self.call('pay_add',id=5,kind='salary',amount='2300001')
        e=self.call('pay_add',id=5,kind='salary',amount='2300000')['employee']
        self.assertEqual(e['payroll']['remaining'],0)
        self.assertEqual([x['kind'] for x in e['payments']],['salary','advance','penalty','bonus'])
        exp=self.db.execute("SELECT category,currency,amount_uzs FROM cashier_expenses ORDER BY id").fetchall()
        self.assertEqual([tuple(r) for r in exp],[(hr.SALARY_CATEGORY,'UZS',1000000),(hr.SALARY_CATEGORY,'UZS',2300000)])
        o=self.call('overview')
        self.assertEqual(o['totals']['paid'],3300000)

    def test_pay_needs_cash_and_rate(self):
        self.call('profile_save',id=5,salary='3000000')
        with self.assertRaises(ValueError):   # kassa kursi belgilanmagan
            self.call('pay_add',id=5,kind='advance',amount='100000')
        self.cash(100000)
        with self.assertRaises(ValueError):   # kassada pul yetmaydi
            self.call('pay_add',id=5,kind='advance',amount='3000000')
        with self.assertRaises(ValueError):   # kurs o'zgargan
            self.call('pay_add',id=5,kind='advance',amount='10000',expectedRate='12000')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM hr_pay').fetchone()[0],0)

    def test_pay_is_idempotent_by_source(self):
        self.call('profile_save',id=5,salary='3000000')
        for _ in range(2):
            hr.handle(self.db,1,'pay_add',{'id':5,'kind':'bonus','amount':'1000'},source=42,now=NOW);self.db.commit()
        self.assertEqual(hr.payroll_row(self.db,5,'2026-10')['bonus'],1000)

    def test_only_admin_can_write(self):
        for op,args in (('profile_save',{'position':'x'}),('attendance_set',{'day':'2026-10-14','status':'present'}),
                        ('pay_add',{'kind':'bonus','amount':'1'})):
            with self.assertRaises(ValueError):self.call(op,actor=3,id=5,**args)

    def test_activity_and_kpi(self):
        ts=int(datetime(2026,10,10,10,0,tzinfo=hr.TZ).timestamp())
        self.db.execute("INSERT INTO clients(id,agent,name,shop_name,phone,created_ts) VALUES(1,2,'M','Do‘kon','+1',?)",(ts,))
        self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source) VALUES(2,2,1,'delivery',1,5,0,2500,'',?,1)",(ts,))
        self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source) VALUES(2,2,1,'payment',0,0,0,1000,'',?,2)",(ts+60,))
        self.db.execute("INSERT INTO client_visits(client,actor,status,note,ts) VALUES(1,2,'active','zo‘r',?)",(ts+120,))
        self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source) VALUES(2,2,1,'delivery',1,1,0,100,'',?,3)",(ts-40*86400,))
        self.db.commit()
        e=self.call('employee',id=2)['employee']
        self.assertEqual((e['kpi']['deliveriesUsd'],e['kpi']['paymentsUsd'],e['kpi']['visits'],e['kpi']['newClients']),(2500,1000,1,1))
        self.assertEqual([a['type'] for a in e['activity']],['visit','event','event'])
        self.assertIn('Do‘kon',e['activity'][1]['detail'])


if __name__=='__main__':
    unittest.main()
