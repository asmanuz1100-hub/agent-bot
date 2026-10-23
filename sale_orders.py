"""Ombordan savdo buyurtmasi: band qilish, qisman yetkazish, qisman/aralash to'lov, qaytarish, tarix.

Mavjud Savdo ilovasidagi oddiy sotuv (shop.sell) o'zgarmaydi: u darhol yetkaziladi.
Buyurtmada esa:
- Tasdiqlash tovarni yetkazilgan yoki pulni olingan qilmaydi — faqat omborda BAND qiladi
  (mavjud = ombor qoldig'i − ochiq buyurtmalarning yetkazilmagan qismi; shop.quote ham shuni hisobga oladi).
- Yetkazish — faqat shu paytda 'delivery' (va 'sold') hodisasi va ombor chiqimi yoziladi. Shuning uchun mijoz
  qarzi formulasi (berilgan − qaytgan − to'lov) o'zgarmaydi va hech narsa ikki marta sanalmaydi.
- To'lov — bir tasdiqda bir nechta satr (naqd $, naqd so'm, karta); har satr 'payment' hodisasi, kurs saqlanadi.
- Qaytarish — asl buyurtma qatoriga bog'lanadi: 'return' hodisasi va omborga kirim.
- Narx va kurs yozilgan paytdagisi saqlanadi; keyingi narx o'zgarishi eski buyurtmaga ta'sir qilmaydi.
Pul USD sentda (shop.py bilan bir xil). Yozuvlar o'chirilmaydi; har amal tarixga yoziladi.
"""
import time

import core
from core import PostgresDB
import warehouse as wh

DELIVERY={'none':'Yetkazilmadi','partial':'Qisman yetkazildi','full':'Yetkazildi'}
PAYMENT={'unpaid':'To‘lanmagan','partial':'Qisman to‘langan','paid':'To‘langan'}

SCHEMA='''
CREATE TABLE IF NOT EXISTS sale_orders(id INTEGER PRIMARY KEY, seller INTEGER NOT NULL, client INTEGER NOT NULL, price_type TEXT NOT NULL, subtotal INTEGER NOT NULL, discount INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', delivery_date TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open', actor INTEGER NOT NULL, ts INTEGER NOT NULL, source INTEGER UNIQUE);
CREATE TABLE IF NOT EXISTS sale_order_lines(id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, pack INTEGER NOT NULL, qty INTEGER NOT NULL CHECK(qty>0), list_price INTEGER NOT NULL, price INTEGER NOT NULL, discount INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL, delivered INTEGER NOT NULL DEFAULT 0, delivered_amount INTEGER NOT NULL DEFAULT 0, returned INTEGER NOT NULL DEFAULT 0, returned_amount INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sale_order_payments(id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, method TEXT NOT NULL, currency TEXT NOT NULL, amount INTEGER NOT NULL, usd_cents INTEGER NOT NULL, rate INTEGER NOT NULL DEFAULT 0, actor INTEGER NOT NULL, ts INTEGER NOT NULL, source INTEGER UNIQUE);
CREATE TABLE IF NOT EXISTS sale_order_log(id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', actor INTEGER NOT NULL, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_sale_order_lines_order ON sale_order_lines(order_id);
CREATE INDEX IF NOT EXISTS idx_sale_order_lines_pack ON sale_order_lines(pack);
CREATE INDEX IF NOT EXISTS idx_sale_orders_status ON sale_orders(status,ts);
'''
PG_SCHEMA=SCHEMA.replace('INTEGER PRIMARY KEY','BIGSERIAL PRIMARY KEY').replace(' INTEGER',' BIGINT')


def init(db):
    if isinstance(db,PostgresDB):
        for stmt in PG_SCHEMA.split(';'):
            if stmt.strip():db.execute(stmt)
    else:
        db.executescript(SCHEMA)


