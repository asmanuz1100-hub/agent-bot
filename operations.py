"""Amallar jurnali: tizimdagi barcha xodimlar (agent, savdo, kassir, omborchi, rahbar) kiritgan yozuvlar bitta joyda.

Rahbar har qanday xato yozuvni shu yerdan bekor qiladi (o'chiradi) yoki tahrirlaydi — boshqa bo'limga o'tish shart emas.
Faqat rahbar/admin (role='admin') bajaradi. Izsiz o'chirish yo'q:
- agent yozuvlari va ombor harakatlari 'cancelled_*' turiga o'tadi — hech bir hisobot sanamaydi, bazada qoladi;
- savdo sotuvi, ta'minot xaridi, kassa kirimi/o'tkazmasi — corrections.py / cashbook.py dagi bekor qilish;
- boshqa yozuvlar (kassa xarajati, ta'minotchiga to'lov, oylik, konvertatsiya, agent hisobiga pul) asl qatori bilan
  `archived_rows` jadvaliga ko'chiriladi;
- har bekor qilish `voids` jadvalida: kim, qachon, sabab; tahrir bo'lsa yangi yozuvga bog'lanadi.
Tahrirlash = eskisini bekor qilish + to'g'ri qiymatlar bilan yangisini yozish, bitta tranzaksiyada. Shu sabab qoldiq,
qarz, kassa va hisobotlar doim mos qoladi; qoldiq yetmasa (pul topshirilgan, tovar sotilgan) tizim sababini aytadi.
"""
import json
import time
from decimal import Decimal, InvalidOperation

import core
import corrections
from core import PostgresDB, product_name

SCHEMA='''
CREATE TABLE IF NOT EXISTS archived_rows(id INTEGER PRIMARY KEY, tbl TEXT NOT NULL, ref INTEGER NOT NULL, data TEXT NOT NULL, actor INTEGER NOT NULL, reason TEXT NOT NULL, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_archived_rows_tbl ON archived_rows(tbl,ts);
'''
SOURCES={'agent':'Agent','sales':'Savdo','cash':'Kassa','warehouse':'Ombor','supply':'Ta’minot','staff':'Xodimlar'}
AGENT_KINDS={'delivery':'Yetkazish (qarzga)','sold':'Sotish','return':'Qaytarish','payment':'To‘lov'}
WH_KINDS={'in':'Omborga kirim','writeoff':'Brak / hisobdan chiqarish','issue':'Agentga berildi','agent_return':'Agentdan qaytdi'}
LIMIT=500


def init(db):
    if isinstance(db,PostgresDB):
        for stmt in SCHEMA.replace('INTEGER PRIMARY KEY','BIGSERIAL PRIMARY KEY').replace(' INTEGER',' BIGINT').split(';'):
            if stmt.strip():db.execute(stmt)
    else:
        db.executescript(SCHEMA)


def _usd(c):return round(int(c or 0)/100,2)
def _join(*xs):return ' · '.join(str(x) for x in xs if x)


def _row(src,kind,ref,label,ts,who,amount=None,currency='USD',party='',detail='',status='active',cancel=None):
    return {'key':f'{kind}:{int(ref)}','source':src,'sourceLabel':SOURCES[src],'kind':kind,'ref':int(ref),'label':label,
            'ts':int(ts or 0),'who':who or '','amount':amount,'currency':currency,'party':party or '','detail':detail or '',
            'status':status,'cancel':cancel,'canCancel':status=='active','canEdit':status=='active'}


def _vinfo(v):return {'who':v['who'],'ts':v['ts'],'reason':v['reason']} if v else None


def _archived(db,tbl,start,end):
    out=[]
    for r in db.execute('''SELECT x.*,u.name AS who FROM archived_rows x LEFT JOIN users u ON u.id=x.actor
        WHERE x.tbl=? ORDER BY x.ts DESC LIMIT ?''',(tbl,LIMIT)).fetchall():
        d=json.loads(r['data'])
        if start<=int(d.get('ts') or 0)<end:out.append((d,{'who':r['who'] or '','ts':int(r['ts']),'reason':r['reason']}))
    return out


def _names(db):
    return {int(r['id']):r['name'] or str(r['id']) for r in db.execute('SELECT id,name FROM users').fetchall()}


# ======================= JURNAL =======================

