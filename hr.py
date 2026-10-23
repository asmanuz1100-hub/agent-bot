"""Xodimlar (HR): kartochka, davomat, oylik/avans va faoliyat tarixi — rahbar web paneli uchun.

- Kartochka: lavozim, sanalar, manzil, hujjat, favqulodda aloqa. Telefon user_profiles bilan umumiy
  (xodim Mini App'da o'zi ham o'zgartira oladi).
- Oylik tarix bilan saqlanadi (hr_salary: qaysi oydan boshlab qancha), shuning uchun oylik
  o'zgarsa o'tgan oylar hisobi o'zgarmaydi.
- Davomat: rahbar belgilaydi; agentda belgi bo'lmasa, o'sha kuni smena ochgan bo'lsa «Keldi» (avto).
- Oylik hisob (so'mda): hisoblandi = oylik + bonus − jarima; to'landi = avans + oylik to'lovi.
  Avans va oylik to'lovi kassadan «👷 Иш ҳақи» xarajati bo'lib chiqadi (core.add_cashier_expense_uzs).
Yozuvlar o'chirilmaydi; xato bo'lsa teskari yozuv (jarima ↔ bonus) kiritiladi.
"""
import re
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import core
from core import PostgresDB
import profiles
import staff

TZ=ZoneInfo('Asia/Tashkent')
SALARY_CATEGORY='👷 Иш ҳақи'
ATTENDANCE={'present':'Keldi','late':'Kechikdi','absent':'Kelmadi','off':'Dam olish','sick':'Kasal','vacation':'Ta’til'}
WORKED=('present','late')
PAY_KINDS={'bonus':'Bonus','penalty':'Jarima','advance':'Avans','salary':'Oylik to‘lovi'}
CASH_KINDS=('advance','salary')
MAX_SOM=10**10
PROFILE_FIELDS={'position':80,'address':200,'passport':40,'emergency':120,'note':500}

SCHEMA='''
CREATE TABLE IF NOT EXISTS hr_profiles(user_id INTEGER PRIMARY KEY, position TEXT NOT NULL DEFAULT '', hire_date TEXT NOT NULL DEFAULT '', birth_date TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', passport TEXT NOT NULL DEFAULT '', emergency TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', actor INTEGER, updated_ts INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS hr_salary(user_id INTEGER NOT NULL, from_month TEXT NOT NULL, salary_uzs INTEGER NOT NULL CHECK(salary_uzs>=0), actor INTEGER, ts INTEGER NOT NULL, PRIMARY KEY(user_id,from_month));
CREATE TABLE IF NOT EXISTS hr_attendance(user_id INTEGER NOT NULL, day TEXT NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', actor INTEGER, ts INTEGER NOT NULL, PRIMARY KEY(user_id,day));
CREATE TABLE IF NOT EXISTS hr_pay(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, kind TEXT NOT NULL, month TEXT NOT NULL, amount_uzs INTEGER NOT NULL CHECK(amount_uzs>0), note TEXT NOT NULL DEFAULT '', expense INTEGER, actor INTEGER, ts INTEGER NOT NULL, source INTEGER UNIQUE);
CREATE INDEX IF NOT EXISTS idx_hr_attendance_day ON hr_attendance(day);
CREATE INDEX IF NOT EXISTS idx_hr_pay_month ON hr_pay(month,user_id);
'''
PG_SCHEMA=SCHEMA.replace('INTEGER PRIMARY KEY','BIGSERIAL PRIMARY KEY').replace(' INTEGER',' BIGINT')


def init(db):
    if isinstance(db,PostgresDB):
        for stmt in PG_SCHEMA.split(';'):
            if stmt.strip():db.execute(stmt)
    else:
        db.executescript(SCHEMA)


# ---------- yordamchilar ----------

def _now(now=None):
    return int(time.time() if now is None else now)


def today(now=None):
    return datetime.fromtimestamp(_now(now),TZ).date()


def this_month(now=None):
    return today(now).strftime('%Y-%m')


def _month(value,now=None):
    m=str(value or '').strip() or this_month(now)
    if not re.fullmatch(r'20[0-9]{2}-(0[1-9]|1[0-2])',m):raise ValueError('Oy noto‘g‘ri (YYYY-MM).')
    return m


def _day(value):
    s=str(value or '').strip()
    try:return date.fromisoformat(s)
    except ValueError:raise ValueError('Sana noto‘g‘ri (YYYY-MM-DD).')


