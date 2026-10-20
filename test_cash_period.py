"""Moliya «Davr» filtri: kassa harakatlari faqat tanlangan kunlar oralig'idan (kutilayotganlari doim)."""
import os
import tempfile
import time
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import core
import manager_api

TZ = ZoneInfo('Asia/Tashkent')


class CashPeriodTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = core.connect(os.path.join(self.tmp.name, 'c.sqlite3'))
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [(1, 'admin', 'R'), (2, 'agent', 'Ali'), (4, 'cashier', 'K')])
        day = lambda d: int(datetime(2026, 10, d, 12, tzinfo=TZ).timestamp())
        self.db.executemany("INSERT INTO handovers(agent,amount,amount_usd,status,cashier,source,ts,accepted_ts) VALUES(2,0,?,?,4,?,?,?)",
                            [(1000, 'accepted', 1, day(1), day(1)), (2000, 'accepted', 2, day(10), day(10)), (500, 'pending', 3, day(3), None)])
        self.db.commit()
        self.now = day(20)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_only_selected_days_plus_pending(self):
        r = manager_api.cash_period(self.db, '2026-10-05', '2026-10-15', now=self.now)
        amounts = sorted(t['amountUsd'] for t in r['transactions'])
        self.assertEqual(amounts, [5, 20])   # 10-oktyabr qabul + kutilayotgan; 1-oktyabr chiqmaydi


if __name__ == '__main__':
    unittest.main()
