"""Authenticated, read-only manager dashboard over the Agent Bot's existing database.

No state-changing APIs, independent shadow ledgers, or public dashboard tokens.
Telegram initData is validated with the bot token on every request.
"""
import hashlib
import hmac
import json
import re
import time
import math
from datetime import datetime, timedelta
from urllib.parse import parse_qsl
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Tashkent")
MAX_AUTH_AGE = 3600
MAX_CLIENTS = 5000


def verify_init_data(raw, token, now=None):
    """Return Telegram's verified user id, or raise ValueError.

    This works with signed initData from an inline-keyboard Web App button,
    not the unsigned/empty data of reply-keyboard Web Apps.
    """
    if not isinstance(raw, str) or not raw or len(raw) > 8192 or not token:
        raise ValueError("Telegram orqali rahbar panelini qayta oching.")
    try:
        entries = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
        data = dict(entries)
        if len(entries) != len(data) or len(entries) > 32:
            raise ValueError("Telegram avtorizatsiyasi noto‘g‘ri.")
        digest = data.pop("hash")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise ValueError("Telegram avtorizatsiyasi noto‘g‘ri.")
        key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
        # Current Telegram clients may attach an independent Ed25519
        # 'signature'. Validate the bot HMAC with the signature excluded,
        # and accept the legacy signed-all-fields variant as well.
        variants = [data]
        if "signature" in data:
            variants.append({k:v for k,v in data.items() if k!="signature"})
        hashes = []
        for fields in variants:
            check = "\n".join(k + "=" + v for k, v in sorted(fields.items()))
            hashes.append(hmac.new(key, check.encode("utf-8"), hashlib.sha256).hexdigest())
        if not any(hmac.compare_digest(value,digest.lower()) for value in hashes):
            raise ValueError("Telegram imzosi tasdiqlanmadi.")
        issued = int(data["auth_date"])
        now = int(time.time() if now is None else now)
        if issued > now + 60 or issued < now - MAX_AUTH_AGE:
            raise ValueError("Sessiya muddati tugagan. Botdan qayta oching.")
        user = json.loads(data["user"])
        uid = user.get("id")
        if isinstance(uid, bool) or not isinstance(uid, int) or uid <= 0:
            raise ValueError("Telegram akkaunti aniqlanmadi.")
        return uid
    except (KeyError, TypeError, AttributeError, OverflowError, json.JSONDecodeError, UnicodeError) as e:
        raise ValueError("Telegram avtorizatsiyasi noto‘g‘ri.") from e


def _midnight(now):
    return int(datetime.fromtimestamp(now, TZ).replace(
        hour=0, minute=0, second=0, microsecond=0).timestamp())


def _usd(cents):
    return round(int(cents or 0) / 100, 2)


def _float_coord(lat, lon):
    try:
        a, b = float(lat), float(lon)
        return (a, b) if -90 <= a <= 90 and -180 <= b <= 180 else (None, None)
    except (ValueError, TypeError):
        return None, None


def _cash_transactions(db, since):
    return db.execute("""SELECT h.id,h.agent,h.amount_usd,h.amount,h.status,
               h.ts,h.accepted_ts,u.name AS agent_name
        FROM handovers h LEFT JOIN users u ON u.id=h.agent
        WHERE (h.ts>=? OR h.status='pending') ORDER BY h.ts DESC,h.id DESC LIMIT 800""",
        (since,)).fetchall()



def _route_km(a, b):
    try:
        lat1,lon1,lat2,lon2=map(float,(a["lat"],a["lon"],b["lat"],b["lon"]))
    except (TypeError,ValueError,KeyError):
        return 0.0
    if not (-90<=lat1<=90 and -90<=lat2<=90 and -180<=lon1<=180 and -180<=lon2<=180):
        return 0.0
    p1,p2=math.radians(lat1),math.radians(lat2)
    dp=math.radians(lat2-lat1);dl=math.radians(lon2-lon1)
    h=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 6371.0088*2*math.asin(min(1.0,math.sqrt(h)))


