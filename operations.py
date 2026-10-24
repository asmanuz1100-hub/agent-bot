"""Amallar jurnali: agent, savdo, kassa, ombor va ta'minotda xodimlar kiritgan barcha yozuvlar bitta ro'yxatda.

Rahbar xato yozuvni (ikki marta kiritilgan to'lov, test sotuv va h.k.) shu yerdan bekor qiladi yoki tahrirlaydi.
Tamoyil corrections.py bilan bir xil — izsiz o'chirish yo'q:
- agent yozuvi (yetkazish, sotish, qaytarish, naqd to'lov) 'cancelled_*' turiga o'tadi — hech bir hisobot sanamaydi;
- savdo sotuvi, ta'minot xaridi, kassa kirimi/o'tkazmasi — mavjud bekor qilish funksiyalari;
- kassa xarajati arxiv jadvaliga ko'chiriladi (asl qatori to'liq saqlanadi), ombor kirimi/brak 'cancelled_*' bo'ladi;
- har bekor qilish `voids` jadvalida: kim, qachon, sabab.
Tahrirlash = eskisini bekor qilish + to'g'ri summa bilan yangisini yozish, bitta tranzaksiyada.
"""
import json
import time

import core
import corrections
from core import PostgresDB, product_name

SCHEMA='''
CREATE TABLE IF NOT EXISTS cancelled_expenses(id INTEGER PRIMARY KEY, data TEXT NOT NULL, actor INTEGER NOT NULL, reason TEXT NOT NULL, ts INTEGER NOT NULL);
'''
SOURCES={'agent':'Agent','sales':'Savdo','cash':'Kassa','warehouse':'Ombor','supply':'Ta’minot'}
AGENT_KINDS={'delivery':'Yetkazish (qarzga)','sold':'Sotish (naqd)','return':'Qaytarish','payment':'To‘lov'}
WH_KINDS={'in':'Omborga kirim','writeoff':'Brak / hisobdan chiqarish','issue':'Agentga berildi','agent_return':'Agentdan qaytdi',
          'correction_in':'Tuzatish (+)','correction_out':'Tuzatish (−)'}
LIMIT=400


def init(db):
    if isinstance(db,PostgresDB):
        db.execute(SCHEMA.replace('INTEGER PRIMARY KEY','BIGSERIAL PRIMARY KEY').replace(' INTEGER',' BIGINT'))
    else:
        db.executescript(SCHEMA)


def _usd(c):return round(int(c or 0)/100,2)


def _row(src,kind,ref,label,ts,who,amount=None,currency='USD',party='',detail='',status='active',cancel=None,
         can_cancel=False,can_edit=False,hint=''):
    return {'key':f'{kind}:{int(ref)}','source':src,'sourceLabel':SOURCES[src],'kind':kind,'ref':int(ref),'label':label,
            'ts':int(ts or 0),'who':who or '','amount':amount,'currency':currency,'party':party or '','detail':detail or '',
            'status':status,'cancel':cancel,'canCancel':bool(can_cancel and status=='active'),
            'canEdit':bool(can_edit and status=='active'),'hint':hint}


def _void_info(v):
    return {'who':v['who'],'ts':v['ts'],'reason':v['reason']} if v else None


