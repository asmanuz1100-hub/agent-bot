"""Hududlar hisoboti va mijozlar reytingi."""
import time
import unittest

import analytics
import core

DAY = 86400


class InsightsTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali'), (3, 'agent', 'Vali')])
        self.now = int(time.time())
        self.db.execute('UPDATE products SET price=10000 WHERE pack=1')
        core.record(self.db, 1, 2, None, 'load', 1, 500, source=1, currency='USD')
        core.record(self.db, 1, 3, None, 'load', 1, 500, source=2, currency='USD')
        rows = [  # id, agent, shop, region
            (10, 2, 'Baraka', "Qo'qon"), (11, 2, 'Nur', "Qo'qon"), (12, 2, 'Eski', 'Rishton'),
            (13, 3, 'Qarzdor', 'Rishton'), (14, 3, 'Yangi', ''), (15, 3, 'Hech narsa', 'Buvayda')]
        for cid, ag, shop, reg in rows:
            self.db.execute('INSERT INTO clients(id,agent,name,shop_name,region,phone,created_ts) VALUES(?,?,?,?,?,?,?)',
                            (cid, ag, shop, shop, reg, f'+99890000{cid}', self.now - 90 * DAY))
        self.src = 100

    def ev(self, agent, client, kind, qty, days_ago, value=0):
        self.src += 1
        core.record(self.db, agent, agent, client, kind, 1, qty, value, '', self.src, currency='USD',
                    ts=self.now - days_ago * DAY)

    def test_groups_scores_and_regions(self):
        # Baraka: big, regular, paid up -> best
        for d in (1, 8, 15, 22):
            self.ev(2, 10, 'delivery', 10, d)
            self.ev(2, 10, 'payment', 0, d, 10000)
        # Nur: grows strongly vs previous month
        self.ev(2, 11, 'delivery', 2, 40)
        self.ev(2, 11, 'delivery', 6, 3)
        self.ev(2, 11, 'payment', 0, 2, 6000)
        # Eski: last delivery 45 days ago -> sleeping
        self.ev(2, 12, 'delivery', 3, 45)
        # Qarzdor: old unpaid debt -> risky
        self.ev(3, 13, 'delivery', 8, 28)
        # Yangi: first delivery this period, no region
        self.ev(3, 14, 'delivery', 1, 2)
        out = analytics.insights(self.db, 'custom',
                                 time.strftime('%Y-%m-%d', time.localtime(self.now - 29 * DAY)),
                                 time.strftime('%Y-%m-%d', time.localtime(self.now)), now=self.now)
        by = {c['id']: c for c in out['clients']}
        self.assertNotIn(15, by)                       # never delivered -> not rated
        self.assertEqual(by[10]['group'], 'best')
        self.assertEqual(by[10]['rank'], 1)
        self.assertEqual(by[12]['group'], 'sleeping')
        self.assertEqual(by[13]['group'], 'risky')
        self.assertIn('kundan beri to‘lamagan', by[13]['reasons'][0])
        self.assertEqual(by[11]['group'], 'growing')
        self.assertEqual(by[14]['region'], 'Belgilanmagan')
        self.assertTrue(all(0 <= c['score'] <= 100 for c in out['clients']))
        regions = {r['name']: r for r in out['regions']}
        self.assertEqual(out['regions'][0]['name'], "Qo'qon")
        self.assertEqual(regions['Buvayda']['prospects'], 1)
        self.assertAlmostEqual(sum(r['sharePct'] for r in out['regions']), 100, delta=0.5)
        self.assertEqual([t['group'] for t in out['todo']][:2], ['risky', 'sleeping'])
        self.assertEqual(out['summary']['noRegionClients'], 1)
        self.assertEqual({a['agentId'] for a in out['agents']}, {2, 3})

    def test_agent_sees_only_own_clients(self):
        self.ev(2, 10, 'delivery', 5, 1)
        self.ev(3, 13, 'delivery', 5, 1)
        out = analytics.insights(self.db, 'week', agent=2, now=self.now)
        self.assertEqual({c['agentId'] for c in out['clients']}, {2})


if __name__ == '__main__':
    unittest.main()
