"""Омбор ҳисоби: кирим, агентга бериш, агентдан қабул, брак ва сўровлар.

Омбор қолдиғи фақат warehouse_moves журналидан ҳисобланади. Агентга берилган
товар events жадвалига 'load', агентдан омборга қайтган товар 'unload' бўлиб
ёзилади, шунинг учун агент қолдиғи (core.agent_stock) ҳам автомат мос келади.
Ёзувлар ўчирилмайди ва таҳрирланмайди; хато бўлса тескари амал киритилади.
"""
import time
from core import PRODUCTS, PostgresDB, lock_agent, agent_stock, product_name, units_per_block, block_units

KEEPER_ROLES=('warehouse','admin')
MOVE_LABELS={
    'in':'📥 Кирим',
    'issue':'🚚 Агентга берилди',
    'agent_return':'↩️ Агентдан қабул',
    'writeoff':'🗑 Брак / ҳисобдан чиқариш',
}
REQUEST_LABELS={'need':'📥 Товар сўрови','return':'↩️ Омборга қайтариш'}
STATUS_LABELS={'pending':'⏳ Кутилмоқда','accepted':'✅ Қабул қилинди','rejected':'❌ Рад этилди'}

SCHEMA='''
CREATE TABLE IF NOT EXISTS warehouse_moves(id INTEGER PRIMARY KEY, actor INTEGER NOT NULL, kind TEXT NOT NULL, pack INTEGER NOT NULL, qty INTEGER NOT NULL, agent INTEGER, request INTEGER, note TEXT DEFAULT '', ts INTEGER NOT NULL, source INTEGER UNIQUE);
CREATE TABLE IF NOT EXISTS warehouse_requests(id INTEGER PRIMARY KEY, agent INTEGER NOT NULL, kind TEXT NOT NULL, pack INTEGER NOT NULL, qty INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', keeper INTEGER, note TEXT DEFAULT '', ts INTEGER NOT NULL, decided_ts INTEGER, source INTEGER UNIQUE);
CREATE INDEX IF NOT EXISTS idx_wh_moves_pack ON warehouse_moves(pack,kind);
CREATE INDEX IF NOT EXISTS idx_wh_requests_status ON warehouse_requests(status,id);
'''
PG_SCHEMA=SCHEMA.replace('INTEGER PRIMARY KEY','BIGSERIAL PRIMARY KEY').replace(' INTEGER',' BIGINT')

def init(db):
    if isinstance(db,PostgresDB):
        for stmt in PG_SCHEMA.split(';'):
            if stmt.strip():db.execute(stmt)
    else:
        db.executescript(SCHEMA)

def _role(db,uid):
    row=db.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
    return row[0] if row else None

def _require_keeper(db,actor):
    if _role(db,actor) not in KEEPER_ROLES:
        raise ValueError('Бу амал фақат омборчи ёки админ учун.')

def _check_item(pack,qty):
    if pack not in PRODUCTS:raise ValueError('Товар нотўғри.')
    if not isinstance(qty,int) or not 0<qty<=100000:raise ValueError('Миқдор 1 дан 100000 гача бўлсин.')

def _check_agent(db,agent):
    if _role(db,agent)!='agent':raise ValueError('Агент топилмади.')

def _lock_warehouse(db):
    # Serialize every warehouse balance change across PostgreSQL connections.
    if isinstance(db,PostgresDB):
        db.execute("INSERT INTO meta(key,value) VALUES('warehouse_lock','1') ON CONFLICT(key) DO NOTHING")
        db.execute("SELECT value FROM meta WHERE key='warehouse_lock' FOR UPDATE").fetchone()

def _seen(db,source):
    return source is not None and db.execute('SELECT 1 FROM warehouse_moves WHERE source=?',(source,)).fetchone() is not None

def to_units(pack,qty,unit='Дона'):
    # units_per_block raises a clear error when the product has no block size.
    return qty*(units_per_block(pack) if unit=='Блок' else 1)

def stock(db,pack):
    row=db.execute("""SELECT COALESCE(SUM(CASE WHEN kind IN ('in','agent_return') THEN qty
        WHEN kind IN ('issue','writeoff') THEN -qty ELSE 0 END),0)
        FROM warehouse_moves WHERE pack=?""",(pack,)).fetchone()
    return int(row[0] or 0)

def stock_all(db):
    return {p:stock(db,p) for p in PRODUCTS}

def reserved_return(db,agent,pack):
    row=db.execute("""SELECT COALESCE(SUM(qty),0) FROM warehouse_requests
        WHERE agent=? AND pack=? AND kind='return' AND status='pending'""",(agent,pack)).fetchone()
    return int(row[0] or 0)

