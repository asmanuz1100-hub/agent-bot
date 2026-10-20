"""Омбор ҳисоби: кирим, агентга бериш, агентдан қабул, брак ва сўровлар.

Омбор қолдиғи фақат warehouse_moves журналидан ҳисобланади. Агентга берилган
товар events жадвалига 'load', агентдан омборга қайтган товар 'unload' бўлиб
ёзилади, шунинг учун агент қолдиғи (core.agent_stock) ҳам автомат мос келади.
Ёзувлар ўчирилмайди ва таҳрирланмайди; хато бўлса тескари амал киритилади.
"""
import hashlib
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from core import PRODUCTS, PostgresDB, lock_agent, agent_stock, product_name, units_per_block, block_units

TZ=ZoneInfo('Asia/Tashkent')

KEEPER_ROLES=('warehouse','admin')   # Ombor panelini ko‘radi
OPERATOR_ROLES=('warehouse',)        # tovar harakatini faqat omborchi kiritadi
# Istisno: asosiy rahbar web panel orqali (bot shu so'rov davomida ID ni o'rnatadi). Telegram bot/Mini App'ga ta'sir qilmaydi.
import contextvars
WEB_PRIMARY_OPERATOR=contextvars.ContextVar('web_primary_operator',default=None)
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
    reset_agent_stock_once(db)

STOCK_RESET_KEY='agent_stock_reset_v1'

def reset_agent_stock_once(db,now=None):
    """Yangi qoida: agent faqat ombordan olgan tovarini topshiradi. Ishga tushganda eski
    (tarixdan hisoblangan, minus bo‘lishi mumkin) qoldiq bir marta 0 ga tushiriladi.

    Har agent/mahsulot uchun teskari 'adjust' yozuvi qo‘shiladi; mijoz qarzi, to‘lovlar va
    hisobotlar o‘zgarmaydi. Meta kalit faqat bir marta yoziladi (bir nechta instance xavfsiz)."""
    from core import agent_stock_map
    claimed=db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO NOTHING RETURNING key",
                       (STOCK_RESET_KEY,str(int(time.time() if now is None else now)))).fetchone()
    if not claimed:return 0
    ts=int(time.time() if now is None else now);n=0
    for (agent,) in db.execute("SELECT DISTINCT agent FROM events WHERE agent IS NOT NULL").fetchall():
        for pack,qty in agent_stock_map(db,int(agent)).items():
            if qty:
                db.execute('''INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
                    VALUES(?,?,NULL,'adjust',?,?,0,0,?,?,NULL)''',
                           (int(agent),int(agent),pack,-qty,f'Qoldiq 0 ga tushirildi (eski: {qty} dona)',ts))
                n+=1
    return n

def _role(db,uid):
    row=db.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
    return row[0] if row else None

def _require_keeper(db,actor):
    if _role(db,actor) not in KEEPER_ROLES:
        raise ValueError('Bu bo‘lim faqat omborchi yoki rahbar uchun.')

def _require_operator(db,actor):
    if _role(db,actor)=='admin' and WEB_PRIMARY_OPERATOR.get()==actor:return
    if _role(db,actor) not in OPERATOR_ROLES:
        raise ValueError('Tovar harakatini faqat omborchi kiritadi. Rahbar ombor panelini faqat ko‘radi.')

def _check_item(pack,qty):
    if pack not in PRODUCTS:raise ValueError('Mahsulot noto‘g‘ri.')
    if not isinstance(qty,int) or not 0<qty<=100000:raise ValueError('Miqdor 1 dan 100000 gacha bo‘lsin.')

def _check_agent(db,agent):
    if _role(db,agent)!='agent':raise ValueError('Agent topilmadi.')

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
    _require_operator(db,actor);_check_item(pack,qty)
    _lock_warehouse(db)
    if _seen(db,source):return None
    return _move(db,actor,'in',pack,qty,note=note,source=source)

def write_off(db,actor,pack,qty,note,source=None):
    _require_operator(db,actor);_check_item(pack,qty)
    if not (note or '').strip():raise ValueError('Brak sababini yozing.')
    _lock_warehouse(db)
    if _seen(db,source):return None
    if stock(db,pack)<qty:raise ValueError(f'Omborda {product_name(pack)} yetarli emas: {stock(db,pack)} dona bor.')
    return _move(db,actor,'writeoff',pack,qty,note=note,source=source)

def issue(db,actor,agent,pack,qty,note='',source=None,request=None):
    """Омбордан агентга товар бериш: омбор камаяди, агентда 'load' пайдо бўлади."""
    _require_operator(db,actor);_check_item(pack,qty);_check_agent(db,agent)
    lock_agent(db,agent);_lock_warehouse(db)
    if _seen(db,source):return None
    if stock(db,pack)<qty:
        raise ValueError(f'Omborda {product_name(pack)} yetarli emas: {stock(db,pack)} dona bor.')
    move=_move(db,actor,'issue',pack,qty,agent=agent,request=request,note=note,source=source)
    db.execute('''INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
        VALUES(?,?,NULL,'load',?,?,0,0,?,?,NULL)''',(actor,agent,pack,qty,f'Омбор #{move}'+(f' | {note}' if note else ''),int(time.time())))
    return move

