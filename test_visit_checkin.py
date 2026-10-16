"""Visit check-in: GPS at the shop (from Telegram live location), shelf photo, shop stock count."""
import re
import time
import unittest

import agent_api
import core

PHOTO = 'AgACAgIAAxkBAAIBvisitPhoto_123'


class VisitCheckinTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [
            (1, 'admin', 'Admin'), (2, 'agent', 'Ali'), (3, 'cashier', 'Kassir')])
        self.now = int(time.time()) - 60
        self.db.execute('UPDATE products SET price=? WHERE pack=1', (10000,))
        core.record(self.db, 1, 2, None, 'load', 1, 50, source=7001, currency='USD')
        out = agent_api.mutate(self.db, 2, 'add_client', {
            'shopName': 'Baraka', 'name': 'Vali', 'phone': '+998901234567', 'address': 'Qo‘qon',
            'lat': 40.54, 'lon': 70.94, 'status': 'interested', 'note': 'x'}, 'client_create_1', self.now - 3600)
        self.cid = out['clientId']
        core.record(self.db, 2, 2, self.cid, 'delivery', 1, 12, 0, '', 8001, currency='USD')
        self.db.execute('INSERT INTO shifts(id,agent,start,live_id) VALUES(99,2,?,777)', (self.now - 7200,))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def point(self, ts, lat=40.5401, lon=70.9401, acc=10):
        self.db.execute('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(99,?,?,?,?)', (ts, lat, lon, acc))

    def visit(self, rid, **kw):
        payload = {'clientId': self.cid, 'status': 'active', 'note': 'Javon to‘ldirildi',
                   'checkinTs': self.now - 900, 'photoFileId': PHOTO, 'offlineTs': self.now}
        payload.update(kw)
        return agent_api.mutate(self.db, 2, 'visit', payload, 'req_' + rid + '_000000', self.now)

    def test_visit_at_shop_saves_gps_photo_and_stock(self):
        self.point(self.now - 600)
        out = self.visit('v1', stock=[{'pack': 1, 'qty': '8'}, {'pack': 3, 'qty': ''}])
        self.assertTrue(out['ok'])
        self.assertEqual(out['durationMin'], 15)
        self.assertLess(out['distanceM'], 30)
        v = self.db.execute('SELECT checkin_ts,distance_m,photo,lat FROM client_visits WHERE id=?', (out['visitId'],)).fetchone()
        self.assertEqual((v['checkin_ts'], v['photo']), (self.now - 900, PHOTO))
        self.assertAlmostEqual(v['lat'], 40.5401)
        rows = self.db.execute('SELECT pack,counted,expected FROM visit_stock WHERE visit=?', (out['visitId'],)).fetchall()
        self.assertEqual([tuple(r) for r in rows], [(1, 8, 12)])   # blank count is skipped
        d = agent_api.client_detail(self.db, 2, self.cid, self.now)
        last = d['visits'][0]
        self.assertEqual((last['durationMin'], last['hasPhoto']), (15, True))
        self.assertEqual(last['stock'][0]['counted'] - last['stock'][0]['expected'], -4)
        self.assertEqual(core.client_stock_total(self.db, self.cid, 1), 12)  # counting never changes the ledger

    def test_far_from_shop_is_rejected(self):
        self.point(self.now - 600, lat=40.56, lon=70.94)   # ~2 km away
        with self.assertRaisesRegex(ValueError, 'uzoqdasiz'):
            self.visit('v_far')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM client_visits WHERE checkin_ts>0').fetchone()[0], 0)

    def test_one_point_at_the_shop_during_the_visit_is_enough(self):
        self.point(self.now - 850, lat=40.56, lon=70.94)
        self.point(self.now - 500)
        self.point(self.now - 100, lat=40.56, lon=70.94)
        self.assertTrue(self.visit('v_mid')['ok'])

    def test_no_live_location_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'GPS nuqtasi topilmadi'):
            self.visit('v_nogps')

    def test_photo_is_required(self):
        self.point(self.now - 600)
        with self.assertRaisesRegex(ValueError, 'rasmini'):
            self.visit('v_nophoto', photoFileId='')

    def test_bad_checkin_time_is_rejected(self):
        self.point(self.now - 600)
        with self.assertRaisesRegex(ValueError, 'boshlanish'):
            self.visit('v_old', checkinTs=self.now - 7 * 3600)
        with self.assertRaisesRegex(ValueError, 'boshlanish'):
            self.visit('v_future', checkinTs=self.now + 3600)

    def test_stock_validation(self):
        self.point(self.now - 600)
        with self.assertRaisesRegex(ValueError, 'ikki marta'):
            self.visit('v_dup', stock=[{'pack': 1, 'qty': 1}, {'pack': 1, 'qty': 2}])
        with self.assertRaisesRegex(ValueError, 'topilmadi'):
            self.visit('v_bad', stock=[{'pack': 999999, 'qty': 1}])
        with self.assertRaisesRegex(ValueError, '0 dan'):
            self.visit('v_neg', stock=[{'pack': 1, 'qty': -1}])

    def test_old_cached_app_visit_still_works(self):
        out = agent_api.mutate(self.db, 2, 'visit', {'clientId': self.cid, 'status': 'interested', 'note': 'Taklif'},
                               'req_v_old_app_000000', self.now)
        self.assertTrue(out['ok'])

    def test_visit_check_reports_distance(self):
        self.point(self.now - 30)
        r = agent_api.visit_check(self.db, 2, self.cid, self.now)
        self.assertTrue(r['ok']);self.assertLess(r['distanceM'], 30)
        self.point(self.now - 5, lat=40.56, lon=70.94)
        r = agent_api.visit_check(self.db, 2, self.cid, self.now)
        self.assertFalse(r['ok']);self.assertIn('uzoqdasiz', r['message'])

    def test_visit_check_needs_live_location(self):
        self.db.execute('UPDATE shifts SET live_id=NULL WHERE id=99')
        r = agent_api.visit_check(self.db, 2, self.cid, self.now)
        self.assertFalse(r['ok']);self.assertIn('jonli lokatsiya', r['message'])

    def test_visit_photo_link_is_signed(self):
        import os
        from unittest.mock import patch
        import bot
        with patch.dict(os.environ, {'WEBHOOK_BASE_URL': 'https://x.example'}):
            link = bot.visit_photo_link(42)
        m = re.fullmatch(r'https://x\.example/map/visit-photo/42/(\d+)/([0-9a-f]{32})', link)
        self.assertTrue(m)
        self.assertTrue(bot._map_valid('visit-photo/42', m.group(1), m.group(2)))
        self.assertFalse(bot._map_valid('visit-photo/43', m.group(1), m.group(2)))

    def test_miniapp_has_visit_section(self):
        html = open('miniapps/agent/index.html', encoding='utf-8').read()
        for marker in ('id="visitStart"', 'visitFinish', 'request("visit_check"', 'data-stock-pack', 'checkinTs'):
            self.assertIn(marker, html)


if __name__ == '__main__':
    unittest.main()
