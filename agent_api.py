"""Secure live API for ASMAN Agent Mini App.

The browser never receives a bot token. Every request is authenticated by
Telegram initData and the current database role. Write actions reuse core
inventory/cash rules and customer_status visit rules.
"""
import hashlib
import os
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import core
import customer_status as cs
import manager_api

TZ=ZoneInfo("Asia/Tashkent")
MAX_CLIENTS=5000
MAX_WRITE_ITEMS=12
OFFLINE_MAX_AGE=7*86400

STATUS_LABELS={
    "active":"Товар олган",
    "interested":"Таклиф берилган",
    "waiting":"Кутишда",
    "declined":"Ҳозирча олмайди",
}
FEATURE_ACTION={
    "client":"client",
    "add_client":"client",
    "client_detail":"clients",
    "client_edit":"clients",
    "visit":"visit",
    "delivery":"delivery",
    "payment":"payment",
    "return":"return",
    "handover":"handover",
    "sold":"sold",
    "order":"order",
}


def _agent_session_seconds():
    """Agents keep the Mini App open for a whole shift; Telegram initData is only issued on open."""
    try:
        hours=float(os.getenv('AGENT_SESSION_HOURS','12'))
    except ValueError:
        hours=12.0
    return int(min(24.0,max(1.0,hours))*3600)


AGENT_MAX_AUTH_AGE=_agent_session_seconds()


def verify_init_data(raw,token,now=None):
    return manager_api.verify_init_data(raw,token,now,max_age=AGENT_MAX_AUTH_AGE)


def _midnight(now):
    return int(datetime.fromtimestamp(now,TZ).replace(
        hour=0,minute=0,second=0,microsecond=0).timestamp())


def _usd(cents):
    return round(int(cents or 0)/100,2)


def _coord(lat,lon):
    try:
        lat=float(lat);lon=float(lon)
    except (TypeError,ValueError):
        return None,None
    if not (-90<=lat<=90 and -180<=lon<=180):
        return None,None
    return lat,lon


def _require_agent(db,agent):
    row=db.execute("SELECT id,name FROM users WHERE id=? AND role='agent'",(agent,)).fetchone()
    if not row:raise ValueError("Agent akkaunti faol emas.")
    return row


def _feature(db,agent,name):
    if not core.feature_enabled(db,agent,name):
        raise ValueError("Bu funksiya rahbar tomonidan o‘chirilgan.")


def _client(db,cid):
    try:cid=int(cid)
    except (TypeError,ValueError):raise ValueError("Mijoz noto‘g‘ri.")
    row=db.execute("SELECT * FROM clients WHERE id=?",(cid,)).fetchone()
    if not row:raise ValueError("Mijoz topilmadi.")
    return row


def _live_ready(db,agent,max_age=300,now=None):
    at_ts=int(time.time() if now is None else now)
    shift=db.execute('''SELECT * FROM shifts
        WHERE agent=? AND start<=? AND ("end" IS NULL OR "end">=?)
        ORDER BY start DESC,id DESC LIMIT 1''',(agent,at_ts,at_ts)).fetchone()
    if not shift:return False,'Avval «Ishni boshlash»ni bosing.'
    if shift['live_id'] is None:
        return False,'Ish boshlangan, lekin Telegram jonli lokatsiyasi hali ulanmagan.'
    p=db.execute('''SELECT ts FROM points WHERE shift=? AND ts<=?
        ORDER BY ts DESC,id DESC LIMIT 1''',(shift['id'],at_ts)).fetchone()
    if not p:return False,'Jonli lokatsiya ulangan, lekin GPS koordinatasi hali kelmagan.'
    age=max(0,at_ts-int(p[0]))
    if age>max_age:
        return False,f'Jonli lokatsiya {age//60} daqiqadan beri yangilanmagan. Telegram live-location, GPS va internetni tekshiring.'
    return True,''


def visit_radius_m():
    try:value=int(os.getenv("VISIT_RADIUS_M","200"))
    except ValueError:value=200
    return max(50,min(value,2000))


VISIT_MAX_HOURS=6


def _agent_points(db,agent,lo,hi):
    return db.execute("""SELECT p.ts,p.lat,p.lon,p.accuracy FROM points p JOIN shifts s ON s.id=p.shift
        WHERE s.agent=? AND p.ts>=? AND p.ts<=? ORDER BY p.ts,p.id""",(agent,lo,hi)).fetchall()


def _visit_gps(db,agent,c,start_ts,end_ts):
    """Closest live-location point to the shop while the visit lasted (server-side, not the phone's claim)."""
    if c['lat'] is None or c['lon'] is None:return None,None,None
    points=_agent_points(db,agent,int(start_ts)-300,int(end_ts)+60)
    if not points:
        raise ValueError("Tashrif vaqtida GPS nuqtasi topilmadi. «Ishni boshlash»ni bosing va Telegram jonli lokatsiyasini yoqing.")
    shop={'lat':float(c['lat']),'lon':float(c['lon'])}
    best=min(points,key=lambda p:core.distance(shop,{'lat':float(p['lat']),'lon':float(p['lon'])}))
    d=int(round(core.distance(shop,{'lat':float(best['lat']),'lon':float(best['lon'])})))
    radius=visit_radius_m()
    allowed=radius+min(int(best['accuracy'] or 0),100)
    if d>allowed:
        raise ValueError(f"Siz do‘kondan {d} m uzoqdasiz (ruxsat: {radius} m). Tashrif faqat do‘kon yonida qayd etiladi.")
    return float(best['lat']),float(best['lon']),d


def visit_check(db,agent,cid,now=None):
    """Read-only: is the agent at the shop right now? Used when a visit starts."""
    _require_agent(db,agent);_feature(db,agent,'visit')
    c=_client(db,cid);now=int(time.time() if now is None else now);radius=visit_radius_m()
    ok,msg=_live_ready(db,agent,now=now)
    if not ok:return {"ok":False,"radiusM":radius,"distanceM":None,"message":msg}
    if c['lat'] is None or c['lon'] is None:
        return {"ok":True,"radiusM":radius,"distanceM":None,"message":"Mijoz lokatsiyasi kiritilmagan — masofa tekshirilmaydi."}
    p=_agent_points(db,agent,now-300,now+60)[-1]
    d=int(round(core.distance({'lat':float(c['lat']),'lon':float(c['lon'])},{'lat':float(p['lat']),'lon':float(p['lon'])})))
    near=d<=radius+min(int(p['accuracy'] or 0),100)
    return {"ok":near,"radiusM":radius,"distanceM":d,"gpsAgeSec":max(0,now-int(p['ts'])),
            "message":(f"Siz do‘kon yonidasiz ({d} m)." if near else f"Siz do‘kondan {d} m uzoqdasiz. Do‘konga yetib kelgach boshlang.")}


def _visit_stock_items(db,cid,raw):
    if raw in (None,""):return []
    if not isinstance(raw,list) or len(raw)>50:raise ValueError("Qoldiq ro‘yxati noto‘g‘ri.")
    valid=set(core.product_ids());seen=set();items=[]
    for it in raw:
        if not isinstance(it,dict):raise ValueError("Qoldiq ro‘yxati noto‘g‘ri.")
        if it.get("qty") in (None,""):continue
        try:pack=int(it.get("pack"));qty=int(str(it.get("qty")).strip())
        except (TypeError,ValueError):raise ValueError("Qoldiq soni butun son bo‘lsin.")
        if pack not in valid:raise ValueError("Mahsulot topilmadi.")
        if pack in seen:raise ValueError("Bir mahsulot ikki marta sanalgan.")
        if not 0<=qty<=100000:raise ValueError("Qoldiq soni 0 dan 100000 gacha bo‘lsin.")
        seen.add(pack);items.append((pack,qty,int(core.client_stock_total(db,cid,pack))))
    return items


def _operation_ts(payload,server_now):
    raw=payload.get("offlineTs")
    if raw in (None,""):
        return int(server_now)
    try:ts=int(raw)
    except (TypeError,ValueError):
        raise ValueError("Offline vaqt noto‘g‘ri.")
    if ts>int(server_now)+60:
        raise ValueError("Offline vaqt kelajakda bo‘lishi mumkin emas.")
    if ts<int(server_now)-OFFLINE_MAX_AGE:
        raise ValueError("Offline amal 7 kundan eski. Rahbar orqali tekshiring.")
    return ts


def _parse_phones(value):
    pattern=r'(?<!\d)(?:\+?998[\s().-]*)?\d(?:[\s().-]*\d){8}(?!\d)'
    found=[]
    for raw in re.findall(pattern,str(value or '')):
        digits=re.sub(r'\D','',raw)
        if len(digits)==9:digits='998'+digits
        if re.fullmatch(r'998\d{9}',digits):
            phone='+'+digits
            if phone not in found:found.append(phone)
    if not found:raise ValueError('Telefonni +998XXXXXXXXX ko‘rinishida kiriting.')
    if len(found)>3:raise ValueError('Ko‘pi bilan 3 ta telefon raqami kiriting.')
    return found


def _request_key(agent,request_id):
    request_id=str(request_id or '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,96}',request_id):
        raise ValueError("So‘rov identifikatori noto‘g‘ri.")
    return f'agent_api:{int(agent)}:{request_id}'