def journal(db,start,end,source=None,q=''):
    import cashbook
    q=str(q or '').strip().lower()
    items=[];names=_names(db)
    want=lambda s:not source or source==s
    if want('agent'):
        void=corrections.voided(db,'agent_event');void.update(corrections.voided(db,'payment'))
        kinds=list(AGENT_KINDS)+['cancelled_'+k for k in AGENT_KINDS]
        ph=','.join('?'*len(kinds))
        for r in db.execute(f'''SELECT e.*,c.name AS client_name,c.shop_name FROM events e LEFT JOIN clients c ON c.id=e.client
            WHERE e.agent IS NOT NULL AND e.kind IN ({ph}) AND e.ts>=? AND e.ts<? AND COALESCE(e.note,'') NOT LIKE ?
            ORDER BY e.ts DESC LIMIT ?''',(*kinds,start,end,'Savdo #%',LIMIT)).fetchall():
            k=str(r['kind']);base=k.replace('cancelled_','');off=k.startswith('cancelled_')
            card=(r['pay_method'] or '')=='card';uzs=int(r['paid_uzs'] or 0)
            amount,cur=(uzs,'UZS') if uzs else (_usd(r['amount_usd']),'USD')
            prod=f"{product_name(int(r['pack']))} × {int(r['qty'])}" if int(r['pack'] or 0) and int(r['qty'] or 0) else ''
            items.append(_row('agent',base,r['id'],AGENT_KINDS[base]+(' (karta)' if card else ''),r['ts'],names.get(int(r['agent']),''),
                amount if base=='payment' or amount else None,cur,r['shop_name'] or r['client_name'] or '',
                _join(prod,str(r['note'] or '')[:120]),'cancelled' if off else 'active',_vinfo(void.get(int(r['id'])))))
        void=corrections.voided(db,'handover')
        for r in db.execute('''SELECT h.* FROM handovers h WHERE h.status IN ('accepted','cancelled')
            AND COALESCE(h.accepted_ts,h.ts)>=? AND COALESCE(h.accepted_ts,h.ts)<? ORDER BY h.ts DESC LIMIT ?''',(start,end,LIMIT)).fetchall():
            som=int(r['amount'] or 0)//100
            items.append(_row('agent','handover',r['id'],'Kassaga topshirdi',r['accepted_ts'] or r['ts'],names.get(int(r['agent'] or 0),''),
                som if som else _usd(r['amount_usd']),'UZS' if som else 'USD','Kassir: '+names.get(int(r['cashier'] or 0),''),'',
                'active' if r['status']=='accepted' else 'cancelled',_vinfo(void.get(int(r['id'])))))
    if want('sales'):
        void=corrections.voided(db,'sale')
        for r in db.execute('''SELECT s.*,c.name AS client_name,c.shop_name FROM shop_sales s LEFT JOIN clients c ON c.id=s.client
            WHERE s.ts>=? AND s.ts<? ORDER BY s.ts DESC LIMIT ?''',(start,end,LIMIT)).fetchall():
            v=void.get(int(r['id']))
            lines=db.execute('SELECT pack,qty FROM shop_sale_lines WHERE sale=? ORDER BY id',(r['id'],)).fetchall()
            items.append(_row('sales','sale',r['id'],f"Sotuv #{int(r['id'])}",r['ts'],names.get(int(r['seller']),''),_usd(r['total']),'USD',
                r['shop_name'] or r['client_name'] or '',_join(', '.join(f"{product_name(int(l['pack']))} × {int(l['qty'])}" for l in lines),
                f"to‘landi {_usd(r['paid']):,.2f} $",r['note']),'cancelled' if v else 'active',_vinfo(v)))
    if want('cash'):
        for r in db.execute('''SELECT m.*,cu.name AS cancel_who FROM cash_moves m LEFT JOIN users cu ON cu.id=m.cancel_actor
            WHERE m.ts>=? AND m.ts<? ORDER BY m.ts DESC LIMIT ?''',(start,end,LIMIT)).fetchall():
            inc=r['kind']=='income';st='active' if r['status']=='active' else 'cancelled'
            cur=r['currency']
            items.append(_row('cash','cash_move',r['id'],'Kassa kirimi' if inc else 'Kassa o‘tkazmasi',r['ts'],names.get(int(r['actor']),''),
                _usd(r['amount']) if cur=='USD' else int(r['amount']),cur,
                r['counterparty'] if inc else f"{cashbook.POCKETS.get(r['from_pocket'],'')} → {cashbook.POCKETS.get(r['to_pocket'],'')}",
                _join(r['category'],r['note']),st,
                {'who':r['cancel_who'] or '','ts':int(r['cancel_ts'] or 0),'reason':r['cancel_reason'] or ''} if st!='active' else None))
        linked=_linked_expenses(db)
        exp=lambda d,st,c:_row('cash','expense',d['id'],'Kassa xarajati',d['ts'],names.get(int(d.get('cashier') or 0),''),
            int(d.get('amount_uzs') or 0) if (d.get('currency') or 'USD')=='UZS' else _usd(d.get('amount_usd')),
            'UZS' if (d.get('currency') or 'USD')=='UZS' else 'USD',d.get('recipient') or '',_join(d.get('category'),d.get('note')),st,c)
        for r in db.execute('SELECT * FROM cashier_expenses WHERE ts>=? AND ts<? ORDER BY ts DESC LIMIT ?',(start,end,LIMIT)).fetchall():
            if int(r['id']) not in linked:items.append(exp(dict(r),'active',None))   # bog'langanlari o'z yozuvi bilan chiqadi
        for d,c in _archived(db,'cashier_expenses',start,end):
            if not str(c['reason']).startswith(('Ta’minot to‘lovi #','Oylik to‘lovi #')):items.append(exp(d,'cancelled',c))
        conv=lambda d,st,c:_row('cash','conversion',d['id'],'Konvertatsiya',d['ts'],names.get(int(d.get('cashier') or 0),''),
            _usd(d['amount_from']) if d['from_currency']=='USD' else int(d['amount_from']),d['from_currency'],
            f"→ {(_usd(d['amount_to']) if d['from_currency']=='UZS' else int(d['amount_to'])):,} {'USD' if d['from_currency']=='UZS' else 'UZS'}",
            _join(f"kurs {int(d.get('rate_uzs_per_usd') or 0):,}",d.get('note')),st,c)
        for r in db.execute('SELECT * FROM cashier_conversions WHERE ts>=? AND ts<? ORDER BY ts DESC LIMIT ?',(start,end,LIMIT)).fetchall():
            items.append(conv(dict(r),'active',None))
        for d,c in _archived(db,'cashier_conversions',start,end):items.append(conv(d,'cancelled',c))
        fund=lambda d,st,c:_row('cash','agent_fund',d['id'],'Agent xarajat hisobiga',d['ts'],names.get(int(d.get('actor') or 0),''),
            int(d['amount_uzs']) if int(d.get('amount_uzs') or 0) else _usd(d['amount_usd']),'UZS' if int(d.get('amount_uzs') or 0) else 'USD',
            names.get(int(d.get('agent') or 0),''),d.get('note') or '',st,c)
        for r in db.execute("SELECT * FROM agent_funds WHERE kind='topup' AND ts>=? AND ts<? ORDER BY ts DESC LIMIT ?",(start,end,LIMIT)).fetchall():
            items.append(fund(dict(r),'active',None))
        for d,c in _archived(db,'agent_funds',start,end):items.append(fund(d,'cancelled',c))
    if want('warehouse'):
        void=corrections.voided(db,'wh_move')
        kinds=list(WH_KINDS)+['cancelled_'+k for k in WH_KINDS]
        ph=','.join('?'*len(kinds))
        for r in db.execute(f'''SELECT * FROM warehouse_moves WHERE kind IN ({ph}) AND ts>=? AND ts<? AND COALESCE(note,'') NOT LIKE ?
            ORDER BY ts DESC LIMIT ?''',(*kinds,start,end,'Xarid #%',LIMIT)).fetchall():
            k=str(r['kind']);off=k.startswith('cancelled_');base=k.replace('cancelled_','')
            items.append(_row('warehouse','wh_move',r['id'],WH_KINDS[base],r['ts'],names.get(int(r['actor']),''),None,'',
                names.get(int(r['agent'] or 0),'') if r['agent'] else '',_join(f"{product_name(int(r['pack']))} × {int(r['qty'])}",r['note']),
                'cancelled' if off else 'active',_vinfo(void.get(int(r['id'])))))
    if want('supply'):
        void=corrections.voided(db,'purchase')
        for r in db.execute('''SELECT p.*,s.name AS supplier_name FROM purchases p LEFT JOIN suppliers s ON s.id=p.supplier
            WHERE p.ts>=? AND p.ts<? ORDER BY p.ts DESC LIMIT ?''',(start,end,LIMIT)).fetchall():
            v=void.get(int(r['id']))
            items.append(_row('supply','purchase',r['id'],f"Xarid #{int(r['id'])}",r['ts'],names.get(int(r['actor']),''),_usd(r['total_usd']),'USD',
                r['supplier_name'] or '',r['note'] or '','cancelled' if v else 'active',_vinfo(v)))
        sup={int(r['id']):r['name'] for r in db.execute('SELECT id,name FROM suppliers').fetchall()}
        sp=lambda d,st,c:_row('supply','supplier_payment',d['id'],'Ta’minotchiga to‘lov',d['ts'],names.get(int(d.get('actor') or 0),''),
            _usd(d['amount_usd']),'USD',sup.get(int(d['supplier']),''),d.get('note') or '',st,c)
        for r in db.execute('SELECT * FROM supplier_payments WHERE ts>=? AND ts<? ORDER BY ts DESC LIMIT ?',(start,end,LIMIT)).fetchall():
            items.append(sp(dict(r),'active',None))
        for d,c in _archived(db,'supplier_payments',start,end):items.append(sp(d,'cancelled',c))
    if want('staff'):
        import hr
        workers={int(r['id']):r['name'] for r in db.execute('SELECT id,name FROM hr_workers').fetchall()}
        def hp(d,st,c):
            uzs=d.get('paid_currency')=='UZS' and int(d.get('paid_amount') or 0)
            return _row('staff','hr_pay',d['id'],hr.PAY_KINDS.get(d['kind'],d['kind'])+' · '+str(d.get('month') or ''),d['ts'],
                names.get(int(d.get('actor') or 0),''),int(d['paid_amount']) if uzs else _usd(d.get('paid_amount') or d['amount']),
                'UZS' if uzs else 'USD',workers.get(int(d['worker_id']),''),d.get('note') or '',st,c)
        for r in db.execute('SELECT * FROM hr_w_pay WHERE ts>=? AND ts<? ORDER BY ts DESC LIMIT ?',(start,end,LIMIT)).fetchall():
            items.append(hp(dict(r),'active',None))
        for d,c in _archived(db,'hr_w_pay',start,end):items.append(hp(d,'cancelled',c))
    if q:
        items=[x for x in items if q in ' '.join(str(x[k]) for k in ('label','who','party','detail','sourceLabel','ref')).lower()]
    items.sort(key=lambda x:-x['ts'])
    items=items[:LIMIT]
    return {'items':items,'sources':SOURCES,'cancelled':sum(1 for x in items if x['status']!='active')}