def _opt_date(value,label):
    s=str(value or '').strip()
    if not s:return ''
    try:return date.fromisoformat(s).isoformat()
    except ValueError:raise ValueError(f'{label} noto‘g‘ri (YYYY-MM-DD).')


def _month_days(month):
    y,m=map(int,month.split('-'))
    first=date(y,m,1)
    nxt=date(y+(m==12),m%12+1,1)
    return first,nxt


def _ts(d):
    return int(datetime(d.year,d.month,d.day,tzinfo=TZ).timestamp())


def _som(value,label='Summa'):
    s=str(value if value is not None else '').replace(' ','').replace(',','')
    if not s.isdecimal():raise ValueError(f'{label}: butun so‘m kiriting.')
    n=int(s)
    if not 0<n<=MAX_SOM:raise ValueError(f'{label}: 1 dan {MAX_SOM:,} gacha.'.replace(',',' '))
    return n


def _text(value,label,limit):
    t=str(value or '').strip()
    if len(t)>limit:raise ValueError(f'{label} {limit} belgidan oshmasin.')
    return t


def _employee(db,uid):
    try:uid=int(uid)
    except (TypeError,ValueError):raise ValueError('Xodim ID noto‘g‘ri.')
    row=db.execute('SELECT id,name,role FROM users WHERE id=?',(uid,)).fetchone()
    if not row:raise ValueError('Xodim topilmadi.')
    role,active=staff._role_of(row)
    if not role:raise ValueError('Bu foydalanuvchi xodim emas.')
    return {'id':uid,'name':row['name'] or str(uid),'role':role,'roleLabel':staff.ROLES[role],'active':active}


def _staff_rows(db,active_only=False):
    roles=tuple(staff.ROLES)+(() if active_only else tuple(staff.DISABLED.values()))
    return db.execute(f"SELECT id,name,role FROM users WHERE role IN ({','.join('?'*len(roles))}) ORDER BY name,id",roles).fetchall()


def salary_for(db,uid,month):
    row=db.execute('''SELECT salary_uzs FROM hr_salary WHERE user_id=? AND from_month<=?
        ORDER BY from_month DESC LIMIT 1''',(uid,month)).fetchone()
    return int(row[0]) if row else 0


# ---------- kartochka ----------

def profile(db,uid):
    p=db.execute('SELECT * FROM hr_profiles WHERE user_id=?',(uid,)).fetchone()
    up=db.execute('SELECT phone FROM user_profiles WHERE user_id=?',(uid,)).fetchone()
    out={k:(p[k] if p else '') or '' for k in ('position','hire_date','birth_date','address','passport','emergency','note')}
    out['phone']=(up['phone'] if up else '') or ''
    out['salary']=salary_for(db,uid,this_month())
    out['updatedTs']=int(p['updated_ts']) if p else 0
    return out


def save_profile(db,actor,uid,payload,now=None):
    core._require_admin(db,actor)
    emp=_employee(db,uid);uid=emp['id']
    vals={k:_text(payload.get(k),label,lim) for k,(label,lim) in
          {'position':('Lavozim',80),'address':('Manzil',200),'passport':('Hujjat',40),
           'emergency':('Favqulodda aloqa',120),'note':('Izoh',500)}.items()}
    vals['hire_date']=_opt_date(payload.get('hire_date'),'Ishga kirgan sana')
    vals['birth_date']=_opt_date(payload.get('birth_date'),'Tug‘ilgan sana')
    ts=_now(now)
    db.execute('''INSERT INTO hr_profiles(user_id,position,hire_date,birth_date,address,passport,emergency,note,actor,updated_ts)
        VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET position=excluded.position,hire_date=excluded.hire_date,
        birth_date=excluded.birth_date,address=excluded.address,passport=excluded.passport,emergency=excluded.emergency,
        note=excluded.note,actor=excluded.actor,updated_ts=excluded.updated_ts''',
        (uid,vals['position'],vals['hire_date'],vals['birth_date'],vals['address'],vals['passport'],vals['emergency'],vals['note'],actor,ts))
    if 'phone' in payload:profiles.save(db,uid,{'phone':payload.get('phone')},now=ts)
    if payload.get('salary') not in (None,''):
        s=str(payload.get('salary')).replace(' ','')
        if not s.isdecimal() or int(s)>MAX_SOM:raise ValueError('Oylik: butun so‘m kiriting.')
        set_salary(db,actor,uid,int(s),payload.get('salaryFrom'),now=ts)
    return profile(db,uid)


