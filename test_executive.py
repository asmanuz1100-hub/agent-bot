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
        self.ev(2, 10, 'payment', 4000, y + 60)       # kecha 40$
        self.ev(2, 10, 'delivery', 5000, t)           # bugun 50$
        self.ev(2, 10, 'return', 1000, t + 60)        # bugun qaytish 10$
        self.ev(2, 10, 'payment', 2000, t + 120, uzs=250000)  # bugun 20$ so'mda
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

    def test_read_only(self):
        self.seed()
        before = self.db.total_changes
        executive.executive(self.db, 'd30', agent=2, region='qoqon', now=self.now)
        self.assertEqual(self.db.total_changes, before)


if __name__ == '__main__':
    unittest.main()
