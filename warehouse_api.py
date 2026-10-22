"""Омбор Mini App API: омборчи (warehouse/admin) ва агент сўровлари.

Ҳамма ҳисоб-китоб warehouse.py да; бу модуль фақат киришни текширади,
сўровни таҳлил қилади ва хабарномаларни тайёрлайди (`_notify`).
Хабарномалар фақат commitдан кейин юборилади (bot.py).
"""
import hashlib
import re
import time

import core
import warehouse as wh

KEEPER_ACTIONS=('dashboard','receive','issue','writeoff','decide','take_back','orders','order_status','moves')
ORDER_FILTERS=('open','new','preparing','loaded','delivered','rejected')
AGENT_ACTIONS=('my','request')


def _role(db,uid):
    row=db.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
    return row[0] if row else None


def keeper_ids(db):
    return [int(r[0]) for r in db.execute("SELECT id FROM users WHERE role='warehouse'").fetchall()]


def _int(value,label,lo=1,hi=10**12):
    if isinstance(value,bool):raise ValueError(f'{label} noto‘g‘ri.')
    if isinstance(value,str):
        value=value.strip()
        if not re.fullmatch(r'-?[0-9]{1,13}',value):raise ValueError(f'{label} noto‘g‘ri.')
    try:n=int(value)
    except (TypeError,ValueError):raise ValueError(f'{label} noto‘g‘ri.')
    if n!=value and not isinstance(value,str):raise ValueError(f'{label} noto‘g‘ri.')
    if not lo<=n<=hi:raise ValueError(f'{label} noto‘g‘ri.')
    return n


def _pack(payload):
    pack=_int(payload.get('pack'),'Mahsulot',0)
    if pack not in core.PRODUCTS:raise ValueError('Mahsulot noto‘g‘ri.')
    return pack


def _qty(payload,pack):
    qty=_int(payload.get('qty'),'Miqdor',1,100000)
    unit=payload.get('unit') or 'Дона'
    if unit not in ('Дона','Блок'):raise ValueError('O‘lchov birligi noto‘g‘ri.')
    units=wh.to_units(pack,qty,unit)
    if units>100000:raise ValueError('Miqdor 1 dan 100000 donagacha bo‘lsin.')
    return units


def _note(payload,required=False,label='Izoh'):
    note=str(payload.get('note') or '').strip()
    if len(note)>300:raise ValueError(f'{label} 300 belgidan oshmasin.')
    if required and not note:raise ValueError(f'{label}ni yozing.')
    return note


def _source(actor,payload):
    """Stable idempotency key from the Mini App requestId (double taps / retries)."""
    rid=payload.get('requestId')
    if rid is None:return None
    if not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,64}',rid):
        raise ValueError('So‘rov identifikatori noto‘g‘ri.')
    digest=hashlib.sha256(f'wh:{actor}:{rid}'.encode()).hexdigest()
    return int(digest[:15],16)


def _name(db,uid):
    row=db.execute('SELECT name FROM users WHERE id=?',(uid,)).fetchone()
    return row[0] if row else str(uid)


def _units_text(pack,qty):
    block=core.block_units(pack)
    if block and qty>=block:
        return f'{qty} дона ({qty//block} блок' + (f' + {qty%block} дона)' if qty%block else ')')
    return f'{qty} дона'


