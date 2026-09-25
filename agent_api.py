"""Secure live API for ASMAN Agent Mini App.

The browser never receives a bot token. Every request is authenticated by
Telegram initData and the current database role. Write actions reuse core
inventory/cash rules and customer_status visit rules.
"""
import hashlib
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import core
import customer_status as cs
import manager_api

TZ=ZoneInfo("Asia/Tashkent")
MAX_CLIENTS=5000
MAX_WRITE_ITEMS=12

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
    "visit":"visit",
    "delivery":"delivery",
    "payment":"payment",
    "return":"return",
    "handover":"handover",
}


def verify_init_data(raw,token,now=None):
    return manager_api.verify_init_data(raw,token,now)


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
    now=int(time.time() if now is None else now)
    shift=db.execute('SELECT * FROM shifts WHERE agent=? AND end IS NULL ORDER BY id DESC LIMIT 1',(agent,)).fetchone()
    if not shift:return False,'Avval «Ishni boshlash»ni bosing.'
    if shift['live_id'] is None:
        return False,'Ish boshlangan, lekin Telegram jonli lokatsiyasi hali ulanmagan.'
    p=db.execute('SELECT ts FROM points WHERE shift=? ORDER BY ts DESC,id DESC LIMIT 1',(shift['id'],)).fetchone()
    if not p:return False,'Jonli lokatsiya ulangan, lekin GPS koordinatasi hali kelmagan.'
    age=max(0,now-int(p[0]))
    if age>max_age:
        return False,f'Jonli lokatsiya {age//60} daqiqadan beri yangilanmagan. Telegram live-location, GPS va internetni tekshiring.'
    return True,''


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


def _client_snapshot(db,now):
    rows=db.execute("""SELECT c.*,u.name AS agent_name FROM clients c
        LEFT JOIN users u ON u.id=c.agent ORDER BY c.id DESC LIMIT ?""",(MAX_CLIENTS,)).fetchall()
    latest=db.execute("""SELECT v.client,v.status,v.followup,v.ts,v.note,v.actor,u.name AS actor_name
        FROM client_visits v LEFT JOIN users u ON u.id=v.actor
        WHERE v.id=(SELECT MAX(v2.id) FROM client_visits v2 WHERE v2.client=v.client)""").fetchall()
    latest_by={int(v['client']):v for v in latest}
    contacts=db.execute("""SELECT client,MAX(ts) AS ts FROM events
        WHERE client IS NOT NULL AND kind IN ('visit','delivery','payment','return')
        GROUP BY client""").fetchall()
    contacts={int(x['client']):int(x['ts']) for x in contacts if x['ts'] is not None}
    balances=db.execute("""SELECT client,
        COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd
                          WHEN kind IN ('payment','return') THEN -amount_usd ELSE 0 END),0) AS debt
        FROM events WHERE client IS NOT NULL GROUP BY client""").fetchall()
    debt={int(x['client']):int(x['debt'] or 0) for x in balances}
    stock_rows=db.execute("""SELECT client,pack,
        COALESCE(SUM(CASE WHEN kind='delivery' THEN qty
                          WHEN kind IN ('sold','return') THEN -qty ELSE 0 END),0) AS qty
        FROM events WHERE client IS NOT NULL AND pack IN (1,3,5)
        GROUP BY client,pack""").fetchall()
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
            "address":c['address'] or "","lat":lat,"lon":lon,
            "owner":c['agent_name'] or str(c['agent']),"ownerId":int(c['agent']),
            "status":status,"statusLabel":STATUS_LABELS.get(status,status),
            "age":age,"days":days,"lastTs":last or None,"followup":followup,
            "note":(v['note'] if v else c['comment']) or "",
            "debtUsd":_usd(debt.get(cid,0)),
            "stock":{"1":stocks.get(cid,{}).get(1,0),
                     "3":stocks.get(cid,{}).get(3,0),
                     "5":stocks.get(cid,{}).get(5,0)}
        })
    return result


