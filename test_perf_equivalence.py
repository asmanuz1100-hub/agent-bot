"""Tezlashtirilgan so'rovlar eski hisob bilan aynan bir xil natija berishini tekshiradi."""
import random
import unittest

import agent_api
import core
import customer_status as cs
import manager_api

DAY = 86400


class PerfEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'R'), (2, 'agent', 'A'), (3, 'agent', 'B')])
        rnd = random.Random(11)
        self.now = 1_800_000_000
        packs = core.product_ids()[:4]
        for i, p in enumerate(packs):
            self.db.execute('UPDATE products SET price=? WHERE pack=?', (1000 + 250 * i, p))
            for a in (2, 3):
                core.record(self.db, 1, a, None, 'load', p, 500, source=10_000 + a * 100 + i, currency='USD', ts=self.now - 20 * DAY)
        for cid in range(1, 9):
            ag = 2 if cid % 2 else 3
            self.db.execute("""INSERT INTO clients(id,agent,name,phone,region,lat,lon,created_ts,map_only)
                VALUES(?,?,?,?,'Qo‘qon',40.5,70.9,?,0)""", (cid, ag, f'C{cid}', f'+99890000{cid:04d}', self.now - 30 * DAY))
        src = 20_000
        for _ in range(300):
            cid = rnd.randint(1, 8); ag = 2 if cid % 2 else 3
            ts = self.now - rnd.randint(0, 9 * DAY)
            kind = rnd.choice(['delivery', 'payment', 'return', 'visit'])
            src += 1
            if kind == 'delivery':
                core.record(self.db, ag, ag, cid, 'delivery', rnd.choice(packs), rnd.randint(1, 4), source=src, currency='USD', ts=ts)
            elif kind == 'payment':
                core.record(self.db, ag, ag, cid, 'payment', 0, 0, rnd.randint(100, 900), '', src, currency='USD', ts=ts)
            elif kind == 'return':
                try:
                    core.record(self.db, ag, ag, cid, 'return', rnd.choice(packs), 1, source=src, currency='USD', ts=ts)
                except ValueError:
                    pass
            else:
                cs.add_visit(self.db, ag, cid, rnd.choice(['active', 'interested']), 'x', ts=ts)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_dashboard_daily_series_equals_full_period_reports(self):
        d = manager_api.dashboard(self.db, self.now)
        today = manager_api._midnight(self.now)
        staff = self.db.execute("SELECT id,name FROM users WHERE role='agent' ORDER BY name,id").fetchall()
        since = today - 29 * DAY
        visits = [(int(v[0]), int(v[1])) for v in self.db.execute(
            'SELECT actor,ts FROM client_visits WHERE ts>=? AND ts<=?', (since, self.now)).fetchall()]
        visits += [(int(v[0]), int(v[1])) for v in self.db.execute(
            "SELECT agent,ts FROM events WHERE kind='visit' AND ts>=? AND ts<=?", (since, self.now)).fetchall()]
        expected = []
        for k in range(6, -1, -1):
            day = today - k * DAY
            r = manager_api._period_report(self.db, day, min(day + DAY, self.now + 1), staff, [], visits, self.now)
            expected.append((r['visits'], r['deliveredUsd'], r['paymentsUsd']))
        got = [(s['visits'], s['deliveredUsd'], s['paymentsUsd']) for s in d['reports']['series']]
        self.assertEqual(got, expected)
        self.assertTrue(any(x[1] for x in got) and any(x[2] for x in got))

    def test_products_stock_and_price_match_core(self):
        for agent in (2, 3):
            for p in agent_api._products(self.db, agent):
                self.assertEqual(p['agentStock'], int(core.agent_stock(self.db, agent, p['pack'])), p['pack'])
                self.assertEqual(p['priceUsd'], round(core.product_price(self.db, p['pack']) / 100, 2))

    def test_latest_visit_is_the_newest_per_client(self):
        rows = {c['id']: c for c in agent_api._client_snapshot(self.db, self.now)}
        for cid in range(1, 9):
            v = self.db.execute('SELECT status,ts FROM client_visits WHERE client=? ORDER BY id DESC LIMIT 1', (cid,)).fetchone()
            if v:
                self.assertEqual(rows[cid]['status'], v['status'])
                self.assertGreaterEqual(rows[cid]['lastTs'], int(v['ts']))
        m = {c['id']: c for c in manager_api.dashboard(self.db, self.now)['clients']}
        for cid in range(1, 9):
            self.assertEqual((m[cid]['status'], m[cid]['lastTs'], m[cid]['debtUsd']),
                             (rows[cid]['status'], rows[cid]['lastTs'], rows[cid]['debtUsd']))


class AgentFundBatchTests(unittest.TestCase):
    def test_batch_wallets_equal_per_agent_functions(self):
        db = core.connect(':memory:')
        db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                       [(1, 'admin', 'R'), (2, 'agent', 'A'), (3, 'agent', 'B'), (4, 'agent', 'C')])
        rows = [(2, 1, 'topup', 1000, 0, 0), (2, 1, 'expense', 333, 0, 0), (2, 1, 'topup', 850, 100000, 12700),
                (3, 1, 'topup', 1, 0, 0), (3, 1, 'expense', 40, 5000, 12500), (3, 1, 'topup', 4000, 500000, 12500)]
        for i, (a, actor, kind, usd, uzs, rate) in enumerate(rows):
            db.execute("""INSERT INTO agent_funds(agent,actor,kind,amount_usd,amount_uzs,rate_uzs_per_usd,source,ts)
                VALUES(?,?,?,?,?,?,?,?)""", (a, actor, kind, usd, uzs, rate, 900 + i, 1_800_000_000 + i))
        for rate in (None, 12655):
            if rate:
                db.execute('INSERT INTO meta(key,value) VALUES(?,?)', (core.CASHIER_RATE_KEY, str(rate)))
            got = core.agent_fund_balances(db)
            for a in (2, 3, 4):
                self.assertEqual(got.get(a, (0, 0)),
                                 (core.agent_fund_balance_usd(db, a), core.agent_fund_balance_uzs(db, a)), (a, rate))
        db.close()


if __name__ == '__main__':
    unittest.main()
