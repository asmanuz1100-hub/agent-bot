"""Hududlar, mijozlar va mahsulotlar hisoboti (Rahbar va Agent ilovalari).

Ma'nolar (core.record bilan bir xil, USD sentda, butun son):
  * delivery  — mijozga berilgan tovar (konsignatsiya). Mijoz qarzi shu paytda yoziladi.
  * sold      — mijoz shu tovarni sotgani tasdiqlandi = REALIZATSIYA. Qiymati asl partiya
                narxida (FIFO); qarzni o'zgartirmaydi.
  * return    — mijozdagi SOTILMAGAN tovar qaytdi (core faqat qoldiqdagi tovarni qaytaradi).
                Qarzni kamaytiradi, realizatsiyadan ayirilmaydi.
  * payment   — mijoz to'lovi, qarzni kamaytiradi.
  Qarz(t)          = sum(delivery) - sum(payment) - sum(return), ts < t. Manfiy = avans.
  Mijozdagi qoldiq = delivery - sold - return (dona va partiya qiymati).

Davr hisobotidagi qarz — davr OXIRIDAGI qoldiq. Bugungi qarz alohida: debtNowCents.
Qarz yoshi uchun to'lov muddati ma'lumoti yo'q: faqat "eng eski to'lanmagan yuk necha kun
oldin berilgan" (to'lov va qaytarishlarni eng eski yuklarga FIFO taqsimlab, taxminiy) va
"oxirgi to'lovdan beri" ko'rsatiladi. "Muddati o'tgan" deb belgilanmaydi.

Agentga bog'lash: c.agent — mijozning joriy egasi (portfel, undirish mas'uliyati);
e.agent — operatsiyani bajargan agent. Mijoz ro'yxati, qarz va "Bugun kimga" portfel
bo'yicha; agentlar jadvalidagi "operatsiyalar" esa e.agent bo'yicha alohida beriladi.
"""
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import core

TZ = ZoneInfo('Asia/Tashkent')
DAY = 86400
GROWTH_PCT = 15          # realizatsiya shuncha % o'ssa — "O'sayotgan"
DECLINE_PCT = -25        # shuncha % tushsa — "E'tibor kerak"
VISIT_DUE_DAYS = 5       # ilovadagi qizil belgi bilan bir xil
STOCK_CHECK_DAYS = 21
PROSPECT_DAYS = 14
TODAY_WINDOW_DAYS = 28
TODAY_DROP_PCT = -40
NO_NAME = {'йўқ', 'йук', 'йок', 'йўк', 'нет', 'yoq', "yo'q", 'yo‘q', 'yok', '-', '—', '–', '.', '0',
           'no', 'none', 'null', 'номаълум'}


def _day_start(ts):
    return datetime.fromtimestamp(ts, TZ).replace(hour=0, minute=0, second=0, microsecond=0)


def _fmt(dt):
    return dt.strftime('%d.%m.%Y')


def period_bounds(period, date_from=None, date_to=None, now=None):
    """[start,end) va teng davomiylikdagi oldingi davr [prev_start,prev_end), Asia/Tashkent."""
    now = int(time.time() if now is None else now)
    today = _day_start(now)
    period = str(period or 'month')
    if period == 'today':
        start = today
        prev = today - timedelta(days=1)
        name = 'Bugun'
        cmp_name = 'Kecha shu vaqtgacha'
    elif period == 'week':
        start = today - timedelta(days=6)
        prev = start - timedelta(days=7)
        name = 'Oxirgi 7 kun (kalendar hafta emas)'
        cmp_name = 'Oldingi 7 kun'
    elif period == 'month':
        start = today.replace(day=1)
        prev = (start - timedelta(days=1)).replace(day=1)
        name = 'Shu oy'
        cmp_name = 'O‘tgan oyning shu kunlari'
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
        cmp_name = 'Oldingi teng davr'
    else:
        raise ValueError('Davr noto‘g‘ri.')
    s = int(start.timestamp())
    if period == 'custom':
        e = min(int((b + timedelta(days=1)).timestamp()), now + 1)
    else:
        e = now + 1
    if e <= s:
        raise ValueError('Davr hali boshlanmagan.')
    ps = int(prev.timestamp())
    pe = min(ps + (e - s), s)
    last_day = datetime.fromtimestamp(e - 1, TZ)
    prev_last = datetime.fromtimestamp(pe - 1, TZ)
    return {'period': period, 'start': s, 'end': e, 'prevStart': ps, 'prevEnd': pe,
            'complete': e <= now, 'equalCompare': (pe - ps) == (e - s),
            'label': f"{name}: {_fmt(start)} – {_fmt(last_day)}" + ('' if e <= now else f" ({last_day:%H:%M} gacha)"),
            'compareLabel': f"{cmp_name}: {_fmt(prev)} – {_fmt(prev_last)}" + ('' if e <= now else f" ({prev_last:%H:%M} gacha)")}