def _linked_expenses(db):
    out={}
    for sql in ('SELECT expense FROM supplier_payments WHERE expense IS NOT NULL','SELECT expense FROM hr_w_pay WHERE expense IS NOT NULL'):
        for r in db.execute(sql).fetchall():out[int(r[0])]=True
    return out


# ======================= ARXIV =======================

def _archive(db,tbl,ref,actor,reason,ts):
    row=db.execute(f'SELECT * FROM {tbl} WHERE id=?',(int(ref),)).fetchone()
    if not row:raise ValueError('Yozuv topilmadi yoki allaqachon bekor qilingan.')
    data={k:row[k] for k in row.keys()}
    db.execute('INSERT INTO archived_rows(tbl,ref,data,actor,reason,ts) VALUES(?,?,?,?,?,?)',
               (tbl,int(ref),json.dumps(data,ensure_ascii=False,default=int),actor,reason,ts))
    db.execute(f'DELETE FROM {tbl} WHERE id=?',(int(ref),))
    return data


# ======================= BEKOR QILISH =======================

def cancel(db,actor,kind,ref,reason,now=None):
    corrections.require_admin(db,actor)
    reason=corrections._reason(reason)
    try:ref=int(ref)
    except (TypeError,ValueError):raise ValueError('Yozuv ID noto‘g‘ri.')
    ts=int(time.time() if now is None else now)
    fn=_CANCEL.get(kind)
    if not fn:raise ValueError('Bu turdagi yozuv noma’lum.')
    fn(db,actor,ref,reason,ts)
    return ref


def _c_payment(db,actor,ref,reason,ts):
    ev=db.execute('SELECT * FROM events WHERE id=?',(ref,)).fetchone()
    if ev is not None and (ev['pay_method'] or '')=='card' and ev['kind']=='payment':
        core.lock_agent(db,int(ev['agent']))
        corrections._mark(db,'payment',ref,actor,reason,ts)
        db.execute("UPDATE events SET kind='cancelled_payment' WHERE id=?",(ref,))
        return
    corrections.cancel_payment(db,actor,ref,reason,now=ts)


