"""Таъминот: таъминотчилар, харид, хом ашё омбори ва ишлаб чиқариш.

- Харид қаторлари тайёр маҳсулот (pack) ёки хом ашё (material) бўлиши мумкин.
  Маҳсулот warehouse.receive орқали омборга 'in' бўлиб тушади, хом ашё эса
  material_moves журналига 'in' бўлиб ёзилади. Харид суммаси таъминотчига
  бўлган қарзимизга қўшилади.
- Таъминотчига тўлов касса харажати (core.add_cashier_expense) бўлиб ёзилади ва
  қарзни камайтиради.
- Ишлаб чиқариш: хом ашё сарфланади ('use') ва тайёр маҳсулот омборга киради.

Пул суммалари бошқа модуллардаги каби USD центда. Хом ашё миқдори минг улушда
(qty_milli: 1 кг = 1000), шунда 2.5 кг аниқ сақланади.
Ёзувлар ўчирилмайди ва таҳрирланмайди; хато бўлса тескари амал киритилади.
"""
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import core
from core import PostgresDB, product_name
import warehouse as wh

SUPPLIER_PAY_CATEGORY='🏭 Таъминотчига тўлов'
MATERIAL_UNITS={'kg':'kg','l':'litr','dona':'dona','m':'metr','qop':'qop'}
MATERIAL_MOVES={'in':'Kirim','use':'Ishlab chiqarishga','writeoff':'Brak / hisobdan chiqarish'}
MAX_LINES=30
MAX_QTY_MILLI=10**10           # 10 mln kg
MAX_TOTAL_USD=10**10           # 100 mln USD (centda): noto'g'ri kiritishdan himoya

SCHEMA='''
CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, actor INTEGER NOT NULL, ts INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS materials(id INTEGER PRIMARY KEY, name TEXT NOT NULL, unit TEXT NOT NULL, min_milli INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1, actor INTEGER NOT NULL, ts INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY, supplier INTEGER NOT NULL, actor INTEGER NOT NULL, total_usd INTEGER NOT NULL CHECK(total_usd>=0), note TEXT NOT NULL DEFAULT '', ts INTEGER NOT NULL, source INTEGER UNIQUE);
CREATE TABLE IF NOT EXISTS purchase_lines(id INTEGER PRIMARY KEY, purchase INTEGER NOT NULL, pack INTEGER, material INTEGER, qty INTEGER NOT NULL CHECK(qty>0), price_usd INTEGER NOT NULL CHECK(price_usd>=0), total_usd INTEGER NOT NULL CHECK(total_usd>=0), move INTEGER);
CREATE TABLE IF NOT EXISTS supplier_payments(id INTEGER PRIMARY KEY, supplier INTEGER NOT NULL, actor INTEGER NOT NULL, amount_usd INTEGER NOT NULL CHECK(amount_usd>0), expense INTEGER, pay_from TEXT NOT NULL DEFAULT 'cash', note TEXT NOT NULL DEFAULT '', ts INTEGER NOT NULL, source INTEGER UNIQUE);
CREATE TABLE IF NOT EXISTS material_moves(id INTEGER PRIMARY KEY, material INTEGER NOT NULL, kind TEXT NOT NULL, qty_milli INTEGER NOT NULL CHECK(qty_milli>0), actor INTEGER NOT NULL, purchase INTEGER, production INTEGER, note TEXT NOT NULL DEFAULT '', ts INTEGER NOT NULL, source INTEGER UNIQUE);
CREATE TABLE IF NOT EXISTS productions(id INTEGER PRIMARY KEY, pack INTEGER NOT NULL, qty INTEGER NOT NULL CHECK(qty>0), move INTEGER, actor INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', ts INTEGER NOT NULL, source INTEGER UNIQUE);
CREATE INDEX IF NOT EXISTS idx_purchases_supplier ON purchases(supplier,ts);
CREATE INDEX IF NOT EXISTS idx_purchase_lines_purchase ON purchase_lines(purchase);
CREATE INDEX IF NOT EXISTS idx_supplier_payments_supplier ON supplier_payments(supplier,ts);
CREATE INDEX IF NOT EXISTS idx_material_moves_material ON material_moves(material,kind);
'''
PG_SCHEMA=SCHEMA.replace('INTEGER PRIMARY KEY','BIGSERIAL PRIMARY KEY').replace(' INTEGER',' BIGINT')