def set_salary(db,actor,uid,amount,from_month=None,now=None):
    core._require_admin(db,actor)
    month=_month(from_month,now)
    if salary_for(db,uid,month)==amount and db.execute('SELECT 1 FROM hr_salary WHERE user_id=?',(uid,)).fetchone():return
    db.execute('''INSERT INTO hr_salary(user_id,from_month,salary_uzs,actor,ts) VALUES(?,?,?,?,?)
        ON CONFLICT(user_id,from_month) DO UPDATE SET salary_uzs=excluded.salary_uzs,actor=excluded.actor,ts=excluded.ts''',
        (uid,month,amount,actor,_now(now)))
    db.execute('INSERT INTO role_audit(actor,old_id,new_id,action,ts) VALUES(?,?,?,?,?)',(actor,uid,uid,'salary_set',_now(now)))


# ---------- davomat ----------

def set_attendance(db,actor,uid,day,status,note='',now=None):
    core._require_admin(db,actor)
    emp=_employee(db,uid)
    d=_day(day)
    if d>today(now):raise ValueError('Kelajak kun uchun davomat belgilab bo‘lmaydi.')
    if status in (None,'','auto'):
        db.execute('DELETE FROM hr_attendance WHERE user_id=? AND day=?',(emp['id'],d.isoformat()))
        return
    if status not in ATTENDANCE:raise ValueError('Davomat holati noto‘g‘ri.')
    db.execute('''INSERT INTO hr_attendance(user_id,day,status,note,actor,ts) VALUES(?,?,?,?,?,?)
        ON CONFLICT(user_id,day) DO UPDATE SET status=excluded.status,note=excluded.note,actor=excluded.actor,ts=excluded.ts''',
        (emp['id'],d.isoformat(),status,_text(note,'Izoh',200),actor,_now(now)))


def _shift_days(db,uids,first,nxt):
    """{uid: set(iso_day)} — agent smena ochgan kunlar (Toshkent vaqti)."""
    if not uids:return {}
    out={}
    marks=','.join('?'*len(uids))
    for r in db.execute(f'SELECT agent,start FROM shifts WHERE agent IN ({marks}) AND start>=? AND start<?',
                        (*uids,_ts(first),_ts(nxt))).fetchall():
        out.setdefault(int(r['agent']),set()).add(datetime.fromtimestamp(int(r['start']),TZ).date().isoformat())
    return out


def attendance_month(db,uids,month):
    """{uid: {iso_day: {'status','note','auto'}}}"""
    first,nxt=_month_days(month)
    out={u:{} for u in uids}
    for u,days in _shift_days(db,list(uids),first,nxt).items():
        for d in days:out[u][d]={'status':'present','note':'Smena ochilgan','auto':True}
    if uids:
        marks=','.join('?'*len(uids))
        for r in db.execute(f'SELECT user_id,day,status,note FROM hr_attendance WHERE user_id IN ({marks}) AND day>=? AND day<?',
                            (*uids,first.isoformat(),nxt.isoformat())).fetchall():
            out[int(r['user_id'])][r['day']]={'status':r['status'],'note':r['note'] or '','auto':False}
    return out


def _att_summary(days):
    s={k:0 for k in ATTENDANCE}
    for v in days.values():s[v['status']]=s.get(v['status'],0)+1
    s['worked']=s['present']+s['late']
    return s


# ---------- oylik ----------

def add_pay(db,actor,uid,kind,amount,month=None,note='',source=None,pay_from='cash',expected_rate=None,now=None):
    core._require_admin(db,actor)
    emp=_employee(db,uid)
    if kind not in PAY_KINDS:raise ValueError('To‘lov turi noto‘g‘ri.')
    month=_month(month,now)
    amount=_som(amount)
    note=_text(note,'Izoh',300)
    if kind=='penalty' and not note:raise ValueError('Jarima sababini yozing.')
    if source is not None:
        old=db.execute('SELECT id FROM hr_pay WHERE source=?',(source,)).fetchone()
        if old:return int(old[0])
    expense=None
    if kind in CASH_KINDS:
        if not isinstance(source,int) or source<=0:raise ValueError('Operatsiya ID noto‘g‘ri.')
        p=payroll_row(db,emp['id'],month)
        if kind=='salary' and amount>p['remaining']:
            raise ValueError(f"Qolgan oylik {p['remaining']:,} so‘m. Undan ko‘p to‘lab bo‘lmaydi.".replace(',',' '))
        label=f"{emp['name']} · {PAY_KINDS[kind]} {month}"
        expense,_,_=core.add_cashier_expense_uzs(db,actor,amount,SALARY_CATEGORY,label,note,source,
                                                 expected_rate=expected_rate,pay_from=pay_from)
    return int(db.execute('''INSERT INTO hr_pay(user_id,kind,month,amount_uzs,note,expense,actor,ts,source)
        VALUES(?,?,?,?,?,?,?,?,?) RETURNING id''',(emp['id'],kind,month,amount,note,expense,actor,_now(now),source)).fetchone()[0])