def _move(db,actor,kind,pack,qty,agent=None,request=None,note='',source=None):
    cur=db.execute('''INSERT INTO warehouse_moves(actor,kind,pack,qty,agent,request,note,ts,source)
        VALUES(?,?,?,?,?,?,?,?,?) RETURNING id''',(actor,kind,pack,qty,agent,request,note or '',int(time.time()),source))
    return int(cur.fetchone()[0])

def receive(db,actor,pack,qty,note='',source=None):
    """Ишлаб чиқариш ёки харид ҳисобидан омборга кирим."""
    _require_keeper(db,actor);_check_item(pack,qty)
    _lock_warehouse(db)
    if _seen(db,source):return None
    return _move(db,actor,'in',pack,qty,note=note,source=source)

def write_off(db,actor,pack,qty,note,source=None):
    _require_keeper(db,actor);_check_item(pack,qty)
    if not (note or '').strip():raise ValueError('Брак сабабини ёзинг.')
    _lock_warehouse(db)
    if _seen(db,source):return None
    if stock(db,pack)<qty:raise ValueError(f'Омборда {product_name(pack)} етарли эмас.')
    return _move(db,actor,'writeoff',pack,qty,note=note,source=source)

def issue(db,actor,agent,pack,qty,note='',source=None,request=None):
    """Омбордан агентга товар бериш: омбор камаяди, агентда 'load' пайдо бўлади."""
    _require_keeper(db,actor);_check_item(pack,qty);_check_agent(db,agent)
    lock_agent(db,agent);_lock_warehouse(db)
    if _seen(db,source):return None
    if stock(db,pack)<qty:
        raise ValueError(f'Омборда {product_name(pack)} етарли эмас: {stock(db,pack)} дона бор.')
    move=_move(db,actor,'issue',pack,qty,agent=agent,request=request,note=note,source=source)
    db.execute('''INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
        VALUES(?,?,NULL,'load',?,?,0,0,?,?,NULL)''',(actor,agent,pack,qty,f'Омбор #{move}'+(f' | {note}' if note else ''),int(time.time())))
    return move

def _accept_return(db,actor,agent,pack,qty,request,note=''):
    lock_agent(db,agent);_lock_warehouse(db)
    if agent_stock(db,agent,pack)<qty:raise ValueError('Агентда қайтариладиган товар етарли эмас.')
    move=_move(db,actor,'agent_return',pack,qty,agent=agent,request=request,note=note)
    db.execute('''INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
        VALUES(?,?,NULL,'unload',?,?,0,0,?,?,NULL)''',(actor,agent,pack,qty,f'Омборга қайтди #{move}',int(time.time())))
    return move

def create_request(db,agent,kind,pack,qty,note='',source=None):
    """Агент сўрови: 'need' — омбордан товар, 'return' — омборга қайтариш."""
    _check_agent(db,agent);_check_item(pack,qty)
    if kind not in REQUEST_LABELS:raise ValueError('Сўров тури нотўғри.')
    lock_agent(db,agent)
    if source is not None:
        old=db.execute('SELECT id FROM warehouse_requests WHERE source=?',(source,)).fetchone()
        if old:return int(old[0])
    if kind=='return':
        free=agent_stock(db,agent,pack)-reserved_return(db,agent,pack)
        if free<qty:raise ValueError(f'Қўлингизда {product_name(pack)}дан {max(free,0)} дона эркин қолдиқ бор.')
    cur=db.execute('''INSERT INTO warehouse_requests(agent,kind,pack,qty,note,ts,source)
        VALUES(?,?,?,?,?,?,?) RETURNING id''',(agent,kind,pack,qty,note or '',int(time.time()),source))
    return int(cur.fetchone()[0])

