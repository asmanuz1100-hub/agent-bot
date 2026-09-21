import sqlite3, json, time, math, re, os
from decimal import Decimal, InvalidOperation

PRODUCTS={
    1:'Грунтовка 7/1 — 1 кг',
    3:'Грунтовка 7/1 — 3 кг',
    5:'Грунтовка 7/1 — 5 кг',
}

AGENT_FEATURES=(
    'client','clients','delivery','order','sold',
    'payment','return','visit','handover','balance'
)

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, role TEXT NOT NULL, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY, agent INTEGER NOT NULL, name TEXT, phone TEXT UNIQUE, address TEXT, lat REAL, lon REAL, photo TEXT, shop_name TEXT, comment TEXT DEFAULT '', payment_due TEXT, created_ts INTEGER);
CREATE TABLE IF NOT EXISTS sessions(agent INTEGER PRIMARY KEY, data TEXT);
CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY, agent INTEGER, start INTEGER, end INTEGER, live_id INTEGER);
CREATE UNIQUE INDEX IF NOT EXISTS one_shift ON shifts(agent) WHERE end IS NULL;
CREATE TABLE IF NOT EXISTS points(id INTEGER PRIMARY KEY, shift INTEGER, ts INTEGER, lat REAL, lon REAL, accuracy REAL, UNIQUE(shift,ts));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, actor INTEGER, agent INTEGER, client INTEGER, kind TEXT, pack INTEGER DEFAULT 0, qty INTEGER DEFAULT 0, amount INTEGER DEFAULT 0, amount_usd INTEGER DEFAULT 0, note TEXT DEFAULT '', ts INTEGER, source INTEGER UNIQUE);
CREATE TABLE IF NOT EXISTS handovers(id INTEGER PRIMARY KEY, agent INTEGER, amount INTEGER, amount_usd INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', cashier INTEGER, source INTEGER UNIQUE, ts INTEGER);
CREATE TABLE IF NOT EXISTS return_allocations(return_event INTEGER NOT NULL, delivery_event INTEGER NOT NULL, qty INTEGER NOT NULL, amount_usd INTEGER NOT NULL, PRIMARY KEY(return_event,delivery_event));
CREATE TABLE IF NOT EXISTS failed_updates(update_id INTEGER PRIMARY KEY, actor INTEGER, failure_type TEXT, attempts INTEGER DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending', last_error TEXT, created_ts INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS role_audit(id INTEGER PRIMARY KEY, actor INTEGER NOT NULL, old_id INTEGER, new_id INTEGER, action TEXT NOT NULL, ts INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS processed(id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS products(pack INTEGER PRIMARY KEY, name TEXT NOT NULL, price INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS agent_features(agent INTEGER NOT NULL, feature TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(agent,feature));
CREATE INDEX IF NOT EXISTS idx_clients_agent ON clients(agent);
CREATE INDEX IF NOT EXISTS idx_events_agent_kind_pack ON events(agent,kind,pack);
CREATE INDEX IF NOT EXISTS idx_events_agent_ts ON events(agent,ts);
CREATE INDEX IF NOT EXISTS idx_events_client_ts ON events(client,ts);
CREATE INDEX IF NOT EXISTS idx_points_shift_ts ON points(shift,ts);
CREATE INDEX IF NOT EXISTS idx_shifts_agent_start ON shifts(agent,start);
CREATE INDEX IF NOT EXISTS idx_handovers_agent_status ON handovers(agent,status);
'''

PG_SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id BIGINT PRIMARY KEY, role TEXT NOT NULL, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS clients(id BIGSERIAL PRIMARY KEY, agent BIGINT NOT NULL, name TEXT, phone TEXT UNIQUE, address TEXT, lat DOUBLE PRECISION, lon DOUBLE PRECISION, photo TEXT, shop_name TEXT, comment TEXT DEFAULT '', payment_due TEXT, created_ts BIGINT);
CREATE TABLE IF NOT EXISTS sessions(agent BIGINT PRIMARY KEY, data TEXT);
CREATE TABLE IF NOT EXISTS shifts(id BIGSERIAL PRIMARY KEY, agent BIGINT, start BIGINT, end BIGINT, live_id BIGINT);
CREATE UNIQUE INDEX IF NOT EXISTS one_shift ON shifts(agent) WHERE end IS NULL;
CREATE TABLE IF NOT EXISTS points(id BIGSERIAL PRIMARY KEY, shift BIGINT, ts BIGINT, lat DOUBLE PRECISION, lon DOUBLE PRECISION, accuracy DOUBLE PRECISION, UNIQUE(shift,ts));
CREATE TABLE IF NOT EXISTS events(id BIGSERIAL PRIMARY KEY, actor BIGINT, agent BIGINT, client BIGINT, kind TEXT, pack INTEGER DEFAULT 0, qty INTEGER DEFAULT 0, amount BIGINT DEFAULT 0, amount_usd BIGINT DEFAULT 0, note TEXT DEFAULT '', ts BIGINT, source BIGINT UNIQUE);
CREATE TABLE IF NOT EXISTS handovers(id BIGSERIAL PRIMARY KEY, agent BIGINT, amount BIGINT, amount_usd BIGINT DEFAULT 0, status TEXT DEFAULT 'pending', cashier BIGINT, source BIGINT UNIQUE, ts BIGINT, accepted_ts BIGINT);
CREATE TABLE IF NOT EXISTS return_allocations(return_event BIGINT NOT NULL, delivery_event BIGINT NOT NULL, qty BIGINT NOT NULL, amount_usd BIGINT NOT NULL, PRIMARY KEY(return_event,delivery_event));
CREATE TABLE IF NOT EXISTS failed_updates(update_id BIGINT PRIMARY KEY, actor BIGINT, failure_type TEXT, attempts INTEGER DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending', last_error TEXT, created_ts BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS role_audit(id BIGSERIAL PRIMARY KEY, actor BIGINT NOT NULL, old_id BIGINT, new_id BIGINT, action TEXT NOT NULL, ts BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS processed(id BIGINT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS products(pack INTEGER PRIMARY KEY, name TEXT NOT NULL, price BIGINT DEFAULT 0);
CREATE TABLE IF NOT EXISTS agent_features(agent BIGINT NOT NULL, feature TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(agent,feature));
CREATE INDEX IF NOT EXISTS idx_clients_agent ON clients(agent);
CREATE INDEX IF NOT EXISTS idx_events_agent_kind_pack ON events(agent,kind,pack);
CREATE INDEX IF NOT EXISTS idx_events_agent_ts ON events(agent,ts);
CREATE INDEX IF NOT EXISTS idx_events_client_ts ON events(client,ts);
CREATE INDEX IF NOT EXISTS idx_points_shift_ts ON points(shift,ts);
CREATE INDEX IF NOT EXISTS idx_shifts_agent_start ON shifts(agent,start);
CREATE INDEX IF NOT EXISTS idx_handovers_agent_status ON handovers(agent,status);
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
    # PostgreSQL reserves END for CASE expressions. Quote only the shifts.end
    # column where SQL grammar clearly treats it as a column, never CASE ... END.
    sql=re.sub(r'\bend\b(?=\s+(?:INTEGER|BIGINT)\b)','"end"',sql,flags=re.IGNORECASE)
    sql=re.sub(r'\bend\b(?=\s+IS\b)','"end"',sql,flags=re.IGNORECASE)
    sql=re.sub(r'\bend\b(?=\s*(?:=|>=|<=|>|<))','"end"',sql,flags=re.IGNORECASE)
    sql=re.sub(r'(?<=\.)\bend\b','"end"',sql,flags=re.IGNORECASE)
    return sql

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

def connect(path,initialize=True):
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
        if not initialize:
            db.execute(f'SET search_path TO "{schema}"')
            db.commit()
            return db
        db.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        db.execute(f'SET search_path TO "{schema}"')
        for stmt in PG_SCHEMA.split(';'):
            if stmt.strip():db.execute(stmt)
        db.execute('ALTER TABLE clients ADD COLUMN IF NOT EXISTS shop_name TEXT')
        db.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS comment TEXT DEFAULT ''")
        db.execute('ALTER TABLE clients ADD COLUMN IF NOT EXISTS payment_due TEXT')
        db.execute('ALTER TABLE clients ADD COLUMN IF NOT EXISTS created_ts BIGINT')
        db.execute('ALTER TABLE events ADD COLUMN IF NOT EXISTS amount_usd BIGINT DEFAULT 0')
        db.execute('ALTER TABLE handovers ADD COLUMN IF NOT EXISTS amount_usd BIGINT DEFAULT 0')
        for pack,name in PRODUCTS.items():
            db.execute('INSERT INTO products(pack,name,price) VALUES(?,?,0) ON CONFLICT(pack) DO UPDATE SET name=excluded.name',(pack,name))
        _backfill_unbilled_deliveries(db)
        db.commit()
        return db
    db=sqlite3.connect(path,timeout=30)
    db.row_factory=sqlite3.Row
    if not initialize:
        db.execute('PRAGMA busy_timeout=30000')
        return db
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
    if 'created_ts' not in client_cols:
        db.execute('ALTER TABLE clients ADD COLUMN created_ts INTEGER')
    if 'amount_usd' not in {r[1] for r in db.execute('PRAGMA table_info(events)')}:
        db.execute('ALTER TABLE events ADD COLUMN amount_usd INTEGER DEFAULT 0')
    if 'amount_usd' not in {r[1] for r in db.execute('PRAGMA table_info(handovers)')}:
        db.execute('ALTER TABLE handovers ADD COLUMN amount_usd INTEGER DEFAULT 0')
    for pack,name in PRODUCTS.items():
        db.execute('INSERT INTO products(pack,name,price) VALUES(?,?,0) ON CONFLICT(pack) DO UPDATE SET name=excluded.name',(pack,name))
    _backfill_unbilled_deliveries(db)
    db.execute('PRAGMA journal_mode=WAL')
    return db

def _backfill_unbilled_deliveries(db):
    # One-time migration: only deliveries to clients with no historical sales/payment.
    # Never reinterpret existing UZS sales or payments as USD.
    if db.execute("SELECT 1 FROM meta WHERE key='usd_delivery_backfill_v1'").fetchone():return
    rows=db.execute("""SELECT e.id,e.client,e.pack,e.qty,p.price
        FROM events e JOIN products p ON p.pack=e.pack
        WHERE e.kind='delivery' AND e.amount=0 AND e.amount_usd=0 AND p.price>0
        AND NOT EXISTS (SELECT 1 FROM events older WHERE older.client=e.client
            AND older.kind IN ('sold','payment') AND older.amount<>0)""").fetchall()
    for row in rows:
        db.execute("UPDATE events SET amount_usd=?,note=COALESCE(note,'') || ? WHERE id=? AND amount_usd=0",
                   (int(row[3])*int(row[4]),' | USD ҳисобга ўтказилди: жорий каталог нархи асосида',row[0]))
    db.execute("INSERT INTO meta(key,value) VALUES('usd_delivery_backfill_v1',?) ON CONFLICT(key) DO NOTHING",
               (str(len(rows)),))

def client_debt_usd(db,client):
    row=db.execute("""SELECT COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd
        WHEN kind IN ('payment','return') THEN -amount_usd ELSE 0 END),0)
        FROM events WHERE client=?""",(client,)).fetchone()
    return int(row[0] or 0)

def cash_usd(db,agent):
    paid=db.execute("SELECT COALESCE(SUM(amount_usd),0) FROM handovers WHERE agent=? AND status='accepted'",(agent,)).fetchone()[0]
    return amount(db,agent,['payment'],field='amount_usd')-int(paid or 0)

def legacy_debt_uzs(db,client):
    row=db.execute("""SELECT COALESCE(SUM(CASE WHEN kind='sold' THEN amount
        WHEN kind='payment' THEN -amount ELSE 0 END),0) FROM events WHERE client=?""",(client,)).fetchone()
    return int(row[0] or 0)

def lock_agent(db,agent):
    # This row lock serializes inventory, balances and shifts for one agent
    # across independent PostgreSQL webhook connections.
    if isinstance(db,PostgresDB):
        db.execute('SELECT id FROM users WHERE id=? FOR UPDATE',(agent,)).fetchone()

def _delivery_return_allocations(db,client,pack,qty):
    """Return unsold units against their original USD delivery prices (FIFO).

    A sold unit stays billed but cannot be returned as unsold stock. Reconstruct
    lots in event order, deducting previous sales and explicitly allocated
    returns before choosing available units for the new return.
    """
    events=db.execute("""SELECT id,kind,qty,amount_usd FROM events
        WHERE client=? AND pack=? AND kind IN ('delivery','sold','return')
        ORDER BY id""",(client,pack)).fetchall()
    prior=db.execute("""SELECT a.return_event,a.delivery_event,a.qty
        FROM return_allocations a JOIN events e ON e.id=a.return_event
        WHERE e.client=? AND e.pack=?""",(client,pack)).fetchall()
    assigned={}
    for row in prior:
        assigned.setdefault(int(row['return_event']),[]).append(
            (int(row['delivery_event']),int(row['qty'])))
    lots=[]
    for e in events:
        kind=e['kind']
        if kind=='delivery' and int(e['amount_usd'] or 0)>0:
            units=int(e['qty']);amount=int(e['amount_usd'])
            if units<=0 or amount%units:
                raise ValueError('USD топшириш партияси нархини текширинг.')
            lots.append({'id':int(e['id']),'available':units,'unit':amount//units})
        elif kind=='sold':
            remaining=int(e['qty'])
            for lot in lots:
                n=min(remaining,lot['available'])
                lot['available']-=n;remaining-=n
                if not remaining:break
        elif kind=='return' and int(e['amount_usd'] or 0)>0:
            allocations=assigned.get(int(e['id']))
            if not allocations:
                raise ValueError('Олдинги USD қайтаришда партия белгиланмаган. Админ текширсин.')
            for delivery_id,units in allocations:
                lot=next((lot for lot in lots if lot['id']==delivery_id),None)
                if lot is None or units<=0 or units>lot['available']:
                    raise ValueError('Товар қайтариш партиясида мос келмаслик бор.')
                lot['available']-=units
    remaining=qty;result=[]
    for lot in lots:
        take=min(remaining,lot['available'])
        if take:
            result.append((lot['id'],take,take*lot['unit']))
            remaining-=take
        if not remaining:break
    if remaining:
        raise ValueError('Қайтарилган товар учун USD партия қолдиғи етарли эмас. Админ ҳисобни текширсин.')
    return result

def transfer_agent_account(db,actor,old_id,new_id):
    """Replace an agent's Telegram login, preserving client, stock and ledger history.

    The caller must be a primary admin; we re-check the actor's DB role here.
    A closed shift is required so the old account's live-location message
    cannot accidentally become associated with the new Telegram account.
    """
    if db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()[0]!='admin':
        raise ValueError('Фақат админ.')
    if not isinstance(new_id,int) or new_id<=0 or old_id==new_id:
        raise ValueError('Янги Telegram ID нотўғри.')
    if isinstance(db,PostgresDB):
        db.execute('SELECT id FROM users WHERE id IN (?,?) ORDER BY id FOR UPDATE',(old_id,new_id)).fetchall()
    current=db.execute('SELECT name,role FROM users WHERE id=?',(old_id,)).fetchone()
    if not current or current['role']!='agent':raise ValueError('Эски ID агент эмас.')
    if db.execute('SELECT 1 FROM users WHERE id=?',(new_id,)).fetchone():
        raise ValueError('Янги ID аввал рўйхатдан ўтган. Бўш Telegram ID киритинг.')
    if db.execute('SELECT 1 FROM shifts WHERE agent=? AND end IS NULL',(old_id,)).fetchone():
        raise ValueError('Аввал агент сменасини ёпинг.')
    db.execute('INSERT INTO users(id,role,name) VALUES(?,?,?)',(new_id,'agent',current['name']))
    for table in ('clients','events','shifts','handovers'):
        db.execute(f'UPDATE {table} SET agent=? WHERE agent=?',(new_id,old_id))
    db.execute('INSERT INTO agent_features(agent,feature,enabled) SELECT ?,feature,enabled FROM agent_features WHERE agent=?',
               (new_id,old_id))
    db.execute('DELETE FROM agent_features WHERE agent=?',(old_id,))
    db.execute('DELETE FROM sessions WHERE agent=?',(old_id,))
    db.execute("UPDATE users SET role='disabled' WHERE id=?",(old_id,))
    db.execute('INSERT INTO role_audit(actor,old_id,new_id,action,ts) VALUES(?,?,?,?,?)',
               (actor,old_id,new_id,'agent_transfer',int(time.time())))

def feature_enabled(db,agent,feature):
    if feature not in AGENT_FEATURES:return True
    row=db.execute('SELECT enabled FROM agent_features WHERE agent=? AND feature=?',(agent,feature)).fetchone()
    return True if row is None else bool(row[0])

def set_agent_feature(db,actor,agent,feature,enabled):
    r=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not r or r[0]!='admin':raise ValueError('Фақат админ хизматларни бошқаради.')
    a=db.execute("SELECT role FROM users WHERE id=?",(agent,)).fetchone()
    if not a or a[0]!='agent':raise ValueError('Агент топилмади.')
    if feature not in AGENT_FEATURES:raise ValueError('Хизмат топилмади.')
    db.execute(
        'INSERT INTO agent_features(agent,feature,enabled) VALUES(?,?,?) '
        'ON CONFLICT(agent,feature) DO UPDATE SET enabled=excluded.enabled',
        (agent,feature,1 if enabled else 0)
    )

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
    assert field in ('qty','amount','amount_usd')
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

def record(db, actor, agent, client, kind, pack=0, qty=0, value=0, note='', source=None, currency='UZS'):
    role=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not role or role[0] not in ('admin','agent'): raise ValueError('Рухсат йўқ.')
    if role[0]!='admin' and actor!=agent: raise ValueError('Рухсат йўқ.')
    target=db.execute('SELECT role FROM users WHERE id=?',(agent,)).fetchone()
    if not target or target[0]!='agent': raise ValueError('Агент топилмади.')
    if kind not in ('load','delivery','sold','return','payment','order','visit'): raise ValueError('Амал нотўғри.')
    lock_agent(db,agent)
    if kind=='load' and role[0]!='admin': raise ValueError('Товарни фақат админ беради.')
    if kind!='load':
        c=db.execute('SELECT agent FROM clients WHERE id=?',(client,)).fetchone()
        if not c or c[0]!=agent: raise ValueError('Мижоз бу агентга тегишли эмас.')
    if kind in ('load','delivery','sold','return','order'):
        if pack not in (1,3,5) or not isinstance(qty,int) or qty<=0: raise ValueError('Қадоқ ёки миқдор нотўғри.')
    if kind=='delivery' and agent_stock(db,agent,pack)<qty: raise ValueError('Агентда етарли товар йўқ. Админ кирим қилсин.')
    if kind in ('sold','return') and client_stock(db,agent,client,pack)<qty: raise ValueError('Мижозда етарли товар йўқ.')
    if currency not in ('USD','UZS'):raise ValueError('Валюта нотўғри.')
    if kind=='payment' and (not isinstance(value,int) or value<=0): raise ValueError('Сумма киритилмаган.')
    if currency=='UZS' and kind=='sold' and (not isinstance(value,int) or value<=0):
        raise ValueError('Сумма киритилмаган.')
    usd=0;allocations=[]
    if currency=='USD':
        if kind=='delivery':
            unit=product_price(db,pack)
            if unit<=0:raise ValueError('Админ аввал товарнинг USD нархини киритсин.')
            usd=qty*unit
        elif kind=='return':
            allocations=_delivery_return_allocations(db,client,pack,qty)
            usd=sum(a[2] for a in allocations)
        elif kind=='payment':usd=value
        # Sale is physical confirmation only: delivery already generated the USD receivable.
        value=0
    cur=db.execute('INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source) VALUES(?,?,?,?,?,?,?,?,?,?,?) RETURNING id',
               (actor,agent,client,kind,pack,qty,value,usd,note,int(time.time()),source))
    if allocations:
        return_id=cur.fetchone()[0]
        for delivery_id,count,cents in allocations:
            db.execute('INSERT INTO return_allocations(return_event,delivery_event,qty,amount_usd) VALUES(?,?,?,?)',
                       (return_id,delivery_id,count,cents))

def handover(db,a,value,source,currency='UZS'):
    role=db.execute('SELECT role FROM users WHERE id=?',(a,)).fetchone()
    if not role or role[0]!='agent': raise ValueError('Фақат агент.')
    lock_agent(db,a)
    if currency not in ('USD','UZS'):raise ValueError('Валюта нотўғри.')
    field='amount_usd' if currency=='USD' else 'amount'
    reserved=db.execute(f"SELECT COALESCE(SUM({field}),0) FROM handovers WHERE agent=? AND status='pending'",(a,)).fetchone()[0]
    available=cash_usd(db,a) if currency=='USD' else cash(db,a)
    if value<=0 or value>available-reserved: raise ValueError('Қўлдаги эркин пулдан ортиқ сумма.')
    db.execute('INSERT INTO handovers(agent,amount,amount_usd,source,ts) VALUES(?,?,?,?,?)',
               (a,0 if currency=='USD' else value,value if currency=='USD' else 0,source,int(time.time())))

def accept(db,actor,hid,accepted=True):
    r=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not r or r[0]!='cashier': raise ValueError('Фақат кассир тасдиқлайди.')
    row=db.execute("SELECT * FROM handovers WHERE id=? AND status='pending'",(hid,)).fetchone()
    if not row: raise ValueError('Топшириқ топилмади ёки аввал тасдиқланган.')
    lock_agent(db,row['agent'])
    # Re-read after acquiring the agent's ledger lock: another cashier may
    # have accepted this handover in the meantime.
    row=db.execute("SELECT * FROM handovers WHERE id=? AND status='pending'",(hid,)).fetchone()
    if not row:raise ValueError('Бу топшириқ аввал ҳал қилинган.')
    if accepted and (cash_usd(db,row['agent'])<row['amount_usd'] or cash(db,row['agent'])<row['amount']): raise ValueError('Агент пули етарли эмас.')
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
