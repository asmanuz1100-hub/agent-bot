"""Sodda hisobot: Hududlar, Mahsulotlar, Mijozlar (KPI) va "Bugun kimga".

Biznes qoidasi (USD sentda, butun son):
  * Berilgan tovar = delivery.amount_usd
  * Qaytgan tovar  = return.amount_usd
  * Olingan pul    = payment.amount_usd
  * Qarz(t)        = berilgan − qaytgan − olingan pul, ts < t. Manfiy qiymat = avans.
  Qarz va avans alohida yig'iladi: bir mijozning avansi boshqasining qarzini kamaytirmaydi.
  "Sotildi" yozuvlari bu hisobotga kirmaydi (funksiya va tarix saqlanadi).
  Eski so'mdagi (USD narxsiz) yozuvlar konvertatsiya qilinmaydi — faqat sanaladi.

Davr hisobotidagi qarz — tanlangan davr oxiridagi qoldiq; to'lov — faqat shu davrdagi.
Taqqoslash teng davomiylikdagi oynalarda: oldingi oy qisqa bo'lsa ikkala oyna qisqartiriladi.

Agentga bog'lash: c.agent — mijozning joriy egasi (portfel, qarz, "Bugun kimga");
e.agent — operatsiyani bajargan agent (agentlar jadvalidagi operatsiyalar).

Hisob har so'rovda SQL'da yig'iladi (GROUP BY), voqealar qatorma-qator yuklanmaydi.
"""
import time
from datetime import date, datetime, timedelta
from fractions import Fraction
from zoneinfo import ZoneInfo

import core

TZ = ZoneInfo('Asia/Tashkent')
DAY = 86400

# KPI konfiguratsiyasi — boshqaruv uchun boshlang'ich qoida (statistik model emas).
KPI = {
    'activity': {'both': 30, 'current_only': 20, 'previous_only': 10, 'none': 0},
    'payment_max': 40,
    # O'sish bali (har biri 0–15). Oraliqlar kesishmaydi: [min, max) foizda.
    'growth_bands': [(20, None, 15), (5, 20, 12), (-5, 5, 8), (-20, -5, 4), (None, -20, 0)],
    'groups': [(70, 'active', 'Faol'), (40, 'low', 'Faolligi past'), (0, 'passive', 'Passiv')],
    # Yangi mijoz: birinchi tovardan shuncha kun o'tmaguncha ball berilmaydi.
    # Hozircha 15 kun (Ali qarori); keyinroq 30 kunga qaytariladi.
    'new_days': 15,
}
TODAY = {'visit_due_days': 5, 'prospect_days': 14}
NO_NAME = {'йўқ', 'йук', 'йок', 'йўк', 'нет', 'yoq', "yo'q", 'yo‘q', 'yok', '-', '—', '–', '.', '0',
           'no', 'none', 'null', 'номаълум'}


def _i(v):
    return int(v or 0)


def _day_start(ts):
    return datetime.fromtimestamp(ts, TZ).replace(hour=0, minute=0, second=0, microsecond=0)


def _fmt(ts):
    return datetime.fromtimestamp(ts, TZ).strftime('%d.%m.%Y')


def _fmt_end(ts_exclusive, partial):
    d = datetime.fromtimestamp(ts_exclusive - 1, TZ)
    return d.strftime('%d.%m.%Y') + (d.strftime(' %H:%M gacha') if partial else '')


