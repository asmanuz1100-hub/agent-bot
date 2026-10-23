"""Kassa kengaytmasi: qo'lda kirim, hisoblar orasida o'tkazma, bekor qilish, kun yopish va yagona jurnal.

Mavjud kassa (core.cashier_flows: agent topshiriqlari, xarajatlar, karta to'lovlari, konvertatsiya,
agent hisobini to'ldirish) o'zgarmaydi. Yangi amallar faqat cash_moves jadvaliga yoziladi va mavjud
balanslarga QO'SHILADI — eski yozuvlar qayta hisoblanmaydi, yangi yozuv bo'lmasa natija avvalgidek.

Hisoblar: naqd, karta, bank; har biri so'm (butun so'm) va dollar (sent) — kurs bilan aralashtirilmaydi.
- Kirim: tashqi manbadan hisobga (daromad).
- O'tkazma: bir valyutada hisobdan hisobga — daromad ham, xarajat ham emas.
- Bekor qilish: yozuv o'chmaydi, holati 'cancelled' bo'ladi, kim/qachon/nima uchun saqlanadi.
- Kun yopish: tizim qoldig'i, sanalgan pul va farq yoziladi; farq avtomatik tuzatilmaydi.
Eski (aralash) USD hisoblari uchun har so'm yozuvining USD ekvivalenti yozilgan paytdagi kurs bilan saqlanadi.
"""
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from core import PostgresDB

TZ=ZoneInfo('Asia/Tashkent')
POCKETS={'cash':'Naqd','card':'Karta','bank':'Bank'}
CURRENCIES=('UZS','USD')
INCOME_CATEGORIES=('Mijozdan to‘lov (kassaga to‘g‘ridan)','Ta’sischi mablag‘i','Qarz olindi','Qaytarilgan pul','Boshqa kirim')
MAX_AMOUNT=10**12

SCHEMA='''
CREATE TABLE IF NOT EXISTS cash_moves(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, from_pocket TEXT NOT NULL DEFAULT '', to_pocket TEXT NOT NULL DEFAULT '', currency TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), usd_eq INTEGER NOT NULL DEFAULT 0, rate INTEGER NOT NULL DEFAULT 0, category TEXT NOT NULL DEFAULT '', counterparty TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', actor INTEGER NOT NULL, ts INTEGER NOT NULL, source INTEGER UNIQUE, status TEXT NOT NULL DEFAULT 'active', cancel_actor INTEGER, cancel_ts INTEGER, cancel_reason TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS cash_closings(id INTEGER PRIMARY KEY, day TEXT NOT NULL, pocket TEXT NOT NULL, currency TEXT NOT NULL, system INTEGER NOT NULL, counted INTEGER NOT NULL, diff INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', actor INTEGER NOT NULL, ts INTEGER NOT NULL, UNIQUE(day,pocket,currency));
CREATE INDEX IF NOT EXISTS idx_cash_moves_ts ON cash_moves(ts);
'''
PG_SCHEMA=SCHEMA.replace('INTEGER PRIMARY KEY','BIGSERIAL PRIMARY KEY').replace(' INTEGER',' BIGINT')


def init(db):
    if isinstance(db,PostgresDB):
        for stmt in PG_SCHEMA.split(';'):
            if stmt.strip():db.execute(stmt)
    else:
        db.executescript(SCHEMA)


def _lock(db):
    # core.add_cashier_expense bilan bir xil kassa qulfi: bir vaqtda ikki amal qoldiqni buzmasin.
    if isinstance(db,PostgresDB):
        db.execute('SELECT pg_advisory_xact_lock(7806292501)').fetchone()


def parse_amount(value,currency):
    s=str(value if value is not None else '').replace(' ','')
    if currency=='UZS':
        s=s.replace(',','')
        if not s.isdecimal():raise ValueError('Summa: butun so‘m kiriting.')
        n=int(s)
    else:
        try:d=Decimal(s.replace(',','.'))*100
        except InvalidOperation:raise ValueError('Summa: dollarda kiriting (masalan 250 yoki 250.50).')
        if not d.is_finite() or d!=d.to_integral_value():raise ValueError('Summa: ko‘pi bilan 2 kasr xona.')
        n=int(d)
    if not 0<n<=MAX_AMOUNT:raise ValueError('Summa noto‘g‘ri.')
    return n