def reserved(db,pack,exclude=None):
    """Ochiq buyurtmalarda band, hali yetkazilmagan dona."""
    sql='''SELECT COALESCE(SUM(l.qty-l.delivered),0) FROM sale_order_lines l JOIN sale_orders o ON o.id=l.order_id
        WHERE o.status='open' AND l.pack=?'''
    args=[pack]
    if exclude is not None:
        sql+=' AND o.id<>?';args.append(exclude)
    return int(db.execute(sql,args).fetchone()[0] or 0)


def available(db,pack,exclude=None):
    return wh.stock(db,pack)-reserved(db,pack,exclude)


def _log(db,oid,action,detail,actor,ts):
    db.execute('INSERT INTO sale_order_log(order_id,action,detail,actor,ts) VALUES(?,?,?,?,?)',(oid,action,detail,actor,ts))


def _order(db,oid):
    try:oid=int(oid)
    except (TypeError,ValueError):raise ValueError('Buyurtma raqami noto‘g‘ri.')
    row=db.execute('SELECT * FROM sale_orders WHERE id=?',(oid,)).fetchone()
    if not row:raise ValueError('Buyurtma topilmadi.')
    return row


def _src(actor,payload,index):
    import shop
    return shop._source(actor,payload.get('requestId'),index)


def _sums(db,oid):
    one=lambda sql:int(db.execute(sql,(oid,)).fetchone()[0] or 0)
    return {'delivered':one('SELECT COALESCE(SUM(delivered_amount),0) FROM sale_order_lines WHERE order_id=?'),
            'returned':one('SELECT COALESCE(SUM(returned_amount),0) FROM sale_order_lines WHERE order_id=?'),
            'paid':one('SELECT COALESCE(SUM(usd_cents),0) FROM sale_order_payments WHERE order_id=?'),
            'qty':one('SELECT COALESCE(SUM(qty),0) FROM sale_order_lines WHERE order_id=?'),
            'qty_delivered':one('SELECT COALESCE(SUM(delivered),0) FROM sale_order_lines WHERE order_id=?')}


def states(db,row):
    s=_sums(db,int(row['id']))
    d='none' if s['qty_delivered']==0 else 'full' if s['qty_delivered']>=s['qty'] else 'partial'
    due=int(row['total'])-s['returned']
    p='unpaid' if s['paid']==0 else 'paid' if s['paid']>=due else 'partial'
    return d,p,s


# ---------- amallar ----------

def create(db,actor,payload,now=None):
    """Buyurtma: narx/chegirma/ruxsat shop.quote bilan; faqat band qilinadi."""
    import shop
    src=_src(actor,payload,0)
    old=db.execute('SELECT id FROM sale_orders WHERE source=?',(src,)).fetchone()
    if old:return int(old[0])
    who=shop._seller(db,actor,payload)
    core.lock_agent(db,who)
    wh._lock_warehouse(db)   # ikki sotuvchi bir vaqtda bir qoldiqni band qilmasin
    q=shop.quote(db,actor,payload)
    if q['walkin']:raise ValueError('Buyurtma uchun mijozni tanlang.')
    if q['stockShort']:raise ValueError('Omborda yetarli emas — '+'; '.join(q['stockShort']))
    date=str(payload.get('deliveryDate') or '').strip()[:10]
    address=str(payload.get('address') or '').strip()[:300]
    note=str(payload.get('note') or '').strip()[:300]
    ts=int(time.time() if now is None else now)
    oid=int(db.execute('''INSERT INTO sale_orders(seller,client,price_type,subtotal,discount,total,note,delivery_date,address,actor,ts,source)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id''',(who,q['client']['id'],q['priceType'],q['subtotal'],q['discount'],q['total'],
        note,date,address,actor,ts,src)).fetchone()[0])
    for l in q['lines']:
        db.execute('''INSERT INTO sale_order_lines(order_id,pack,qty,list_price,price,discount,total) VALUES(?,?,?,?,?,?,?)''',
                   (oid,l['pack'],l['qty'],l['listPrice'],l['price'],l['discount'],l['total']))
    _log(db,oid,'create',f"{len(q['lines'])} qator, jami ${q['total']/100:.2f}",actor,ts)
    return oid


