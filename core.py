import sqlite3, json, time, math, re, os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

PRODUCT_CATALOG={
    # Existing Gruntovka 7/1 SKUs keep their historical IDs.
    1:   {'name':'Грунтовка 7/1 — 1 кг','weight_kg':1,'block_units':10,'default_price':0},
    3:   {'name':'Грунтовка 7/1 — 3 кг','weight_kg':3,'block_units':6,'default_price':0},
    5:   {'name':'Грунтовка 7/1 — 5 кг','weight_kg':5,'block_units':2,'default_price':0},

    # Emulsion SKUs use unique internal IDs because several products share
    # the same 4/7/10/20 kg package sizes.
    1004:{'name':'Эмульсия — Стен и потолков — 4 кг','weight_kg':4,'block_units':None,'default_price':375},
    1007:{'name':'Эмульсия — Стен и потолков — 7 кг','weight_kg':7,'block_units':None,'default_price':565},
    1010:{'name':'Эмульсия — Стен и потолков — 10 кг','weight_kg':10,'block_units':None,'default_price':785},
    1020:{'name':'Эмульсия — Стен и потолков — 20 кг','weight_kg':20,'block_units':None,'default_price':1500},

    2004:{'name':'Эмульсия — Фасадная — 4 кг','weight_kg':4,'block_units':None,'default_price':390},
    2007:{'name':'Эмульсия — Фасадная — 7 кг','weight_kg':7,'block_units':None,'default_price':590},
    2010:{'name':'Эмульсия — Фасадная — 10 кг','weight_kg':10,'block_units':None,'default_price':820},
    2020:{'name':'Эмульсия — Фасадная — 20 кг','weight_kg':20,'block_units':None,'default_price':1565},

    3004:{'name':'Эмульсия — Моющаяся / A-baza — 4 кг','weight_kg':4,'block_units':None,'default_price':415},
    3007:{'name':'Эмульсия — Моющаяся / A-baza — 7 кг','weight_kg':7,'block_units':None,'default_price':635},
    3010:{'name':'Эмульсия — Моющаяся / A-baza — 10 кг','weight_kg':10,'block_units':None,'default_price':885},
    3020:{'name':'Эмульсия — Моющаяся / A-baza — 20 кг','weight_kg':20,'block_units':None,'default_price':1700},

    4004:{'name':'Эмульсия — B-baza — 4 кг','weight_kg':4,'block_units':None,'default_price':530},
    4007:{'name':'Эмульсия — B-baza — 7 кг','weight_kg':7,'block_units':None,'default_price':840},
    4010:{'name':'Эмульсия — B-baza — 10 кг','weight_kg':10,'block_units':None,'default_price':1180},
    4020:{'name':'Эмульсия — B-baza — 20 кг','weight_kg':20,'block_units':None,'default_price':2285},

    5004:{'name':'Эмульсия — C-baza — 4 кг','weight_kg':4,'block_units':None,'default_price':545},
    5007:{'name':'Эмульсия — C-baza — 7 кг','weight_kg':7,'block_units':None,'default_price':850},
    5010:{'name':'Эмульсия — C-baza — 10 кг','weight_kg':10,'block_units':None,'default_price':1190},
    5020:{'name':'Эмульсия — C-baza — 20 кг','weight_kg':20,'block_units':None,'default_price':2300},
}
PRODUCTS={sku:item['name'] for sku,item in PRODUCT_CATALOG.items()}
PRODUCT_WEIGHTS={sku:int(item['weight_kg']) for sku,item in PRODUCT_CATALOG.items()}
PRODUCT_DEFAULT_PRICES={sku:int(item['default_price']) for sku,item in PRODUCT_CATALOG.items()}
PACK_UNITS={sku:int(item['block_units']) for sku,item in PRODUCT_CATALOG.items() if item['block_units']}
BUILTIN_PRODUCTS=frozenset(PRODUCT_CATALOG)
# Products the manager added in the Ombor (warehouse) section live in the
# products table and are merged into the dicts above by refresh_catalog().
INACTIVE_PRODUCTS=set()
CUSTOM_PRODUCT_START=100000

def product_ids():
    return tuple(PRODUCTS.keys())

def active_product_ids():
    return tuple(p for p in PRODUCTS if p not in INACTIVE_PRODUCTS)

def product_weight(pack):
    try:return PRODUCT_WEIGHTS[int(pack)]
    except (KeyError,TypeError,ValueError):raise ValueError('Нотўғри товар.')

def refresh_catalog(db):
    """Merge manager-added products and archive flags from the DB into the in-memory catalog."""
    try:
        rows=db.execute('SELECT pack,name,weight_kg,block_units,active,custom FROM products').fetchall()
    except Exception:
        return
    seen=set()
    for r in rows:
        pack=int(r['pack'])
        if int(r['custom'] or 0) and pack not in BUILTIN_PRODUCTS:
            seen.add(pack)
            PRODUCTS[pack]=r['name']
            w=float(r['weight_kg'] or 0);PRODUCT_WEIGHTS[pack]=int(w) if w==int(w) else w
            if int(r['block_units'] or 0)>0:PACK_UNITS[pack]=int(r['block_units'])
            else:PACK_UNITS.pop(pack,None)
        if pack in PRODUCTS:
            if int(r['active'] if r['active'] is not None else 1):INACTIVE_PRODUCTS.discard(pack)
            else:INACTIVE_PRODUCTS.add(pack)
    for pack in [p for p in PRODUCTS if p not in BUILTIN_PRODUCTS and p not in seen]:
        PRODUCTS.pop(pack,None);PRODUCT_WEIGHTS.pop(pack,None);PACK_UNITS.pop(pack,None);INACTIVE_PRODUCTS.discard(pack)

def block_units(pack):
    try:return PACK_UNITS.get(int(pack))
    except (TypeError,ValueError):return None

def units_per_block(pack):
    units=block_units(pack)
    if not units:raise ValueError('Бу товар учун блок миқдори белгиланмаган.')
    return units