def _products(db,agent):
    out=[]
    for pack in (1,3,5):
        out.append({"pack":pack,"name":core.product_name(pack),
                    "priceUsd":_usd(core.product_price(db,pack)),
                    "agentStock":int(core.agent_stock(db,agent,pack)),
                    "blockUnits":int(core.units_per_block(pack))})
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
    payments=db.execute("""SELECT e.id,e.client,e.amount_usd,e.ts,c.shop_name,c.name
        FROM events e LEFT JOIN clients c ON c.id=e.client
        WHERE e.agent=? AND e.kind='payment' AND e.ts>=?
        ORDER BY e.ts DESC,e.id DESC LIMIT 300""",(agent,month)).fetchall()
    handovers=db.execute("""SELECT id,amount_usd,status,ts,accepted_ts
        FROM handovers WHERE agent=? AND (ts>=? OR status='pending')
        ORDER BY ts DESC,id DESC LIMIT 200""",(agent,month)).fetchall()
    cash_ops=[]
    for e in payments:
        cash_ops.append({"id":f"p{int(e['id'])}","kind":"payment",
                         "client":e['shop_name'] or e['name'] or f"Mijoz #{e['client']}",
                         "amountUsd":_usd(e['amount_usd']),"ts":int(e['ts']),"state":"collected"})
    for h in handovers:
        cash_ops.append({"id":f"h{int(h['id'])}","kind":"handover","client":"Kassaga topshirish",
                         "amountUsd":_usd(h['amount_usd']),"ts":int(h['ts']),
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


def snapshot(db,agent,now=None):
    """Compatibility shape consumed by the premium Agent Mini App UI."""
    now=int(time.time() if now is None else now)
    base=dashboard(db,agent,now)
    today=base["todayStart"];week=today-6*86400;month=today-29*86400
    cash_on_hand=int(core.cash_usd(db,agent))
    pending=int(db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM handovers
        WHERE agent=? AND status='pending'""",(agent,)).fetchone()[0] or 0)
    event_rows=db.execute("""SELECT e.id,e.kind,e.client,e.pack,e.qty,e.amount_usd,e.ts,
        c.shop_name,c.name FROM events e LEFT JOIN clients c ON c.id=e.client
        WHERE e.agent=? AND e.ts>=? AND e.kind IN ('delivery','sold','return','payment','order','visit')
        ORDER BY e.ts DESC,e.id DESC LIMIT 500""",(agent,month)).fetchall()
    events=[{"id":int(e["id"]),"kind":e["kind"],
             "clientId":int(e["client"]) if e["client"] is not None else None,
             "shop":e["shop_name"] or e["name"] or (f"Mijoz #{e['client']}" if e["client"] else ""),
             "pack":int(e["pack"] or 0),"qty":int(e["qty"] or 0),
             "amountUsd":_usd(e["amount_usd"]),"ts":int(e["ts"])} for e in event_rows]
    hand_rows=db.execute("""SELECT id,amount_usd,status,ts,accepted_ts FROM handovers
        WHERE agent=? AND (ts>=? OR status='pending') ORDER BY ts DESC,id DESC LIMIT 300""",
        (agent,month)).fetchall()
    handovers=[{"id":int(h["id"]),"amountUsd":_usd(h["amount_usd"]),
                "status":h["status"],"ts":int(h["ts"]),
                "acceptedTs":int(h["accepted_ts"] or 0) or None} for h in hand_rows]
    def p(lo):
        row=db.execute("""SELECT
          COALESCE(SUM(CASE WHEN kind='payment' THEN amount_usd ELSE 0 END),0),
          COALESCE(SUM(CASE WHEN kind='delivery' THEN qty ELSE 0 END),0)
          FROM events WHERE agent=? AND ts>=? AND ts<=?""",(agent,lo,now)).fetchone()
        return {"visits":int(db.execute("""SELECT COUNT(*) FROM client_visits
                    WHERE actor=? AND ts>=? AND ts<=?""",(agent,lo,now)).fetchone()[0] or 0),
                "newClients":int(db.execute("""SELECT COUNT(*) FROM clients
                    WHERE agent=? AND created_ts>=? AND created_ts<=?""",(agent,lo,now)).fetchone()[0] or 0),
                "paymentsUsd":_usd(row[0]),"goods":int(row[1] or 0)}
    clients=[]
    for c in base["clients"]:
        item=dict(c)
        item["agent"]=item.pop("owner")
        item["agentId"]=item.pop("ownerId")
        item["comment"]=item.get("note","")
        item["status"]=item.get("statusLabel") or item.get("status")
        clients.append(item)
    products=[{"pack":x["pack"],"name":x["name"],"priceUsd":x["priceUsd"],
               "stock":x["agentStock"],"blockUnits":x["blockUnits"]} for x in base["products"]]
    shift=base["shift"]
    return {"generatedTs":base["generatedTs"],"timezone":base["timezone"],
            "me":{"id":base["profile"]["id"],"name":base["profile"]["name"],
                  "shiftOpen":shift["open"],"shiftStart":shift["start"],
                  "liveAttached":shift["liveConnected"],
                  "gps":{"ts":shift["lastGpsTs"],"lat":shift["lat"],"lon":shift["lon"]}},
            "features":base["features"],"clients":clients,"products":products,
            "events":events,"handovers":handovers,
            "summary":{"visitsToday":base["summary"]["visitsToday"],
                       "newClientsToday":base["summary"]["newClientsToday"],
                       "paymentTodayUsd":base["summary"]["paymentsTodayUsd"],
                       "goodsToday":base["summary"]["deliveryTodayQty"],
                       "cashOnHandUsd":_usd(cash_on_hand),
                       "cashAvailableUsd":_usd(max(0,cash_on_hand-pending))},
            "period":{"day":p(today),"week":p(week),"month":p(month)},
            "clientCount":len(clients),
            "truncated":int(db.execute("SELECT COUNT(*) FROM clients").fetchone()[0] or 0)>MAX_CLIENTS}


def client_detail(db,agent,cid,now=None):
    _require_agent(db,agent);_feature(db,agent,'clients')
    c=_client(db,cid);now=int(time.time() if now is None else now)
    snapshots={x['id']:x for x in _client_snapshot(db,now)}
    base=snapshots.get(int(c['id']))
    visits=db.execute("""SELECT v.status,v.note,v.followup,v.ts,v.actor,u.name AS actor_name
        FROM client_visits v LEFT JOIN users u ON u.id=v.actor
        WHERE v.client=? ORDER BY v.ts DESC,v.id DESC LIMIT 20""",(c['id'],)).fetchall()
    events=db.execute("""SELECT e.id,e.kind,e.pack,e.qty,e.amount_usd,e.ts,u.name AS actor_name
        FROM events e LEFT JOIN users u ON u.id=e.actor WHERE e.client=?
        AND e.kind IN ('delivery','sold','return','payment','order','visit')
        ORDER BY e.ts DESC,e.id DESC LIMIT 40""",(c['id'],)).fetchall()
    return {
      "client":base,
      "visits":[{"status":v['status'],"statusLabel":STATUS_LABELS.get(v['status'],v['status']),
                 "note":v['note'] or "","followup":v['followup'] or None,
                 "ts":int(v['ts']),"actor":v['actor_name'] or str(v['actor'])} for v in visits],
      "events":[{"id":int(e['id']),"kind":e['kind'],"pack":int(e['pack'] or 0),
                 "qty":int(e['qty'] or 0),"amountUsd":_usd(e['amount_usd']),
                 "ts":int(e['ts']),"actor":e['actor_name'] or ""} for e in events]
    }


def route(db,agent):
    _require_agent(db,agent)
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


def mutate(db,agent,action,payload,request_id,now=None):
    now=int(time.time() if now is None else now)
    _require_agent(db,agent)
    feature=FEATURE_ACTION.get(action)
    if feature:_feature(db,agent,feature)
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
        address=str(payload.get("address") or "").strip()
        note=str(payload.get("note") or "").strip()
        if not shop or len(shop)>120:raise ValueError("Do‘kon nomini kiriting.")
        if not address or len(address)>300:raise ValueError("Manzilni kiriting.")
        if not note or len(note)>1000:raise ValueError("Mijoz bilan suhbat izohini kiriting.")
        phones=_parse_phones(payload.get("phone"))
        entered=set(phones)
        for row in db.execute("SELECT phone FROM clients WHERE phone IS NOT NULL").fetchall():
            try:existing=set(_parse_phones(row[0]))
            except ValueError:continue
            if entered & existing:raise ValueError("Telefon raqamlaridan biri avval kiritilgan.")
        lat,lon=_coord(payload.get("lat"),payload.get("lon"))
        if lat is None:raise ValueError("Mijoz joylashuvini GPS orqali belgilang.")
        status=str(payload.get("status") or "interested")
        if status not in cs.LABELS:
            raise ValueError("Mijoz maqomi noto‘g‘ri.")
        followup=payload.get("followup") or None
        followup=cs.normalize(status,followup)
        cur=db.execute("""INSERT INTO clients(agent,name,phone,address,lat,lon,photo,shop_name,
            comment,payment_due,created_ts,map_only)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,1) RETURNING id""",
            (agent,name," · ".join(phones),address,lat,lon,None,shop,note,None,now))
        cid=int(cur.fetchone()[0])
        cs.add_visit(db,agent,cid,status,note,followup)
        return {"ok":True,"clientId":cid,"message":"Mijoz real bazaga saqlandi."}
    if action=="handover":
        amount=core.money(payload.get("amount"))
        core.handover(db,agent,amount,source,currency='USD')
        row=db.execute("SELECT id FROM handovers WHERE agent=? AND source=?",(agent,source)).fetchone()
        hid=int(row[0]) if row else None
        return {"ok":True,"handoverId":hid,"message":"Kassaga topshirish yuborildi. Kassir tasdig‘i kutilmoqda.",
                "_notify":{"kind":"handover","handoverId":hid,"amount":amount}}
    cid=int(payload.get("clientId") or 0)
    _client(db,cid)
    if action=="visit":
        status=str(payload.get("status") or "")
        note=str(payload.get("note") or "").strip()
        followup=payload.get("followup") or None
        cs.add_visit(db,agent,cid,status,note,followup)
        return {"ok":True,"message":"Tashrif saqlandi."}
    if action=="delivery":
        items=payload.get("items")
        if not isinstance(items,list) or not items or len(items)>MAX_WRITE_ITEMS:
            raise ValueError("Kamida bitta tovar kiriting.")
        required={}
        clean=[]
        for item in items:
            if not isinstance(item,dict):raise ValueError("Tovar noto‘g‘ri.")
            try:pack=int(item.get("pack"));qty=int(item.get("qty"))
            except (TypeError,ValueError):raise ValueError("Tovar miqdori noto‘g‘ri.")
            if pack not in (1,3,5) or qty<=0 or qty>100000:raise ValueError("Tovar miqdori noto‘g‘ri.")
            required[pack]=required.get(pack,0)+qty;clean.append((pack,qty))
        for pack,qty in required.items():
            if core.agent_stock(db,agent,pack)<qty:
                raise ValueError(f"{core.product_name(pack)} agent qoldig‘ida yetarli emas.")
        for idx,(pack,qty) in enumerate(clean):
            core.record(db,agent,agent,cid,'delivery',pack,qty,0,'Mini App',
                        _source(agent,request_id,idx+1),currency='USD')
        cs.add_visit(db,agent,cid,'active','Tovar berildi: '+', '.join(
            f"{core.product_name(pack)} {qty} dona" for pack,qty in clean))
        return {"ok":True,"message":"Tovar topshirildi va mijoz qarzi yangilandi."}
    if action=="payment":
        ok,msg=_live_ready(db,agent,now=now)
        if not ok:raise ValueError(msg)
        amount=core.money(payload.get("amount"))
        core.record(db,agent,agent,cid,'payment',0,0,amount,'Mini App',source,currency='USD')
        return {"ok":True,"message":f"{_usd(amount):.2f} USD to‘lov saqlandi.",
                "_notify":{"kind":"payment","client":cid,"amount":amount}}
    if action=="return":
        ok,msg=_live_ready(db,agent,now=now)
        if not ok:raise ValueError(msg)
        items=payload.get("items")
        if not isinstance(items,list) or not items or len(items)>MAX_WRITE_ITEMS:
            raise ValueError("Qaytariladigan tovarni kiriting.")
        clean=[]
        for item in items:
            if not isinstance(item,dict):raise ValueError("Qaytarish noto‘g‘ri.")
            try:pack=int(item.get("pack"));qty=int(item.get("qty"))
            except (TypeError,ValueError):raise ValueError("Qaytarish miqdori noto‘g‘ri.")
            if pack not in (1,3,5) or qty<=0 or qty>100000:
                raise ValueError("Qaytarish miqdori noto‘g‘ri.")
            clean.append((pack,qty))
        for pack,qty in clean:
            if core.client_stock_total(db,cid,pack)<qty:
                raise ValueError(f"{core.product_name(pack)} mijozda yetarli emas.")
        for idx,(pack,qty) in enumerate(clean):
            core.record(db,agent,agent,cid,'return',pack,qty,0,'Mini App',
                        _source(agent,request_id,idx+1),currency='USD')
        cs.add_visit(db,agent,cid,'active','Tovar qaytarildi: '+', '.join(
            f"{core.product_name(pack)} {qty} dona" for pack,qty in clean))
        return {"ok":True,"message":"Tovar qaytarildi va qarz yangilandi."}
    raise ValueError("Amal noto‘g‘ri.")
