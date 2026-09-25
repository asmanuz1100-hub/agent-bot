"""Agent Mini App: signed Telegram, role-limited reads and transactional bot-ledger writes."""
import hashlib
import json
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import core
import customer_status as cs
from manager_api import verify_init_data

TZ=ZoneInfo("Asia/Tashkent")
WRITE_ACTIONS={"client","visit","delivery","return","payment","handover","shift_start","shift_end"}
MAX_CLIENTS=5000


def authorize(db,raw,token):
    uid=verify_init_data(raw,token)
    row=db.execute("SELECT id,name,role FROM users WHERE id=?",(uid,)).fetchone()
    if not row or row["role"]!="agent":
        raise PermissionError("Mini App'ga faqat faol agent kirishi mumkin.")
    return uid,row["name"] or str(uid)


def _num(v):
    return int(v or 0)


def _usd(v):
    return _num(v)/100


def _coord(lat,lon,required=False):
    try:
        lat=float(lat);lon=float(lon)
        if not -90<=lat<=90 or not -180<=lon<=180:raise ValueError()
        return lat,lon
    except (TypeError,ValueError):
        if required:raise ValueError("Do‘kon lokatsiyasini xaritada belgilang.")
        return None,None


def _text(value,label,limit,required=True):
    v=str(value or "").strip()
    if (required and not v) or len(v)>limit:
        raise ValueError(label+" ma’lumoti noto‘g‘ri.")
    return v


def _client_exists(db,cid):
    try:cid=int(cid)
    except (TypeError,ValueError):raise ValueError("Mijozni tanlang.")
    if cid<=0 or not db.execute("SELECT id FROM clients WHERE id=?",(cid,)).fetchone():
        raise ValueError("Mijoz topilmadi.")
    return cid