def _accept_return(db,actor,agent,pack,qty,request,note='',source=None):
    lock_agent(db,agent);_lock_warehouse(db)
    if agent_stock(db,agent,pack)<qty:raise ValueError('Agentda qaytariladigan tovar yetarli emas.')
    move=_move(db,actor,'agent_return',pack,qty,agent=agent,request=request,note=note,source=source)
    db.execute('''INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
        VALUES(?,?,NULL,'unload',?,?,0,0,?,?,NULL)''',(actor,agent,pack,qty,f'Омборга қайтди #{move}',int(time.time())))
    return move

def take_back(db,actor,agent,pack,qty,note='',source=None):
    """Агент товарни ўзи олиб келди: сўровсиз омборга қабул (кутаётган қайтариш сўровлари ҳисобга олинади)."""
    _require_operator(db,actor);_check_item(pack,qty);_check_agent(db,agent)
    lock_agent(db,agent);_lock_warehouse(db)
    if _seen(db,source):return None
    free=agent_stock(db,agent,pack)-reserved_return(db,agent,pack)
    if free<qty:raise ValueError(f'Agentda {product_name(pack)} bo‘yicha {max(free,0)} dona erkin qoldiq bor.')
    return _accept_return(db,actor,agent,pack,qty,None,note,source)

def _order_move_source(oid,idx):
    return -(int.from_bytes(hashlib.sha256(f'order-wh/{oid}/{idx}'.encode()).digest()[:7],'big')*16+11)

def issue_order(db,actor,oid,agent,lines):
    """Буюртма агентга берилганда: омбор камаяди, агентда 'load' пайдо бўлади.

    lines=[(pack,qty,event_source)]; омборда бирорта товар етмаса, ҳеч нарса ёзилмайди.
    """
    lock_agent(db,agent);_lock_warehouse(db)
    need={}
    for pack,qty,_ in lines:need[pack]=need.get(pack,0)+qty
    short=[f'{product_name(p)}: kerak {q}, omborda {stock(db,p)}' for p,q in need.items() if stock(db,p)<q]
    if short:raise ValueError('Omborda tovar yetarli emas — '+'; '.join(short)+'. Avval kirim qiling.')
    now=int(time.time());moves=[]
    for idx,(pack,qty,event_source) in enumerate(lines):
        source=_order_move_source(oid,idx)
        if _seen(db,source):continue
        moves.append(_move(db,actor,'issue',pack,qty,agent=agent,note=f'Buyurtma #{oid}',source=source))
        db.execute('''INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
            VALUES(?,?,NULL,'load',?,?,0,0,?,?,?)''',(actor,agent,pack,qty,f'Buyurtma #{oid}',now,event_source))
    return moves

def create_request(db,agent,kind,pack,qty,note='',source=None):
    """Агент сўрови: 'need' — омбордан товар, 'return' — омборга қайтариш."""
    _check_agent(db,agent);_check_item(pack,qty)
    if kind not in REQUEST_LABELS:raise ValueError('So‘rov turi noto‘g‘ri.')
    lock_agent(db,agent)
    if source is not None:
        old=db.execute('SELECT id FROM warehouse_requests WHERE source=?',(source,)).fetchone()
        if old:return int(old[0])
    if kind=='return':
        free=agent_stock(db,agent,pack)-reserved_return(db,agent,pack)
        if free<qty:raise ValueError(f'Qo‘lingizda {product_name(pack)} bo‘yicha {max(free,0)} dona erkin qoldiq bor.')
    cur=db.execute('''INSERT INTO warehouse_requests(agent,kind,pack,qty,note,ts,source)
        VALUES(?,?,?,?,?,?,?) RETURNING id''',(agent,kind,pack,qty,note or '',int(time.time()),source))
    return int(cur.fetchone()[0])

def decide(db,actor,request_id,accepted=True,qty=None):
    """Омборчи сўровни қабул ёки рад қилади. Товар сўровида миқдорни камайтириш мумкин."""
    _require_operator(db,actor)
    row=db.execute("SELECT * FROM warehouse_requests WHERE id=? AND status='pending'",(request_id,)).fetchone()
    if not row:raise ValueError('So‘rov topilmadi yoki avval hal qilingan.')
    lock_agent(db,row['agent']);_lock_warehouse(db)
    row=db.execute("SELECT * FROM warehouse_requests WHERE id=? AND status='pending'",(request_id,)).fetchone()
    if not row:raise ValueError('Bu so‘rov avval hal qilingan.')
    final=int(row['qty'])
    if accepted:
        if qty is not None:
            if row['kind']!='need':raise ValueError('Qaytarishda miqdor o‘zgartirilmaydi.')
            _check_item(int(row['pack']),qty)
            if qty>final:raise ValueError('So‘ralgandan ko‘p berib bo‘lmaydi.')
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

