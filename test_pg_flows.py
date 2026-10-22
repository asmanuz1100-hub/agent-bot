"""PostgreSQL'da (TEST_DATABASE_URL bo'lsa): qora ro'yxat qoidalari va mijozlar ro'yxati keshining yangiligi."""
import os
import subprocess
import sys
import unittest
import unittest.mock
import uuid

import agent_api
import cashier_api
import core
import customer_status as cs
import manager_api
import test_blacklist
import test_warehouse_api
import test_purchases

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
class PgPurchasesTests(_PgMixin, test_purchases.PurchasesTests):
    """Ta'minot moduli PostgreSQL'da: BIGSERIAL sxema, qulf va Decimal yig'indilar."""
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

    def test_dashboard_is_json_serializable(self):
        import json
        sid = self.supplier()
        mid = self.material()
        self.call(5, 'purchase', supplierId=sid, lines=[{'material': mid, 'qty': '3.5', 'price': '1.1'}])
        json.dumps(purchases_dashboard(self.db))


def purchases_dashboard(db):
    import purchases
    return purchases.handle(db, 1, 'dashboard', {})


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
class PgWarehouseApiTests(_PgMixin, test_warehouse_api.WarehouseApiTests):
    """Omborchi/agent ombor oqimi PostgreSQL'da (BIGSERIAL, FOR UPDATE lock, RETURNING)."""
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
        a[0]['stock']['1'] = 999
        b = agent_api.quick_snapshot(self.db, 2, 1_800_000_001)['clients']
        self.assertNotIn('photoUrl', b[0])
        self.assertEqual(b[0]['stock'], {'1': 5})


