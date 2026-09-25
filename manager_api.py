"""Authenticated, read-only manager dashboard over the Agent Bot's existing database.

No state-changing APIs, independent shadow ledgers, or public dashboard tokens.
Telegram initData is validated with the bot token on every request.
"""
import hashlib
import hmac
import json
import re
import time
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
        check = "\n".join(k + "=" + v for k, v in sorted(data.items()))
        expected = hmac.new(key, check.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, digest.lower()):
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
         c.lat,c.lon,c.comment,c.payment_due,c.created_ts,c.map_only,
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
            "debtUsd":_usd(debt_by_client.get(cid,0))
        })
    agents = []
    for u in staff:
        uid=int(u["id"]);shift=shifts.get(uid)
        p=points.get(int(shift["id"])) if shift else None
        lat,lon=_float_coord(p["lat"],p["lon"]) if p else (None,None)
        ts=int(p["ts"]) if p else None
        status = ("offline" if not shift else
                  "active" if ts is not None and now-ts<=300 else "late")
        agents.append({
            "id":uid,"name":u["name"] or str(uid),
            "status":status,"shiftOpen":bool(shift),
            "shiftStart":int(shift["start"]) if shift else None,
            "lastGpsTs":ts,"lat":lat,"lon":lon,
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
    series=[]
    for k in range(6,-1,-1):
        day=today-k*86400
        next_day=day+86400
        series.append({"day":datetime.fromtimestamp(day,TZ).strftime("%d.%m"),
                       "visits":sum(1 for _,ts in recent_visits if day<=ts<next_day)})
    return {
        "generatedTs":now,"timezone":"Asia/Tashkent","readOnly":True,
        "clientCount":int(all_clients),"clientsTruncated":int(all_clients)>MAX_CLIENTS,
        "agents":agents,"clients":clients,"transactions":transactions,
        "summary":{"agentCount":len(agents),"workingAgents":sum(a["shiftOpen"] for a in agents),
                   "visitsToday":sum(visits_today.values()),"newClientsToday":int(new_today),
                   "overdueClients":red_count,"acceptedTodayUsd":_usd(cash_total),
                   "pendingUsd":_usd(pending_total)},
        "reports":{"week":{"visits":sum(v>=week for _,v in recent_visits),
                           "newClients":int(db.execute(
                               "SELECT COUNT(*) FROM clients WHERE created_ts>=?",
                               (week,)).fetchone()[0])},
                   "month":{"visits":len(recent_visits),"newClients":int(db.execute(
                               "SELECT COUNT(*) FROM clients WHERE created_ts>=?",
                               (since,)).fetchone()[0])},
                   "series":series}
    }


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
    shift=db.execute("""SELECT id,start,end FROM shifts WHERE agent=?
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
            "start":int(shift["start"]),"end":int(shift["end"]) if shift["end"] else None,
            "points":coords}