def decide(db,actor,request_id,accepted=True,qty=None):
    """Омборчи сўровни қабул ёки рад қилади. Товар сўровида миқдорни камайтириш мумкин."""
    _require_keeper(db,actor)
    row=db.execute("SELECT * FROM warehouse_requests WHERE id=? AND status='pending'",(request_id,)).fetchone()
    if not row:raise ValueError('Сўров топилмади ёки аввал ҳал қилинган.')
    lock_agent(db,row['agent']);_lock_warehouse(db)
    row=db.execute("SELECT * FROM warehouse_requests WHERE id=? AND status='pending'",(request_id,)).fetchone()
    if not row:raise ValueError('Бу сўров аввал ҳал қилинган.')
    final=int(row['qty'])
    if accepted:
        if qty is not None:
            if row['kind']!='need':raise ValueError('Қайтаришда миқдор ўзгартирилмайди.')
            _check_item(int(row['pack']),qty)
            if qty>final:raise ValueError('Сўралгандан кўп бериб бўлмайди.')
            final=qty
        if row['kind']=='need':
            issue(db,actor,int(row['agent']),int(row['pack']),final,note=f'Сўров #{request_id}',request=request_id)
        else:
            _accept_return(db,actor,int(row['agent']),int(row['pack']),final,request_id)
    db.execute('UPDATE warehouse_requests SET status=?,keeper=?,qty=?,decided_ts=? WHERE id=?',
               ('accepted' if accepted else 'rejected',actor,final,int(time.time()),request_id))
    return {'id':int(row['id']),'agent':int(row['agent']),'kind':row['kind'],'pack':int(row['pack']),
            'qty':final,'requested':int(row['qty']),'accepted':accepted}

def pending_requests(db,limit=50):
    return db.execute("""SELECT r.*,u.name AS agent_name FROM warehouse_requests r
        LEFT JOIN users u ON u.id=r.agent WHERE r.status='pending' ORDER BY r.id LIMIT ?""",(limit,)).fetchall()

def recent_moves(db,limit=30):
    return db.execute("""SELECT m.*,ua.name AS agent_name,uk.name AS actor_name FROM warehouse_moves m
        LEFT JOIN users ua ON ua.id=m.agent LEFT JOIN users uk ON uk.id=m.actor
        ORDER BY m.id DESC LIMIT ?""",(limit,)).fetchall()

def agent_requests(db,agent,limit=10):
    return db.execute('SELECT * FROM warehouse_requests WHERE agent=? ORDER BY id DESC LIMIT ?',(agent,limit)).fetchall()

def snapshot(db,actor):
    """Омборчи иловаси учун бутун ҳолат (фақат ўқиш)."""
    _require_keeper(db,actor)
    agents=db.execute("SELECT id,name FROM users WHERE role='agent' ORDER BY name").fetchall()
    today=int(time.time())-24*3600
    totals=db.execute("""SELECT kind,COALESCE(SUM(qty),0) FROM warehouse_moves WHERE ts>=? GROUP BY kind""",(today,)).fetchall()
    return {
        'me':{'id':actor,'role':_role(db,actor),
              'name':(db.execute('SELECT name FROM users WHERE id=?',(actor,)).fetchone() or [''])[0]},
        'products':[{'pack':p,'name':name,'block':block_units(p) or 0,'stock':stock(db,p)} for p,name in PRODUCTS.items()],
        'agents':[{'id':int(a['id']),'name':a['name'],
                   'stock':{str(p):agent_stock(db,a['id'],p) for p in PRODUCTS}} for a in agents],
        'requests':[{'id':int(r['id']),'agent':int(r['agent']),'agent_name':r['agent_name'] or str(r['agent']),
                     'kind':r['kind'],'pack':int(r['pack']),'qty':int(r['qty']),'note':r['note'] or '',
                     'ts':int(r['ts'])} for r in pending_requests(db)],
        'moves':[{'id':int(m['id']),'kind':m['kind'],'pack':int(m['pack']),'qty':int(m['qty']),
                  'agent_name':m['agent_name'] or '','actor_name':m['actor_name'] or '',
                  'note':m['note'] or '','ts':int(m['ts'])} for m in recent_moves(db,40)],
        'today':{k:int(v) for k,v in totals},
    }

def report_text(db):
    lines=['🏬 ОМБОР ҚОЛДИҒИ']
    for p,name in PRODUCTS.items():
        n=stock(db,p);block=block_units(p)
        # Some catalog items (emulsions) have no block size: show pieces only.
        lines.append(f'{name}: {n} дона ({n//block} блок + {n%block} дона)' if block else f'{name}: {n} дона')
    pending=pending_requests(db,20)
    if pending:
        lines.append('\n⏳ КУТАЁТГАН СЎРОВЛАР')
        for r in pending:
            lines.append(f"#{r['id']} · {REQUEST_LABELS[r['kind']]} · {r['agent_name'] or r['agent']} · "
                         f"{product_name(r['pack'])} {r['qty']} дона")
    moves=recent_moves(db,10)
    if moves:
        lines.append('\n🧾 ОХИРГИ ҲАРАКАТЛАР')
        for m in moves:
            who=f" · {m['agent_name']}" if m['agent_name'] else ''
            lines.append(f"#{m['id']} {MOVE_LABELS[m['kind']]}{who} · {product_name(m['pack'])} {m['qty']} дона")
    return '\n'.join(lines)
