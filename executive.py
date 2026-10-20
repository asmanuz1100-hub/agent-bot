"""Rahbar Web — Executive dashboard (faqat o'qish).

Bitta so'rovda: tanlangan davr KPI'lari, teng uzunlikdagi oldingi davr bilan solishtirish,
savdo / pul yig'ish / qarzdorlik dinamikasi va agentlar samaradorligi.

Hisob qoidalari mavjud hisobotlar bilan bir xil (yagona manba):
- Realizatsiya = berilgan tovar − qaytarilgan tovar (USD, `manager_api._period_report` kabi).
- Yig'ilgan pul = `payment` hodisalari (USD; so'mdagi to'lov kelishilgan kurs bilan USD'ga yozilgan).
- Qarz (T paytdagi) = mavjud mijozlarning T gacha bo'lgan musbat qoldiqlari yig'indisi;
  avans (manfiy qoldiq) alohida. `manager_api.dashboard` va Kassir bilan bir xil.
- Tashrif = `client_visits` + eski `events.kind='visit'` (dashboard kabi).
Valyuta: USD va UZS qo'shilmaydi. So'mda olingan to'lov `paidUzs` sifatida alohida beriladi.
"""
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import core
from analytics import region_key

TZ = ZoneInfo('Asia/Tashkent')
DAY = 86400
PERIODS = ('today', 'yesterday', 'd7', 'd30', 'month', 'custom', 'all')
GROUPS = ('auto', 'day', 'week', 'month')


def _usd(cents):
    return round(int(cents or 0) / 100, 2)