def order_list(db,status='open',limit=100):
    """Омборчи учун мижоз буюртмалари (нархсиз) ва омбордаги қолдиқ билан солиштириш."""
    status=str(status or 'open')
    if status not in ORDER_FILTERS:raise ValueError('Buyurtma holati noto‘g‘ri.')
    statuses=core.ORDER_OPEN if status=='open' else (status,)
    rows=db.execute(f"""SELECT o.*,u.name AS agent_name,COALESCE(c.shop_name,c.name) AS client_name,c.address AS client_address
        FROM orders o LEFT JOIN users u ON u.id=o.agent LEFT JOIN clients c ON c.id=o.client
        WHERE o.status IN ({','.join('?' for _ in statuses)})
        ORDER BY CASE o.status WHEN 'new' THEN 0 WHEN 'preparing' THEN 1 ELSE 2 END,
                 CASE WHEN o.status IN ('new','preparing') THEN o.ts ELSE -o.updated_ts END,o.id
        LIMIT ?""",(*statuses,limit)).fetchall()
    stock={}
    out=[]
    for r in rows:
        v=core.order_view(db,r)
        items=[]
        for i in v['items']:
            have=None
            if i['pack'] is not None:
                if i['pack'] not in stock:stock[i['pack']]=wh.stock(db,i['pack'])
                have=stock[i['pack']]
            items.append({'pack':i['pack'],'name':i['name'],'qty':i['qty'],'custom':i['custom'],
                          'block':core.block_units(i['pack']) or 0 if i['pack'] is not None else 0,'stock':have})
        out.append({'id':v['id'],'status':v['status'],'agent':v['agentId'],'agent_name':r['agent_name'] or str(r['agent']),
                    'client':v['clientId'],'client_name':r['client_name'] or f"#{r['client']}",
                    'client_address':r['client_address'] or '','note':v['note'],'admin_note':v['adminNote'],
                    'ts':v['ts'],'updated_ts':v['updatedTs'],'unmapped':v['unmapped'],'items':items,
                    'ready':not v['unmapped'] and all(i['stock'] is not None and i['stock']>=i['qty'] for i in items)})
    counts={s:0 for s in core.ORDER_STATUSES}
    for r in db.execute('SELECT status,COUNT(*) FROM orders GROUP BY status').fetchall():
        counts[r[0]]=int(r[1])
    return {'filter':status,'counts':counts,'list':out}


def keeper_dashboard(db,actor,order_filter='open'):
    core.refresh_catalog(db)
    data=wh.snapshot(db,actor)
    active=set(core.active_product_ids())
    for p in data['products']:p['active']=p['pack'] in active
    data['orders']=order_list(db,order_filter)
    data['labels']={'moves':wh.MOVE_LABELS,'requests':wh.REQUEST_LABELS}
    data['mode']='keeper'
    return data


def agent_dashboard(db,agent):
    if _role(db,agent)!='agent':raise ValueError('Бу бўлим фақат агент учун.')
    core.refresh_catalog(db)
    products=[]
    for p in core.active_product_ids():
        have=core.agent_stock(db,agent,p)
        products.append({'pack':p,'name':core.PRODUCTS[p],'block':core.block_units(p) or 0,
                         'stock':have,'free':max(have-wh.reserved_return(db,agent,p),0)})
    reqs=[{'id':int(r['id']),'kind':r['kind'],'pack':int(r['pack']),'name':core.product_name(r['pack']),
           'qty':int(r['qty']),'status':r['status'],'note':r['note'] or '','ts':int(r['ts'])}
          for r in wh.agent_requests(db,agent,20)]
    return {'mode':'agent','me':{'id':agent,'role':'agent','name':_name(db,agent)},
            'products':products,'requests':reqs,
            'labels':{'requests':wh.REQUEST_LABELS,'status':wh.STATUS_LABELS}}