@unittest.skipUnless(URL, 'TEST_DATABASE_URL berilmagan')
class PgCacheConsistencyTests(_PgMixin, unittest.TestCase):
    """Kesh qaysi yozuv yo'li bo'lmasin, hech qachon eski qarz/ombor/egasini ko'rsatmasin."""
    NOW = 1_800_000_000

    def setUp(self):
        self.db = self._pg()
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'R'), (2, 'agent', 'A'), (3, 'agent', 'B'), (5, 'cashier', 'K')])
        self.db.execute('UPDATE products SET price=? WHERE pack=1', (1000,))
        for a in (2, 3):
            core.record(self.db, 1, a, None, 'load', 1, 100, source=a, currency='USD')
        for cid, ag in ((10, 2), (11, 2), (12, 3)):
            self.db.execute("""INSERT INTO clients(id,agent,name,phone,region,lat,lon,created_ts,map_only)
                VALUES(?,?,?,?,'Qo‘qon',40.5,70.9,1,0)""", (cid, ag, f'C{cid}', f'+9989000000{cid}'))
            core.record(self.db, ag, ag, cid, 'delivery', 1, 5, source=100 + cid, currency='USD')
        self.db.commit()
        agent_api._SNAPSHOT_CACHE.clear()
        self.others = []

    def tearDown(self):
        for c in self.others:
            try:
                c.rollback(); c.close()
            except Exception:
                pass
        self._drop()

    def other(self):
        c = core.connect(URL, initialize=False)
        self.others.append(c)
        return c

    def rows(self, db=None, agent=2):
        return {c['id']: c for c in agent_api.quick_snapshot(db or self.db, agent, self.NOW)['clients']}

    def fresh(self):
        return {c['id']: c for c in agent_api._client_snapshot_build(self.db, self.NOW, None)}

    def assert_matches_fresh(self):
        cached = {k: {f: v for f, v in r.items()} for k, r in
                  ((r['id'], r) for r in agent_api._client_snapshot(self.db, self.NOW))}
        self.assertEqual(cached, self.fresh())

    def test_out_of_order_commits_are_never_lost(self):
        """Ilgari belgi MAX(id) edi: kichik id li tranzaksiya kechroq commit bo'lsa to'lov ko'rinmasdi."""
        self.rows()
        a, b = self.other(), self.other()
        core.record(a, 2, 2, 10, 'payment', 0, 0, 1000, '', 501, currency='USD', ts=self.NOW)   # kichikroq id
        core.record(b, 3, 3, 12, 'payment', 0, 0, 2000, '', 502, currency='USD', ts=self.NOW)   # kattaroq id (boshqa agent)
        b.commit()
        r = self.rows()
        self.assertEqual((r[10]['debtUsd'], r[12]['debtUsd']), (50.0, 30.0))
        a.commit()
        r = self.rows()
        self.assertEqual((r[10]['debtUsd'], r[12]['debtUsd']), (40.0, 30.0))
        self.assert_matches_fresh()

    def test_every_write_path_refreshes_the_list(self):
        self.rows()
        core.record(self.db, 2, 2, 10, 'payment', 0, 0, 1500, '', 601, currency='USD', ts=self.NOW)
        self.db.commit()
        self.assertEqual(self.rows()[10]['debtUsd'], 35.0)
        core.record(self.db, 2, 2, 10, 'return', 1, 1, source=602, currency='USD', ts=self.NOW)
        self.db.commit()
        r = self.rows()[10]
        self.assertEqual((r['debtUsd'], r['stock']), (25.0, {'1': 4}))
        ev = self.db.execute("SELECT id FROM events WHERE client=11 AND kind='delivery'").fetchone()[0]
        core.correct_delivery(self.db, 1, ev, 1, 2)                       # tuzatish
        self.db.commit()
        r = self.rows()[11]
        self.assertEqual((r['debtUsd'], r['stock']), (20.0, {'1': 2}))
        self.db.execute('UPDATE clients SET agent=3 WHERE id=11')           # boshqa agentga o'tkazish
        self.db.commit()
        self.assertEqual(self.rows()[11]['agentId'], 3)
        manager_api.client_delete_commit(self.db, 1, 12, now=self.NOW)       # o'chirish
        self.db.commit()
        self.assertNotIn(12, self.rows())
        core.rename_agent(self.db, 1, 3, 'Yangi ism')                        # agent ismi
        self.db.commit()
        self.assertEqual(self.rows()[11]['agent'], 'Yangi ism')
        self.db.execute('DELETE FROM events WHERE source=602')               # yozuv o'chirildi
        self.db.commit()
        self.assertEqual(self.rows()[10]['debtUsd'], 35.0)
        self.assert_matches_fresh()

    def test_cash_and_handover_are_never_cached(self):
        core.record(self.db, 2, 2, 10, 'payment', 0, 0, 3000, '', 701, currency='USD', ts=self.NOW)
        self.db.commit()
        snap = agent_api.quick_snapshot(self.db, 2, self.NOW)
        self.assertEqual(snap['summary']['cashOnHandUsd'], 30.0)
        res = agent_api.mutate(self.db, 2, 'handover', {'currency': 'USD', 'amount': '20'}, 'ho_cache_1234567', self.NOW)
        self.db.commit()
        snap = agent_api.quick_snapshot(self.db, 2, self.NOW)
        self.assertEqual(snap['summary']['cashAvailableUsd'], 10.0)
        core.accept(self.db, 5, res['handoverId'])
        self.db.commit()
        snap = agent_api.quick_snapshot(self.db, 2, self.NOW)
        self.assertEqual(snap['summary']['cashOnHandUsd'], 10.0)
        self.assertEqual(core.cashier_balance_usd(self.db), 2000)

    def test_own_uncommitted_write_is_visible_in_same_transaction(self):
        self.rows()
        core.record(self.db, 2, 2, 10, 'payment', 0, 0, 1000, '', 801, currency='USD', ts=self.NOW)
        self.assertEqual(self.rows()[10]['debtUsd'], 40.0)       # commit qilinmagan, lekin shu tranzaksiya
        self.db.rollback()
        self.assertEqual(self.rows()[10]['debtUsd'], 50.0)       # bekor qilindi -> keshda ham yo'q

    def test_other_process_write_is_seen(self):
        """Ikkinchi server nusxasi (alohida jarayon) yozsa ham bu jarayondagi kesh yangilanadi."""
        self.rows()
        code = ("import core;db=core.connect(%r,initialize=False);"
                "core.record(db,2,2,10,'payment',0,0,2500,'',901,currency='USD',ts=1800000000);db.commit()") % URL
        env = dict(os.environ)
        subprocess.run([sys.executable, '-c', code], check=True, env=env, cwd=os.path.dirname(os.path.abspath(core.__file__)))
        self.assertEqual(self.rows()[10]['debtUsd'], 25.0)

    def test_role_change_is_not_cached(self):
        self.rows(agent=3)
        core.deactivate_agent(self.db, 1, 3)
        self.db.commit()
        with self.assertRaises(Exception):
            agent_api.quick_snapshot(self.db, 3, self.NOW)

    def test_age_follows_request_time_not_cache_time(self):
        a = self.rows()[10]
        later = agent_api.quick_snapshot(self.db, 2, self.NOW + 10 * 86400)['clients']
        b = next(c for c in later if c['id'] == 10)
        self.assertEqual(b['age'], 'red')
        self.assertGreater(b['days'], a['days'] or 0)

    def test_concurrent_patch_equals_full_rebuild(self):
        import random
        rnd = random.Random(5)
        self.rows()
        for i in range(40):
            c = self.other()
            cid = rnd.choice([10, 11, 12])
            ag = 3 if cid == 12 else 2
            kind = rnd.choice(['payment', 'delivery', 'visit'])
            if kind == 'payment':
                core.record(c, ag, ag, cid, 'payment', 0, 0, rnd.randint(1, 300), '', 2000 + i, currency='USD', ts=self.NOW)
            elif kind == 'delivery':
                core.record(c, ag, ag, cid, 'delivery', 1, 1, source=2000 + i, currency='USD', ts=self.NOW)
            else:
                cs.add_visit(c, ag, cid, 'active', 'x', ts=self.NOW + i)
            if rnd.random() < 0.8:
                c.commit()
            else:
                c.rollback()
            if i % 3 == 0:
                self.rows()
        self.assert_matches_fresh()


