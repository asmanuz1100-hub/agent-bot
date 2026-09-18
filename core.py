import sqlite3, json, time, math, re, os
from decimal import Decimal, InvalidOperation

PRODUCTS={
    1:'Грунтовка 7/1 — 1 кг',
    3:'Грунтовка 7/1 — 3 кг',
    5:'Грунтовка 7/1 — 5 кг',
}

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, role TEXT NOT NULL, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY, agent INTEGER NOT NULL, name TEXT, phone TEXT UNIQUE, address TEXT, lat REAL, lon REAL, photo TEXT, shop_name TEXT, comment TEXT DEFAULT '', payment_due TEXT);
CREATE TABLE IF NOT EXISTS sessions(agent INTEGER PRIMARY KEY, data TEXT);
CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY, agent INTEGER, start INTEGER, end INTEGER, live_id INTEGER);
CREATE UNIQUE INDEX IF NOT EXISTS one_shift ON shifts(agent) WHERE end IS NULL;
CREATE TABLE IF NOT EXISTS points(id INTEGER PRIMARY KEY, shift INTEGER, ts INTEGER, lat REAL, lon REAL, accuracy REAL, UNIQUE(shift,ts));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, actor INTEGER, agent INTEGER, client INTEGER, kind TEXT, pack INTEGER DEFAULT 0, qty INTEGER DEFAULT 0, amount INTEGER DEFAULT 0, note TEXT DEFAULT '', ts INTEGER, source INTEGER UNIQUE);
CREATE TABLE IF NOT EXISTS handovers(id INTEGER PRIMARY KEY, agent INTEGER, amount INTEGER, status TEXT DEFAULT 'pending', cashier INTEGER, source INTEGER UNIQUE, ts INTEGER);
CREATE TABLE IF NOT EXISTS processed(id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS products(pack INTEGER PRIMARY KEY, name TEXT NOT NULL, price INTEGER DEFAULT 0);
'''

PG_SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id BIGINT PRIMARY KEY, role TEXT NOT NULL, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS clients(id BIGSERIAL PRIMARY KEY, agent BIGINT NOT NULL, name TEXT, phone TEXT UNIQUE, address TEXT, lat DOUBLE PRECISION, lon DOUBLE PRECISION, photo TEXT, shop_name TEXT, comment TEXT DEFAULT '', payment_due TEXT);
CREATE TABLE IF NOT EXISTS sessions(agent BIGINT PRIMARY KEY, data TEXT);
CREATE TABLE IF NOT EXISTS shifts(id BIGSERIAL PRIMARY KEY, agent BIGINT, start BIGINT, end BIGINT, live_id BIGINT);
CREATE UNIQUE INDEX IF NOT EXISTS one_shift ON shifts(agent) WHERE end IS NULL;
CREATE TABLE IF NOT EXISTS points(id BIGSERIAL PRIMARY KEY, shift BIGINT, ts BIGINT, lat DOUBLE PRECISION, lon DOUBLE PRECISION, accuracy DOUBLE PRECISION, UNIQUE(shift,ts));
CREATE TABLE IF NOT EXISTS events(id BIGSERIAL PRIMARY KEY, actor BIGINT, agent BIGINT, client BIGINT, kind TEXT, pack INTEGER DEFAULT 0, qty INTEGER DEFAULT 0, amount BIGINT DEFAULT 0, note TEXT DEFAULT '', ts BIGINT, source BIGINT UNIQUE);
CREATE TABLE IF NOT EXISTS handovers(id BIGSERIAL PRIMARY KEY, agent BIGINT, amount BIGINT, status TEXT DEFAULT 'pending', cashier BIGINT, source BIGINT UNIQUE, ts BIGINT, accepted_ts BIGINT);
CREATE TABLE IF NOT EXISTS processed(id BIGINT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS products(pack INTEGER PRIMARY KEY, name TEXT NOT NULL, price BIGINT DEFAULT 0);
'''

class HybridRow:
    __slots__=('columns','values','data')
    def __init__(self, columns, values):
        self.columns=columns
        self.values=tuple(values)
        self.data=dict(zip(columns,self.values))
    def __getitem__(self,key):
        return self.values[key] if isinstance(key,(int,slice)) else self.data[key]
    def __iter__(self): return iter(self.values)
    def __len__(self): return len(self.values)
    def keys(self): return self.data.keys()

def _hybrid_row(cursor):
    if cursor.description is None:
        return lambda values: values
    cols=[c.name for c in cursor.description]
    return lambda values: HybridRow(cols,values)

def _pg_sql(sql):
    sql=sql.replace('?','%s')
    return re.sub(r'\\bend\\b','"end"',sql,flags=re.IGNORECASE)

class PostgresDB:
    def __init__(self,conn): self.conn=conn
    def execute(self,sql,params=()):
        return self.conn.execute(_pg_sql(sql),params)
    def executemany(self,sql,params):
        cur=self.conn.cursor()
        cur.executemany(_pg_sql(sql),params)
        return cur
    def commit(self): self.conn.commit()
    def rollback(self): self.conn.rollback()
    def close(self): self.conn.close()
    def __enter__(self): return self
    def __exit__(self,typ,val,tb):
        if typ is None:self.conn.commit()
        else:self.conn.rollback()
        return False

def is_integrity_error(exc):
    if isinstance(exc,sqlite3.IntegrityError):return True
    return exc.__class__.__name__ in ('IntegrityError','UniqueViolation','ForeignKeyViolation','NotNullViolation','CheckViolation')

def connect(path):
    if str(path).startswith(('postgres://','postgresql://')):
        try:
            import psycopg
        except ImportError as e:
            raise RuntimeError('PostgreSQL учун psycopg ўрнатилмаган.') from e
        conn=psycopg.connect(path,row_factory=_hybrid_row)
        db=PostgresDB(conn)
        schema=(os.getenv('DB_SCHEMA','agentbot') or 'agentbot').strip()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',schema):
            raise ValueError('DB_SCHEMA нотўғри.')
        db.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        db.execute(f'SET search_path TO "{schema}"')
        for stmt in PG_SCHEMA.split(';'):
            if stmt.strip():db.execute(stmt)
        db.execute('ALTER TABLE clients ADD COLUMN IF NOT EXISTS shop_name TEXT')
        db.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS comment TEXT DEFAULT ''")
        db.execute('ALTER TABLE clients ADD COLUMN IF NOT EXISTS payment_due TEXT')
        for pack,name in PRODUCTS.items():
            db.execute('INSERT INTO products(pack,name,price) VALUES(?,?,0) ON CONFLICT(pack) DO UPDATE SET name=excluded.name',(pack,name))
        db.commit()
        return db
    db=sqlite3.connect(path)
    db.row_factory=sqlite3.Row
    db.executescript(SCHEMA)
    if 'accepted_ts' not in {r[1] for r in db.execute('PRAGMA table_info(handovers)')}:
        db.execute('ALTER TABLE handovers ADD COLUMN accepted_ts INTEGER')
    client_cols={r[1] for r in db.execute('PRAGMA table_info(clients)')}
    if 'shop_name' not in client_cols:
        db.execute('ALTER TABLE clients ADD COLUMN shop_name TEXT')
    if 'comment' not in client_cols:
        db.execute("ALTER TABLE clients ADD COLUMN comment TEXT DEFAULT ''")
    if 'payment_due' not in client_cols:
        db.execute('ALTER TABLE clients ADD COLUMN payment_due TEXT')
    for pack,name in PRODUCTS.items():
        db.execute('INSERT INTO products(pack,name,price) VALUES(?,?,0) ON CONFLICT(pack) DO UPDATE SET name=excluded.name',(pack,name))
    db.execute('PRAGMA journal_mode=WAL')
    return db

def product_name(pack):
    return PRODUCTS.get(int(pack),f'Товар {pack}')

def product_price(db,pack):
    row=db.execute('SELECT price FROM products WHERE pack=?',(pack,)).fetchone()
    return int(row[0]) if row else 0

def set_product_price(db,actor,pack,value):
    r=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not r or r[0]!='admin':raise ValueError('Нархни фақат админ ўзгартиради.')
    if pack not in PRODUCTS:raise ValueError('Товар топилмади.')
    if not isinstance(value,int) or value<=0:raise ValueError('Нарх нотўғри.')
    db.execute('UPDATE products SET price=?,name=? WHERE pack=?',(value,PRODUCTS[pack],pack))

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
        if s['live_id'] is not None and s['live_id']!=mid:return False
        if s['live_id'] is None:
            db.execute('UPDATE shifts SET live_id=? WHERE id=?',(mid,s['id']))
    if not loc.get('live_period'):return False
    if not (-90<=loc['latitude']<=90 and -180<=loc['longitude']<=180): return False
    db.execute('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,?) ON CONFLICT(shift,ts) DO NOTHING',(s['id'],ts,loc['latitude'],loc['longitude'],loc.get('horizontal_accuracy')))
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