def _period_report(db, start, end, staff, clients, recent_visits, now):
    """Read-only KPI snapshot for a half-open [start,end) manager period."""
    start,end=int(start),int(end)
    by_agent={int(u["id"]):{
        "agentId":int(u["id"]),"agent":u["name"] or str(u["id"]),
        "visits":0,"newClients":0,"deliveredUsd":0.0,"paymentsUsd":0.0,
        "returnsUsd":0.0,"deliveredQty":0,"soldQty":0,
        "workSeconds":0,"distanceKm":0.0,
        "clients":0,"overdueClients":0,
    } for u in staff}
    for c in clients:
        aid=int(c["agentId"])
        if aid in by_agent:
            by_agent[aid]["clients"]+=1
            if c["age"]=="red":by_agent[aid]["overdueClients"]+=1
    for actor,ts in recent_visits:
        if start<=ts<end and actor in by_agent:
            by_agent[actor]["visits"]+=1

    event_rows=db.execute("""SELECT agent,kind,
        COALESCE(SUM(amount_usd),0) AS amount_usd,
        COALESCE(SUM(qty),0) AS qty
        FROM events WHERE ts>=? AND ts<? AND kind IN ('delivery','payment','return','sold')
        GROUP BY agent,kind""",(start,end)).fetchall()
    delivered=payments=returns=0
    delivered_qty=sold_qty=0
    for row in event_rows:
        aid=int(row["agent"]);kind=row["kind"]
        cents=int(row["amount_usd"] or 0);qty=int(row["qty"] or 0)
        target=by_agent.get(aid)
        if kind=="delivery":
            delivered+=cents;delivered_qty+=qty
            if target:target["deliveredUsd"]=_usd(cents);target["deliveredQty"]=qty
        elif kind=="payment":
            payments+=cents
            if target:target["paymentsUsd"]=_usd(cents)
        elif kind=="return":
            returns+=cents
            if target:target["returnsUsd"]=_usd(cents)
        elif kind=="sold":
            sold_qty+=qty
            if target:target["soldQty"]=qty

    product_names={int(r["pack"]):r["name"] for r in db.execute(
        "SELECT pack,name FROM products ORDER BY pack").fetchall()}
    product_rows=db.execute("""SELECT pack,kind,
        COALESCE(SUM(qty),0) AS qty,
        COALESCE(SUM(amount_usd),0) AS amount_usd
        FROM events
        WHERE ts>=? AND ts<? AND pack>0
          AND kind IN ('delivery','sold','return')
        GROUP BY pack,kind ORDER BY pack,kind""",(start,end)).fetchall()
    products={}
    for row in product_rows:
        pack=int(row["pack"]);kind=row["kind"];qty=int(row["qty"] or 0);cents=int(row["amount_usd"] or 0)
        item=products.setdefault(pack,{
            "pack":pack,"name":product_names.get(pack) or f"{pack} kg",
            "deliveredQty":0,"deliveredUsd":0.0,
            "soldQty":0,"returnedQty":0,"returnedUsd":0.0,
            "sharePct":0.0,
        })
        if kind=="delivery":
            item["deliveredQty"]=qty;item["deliveredUsd"]=_usd(cents)
        elif kind=="sold":
            item["soldQty"]=qty
        elif kind=="return":
            item["returnedQty"]=qty;item["returnedUsd"]=_usd(cents)
    product_list=list(products.values())
    product_total=sum(float(p["deliveredUsd"] or 0) for p in product_list)
    for p in product_list:
        p["sharePct"]=round((float(p["deliveredUsd"] or 0)/product_total*100) if product_total else 0,1)
    product_list.sort(key=lambda p:(p["deliveredUsd"],p["deliveredQty"],-p["pack"]),reverse=True)
    top_product=product_list[0]["name"] if product_list and product_list[0]["deliveredUsd"]>0 else None

    new_rows=db.execute("""SELECT agent,COUNT(*) AS n FROM clients
        WHERE created_ts>=? AND created_ts<? GROUP BY agent""",(start,end)).fetchall()
    new_clients=0
    for row in new_rows:
        n=int(row["n"] or 0);new_clients+=n
        if int(row["agent"]) in by_agent:by_agent[int(row["agent"])]["newClients"]=n

    shifts=db.execute("""SELECT id,agent,start,"end" AS end_ts FROM shifts
        WHERE start<? AND COALESCE("end",?)>? ORDER BY agent,start,id""",
        (end,now,start)).fetchall()
    shift_agent={}
    work_seconds=0
    for sh in shifts:
        aid=int(sh["agent"]);sid=int(sh["id"]);shift_agent[sid]=aid
        left=max(start,int(sh["start"] or start))
        right=min(end,int(sh["end_ts"] or now),now)
        seconds=max(0,right-left)
        work_seconds+=seconds
        if aid in by_agent:by_agent[aid]["workSeconds"]+=seconds

    point_rows=db.execute("""SELECT p.shift,p.ts,p.lat,p.lon
        FROM points p JOIN shifts s ON s.id=p.shift
        WHERE p.ts>=? AND p.ts<? AND s.start<?
        ORDER BY p.shift,p.ts,p.id""",(start,end,end)).fetchall()
    prev_by_shift={};distance_km=0.0
    for p in point_rows:
        sid=int(p["shift"]);aid=shift_agent.get(sid)
        previous=prev_by_shift.get(sid)
        if previous is not None:
            km=_route_km(previous,p)
            # Ignore impossible GPS jumps. This is a field-sales route, not air travel.
            if 0<=km<=25:
                distance_km+=km
                if aid in by_agent:by_agent[aid]["distanceKm"]+=km
        prev_by_shift[sid]=p

    accepted=int(db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM handovers
        WHERE status='accepted' AND COALESCE(accepted_ts,ts)>=?
          AND COALESCE(accepted_ts,ts)<?""",(start,end)).fetchone()[0] or 0)
    expenses=int(db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM cashier_expenses
        WHERE ts>=? AND ts<?""",(start,end)).fetchone()[0] or 0)
    visits=sum(1 for _,ts in recent_visits if start<=ts<end)
    agents=list(by_agent.values())
    for a in agents:a["distanceKm"]=round(a["distanceKm"],2)
    agents.sort(key=lambda a:(a["deliveredUsd"],a["paymentsUsd"],a["visits"]),reverse=True)
    return {
        "start":start,"end":end,"visits":visits,"newClients":new_clients,
        "deliveredUsd":_usd(delivered),"paymentsUsd":_usd(payments),
        "returnsUsd":_usd(returns),"deliveredQty":delivered_qty,"soldQty":sold_qty,
        "acceptedCashUsd":_usd(accepted),"cashierExpensesUsd":_usd(expenses),
        "workSeconds":work_seconds,"distanceKm":round(distance_km,2),
        "agents":agents,"products":product_list,"topProduct":top_product,
    }