AGENT_FEATURES=(
    'client','clients','delivery','order','sold',
    'payment','return','visit','handover','balance'
)

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, role TEXT NOT NULL, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS user_profiles(user_id INTEGER PRIMARY KEY, photo TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', updated_ts INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS photo_thumbs(file_id TEXT PRIMARY KEY, data BLOB NOT NULL, ts INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY, agent INTEGER NOT NULL, name TEXT, phone TEXT UNIQUE, address TEXT, region TEXT NOT NULL DEFAULT '', lat REAL, lon REAL, photo TEXT, shop_name TEXT, comment TEXT DEFAULT '', payment_due TEXT, created_ts INTEGER, map_only INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS deleted_clients(id INTEGER PRIMARY KEY, agent INTEGER NOT NULL, name TEXT, phone TEXT, address TEXT, region TEXT NOT NULL DEFAULT '', lat REAL, lon REAL, photo TEXT, shop_name TEXT, comment TEXT DEFAULT '', payment_due TEXT, created_ts INTEGER, map_only INTEGER NOT NULL DEFAULT 0, deleted_by INTEGER NOT NULL, deleted_ts INTEGER NOT NULL, debt_usd INTEGER NOT NULL DEFAULT 0, event_count INTEGER NOT NULL DEFAULT 0, visit_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions(agent INTEGER PRIMARY KEY, data TEXT);
CREATE TABLE IF NOT EXISTS client_blacklist_log(id INTEGER PRIMARY KEY, client INTEGER NOT NULL, actor INTEGER NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', ts INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY, agent INTEGER, start INTEGER, end INTEGER, live_id INTEGER);
CREATE UNIQUE INDEX IF NOT EXISTS one_shift ON shifts(agent) WHERE end IS NULL;
CREATE TABLE IF NOT EXISTS points(id INTEGER PRIMARY KEY, shift INTEGER, ts INTEGER, lat REAL, lon REAL, accuracy REAL, UNIQUE(shift,ts));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, actor INTEGER, agent INTEGER, client INTEGER, kind TEXT, pack INTEGER DEFAULT 0, qty INTEGER DEFAULT 0, amount INTEGER DEFAULT 0, amount_usd INTEGER DEFAULT 0, note TEXT DEFAULT '', ts INTEGER, source INTEGER UNIQUE);
CREATE TABLE IF NOT EXISTS handovers(id INTEGER PRIMARY KEY, agent INTEGER, amount INTEGER, amount_usd INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', cashier INTEGER, source INTEGER UNIQUE, ts INTEGER);
CREATE TABLE IF NOT EXISTS cashier_expenses(id INTEGER PRIMARY KEY, cashier INTEGER NOT NULL, amount_usd INTEGER NOT NULL CHECK(amount_usd>0), category TEXT NOT NULL, recipient TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', source INTEGER NOT NULL UNIQUE, ts INTEGER NOT NULL, currency TEXT NOT NULL DEFAULT 'USD', amount_uzs INTEGER NOT NULL DEFAULT 0, rate_uzs_per_usd INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS cashier_incomes(id INTEGER PRIMARY KEY, cashier INTEGER NOT NULL, amount_usd INTEGER NOT NULL CHECK(amount_usd>0), category TEXT NOT NULL, source_name TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', source INTEGER NOT NULL UNIQUE, ts INTEGER NOT NULL, currency TEXT NOT NULL DEFAULT 'USD', amount_uzs INTEGER NOT NULL DEFAULT 0, rate_uzs_per_usd INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS cashier_fx_rates(id INTEGER PRIMARY KEY, cashier INTEGER NOT NULL, rate_uzs_per_usd INTEGER NOT NULL, source INTEGER NOT NULL UNIQUE, ts INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, agent INTEGER NOT NULL, client INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new','preparing','loaded','delivered','rejected')), note TEXT NOT NULL DEFAULT '', admin_note TEXT NOT NULL DEFAULT '', source INTEGER NOT NULL UNIQUE, ts INTEGER NOT NULL, updated_ts INTEGER NOT NULL, admin INTEGER);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status,ts);
CREATE INDEX IF NOT EXISTS idx_orders_client ON orders(client,ts);
CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, pack INTEGER, custom_name TEXT NOT NULL DEFAULT '', qty INTEGER NOT NULL CHECK(qty>0));
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE TABLE IF NOT EXISTS visit_stock(id INTEGER PRIMARY KEY, visit INTEGER NOT NULL, client INTEGER NOT NULL, pack INTEGER NOT NULL, counted INTEGER NOT NULL CHECK(counted>=0), expected INTEGER NOT NULL DEFAULT 0, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_visit_stock_visit ON visit_stock(visit);
CREATE TABLE IF NOT EXISTS card_payments(id INTEGER PRIMARY KEY, agent INTEGER NOT NULL, client INTEGER NOT NULL, currency TEXT NOT NULL DEFAULT 'UZS', amount_uzs INTEGER NOT NULL DEFAULT 0, amount_usd INTEGER NOT NULL CHECK(amount_usd>0), rate_uzs_per_usd INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','confirmed','rejected')), source INTEGER NOT NULL UNIQUE, ts INTEGER NOT NULL, cashier INTEGER, decided_ts INTEGER, event_id INTEGER);
CREATE TABLE IF NOT EXISTS agent_funds(id INTEGER PRIMARY KEY, agent INTEGER NOT NULL, actor INTEGER NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('topup','expense')), amount_usd INTEGER NOT NULL CHECK(amount_usd>0), amount_uzs INTEGER NOT NULL DEFAULT 0, rate_uzs_per_usd INTEGER NOT NULL DEFAULT 0, category TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', source INTEGER NOT NULL UNIQUE, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_agent_funds_agent_ts ON agent_funds(agent,ts);
CREATE INDEX IF NOT EXISTS idx_cashier_expenses_ts ON cashier_expenses(ts);
CREATE INDEX IF NOT EXISTS idx_cashier_incomes_ts ON cashier_incomes(ts);
CREATE TABLE IF NOT EXISTS return_allocations(return_event INTEGER NOT NULL, delivery_event INTEGER NOT NULL, qty INTEGER NOT NULL, amount_usd INTEGER NOT NULL, PRIMARY KEY(return_event,delivery_event));
CREATE TABLE IF NOT EXISTS failed_updates(update_id INTEGER PRIMARY KEY, actor INTEGER, failure_type TEXT, attempts INTEGER DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending', last_error TEXT, created_ts INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS role_audit(id INTEGER PRIMARY KEY, actor INTEGER NOT NULL, old_id INTEGER, new_id INTEGER, action TEXT NOT NULL, ts INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS client_edits(id INTEGER PRIMARY KEY, client INTEGER NOT NULL, actor INTEGER NOT NULL, field TEXT NOT NULL, old_value TEXT, new_value TEXT, ts INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS client_visits(id INTEGER PRIMARY KEY, client INTEGER NOT NULL, actor INTEGER NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL, followup TEXT, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_client_visits_client_id ON client_visits(client,id);
CREATE TABLE IF NOT EXISTS collection_tasks(id INTEGER PRIMARY KEY, client INTEGER NOT NULL, agent INTEGER NOT NULL, cashier INTEGER NOT NULL, debt_usd INTEGER NOT NULL CHECK(debt_usd>0), note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','done','cancelled')), created_ts INTEGER NOT NULL, completed_ts INTEGER);
CREATE INDEX IF NOT EXISTS idx_collection_tasks_agent_status ON collection_tasks(agent,status,created_ts);
CREATE INDEX IF NOT EXISTS idx_collection_tasks_client_status ON collection_tasks(client,status,created_ts);
CREATE TABLE IF NOT EXISTS delivery_edits(id INTEGER PRIMARY KEY, delivery_event INTEGER NOT NULL, client INTEGER NOT NULL, actor INTEGER NOT NULL, old_pack INTEGER NOT NULL, new_pack INTEGER NOT NULL, old_qty INTEGER NOT NULL, new_qty INTEGER NOT NULL, old_amount_usd INTEGER NOT NULL, new_amount_usd INTEGER NOT NULL, ts INTEGER NOT NULL);
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
CREATE TABLE IF NOT EXISTS user_profiles(user_id BIGINT PRIMARY KEY, photo TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', updated_ts BIGINT NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS photo_thumbs(file_id TEXT PRIMARY KEY, data BYTEA NOT NULL, ts BIGINT NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS clients(id BIGSERIAL PRIMARY KEY, agent BIGINT NOT NULL, name TEXT, phone TEXT UNIQUE, address TEXT, region TEXT NOT NULL DEFAULT '', lat DOUBLE PRECISION, lon DOUBLE PRECISION, photo TEXT, shop_name TEXT, comment TEXT DEFAULT '', payment_due TEXT, created_ts BIGINT, map_only INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS deleted_clients(id BIGINT PRIMARY KEY, agent BIGINT NOT NULL, name TEXT, phone TEXT, address TEXT, region TEXT NOT NULL DEFAULT '', lat DOUBLE PRECISION, lon DOUBLE PRECISION, photo TEXT, shop_name TEXT, comment TEXT DEFAULT '', payment_due TEXT, created_ts BIGINT, map_only INTEGER NOT NULL DEFAULT 0, deleted_by BIGINT NOT NULL, deleted_ts BIGINT NOT NULL, debt_usd BIGINT NOT NULL DEFAULT 0, event_count BIGINT NOT NULL DEFAULT 0, visit_count BIGINT NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions(agent BIGINT PRIMARY KEY, data TEXT);
CREATE TABLE IF NOT EXISTS client_blacklist_log(id BIGSERIAL PRIMARY KEY, client BIGINT NOT NULL, actor BIGINT NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', ts BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS shifts(id BIGSERIAL PRIMARY KEY, agent BIGINT, start BIGINT, end BIGINT, live_id BIGINT);
CREATE UNIQUE INDEX IF NOT EXISTS one_shift ON shifts(agent) WHERE end IS NULL;
CREATE TABLE IF NOT EXISTS points(id BIGSERIAL PRIMARY KEY, shift BIGINT, ts BIGINT, lat DOUBLE PRECISION, lon DOUBLE PRECISION, accuracy DOUBLE PRECISION, UNIQUE(shift,ts));
CREATE TABLE IF NOT EXISTS events(id BIGSERIAL PRIMARY KEY, actor BIGINT, agent BIGINT, client BIGINT, kind TEXT, pack INTEGER DEFAULT 0, qty INTEGER DEFAULT 0, amount BIGINT DEFAULT 0, amount_usd BIGINT DEFAULT 0, note TEXT DEFAULT '', ts BIGINT, source BIGINT UNIQUE);
CREATE TABLE IF NOT EXISTS handovers(id BIGSERIAL PRIMARY KEY, agent BIGINT, amount BIGINT, amount_usd BIGINT DEFAULT 0, status TEXT DEFAULT 'pending', cashier BIGINT, source BIGINT UNIQUE, ts BIGINT, accepted_ts BIGINT);
CREATE TABLE IF NOT EXISTS cashier_expenses(id BIGSERIAL PRIMARY KEY, cashier BIGINT NOT NULL, amount_usd BIGINT NOT NULL CHECK(amount_usd>0), category TEXT NOT NULL, recipient TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', source BIGINT NOT NULL UNIQUE, ts BIGINT NOT NULL, currency TEXT NOT NULL DEFAULT 'USD', amount_uzs BIGINT NOT NULL DEFAULT 0, rate_uzs_per_usd BIGINT NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS cashier_incomes(id BIGSERIAL PRIMARY KEY, cashier BIGINT NOT NULL, amount_usd BIGINT NOT NULL CHECK(amount_usd>0), category TEXT NOT NULL, source_name TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', source BIGINT NOT NULL UNIQUE, ts BIGINT NOT NULL, currency TEXT NOT NULL DEFAULT 'USD', amount_uzs BIGINT NOT NULL DEFAULT 0, rate_uzs_per_usd BIGINT NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS cashier_fx_rates(id BIGSERIAL PRIMARY KEY, cashier BIGINT NOT NULL, rate_uzs_per_usd BIGINT NOT NULL, source BIGINT NOT NULL UNIQUE, ts BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS orders(id BIGSERIAL PRIMARY KEY, agent BIGINT NOT NULL, client BIGINT NOT NULL, status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new','preparing','loaded','delivered','rejected')), note TEXT NOT NULL DEFAULT '', admin_note TEXT NOT NULL DEFAULT '', source BIGINT NOT NULL UNIQUE, ts BIGINT NOT NULL, updated_ts BIGINT NOT NULL, admin BIGINT);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status,ts);
CREATE INDEX IF NOT EXISTS idx_orders_client ON orders(client,ts);
CREATE TABLE IF NOT EXISTS order_items(id BIGSERIAL PRIMARY KEY, order_id BIGINT NOT NULL, pack BIGINT, custom_name TEXT NOT NULL DEFAULT '', qty BIGINT NOT NULL CHECK(qty>0));
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE TABLE IF NOT EXISTS visit_stock(id BIGSERIAL PRIMARY KEY, visit BIGINT NOT NULL, client BIGINT NOT NULL, pack BIGINT NOT NULL, counted BIGINT NOT NULL CHECK(counted>=0), expected BIGINT NOT NULL DEFAULT 0, ts BIGINT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_visit_stock_visit ON visit_stock(visit);
CREATE TABLE IF NOT EXISTS card_payments(id BIGSERIAL PRIMARY KEY, agent BIGINT NOT NULL, client BIGINT NOT NULL, currency TEXT NOT NULL DEFAULT 'UZS', amount_uzs BIGINT NOT NULL DEFAULT 0, amount_usd BIGINT NOT NULL CHECK(amount_usd>0), rate_uzs_per_usd BIGINT NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','confirmed','rejected')), source BIGINT NOT NULL UNIQUE, ts BIGINT NOT NULL, cashier BIGINT, decided_ts BIGINT, event_id BIGINT);
CREATE TABLE IF NOT EXISTS agent_funds(id BIGSERIAL PRIMARY KEY, agent BIGINT NOT NULL, actor BIGINT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('topup','expense')), amount_usd BIGINT NOT NULL CHECK(amount_usd>0), amount_uzs BIGINT NOT NULL DEFAULT 0, rate_uzs_per_usd BIGINT NOT NULL DEFAULT 0, category TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', source BIGINT NOT NULL UNIQUE, ts BIGINT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_agent_funds_agent_ts ON agent_funds(agent,ts);
CREATE INDEX IF NOT EXISTS idx_cashier_expenses_ts ON cashier_expenses(ts);
CREATE INDEX IF NOT EXISTS idx_cashier_incomes_ts ON cashier_incomes(ts);
CREATE TABLE IF NOT EXISTS return_allocations(return_event BIGINT NOT NULL, delivery_event BIGINT NOT NULL, qty BIGINT NOT NULL, amount_usd BIGINT NOT NULL, PRIMARY KEY(return_event,delivery_event));
CREATE TABLE IF NOT EXISTS failed_updates(update_id BIGINT PRIMARY KEY, actor BIGINT, failure_type TEXT, attempts INTEGER DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending', last_error TEXT, created_ts BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS role_audit(id BIGSERIAL PRIMARY KEY, actor BIGINT NOT NULL, old_id BIGINT, new_id BIGINT, action TEXT NOT NULL, ts BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS client_edits(id BIGSERIAL PRIMARY KEY, client BIGINT NOT NULL, actor BIGINT NOT NULL, field TEXT NOT NULL, old_value TEXT, new_value TEXT, ts BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS client_visits(id BIGSERIAL PRIMARY KEY, client BIGINT NOT NULL, actor BIGINT NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL, followup TEXT, ts BIGINT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_client_visits_client_id ON client_visits(client,id);
CREATE TABLE IF NOT EXISTS collection_tasks(id BIGSERIAL PRIMARY KEY, client BIGINT NOT NULL, agent BIGINT NOT NULL, cashier BIGINT NOT NULL, debt_usd BIGINT NOT NULL CHECK(debt_usd>0), note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','done','cancelled')), created_ts BIGINT NOT NULL, completed_ts BIGINT);
CREATE INDEX IF NOT EXISTS idx_collection_tasks_agent_status ON collection_tasks(agent,status,created_ts);
CREATE INDEX IF NOT EXISTS idx_collection_tasks_client_status ON collection_tasks(client,status,created_ts);
CREATE TABLE IF NOT EXISTS delivery_edits(id BIGSERIAL PRIMARY KEY, delivery_event BIGINT NOT NULL, client BIGINT NOT NULL, actor BIGINT NOT NULL, old_pack INTEGER NOT NULL, new_pack INTEGER NOT NULL, old_qty BIGINT NOT NULL, new_qty BIGINT NOT NULL, old_amount_usd BIGINT NOT NULL, new_amount_usd BIGINT NOT NULL, ts BIGINT NOT NULL);
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
            refresh_catalog(db)
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
        db.execute('ALTER TABLE clients ADD COLUMN IF NOT EXISTS map_only INTEGER NOT NULL DEFAULT 0')
        db.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS region TEXT NOT NULL DEFAULT ''")
        db.execute('ALTER TABLE clients ADD COLUMN IF NOT EXISTS blacklisted INTEGER NOT NULL DEFAULT 0')
        db.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS blacklist_reason TEXT NOT NULL DEFAULT ''")
        db.execute('ALTER TABLE clients ADD COLUMN IF NOT EXISTS blacklist_ts BIGINT')
        db.execute('ALTER TABLE clients ADD COLUMN IF NOT EXISTS blacklist_by BIGINT')
        db.execute('ALTER TABLE events ADD COLUMN IF NOT EXISTS amount_usd BIGINT DEFAULT 0')
        db.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS pay_method TEXT NOT NULL DEFAULT ''")
        db.execute('ALTER TABLE events ADD COLUMN IF NOT EXISTS paid_uzs BIGINT NOT NULL DEFAULT 0')
        db.execute('ALTER TABLE events ADD COLUMN IF NOT EXISTS fx_rate BIGINT NOT NULL DEFAULT 0')
        for column,definition in (('checkin_ts','BIGINT NOT NULL DEFAULT 0'),('lat','DOUBLE PRECISION'),('lon','DOUBLE PRECISION'),
                                  ('distance_m','BIGINT'),('photo',"TEXT NOT NULL DEFAULT ''")):
            db.execute(f'ALTER TABLE client_visits ADD COLUMN IF NOT EXISTS {column} {definition}')
        db.execute('ALTER TABLE handovers ADD COLUMN IF NOT EXISTS amount_usd BIGINT DEFAULT 0')
        for column,definition in (('weight_kg','DOUBLE PRECISION NOT NULL DEFAULT 0'),('block_units','BIGINT NOT NULL DEFAULT 0'),
                                  ('active','INTEGER NOT NULL DEFAULT 1'),('custom','INTEGER NOT NULL DEFAULT 0'),('created_ts','BIGINT NOT NULL DEFAULT 0')):
            db.execute(f'ALTER TABLE products ADD COLUMN IF NOT EXISTS {column} {definition}')
        db.execute("ALTER TABLE cashier_expenses ADD COLUMN IF NOT EXISTS currency TEXT NOT NULL DEFAULT 'USD'")
        db.execute('ALTER TABLE cashier_expenses ADD COLUMN IF NOT EXISTS amount_uzs BIGINT NOT NULL DEFAULT 0')
        db.execute('ALTER TABLE cashier_expenses ADD COLUMN IF NOT EXISTS rate_uzs_per_usd BIGINT NOT NULL DEFAULT 0')
        db.execute("ALTER TABLE cashier_expenses ADD COLUMN IF NOT EXISTS pay_from TEXT NOT NULL DEFAULT 'cash'")
        db.execute("ALTER TABLE card_payments ADD COLUMN IF NOT EXISTS photo TEXT NOT NULL DEFAULT ''")
        db.execute('ALTER TABLE agent_funds ADD COLUMN IF NOT EXISTS amount_uzs BIGINT NOT NULL DEFAULT 0')
        db.execute('ALTER TABLE agent_funds ADD COLUMN IF NOT EXISTS rate_uzs_per_usd BIGINT NOT NULL DEFAULT 0')
        for pack,item in PRODUCT_CATALOG.items():
            db.execute('INSERT INTO products(pack,name,price) VALUES(?,?,?) ON CONFLICT(pack) DO UPDATE SET name=excluded.name',
                       (pack,item['name'],PRODUCT_DEFAULT_PRICES.get(pack,0)))
        refresh_catalog(db)
        _promote_8068123777_to_admin_once(db)
        _backfill_unbilled_deliveries(db)
        _backfill_existing_client_regions_once(db)
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
    if 'map_only' not in client_cols:
        db.execute('ALTER TABLE clients ADD COLUMN map_only INTEGER NOT NULL DEFAULT 0')
    if 'region' not in client_cols:
        db.execute("ALTER TABLE clients ADD COLUMN region TEXT NOT NULL DEFAULT ''")
    for column,definition in (('blacklisted','INTEGER NOT NULL DEFAULT 0'),('blacklist_reason',"TEXT NOT NULL DEFAULT ''"),
                              ('blacklist_ts','INTEGER'),('blacklist_by','INTEGER')):
        if column not in client_cols:db.execute(f'ALTER TABLE clients ADD COLUMN {column} {definition}')
    if 'amount_usd' not in {r[1] for r in db.execute('PRAGMA table_info(events)')}:
        db.execute('ALTER TABLE events ADD COLUMN amount_usd INTEGER DEFAULT 0')
    event_cols={r[1] for r in db.execute('PRAGMA table_info(events)')}
    for column,definition in (('pay_method',"TEXT NOT NULL DEFAULT ''"),('paid_uzs','INTEGER NOT NULL DEFAULT 0'),('fx_rate','INTEGER NOT NULL DEFAULT 0')):
        if column not in event_cols:db.execute(f'ALTER TABLE events ADD COLUMN {column} {definition}')
    visit_cols={r[1] for r in db.execute('PRAGMA table_info(client_visits)')}
    for column,definition in (('checkin_ts','INTEGER NOT NULL DEFAULT 0'),('lat','REAL'),('lon','REAL'),
                              ('distance_m','INTEGER'),('photo',"TEXT NOT NULL DEFAULT ''")):
        if column not in visit_cols:db.execute(f'ALTER TABLE client_visits ADD COLUMN {column} {definition}')
    if 'amount_usd' not in {r[1] for r in db.execute('PRAGMA table_info(handovers)')}:
        db.execute('ALTER TABLE handovers ADD COLUMN amount_usd INTEGER DEFAULT 0')
    expense_cols={r[1] for r in db.execute('PRAGMA table_info(cashier_expenses)')}
    for column,definition in (('currency',"TEXT NOT NULL DEFAULT 'USD'"),('amount_uzs','INTEGER NOT NULL DEFAULT 0'),('rate_uzs_per_usd','INTEGER NOT NULL DEFAULT 0'),('pay_from',"TEXT NOT NULL DEFAULT 'cash'")):
        if column not in expense_cols:db.execute(f'ALTER TABLE cashier_expenses ADD COLUMN {column} {definition}')
    if 'photo' not in {r[1] for r in db.execute('PRAGMA table_info(card_payments)')}:
        db.execute("ALTER TABLE card_payments ADD COLUMN photo TEXT NOT NULL DEFAULT ''")
    fund_cols={r[1] for r in db.execute('PRAGMA table_info(agent_funds)')}
    for column,definition in (('amount_uzs','INTEGER NOT NULL DEFAULT 0'),('rate_uzs_per_usd','INTEGER NOT NULL DEFAULT 0')):
        if column not in fund_cols:db.execute(f'ALTER TABLE agent_funds ADD COLUMN {column} {definition}')
    product_cols={r[1] for r in db.execute('PRAGMA table_info(products)')}
    for column,definition in (('weight_kg','REAL NOT NULL DEFAULT 0'),('block_units','INTEGER NOT NULL DEFAULT 0'),
                              ('active','INTEGER NOT NULL DEFAULT 1'),('custom','INTEGER NOT NULL DEFAULT 0'),('created_ts','INTEGER NOT NULL DEFAULT 0')):
        if column not in product_cols:db.execute(f'ALTER TABLE products ADD COLUMN {column} {definition}')
    for pack,item in PRODUCT_CATALOG.items():
        db.execute('INSERT INTO products(pack,name,price) VALUES(?,?,?) ON CONFLICT(pack) DO UPDATE SET name=excluded.name',
                   (pack,item['name'],PRODUCT_DEFAULT_PRICES.get(pack,0)))
    refresh_catalog(db)
    _promote_8068123777_to_admin_once(db)
    _backfill_unbilled_deliveries(db)
    _backfill_existing_client_regions_once(db)
    db.commit()
    db.execute('PRAGMA journal_mode=WAL')
    return db

def _backfill_existing_client_regions_once(db):
    """Classify the 91 legacy clients from their written addresses, once.

    Only the original IDs are eligible. Existing manual region edits are kept;
    this never classifies new customers or reassigns one after a later edit.
    """
    key='client_regions_from_address_20260928'
    if db.execute('SELECT 1 FROM meta WHERE key=?',(key,)).fetchone():return
    patterns=(('Bag‘dod',r'ба[ғг]дод'),('Uchko‘prik',r'учк[ўуо]прик'),
              ('Rishton',r'риштон'),('Buvayda',r'бувайда'),
              ('Furqat',r'фур[қк]ат'),('Beshariq',r'бешари[қк]'),
              ('O‘zbekiston',r'ўзбекистон\s+тумани'))
    updated=0
    for row in db.execute("SELECT id,address,region FROM clients WHERE id<=91 AND TRIM(COALESCE(region,''))='' ORDER BY id").fetchall():
        address=(row['address'] or '').strip()
        matches=[name for name,pattern in patterns if re.search(pattern,address,re.I)]
        if 'Яйпан' in address and 'O‘zbekiston' in matches:
            matches=['Yaypan']
        if not matches and address=='Чиркай':matches=['Furqat']
        if not matches and address=='Қушқўноқ':matches=['O‘zbekiston']
        if len(matches)!=1:continue
        db.execute("UPDATE clients SET region=? WHERE id=? AND TRIM(COALESCE(region,''))='' AND address=?",
                   (matches[0],row['id'],row['address']))
        updated+=1
    db.execute('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO NOTHING',(key,str(updated)))

def _promote_8068123777_to_admin_once(db):
    """One-time requested role migration for Telegram user 8068123777.

    The user was verified in production as an agent with no open shift,
    pending handover, clients, or ledger events before this migration was added.
    The secondary_admin meta flag matches normal admin promotion behavior so
    the role is not accidentally reverted by stale agent state.
    """
    uid=8068123777
    key='role_migration:8068123777:agent_to_admin:20260925'
    if db.execute('SELECT 1 FROM meta WHERE key=?',(key,)).fetchone():return
    row=db.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
    if not row:return
    if row['role']=='agent':
        if db.execute('SELECT 1 FROM shifts WHERE agent=? AND end IS NULL',(uid,)).fetchone():
            raise RuntimeError('8068123777 has an open shift; admin migration stopped.')
        if db.execute("SELECT 1 FROM handovers WHERE agent=? AND status='pending'",(uid,)).fetchone():
            raise RuntimeError('8068123777 has a pending handover; admin migration stopped.')
        db.execute("UPDATE users SET role='admin' WHERE id=?",(uid,))
        db.execute('DELETE FROM sessions WHERE agent=?',(uid,))
    elif row['role']!='admin':
        raise RuntimeError('8068123777 has an unexpected role; admin migration stopped.')
    db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (f'secondary_admin:{uid}','1'))
    db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO NOTHING",
               (key,'requested_agent_to_admin'))

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
    """US dollars physically held by the agent.

    Only cash payments taken in USD count. Payments taken in so'm (paid_uzs>0)
    sit in the agent's so'm cash, and card payments go straight to the bank.
    Only USD handovers (amount=0) leave this wallet.
    """
    got=db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM events WHERE agent=? AND kind='payment'
        AND COALESCE(paid_uzs,0)=0 AND COALESCE(pay_method,'')<>'card'""",(agent,)).fetchone()[0]
    paid=db.execute("SELECT COALESCE(SUM(amount_usd),0) FROM handovers WHERE agent=? AND status='accepted' AND COALESCE(amount,0)=0",(agent,)).fetchone()[0]
    return int(got or 0)-int(paid or 0)

def agent_uzs_value_usd(db,agent,include_pending=True):
    """USD value (at the agreed client rates) of the so'm still held by the agent."""
    got=db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM events WHERE agent=? AND kind='payment'
        AND COALESCE(paid_uzs,0)>0 AND COALESCE(pay_method,'')='cash'""",(agent,)).fetchone()[0]
    statuses="('accepted','pending')" if include_pending else "('accepted')"
    handed=db.execute(f"SELECT COALESCE(SUM(amount_usd),0) FROM handovers WHERE agent=? AND COALESCE(amount,0)>0 AND status IN {statuses}",(agent,)).fetchone()[0]
    return int(got or 0)-int(handed or 0)

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


def add_agent(db,actor,uid,name):
    """Create a new active agent without reusing any existing staff identity."""
    administrator=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not administrator or administrator[0]!='admin':raise ValueError('Фақат админ агент қўшиши мумкин.')
    if not isinstance(uid,int) or uid<=0:raise ValueError('Telegram ID нотўғри.')
    if not isinstance(name,str) or not name.strip() or len(name.strip())>120:
        raise ValueError('Агент исмини киритинг.')
    if db.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone():
        raise ValueError('Бу Telegram ID аввал рўйхатдан ўтган. Бошқа ID киритинг.')
    db.execute('INSERT INTO users(id,role,name) VALUES(?,?,?)',(uid,'agent',name.strip()))
    db.execute('INSERT INTO role_audit(actor,old_id,new_id,action,ts) VALUES(?,?,?,?,?)',
               (actor,None,uid,'agent_created',int(time.time())))
    return uid


def _require_admin(db,actor):
    row=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not row or row[0]!='admin':raise ValueError('Фақат раҳбар (админ).')


def _staff_name(name,label='Исм'):
    if not isinstance(name,str) or not name.strip() or len(name.strip())>120:raise ValueError(f'{label}ни киритинг (1–120 белги).')
    return name.strip()


def _telegram_id(uid):
    try:uid=int(str(uid).strip())
    except (TypeError,ValueError):raise ValueError('Telegram ID нотўғри.')
    if not 1<=uid<=10**13:raise ValueError('Telegram ID нотўғри.')
    return uid


def add_cashier(db,actor,uid,name):
    """New cashier (or re-open a previously disabled cashier ID)."""
    _require_admin(db,actor);uid=_telegram_id(uid);name=_staff_name(name,'Кассир исми')
    row=db.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
    if row and row[0]!='cashier_disabled':raise ValueError('Бу Telegram ID аввал рўйхатдан ўтган. Бошқа ID киритинг.')
    if row:db.execute("UPDATE users SET role='cashier',name=? WHERE id=?",(name,uid))
    else:db.execute("INSERT INTO users(id,role,name) VALUES(?,'cashier',?)",(uid,name))
    db.execute('INSERT INTO role_audit(actor,old_id,new_id,action,ts) VALUES(?,?,?,?,?)',
               (actor,None,uid,'cashier_created',int(time.time())))
    return uid


def rename_cashier(db,actor,uid,name):
    _require_admin(db,actor);name=_staff_name(name,'Янги исм')
    row=db.execute("SELECT name FROM users WHERE id=? AND role='cashier'",(_telegram_id(uid),)).fetchone()
    if not row:raise ValueError('Фаол кассир топилмади.')
    if row[0]==name:raise ValueError('Исм ўзгармаган.')
    db.execute('UPDATE users SET name=? WHERE id=?',(name,int(uid)))
    db.execute('INSERT INTO role_audit(actor,old_id,new_id,action,ts) VALUES(?,?,?,?,?)',
               (actor,int(uid),int(uid),'cashier_renamed',int(time.time())))
    return name


def deactivate_cashier(db,actor,uid):
    """Close cashier access; every accepted handover and expense keeps the old name."""
    _require_admin(db,actor);uid=_telegram_id(uid)
    if not db.execute("SELECT 1 FROM users WHERE id=? AND role='cashier'",(uid,)).fetchone():
        raise ValueError('Фаол кассир топилмади.')
    if db.execute("SELECT COUNT(*) FROM users WHERE role='cashier'").fetchone()[0]<=1:
        raise ValueError('Охирги кассирни ёпиб бўлмайди. Аввал янги кассир қўшинг.')
    db.execute("UPDATE users SET role='cashier_disabled' WHERE id=?",(uid,))
    db.execute('INSERT INTO role_audit(actor,old_id,new_id,action,ts) VALUES(?,?,?,?,?)',
               (actor,uid,None,'cashier_deactivated',int(time.time())))


def activate_cashier(db,actor,uid):
    _require_admin(db,actor);uid=_telegram_id(uid)
    if not db.execute("SELECT 1 FROM users WHERE id=? AND role='cashier_disabled'",(uid,)).fetchone():
        raise ValueError('Ёпилган кассир топилмади.')
    db.execute("UPDATE users SET role='cashier' WHERE id=?",(uid,))
    db.execute('INSERT INTO role_audit(actor,old_id,new_id,action,ts) VALUES(?,?,?,?,?)',
               (actor,None,uid,'cashier_activated',int(time.time())))


def transfer_cashier_account(db,actor,old_id,new_id):
    """Give the cashier role to a new Telegram account; the old account is closed, history stays."""
    _require_admin(db,actor);old_id=_telegram_id(old_id);new_id=_telegram_id(new_id)
    if old_id==new_id:raise ValueError('Янги ID эскисидан фарқ қилсин.')
    row=db.execute("SELECT name FROM users WHERE id=? AND role='cashier'",(old_id,)).fetchone()
    if not row:raise ValueError('Фаол кассир топилмади.')
    other=db.execute('SELECT role FROM users WHERE id=?',(new_id,)).fetchone()
    if other and other[0]!='cashier_disabled':raise ValueError('Янги Telegram ID аввал рўйхатдан ўтган.')
    if other:db.execute("UPDATE users SET role='cashier',name=? WHERE id=?",(row[0],new_id))
    else:db.execute("INSERT INTO users(id,role,name) VALUES(?,'cashier',?)",(new_id,row[0]))
    db.execute("UPDATE users SET role='cashier_disabled' WHERE id=?",(old_id,))
    db.execute('INSERT INTO role_audit(actor,old_id,new_id,action,ts) VALUES(?,?,?,?,?)',
               (actor,old_id,new_id,'cashier_transferred',int(time.time())))
    return new_id


def rename_agent(db,actor,agent_id,name):
    """Rename one active agent and record the administrative action."""
    administrator=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not administrator or administrator[0]!='admin':raise ValueError('Фақат админ.')
    if not isinstance(name,str) or not name.strip() or len(name.strip())>120:
        raise ValueError('Агентнинг янги исмини киритинг.')
    row=db.execute("SELECT name,role FROM users WHERE id=?",(agent_id,)).fetchone()
    if not row or row['role']!='agent':raise ValueError('Фаол агент топилмади.')
    new_name=name.strip()
    if row['name']==new_name:raise ValueError('Агент исми ўзгармаган.')
    if isinstance(db,PostgresDB):
        row=db.execute('SELECT name,role FROM users WHERE id=? FOR UPDATE',(agent_id,)).fetchone()
    db.execute('UPDATE users SET name=? WHERE id=?',(new_name,agent_id))
    db.execute('INSERT INTO role_audit(actor,old_id,new_id,action,ts) VALUES(?,?,?,?,?)',
               (actor,agent_id,agent_id,'agent_renamed',int(time.time())))
    return new_name


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

def delivery_correction_plan(db,actor,event_id,new_pack,new_qty):
    """Validate a correction to one USD delivery without rewriting downstream sales/returns."""
    identity=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    row=db.execute("""SELECT e.*,c.agent AS owner FROM events e
        JOIN clients c ON c.id=e.client WHERE e.id=? AND e.kind='delivery'""",(event_id,)).fetchone()
    if not identity or not row or not (identity[0]=='admin' or
        (identity[0]=='agent' and int(row['owner'])==actor)):
        raise ValueError('Бу товар топширишини ўзгартиришга рухсат йўқ.')
    if new_pack not in PRODUCTS or not isinstance(new_qty,int) or new_qty<=0:
        raise ValueError('Товар ёки миқдор нотўғри.')
    agent=int(row['agent']);client=int(row['client'])
    if isinstance(db,PostgresDB):
        lock_agent(db,agent)
        row=db.execute("""SELECT e.*,c.agent AS owner FROM events e
            JOIN clients c ON c.id=e.client WHERE e.id=? AND e.kind='delivery' FOR UPDATE""",
            (event_id,)).fetchone()
    old_pack=int(row['pack']);old_qty=int(row['qty']);old_amount=int(row['amount_usd'] or 0)
    if old_qty<=0 or old_amount<=0 or old_amount%old_qty:
        raise ValueError('Бу эски топширишда USD нархи аниқ сақланмаган. Уни автомат тузатиб бўлмайди.')
    if new_pack==old_pack and new_qty==old_qty:
        raise ValueError('Товар ва миқдор ўзгармаган.')
    # Once a sale/return happened after this delivery, rewriting the earlier lot
    # can change historical FIFO pricing. Use return/new delivery instead.
    packs={old_pack,new_pack}
    placeholders=','.join('?' for _ in packs)
    downstream=db.execute(f"""SELECT 1 FROM events
        WHERE client=? AND id>? AND kind IN ('sold','return') AND pack IN ({placeholders})
        LIMIT 1""",(client,event_id,*sorted(packs))).fetchone()
    if downstream:
        raise ValueError('Бу топширишдан кейин сотув ёки қайтариш бор. Тарихни бузмаслик учун бу ёзувни ўзгартириб бўлмайди; қайтариш ёки янги топшириш қилинг.')
    if new_pack==old_pack:
        unit=old_amount//old_qty
        delta=new_qty-old_qty
        if delta>0 and agent_stock(db,agent,old_pack)<delta:
            raise ValueError('Агентда қўшимча миқдор учун товар етарли эмас.')
    else:
        unit=product_price(db,new_pack)
        if unit<=0:raise ValueError('Янги товар учун USD нарх киритилмаган.')
        if agent_stock(db,agent,new_pack)<new_qty:
            raise ValueError('Агентда танланган янги товардан етарли қолдиқ йўқ.')
    new_amount=new_qty*unit
    debt_after=client_debt_usd(db,client)-old_amount+new_amount
    if debt_after<0:
        raise ValueError('Тузатишдан кейин мижоз қарзи манфий бўлиб қолади. Аввал тўловни текширинг.')
    return {'event':int(row['id']),'agent':agent,'client':client,
            'old_pack':old_pack,'new_pack':new_pack,'old_qty':old_qty,'new_qty':new_qty,
            'old_amount_usd':old_amount,'new_amount_usd':new_amount,'unit_price':unit,
            'debt_after':debt_after,'ts':int(row['ts'] or 0)}

def correct_delivery(db,actor,event_id,new_pack,new_qty):
    plan=delivery_correction_plan(db,actor,event_id,new_pack,new_qty)
    db.execute("""UPDATE events SET pack=?,qty=?,amount_usd=?,
        note=COALESCE(note,'') || ? WHERE id=? AND kind='delivery'""",
        (plan['new_pack'],plan['new_qty'],plan['new_amount_usd'],
         f" | Тузатилди {int(time.time())}: {plan['old_pack']}кг/{plan['old_qty']} -> {plan['new_pack']}кг/{plan['new_qty']}",
         event_id))
    db.execute("""INSERT INTO delivery_edits(delivery_event,client,actor,old_pack,new_pack,
        old_qty,new_qty,old_amount_usd,new_amount_usd,ts) VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (event_id,plan['client'],actor,plan['old_pack'],plan['new_pack'],plan['old_qty'],
         plan['new_qty'],plan['old_amount_usd'],plan['new_amount_usd'],int(time.time())))
    return plan

CLIENT_EDIT_FIELDS=('name','shop_name','phone','address','region','comment','payment_due','photo','lat','lon')

def photo_version(file_id):
    """Short stable tag of a Telegram file_id for cache-busting photo links."""
    if not file_id:return ''
    import hashlib
    return hashlib.sha1(str(file_id).encode()).hexdigest()[:10]


def edit_client(db,actor,client_id,values):
    """Edit the chosen customer profile only; product/receivable history is immutable."""
    identity=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    current=db.execute('SELECT * FROM clients WHERE id=?',(client_id,)).fetchone()
    if not identity or not current or identity[0] not in ('admin','agent'):
        raise ValueError('Бу мижоз маълумотини ўзгартиришга рухсат йўқ.')
    if identity[0]!='admin' and int(current['blacklisted'] or 0):raise ValueError(BLACKLIST_MSG)
    if not values or any(field not in CLIENT_EDIT_FIELDS for field in values):
        raise ValueError('Таҳрирланадиган маълумот нотўғри.')
    if isinstance(db,PostgresDB):
        current=db.execute('SELECT * FROM clients WHERE id=? FOR UPDATE',(client_id,)).fetchone()
    for field,new in values.items():
        before=current[field]
        if before==new:continue
        if field=='phone' and db.execute('SELECT 1 FROM clients WHERE phone=? AND id<>?',(new,client_id)).fetchone():
            raise ValueError('Бу телефон бошқа мижозга бириктирилган.')
        db.execute(f'UPDATE clients SET {field}=? WHERE id=?',(new,client_id))
        db.execute('INSERT INTO client_edits(client,actor,field,old_value,new_value,ts) VALUES(?,?,?,?,?,?)',
                   (client_id,actor,field,str(before) if before is not None else None,
                    str(new) if new is not None else None,int(time.time())))
    return True

def deactivate_agent(db,actor,agent_id):
    """Disable login but never delete customer, stock, cash, GPS or invoice history."""
    admin=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not admin or admin[0]!='admin':raise ValueError('Фақат админ агент ҳисобини ёпиши мумкин.')
    agent=db.execute('SELECT role FROM users WHERE id=?',(agent_id,)).fetchone()
    if not agent or agent[0]!='agent':raise ValueError('Фаол агент топилмади.')
    if isinstance(db,PostgresDB):db.execute('SELECT id FROM users WHERE id=? FOR UPDATE',(agent_id,)).fetchone()
    if db.execute('SELECT 1 FROM shifts WHERE agent=? AND end IS NULL',(agent_id,)).fetchone():
        raise ValueError('Аввал агентнинг иш сменасини тугатинг.')
    db.execute("UPDATE users SET role='disabled' WHERE id=?",(agent_id,))
    db.execute('DELETE FROM sessions WHERE agent=?',(agent_id,))
    db.execute('INSERT INTO role_audit(actor,old_id,new_id,action,ts) VALUES(?,?,?,?,?)',
               (actor,agent_id,None,'agent_deactivated',int(time.time())))

def add_or_promote_admin(db,actor,uid,name):
    """Provision an admin without overwriting a registered user's business ledger.

    The bot checks ADMIN_IDS at the entry point; this helper also checks the
    actor's persisted admin role. Existing users can be promoted only after
    their agent obligations have been settled.
    """
    administrator=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not administrator or administrator[0]!='admin':
        raise ValueError('Фақат админ.')
    if not isinstance(uid,int) or uid<=0 or uid==actor:
        raise ValueError('Янги админ Telegram ID рақами нотўғри.')
    if not isinstance(name,str) or not name.strip() or len(name)>120:
        raise ValueError('Янги админ исмини киритинг.')
    row=db.execute('SELECT id,role FROM users WHERE id=?',(uid,)).fetchone()
    if isinstance(db,PostgresDB) and row:
        row=db.execute('SELECT id,role FROM users WHERE id=? FOR UPDATE',(uid,)).fetchone()
    if not row:
        db.execute('INSERT INTO users(id,role,name) VALUES(?,?,?)',(uid,'admin',name.strip()))
        db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                   (f'secondary_admin:{uid}','1'))
        db.execute('INSERT INTO role_audit(actor,old_id,new_id,action,ts) VALUES(?,?,?,?,?)',
                   (actor,None,uid,'admin_created',int(time.time())))
        return 'created'
    if row['role']=='admin':
        raise ValueError('Бу Telegram ID аллақачон админ.')
    if row['role'] not in ('agent','disabled','cashier'):
        raise ValueError('Бу аккаунт ролини админга ўзгартириш мумкин эмас.')
    if db.execute('SELECT 1 FROM shifts WHERE agent=? AND end IS NULL',(uid,)).fetchone():
        raise ValueError('Аввал ходимнинг очиқ сменасини ёпинг.')
    if db.execute('SELECT 1 FROM clients WHERE agent=? LIMIT 1',(uid,)).fetchone():
        raise ValueError('Бу аккаунтга мижозлар бириктирилган. Аввал уларни бошқа агентга ўтказиш керак.')
    if any(agent_stock(db,uid,pack)!=0 for pack in PRODUCTS):
        raise ValueError('Ходимда товар қолдиғи бор. Аввал товар ҳисобини ёпинг.')
    if cash_usd(db,uid)!=0 or cash(db,uid)!=0:
        raise ValueError('Ходимнинг касса қолдиғи бор. Аввал кассани ёпинг.')
    if db.execute("SELECT 1 FROM handovers WHERE agent=? AND status='pending' LIMIT 1",(uid,)).fetchone():
        raise ValueError('Кассирга топшириш тасдиқланмаган. Аввал уни ҳал қилинг.')
    db.execute('UPDATE users SET role=?,name=? WHERE id=?',('admin',name.strip(),uid))
    db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (f'secondary_admin:{uid}','1'))
    db.execute('DELETE FROM sessions WHERE agent=?',(uid,))
    db.execute('INSERT INTO role_audit(actor,old_id,new_id,action,ts) VALUES(?,?,?,?,?)',
               (actor,uid,uid,'admin_promoted_from_'+row['role'],int(time.time())))
    return 'promoted'

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

def client_stock_total(db,c,p):
    """Physical stock held by a customer across all agents."""
    row=db.execute("""SELECT COALESCE(SUM(CASE WHEN kind='delivery' THEN qty
        WHEN kind IN ('sold','return') THEN -qty ELSE 0 END),0)
        FROM events WHERE client=? AND pack=?""",(c,p)).fetchone()
    return int(row[0] or 0)

def cash(db,a):
    """So'm held by the agent in tiyin (1/100 so'm), the legacy unit of events.amount and
    handovers.amount: legacy UZS payments plus new so'm cash payments (paid_uzs is whole so'm)."""
    collected=amount(db,a,['payment'],field='amount')
    collected+=100*int(db.execute("""SELECT COALESCE(SUM(paid_uzs),0) FROM events WHERE agent=? AND kind='payment'
        AND COALESCE(pay_method,'')='cash'""",(a,)).fetchone()[0] or 0)
    paid=db.execute("SELECT COALESCE(SUM(amount),0) FROM handovers WHERE agent=? AND status='accepted'",(a,)).fetchone()[0]
    return collected-paid

def cash_som(db,a):
    """Whole so'm held by the agent (for the Mini App and messages)."""
    return cash(db,a)//100

def _som_text(tiyin):
    tiyin=int(tiyin or 0)
    text=f"{tiyin//100:,}" if tiyin%100==0 else f"{tiyin/100:,.2f}"
    return text.replace(',',' ')

def handover_value_text(row):
    """'1 185 000 сўм (≈ 100.00 USD)' for so'm handovers, '30.00 USD' for dollar ones."""
    amount_tiyin=int(row['amount'] or 0);usd=int(row['amount_usd'] or 0)
    if amount_tiyin>0:
        return f"{_som_text(amount_tiyin)} сўм"+(f" (≈ {usd/100:,.2f} USD)".replace(',',' ') if usd else '')
    return f"{usd/100:,.2f} USD".replace(',',' ')

BLACKLIST_MSG='⛔ Mijoz qora ro‘yxatda — u bilan hech qanday amal bajarib bo‘lmaydi.'


def client_blacklisted(db,client):
    try:client=int(client)
    except (TypeError,ValueError):return False
    row=db.execute('SELECT blacklisted FROM clients WHERE id=?',(client,)).fetchone()
    return bool(row and int(row[0] or 0))


def ensure_not_blacklisted(db,client):
    if client_blacklisted(db,client):raise ValueError(BLACKLIST_MSG)


def set_client_blacklist(db,actor,client,on,reason='',ts=None):
    """Mijoz o'chirilmaydi: faqat belgi qo'yiladi va tarix (client_blacklist_log) yoziladi.
    Qo'shish: rahbar yoki agent (sabab majburiy). Chiqarish: faqat rahbar."""
    role=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not role or role[0] not in ('admin','agent'):raise ValueError('Ruxsat yo‘q.')
    try:client=int(client)
    except (TypeError,ValueError):raise ValueError('Mijoz noto‘g‘ri.')
    row=db.execute('SELECT id,blacklisted FROM clients WHERE id=?',(client,)).fetchone()
    if not row:raise ValueError('Mijoz topilmadi.')
    ts=int(time.time() if ts is None else ts)
    reason=str(reason or '').strip()
    if on:
        if len(reason)<3:raise ValueError('Qora ro‘yxatga qo‘shish sababini yozing.')
        if len(reason)>300:raise ValueError('Sabab juda uzun.')
        if int(row[1] or 0):raise ValueError('Mijoz allaqachon qora ro‘yxatda.')
        db.execute('UPDATE clients SET blacklisted=1,blacklist_reason=?,blacklist_ts=?,blacklist_by=? WHERE id=?',(reason,ts,actor,client))
    else:
        if role[0]!='admin':raise ValueError('Qora ro‘yxatdan faqat rahbar chiqara oladi.')
        if not int(row[1] or 0):raise ValueError('Mijoz qora ro‘yxatda emas.')
        db.execute("UPDATE clients SET blacklisted=0,blacklist_reason='',blacklist_ts=NULL,blacklist_by=NULL WHERE id=?",(client,))
    db.execute('INSERT INTO client_blacklist_log(client,actor,action,reason,ts) VALUES(?,?,?,?,?)',
               (client,actor,'add' if on else 'remove',reason,ts))
    return {'clientId':client,'blacklisted':bool(on)}


def record(db, actor, agent, client, kind, pack=0, qty=0, value=0, note='', source=None, currency='UZS', ts=None):
    role=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not role or role[0] not in ('admin','agent'): raise ValueError('Рухсат йўқ.')
    if role[0]!='admin' and actor!=agent: raise ValueError('Рухсат йўқ.')
    target=db.execute('SELECT role FROM users WHERE id=?',(agent,)).fetchone()
    if not target or target[0]!='agent': raise ValueError('Агент топилмади.')
    if kind not in ('load','delivery','sold','return','payment','order','visit'): raise ValueError('Амал нотўғри.')
    lock_agent(db,agent)
    if kind=='load' and role[0]!='admin': raise ValueError('Товарни фақат админ беради.')
    if kind!='load':
        c=db.execute('SELECT id,blacklisted FROM clients WHERE id=?',(client,)).fetchone()
        if not c: raise ValueError('Мижоз топилмади.')
        if int(c[1] or 0): raise ValueError(BLACKLIST_MSG)
    if kind in ('load','delivery','sold','return','order'):
        if pack not in PRODUCTS or not isinstance(qty,int) or qty<=0: raise ValueError('Товар ёки миқдор нотўғри.')
    # Delivery is allowed even when the accounting stock is zero or negative.
    # A negative agent stock is an operational discrepancy to reconcile later;
    # it must not block a real customer delivery.
    if kind in ('sold','return') and client_stock_total(db,client,pack)<qty: raise ValueError('Мижозда етарли товар йўқ.')
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
        elif kind=='sold':
            # Sale is recognition of inventory revenue at the original delivered
            # USD lot price. The client debt was already booked at delivery.
            usd=sum(a[2] for a in _delivery_return_allocations(db,client,pack,qty))
        elif kind=='payment':usd=value
        # Sale is physical confirmation only: delivery already generated the USD receivable.
        value=0
    cur=db.execute('INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source) VALUES(?,?,?,?,?,?,?,?,?,?,?) RETURNING id',
               (actor,agent,client,kind,pack,qty,value,usd,note,int(time.time() if ts is None else ts),source))
    if kind=='delivery':
        db.execute('UPDATE clients SET map_only=0 WHERE id=? AND map_only<>0',(client,))
    if allocations:
        return_id=cur.fetchone()[0]
        for delivery_id,count,cents in allocations:
            db.execute('INSERT INTO return_allocations(return_event,delivery_event,qty,amount_usd) VALUES(?,?,?,?)',
                       (return_id,delivery_id,count,cents))

def handover(db,a,value,source,currency='UZS',ts=None):
    role=db.execute('SELECT role FROM users WHERE id=?',(a,)).fetchone()
    if not role or role[0]!='agent': raise ValueError('Фақат агент.')
    lock_agent(db,a)
    if currency not in ('USD','UZS'):raise ValueError('Валюта нотўғри.')
    if isinstance(value,bool) or not isinstance(value,int):raise ValueError('Сумма нотўғри.')
    if currency=='USD':
        reserved=db.execute("SELECT COALESCE(SUM(amount_usd),0) FROM handovers WHERE agent=? AND status='pending' AND COALESCE(amount,0)=0",(a,)).fetchone()[0]
        available=cash_usd(db,a)
    else:
        reserved=db.execute("SELECT COALESCE(SUM(amount),0) FROM handovers WHERE agent=? AND status='pending' AND COALESCE(amount,0)>0",(a,)).fetchone()[0]
        available=cash(db,a)
    free=available-int(reserved or 0)
    if value<=0 or value>free: raise ValueError('Қўлдаги эркин пулдан ортиқ сумма.')
    usd=value
    if currency=='UZS':
        # Book the so'm at the rates the agent actually agreed with clients
        # (average of the so'm still on hand), so the USD cashbook stays exact.
        value_usd=max(0,agent_uzs_value_usd(db,a))
        usd=value_usd if value==free else int((Decimal(value_usd)*value/Decimal(free)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    db.execute('INSERT INTO handovers(agent,amount,amount_usd,source,ts) VALUES(?,?,?,?,?)',
               (a,0 if currency=='USD' else value,usd,source,int(time.time() if ts is None else ts)))

def accept(db,actor,hid,accepted=True):
    r=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not r or r[0] not in ('cashier','admin'): raise ValueError('Фақат кассир ёки админ тасдиқлайди.')
    row=db.execute("SELECT * FROM handovers WHERE id=? AND status='pending'",(hid,)).fetchone()
    if not row: raise ValueError('Топшириқ топилмади ёки аввал тасдиқланган.')
    lock_agent(db,row['agent'])
    # Re-read after acquiring the agent's ledger lock: another cashier may
    # have accepted this handover in the meantime.
    row=db.execute("SELECT * FROM handovers WHERE id=? AND status='pending'",(hid,)).fetchone()
    if not row:raise ValueError('Бу топшириқ аввал ҳал қилинган.')
    if accepted:
        enough=cash(db,row['agent'])>=row['amount'] if int(row['amount'] or 0)>0 else cash_usd(db,row['agent'])>=row['amount_usd']
        if not enough:raise ValueError('Агент пули етарли эмас.')
    db.execute('UPDATE handovers SET status=?,cashier=?,accepted_ts=? WHERE id=?',('accepted' if accepted else 'rejected',actor,int(time.time()),hid))

def cashier_balance_usd(db):
    """Accepted agent handovers less cashier expenses and agent funding, in USD cents.

    Agent funding is a cash transfer out of the cashier into a separate agent
    expense wallet. Agent spending later consumes that wallet and must not be
    deducted from the cashier a second time.
    """
    accepted=db.execute("SELECT COALESCE(SUM(amount_usd),0) FROM handovers WHERE status='accepted'").fetchone()[0]
    spent=db.execute('SELECT COALESCE(SUM(amount_usd),0) FROM cashier_expenses').fetchone()[0]
    funded=db.execute("SELECT COALESCE(SUM(amount_usd),0) FROM agent_funds WHERE kind='topup'").fetchone()[0]
    return int(accepted or 0)-int(spent or 0)-int(funded or 0)


PERIOD_NAMES={'today':'Bugun','week':'7 kun','month':'Shu oy','custom':'Davr'}


def resolve_period(period,date_from=None,date_to=None,now=None):
    """[start,end) Unix range in Asia/Tashkent for today / week (7 days) / month (this month) / custom dates."""
    from datetime import datetime as _dt,timedelta as _td
    from zoneinfo import ZoneInfo as _Z
    tz=_Z('Asia/Tashkent')
    now=int(time.time() if now is None else now)
    today=_dt.fromtimestamp(now,tz).replace(hour=0,minute=0,second=0,microsecond=0)
    period=str(period or 'today')
    if period=='today':start=today;label='Bugun'
    elif period=='week':start=today-_td(days=6);label='Oxirgi 7 kun'
    elif period=='month':start=today.replace(day=1);label=today.strftime('%m.%Y')+' oyi'
    elif period=='custom':
        try:
            a=_dt.strptime(str(date_from or ''),'%Y-%m-%d').replace(tzinfo=tz)
            b=_dt.strptime(str(date_to or ''),'%Y-%m-%d').replace(tzinfo=tz)
        except ValueError:
            raise ValueError('Davr sanalarini to‘g‘ri tanlang.')
        if b<a:a,b=b,a
        if (b-a).days>400:raise ValueError('Davr 400 kundan oshmasin.')
        start=a;end=int((b+_td(days=1)).timestamp())
        return int(start.timestamp()),min(end,now+1),a.strftime('%d.%m.%Y')+' – '+b.strftime('%d.%m.%Y')
    else:raise ValueError('Davr noto‘g‘ri.')
    return int(start.timestamp()),now+1,label


POCKETS_SINCE_KEY='cashier_pockets_since'


def pockets_since(db):
    """Moment from which the three pockets are counted separately.

    Older ledger rows mixed so'm and dollars through a rate, so they stay in one
    'opening' USD figure. A fresh database starts at 0 (everything counted).
    """
    row=db.execute('SELECT value FROM meta WHERE key=?',(POCKETS_SINCE_KEY,)).fetchone()
    if row:
        try:return int(row[0])
        except (TypeError,ValueError):pass
    used=db.execute("""SELECT EXISTS(SELECT 1 FROM handovers WHERE status='accepted')
        OR EXISTS(SELECT 1 FROM cashier_expenses) OR EXISTS(SELECT 1 FROM agent_funds)""").fetchone()[0]
    since=int(time.time()) if used else 0
    db.execute('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO NOTHING',(POCKETS_SINCE_KEY,str(since)))
    return since


def cashier_flows(db,start=None,end=None):
    """Cashier money split by real pocket, never mixed through a rate.

    cash_uzs / card_uzs are whole so'm, cash_usd / card_usd are USD cents.
    Without start/end: pocket balances counted from pockets_since(), plus the
    older mixed balance as opening_usd. With start/end: the movement in [start,end).
    """
    def one(sql,args):
        return int(db.execute(sql,args).fetchone()[0] or 0)
    balance=start is None
    if balance:
        since=pockets_since(db)
        start,end=since,2**62
    start,end=int(start),int(end)
    hw=' AND COALESCE(accepted_ts,ts)>=? AND COALESCE(accepted_ts,ts)<?'
    ew=fw=cw=' AND ts>=? AND ts<?'
    args=(start,end)
    out={
        'in_cash_uzs':one("SELECT COALESCE(SUM(amount),0) FROM handovers WHERE status='accepted' AND COALESCE(amount,0)>0"+hw,args)//100,
        'in_cash_usd':one("SELECT COALESCE(SUM(amount_usd),0) FROM handovers WHERE status='accepted' AND COALESCE(amount,0)=0"+hw,args),
        'in_card_uzs':one("SELECT COALESCE(SUM(amount_uzs),0) FROM cashier_incomes WHERE currency='UZS'"+cw,args),
        'in_card_usd':one("SELECT COALESCE(SUM(amount_usd),0) FROM cashier_incomes WHERE currency<>'UZS'"+cw,args),
        'out_expense_uzs':one("SELECT COALESCE(SUM(amount_uzs),0) FROM cashier_expenses WHERE currency='UZS' AND pay_from<>'card'"+ew,args),
        'out_expense_usd':one("SELECT COALESCE(SUM(amount_usd),0) FROM cashier_expenses WHERE currency<>'UZS' AND pay_from<>'card'"+ew,args),
        'out_card_uzs':one("SELECT COALESCE(SUM(amount_uzs),0) FROM cashier_expenses WHERE currency='UZS' AND pay_from='card'"+ew,args),
        'out_card_usd':one("SELECT COALESCE(SUM(amount_usd),0) FROM cashier_expenses WHERE currency<>'UZS' AND pay_from='card'"+ew,args),
        'out_fund_uzs':one("SELECT COALESCE(SUM(amount_uzs),0) FROM agent_funds WHERE kind='topup' AND COALESCE(amount_uzs,0)>0"+fw,args),
        'out_fund_usd':one("SELECT COALESCE(SUM(amount_usd),0) FROM agent_funds WHERE kind='topup' AND COALESCE(amount_uzs,0)=0"+fw,args),
    }
    out['cash_uzs']=out['in_cash_uzs']-out['out_expense_uzs']-out['out_fund_uzs']
    out['cash_usd']=out['in_cash_usd']-out['out_expense_usd']-out['out_fund_usd']
    out['card_uzs']=out['in_card_uzs']-out['out_card_uzs']
    out['card_usd']=out['in_card_usd']-out['out_card_usd']
    if balance:
        moved=(one("SELECT COALESCE(SUM(amount_usd),0) FROM handovers WHERE status='accepted'"+hw,args)
               -one("SELECT COALESCE(SUM(amount_usd),0) FROM cashier_expenses WHERE 1=1"+ew,args)
               -one("SELECT COALESCE(SUM(amount_usd),0) FROM agent_funds WHERE kind='topup'"+fw,args))
        out['since']=since
        out['opening_usd']=cashier_balance_usd(db)-moved if since else 0
    return out


def agent_fund_balance_usd(db,agent):
    row=db.execute("""SELECT COALESCE(SUM(CASE WHEN kind='topup' THEN amount_usd
        WHEN kind='expense' THEN -amount_usd ELSE 0 END),0)
        FROM agent_funds WHERE agent=?""",(agent,)).fetchone()
    return int(row[0] or 0)


def agent_fund_balance_uzs(db,agent):
    """Spendable agent expense wallet in UZS.

    New wallet operations are stored natively in UZS. Legacy USD-only rows are
    translated at the current cashier rate only to avoid losing an old balance
    during the one-way migration to UZS.
    """
    row=db.execute("""SELECT
        COALESCE(SUM(CASE WHEN amount_uzs>0 AND kind='topup' THEN amount_uzs
                          WHEN amount_uzs>0 AND kind='expense' THEN -amount_uzs ELSE 0 END),0) AS uzs,
        COALESCE(SUM(CASE WHEN amount_uzs=0 AND kind='topup' THEN amount_usd
                          WHEN amount_uzs=0 AND kind='expense' THEN -amount_usd ELSE 0 END),0) AS legacy_usd
        FROM agent_funds WHERE agent=?""",(agent,)).fetchone()
    balance=int(row['uzs'] or 0)
    legacy=int(row['legacy_usd'] or 0)
    rate=cashier_rate(db)
    if legacy and rate:
        balance+=int((Decimal(legacy)*Decimal(rate)/Decimal(100)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    return balance


def fund_agent_expense_uzs(db,actor,agent,amount_uzs,note,source,expected_rate=None):
    identity=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not identity or identity[0] not in ('cashier','admin'):
        raise ValueError('Агент ҳисобини фақат кассир ёки админ тўлдиради.')
    target=db.execute("SELECT name FROM users WHERE id=? AND role='agent'",(agent,)).fetchone()
    if not target:raise ValueError('Агент топилмади.')
    if not isinstance(amount_uzs,int) or isinstance(amount_uzs,bool) or amount_uzs<=0:
        raise ValueError('Сўм миқдори нотўғри.')
    if not isinstance(note,str) or len(note)>1000:
        raise ValueError('Изоҳ 1000 белгидан ошмасин.')
    if not isinstance(source,int) or source<=0:raise ValueError('Операция ID нотўғри.')
    if isinstance(db,PostgresDB):
        db.execute('SELECT pg_advisory_xact_lock(?)',(_CASHBOX_LOCK,)).fetchone()
    lock_agent(db,agent)
    if db.execute('SELECT 1 FROM agent_funds WHERE source=?',(source,)).fetchone():
        raise ValueError('Бу операция аллақачон сақланган.')
    rate=cashier_rate(db)
    if rate is None:raise ValueError('Аввал «💱 Касса курси» бўлимида 1 USD курсини белгиланг.')
    if expected_rate is not None and int(expected_rate)!=rate:
        raise ValueError('Курс ўзгарган. Янги курсда агент балансини қайта киритинг.')
    amount_usd=som_to_usd_cents(amount_uzs,rate)
    if amount_usd>cashier_balance_usd(db):
        raise ValueError('Кассада агентга бериш учун етарли пул йўқ.')
    row=db.execute("""INSERT INTO agent_funds(agent,actor,kind,amount_usd,amount_uzs,rate_uzs_per_usd,category,note,source,ts)
        VALUES(?,?,'topup',?,?,?,'',?,?,?) RETURNING id""",
        (agent,actor,amount_usd,amount_uzs,rate,note.strip(),source,int(time.time()))).fetchone()
    return int(row[0]),amount_usd,rate


def add_agent_expense_uzs(db,actor,amount_uzs,category,note,source,expected_rate=None,ts=None):
    identity=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not identity or identity[0]!='agent':
        raise ValueError('Харажатни фақат агент ўз ҳисобидан киритади.')
    if not isinstance(amount_uzs,int) or isinstance(amount_uzs,bool) or amount_uzs<=0:
        raise ValueError('Харажат суммаси нотўғри.')
    if category not in CASHIER_EXPENSE_CATEGORIES:
        raise ValueError('Харажат турини рўйхатдан танланг.')
    if not isinstance(note,str) or len(note)>1000:
        raise ValueError('Изоҳ 1000 белгидан ошмасин.')
    if not isinstance(source,int) or source<=0:raise ValueError('Операция ID нотўғри.')
    lock_agent(db,actor)
    if db.execute('SELECT 1 FROM agent_funds WHERE source=?',(source,)).fetchone():
        raise ValueError('Бу операция аллақачон сақланган.')
    if amount_uzs>agent_fund_balance_uzs(db,actor):
        raise ValueError('Агент харажат ҳисобида етарли сўм йўқ.')
    rate=cashier_rate(db)
    if rate is None:raise ValueError('Аввал касса курсини белгиланг.')
    if expected_rate is not None and int(expected_rate)!=rate:
        raise ValueError('Курс ўзгарган. Янги курсда харажатни қайта тасдиқланг.')
    amount_usd=som_to_usd_cents(amount_uzs,rate)
    row=db.execute("""INSERT INTO agent_funds(agent,actor,kind,amount_usd,amount_uzs,rate_uzs_per_usd,category,note,source,ts)
        VALUES(?,?,'expense',?,?,?,?,?,?,?) RETURNING id""",
        (actor,actor,amount_usd,amount_uzs,rate,category,note.strip(),source,int(time.time() if ts is None else ts))).fetchone()
    return int(row[0]),amount_usd,rate


def fund_agent_expense(db,actor,agent,amount_usd,note,source):
    identity=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not identity or identity[0] not in ('cashier','admin'):
        raise ValueError('Агент ҳисобини фақат кассир ёки админ тўлдиради.')
    target=db.execute("SELECT name FROM users WHERE id=? AND role='agent'",(agent,)).fetchone()
    if not target:raise ValueError('Агент топилмади.')
    if not isinstance(amount_usd,int) or isinstance(amount_usd,bool) or amount_usd<=0:
        raise ValueError('Сумма нотўғри.')
    if not isinstance(note,str) or len(note)>1000:
        raise ValueError('Изоҳ 1000 белгидан ошмасин.')
    if not isinstance(source,int) or source<=0:raise ValueError('Операция ID нотўғри.')
    if isinstance(db,PostgresDB):
        db.execute('SELECT pg_advisory_xact_lock(7806292501)').fetchone()
    lock_agent(db,agent)
    if db.execute('SELECT 1 FROM agent_funds WHERE source=?',(source,)).fetchone():
        raise ValueError('Бу операция аллақачон сақланган.')
    if amount_usd>cashier_balance_usd(db):
        raise ValueError('Кассада агентга бериш учун етарли пул йўқ.')
    row=db.execute("""INSERT INTO agent_funds(agent,actor,kind,amount_usd,category,note,source,ts)
        VALUES(?,?,'topup',?,'',?,?,?) RETURNING id""",
        (agent,actor,amount_usd,note.strip(),source,int(time.time()))).fetchone()
    return int(row[0])


def add_agent_expense(db,actor,amount_usd,category,note,source):
    identity=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not identity or identity[0]!='agent':
        raise ValueError('Харажатни фақат агент ўз ҳисобидан киритади.')
    if not isinstance(amount_usd,int) or isinstance(amount_usd,bool) or amount_usd<=0:
        raise ValueError('Харажат суммаси нотўғри.')
    if category not in CASHIER_EXPENSE_CATEGORIES:
        raise ValueError('Харажат турини рўйхатдан танланг.')
    if not isinstance(note,str) or len(note)>1000:
        raise ValueError('Изоҳ 1000 белгидан ошмасин.')
    if not isinstance(source,int) or source<=0:raise ValueError('Операция ID нотўғри.')
    lock_agent(db,actor)
    if db.execute('SELECT 1 FROM agent_funds WHERE source=?',(source,)).fetchone():
        raise ValueError('Бу операция аллақачон сақланган.')
    if amount_usd>agent_fund_balance_usd(db,actor):
        raise ValueError('Агент харажат ҳисобида етарли пул йўқ.')
    row=db.execute("""INSERT INTO agent_funds(agent,actor,kind,amount_usd,category,note,source,ts)
        VALUES(?,?,'expense',?,?,?,?,?) RETURNING id""",
        (actor,actor,amount_usd,category,note.strip(),source,int(time.time()))).fetchone()
    return int(row[0])


CASHIER_INCOME_CATEGORIES=(
    '💵 Савдодан ташқари кирим', '🏦 Банк/кассадан', '👨‍💼 Раҳбардан',
    '↩️ Қайтган пул', '📦 Бошқа кирим',
)

CASHIER_EXPENSE_CATEGORIES=(
    '🚚 Йўл харажати', '⛽ Ёқилғи', '🍽 Тушлик', '👷 Иш ҳақи',
    '🏢 Офис ва хўжалик', '📦 Бошқа харажат',
)


def add_cashier_income(db,actor,amount_usd,category,source_name,note,source):
    """Manual cashier income is intentionally disabled.

    Cash enters the cashier ledger only through an agent handover that the
    cashier explicitly accepts.
    """
    raise ValueError('Кассир қўлда кирим қила олмайди. Кирим фақат агент пул топшириб, кассир тасдиқлаганда тушади.')

def add_cashier_expense(db,actor,amount_usd,category,recipient,note,source,pocket='USD',pay_from='cash'):
    identity=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not identity or identity[0] not in ('cashier','admin'):
        raise ValueError('Харажатни фақат кассир ёки админ киритиши мумкин.')
    if not isinstance(amount_usd,int) or isinstance(amount_usd,bool) or amount_usd<=0:
        raise ValueError('Харажат суммаси нотўғри.')
    if category not in CASHIER_EXPENSE_CATEGORIES:
        raise ValueError('Харажат турини рўйхатдан танланг.')
    if not isinstance(recipient,str) or not recipient.strip() or len(recipient)>200:
        raise ValueError('Кимга ёки нима учун берилганини киритинг (1–200 белги).')
    if not isinstance(note,str) or len(note)>1000:
        raise ValueError('Изоҳ 1000 белгидан ошмасин.')
    if not isinstance(source,int) or source<=0:
        raise ValueError('Операция ID нотўғри.')
    # Lock the common cashbox when two PostgreSQL cashiers attempt to spend
    # simultaneously; the surrounding transaction owns this advisory lock.
    if isinstance(db,PostgresDB):
        db.execute('SELECT pg_advisory_xact_lock(7806292501)').fetchone()
    if db.execute('SELECT 1 FROM cashier_expenses WHERE source=?',(source,)).fetchone():
        raise ValueError('Бу харажат аллақачон сақланган.')
    if pay_from not in ('cash','card'):
        raise ValueError('Харажат манбаини танланг: нақд ёки карта.')
    limit=cashier_balance_usd(db)
    if pay_from=='card':
        # A card expense is paid from card/bank receipts, so the whole cashbox counts.
        limit+=int(db.execute('SELECT COALESCE(SUM(amount_usd),0) FROM cashier_incomes').fetchone()[0] or 0)
    if amount_usd>limit:
        raise ValueError('Кассада етарли қабул қилинган пул йўқ.')
    return int(db.execute('INSERT INTO cashier_expenses(cashier,amount_usd,category,recipient,note,source,ts,pay_from) VALUES(?,?,?,?,?,?,?,?) RETURNING id',(actor,amount_usd,category,recipient.strip(),note.strip(),source,int(time.time()),pay_from)).fetchone()[0])


# Manually maintained internal bookkeeping rate; never implies a live FX quote.
CASHIER_RATE_KEY='cashier_uzs_per_usd'
_CASHBOX_LOCK=7806292501


def parse_whole_som(raw,label='Сумма'):
    text=str(raw or '').strip().replace(' ','')
    if not text.isdecimal() or not 1<=int(text)<=10**12:
        raise ValueError(f'{label}: 1 дан 1 000 000 000 000 гача бутун сўм киритинг.')
    return int(text)


def cashier_rate(db):
    row=db.execute('SELECT value FROM meta WHERE key=?',(CASHIER_RATE_KEY,)).fetchone()
    if not row:return None
    try:rate=int(row[0])
    except (TypeError,ValueError):return None
    return rate if 100<=rate<=10**7 else None


def set_cashier_rate(db,actor,rate,source):
    identity=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not identity or identity[0] not in ('cashier','admin'):
        raise ValueError('Курсни фақат кассир ёки админ белгилайди.')
    if isinstance(rate,bool) or not isinstance(rate,int) or not 100<=rate<=10**7:
        raise ValueError('1 USD учун бутун сўмда курс киритинг (100–10 000 000).')
    if not isinstance(source,int) or source<=0:raise ValueError('Операция ID нотўғри.')
    if isinstance(db,PostgresDB):
        db.execute('SELECT pg_advisory_xact_lock(?)',(_CASHBOX_LOCK,)).fetchone()
    if db.execute('SELECT 1 FROM cashier_fx_rates WHERE source=?',(source,)).fetchone():
        raise ValueError('Бу курс аллақачон сақланган.')
    db.execute('INSERT INTO cashier_fx_rates(cashier,rate_uzs_per_usd,source,ts) VALUES(?,?,?,?)',
               (actor,rate,source,int(time.time())))
    db.execute('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
               (CASHIER_RATE_KEY,str(rate)))
    return rate


def som_to_usd_cents(som,rate):
    if not isinstance(som,int) or isinstance(som,bool) or som<=0:raise ValueError('Сўм миқдори нотўғри.')
    if not isinstance(rate,int) or not 100<=rate<=10**7:raise ValueError('Аввал касса курсини белгиланг.')
    cents=int((Decimal(som)*100/Decimal(rate)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    if cents<=0:raise ValueError('Харажат 0.01 USD дан кичик. Суммани текширинг.')
    return cents


def add_cashier_income_uzs(db,actor,amount_uzs,category,source_name,note,source,expected_rate=None):
    raise ValueError('Кассир қўлда кирим қила олмайди. Кирим фақат агент пул топшириб, кассир тасдиқлаганда тушади.')

def add_cashier_expense_uzs(db,actor,amount_uzs,category,recipient,note,source,expected_rate=None,pay_from='cash'):
    if isinstance(db,PostgresDB):
        db.execute('SELECT pg_advisory_xact_lock(?)',(_CASHBOX_LOCK,)).fetchone()
    rate=cashier_rate(db)
    if rate is None:raise ValueError('Аввал «💱 Касса курси» бўлимида 1 USD курсини белгиланг.')
    if expected_rate is not None and rate!=expected_rate:
        raise ValueError('Курс ўзгарган. Янги курсда харажатни қайта киритинг.')
    cents=som_to_usd_cents(amount_uzs,rate)
    expense_id=add_cashier_expense(db,actor,cents,category,recipient,note,source,pocket='UZS',pay_from=pay_from)
    db.execute("""UPDATE cashier_expenses SET currency='UZS',amount_uzs=?,rate_uzs_per_usd=?
           WHERE id=?""",(amount_uzs,rate,expense_id))
    return expense_id,cents,rate


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

def track_km(points):
    """Walked/driven distance from GPS points, robust to phone GPS noise.

    A point is skipped when its accuracy is worse than 100 m, when it implies an
    impossible speed (> 55 m/s), or when it is within the noise radius of the last
    counted point (standing in a shop must not add kilometres). A silence longer
    than 30 minutes restarts the trail instead of drawing a straight line.
    """
    km=0.0;ref=None
    for p in points:
        try:
            lat,lon,ts=float(p['lat']),float(p['lon']),int(p['ts'])
        except (TypeError,ValueError,KeyError):
            continue
        if not (-90<=lat<=90 and -180<=lon<=180):continue
        acc=float((p['accuracy'] if 'accuracy' in p.keys() else 0) or 0) if hasattr(p,'keys') else 0.0
        if acc>100:continue
        cur={'lat':lat,'lon':lon,'ts':ts,'acc':acc}
        if ref is None:ref=cur;continue
        dt=ts-ref['ts']
        if dt<=0:continue
        if dt>1800:ref=cur;continue
        d=distance(ref,cur)
        if d/dt>55:continue
        if d<max(15.0,ref['acc']+acc):continue
        km+=d/1000;ref=cur
    return km

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
    return {'km':round(track_km(points),2),'gaps':gaps,'stops':stops}


# ---------------------------------------------------------------------------
# Client payments in so'm (agreed rate) and by card (confirmed by the cashier)
# ---------------------------------------------------------------------------
PAY_METHODS=('cash','card')


def validate_agent_rate(db,rate):
    """Rate agreed between agent and client. Guard against typos (11850 vs 1185)."""
    if isinstance(rate,bool) or not isinstance(rate,int):raise ValueError('Kursni butun so‘mda kiriting.')
    base=cashier_rate(db)
    if base:
        low,high=int(base*0.8),int(base*1.2)+1
        if not low<=rate<=high:
            raise ValueError(f'Kurs {rate:,} so‘m kassa kursidan ({base:,}) juda farq qiladi. Tekshirib qayta kiriting.')
    elif not 1000<=rate<=100000:
        raise ValueError('Kurs 1 000 – 100 000 so‘m oralig‘ida bo‘lsin.')
    return rate


def implied_rate(db,som,usd_cents):
    """Agent typed both the so'm received and its dollar equivalent: derive and sanity-check the rate."""
    if isinstance(som,bool) or not isinstance(som,int) or som<=0:raise ValueError('So‘m summasini kiriting.')
    if isinstance(usd_cents,bool) or not isinstance(usd_cents,int) or usd_cents<=0:raise ValueError('Dollar summasini kiriting.')
    rate=int((Decimal(som)*100/Decimal(usd_cents)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    try:validate_agent_rate(db,rate)
    except ValueError:
        base=cashier_rate(db)
        raise ValueError(f'{som:,} so‘m = {usd_cents/100:.2f} $ bo‘lsa kurs {rate:,} chiqadi'+(f' (kassa kursi {base:,})' if base else '')+'. Summalarni tekshiring.')
    return rate


def record_client_payment(db,actor,agent,client,currency,value,method,rate=None,note='',source=None,ts=None,usd_cents=None):
    """Cash payment: reduces client debt immediately (USD), money stays with the agent.

    currency='USD': value in cents. currency='UZS': value in whole so'm, converted at the agreed rate.
    """
    if method!='cash':raise ValueError('Bu funksiya faqat naqd to‘lov uchun.')
    if currency=='USD':
        record(db,actor,agent,client,'payment',0,0,value,note,source,currency='USD',ts=ts)
        db.execute("UPDATE events SET pay_method='cash' WHERE source=?",(source,))
        return value,0,0
    if currency!='UZS':raise ValueError('Valyutani USD yoki UZS qilib tanlang.')
    if usd_cents is not None:
        rate=implied_rate(db,value,usd_cents);usd=usd_cents
    else:
        rate=validate_agent_rate(db,rate)
        usd=som_to_usd_cents(value,rate)
    record(db,actor,agent,client,'payment',0,0,usd,note,source,currency='USD',ts=ts)
    db.execute("UPDATE events SET pay_method='cash',paid_uzs=?,fx_rate=? WHERE source=?",(value,rate,source))
    return usd,value,rate


def submit_card_payment(db,agent,client,currency,value,rate=None,note='',source=None,ts=None,usd_cents=None,photo=''):
    """Card / bank transfer: waits for the cashier; client debt is NOT reduced yet."""
    ensure_not_blacklisted(db,client)
    role=db.execute('SELECT role FROM users WHERE id=?',(agent,)).fetchone()
    if not role or role[0]!='agent':raise ValueError('Агент топилмади.')
    if not db.execute('SELECT id FROM clients WHERE id=?',(client,)).fetchone():raise ValueError('Мижоз топилмади.')
    if not isinstance(source,int):raise ValueError('Операция ID нотўғри.')
    lock_agent(db,agent)
    old=db.execute('SELECT id FROM card_payments WHERE source=?',(source,)).fetchone()
    if old:return int(old[0]),None,None,None
    if currency=='USD':
        if isinstance(value,bool) or not isinstance(value,int) or value<=0:raise ValueError('Сумма киритилмаган.')
        som,usd,rate=0,value,0
    elif currency=='UZS':
        som=value
        if usd_cents is not None:rate=implied_rate(db,som,usd_cents);usd=usd_cents
        else:rate=validate_agent_rate(db,rate);usd=som_to_usd_cents(som,rate)
    else:raise ValueError('Valyutani USD yoki UZS qilib tanlang.')
    row=db.execute("""INSERT INTO card_payments(agent,client,currency,amount_uzs,amount_usd,rate_uzs_per_usd,note,status,source,ts,photo)
        VALUES(?,?,?,?,?,?,?,'pending',?,?,?) RETURNING id""",
        (agent,client,currency,som,usd,rate,str(note or '')[:500],source,int(time.time() if ts is None else ts),str(photo or ''))).fetchone()
    return int(row[0]),usd,som,rate


def decide_card_payment(db,actor,payment_id,confirm=True):
    """Cashier confirms the money reached the bank (or rejects it)."""
    identity=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not identity or identity[0] not in ('cashier','admin'):
        raise ValueError('Karta to‘lovini faqat kassir yoki admin tasdiqlaydi.')
    row=db.execute("SELECT * FROM card_payments WHERE id=?",(payment_id,)).fetchone()
    if not row:raise ValueError('Karta to‘lovi topilmadi.')
    lock_agent(db,row['agent'])
    row=db.execute("SELECT * FROM card_payments WHERE id=? AND status='pending'",(payment_id,)).fetchone()
    if not row:raise ValueError('Bu karta to‘lovi avval ko‘rib chiqilgan.')
    now=int(time.time())
    if not confirm:
        db.execute("UPDATE card_payments SET status='rejected',cashier=?,decided_ts=? WHERE id=?",(actor,now,payment_id))
        return None
    c=db.execute('SELECT name,shop_name FROM clients WHERE id=?',(row['client'],)).fetchone()
    label=(c['shop_name'] or c['name']) if c else f"#{row['client']}"
    som=int(row['amount_uzs'] or 0);rate=int(row['rate_uzs_per_usd'] or 0)
    note=(f"Karta · {som:,} UZS · 1 USD = {rate:,} UZS" if som else "Karta · USD")+(f" · {row['note']}" if row['note'] else '')
    ev=db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source,pay_method,paid_uzs,fx_rate)
        VALUES(?,?,?,'payment',0,0,0,?,?,?,?,'card',?,?) RETURNING id""",
        (row['agent'],row['agent'],row['client'],int(row['amount_usd']),note,int(row['ts']),int(row['source']),som,rate)).fetchone()
    event_id=int(ev[0])
    if isinstance(db,PostgresDB):
        db.execute('SELECT pg_advisory_xact_lock(?)',(_CASHBOX_LOCK,)).fetchone()
    db.execute("""INSERT INTO cashier_incomes(cashier,amount_usd,category,source_name,note,source,ts,currency,amount_uzs,rate_uzs_per_usd)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (actor,int(row['amount_usd']),'Mijoz to‘lovi · karta',label,f"Karta to‘lovi #{payment_id}",int(row['source']),now,
         row['currency'],som,rate))
    db.execute("UPDATE card_payments SET status='confirmed',cashier=?,decided_ts=?,event_id=? WHERE id=?",(actor,now,event_id,payment_id))
    if client_debt_usd(db,row['client'])<=0:
        db.execute("UPDATE collection_tasks SET status='done',completed_ts=? WHERE client=? AND status='open'",(now,row['client']))
    return event_id


def payment_label(row):
    """Human text for a payment row in act sverka / client card."""
    try:som=int(row['paid_uzs'] or 0);rate=int(row['fx_rate'] or 0);method=row['pay_method'] or ''
    except (KeyError,IndexError,TypeError):return ''
    parts=[]
    if som:parts.append(f"{som:,} сўм".replace(',',' '))
    if rate:parts.append(f"курс {rate:,}".replace(',',' '))
    if method=='card':parts.append('карта')
    elif method=='cash':parts.append('нақд')
    return ' · '.join(parts)



# ---------------------------------------------------------------------------
# Ombor: manager-maintained product catalog and agent orders
# ---------------------------------------------------------------------------
ORDER_STATUSES=('new','preparing','loaded','delivered','rejected')
ORDER_STATUS_LABELS={'new':'Yangi','preparing':'Tayyorlanmoqda','loaded':'Agentga berildi',
                     'delivered':'Mijozga yetkazildi','rejected':'Rad etildi'}
ORDER_OPEN=('new','preparing')


def _require_admin(db,actor,msg='Фақат раҳбар (админ) учун.'):
    r=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not r or r[0]!='admin':raise ValueError(msg)


def clean_product_name(value):
    name=re.sub(r'\s+',' ',str(value or '')).strip()
    if not 2<=len(name)<=120:raise ValueError('Mahsulot nomi 2–120 belgi bo‘lsin.')
    return name


def _name_key(value):
    return re.sub(r'[^0-9a-zа-яёўқғҳʼ‘’]+','',str(value or '').lower().replace('‘',"'"))


def _parse_weight(value):
    try:w=Decimal(str(value).replace(',','.').strip())
    except (InvalidOperation,ValueError):raise ValueError('Og‘irlik (kg) noto‘g‘ri.')
    if not w.is_finite() or w<=0 or w>1000:raise ValueError('Og‘irlik 0 dan katta va 1000 kg gacha bo‘lsin.')
    return float(w.quantize(Decimal('0.001')))


def add_product(db,actor,name,weight_kg,price_cents,block=0,ts=None):
    _require_admin(db,actor,'Mahsulotni faqat rahbar qo‘shadi.')
    name=clean_product_name(name);weight=_parse_weight(weight_kg)
    if isinstance(price_cents,bool) or not isinstance(price_cents,int) or price_cents<=0:raise ValueError('Narxni USD da kiriting.')
    try:block=int(block or 0)
    except (TypeError,ValueError):raise ValueError('Blokdagi dona soni noto‘g‘ri.')
    if not 0<=block<=1000:raise ValueError('Blokdagi dona soni noto‘g‘ri.')
    key=_name_key(name)
    for r in db.execute('SELECT pack,name FROM products').fetchall():
        if _name_key(r['name'])==key:raise ValueError(f"Bu mahsulot katalogda bor: {r['name']}")
    top=db.execute('SELECT COALESCE(MAX(pack),0) FROM products WHERE pack>=?',(CUSTOM_PRODUCT_START,)).fetchone()[0]
    pack=max(CUSTOM_PRODUCT_START,int(top or 0)+1)
    db.execute('INSERT INTO products(pack,name,price,weight_kg,block_units,active,custom,created_ts) VALUES(?,?,?,?,?,1,1,?)',
               (pack,name,price_cents,weight,block,int(time.time() if ts is None else ts)))
    refresh_catalog(db)
    return pack


def agent_custom_product(db,agent,name,price_cents,ts=None):
    """An agent hands over a product that is not in the catalog yet: reuse a same-named product,
    otherwise add it (marked custom) so stock, debt and reports work; the manager can edit it later."""
    name=clean_product_name(name)
    if isinstance(price_cents,bool) or not isinstance(price_cents,int) or price_cents<=0:
        raise ValueError(f'{name}: 1 dona narxini USD da kiriting.')
    key=_name_key(name)
    for r in db.execute('SELECT pack,name,price,active FROM products').fetchall():
        if _name_key(r['name'])==key:
            pack=int(r['pack'])
            if not int(r['price'] or 0):db.execute('UPDATE products SET price=? WHERE pack=?',(price_cents,pack))
            if not int(r['active'] if r['active'] is not None else 1):db.execute('UPDATE products SET active=1 WHERE pack=?',(pack,))
            refresh_catalog(db)
            return pack,False
    top=db.execute('SELECT COALESCE(MAX(pack),0) FROM products WHERE pack>=?',(CUSTOM_PRODUCT_START,)).fetchone()[0]
    pack=max(CUSTOM_PRODUCT_START,int(top or 0)+1)
    db.execute('INSERT INTO products(pack,name,price,weight_kg,block_units,active,custom,created_ts) VALUES(?,?,?,?,?,1,1,?)',
               (pack,name,price_cents,0,0,int(time.time() if ts is None else ts)))
    refresh_catalog(db)
    return pack,True

def update_product(db,actor,pack,name=None,price_cents=None,active=None,weight_kg=None):
    _require_admin(db,actor,'Mahsulotni faqat rahbar o‘zgartiradi.')
    try:pack=int(pack)
    except (TypeError,ValueError):raise ValueError('Mahsulot topilmadi.')
    row=db.execute('SELECT * FROM products WHERE pack=?',(pack,)).fetchone()
    if not row or pack not in PRODUCTS:raise ValueError('Mahsulot topilmadi.')
    custom=pack not in BUILTIN_PRODUCTS
    if name not in (None,'') and clean_product_name(name)!=row['name']:
        if not custom:raise ValueError('Asosiy mahsulot nomi o‘zgarmaydi — faqat narx va holat.')
        new=clean_product_name(name);key=_name_key(new)
        for r in db.execute('SELECT pack,name FROM products WHERE pack<>?',(pack,)).fetchall():
            if _name_key(r['name'])==key:raise ValueError(f"Bu nom band: {r['name']}")
        db.execute('UPDATE products SET name=? WHERE pack=?',(new,pack))
    if weight_kg not in (None,''):
        if not custom:raise ValueError('Asosiy mahsulot og‘irligi o‘zgarmaydi.')
        db.execute('UPDATE products SET weight_kg=? WHERE pack=?',(_parse_weight(weight_kg),pack))
    if price_cents is not None:
        if isinstance(price_cents,bool) or not isinstance(price_cents,int) or price_cents<=0:raise ValueError('Narx noto‘g‘ri.')
        db.execute('UPDATE products SET price=? WHERE pack=?',(price_cents,pack))
    if active is not None:
        if not isinstance(active,bool):raise ValueError('Holat noto‘g‘ri.')
        db.execute('UPDATE products SET active=? WHERE pack=?',(1 if active else 0,pack))
    refresh_catalog(db)
    return pack


def catalog(db):
    rows=db.execute('SELECT pack,name,price,weight_kg,block_units,active,custom,created_ts FROM products ORDER BY custom,pack').fetchall()
    out=[]
    for r in rows:
        pack=int(r['pack'])
        if pack not in PRODUCTS:continue
        out.append({'pack':pack,'name':PRODUCTS[pack],'priceCents':int(r['price'] or 0),
                    'weightKg':PRODUCT_WEIGHTS.get(pack),'blockUnits':PACK_UNITS.get(pack),
                    'active':pack not in INACTIVE_PRODUCTS,'custom':pack not in BUILTIN_PRODUCTS})
    return out


def _order_source(tag):
    import hashlib
    return -(int.from_bytes(hashlib.sha256(tag.encode()).digest()[:7],'big')*16+9)


def create_order(db,agent,client,items,note='',source=None,ts=None):
    role=db.execute('SELECT role FROM users WHERE id=?',(agent,)).fetchone()
    if not role or role[0]!='agent':raise ValueError('Агент топилмади.')
    if not db.execute('SELECT id FROM clients WHERE id=?',(client,)).fetchone():raise ValueError('Мижоз топилмади.')
    if not isinstance(source,int):raise ValueError('Операция ID нотўғри.')
    ensure_not_blacklisted(db,client)
    old=db.execute('SELECT id FROM orders WHERE source=?',(source,)).fetchone()
    if old:return int(old[0]),True
    if not isinstance(items,list) or not items or len(items)>30:raise ValueError('Buyurtmaga 1–30 qator mahsulot kiriting.')
    clean=[];seen=set()
    for it in items:
        if not isinstance(it,dict):raise ValueError('Buyurtma qatori noto‘g‘ri.')
        try:qty=int(str(it.get('qty')).strip())
        except (TypeError,ValueError):raise ValueError('Buyurtma soni butun son bo‘lsin.')
        if not 0<qty<=100000:raise ValueError('Buyurtma soni 1 dan 100000 gacha bo‘lsin.')
        raw_pack=it.get('pack')
        if raw_pack not in (None,'','custom'):
            try:pack=int(raw_pack)
            except (TypeError,ValueError):raise ValueError('Mahsulot topilmadi.')
            if pack not in PRODUCTS or pack in INACTIVE_PRODUCTS:raise ValueError('Mahsulot katalogda yo‘q yoki arxivda.')
            key=('p',pack);clean_item=(pack,'',qty)
        else:
            name=clean_product_name(it.get('name'))
            # A typed name that matches a catalog product is attached to it directly.
            match=[p for p in active_product_ids() if _name_key(PRODUCTS[p])==_name_key(name)]
            if match:key=('p',match[0]);clean_item=(match[0],'',qty)
            else:key=('n',_name_key(name));clean_item=(None,name,qty)
        if key in seen:raise ValueError('Bir mahsulot buyurtmada ikki marta yozilgan.')
        seen.add(key);clean.append(clean_item)
    note=str(note or '').strip()
    if len(note)>500:raise ValueError('Izoh 500 belgidan oshmasin.')
    now=int(time.time() if ts is None else ts)
    row=db.execute("""INSERT INTO orders(agent,client,status,note,source,ts,updated_ts) VALUES(?,?,'new',?,?,?,?) RETURNING id""",
                   (agent,client,note,source,now,now)).fetchone()
    oid=int(row[0])
    for pack,name,qty in clean:
        db.execute('INSERT INTO order_items(order_id,pack,custom_name,qty) VALUES(?,?,?,?)',(oid,pack,name,qty))
    return oid,False


def order_items(db,oid):
    out=[]
    for r in db.execute('SELECT id,pack,custom_name,qty FROM order_items WHERE order_id=? ORDER BY id',(oid,)).fetchall():
        pack=int(r['pack']) if r['pack'] is not None else None
        out.append({'id':int(r['id']),'pack':pack,'qty':int(r['qty']),
                    'name':PRODUCTS.get(pack,f'Товар {pack}') if pack is not None else r['custom_name'],
                    'custom':pack is None,'requestedName':r['custom_name'] or '',
                    'priceCents':product_price(db,pack) if pack is not None else 0})
    return out


def order_view(db,row):
    items=order_items(db,int(row['id']))
    return {'id':int(row['id']),'agentId':int(row['agent']),'clientId':int(row['client']),
            'status':row['status'],'statusLabel':ORDER_STATUS_LABELS.get(row['status'],row['status']),
            'note':row['note'] or '','adminNote':row['admin_note'] or '','ts':int(row['ts']),
            'updatedTs':int(row['updated_ts'] or row['ts']),'items':items,
            'unmapped':sum(1 for i in items if i['custom']),
            'totalCents':sum(i['priceCents']*i['qty'] for i in items if not i['custom'])}


def set_order_status(db,actor,oid,status,admin_note=''):
    _require_admin(db,actor,'Buyurtma holatini faqat rahbar o‘zgartiradi.')
    if status not in ORDER_STATUSES:raise ValueError('Holat noto‘g‘ri.')
    row=db.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
    if not row:raise ValueError('Buyurtma topilmadi.')
    lock_agent(db,row['agent'])
    row=db.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
    cur=row['status']
    allowed={'new':('preparing','loaded','rejected'),'preparing':('loaded','rejected','new'),
             'loaded':('delivered',),'delivered':(),'rejected':('new',)}
    if status==cur:raise ValueError('Buyurtma allaqachon shu holatda.')
    if status not in allowed[cur]:
        raise ValueError(f"«{ORDER_STATUS_LABELS[cur]}» holatidan «{ORDER_STATUS_LABELS[status]}» ga o‘tib bo‘lmaydi.")
    note=str(admin_note or '').strip()[:500]
    if status=='rejected' and not note:raise ValueError('Rad etish sababini yozing.')
    if status=='loaded':
        items=order_items(db,oid)
        if any(i['custom'] for i in items):
            raise ValueError('Avval katalogda yo‘q mahsulotlarni katalogga qo‘shing yoki bog‘lang.')
        for idx,i in enumerate(items):
            record(db,actor,int(row['agent']),None,'load',i['pack'],i['qty'],
                   note=f'Buyurtma #{oid}',source=_order_source(f'order-load/{oid}/{idx}'),currency='USD')
    db.execute('UPDATE orders SET status=?,admin=?,admin_note=?,updated_ts=? WHERE id=?',
               (status,actor,note or (row['admin_note'] or ''),int(time.time()),oid))
    return row


def mark_order_delivered_by_agent(db,agent,client,oid,ts=None):
    row=db.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
    if not row or int(row['agent'])!=int(agent) or int(row['client'])!=int(client):
        raise ValueError('Buyurtma bu mijoz va agentga tegishli emas.')
    if row['status']!='loaded':raise ValueError('Buyurtma hali agentga berilmagan.')
    db.execute("UPDATE orders SET status='delivered',updated_ts=? WHERE id=?",(int(time.time() if ts is None else ts),oid))


def map_custom_name(db,actor,name,pack):
    """Attach every open order line typed as `name` to an existing catalog product."""
    _require_admin(db,actor,'Faqat rahbar bog‘laydi.')
    try:pack=int(pack)
    except (TypeError,ValueError):raise ValueError('Mahsulot topilmadi.')
    if pack not in PRODUCTS or pack in INACTIVE_PRODUCTS:raise ValueError('Mahsulot topilmadi yoki arxivda.')
    key=_name_key(name)
    if not key:raise ValueError('Nom bo‘sh.')
    rows=db.execute(f"""SELECT i.id,i.order_id,i.qty,i.custom_name FROM order_items i JOIN orders o ON o.id=i.order_id
        WHERE i.pack IS NULL AND o.status IN ({','.join('?' for _ in ORDER_OPEN)})""",ORDER_OPEN).fetchall()
    n=0
    for r in rows:
        if _name_key(r['custom_name'])!=key:continue
        dup=db.execute('SELECT id,qty FROM order_items WHERE order_id=? AND pack=?',(r['order_id'],pack)).fetchone()
        if dup:
            db.execute('UPDATE order_items SET qty=? WHERE id=?',(int(dup['qty'])+int(r['qty']),dup['id']))
            db.execute('DELETE FROM order_items WHERE id=?',(r['id'],))
        else:
            db.execute('UPDATE order_items SET pack=? WHERE id=?',(pack,r['id']))
        n+=1
    return n


def custom_demand(db):
    rows=db.execute(f"""SELECT i.custom_name,i.qty,o.id AS order_id,o.client,o.agent,o.ts FROM order_items i JOIN orders o ON o.id=i.order_id
        WHERE i.pack IS NULL AND o.status IN ({','.join('?' for _ in ORDER_OPEN)}) ORDER BY o.ts""",ORDER_OPEN).fetchall()
    groups={}
    for r in rows:
        key=_name_key(r['custom_name'])
        g=groups.setdefault(key,{'name':r['custom_name'],'names':set(),'qty':0,'orders':set(),'clients':set(),'agents':set(),'firstTs':int(r['ts'])})
        g['names'].add(r['custom_name']);g['qty']+=int(r['qty']);g['orders'].add(int(r['order_id']))
        g['clients'].add(int(r['client']));g['agents'].add(int(r['agent']))
    out=[{'name':g['name'],'variants':sorted(g['names']),'qty':g['qty'],'orders':len(g['orders']),
          'clients':len(g['clients']),'agents':len(g['agents']),'firstTs':g['firstTs']} for g in groups.values()]
    out.sort(key=lambda x:(-x['clients'],-x['qty']))
    return out
