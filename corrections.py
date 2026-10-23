"""Rahbar tuzatishlari: ta'minot xaridini va savdo sotuvini bekor qilish (o'chirish) va tahrirlash.

Yozuvlar izsiz o'chirilmaydi (kassa bekor qilish bilan bir xil tamoyil):
- asl xarid/sotuv saqlanadi, `voids` jadvaliga «bekor qilindi» belgisi, sabab, kim va qachon yoziladi;
- uning ta'siri teskari yozuv bilan qaytariladi:
  xarid — ombordan 'correction_out' (yoki xom ashyo 'cancel'), ta'minotchi qarzi kamayadi (balance bekorni sanamaydi);
  sotuv — omborga 'correction_in', mijozga 'return' hodisasi (qarz va sof savdo kamayadi), olingan pul teskari
  to'lov bilan qaytadi (rahbar sotgan bo'lsa kassa kirimi cashbook.cancel orqali bekor qilinadi).
- Tahrirlash = eski yozuvni bekor qilish + yangisini yozish, bitta tranzaksiyada; ikkalasi bir-biriga bog'lanadi.
Faqat rahbar (role='admin') bajaradi.
"""
import time

import core
from core import PostgresDB, product_name
import warehouse as wh

SCHEMA='''
CREATE TABLE IF NOT EXISTS voids(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, ref INTEGER NOT NULL, actor INTEGER NOT NULL, reason TEXT NOT NULL, ts INTEGER NOT NULL, replaced_by INTEGER, UNIQUE(kind,ref));
'''
PG_SCHEMA=SCHEMA.replace('INTEGER PRIMARY KEY','BIGSERIAL PRIMARY KEY').replace(' INTEGER',' BIGINT')
KINDS=('purchase','sale')


def init(db):
    if isinstance(db,PostgresDB):
        for stmt in PG_SCHEMA.split(';'):
            if stmt.strip():db.execute(stmt)
    else:
        db.executescript(SCHEMA)


def require_admin(db,actor):
    row=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not row or row[0]!='admin':
        raise ValueError('O‘chirish va tahrirlash faqat rahbar uchun.')


def _reason(reason):
    reason=str(reason or '').strip()
    if not reason or len(reason)>300:raise ValueError('Sababini yozing (1–300 belgi).')
    return reason


def voided(db,kind):
    """{ref: {'reason','who','ts','replacedBy'}} — ro'yxatlarda belgilash uchun."""
    rows=db.execute('''SELECT v.*,u.name AS who FROM voids v LEFT JOIN users u ON u.id=v.actor WHERE v.kind=?''',(kind,)).fetchall()
    return {int(r['ref']):{'reason':r['reason'],'who':r['who'] or '','ts':int(r['ts']),
                           'replacedBy':int(r['replaced_by']) if r['replaced_by'] is not None else None} for r in rows}


def is_voided(db,kind,ref):
    return db.execute('SELECT 1 FROM voids WHERE kind=? AND ref=?',(kind,int(ref))).fetchone() is not None


def _mark(db,kind,ref,actor,reason,ts):
    if is_voided(db,kind,ref):raise ValueError('Bu yozuv allaqachon bekor qilingan.')
    db.execute('INSERT INTO voids(kind,ref,actor,reason,ts) VALUES(?,?,?,?,?)',(kind,int(ref),actor,reason,ts))


def link_replacement(db,kind,ref,new_ref):
    db.execute('UPDATE voids SET replaced_by=? WHERE kind=? AND ref=?',(int(new_ref),kind,int(ref)))


# ---------- ta'minot xaridi ----------

def cancel_purchase(db,actor,pid,reason,now=None):
    import purchases
    require_admin(db,actor)
    reason=_reason(reason)
    purchases._lock(db);wh._lock_warehouse(db)
    p=db.execute('SELECT * FROM purchases WHERE id=?',(int(pid),)).fetchone()
    if not p:raise ValueError('Xarid topilmadi.')
    ts=int(time.time() if now is None else now)
    _mark(db,'purchase',p['id'],actor,reason,ts)
    label=f"Xarid #{int(p['id'])} bekor qilindi · {reason[:150]}"
    lines=db.execute('SELECT * FROM purchase_lines WHERE purchase=? ORDER BY id',(p['id'],)).fetchall()
    # Avval hammasi tekshiriladi: kirim qilingan tovar allaqachon sotilgan/berilgan bo'lsa — bekor qilinmaydi.
    need={}
    for l in lines:
        if l['pack'] is not None:need[int(l['pack'])]=need.get(int(l['pack']),0)+int(l['qty'])
    for pack,qty in need.items():
        have=wh.stock(db,pack)
        if have<qty:
            raise ValueError(f'{product_name(pack)}: omborda {have} dona qolgan, xaridda {qty} dona. '
                             'Tovar sotilgan yoki berilgan — avval omborni to‘g‘rilang.')
    for l in lines:
        if l['material'] is not None:
            m=purchases._material(db,int(l['material']))
            have=purchases.material_stock(db,int(l['material']))
            if have<int(l['qty']):
                raise ValueError(f"{m['name']}: omborda {purchases.milli_text(have)} qolgan, xaridda {purchases.milli_text(int(l['qty']))}. "
                                 'Xom ashyo ishlatilgan — bekor qilib bo‘lmaydi.')
    for l in lines:
        if l['pack'] is not None:
            wh._move(db,actor,'correction_out',int(l['pack']),int(l['qty']),note=label)
        else:
            purchases._material_move(db,actor,int(l['material']),'cancel',int(l['qty']),label,purchase=int(p['id']))
    return int(p['id'])


