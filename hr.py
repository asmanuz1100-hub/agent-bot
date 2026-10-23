"""Sex ishchilari (HR): kartochka, davomat, oylik va avans — rahbar web paneli uchun.

Bu yerdagi ishchilar tizimdan foydalanmaydi (Telegram ID, Mini App yoki web login yo'q).
Admin, kassir, savdo, ombor va agent kabi tizim foydalanuvchilari staff.py da boshqariladi.

- Oylik tarix bilan saqlanadi (hr_w_salary: qaysi oydan boshlab qancha), shuning uchun oylik
  o'zgarsa o'tgan oylar hisobi o'zgarmaydi.
- Oldingi oylardan qolgan to'lov (yoki ortiqcha berilgan pul) keyingi oyga o'tadi: carry.
  Ishchi yopilsa keyingi oydan oylik 0 yoziladi, qayta olinsa oylik tiklanadi — ishlamagan oyga hisoblanmaydi.
- Har ishchining oylik valyutasi bor: so'm (butun so'm) yoki dollar (sent). Oylik, bonus, jarima va
  qoldiq shu valyutada: hisoblandi = oylik + bonus − jarima; to'landi = avans + oylik to'lovi.
- Avans va oylik to'lovi kassadan «👷 Иш ҳақи» xarajati bo'lib chiqadi, so'mda ham, dollarda ham
  berilishi mumkin; boshqa valyutada berilsa kassa kursi bo'yicha ishchi valyutasiga o'giriladi.
Yozuvlar o'chirilmaydi; ishchi ishdan ketsa «yopiladi», tarixi saqlanadi.
"""
import re
import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo

import core
from core import PostgresDB

TZ=ZoneInfo('Asia/Tashkent')
SALARY_CATEGORY='👷 Иш ҳақи'
ATTENDANCE={'present':'Keldi','late':'Kechikdi','absent':'Kelmadi','off':'Dam olish','sick':'Kasal','vacation':'Ta’til'}
WORKED=('present','late')
PAY_KINDS={'bonus':'Bonus','penalty':'Jarima','advance':'Avans','salary':'Oylik to‘lovi'}
CASH_KINDS=('advance','salary')
MAX_SOM=10**10
CURRENCIES={'UZS':'so‘m','USD':'$'}
_PHONE=re.compile(r'\+?[0-9][0-9 ()-]{6,22}')

SCHEMA='''
CREATE TABLE IF NOT EXISTS hr_workers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, position TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', hire_date TEXT NOT NULL DEFAULT '', birth_date TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', passport TEXT NOT NULL DEFAULT '', emergency TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, actor INTEGER, ts INTEGER NOT NULL, updated_ts INTEGER NOT NULL DEFAULT 0, currency TEXT NOT NULL DEFAULT 'UZS', department TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS hr_w_salary(worker_id INTEGER NOT NULL, from_month TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>=0), actor INTEGER, ts INTEGER NOT NULL, PRIMARY KEY(worker_id,from_month));
CREATE TABLE IF NOT EXISTS hr_w_attendance(worker_id INTEGER NOT NULL, day TEXT NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', actor INTEGER, ts INTEGER NOT NULL, PRIMARY KEY(worker_id,day));
CREATE TABLE IF NOT EXISTS hr_w_pay(id INTEGER PRIMARY KEY, worker_id INTEGER NOT NULL, kind TEXT NOT NULL, month TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), paid_currency TEXT NOT NULL DEFAULT '', paid_amount INTEGER NOT NULL DEFAULT 0, rate INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '', expense INTEGER, actor INTEGER, ts INTEGER NOT NULL, source INTEGER UNIQUE);
CREATE INDEX IF NOT EXISTS idx_hr_w_attendance_day ON hr_w_attendance(day);
CREATE INDEX IF NOT EXISTS idx_hr_w_pay_month ON hr_w_pay(month,worker_id);
'''
PG_SCHEMA=SCHEMA.replace('INTEGER PRIMARY KEY','BIGSERIAL PRIMARY KEY').replace(' INTEGER',' BIGINT')