def deliver(db,actor,oid,items,payload,now=None):
    """items: {pack: dona}. Faqat shu yerda tovar mijozga o'tadi (delivery/sold hodisasi, ombor chiqimi)."""
    o=_order(db,oid);oid=int(o['id'])
    if o['status']!='open':raise ValueError('Buyurtma ochiq emas.')
    if not isinstance(items,dict) or not items:raise ValueError('Yetkaziladigan miqdorni kiriting.')
    core.lock_agent(db,int(o['seller']))
    wh._lock_warehouse(db)
    ts=int(time.time() if now is None else now)
    tag=f'Buyurtma #{oid}'
    if db.execute('SELECT 1 FROM events WHERE source=?',(_src(actor,payload,1000),)).fetchone():
        return oid   # takroriy so'rov: birinchi qator allaqachon yozilgan
    done=[]
    for i,(pack,qty) in enumerate(sorted(items.items(),key=lambda kv:int(kv[0]))):
        pack=int(pack);qty=int(qty)
        if qty<=0:continue
        line=db.execute('SELECT * FROM sale_order_lines WHERE order_id=? AND pack=?',(oid,pack)).fetchone()
        if not line:raise ValueError('Bu mahsulot buyurtmada yo‘q.')
        left=int(line['qty'])-int(line['delivered'])
        if qty>left:raise ValueError(f'{core.product_name(pack)}: qolgan {left} dona.')
        if wh.stock(db,pack)<qty:raise ValueError(f'{core.product_name(pack)}: omborda {wh.stock(db,pack)} dona.')
        # summa: oxirgi yetkazish qoldiqni oladi — yaxlitlash farqi yo'qolmaydi
        amount=int(line['total'])-int(line['delivered_amount']) if qty==left else int(line['total'])*qty//int(line['qty'])
        source=_src(actor,payload,1000+i*3)
        db.execute('UPDATE sale_order_lines SET delivered=delivered+?,delivered_amount=delivered_amount+? WHERE id=?',(qty,amount,line['id']))
        wh._move(db,actor,'shop_sale',pack,qty,agent=int(o['seller']),note=tag,source=source)
        for k,kind in ((1,'delivery'),(2,'sold')):
            db.execute('''INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
                VALUES(?,?,?,?,?,?,0,?,?,?,?)''',(actor,int(o['seller']),int(o['client']),kind,pack,qty,amount,tag,ts,source+k))
        done.append(f'{core.product_name(pack)} {qty} dona')
    if not done:raise ValueError('Yetkaziladigan miqdorni kiriting.')
    _log(db,oid,'deliver',', '.join(done),actor,ts)
    return oid


def pay(db,actor,oid,lines,payload,now=None):
    """lines: [{'method':'cash_usd'|'cash_uzs'|'card','amount':..,'rate':..}] — bitta tasdiq, bitta tranzaksiya."""
    import shop
    o=_order(db,oid);oid=int(o['id'])
    if o['status']=='cancelled':raise ValueError('Buyurtma bekor qilingan.')
    if not isinstance(lines,list) or not 1<=len(lines)<=6:raise ValueError('To‘lov satrlarini kiriting.')
    core.lock_agent(db,int(o['seller']))
    first=_src(actor,payload,2000)
    if db.execute('SELECT 1 FROM sale_order_payments WHERE source=?',(first,)).fetchone():return oid
    d,p,s=states(db,o)
    left=int(o['total'])-s['returned']-s['paid']
    parsed=[]
    for ln in lines:
        if not isinstance(ln,dict):raise ValueError('To‘lov satri noto‘g‘ri.')
        m=ln.get('method')
        if m=='cash_uzs':
            cents,method,uzs,rate=shop._payment(db,{'method':m,'paidUzs':ln.get('amount'),'rate':ln.get('rate')},None)
            parsed.append((m,'UZS',uzs,cents,rate))
        else:
            cents,method,uzs,rate=shop._payment(db,{'method':m,'paid':ln.get('amount')},None)
            parsed.append((m,'USD',cents,cents,0))
        if cents<=0:raise ValueError('To‘lov summasini kiriting.')
    total=sum(x[3] for x in parsed)
    if total>left:raise ValueError(f'To‘lov (${total/100:.2f}) qolgan summadan (${left/100:.2f}) ko‘p.')
    ts=int(time.time() if now is None else now)
    tag=f'Buyurtma #{oid}'
    for i,(m,cur,amount,cents,rate) in enumerate(parsed):
        src=first+i*2
        db.execute('''INSERT INTO sale_order_payments(order_id,method,currency,amount,usd_cents,rate,actor,ts,source)
            VALUES(?,?,?,?,?,?,?,?,?)''',(oid,m,cur,amount,cents,rate,actor,ts,src))
        shop._insert_payment(db,actor,int(o['seller']),int(o['client']),cents,m,amount if cur=='UZS' else 0,rate,tag,src+1,ts)
    _log(db,oid,'pay',' + '.join((f'{a:,} so‘m'.replace(',',' ') if c=='UZS' else f'${a/100:.2f}')+(' karta' if m=='card' else '') for m,c,a,_,_ in parsed),actor,ts)
    return oid