def _midnight(ts):
    return int(datetime.fromtimestamp(ts, TZ).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


def _fmt(ts):
    return datetime.fromtimestamp(ts, TZ).strftime('%d.%m.%Y')


def resolve(db, period, date_from=None, date_to=None, now=None):
    """[start,end) va teng uzunlikdagi oldingi davr [prevStart,prevEnd). end hech qachon now+1 dan oshmaydi."""
    now = int(time.time() if now is None else now)
    period = str(period or 'today')
    if period not in PERIODS:
        raise ValueError('Davr noto‘g‘ri.')
    today = _midnight(now)
    end = now + 1
    if period == 'today':
        start, label = today, 'Bugun'
    elif period == 'yesterday':
        start, end, label = _midnight(today - 1), today, 'Kecha'
    elif period == 'd7':
        start, label = _midnight(today - 6 * DAY + 3600), 'Oxirgi 7 kun'
    elif period == 'd30':
        start, label = _midnight(today - 29 * DAY + 3600), 'Oxirgi 30 kun'
    elif period == 'month':
        d = datetime.fromtimestamp(now, TZ)
        start = int(d.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
        label = d.strftime('%m.%Y') + ' oyi'
    elif period == 'custom':
        start, end, label = core.resolve_period('custom', date_from, date_to, now)
    else:
        first = db.execute("""SELECT MIN(ts) FROM (SELECT MIN(ts) AS ts FROM events WHERE ts>0
            UNION ALL SELECT MIN(created_ts) FROM clients WHERE created_ts>0) x""").fetchone()[0]
        start, label = _midnight(int(first or today)), 'Umumiy'
    length = max(1, end - start)
    if period == 'all':
        prev = None
    elif period == 'month':
        # Joriy oy (1-sanadan bugungacha) ↔ o'tgan oyning xuddi shu kunlari.
        d = datetime.fromtimestamp(start, TZ)
        p = (d - timedelta(days=1)).replace(day=1)
        prev = (int(p.timestamp()), min(int(p.timestamp()) + length, start))
    elif period in ('today', 'd7', 'd30'):
        # Xuddi shu soatgacha solishtirish: bugun 15:00 gacha ↔ kecha 15:00 gacha, 7 kun ↔ undan oldingi 7 kun.
        shift = {'today': 1, 'd7': 7, 'd30': 30}[period] * DAY
        prev = (start - shift, end - shift)
    else:
        prev = (start - length, start)
    return {'period': period, 'start': start, 'end': end, 'label': label,
            'prevStart': prev[0] if prev else None, 'prevEnd': prev[1] if prev else None,
            'prevLabel': (_fmt(prev[0]) + ' – ' + _fmt(prev[1] - 1)) if prev else None}


class _Scope:
    """Agent va hudud filtri. Hudud — mijoz hududi (Tahlil bilan bir xil normalizatsiya)."""

    def __init__(self, db, agent=None, region=None):
        self.agent = int(agent) if agent not in (None, '', 0, '0') else None
        self.region = region_key(region) if region else None
        rows = db.execute('SELECT id,agent,region FROM clients').fetchall()
        self.clients = {int(r['id']) for r in rows
                        if (self.agent is None or int(r['agent']) == self.agent)
                        and (self.region is None or region_key(r['region']) == self.region)}
        self.region_on = self.region is not None

    def event_ok(self, agent, client):
        if self.agent is not None and int(agent or 0) != self.agent:
            return False
        if self.region_on and (client is None or int(client) not in self.clients):
            return False
        return True


def _window(db, scope, start, end):
    """Bitta oyna uchun pul/savdo/tashrif/yangi mijoz/faol agent ko'rsatkichlari."""
    s = {'deliveredCents': 0, 'returnedCents': 0, 'paymentsCents': 0, 'paidUzs': 0,
         'paidCashUsdCents': 0, 'paidCashUzsUsdCents': 0, 'paidCardCents': 0,
         'visits': 0, 'newClients': 0, 'activeAgents': set()}
    for e in db.execute("""SELECT agent,client,kind,amount_usd,pay_method,paid_uzs FROM events
            WHERE ts>=? AND ts<? AND kind IN ('delivery','return','payment','visit')""", (start, end)).fetchall():
        if not scope.event_ok(e['agent'], e['client']):
            continue
        cents = int(e['amount_usd'] or 0)
        kind = e['kind']
        if kind == 'delivery':
            s['deliveredCents'] += cents
        elif kind == 'return':
            s['returnedCents'] += cents
        elif kind == 'payment':
            s['paymentsCents'] += cents
            if (e['pay_method'] or '') == 'card':
                s['paidCardCents'] += cents
            elif int(e['paid_uzs'] or 0) > 0:
                s['paidUzs'] += int(e['paid_uzs']); s['paidCashUzsUsdCents'] += cents
            else:
                s['paidCashUsdCents'] += cents
        elif kind == 'visit':
            s['visits'] += 1
        if e['agent'] is not None and kind != 'visit':
            s['activeAgents'].add(int(e['agent']))
    for v in db.execute('SELECT actor,client FROM client_visits WHERE ts>=? AND ts<?', (start, end)).fetchall():
        if scope.event_ok(v['actor'], v['client']):
            s['visits'] += 1
            s['activeAgents'].add(int(v['actor']))
    for c in db.execute('SELECT id,agent FROM clients WHERE created_ts>=? AND created_ts<?', (start, end)).fetchall():
        if int(c['id']) in scope.clients:
            s['newClients'] += 1
    for sh in db.execute("""SELECT agent FROM shifts WHERE start<? AND COALESCE("end",?)>?""", (end, end, start)).fetchall():
        if scope.agent is None or int(sh['agent']) == scope.agent:
            if not scope.region_on:
                s['activeAgents'].add(int(sh['agent']))
    agents = {int(r['id']) for r in db.execute("SELECT id FROM users WHERE role='agent'").fetchall()}
    s['activeAgents'] = len(s['activeAgents'] & agents)
    s['realizationCents'] = s['deliveredCents'] - s['returnedCents']
    return s


def _debt_timeline(db, scope, points):
    """Har bir T (o'sib boradigan) uchun T gacha musbat qoldiqlar va avanslar yig'indisi (sentlarda)."""
    rows = db.execute("""SELECT e.client,e.ts,e.kind,e.amount_usd FROM events e JOIN clients c ON c.id=e.client
        WHERE e.kind IN ('delivery','payment','return') ORDER BY e.ts,e.id""").fetchall()
    bal = {}
    debt = adv = 0
    out = []
    i = 0
    for t in points:
        while i < len(rows) and int(rows[i]['ts'] or 0) < t:
            r = rows[i]; i += 1
            cid = int(r['client'])
            if cid not in scope.clients:
                continue
            old = bal.get(cid, 0)
            delta = int(r['amount_usd'] or 0) * (1 if r['kind'] == 'delivery' else -1)
            new = old + delta
            bal[cid] = new
            debt += max(0, new) - max(0, old)
            adv += max(0, -new) - max(0, -old)
        out.append((debt, adv))
    return out


AGING = ((0, 30, '0–30'), (31, 60, '31–60'), (61, 90, '61–90'), (91, None, '90+'))


def _debt_aging(db, scope, as_of):
    """Qarz yoshi (FIFO): to'lov va qaytarishlar eng eski yopilmagan tovar berishni yopadi.
    Qolgan qism tovar berilgan kundan `as_of`gacha bo'lgan kunlar bo'yicha guruhlanadi.
    Guruhlar yig'indisi = musbat qoldiqlar yig'indisi (umumiy qarz)."""
    rows = db.execute("""SELECT e.client,e.ts,e.kind,e.amount_usd FROM events e JOIN clients c ON c.id=e.client
        WHERE e.kind IN ('delivery','payment','return') AND e.ts<? ORDER BY e.client,e.ts,e.id""", (as_of,)).fetchall()
    out = [{'label': b[2], 'minDays': b[0], 'maxDays': b[1], 'cents': 0, 'clients': set()} for b in AGING]
    cur = None
    queue = []   # [ts, qolgan sent]
    credit = 0   # avans: keyingi tovar berishni yopadi

    def flush(cid):
        for ts, left in queue:
            if left <= 0:
                continue
            days = max(0, (as_of - int(ts)) // DAY)
            for b in out:
                if days >= b['minDays'] and (b['maxDays'] is None or days <= b['maxDays']):
                    b['cents'] += left
                    b['clients'].add(cid)
                    break
    for r in rows:
        cid = int(r['client'])
        if cid not in scope.clients:
            continue
        if cid != cur:
            if cur is not None:
                flush(cur)
            cur, queue, credit = cid, [], 0
        cents = int(r['amount_usd'] or 0)
        if r['kind'] == 'delivery':
            use = min(credit, cents)
            credit -= use
            if cents - use > 0:
                queue.append([int(r['ts']), cents - use])
        else:
            while cents > 0 and queue:
                take = min(cents, queue[0][1])
                queue[0][1] -= take
                cents -= take
                if queue[0][1] <= 0:
                    queue.pop(0)
            credit += cents
    if cur is not None:
        flush(cur)
    return [{'label': b['label'], 'minDays': b['minDays'], 'maxDays': b['maxDays'],
             'usd': _usd(b['cents']), 'clients': len(b['clients'])} for b in out]


def _conversions(db, start, end):
    """Kassir konvertatsiyalari (kassa darajasida, agent/hudud filtriga bog'liq emas).
    Dollar summasi sentda, so'm butun so'mda saqlanadi — bu yerda ko'rsatish birligiga o'tkaziladi."""
    rows = db.execute("""SELECT c.ts,c.pay_from,c.from_currency,c.amount_from,c.amount_to,c.rate_uzs_per_usd,c.note,
            COALESCE(u.name,CAST(c.cashier AS TEXT)) AS cashier
        FROM cashier_conversions c LEFT JOIN users u ON u.id=c.cashier
        WHERE c.ts>=? AND c.ts<? ORDER BY c.ts DESC,c.id DESC LIMIT 50""", (start, end)).fetchall()
    out = []
    for r in rows:
        usd_first = r['from_currency'] == 'USD'
        out.append({'ts': int(r['ts']), 'payFrom': r['pay_from'], 'from': r['from_currency'], 'to': 'UZS' if usd_first else 'USD',
                    'amountFrom': _usd(r['amount_from']) if usd_first else int(r['amount_from']),
                    'amountTo': int(r['amount_to']) if usd_first else _usd(r['amount_to']),
                    'rate': int(r['rate_uzs_per_usd']), 'cashier': r['cashier'], 'note': r['note'] or ''})
    return out


def _agents_cash(db, scope):
    """Agentlardagi pul: dollar va so'm alohida (hech qachon qo'shilmaydi) va kassirda tasdiq kutayotgani."""
    rows = db.execute("SELECT id,name FROM users WHERE role='agent' ORDER BY name,id").fetchall()
    out = {'cashUsd': 0, 'cashUzs': 0, 'pendingUsd': 0, 'pendingUzs': 0, 'agents': []}
    for u in rows:
        aid = int(u['id'])
        if scope.agent is not None and aid != scope.agent:
            continue
        # PostgreSQL SUM() Decimal qaytaradi — JSON uchun butun songa o'tkaziladi.
        usd_c = int(core.cash_usd(db, aid))
        som = int(core.cash_som(db, aid))
        pend = db.execute("""SELECT COALESCE(SUM(CASE WHEN COALESCE(amount,0)=0 THEN amount_usd ELSE 0 END),0),
            COALESCE(SUM(amount),0) FROM handovers WHERE agent=? AND status='pending'""", (aid,)).fetchone()
        p_usd, p_uzs = int(pend[0] or 0), int(pend[1] or 0) // 100
        out['cashUsd'] += usd_c; out['cashUzs'] += som; out['pendingUsd'] += p_usd; out['pendingUzs'] += p_uzs
        if usd_c or som or p_usd or p_uzs:
            out['agents'].append({'agentId': aid, 'agent': u['name'] or str(aid), 'cashUsd': _usd(usd_c), 'cashUzs': som,
                                  'pendingUsd': _usd(p_usd), 'pendingUzs': p_uzs})
    out['agents'].sort(key=lambda a: (-a['cashUsd'], -a['cashUzs'], a['agent']))
    out['cashUsd'] = _usd(out['cashUsd']); out['pendingUsd'] = _usd(out['pendingUsd'])
    out['regionApplies'] = False  # pul agentda turadi, hududga bog'lanmaydi
    return out


def _buckets(start, end, group):
    days = (end - start + DAY - 1) // DAY
    if group == 'auto':
        group = 'hour' if end - start <= DAY else 'day' if days <= 45 else 'week' if days <= 200 else 'month'
    out = []
    cur = start
    while cur < end:
        d = datetime.fromtimestamp(cur, TZ)
        if group == 'hour':
            nxt = cur + 3600
            label = d.strftime('%H:00')
        elif group == 'day':
            nxt = _midnight(cur + DAY + 3600)
            label = d.strftime('%d.%m')
        elif group == 'week':
            nxt = _midnight(cur + 7 * DAY + 3600)
            label = d.strftime('%d.%m')
        else:
            nxt = int((d.replace(day=1) + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
            label = d.strftime('%m.%Y')
        nxt = min(nxt, end)
        out.append((cur, nxt, label))
        cur = nxt
        if len(out) > 400:
            break
    return out, group


def _delta(cur, prev):
    if prev is None:
        return None
    if prev == 0:
        return None if cur == 0 else {'kind': 'new'}
    return {'kind': 'pct', 'pct': round((cur - prev) * 100.0 / abs(prev), 1)}


def executive(db, period='today', date_from=None, date_to=None, agent=None, region=None, group='auto', now=None):
    now = int(time.time() if now is None else now)
    if group not in GROUPS:
        raise ValueError('Guruhlash noto‘g‘ri.')
    rng = resolve(db, period, date_from, date_to, now)
    scope = _Scope(db, agent, region)
    cur = _window(db, scope, rng['start'], rng['end'])
    prev = _window(db, scope, rng['prevStart'], rng['prevEnd']) if rng['prevStart'] is not None else None

    buckets, group = _buckets(rng['start'], rng['end'], group)
    debt_points = [b[1] for b in buckets] + [rng['start']] + ([rng['prevStart']] if rng['prevStart'] else [])
    order = sorted(set(debt_points))
    timeline = dict(zip(order, _debt_timeline(db, scope, order)))
    debt_end, adv_end = timeline[buckets[-1][1]] if buckets else (0, 0)
    debt_start = timeline[rng['start']][0]

    series = []
    events = db.execute("""SELECT agent,client,kind,amount_usd,ts FROM events
        WHERE ts>=? AND ts<? AND kind IN ('delivery','return','payment')""", (rng['start'], rng['end'])).fetchall()
    sums = [[0, 0, 0] for _ in buckets]
    starts = [b[0] for b in buckets]
    import bisect
    for e in events:
        if not scope.event_ok(e['agent'], e['client']):
            continue
        k = bisect.bisect_right(starts, int(e['ts'])) - 1
        if k < 0:
            continue
        idx = {'delivery': 0, 'return': 1, 'payment': 2}[e['kind']]
        sums[k][idx] += int(e['amount_usd'] or 0)
    for (a, b, label), (d, r, p) in zip(buckets, sums):
        series.append({'day': label, 'start': a, 'end': b, 'realizationUsd': _usd(d - r), 'paymentsUsd': _usd(p),
                       'returnsUsd': _usd(r), 'debtUsd': _usd(timeline[b][0])})

    # Agentlar samaradorligi (tanlangan davr).
    names = {int(u['id']): u['name'] for u in db.execute("SELECT id,name FROM users WHERE role='agent'").fetchall()}
    perf = {}
    for e in events:
        if not scope.event_ok(e['agent'], e['client']) or int(e['agent'] or 0) not in names:
            continue
        a = perf.setdefault(int(e['agent']), [0, 0, 0])
        a[{'delivery': 0, 'return': 1, 'payment': 2}[e['kind']]] += int(e['amount_usd'] or 0)
    visits = {}
    for v in db.execute('SELECT actor,client FROM client_visits WHERE ts>=? AND ts<?', (rng['start'], rng['end'])).fetchall():
        if scope.event_ok(v['actor'], v['client']):
            visits[int(v['actor'])] = visits.get(int(v['actor']), 0) + 1
    agents = []
    for aid, name in names.items():
        if scope.agent is not None and aid != scope.agent:
            continue
        d, r, p = perf.get(aid, (0, 0, 0))
        agents.append({'agentId': aid, 'agent': name or str(aid), 'realizationUsd': _usd(d - r),
                       'paymentsUsd': _usd(p), 'visits': visits.get(aid, 0),
                       'collectionPct': round(p * 100.0 / (d - r), 1) if d - r > 0 else None})
    agents.sort(key=lambda a: (-a['realizationUsd'], -a['paymentsUsd'], a['agent']))

    # Hududlar bo'yicha savdo (tanlangan davr, mijoz hududi bo'yicha).
    creg = {int(r['id']): r['region'] for r in db.execute('SELECT id,region FROM clients').fetchall()}
    by_region = {}
    for e in events:
        if not scope.event_ok(e['agent'], e['client']) or e['client'] is None:
            continue
        raw = creg.get(int(e['client']))
        if raw is None:
            continue
        key = region_key(raw) or ''
        g = by_region.setdefault(key, {'key': key, 'name': (raw or '').strip() or 'Belgilanmagan', 'd': 0, 'r': 0, 'p': 0})
        g[{'delivery': 'd', 'return': 'r', 'payment': 'p'}[e['kind']]] += int(e['amount_usd'] or 0)
    region_sales = sorted(({'key': g['key'], 'name': g['name'], 'realizationUsd': _usd(g['d'] - g['r']), 'paymentsUsd': _usd(g['p'])}
                           for g in by_region.values()), key=lambda x: (-x['realizationUsd'], x['name']))

    # Oy kalendari (davr oxiri tushgan oy, kunma-kun realizatsiya va pul) — o'ng paneldagi kalendar uchun.
    last = datetime.fromtimestamp(min(rng['end'], now + 1) - 1, TZ)
    m0 = int(last.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
    m1 = int((last.replace(day=1) + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
    cal = {}
    for e in db.execute("""SELECT agent,client,kind,amount_usd,ts FROM events
            WHERE ts>=? AND ts<? AND kind IN ('delivery','return','payment')""", (m0, min(m1, now + 1))).fetchall():
        if not scope.event_ok(e['agent'], e['client']):
            continue
        day = datetime.fromtimestamp(int(e['ts']), TZ).day
        c = cal.setdefault(day, [0, 0])
        if e['kind'] == 'payment':
            c[1] += int(e['amount_usd'] or 0)
        else:
            c[0] += int(e['amount_usd'] or 0) * (1 if e['kind'] == 'delivery' else -1)
    calendar = {'year': last.year, 'month': last.month, 'firstWeekday': datetime.fromtimestamp(m0, TZ).weekday(),
                'days': (datetime.fromtimestamp(m1 - 1, TZ)).day,
                'values': {str(k): {'realizationUsd': _usd(v[0]), 'paymentsUsd': _usd(v[1])} for k, v in cal.items()}}

    def kpi(key, cur_v, prev_v, money=True):
        return {'key': key, 'value': _usd(cur_v) if money else cur_v,
                'prev': (_usd(prev_v) if money else prev_v) if prev_v is not None else None,
                'delta': _delta(cur_v, prev_v)}
    regions = {}
    for r in db.execute('SELECT region FROM clients').fetchall():
        key = region_key(r['region'])
        if key:
            regions.setdefault(key, (r['region'] or '').strip())
    return {
        'range': rng, 'group': group, 'generatedTs': now,
        'filters': {'agentId': scope.agent, 'region': region or '', 'regionKey': scope.region},
        'kpis': [
            kpi('realization', cur['realizationCents'], prev['realizationCents'] if prev else None),
            kpi('collected', cur['paymentsCents'], prev['paymentsCents'] if prev else None),
            kpi('debt', debt_end, debt_start if prev else None),
            kpi('activeAgents', cur['activeAgents'], prev['activeAgents'] if prev else None, money=False),
            kpi('newClients', cur['newClients'], prev['newClients'] if prev else None, money=False),
            kpi('visits', cur['visits'], prev['visits'] if prev else None, money=False),
        ],
        'advanceUsd': _usd(adv_end),
        'collections': {'cashUsd': _usd(cur['paidCashUsdCents']), 'cashUzs': cur['paidUzs'],
                        'cashUzsAsUsd': _usd(cur['paidCashUzsUsdCents']), 'cardUsd': _usd(cur['paidCardCents']),
                        'returnsUsd': _usd(cur['returnedCents']), 'grossDeliveredUsd': _usd(cur['deliveredCents'])},
        'series': series, 'agents': agents,
        'debtAging': _debt_aging(db, scope, rng['end']), 'agentsCash': _agents_cash(db, scope),
        'regionSales': region_sales, 'calendar': calendar,
        'conversions': _conversions(db, rng['start'], rng['end']),
        'options': {'agents': [{'id': k, 'name': v or str(k)} for k, v in sorted(names.items(), key=lambda kv: (kv[1] or '', kv[0]))],
                    'regions': [{'key': k, 'name': v} for k, v in sorted(regions.items(), key=lambda kv: kv[1])]},
    }