def _cols(db,table):
    if isinstance(db,PostgresDB):
        return {r[0] for r in db.execute('''SELECT column_name FROM information_schema.columns
            WHERE table_schema=current_schema() AND table_name=?''',(table,)).fetchall()}
    return {r[1] for r in db.execute(f'PRAGMA table_info({table})').fetchall()}


def _migrate(db):
    """Valyutasiz birinchi sxema (so'm ustunlari) -> valyutali sxema. Ma'lumot saqlanadi, eski yozuvlar so'mda."""
    big='BIGINT' if isinstance(db,PostgresDB) else 'INTEGER'
    wcols=_cols(db,'hr_workers')
    if 'currency' not in wcols:
        db.execute("ALTER TABLE hr_workers ADD COLUMN currency TEXT NOT NULL DEFAULT 'UZS'")
    if 'department' not in wcols:
        db.execute("ALTER TABLE hr_workers ADD COLUMN department TEXT NOT NULL DEFAULT ''")
    if 'salary_uzs' in _cols(db,'hr_w_salary'):
        db.execute('ALTER TABLE hr_w_salary RENAME COLUMN salary_uzs TO amount')
    cols=_cols(db,'hr_w_pay')
    if 'amount_uzs' in cols:
        db.execute('ALTER TABLE hr_w_pay RENAME COLUMN amount_uzs TO amount')
    for col,ddl in (('paid_currency',"TEXT NOT NULL DEFAULT ''"),('paid_amount',f'{big} NOT NULL DEFAULT 0'),('rate',f'{big} NOT NULL DEFAULT 0')):
        if col not in cols:db.execute(f'ALTER TABLE hr_w_pay ADD COLUMN {col} {ddl}')


def init(db):
    if isinstance(db,PostgresDB):
        for stmt in PG_SCHEMA.split(';'):
            if stmt.strip():db.execute(stmt)
    else:
        db.executescript(SCHEMA)
    _migrate(db)


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
    try:return date.fromisoformat(str(value or '').strip())
    except ValueError:raise ValueError('Sana noto‘g‘ri (YYYY-MM-DD).')


def _opt_date(value,label):
    s=str(value or '').strip()
    if not s:return ''
    try:return date.fromisoformat(s).isoformat()
    except ValueError:raise ValueError(f'{label} noto‘g‘ri (YYYY-MM-DD).')


def _month_days(month):
    y,m=map(int,month.split('-'))
    return date(y,m,1),date(y+(m==12),m%12+1,1)


def _money(value,currency,label='Summa',allow_zero=False):
    """So'm -> butun so'm; dollar -> sent (ko'pi bilan 2 kasr)."""
    s=str(value if value is not None else '').replace(' ','')
    if currency=='UZS':
        s=s.replace(',','')
        if not s.isdecimal():raise ValueError(f'{label}: butun so‘m kiriting.')
        n=int(s)
    else:
        try:d=Decimal(s.replace(',','.'))*100
        except InvalidOperation:raise ValueError(f'{label}: dollarda kiriting (masalan 250 yoki 250.50).')
        if not d.is_finite() or d!=d.to_integral_value():raise ValueError(f'{label}: ko‘pi bilan 2 kasr xona.')
        n=int(d)
    if not (0 if allow_zero else 1)<=n<=MAX_SOM:raise ValueError(f'{label} noto‘g‘ri.')
    return n


def _currency(value):
    c=str(value or 'UZS').upper()
    if c not in CURRENCIES:raise ValueError('Valyuta noto‘g‘ri: so‘m yoki dollar.')
    return c


def _text(value,label,limit,required=False):
    t=re.sub(r'\s+',' ',str(value or '')).strip()
    if len(t)>limit:raise ValueError(f'{label} {limit} belgidan oshmasin.')
    if required and not t:raise ValueError(f'{label}ni kiriting.')
    return t


def _worker(db,wid):
    try:wid=int(wid)
    except (TypeError,ValueError):raise ValueError('Ishchi ID noto‘g‘ri.')
    row=db.execute('SELECT * FROM hr_workers WHERE id=?',(wid,)).fetchone()
    if not row:raise ValueError('Ishchi topilmadi.')
    return row


def salary_for(db,wid,month):
    row=db.execute('''SELECT amount FROM hr_w_salary WHERE worker_id=? AND from_month<=?
        ORDER BY from_month DESC LIMIT 1''',(wid,month)).fetchone()
    return int(row[0]) if row else 0


