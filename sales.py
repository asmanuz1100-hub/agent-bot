"""Rahbar Web — Savdo bo'limi (faqat o'qish, Bito «Sotuvlar» dashboardi kabi).

Hisob qoidalari `executive` bilan bir xil:
- Savdo summasi = `delivery` hodisalari (USD), qaytarish = `return`, sof savdo = ayirmasi.
- Chek = bitta agentning bitta mijozga bir kalendar kunida (Toshkent vaqti) bergan tovarlari.
- To'lov turlari: naqd USD, naqd so'm (USD ekvivalenti), karta; «Qarzga» = sof savdo − yig'ilgan pul (manfiy bo'lsa 0).
Barcha DB qiymatlari int() orqali o'tadi: PostgreSQL SUM/BIGINT Decimal qaytarishi mumkin.
"""
from datetime import datetime

import core
from executive import TZ, _Scope, _delta, _usd, resolve

JOURNAL_LIMIT = 300
TOP = 10


def _name(pack):
    try:
        return core.PRODUCTS.get(int(pack)) or f'Mahsulot #{int(pack)}'
    except (TypeError, ValueError):
        return 'Nomaʼlum mahsulot'


def _window(db, scope, start, end):
    rows = db.execute("""SELECT id,agent,client,kind,pack,qty,amount_usd,pay_method,paid_uzs,ts FROM events
        WHERE ts>=? AND ts<? AND kind IN ('delivery','return','payment') ORDER BY ts,id""", (start, end)).fetchall()
    return [r for r in rows if scope.event_ok(r['agent'], r['client'])]


def _totals(rows):
    t = {'sold': 0, 'returned': 0, 'paid': 0, 'cash': 0, 'cashUzs': 0, 'cashUzsUsd': 0, 'card': 0, 'qty': 0}
    checks = set()
    for r in rows:
        cents = int(r['amount_usd'] or 0)
        if r['kind'] == 'delivery':
            t['sold'] += cents
            t['qty'] += int(r['qty'] or 0)
            day = datetime.fromtimestamp(int(r['ts']), TZ).date()
            checks.add((int(r['agent'] or 0), int(r['client'] or 0), day))
        elif r['kind'] == 'return':
            t['returned'] += cents
        else:
            t['paid'] += cents
            if (r['pay_method'] or '') == 'card':
                t['card'] += cents
            elif int(r['paid_uzs'] or 0) > 0:
                t['cashUzs'] += int(r['paid_uzs'] or 0)
                t['cashUzsUsd'] += cents
            else:
                t['cash'] += cents
    t['checks'] = len(checks)
    t['net'] = t['sold'] - t['returned']
    return t