def journal(db,start,end,source=None,q=''):
    q=str(q or '').strip().lower()
    items=[]
    want=lambda s:not source or source==s
    if want('agent'):
        void=corrections.voided(db,'agent_event');void.update(corrections.voided(db,'payment'))
        kinds=list(AGENT_KINDS)+['cancelled_'+k for k in AGENT_KINDS]
        ph=','.join('?'*len(kinds))
        for r in db.execute(f'''SELECT e.*,a.name AS agent_name,u.name AS who,c.name AS client_name,c.shop_name
            FROM events e LEFT JOIN users a ON a.id=e.agent LEFT JOIN users u ON u.id=e.actor LEFT JOIN clients c ON c.id=e.client
            WHERE e.agent IS NOT NULL AND e.kind IN ({ph}) AND e.ts>=? AND e.ts<? AND COALESCE(e.note,'') NOT LIKE ?
            ORDER BY e.ts DESC LIMIT ?''',(*kinds,start,end,'Savdo #%',LIMIT)).fetchall():
            k=str(r['kind']);base=k.replace('cancelled_','');off=k.startswith('cancelled_')
            card=(r['pay_method'] or '')=='card'
            uzs=int(r['paid_uzs'] or 0)
            amount,cur=(uzs,'UZS') if uzs else (_usd(r['amount_usd']),'USD')
            detail=(f"{product_name(int(r['pack']))} × {int(r['qty'])}" if int(r['pack'] or 0) and int(r['qty'] or 0) else '')
            if card:detail=(detail+' · ' if detail else '')+'karta'
            if r['note']:detail=(detail+' · ' if detail else '')+str(r['note'])[:120]
            items.append(_row('agent',k if not off else base,r['id'],AGENT_KINDS[base],r['ts'],r['agent_name'] or r['who'],
                amount,cur,r['shop_name'] or r['client_name'] or '',detail,'cancelled' if off else 'active',
                _void_info(void.get(int(r['id']))),can_cancel=not card,can_edit=base=='payment' and not card,
                hint='Karta to‘lovini kassir bo‘limida bekor qiling.' if card else ''))
    if want('sales'):
        void=corrections.voided(db,'sale')
        for r in db.execute('''SELECT s.*,u.name AS who,c.name AS client_name,c.shop_name FROM shop_sales s
            LEFT JOIN users u ON u.id=s.seller LEFT JOIN clients c ON c.id=s.client WHERE s.ts>=? AND s.ts<?
            ORDER BY s.ts DESC LIMIT ?''',(start,end,LIMIT)).fetchall():
            v=void.get(int(r['id']))
            detail=f"to‘landi {_usd(r['paid']):,.2f} $"+(f" · {r['note']}" if r['note'] else '')
            items.append(_row('sales','sale',r['id'],f"Sotuv #{int(r['id'])}",r['ts'],r['who'],_usd(r['total']),'USD',
                r['shop_name'] or r['client_name'] or '',detail,'cancelled' if v else 'active',_void_info(v),can_cancel=True,
                hint='Tarkibini o‘zgartirish: Savdo bo‘limida sotuvni tahrirlang.'))
    if want('cash'):
        import cashbook
        for r in db.execute('''SELECT m.*,u.name AS who,cu.name AS cancel_who FROM cash_moves m LEFT JOIN users u ON u.id=m.actor
            LEFT JOIN users cu ON cu.id=m.cancel_actor WHERE m.ts>=? AND m.ts<? ORDER BY m.ts DESC LIMIT ?''',(start,end,LIMIT)).fetchall():
            inc=r['kind']=='income';st='active' if r['status']=='active' else 'cancelled'
            cur=r['currency'];amount=_usd(r['amount']) if cur=='USD' else int(r['amount'])
            items.append(_row('cash','cash_move',r['id'],'Kassa kirimi' if inc else 'Kassa o‘tkazmasi',r['ts'],r['who'],amount,cur,
                r['counterparty'] if inc else f"{cashbook.POCKETS.get(r['from_pocket'],'')} → {cashbook.POCKETS.get(r['to_pocket'],'')}",
                ' · '.join(x for x in (r['category'] or '',r['note'] or '') if x),st,
                {'who':r['cancel_who'] or '','ts':int(r['cancel_ts'] or 0),'reason':r['cancel_reason'] or ''} if st!='active' else None,
                can_cancel=True,can_edit=True))
        linked=_linked_expenses(db)
        for r in db.execute('''SELECT e.*,u.name AS who FROM cashier_expenses e LEFT JOIN users u ON u.id=e.cashier
            WHERE e.ts>=? AND e.ts<? ORDER BY e.ts DESC LIMIT ?''',(start,end,LIMIT)).fetchall():
            uzs=(r['currency'] or 'USD')=='UZS'
            hint=linked.get(int(r['id']),'')
            items.append(_row('cash','expense',r['id'],'Kassa xarajati',r['ts'],r['who'],
                int(r['amount_uzs']) if uzs else _usd(r['amount_usd']),'UZS' if uzs else 'USD',r['recipient'] or '',
                ' · '.join(x for x in (r['category'] or '',r['note'] or '') if x),can_cancel=not hint,can_edit=not hint,hint=hint))
        for r in db.execute('''SELECT x.*,u.name AS who FROM cancelled_expenses x LEFT JOIN users u ON u.id=x.actor
            ORDER BY x.ts DESC LIMIT ?''',(LIMIT,)).fetchall():
            d=json.loads(r['data'])
            if not (start<=int(d.get('ts') or 0)<end):continue
            uzs=(d.get('currency') or 'USD')=='UZS'
            items.append(_row('cash','expense',d['id'],'Kassa xarajati',d['ts'],d.get('who') or '',
                int(d.get('amount_uzs') or 0) if uzs else _usd(d.get('amount_usd')),'UZS' if uzs else 'USD',d.get('recipient') or '',
                ' · '.join(x for x in (d.get('category') or '',d.get('note') or '') if x),'cancelled',
                {'who':r['who'] or '','ts':int(r['ts']),'reason':r['reason']}))
    if want('warehouse'):
        void=corrections.voided(db,'wh_move')
        kinds=list(WH_KINDS)+['cancelled_in','cancelled_writeoff']
        ph=','.join('?'*len(kinds))
        for r in db.execute(f'''SELECT m.*,u.name AS who,a.name AS agent_name FROM warehouse_moves m LEFT JOIN users u ON u.id=m.actor
            LEFT JOIN users a ON a.id=m.agent WHERE m.kind IN ({ph}) AND m.ts>=? AND m.ts<? ORDER BY m.ts DESC LIMIT ?''',
            (*kinds,start,end,LIMIT)).fetchall():
            k=str(r['kind']);off=k.startswith('cancelled_');base=k.replace('cancelled_','')
            simple=base in ('in','writeoff') and not str(r['note'] or '').startswith(('Xarid #','Харид #'))
            items.append(_row('warehouse','wh_move',r['id'],WH_KINDS[base],r['ts'],r['who'],None,'',
                r['agent_name'] or '',f"{product_name(int(r['pack']))} × {int(r['qty'])}"+(f" · {r['note']}" if r['note'] else ''),
                'cancelled' if off else 'active',_void_info(void.get(int(r['id']))),can_cancel=simple,
                hint='' if simple else 'Agentga berish/qaytarish va xarid kirimi o‘z bo‘limida tuzatiladi.'))
    if want('supply'):
        void=corrections.voided(db,'purchase')
        for r in db.execute('''SELECT p.*,u.name AS who,s.name AS supplier_name FROM purchases p LEFT JOIN users u ON u.id=p.actor
            LEFT JOIN suppliers s ON s.id=p.supplier WHERE p.ts>=? AND p.ts<? ORDER BY p.ts DESC LIMIT ?''',(start,end,LIMIT)).fetchall():
            v=void.get(int(r['id']))
            items.append(_row('supply','purchase',r['id'],f"Xarid #{int(r['id'])}",r['ts'],r['who'],_usd(r['total_usd']),'USD',
                r['supplier_name'] or '',r['note'] or '','cancelled' if v else 'active',_void_info(v),can_cancel=True,
                hint='Tarkibini o‘zgartirish: Ombor → Ta’minot bo‘limida xaridni tahrirlang.'))
    if q:
        items=[x for x in items if q in ' '.join(str(x[k]) for k in ('label','who','party','detail','sourceLabel','ref')).lower()]
    items.sort(key=lambda x:-x['ts'])
    items=items[:LIMIT]
    return {'items':items,'sources':SOURCES,
            'counts':{s:sum(1 for x in items if x['source']==s) for s in SOURCES},
            'cancelled':sum(1 for x in items if x['status']!='active')}