# ---------- ishchi kartochkasi ----------

def _fields(payload):
    phone=_text(payload.get('phone'),'Telefon',40)
    if phone and not _PHONE.fullmatch(phone):raise ValueError('Telefon raqami noto‘g‘ri. Masalan: +998 90 123 45 67')
    return {'name':_text(payload.get('name'),'Ism',80,required=True),'position':_text(payload.get('position'),'Lavozim',80),
            'department':_text(payload.get('department'),'Bo‘lim',80),
            'phone':phone,'hire_date':_opt_date(payload.get('hire_date'),'Ishga kirgan sana'),
            'birth_date':_opt_date(payload.get('birth_date'),'Tug‘ilgan sana'),'address':_text(payload.get('address'),'Manzil',200),
            'passport':_text(payload.get('passport'),'Hujjat',40),'emergency':_text(payload.get('emergency'),'Favqulodda aloqa',120),
            'note':str(payload.get('note') or '').strip()[:500]}


def _apply_salary(db,actor,wid,payload,now):
    if payload.get('salary') in (None,''):return
    cur=_worker(db,wid)['currency']
    set_salary(db,actor,wid,_money(payload.get('salary'),cur,'Oylik',allow_zero=True),payload.get('salaryFrom'),now=now)


def currency_lock(db,wid,now=None):
    """Valyutani nima to'sadi (None — o'zgartirish mumkin). Hisoblangan oylik tarixi o'chirilmaydi va
    eski summaga yangi valyuta yozilmaydi: o'tgan oyga oylik hisoblangan bo'lsa valyuta o'zgarmaydi."""
    if db.execute('SELECT 1 FROM hr_w_pay WHERE worker_id=? LIMIT 1',(wid,)).fetchone():
        return 'Bu ishchiga to‘lov yoki bonus/jarima yozilgan — oylik valyutasini o‘zgartirib bo‘lmaydi.'
    if db.execute('SELECT 1 FROM hr_w_salary WHERE worker_id=? AND from_month<? AND amount>0 LIMIT 1',(wid,this_month(now))).fetchone():
        return ('O‘tgan oylarga oylik hisoblangan — valyutani o‘zgartirsa eski qarz buziladi. '
                'Avval qolgan oylikni to‘lab, ishchini yoping va yangi valyutada yangi kartochka oching.')
    return None


def _set_currency(db,wid,payload,now=None):
    """Valyuta faqat hisob tarixi yo'q ishchida o'zgaradi (joriy/kelgusi oy oyligi yangi valyutada qayta kiritiladi)."""
    if payload.get('currency') in (None,''):return
    cur=_currency(payload.get('currency'))
    if _worker(db,wid)['currency']==cur:return
    why=currency_lock(db,wid,now)
    if why:raise ValueError(why)
    if payload.get('salary') in (None,''):raise ValueError('Valyuta o‘zgarsa, oylikni yangi valyutada kiriting.')
    # faqat hali hisoblanmagan (joriy va kelgusi oy) yozuvlar — o'tgan oylarda summa yo'q yoki 0
    db.execute('DELETE FROM hr_w_salary WHERE worker_id=? AND from_month>=?',(wid,this_month(now)))
    db.execute('UPDATE hr_workers SET currency=? WHERE id=?',(cur,wid))


def add_worker(db,actor,payload,now=None):
    core._require_admin(db,actor)
    f=_fields(payload)
    if db.execute('SELECT 1 FROM hr_workers WHERE LOWER(name)=LOWER(?) AND active=1',(f['name'],)).fetchone():
        raise ValueError('Bu ismli faol ishchi bor. Familiyasini ham yozing.')
    ts=_now(now)
    wid=int(db.execute('''INSERT INTO hr_workers(name,position,phone,hire_date,birth_date,address,passport,emergency,note,actor,ts,updated_ts,currency,department)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id''',(f['name'],f['position'],f['phone'],f['hire_date'],f['birth_date'],
        f['address'],f['passport'],f['emergency'],f['note'],actor,ts,ts,_currency(payload.get('currency')),f['department'])).fetchone()[0])
    _apply_salary(db,actor,wid,payload,ts)
    return wid