def dashboard(db, now=None):
    """One consistent read snapshot of the real agentbot schema.

    Times are Unix timestamps; monetary values in USD are converted from the
    existing integer-cent ledger. Legacy UZS is never converted to USD.
    """
    now = int(time.time() if now is None else now)
    today = _midnight(now)
    since = today - 29 * 86400
    week = today - 6 * 86400
    staff = db.execute("SELECT id,name FROM users WHERE role='agent' ORDER BY name,id").fetchall()
    open_shifts = db.execute("""SELECT s.id,s.agent,s.start,s.live_id
       FROM shifts s WHERE s.end IS NULL ORDER BY s.start DESC,s.id DESC""").fetchall()
    shifts = {}
    for sh in open_shifts:
        shifts.setdefault(int(sh["agent"]), sh)
    last_points = db.execute("""SELECT p.shift,p.lat,p.lon,p.ts,p.accuracy
       FROM points p JOIN shifts s ON s.id=p.shift
       WHERE s.end IS NULL
         AND p.id=(SELECT MAX(p2.id) FROM points p2 WHERE p2.shift=p.shift)""").fetchall()
    points = {int(p["shift"]): p for p in last_points}
    # Last known GPS is also useful after a shift closes, but it must never be
    # presented as live. Keep it separately and mark the location source.
    historical_points = db.execute("""SELECT s.agent,p.lat,p.lon,p.ts,p.accuracy,p.id
       FROM points p JOIN shifts s ON s.id=p.shift
       WHERE p.id=(SELECT p2.id FROM points p2
          JOIN shifts s2 ON s2.id=p2.shift
          WHERE s2.agent=s.agent ORDER BY p2.ts DESC,p2.id DESC LIMIT 1)
       ORDER BY s.agent""").fetchall()
    last_by_agent = {int(p["agent"]): p for p in historical_points}
    visit_rows = db.execute("""SELECT v.actor,v.ts FROM client_visits v
       WHERE v.ts>=? AND v.ts<=?""", (since, now)).fetchall()
    legacy_visits = db.execute("""SELECT agent,ts FROM events
       WHERE kind='visit' AND ts>=? AND ts<=?""", (since, now)).fetchall()
    recent_visits = [(int(v["actor"]), int(v["ts"])) for v in visit_rows] + [
        (int(v["agent"]), int(v["ts"])) for v in legacy_visits]
    visits_today = {}
    for actor, ts in recent_visits:
        if ts >= today:
            visits_today[actor] = visits_today.get(actor, 0) + 1
    all_clients = db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    rows = db.execute("""SELECT c.id,c.agent,c.name,c.shop_name,c.phone,c.address,
         c.lat,c.lon,c.photo,c.comment,c.payment_due,c.created_ts,c.map_only,
         u.name AS agent_name
         FROM clients c LEFT JOIN users u ON u.id=c.agent
         ORDER BY c.id DESC LIMIT ?""",(MAX_CLIENTS,)).fetchall()
    latest = db.execute("""SELECT v.client,v.status,v.followup,v.ts,v.note
        FROM client_visits v WHERE v.id=(SELECT MAX(v2.id)
             FROM client_visits v2 WHERE v2.client=v.client)""").fetchall()
    latest_by_client = {int(v["client"]): v for v in latest}
    contacts = db.execute("""SELECT client,MAX(ts) AS ts FROM events
        WHERE client IS NOT NULL AND kind IN ('visit','delivery','payment','return')
        GROUP BY client""").fetchall()
    contacts_by_client = {int(e["client"]):int(e["ts"]) for e in contacts if e["ts"] is not None}
    balances = db.execute("""SELECT client,
        COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd
                          WHEN kind IN ('payment','return') THEN -amount_usd
                          ELSE 0 END),0) AS debt
        FROM events WHERE client IS NOT NULL GROUP BY client""").fetchall()
    debt_by_client = {int(e["client"]):int(e["debt"] or 0) for e in balances}
    clients = []
    red_count = 0
    for c in rows:
        cid = int(c["id"])
        v = latest_by_client.get(cid)
        last = max(int(c["created_ts"] or 0),
                   int(v["ts"] or 0) if v else 0,
                   contacts_by_client.get(cid, 0))
        days = max(0, (now-last)//86400) if last else None
        followup = str(v["followup"] or "") if v else ""
        planned = False
        if followup:
            try:
                planned = datetime.fromisoformat(followup).date() > datetime.fromtimestamp(now,TZ).date()
            except ValueError:
                planned = False
        age = ("scheduled" if planned else "unknown" if days is None else
               "red" if days >= 5 else "yellow" if days >= 3 else "fresh")
        if age == "red":
            red_count += 1
        status = (v["status"] if v else
                  "interested" if c["map_only"] else "active")
        lat, lon = _float_coord(c["lat"], c["lon"])
        clients.append({
            "id":cid,"name":c["shop_name"] or c["name"] or "Mijoz",
            "person":c["name"] or "", "address":c["address"] or "",
            "phone":c["phone"] or "", "agent":c["agent_name"] or str(c["agent"]),
            "agentId":int(c["agent"]),"lat":lat,"lon":lon,
            "status":status,"age":age,"days":days,"lastTs":last or None,
            "followup":followup or None,"note":(v["note"] if v else c["comment"]) or "",
            "createdTs":int(c["created_ts"] or 0) or None,"hasPhoto":bool(c["photo"]),
            "debtUsd":_usd(debt_by_client.get(cid,0))
        })
    agents = []
    for u in staff:
        uid=int(u["id"]);shift=shifts.get(uid)
        live_point=points.get(int(shift["id"])) if shift else None
        p=live_point or last_by_agent.get(uid)
        lat,lon=_float_coord(p["lat"],p["lon"]) if p else (None,None)
        ts=int(p["ts"]) if p else None
        status = ("offline" if not shift else
                  "active" if live_point is not None and ts is not None and now-ts<=300 else "late")
        location_source=("live" if shift and live_point is not None else
                         "last" if p is not None else "none")
        agents.append({
            "id":uid,"name":u["name"] or str(uid),
            "status":status,"shiftOpen":bool(shift),
            "shiftStart":int(shift["start"]) if shift else None,
            "lastGpsTs":ts,"lat":lat,"lon":lon,
            "locationSource":location_source,
            "done":visits_today.get(uid,0),
            "late":sum(1 for c in clients if c["agentId"]==uid and c["age"]=="red"),
            "clients":sum(1 for c in clients if c["agentId"]==uid)
        })
    transactions = []
    for h in _cash_transactions(db,since):
        transactions.append({
            "id":int(h["id"]),"agent":h["agent_name"] or str(h["agent"]),
            "agentId":int(h["agent"]),"amountUsd":_usd(h["amount_usd"]),
            "amountUzs":_usd(h["amount"]),"state":h["status"],
            "ts":int(h["ts"] or 0),"acceptedTs":int(h["accepted_ts"] or 0) or None
        })
    # Totals must cover the whole day, independent of the limited activity list.
    cash_total = db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM handovers
        WHERE status='accepted' AND COALESCE(accepted_ts,ts)>=?
        AND COALESCE(accepted_ts,ts)<=?""",(today,now)).fetchone()[0]
    pending_total = db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM handovers
        WHERE status='pending'""").fetchone()[0]
    new_today = db.execute("""SELECT COUNT(*) FROM clients WHERE created_ts>=?
        AND created_ts<=?""",(today,now)).fetchone()[0]
    report_today=_period_report(db,today,now+1,staff,clients,recent_visits,now)
    report_week=_period_report(db,week,now+1,staff,clients,recent_visits,now)
    report_month=_period_report(db,since,now+1,staff,clients,recent_visits,now)
    series=[]
    for k in range(6,-1,-1):
        day=today-k*86400
        next_day=min(day+86400,now+1)
        daily=_period_report(db,day,next_day,staff,clients,recent_visits,now)
        series.append({"day":datetime.fromtimestamp(day,TZ).strftime("%d.%m"),
                       "visits":daily["visits"],"deliveredUsd":daily["deliveredUsd"],
                       "paymentsUsd":daily["paymentsUsd"]})
    total_debt=sum(int(v or 0) for v in debt_by_client.values())
    return {
        "generatedTs":now,"todayStart":today,"timezone":"Asia/Tashkent","readOnly":True,
        "clientCount":int(all_clients),"clientsTruncated":int(all_clients)>MAX_CLIENTS,
        "agents":agents,"clients":clients,"transactions":transactions,
        "summary":{"agentCount":len(agents),"workingAgents":sum(a["shiftOpen"] for a in agents),
                   "visitsToday":sum(visits_today.values()),"newClientsToday":int(new_today),
                   "overdueClients":red_count,"acceptedTodayUsd":_usd(cash_total),
                   "pendingUsd":_usd(pending_total),"debtUsd":_usd(total_debt)},
        "reports":{"today":report_today,"week":report_week,"month":report_month,
                   "series":series}
    }