def handle(db,actor,action,payload):
    """Dispatch one Mini App call. Returns JSON-able dict; '_notify' = [(user_ids, text)]."""
    role=_role(db,actor)
    action=str(action or 'dashboard')
    if role=='agent':
        if action in ('dashboard','my'):return agent_dashboard(db,actor)
        if action!='request':raise ValueError('Bu amal agent uchun emas.')
        kind=payload.get('kind')
        if kind not in wh.REQUEST_LABELS:raise ValueError('So‘rov turi noto‘g‘ri.')
        pack=_pack(payload);qty=_qty(payload,pack)
        rid=wh.create_request(db,actor,kind,pack,qty,_note(payload),source=_source(actor,payload))
        data=agent_dashboard(db,actor)
        data['created']=rid
        text=(f"{wh.REQUEST_LABELS[kind]} #{rid}\n👤 {_name(db,actor)}\n📦 {core.product_name(pack)} · {_units_text(pack,qty)}"
              +(f"\n📝 {_note(payload)}" if _note(payload) else '')+"\n\nОмбор Mini Appда қабул ёки рад қилинг.")
        data['_notify']=[(set(keeper_ids(db))|set(core_admins(db)),text)]
        return data
    if role not in wh.KEEPER_ROLES:
        raise ValueError('Bu bo‘lim faqat omborchi, rahbar yoki agent uchun.')
    order_filter=payload.get('orderFilter') or 'open'
    if action=='dashboard':return keeper_dashboard(db,actor,order_filter)
    if action not in KEEPER_ACTIONS:raise ValueError('Amal noto‘g‘ri.')
    if action=='orders':return {'orders':order_list(db,payload.get('status'))}
    if action=='moves':
        kind=payload.get('kind') or None
        if kind is not None and kind not in wh.MOVE_LABELS:raise ValueError('Harakat turi noto‘g‘ri.')
        pack=None if payload.get('pack') in (None,'') else _pack(payload)
        agent=None if payload.get('agent') in (None,'') else _int(payload.get('agent'),'Agent')
        before=None if payload.get('before') in (None,'') else _int(payload.get('before'),'Sahifa')
        rows=wh.recent_moves(db,50,kind=kind,pack=pack,agent=agent,before=before)
        return {'moves':[wh.move_view(m) for m in rows],'more':len(rows)==50}
    source=_source(actor,payload)
    notify=[]
    orders=[]
    if action=='receive':
        pack=_pack(payload);qty=_qty(payload,pack)
        move=wh.receive(db,actor,pack,qty,_note(payload),source=source)
        result={'move':move}
    elif action=='writeoff':
        pack=_pack(payload);qty=_qty(payload,pack)
        move=wh.write_off(db,actor,pack,qty,_note(payload,required=True,label='Brak sababi'),source=source)
        result={'move':move}
    elif action=='take_back':
        agent=_int(payload.get('agent'),'Agent')
        pack=_pack(payload);qty=_qty(payload,pack)
        move=wh.take_back(db,actor,agent,pack,qty,_note(payload),source=source)
        result={'move':move}
        if move:
            notify.append(({agent},f"↩️ Омборга қабул қилинди #{move}\n📦 {core.product_name(pack)} · {_units_text(pack,qty)}\n"
                                   f"Сизнинг қолдиғингиз: {core.agent_stock(db,agent,pack)} дона."))
    elif action=='order_status':
        oid=_int(payload.get('id'),'Buyurtma raqami')
        to=str(payload.get('to') or '')
        if to not in ('preparing','loaded','rejected','new'):raise ValueError('Buyurtma holati noto‘g‘ri.')
        note=str(payload.get('note') or '').strip()
        if len(note)>300:raise ValueError('Izoh 300 belgidan oshmasin.')
        core.set_order_status(db,actor,oid,to,note)
        result={'order':oid}
        orders.append(oid)
    elif action=='issue':
        agent=_int(payload.get('agent'),'Агент')
        pack=_pack(payload);qty=_qty(payload,pack)
        move=wh.issue(db,actor,agent,pack,qty,_note(payload),source=source)
        result={'move':move}
        if move:
            notify.append(({agent},f"🚚 Омбордан товар берилди #{move}\n📦 {core.product_name(pack)} · {_units_text(pack,qty)}\n"
                                   f"Сизнинг қолдиғингиз: {core.agent_stock(db,agent,pack)} дона."))
    else:  # decide
        rid=_int(payload.get('id'),'So‘rov raqami')
        accepted=payload.get('accepted') is True
        qty=payload.get('qty')
        qty=None if qty in (None,'') else _int(qty,'Miqdor',1,100000)
        res=wh.decide(db,actor,rid,accepted=accepted,qty=qty)
        result={'decided':res}
        verb='✅ қабул қилинди' if res['accepted'] else '❌ рад этилди'
        extra=f" (сўралган: {res['requested']} дона)" if res['accepted'] and res['qty']!=res['requested'] else ''
        notify.append(({res['agent']},f"{wh.REQUEST_LABELS[res['kind']]} #{res['id']} {verb}\n"
                                      f"📦 {core.product_name(res['pack'])} · {_units_text(res['pack'],res['qty'])}{extra}"))
    data=keeper_dashboard(db,actor,order_filter)
    data.update(result)
    if notify:data['_notify']=notify
    if orders:data['_orders']=orders
    return data


def core_admins(db):
    return [int(r[0]) for r in db.execute("SELECT id FROM users WHERE role='admin'").fetchall()]