def _pocket(p):
    p=str(p or '')
    if p not in POCKETS:raise ValueError('Hisobni tanlang: naqd, karta yoki bank.')
    return p


def _currency(c):
    c=str(c or '').upper()
    if c not in CURRENCIES:raise ValueError('Valyutani tanlang: so‘m yoki dollar.')
    return c


def _usd_eq(db,currency,amount):
    """Eski aralash USD hisoblari uchun ekvivalent va ishlatilgan kurs."""
    import core
    if currency=='USD':return amount,0
    rate=core.cashier_rate(db)
    if rate is None:raise ValueError('Avval kassa kursini belgilang (so‘m yozuvining USD ekvivalenti uchun).')
    return core.som_to_usd_cents(amount,rate),rate


# ---------- mavjud balanslarga qo'shiladigan summalar ----------

def flows_add(db,out,start,end):
    """core.cashier_flows natijasiga cash_moves ta'sirini qo'shadi (joyida). Yangi yozuv bo'lmasa — 0."""
    for p in POCKETS:
        for c in ('uzs','usd'):
            out[f'manual_in_{p}_{c}']=0
            out[f'transfer_{p}_{c}']=0
    rows=db.execute("""SELECT kind,from_pocket,to_pocket,currency,amount FROM cash_moves
        WHERE status='active' AND ts>=? AND ts<?""",(int(start),int(end))).fetchall()
    for r in rows:
        c=r['currency'].lower();a=int(r['amount'])
        if r['kind']=='income':
            out[f"manual_in_{r['to_pocket']}_{c}"]+=a
        else:
            out[f"transfer_{r['from_pocket']}_{c}"]-=a
            out[f"transfer_{r['to_pocket']}_{c}"]+=a
    for p in ('cash','card'):
        for c in ('uzs','usd'):
            out[f'{p}_{c}']+=out[f'manual_in_{p}_{c}']+out[f'transfer_{p}_{c}']
    for c in ('uzs','usd'):
        out[f'bank_{c}']=out[f'manual_in_bank_{c}']+out[f'transfer_bank_{c}']
    return out


def legacy_usd(db,pocket,start=None,end=None):
    """Eski USD-ekvivalent hisoblar (cashier_balance_usd / cashier_source_balance_usd) uchun sof ta'sir."""
    w,args=('',()) if start is None else (' AND ts>=? AND ts<?',(int(start),int(end)))
    one=lambda sql,a:int(db.execute(sql,a).fetchone()[0] or 0)
    inc=one("SELECT COALESCE(SUM(usd_eq),0) FROM cash_moves WHERE status='active' AND kind='income' AND to_pocket=?"+w,(pocket,*args))
    tin=one("SELECT COALESCE(SUM(usd_eq),0) FROM cash_moves WHERE status='active' AND kind='transfer' AND to_pocket=?"+w,(pocket,*args))
    tout=one("SELECT COALESCE(SUM(usd_eq),0) FROM cash_moves WHERE status='active' AND kind='transfer' AND from_pocket=?"+w,(pocket,*args))
    return inc+tin-tout


def balances(db):
    """Har hisob va valyuta bo'yicha hozirgi qoldiq (so'm butun, dollar sent)."""
    import core
    f=core.cashier_flows(db)
    out={}
    for p in POCKETS:
        for c in ('uzs','usd'):
            v=int(f.get(f'{p}_{c}',0))
            if p=='cash' and c=='usd':v+=int(f.get('opening_usd',0))   # eski aralash qoldiq naqd dollar ichida
            out[f'{p}_{c}']=v
    return out


def _available(db,pocket,currency):
    return balances(db)[f'{pocket}_{currency.lower()}']


# ---------- amallar ----------

def _seen(db,source):
    if source is None:return None
    row=db.execute('SELECT id FROM cash_moves WHERE source=?',(source,)).fetchone()
    return int(row[0]) if row else None