def payroll_row(db,uid,month):
    sums={k:0 for k in PAY_KINDS}
    for r in db.execute('SELECT kind,COALESCE(SUM(amount_uzs),0) FROM hr_pay WHERE user_id=? AND month=? GROUP BY kind',(uid,month)).fetchall():
        sums[r[0]]=int(r[1] or 0)
    base=salary_for(db,uid,month)
    due=base+sums['bonus']-sums['penalty']
    paid=sums['advance']+sums['salary']
    return {'salary':base,'bonus':sums['bonus'],'penalty':sums['penalty'],'advance':sums['advance'],
            'paidSalary':sums['salary'],'due':due,'paid':paid,'remaining':due-paid}


def pay_list(db,uid,month):
    return [{'id':int(r['id']),'kind':r['kind'],'label':PAY_KINDS.get(r['kind'],r['kind']),'amount':int(r['amount_uzs']),
             'note':r['note'] or '','cash':r['expense'] is not None,'actorName':r['actor_name'] or '','ts':int(r['ts'])}
            for r in db.execute('''SELECT p.*,u.name AS actor_name FROM hr_pay p LEFT JOIN users u ON u.id=p.actor
                WHERE p.user_id=? AND p.month=? ORDER BY p.id DESC''',(uid,month)).fetchall()]


# ---------- faoliyat ----------

EVENT_LABELS={'delivery':'Tovar berdi','payment':'To‘lov oldi','return':'Qaytarish','sold':'Sotildi','load':'Ombordan oldi',
              'unload':'Omborga topshirdi','adjust':'Qoldiq tuzatildi','expense':'Xarajat'}