def _c_agent_event(db,actor,ref,reason,ts):
    ev=db.execute('SELECT * FROM events WHERE id=?',(ref,)).fetchone()
    if not ev or ev['kind'] not in ('delivery','sold','return') or ev['agent'] is None:
        raise ValueError('Yozuv topilmadi yoki allaqachon bekor qilingan.')
    if str(ev['note'] or '').startswith('Savdo #'):raise ValueError('Bu savdo sotuvining qismi — Savdo yozuvini bekor qiling.')
    agent=int(ev['agent']);core.lock_agent(db,agent)
    kind=ev['kind'];pack=int(ev['pack'] or 0);qty=int(ev['qty'] or 0)
    if kind=='return' and pack and core.agent_stock(db,agent,pack)<qty:
        raise ValueError(f'Agentda {product_name(pack)} {core.agent_stock(db,agent,pack)} dona qolgan — qaytarishni bekor qilib bo‘lmaydi.')
    if kind=='delivery' and pack and core.client_stock_total(db,int(ev['client']),pack)<qty:
        raise ValueError(f'Mijozda {product_name(pack)} yetarli emas (sotilgan yoki qaytarilgan) — avval o‘sha yozuvlarni bekor qiling.')
    corrections._mark(db,'agent_event',ref,actor,reason,ts)
    db.execute("UPDATE events SET kind='cancelled_'||kind WHERE id=?",(ref,))


def _c_handover(db,actor,ref,reason,ts):
    import cashbook
    cashbook._lock(db)
    h=db.execute('SELECT * FROM handovers WHERE id=?',(ref,)).fetchone()
    if not h or h['status']!='accepted':raise ValueError('Topshiriq topilmadi yoki allaqachon bekor qilingan.')
    core.lock_agent(db,int(h['agent']))
    som=int(h['amount'] or 0)//100
    cur,amount=('UZS',som) if som else ('USD',int(h['amount_usd'] or 0))
    if amount>cashbook._available(db,'cash',cur):
        raise ValueError(f'Kassada (naqd) yetarli {cur} yo‘q — bu pul ishlatilgan.')
    corrections._mark(db,'handover',ref,actor,reason,ts)
    db.execute("UPDATE handovers SET status='cancelled' WHERE id=?",(ref,))   # pul qayta agent qo'lida hisoblanadi


def _c_sale(db,actor,ref,reason,ts):corrections.cancel_sale(db,actor,ref,reason,now=ts)
def _c_purchase(db,actor,ref,reason,ts):corrections.cancel_purchase(db,actor,ref,reason,now=ts)


def _c_cash_move(db,actor,ref,reason,ts):
    import cashbook
    cashbook.cancel(db,actor,ref,reason,now=ts)


def _c_expense(db,actor,ref,reason,ts):
    import cashbook
    cashbook._lock(db)
    if _linked_expenses(db).get(ref):raise ValueError('Bu xarajat ta’minot to‘lovi yoki oylik — o‘sha yozuvni bekor qiling.')
    _archive(db,'cashier_expenses',ref,actor,reason,ts)
    corrections._mark(db,'expense',ref,actor,reason,ts)


def _c_conversion(db,actor,ref,reason,ts):
    import cashbook
    cashbook._lock(db)
    c=db.execute('SELECT * FROM cashier_conversions WHERE id=?',(ref,)).fetchone()
    if not c:raise ValueError('Konvertatsiya topilmadi yoki allaqachon bekor qilingan.')
    to_cur='USD' if c['from_currency']=='UZS' else 'UZS'
    if int(c['amount_to'])>cashbook._available(db,c['pay_from'],to_cur):
        raise ValueError(f'Kassada yetarli {to_cur} yo‘q — almashtirilgan pul ishlatilgan.')
    _archive(db,'cashier_conversions',ref,actor,reason,ts)
    corrections._mark(db,'conversion',ref,actor,reason,ts)


def _c_agent_fund(db,actor,ref,reason,ts):
    import cashbook
    cashbook._lock(db)
    f=db.execute("SELECT * FROM agent_funds WHERE id=? AND kind='topup'",(ref,)).fetchone()
    if not f:raise ValueError('Yozuv topilmadi yoki allaqachon bekor qilingan.')
    core.lock_agent(db,int(f['agent']))
    bal=db.execute("""SELECT COALESCE(SUM(CASE WHEN kind='topup' THEN amount_usd ELSE -amount_usd END),0) FROM agent_funds WHERE agent=?""",
                   (int(f['agent']),)).fetchone()[0]
    if int(bal or 0)<int(f['amount_usd']):raise ValueError('Agent bu puldan xarajat qilib bo‘lgan — avval xarajatlarini tuzating.')
    _archive(db,'agent_funds',ref,actor,reason,ts)
    corrections._mark(db,'agent_fund',ref,actor,reason,ts)


def _c_wh_move(db,actor,ref,reason,ts):
    import warehouse as wh
    m=db.execute('SELECT * FROM warehouse_moves WHERE id=?',(ref,)).fetchone()
    if not m or m['kind'] not in WH_KINDS:raise ValueError('Ombor yozuvi topilmadi yoki allaqachon bekor qilingan.')
    if str(m['note'] or '').startswith('Xarid #'):raise ValueError('Bu xarid kirimi — Ta’minot xaridini bekor qiling.')
    k=m['kind'];pack=int(m['pack']);qty=int(m['qty'])
    if m['agent']:core.lock_agent(db,int(m['agent']))
    wh._lock_warehouse(db)
    if k in ('in','agent_return') and wh.stock(db,pack)<qty:
        raise ValueError(f'Omborda {product_name(pack)} {wh.stock(db,pack)} dona qolgan — bekor qilib bo‘lmaydi.')
    if k=='issue' and core.agent_stock(db,int(m['agent']),pack)<qty:
        raise ValueError(f"Agentda {product_name(pack)} {core.agent_stock(db,int(m['agent']),pack)} dona qolgan — tovar mijozga berilgan.")
    corrections._mark(db,'wh_move',ref,actor,reason,ts)
    db.execute("UPDATE warehouse_moves SET kind='cancelled_'||kind WHERE id=?",(ref,))
    # Agentdagi juft yozuv ('load' / 'unload') ham bekor bo'ladi.
    if k=='issue':
        db.execute("""UPDATE events SET kind='cancelled_load' WHERE agent=? AND kind='load' AND pack=? AND qty=?
            AND (note=? OR note LIKE ?)""",(int(m['agent']),pack,qty,f'Омбор #{ref}',f'Омбор #{ref} |%'))
    elif k=='agent_return':
        db.execute("""UPDATE events SET kind='cancelled_unload' WHERE agent=? AND kind='unload' AND pack=? AND qty=? AND note=?""",
                   (int(m['agent']),pack,qty,f'Омборга қайтди #{ref}'))