def region_key(name):
    """Agent ilovasidagi regionKey() bilan bir xil normalizatsiya."""
    key = ' '.join(str(name or '').strip().lower().replace('‘', '').replace('’', '').replace('ʻ', '')
                   .replace('\x60', '').replace('´', '').replace("'", '').split())
    return 'yaypan' if key == 'yapan' else key


def display_name(c):
    shop = (c['shop_name'] or '').strip()
    person = (c['name'] or '').strip()
    for value in (shop, person):
        if value and value.lower() not in NO_NAME:
            return value
    return f"Mijoz #{int(c['id'])}"


def _bucket():
    return {'delivered': 0, 'deliveredQty': 0, 'sold': 0, 'soldQty': 0, 'soldEvents': 0, 'soldNoPriceQty': 0,
            'returned': 0, 'returnedQty': 0, 'paid': 0, 'payments': 0}


def _add(b, e):
    kind = e['kind']
    usd = int(e['amount_usd'] or 0)
    qty = int(e['qty'] or 0)
    if kind == 'delivery':
        b['delivered'] += usd
        b['deliveredQty'] += qty
    elif kind == 'sold':
        b['sold'] += usd
        b['soldQty'] += qty
        b['soldEvents'] += 1
        if usd <= 0:
            b['soldNoPriceQty'] += qty
    elif kind == 'return':
        b['returned'] += usd
        b['returnedQty'] += qty
    elif kind == 'payment':
        b['paid'] += usd
        b['payments'] += 1


def _realization(b):
    """Davrda "Sotildi" yozuvi bo'lmasa — ma'lumot yo'q (None), 0 emas."""
    return b['sold'] if b['soldEvents'] else None


def growth(cur, prev):
    """O'sish faqat ikkala davrda ham ma'lumot bo'lsa foizda."""
    if cur is None and prev is None:
        return {'kind': 'noData', 'pct': None, 'text': 'Ma’lumot yetarli emas'}
    if (prev or 0) <= 0 and (cur or 0) > 0:
        return {'kind': 'started', 'pct': None, 'text': 'Bu davrda savdo boshlandi'}
    if prev is not None and prev > 0 and cur is None:
        return {'kind': 'noCurrent', 'pct': None, 'text': 'Bu davrda realizatsiya yozilmagan'}
    if cur is None or prev is None:
        return {'kind': 'noData', 'pct': None, 'text': 'Ma’lumot yetarli emas'}
    if prev > 0:
        pct = round((cur - prev) * 100.0 / prev, 1)
        return {'kind': 'pct', 'pct': pct, 'text': f"{'▲' if pct >= 0 else '▼'}{abs(pct):.0f}%"}
    return {'kind': 'zero', 'pct': None, 'text': 'Ikkala davrda ham 0'}


def _load(db, agent):
    args = []
    where = ''
    if agent is not None:
        where = ' WHERE c.agent=?'
        args.append(int(agent))
    clients = db.execute(f"""SELECT c.id,c.agent,c.name,c.shop_name,c.region,c.created_ts,c.map_only,
        c.payment_due,u.name AS agent_name FROM clients c LEFT JOIN users u ON u.id=c.agent{where}
        ORDER BY c.id""", args).fetchall()
    events = db.execute(f"""SELECT e.id,e.client,e.agent,e.kind,e.pack,e.qty,e.amount,e.amount_usd,e.ts
        FROM events e JOIN clients c ON c.id=e.client
        WHERE e.kind IN ('delivery','sold','return','payment'){where.replace(' WHERE', ' AND')}
        ORDER BY e.ts,e.id""", args).fetchall()
    return clients, events