def client_detail(db, client_id, limit=120):
    """Full manager view of one customer without changing business ledgers."""
    try:
        client_id=int(client_id)
    except (TypeError,ValueError):
        raise ValueError("Mijoz ID noto‘g‘ri.")
    if client_id<=0:
        raise ValueError("Mijoz ID noto‘g‘ri.")
    c=db.execute("""SELECT c.*,u.name AS agent_name
        FROM clients c LEFT JOIN users u ON u.id=c.agent WHERE c.id=?""",(client_id,)).fetchone()
    if not c:
        raise ValueError("Mijoz topilmadi.")
    debt=int(db.execute("""SELECT COALESCE(SUM(CASE
        WHEN kind='delivery' THEN amount_usd
        WHEN kind IN ('payment','return') THEN -amount_usd ELSE 0 END),0)
        FROM events WHERE client=?""",(client_id,)).fetchone()[0] or 0)
    stock_rows=db.execute("""SELECT e.pack,
        COALESCE(SUM(CASE WHEN e.kind='delivery' THEN e.qty
                          WHEN e.kind IN ('sold','return') THEN -e.qty ELSE 0 END),0) AS qty,
        COALESCE(p.name,CAST(e.pack AS TEXT)) AS product_name
        FROM events e LEFT JOIN products p ON p.pack=e.pack
        WHERE e.client=? AND e.pack>0 AND e.kind IN ('delivery','sold','return')
        GROUP BY e.pack,p.name ORDER BY e.pack""",(client_id,)).fetchall()
    stocks=[{"pack":int(r["pack"]),"name":r["product_name"] or str(r["pack"]),
             "qty":int(r["qty"] or 0)} for r in stock_rows]
    rows=db.execute("""SELECT e.id,e.kind,e.pack,e.qty,e.amount,e.amount_usd,e.note,e.ts,
             COALESCE(u.name,CAST(e.actor AS TEXT),CAST(e.agent AS TEXT)) AS actor_name,
             COALESCE(p.name,CAST(e.pack AS TEXT)) AS product_name
        FROM events e
        LEFT JOIN users u ON u.id=e.actor
        LEFT JOIN products p ON p.pack=e.pack
        WHERE e.client=? AND e.kind IN ('delivery','payment','sold','return','order','visit')
        ORDER BY e.ts DESC,e.id DESC LIMIT ?""",(client_id,max(1,min(int(limit),500)))).fetchall()
    events=[{
        "id":int(r["id"]),"kind":r["kind"],"pack":int(r["pack"] or 0),
        "product":r["product_name"] if r["pack"] else "",
        "qty":int(r["qty"] or 0),"amountUzs":int(r["amount"] or 0),
        "amountUsd":_usd(r["amount_usd"]),"note":r["note"] or "",
        "ts":int(r["ts"] or 0),"actor":r["actor_name"] or "—"
    } for r in rows]
    visits=db.execute("""SELECT v.id,v.actor,v.status,v.note,v.followup,v.ts,
               COALESCE(u.name,CAST(v.actor AS TEXT)) AS actor_name
        FROM client_visits v LEFT JOIN users u ON u.id=v.actor
        WHERE v.client=? ORDER BY v.ts DESC,v.id DESC LIMIT 80""",(client_id,)).fetchall()
    visit_rows=[{
        "id":int(r["id"]),"status":r["status"] or "","note":r["note"] or "",
        "followup":r["followup"] or "","ts":int(r["ts"] or 0),
        "actor":r["actor_name"] or "—"
    } for r in visits]
    edits=db.execute("""SELECT ce.id,ce.field,ce.old_value,ce.new_value,ce.ts,
               COALESCE(u.name,CAST(ce.actor AS TEXT)) AS actor_name
        FROM client_edits ce LEFT JOIN users u ON u.id=ce.actor
        WHERE ce.client=? ORDER BY ce.ts DESC,ce.id DESC LIMIT 50""",(client_id,)).fetchall()
    edit_rows=[{
        "id":int(r["id"]),"field":r["field"],"old":r["old_value"],"new":r["new_value"],
        "ts":int(r["ts"] or 0),"actor":r["actor_name"] or "—"
    } for r in edits]
    totals=db.execute("""SELECT
        COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='payment' THEN amount_usd ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='return' THEN amount_usd ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='delivery' THEN qty ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='sold' THEN qty ELSE 0 END),0)
        FROM events WHERE client=?""",(client_id,)).fetchone()
    lat,lon=_float_coord(c["lat"],c["lon"])
    return {
        "id":client_id,"name":c["shop_name"] or c["name"] or "Mijoz",
        "person":c["name"] or "","shopName":c["shop_name"] or "",
        "phone":c["phone"] or "","address":c["address"] or "",
        "comment":c["comment"] or "","paymentDue":c["payment_due"] or "",
        "agentId":int(c["agent"]),"agent":c["agent_name"] or str(c["agent"]),
        "createdTs":int(c["created_ts"] or 0),"mapOnly":bool(c["map_only"]),
        "lat":lat,"lon":lon,"photo":c["photo"] or "",
        "debtUsd":_usd(debt),"stocks":stocks,"events":events,"visits":visit_rows,"edits":edit_rows,
        "totals":{"deliveredUsd":_usd(totals[0]),"paidUsd":_usd(totals[1]),
                  "returnedUsd":_usd(totals[2]),"deliveredQty":int(totals[3] or 0),
                  "soldQty":int(totals[4] or 0)}
    }