def edit_purchase(db,actor,pid,sid,lines,note,reason,source=None):
    """Eski xarid bekor + yangisi yoziladi (bitta tranzaksiya). Yangi xarid ID qaytadi."""
    import purchases
    require_admin(db,actor)
    if source is not None and purchases._seen(db,'purchases',source):return purchases._seen(db,'purchases',source)
    cancel_purchase(db,actor,pid,reason or 'Tahrirlandi')
    new=purchases.record_purchase(db,actor,sid,lines,note,source=source)
    link_replacement(db,'purchase',pid,new)
    return new


# ---------- savdo sotuvi ----------

def _sale_payment_event(db,sale):
    tag=f"Savdo #{int(sale['id'])}"+(f" | {sale['note']}" if sale['note'] else '')
    return db.execute("""SELECT * FROM events WHERE kind='payment' AND client=? AND note=? AND ts=? AND amount_usd>0
        ORDER BY id LIMIT 1""",(sale['client'],tag,sale['ts'])).fetchone()


def cancel_sale(db,actor,sale_id,reason,now=None):
    require_admin(db,actor)
    reason=_reason(reason)
    s=db.execute('SELECT * FROM shop_sales WHERE id=?',(int(sale_id),)).fetchone()
    if not s:raise ValueError('Sotuv topilmadi.')
    seller=int(s['seller'])
    core.lock_agent(db,seller);wh._lock_warehouse(db)
    ts=int(time.time() if now is None else now)
    _mark(db,'sale',s['id'],actor,reason,ts)
    label=f"Savdo #{int(s['id'])} bekor qilindi · {reason[:150]}"
    # 1) Olingan pul qaytadi.
    ev=_sale_payment_event(db,s) if int(s['paid'] or 0)>0 else None
    if ev is not None:
        move=db.execute("SELECT id FROM cash_moves WHERE event=?",(ev['id'],)).fetchone() if ev['agent'] is None else None
        if move is not None:
            import cashbook
            cashbook.cancel(db,actor,int(move[0]),label,now=ts)   # kassa qoldig'i tekshiriladi, qarz teskari yozuv bilan qaytadi
        else:
            agent=int(ev['agent'])
            usd=int(ev['amount_usd']);uzs=int(ev['paid_uzs'] or 0);method=ev['pay_method'] or ''
            if method!='card':
                if uzs and core.cash(db,agent)<uzs*100:
                    raise ValueError('Sotuvchi bu so‘mni kassaga topshirib bo‘lgan — avval kassadan qaytarilsin.')
                if not uzs and core.cash_usd(db,agent)<usd:
                    raise ValueError('Sotuvchi bu dollarni kassaga topshirib bo‘lgan — avval kassadan qaytarilsin.')
            db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source,pay_method,paid_uzs,fx_rate)
                VALUES(?,?,?,'payment',0,0,0,?,?,?,NULL,?,?,?)""",(actor,agent,s['client'],-usd,label,ts,method,-uzs,int(ev['fx_rate'] or 0)))
    # 2) Tovar omborga qaytadi, mijoz qarzi/savdo 'return' bilan kamayadi.
    for l in db.execute('SELECT * FROM shop_sale_lines WHERE sale=? ORDER BY id',(s['id'],)).fetchall():
        wh._move(db,actor,'correction_in',int(l['pack']),int(l['qty']),agent=seller,note=label)
        db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
            VALUES(?,?,?,'return',?,?,0,?,?,?,NULL)""",(actor,seller,s['client'],int(l['pack']),int(l['qty']),int(l['total']),label,ts))
    return int(s['id'])