def _linked_expenses(db):
    """Ta'minot to'lovi va oylik bilan bog'langan xarajatlar faqat o'z bo'limida tuzatiladi."""
    out={}
    for sql,msg in (('SELECT expense FROM supplier_payments WHERE expense IS NOT NULL','Ta’minotchiga to‘lov — Ta’minot bo‘limida tuzating.'),
                    ('SELECT expense FROM hr_w_pay WHERE expense IS NOT NULL','Oylik/avans — Xodimlar bo‘limida tuzating.')):
        try:
            for r in db.execute(sql).fetchall():out[int(r[0])]=msg
        except Exception:
            if isinstance(db,PostgresDB):raise
    return out


# ---------- bekor qilish ----------

def cancel(db,actor,kind,ref,reason,now=None):
    corrections.require_admin(db,actor)
    reason=corrections._reason(reason)
    try:ref=int(ref)
    except (TypeError,ValueError):raise ValueError('Yozuv ID noto‘g‘ri.')
    ts=int(time.time() if now is None else now)
    if kind=='payment':
        return corrections.cancel_payment(db,actor,ref,reason,now=ts)
    if kind in ('delivery','sold','return'):
        return _cancel_agent_event(db,actor,ref,reason,ts)
    if kind=='sale':return corrections.cancel_sale(db,actor,ref,reason,now=ts)
    if kind=='purchase':return corrections.cancel_purchase(db,actor,ref,reason,now=ts)
    if kind=='cash_move':
        import cashbook
        cashbook.cancel(db,actor,ref,reason,now=ts);return ref
    if kind=='expense':return _cancel_expense(db,actor,ref,reason,ts)
    if kind=='wh_move':return _cancel_wh_move(db,actor,ref,reason,ts)
    raise ValueError('Bu turdagi yozuvni bekor qilib bo‘lmaydi.')