def client_edit_preview(db, client_id, values):
    """Validate manager-editable profile fields and return old/new values for confirmation."""
    try:
        client_id=int(client_id)
    except (TypeError,ValueError):
        raise ValueError("Mijoz ID noto‘g‘ri.")
    if not isinstance(values,dict) or not values:
        raise ValueError("O‘zgartirishlar kiritilmagan.")
    allowed={"name","shop_name","phone","address","comment","payment_due"}
    if any(k not in allowed for k in values):
        raise ValueError("Bu maydon Rahbar App orqali o‘zgartirilmaydi.")
    current=db.execute("SELECT * FROM clients WHERE id=?",(client_id,)).fetchone()
    if not current:
        raise ValueError("Mijoz topilmadi.")
    clean={}
    for key,value in values.items():
        if value is None:
            value=""
        if not isinstance(value,str):
            raise ValueError("Matn maydoni noto‘g‘ri.")
        value=value.strip()
        if key=="phone":
            if len(value)>40:
                raise ValueError("Telefon juda uzun.")
        elif len(value)>500:
            raise ValueError("Matn juda uzun.")
        if str(current[key] or "")!=value:
            clean[key]=value
    if not clean:
        raise ValueError("Ma’lumot o‘zgarmagan.")
    return {"clientId":client_id,
            "changes":[{"field":k,"old":str(current[k] or ""),"new":v} for k,v in clean.items()],
            "values":clean}


