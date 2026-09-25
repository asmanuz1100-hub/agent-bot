"""Read-only cashier reconciliation view.

Customer payments belong to the agent until a cashier accepts a handover.
Existing handovers have no payment-event foreign key; customer rows shown near
a handover are contextual, NEVER an asserted allocation of its amount.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Tashkent")


def usd(cents):
    cents = int(cents or 0)
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}{whole:,}.{fraction:02d}"


def date_of(ts):
    return datetime.fromtimestamp(int(ts), TZ).strftime("%d.%m.%Y %H:%M")


def customer_payments(db, agent, since=0, until=None, limit=12):
    upper = int(until) if until is not None else 9999999999
    return db.execute("""SELECT e.id,e.ts,e.amount_usd,e.client,
          c.name AS customer_name,c.shop_name
        FROM events e LEFT JOIN clients c ON c.id=e.client
        WHERE e.agent=? AND e.kind='payment' AND e.amount_usd>0
          AND e.ts>? AND e.ts<=?
        ORDER BY e.ts DESC,e.id DESC LIMIT ?""",
        (agent, int(since), upper, max(1, min(int(limit), 50)))).fetchall()


def payment_line(row):
    customer = row["shop_name"]
    if not customer or customer == "Йўқ":
        customer = row["customer_name"]
    customer = customer or f"Мижоз #{row['client']}"
    return f"• {date_of(row['ts'])} · {customer} (#{row['client']}) · {usd(row['amount_usd'])} USD"


def handover_context(db, row, limit=12):
    """Recent payments before submission for verification, NOT allocated receipts."""
    previous = db.execute(
        "SELECT COALESCE(MAX(ts),0) FROM handovers WHERE agent=? AND id<?",
        (row["agent"], row["id"])).fetchone()
    since = int(previous[0] or 0)
    payments = customer_payments(db, row["agent"], since, row["ts"], limit + 1)
    chosen = payments[:limit]
    heading = "🧾 Агентнинг ушбу топшириқдан олдинги мижоз тўловлари:"
    lines = [heading]
    lines.extend(payment_line(p) for p in chosen)
    if not chosen:
        lines.append("Бу оралиқда мижоздан тўлов ёзуви топилмади.")
    if len(payments) > limit:
        lines.append(f"… Сўнгги {limit} та тўлов кўрсатилди.")
    elif chosen:
        total = sum(int(p["amount_usd"] or 0) for p in chosen)
        lines.append(f"Ушбу оралиқда қайд этилган тўловлар: {usd(total)} USD.")
    lines.append(
        "⚠️ Мижоз тўловлари топшириш IDсига алоҳида боғланмаган. "
        "Бу рўйхат текшириш учун; пул ҳақиқатан кассирга берилганини тасдиқламайди."
    )
    return "\n".join(lines)


def report(db):
    """No write, no artificial reversal, no double counting in cashier's balance."""
    pending = db.execute("""SELECT h.id,h.agent,h.ts,h.amount_usd,h.amount,
           u.name AS agent_name FROM handovers h
           LEFT JOIN users u ON u.id=h.agent
           WHERE h.status='pending' ORDER BY h.ts DESC,h.id DESC LIMIT 30""").fetchall()
    total_pending = int(db.execute(
        "SELECT COALESCE(SUM(amount_usd),0) FROM handovers WHERE status='pending'"
    ).fetchone()[0] or 0)
    result = [
        "⏳ ТАСДИҚЛАНМАГАН ПУЛЛАР",
        f"Кассир тасдиғини кутаётган топшириқлар: {usd(total_pending)} USD",
        "Бу сумма касса қолдиғига киритилмаган.",
        "",
        "🏦 КАССИР ҚАБУЛ ҚИЛМАГАН ТОПШИРИҚЛАР",
    ]
    if pending:
        for hand in pending:
            value = (f"{usd(hand['amount_usd'])} USD" if hand["amount_usd"]
                     else f"{usd(hand['amount'])} сўм")
            result.append(
                f"\n№{hand['id']} · {hand['agent_name'] or hand['agent']}\n"
                f"Сумма: {value} · {date_of(hand['ts'])}\n"
                f"{handover_context(db, hand, limit=12)}\n"
                f"🔎 Кўриб чиқиш: /review {hand['id']}"
            )
    else:
        result.append("Ҳозирча кутилаётган топшириқ йўқ.")
    result.extend(["", "👨‍💼 АГЕНТЛАРДА — ҲАЛИ КАССИР ҚАБУЛ ҚИЛМАГАН ЙИҒИМЛАР"])
    agents = db.execute("SELECT id,name FROM users WHERE role IN ('agent','disabled') ORDER BY name,id").fetchall()
    total_unsubmitted = 0
    found = False
    for agent in agents:
        aid = int(agent["id"])
        collected = int(db.execute(
            "SELECT COALESCE(SUM(amount_usd),0) FROM events WHERE agent=? AND kind='payment'",
            (aid,)).fetchone()[0] or 0)
        accepted = int(db.execute(
            "SELECT COALESCE(SUM(amount_usd),0) FROM handovers WHERE agent=? AND status='accepted'",
            (aid,)).fetchone()[0] or 0)
        awaiting = int(db.execute(
            "SELECT COALESCE(SUM(amount_usd),0) FROM handovers WHERE agent=? AND status='pending'",
            (aid,)).fetchone()[0] or 0)
        unmatched = collected - accepted - awaiting
        if not (collected or awaiting or accepted):
            continue
        found = True
        total_unsubmitted += unmatched
        result.append(
            f"\n{agent['name'] or aid}: жами йиғим {usd(collected)} USD;\n"
            f"Касса қабул қилган {usd(accepted)} USD; кутилаётган {usd(awaiting)} USD;\n"
            f"Топшириш сўровисиз қолган ҳисобий сумма: {usd(unmatched)} USD."
        )
        if unmatched:
            last = int(db.execute(
                "SELECT COALESCE(MAX(ts),0) FROM handovers WHERE agent=?",
                (aid,)).fetchone()[0] or 0)
            recent = customer_payments(db, aid, last, limit=8)
            if recent:
                result.append("Сўнгги топшириш сўровидан кейинги мижоз тўловлари:")
                result.extend(payment_line(p) for p in recent)
            else:
                result.append("Мижозлар бўйича бу сумманинг алоҳида боғланиши мавжуд эмас.")
    if not found:
        result.append("Агентлардан пул йиғими ҳали киритилмаган.")
    result.extend([
        "",
        f"📌 Ҳали топшириш сўровисиз ҳисобий жами: {usd(total_unsubmitted)} USD.",
        "⚠️ Мижоз тўлови қайди ва кассага топшириш икки хил операция. "
        "Мижозлар рўйхати пулнинг физик топширилганини исботламайди. "
        "Ҳеч қандай янги тўлов ёки топшириш автоматик яратилмади.",
    ])
    return "\n".join(result)
