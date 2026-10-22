"""Харид ва таъминотчилар.

Омборчи таъминотчидан товар харид қилганини киритади: ҳар бир қатор омборга
'in' ҳаракати бўлиб тушади (warehouse.receive), харид суммаси эса таъминотчига
бўлган қарзимизга қўшилади. Кассир ёки раҳбар таъминотчига тўлов қилганда касса
харажати (core.add_cashier_expense) ёзилади ва қарз камаяди.

Пул суммалари бошқа модуллардаги каби USD центда сақланади.
Ёзувлар ўчирилмайди ва таҳрирланмайди; хато бўлса тескари амал киритилади.
"""
import time

import core
from core import PRODUCTS, PostgresDB, product_name
import warehouse as wh

SUPPLIER_PAY_CATEGORY='🏭 Таъминотчига тўлов'
MAX_LINES=30
MAX_TOTAL_USD=10**10  # 100 mln USD (centda), noto'g'ri kiritishdan himoya

SCHEMA='''
CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, actor INTEGER NOT NULL, ts INTEGER NOT NULL, source INTEGER UNIQUE);
CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY, supplier INTEGER NOT NULL, actor INTEGER NOT NULL, total_usd INTEGER NOT NULL CHECK(total_usd>=0), note TEXT NOT NULL DEFAULT '', ts INTEGER NOT NULL, source INTEGER UNIQUE);
CREATE TABLE IF NOT EXISTS purchase_lines(id INTEGER PRIMARY KEY, purchase INTEGER NOT NULL, pack INTEGER NOT NULL, qty INTEGER NOT NULL CHECK(qty>0), price_usd INTEGER NOT NULL CHECK(price_usd>=0), move INTEGER);
CREATE TABLE IF NOT EXISTS supplier_payments(id INTEGER PRIMARY KEY, supplier INTEGER NOT NULL, actor INTEGER NOT NULL, amount_usd INTEGER NOT NULL CHECK(amount_usd>0), expense INTEGER, note TEXT NOT NULL DEFAULT '', ts INTEGER NOT NULL, source INTEGER UNIQUE);
CREATE INDEX IF NOT EXISTS idx_purchases_supplier ON purchases(supplier,ts);
CREATE INDEX IF NOT EXISTS idx_purchase_lines_purchase ON purchase_lines(purchase);
CREATE INDEX IF NOT EXISTS idx_supplier_payments_supplier ON supplier_payments(supplier,ts);
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


def _require_viewer(db,actor):
    if _role(db,actor) not in ('warehouse','admin','cashier'):
        raise ValueError('Bu bo‘lim faqat omborchi, kassir yoki rahbar uchun.')


def _require_buyer(db,actor):
    if _role(db,actor) not in ('warehouse','admin'):
        raise ValueError('Xaridni faqat omborchi yoki rahbar kiritadi.')


def _lock(db):
    if isinstance(db,PostgresDB):
        db.execute("INSERT INTO meta(key,value) VALUES('purchases_lock','1') ON CONFLICT(key) DO NOTHING")
        db.execute("SELECT value FROM meta WHERE key='purchases_lock' FOR UPDATE").fetchone()


def _text(value,label,limit,required=False):
    text=str(value or '').strip()
    if len(text)>limit:raise ValueError(f'{label} {limit} belgidan oshmasin.')
    if required and not text:raise ValueError(f'{label}ni kiriting.')
    return text


def _supplier(db,sid):
    row=db.execute('SELECT * FROM suppliers WHERE id=?',(sid,)).fetchone()
    if not row:raise ValueError('Ta’minotchi topilmadi.')
    return row


def add_supplier(db,actor,name,phone='',note='',source=None):
    _require_buyer(db,actor)
    name=_text(name,'Ta’minotchi nomi',120,required=True)
    phone=_text(phone,'Telefon',40);note=_text(note,'Izoh',300)
    _lock(db)
    if source is not None:
        old=db.execute('SELECT id FROM suppliers WHERE source=?',(source,)).fetchone()
        if old:return int(old[0])
    if db.execute('SELECT 1 FROM suppliers WHERE LOWER(name)=LOWER(?) AND active=1',(name,)).fetchone():
        raise ValueError('Bu nomli ta’minotchi allaqachon bor.')
    return int(db.execute('''INSERT INTO suppliers(name,phone,note,actor,ts,source) VALUES(?,?,?,?,?,?) RETURNING id''',
                          (name,phone,note,actor,int(time.time()),source)).fetchone()[0])


def balance(db,sid):
    """Ta'minotchiga qarzimiz (USD cent). Musbat = biz qarzdormiz."""
    bought=db.execute('SELECT COALESCE(SUM(total_usd),0) FROM purchases WHERE supplier=?',(sid,)).fetchone()[0]
    paid=db.execute('SELECT COALESCE(SUM(amount_usd),0) FROM supplier_payments WHERE supplier=?',(sid,)).fetchone()[0]
    return int(bought or 0)-int(paid or 0)


def record_purchase(db,actor,sid,lines,note='',source=None):
    """lines: [(pack, qty_dona, price_usd_cent_per_dona), ...]. Omborga kirim + qarz."""
    _require_buyer(db,actor)
    supplier=_supplier(db,sid)
    if not supplier['active']:raise ValueError('Bu ta’minotchi o‘chirilgan.')
    if not lines:raise ValueError('Kamida bitta mahsulot kiriting.')
    if len(lines)>MAX_LINES:raise ValueError(f'Bitta xaridda {MAX_LINES} tadan ko‘p qator bo‘lmasin.')
    clean=[]
    for pack,qty,price in lines:
        if pack not in PRODUCTS:raise ValueError('Mahsulot noto‘g‘ri.')
        if not isinstance(qty,int) or isinstance(qty,bool) or not 0<qty<=100000:raise ValueError('Miqdor 1 dan 100000 gacha bo‘lsin.')
        if not isinstance(price,int) or isinstance(price,bool) or not 0<=price<=10**8:raise ValueError('Narx noto‘g‘ri.')
        clean.append((pack,qty,price))
    total=sum(q*p for _,q,p in clean)
    if total>MAX_TOTAL_USD:raise ValueError('Xarid summasi juda katta. Tekshirib qayta kiriting.')
    note=_text(note,'Izoh',300)
    _lock(db)
    if source is not None:
        old=db.execute('SELECT id FROM purchases WHERE source=?',(source,)).fetchone()
        if old:return int(old[0])
    pid=int(db.execute('''INSERT INTO purchases(supplier,actor,total_usd,note,ts,source) VALUES(?,?,?,?,?,?) RETURNING id''',
                       (sid,actor,total,note,int(time.time()),source)).fetchone()[0])
    # Rahbar ham xarid kirita oladi: ombor kirimini shu so'rov davomida unga ruxsat beramiz.
    token=wh.WEB_PRIMARY_OPERATOR.set(actor) if _role(db,actor)=='admin' else None
    try:
        for pack,qty,price in clean:
            # Idempotentlik xarid darajasida (purchases.source) tekshirilgan.
            move=wh.receive(db,actor,pack,qty,note=f"Xarid #{pid} · {supplier['name']}")
            db.execute('INSERT INTO purchase_lines(purchase,pack,qty,price_usd,move) VALUES(?,?,?,?,?)',(pid,pack,qty,price,move))
    finally:
        if token is not None:wh.WEB_PRIMARY_OPERATOR.reset(token)
    return pid


def pay_supplier(db,actor,sid,amount_usd,note='',source=None,pay_from='cash'):
    """Kassadan ta'minotchiga to'lov: kassa xarajati + ta'minotchi qarzi kamayadi."""
    supplier=_supplier(db,sid)
    if not isinstance(amount_usd,int) or isinstance(amount_usd,bool) or amount_usd<=0:
        raise ValueError('To‘lov summasi noto‘g‘ri.')
    note=_text(note,'Izoh',300)
    if not isinstance(source,int) or source<=0:raise ValueError('Operatsiya ID noto‘g‘ri.')
    _lock(db)
    if db.execute('SELECT 1 FROM supplier_payments WHERE source=?',(source,)).fetchone():
        raise ValueError('Bu to‘lov allaqachon saqlangan.')
    debt=balance(db,sid)
    if amount_usd>debt:
        raise ValueError(f'Ta’minotchiga qarz {debt/100:,.2f} USD. Undan ko‘p to‘lab bo‘lmaydi.'.replace(',',' '))
    # Rol tekshiruvi, kassa qulfi va qoldiq tekshiruvi add_cashier_expense ichida.
    expense=core.add_cashier_expense(db,actor,amount_usd,SUPPLIER_PAY_CATEGORY,supplier['name'],
                                     note or f"Ta’minotchi #{sid}",source,pay_from=pay_from,
                                     system_category=True)
    return int(db.execute('''INSERT INTO supplier_payments(supplier,actor,amount_usd,expense,note,ts,source) VALUES(?,?,?,?,?,?,?) RETURNING id''',
                          (sid,actor,amount_usd,expense,note,int(time.time()),source)).fetchone()[0])


def suppliers(db,actor):
    _require_viewer(db,actor)
    rows=db.execute('SELECT * FROM suppliers WHERE active=1 ORDER BY name').fetchall()
    out=[{'id':int(r['id']),'name':r['name'],'phone':r['phone'] or '','note':r['note'] or '','debt':balance(db,int(r['id']))}
         for r in rows]
    return {'suppliers':out,'totalDebt':sum(max(s['debt'],0) for s in out)}


def ledger(db,actor,sid,limit=100):
    """Ta'minotchi akt-sverkasi: xaridlar va to'lovlar, eng yangisi yuqorida."""
    _require_viewer(db,actor)
    supplier=_supplier(db,sid)
    items=[]
    for p in db.execute('SELECT * FROM purchases WHERE supplier=? ORDER BY id DESC LIMIT ?',(sid,limit)).fetchall():
        lines=[{'pack':int(l['pack']),'name':product_name(l['pack']),'qty':int(l['qty']),'price':int(l['price_usd'])}
               for l in db.execute('SELECT * FROM purchase_lines WHERE purchase=? ORDER BY id',(p['id'],)).fetchall()]
        items.append({'type':'purchase','id':int(p['id']),'amount':int(p['total_usd']),'note':p['note'] or '',
                      'ts':int(p['ts']),'lines':lines})
    for r in db.execute('SELECT * FROM supplier_payments WHERE supplier=? ORDER BY id DESC LIMIT ?',(sid,limit)).fetchall():
        items.append({'type':'payment','id':int(r['id']),'amount':int(r['amount_usd']),'note':r['note'] or '','ts':int(r['ts'])})
    items.sort(key=lambda x:(x['ts'],x['type']=='payment',x['id']),reverse=True)
    return {'supplier':{'id':int(supplier['id']),'name':supplier['name'],'phone':supplier['phone'] or ''},
            'debt':balance(db,sid),'items':items[:limit]}
