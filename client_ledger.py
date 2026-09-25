"""Shared read-only customer goods and payment history for Telegram and map cards.

Financial events and explicit client_visits are deliberately separate ledgers.
Never count 'sold' again as a delivery or a new receivable.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from core import product_name

TZ = ZoneInfo('Asia/Tashkent')
KINDS = ('delivery', 'payment', 'sold', 'return', 'order', 'visit')


def usd(cents):
    cents = int(cents or 0)
    sign = '-' if cents < 0 else ''
    whole, frac = divmod(abs(cents), 100)
    return f'{sign}{whole:,}.{frac:02d}'


def totals(db, client_id):
    row = db.execute("""SELECT
        COALESCE(SUM(CASE WHEN kind='delivery' THEN qty ELSE 0 END),0) AS delivered_qty,
        COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd ELSE 0 END),0) AS delivered_usd,
        COALESCE(SUM(CASE WHEN kind='payment' THEN amount_usd ELSE 0 END),0) AS paid_usd,
        COALESCE(SUM(CASE WHEN kind='payment' THEN amount ELSE 0 END),0) AS paid_uzs,
        COALESCE(SUM(CASE WHEN kind='return' THEN qty ELSE 0 END),0) AS returned_qty,
        COALESCE(SUM(CASE WHEN kind='return' THEN amount_usd ELSE 0 END),0) AS returned_usd,
        COALESCE(SUM(CASE WHEN kind='sold' THEN qty ELSE 0 END),0) AS sold_qty
        FROM events WHERE client=?""", (client_id,)).fetchone()
    return {key: int(row[key] or 0) for key in row.keys()}


def rows(db, client_id, limit=25):
    limit = max(1, min(int(limit), 500))
    return db.execute("""SELECT e.id,e.kind,e.pack,e.qty,e.amount,e.amount_usd,e.ts,
                 e.actor,e.agent,u.name AS actor_name
        FROM events e LEFT JOIN users u ON u.id=e.actor
        WHERE e.client=? AND e.kind IN ('delivery','payment','sold','return','order','visit')
        ORDER BY e.ts DESC,e.id DESC LIMIT ?""", (client_id, limit)).fetchall()


def summary(db, client_id):
    t = totals(db, client_id)
    lines = [
        f"📦 Жами берилган товар: {t['delivered_qty']} дона · {usd(t['delivered_usd'])} USD",
        f"💰 Жами олинган пул: {usd(t['paid_usd'])} USD",
        f"↩️ Жами қайтарилган: {t['returned_qty']} дона · {usd(t['returned_usd'])} USD",
        f"🛍 Сотилгани қайд этилган: {t['sold_qty']} дона (иккинчи марта қарз ҳисобланмайди)",
    ]
    if t['paid_uzs']:
        lines.append(f"💴 Эски сўмда олинган пул: {usd(t['paid_uzs'])} сўм (USDга қўшилмаган)")
    return '\n'.join(lines)


def entry(row):
    stamp = datetime.fromtimestamp(int(row['ts']), TZ).strftime('%d.%m.%Y %H:%M') if row['ts'] else 'Сана номаълум'
    actor = row['actor_name'] or str(row['actor'] or row['agent'] or 'Номаълум')
    kind = row['kind']
    pack = product_name(row['pack']) if kind in ('delivery', 'sold', 'return', 'order') else ''
    if kind == 'delivery':
        detail = f"📦 Берилди: {pack} · {row['qty']} дона · {usd(row['amount_usd'])} USD"
    elif kind == 'payment':
        detail = (f"💰 Пул олинди: {usd(row['amount_usd'])} USD" if row['amount_usd']
                  else f"💰 Пул олинди: {usd(row['amount'])} сўм")
    elif kind == 'return':
        detail = f"↩️ Қайтарилди: {pack} · {row['qty']} дона · {usd(row['amount_usd'])} USD қарз камайди"
    elif kind == 'sold':
        detail = f"🛍 Сотилгани қайд этилди: {pack} · {row['qty']} дона · {usd(row['amount_usd'])} USD (янги қарз эмас)"
    elif kind == 'order':
        detail = f"🛒 Буюртма: {pack} · {row['qty']} дона"
    else:
        detail = '📝 Ташриф қайди'
    return f"{stamp} · {actor}\n{detail}"


def recent_text(db, client_id, limit=12):
    items = rows(db, client_id, limit + 1)
    if not items:
        return 'Ҳали товар бериш ёки пул олиш операциялари йўқ.'
    text = '\n\n'.join(entry(item) for item in items[:limit])
    if len(items) > limit:
        text += f'\n\n… Сўнгги {limit} та операция кўрсатилди.'
    return text
