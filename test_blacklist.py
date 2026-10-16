"""Qora ro'yxat: mijoz o'chirilmaydi, xaritada qoladi, u bilan hech qanday amal bajarilmaydi.
Qo'shish — rahbar yoki agent (sabab bilan), chiqarish — faqat rahbar. Tashrif yoshi to'lovdan yangilanmaydi."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import agent_api
import analytics
import core
import customer_status as cs
import manager_api

TZ = ZoneInfo('Asia/Tashkent')


class BlacklistTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali'), (3, 'cashier', 'Kassir')])
        self.now = int(datetime(2026, 10, 10, 12, 0, tzinfo=TZ).timestamp())
        self.db.execute('UPDATE products SET price=? WHERE pack=1', (1000,))
        core.record(self.db, 1, 2, None, 'load', 1, 100, source=1, currency='USD', ts=self.now - 90 * 86400)
        self.cid = agent_api.mutate(self.db, 2, 'add_client', {
            'shopName': 'Yomon do‘kon', 'name': 'Vali', 'phone': '+998901112233',
            'lat': 40.54, 'lon': 70.94, 'region': 'Qo‘qon'}, 'add_client_1234567', self.now - 60 * 86400)['clientId']
        agent_api.mutate(self.db, 2, 'delivery', {'clientId': self.cid, 'items': [{'pack': 1, 'qty': 5}]},
                         'deliv_12345678', self.now - 50 * 86400)

    def tearDown(self):
        self.db.close()

    def bl(self, actor=2, on=True, reason='To‘lamaydi, telefonni olmaydi', req='bl_1234567890'):
        if actor == 1:
            return core.set_client_blacklist(self.db, 1, self.cid, on, reason, ts=self.now)
        return agent_api.mutate(self.db, actor, 'client_blacklist',
                                {'clientId': self.cid, 'on': on, 'reason': reason}, req, self.now)

    def test_agent_adds_with_reason_client_stays_in_db_and_map(self):
        with self.assertRaisesRegex(ValueError, 'sababini'):
            self.bl(reason='', req='bl_empty_123456')
        self.bl()
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM clients').fetchone()[0], 1)
        c = next(x for x in agent_api.quick_snapshot(self.db, 2, self.now)['clients'] if x['id'] == self.cid)
        self.assertTrue(c['blacklisted'])
        self.assertIsNotNone(c['lat'])
        self.assertEqual(c['debtUsd'], 50.0)
        m = next(x for x in manager_api.dashboard(self.db, self.now)['clients'] if x['id'] == self.cid)
        self.assertTrue(m['blacklisted'])
        self.assertIn('To‘lamaydi', m['blacklistReason'])
        log = manager_api.client_detail(self.db, self.cid)['blacklistLog']
        self.assertEqual([x['action'] for x in log], ['add'])

    def test_all_operations_blocked(self):
        self.bl()
        attempts = [
            ('delivery', {'items': [{'pack': 1, 'qty': 1}]}),
            ('payment', {'currency': 'USD', 'amount': '10', 'method': 'cash'}),
            ('return', {'items': [{'pack': 1, 'qty': 1}]}),
            ('visit', {'status': 'active', 'note': 'keldim'}),
            ('client_edit', {'shop': 'Yangi nom'}),
        ]
        for i, (action, extra) in enumerate(attempts):
            payload = {'clientId': self.cid}
            payload.update(extra)
            with self.assertRaisesRegex(ValueError, 'qora ro‘yxatda', msg=action):
                agent_api.mutate(self.db, 2, action, payload, f'blocked_{i}_123456', self.now)
        with self.assertRaisesRegex(ValueError, 'qora ro‘yxatda'):
            core.record(self.db, 2, 2, self.cid, 'payment', 0, 0, 100, '', 555, currency='USD', ts=self.now)
        with self.assertRaisesRegex(ValueError, 'qora ro‘yxatda'):
            cs.add_visit(self.db, 2, self.cid, 'active', 'Bot orqali tashrif', ts=self.now)
        with self.assertRaisesRegex(ValueError, 'qora ro‘yxatda'):
            core.create_order(self.db, 2, self.cid, [{'pack': 1, 'qty': 1}], source=777, ts=self.now)
        # Tarix o'zgarmaydi: qarz va yozuvlar joyida.
        self.assertEqual(core.client_debt_usd(self.db, self.cid), 5000)

    def test_only_manager_removes(self):
        self.bl()
        with self.assertRaisesRegex(ValueError, 'faqat rahbar'):
            self.bl(on=False, req='bl_remove_12345')
        core.set_client_blacklist(self.db, 1, self.cid, False, ts=self.now + 10)
        core.record(self.db, 2, 2, self.cid, 'payment', 0, 0, 1000, '', 901, currency='USD', ts=self.now + 20)
        self.assertEqual(core.client_debt_usd(self.db, self.cid), 4000)
        log = manager_api.client_detail(self.db, self.cid)['blacklistLog']
        self.assertEqual([x['action'] for x in log], ['remove', 'add'])

    def test_excluded_from_today_plan_and_rating(self):
        self.assertIn(self.cid, [i['clientId'] for i in analytics.today_plan(self.db, agent=2, now=self.now)['items']])
        self.bl()
        self.assertNotIn(self.cid, [i['clientId'] for i in analytics.today_plan(self.db, agent=2, now=self.now)['items']])
        row = next(c for c in analytics.insights(self.db, 'month', now=self.now)['clients'] if c['id'] == self.cid)
        self.assertEqual(row['kpi']['status'], 'blacklisted')
        self.assertNotIn('rank', row)

    def test_payment_does_not_refresh_visit_age(self):
        core.record(self.db, 2, 2, self.cid, 'payment', 0, 0, 500, '', 902, currency='USD', ts=self.now - 3600)
        m = next(x for x in manager_api.dashboard(self.db, self.now)['clients'] if x['id'] == self.cid)
        self.assertEqual((m['age'], m['days']), ('red', 50))
        a = next(x for x in agent_api.quick_snapshot(self.db, 2, self.now)['clients'] if x['id'] == self.cid)
        self.assertEqual(a['age'], 'red')
        self.assertEqual(m['region'], 'Qo‘qon')


if __name__ == '__main__':
    unittest.main()