def snapshot(db,uid,name,now=None):
    now=int(time.time() if now is None else now)
    today=int(datetime.fromtimestamp(now,TZ).replace(hour=0,minute=0,second=0,microsecond=0).timestamp())
    shift=db.execute('SELECT id,start,live_id FROM shifts WHERE agent=? AND "end" IS NULL ORDER BY id DESC LIMIT 1',(uid,)).fetchone()
    p=db.execute("SELECT lat,lon,ts FROM points WHERE shift=? ORDER BY id DESC LIMIT 1",(shift["id"],)).fetchone() if shift else None
    lat,lon=_coord(p["lat"],p["lon"]) if p else (None,None)
    total=_num(db.execute("SELECT COUNT(*) FROM clients").fetchone()[0])
    rows=db.execute("""SELECT c.id,c.agent,c.name,c.shop_name,c.phone,c.address,c.lat,c.lon,
        c.comment,c.payment_due,c.created_ts,c.map_only,u.name AS agent_name
        FROM clients c LEFT JOIN users u ON u.id=c.agent ORDER BY c.id DESC LIMIT ?""",(MAX_CLIENTS,)).fetchall()
    visitrows=db.execute("""SELECT client,status,note,followup,ts FROM client_visits v
       WHERE v.id=(SELECT MAX(v2.id) FROM client_visits v2 WHERE v2.client=v.client)""").fetchall()
    visits={_num(v["client"]):v for v in visitrows}
    contactrows=db.execute("""SELECT client,MAX(ts) AS last_ts FROM events
       WHERE client IS NOT NULL AND kind IN ('visit','delivery','payment','return')
       GROUP BY client""").fetchall()
    contacts={_num(v["client"]):_num(v["last_ts"]) for v in contactrows}
    ledgers=db.execute("""SELECT client,
      COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd
         WHEN kind IN ('payment','return') THEN -amount_usd ELSE 0 END),0) AS debt,
      COALESCE(SUM(CASE WHEN kind='delivery' AND pack=1 THEN qty WHEN kind IN ('return','sold') AND pack=1 THEN -qty ELSE 0 END),0) AS q1,
      COALESCE(SUM(CASE WHEN kind='delivery' AND pack=3 THEN qty WHEN kind IN ('return','sold') AND pack=3 THEN -qty ELSE 0 END),0) AS q3,
      COALESCE(SUM(CASE WHEN kind='delivery' AND pack=5 THEN qty WHEN kind IN ('return','sold') AND pack=5 THEN -qty ELSE 0 END),0) AS q5
      FROM events WHERE client IS NOT NULL GROUP BY client""").fetchall()
    ledger={_num(v["client"]):v for v in ledgers}
    result=[]
    for c in rows:
        cid=_num(c["id"]);v=visits.get(cid)
        last=max(_num(c["created_ts"]),_num(v["ts"]) if v else 0,contacts.get(cid,0))
        days=max(0,(now-last)//86400) if last else None
        followup=v["followup"] if v else None
        planned=False
        if followup:
            try:planned=datetime.fromisoformat(str(followup)).date()>datetime.fromtimestamp(now,TZ).date()
            except ValueError:pass
        age="scheduled" if planned else "unknown" if days is None else "red" if days>=5 else "yellow" if days>=3 else "fresh"
        clat,clon=_coord(c["lat"],c["lon"])
        stock=ledger.get(cid)
        result.append({"id":cid,"name":c["shop_name"] or c["name"] or "Mijoz",
         "person":c["name"] or "","phone":c["phone"] or "","address":c["address"] or "",
         "agent":c["agent_name"] or str(c["agent"]),"agentId":_num(c["agent"]),
         "lat":clat,"lon":clon,"comment":c["comment"] or "",
         "status":v["status"] if v else ("interested" if c["map_only"] else "active"),
         "note":v["note"] if v else c["comment"] or "","age":age,"days":days,"lastTs":last or None,
         "followup":followup,"debtUsd":_usd(stock["debt"] if stock else 0),
         "stock":{str(pack):_num(stock["q"+str(pack)]) if stock else 0 for pack in (1,3,5)}})
    prows=db.execute("SELECT pack,name,price FROM products WHERE pack IN (1,3,5) ORDER BY pack").fetchall()
    products=[{"pack":_num(p["pack"]),"name":p["name"],"priceUsd":_usd(p["price"]),
               "stock":core.agent_stock(db,uid,_num(p["pack"]))} for p in prows]
    recent=db.execute("""SELECT e.id,e.client,e.kind,e.pack,e.qty,e.amount_usd,e.ts,
       c.shop_name,c.name AS client_name FROM events e LEFT JOIN clients c ON c.id=e.client
       WHERE e.agent=? AND e.ts>=? ORDER BY e.ts DESC,e.id DESC LIMIT 250""",(uid,today-30*86400)).fetchall()
    events=[{"id":_num(e["id"]),"client":_num(e["client"]),"shop":e["shop_name"] or e["client_name"] or "",
             "kind":e["kind"],"pack":_num(e["pack"]),"qty":_num(e["qty"]),
             "amountUsd":_usd(e["amount_usd"]),"ts":_num(e["ts"])} for e in recent]
    handrows=db.execute("""SELECT id,amount_usd,status,ts,accepted_ts FROM handovers
      WHERE agent=? ORDER BY id DESC LIMIT 80""",(uid,)).fetchall()
    handovers=[{"id":_num(h["id"]),"amountUsd":_usd(h["amount_usd"]),
                "status":h["status"],"ts":_num(h["ts"]),"acceptedTs":h["accepted_ts"]} for h in handrows]
    collected=_num(db.execute("SELECT COALESCE(SUM(amount_usd),0) FROM events WHERE agent=? AND kind='payment'",(uid,)).fetchone()[0])
    accepted=_num(db.execute("SELECT COALESCE(SUM(amount_usd),0) FROM handovers WHERE agent=? AND status='accepted'",(uid,)).fetchone()[0])
    pending=_num(db.execute("SELECT COALESCE(SUM(amount_usd),0) FROM handovers WHERE agent=? AND status='pending'",(uid,)).fetchone()[0])
    visit_count=_num(db.execute("SELECT COUNT(*) FROM client_visits WHERE actor=? AND ts>=?",(uid,today)).fetchone()[0])
    legacy=_num(db.execute("SELECT COUNT(*) FROM events WHERE agent=? AND kind='visit' AND ts>=?",(uid,today)).fetchone()[0])
    new_clients=_num(db.execute("SELECT COUNT(*) FROM clients WHERE agent=? AND created_ts>=?",(uid,today)).fetchone()[0])
    period={}
    for label,begin in (("day",today),("week",today-6*86400),("month",today-29*86400)):
        v=_num(db.execute("SELECT COUNT(*) FROM client_visits WHERE actor=? AND ts>=?",(uid,begin)).fetchone()[0])
        v+=_num(db.execute("SELECT COUNT(*) FROM events WHERE agent=? AND kind='visit' AND ts>=?",(uid,begin)).fetchone()[0])
        n=_num(db.execute("SELECT COUNT(*) FROM clients WHERE agent=? AND created_ts>=?",(uid,begin)).fetchone()[0])
        cash=_num(db.execute("SELECT COALESCE(SUM(amount_usd),0) FROM events WHERE agent=? AND kind='payment' AND ts>=?",(uid,begin)).fetchone()[0])
        period[label]={"visits":v,"newClients":n,"paymentsUsd":_usd(cash)}
    return {"readOnly":False,"generatedTs":now,"todayStart":today,
      "me":{"id":uid,"name":name,"shiftOpen":bool(shift),
            "shiftStart":_num(shift["start"]) if shift else None,
            "liveAttached":bool(shift and shift["live_id"]),
            "gps":{"lat":lat,"lon":lon,"ts":_num(p["ts"]) if p else None}},
      "clients":result,"clientCount":total,"truncated":total>MAX_CLIENTS,
      "products":products,"events":events,"handovers":handovers,
      "summary":{"visitsToday":visit_count+legacy,"newClientsToday":new_clients,
                 "paymentTodayUsd":period["day"]["paymentsUsd"],
                 "goodsToday":sum(e["qty"] for e in events if e["kind"]=="delivery" and e["ts"]>=today),
                 "cashAvailableUsd":_usd(collected-accepted-pending),
                 "cashOnHandUsd":_usd(collected-accepted)},
      "period":period}


def route(db,uid):
    shift=db.execute('SELECT id,start,"end" FROM shifts WHERE agent=? ORDER BY id DESC LIMIT 1',(uid,)).fetchone()
    if not shift:return {"points":[],"start":None,"end":None}
    pts=db.execute("SELECT lat,lon,ts FROM points WHERE shift=? ORDER BY ts DESC,id DESC LIMIT 1500",(shift["id"],)).fetchall()
    out=[]
    for p in reversed(pts):
        a,b=_coord(p["lat"],p["lon"])
        if a is not None:out.append({"lat":a,"lon":b,"ts":_num(p["ts"])})
    return {"points":out,"start":_num(shift["start"]),
            "end":_num(shift["end"]) if shift["end"] else None}


def _write_once(db,uid,action,data):
    token=_text(data.get("nonce"),"So‘rov identifikatori",90)
    if not re.fullmatch(r"[a-zA-Z0-9_-]{8,90}",token):
        raise ValueError("So‘rov identifikatori noto‘g‘ri.")
    db.execute("""CREATE TABLE IF NOT EXISTS agent_miniapp_requests(
       uid BIGINT NOT NULL, nonce TEXT NOT NULL, action TEXT NOT NULL,
       created_ts BIGINT NOT NULL, PRIMARY KEY(uid,nonce))""")
    # Serialize all agent financial operations and deduplication on one agent row.
    core.lock_agent(db,uid)
    prev=db.execute("SELECT action FROM agent_miniapp_requests WHERE uid=? AND nonce=?",(uid,token)).fetchone()
    if prev:
        if prev["action"]!=action:raise ValueError("So‘rov identifikatori boshqa amal uchun ishlatilgan.")
        return {"ok":True,"duplicate":True}
    result=mutate(db,uid,action,data)
    db.execute("INSERT INTO agent_miniapp_requests(uid,nonce,action,created_ts) VALUES(?,?,?,?)",
               (uid,token,action,int(time.time())))
    return dict({"ok":True},**result)


def mutate(db,uid,action,data):
    if action not in WRITE_ACTIONS:raise ValueError("Bu amal ruxsat etilmagan.")
    now=int(time.time())
    if action=="shift_start":
        if db.execute('SELECT 1 FROM shifts WHERE agent=? AND "end" IS NULL',(uid,)).fetchone():
            raise ValueError("Ish kuni allaqachon boshlangan.")
        db.execute('INSERT INTO shifts(agent,start) VALUES(?,?)',(uid,now))
        return {"message":"Ish kuni boshlandi. Telegram chatidan jonli lokatsiyani qo‘lda ulang."}
    if action=="shift_end":
        sh=db.execute('SELECT id FROM shifts WHERE agent=? AND "end" IS NULL ORDER BY id DESC LIMIT 1',(uid,)).fetchone()
        if not sh:raise ValueError("Ochiq ish kuni yo‘q.")
        db.execute('UPDATE shifts SET "end"=? WHERE id=?',(now,sh["id"]))
        return {"message":"Ish kuni tugadi. Telegram ichida jonli lokatsiya ulashishni ham to‘xtating."}
    if action=="client":
        shop=_text(data.get("shop"),"Do‘kon nomi",90)
        person=_text(data.get("person"),"Mijoz ismi",90)
        phone=_text(data.get("phone"),"Telefon",90)
        from bot import parse_phones
        phones=set(parse_phones(phone))
        for row in db.execute("SELECT phone FROM clients WHERE phone IS NOT NULL").fetchall():
            try:
                if phones & set(parse_phones(row[0])):raise ValueError("Telefon raqami oldin kiritilgan.")
            except ValueError as e:
                if str(e)=="Telefon raqami oldin kiritilgan.":raise
        lat,lon=_coord(data.get("lat"),data.get("lon"),required=True)
        address=_text(data.get("address"),"Manzil",250)
        note=_text(data.get("note"),"Izoh",1000)
        status=_text(data.get("status") or "interested","Holat",20)
        followup=data.get("followup") or None
        cs.normalize(status,followup)
        cur=db.execute("""INSERT INTO clients(agent,name,phone,address,lat,lon,photo,shop_name,
            comment,payment_due,created_ts,map_only)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,1) RETURNING id""",
            (uid,person,phone,address,lat,lon,None,shop,note,None,now))
        cid=int(cur.fetchone()[0])
        cs.add_visit(db,uid,cid,status,note,followup)
        return {"clientId":cid,"message":"Mijoz bazaga qo‘shildi."}
    cid=_client_exists(db,data.get("clientId")) if action in ("visit","delivery","return","payment") else None
    if action=="visit":
        status=_text(data.get("status"),"Tashrif holati",20)
        note=_text(data.get("note"),"Tashrif izohi",1000)
        cs.add_visit(db,uid,cid,status,note,data.get("followup") or None)
        return {"message":"Tashrif saqlandi."}
    if action in ("delivery","return"):
        items=data.get("items")
        if not isinstance(items,list) or not 1<=len(items)<=10:raise ValueError("1–10 ta mahsulot kiriting.")
        parsed=[]
        for item in items:
            if not isinstance(item,dict):raise ValueError("Mahsulot noto‘g‘ri.")
            pack=int(item.get("pack"));qty=core.count(item.get("qty"))
            if pack not in (1,3,5):raise ValueError("Qadoq noto‘g‘ri.")
            parsed.append((pack,qty))
        if action=="delivery":
            need={p:sum(q for p2,q in parsed if p2==p) for p,_ in parsed}
            for p,q in need.items():
                if core.agent_stock(db,uid,p)<q:raise ValueError("Agent omborida tovar yetarli emas.")
        for pack,qty in parsed:
            core.record(db,uid,uid,cid,action,pack,qty,0,currency="USD")
        cs.add_visit(db,uid,cid,"active",
            ("Tovar berildi: " if action=="delivery" else "Tovar qaytarildi: ")+
            ", ".join(str(pack)+" kg × "+str(qty) for pack,qty in parsed))
        return {"message":"Tovar operatsiyasi saqlandi."}
    if action=="payment":
        cents=core.money(data.get("amount"))
        if cents>core.client_debt_usd(db,cid):
            raise ValueError("To‘lov USD qarzdan ko‘p. Kassani tekshiring.")
        core.record(db,uid,uid,cid,"payment",value=cents,currency="USD")
        return {"message":"To‘lov saqlandi."}
    if action=="handover":
        core.handover(db,uid,core.money(data.get("amount")),source=None,currency="USD")
        return {"message":"Pul kassir tasdig‘ini kutmoqda."}
    raise ValueError("Amal mavjud emas.")


def handle(db,uid,action,data):
    if action=="snapshot":return snapshot(db,uid,db.execute("SELECT name FROM users WHERE id=?",(uid,)).fetchone()[0] or str(uid))
    if action=="route":return route(db,uid)
    if action in WRITE_ACTIONS:return _write_once(db,uid,action,data)
    raise ValueError("Amal mavjud emas.")