def recent_moves(db,limit=30,kind=None,pack=None,agent=None,before=None):
    where,args=[],[]
    if kind:where.append('m.kind=?');args.append(kind)
    if pack is not None:where.append('m.pack=?');args.append(pack)
    if agent is not None:where.append('m.agent=?');args.append(agent)
    if before is not None:where.append('m.id<?');args.append(before)
    sql=("""SELECT m.*,ua.name AS agent_name,uk.name AS actor_name FROM warehouse_moves m
        LEFT JOIN users ua ON ua.id=m.agent LEFT JOIN users uk ON uk.id=m.actor"""
         +(' WHERE '+' AND '.join(where) if where else '')+' ORDER BY m.id DESC LIMIT ?')
    return db.execute(sql,(*args,limit)).fetchall()

def move_view(m):
    return {'id':int(m['id']),'kind':m['kind'],'pack':int(m['pack']),'qty':int(m['qty']),
            'agent':int(m['agent']) if m['agent'] is not None else None,
            'agent_name':m['agent_name'] or '','actor_name':m['actor_name'] or '',
            'note':m['note'] or '','ts':int(m['ts'])}

def day_start(now=None):
    d=datetime.fromtimestamp(time.time() if now is None else now,TZ)
    return int(d.replace(hour=0,minute=0,second=0,microsecond=0).timestamp())

def month_start(now=None):
    d=datetime.fromtimestamp(time.time() if now is None else now,TZ)
    return int(d.replace(day=1,hour=0,minute=0,second=0,microsecond=0).timestamp())

def manager_summary(db,now=None):
    """Rahbar uchun: ombor qoldig‘i va agentlarga chiqqan tovar (bugun / shu oy)."""
    day,month=day_start(now),month_start(now)
    issued={}
    for r in db.execute("""SELECT pack,COALESCE(SUM(CASE WHEN ts>=? THEN qty ELSE 0 END),0),COALESCE(SUM(qty),0)
        FROM warehouse_moves WHERE kind='issue' AND ts>=? GROUP BY pack""",(day,month)).fetchall():
        issued[int(r[0])]=(int(r[1] or 0),int(r[2] or 0))
    totals=dict(db.execute("""SELECT kind,COALESCE(SUM(qty),0) FROM warehouse_moves WHERE ts>=? GROUP BY kind""",(month,)).fetchall())
    products=[]
    for p,name in PRODUCTS.items():
        n=stock(db,p);t,m=issued.get(p,(0,0))
        if n or t or m:
            products.append({'pack':p,'name':name,'block':block_units(p) or 0,'stock':n,'issuedToday':t,'issuedMonth':m})
    products.sort(key=lambda x:(-x['issuedMonth'],-x['stock'],x['pack']))
    return {'stockTotal':sum(max(x['stock'],0) for x in products),
            'issuedToday':sum(x['issuedToday'] for x in products),'issuedMonth':sum(x['issuedMonth'] for x in products),
            'returnedMonth':int(totals.get('agent_return',0) or 0),'writeoffMonth':int(totals.get('writeoff',0) or 0),
            'receivedMonth':int(totals.get('in',0) or 0),'products':products}

def open_order_demand(db):
    """Янги ва тайёрланаётган буюртмаларда ҳар товардан қанча керак."""
    rows=db.execute("""SELECT i.pack,COALESCE(SUM(i.qty),0) FROM order_items i JOIN orders o ON o.id=i.order_id
        WHERE i.pack IS NOT NULL AND o.status IN ('new','preparing') GROUP BY i.pack""").fetchall()
    return {int(r[0]):int(r[1]) for r in rows}

def agent_requests(db,agent,limit=10):
    return db.execute('SELECT * FROM warehouse_requests WHERE agent=? ORDER BY id DESC LIMIT ?',(agent,limit)).fetchall()

def snapshot(db,actor):
    """Омборчи иловаси учун бутун ҳолат (фақат ўқиш)."""
    _require_keeper(db,actor)
    agents=db.execute("SELECT id,name FROM users WHERE role='agent' ORDER BY name").fetchall()
    totals=db.execute("""SELECT kind,COALESCE(SUM(qty),0) FROM warehouse_moves WHERE ts>=? GROUP BY kind""",(day_start(),)).fetchall()
    demand=open_order_demand(db)
    return {
        'me':{'id':actor,'role':_role(db,actor),
              'name':(db.execute('SELECT name FROM users WHERE id=?',(actor,)).fetchone() or [''])[0]},
        'products':[{'pack':p,'name':name,'block':block_units(p) or 0,'stock':stock(db,p),'demand':demand.get(p,0)}
                    for p,name in PRODUCTS.items()],
        'agents':[{'id':int(a['id']),'name':a['name'],
                   'stock':{str(p):agent_stock(db,a['id'],p) for p in PRODUCTS}} for a in agents],
        'requests':[{'id':int(r['id']),'agent':int(r['agent']),'agent_name':r['agent_name'] or str(r['agent']),
                     'kind':r['kind'],'pack':int(r['pack']),'qty':int(r['qty']),'note':r['note'] or '',
                     'ts':int(r['ts'])} for r in pending_requests(db)],
        'moves':[move_view(m) for m in recent_moves(db,40)],
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
