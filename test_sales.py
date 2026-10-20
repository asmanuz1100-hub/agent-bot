"""Rahbar Web Savdo bo'limi: KPI, cheklar, to'lov turlari, top ro'yxatlar va jurnal."""
import json
import unittest
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import core
import executive
import sales

TZ = ZoneInfo('Asia/Tashkent')
DAY = 86400


class SalesTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali'), (3, 'agent', 'Vali')])
        self.now = int(datetime(2026, 10, 15, 15, 0, tzinfo=TZ).timestamp())
        self.today = int(datetime(2026, 10, 15, tzinfo=TZ).timestamp())
        self.src = 1000
        for cid, agent, region in ((10, 2, 'Qo‘qon'), (20, 3, 'Rishton')):
            self.db.execute("INSERT INTO clients(id,agent,name,shop_name,region,phone,created_ts) VALUES(?,?,?,?,?,?,?)",
                            (cid, agent, f'C{cid}', f'Dokon{cid}', region, f'+9989000{cid}', self.today - 20 * DAY))
        self.pack = next(iter(core.PRODUCTS))

    def ev(self, agent, client, kind, cents, ts, qty=0, method='', uzs=0):
        self.src += 1
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source,pay_method,paid_uzs)
            VALUES(?,?,?,?,?,?,0,?,'',?,?,?,?)""", (agent, agent, client, kind, self.pack, qty, cents, ts, self.src, method, uzs))

    def seed(self):
        t, y = self.today + 7200, self.today - DAY + 7200
        self.ev(2, 10, 'delivery', 10000, y, qty=10)            # kecha: 1 chek, 100$
        self.ev(2, 10, 'delivery', 5000, t, qty=5)              # bugun Ali→C10: bitta chek, 2 qator
        self.ev(2, 10, 'delivery', 2000, t + 300, qty=2)
        self.ev(2, 10, 'return', 1000, t + 600, qty=1)
        self.ev(2, 10, 'payment', 2000, t + 900, method='cash', uzs=250000)
        self.ev(3, 20, 'delivery', 3000, t, qty=3)              # Vali→C20: ikkinchi chek
        self.ev(3, 20, 'payment', 1000, t + 60, method='card')
        self.ev(3, 20, 'payment', 500, t + 90, method='cash')

    def k(self, d, key):
        return next(x for x in d['kpis'] if x['key'] == key)

    def test_today_kpis_checks_and_comparison(self):
        self.seed()
        d = sales.sales(self.db, 'today', now=self.now)
        self.assertEqual(self.k(d, 'sold')['value'], 100)        # 50+20+30
        self.assertEqual(self.k(d, 'sold')['prev'], 100)
        self.assertEqual(self.k(d, 'returned')['value'], 10)
        self.assertEqual(self.k(d, 'net')['value'], 90)
        self.assertEqual(self.k(d, 'checks')['value'], 2)
        self.assertEqual(self.k(d, 'checks')['prev'], 1)
        self.assertEqual(self.k(d, 'avgCheck')['value'], 50)
        self.assertEqual(self.k(d, 'qty')['value'], 10)
        self.assertEqual(d['avgItemsPerCheck'], 5)

    def test_payment_split_and_credit(self):
        self.seed()
        p = sales.sales(self.db, 'today', now=self.now)['payments']
        self.assertEqual(p['totalUsd'], 35)
        self.assertEqual(p['cashUzsAsUsd'], 20)
        self.assertEqual(p['cashUzs'], 250000)
        self.assertEqual(p['cardUsd'], 10)
        self.assertEqual(p['cashUsd'], 5)
        self.assertEqual(p['onCreditUsd'], 55)                   # 90 sof savdo − 35 to'lov

    def test_net_matches_executive_realization(self):
        self.seed()
        for period in ('today', 'd7', 'month', 'all'):
            d = sales.sales(self.db, period, now=self.now)
            e = executive.executive(self.db, period, now=self.now)
            self.assertEqual(self.k(d, 'net')['value'], next(x for x in e['kpis'] if x['key'] == 'realization')['value'], period)

    def test_top_lists_and_journal(self):
        self.seed()
        d = sales.sales(self.db, 'today', now=self.now)
        self.assertEqual([c['clientId'] for c in d['topClients']], [10, 20])
        self.assertEqual(d['topClients'][0]['netUsd'], 60)
        self.assertEqual(d['topClients'][0]['client'], 'Dokon10')
        self.assertEqual(d['topProducts'][0]['qty'], 10)
        self.assertEqual(d['topProducts'][0]['returnedQty'], 1)
        self.assertEqual(d['topProducts'][0]['netUsd'], 90)
        self.assertEqual([a['agent'] for a in d['agents']], ['Ali', 'Vali'])
        kinds = sorted((j['kind'], j['client'], j['amountUsd']) for j in d['journal'])
        self.assertEqual(kinds, [('return', 'Dokon10', 10), ('sale', 'Dokon10', 70), ('sale', 'Dokon20', 30)])
        self.assertEqual(d['journalTotal'], 3)

    def test_agent_and_region_filters(self):
        self.seed()
        d = sales.sales(self.db, 'today', agent=3, now=self.now)
        self.assertEqual(self.k(d, 'sold')['value'], 30)
        self.assertEqual(self.k(d, 'checks')['value'], 1)
        r = sales.sales(self.db, 'today', region="Qo'qon", now=self.now)
        self.assertEqual(self.k(r, 'net')['value'], 60)

    def test_empty_period_and_json_safe_with_decimal(self):
        d = sales.sales(self.db, 'today', now=self.now)
        self.assertEqual(self.k(d, 'checks')['value'], 0)
        self.assertEqual(d['journal'], [])
        self.seed()
        json.dumps(sales.sales(self.db, 'all', now=self.now))
        rows = [{k: (Decimal(v) if k in ('amount_usd', 'qty', 'paid_uzs') else v) for k, v in dict(r).items()}
                for r in self.db.execute('SELECT * FROM events').fetchall()]
        t = sales._totals(rows)                                  # PostgreSQL BIGINT/SUM Decimal qaytarishi mumkin
        json.dumps(t)
        self.assertEqual(t['sold'], 20000)

if __name__ == '__main__':
    unittest.main()