def route(db, agent_id, now=None):
    """One agent's most recent shift trajectory, never a guessed position."""
    try:
        agent_id=int(agent_id)
    except (ValueError,TypeError):
        raise ValueError("Agent ID noto‘g‘ri.")
    agent=db.execute("SELECT id,name FROM users WHERE id=? AND role='agent'",
                     (agent_id,)).fetchone()
    if not agent:
        raise ValueError("Agent topilmadi.")
    shift=db.execute("""SELECT id,start,"end" AS end_ts FROM shifts WHERE agent=?
        ORDER BY id DESC LIMIT 1""",(agent_id,)).fetchone()
    if not shift:
        return {"agentId":agent_id,"agent":agent["name"],"points":[],
                "start":None,"end":None}
    pts=db.execute("""SELECT lat,lon,ts FROM points WHERE shift=?
        ORDER BY ts DESC,id DESC LIMIT 1500""",(shift["id"],)).fetchall()
    coords=[]
    for p in reversed(pts):
        lat,lon=_float_coord(p["lat"],p["lon"])
        if lat is not None:
            coords.append({"lat":lat,"lon":lon,"ts":int(p["ts"])})
    return {"agentId":agent_id,"agent":agent["name"],
            "start":int(shift["start"]),"end":int(shift["end_ts"]) if shift["end_ts"] else None,
            "points":coords}
