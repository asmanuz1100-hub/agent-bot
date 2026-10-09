"""Hududlar va mijozlar reytingi (KPI) — Rahbar va Agent ilovalari uchun.

Hammasi mavjud yozuvlardan hisoblanadi (tovar berish, qaytarish, to'lov, mijoz hududi);
yangi ma'lumot kiritish shart emas. Pul qiymatlari USD tsentda hisoblanib, javobda USD
(float) qilib beriladi.

Mijoz bahosi 100 ballik va oddiy tushuntiriladi:
  * Sotuv hajmi   — 40 ball (davrdagi sof realizatsiya, eng yaxshi mijozlarga nisbatan)
  * To'lov        — 30 ball (qarz yo'q / qanchasini to'lagan / qarz necha kunlik)
  * Muntazamlik   — 15 ball (davrda necha marta tovar olgan)
  * O'sish        — 15 ball (o'tgan shunday davrga nisbatan)
"""
import time

import core

DAY = 86400
SLEEP_DAYS = 30          # shuncha kun tovar olmasa — "Uxlab qolgan"
RISK_DEBT_DAYS = 21      # qarz shuncha kundan beri to'lanmasa — "Xavfli"

GROUPS = [
    # key, belgi, nomi, nima qilish kerak
    ('best', '🏆', 'Eng yaxshi', 'Ushlab qoling: assortimentni kengaytiring, yangi mahsulot taklif qiling.'),
    ('growing', '📈', 'O‘sayotgan', 'Ko‘proq tovar va yangi mahsulot taklif qiling.'),
    ('stable', '✅', 'Barqaror', 'Rejadagi tashriflarni davom ettiring.'),
    ('attention', '⚠️', 'E’tibor kerak', 'Sababini so‘rang: narx, raqobatchi yoki tovar sotilmayaptimi.'),
    ('risky', '🔴', 'Xavfli', 'Avval qarzni yig‘ing, keyin yangi tovar bering.'),
    ('sleeping', '💤', 'Uxlab qolgan', 'Tashrif buyuring va qaytaring: aksiya yoki yangi mahsulot taklif qiling.'),
]
GROUP_INFO = {g[0]: {'key': g[0], 'icon': g[1], 'label': g[2], 'advice': g[3]} for g in GROUPS}


def _usd(cents):
    return round(int(cents or 0) / 100, 2)


def _money(cents):
    return f"{_usd(cents):,.2f} $"


def _region_key(name):
    return ' '.join(str(name or '').replace('‘', "'").replace('’', "'").split()).lower()


