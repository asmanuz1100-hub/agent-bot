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

KEEPER_ACTIONS=('dashboard','receive','issue','writeoff','decide')
AGENT_ACTIONS=('my','request')


def _role(db,uid):
    row=db.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
    return row[0] if row else None


def keeper_ids(db):
    return [int(r[0]) for r in db.execute("SELECT id FROM users WHERE role='warehouse'").fetchall()]


def _int(value,label,lo=1,hi=10**12):
    if isinstance(value,bool):raise ValueError(f'{label} нотўғри.')
    if isinstance(value,str):
        value=value.strip()
        if not re.fullmatch(r'-?[0-9]{1,13}',value):raise ValueError(f'{label} нотўғри.')
    try:n=int(value)
    except (TypeError,ValueError):raise ValueError(f'{label} нотўғри.')
    if n!=value and not isinstance(value,str):raise ValueError(f'{label} нотўғри.')
    if not lo<=n<=hi:raise ValueError(f'{label} нотўғри.')
    return n


def _pack(payload):
    pack=_int(payload.get('pack'),'Товар',0)
    if pack not in core.PRODUCTS:raise ValueError('Товар нотўғри.')
    return pack


def _qty(payload,pack):
    qty=_int(payload.get('qty'),'Миқдор',1,100000)
    unit=payload.get('unit') or 'Дона'
    if unit not in ('Дона','Блок'):raise ValueError('Ўлчов бирлиги нотўғри.')
    units=wh.to_units(pack,qty,unit)
    if units>100000:raise ValueError('Миқдор 1 дан 100000 донагача бўлсин.')
    return units


def _note(payload,required=False,label='Изоҳ'):
    note=str(payload.get('note') or '').strip()
    if len(note)>300:raise ValueError(f'{label} 300 белгидан ошмасин.')
    if required and not note:raise ValueError('Брак сабабини ёзинг.')
    return note


def _source(actor,payload):
    """Stable idempotency key from the Mini App requestId (double taps / retries)."""
    rid=payload.get('requestId')
    if rid is None:return None
    if not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,64}',rid):
        raise ValueError('Сўров идентификатори нотўғри.')
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


def keeper_dashboard(db,actor):
    core.refresh_catalog(db)
    data=wh.snapshot(db,actor)
    active=set(core.active_product_ids())
    for p in data['products']:p['active']=p['pack'] in active
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
        if action!='request':raise ValueError('Бу амал агент учун эмас.')
        kind=payload.get('kind')
        if kind not in wh.REQUEST_LABELS:raise ValueError('Сўров тури нотўғри.')
        pack=_pack(payload);qty=_qty(payload,pack)
        rid=wh.create_request(db,actor,kind,pack,qty,_note(payload),source=_source(actor,payload))
        data=agent_dashboard(db,actor)
        data['created']=rid
        text=(f"{wh.REQUEST_LABELS[kind]} #{rid}\n👤 {_name(db,actor)}\n📦 {core.product_name(pack)} · {_units_text(pack,qty)}"
              +(f"\n📝 {_note(payload)}" if _note(payload) else '')+"\n\nОмбор Mini Appда қабул ёки рад қилинг.")
        data['_notify']=[(set(keeper_ids(db))|set(core_admins(db)),text)]
        return data
    if role not in wh.KEEPER_ROLES:
        raise ValueError('Бу бўлим фақат омборчи, админ ёки агент учун.')
    if action=='dashboard':return keeper_dashboard(db,actor)
    if action not in KEEPER_ACTIONS:raise ValueError('Амал нотўғри.')
    source=_source(actor,payload)
    notify=[]
    if action=='receive':
        pack=_pack(payload);qty=_qty(payload,pack)
        move=wh.receive(db,actor,pack,qty,_note(payload),source=source)
        result={'move':move}
    elif action=='writeoff':
        pack=_pack(payload);qty=_qty(payload,pack)
        move=wh.write_off(db,actor,pack,qty,_note(payload,required=True,label='Сабаб'),source=source)
        result={'move':move}
    elif action=='issue':
        agent=_int(payload.get('agent'),'Агент')
        pack=_pack(payload);qty=_qty(payload,pack)
        move=wh.issue(db,actor,agent,pack,qty,_note(payload),source=source)
        result={'move':move}
        if move:
            notify.append(({agent},f"🚚 Омбордан товар берилди #{move}\n📦 {core.product_name(pack)} · {_units_text(pack,qty)}\n"
                                   f"Сизнинг қолдиғингиз: {core.agent_stock(db,agent,pack)} дона."))
    else:  # decide
        rid=_int(payload.get('id'),'Сўров рақами')
        accepted=payload.get('accepted') is True
        qty=payload.get('qty')
        qty=None if qty in (None,'') else _int(qty,'Миқдор',1,100000)
        res=wh.decide(db,actor,rid,accepted=accepted,qty=qty)
        result={'decided':res}
        verb='✅ қабул қилинди' if res['accepted'] else '❌ рад этилди'
        extra=f" (сўралган: {res['requested']} дона)" if res['accepted'] and res['qty']!=res['requested'] else ''
        notify.append(({res['agent']},f"{wh.REQUEST_LABELS[res['kind']]} #{res['id']} {verb}\n"
                                      f"📦 {core.product_name(res['pack'])} · {_units_text(res['pack'],res['qty'])}{extra}"))
    data=keeper_dashboard(db,actor)
    data.update(result)
    if notify:data['_notify']=notify
    return data


def core_admins(db):
    return [int(r[0]) for r in db.execute("SELECT id FROM users WHERE role='admin'").fetchall()]