def _c_supplier_payment(db,actor,ref,reason,ts):
    import cashbook,purchases
    purchases._lock(db);cashbook._lock(db)
    p=_archive(db,'supplier_payments',ref,actor,reason,ts)
    if p.get('expense'):_archive(db,'cashier_expenses',int(p['expense']),actor,f'Ta’minot to‘lovi #{ref} bekor · {reason}'[:300],ts)
    corrections._mark(db,'supplier_payment',ref,actor,reason,ts)


def _c_hr_pay(db,actor,ref,reason,ts):
    import cashbook
    cashbook._lock(db)
    p=_archive(db,'hr_w_pay',ref,actor,reason,ts)
    if p.get('expense'):_archive(db,'cashier_expenses',int(p['expense']),actor,f'Oylik to‘lovi #{ref} bekor · {reason}'[:300],ts)
    corrections._mark(db,'hr_pay',ref,actor,reason,ts)


_CANCEL={'payment':_c_payment,'delivery':_c_agent_event,'sold':_c_agent_event,'return':_c_agent_event,'handover':_c_handover,
         'sale':_c_sale,'purchase':_c_purchase,'cash_move':_c_cash_move,'expense':_c_expense,'conversion':_c_conversion,
         'agent_fund':_c_agent_fund,'wh_move':_c_wh_move,'supplier_payment':_c_supplier_payment,'hr_pay':_c_hr_pay}


# ======================= TAHRIRLASH =======================
# form(): tahrir oynasi maydonlari (joriy qiymatlar bilan). edit(): yangi qiymatlar bilan almashtirish.

def _f(name,label,value,kind='text',**kw):
    return {'name':name,'label':label,'value':value,'type':kind,**kw}


def _money_field(name,label,cur,value):
    return _f(name,f"{label} ({'so‘m' if cur=='UZS' else 'USD'})",value,'number',step='1' if cur=='UZS' else '0.01')


def _one(db,sql,args):
    r=db.execute(sql,args).fetchone()
    if not r:raise ValueError('Yozuv topilmadi yoki allaqachon bekor qilingan.')
    return r