def _period_sums(db, start, end, agent=None):
    """{client: {...}} sums of events in [start, end)."""
    args = [start, end]
    where = ''
    if agent is not None:
        where = ' AND c.agent=?'
        args.append(int(agent))
    rows = db.execute(f"""SELECT e.client AS client,
        COALESCE(SUM(CASE WHEN e.kind='delivery' THEN e.amount_usd ELSE 0 END),0) AS delivered,
        COALESCE(SUM(CASE WHEN e.kind='return' THEN e.amount_usd ELSE 0 END),0) AS returned,
        COALESCE(SUM(CASE WHEN e.kind='payment' THEN e.amount_usd ELSE 0 END),0) AS paid,
        COALESCE(SUM(CASE WHEN e.kind='delivery' THEN e.qty ELSE 0 END),0) AS qty,
        COALESCE(SUM(CASE WHEN e.kind='sold' THEN e.qty ELSE 0 END),0) AS sold_qty
        FROM events e JOIN clients c ON c.id=e.client
        WHERE e.ts>=? AND e.ts<? AND e.client IS NOT NULL{where}
        GROUP BY e.client""", args).fetchall()
    out = {int(r['client']): {'delivered': int(r['delivered'] or 0), 'returned': int(r['returned'] or 0),
                              'paid': int(r['paid'] or 0), 'qty': int(r['qty'] or 0),
                              'soldQty': int(r['sold_qty'] or 0)} for r in rows}
    # Necha xil kunda tovar olgan (muntazamlik). Kunlar Toshkent vaqti bo'yicha.
    day_rows = db.execute(f"""SELECT e.client AS client,e.ts AS ts FROM events e JOIN clients c ON c.id=e.client
        WHERE e.kind='delivery' AND e.ts>=? AND e.ts<?{where}""", args).fetchall()
    days = {}
    for r in day_rows:
        days.setdefault(int(r['client']), set()).add((int(r['ts']) + 5 * 3600) // DAY)
    for cid, s in days.items():
        out.setdefault(cid, {'delivered': 0, 'returned': 0, 'paid': 0, 'qty': 0, 'soldQty': 0})['orderDays'] = len(s)
    return out


def _lifetime(db, agent=None):
    """{client: debt, last delivery/payment, first delivery} over all time."""
    args = []
    where = ''
    if agent is not None:
        where = ' WHERE c.agent=?'
        args.append(int(agent))
    rows = db.execute(f"""SELECT c.id AS client,
        COALESCE(SUM(CASE WHEN e.kind='delivery' THEN e.amount_usd
                          WHEN e.kind IN ('payment','return') THEN -e.amount_usd ELSE 0 END),0) AS debt,
        MAX(CASE WHEN e.kind='delivery' THEN e.ts END) AS last_delivery,
        MIN(CASE WHEN e.kind='delivery' THEN e.ts END) AS first_delivery,
        MAX(CASE WHEN e.kind='payment' THEN e.ts END) AS last_payment
        FROM clients c LEFT JOIN events e ON e.client=c.id{where}
        GROUP BY c.id""", args).fetchall()
    return {int(r['client']): {'debt': int(r['debt'] or 0),
                               'lastDelivery': int(r['last_delivery'] or 0) or None,
                               'firstDelivery': int(r['first_delivery'] or 0) or None,
                               'lastPayment': int(r['last_payment'] or 0) or None} for r in rows}


def _growth_pct(cur, prev):
    if prev <= 0:
        return None
    return round((cur - prev) * 100.0 / prev, 1)


def insights(db, period='month', date_from=None, date_to=None, agent=None, now=None):
    """Hududlar hisoboti va mijozlar reytingi. agent berilsa — faqat shu agentning mijozlari."""
    now = int(time.time() if now is None else now)
    start, end, label = core.resolve_period(period, date_from, date_to, now=now)
    length = max(DAY, end - start)
    prev_start, prev_end = start - length, start
    period_weeks = max(1.0, length / (7 * DAY))

    args = []
    where = "WHERE COALESCE(c.map_only,0)=0"
    if agent is not None:
        where += ' AND c.agent=?'
        args.append(int(agent))
    clients = db.execute(f"""SELECT c.id,c.agent,c.name,c.shop_name,c.region,c.address,c.created_ts,
        u.name AS agent_name FROM clients c LEFT JOIN users u ON u.id=c.agent {where}""", args).fetchall()
    cur = _period_sums(db, start, end, agent)
    prev = _period_sums(db, prev_start, prev_end, agent)
    life = _lifetime(db, agent)

    rated = []
    for c in clients:
        cid = int(c['id'])
        lf = life.get(cid, {})
        if not lf.get('firstDelivery'):
            continue                      # hali tovar olmagan — reytingga kirmaydi
        p = cur.get(cid, {})
        q = prev.get(cid, {})
        sales = int(p.get('delivered', 0)) - int(p.get('returned', 0))
        prev_sales = int(q.get('delivered', 0)) - int(q.get('returned', 0))
        debt = max(0, int(lf.get('debt', 0)))
        last_del = lf.get('lastDelivery')
        last_pay = lf.get('lastPayment')
        since_delivery = (now - last_del) // DAY if last_del else None
        debt_days = 0
        if debt > 0:
            ref = last_pay or lf.get('firstDelivery') or now
            debt_days = max(0, (now - ref) // DAY)
        rated.append({'c': c, 'cid': cid, 'sales': sales, 'prevSales': prev_sales, 'paid': int(p.get('paid', 0)),
                      'qty': int(p.get('qty', 0)), 'soldQty': int(p.get('soldQty', 0)),
                      'orderDays': int(p.get('orderDays', 0)), 'debt': debt, 'debtDays': int(debt_days),
                      'sinceDelivery': since_delivery, 'lastDelivery': last_del})

    # Sotuv hajmi: eng yaxshi mijozlarning 90-persentiliga nisbatan (bitta katta mijoz hammani bosib ketmasin).
    positive = sorted(r['sales'] for r in rated if r['sales'] > 0)
    ref_sales = positive[int(len(positive) * 0.9)] if positive else 0
    if positive and ref_sales <= 0:
        ref_sales = positive[-1]

    for r in rated:
        reasons = []
        vol = 40.0 * min(1.0, r['sales'] / ref_sales) if ref_sales > 0 and r['sales'] > 0 else 0.0
        if r['debt'] <= 0:
            pay = 30.0
        else:
            ratio = r['paid'] / (r['paid'] + r['debt']) if (r['paid'] + r['debt']) > 0 else 0
            age = 10.0 if r['debtDays'] <= 7 else 5.0 if r['debtDays'] <= 14 else 0.0
            pay = 20.0 * ratio + age
        reg = 15.0 * min(1.0, r['orderDays'] / period_weeks) if r['orderDays'] else 0.0
        growth = _growth_pct(r['sales'], r['prevSales'])
        if growth is None:
            gro = 10.0 if r['sales'] > 0 else 0.0
        elif growth >= 10:
            gro = 15.0
        elif growth > -10:
            gro = 8.0
        else:
            gro = 0.0
        score = int(round(vol + pay + reg + gro))
        r.update({'score': score, 'growth': growth,
                  'parts': {'sales': round(vol), 'payment': round(pay), 'regular': round(reg), 'growth': round(gro)}})

        # Guruh: avval xavfli holatlar, keyin ball.
        if r['sinceDelivery'] is not None and r['sinceDelivery'] >= SLEEP_DAYS:
            group = 'sleeping'
            reasons.append(f"{r['sinceDelivery']} kundan beri tovar olmagan")
        elif r['debt'] > 0 and r['debtDays'] >= RISK_DEBT_DAYS:
            group = 'risky'
            reasons.append(f"Qarz {_money(r['debt'])} · {r['debtDays']} kundan beri to‘lamagan")
        elif score >= 70:
            group = 'best'
        elif growth is not None and growth >= 15:
            group = 'growing'
        elif growth is None and r['sales'] > 0 and r['prevSales'] <= 0:
            group = 'growing'
            reasons.append('Yangi faol mijoz')
        elif score < 40 or (growth is not None and growth <= -25):
            group = 'attention'
        else:
            group = 'stable'

        if r['sales'] > 0:
            reasons.append(f"Realizatsiya {_money(r['sales'])}")
        if growth is not None and abs(growth) >= 10:
            reasons.append(f"Sotuv {'▲' if growth > 0 else '▼'}{abs(growth):.0f}% o‘tgan davrga nisbatan")
        if r['orderDays'] >= 2:
            reasons.append(f"{r['orderDays']} marta tovar olgan")
        if r['debt'] > 0 and group != 'risky':
            reasons.append(f"Qarz {_money(r['debt'])}" + (f" · {r['debtDays']} kun" if r['debtDays'] else ''))
        elif r['debt'] <= 0:
            reasons.append('Qarzi yo‘q')
        if r['sales'] <= 0 and group not in ('sleeping',):
            reasons.append('Bu davrda tovar olmagan')
        r['group'] = group
        r['reasons'] = reasons[:3]

    rated.sort(key=lambda r: (-r['score'], -r['sales'], r['cid']))

    def client_json(r, rank):
        c = r['c']
        g = GROUP_INFO[r['group']]
        return {'id': r['cid'], 'rank': rank, 'name': c['shop_name'] or c['name'] or f"Mijoz #{r['cid']}",
                'person': c['name'] or '', 'region': (c['region'] or '').strip() or 'Belgilanmagan',
                'agentId': int(c['agent']), 'agent': c['agent_name'] or str(c['agent']),
                'score': r['score'], 'parts': r['parts'], 'group': r['group'], 'groupLabel': g['label'],
                'groupIcon': g['icon'], 'advice': g['advice'], 'reasons': r['reasons'],
                'salesUsd': _usd(r['sales']), 'prevSalesUsd': _usd(r['prevSales']), 'growthPct': r['growth'],
                'paidUsd': _usd(r['paid']), 'debtUsd': _usd(r['debt']), 'debtDays': r['debtDays'],
                'qty': r['qty'], 'orderDays': r['orderDays'], 'daysSinceDelivery': r['sinceDelivery']}

    client_list = [client_json(r, i + 1) for i, r in enumerate(rated)]
    groups = []
    for key, icon, label_, advice in GROUPS:
        items = [x for x in client_list if x['group'] == key]
        groups.append({'key': key, 'icon': icon, 'label': label_, 'advice': advice, 'count': len(items),
                       'salesUsd': round(sum(x['salesUsd'] for x in items), 2),
                       'debtUsd': round(sum(x['debtUsd'] for x in items), 2)})

    # Hududlar
    regions = {}
    for r in rated:
        c = r['c']
        name = (c['region'] or '').strip() or 'Belgilanmagan'
        key = _region_key(name) or 'belgilanmagan'
        g = regions.setdefault(key, {'name': name, 'clients': 0, 'active': 0, 'sales': 0, 'prev': 0, 'paid': 0,
                                     'debt': 0, 'best': 0, 'risky': 0, 'sleeping': 0, 'agents': set(), 'top': None})
        g['clients'] += 1
        g['active'] += 1 if r['sales'] > 0 else 0
        g['sales'] += r['sales']
        g['prev'] += r['prevSales']
        g['paid'] += r['paid']
        g['debt'] += r['debt']
        g['agents'].add(c['agent_name'] or str(c['agent']))
        if r['group'] in ('best', 'risky', 'sleeping'):
            g[r['group']] += 1
        if r['sales'] > 0 and (g['top'] is None or r['sales'] > g['top'][1]):
            g['top'] = (c['shop_name'] or c['name'] or f"Mijoz #{r['cid']}", r['sales'])
    # Tovar olmagan mijozlar ham hudud bo'yicha sanaladi (qamrov uchun).
    for c in clients:
        if life.get(int(c['id']), {}).get('firstDelivery'):
            continue
        name = (c['region'] or '').strip() or 'Belgilanmagan'
        key = _region_key(name) or 'belgilanmagan'
        g = regions.setdefault(key, {'name': name, 'clients': 0, 'active': 0, 'sales': 0, 'prev': 0, 'paid': 0,
                                     'debt': 0, 'best': 0, 'risky': 0, 'sleeping': 0, 'agents': set(), 'top': None})
        g.setdefault('prospects', 0)
        g['prospects'] = g.get('prospects', 0) + 1
    total_sales = sum(max(0, g['sales']) for g in regions.values())
    region_list = []
    for g in regions.values():
        region_list.append({
            'name': g['name'], 'clients': g['clients'], 'activeClients': g['active'],
            'prospects': g.get('prospects', 0),
            'salesUsd': _usd(g['sales']), 'prevSalesUsd': _usd(g['prev']), 'growthPct': _growth_pct(g['sales'], g['prev']),
            'paidUsd': _usd(g['paid']), 'debtUsd': _usd(g['debt']),
            'avgPerActiveUsd': _usd(g['sales'] // g['active']) if g['active'] else 0,
            'sharePct': round(max(0, g['sales']) * 100.0 / total_sales, 1) if total_sales else 0,
            'best': g['best'], 'risky': g['risky'], 'sleeping': g['sleeping'],
            'agents': sorted(g['agents']),
            'topClient': ({'name': g['top'][0], 'salesUsd': _usd(g['top'][1])} if g['top'] else None)})
    region_list.sort(key=lambda x: (-x['salesUsd'], -x['clients'], x['name']))
    for i, x in enumerate(region_list):
        x['rank'] = i + 1

    # Agentlar kesimi (rahbar uchun)
    by_agent = {}
    for x in client_list:
        a = by_agent.setdefault(x['agentId'], {'agentId': x['agentId'], 'agent': x['agent'], 'clients': 0, 'active': 0,
                                               'salesUsd': 0.0, 'debtUsd': 0.0, 'scoreSum': 0,
                                               **{k: 0 for k, *_ in GROUPS}})
        a['clients'] += 1
        a['active'] += 1 if x['salesUsd'] > 0 else 0
        a['salesUsd'] += x['salesUsd']
        a['debtUsd'] += x['debtUsd']
        a['scoreSum'] += x['score']
        a[x['group']] += 1
    agents = []
    for a in by_agent.values():
        a['avgScore'] = round(a.pop('scoreSum') / a['clients']) if a['clients'] else 0
        a['salesUsd'] = round(a['salesUsd'], 2)
        a['debtUsd'] = round(a['debtUsd'], 2)
        agents.append(a)
    agents.sort(key=lambda a: (-a['salesUsd'], -a['avgScore']))

    # "Bugun kimga borish kerak": avval xavfli (qarz), keyin uxlab qolgan, keyin e'tibor kerak.
    order = {'risky': 0, 'sleeping': 1, 'attention': 2}
    todo = sorted((x for x in client_list if x['group'] in order),
                  key=lambda x: (order[x['group']], -x['debtUsd'], -(x['daysSinceDelivery'] or 0)))[:15]

    no_region = sum(1 for c in clients if not (c['region'] or '').strip())
    summary = {'ratedClients': len(client_list), 'totalClients': len(clients),
               'activeClients': sum(1 for x in client_list if x['salesUsd'] > 0),
               'salesUsd': round(sum(x['salesUsd'] for x in client_list), 2),
               'debtUsd': round(sum(x['debtUsd'] for x in client_list), 2),
               'avgScore': round(sum(x['score'] for x in client_list) / len(client_list)) if client_list else 0,
               'noRegionClients': no_region}
    return {'period': period, 'label': label, 'start': start, 'end': end,
            'summary': summary, 'groups': groups, 'regions': region_list, 'clients': client_list,
            'agents': agents, 'todo': todo,
            'scoring': {'sales': 40, 'payment': 30, 'regular': 15, 'growth': 15,
                        'sleepDays': SLEEP_DAYS, 'riskDebtDays': RISK_DEBT_DAYS}}