def _reserve(db,agent,request_id,action):
    key=_request_key(agent,request_id)
    row=db.execute("""INSERT INTO meta(key,value) VALUES(?,?)
        ON CONFLICT(key) DO NOTHING RETURNING key""",(key,action)).fetchone()
    return bool(row)


def _source(agent,request_id,index=0):
    raw=f'{int(agent)}:{request_id}:{index}'.encode()
    value=int.from_bytes(hashlib.sha256(raw).digest()[:7],'big')
    return -(value*16+int(index)+1)


def _visit_age(last,followup,now):
    if followup:
        try:
            planned=datetime.fromisoformat(str(followup)).date()
            if planned>datetime.fromtimestamp(now,TZ).date():
                return "scheduled",None
        except ValueError:pass
    if not last:return "unknown",None
    days=max(0,(now-int(last))//86400)
    return ("red" if days>=5 else "yellow" if days>=3 else "fresh"),int(days)


def _client_snapshot(db,now,client_id=None):
    if client_id is None:
        rows=db.execute("""SELECT c.*,u.name AS agent_name FROM clients c
            LEFT JOIN users u ON u.id=c.agent ORDER BY c.id DESC LIMIT ?""",(MAX_CLIENTS,)).fetchall()
        latest=db.execute("""SELECT v.client,v.status,v.followup,v.ts,v.note,v.actor,u.name AS actor_name
            FROM client_visits v LEFT JOIN users u ON u.id=v.actor
            WHERE v.id=(SELECT MAX(v2.id) FROM client_visits v2 WHERE v2.client=v.client)""").fetchall()
        contacts_rows=db.execute("""SELECT client,MAX(ts) AS ts FROM events
            WHERE client IS NOT NULL AND kind IN ('visit','delivery','sold','return')
            GROUP BY client""").fetchall()
        balances=db.execute("""SELECT client,
            COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd
                              WHEN kind IN ('payment','return') THEN -amount_usd ELSE 0 END),0) AS debt
            FROM events WHERE client IS NOT NULL GROUP BY client""").fetchall()
        stock_rows=db.execute("""SELECT client,pack,
            COALESCE(SUM(CASE WHEN kind='delivery' THEN qty
                              WHEN kind IN ('sold','return') THEN -qty ELSE 0 END),0) AS qty
            FROM events WHERE client IS NOT NULL AND pack>0 GROUP BY client,pack""").fetchall()
    else:
        cid=int(client_id)
        rows=db.execute("""SELECT c.*,u.name AS agent_name FROM clients c
            LEFT JOIN users u ON u.id=c.agent WHERE c.id=? LIMIT 1""",(cid,)).fetchall()
        latest=db.execute("""SELECT v.client,v.status,v.followup,v.ts,v.note,v.actor,u.name AS actor_name
            FROM client_visits v LEFT JOIN users u ON u.id=v.actor
            WHERE v.client=? ORDER BY v.id DESC LIMIT 1""",(cid,)).fetchall()
        contacts_rows=db.execute("""SELECT client,MAX(ts) AS ts FROM events
            WHERE client=? AND kind IN ('visit','delivery','sold','return') GROUP BY client""",(cid,)).fetchall()
        balances=db.execute("""SELECT client,
            COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd
                              WHEN kind IN ('payment','return') THEN -amount_usd ELSE 0 END),0) AS debt
            FROM events WHERE client=? GROUP BY client""",(cid,)).fetchall()
        stock_rows=db.execute("""SELECT client,pack,
            COALESCE(SUM(CASE WHEN kind='delivery' THEN qty
                              WHEN kind IN ('sold','return') THEN -qty ELSE 0 END),0) AS qty
            FROM events WHERE client=? AND pack>0 GROUP BY client,pack""",(cid,)).fetchall()

    latest_by={int(v['client']):v for v in latest}
    contacts={int(x['client']):int(x['ts']) for x in contacts_rows if x['ts'] is not None}
    debt={int(x['client']):int(x['debt'] or 0) for x in balances}
    stocks={}
    for x in stock_rows:
        stocks.setdefault(int(x['client']),{})[int(x['pack'])]=int(x['qty'] or 0)
    result=[]
    for c in rows:
        cid=int(c['id']);v=latest_by.get(cid)
        last=max(int(c['created_ts'] or 0),contacts.get(cid,0),int(v['ts'] or 0) if v else 0)
        followup=(v['followup'] if v else None) or None
        age,days=_visit_age(last,followup,now)
        lat,lon=_coord(c['lat'],c['lon'])
        status=v['status'] if v else ('interested' if c['map_only'] else 'active')
        result.append({
            "id":cid,"name":c['shop_name'] or c['name'] or f"Mijoz #{cid}",
            "person":c['name'] or "","phone":c['phone'] or "",
            "address":c['address'] or "","region":c['region'] or "","lat":lat,"lon":lon,
            "owner":c['agent_name'] or str(c['agent']),"ownerId":int(c['agent']),
            "status":status,"statusLabel":STATUS_LABELS.get(status,status),
            "age":age,"days":days,"lastTs":last or None,"followup":followup,
            "note":(v['note'] if v else c['comment']) or "",
            "profileComment":c['comment'] or "",
            "createdTs":int(c['created_ts'] or 0) or None,
            "hasPhoto":bool(c['photo']),"photoV":core.photo_version(c['photo']),
            "debtUsd":_usd(debt.get(cid,0)),
            "blacklisted":bool(int(c['blacklisted'] or 0)),"blacklistReason":c['blacklist_reason'] or "",
            "blacklistTs":int(c['blacklist_ts'] or 0) or None,
            "stock":{str(pack):stocks.get(cid,{}).get(pack,0) for pack in core.product_ids()}
        })
    return result

def _products(db,agent):
    out=[]
    for pack in core.product_ids():
        active=pack not in core.INACTIVE_PRODUCTS
        stock=int(core.agent_stock(db,agent,pack))
        if not active and stock==0:continue
        out.append({"pack":pack,"name":core.product_name(pack),"active":active,"custom":pack not in core.BUILTIN_PRODUCTS,
                    "weightKg":core.product_weight(pack),
                    "priceUsd":_usd(core.product_price(db,pack)),
                    "agentStock":int(core.agent_stock(db,agent,pack)),
                    "blockUnits":core.block_units(pack)})
    return out


def dashboard(db,agent,now=None):
    now=int(time.time() if now is None else now)
    user=_require_agent(db,agent)
    today=_midnight(now);week=today-6*86400;month=today-29*86400
    clients=_client_snapshot(db,now) if core.feature_enabled(db,agent,'clients') else []
    shift=db.execute('SELECT * FROM shifts WHERE agent=? AND end IS NULL ORDER BY id DESC LIMIT 1',(agent,)).fetchone()
    point=None
    if shift:
        point=db.execute('SELECT lat,lon,ts,accuracy FROM points WHERE shift=? ORDER BY ts DESC,id DESC LIMIT 1',(shift['id'],)).fetchone()
    lat,lon=_coord(point['lat'],point['lon']) if point else (None,None)
    visit_today=int(db.execute("""SELECT COUNT(*) FROM client_visits
        WHERE actor=? AND ts>=? AND ts<=?""",(agent,today,now)).fetchone()[0] or 0)
    new_today=int(db.execute("""SELECT COUNT(*) FROM clients
        WHERE agent=? AND created_ts>=? AND created_ts<=?""",(agent,today,now)).fetchone()[0] or 0)
    payments_today=int(db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM events
        WHERE agent=? AND kind='payment' AND ts>=? AND ts<=?""",(agent,today,now)).fetchone()[0] or 0)
    delivery_today=db.execute("""SELECT COALESCE(SUM(qty),0),COALESCE(SUM(amount_usd),0)
        FROM events WHERE agent=? AND kind='delivery' AND ts>=? AND ts<=?""",(agent,today,now)).fetchone()
    payments=db.execute("""SELECT e.id,e.client,e.amount_usd,e.ts,e.paid_uzs,e.fx_rate,e.pay_method,c.shop_name,c.name
        FROM events e LEFT JOIN clients c ON c.id=e.client
        WHERE e.agent=? AND e.kind='payment' AND e.ts>=?
        ORDER BY e.ts DESC,e.id DESC LIMIT 300""",(agent,month)).fetchall()
    handovers=db.execute("""SELECT id,amount,amount_usd,status,ts,accepted_ts
        FROM handovers WHERE agent=? AND (ts>=? OR status='pending')
        ORDER BY ts DESC,id DESC LIMIT 200""",(agent,month)).fetchall()
    cash_ops=[]
    for e in payments:
        cash_ops.append({"id":f"p{int(e['id'])}","kind":"payment",
                         "client":e['shop_name'] or e['name'] or f"Mijoz #{e['client']}",
                         "amountUsd":_usd(e['amount_usd']),"amountUzs":int(e['paid_uzs'] or 0),
                         "rate":int(e['fx_rate'] or 0),"method":e['pay_method'] or 'cash',
                         "ts":int(e['ts']),"state":"bank" if e['pay_method']=='card' else "collected"})
    for h in handovers:
        cash_ops.append({"id":f"h{int(h['id'])}","kind":"handover","client":"Kassaga topshirish",
                         "amountUsd":_usd(h['amount_usd']),"amountUzs":int(h['amount'] or 0)//100,
                         "currency":"UZS" if int(h['amount'] or 0)>0 else "USD","ts":int(h['ts']),
                         "acceptedTs":int(h['accepted_ts'] or 0) or None,"state":h['status']})
    cash_ops.sort(key=lambda x:x['ts'],reverse=True)
    series=[]
    for k in range(6,-1,-1):
        lo=today-k*86400;hi=lo+86400
        count=int(db.execute("""SELECT COUNT(*) FROM client_visits
            WHERE actor=? AND ts>=? AND ts<?""",(agent,lo,hi)).fetchone()[0] or 0)
        series.append({"day":datetime.fromtimestamp(lo,TZ).strftime("%d.%m"),"visits":count})
    def period(lo):
        row=db.execute("""SELECT
          COALESCE(SUM(CASE WHEN kind='payment' THEN amount_usd ELSE 0 END),0),
          COALESCE(SUM(CASE WHEN kind='delivery' THEN qty ELSE 0 END),0),
          COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd ELSE 0 END),0),
          COALESCE(SUM(CASE WHEN kind='return' THEN qty ELSE 0 END),0)
          FROM events WHERE agent=? AND ts>=? AND ts<=?""",(agent,lo,now)).fetchone()
        return {
          "visits":int(db.execute("SELECT COUNT(*) FROM client_visits WHERE actor=? AND ts>=? AND ts<=?",
                                  (agent,lo,now)).fetchone()[0] or 0),
          "newClients":int(db.execute("SELECT COUNT(*) FROM clients WHERE agent=? AND created_ts>=? AND created_ts<=?",
                                     (agent,lo,now)).fetchone()[0] or 0),
          "paymentsUsd":_usd(row[0]),"deliveryQty":int(row[1] or 0),
          "deliveryUsd":_usd(row[2]),"returnQty":int(row[3] or 0)}
    features={name:bool(core.feature_enabled(db,agent,name)) for name in core.AGENT_FEATURES}
    urgent=sorted([c for c in clients if c['age'] in ('red','yellow','scheduled')],
                  key=lambda c:(0 if c['age']=='red' else 1 if c['age']=='yellow' else 2,
                                c['lastTs'] or 0))[:20]
    return {
      "generatedTs":now,"todayStart":today,"timezone":"Asia/Tashkent","readOnly":False,
      "profile":{"id":int(agent),"name":user['name'] or str(agent)},
      "shift":{"open":bool(shift),"id":int(shift['id']) if shift else None,
               "start":int(shift['start']) if shift else None,
               "liveConnected":bool(shift and shift['live_id'] is not None),
               "lastGpsTs":int(point['ts']) if point else None,
               "lat":lat,"lon":lon},
      "features":features,"products":_products(db,agent),
      "clients":clients,"urgent":urgent,
      "summary":{"visitsToday":visit_today,"newClientsToday":new_today,
                 "paymentsTodayUsd":_usd(payments_today),
                 "deliveryTodayQty":int(delivery_today[0] or 0),
                 "deliveryTodayUsd":_usd(delivery_today[1]),
                 "cashAvailableUsd":_usd(core.cash_usd(db,agent)),
                 "clientCount":len(clients)},
      "cash":cash_ops,
      "reports":{"week":period(week),"month":period(month),"series":series}
    }



def _collection_tasks(db,agent):
    rows=db.execute("""SELECT t.id,t.client,t.debt_usd,t.note,t.created_ts,
        c.name,c.shop_name,c.phone,c.address
        FROM collection_tasks t LEFT JOIN clients c ON c.id=t.client
        WHERE t.agent=? AND t.status='open'
        ORDER BY t.created_ts DESC,t.id DESC LIMIT 100""",(agent,)).fetchall()
    out=[]
    for x in rows:
        current=core.client_debt_usd(db,int(x['client']))
        if current<=0:
            db.execute("UPDATE collection_tasks SET status='done',completed_ts=? WHERE id=? AND status='open'",
                       (int(time.time()),int(x['id'])))
            continue
        out.append({"id":int(x['id']),"clientId":int(x['client']),
                    "client":x['shop_name'] or x['name'] or f"Mijoz #{x['client']}",
                    "phone":x['phone'] or "","address":x['address'] or "",
                    "assignedDebtUsd":_usd(x['debt_usd']),"currentDebtUsd":_usd(current),
                    "note":x['note'] or "","createdTs":int(x['created_ts'] or 0)})
    return out


def quick_snapshot(db,agent,now=None):
    """Fast first-paint payload for Agent Mini App.

    Keeps the same essential shape as snapshot(), but skips report analytics,
    long cash/event histories and product-period aggregation until the user
    opens those sections.
    """
    now=int(time.time() if now is None else now)
    user=_require_agent(db,agent)
    today=_midnight(now)
    clients_raw=_client_snapshot(db,now) if core.feature_enabled(db,agent,'clients') else []
    clients=[]
    for c in clients_raw:
        item=dict(c)
        item["agent"]=item.pop("owner")
        item["agentId"]=item.pop("ownerId")
        item["comment"]=item.get("note","")
        item["status"]=item.get("statusLabel") or item.get("status")
        clients.append(item)
    products=[{"pack":x["pack"],"name":x["name"],"weightKg":x["weightKg"],"priceUsd":x["priceUsd"],
               "stock":x["agentStock"],"blockUnits":x["blockUnits"],"active":x["active"],"custom":x["custom"]} for x in _products(db,agent)]

    shift=db.execute('SELECT * FROM shifts WHERE agent=? AND "end" IS NULL ORDER BY id DESC LIMIT 1',
                     (agent,)).fetchone()
    point=None
    if shift:
        point=db.execute('SELECT lat,lon,ts,accuracy FROM points WHERE shift=? ORDER BY ts DESC,id DESC LIMIT 1',
                         (shift['id'],)).fetchone()
    lat,lon=_coord(point['lat'],point['lon']) if point else (None,None)

    visit_today=int(db.execute("""SELECT COUNT(*) FROM client_visits
        WHERE actor=? AND ts>=? AND ts<=?""",(agent,today,now)).fetchone()[0] or 0)
    new_today=int(db.execute("""SELECT COUNT(*) FROM clients
        WHERE agent=? AND created_ts>=? AND created_ts<=?""",(agent,today,now)).fetchone()[0] or 0)
    payments_today=int(db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM events
        WHERE agent=? AND kind='payment' AND ts>=? AND ts<=?""",(agent,today,now)).fetchone()[0] or 0)
    delivery_today=db.execute("""SELECT COALESCE(SUM(qty),0) FROM events
        WHERE agent=? AND kind='delivery' AND ts>=? AND ts<=?""",(agent,today,now)).fetchone()

    cash_on_hand=int(core.cash_usd(db,agent))
    pending=int(db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM handovers
        WHERE agent=? AND status='pending' AND COALESCE(amount,0)=0""",(agent,)).fetchone()[0] or 0)
    cash_on_hand_uzs,pending_uzs,card_pending=_uzs_cash_state(db,agent)
    features={name:bool(core.feature_enabled(db,agent,name)) for name in core.AGENT_FEATURES}
    owned_clients=[c for c in clients if int(c.get("agentId") or 0)==int(agent)]
    wallet={
        "balanceUzs":int(core.agent_fund_balance_uzs(db,agent)),
        "balanceUsd":_usd(core.agent_fund_balance_usd(db,agent)),
        "categories":list(core.CASHIER_EXPENSE_CATEGORIES),
        "history":[]
    }
    return {
        "generatedTs":now,"timezone":"Asia/Tashkent","quick":True,
        "me":{"id":int(agent),"name":user["name"] or str(agent),
              "shiftOpen":bool(shift),"shiftStart":int(shift["start"]) if shift else None,
              "liveAttached":bool(shift and shift['live_id'] is not None),
              "gps":{"ts":int(point["ts"]) if point else None,"lat":lat,"lon":lon}},
        "features":features,"clients":clients,"products":products,
        "collectionTasks":_collection_tasks(db,agent),
        "events":[],"handovers":[],"expenseWallet":wallet,
        "cashierRateUzsPerUsd":core.cashier_rate(db),
        "summary":{"visitsToday":visit_today,"newClientsToday":new_today,
                   "paymentTodayUsd":_usd(payments_today),
                   "paymentTodayUzs":_payments_split(db,agent,today,now)[0],
                   "paymentTodayUsdCash":_usd(_payments_split(db,agent,today,now)[1]),
                   "goodsToday":int(delivery_today[0] or 0),
                   "cashOnHandUsd":_usd(cash_on_hand),
                   "cashAvailableUsd":_usd(max(0,cash_on_hand-pending)),
                   "cashOnHandUzs":cash_on_hand_uzs,
                   "cashAvailableUzs":max(0,cash_on_hand_uzs-pending_uzs),
                   "cardPending":card_pending},
        "period":{"day":{},"week":{},"month":{}},
        "reportAnalytics":{},
        "clientCount":len(owned_clients),
        "truncated":int(db.execute("SELECT COUNT(*) FROM clients").fetchone()[0] or 0)>MAX_CLIENTS
    }

def _uzs_cash_state(db,agent):
    on_hand=int(core.cash_som(db,agent))
    pending=int(db.execute("""SELECT COALESCE(SUM(amount),0) FROM handovers
        WHERE agent=? AND status='pending' AND COALESCE(amount,0)>0""",(agent,)).fetchone()[0] or 0)//100
    rows=db.execute("""SELECT p.id,p.client,p.currency,p.amount_uzs,p.amount_usd,p.rate_uzs_per_usd,p.ts,
        c.shop_name,c.name FROM card_payments p LEFT JOIN clients c ON c.id=p.client
        WHERE p.agent=? AND p.status='pending' ORDER BY p.ts DESC,p.id DESC LIMIT 50""",(agent,)).fetchall()
    cards=[{"id":int(r["id"]),"clientId":int(r["client"]),"client":r["shop_name"] or r["name"] or f"#{r['client']}",
            "currency":r["currency"],"amountUzs":int(r["amount_uzs"] or 0),"amountUsd":_usd(r["amount_usd"]),
            "rate":int(r["rate_uzs_per_usd"] or 0),"ts":int(r["ts"])} for r in rows]
    return on_hand,pending,cards


def _payments_split(db,agent,lo,hi):
    """Money taken from clients as it was received: so'm total, dollar-only total (cents)."""
    r=db.execute("""SELECT COALESCE(SUM(CASE WHEN COALESCE(paid_uzs,0)>0 THEN paid_uzs ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN COALESCE(paid_uzs,0)=0 THEN amount_usd ELSE 0 END),0)
        FROM events WHERE agent=? AND kind='payment' AND ts>=? AND ts<=?""",(agent,lo,hi)).fetchone()
    return int(r[0] or 0),int(r[1] or 0)


def _period_totals(db,agent,lo,now):
    pay=db.execute("""SELECT
      COALESCE(SUM(CASE WHEN COALESCE(paid_uzs,0)>0 THEN paid_uzs ELSE 0 END),0),
      COALESCE(SUM(CASE WHEN COALESCE(paid_uzs,0)=0 THEN amount_usd ELSE 0 END),0),
      COALESCE(SUM(CASE WHEN pay_method='card' THEN amount_usd ELSE 0 END),0)
      FROM events WHERE agent=? AND kind='payment' AND ts>=? AND ts<=?""",(agent,lo,now)).fetchone()
    card_wait=db.execute("""SELECT COALESCE(SUM(amount_uzs),0),COALESCE(SUM(CASE WHEN currency='USD' THEN amount_usd ELSE 0 END),0),COUNT(*)
      FROM card_payments WHERE agent=? AND status='pending' AND ts>=? AND ts<=?""",(agent,lo,now)).fetchone()
    row=db.execute("""SELECT
      COALESCE(SUM(CASE WHEN kind='payment' THEN amount_usd ELSE 0 END),0),
      COALESCE(SUM(CASE WHEN kind='delivery' THEN qty ELSE 0 END),0),
      COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd ELSE 0 END),0),
      COALESCE(SUM(CASE WHEN kind='sold' THEN qty ELSE 0 END),0),
      COALESCE(SUM(CASE WHEN kind='return' THEN qty ELSE 0 END),0),
      COALESCE(SUM(CASE WHEN kind='return' THEN amount_usd ELSE 0 END),0)
      FROM events WHERE agent=? AND ts>=? AND ts<=?""",(agent,lo,now)).fetchone()
    expense=db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM agent_funds
                WHERE agent=? AND kind='expense' AND ts>=? AND ts<=?""",(agent,lo,now)).fetchone()
    accepted=db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM handovers
                WHERE agent=? AND status='accepted' AND accepted_ts>=? AND accepted_ts<=?""",(agent,lo,now)).fetchone()
    return {"visits":int(db.execute("""SELECT COUNT(*) FROM client_visits
                WHERE actor=? AND ts>=? AND ts<=?""",(agent,lo,now)).fetchone()[0] or 0),
            "newClients":int(db.execute("""SELECT COUNT(*) FROM clients
                WHERE agent=? AND created_ts>=? AND created_ts<=?""",(agent,lo,now)).fetchone()[0] or 0),
            "paymentsUsd":_usd(row[0]),"paymentsUzs":int(pay[0] or 0),"paymentsUsdCash":_usd(pay[1]),
            "paymentsCardUsd":_usd(pay[2]),"cardPendingUzs":int(card_wait[0] or 0),
            "cardPendingUsd":_usd(card_wait[1]),"cardPendingCount":int(card_wait[2] or 0),
            "goods":int(row[1] or 0),
            "deliveryQty":int(row[1] or 0),"deliveryUsd":_usd(row[2]),
            "soldQty":int(row[3] or 0),"returnQty":int(row[4] or 0),
            "returnUsd":_usd(row[5]),"expenseUsd":_usd(expense[0]),
            "handoverAcceptedUsd":_usd(accepted[0])}


