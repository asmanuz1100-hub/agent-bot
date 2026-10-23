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
        self.assertEqual(self.call('overview')['money']['UZS']['paid'],3300000)

    def test_pay_needs_cash_and_rate(self):
        wid=self.worker()
        with self.assertRaises(ValueError):   # kassa kursi belgilanmagan
            self.call('pay_add',id=wid,kind='advance',amount='100000')
        self.cash(100000)
        with self.assertRaises(ValueError):   # kassada pul yetmaydi
            self.call('pay_add',id=wid,kind='advance',amount='3000000')
        with self.assertRaises(ValueError):   # kurs o'zgargan
            self.call('pay_add',id=wid,kind='advance',amount='10000',expectedRate='12000')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM hr_w_pay').fetchone()[0],0)

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


    def test_init_survives_first_version_tables(self):
        # Birinchi HR versiyasi (7fed78e) jonli bazada user_id ustunli hr_salary/hr_attendance/hr_pay yaratgan.
        # Yangi kod ularga tegmasligi va ishga tushishi kerak.
        old_schema=('''
            CREATE TABLE IF NOT EXISTS hr_profiles(user_id INTEGER PRIMARY KEY, position TEXT);
            CREATE TABLE IF NOT EXISTS hr_salary(user_id INTEGER NOT NULL, from_month TEXT NOT NULL, salary_uzs INTEGER NOT NULL, actor INTEGER, ts INTEGER NOT NULL, PRIMARY KEY(user_id,from_month));
            CREATE TABLE IF NOT EXISTS hr_attendance(user_id INTEGER NOT NULL, day TEXT NOT NULL, status TEXT NOT NULL, note TEXT, actor INTEGER, ts INTEGER NOT NULL, PRIMARY KEY(user_id,day));
            CREATE TABLE IF NOT EXISTS hr_pay(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, kind TEXT NOT NULL, month TEXT NOT NULL, amount_uzs INTEGER NOT NULL, note TEXT, expense INTEGER, actor INTEGER, ts INTEGER NOT NULL, source INTEGER UNIQUE);
            CREATE INDEX IF NOT EXISTS idx_hr_pay_month ON hr_pay(month,user_id);
        ''')
        if isinstance(self.db,core.PostgresDB):
            old_schema=old_schema.replace('INTEGER PRIMARY KEY','BIGSERIAL PRIMARY KEY').replace(' INTEGER',' BIGINT')
        for stmt in old_schema.split(';'):
            if stmt.strip():self.db.execute(stmt)
        hr.init(self.db)
        wid=self.worker()
        self.call('attendance_set',id=wid,day='2026-10-14',status='present')
        self.call('pay_add',id=wid,kind='bonus',amount='1000')
        self.assertEqual(hr.payroll_row(self.db,wid,'2026-10')['due'],3001000)

    def test_usd_worker_paid_in_usd_and_uzs(self):
        wid=self.worker('Dollar usta',salary='600',currency='USD')
        w=self.call('worker',id=wid)['worker']
        self.assertEqual((w['currency'],w['salary'],w['payroll']['currency']),('USD',60000,'USD'))
        self.cash(20000000)                      # kurs 12 500
        self.call('pay_add',id=wid,kind='bonus',amount='50.50',note='reja')
        self.call('pay_add',id=wid,kind='advance',amount='100')                                  # $100 naqd dollar
        self.call('pay_add',id=wid,kind='advance',amount='1250000',payCurrency='UZS',expectedRate='12500')  # = $100
        p=self.call('worker',id=wid)['worker']['payroll']
        self.assertEqual((p['due'],p['paid'],p['remaining']),(65050,20000,45050))
        with self.assertRaises(ValueError):self.call('pay_add',id=wid,kind='salary',amount='450.51')
        w=self.call('pay_add',id=wid,kind='salary',amount='450.50')['worker']
        self.assertEqual(w['payroll']['remaining'],0)
        uzs=next(x for x in w['payments'] if x['paidCurrency']=='UZS')
        self.assertEqual((uzs['amount'],uzs['paidAmount'],uzs['rate']),(10000,1250000,12500))
        exp=self.db.execute('SELECT currency,amount_usd,amount_uzs FROM cashier_expenses ORDER BY id').fetchall()
        self.assertEqual([tuple(r) for r in exp],[('USD',10000,0),('UZS',10000,1250000),('USD',45050,0)])
        o=self.call('overview')
        self.assertEqual((o['money']['USD']['paid'],o['money']['UZS']['paid']),(65050,0))
        with self.assertRaises(ValueError):self.call('worker_add',name='X',salary='1.001',currency='USD')
        with self.assertRaises(ValueError):self.call('worker_add',name='Y',currency='EUR')

    def test_uzs_worker_paid_in_usd(self):
        wid=self.worker()                         # 3 000 000 so'm
        self.cash(5000000)
        self.call('pay_add',id=wid,kind='advance',amount='40',payCurrency='USD',expectedRate='12500')
        self.assertEqual(self.call('worker',id=wid)['worker']['payroll']['advance'],500000)

    def test_currency_change_only_before_payments(self):
        wid=self.worker()
        with self.assertRaises(ValueError):       # valyuta o'zgarsa oylik ham kerak
            self.call('worker_save',id=wid,name='Karim Usta',currency='USD')
        self.call('worker_save',id=wid,name='Karim Usta',currency='USD',salary='300')
        w=self.call('worker',id=wid)['worker']
        self.assertEqual((w['currency'],w['salary'],len(w['salaryHistory'])),('USD',30000,1))
        self.call('pay_add',id=wid,kind='bonus',amount='10')
        with self.assertRaises(ValueError):
            self.call('worker_save',id=wid,name='Karim Usta',currency='UZS',salary='1000000')

    def test_migrates_uzs_only_columns(self):
        # Jonli bazadagi oldingi versiya: hr_w_salary.salary_uzs, hr_w_pay.amount_uzs, hr_workers.currency yo'q.
        big='BIGINT' if isinstance(self.db,core.PostgresDB) else 'INTEGER'
        for t in ('hr_w_pay','hr_w_salary','hr_w_attendance','hr_workers'):self.db.execute(f'DROP TABLE {t}')
        pk='BIGSERIAL PRIMARY KEY' if big=='BIGINT' else 'INTEGER PRIMARY KEY'
        self.db.execute(f"CREATE TABLE hr_workers(id {pk}, name TEXT NOT NULL, position TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', hire_date TEXT NOT NULL DEFAULT '', birth_date TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', passport TEXT NOT NULL DEFAULT '', emergency TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', active {big} NOT NULL DEFAULT 1, actor {big}, ts {big} NOT NULL, updated_ts {big} NOT NULL DEFAULT 0)")
        self.db.execute(f"CREATE TABLE hr_w_salary(worker_id {big} NOT NULL, from_month TEXT NOT NULL, salary_uzs {big} NOT NULL CHECK(salary_uzs>=0), actor {big}, ts {big} NOT NULL, PRIMARY KEY(worker_id,from_month))")
        self.db.execute(f"CREATE TABLE hr_w_attendance(worker_id {big} NOT NULL, day TEXT NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', actor {big}, ts {big} NOT NULL, PRIMARY KEY(worker_id,day))")
        self.db.execute(f"CREATE TABLE hr_w_pay(id {pk}, worker_id {big} NOT NULL, kind TEXT NOT NULL, month TEXT NOT NULL, amount_uzs {big} NOT NULL CHECK(amount_uzs>0), note TEXT NOT NULL DEFAULT '', expense {big}, actor {big}, ts {big} NOT NULL, source {big} UNIQUE)")
        self.db.execute("INSERT INTO hr_workers(name,ts) VALUES('Eski',1)")
        self.db.execute("INSERT INTO hr_w_salary(worker_id,from_month,salary_uzs,ts) VALUES(1,'2026-10',2000000,1)")
        self.db.execute("INSERT INTO hr_w_pay(worker_id,kind,month,amount_uzs,note,ts) VALUES(1,'bonus','2026-10',5000,'',1)")
        hr.init(self.db);hr.init(self.db)        # ikki marta — idempotent
        self.db.commit()
        p=self.call('worker',id=1)['worker']['payroll']
        self.assertEqual((p['currency'],p['salary'],p['bonus']),('UZS',2000000,5000))
        self.worker('Yangi',salary='100',currency='USD')

    def at(self,month):
        y,m=map(int,month.split('-'))
        return int(datetime(y,m,15,12,0,tzinfo=hr.TZ).timestamp())

    def pay(self,wid,kind,amount,month,**kw):
        self.n+=1
        hr.handle(self.db,1,'pay_add',dict(id=wid,kind=kind,amount=amount,month=month,**kw),source=9000+self.n,now=self.at(month))
        self.db.commit()
        return hr.payroll_row(self.db,wid,month)

    def test_spec_example_4m_salary_1m_advance_3m_final(self):
        wid=self.worker('Misol',salary='4000000')
        self.cash(10000000)
        p=self.pay(wid,'advance','1000000','2026-10')
        self.assertEqual((p['due'],p['paid'],p['remaining']),(4000000,1000000,3000000))
        with self.assertRaises(ValueError):self.pay(wid,'salary','3000001','2026-10')   # ortiqcha to'lov yo'q
        p=self.pay(wid,'salary','3000000','2026-10')
        self.assertEqual(p['remaining'],0)
        # kassadan avans bir marta, oylik bir marta chiqdi — jami 4 mln
        self.assertEqual(tuple(int(x) for x in self.db.execute('SELECT SUM(amount_uzs),COUNT(*) FROM cashier_expenses').fetchone()),(4000000,2))
        with self.assertRaises(ValueError):self.pay(wid,'salary','1','2026-10')         # ikkinchi marta to'lab bo'lmaydi

    def test_previous_month_balance_carries_over(self):
        wid=self.worker('Qoldiq',salary='4000000',salaryFrom='2026-09')
        self.cash(20000000)
        self.pay(wid,'advance','1000000','2026-09')           # sentabrdan 3 mln qoldi
        p=hr.payroll_row(self.db,wid,'2026-10')
        self.assertEqual((p['carry'],p['due'],p['remaining']),(3000000,4000000,7000000))
        p=self.pay(wid,'salary','7000000','2026-10')          # qarz + shu oy birga
        self.assertEqual(p['remaining'],0)
        self.assertEqual(hr.payroll_row(self.db,wid,'2026-11')['carry'],0)

    def test_overpaid_advance_is_visible_and_deducted_next_month(self):
        wid=self.worker('Ortiqcha',salary='2000000',salaryFrom='2026-09')
        self.cash(20000000)
        p=self.pay(wid,'advance','2500000','2026-09')          # avans oylikdan ko'p
        self.assertEqual((p['remaining'],p['overpaid']),(-500000,500000))
        p=hr.payroll_row(self.db,wid,'2026-10')
        self.assertEqual((p['carry'],p['remaining'],p['overpaid']),(-500000,1500000,0))
        o=hr.overview(self.db,'2026-09',now=self.at('2026-09'))
        self.assertEqual((o['money']['UZS']['remaining'],o['money']['UZS']['overpaid']),(0,500000))

    def test_closed_worker_does_not_accrue_until_reopened(self):
        wid=self.worker('Ketgan',salary='1000000',salaryFrom='2026-08')
        hr.set_active(self.db,1,wid,False,now=self.at('2026-08'));self.db.commit()
        self.assertEqual((hr.salary_for(self.db,wid,'2026-08'),hr.salary_for(self.db,wid,'2026-09')),(1000000,0))
        hr.set_active(self.db,1,wid,True,now=self.at('2026-10'));self.db.commit()
        p=hr.payroll_row(self.db,wid,'2026-10')
        self.assertEqual((p['carry'],p['salary'],p['remaining']),(1000000,1000000,2000000))   # avgust to'lanmagan + oktabr

    def test_mixed_currency_rounding_uses_stored_rate(self):
        wid=self.worker('Dollarchi',salary='100',currency='USD')
        self.cash(5000000)
        p=self.pay(wid,'advance','1000001','2026-10',payCurrency='UZS',expectedRate='12500')
        self.assertEqual(p['advance'],8000)                     # 80.00008 $ -> 80.00 $ (yarim yuqoriga)
        row=self.db.execute('SELECT paid_amount,rate FROM hr_w_pay').fetchone()
        self.assertEqual(tuple(row),(1000001,12500))

    def test_agent_cash_does_not_touch_worker_payroll(self):
        wid=self.worker('Alohida',salary='1000000')
        before=hr.payroll_row(self.db,wid,'2026-10')
        self.db.execute("INSERT INTO handovers(agent,amount,amount_usd,status,ts,cashier) VALUES(2,0,50000,'accepted',?,3)",(NOW,))
        self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source) VALUES(2,2,NULL,'payment',0,0,0,50000,'',?,77)",(NOW,))
        self.db.commit()
        self.assertEqual(hr.payroll_row(self.db,wid,'2026-10'),before)

    def test_department_saved(self):
        wid=self.worker('Bolimli',department='Quyish sexi',position='Usta')
        c=self.call('worker',id=wid)['worker']['card']
        self.assertEqual((c['department'],c['position']),('Quyish sexi','Usta'))

if __name__=='__main__':
    unittest.main()
