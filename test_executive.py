"""Executive dashboard: davrlar, filtrlar, oldingi davr bilan solishtirish va boshqa ekranlar bilan moslik."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import core
import executive
import manager_api

TZ = ZoneInfo('Asia/Tashkent')
DAY = 86400


class ExecutiveTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali'), (3, 'agent', 'Vali'), (4, 'cashier', 'Kassir')])
        self.now = int(datetime(2026, 10, 15, 15, 0, tzinfo=TZ).timestamp())
        self.today = int(datetime(2026, 10, 15, tzinfo=TZ).timestamp())
        self.src = 1000
        # Ali — Qo'qon, Vali — Rishton
        for cid, agent, region in ((10, 2, 'Qo‘qon'), (11, 2, "Qo'qon"), (20, 3, 'Rishton')):
            self.db.execute("INSERT INTO clients(id,agent,name,region,phone,created_ts) VALUES(?,?,?,?,?,?)",
                            (cid, agent, f'C{cid}', region, f'+9989000{cid}', self.today - 20 * DAY))
        self.db.execute("UPDATE clients SET created_ts=? WHERE id=11", (self.today + 3600,))  # bugun yangi mijoz

    def ev(self, agent, client, kind, cents, ts, **kw):
        self.src += 1
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source,pay_method,paid_uzs)
            VALUES(?,?,?,?,0,0,0,?,'',?,?,?,?)""",
                        (agent, agent, client, kind, cents, ts, self.src, kw.get('method', ''), kw.get('uzs', 0)))

    def seed(self):
        t, y = self.today + 7200, self.today - DAY + 7200
        self.ev(2, 10, 'delivery', 10000, y)          # kecha 100$
        self.ev(2, 10, 'payment', 4000, y + 60, method='cash')  # kecha 40$ naqd dollar
        self.ev(2, 10, 'delivery', 5000, t)           # bugun 50$
        self.ev(2, 10, 'return', 1000, t + 60)        # bugun qaytish 10$
        self.ev(2, 10, 'payment', 2000, t + 120, uzs=250000, method='cash')  # bugun 20$ so'mda (record_client_payment kabi)
        self.ev(3, 20, 'delivery', 3000, t)           # Vali bugun 30$
        self.ev(3, 20, 'payment', 5000, t + 60, method='card')  # 50$ karta → 20$ avans
        self.db.execute("INSERT INTO client_visits(client,actor,status,note,followup,ts) VALUES(10,2,'active','x',NULL,?)", (t,))

    def k(self, data, key):
        return next(x for x in data['kpis'] if x['key'] == key)

    def test_today_kpis_and_comparison_with_yesterday(self):
        self.seed()
        d = executive.executive(self.db, 'today', now=self.now)
        self.assertEqual(self.k(d, 'realization')['value'], 70)       # 50-10+30
        self.assertEqual(self.k(d, 'realization')['prev'], 100)
        self.assertEqual(self.k(d, 'realization')['delta'], {'kind': 'pct', 'pct': -30.0})
        self.assertEqual(self.k(d, 'collected')['value'], 70)          # 20 + 50
        self.assertEqual(self.k(d, 'collected')['prev'], 40)
        self.assertEqual(self.k(d, 'debt')['value'], 80)               # Ali 100-40+50-10-20=80; Vali avans
        self.assertEqual(self.k(d, 'debt')['prev'], 60)                # bugun boshida: Ali 60
        self.assertEqual(d['advanceUsd'], 20)
        self.assertEqual(self.k(d, 'newClients')['value'], 1)
        self.assertEqual(self.k(d, 'visits')['value'], 1)
        self.assertEqual(self.k(d, 'activeAgents')['value'], 2)
        c = d['collections']
        self.assertEqual((c['cashUsd'], c['cashUzs'], c['cashUzsAsUsd'], c['cardUsd']), (0, 250000, 20, 50))

    def test_matches_dashboard_and_period_report(self):
        self.seed()
        d = executive.executive(self.db, 'today', now=self.now)
        dash = manager_api.dashboard(self.db, self.now)
        self.assertEqual(self.k(d, 'realization')['value'], dash['reports']['today']['deliveredUsd'])
        self.assertEqual(self.k(d, 'collected')['value'], dash['reports']['today']['paymentsUsd'])
        self.assertEqual(self.k(d, 'debt')['value'], dash['summary']['debtUsd'])
        self.assertEqual(d['advanceUsd'], dash['summary']['advanceUsd'])
        self.assertEqual(self.k(d, 'visits')['value'], dash['summary']['visitsToday'])
        self.assertEqual(self.k(d, 'newClients')['value'], dash['summary']['newClientsToday'])
        week = executive.executive(self.db, 'd7', now=self.now)
        self.assertEqual(self.k(week, 'realization')['value'], dash['reports']['week']['deliveredUsd'])
        self.assertEqual(self.k(week, 'collected')['value'], dash['reports']['week']['paymentsUsd'])

    def test_agent_and_region_filters(self):
        self.seed()
        ali = executive.executive(self.db, 'today', agent=2, now=self.now)
        self.assertEqual(self.k(ali, 'realization')['value'], 40)
        self.assertEqual(self.k(ali, 'debt')['value'], 80)
        self.assertEqual(ali['advanceUsd'], 0)
        self.assertEqual([a['agentId'] for a in ali['agents']], [2])
        rish = executive.executive(self.db, 'today', region='rishton', now=self.now)
        self.assertEqual(self.k(rish, 'realization')['value'], 30)
        self.assertEqual(self.k(rish, 'debt')['value'], 0)
        self.assertEqual(rish['advanceUsd'], 20)
        kokand = executive.executive(self.db, 'today', region='Qo‘qon', now=self.now)  # apostrof turlari bir xil
        self.assertEqual(self.k(kokand, 'newClients')['value'], 1)
        self.assertEqual({r['key'] for r in kokand['options']['regions']}, {'qoqon', 'rishton'})

    def test_debt_series_and_groups(self):
        self.seed()
        d = executive.executive(self.db, 'd7', now=self.now)
        self.assertEqual(d['group'], 'day')
        self.assertEqual(len(d['series']), 7)
        self.assertEqual(d['series'][-2]['debtUsd'], 60)   # kecha oxirida
        self.assertEqual(d['series'][-1]['debtUsd'], 80)
        self.assertEqual(sum(x['realizationUsd'] for x in d['series']), self.k(d, 'realization')['value'])
        m = executive.executive(self.db, 'd30', group='week', now=self.now)
        self.assertEqual(m['group'], 'week')
        self.assertEqual(sum(x['paymentsUsd'] for x in m['series']), self.k(m, 'collected')['value'])

    def test_single_day_uses_hourly_buckets(self):
        self.seed()
        d = executive.executive(self.db, 'today', now=self.now)
        self.assertEqual(d['group'], 'hour')
        self.assertEqual(len(d['series']), 16)  # 00:00 … 15:00
        self.assertEqual(sum(x['realizationUsd'] for x in d['series']), 70)
        self.assertEqual(d['series'][-1]['debtUsd'], 80)
        y = executive.executive(self.db, 'yesterday', now=self.now)
        self.assertEqual(len(y['series']), 24)

    def test_periods(self):
        r = executive.resolve(self.db, 'yesterday', now=self.now)
        self.assertEqual((r['start'], r['end']), (self.today - DAY, self.today))
        self.assertEqual((r['prevStart'], r['prevEnd']), (self.today - 2 * DAY, self.today - DAY))
        m = executive.resolve(self.db, 'month', now=self.now)
        self.assertEqual(m['start'], int(datetime(2026, 10, 1, tzinfo=TZ).timestamp()))
        self.assertEqual(m['prevStart'], int(datetime(2026, 9, 1, tzinfo=TZ).timestamp()))
        c = executive.resolve(self.db, 'custom', '2026-10-01', '2026-10-10', now=self.now)
        self.assertEqual(c['end'] - c['start'], 10 * DAY)
        self.assertEqual(c['prevEnd'], c['start'])
        a = executive.resolve(self.db, 'all', now=self.now)
        self.assertIsNone(a['prevStart'])
        with self.assertRaises(ValueError):
            executive.resolve(self.db, 'year', now=self.now)

    def test_debt_aging_fifo_sums_to_total_debt(self):
        # Ali (C10): 45 kun oldin 100$, 10 kun oldin 50$, 5 kun oldin 120$ to'lov → FIFO: eski 100$ yopiladi,
        # 10 kunlik 50$ dan 20$ yopiladi → 30$ qoladi (0–30 guruh).
        self.ev(2, 10, 'delivery', 10000, self.today - 45 * DAY)
        self.ev(2, 10, 'delivery', 5000, self.today - 10 * DAY)
        self.ev(2, 10, 'payment', 12000, self.today - 5 * DAY)
        # Vali (C20): 95 kun oldin 40$ to'lanmagan (90+), ortiqcha to'lov yo'q.
        self.ev(3, 20, 'delivery', 4000, self.today - 95 * DAY)
        d = executive.executive(self.db, 'today', now=self.now)
        aging = {b['label']: b for b in d['debtAging']}
        self.assertEqual(aging['0–30']['usd'], 30)
        self.assertEqual(aging['90+']['usd'], 40)
        self.assertEqual(aging['31–60']['usd'], 0)
        self.assertEqual(sum(b['usd'] for b in d['debtAging']), self.k(d, 'debt')['value'])
        self.assertEqual(aging['90+']['clients'], 1)

    def test_advance_covers_later_delivery_in_aging(self):
        self.ev(2, 10, 'payment', 3000, self.today - 40 * DAY)   # avans 30$
        self.ev(2, 10, 'delivery', 5000, self.today - 20 * DAY)  # 50$ dan 30$ avans bilan yopiladi
        d = executive.executive(self.db, 'today', now=self.now)
        self.assertEqual(sum(b['usd'] for b in d['debtAging']), 20)
        self.assertEqual(self.k(d, 'debt')['value'], 20)

    def test_agents_cash_keeps_usd_and_uzs_apart(self):
        self.seed()   # Ali: kecha 40$ naqd dollar, bugun 250 000 so'm; Vali: karta (agentda turmaydi)
        self.db.execute("INSERT INTO handovers(agent,amount,amount_usd,status,cashier,source,ts) VALUES(2,0,1500,'pending',NULL,9001,?)", (self.today,))
        d = executive.executive(self.db, 'today', now=self.now)
        cash = d['agentsCash']
        self.assertEqual(cash['cashUsd'], 40)
        self.assertEqual(cash['cashUzs'], 250000)
        self.assertEqual(cash['pendingUsd'], 15)
        self.assertEqual([a['agentId'] for a in cash['agents']], [2])
        only_vali = executive.executive(self.db, 'today', agent=3, now=self.now)['agentsCash']
        self.assertEqual((only_vali['cashUsd'], only_vali['cashUzs']), (0, 0))

    def test_region_sales_and_calendar(self):
        self.seed()
        d = executive.executive(self.db, 'today', now=self.now)
        regs = {r['key']: r for r in d['regionSales']}
        self.assertEqual(regs['qoqon']['realizationUsd'], 40)
        self.assertEqual(regs['rishton']['realizationUsd'], 30)
        self.assertEqual(sum(r['realizationUsd'] for r in d['regionSales']), self.k(d, 'realization')['value'])
        cal = d['calendar']
        self.assertEqual((cal['year'], cal['month'], cal['days']), (2026, 10, 31))
        self.assertEqual(cal['values']['15']['realizationUsd'], 70)
        self.assertEqual(cal['values']['14']['realizationUsd'], 100)

    def test_conversions_are_listed_in_display_units(self):
        self.db.execute("""INSERT INTO cashier_conversions(cashier,pay_from,from_currency,amount_from,amount_to,rate_uzs_per_usd,valuation_rate,usd_delta,note,source,ts)
            VALUES(4,'cash','USD',10000,1270000,12700,12700,0,'',501,?)""", (self.today + 60,))
        self.db.execute("""INSERT INTO cashier_conversions(cashier,pay_from,from_currency,amount_from,amount_to,rate_uzs_per_usd,valuation_rate,usd_delta,note,source,ts)
            VALUES(4,'card','UZS',635000,5000,12700,12700,0,'',502,?)""", (self.today - 3 * DAY,))
        d = executive.executive(self.db, 'today', now=self.now)
        self.assertEqual(len(d['conversions']), 1)
        c = d['conversions'][0]
        self.assertEqual((c['from'], c['amountFrom'], c['to'], c['amountTo'], c['rate']), ('USD', 100, 'UZS', 1270000, 12700))
        w = executive.executive(self.db, 'd7', now=self.now)['conversions']
        self.assertEqual([(x['from'], x['amountFrom'], x['amountTo']) for x in w], [('USD', 100, 1270000), ('UZS', 635000, 50)])

    def test_warehouse_all_statuses_for_kanban(self):
        now = self.now
        for i, st in enumerate(('new', 'preparing', 'loaded', 'delivered', 'rejected')):
            self.db.execute("INSERT INTO orders(agent,client,status,note,source,ts,updated_ts) VALUES(2,10,?,'',?,?,?)", (st, 600 + i, now - i, now - i))
        w = manager_api.warehouse(self.db, 'all')
        self.assertEqual(sorted(o['status'] for o in w['orders']), sorted(('new', 'preparing', 'loaded', 'delivered', 'rejected')))
        self.assertEqual(w['filter'], 'all')
        with self.assertRaises(ValueError):
            manager_api.warehouse(self.db, 'bogus')

    def test_postgres_decimal_sums_stay_json_serializable(self):
        # Production (PostgreSQL) SUM() Decimal qaytaradi: executive javobi JSON'ga o'tishi shart.
        import json
        from decimal import Decimal
        from unittest import mock
        self.seed()
        with mock.patch.object(core, 'cash_som', lambda db, a: Decimal('250000')), \
             mock.patch.object(core, 'cash_usd', lambda db, a: Decimal('4000')):
            d = executive.executive(self.db, 'today', now=self.now)
        json.dumps(d)
        self.assertEqual((d['agentsCash']['cashUsd'], d['agentsCash']['cashUzs']), (80, 500000))
        import bot
        self.assertEqual(json.loads(json.dumps({'a': Decimal('12'), 'b': Decimal('1.5')}, default=bot._json_number)), {'a': 12, 'b': 1.5})
        with self.assertRaises(TypeError):
            json.dumps({'x': object()}, default=bot._json_number)

    def test_read_only(self):
        self.seed()
        before = self.db.total_changes
        executive.executive(self.db, 'd30', agent=2, region='qoqon', now=self.now)
        self.assertEqual(self.db.total_changes, before)


if __name__ == '__main__':
    unittest.main()