def _period_products(db,agent,products,lo,now):
    rows=db.execute("""SELECT pack,
        COALESCE(SUM(CASE WHEN kind='delivery' THEN qty ELSE 0 END),0) AS delivery_qty,
        COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd ELSE 0 END),0) AS delivery_usd,
        COALESCE(SUM(CASE WHEN kind='sold' THEN qty ELSE 0 END),0) AS sold_qty,
        COALESCE(SUM(CASE WHEN kind='return' THEN qty ELSE 0 END),0) AS return_qty,
        COALESCE(SUM(CASE WHEN kind='return' THEN amount_usd ELSE 0 END),0) AS return_usd
        FROM events WHERE agent=? AND ts>=? AND ts<=? AND pack>0
        GROUP BY pack""",(agent,lo,now)).fetchall()
    by_pack={int(r["pack"]):r for r in rows}
    out=[]
    for product in products:
        r=by_pack.get(int(product["pack"]))
        out.append({"pack":product["pack"],"name":product["name"],"weightKg":product["weightKg"],
                    "stock":product["stock"],"priceUsd":product["priceUsd"],
                    "deliveryQty":int(r["delivery_qty"] or 0) if r else 0,
                    "deliveryUsd":_usd(r["delivery_usd"]) if r else 0,
                    "soldQty":int(r["sold_qty"] or 0) if r else 0,
                    "returnQty":int(r["return_qty"] or 0) if r else 0,
                    "returnUsd":_usd(r["return_usd"]) if r else 0})
    return out