def _cancel_agent_event(db,actor,ref,reason,ts):
    ev=db.execute('SELECT * FROM events WHERE id=?',(ref,)).fetchone()
    if not ev or ev['kind'] not in ('delivery','sold','return') or ev['agent'] is None:
        raise ValueError('Yozuv topilmadi yoki allaqachon bekor qilingan.')
    if str(ev['note'] or '').startswith('Savdo #'):raise ValueError('Bu savdo sotuvi — uni Savdo yozuvi sifatida bekor qiling.')
    agent=int(ev['agent']);core.lock_agent(db,agent)
    kind=ev['kind'];pack=int(ev['pack'] or 0);qty=int(ev['qty'] or 0)
    # Qaytarish bekor bo'lsa tovar agentdan chiqadi — u agentda bo'lishi kerak.
    if kind=='return' and pack and core.agent_stock(db,agent,pack)<qty:
        raise ValueError(f'Agentda {product_name(pack)} {core.agent_stock(db,agent,pack)} dona qolgan — qaytarishni bekor qilib bo‘lmaydi.')
    # Yetkazish bekor bo'lsa tovar mijozdan chiqadi — mijoz uni sotib/qaytarib bo'lmagan bo'lishi kerak.
    if kind=='delivery' and pack and core.client_stock_total(db,int(ev['client']),pack)<qty:
        raise ValueError(f'Mijozda {product_name(pack)} yetarli emas (sotilgan yoki qaytarilgan) — avval o‘sha yozuvlarni bekor qiling.')
    corrections._mark(db,'agent_event',ref,actor,reason,ts)
    db.execute("UPDATE events SET kind='cancelled_'||kind WHERE id=?",(ref,))
    return ref


def _cancel_expense(db,actor,ref,reason,ts):
    import cashbook
    cashbook._lock(db)
    r=db.execute('SELECT e.*,u.name AS who FROM cashier_expenses e LEFT JOIN users u ON u.id=e.cashier WHERE e.id=?',(ref,)).fetchone()
    if not r:raise ValueError('Xarajat topilmadi yoki allaqachon bekor qilingan.')
    hint=_linked_expenses(db).get(ref)
    if hint:raise ValueError(hint)
    data={k:r[k] for k in r.keys()}
    db.execute('INSERT INTO cancelled_expenses(data,actor,reason,ts) VALUES(?,?,?,?)',
               (json.dumps(data,ensure_ascii=False,default=int),actor,reason,ts))
    db.execute('DELETE FROM cashier_expenses WHERE id=?',(ref,))
    corrections._mark(db,'expense',ref,actor,reason,ts)
    return ref


def _cancel_wh_move(db,actor,ref,reason,ts):
    import warehouse as wh
    wh._lock_warehouse(db)
    m=db.execute('SELECT * FROM warehouse_moves WHERE id=?',(ref,)).fetchone()
    if not m or m['kind'] not in ('in','writeoff'):raise ValueError('Bu ombor yozuvini bu yerdan bekor qilib bo‘lmaydi.')
    if str(m['note'] or '').startswith(('Xarid #','Харид #')):raise ValueError('Xarid kirimi — xaridni Ta’minot yozuvi sifatida bekor qiling.')
    if m['kind']=='in' and wh.stock(db,int(m['pack']))<int(m['qty']):
        raise ValueError(f"Omborda {product_name(int(m['pack']))} {wh.stock(db,int(m['pack']))} dona qolgan — kirimni bekor qilib bo‘lmaydi.")
    corrections._mark(db,'wh_move',ref,actor,reason,ts)
    db.execute("UPDATE warehouse_moves SET kind='cancelled_'||kind WHERE id=?",(ref,))
    return ref