def form(db,actor,kind,ref):
    corrections.require_admin(db,actor)
    ref=int(ref)
    if kind=='payment':
        e=_one(db,'SELECT * FROM events WHERE id=? AND kind=?',(ref,'payment'))
        uzs=int(e['paid_uzs'] or 0)
        return [_money_field('amount','Summa','UZS' if uzs else 'USD',uzs or _usd(e['amount_usd'])),_f('note','Izoh',e['note'] or '')]
    if kind in ('delivery','sold','return'):
        e=_one(db,'SELECT * FROM events WHERE id=? AND kind=?',(ref,kind))
        return [_f('qty',f"Miqdor — {product_name(int(e['pack']))} (dona)",int(e['qty']),'number',step='1'),_f('note','Izoh',e['note'] or '')]
    if kind=='handover':
        h=_one(db,"SELECT * FROM handovers WHERE id=? AND status='accepted'",(ref,))
        som=int(h['amount'] or 0)//100
        return [_money_field('amount','Topshirilgan summa','UZS' if som else 'USD',som or _usd(h['amount_usd']))]
    if kind=='sale':
        s=_one(db,'SELECT * FROM shop_sales WHERE id=?',(ref,))
        if corrections.is_voided(db,'sale',ref):raise ValueError('Sotuv allaqachon bekor qilingan.')
        out=[]
        for i,l in enumerate(db.execute('SELECT * FROM shop_sale_lines WHERE sale=? ORDER BY id',(ref,)).fetchall()):
            nm=product_name(int(l['pack']))
            out+=[_f(f'qty_{i}',f'{nm} — miqdor (0 = olib tashlash)',int(l['qty']),'number',step='1'),
                  _f(f'price_{i}',f'{nm} — narx (USD)',_usd(l['price']),'number',step='0.01')]
        out.append(_f('discount','Chegirma (USD)',_usd(s['discount']),'number',step='0.01'))
        if (s['pay_method'] or '')=='cash_uzs':out.append(_money_field('paid','To‘langan','UZS',int(s['paid_uzs'] or 0)))
        else:out.append(_money_field('paid','To‘langan','USD',_usd(s['paid'])))
        out.append(_f('note','Izoh',s['note'] or ''))
        return out
    if kind=='purchase':
        import purchases
        p=_one(db,'SELECT * FROM purchases WHERE id=?',(ref,))
        if corrections.is_voided(db,'purchase',ref):raise ValueError('Xarid allaqachon bekor qilingan.')
        out=[]
        for i,l in enumerate(db.execute('SELECT * FROM purchase_lines WHERE purchase=? ORDER BY id',(ref,)).fetchall()):
            if l['pack'] is not None:nm=product_name(int(l['pack']));q=int(l['qty']);unit='dona';step='1'
            else:
                m=purchases._material(db,int(l['material']));nm=m['name'];q=int(l['qty'])/1000;step='0.001'
                unit=m['unit'] if 'unit' in m.keys() else 'birlik'
            out+=[_f(f'qty_{i}',f'{nm} — miqdor ({unit}, 0 = olib tashlash)',q,'number',step=step),
                  _f(f'price_{i}',f'{nm} — narx (USD)',_usd(l['price_usd']),'number',step='0.01')]
        out.append(_f('note','Izoh',p['note'] or ''))
        return out
    if kind=='cash_move':
        m=_one(db,"SELECT * FROM cash_moves WHERE id=? AND status='active'",(ref,))
        return [_money_field('amount','Summa',m['currency'],_usd(m['amount']) if m['currency']=='USD' else int(m['amount'])),_f('note','Izoh',m['note'] or '')]
    if kind=='expense':
        e=_one(db,'SELECT * FROM cashier_expenses WHERE id=?',(ref,))
        uzs=(e['currency'] or 'USD')=='UZS'
        return [_money_field('amount','Summa','UZS' if uzs else 'USD',int(e['amount_uzs']) if uzs else _usd(e['amount_usd'])),
                _f('recipient','Kimga / nima uchun',e['recipient'] or ''),_f('note','Izoh',e['note'] or '')]
    if kind=='conversion':
        c=_one(db,'SELECT * FROM cashier_conversions WHERE id=?',(ref,))
        fc=c['from_currency'];tc='USD' if fc=='UZS' else 'UZS'
        return [_money_field('amount','Berilgan',fc,_usd(c['amount_from']) if fc=='USD' else int(c['amount_from'])),
                _money_field('amount_to','Olingan',tc,_usd(c['amount_to']) if tc=='USD' else int(c['amount_to'])),_f('note','Izoh',c['note'] or '')]
    if kind=='agent_fund':
        f=_one(db,"SELECT * FROM agent_funds WHERE id=? AND kind='topup'",(ref,))
        uzs=int(f['amount_uzs'] or 0)
        return [_money_field('amount','Summa','UZS' if uzs else 'USD',uzs or _usd(f['amount_usd'])),_f('note','Izoh',f['note'] or '')]
    if kind=='wh_move':
        m=_one(db,'SELECT * FROM warehouse_moves WHERE id=?',(ref,))
        if m['kind'] not in WH_KINDS:raise ValueError('Yozuv allaqachon bekor qilingan.')
        return [_f('qty',f"Miqdor — {product_name(int(m['pack']))} (dona)",int(m['qty']),'number',step='1'),_f('note','Izoh',m['note'] or '')]
    if kind=='supplier_payment':
        p=_one(db,'SELECT * FROM supplier_payments WHERE id=?',(ref,))
        return [_money_field('amount','Summa','USD',_usd(p['amount_usd'])),_f('note','Izoh',p['note'] or '')]
    if kind=='hr_pay':
        p=_one(db,'SELECT * FROM hr_w_pay WHERE id=?',(ref,))
        cur=p['paid_currency'] or 'USD'
        return [_money_field('amount','Summa',cur,int(p['paid_amount']) if cur=='UZS' else _usd(p['paid_amount'] or p['amount'])),
                _f('note','Izoh',p['note'] or '')]
    raise ValueError('Bu turdagi yozuv noma’lum.')


def _cents(v,label='Summa',zero=False):
    try:d=Decimal(str(v if v is not None else '').replace(' ','').replace(',','.'))*100
    except InvalidOperation:raise ValueError(f'{label} noto‘g‘ri.')
    if not d.is_finite():raise ValueError(f'{label} noto‘g‘ri.')
    n=int(d.to_integral_value())
    if n<0 or (n==0 and not zero):raise ValueError(f'{label} noldan katta bo‘lsin.')
    return n


def _whole(v,label='Summa',zero=False):
    try:n=int(Decimal(str(v if v is not None else '').replace(' ','').replace(',','.')))
    except InvalidOperation:raise ValueError(f'{label} noto‘g‘ri.')
    if n<0 or (n==0 and not zero):raise ValueError(f'{label} noldan katta bo‘lsin.')
    return n


def _amt(v,cur):return _whole(v) if cur=='UZS' else _cents(v)
def _txt(v,default=''):return default if v is None else str(v).strip()[:300]
def _money_text(n,cur):return str(n) if cur=='UZS' else f'{n/100:.2f}'


def _copy_row(db,tbl,row,**changes):
    data={k:row[k] for k in row.keys() if k!='id'};data.update(changes)
    cols=','.join(data);ph=','.join('?'*len(data))
    return int(db.execute(f'INSERT INTO {tbl}({cols}) VALUES({ph}) RETURNING id',tuple(data.values())).fetchone()[0])