def period_report(db,agent,date_from,date_to,now=None):
    """Agent report for a custom date range (YYYY-MM-DD, Tashkent days, inclusive)."""
    _require_agent(db,agent)
    now=int(time.time() if now is None else now)
    try:
        d1=datetime.strptime(str(date_from or "").strip(),"%Y-%m-%d").replace(tzinfo=TZ)
        d2=datetime.strptime(str(date_to or "").strip(),"%Y-%m-%d").replace(tzinfo=TZ)
    except ValueError:
        raise ValueError("Sanani to‘g‘ri tanlang.")
    if d2<d1:d1,d2=d2,d1
    if (d2-d1).days>366:raise ValueError("Davr 1 yildan oshmasin.")
    lo=int(d1.timestamp());hi=min(now,int((d2+timedelta(days=1)).timestamp())-1)
    if lo>now:raise ValueError("Kelajakdagi sana tanlangan.")
    products=[{"pack":x["pack"],"name":x["name"],"weightKg":x["weightKg"],"priceUsd":x["priceUsd"],
               "stock":x["agentStock"]} for x in _products(db,agent)]
    return {"from":d1.strftime("%Y-%m-%d"),"to":d2.strftime("%Y-%m-%d"),"start":lo,"end":hi,
            "label":d1.strftime("%d.%m.%Y")+" – "+d2.strftime("%d.%m.%Y"),
            "period":_period_totals(db,agent,lo,hi),
            "products":_period_products(db,agent,products,lo,hi)}