def add_income(db,actor,pocket,currency,amount,category,counterparty,note,source,now=None):
    pocket=_pocket(pocket);currency=_currency(currency);amount=parse_amount(amount,currency)
    if category not in INCOME_CATEGORIES:raise ValueError('Kirim turini ro‘yxatdan tanlang.')
    counterparty=str(counterparty or '').strip()
    if not counterparty or len(counterparty)>200:raise ValueError('Kimdan kelganini yozing (1–200 belgi).')
    note=str(note or '').strip()
    if len(note)>500:raise ValueError('Izoh 500 belgidan oshmasin.')
    if not isinstance(source,int) or source<=0:raise ValueError('Operatsiya ID noto‘g‘ri.')
    _lock(db)
    old=_seen(db,source)
    if old:return old
    usd_eq,rate=_usd_eq(db,currency,amount)
    return int(db.execute('''INSERT INTO cash_moves(kind,to_pocket,currency,amount,usd_eq,rate,category,counterparty,note,actor,ts,source)
        VALUES('income',?,?,?,?,?,?,?,?,?,?,?) RETURNING id''',(pocket,currency,amount,usd_eq,rate,category,counterparty,note,actor,
        int(time.time() if now is None else now),source)).fetchone()[0])


def add_transfer(db,actor,from_pocket,to_pocket,currency,amount,note,source,now=None):
    a=_pocket(from_pocket);b=_pocket(to_pocket);currency=_currency(currency);amount=parse_amount(amount,currency)
    if a==b:raise ValueError('Qayerdan va qayerga bir xil bo‘lmasin.')
    note=str(note or '').strip()
    if len(note)>500:raise ValueError('Izoh 500 belgidan oshmasin.')
    if not isinstance(source,int) or source<=0:raise ValueError('Operatsiya ID noto‘g‘ri.')
    _lock(db)
    old=_seen(db,source)
    if old:return old
    have=_available(db,a,currency)
    if amount>have:raise ValueError(f'{POCKETS[a]} hisobida yetarli {currency} yo‘q.')
    usd_eq,rate=_usd_eq(db,currency,amount)
    return int(db.execute('''INSERT INTO cash_moves(kind,from_pocket,to_pocket,currency,amount,usd_eq,rate,note,actor,ts,source)
        VALUES('transfer',?,?,?,?,?,?,?,?,?,?) RETURNING id''',(a,b,currency,amount,usd_eq,rate,note,actor,
        int(time.time() if now is None else now),source)).fetchone()[0])


def cancel(db,actor,move_id,reason,now=None):
    """Bekor qilish: yozuv saqlanadi, holati o'zgaradi. Qoldiq manfiyga tushadigan bo'lsa ruxsat yo'q."""
    reason=str(reason or '').strip()
    if not reason or len(reason)>300:raise ValueError('Bekor qilish sababini yozing (1–300 belgi).')
    _lock(db)
    row=db.execute('SELECT * FROM cash_moves WHERE id=?',(int(move_id),)).fetchone()
    if not row:raise ValueError('Operatsiya topilmadi.')
    if row['status']!='active':raise ValueError('Bu operatsiya allaqachon bekor qilingan.')
    # Kirim bekor bo'lsa pul hisobdan chiqadi; o'tkazma bekor bo'lsa qabul qilgan hisobdan qaytadi.
    take=row['to_pocket']
    if int(row['amount'])>_available(db,take,row['currency']):
        raise ValueError(f"{POCKETS[take]} hisobida yetarli {row['currency']} yo‘q — avval pul qaytishini ta’minlang.")
    db.execute("UPDATE cash_moves SET status='cancelled',cancel_actor=?,cancel_ts=?,cancel_reason=? WHERE id=?",
               (actor,int(time.time() if now is None else now),reason,int(row['id'])))


def today(now=None):
    return datetime.fromtimestamp(int(time.time() if now is None else now),TZ).date().isoformat()