def _client_ledgers(clients, events, b):
    start, end, ps, pe = b['start'], b['end'], b['prevStart'], b['prevEnd']
    led = {}
    for c in clients:
        led[int(c['id'])] = {'cur': _bucket(), 'prev': _bucket(), 'debtEnd': 0, 'debtNow': 0, 'stockQty': 0,
                             'stockValue': 0, 'deliveries': [], 'credits': 0, 'firstDelivery': None,
                             'lastDelivery': None, 'lastPayment': None, 'lastSold': None, 'soldEver': False,
                             'legacyUzs': 0, 'packs': {}}
    for e in events:
        x = led.get(int(e['client']))
        if x is None:
            continue
        kind = e['kind']
        ts = int(e['ts'] or 0)
        usd = int(e['amount_usd'] or 0)
        qty = int(e['qty'] or 0)
        sign = 1 if kind == 'delivery' else -1 if kind in ('payment', 'return') else 0
        x['debtNow'] += sign * usd
        if kind in ('sold', 'payment') and usd == 0 and int(e['amount'] or 0) > 0:
            x['legacyUzs'] += 1        # eski so'mdagi yozuv: USD hisobga kirmaydi
        if ts >= end:
            continue
        x['debtEnd'] += sign * usd
        if kind == 'delivery':
            x['stockQty'] += qty
            x['stockValue'] += usd
            x['deliveries'].append((ts, usd))
            x['firstDelivery'] = ts if x['firstDelivery'] is None else x['firstDelivery']
            x['lastDelivery'] = ts
        elif kind in ('sold', 'return'):
            x['stockQty'] -= qty
            x['stockValue'] -= usd
        if kind in ('payment', 'return'):
            x['credits'] += usd
        if kind == 'payment':
            x['lastPayment'] = ts
        if kind == 'sold':
            x['lastSold'] = ts
            x['soldEver'] = True
        if start <= ts < end:
            _add(x['cur'], e)
            if int(e['pack'] or 0) > 0:
                _add(x['packs'].setdefault(int(e['pack']), _bucket()), e)
        elif ps <= ts < pe:
            _add(x['prev'], e)
    return led


def oldest_open(deliveries, credits):
    """FIFO: to'lov va qaytarishlar eng eski yuklarni yopadi; birinchi ochiq yuk sanasi."""
    left = credits
    for ts, amount in deliveries:
        if left >= amount:
            left -= amount
            continue
        return ts
    return None