def snapshot(db,agent,now=None):
    """Compatibility shape consumed by the premium Agent Mini App UI."""
    now=int(time.time() if now is None else now)
    base=dashboard(db,agent,now)
    today=base["todayStart"];week=today-6*86400;month=today-29*86400
    cash_on_hand=int(core.cash_usd(db,agent))
    pending=int(db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM handovers
        WHERE agent=? AND status='pending' AND COALESCE(amount,0)=0""",(agent,)).fetchone()[0] or 0)
    cash_on_hand_uzs,pending_uzs,card_pending=_uzs_cash_state(db,agent)
    event_rows=db.execute("""SELECT e.id,e.kind,e.client,e.pack,e.qty,e.amount_usd,e.ts,
        e.pay_method,e.paid_uzs,e.fx_rate,
        c.shop_name,c.name FROM events e LEFT JOIN clients c ON c.id=e.client
        WHERE e.agent=? AND e.ts>=? AND e.kind IN ('delivery','sold','return','payment','order','visit')
        ORDER BY e.ts DESC,e.id DESC LIMIT 500""",(agent,month)).fetchall()
    events=[{"id":int(e["id"]),"kind":e["kind"],
             "clientId":int(e["client"]) if e["client"] is not None else None,
             "shop":e["shop_name"] or e["name"] or (f"Mijoz #{e['client']}" if e["client"] else ""),
             "pack":int(e["pack"] or 0),"qty":int(e["qty"] or 0),
             "amountUsd":_usd(e["amount_usd"]),"ts":int(e["ts"]),
             "payMethod":e["pay_method"] or "","paidUzs":int(e["paid_uzs"] or 0),
             "rate":int(e["fx_rate"] or 0)} for e in event_rows]
    hand_rows=db.execute("""SELECT id,amount,amount_usd,status,ts,accepted_ts FROM handovers
        WHERE agent=? AND (ts>=? OR status='pending') ORDER BY ts DESC,id DESC LIMIT 300""",
        (agent,month)).fetchall()
    handovers=[{"id":int(h["id"]),"amountUsd":_usd(h["amount_usd"]),
                "currency":"UZS" if int(h["amount"] or 0)>0 else "USD",
                "amountUzs":int(h["amount"] or 0)//100,
                "status":h["status"],"ts":int(h["ts"]),
                "acceptedTs":int(h["accepted_ts"] or 0) or None} for h in hand_rows]
    fund_rows=db.execute("""SELECT f.id,f.kind,f.amount_usd,f.amount_uzs,f.rate_uzs_per_usd,f.category,f.note,f.ts,
        u.name AS actor_name FROM agent_funds f LEFT JOIN users u ON u.id=f.actor
        WHERE f.agent=? ORDER BY f.ts DESC,f.id DESC LIMIT 100""",(agent,)).fetchall()
    expense_wallet={
        "balanceUzs":int(core.agent_fund_balance_uzs(db,agent)),
        "balanceUsd":_usd(core.agent_fund_balance_usd(db,agent)),
        "categories":list(core.CASHIER_EXPENSE_CATEGORIES),
        "history":[{"id":int(x["id"]),"kind":x["kind"],"amountUsd":_usd(x["amount_usd"]),
                    "amountUzs":int(x["amount_uzs"] or 0),
                    "rateUzsPerUsd":int(x["rate_uzs_per_usd"] or 0),
                    "category":x["category"] or "","note":x["note"] or "",
                    "actor":x["actor_name"] or "","ts":int(x["ts"])} for x in fund_rows]
    }
    def p(lo):
        return _period_totals(db,agent,lo,now)
    clients=[]
    for c in base["clients"]:
        item=dict(c)
        item["agent"]=item.pop("owner")
        item["agentId"]=item.pop("ownerId")
        item["comment"]=item.get("note","")
        item["status"]=item.get("statusLabel") or item.get("status")
        clients.append(item)
    products=[{"pack":x["pack"],"name":x["name"],"weightKg":x["weightKg"],"priceUsd":x["priceUsd"],
               "stock":x["agentStock"],"blockUnits":x["blockUnits"]} for x in base["products"]]
    owned_clients=[c for c in clients if int(c.get("agentId") or 0)==int(agent)]
    report_client_status={"fresh":0,"yellow":0,"red":0,"scheduled":0,"unknown":0}
    for c in owned_clients:
        key=c.get("age") if c.get("age") in report_client_status else "unknown"
        report_client_status[key]+=1
    client_debt_usd=round(sum(float(c.get("debtUsd") or 0) for c in owned_clients),2)

    def product_report(lo):
        return _period_products(db,agent,products,lo,now)

    report_series=[]
    for k in range(6,-1,-1):
        lo=today-k*86400;hi=min(now,lo+86400-1)
        row=db.execute("""SELECT
            COALESCE(SUM(CASE WHEN kind='payment' THEN amount_usd ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN kind='delivery' THEN qty ELSE 0 END),0)
            FROM events WHERE agent=? AND ts>=? AND ts<=?""",(agent,lo,hi)).fetchone()
        visits=int(db.execute("""SELECT COUNT(*) FROM client_visits
            WHERE actor=? AND ts>=? AND ts<=?""",(agent,lo,hi)).fetchone()[0] or 0)
        report_series.append({"day":datetime.fromtimestamp(lo,TZ).strftime("%d.%m"),
                              "visits":visits,"paymentsUsd":_usd(row[0]),
                              "deliveryUsd":_usd(row[1]),"deliveryQty":int(row[2] or 0)})

    shift=base["shift"]
    return {"generatedTs":base["generatedTs"],"timezone":base["timezone"],
            "me":{"id":base["profile"]["id"],"name":base["profile"]["name"],
                  "shiftOpen":shift["open"],"shiftStart":shift["start"],
                  "liveAttached":shift["liveConnected"],
                  "gps":{"ts":shift["lastGpsTs"],"lat":shift["lat"],"lon":shift["lon"]}},
            "features":base["features"],"clients":clients,"products":products,
            "collectionTasks":_collection_tasks(db,agent),
            "events":events,"handovers":handovers,"expenseWallet":expense_wallet,
            "cashierRateUzsPerUsd":core.cashier_rate(db),
            "summary":{"visitsToday":base["summary"]["visitsToday"],
                       "newClientsToday":base["summary"]["newClientsToday"],
                       "paymentTodayUsd":base["summary"]["paymentsTodayUsd"],
                       "paymentTodayUzs":_payments_split(db,agent,today,now)[0],
                       "paymentTodayUsdCash":_usd(_payments_split(db,agent,today,now)[1]),
                       "goodsToday":base["summary"]["deliveryTodayQty"],
                       "cashOnHandUsd":_usd(cash_on_hand),
                       "cashAvailableUsd":_usd(max(0,cash_on_hand-pending)),
                       "cashOnHandUzs":cash_on_hand_uzs,
                       "cashAvailableUzs":max(0,cash_on_hand_uzs-pending_uzs),
                       "cardPending":card_pending},
            "period":{"day":p(today),"week":p(week),"month":p(month)},
            "reportAnalytics":{"series":report_series,
                               "clients":{"total":len(owned_clients),"debtUsd":client_debt_usd,
                                          "status":report_client_status},
                               "products":{"day":product_report(today),
                                           "week":product_report(week),
                                           "month":product_report(month)}},
            "clientCount":len(owned_clients),
            "truncated":int(db.execute("SELECT COUNT(*) FROM clients").fetchone()[0] or 0)>MAX_CLIENTS}


def client_detail(db,agent,cid,now=None):
    _require_agent(db,agent);_feature(db,agent,'clients')
    c=_client(db,cid);now=int(time.time() if now is None else now)
    snapshots={x['id']:x for x in _client_snapshot(db,now,c['id'])}
    base=snapshots.get(int(c['id']))
    visits=db.execute("""SELECT v.id,v.status,v.note,v.followup,v.ts,v.actor,u.name AS actor_name,
        v.checkin_ts,v.distance_m,v.photo
        FROM client_visits v LEFT JOIN users u ON u.id=v.actor
        WHERE v.client=? ORDER BY v.ts DESC,v.id DESC LIMIT 20""",(c['id'],)).fetchall()
    stock_by={}
    ids=[int(v['id']) for v in visits]
    if ids:
        for r in db.execute(f"SELECT visit,pack,counted,expected FROM visit_stock WHERE visit IN ({','.join('?' for _ in ids)}) ORDER BY id",ids).fetchall():
            stock_by.setdefault(int(r['visit']),[]).append({"pack":int(r['pack']),"name":core.product_name(int(r['pack'])),
                "counted":int(r['counted']),"expected":int(r['expected'])})
    events=db.execute("""SELECT e.id,e.kind,e.pack,e.qty,e.amount_usd,e.ts,e.pay_method,e.paid_uzs,u.name AS actor_name
        FROM events e LEFT JOIN users u ON u.id=e.actor WHERE e.client=?
        AND e.kind IN ('delivery','sold','return','payment','order','visit')
        ORDER BY e.ts DESC,e.id DESC LIMIT 40""",(c['id'],)).fetchall()
    return {
      "client":base,
      "visits":[{"status":v['status'],"statusLabel":STATUS_LABELS.get(v['status'],v['status']),
                 "note":v['note'] or "","followup":v['followup'] or None,
                 "ts":int(v['ts']),"actor":v['actor_name'] or str(v['actor']),
                 "id":int(v['id']),"checkinTs":int(v['checkin_ts'] or 0) or None,
                 "durationMin":(max(1,(int(v['ts'])-int(v['checkin_ts'])+59)//60) if int(v['checkin_ts'] or 0) else None),
                 "distanceM":(int(v['distance_m']) if v['distance_m'] is not None else None),
                 "hasPhoto":bool(v['photo']),"stock":stock_by.get(int(v['id']),[])} for v in visits],
      "visitRadiusM":visit_radius_m(),
      "orders":[core.order_view(db,o) for o in db.execute(
          "SELECT * FROM orders WHERE client=? ORDER BY ts DESC,id DESC LIMIT 10",(c['id'],)).fetchall()],
      "events":[{"id":int(e['id']),"kind":e['kind'],"pack":int(e['pack'] or 0),
                 "qty":int(e['qty'] or 0),"amountUsd":_usd(e['amount_usd']),
                 "payMethod":e['pay_method'] or "","paidUzs":int(e['paid_uzs'] or 0),
                 "ts":int(e['ts']),"actor":e['actor_name'] or ""} for e in events]
    }


def route(db,agent,period=None,now=None):
    _require_agent(db,agent)
    now=int(time.time() if now is None else now)
    if period is None:
        shift=db.execute("""SELECT id,start,"end" AS end_ts FROM shifts WHERE agent=?
            ORDER BY id DESC LIMIT 1""",(agent,)).fetchone()
        if not shift:return {"start":None,"end":None,"points":[]}
        rows=db.execute("""SELECT lat,lon,ts FROM points WHERE shift=?
            ORDER BY ts DESC,id DESC LIMIT 1500""",(shift['id'],)).fetchall()
        points=[]
        for p in reversed(rows):
            lat,lon=_coord(p['lat'],p['lon'])
            if lat is not None:points.append({"lat":lat,"lon":lon,"ts":int(p['ts'])})
        return {"start":int(shift['start']),"end":int(shift['end_ts']) if shift['end_ts'] else None,
                "points":points}

    period=str(period or "").lower()
    if period not in ("day","week","month"):
        raise ValueError("GPS hisobot davri noto‘g‘ri.")
    today=_midnight(now)
    start=today if period=="day" else today-6*86400 if period=="week" else today-29*86400
    shifts=db.execute("""SELECT id,start,"end" AS end_ts FROM shifts
        WHERE agent=? AND start<=? AND ("end" IS NULL OR "end">=?)
        ORDER BY start,id""",(agent,now,start)).fetchall()

    total_km=0.0;work_seconds=0;gps_points=0;gaps=0;stops=0
    segments=[];first_ts=None;last_ts=None
    for shift in shifts:
        lo=max(start,int(shift["start"]))
        hi=min(now,int(shift["end_ts"]) if shift["end_ts"] else now)
        if hi<lo:continue
        work_seconds+=max(0,hi-lo)
        rows=db.execute("""SELECT lat,lon,ts,accuracy FROM points
            WHERE shift=? AND ts>=? AND ts<=? ORDER BY ts,id""",
            (shift["id"],lo,hi)).fetchall()
        pts=[]
        for row in rows:
            lat,lon=_coord(row["lat"],row["lon"])
            if lat is None:continue
            pts.append({"lat":lat,"lon":lon,"ts":int(row["ts"]),
                        "accuracy":float(row["accuracy"] or 0)})
        if not pts:continue
        gps_points+=len(pts)
        first_ts=pts[0]["ts"] if first_ts is None else min(first_ts,pts[0]["ts"])
        last_ts=pts[-1]["ts"] if last_ts is None else max(last_ts,pts[-1]["ts"])
        stats=core.route_stats(pts,lo,hi)
        total_km+=float(stats["km"] or 0);gaps+=len(stats["gaps"]);stops+=len(stats["stops"])

        current=[];prev=None
        for p in pts:
            if p["accuracy"]>100:
                if current:segments.append(current);current=[]
                prev=None;continue
            if prev:
                dt=p["ts"]-prev["ts"]
                if dt>300 or dt<=0 or core.distance(prev,p)/max(1,dt)>55:
                    if current:segments.append(current)
                    current=[]
            current.append({"lat":p["lat"],"lon":p["lon"],"ts":p["ts"],
                            "accuracy":round(p["accuracy"],1)})
            prev=p
        if current:segments.append(current)

    # Keep map payload bounded without changing distance calculation, which uses all stored points above.
    visible=sum(len(seg) for seg in segments)
    if visible>8000:
        step=max(2,(visible+7999)//8000)
        sampled=[]
        for seg in segments:
            if len(seg)<=2:sampled.append(seg);continue
            part=seg[::step]
            if part[-1] is not seg[-1]:part.append(seg[-1])
            sampled.append(part)
        segments=sampled
    points=[p for seg in segments for p in seg]
    return {"period":period,"start":start,"end":now,
            "firstGpsTs":first_ts,"lastGpsTs":last_ts,
            "km":round(total_km,2),"workSeconds":int(work_seconds),
            "shiftCount":len(shifts),"gpsPoints":int(gps_points),
            "stops":int(stops),"gaps":int(gaps),
            "points":points,"segments":segments}


def mutate(db,agent,action,payload,request_id,now=None,admin_override=False):
    now=int(time.time() if now is None else now)
    op_ts=_operation_ts(payload,now)
    _require_agent(db,agent)
    feature=FEATURE_ACTION.get(action)
    if feature and not admin_override:_feature(db,agent,feature)
    core.lock_agent(db,agent)
    if not _reserve(db,agent,request_id,action):
        return {"ok":True,"duplicate":True,"message":"Bu so‘rov avval saqlangan."}
    source=_source(agent,request_id)
    if action=="shift_start":
        if db.execute("SELECT 1 FROM shifts WHERE agent=? AND end IS NULL",(agent,)).fetchone():
            raise ValueError("Ish allaqachon boshlangan.")
        cur=db.execute("INSERT INTO shifts(agent,start) VALUES(?,?) RETURNING id",(agent,now))
        return {"ok":True,"shiftId":int(cur.fetchone()[0]),
                "message":"Ish boshlandi. Endi Telegram chatda jonli lokatsiyani ulashing."}
    if action=="shift_end":
        shift=db.execute("SELECT id FROM shifts WHERE agent=? AND end IS NULL ORDER BY id DESC LIMIT 1",(agent,)).fetchone()
        if not shift:return {"ok":True,"message":"Ochiq smena yo‘q."}
        db.execute("UPDATE shifts SET end=? WHERE id=?",(now,shift['id']))
        return {"ok":True,"message":"Ish tugadi. Telegramdagi jonli lokatsiyani ham to‘xtating.",
                "_notify":{"kind":"shift_end","shiftId":int(shift['id'])}}
    if action in ("client","add_client"):
        shop=str(payload.get("shopName") or payload.get("shop") or "").strip()
        name=str(payload.get("name") or payload.get("person") or "").strip() or shop
        if not shop or len(shop)>120:raise ValueError("Do‘kon nomini kiriting.")
        phones=_parse_phones(payload.get("phone"))
        entered=set(phones)
        for row in db.execute("SELECT phone FROM clients WHERE phone IS NOT NULL").fetchall():
            try:existing=set(_parse_phones(row[0]))
            except ValueError:continue
            if entered & existing:raise ValueError("Telefon raqamlaridan biri avval kiritilgan.")
        lat,lon=_coord(payload.get("lat"),payload.get("lon"))
        if lat is None:raise ValueError("Mijoz joylashuvini GPS orqali belgilang.")
        address=str(payload.get("address") or "").strip()
        if len(address)>300:raise ValueError("Manzil juda uzun.")
        if not address:address=f"GPS: {lat:.6f}, {lon:.6f}"
        region=str(payload.get('region') or '').strip()
        if len(region)>80:raise ValueError('Hudud nomi juda uzun.')
        photo_file=str(payload.get("photoFileId") or "").strip()
        if photo_file and not re.fullmatch(r"[A-Za-z0-9_-]{10,512}",photo_file):
            raise ValueError("Mijoz fotosi identifikatori noto‘g‘ri.")
        items=payload.get("items") or []
        if not isinstance(items,list) or len(items)>MAX_WRITE_ITEMS:
            raise ValueError("Mahsulotlar ro‘yxati noto‘g‘ri.")
        clean=[];required={}
        for item in items:
            if not isinstance(item,dict):raise ValueError("Mahsulot noto‘g‘ri.")
            try:pack=int(item.get("pack"));qty=int(item.get("qty"))
            except (TypeError,ValueError):raise ValueError("Mahsulot miqdori noto‘g‘ri.")
            if pack not in core.PRODUCTS or qty<=0 or qty>100000:
                raise ValueError("Mahsulot miqdori noto‘g‘ri.")
            required[pack]=required.get(pack,0)+qty
            clean.append((pack,qty))
        status="active" if clean else str(payload.get("status") or "interested")
        if status not in cs.LABELS:
            raise ValueError("Mijoz maqomi noto‘g‘ri.")
        followup=None if clean else (payload.get("followup") or None)
        followup=cs.normalize(status,followup)
        note=str(payload.get("note") or "").strip()
        if len(note)>1000:raise ValueError("Izoh juda uzun.")
        if not note:
            note=("Tovar berildi" if clean else "Yangi mijoz · mahsulot hozircha berilmadi")
        cur=db.execute("""INSERT INTO clients(agent,name,phone,address,region,lat,lon,photo,shop_name,
            comment,payment_due,created_ts,map_only)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1) RETURNING id""",
            (agent,name," · ".join(phones),address,region,lat,lon,photo_file or None,shop,note,None,op_ts))
        cid=int(cur.fetchone()[0])
        if clean:
            for idx,(pack,qty) in enumerate(clean):
                core.record(db,agent,agent,cid,'delivery',pack,qty,0,'Yangi mijoz · Mini App',
                            _source(agent,request_id,idx+1),currency='USD',ts=op_ts)
            visit_note="Tovar berildi: "+", ".join(
                f"{core.product_name(pack)} {qty} dona" for pack,qty in clean)
            if note and note!="Tovar berildi":visit_note+=" · "+note
            cs.add_visit(db,agent,cid,'active',visit_note,None,ts=op_ts)
            return {"ok":True,"clientId":cid,"deliveredItems":len(clean),
                    "message":"Mijoz va mahsulotlar real bazaga saqlandi."}
        cs.add_visit(db,agent,cid,status,note,followup,ts=op_ts)
        return {"ok":True,"clientId":cid,"deliveredItems":0,
                "message":"Mijoz mahsulotsiz prospekt sifatida saqlandi."}
    if action=="handover":
        currency=str(payload.get("currency") or "USD").upper()
        if currency=="UZS":
            amount=core.parse_whole_som(payload.get("amount"),"Summa")
        elif currency=="USD":
            amount=core.money(payload.get("amount"))
        else:
            raise ValueError("Valyutani USD yoki UZS qilib tanlang.")
        # handovers.amount keeps the legacy tiyin unit (1/100 so'm)
        core.handover(db,agent,amount*100 if currency=="UZS" else amount,source,currency=currency,ts=op_ts)
        row=db.execute("SELECT id,amount,amount_usd FROM handovers WHERE agent=? AND source=?",(agent,source)).fetchone()
        hid=int(row[0]) if row else None
        shown=f"{amount:,} so‘m" if currency=="UZS" else f"{_usd(amount):.2f} USD"
        return {"ok":True,"handoverId":hid,"message":f"Kassaga {shown} topshirish yuborildi. Kassir tasdig‘i kutilmoqda.",
                "_notify":{"kind":"handover","handoverId":hid,"amount":int(row["amount_usd"]) if row else amount,
                           "currency":currency,"amountUzs":amount if currency=="UZS" else None}}
    if action=="agent_expense":
        category=str(payload.get("category") or "").strip()
        note=str(payload.get("note") or "").strip()
        if not note:raise ValueError("Xarajat izohini kiriting.")
        amount_uzs=core.parse_whole_som(payload.get("amount"),"Xarajat")
        expected_rate=payload.get("expectedRate")
        expected_rate=(core.parse_whole_som(expected_rate,"Kurs") if expected_rate not in (None,"") else None)
        expense_source=abs(source)
        expense_id,amount_usd,rate=core.add_agent_expense_uzs(
            db,agent,amount_uzs,category,note,expense_source,expected_rate=expected_rate,ts=op_ts)
        balance_uzs=core.agent_fund_balance_uzs(db,agent)
        return {"ok":True,"expenseId":expense_id,"balanceUzs":balance_uzs,
                "convertedUsd":_usd(amount_usd),"rateUzsPerUsd":rate,
                "message":f"Xarajat saqlandi: {amount_uzs:,} UZS. Qoldiq: {balance_uzs:,} UZS.",
                "_notify":{"kind":"agent_expense","expenseId":expense_id,"amount":amount_usd,
                           "amountUzs":amount_uzs,"rate":rate,
                           "category":category,"note":note,"balanceUzs":balance_uzs}}
    cid=int(payload.get("clientId") or 0)
    current_client=_client(db,cid)
    if action=="client_blacklist":
        on=bool(payload.get("on",True))
        core.set_client_blacklist(db,agent,cid,on,payload.get("reason") or "",ts=now)
        return {"ok":True,"clientId":cid,"blacklisted":on,
                "message":"⛔ Mijoz qora ro‘yxatga qo‘shildi. U bazada va xaritada qoladi." if on else "✅ Mijoz qora ro‘yxatdan chiqarildi.",
                "_notify":{"kind":"blacklist","client":cid,"reason":str(payload.get("reason") or "").strip()} if on else None}
    if int(current_client['blacklisted'] or 0):
        raise ValueError(core.BLACKLIST_MSG)
    if action=="client_edit":
        shop=str(payload.get("shopName") or payload.get("shop") or "").strip()
        person=str(payload.get("name") or payload.get("person") or "").strip()
        if not shop or len(shop)>120:raise ValueError("Do‘kon nomini kiriting.")
        if len(person)>120:raise ValueError("Mijoz ismi juda uzun.")
        phones=_parse_phones(payload.get("phone"))
        entered=set(phones)
        for row in db.execute("SELECT id,phone FROM clients WHERE id<>? AND phone IS NOT NULL",(cid,)).fetchall():
            try:existing=set(_parse_phones(row["phone"]))
            except ValueError:continue
            if entered & existing:raise ValueError("Telefon raqamlaridan biri boshqa mijozda mavjud.")
        address=str(payload.get("address") or "").strip()
        note=str(payload.get("note") or payload.get("comment") or "").strip()
        if len(address)>300:raise ValueError("Manzil juda uzun.")
        if len(note)>1000:raise ValueError("Izoh juda uzun.")
        region=str(payload.get('region') or '').strip()
        if len(region)>80:raise ValueError('Hudud nomi juda uzun.')
        values={"shop_name":shop,"name":person,"phone":" · ".join(phones),
                "address":address,"region":region,"comment":note}
        if "lat" in payload or "lon" in payload:
            lat,lon=_coord(payload.get("lat"),payload.get("lon"))
            if lat is None:raise ValueError("Mijoz lokatsiyasining ikkala koordinatasini kiriting.")
            values.update(lat=lat,lon=lon)
        photo_file=str(payload.get("photoFileId") or "").strip()
        if photo_file:
            if not re.fullmatch(r"[A-Za-z0-9_-]{10,512}",photo_file):
                raise ValueError("Mijoz fotosi identifikatori noto‘g‘ri.")
            values["photo"]=photo_file
        core.edit_client(db,agent,cid,values)
        return {"ok":True,"clientId":cid,
                "message":"Mijoz ma’lumotlari yangilandi. Savdo va qarz tarixi o‘zgarmadi."}
    if action=="visit":
        status=str(payload.get("status") or "")
        note=str(payload.get("note") or "").strip()
        followup=payload.get("followup") or None
        if payload.get("checkinTs") in (None,""):
            # Older cached app versions: plain visit note without check-in.
            cs.add_visit(db,agent,cid,status,note,followup,ts=op_ts)
            return {"ok":True,"message":"Tashrif saqlandi."}
        try:checkin=int(payload.get("checkinTs"))
        except (TypeError,ValueError):raise ValueError("Tashrif boshlanish vaqti noto‘g‘ri.")
        if checkin>op_ts+60 or op_ts-checkin>VISIT_MAX_HOURS*3600:
            raise ValueError("Tashrif boshlanish vaqti noto‘g‘ri. Tashrifni qaytadan boshlang.")
        checkin=min(checkin,op_ts)
        photo=str(payload.get("photoFileId") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{10,512}",photo):raise ValueError("Do‘kon (javon) rasmini oling.")
        stock=_visit_stock_items(db,cid,payload.get("stock"))
        lat,lon,dist=_visit_gps(db,agent,current_client,checkin,op_ts)
        vid=cs.add_visit(db,agent,cid,status,note,followup,ts=op_ts)
        db.execute("UPDATE client_visits SET checkin_ts=?,lat=?,lon=?,distance_m=?,photo=? WHERE id=?",
                   (checkin,lat,lon,dist,photo,vid))
        for pack,qty,expected in stock:
            db.execute("INSERT INTO visit_stock(visit,client,pack,counted,expected,ts) VALUES(?,?,?,?,?,?)",
                       (vid,cid,pack,qty,expected,op_ts))
        minutes=max(1,(op_ts-checkin+59)//60)
        parts=[f"{minutes} daqiqa"]
        if dist is not None:parts.append(f"do‘kondan {dist} m")
        if stock:parts.append(f"{len(stock)} xil qoldiq sanaldi")
        return {"ok":True,"visitId":vid,"distanceM":dist,"durationMin":minutes,
                "message":"Tashrif saqlandi: "+", ".join(parts)+"."}
    if action=="delivery":
        items=payload.get("items")
        if not isinstance(items,list) or not items or len(items)>MAX_WRITE_ITEMS:
            raise ValueError("Kamida bitta tovar kiriting.")
        required={}
        clean=[];new_products=[]
        for item in items:
            if not isinstance(item,dict):raise ValueError("Tovar noto‘g‘ri.")
            if str(item.get("customName") or "").strip():
                # Product not in the catalog: the agent writes its name and unit price.
                try:qty=int(item.get("qty"))
                except (TypeError,ValueError):raise ValueError("Tovar miqdori noto‘g‘ri.")
                if qty<=0 or qty>100000:raise ValueError("Tovar miqdori noto‘g‘ri.")
                pack,created=core.agent_custom_product(db,agent,item.get("customName"),core.money(item.get("priceUsd")),ts=op_ts)
                if created:new_products.append(core.product_name(pack))
                required[pack]=required.get(pack,0)+qty;clean.append((pack,qty));continue
            try:pack=int(item.get("pack"));qty=int(item.get("qty"))
            except (TypeError,ValueError):raise ValueError("Tovar miqdori noto‘g‘ri.")
            if pack not in core.PRODUCTS or qty<=0 or qty>100000:raise ValueError("Tovar miqdori noto‘g‘ri.")
            required[pack]=required.get(pack,0)+qty;clean.append((pack,qty))
        oid=None
        if payload.get("orderId") not in (None,""):
            try:oid=int(payload.get("orderId"))
            except (TypeError,ValueError):raise ValueError("Buyurtma raqami noto‘g‘ri.")
            core.mark_order_delivered_by_agent(db,agent,cid,oid,ts=op_ts)   # validates before any write
        for idx,(pack,qty) in enumerate(clean):
            core.record(db,agent,agent,cid,'delivery',pack,qty,0,'Mini App'+(f' · buyurtma #{oid}' if oid else ''),
                        _source(agent,request_id,idx+1),currency='USD',ts=op_ts)
        cs.add_visit(db,agent,cid,'active','Tovar berildi: '+', '.join(
            f"{core.product_name(pack)} {qty} dona" for pack,qty in clean),ts=op_ts)
        extra=(" Katalogga qo‘shildi: "+", ".join(new_products)+" — rahbar narxini tekshiradi.") if new_products else ""
        if oid:
            return {"ok":True,"message":f"Buyurtma #{oid} mijozga topshirildi, qarz yangilandi.{extra}"}
        return {"ok":True,"message":"Tovar topshirildi va mijoz qarzi yangilandi."+extra}
    if action=="sold":
        items=payload.get("items")
        if not isinstance(items,list) or not items or len(items)>MAX_WRITE_ITEMS:
            raise ValueError("Sotilgan tovarni kiriting.")
        clean={}
        for item in items:
            if not isinstance(item,dict):raise ValueError("Tovar noto‘g‘ri.")
            try:pack=int(item.get("pack"));qty=int(item.get("qty"))
            except (TypeError,ValueError):raise ValueError("Sotilgan miqdor noto‘g‘ri.")
            if pack not in core.PRODUCTS or qty<=0 or qty>100000:raise ValueError("Sotilgan miqdor noto‘g‘ri.")
            clean[pack]=clean.get(pack,0)+qty
        for pack,qty in clean.items():
            have=core.client_stock_total(db,cid,pack)
            if have<qty:raise ValueError(f"{core.product_name(pack)}: mijozda hisob bo‘yicha {have} dona bor.")
        for idx,(pack,qty) in enumerate(clean.items()):
            core.record(db,agent,agent,cid,'sold',pack,qty,0,'Mini App · sotildi',
                        _source(agent,request_id,idx+1),currency='USD',ts=op_ts)
        return {"ok":True,"message":"Sotilgan tovar yozildi. Mijozdagi qoldiq kamaydi, qarz o‘zgarmadi."}
    if action=="order":
        oid,dup=core.create_order(db,agent,cid,payload.get("items"),payload.get("note"),source=source,ts=op_ts)
        if dup:return {"ok":True,"duplicate":True,"orderId":oid,"message":"Bu buyurtma avval yuborilgan."}
        view=core.order_view(db,db.execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone())
        extra=f" {view['unmapped']} ta mahsulot katalogda yo‘q — rahbar ko‘rib chiqadi." if view['unmapped'] else ""
        return {"ok":True,"orderId":oid,"message":f"Buyurtma #{oid} omborga yuborildi.{extra}",
                "_notify":{"kind":"order","orderId":oid}}
    if action=="payment":
        if not admin_override:
            ok,msg=_live_ready(db,agent,now=op_ts)
            if not ok:raise ValueError(msg)
        currency=str(payload.get("currency") or "USD").upper()
        method=str(payload.get("method") or "cash").lower()
        if method not in core.PAY_METHODS:raise ValueError("To‘lov usulini tanlang: naqd yoki karta.")
        if currency not in ("USD","UZS"):raise ValueError("Valyutani USD yoki UZS qilib tanlang.")
        rate=None;usd_in=None
        if currency=="UZS":
            som=core.parse_whole_som(payload.get("amount"),"To‘lov")
            raw_rate=payload.get("rate")
            if payload.get("usd") not in (None,""):
                # New flow: agent enters the so'm received AND its dollar equivalent; the rate is derived.
                usd_in=core.money(payload.get("usd"))
                rate=core.implied_rate(db,som,usd_in)
            elif raw_rate not in (None,""):
                rate=core.parse_whole_som(raw_rate,"Kurs")
            else:
                # Older cached app versions send only the cashier rate they saw.
                rate=core.cashier_rate(db)
                if rate is None:raise ValueError("Kassir hali kurs belgilamagan. Mijoz bilan kelishilgan kursni kiriting.")
                expected_raw=payload.get("expectedRate")
                if expected_raw not in (None,"") and core.parse_whole_som(expected_raw,"Kurs")!=rate:
                    raise ValueError("Kassir kursni o‘zgartirdi. Yangi kursni ko‘rib to‘lovni qayta tasdiqlang.")
            value=som
        else:
            value=core.money(payload.get("amount"))
        label="Karta" if method=="card" else "Naqd"
        note=f"Mini App · {label} · "+((f"{value} UZS = {_usd(usd_in):.2f} USD · kurs {rate}" if usd_in else f"{value} UZS · 1 USD = {rate} UZS") if currency=="UZS" else "USD")
        if method=="card":
            # Card / bank transfer: the agent photographs the receipt (chek) so the cashier can check it.
            receipt=str(payload.get("photoFileId") or "").strip()
            if receipt and not re.fullmatch(r"[A-Za-z0-9_-]{10,512}",receipt):
                raise ValueError("Chek rasmi noto‘g‘ri. Qayta suratga oling.")
            if not receipt and not admin_override:
                raise ValueError("Karta to‘lovi uchun chekni rasmga oling.")
            pid,usd,som_saved,rate_saved=core.submit_card_payment(db,agent,cid,currency,value,rate=rate,note=note,source=source,ts=op_ts,usd_cents=usd_in,photo=receipt)
            if usd is None:
                return {"ok":True,"duplicate":True,"cardPaymentId":pid}
            shown=f"{value:,} UZS → {_usd(usd):.2f} USD (kurs {rate:,})" if currency=="UZS" else f"{_usd(usd):.2f} USD"
            return {"ok":True,"cardPaymentId":pid,"pendingConfirmation":True,
                    "message":f"Karta to‘lovi yuborildi: {shown}. Kassir bankdan tasdiqlagach mijoz qarzidan ayriladi.",
                    "_notify":{"kind":"card_payment","client":cid,"paymentId":pid,"amount":usd,"currency":currency,
                               "amountUzs":value if currency=="UZS" else None,"rate":rate}}
        usd,som_saved,rate_saved=core.record_client_payment(db,agent,agent,cid,currency,value,'cash',rate=rate,
                                                            note=note,source=source,ts=op_ts,usd_cents=usd_in)
        if core.client_debt_usd(db,cid)<=0:
            db.execute("UPDATE collection_tasks SET status='done',completed_ts=? WHERE client=? AND status='open'",
                       (op_ts,cid))
        if currency=="UZS":
            message=f"{value:,} UZS → {_usd(usd):.2f} USD to‘lov saqlandi. Kurs: 1 USD = {rate:,} UZS. Pul qo‘lingizda so‘mda turadi."
        else:
            message=f"{_usd(usd):.2f} USD to‘lov saqlandi."
        return {"ok":True,"message":message,"convertedUsd":_usd(usd),
                "rateUzsPerUsd":rate if currency=="UZS" else core.cashier_rate(db),
                "_notify":{"kind":"payment","client":cid,"amount":usd,"currency":currency,
                           "amountUzs":value if currency=="UZS" else None,"rate":rate}}
    if action=="return":
        if not admin_override:
            ok,msg=_live_ready(db,agent,now=op_ts)
            if not ok:raise ValueError(msg)
        items=payload.get("items")
        if not isinstance(items,list) or not items or len(items)>MAX_WRITE_ITEMS:
            raise ValueError("Qaytariladigan tovarni kiriting.")
        clean=[]
        for item in items:
            if not isinstance(item,dict):raise ValueError("Qaytarish noto‘g‘ri.")
            try:pack=int(item.get("pack"));qty=int(item.get("qty"))
            except (TypeError,ValueError):raise ValueError("Qaytarish miqdori noto‘g‘ri.")
            if pack not in core.PRODUCTS or qty<=0 or qty>100000:
                raise ValueError("Qaytarish miqdori noto‘g‘ri.")
            clean.append((pack,qty))
        for pack,qty in clean:
            if core.client_stock_total(db,cid,pack)<qty:
                raise ValueError(f"{core.product_name(pack)} mijozda yetarli emas.")
        for idx,(pack,qty) in enumerate(clean):
            core.record(db,agent,agent,cid,'return',pack,qty,0,'Mini App',
                        _source(agent,request_id,idx+1),currency='USD',ts=op_ts)
        cs.add_visit(db,agent,cid,'active','Tovar qaytarildi: '+', '.join(
            f"{core.product_name(pack)} {qty} dona" for pack,qty in clean),ts=op_ts)
        if core.client_debt_usd(db,cid)<=0:
            db.execute("UPDATE collection_tasks SET status='done',completed_ts=? WHERE client=? AND status='open'",
                       (op_ts,cid))
        return {"ok":True,"message":"Tovar qaytarildi va qarz yangilandi."}
    raise ValueError("Amal noto‘g‘ri.")