def save_worker(db,actor,wid,payload,now=None):
    core._require_admin(db,actor)
    wid=int(_worker(db,wid)['id'])
    f=_fields(payload)
    if db.execute('SELECT 1 FROM hr_workers WHERE LOWER(name)=LOWER(?) AND active=1 AND id<>?',(f['name'],wid)).fetchone():
        raise ValueError('Bu ismli faol ishchi bor. Familiyasini ham yozing.')
    ts=_now(now)
    db.execute('''UPDATE hr_workers SET name=?,department=?,position=?,phone=?,hire_date=?,birth_date=?,address=?,passport=?,emergency=?,note=?,
        actor=?,updated_ts=? WHERE id=?''',(f['name'],f['department'],f['position'],f['phone'],f['hire_date'],f['birth_date'],f['address'],
        f['passport'],f['emergency'],f['note'],actor,ts,wid))
    _set_currency(db,wid,payload,now)
    _apply_salary(db,actor,wid,payload,ts)


def next_month(month):
    y,m=map(int,month.split('-'))
    return f'{y+(m==12)}-{m%12+1:02d}'


def set_active(db,actor,wid,active,now=None):
    """Yopish: shu oy oyligi to'liq, keyingi oydan 0. Qayta olish: shu oydan oxirgi oylik tiklanadi."""
    core._require_admin(db,actor)
    w=_worker(db,wid);wid=int(w['id'])
    if bool(w['active'])==bool(active):raise ValueError('Holat o‘zgarmagan.')
    if active and db.execute('SELECT 1 FROM hr_workers WHERE LOWER(name)=LOWER(?) AND active=1',(w['name'],)).fetchone():
        raise ValueError('Bu ismli faol ishchi bor.')
    month=this_month(now)
    if active:
        last=db.execute('SELECT amount FROM hr_w_salary WHERE worker_id=? AND amount>0 ORDER BY from_month DESC LIMIT 1',(wid,)).fetchone()
        if last:
            set_salary(db,actor,wid,int(last[0]),month,now=now)
            # Shu oyda yopilib qayta ochilsa, yopishda yozilgan kelgusi «0» hali kuchga kirmagan — tiklanadi.
            # Yozuv o'chirilmaydi: summa, kim va qachon yangilanadi.
            db.execute('UPDATE hr_w_salary SET amount=?,actor=?,ts=? WHERE worker_id=? AND from_month>? AND amount=0',
                       (int(last[0]),actor,_now(now),wid,month))
    elif db.execute('SELECT 1 FROM hr_w_salary WHERE worker_id=?',(wid,)).fetchone():
        set_salary(db,actor,wid,0,next_month(month),now=now)
    db.execute('UPDATE hr_workers SET active=? WHERE id=?',(1 if active else 0,wid))


def set_salary(db,actor,wid,amount,from_month=None,now=None):
    core._require_admin(db,actor)
    month=_month(from_month,now)
    if db.execute('SELECT 1 FROM hr_w_salary WHERE worker_id=?',(wid,)).fetchone() and salary_for(db,wid,month)==amount:return
    db.execute('''INSERT INTO hr_w_salary(worker_id,from_month,amount,actor,ts) VALUES(?,?,?,?,?)
        ON CONFLICT(worker_id,from_month) DO UPDATE SET amount=excluded.amount,actor=excluded.actor,ts=excluded.ts''',
        (wid,month,amount,actor,_now(now)))


def _card(db,w):
    return {k:(w[k] or '') for k in ('department','position','phone','hire_date','birth_date','address','passport','emergency','note')}


# ---------- davomat ----------

def set_attendance(db,actor,wid,day,status,note='',now=None):
    core._require_admin(db,actor)
    w=_worker(db,wid)
    d=_day(day)
    if d>today(now):raise ValueError('Kelajak kun uchun davomat belgilab bo‘lmaydi.')
    if status in (None,'','clear'):
        db.execute('DELETE FROM hr_w_attendance WHERE worker_id=? AND day=?',(int(w['id']),d.isoformat()))
        return
    if status not in ATTENDANCE:raise ValueError('Davomat holati noto‘g‘ri.')
    db.execute('''INSERT INTO hr_w_attendance(worker_id,day,status,note,actor,ts) VALUES(?,?,?,?,?,?)
        ON CONFLICT(worker_id,day) DO UPDATE SET status=excluded.status,note=excluded.note,actor=excluded.actor,ts=excluded.ts''',
        (int(w['id']),d.isoformat(),status,_text(note,'Izoh',200),actor,_now(now)))


