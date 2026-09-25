"""Read-only daily cashier book in Asia/Tashkent time.

Collected customer payments and pending handovers NEVER count as cashier income.
UZS expenses retain both their actual integer-som amount and booked USD cents
at the rate saved when the transaction was posted.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import core

TZ=ZoneInfo('Asia/Tashkent')


def usd(cents):
    cents=int(cents or 0)
    sign='-' if cents<0 else ''
    whole,frac=divmod(abs(cents),100)
    return f"{sign}{whole:,}.{frac:02d}"


def som(amount):
    return f"{int(amount or 0):,}".replace(',',' ')


def report(db,now=None):
    now=int(now if now is not None else datetime.now(TZ).timestamp())
    day=datetime.fromtimestamp(now,TZ).replace(hour=0,minute=0,second=0,microsecond=0)
    start=int(day.timestamp())
    end=int((day+timedelta(days=1)).timestamp())
    cash_accepted=int(db.execute("""SELECT COALESCE(SUM(amount_usd),0)
          FROM handovers WHERE status='accepted' AND accepted_ts>=? AND accepted_ts<?""",
          (start,end)).fetchone()[0] or 0)
    collected=int(db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM events
          WHERE kind='payment' AND ts>=? AND ts<?""",(start,end)).fetchone()[0] or 0)
    opening_income=int(db.execute("""SELECT COALESCE(SUM(amount_usd),0)
          FROM handovers WHERE status='accepted' AND COALESCE(accepted_ts,ts)<?""",(start,)).fetchone()[0] or 0)
    opening_expense=int(db.execute("""SELECT COALESCE(SUM(amount_usd),0)
          FROM cashier_expenses WHERE ts<?""",(start,)).fetchone()[0] or 0)
    expense=db.execute("""SELECT
         COALESCE(SUM(amount_usd),0) AS usd_equivalent,
         COALESCE(SUM(CASE WHEN currency='UZS' THEN amount_uzs ELSE 0 END),0) AS original_uzs,
         COALESCE(SUM(CASE WHEN currency='USD' THEN amount_usd ELSE 0 END),0) AS original_usd
         FROM cashier_expenses WHERE ts>=? AND ts<?""",(start,end)).fetchone()
    pending=int(db.execute("""SELECT COALESCE(SUM(amount_usd),0)
          FROM handovers WHERE status='pending'""").fetchone()[0] or 0)
    rate=core.cashier_rate(db)
    opening=opening_income-opening_expense
    closing=opening+cash_accepted-int(expense['usd_equivalent'] or 0)
    rows=db.execute("""SELECT e.ts,e.currency,e.amount_uzs,e.amount_usd,e.rate_uzs_per_usd,
          e.category,e.recipient,u.name AS cashier_name FROM cashier_expenses e
          LEFT JOIN users u ON u.id=e.cashier
          WHERE e.ts>=? AND e.ts<? ORDER BY e.ts DESC,e.id DESC LIMIT 25""",(start,end)).fetchall()
    accepted=db.execute("""SELECT h.ts,h.accepted_ts,h.amount_usd,u.name AS agent_name
          FROM handovers h LEFT JOIN users u ON u.id=h.agent
          WHERE h.status='accepted' AND h.accepted_ts>=? AND h.accepted_ts<?
          ORDER BY h.accepted_ts DESC,h.id DESC LIMIT 20""",(start,end)).fetchall()
    out=[
       f"📊 КУНЛИК КАССА · {day.strftime('%d.%m.%Y')}",
       f"💵 Кун бошидаги ҳисобий қолдиқ: {usd(opening)} USD",
       f"✅ Бугун кассир қабул қилган: {usd(cash_accepted)} USD",
       f"🧾 Бугун сўмдаги харажат: {som(expense['original_uzs'])} сўм",
       f"🧾 Бугун USD харажати: {usd(expense['original_usd'])} USD",
       f"💱 Харажатларнинг жами USD эквиваленти: {usd(expense['usd_equivalent'])} USD",
       f"💰 Кун охиридаги ҳисобий қолдиқ: {usd(closing)} USD",
       f"⏳ Ҳали тасдиқланмаган топшириқ: {usd(pending)} USD (қолдиққа қўшилмаган)",
       f"👥 Бугун агентлар мижоздан олган: {usd(collected)} USD (кассир кирими эмас)",
       f"💱 Жорий ички курс: 1 USD = {som(rate)} сўм" if rate else "💱 Касса курси: ҳали белгиланмаган",
       "",
       "🏦 БУГУН ҚАБУЛ ҚИЛИНГАН ПУЛЛАР:",
    ]
    if accepted:
        out.extend(f"• {datetime.fromtimestamp(int(h['accepted_ts']),TZ).strftime('%H:%M')} · "
                   f"{h['agent_name'] or 'Агент'} · {usd(h['amount_usd'])} USD" for h in accepted)
    else:out.append("Ҳали қабул қилинмаган.")
    out.extend(["","🧾 БУГУНГИ ХАРАЖАТЛАР:"])
    if rows:
        for e in rows:
            original=(f"{som(e['amount_uzs'])} сўм · 1 USD = {som(e['rate_uzs_per_usd'])} сўм"
                      if e['currency']=='UZS' else f"{usd(e['amount_usd'])} USD")
            out.append(f"• {datetime.fromtimestamp(int(e['ts']),TZ).strftime('%H:%M')} · {e['category']}"
                       f"\n{original} → {usd(e['amount_usd'])} USD · {e['recipient']}")
    else:out.append("Ҳали харажат киритилмаган.")
    out.append("\nℹ️ Қолдиқ — тизимда кассир тасдиқлаган пуллар минус қайд қилинган харажатларнинг USD эквиваленти. "
               "Бу ҳақиқий сўм ва доллар банкнотлари қолдиғини ёки аввалги дастурдан ташқари нақдни алоҳида ҳисобламайди.")
    return '\n'.join(out)