def init(db):
    if isinstance(db,PostgresDB):
        for stmt in PG_SCHEMA.split(';'):
            if stmt.strip():db.execute(stmt)
    else:
        db.executescript(SCHEMA)


# ---------- yordamchilar ----------

def _role(db,uid):
    row=db.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
    return row[0] if row else None


def _require_viewer(db,actor):
    if _role(db,actor) not in ('warehouse','admin','cashier','production'):
        raise ValueError('Bu bo‘lim faqat omborchi, kassir yoki rahbar uchun.')


def _require_operator(db,actor):
    if _role(db,actor) not in ('warehouse','admin'):
        raise ValueError('Xarid va xom ashyo harakatini faqat omborchi yoki rahbar kiritadi.')


def _lock(db):
    # Barcha ta'minot yozuvlarini PostgreSQL ulanishlari orasida ketma-ket qiladi.
    if isinstance(db,PostgresDB):
        db.execute("INSERT INTO meta(key,value) VALUES('purchases_lock','1') ON CONFLICT(key) DO NOTHING")
        db.execute("SELECT value FROM meta WHERE key='purchases_lock' FOR UPDATE").fetchone()


def _text(value,label,limit,required=False):
    text=str(value or '').strip()
    if len(text)>limit:raise ValueError(f'{label} {limit} belgidan oshmasin.')
    if required and not text:raise ValueError(f'{label}ni kiriting.')
    return text


def _int(value,label,lo=1,hi=10**12):
    if isinstance(value,bool):raise ValueError(f'{label} noto‘g‘ri.')
    try:n=int(str(value).strip())
    except (TypeError,ValueError):raise ValueError(f'{label} noto‘g‘ri.')
    if not lo<=n<=hi:raise ValueError(f'{label} noto‘g‘ri.')
    return n


def _decimal(value,label):
    try:n=Decimal(str(value).replace(' ','').replace(',','.'))
    except (InvalidOperation,ValueError):raise ValueError(f'{label} noto‘g‘ri.')
    if not n.is_finite():raise ValueError(f'{label} noto‘g‘ri.')
    return n


def parse_milli(value,label='Miqdor'):
    """'2.5' -> 2500. Ko'pi bilan 3 kasr xona."""
    n=_decimal(value,label)*1000
    if n!=n.to_integral_value() or not 0<n<=MAX_QTY_MILLI:
        raise ValueError(f'{label}: musbat son kiriting (ko‘pi bilan 3 kasr xona).')
    return int(n)


def parse_cents(value,label='Narx',allow_zero=True):
    n=_decimal(value,label)*100
    if n!=n.to_integral_value() or n<0 or (n==0 and not allow_zero) or n>MAX_TOTAL_USD:
        raise ValueError(f'{label}: musbat summa kiriting (ko‘pi bilan 2 kasr xona).')
    return int(n)


def milli_text(milli):
    s=f'{Decimal(milli)/1000:f}'
    if '.' in s:s=s.rstrip('0').rstrip('.')
    return s


def _supplier(db,sid):
    row=db.execute('SELECT * FROM suppliers WHERE id=?',(sid,)).fetchone()
    if not row:raise ValueError('Ta’minotchi topilmadi.')
    return row


def _material(db,mid):
    row=db.execute('SELECT * FROM materials WHERE id=?',(mid,)).fetchone()
    if not row:raise ValueError('Xom ashyo topilmadi.')
    return row


def _seen(db,table,source):
    if source is None:return None
    row=db.execute(f'SELECT id FROM {table} WHERE source=?',(source,)).fetchone()
    return int(row[0]) if row else None


class _AsOperator:
    """Rahbar ham ombor kirimini qila olsin: warehouse.receive faqat shu chaqiruv davomida ruxsat beradi."""
    def __init__(self,db,actor):self.on=_role(db,actor)=='admin';self.actor=actor
    def __enter__(self):self.tok=wh.WEB_PRIMARY_OPERATOR.set(self.actor) if self.on else None
    def __exit__(self,*a):
        if self.tok is not None:wh.WEB_PRIMARY_OPERATOR.reset(self.tok)


