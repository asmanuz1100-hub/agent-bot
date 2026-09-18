import sqlite3, json, time, math
from decimal import Decimal, InvalidOperation

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, role TEXT NOT NULL, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY, agent INTEGER NOT NULL, name TEXT, phone TEXT UNIQUE, address TEXT, lat REAL, lon REAL, photo TEXT);
CREATE TABLE IF NOT EXISTS sessions(agent INTEGER PRIMARY KEY, data TEXT);
CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY, agent INTEGER, start INTEGER, end INTEGER, live_id INTEGER);
CREATE UNIQUE INDEX IF NOT EXISTS one_shift ON shifts(agent) WHERE end IS NULL;
CREATE TABLE IF NOT EXISTS points(id INTEGER PRIMARY KEY, shift INTEGER, ts INTEGER, lat REAL, lon REAL, accuracy REAL, UNIQUE(shift,ts));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, actor INTEGER, agent INTEGER, client INTEGER, kind TEXT, pack INTEGER DEFAULT 0, qty INTEGER DEFAULT 0, amount INTEGER DEFAULT 0, note TEXT DEFAULT '', ts INTEGER, source INTEGER UNIQUE);
CREATE TABLE IF NOT EXISTS handovers(id INTEGER PRIMARY KEY, agent INTEGER, amount INTEGER, status TEXT DEFAULT 'pending', cashier INTEGER, source INTEGER UNIQUE, ts INTEGER);
CREATE TABLE IF NOT EXISTS processed(id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
'''

def connect(path):
    db=sqlite3.connect(path); db.row_factory=sqlite3.Row
    db.executescript(SCHEMA)
    if 'accepted_ts' not in {r[1] for r in db.execute('PRAGMA table_info(handovers)')}:
        db.execute('ALTER TABLE handovers ADD COLUMN accepted_ts INTEGER')
    db.execute('PRAGMA journal_mode=WAL'); return db

def money(value):
    try:
        n=Decimal(str(value).replace(' ', '').replace(',', '.'))
        if not n.is_finite() or n<=0 or n*100 != (n*100).to_integral_value() or n>10**12: raise ValueError()
        return int(n*100)
    except (InvalidOperation, ValueError): raise ValueError('Мусбат сумма киритинг (кўпи билан 2 каср хона).')

def count(value):
    if not str(value).isdigit() or not 0<int(value)<=100000: raise ValueError('1 дан 100000 гача бутун сон киритинг.')
    return int(value)

def amount(db, agent, kinds, client=None, pack=None, field='qty'):
    assert field in ('qty','amount')
    q=f'SELECT COALESCE(SUM({field}),0) FROM events WHERE agent=? AND kind IN ({",".join("?" for _ in kinds)})'
    args=[agent,*kinds]
    if client is not None: q+=' AND client=?'; args.append(client)
    if pack is not None: q+=' AND pack=?'; args.append(pack)
    return db.execute(q,args).fetchone()[0]

def agent_stock(db,a,p):
    return amount(db,a,['load'],pack=p)-amount(db,a,['delivery'],pack=p)+amount(db,a,['return'],pack=p)

def client_stock(db,a,c,p):
    return amount(db,a,['delivery'],c,p)-amount(db,a,['sold','return'],c,p)

def cash(db,a):
    collected=amount(db,a,['payment'],field='amount')
    paid=db.execute("SELECT COALESCE(SUM(amount),0) FROM handovers WHERE agent=? AND status='accepted'",(a,)).fetchone()[0]
    return collected-paid

def record(db, actor, agent, client, kind, pack=0, qty=0, value=0, note='', source=None):
    role=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not role or role[0] not in ('admin','agent'): raise ValueError('Рухсат йўқ.')
    if role[0]!='admin' and actor!=agent: raise ValueError('Рухсат йўқ.')
    target=db.execute('SELECT role FROM users WHERE id=?',(agent,)).fetchone()
    if not target or target[0]!='agent': raise ValueError('Агент топилмади.')
    if kind not in ('load','delivery','sold','return','payment','order','visit'): raise ValueError('Амал нотўғри.')
    if kind=='load' and role[0]!='admin': raise ValueError('Товарни фақат админ беради.')
    if kind!='load':
        c=db.execute('SELECT agent FROM clients WHERE id=?',(client,)).fetchone()
        if not c or c[0]!=agent: raise ValueError('Мижоз бу агентга тегишли эмас.')
    if kind in ('load','delivery','sold','return','order'):
        if pack not in (1,3,5) or not isinstance(qty,int) or qty<=0: raise ValueError('Қадоқ ёки миқдор нотўғри.')
    if kind=='delivery' and agent_stock(db,agent,pack)<qty: raise ValueError('Агентда етарли товар йўқ. Админ кирим қилсин.')
    if kind in ('sold','return') and client_stock(db,agent,client,pack)<qty: raise ValueError('Мижозда етарли товар йўқ.')
    if kind in ('sold','payment') and (not isinstance(value,int) or value<=0): raise ValueError('Сумма киритилмаган.')
    db.execute('INSERT INTO events(actor,agent,client,kind,pack,qty,amount,note,ts,source) VALUES(?,?,?,?,?,?,?,?,?,?)',(actor,agent,client,kind,pack,qty,value,note,int(time.time()),source))

def handover(db,a,value,source):
    role=db.execute('SELECT role FROM users WHERE id=?',(a,)).fetchone()
    if not role or role[0]!='agent': raise ValueError('Фақат агент.')
    reserved=db.execute("SELECT COALESCE(SUM(amount),0) FROM handovers WHERE agent=? AND status='pending'",(a,)).fetchone()[0]
    if value<=0 or value>cash(db,a)-reserved: raise ValueError('Қўлдаги эркин пулдан ортиқ сумма.')
    db.execute('INSERT INTO handovers(agent,amount,source,ts) VALUES(?,?,?,?)',(a,value,source,int(time.time())))

def accept(db,actor,hid,accepted=True):
    r=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not r or r[0]!='cashier': raise ValueError('Фақат кассир тасдиқлайди.')
    row=db.execute("SELECT * FROM handovers WHERE id=? AND status='pending'",(hid,)).fetchone()
    if not row: raise ValueError('Топшириқ топилмади ёки аввал тасдиқланган.')
    if accepted and cash(db,row['agent'])<row['amount']: raise ValueError('Агент пули етарли эмас.')
    db.execute('UPDATE handovers SET status=?,cashier=?,accepted_ts=? WHERE id=?',('accepted' if accepted else 'rejected',actor,int(time.time()),hid))

def point(db,agent,message,edited=False):
    s=db.execute('SELECT * FROM shifts WHERE agent=? AND end IS NULL',(agent,)).fetchone()
    if not s:return False
    loc=message['location']; mid=message['message_id']; ts=message.get('edit_date',message['date'])
    if ts<s['start']:return False
    if edited and s['live_id']!=mid:return False
    if not edited:
        if not loc.get('live_period'):return False
        db.execute('UPDATE shifts SET live_id=? WHERE id=?',(mid,s['id']))
    if not loc.get('live_period'):return False
    if not (-90<=loc['latitude']<=90 and -180<=loc['longitude']<=180): return False
    db.execute('INSERT OR IGNORE INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,?)',(s['id'],ts,loc['latitude'],loc['longitude'],loc.get('horizontal_accuracy')))
    return True

def distance(a,b):
    la,lb=math.radians(a['lat']),math.radians(b['lat'])
    x=math.sin((lb-la)/2)**2+math.cos(la)*math.cos(lb)*math.sin(math.radians(b['lon']-a['lon'])/2)**2
    return 6371000*2*math.asin(min(1,math.sqrt(x)))

def route_stats(points,start,end):
    km=0; gaps=[]; stops=[]; anchor=None; last=None
    if not points:return {'km':0,'gaps':[(start,end)],'stops':[]}
    if points[0]['ts']-start>300:gaps.append((start,points[0]['ts']))
    for p in points:
        if last:
            dt=p['ts']-last['ts']; d=distance(last,p)
            if dt>300:
                gaps.append((last['ts'],p['ts'])); anchor=None
            elif dt>0 and d/dt<=55 and (p['accuracy'] or 0)<=100 and (last['accuracy'] or 0)<=100:km+=d/1000
            else: anchor=None
        if (p['accuracy'] or 0)>100:
            anchor=None
        elif anchor is None:anchor=p
        elif distance(anchor,p)>70:
            if last and last['ts']-anchor['ts']>=300:stops.append((anchor['ts'],last['ts'],anchor['lat'],anchor['lon']))
            anchor=p
        last=p
    if anchor and last['ts']-anchor['ts']>=300:stops.append((anchor['ts'],last['ts'],anchor['lat'],anchor['lon']))
    if end-points[-1]['ts']>300:gaps.append((points[-1]['ts'],end))
    return {'km':round(km,2),'gaps':gaps,'stops':stops}