@unittest.skipUnless(URL, 'TEST_DATABASE_URL berilmagan')
class PgPoolTests(_PgMixin, unittest.TestCase):
    def setUp(self):
        self.db = self._pg()
        self.db.execute("INSERT INTO users(id,role,name) VALUES(1,'admin','R'),(2,'agent','A')")
        self.db.commit()
        self.pool = core.PgPool(URL, size=2, timeout=0.5)

    def tearDown(self):
        self.pool.close()
        self._drop()

    def test_uncommitted_work_and_locks_never_leak_to_next_request(self):
        a = self.pool.get()
        a.execute("INSERT INTO meta(key,value) VALUES('leak','x')")
        a.execute('SELECT pg_advisory_xact_lock(4242)').fetchone()
        a.close()                                            # so'rov xato bilan tugadi, commit yo'q
        b = self.pool.get()
        self.assertIsNone(b.execute("SELECT 1 FROM meta WHERE key='leak'").fetchone())
        self.assertTrue(b.execute('SELECT pg_try_advisory_xact_lock(4242)').fetchone()[0])
        self.assertEqual(b.execute('SHOW search_path').fetchone()[0].strip('"'), self.schema)
        b.close()
        self.assertEqual(self.pool.stats()['opened'], 1)     # bitta ulanish qayta ishlatildi

    def test_failed_statement_connection_is_reset(self):
        a = self.pool.get()
        with self.assertRaises(Exception):
            a.execute('SELECT * FROM no_such_table').fetchall()
        a.close()
        b = self.pool.get()
        self.assertEqual(b.execute('SELECT COUNT(*) FROM users').fetchone()[0], 2)
        b.close()

    def test_bounded_with_timeout_and_slot_released(self):
        a, b = self.pool.get(), self.pool.get()
        with self.assertRaises(core.PoolTimeout):
            self.pool.get()
        a.close(); a.close()                                  # ikki marta close xavfsiz
        c = self.pool.get()
        c.close(); b.close()
        self.assertLessEqual(self.pool.stats()['opened'], 2)

    def test_broken_connection_is_discarded(self):
        a = self.pool.get()
        a.conn.close()
        a.close()
        b = self.pool.get()
        self.assertEqual(b.execute('SELECT 1').fetchone()[0], 1)
        b.close()
        self.assertEqual(self.pool.stats()['discarded'], 1)

    def test_parallel_duplicate_payment_writes_once(self):
        import threading
        self.db.execute("UPDATE products SET price=1000 WHERE pack=1")
        core.record(self.db, 1, 2, None, 'load', 1, 10, source=1, currency='USD')
        self.db.execute("""INSERT INTO clients(id,agent,name,phone,region,lat,lon,created_ts,map_only)
            VALUES(10,2,'C','+998900000010','Qo‘qon',40.5,70.9,1,0)""")
        core.record(self.db, 2, 2, 10, 'delivery', 1, 5, source=2, currency='USD')
        self.db.commit()
        pool = core.PgPool(URL, size=6, timeout=5)
        out = []

        def go():
            d = pool.get()
            try:
                out.append(agent_api.mutate(d, 2, 'payment', {'clientId': 10, 'currency': 'USD', 'amount': '7',
                                                             'method': 'cash'}, 'pay_same_123456', 1_800_000_000))
                d.commit()
            except Exception as e:
                d.rollback(); out.append(e)
            finally:
                d.close()
        with unittest.mock.patch.object(agent_api, '_live_ready', lambda *a, **k: (True, '')):
            th = [threading.Thread(target=go) for _ in range(6)]
            [t.start() for t in th]; [t.join() for t in th]
        pool.close()
        n = self.db.execute("SELECT COUNT(*) FROM events WHERE kind='payment' AND client=10").fetchone()[0]
        self.assertEqual(n, 1, out)


if __name__ == '__main__':
    unittest.main()