def close_day(db,actor,counted,note='',now=None):
    """counted: {'cash_uzs': '1000000', ...} — sanalgan pul. Farq yoziladi, qoldiq o'zgarmaydi."""
    if not isinstance(counted,dict) or not counted:raise ValueError('Sanalgan summani kiriting.')
    note=str(note or '').strip()[:500]
    day=today(now);ts=int(time.time() if now is None else now)
    bal=balances(db)
    rows=[]
    for key,val in counted.items():
        if key not in bal:raise ValueError('Hisob noto‘g‘ri.')
        p,c=key.split('_');cur=c.upper()
        if str(val).strip()=='':continue
        n=0 if str(val).strip() in ('0','0.00') else parse_amount(val,cur)
        if db.execute('SELECT 1 FROM cash_closings WHERE day=? AND pocket=? AND currency=?',(day,p,cur)).fetchone():
            raise ValueError(f'{POCKETS[p]} {cur} bugun allaqachon yopilgan.')
        rows.append((day,p,cur,bal[key],n,n-bal[key],note,actor,ts))
    if not rows:raise ValueError('Sanalgan summani kiriting.')
    for r in rows:
        db.execute('INSERT INTO cash_closings(day,pocket,currency,system,counted,diff,note,actor,ts) VALUES(?,?,?,?,?,?,?,?,?)',r)
    return closings(db,day)


def closings(db,day=None,limit=60):
    w,args=('WHERE c.day=?',(day,)) if day else ('',())
    return [{'id':int(r['id']),'day':r['day'],'pocket':r['pocket'],'pocketLabel':POCKETS.get(r['pocket'],r['pocket']),
             'currency':r['currency'],'system':int(r['system']),'counted':int(r['counted']),'diff':int(r['diff']),
             'note':r['note'] or '','who':r['who'] or '','ts':int(r['ts'])}
            for r in db.execute(f'''SELECT c.*,u.name AS who FROM cash_closings c LEFT JOIN users u ON u.id=c.actor {w}
                ORDER BY c.day DESC,c.id DESC LIMIT ?''',(*args,limit)).fetchall()]


# ---------- yagona jurnal ----------

def _type_of_expense(category):
    if 'Дивиденд' in category:return 'dividend','Dividend'
    if 'Иш ҳақи' in category:return 'payroll','Oylik / avans'
    if 'Таъминотчи' in category:return 'supplier','Ta’minotchiga to‘lov'
    return 'expense','Xarajat'