# ---------- tahrirlash (summa va izoh) ----------

def edit(db,actor,kind,ref,amount,note,reason,source):
    """Eski yozuv bekor + to'g'ri summa bilan yangisi. Yangi yozuv ID qaytadi."""
    corrections.require_admin(db,actor)
    reason=corrections._reason(reason or 'Tahrirlandi')
    try:ref=int(ref)
    except (TypeError,ValueError):raise ValueError('Yozuv ID noto‘g‘ri.')
    if not isinstance(source,int) or source<=0:raise ValueError('Operatsiya ID noto‘g‘ri.')
    if kind=='payment':
        ev=db.execute('SELECT * FROM events WHERE id=?',(ref,)).fetchone()
        if not ev or ev['kind']!='payment':raise ValueError('To‘lov topilmadi yoki allaqachon bekor qilingan.')
        uzs=int(ev['paid_uzs'] or 0)
        cur='UZS' if uzs else 'USD'
        value=_parse(amount,cur)
        corrections.cancel_payment(db,actor,ref,reason)
        newnote=str(ev['note'] or '') if note is None else str(note).strip()[:300]
        if cur=='UZS':
            rate=int(ev['fx_rate'] or 0)
            if rate<=0:raise ValueError('Asl to‘lov kursi topilmadi — bekor qilib, qayta kiriting.')
            core.record_client_payment(db,actor,int(ev['agent']),int(ev['client']),'UZS',value,'cash',
                                       note=newnote,source=source,ts=int(ev['ts']),usd_cents=core.som_to_usd_cents(value,rate))
        else:
            core.record_client_payment(db,actor,int(ev['agent']),int(ev['client']),'USD',value,'cash',note=newnote,source=source,ts=int(ev['ts']))
        new=int(db.execute('SELECT id FROM events WHERE source=?',(source,)).fetchone()[0])
    elif kind=='cash_move':
        import cashbook
        m=db.execute('SELECT * FROM cash_moves WHERE id=?',(ref,)).fetchone()
        if not m or m['status']!='active':raise ValueError('Kassa yozuvi topilmadi yoki allaqachon bekor qilingan.')
        value=_parse(amount,m['currency'],raw=True)
        newnote=m['note'] if note is None else note
        cashbook.cancel(db,actor,ref,reason)
        if m['kind']=='income':
            new=cashbook.add_income(db,actor,m['to_pocket'],m['currency'],value,m['category'],m['counterparty'],newnote,source,
                                    now=int(m['ts']),client=m['client'] if m['client'] else None)
        else:
            new=cashbook.add_transfer(db,actor,m['from_pocket'],m['to_pocket'],m['currency'],value,newnote,source,now=int(m['ts']))
    elif kind=='expense':
        import cashbook
        r=db.execute('SELECT * FROM cashier_expenses WHERE id=?',(ref,)).fetchone()
        if not r:raise ValueError('Xarajat topilmadi yoki allaqachon bekor qilingan.')
        cur=(r['currency'] or 'USD')
        value=_parse(amount,cur,raw=True)
        newnote=r['note'] if note is None else note
        _cancel_expense(db,actor,ref,reason,int(time.time()))
        new=cashbook.add_expense(db,actor,r['pay_from'] or 'cash',cur,value,r['category'],r['recipient'],newnote,source)
        if new is None:raise ValueError('Takroriy so‘rov.')
    else:
        raise ValueError('Bu yozuvni faqat bekor qilish mumkin. To‘g‘risini o‘z bo‘limida qayta kiriting.')
    if kind!='cash_move':corrections.link_replacement(db,kind,ref,new)   # kassa harakati o'z holatini cash_moves'da saqlaydi
    return int(new)


def _parse(amount,currency,raw=False):
    """USD: «12.50» → 1250 sent (raw=True bo'lsa matn qaytadi — cashbook o'zi tekshiradi). UZS: butun so'm."""
    s=str(amount if amount is not None else '').replace(' ','').replace(',','.').strip()
    if raw:
        if not s:raise ValueError('Yangi summani kiriting.')
        return s
    try:
        if currency=='UZS':
            v=int(float(s))
        else:
            v=int(round(float(s)*100))
    except ValueError:
        raise ValueError('Summa noto‘g‘ri.')
    if v<=0:raise ValueError('Summa noldan katta bo‘lsin.')
    return v