def attendance_month(db,wids,month):
    """{wid: {iso_day: {'status','note'}}}"""
    first,nxt=_month_days(month)
    out={w:{} for w in wids}
    if wids:
        marks=','.join('?'*len(wids))
        for r in db.execute(f'SELECT worker_id,day,status,note FROM hr_w_attendance WHERE worker_id IN ({marks}) AND day>=? AND day<?',
                            (*wids,first.isoformat(),nxt.isoformat())).fetchall():
            out[int(r['worker_id'])][r['day']]={'status':r['status'],'note':r['note'] or ''}
    return out


def _att_summary(days):
    s={k:0 for k in ATTENDANCE}
    for v in days.values():s[v['status']]=s.get(v['status'],0)+1
    s['worked']=s['present']+s['late']
    return s


# ---------- oylik ----------

def add_pay(db,actor,wid,kind,amount,month=None,note='',source=None,pay_from='cash',expected_rate=None,
            pay_currency=None,now=None):
    """Bonus/jarima — ishchi valyutasida. Avans/oylik — kassadan pay_currency da (bo'sh bo'lsa ishchi valyutasi)."""
    core._require_admin(db,actor)
    w=_worker(db,wid);wid=int(w['id']);cur=w['currency']
    if kind not in PAY_KINDS:raise ValueError('To‘lov turi noto‘g‘ri.')
    month=_month(month,now)
    if not w['active']:
        # Ishdan ketgan: yangi avans yo'q; qolgan oylikni to'lash (yakuniy hisob) va ishlagan oyi uchun
        # bonus/jarima mumkin. Yangi oylik hisoblanmaydi (yopishda keyingi oydan 0).
        if kind=='advance':raise ValueError('Ishdan ketgan ishchiga avans berilmaydi. Qolgan oylikni «Oylik to‘lovi» bilan to‘lang.')
        if kind in ('bonus','penalty') and salary_for(db,wid,month)<=0:
            raise ValueError('Ishchi bu oyda ishlamagan — bonus/jarima faqat ishlagan oyiga yoziladi.')
    note=_text(note,'Izoh',300)
    if kind=='penalty' and not note:raise ValueError('Jarima sababini yozing.')
    if source is not None:
        old=db.execute('SELECT id FROM hr_w_pay WHERE source=?',(source,)).fetchone()
        if old:return int(old[0])
    paid_cur=_currency(pay_currency or cur) if kind in CASH_KINDS else cur
    paid=_money(amount,paid_cur)
    expense=None;rate=0;credited=paid
    if kind in CASH_KINDS:
        if not isinstance(source,int) or source<=0:raise ValueError('Operatsiya ID noto‘g‘ri.')
        if paid_cur!=cur or paid_cur=='UZS':
            rate=core.cashier_rate(db)
            if rate is None:raise ValueError('Avval kassada 1 USD kursini belgilang.')
            if expected_rate is not None and rate!=expected_rate:raise ValueError('Kassa kursi o‘zgargan. Qayta kiriting.')
        if paid_cur!=cur:
            # so'm -> sent yoki sent -> so'm, kassa kursi bo'yicha
            credited=core.som_to_usd_cents(paid,rate) if paid_cur=='UZS' else int((Decimal(paid)*rate/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        if kind=='salary':
            left=payroll_row(db,wid,month)['remaining']
            if credited>left:raise ValueError(f'Qolgan oylik {fmt(left,cur)}. Undan ko‘p to‘lab bo‘lmaydi.')
        label=f"{w['name']} · {PAY_KINDS[kind]} {month}"
        if paid_cur=='UZS':
            expense,_,_=core.add_cashier_expense_uzs(db,actor,paid,SALARY_CATEGORY,label,note,source,
                                                     expected_rate=rate,pay_from=pay_from)
        else:
            expense=core.add_cashier_expense(db,actor,paid,SALARY_CATEGORY,label,note,source,pay_from=pay_from)
    return int(db.execute('''INSERT INTO hr_w_pay(worker_id,kind,month,amount,paid_currency,paid_amount,rate,note,expense,actor,ts,source)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id''',(wid,kind,month,credited,paid_cur,paid,rate,note,expense,actor,_now(now),source)).fetchone()[0])


def fmt(n,cur):
    return f"{n:,} so‘m".replace(',',' ') if cur=='UZS' else f"${n/100:,.2f}".replace(',',' ')


def carry(db,wid,month):
    """Oldingi oylar yakuni: musbat — ishchiga qarzimiz, manfiy — ortiqcha berilgan (keyingi oydan ushlanadi)."""
    first=db.execute('SELECT MIN(from_month) FROM hr_w_salary WHERE worker_id=?',(wid,)).fetchone()[0]
    accrued=0
    if first:
        m=first
        while m<month:
            accrued+=salary_for(db,wid,m)
            m=next_month(m)
    sums={k:0 for k in PAY_KINDS}
    for r in db.execute('SELECT kind,COALESCE(SUM(amount),0) FROM hr_w_pay WHERE worker_id=? AND month<? GROUP BY kind',(wid,month)).fetchall():
        sums[r[0]]=int(r[1] or 0)
    return accrued+sums['bonus']-sums['penalty']-sums['advance']-sums['salary']


def payroll_row(db,wid,month):
    sums={k:0 for k in PAY_KINDS}
    for r in db.execute('SELECT kind,COALESCE(SUM(amount),0) FROM hr_w_pay WHERE worker_id=? AND month=? GROUP BY kind',(wid,month)).fetchall():
        sums[r[0]]=int(r[1] or 0)
    base=salary_for(db,wid,month)
    due=base+sums['bonus']-sums['penalty']
    paid=sums['advance']+sums['salary']
    cur=(db.execute('SELECT currency FROM hr_workers WHERE id=?',(wid,)).fetchone() or ['UZS'])[0]
    prev=carry(db,wid,month)
    left=prev+due-paid
    return {'currency':cur,'carry':prev,'salary':base,'bonus':sums['bonus'],'penalty':sums['penalty'],'advance':sums['advance'],
            'paidSalary':sums['salary'],'due':due,'paid':paid,'remaining':left,'overpaid':max(-left,0)}


def pay_list(db,wid,month):
    return [{'id':int(r['id']),'kind':r['kind'],'label':PAY_KINDS.get(r['kind'],r['kind']),'amount':int(r['amount']),
             'paidCurrency':r['paid_currency'] or '','paidAmount':int(r['paid_amount'] or 0),'rate':int(r['rate'] or 0),
             'note':r['note'] or '','cash':r['expense'] is not None,'actorName':r['actor_name'] or '','ts':int(r['ts'])}
            for r in db.execute('''SELECT p.*,u.name AS actor_name FROM hr_w_pay p LEFT JOIN users u ON u.id=p.actor
                WHERE p.worker_id=? AND p.month=? ORDER BY p.id DESC''',(wid,month)).fetchall()]


# ---------- ko'rinishlar ----------

def overview(db,month=None,day=None,closed=False,now=None):
    month=_month(month,now)
    d=_day(day) if day else today(now)
    rows=db.execute('SELECT * FROM hr_workers'+('' if closed else ' WHERE active=1')+' ORDER BY active DESC,name,id').fetchall()
    wids=[int(r['id']) for r in rows]
    att=attendance_month(db,wids,month)
    day_month=d.strftime('%Y-%m')
    att_day=att if day_month==month else attendance_month(db,wids,day_month)
    out=[]
    for r in rows:
        wid=int(r['id'])
        out.append({'id':wid,'name':r['name'],'currency':r['currency'] or 'UZS','department':r['department'] or '','position':r['position'] or '','phone':r['phone'] or '','active':bool(r['active']),
                    'hireDate':r['hire_date'] or '','attendance':_att_summary(att.get(wid,{})),
                    'day':att_day.get(wid,{}).get(d.isoformat()),'payroll':payroll_row(db,wid,month)})
    act=[x for x in out if x['active']]
    # 'remaining' — faqat biz qarzdor bo'lganlar; ortiqcha berilgan pul alohida ('overpaid'), bir-birini yopmaydi.
    money={c:{'salary':sum(x['payroll']['salary'] for x in act if x['currency']==c),
              'due':sum(x['payroll']['due'] for x in act if x['currency']==c),
              'paid':sum(x['payroll']['paid'] for x in act if x['currency']==c),
              'remaining':sum(max(x['payroll']['remaining'],0) for x in act if x['currency']==c),
              'overpaid':sum(x['payroll']['overpaid'] for x in act if x['currency']==c)} for c in CURRENCIES}
    return {'month':month,'day':d.isoformat(),'workers':out,
            'statuses':[[k,v] for k,v in ATTENDANCE.items()],'payKinds':[[k,v] for k,v in PAY_KINDS.items()],
            'money':money,'currencies':[[k,v] for k,v in CURRENCIES.items()],
            'totals':{'present':sum(1 for x in act if x['day'] and x['day']['status'] in WORKED),
                      'absent':sum(1 for x in act if x['day'] and x['day']['status']=='absent'),
                      'unmarked':sum(1 for x in act if not x['day']),'count':len(act),
                      'closed':int(db.execute('SELECT COUNT(*) FROM hr_workers WHERE active=0').fetchone()[0] or 0)},
            'cashRate':core.cashier_rate(db)}


def worker(db,wid,month=None,now=None):
    month=_month(month,now)
    w=_worker(db,wid);wid=int(w['id'])
    first,nxt=_month_days(month)
    days=attendance_month(db,[wid],month)[wid]
    cal=[];d=first;t=today(now)
    while d<nxt:
        mark=days.get(d.isoformat())
        cal.append({'day':d.isoformat(),'dow':d.weekday(),'future':d>t,**(mark or {'status':'','note':''})})
        d+=timedelta(days=1)
    return {'id':wid,'name':w['name'],'active':bool(w['active']),'currency':w['currency'] or 'UZS',
            'canChangeCurrency':currency_lock(db,wid,now) is None,'currencyLock':currency_lock(db,wid,now) or '','card':_card(db,w),'salary':salary_for(db,wid,this_month(now)),
            'month':month,'calendar':cal,'attendance':_att_summary(days),'payroll':payroll_row(db,wid,month),
            'payments':pay_list(db,wid,month),
            'salaryHistory':[{'from':r['from_month'],'amount':int(r['amount'])} for r in
                             db.execute('SELECT from_month,amount FROM hr_w_salary WHERE worker_id=? ORDER BY from_month DESC',(wid,)).fetchall()],
            'statuses':[[k,v] for k,v in ATTENDANCE.items()],'payKinds':[[k,v] for k,v in PAY_KINDS.items()],
            'currencies':[[k,v] for k,v in CURRENCIES.items()],'cashRate':core.cashier_rate(db)}


# ---------- web panel amallari ----------

OPS=('overview','worker','worker_add','worker_save','worker_close','worker_open','attendance_set','attendance_bulk','pay_add')
PRIMARY_OPS=('pay_add',)


def handle(db,actor,op,payload,source=None,now=None):
    op=str(op or 'overview')
    if op not in OPS:raise ValueError('Ishchilar amali noto‘g‘ri.')
    month=payload.get('month')
    if op=='overview':return overview(db,month,payload.get('day'),bool(payload.get('closed')),now=now)
    wid=payload.get('id')
    if op=='worker':return {'worker':worker(db,wid,month,now=now)}
    if op=='worker_add':
        wid=add_worker(db,actor,payload,now=now)
    elif op=='worker_save':
        save_worker(db,actor,wid,payload,now=now)
    elif op in ('worker_close','worker_open'):
        set_active(db,actor,wid,op=='worker_open',now=now)
    elif op=='attendance_set':
        set_attendance(db,actor,wid,payload.get('day'),payload.get('status'),payload.get('note'),now=now)
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
        add_pay(db,actor,wid,payload.get('kind'),payload.get('amount'),month,payload.get('note'),source=source,
                pay_from=str(payload.get('payFrom') or 'cash'),expected_rate=rate,pay_currency=payload.get('payCurrency'),now=now)
    return {'worker':worker(db,wid,month,now=now)}