def period_bounds(period, date_from=None, date_to=None, now=None):
    """Joriy davr [start,end) va taqqoslash uchun teng oynalar [cmpStart,cmpEnd) / [prevStart,prevEnd)."""
    now = int(time.time() if now is None else now)
    today = _day_start(now)
    period = str(period or 'month')
    if period == 'today':
        start, prev, name = today, today - timedelta(days=1), 'Bugun'
    elif period == 'week':
        start = today - timedelta(days=6)
        prev, name = start - timedelta(days=7), 'Oxirgi 7 kun'
    elif period == 'month':
        start = today.replace(day=1)
        prev, name = (start - timedelta(days=1)).replace(day=1), 'Shu oy'
    elif period == 'custom':
        try:
            a = datetime.strptime(str(date_from or ''), '%Y-%m-%d').replace(tzinfo=TZ)
            b = datetime.strptime(str(date_to or ''), '%Y-%m-%d').replace(tzinfo=TZ)
        except ValueError:
            raise ValueError('Davr sanalarini to‘g‘ri tanlang.')
        if b < a:
            a, b = b, a
        if (b - a).days > 400:
            raise ValueError('Davr 400 kundan oshmasin.')
        start = a
        prev = a - (b + timedelta(days=1) - a)
        name = 'Tanlangan davr'
    else:
        raise ValueError('Davr noto‘g‘ri.')
    s, ps = int(start.timestamp()), int(prev.timestamp())
    e = min(int((b + timedelta(days=1)).timestamp()), now + 1) if period == 'custom' else now + 1
    if e <= s:
        raise ValueError('Davr hali boshlanmagan.')
    length = min(e - s, s - ps)          # oldingi oyna joriy davr boshidan oshmaydi
    partial = e > now
    trimmed = length < e - s
    return {'period': period, 'start': s, 'end': e, 'complete': not partial,
            'cmpStart': s, 'cmpEnd': s + length, 'prevStart': ps, 'prevEnd': ps + length,
            'trimmed': trimmed,
            'label': f"{name}: {_fmt(s)} – {_fmt_end(e, partial)}",
            'compareLabel': (f"{_fmt(s)} – {_fmt_end(s + length, partial and not trimmed)} va "
                             f"{_fmt(ps)} – {_fmt_end(ps + length, partial and not trimmed)}")}


def region_key(name):
    """Agent ilovasidagi regionKey() bilan bir xil normalizatsiya."""
    key = ' '.join(str(name or '').strip().lower().replace('‘', '').replace('’', '').replace('ʻ', '')
                   .replace('\x60', '').replace('´', '').replace("'", '').split())
    return 'yaypan' if key == 'yapan' else key


def display_name(c):
    for value in ((c['shop_name'] or '').strip(), (c['name'] or '').strip()):
        if value and value.lower() not in NO_NAME:
            return value
    return f"Mijoz #{int(c['id'])}"


def growth(cur, prev, known=True, started_text='Bu davrda boshlandi'):
    """O'sish = (joriy − oldingi) / oldingi × 100. Nol va noma'lum aralashtirilmaydi."""
    if not known:
        return {'kind': 'unknown', 'pct': None, 'text': 'Taqqoslash uchun ma’lumot yetarli emas'}
    if prev == 0:
        if cur > 0:
            return {'kind': 'started', 'pct': None, 'text': started_text}
        return {'kind': 'zero', 'pct': None, 'text': 'Ikkala davrda ham 0'}
    pct = round((cur - prev) * 100.0 / prev, 1)
    return {'kind': 'pct', 'pct': pct, 'text': f"{'↑' if pct >= 0 else '↓'}{abs(pct):.0f}%"}


def growth_points(cur, prev):
    """0–15 ball. Faqat oldingi qiymat > 0 bo'lsa; aks holda None (noma'lum)."""
    if prev <= 0:
        return None
    diff = (cur - prev) * 100           # foizni butun sonlarda solishtiramiz: diff >= p*prev
    for lo, hi, pts in KPI['growth_bands']:
        if (lo is None or diff >= lo * prev) and (hi is None or diff < hi * prev):
            return pts
    return 0


def activity_points(cur_delivered, prev_delivered):
    a = KPI['activity']
    if cur_delivered and prev_delivered:
        return a['both']
    if cur_delivered:
        return a['current_only']
    if prev_delivered:
        return a['previous_only']
    return a['none']


def kpi_group(total):
    for threshold, key, label in KPI['groups']:
        if total >= threshold:
            return key, label
    return KPI['groups'][-1][1], KPI['groups'][-1][2]