def sales(db, period='month', date_from=None, date_to=None, agent=None, region=None, now=None):
    rng = resolve(db, period, date_from, date_to, now)
    scope = _Scope(db, agent, region)
    core.refresh_catalog(db)
    rows = _window(db, scope, rng['start'], rng['end'])
    cur = _totals(rows)
    prev = _totals(_window(db, scope, rng['prevStart'], rng['prevEnd'])) if rng['prevStart'] is not None else None

    names = {int(u['id']): u['name'] for u in db.execute('SELECT id,name FROM users').fetchall()}
    clients = {int(c['id']): c for c in db.execute('SELECT id,name,shop_name,phone,region FROM clients').fetchall()}

    def client_name(cid):
        c = clients.get(int(cid or 0))
        if not c:
            return 'Oʻchirilgan mijoz'
        return (c['shop_name'] or c['name'] or '').strip() or f'Mijoz #{cid}'

    products, by_client, by_agent, journal = {}, {}, {}, {}
    for r in rows:
        cents = int(r['amount_usd'] or 0)
        if r['kind'] == 'payment':
            continue
        sign = 1 if r['kind'] == 'delivery' else -1
        qty = int(r['qty'] or 0)
        p = products.setdefault(int(r['pack'] or 0), {'pack': int(r['pack'] or 0), 'qty': 0, 'cents': 0, 'returnedQty': 0})
        if sign > 0:
            p['qty'] += qty
            p['cents'] += cents
        else:
            p['returnedQty'] += qty
            p['cents'] -= cents
        cid, aid = int(r['client'] or 0), int(r['agent'] or 0)
        c = by_client.setdefault(cid, {'cents': 0, 'qty': 0, 'checks': set()})
        a = by_agent.setdefault(aid, {'cents': 0, 'checks': set()})
        c['cents'] += sign * cents
        a['cents'] += sign * cents
        day = datetime.fromtimestamp(int(r['ts']), TZ).date()
        key = (r['kind'], aid, cid, day)
        if sign > 0:
            c['qty'] += qty
            c['checks'].add(key)
            a['checks'].add(key)
        j = journal.setdefault(key, {'kind': 'sale' if sign > 0 else 'return', 'ts': int(r['ts']), 'agentId': aid,
                                     'agent': names.get(aid) or str(aid), 'clientId': cid, 'client': client_name(cid),
                                     'phone': (clients[cid]['phone'] if cid in clients else '') or '',
                                     'qty': 0, 'cents': 0, 'items': {}})
        j['ts'] = max(j['ts'], int(r['ts']))
        j['qty'] += qty
        j['cents'] += cents
        it = j['items'].setdefault(int(r['pack'] or 0), [0, 0])
        it[0] += qty
        it[1] += cents

    sold = max(cur['sold'], 1)
    top_products = sorted(({'pack': p['pack'], 'name': _name(p['pack']), 'qty': p['qty'], 'returnedQty': p['returnedQty'],
                            'netUsd': _usd(p['cents']), 'sharePct': round(p['cents'] * 100.0 / sold, 1) if cur['sold'] else 0}
                           for p in products.values()), key=lambda x: (-x['netUsd'], -x['qty'], x['name']))
    net = max(cur['net'], 1)
    top_clients = sorted(({'clientId': k, 'client': client_name(k), 'netUsd': _usd(v['cents']), 'qty': v['qty'],
                           'checks': len(v['checks']), 'sharePct': round(v['cents'] * 100.0 / net, 1) if cur['net'] > 0 else 0}
                          for k, v in by_client.items()), key=lambda x: (-x['netUsd'], x['client']))
    top_agents = sorted(({'agentId': k, 'agent': names.get(k) or str(k), 'netUsd': _usd(v['cents']), 'checks': len(v['checks']),
                          'sharePct': round(v['cents'] * 100.0 / net, 1) if cur['net'] > 0 else 0}
                         for k, v in by_agent.items()), key=lambda x: (-x['netUsd'], x['agent']))
    entries = sorted(journal.values(), key=lambda j: -j['ts'])
    lines = [{'kind': j['kind'], 'ts': j['ts'], 'agentId': j['agentId'], 'agent': j['agent'], 'clientId': j['clientId'],
              'client': j['client'], 'phone': j['phone'], 'qty': j['qty'], 'amountUsd': _usd(j['cents']),
              'items': [{'name': _name(k), 'qty': v[0], 'amountUsd': _usd(v[1])} for k, v in sorted(j['items'].items())]}
             for j in entries[:JOURNAL_LIMIT]]

    def kpi(key, c, p, money=True):
        return {'key': key, 'value': _usd(c) if money else c,
                'prev': (_usd(p) if money else p) if p is not None else None, 'delta': _delta(c, p)}

    def avg(t):
        return t['sold'] // t['checks'] if t['checks'] else 0

    on_credit = max(cur['net'] - cur['paid'], 0)
    return {
        'range': rng, 'filters': {'agentId': scope.agent, 'region': region or ''},
        'kpis': [
            kpi('sold', cur['sold'], prev['sold'] if prev else None),
            kpi('net', cur['net'], prev['net'] if prev else None),
            kpi('returned', cur['returned'], prev['returned'] if prev else None),
            kpi('checks', cur['checks'], prev['checks'] if prev else None, money=False),
            kpi('avgCheck', avg(cur), avg(prev) if prev else None),
            kpi('qty', cur['qty'], prev['qty'] if prev else None, money=False),
        ],
        'avgItemsPerCheck': round(cur['qty'] / cur['checks'], 1) if cur['checks'] else 0,
        'payments': {'totalUsd': _usd(cur['paid']), 'cashUsd': _usd(cur['cash']), 'cashUzs': cur['cashUzs'],
                     'cashUzsAsUsd': _usd(cur['cashUzsUsd']), 'cardUsd': _usd(cur['card']), 'onCreditUsd': _usd(on_credit)},
        'topProducts': top_products[:TOP], 'topClients': top_clients[:TOP], 'agents': top_agents,
        'journal': lines, 'journalTotal': len(entries), 'journalLimit': JOURNAL_LIMIT,
    }
