"""PostgreSQL'da (TEST_DATABASE_URL bo'lsa): qora ro'yxat qoidalari va mijozlar ro'yxati keshining yangiligi."""
import os
import unittest
import uuid

import agent_api
import core
import test_blacklist

URL = os.getenv('TEST_DATABASE_URL')


class _PgMixin:
    def _pg(self):
        self.schema = 't_' + uuid.uuid4().hex[:12]
        os.environ['DB_SCHEMA'] = self.schema
        return core.connect(URL)

    def _drop(self):
        try:
            self.db.rollback()
            self.db.execute(f'DROP SCHEMA "{self.schema}" CASCADE')
            self.db.commit()
        finally:
            self.db.close()
            os.environ.pop('DB_SCHEMA', None)


@unittest.skipUnless(URL, 'TEST_DATABASE_URL berilmagan')
class PgBlacklistTests(_PgMixin, test_blacklist.BlacklistTests):
    def setUp(self):
        orig = core.connect
        core.connect = lambda path, *a, **k: orig(URL, *a, **k) if path == ':memory:' else orig(path, *a, **k)
        try:
            self.schema = 't_' + uuid.uuid4().hex[:12]
            os.environ['DB_SCHEMA'] = self.schema
            super().setUp()
        finally:
            core.connect = orig

    def tearDown(self):
        self._drop()


@unittest.skipUnless(URL, 'TEST_DATABASE_URL berilmagan')
class PgSnapshotCacheTests(_PgMixin, unittest.TestCase):
    def setUp(self):
        self.db = self._pg()
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [(1, 'admin', 'R'), (2, 'agent', 'A')])
        self.db.execute('UPDATE products SET price=? WHERE pack=1', (1000,))
        core.record(self.db, 1, 2, None, 'load', 1, 100, source=1, currency='USD')
        self.db.execute("""INSERT INTO clients(id,agent,name,phone,region,lat,lon,created_ts,map_only)
            VALUES(10,2,'C','+998900000010','Qo‘qon',40.5,70.9,1,0)""")
        core.record(self.db, 2, 2, 10, 'delivery', 1, 5, source=2, currency='USD')
        self.db.commit()
        agent_api._SNAPSHOT_CACHE.clear()

    def tearDown(self):
        self._drop()

    def debt(self, now):
        return next(c for c in agent_api.quick_snapshot(self.db, 2, now)['clients'] if c['id'] == 10)['debtUsd']

    def test_cache_never_shows_stale_debt_after_any_write(self):
        now = 1_800_000_000
        self.assertEqual(self.debt(now), 50.0)
        self.assertEqual(self.debt(now + 1), 50.0)            # o'zgarish yo'q — keshdan
        core.record(self.db, 2, 2, 10, 'payment', 0, 0, 2000, '', 3, currency='USD', ts=now)
        self.db.commit()
        self.assertEqual(self.debt(now + 2), 30.0)            # yozuvdan keyin darhol yangi
        core.edit_client(self.db, 1, 10, {'region': 'Rishton'})
        self.db.commit()
        c = next(c for c in agent_api.quick_snapshot(self.db, 2, now + 3)['clients'] if c['id'] == 10)
        self.assertEqual(c['region'], 'Rishton')
        core.set_client_blacklist(self.db, 1, 10, True, 'test sabab', ts=now)
        self.db.commit()
        c = next(c for c in agent_api.quick_snapshot(self.db, 2, now + 4)['clients'] if c['id'] == 10)
        self.assertTrue(c['blacklisted'])

    def test_cached_rows_are_copies(self):
        a = agent_api.quick_snapshot(self.db, 2, 1_800_000_000)['clients']
        a[0]['photoUrl'] = 'x'
        b = agent_api.quick_snapshot(self.db, 2, 1_800_000_001)['clients']
        self.assertNotIn('photoUrl', b[0])


if __name__ == '__main__':
    unittest.main()