def client_kpi(x, b, ref):
    """Mijoz bahosi faqat o'z ma'lumotidan — filtrga va boshqa mijozlarga bog'liq emas."""
    first = x['firstDelivery']
    if first is None:
        return {'status': 'prospect', 'label': 'Istiqbolli'}
    if ref - first < KPI['new_days'] * DAY:
        return {'status': 'new', 'label': 'Yangi', 'firstDeliveryTs': first}
    base = x['delEnd'] - x['retEnd']
    if base <= 0:
        return {'status': 'nobase', 'label': 'Baholash uchun asos yo‘q'}
    act = activity_points(x['delCmp'] > 0, x['delPrev'] > 0)
    pay = Fraction(KPI['payment_max']) * min(Fraction(1), max(Fraction(0), Fraction(x['paidEnd'], base)))
    gd = growth_points(x['delCmp'], x['delPrev'])
    gp = growth_points(x['paidCmp'], x['paidPrev'])
    parts = {'activity': act, 'payment': round(float(pay), 1),
             'deliveryGrowth': gd, 'paymentGrowth': gp}
    if not x['prevKnown'] or gd is None or gp is None:
        # Dastlabki ball: o'tgan davr bilan solishtirib bo'lmaydi, shuning uchun o'sish qismi olinmaydi.
        # Faollik (shu davrda tovar oldi — 30) + to'lov (0–40) = 70 dan, 100 ballga keltiriladi.
        act0 = KPI['activity']['both'] if x['delCmp'] > 0 else 0
        total = (act0 + pay) * Fraction(100, KPI['activity']['both'] + KPI['payment_max'])
        key, label = kpi_group(total)
        parts = {'activity': act0, 'payment': round(float(pay), 1), 'deliveryGrowth': None, 'paymentGrowth': None}
        return {'status': 'rated', 'provisional': True, 'score': int(total + Fraction(1, 2)), 'group': key,
                'label': label, 'parts': parts}
    total = act + pay + gd + gp
    key, label = kpi_group(total)
    return {'status': 'rated', 'score': int(total + Fraction(1, 2)), 'group': key, 'label': label, 'parts': parts}


def _scope(agent, alias='c'):
    if agent is None:
        return '', []
    return f' AND {alias}.agent=?', [int(agent)]


def _client_sums(db, b, agent):
    """Har mijoz uchun bitta GROUP BY so'rov."""
    w, wa = _scope(agent)
    s, e, cs, ce, ps, pe = b['start'], b['end'], b['cmpStart'], b['cmpEnd'], b['prevStart'], b['prevEnd']

    def win(kind, lo, hi, col='amount_usd'):
        return f"COALESCE(SUM(CASE WHEN e.kind='{kind}' AND e.ts>={lo} AND e.ts<{hi} THEN e.{col} ELSE 0 END),0)"

    sql = f"""SELECT e.client AS client,
        {win('delivery', 0, e)} AS del_end, {win('return', 0, e)} AS ret_end, {win('payment', 0, e)} AS paid_end,
        COALESCE(SUM(CASE WHEN e.kind='delivery' THEN e.amount_usd WHEN e.kind IN ('return','payment') THEN -e.amount_usd ELSE 0 END),0) AS debt_now,
        {win('delivery', s, e)} AS del_cur, {win('delivery', s, e, 'qty')} AS del_cur_qty,
        {win('return', s, e)} AS ret_cur, {win('return', s, e, 'qty')} AS ret_cur_qty, {win('payment', s, e)} AS paid_cur,
        {win('delivery', cs, ce)} AS del_cmp, {win('payment', cs, ce)} AS paid_cmp,
        {win('delivery', ps, pe)} AS del_prev, {win('payment', ps, pe)} AS paid_prev,
        MIN(CASE WHEN e.kind='delivery' AND e.ts<{e} THEN e.ts END) AS first_delivery,
        MIN(e.ts) AS first_event,
        COALESCE(SUM(CASE WHEN e.kind IN ('payment','sold','delivery') AND e.amount_usd=0 AND e.amount>0 THEN 1 ELSE 0 END),0) AS legacy
        FROM events e JOIN clients c ON c.id=e.client
        WHERE e.client IS NOT NULL AND e.kind IN ('delivery','return','payment','sold'){w}
        GROUP BY e.client"""
    out = {}
    for r in db.execute(sql, wa).fetchall():
        out[_i(r['client'])] = {
            'delEnd': _i(r['del_end']), 'retEnd': _i(r['ret_end']), 'paidEnd': _i(r['paid_end']),
            'debtNow': _i(r['debt_now']), 'delCur': _i(r['del_cur']), 'delCurQty': _i(r['del_cur_qty']),
            'retCur': _i(r['ret_cur']), 'retCurQty': _i(r['ret_cur_qty']), 'paidCur': _i(r['paid_cur']),
            'delCmp': _i(r['del_cmp']), 'paidCmp': _i(r['paid_cmp']),
            'delPrev': _i(r['del_prev']), 'paidPrev': _i(r['paid_prev']),
            'firstDelivery': _i(r['first_delivery']) or None, 'firstEvent': _i(r['first_event']) or None,
            'legacy': _i(r['legacy'])}
    return out