def journal(db,start=None,end=None,limit=200):
    """Barcha kassa harakatlari bitta ro'yxatda: tur, kimdan/kimga, asl summa va valyuta, kurs, hisob, kim, holat."""
    start=0 if start is None else int(start);end=2**62 if end is None else int(end)
    items=[]
    for r in db.execute('''SELECT h.*,u.name AS agent_name,c.name AS cashier_name FROM handovers h LEFT JOIN users u ON u.id=h.agent
        LEFT JOIN users c ON c.id=h.cashier WHERE h.status='accepted' AND COALESCE(h.accepted_ts,h.ts)>=? AND COALESCE(h.accepted_ts,h.ts)<?
        ORDER BY COALESCE(h.accepted_ts,h.ts) DESC LIMIT ?''',(start,end,limit)).fetchall():
        som=int(r['amount'] or 0)//100
        items.append({'type':'handover','group':'income','label':'Agentdan qabul','id':int(r['id']),'from':r['agent_name'] or '',
                      'to':POCKETS['cash'],'currency':'UZS' if som else 'USD','amount':som or int(r['amount_usd'] or 0),
                      'rate':0,'who':r['cashier_name'] or '','ts':int(r['accepted_ts'] or r['ts']),'status':'active','link':{'handover':int(r['id'])}})
    for r in db.execute('''SELECT e.*,u.name AS who FROM cashier_expenses e LEFT JOIN users u ON u.id=e.cashier
        WHERE e.ts>=? AND e.ts<? ORDER BY e.ts DESC LIMIT ?''',(start,end,limit)).fetchall():
        t,lbl=_type_of_expense(r['category'] or '')
        uzs=(r['currency'] or 'USD')=='UZS'
        items.append({'type':t,'group':'expense','label':lbl,'id':int(r['id']),'from':POCKETS.get(r['pay_from'] or 'cash','Naqd'),
                      'to':r['recipient'] or '','category':r['category'] or '','currency':'UZS' if uzs else 'USD',
                      'amount':int(r['amount_uzs'] or 0) if uzs else int(r['amount_usd']),'rate':int(r['rate_uzs_per_usd'] or 0),
                      'note':r['note'] or '','who':r['who'] or '','ts':int(r['ts']),'status':'active'})
    for r in db.execute('''SELECT f.*,u.name AS agent_name,a.name AS who FROM agent_funds f LEFT JOIN users u ON u.id=f.agent
        LEFT JOIN users a ON a.id=f.actor WHERE f.kind='topup' AND f.ts>=? AND f.ts<? ORDER BY f.ts DESC LIMIT ?''',(start,end,limit)).fetchall():
        uzs=int(r['amount_uzs'] or 0)>0
        items.append({'type':'agent_fund','group':'internal','label':'Agent xarajat hisobiga','id':int(r['id']),'from':POCKETS['cash'],
                      'to':r['agent_name'] or '','currency':'UZS' if uzs else 'USD','amount':int(r['amount_uzs']) if uzs else int(r['amount_usd']),
                      'rate':int(r['rate_uzs_per_usd'] or 0),'note':r['note'] or '','who':r['who'] or '','ts':int(r['ts']),'status':'active'})
    for r in db.execute('''SELECT c.*,u.name AS who FROM cashier_conversions c LEFT JOIN users u ON u.id=c.cashier
        WHERE c.ts>=? AND c.ts<? ORDER BY c.ts DESC LIMIT ?''',(start,end,limit)).fetchall():
        other='UZS' if r['from_currency']=='USD' else 'USD'
        items.append({'type':'conversion','group':'internal','label':'Konvertatsiya','id':int(r['id']),
                      'from':f"{POCKETS.get(r['pay_from'],'')} {r['from_currency']}",'to':f"{POCKETS.get(r['pay_from'],'')} {other}",
                      'currency':r['from_currency'],'amount':int(r['amount_from']),'toCurrency':other,'toAmount':int(r['amount_to']),
                      'rate':int(r['rate_uzs_per_usd']),'note':r['note'] or '','who':r['who'] or '','ts':int(r['ts']),'status':'active'})
    for r in db.execute('''SELECT m.*,u.name AS who,cu.name AS cancel_who FROM cash_moves m LEFT JOIN users u ON u.id=m.actor
        LEFT JOIN users cu ON cu.id=m.cancel_actor WHERE m.ts>=? AND m.ts<? ORDER BY m.ts DESC LIMIT ?''',(start,end,limit)).fetchall():
        inc=r['kind']=='income'
        items.append({'type':'income' if inc else 'transfer','group':'income' if inc else 'internal','label':'Kirim' if inc else 'O‘tkazma',
                      'id':int(r['id']),'move':int(r['id']),'from':r['counterparty'] if inc else POCKETS.get(r['from_pocket'],''),
                      'to':POCKETS.get(r['to_pocket'],''),'category':r['category'] or '','currency':r['currency'],'amount':int(r['amount']),
                      'rate':int(r['rate'] or 0),'note':r['note'] or '','who':r['who'] or '','ts':int(r['ts']),'status':r['status'],
                      'cancel':{'who':r['cancel_who'] or '','ts':int(r['cancel_ts'] or 0),'reason':r['cancel_reason'] or ''} if r['status']!='active' else None})
    items.sort(key=lambda x:-x['ts'])
    return items[:limit]


def summary(db,start,end):
    """Davr bo'yicha guruhlar: daromad, xarajat, oylik, dividend, ta'minot, ichki harakat — aralashmaydi (valyuta bo'yicha)."""
    out={}
    for it in journal(db,start,end,limit=100000):
        if it['status']!='active':continue
        key=it['type'] if it['group']!='internal' else 'internal'
        g=out.setdefault(key,{'UZS':0,'USD':0,'count':0})
        g[it['currency']]+=it['amount'];g['count']+=1
    return out


def view(db,start=None,end=None):
    import core
    return {'balances':balances(db),'pockets':[[k,v] for k,v in POCKETS.items()],'incomeCategories':list(INCOME_CATEGORIES),
            'journal':journal(db,start,end,limit=200),'summary':summary(db,start or 0,end or 2**62),
            'closings':closings(db),'today':today(),'rate':core.cashier_rate(db)}