# ---------- ta'minotchi ----------

def add_supplier(db,actor,name,phone='',note=''):
    _require_operator(db,actor)
    name=_text(name,'Ta’minotchi nomi',120,required=True)
    phone=_text(phone,'Telefon',40);note=_text(note,'Izoh',300)
    _lock(db)
    if db.execute('SELECT 1 FROM suppliers WHERE LOWER(name)=LOWER(?) AND active=1',(name,)).fetchone():
        raise ValueError('Bu nomli ta’minotchi allaqachon bor.')
    return int(db.execute('INSERT INTO suppliers(name,phone,note,actor,ts) VALUES(?,?,?,?,?) RETURNING id',
                          (name,phone,note,actor,int(time.time()))).fetchone()[0])


def update_supplier(db,actor,sid,name,phone='',note=''):
    _require_operator(db,actor);_supplier(db,sid)
    name=_text(name,'Ta’minotchi nomi',120,required=True)
    phone=_text(phone,'Telefon',40);note=_text(note,'Izoh',300)
    if db.execute('SELECT 1 FROM suppliers WHERE LOWER(name)=LOWER(?) AND active=1 AND id<>?',(name,sid)).fetchone():
        raise ValueError('Bu nomli ta’minotchi allaqachon bor.')
    db.execute('UPDATE suppliers SET name=?,phone=?,note=? WHERE id=?',(name,phone,note,sid))


def balance(db,sid):
    """Ta'minotchiga qarzimiz (USD cent). Musbat = biz qarzdormiz."""
    bought=db.execute('SELECT COALESCE(SUM(total_usd),0) FROM purchases WHERE supplier=?',(sid,)).fetchone()[0]
    paid=db.execute('SELECT COALESCE(SUM(amount_usd),0) FROM supplier_payments WHERE supplier=?',(sid,)).fetchone()[0]
    return int(bought or 0)-int(paid or 0)


# ---------- xom ashyo ----------

def add_material(db,actor,name,unit,min_qty=None):
    _require_operator(db,actor)
    name=_text(name,'Xom ashyo nomi',120,required=True)
    if unit not in MATERIAL_UNITS:raise ValueError('O‘lchov birligini tanlang.')
    min_milli=0 if min_qty in (None,'') else parse_milli(min_qty,'Minimal qoldiq')
    _lock(db)
    if db.execute('SELECT 1 FROM materials WHERE LOWER(name)=LOWER(?) AND active=1',(name,)).fetchone():
        raise ValueError('Bu nomli xom ashyo allaqachon bor.')
    return int(db.execute('INSERT INTO materials(name,unit,min_milli,actor,ts) VALUES(?,?,?,?,?) RETURNING id',
                          (name,unit,min_milli,actor,int(time.time()))).fetchone()[0])


def update_material(db,actor,mid,name,min_qty=None):
    _require_operator(db,actor);_material(db,mid)
    name=_text(name,'Xom ashyo nomi',120,required=True)
    min_milli=0 if min_qty in (None,'') else parse_milli(min_qty,'Minimal qoldiq')
    if db.execute('SELECT 1 FROM materials WHERE LOWER(name)=LOWER(?) AND active=1 AND id<>?',(name,mid)).fetchone():
        raise ValueError('Bu nomli xom ashyo allaqachon bor.')
    db.execute('UPDATE materials SET name=?,min_milli=? WHERE id=?',(name,min_milli,mid))


def material_stock(db,mid):
    row=db.execute("""SELECT COALESCE(SUM(CASE WHEN kind='in' THEN qty_milli ELSE -qty_milli END),0)
        FROM material_moves WHERE material=?""",(mid,)).fetchone()
    return int(row[0] or 0)


def _material_move(db,actor,mid,kind,qty_milli,note='',purchase=None,production=None,source=None):
    return int(db.execute('''INSERT INTO material_moves(material,kind,qty_milli,actor,purchase,production,note,ts,source)
        VALUES(?,?,?,?,?,?,?,?,?) RETURNING id''',(mid,kind,qty_milli,actor,purchase,production,note or '',int(time.time()),source)).fetchone()[0])