EMPTY = {'delEnd': 0, 'retEnd': 0, 'paidEnd': 0, 'debtNow': 0, 'delCur': 0, 'delCurQty': 0, 'retCur': 0,
         'retCurQty': 0, 'paidCur': 0, 'delCmp': 0, 'paidCmp': 0, 'delPrev': 0, 'paidPrev': 0,
         'firstDelivery': None, 'firstEvent': None, 'legacy': 0}


def _money_block(rows):
    """Qarz va avans alohida."""
    debt = sum(max(0, r['debtCents']) for r in rows)
    adv = sum(max(0, -r['debtCents']) for r in rows)
    return debt, adv


def insights(db, period='month', date_from=None, date_to=None, agent=None, now=None):
    now = int(time.time() if now is None else now)
    b = period_bounds(period, date_from, date_to, now)
    ref = min(b['end'] - 1, now)
    w, wa = _scope(agent)
    clients = db.execute(f"""SELECT c.id,c.agent,c.name,c.shop_name,c.region,c.created_ts,c.map_only,c.blacklisted,
        u.name AS agent_name FROM clients c LEFT JOIN users u ON u.id=c.agent WHERE 1=1{w} ORDER BY c.id""", wa).fetchall()
    sums = _client_sums(db, b, agent)

    rows = []
    for c in clients:
        cid = _i(c['id'])
        x = dict(sums.get(cid, EMPTY))
        known_ts = [v for v in (x['firstEvent'], _i(c['created_ts'])) if v]
        first_known = min(known_ts) if known_ts else None
        x['prevKnown'] = first_known is not None and first_known < b['prevEnd']
        debt_end = x['delEnd'] - x['retEnd'] - x['paidEnd']
        rows.append({
            'id': cid, 'name': display_name(c), 'region': (c['region'] or '').strip() or 'Belgilanmagan',
            'regionKey': region_key(c['region']) or '', 'agentId': _i(c['agent']), 'agent': c['agent_name'] or str(c['agent']),
            'deliveredCents': x['delCur'], 'deliveredQty': x['delCurQty'],
            'returnedCents': x['retCur'], 'returnedQty': x['retCurQty'], 'paidCents': x['paidCur'],
            'debtCents': debt_end, 'debtNowCents': x['debtNow'],
            'deliveryGrowth': growth(x['delCmp'], x['delPrev'], x['prevKnown'], 'Bu davrda tovar oldi'),
            'paymentGrowth': growth(x['paidCmp'], x['paidPrev'], x['prevKnown'], 'Bu davrda to‘lov qildi'),
            'kpi': ({'status': 'blacklisted', 'label': 'Qora ro‘yxatda'} if _i(c['blacklisted'])
                    else client_kpi(x, b, ref)), 'legacyEvents': x['legacy'], '_x': x})

    rated = sorted([r for r in rows if r['kpi']['status'] == 'rated'],
                   key=lambda r: (-r['kpi']['score'], -r['deliveredCents'], r['id']))
    for i, r in enumerate(rated):
        r['rank'] = i + 1

    def agg(members):
        xs = [m['_x'] for m in members]
        debt, adv = _money_block(members)
        known = any(x['prevKnown'] for x in xs)
        return {'clients': len(members),
                'prospects': sum(1 for m in members if m['kpi']['status'] == 'prospect'),
                'deliveredCents': sum(m['deliveredCents'] for m in members),
                'deliveredQty': sum(m['deliveredQty'] for m in members),
                'returnedCents': sum(m['returnedCents'] for m in members),
                'paidCents': sum(m['paidCents'] for m in members),
                'debtCents': debt, 'advanceCents': adv,
                'deliveryGrowth': growth(sum(x['delCmp'] for x in xs), sum(x['delPrev'] for x in xs), known, 'Bu davrda tovar oldi'),
                'paymentGrowth': growth(sum(x['paidCmp'] for x in xs), sum(x['paidPrev'] for x in xs), known, 'Bu davrda to‘lov qildi')}

    groups = {}
    for r in rows:
        groups.setdefault(r['regionKey'], []).append(r)
    regions = []
    for key, members in groups.items():
        names = {}
        for m in members:
            names[m['region']] = names.get(m['region'], 0) + 1
        item = agg(members)
        item.update({'key': key or '-', 'name': 'Belgilanmagan' if not key else max(names.items(), key=lambda kv: (kv[1], kv[0]))[0],
                     'clientIds': [m['id'] for m in sorted(members, key=lambda m: (m['kpi']['status'] != 'rated',
                                   -(m['kpi'].get('score') or 0), -m['deliveredCents'], m['id']))]})
        regions.append(item)
    regions.sort(key=lambda r: (-r['deliveredCents'], r['name']))

    # Mahsulotlar: faqat tovar harakati; to'lov mahsulotga taqsimlanmaydi.
    pw, pa = _scope(agent)
    s, e, cs, ce, ps, pe = b['start'], b['end'], b['cmpStart'], b['cmpEnd'], b['prevStart'], b['prevEnd']
    names = {_i(r['pack']): r['name'] for r in db.execute('SELECT pack,name FROM products').fetchall()}
    products = []
    for r in db.execute(f"""SELECT e.pack AS pack,
            COALESCE(SUM(CASE WHEN e.kind='delivery' AND e.ts>={s} AND e.ts<{e} THEN e.qty ELSE 0 END),0) AS dq,
            COALESCE(SUM(CASE WHEN e.kind='delivery' AND e.ts>={s} AND e.ts<{e} THEN e.amount_usd ELSE 0 END),0) AS dc,
            COALESCE(SUM(CASE WHEN e.kind='return' AND e.ts>={s} AND e.ts<{e} THEN e.qty ELSE 0 END),0) AS rq,
            COALESCE(SUM(CASE WHEN e.kind='return' AND e.ts>={s} AND e.ts<{e} THEN e.amount_usd ELSE 0 END),0) AS rc,
            COALESCE(SUM(CASE WHEN e.kind='delivery' AND e.ts>={cs} AND e.ts<{ce} THEN e.qty ELSE 0 END),0) AS cq,
            COALESCE(SUM(CASE WHEN e.kind='delivery' AND e.ts>={cs} AND e.ts<{ce} THEN e.amount_usd ELSE 0 END),0) AS cc,
            COALESCE(SUM(CASE WHEN e.kind='delivery' AND e.ts>={ps} AND e.ts<{pe} THEN e.qty ELSE 0 END),0) AS pq,
            COALESCE(SUM(CASE WHEN e.kind='delivery' AND e.ts>={ps} AND e.ts<{pe} THEN e.amount_usd ELSE 0 END),0) AS pc
            FROM events e JOIN clients c ON c.id=e.client
            WHERE e.pack>0 AND e.kind IN ('delivery','return') AND e.ts>={min(s, ps)} AND e.ts<{e}{pw}
            GROUP BY e.pack""", pa).fetchall():
        p = _i(r['pack'])
        if not any(_i(r[k]) for k in ('dq', 'rq', 'pq')):
            continue
        products.append({'pack': p, 'name': names.get(p) or core.product_name(p),
                         'deliveredQty': _i(r['dq']), 'deliveredCents': _i(r['dc']),
                         'returnedQty': _i(r['rq']), 'returnedCents': _i(r['rc']),
                         'qtyGrowth': growth(_i(r['cq']), _i(r['pq']), True, 'Bu davrda berildi'),
                         'amountGrowth': growth(_i(r['cc']), _i(r['pc']), True, 'Bu davrda berildi')})
    products.sort(key=lambda p: (-p['deliveredCents'], -p['deliveredQty'], p['pack']))

    # Agentlar: operatsiyalar (e.agent) va portfel (c.agent) alohida
    ow, oa = ('', [])
    if agent is not None:
        ow, oa = ' AND e.agent=?', [int(agent)]
    ops = {}
    for o in db.execute(f"""SELECT e.agent AS agent,
            COALESCE(SUM(CASE WHEN e.kind='delivery' THEN e.amount_usd ELSE 0 END),0) AS d,
            COALESCE(SUM(CASE WHEN e.kind='return' THEN e.amount_usd ELSE 0 END),0) AS r,
            COALESCE(SUM(CASE WHEN e.kind='payment' THEN e.amount_usd ELSE 0 END),0) AS p
            FROM events e WHERE e.client IS NOT NULL AND e.ts>=? AND e.ts<?{ow}
            AND e.kind IN ('delivery','return','payment') GROUP BY e.agent""", [s, e] + oa).fetchall():
        ops[_i(o['agent'])] = {'deliveredCents': _i(o['d']), 'returnedCents': _i(o['r']), 'paidCents': _i(o['p'])}
    by_agent = {}
    for r in rows:
        by_agent.setdefault(r['agentId'], []).append(r)
    agent_names = {_i(u['id']): u['name'] for u in db.execute('SELECT id,name FROM users').fetchall()}
    agents = []
    for aid in sorted(set(by_agent) | set(ops)):
        members = by_agent.get(aid, [])
        debt, adv = _money_block(members)
        agents.append({'agentId': aid, 'agent': agent_names.get(aid) or str(aid), 'clients': len(members),
                       'debtCents': debt, 'advanceCents': adv,
                       'operations': ops.get(aid, {'deliveredCents': 0, 'returnedCents': 0, 'paidCents': 0})})
    agents.sort(key=lambda a: (-a['operations']['deliveredCents'], a['agentId']))

    summary = agg(rows)
    summary['rated'] = len(rated)
    summary['legacyEvents'] = sum(r['legacyEvents'] for r in rows)
    for r in rows:
        r.pop('_x')
    order = {'rated': 0, 'new': 1, 'insufficient': 2, 'nobase': 3, 'prospect': 4, 'blacklisted': 5}
    rows.sort(key=lambda r: (order[r['kpi']['status']], r.get('rank') or 0, -r['deliveredCents'], r['id']))
    return {'period': b['period'], 'label': b['label'], 'compareLabel': b['compareLabel'], 'trimmed': b['trimmed'],
            'start': b['start'], 'end': b['end'], 'cmpStart': b['cmpStart'], 'cmpEnd': b['cmpEnd'],
            'prevStart': b['prevStart'], 'prevEnd': b['prevEnd'], 'complete': b['complete'],
            'scope': {'agentId': int(agent) if agent is not None else None},
            'summary': summary, 'regions': regions, 'products': products, 'clients': rows, 'agents': agents,
            'kpiRules': {'activity': KPI['activity'], 'paymentMax': KPI['payment_max'],
                         'growthBands': KPI['growth_bands'], 'groups': KPI['groups'], 'newDays': KPI['new_days']}}