def return_goods(db,actor,oid,pack,qty,reason,payload,now=None):
    """Qaytarish asl buyurtma qatoriga bog'lanadi: 'return' hodisasi va omborga kirim."""
    o=_order(db,oid);oid=int(o['id'])
    reason=str(reason or '').strip()
    if not reason:raise ValueError('Qaytarish sababini yozing.')
    pack=int(pack);qty=int(qty)
    line=db.execute('SELECT * FROM sale_order_lines WHERE order_id=? AND pack=?',(oid,pack)).fetchone()
    if not line:raise ValueError('Bu mahsulot buyurtmada yo‘q.')
    can=int(line['delivered'])-int(line['returned'])
    if not 0<qty<=can:raise ValueError(f'Qaytarish mumkin: {can} dona.')
    core.lock_agent(db,int(o['seller']))
    wh._lock_warehouse(db)
    source=_src(actor,payload,3000)
    if db.execute('SELECT 1 FROM events WHERE source=?',(source,)).fetchone():return oid
    amount=int(line['delivered_amount'])*qty//int(line['delivered']) if qty<can else int(line['delivered_amount'])-int(line['returned_amount'])
    ts=int(time.time() if now is None else now)
    db.execute('UPDATE sale_order_lines SET returned=returned+?,returned_amount=returned_amount+? WHERE id=?',(qty,amount,line['id']))
    db.execute('''INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
        VALUES(?,?,?,'return',?,?,0,?,?,?,?)''',(actor,int(o['seller']),int(o['client']),pack,qty,amount,f'Buyurtma #{oid} qaytarish: {reason[:200]}',ts,source))
    tok=wh.WEB_PRIMARY_OPERATOR.set(actor)
    try:wh._move(db,actor,'in',pack,qty,note=f'Buyurtma #{oid} qaytarildi',source=source+1)
    finally:wh.WEB_PRIMARY_OPERATOR.reset(tok)
    _log(db,oid,'return',f'{core.product_name(pack)} {qty} dona · {reason[:200]}',actor,ts)
    return oid


def cancel(db,actor,oid,reason,now=None):
    o=_order(db,oid);oid=int(o['id'])
    if o['status']!='open':raise ValueError('Buyurtma ochiq emas.')
    reason=str(reason or '').strip()
    if not reason:raise ValueError('Bekor qilish sababini yozing.')
    d,p,s=states(db,o)
    if s['qty_delivered'] or s['paid']:
        raise ValueError('Yetkazilgan yoki to‘langan buyurtmani bekor qilib bo‘lmaydi — avval qaytarish rasmiylashtirilsin.')
    ts=int(time.time() if now is None else now)
    db.execute("UPDATE sale_orders SET status='cancelled' WHERE id=?",(oid,))
    _log(db,oid,'cancel',reason[:300],actor,ts)
    return oid


# ---------- ko'rinishlar ----------