def activity(db,uid,month,limit=150):
    first,nxt=_month_days(month)
    a,b=_ts(first),_ts(nxt)
    items=[]
    def add(rows,fn):
        for r in rows:items.append(fn(r))
    add(db.execute('''SELECT e.kind,e.qty,e.amount_usd,e.ts,COALESCE(c.shop_name,c.name) AS client FROM events e
        LEFT JOIN clients c ON c.id=e.client WHERE e.actor=? AND e.ts>=? AND e.ts<? ORDER BY e.ts DESC LIMIT ?''',(uid,a,b,limit)).fetchall(),
        lambda r:{'type':'event','label':EVENT_LABELS.get(r['kind'],r['kind'] or ''),'detail':(r['client'] or '')
                  +(f" · {int(r['qty'])} dona" if r['qty'] else '')+(f" · ${int(r['amount_usd'] or 0)/100:,.2f}" if r['amount_usd'] else ''),'ts':int(r['ts'])})
    add(db.execute('''SELECT v.status,v.note,v.ts,COALESCE(c.shop_name,c.name) AS client FROM client_visits v
        LEFT JOIN clients c ON c.id=v.client WHERE v.actor=? AND v.ts>=? AND v.ts<? ORDER BY v.ts DESC LIMIT ?''',(uid,a,b,limit)).fetchall(),
        lambda r:{'type':'visit','label':'Tashrif','detail':(r['client'] or '')+(f" · {r['note']}" if r['note'] else ''),'ts':int(r['ts'])})
    add(db.execute('''SELECT start,"end" AS fin FROM shifts WHERE agent=? AND start>=? AND start<? ORDER BY start DESC LIMIT ?''',(uid,a,b,limit)).fetchall(),
        lambda r:{'type':'shift','label':'Smena','detail':datetime.fromtimestamp(int(r['start']),TZ).strftime('%H:%M')+' – '
                  +(datetime.fromtimestamp(int(r['fin']),TZ).strftime('%H:%M') if r['fin'] else 'ochiq'),'ts':int(r['start'])})
    add(db.execute('''SELECT kind,pack,qty,note,ts FROM warehouse_moves WHERE actor=? AND ts>=? AND ts<? ORDER BY ts DESC LIMIT ?''',(uid,a,b,limit)).fetchall(),
        lambda r:{'type':'warehouse','label':'Ombor: '+{'in':'kirim','issue':'agentga berdi','agent_return':'agentdan qabul','writeoff':'brak','shop_sale':'savdo'}.get(r['kind'],r['kind']),
                  'detail':f"{core.product_name(r['pack'])} · {int(r['qty'])} dona"+(f" · {r['note']}" if r['note'] else ''),'ts':int(r['ts'])})
    add(db.execute('''SELECT amount_usd,category,recipient,ts FROM cashier_expenses WHERE cashier=? AND ts>=? AND ts<? ORDER BY ts DESC LIMIT ?''',(uid,a,b,limit)).fetchall(),
        lambda r:{'type':'cash','label':'Kassa xarajati','detail':f"{r['category']} · {r['recipient']} · ${int(r['amount_usd'])/100:,.2f}",'ts':int(r['ts'])})
    add(db.execute('''SELECT h.amount_usd,COALESCE(h.accepted_ts,h.ts) AS t,u.name FROM handovers h LEFT JOIN users u ON u.id=h.agent
        WHERE h.cashier=? AND h.status='accepted' AND COALESCE(h.accepted_ts,h.ts)>=? AND COALESCE(h.accepted_ts,h.ts)<? ORDER BY t DESC LIMIT ?''',(uid,a,b,limit)).fetchall(),
        lambda r:{'type':'cash','label':'Pul qabul qildi','detail':f"{r['name'] or ''} · ${int(r['amount_usd'] or 0)/100:,.2f}",'ts':int(r['t'])})
    add(db.execute('''SELECT total,ts FROM shop_sales WHERE seller=? AND ts>=? AND ts<? ORDER BY ts DESC LIMIT ?''',(uid,a,b,limit)).fetchall(),
        lambda r:{'type':'sale','label':'Savdo','detail':f"${int(r['total'])/100:,.2f}",'ts':int(r['ts'])})
    add(db.execute('''SELECT action,old_id,new_id,ts FROM role_audit WHERE actor=? AND ts>=? AND ts<? ORDER BY ts DESC LIMIT ?''',(uid,a,b,limit)).fetchall(),
        lambda r:{'type':'admin','label':'Boshqaruv amali','detail':str(r['action']),'ts':int(r['ts'])})
    items.sort(key=lambda x:-x['ts'])
    return items[:limit]


def kpi(db,uid,month):
    first,nxt=_month_days(month)
    a,b=_ts(first),_ts(nxt)
    one=lambda sql,args:int(db.execute(sql,args).fetchone()[0] or 0)
    return {
        'deliveriesUsd':one("SELECT COALESCE(SUM(amount_usd),0) FROM events WHERE actor=? AND kind='delivery' AND ts>=? AND ts<?",(uid,a,b)),
        'paymentsUsd':one("SELECT COALESCE(SUM(amount_usd),0) FROM events WHERE actor=? AND kind='payment' AND ts>=? AND ts<?",(uid,a,b)),
        'visits':one('SELECT COUNT(*) FROM client_visits WHERE actor=? AND ts>=? AND ts<?',(uid,a,b)),
        'newClients':one('SELECT COUNT(*) FROM clients WHERE agent=? AND created_ts>=? AND created_ts<?',(uid,a,b)),
        'shifts':one('SELECT COUNT(*) FROM shifts WHERE agent=? AND start>=? AND start<?',(uid,a,b)),
        'warehouseMoves':one('SELECT COUNT(*) FROM warehouse_moves WHERE actor=? AND ts>=? AND ts<?',(uid,a,b)),
        'acceptedUsd':one("SELECT COALESCE(SUM(amount_usd),0) FROM handovers WHERE cashier=? AND status='accepted' AND COALESCE(accepted_ts,ts)>=? AND COALESCE(accepted_ts,ts)<?",(uid,a,b)),
        'shopSalesUsd':one('SELECT COALESCE(SUM(total),0) FROM shop_sales WHERE seller=? AND ts>=? AND ts<?',(uid,a,b)),
    }


# ---------- ko'rinishlar ----------