def _payment_info(x, ref):
    debt = x['debtEnd']
    paid = x['cur']['paid']
    oldest = oldest_open(x['deliveries'], x['credits']) if debt > 0 else None
    if debt < 0:
        code, text = 'advance', 'Avans (oldindan to‘langan)'
    elif debt == 0:
        code, text = 'clear', 'Qarzi yo‘q'
    elif paid > 0:
        code, text = 'paying', 'Qarz bor · davrda to‘lov qilgan'
    else:
        code, text = 'unpaid', 'Qarz bor · davrda to‘lov yo‘q'
    return {'code': code, 'text': text, 'debtEndCents': debt, 'paidCents': paid,
            'lastPaymentDays': (ref - x['lastPayment']) // DAY if x['lastPayment'] else None,
            'oldestOpenDays': (ref - oldest) // DAY if oldest else None}


def insights(db, period='month', date_from=None, date_to=None, agent=None, now=None):
    """Davr hisoboti. agent berilsa — faqat shu agent portfelidagi mijozlar (c.agent)."""
    now = int(time.time() if now is None else now)
    b = period_bounds(period, date_from, date_to, now)
    ref = min(b['end'] - 1, now)
    clients, events = _load(db, agent)
    led = _client_ledgers(clients, events, b)

    rows = []
    for c in clients:
        cid = int(c['id'])
        x = led[cid]
        cur, prev = x['cur'], x['prev']
        prospect = x['firstDelivery'] is None
        new = (not prospect) and b['start'] <= x['firstDelivery'] < b['end']
        real, prev_real = _realization(cur), _realization(prev)
        g = {'kind': 'new', 'pct': None, 'text': 'Yangi mijoz — taqqoslanmaydi'} if new else growth(real, prev_real)
        tags = []
        attention = []
        if prospect:
            tags.append('prospect')
        else:
            if new:
                tags.append('new')
            elif g['kind'] == 'started' or (g['kind'] == 'pct' and g['pct'] >= GROWTH_PCT):
                tags.append('growing')
            if not new:
                if g['kind'] == 'pct' and g['pct'] <= DECLINE_PCT:
                    attention.append(f"Realizatsiya {g['text']} ({b['compareLabel'].split(':')[0].lower()}ga nisbatan)")
                elif g['kind'] == 'noCurrent':
                    attention.append('Oldingi davrda sotgan, bu davrda “Sotildi” yozilmagan')
            if x['stockQty'] > 0 and not x['soldEver']:
                tags.append('noSalesData')
            if attention:
                tags.append('attention')
        active = cur['delivered'] > 0 or cur['soldEvents'] > 0
        rows.append({
            'id': cid, 'name': display_name(c), 'person': (c['name'] or '').strip(),
            'region': (c['region'] or '').strip() or 'Belgilanmagan', 'regionKey': region_key(c['region']) or '',
            'agentId': int(c['agent']), 'agent': c['agent_name'] or str(c['agent']),
            'prospect': prospect, 'mapOnly': bool(c['map_only']), 'new': new, 'active': active,
            'realizationCents': real, 'realizationPartial': cur['soldNoPriceQty'] > 0, 'soldQty': cur['soldQty'],
            'prevRealizationCents': prev_real, 'growth': g,
            'deliveredCents': cur['delivered'], 'deliveredQty': cur['deliveredQty'],
            'prevDeliveredCents': prev['delivered'],
            'returnedCents': cur['returned'], 'returnedQty': cur['returnedQty'],
            'payment': _payment_info(x, ref), 'debtNowCents': x['debtNow'],
            'stockQty': x['stockQty'], 'stockValueCents': x['stockValue'],
            'lastSoldDays': (ref - x['lastSold']) // DAY if x['lastSold'] else None,
            'lastDeliveryDays': (ref - x['lastDelivery']) // DAY if x['lastDelivery'] else None,
            'tags': tags, 'attention': attention, 'legacyUzsEvents': x['legacyUzs']})

    rated = [r for r in rows if not r['prospect']]
    rated.sort(key=lambda r: (r['realizationCents'] is None, -(r['realizationCents'] or 0),
                              -r['deliveredCents'], r['id']))
    for i, r in enumerate(rated):
        r['rank'] = i + 1 if r['realizationCents'] is not None else None

    # Hududlar
    regions = {}
    for r in rows:
        key = r['regionKey'] or ''
        g = regions.setdefault(key, {'names': {}, 'clients': 0, 'active': 0, 'new': 0, 'prospects': 0,
                                     'real': 0, 'realKnown': 0, 'prevReal': 0, 'prevKnown': 0, 'delivered': 0,
                                     'prevDelivered': 0, 'paid': 0, 'debt': 0, 'ids': []})
        g['names'][r['region']] = g['names'].get(r['region'], 0) + 1
        g['clients'] += 1
        g['ids'].append(r)
        if r['prospect']:
            g['prospects'] += 1
            continue
        g['active'] += 1 if r['active'] else 0
        g['new'] += 1 if r['new'] else 0
        if r['realizationCents'] is not None:
            g['real'] += r['realizationCents']
            g['realKnown'] += 1
        if r['prevRealizationCents'] is not None:
            g['prevReal'] += r['prevRealizationCents']
            g['prevKnown'] += 1
        g['delivered'] += r['deliveredCents']
        g['prevDelivered'] += r['prevDeliveredCents']
        g['paid'] += r['payment']['paidCents']
        g['debt'] += r['payment']['debtEndCents']
    total_real = sum(g['real'] for g in regions.values())
    region_list = []
    for key, g in regions.items():
        real = g['real'] if g['realKnown'] else None
        prev_real = g['prevReal'] if g['prevKnown'] else None
        name = 'Belgilanmagan' if not key else max(g['names'].items(), key=lambda kv: (kv[1], kv[0]))[0]
        members = sorted(g['ids'], key=lambda r: (r['prospect'], r['realizationCents'] is None,
                                                  -(r['realizationCents'] or 0), -r['deliveredCents'], r['id']))
        region_list.append({
            'key': key or '-', 'name': name, 'clients': g['clients'], 'activeClients': g['active'],
            'newClients': g['new'], 'prospects': g['prospects'],
            'realizationCents': real, 'deliveredCents': g['delivered'], 'paidCents': g['paid'],
            'debtEndCents': g['debt'],
            'realizationPerActiveCents': (real // g['active']) if (real is not None and g['active']) else None,
            'sharePct': round(real * 100.0 / total_real, 1) if (real and total_real > 0) else 0.0,
            'growth': growth(real, prev_real), 'deliveredGrowth': growth(g['delivered'] or None, g['prevDelivered'] or None),
            'clientIds': [r['id'] for r in members]})
    region_list.sort(key=lambda x: (x['realizationCents'] is None, -(x['realizationCents'] or 0),
                                    -x['deliveredCents'], x['name']))

    # Mahsulotlar (shu mijozlar to'plami, shu davr)
    names = {int(r['pack']): r['name'] for r in db.execute('SELECT pack,name FROM products').fetchall()}
    packs = {}
    for x in led.values():
        for pack, pb in x['packs'].items():
            t = packs.setdefault(pack, _bucket())
            for k in t:
                t[k] += pb[k]
    product_list = [{'pack': p, 'name': names.get(p) or core.product_name(p),
                     'deliveredCents': t['delivered'], 'deliveredQty': t['deliveredQty'],
                     'realizationCents': _realization(t), 'soldQty': t['soldQty'],
                     'returnedCents': t['returned'], 'returnedQty': t['returnedQty']} for p, t in packs.items()]
    product_list.sort(key=lambda p: (-(p['realizationCents'] or 0), -p['deliveredCents'], p['pack']))

    # Agentlar: portfel (c.agent) va operatsiyalar (e.agent) alohida
    portfolio = {}
    for r in rows:
        a = portfolio.setdefault(r['agentId'], {'agentId': r['agentId'], 'agent': r['agent'], 'clients': 0,
                                                'activeClients': 0, 'newClients': 0, 'prospects': 0,
                                                'realizationCents': 0, 'realizationKnown': 0,
                                                'debtEndCents': 0, 'growing': 0, 'attention': 0})
        a['clients'] += 1
        if r['prospect']:
            a['prospects'] += 1
            continue
        a['activeClients'] += 1 if r['active'] else 0
        a['newClients'] += 1 if r['new'] else 0
        a['debtEndCents'] += r['payment']['debtEndCents']
        a['growing'] += 1 if 'growing' in r['tags'] else 0
        a['attention'] += 1 if 'attention' in r['tags'] else 0
        if r['realizationCents'] is not None:
            a['realizationCents'] += r['realizationCents']
            a['realizationKnown'] += 1
    op_args = [b['start'], b['end']]
    op_where = ''
    if agent is not None:
        op_where = ' AND agent=?'
        op_args.append(int(agent))
    ops = {}
    for o in db.execute(f"""SELECT agent,kind,COALESCE(SUM(amount_usd),0) AS usd,COUNT(*) AS n FROM events
            WHERE ts>=? AND ts<? AND client IS NOT NULL AND kind IN ('delivery','sold','return','payment'){op_where}
            GROUP BY agent,kind""", op_args).fetchall():
        ops.setdefault(int(o['agent']), {})[o['kind']] = int(o['usd'] or 0)
    agent_names = {int(u['id']): u['name'] for u in db.execute("SELECT id,name FROM users").fetchall()}
    agents = []
    for aid in sorted(set(portfolio) | set(ops)):
        p = portfolio.get(aid) or {'agentId': aid, 'agent': agent_names.get(aid) or str(aid), 'clients': 0,
                                   'activeClients': 0, 'newClients': 0, 'prospects': 0, 'realizationCents': 0,
                                   'realizationKnown': 0, 'debtEndCents': 0, 'growing': 0, 'attention': 0}
        o = ops.get(aid, {})
        p = dict(p)
        if not p['realizationKnown']:
            p['realizationCents'] = None
        p['operations'] = {'deliveredCents': o.get('delivery', 0), 'realizationCents': o.get('sold', 0),
                           'returnedCents': o.get('return', 0), 'paidCents': o.get('payment', 0)}
        agents.append(p)
    agents.sort(key=lambda a: (-(a['operations']['realizationCents']), -(a['realizationCents'] or 0), a['agentId']))

    real_known = [r['realizationCents'] for r in rated if r['realizationCents'] is not None]
    summary = {
        'totalClients': len(rows), 'ratedClients': len(rated), 'prospects': len(rows) - len(rated),
        'activeClients': sum(1 for r in rated if r['active']), 'newClients': sum(1 for r in rated if r['new']),
        'realizationCents': sum(real_known) if real_known else None,
        'realizationClients': len(real_known),
        'deliveredCents': sum(r['deliveredCents'] for r in rated),
        'returnedCents': sum(r['returnedCents'] for r in rated),
        'paidCents': sum(r['payment']['paidCents'] for r in rated),
        'debtEndCents': sum(r['payment']['debtEndCents'] for r in rated if r['payment']['debtEndCents'] > 0),
        'advanceCents': -sum(r['payment']['debtEndCents'] for r in rated if r['payment']['debtEndCents'] < 0),
        'debtNowCents': sum(r['debtNowCents'] for r in rated if r['debtNowCents'] > 0),
        'growing': sum(1 for r in rated if 'growing' in r['tags']),
        'attention': sum(1 for r in rated if 'attention' in r['tags']),
        'paymentStatus': {k: sum(1 for r in rated if r['payment']['code'] == k)
                          for k in ('clear', 'advance', 'paying', 'unpaid')}}
    quality = {
        'noRegionClients': sum(1 for r in rows if not r['regionKey']),
        'noSalesDataClients': sum(1 for r in rows if 'noSalesData' in r['tags']),
        'soldWithoutPriceQty': sum(led[r['id']]['cur']['soldNoPriceQty'] for r in rows),
        'legacyUzsEvents': sum(r['legacyUzsEvents'] for r in rows),
        'notes': ['Realizatsiya faqat “Sotildi” yozuvlaridan olinadi; yozuv bo‘lmasa “ma’lumot yo‘q”.',
                  'To‘lov muddati yozilmagani uchun qarz “muddati o‘tgan” deb baholanmaydi.',
                  'Eski so‘mdagi (USD narxsiz) yozuvlar USD hisobga qo‘shilmaydi.']}
    return {'period': b['period'], 'label': b['label'], 'compareLabel': b['compareLabel'],
            'start': b['start'], 'end': b['end'], 'prevStart': b['prevStart'], 'prevEnd': b['prevEnd'],
            'complete': b['complete'], 'equalCompare': b['equalCompare'],
            'scope': {'agentId': int(agent) if agent is not None else None,
                      'clients': 'portfel (mijozning joriy agenti)',
                      'operations': 'operatsiyani bajargan agent'},
            'summary': summary, 'regions': region_list, 'clients': rated + [r for r in rows if r['prospect']],
            'products': product_list, 'agents': agents, 'quality': quality,
            'rules': {'growthPct': GROWTH_PCT, 'declinePct': DECLINE_PCT}}


# ---------------------------------------------------------------- Bugun kimga

ACTIONS = {
    'agreed_visit': 'Tashrif buyuring va natijasini yozing',
    'agreed_payment': 'To‘lovni oling yoki yangi sana kelishing',
    'collection_task': 'Qarzni undiring va natijani yozing',
    'sales_drop': 'Sababini so‘rang: narx, raqobatchi yoki qoldiq',
    'visit_due': 'Tashrif buyuring',
    'stock_check': 'Qoldiqni sanang va sotilganini “Sotildi” bilan yozing',
    'prospect': 'Qayta bog‘laning va taklif bering',
}
PRIORITY = {'agreed_visit': 1, 'agreed_payment': 1, 'collection_task': 1, 'sales_drop': 2,
            'visit_due': 3, 'stock_check': 4, 'prospect': 5}


def _date(value):
    try:
        return date.fromisoformat(str(value or '').strip()[:10])
    except ValueError:
        return None


def today_plan(db, agent=None, now=None, limit=25):
    """Bugungi tavsiyalar — faqat joriy ma'lumotdan, davr filtridan mustaqil."""
    now = int(time.time() if now is None else now)
    today = datetime.fromtimestamp(now, TZ).date()
    args = []
    where = ''
    if agent is not None:
        where = ' WHERE c.agent=?'
        args.append(int(agent))
    clients = db.execute(f"""SELECT c.id,c.agent,c.name,c.shop_name,c.region,c.created_ts,c.map_only,c.payment_due,
        u.name AS agent_name FROM clients c LEFT JOIN users u ON u.id=c.agent{where}""", args).fetchall()
    ids = {int(c['id']) for c in clients}
    latest = {}
    for v in db.execute("""SELECT v.client,v.status,v.followup,v.ts FROM client_visits v
            WHERE v.id=(SELECT MAX(v2.id) FROM client_visits v2 WHERE v2.client=v.client)""").fetchall():
        latest[int(v['client'])] = v
    contact = {}
    for v in db.execute("SELECT client,MAX(ts) AS ts FROM client_visits GROUP BY client").fetchall():
        contact[int(v['client'])] = int(v['ts'] or 0)
    w0, w1 = now - 2 * TODAY_WINDOW_DAYS * DAY, now - TODAY_WINDOW_DAYS * DAY
    led = {}
    for e in db.execute("""SELECT client,kind,qty,amount_usd,ts FROM events
            WHERE client IS NOT NULL AND kind IN ('delivery','sold','return','payment','visit')""").fetchall():
        cid = int(e['client'])
        if cid not in ids:
            continue
        x = led.setdefault(cid, {'debt': 0, 'stock': 0, 'delivered': False, 'lastSold': None,
                                 'recent': 0, 'before': 0, 'recentN': 0, 'beforeN': 0})
        kind, usd, qty, ts = e['kind'], int(e['amount_usd'] or 0), int(e['qty'] or 0), int(e['ts'] or 0)
        if kind != 'sold':
            contact[cid] = max(contact.get(cid, 0), ts)
        if kind == 'delivery':
            x['debt'] += usd
            x['stock'] += qty
            x['delivered'] = True
        elif kind in ('payment', 'return'):
            x['debt'] -= usd
            if kind == 'return':
                x['stock'] -= qty
        elif kind == 'sold':
            x['stock'] -= qty
            x['lastSold'] = max(x['lastSold'] or 0, ts)
            if ts >= w1:
                x['recent'] += usd
                x['recentN'] += 1
            elif ts >= w0:
                x['before'] += usd
                x['beforeN'] += 1
    counted = {int(r['client']): int(r['ts'] or 0) for r in db.execute(
        "SELECT client,MAX(ts) AS ts FROM visit_stock GROUP BY client").fetchall()}
    tasks = {}
    targs = []
    twhere = ''
    if agent is not None:
        twhere = ' AND agent=?'
        targs.append(int(agent))
    for t in db.execute(f"""SELECT client,debt_usd,created_ts FROM collection_tasks
            WHERE status='open'{twhere} ORDER BY created_ts""", targs).fetchall():
        tasks.setdefault(int(t['client']), t)

    items = []
    for c in clients:
        cid = int(c['id'])
        x = led.get(cid, {'debt': 0, 'stock': 0, 'delivered': False, 'lastSold': None,
                          'recent': 0, 'before': 0, 'recentN': 0, 'beforeN': 0})
        v = latest.get(cid)
        last = max(contact.get(cid, 0), int(c['created_ts'] or 0)) or None
        days = (now - last) // DAY if last else None
        followup = _date(v['followup']) if v else None
        scheduled = followup is not None and followup > today
        reasons = []
        if followup and followup <= today and v['status'] != 'declined':
            late = (today - followup).days
            reasons.append({'code': 'agreed_visit', 'since': int(v['ts'] or 0),
                            'text': f"Kelishilgan tashrif: {followup:%d.%m}" + (f" ({late} kun o‘tdi)" if late else ' (bugun)')})
        due = _date(c['payment_due'])
        if due and due <= today and x['debt'] > 0:
            late = (today - due).days
            reasons.append({'code': 'agreed_payment', 'since': None,
                            'text': f"Kelishilgan to‘lov sanasi: {due:%d.%m}" + (f" ({late} kun o‘tdi)" if late else ' (bugun)')})
        if cid in tasks and x['debt'] > 0:
            reasons.append({'code': 'collection_task', 'since': int(tasks[cid]['created_ts'] or 0),
                            'text': 'Kassir qarzni undirishni so‘ragan'})
        if x['before'] > 0:
            if x['recentN'] == 0:
                reasons.append({'code': 'sales_drop', 'since': x['lastSold'],
                                'text': f"Oxirgi {TODAY_WINDOW_DAYS} kunda “Sotildi” yozilmagan (oldin bor edi)"})
            elif (x['recent'] - x['before']) * 100 <= TODAY_DROP_PCT * x['before']:
                pct = round((x['recent'] - x['before']) * 100 / x['before'])
                reasons.append({'code': 'sales_drop', 'since': x['lastSold'],
                                'text': f"Realizatsiya {pct}% (oxirgi {TODAY_WINDOW_DAYS} kun oldingisiga nisbatan)"})
        if not scheduled:
            if x['delivered'] and (x['stock'] > 0 or x['debt'] > 0) and days is not None and days >= VISIT_DUE_DAYS:
                reasons.append({'code': 'visit_due', 'since': last, 'text': f"{days} kundan beri tashrif yo‘q"})
            check = max(x['lastSold'] or 0, counted.get(cid, 0))
            if x['stock'] > 0 and (not check or (now - check) // DAY >= STOCK_CHECK_DAYS):
                reasons.append({'code': 'stock_check', 'since': check or None,
                                'text': ('Qoldiq yoki realizatsiya hech yozilmagan' if not check else
                                         f"Qoldiq/realizatsiya {(now - check) // DAY} kun oldin yozilgan")})
            if not x['delivered'] and (not v or v['status'] in ('interested', 'waiting')) and (days is None or days >= PROSPECT_DAYS):
                reasons.append({'code': 'prospect', 'since': last,
                                'text': 'Istiqbolli mijoz' + (f": {days} kundan beri aloqa yo‘q" if days is not None else '')})
        if not reasons:
            continue
        reasons.sort(key=lambda r: PRIORITY[r['code']])
        top = reasons[0]['code']
        items.append({'clientId': cid, 'name': display_name(c), 'region': (c['region'] or '').strip() or 'Belgilanmagan',
                      'agentId': int(c['agent']), 'agent': c['agent_name'] or str(c['agent']),
                      'priority': PRIORITY[top], 'reasons': reasons, 'action': ACTIONS[top],
                      'debtNowCents': x['debt'], 'lastContactTs': last, 'lastContactDays': days})
    items.sort(key=lambda i: (i['priority'], -(i['lastContactDays'] or 0), -max(i['debtNowCents'], 0), i['clientId']))
    return {'asOf': now, 'items': items[:limit], 'total': len(items),
            'note': 'Bugungi tavsiya joriy ma’lumotdan; davr filtri unga ta’sir qilmaydi. Reja avtomatik tuzilmaydi.'}