def view(db,oid):
    o=_order(db,oid)
    d,p,s=states(db,o)
    c=db.execute('SELECT name,shop_name,phone FROM clients WHERE id=?',(o['client'],)).fetchone()
    seller=db.execute('SELECT name FROM users WHERE id=?',(o['seller'],)).fetchone()
    return {'id':int(o['id']),'status':o['status'],'delivery':d,'deliveryLabel':DELIVERY[d],'payment':p,'paymentLabel':PAYMENT[p],
            'client':int(o['client']),'clientName':((c['shop_name'] or c['name']) if c else '') or '','phone':(c['phone'] if c else '') or '',
            'seller':seller[0] if seller else '','priceType':o['price_type'],'subtotal':int(o['subtotal']),'discount':int(o['discount']),
            'total':int(o['total']),'delivered':s['delivered'],'returned':s['returned'],'paid':s['paid'],
            'due':int(o['total'])-s['returned']-s['paid'],'deliveryDate':o['delivery_date'] or '','address':o['address'] or '',
            'note':o['note'] or '','ts':int(o['ts']),
            'lines':[{'pack':int(l['pack']),'name':core.product_name(int(l['pack'])),'qty':int(l['qty']),'listPrice':int(l['list_price']),
                      'price':int(l['price']),'discount':int(l['discount']),'total':int(l['total']),'delivered':int(l['delivered']),
                      'returned':int(l['returned']),'available':available(db,int(l['pack']))}
                     for l in db.execute('SELECT * FROM sale_order_lines WHERE order_id=? ORDER BY id',(o['id'],)).fetchall()],
            'payments':[{'method':r['method'],'currency':r['currency'],'amount':int(r['amount']),'usd':int(r['usd_cents']),
                         'rate':int(r['rate']),'ts':int(r['ts'])} for r in db.execute(
                'SELECT * FROM sale_order_payments WHERE order_id=? ORDER BY id',(o['id'],)).fetchall()],
            'log':[{'action':r['action'],'detail':r['detail'],'who':r['who'] or '','ts':int(r['ts'])} for r in db.execute(
                '''SELECT g.*,u.name AS who FROM sale_order_log g LEFT JOIN users u ON u.id=g.actor WHERE g.order_id=? ORDER BY g.id DESC''',
                (o['id'],)).fetchall()]}


def listing(db,actor,status='open',limit=100):
    import shop
    s=shop._require(db,actor)
    where=["o.status=?"] if status in ('open','cancelled') else []
    args=[status] if where else []
    if s['role']=='sales' and not shop.can(s,'all_sales'):
        where.append('o.seller=?');args.append(actor)   # doira: o'z buyurtmalari
    rows=db.execute('SELECT o.id FROM sale_orders o'+(' WHERE '+' AND '.join(where) if where else '')+' ORDER BY o.id DESC LIMIT ?',(*args,limit)).fetchall()
    return [view(db,int(r[0])) for r in rows]


def handle(db,actor,op,payload,now=None):
    """Savdo ilovasi va web panel uchun. Ruxsat: shop.py (sotuvchi) — doira shu yerda."""
    import shop
    s=shop._require(db,actor)
    op=str(op or 'list')
    oid=payload.get('orderId')
    if oid not in (None,''):
        o=_order(db,oid)
        if s['role']=='sales' and int(o['seller'])!=actor and not shop.can(s,'all_sales'):
            raise ValueError('Bu buyurtma sizniki emas.')
    if op=='list':return {'orders':listing(db,actor,payload.get('status') or 'open')}
    if op=='view':return {'order':view(db,oid)}
    if op=='create':oid=create(db,actor,payload,now=now)
    elif op=='deliver':deliver(db,actor,oid,payload.get('items'),payload,now=now)
    elif op=='pay':
        if not shop.can(s,'collect') and not shop.can(s,'retail'):raise ValueError('To‘lov qabul qilish ruxsati yo‘q.')
        pay(db,actor,oid,payload.get('payments'),payload,now=now)
    elif op=='return':return_goods(db,actor,oid,payload.get('pack'),payload.get('qty'),payload.get('reason'),payload,now=now)
    elif op=='cancel':cancel(db,actor,oid,payload.get('reason'),now=now)
    else:raise ValueError('Buyurtma amali noto‘g‘ri.')
    return {'order':view(db,oid)}