def edit(db,actor,kind,ref,values,reason,source):
    """Eski yozuv bekor + yangi qiymatlar bilan yangisi (bitta tranzaksiya). Yangi yozuv ID qaytadi."""
    corrections.require_admin(db,actor)
    reason=corrections._reason(reason or 'Tahrirlandi')
    try:ref=int(ref)
    except (TypeError,ValueError):raise ValueError('Yozuv ID noto‘g‘ri.')
    if not isinstance(source,int) or source<=0:raise ValueError('Operatsiya ID noto‘g‘ri.')
    v=values if isinstance(values,dict) else {}
    ts=int(time.time())
    if kind=='payment':
        e=_one(db,'SELECT * FROM events WHERE id=? AND kind=?',(ref,'payment'))
        if e['agent'] is None:raise ValueError('Bu kassaga to‘g‘ridan to‘lov — Kassa kirimi yozuvini tahrirlang.')
        uzs=int(e['paid_uzs'] or 0);card=(e['pay_method'] or '')=='card'
        value=_amt(v.get('amount'),'UZS' if uzs else 'USD');note=_txt(v.get('note'),e['note'] or '')
        rate=int(e['fx_rate'] or 0)
        if uzs and rate<=0:raise ValueError('Asl to‘lov kursi topilmadi — bekor qilib, qayta kiriting.')
        _c_payment(db,actor,ref,reason,ts)
        if card:
            new=_copy_row(db,'events',e,kind='payment',amount_usd=core.som_to_usd_cents(value,rate) if uzs else value,
                          paid_uzs=value if uzs else 0,note=note,source=source)
        else:
            if uzs:core.record_client_payment(db,actor,int(e['agent']),int(e['client']),'UZS',value,'cash',note=note,source=source,
                                              ts=int(e['ts']),usd_cents=core.som_to_usd_cents(value,rate))
            else:core.record_client_payment(db,actor,int(e['agent']),int(e['client']),'USD',value,'cash',note=note,source=source,ts=int(e['ts']))
            new=int(db.execute('SELECT id FROM events WHERE source=?',(source,)).fetchone()[0])
        corrections.link_replacement(db,'payment',ref,new);return new
    if kind in ('delivery','sold','return'):
        e=_one(db,'SELECT * FROM events WHERE id=? AND kind=?',(ref,kind))
        qty=_whole(v.get('qty'),'Miqdor')
        _c_agent_event(db,actor,ref,reason,ts)
        core.record(db,actor,int(e['agent']),int(e['client']),kind,int(e['pack']),qty,0,_txt(v.get('note'),e['note'] or ''),source,
                    currency='USD',ts=int(e['ts']))
        new=int(db.execute('SELECT id FROM events WHERE source=?',(source,)).fetchone()[0])
        corrections.link_replacement(db,'agent_event',ref,new);return new
    if kind=='handover':
        h=_one(db,"SELECT * FROM handovers WHERE id=? AND status='accepted'",(ref,))
        som=int(h['amount'] or 0)//100;value=_amt(v.get('amount'),'UZS' if som else 'USD')
        _c_handover(db,actor,ref,reason,ts)
        agent=int(h['agent'])
        have=core.cash_som(db,agent) if som else core.cash_usd(db,agent)
        if value>have:raise ValueError(f"Agent qo‘lida {(have if som else have/100):,} {'so‘m' if som else 'USD'} bor — undan ko‘p topshirib bo‘lmaydi.")
        new=_copy_row(db,'handovers',h,amount=value*100 if som else 0,amount_usd=0 if som else value,source=source)
        corrections.link_replacement(db,'handover',ref,new);return new
    if kind=='sale':
        import shop
        s=_one(db,'SELECT * FROM shop_sales WHERE id=?',(ref,))
        if corrections.is_voided(db,'sale',ref):raise ValueError('Sotuv allaqachon bekor qilingan.')
        items=[]
        for i,l in enumerate(db.execute('SELECT * FROM shop_sale_lines WHERE sale=? ORDER BY id',(ref,)).fetchall()):
            q=_whole(v.get(f'qty_{i}',l['qty']),'Miqdor',zero=True)
            if q:items.append({'pack':int(l['pack']),'qty':q,'price':_money_text(_cents(v.get(f'price_{i}',_usd(l['price'])),'Narx'),'USD')})
        if not items:raise ValueError('Kamida bitta mahsulot qolsin. Butunlay o‘chirish uchun «Bekor qilish»ni bosing.')
        method=s['pay_method'] or ''
        walkin=s['client']==shop.walkin_client(db,int(s['seller'])) if hasattr(shop,'walkin_client') else False
        payload={'requestId':f'operations-{source}','replaceSaleId':ref,'reason':reason,'sellerId':int(s['seller']),
                 'clientId':0 if walkin else int(s['client']),'items':items,'note':_txt(v.get('note'),s['note'] or '')}
        disc=_cents(v.get('discount',_usd(s['discount'])),'Chegirma',zero=True)
        if disc:payload['discount']=_money_text(disc,'USD')
        if method=='cash_uzs':
            paid=_whole(v.get('paid',s['paid_uzs']),'To‘langan',zero=True)
            if paid:payload.update(method=method,paidUzs=str(paid),rate=int(s['fx_rate'] or 0))
        else:
            paid=_cents(v.get('paid',_usd(s['paid'])),'To‘langan',zero=True)
            if paid:payload.update(method=method or 'cash_usd',paid=_money_text(paid,'USD'))
        shop.sell(db,actor,payload)
        return int(db.execute("SELECT replaced_by FROM voids WHERE kind='sale' AND ref=?",(ref,)).fetchone()[0])
    if kind=='purchase':
        p=_one(db,'SELECT * FROM purchases WHERE id=?',(ref,))
        lines=[]
        for i,l in enumerate(db.execute('SELECT * FROM purchase_lines WHERE purchase=? ORDER BY id',(ref,)).fetchall()):
            price=_cents(v.get(f'price_{i}',_usd(l['price_usd'])),'Narx',zero=True)
            if l['pack'] is not None:
                q=_whole(v.get(f'qty_{i}',l['qty']),'Miqdor',zero=True)
                if q:lines.append({'pack':int(l['pack']),'qty':q,'price':price})
            else:
                try:q=int((Decimal(str(v.get(f'qty_{i}',int(l['qty'])/1000)).replace(',','.'))*1000).to_integral_value())
                except InvalidOperation:raise ValueError('Miqdor noto‘g‘ri.')
                if q<0:raise ValueError('Miqdor noto‘g‘ri.')
                if q:lines.append({'material':int(l['material']),'qty':q,'price':price})
        if not lines:raise ValueError('Kamida bitta qator qolsin. Butunlay o‘chirish uchun «Bekor qilish»ni bosing.')
        return corrections.edit_purchase(db,actor,ref,int(p['supplier']),lines,_txt(v.get('note'),p['note'] or ''),reason,source=source)
    if kind=='cash_move':
        import cashbook
        m=_one(db,"SELECT * FROM cash_moves WHERE id=? AND status='active'",(ref,))
        value=_money_text(_amt(v.get('amount'),m['currency']),m['currency'])
        note=_txt(v.get('note'),m['note'] or '')
        cashbook.cancel(db,actor,ref,reason)
        if m['kind']=='income':
            return cashbook.add_income(db,actor,m['to_pocket'],m['currency'],value,m['category'],m['counterparty'],note,source,
                                       now=int(m['ts']),client=m['client'] if m['client'] else None)
        return cashbook.add_transfer(db,actor,m['from_pocket'],m['to_pocket'],m['currency'],value,note,source,now=int(m['ts']))
    if kind=='expense':
        e=_one(db,'SELECT * FROM cashier_expenses WHERE id=?',(ref,))
        cur=e['currency'] or 'USD';value=_amt(v.get('amount'),cur)
        _c_expense(db,actor,ref,reason,ts)
        recipient=_txt(v.get('recipient'),e['recipient'] or '');note=_txt(v.get('note'),e['note'] or '')
        if cur=='UZS':
            new=core.add_cashier_expense_uzs(db,actor,value,e['category'],recipient,note,source,pay_from=e['pay_from'] or 'cash')[0]
        else:
            new=core.add_cashier_expense(db,actor,value,e['category'],recipient,note,source,pay_from=e['pay_from'] or 'cash',system_category=True)
        db.execute('UPDATE cashier_expenses SET cashier=?,ts=? WHERE id=?',(int(e['cashier']),int(e['ts']),new))
        corrections.link_replacement(db,'expense',ref,new);return new
    if kind=='conversion':
        import cashbook
        c=_one(db,'SELECT * FROM cashier_conversions WHERE id=?',(ref,))
        fc=c['from_currency'];tc='USD' if fc=='UZS' else 'UZS'
        a=_amt(v.get('amount'),fc);b=_amt(v.get('amount_to'),tc)
        usd,som=(a,b) if fc=='USD' else (b,a)
        rate=int(Decimal(som*100)/usd) if usd else 0
        if rate<100:raise ValueError('Kurs noto‘g‘ri chiqdi — summalarni tekshiring.')
        _c_conversion(db,actor,ref,reason,ts)
        if a>cashbook._available(db,c['pay_from'],fc):raise ValueError(f'Kassada yetarli {fc} yo‘q.')
        new=_copy_row(db,'cashier_conversions',c,amount_from=a,amount_to=b,rate_uzs_per_usd=rate,note=_txt(v.get('note'),c['note'] or ''),source=source)
        corrections.link_replacement(db,'conversion',ref,new);return new
    if kind=='agent_fund':
        import cashbook
        f=_one(db,"SELECT * FROM agent_funds WHERE id=? AND kind='topup'",(ref,))
        uzs=int(f['amount_uzs'] or 0);value=_amt(v.get('amount'),'UZS' if uzs else 'USD')
        rate=int(f['rate_uzs_per_usd'] or 0)
        if uzs and rate<=0:raise ValueError('Asl kurs topilmadi — bekor qilib, qayta kiriting.')
        _c_agent_fund(db,actor,ref,reason,ts)
        if value>cashbook._available(db,'cash','UZS' if uzs else 'USD'):raise ValueError('Kassada yetarli pul yo‘q.')
        new=_copy_row(db,'agent_funds',f,amount_usd=core.som_to_usd_cents(value,rate) if uzs else value,amount_uzs=value if uzs else 0,
                      note=_txt(v.get('note'),f['note'] or ''),source=source)
        corrections.link_replacement(db,'agent_fund',ref,new);return new
    if kind=='wh_move':
        import warehouse as wh,purchases
        m=_one(db,'SELECT * FROM warehouse_moves WHERE id=?',(ref,))
        if m['kind'] not in WH_KINDS:raise ValueError('Yozuv allaqachon bekor qilingan.')
        qty=_whole(v.get('qty'),'Miqdor');note=_txt(v.get('note'),m['note'] or '');k=m['kind'];pack=int(m['pack'])
        _c_wh_move(db,actor,ref,reason,ts)
        with purchases._AsOperator(db,actor):
            if k=='in':new=wh.receive(db,actor,pack,qty,note=note,source=source)
            elif k=='writeoff':new=wh.write_off(db,actor,pack,qty,note or 'Tuzatildi',source=source)
            elif k=='issue':new=wh.issue(db,actor,int(m['agent']),pack,qty,note=note,source=source)
            else:new=wh.take_back(db,actor,int(m['agent']),pack,qty,note=note,source=source)
        corrections.link_replacement(db,'wh_move',ref,new);return int(new)
    if kind=='supplier_payment':
        import purchases
        p=_one(db,'SELECT * FROM supplier_payments WHERE id=?',(ref,))
        value=_cents(v.get('amount'))
        _c_supplier_payment(db,actor,ref,reason,ts)
        new=purchases.pay_supplier(db,actor,int(p['supplier']),value,_txt(v.get('note'),p['note'] or ''),source=source,pay_from=p['pay_from'] or 'cash')
        corrections.link_replacement(db,'supplier_payment',ref,new);return new
    if kind=='hr_pay':
        import hr
        p=_one(db,'SELECT * FROM hr_w_pay WHERE id=?',(ref,))
        cur=p['paid_currency'] or None
        value=_money_text(_amt(v.get('amount'),cur or 'USD'),cur or 'USD')
        pay_from='cash'
        if p['expense']:
            e=db.execute('SELECT pay_from FROM cashier_expenses WHERE id=?',(int(p['expense']),)).fetchone()
            if e:pay_from=e['pay_from'] or 'cash'
        _c_hr_pay(db,actor,ref,reason,ts)
        new=hr.add_pay(db,actor,int(p['worker_id']),p['kind'],value,month=p['month'],note=_txt(v.get('note'),p['note'] or ''),
                       source=source,pay_from=pay_from,pay_currency=cur)
        corrections.link_replacement(db,'hr_pay',ref,new);return new
    raise ValueError('Bu turdagi yozuv noma’lum.')