def overview(db,month=None,day=None,now=None):
    month=_month(month,now)
    d=_day(day) if day else today(now)
    rows=_staff_rows(db,active_only=True)
    uids=[int(r['id']) for r in rows]
    att=attendance_month(db,uids,month)
    day_month=d.strftime('%Y-%m')
    att_day=att if day_month==month else attendance_month(db,uids,day_month)
    pos={int(r['user_id']):r['position'] or '' for r in db.execute('SELECT user_id,position FROM hr_profiles').fetchall()}
    phones={int(r['user_id']):r['phone'] or '' for r in db.execute('SELECT user_id,phone FROM user_profiles').fetchall()}
    out=[]
    for r in rows:
        uid=int(r['id']);role,_=staff._role_of(r)
        p=payroll_row(db,uid,month)
        today_mark=att_day.get(uid,{}).get(d.isoformat())
        out.append({'id':uid,'name':r['name'] or str(uid),'role':role,'roleLabel':staff.ROLES[role],
                    'position':pos.get(uid,''),'phone':phones.get(uid,''),
                    'attendance':_att_summary(att.get(uid,{})),'day':today_mark,'payroll':p})
    tot=lambda k:sum(x['payroll'][k] for x in out)
    return {'month':month,'day':d.isoformat(),'employees':out,
            'statuses':[[k,v] for k,v in ATTENDANCE.items()],'payKinds':[[k,v] for k,v in PAY_KINDS.items()],
            'totals':{'due':tot('due'),'paid':tot('paid'),'remaining':tot('remaining'),'salary':tot('salary'),
                      'present':sum(1 for x in out if x['day'] and x['day']['status'] in WORKED),
                      'absent':sum(1 for x in out if x['day'] and x['day']['status']=='absent'),
                      'unmarked':sum(1 for x in out if not x['day']),'count':len(out)},
            'cashRate':core.cashier_rate(db)}


def employee(db,uid,month=None,now=None):
    month=_month(month,now)
    emp=_employee(db,uid)
    first,nxt=_month_days(month)
    days=attendance_month(db,[emp['id']],month)[emp['id']]
    cal=[]
    d=first
    t=today(now)
    while d<nxt:
        mark=days.get(d.isoformat())
        cal.append({'day':d.isoformat(),'dow':d.weekday(),'future':d>t,**(mark or {'status':'','note':'','auto':False})})
        d+=timedelta(days=1)
    emp.update({'profile':profile(db,emp['id']),'month':month,'calendar':cal,'attendance':_att_summary(days),
                'payroll':payroll_row(db,emp['id'],month),'payments':pay_list(db,emp['id'],month),
                'activity':activity(db,emp['id'],month),'kpi':kpi(db,emp['id'],month),
                'salaryHistory':[{'from':r['from_month'],'amount':int(r['salary_uzs'])} for r in
                                 db.execute('SELECT from_month,salary_uzs FROM hr_salary WHERE user_id=? ORDER BY from_month DESC',(emp['id'],)).fetchall()],
                'statuses':[[k,v] for k,v in ATTENDANCE.items()],'payKinds':[[k,v] for k,v in PAY_KINDS.items()],
                'cashRate':core.cashier_rate(db)})
    return emp


# ---------- web panel amallari ----------

OPS=('overview','employee','profile_save','attendance_set','attendance_bulk','pay_add')
PRIMARY_OPS=('pay_add',)


def handle(db,actor,op,payload,source=None,now=None):
    op=str(op or 'overview')
    if op not in OPS:raise ValueError('Xodimlar amali noto‘g‘ri.')
    month=payload.get('month')
    if op=='overview':return overview(db,month,payload.get('day'),now=now)
    uid=payload.get('id')
    if op=='employee':return {'employee':employee(db,uid,month,now=now)}
    if op=='profile_save':
        save_profile(db,actor,uid,payload,now=now)
    elif op=='attendance_set':
        set_attendance(db,actor,uid,payload.get('day'),payload.get('status'),payload.get('note'),now=now)
    elif op=='attendance_bulk':
        items=payload.get('items')
        if not isinstance(items,list) or len(items)>500:raise ValueError('Davomat ro‘yxati noto‘g‘ri.')
        for it in items:
            if not isinstance(it,dict):raise ValueError('Davomat ro‘yxati noto‘g‘ri.')
            set_attendance(db,actor,it.get('id'),payload.get('day'),it.get('status'),it.get('note'),now=now)
        return overview(db,month,payload.get('day'),now=now)
    else:
        rate=payload.get('expectedRate')
        rate=int(rate) if str(rate or '').isdecimal() else None
        add_pay(db,actor,uid,payload.get('kind'),payload.get('amount'),month,payload.get('note'),source=source,
                pay_from=str(payload.get('payFrom') or 'cash'),expected_rate=rate,now=now)
    return {'employee':employee(db,uid,month,now=now)}