# ---------------------------------------------------------------- Bugun kimga

ACTIONS = {'agreed_visit': 'Tashrif buyuring', 'agreed_payment': 'To‘lovni oling yoki yangi sana kelishing',
           'collection_task': 'Qarzni undiring', 'visit_due': 'Tashrif buyuring',
           'prospect': 'Qayta bog‘laning'}
PRIORITY = {'agreed_visit': 1, 'agreed_payment': 1, 'collection_task': 1, 'visit_due': 2, 'prospect': 3}


def _date(value):
    try:
        return date.fromisoformat(str(value or '').strip()[:10])
    except ValueError:
        return None


def today_plan(db, agent=None, now=None, limit=25):
    """Joriy ma'lumotdan, davr filtridan mustaqil. Tashrif sanasi to'lovdan yangilanmaydi:
    tashrif = tashrif yozuvi, tovar berish yoki qaytarish; to'lov — alohida moliyaviy operatsiya."""
    now = int(time.time() if now is None else now)
    today = datetime.fromtimestamp(now, TZ).date()
    w, wa = _scope(agent)
    clients = db.execute(f"""SELECT c.id,c.agent,c.name,c.shop_name,c.region,c.created_ts,c.map_only,c.payment_due,
        u.name AS agent_name FROM clients c LEFT JOIN users u ON u.id=c.agent WHERE 1=1{w} AND COALESCE(c.blacklisted,0)=0""", wa).fetchall()
    ev = {}
    for r in db.execute(f"""SELECT e.client AS client,
            COALESCE(SUM(CASE WHEN e.kind='delivery' THEN e.amount_usd WHEN e.kind IN ('return','payment') THEN -e.amount_usd ELSE 0 END),0) AS debt,
            COALESCE(SUM(CASE WHEN e.kind='delivery' THEN 1 ELSE 0 END),0) AS deliveries,
            MAX(CASE WHEN e.kind IN ('visit','delivery','return') THEN e.ts END) AS last_visit,
            MAX(CASE WHEN e.kind='payment' THEN e.ts END) AS last_payment
            FROM events e JOIN clients c ON c.id=e.client
            WHERE e.client IS NOT NULL AND e.kind IN ('delivery','return','payment','visit'){w}
            GROUP BY e.client""", wa).fetchall():
        ev[_i(r['client'])] = r
    visits = {}
    for v in db.execute(f"""SELECT v.client AS client,v.status AS status,v.followup AS followup,v.ts AS ts FROM client_visits v
            JOIN clients c ON c.id=v.client
            WHERE v.id=(SELECT MAX(v2.id) FROM client_visits v2 WHERE v2.client=v.client){w}""", wa).fetchall():
        visits[_i(v['client'])] = v
    tw, ta = ('', [])
    if agent is not None:
        tw, ta = ' AND agent=?', [int(agent)]
    tasks = {}
    for t in db.execute(f"SELECT client,created_ts FROM collection_tasks WHERE status='open'{tw} ORDER BY created_ts", ta).fetchall():
        tasks.setdefault(_i(t['client']), t)

    items = []
    for c in clients:
        cid = _i(c['id'])
        r = ev.get(cid)
        debt = _i(r['debt']) if r else 0
        delivered = bool(r and _i(r['deliveries']))
        v = visits.get(cid)
        last_visit = max(_i(r['last_visit']) if r else 0, _i(v['ts']) if v else 0) or None
        last_payment = (_i(r['last_payment']) if r else 0) or None
        followup = _date(v['followup']) if v else None
        scheduled = followup is not None and followup > today
        reasons = []
        if followup and followup <= today and v['status'] != 'declined':
            late = (today - followup).days
            reasons.append({'code': 'agreed_visit', 'text': f"Kelishilgan tashrif: {followup:%d.%m}" + (f" ({late} kun o‘tdi)" if late else ' (bugun)')})
        due = _date(c['payment_due'])
        if due and due <= today and debt > 0:
            late = (today - due).days
            reasons.append({'code': 'agreed_payment', 'text': f"Kelishilgan to‘lov sanasi: {due:%d.%m}" + (f" ({late} kun o‘tdi)" if late else ' (bugun)')})
        if cid in tasks and debt > 0:
            reasons.append({'code': 'collection_task', 'text': 'Kassir qarzni undirishni so‘ragan'})
        if not scheduled:
            since = last_visit or _i(c['created_ts']) or None
            days = (now - since) // DAY if since else None
            if delivered and debt > 0 and days is not None and days >= TODAY['visit_due_days']:
                reasons.append({'code': 'visit_due', 'text': f"{days} kundan beri tashrif yo‘q"})
            if not delivered and (not v or v['status'] in ('interested', 'waiting')) and (days is None or days >= TODAY['prospect_days']):
                reasons.append({'code': 'prospect', 'text': 'Istiqbolli mijoz' + (f": {days} kundan beri aloqa yo‘q" if days is not None else '')})
        if not reasons:
            continue
        reasons.sort(key=lambda x: PRIORITY[x['code']])
        items.append({'clientId': cid, 'name': display_name(c), 'region': (c['region'] or '').strip() or 'Belgilanmagan',
                      'agentId': _i(c['agent']), 'agent': c['agent_name'] or str(c['agent']),
                      'priority': PRIORITY[reasons[0]['code']], 'reasons': reasons, 'action': ACTIONS[reasons[0]['code']],
                      'debtNowCents': debt, 'lastVisitTs': last_visit, 'lastPaymentTs': last_payment})
    items.sort(key=lambda i: (i['priority'], i['lastVisitTs'] or 0, -max(i['debtNowCents'], 0), i['clientId']))
    return {'asOf': now, 'items': items[:limit], 'total': len(items)}
