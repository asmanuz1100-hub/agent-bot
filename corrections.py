"""Rahbar tuzatishlari: ta'minot xaridini va savdo sotuvini bekor qilish (o'chirish) va tahrirlash.

Yozuvlar izsiz o'chirilmaydi (kassa bekor qilish bilan bir xil tamoyil):
- asl xarid/sotuv saqlanadi, `voids` jadvaliga «bekor qilindi» belgisi, sabab, kim va qachon yoziladi;
- uning ta'siri teskari yozuv bilan qaytariladi:
  xarid — ombordan 'correction_out' (yoki xom ashyo 'cancel'), ta'minotchi qarzi kamayadi (balance bekorni sanamaydi);
  sotuv — uning yozuvlari (yetkazish, sotuv, to'lov, ombor chiqimi) 'cancelled_*' turiga o'tadi: savdo hisobotida
  ham, qarzda ham, omborda ham sanalmaydi (rahbar sotgan bo'lsa kassa kirimi ham bekor qilinadi).
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
KINDS=('purchase','sale','payment')


def init(db):
    if isinstance(db,PostgresDB):
        for stmt in PG_SCHEMA.split(';'):
            if stmt.strip():db.execute(stmt)
    else:
        db.executescript(SCHEMA)
    normalize_voided_sales(db)


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

def _sale_tag(sale):
    return f"Savdo #{int(sale['id'])}"+(f" | {sale['note']}" if sale['note'] else '')


def _hide_sale(db,sale):
    """Bekor qilingan sotuvning yozuvlari 'cancelled_*' turiga o'tadi: hech bir hisobot (savdo, qarz, agent, ombor)
    ularni sanamaydi, lekin bazada saqlanadi. Idempotent — qayta chaqirilsa hech narsa o'zgarmaydi.
    Eski usulda (teskari 'return'/'payment' va 'correction_in') bekor qilinganlar ham shu yerda yashiriladi."""
    sid=int(sale['id']);tag=_sale_tag(sale);label=f'Savdo #{sid} bekor qilindi%'
    db.execute("""UPDATE events SET kind='cancelled_'||kind WHERE client=? AND note=? AND kind IN ('delivery','sold','payment')""",
               (sale['client'],tag))
    db.execute("""UPDATE events SET kind='cancelled_'||kind WHERE client=? AND kind IN ('return','payment')
        AND (note LIKE ? OR note LIKE ?)""",(sale['client'],label,'Bekor qilindi: kassa kirimi #% · '+label))
    db.execute("""UPDATE warehouse_moves SET kind='cancelled_'||kind WHERE (kind='shop_sale' AND note=?)
        OR (kind='correction_in' AND note LIKE ?)""",(tag,label))


def normalize_voided_sales(db):
    """Ishga tushishda: oldin bekor qilingan sotuvlar ham hisobotlardan to'liq chiqariladi."""
    for r in db.execute("SELECT ref FROM voids WHERE kind='sale'").fetchall():
        s=db.execute('SELECT id,client,note FROM shop_sales WHERE id=?',(int(r[0]),)).fetchone()
        if s:_hide_sale(db,s)


def cancel_sale(db,actor,sale_id,reason,now=None):
    require_admin(db,actor)
    reason=_reason(reason)
    s=db.execute('SELECT * FROM shop_sales WHERE id=?',(int(sale_id),)).fetchone()
    if not s:raise ValueError('Sotuv topilmadi.')
    seller=int(s['seller'])
    core.lock_agent(db,seller);wh._lock_warehouse(db)
    ts=int(time.time() if now is None else now)
    _mark(db,'sale',s['id'],actor,reason,ts)
    # Olingan pul: sotuvchi qo'lida bo'lishi (yoki kassada qolgan bo'lishi) kerak — aks holda bekor qilinmaydi.
    ev=db.execute("""SELECT * FROM events WHERE kind='payment' AND client=? AND note=? AND amount_usd>0 ORDER BY id LIMIT 1""",
                  (s['client'],_sale_tag(s))).fetchone() if int(s['paid'] or 0)>0 else None
    if ev is not None:
        move=db.execute("SELECT * FROM cash_moves WHERE event=? AND status='active'",(ev['id'],)).fetchone() if ev['agent'] is None else None
        if move is not None:
            import cashbook
            cashbook._lock(db)
            if int(move['amount'])>cashbook._available(db,move['to_pocket'],move['currency']):
                raise ValueError(f"Kassada ({cashbook.POCKETS[move['to_pocket']]}) yetarli {move['currency']} yo‘q — bu pul ishlatilgan.")
            db.execute("UPDATE cash_moves SET status='cancelled',cancel_actor=?,cancel_ts=?,cancel_reason=? WHERE id=?",
                       (actor,ts,f"Savdo #{int(s['id'])} bekor qilindi · {reason[:150]}",int(move['id'])))
        elif ev['agent'] is not None and (ev['pay_method'] or '')!='card':
            agent=int(ev['agent']);usd=int(ev['amount_usd']);uzs=int(ev['paid_uzs'] or 0)
            if uzs and core.cash(db,agent)<uzs*100:
                raise ValueError('Sotuvchi bu so‘mni kassaga topshirib bo‘lgan — avval kassadan qaytarilsin.')
            if not uzs and core.cash_usd(db,agent)<usd:
                raise ValueError('Sotuvchi bu dollarni kassaga topshirib bo‘lgan — avval kassadan qaytarilsin.')
    _hide_sale(db,s)   # tovar omborga, qarz va pul o'z-o'zidan qaytadi (yozuvlar sanalmaydi)
    return int(s['id'])


# ---------- agent to'lovi (masalan, Mini App'da takror kiritilgan) ----------

def cancel_payment(db,actor,event_id,reason,now=None):
    """Agentning naqd to'lovi bekor qilinadi: yozuv 'cancelled_payment' bo'ladi — mijoz qarzi qaytadi,
    agent qo'lidagi pul kamayadi. Agent bu pulni kassaga topshirib bo'lgan bo'lsa — bekor qilinmaydi."""
    require_admin(db,actor)
    reason=_reason(reason)
    ev=db.execute("SELECT * FROM events WHERE id=?",(int(event_id),)).fetchone()
    if not ev or ev['kind']!='payment':raise ValueError('To‘lov topilmadi yoki allaqachon bekor qilingan.')
    if ev['agent'] is None:raise ValueError('Bu to‘lov kassa orqali kiritilgan — uni Kassa bo‘limida bekor qiling.')
    if (ev['pay_method'] or '')=='card':raise ValueError('Karta to‘lovi kassir tasdig‘i orqali o‘tadi — bu yerda bekor qilinmaydi.')
    agent=int(ev['agent'])
    core.lock_agent(db,agent)
    uzs=int(ev['paid_uzs'] or 0)*100+int(ev['amount'] or 0)
    if uzs and core.cash(db,agent)<uzs:
        raise ValueError('Agent bu so‘mni kassaga topshirib bo‘lgan — avval kassadan qaytarilsin.')
    if not uzs and core.cash_usd(db,agent)<int(ev['amount_usd'] or 0):
        raise ValueError('Agent bu dollarni kassaga topshirib bo‘lgan — avval kassadan qaytarilsin.')
    _mark(db,'payment',ev['id'],actor,reason,int(time.time() if now is None else now))
    db.execute("UPDATE events SET kind='cancelled_payment' WHERE id=?",(int(ev['id']),))
    return int(ev['id'])