def _take_material(db,actor,mid,qty_milli,kind,note,production=None,source=None):
    m=_material(db,mid)
    have=material_stock(db,mid)
    if qty_milli>have:
        raise ValueError(f"Omborda {m['name']} yetarli emas: {milli_text(have)} {MATERIAL_UNITS[m['unit']]} bor.")
    return _material_move(db,actor,mid,kind,qty_milli,note,production=production,source=source)


def material_writeoff(db,actor,mid,qty_milli,note,source=None):
    _require_operator(db,actor)
    note=_text(note,'Sabab',300,required=True)
    _lock(db)
    if _seen(db,'material_moves',source):return _seen(db,'material_moves',source)
    return _take_material(db,actor,mid,qty_milli,'writeoff',note,source=source)


def material_use(db,actor,mid,qty_milli,note='',source=None):
    """Mahsulotga bog'lanmagan sarf (masalan sinov, tozalash)."""
    _require_operator(db,actor)
    note=_text(note,'Izoh',300)
    _lock(db)
    if _seen(db,'material_moves',source):return _seen(db,'material_moves',source)
    return _take_material(db,actor,mid,qty_milli,'use',note,source=source)


# ---------- xarid ----------

def record_purchase(db,actor,sid,lines,note='',source=None):
    """lines: [{'pack':id,'qty':dona,'price':cent_per_dona} | {'material':id,'qty':milli,'price':cent_per_unit}]."""
    _require_operator(db,actor)
    supplier=_supplier(db,sid)
    if not supplier['active']:raise ValueError('Bu ta’minotchi o‘chirilgan.')
    if not lines:raise ValueError('Kamida bitta qator kiriting.')
    if len(lines)>MAX_LINES:raise ValueError(f'Bitta xaridda {MAX_LINES} tadan ko‘p qator bo‘lmasin.')
    clean=[]
    for line in lines:
        price=line['price']
        if not isinstance(price,int) or isinstance(price,bool) or not 0<=price<=MAX_TOTAL_USD:raise ValueError('Narx noto‘g‘ri.')
        if line.get('material') is not None:
            m=_material(db,line['material'])
            if not m['active']:raise ValueError('Bu xom ashyo o‘chirilgan.')
            qty=line['qty']
            if not isinstance(qty,int) or not 0<qty<=MAX_QTY_MILLI:raise ValueError('Miqdor noto‘g‘ri.')
            total=int((Decimal(qty)*price/1000).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            clean.append((None,int(m['id']),qty,price,total))
        else:
            pack=line.get('pack')
            if pack not in core.PRODUCTS:raise ValueError('Mahsulot noto‘g‘ri.')
            qty=line['qty']
            if not isinstance(qty,int) or isinstance(qty,bool) or not 0<qty<=100000:raise ValueError('Miqdor 1 dan 100000 gacha bo‘lsin.')
            clean.append((pack,None,qty,price,qty*price))
    total=sum(x[4] for x in clean)
    if total>MAX_TOTAL_USD:raise ValueError('Xarid summasi juda katta. Tekshirib qayta kiriting.')
    note=_text(note,'Izoh',300)
    _lock(db)
    old=_seen(db,'purchases',source)
    if old:return old
    pid=int(db.execute('INSERT INTO purchases(supplier,actor,total_usd,note,ts,source) VALUES(?,?,?,?,?,?) RETURNING id',
                       (sid,actor,total,note,int(time.time()),source)).fetchone()[0])
    label=f"Xarid #{pid} · {supplier['name']}"
    with _AsOperator(db,actor):
        for pack,mid,qty,price,line_total in clean:
            # Idempotentlik xarid darajasida (purchases.source) tekshirilgan.
            move=wh.receive(db,actor,pack,qty,note=label) if pack is not None else _material_move(db,actor,mid,'in',qty,label,purchase=pid)
            db.execute('INSERT INTO purchase_lines(purchase,pack,material,qty,price_usd,total_usd,move) VALUES(?,?,?,?,?,?,?)',
                       (pid,pack,mid,qty,price,line_total,move))
    return pid


def pay_supplier(db,actor,sid,amount_usd,note='',source=None,pay_from='cash'):
    """Kassadan ta'minotchiga to'lov: kassa xarajati + ta'minotchi qarzi kamayadi."""
    supplier=_supplier(db,sid)
    if not isinstance(amount_usd,int) or isinstance(amount_usd,bool) or amount_usd<=0:
        raise ValueError('To‘lov summasi noto‘g‘ri.')
    note=_text(note,'Izoh',300)
    if not isinstance(source,int) or source<=0:raise ValueError('Operatsiya ID noto‘g‘ri.')
    _lock(db)
    if _seen(db,'supplier_payments',source):raise ValueError('Bu to‘lov allaqachon saqlangan.')
    debt=balance(db,sid)
    if amount_usd>debt:
        raise ValueError(f'Ta’minotchiga qarz {debt/100:,.2f} USD. Undan ko‘p to‘lab bo‘lmaydi.'.replace(',',' '))
    # Rol (kassir/admin), kassa qulfi va qoldiq tekshiruvi add_cashier_expense ichida.
    expense=core.add_cashier_expense(db,actor,amount_usd,SUPPLIER_PAY_CATEGORY,supplier['name'],
                                     note or f"Ta’minotchi #{sid}",source,pay_from=pay_from,system_category=True)
    return int(db.execute('''INSERT INTO supplier_payments(supplier,actor,amount_usd,expense,pay_from,note,ts,source)
        VALUES(?,?,?,?,?,?,?,?) RETURNING id''',(sid,actor,amount_usd,expense,pay_from,note,int(time.time()),source)).fetchone()[0])


# ---------- ishlab chiqarish ----------

def produce(db,actor,pack,qty,inputs,note='',source=None):
    """Xom ashyo sarflab tayyor mahsulot: inputs=[(material_id, qty_milli), ...]."""
    _require_operator(db,actor)
    if pack not in core.PRODUCTS:raise ValueError('Mahsulot noto‘g‘ri.')
    if not isinstance(qty,int) or isinstance(qty,bool) or not 0<qty<=100000:raise ValueError('Miqdor 1 dan 100000 gacha bo‘lsin.')
    if len(inputs)>MAX_LINES:raise ValueError(f'{MAX_LINES} tadan ko‘p xom ashyo bo‘lmasin.')
    seen=set()
    for mid,_ in inputs:
        if mid in seen:raise ValueError('Bitta xom ashyo ikki marta yozilgan.')
        seen.add(mid)
    note=_text(note,'Izoh',300)
    _lock(db)
    old=_seen(db,'productions',source)
    if old:return old
    prod=int(db.execute('INSERT INTO productions(pack,qty,actor,note,ts,source) VALUES(?,?,?,?,?,?) RETURNING id',
                        (pack,qty,actor,note,int(time.time()),source)).fetchone()[0])
    label=f'Ishlab chiqarish #{prod}'
    for mid,milli in inputs:
        _take_material(db,actor,mid,milli,'use',f'{label} · {product_name(pack)}',production=prod)
    with _AsOperator(db,actor):
        move=wh.receive(db,actor,pack,qty,note=label+(f' · {note}' if note else ''))
    db.execute('UPDATE productions SET move=? WHERE id=?',(move,prod))
    return prod


# ---------- ko'rinishlar ----------

def _material_view(db,r):
    have=material_stock(db,int(r['id']))
    return {'id':int(r['id']),'name':r['name'],'unit':r['unit'],'unitLabel':MATERIAL_UNITS.get(r['unit'],r['unit']),
            'stock':milli_text(have),'stockMilli':have,'min':milli_text(int(r['min_milli'] or 0)),
            'low':bool(r['min_milli']) and have<int(r['min_milli'])}


def _line_view(db,l):
    if l['material'] is not None:
        m=db.execute('SELECT name,unit FROM materials WHERE id=?',(l['material'],)).fetchone()
        name=m['name'] if m else f"#{l['material']}";unit=MATERIAL_UNITS.get(m['unit'],'') if m else ''
        return {'kind':'material','id':int(l['material']),'name':name,'qty':milli_text(int(l['qty'])),'unit':unit,
                'price':int(l['price_usd']),'total':int(l['total_usd'])}
    return {'kind':'product','id':int(l['pack']),'name':product_name(l['pack']),'qty':str(int(l['qty'])),'unit':'dona',
            'price':int(l['price_usd']),'total':int(l['total_usd'])}


def dashboard(db,actor):
    _require_viewer(db,actor)
    sups=[{'id':int(r['id']),'name':r['name'],'phone':r['phone'] or '','note':r['note'] or '','debt':balance(db,int(r['id']))}
          for r in db.execute('SELECT * FROM suppliers WHERE active=1 ORDER BY name').fetchall()]
    mats=[_material_view(db,r) for r in db.execute('SELECT * FROM materials WHERE active=1 ORDER BY name').fetchall()]
    purchases=[]
    for p in db.execute('''SELECT p.*,s.name AS supplier_name,u.name AS actor_name FROM purchases p
        LEFT JOIN suppliers s ON s.id=p.supplier LEFT JOIN users u ON u.id=p.actor ORDER BY p.id DESC LIMIT 30''').fetchall():
        lines=[_line_view(db,l) for l in db.execute('SELECT * FROM purchase_lines WHERE purchase=? ORDER BY id',(p['id'],)).fetchall()]
        purchases.append({'id':int(p['id']),'supplier':int(p['supplier']),'supplierName':p['supplier_name'] or '',
                          'actorName':p['actor_name'] or '','total':int(p['total_usd']),'note':p['note'] or '',
                          'ts':int(p['ts']),'lines':lines})
    moves=[{'id':int(m['id']),'kind':m['kind'],'label':MATERIAL_MOVES.get(m['kind'],m['kind']),'material':int(m['material']),
            'name':m['name'] or '','unit':MATERIAL_UNITS.get(m['unit'] or '',''),'qty':milli_text(int(m['qty_milli'])),
            'note':m['note'] or '','actorName':m['actor_name'] or '','ts':int(m['ts'])}
           for m in db.execute('''SELECT mm.*,m.name,m.unit,u.name AS actor_name FROM material_moves mm
               LEFT JOIN materials m ON m.id=mm.material LEFT JOIN users u ON u.id=mm.actor ORDER BY mm.id DESC LIMIT 40''').fetchall()]
    prods=[{'id':int(r['id']),'pack':int(r['pack']),'name':product_name(r['pack']),'qty':int(r['qty']),'note':r['note'] or '',
            'actorName':r['actor_name'] or '','ts':int(r['ts'])}
           for r in db.execute('''SELECT p.*,u.name AS actor_name FROM productions p LEFT JOIN users u ON u.id=p.actor
               ORDER BY p.id DESC LIMIT 20''').fetchall()]
    month=wh.month_start()
    month_bought=int(db.execute('SELECT COALESCE(SUM(total_usd),0) FROM purchases WHERE ts>=?',(month,)).fetchone()[0] or 0)
    month_paid=int(db.execute('SELECT COALESCE(SUM(amount_usd),0) FROM supplier_payments WHERE ts>=?',(month,)).fetchone()[0] or 0)
    core.refresh_catalog(db)
    active=set(core.active_product_ids())
    return {'suppliers':sups,'materials':mats,'purchases':purchases,'materialMoves':moves,'productions':prods,
            'products':[{'pack':p,'name':n,'stock':wh.stock(db,p)} for p,n in core.PRODUCTS.items() if p in active],
            'units':[[k,v] for k,v in MATERIAL_UNITS.items()],
            'summary':{'totalDebt':sum(max(s['debt'],0) for s in sups),'monthBought':month_bought,'monthPaid':month_paid,
                       'lowMaterials':sum(1 for m in mats if m['low']),'suppliers':len(sups),'materials':len(mats)}}


def ledger(db,actor,sid,limit=200):
    """Ta'minotchi akt-sverkasi: xaridlar va to'lovlar, eng yangisi yuqorida."""
    _require_viewer(db,actor)
    supplier=_supplier(db,sid)
    items=[]
    for p in db.execute('SELECT * FROM purchases WHERE supplier=? ORDER BY id DESC LIMIT ?',(sid,limit)).fetchall():
        lines=[_line_view(db,l) for l in db.execute('SELECT * FROM purchase_lines WHERE purchase=? ORDER BY id',(p['id'],)).fetchall()]
        items.append({'type':'purchase','id':int(p['id']),'amount':int(p['total_usd']),'note':p['note'] or '','ts':int(p['ts']),'lines':lines})
    for r in db.execute('SELECT * FROM supplier_payments WHERE supplier=? ORDER BY id DESC LIMIT ?',(sid,limit)).fetchall():
        items.append({'type':'payment','id':int(r['id']),'amount':int(r['amount_usd']),'note':r['note'] or '',
                      'payFrom':r['pay_from'] or 'cash','ts':int(r['ts'])})
    items.sort(key=lambda x:(x['ts'],x['type']=='payment',x['id']),reverse=True)
    return {'supplier':{'id':int(supplier['id']),'name':supplier['name'],'phone':supplier['phone'] or '','note':supplier['note'] or ''},
            'debt':balance(db,sid),'items':items[:limit]}


# ---------- web panel amallari ----------

OPS=('dashboard','ledger','supplier_add','supplier_edit','material_add','material_edit','purchase','pay','produce',
     'material_use','material_writeoff')
WRITE_OPS=OPS[2:]


def handle(db,actor,op,payload,source=None):
    """Rahbar web paneli uchun bitta kirish nuqtasi. Pul/son JSON'dan matn ko'rinishida keladi."""
    op=str(op or 'dashboard')
    if op not in OPS:raise ValueError('Ta’minot amali noto‘g‘ri.')
    if op=='dashboard':return dashboard(db,actor)
    if op=='ledger':return ledger(db,actor,_int(payload.get('supplierId'),'Ta’minotchi'))
    result={}
    if op=='supplier_add':
        result['supplierId']=add_supplier(db,actor,payload.get('name'),payload.get('phone'),payload.get('note'))
    elif op=='supplier_edit':
        update_supplier(db,actor,_int(payload.get('supplierId'),'Ta’minotchi'),payload.get('name'),payload.get('phone'),payload.get('note'))
    elif op=='material_add':
        result['materialId']=add_material(db,actor,payload.get('name'),payload.get('unit'),payload.get('minQty'))
    elif op=='material_edit':
        update_material(db,actor,_int(payload.get('materialId'),'Xom ashyo'),payload.get('name'),payload.get('minQty'))
    elif op=='purchase':
        raw=payload.get('lines')
        if not isinstance(raw,list):raise ValueError('Qatorlar ro‘yxati noto‘g‘ri.')
        lines=[]
        for item in raw:
            if not isinstance(item,dict):raise ValueError('Qatorlar ro‘yxati noto‘g‘ri.')
            price=parse_cents(item.get('price'),'Narx')
            if item.get('material') not in (None,''):
                lines.append({'material':_int(item.get('material'),'Xom ashyo'),'qty':parse_milli(item.get('qty')),'price':price})
            else:
                pack=_int(item.get('pack'),'Mahsulot',0)
                lines.append({'pack':pack,'qty':_int(item.get('qty'),'Miqdor',1,100000),'price':price})
        result['purchaseId']=record_purchase(db,actor,_int(payload.get('supplierId'),'Ta’minotchi'),lines,payload.get('note'),source=source)
    elif op=='pay':
        pay_from=str(payload.get('payFrom') or 'cash')
        result['paymentId']=pay_supplier(db,actor,_int(payload.get('supplierId'),'Ta’minotchi'),
                                         parse_cents(payload.get('amount'),'Summa',allow_zero=False),payload.get('note'),
                                         source=source,pay_from=pay_from)
    elif op=='produce':
        raw=payload.get('inputs') or []
        if not isinstance(raw,list):raise ValueError('Xom ashyo ro‘yxati noto‘g‘ri.')
        inputs=[(_int(i.get('material'),'Xom ashyo'),parse_milli(i.get('qty'))) for i in raw if isinstance(i,dict)]
        result['productionId']=produce(db,actor,_int(payload.get('pack'),'Mahsulot',0),_int(payload.get('qty'),'Miqdor',1,100000),
                                       inputs,payload.get('note'),source=source)
    elif op=='material_use':
        result['moveId']=material_use(db,actor,_int(payload.get('materialId'),'Xom ashyo'),parse_milli(payload.get('qty')),
                                      payload.get('note'),source=source)
    else:
        result['moveId']=material_writeoff(db,actor,_int(payload.get('materialId'),'Xom ashyo'),parse_milli(payload.get('qty')),
                                           payload.get('note'),source=source)
    data=dashboard(db,actor)
    data.update(result)
    return data
