"""Regression coverage for prospective customers stored on the map without goods."""
import json
import re
import time
import unittest
from unittest.mock import patch

import bot
import core
import reports


class ProspectsTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany(
            'INSERT INTO users(id,role,name) VALUES(?,?,?)',
            [(1, 'admin', 'Admin'), (2, 'agent', 'Agent'), (3, 'agent', 'Other')],
        )
        self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)', (int(time.time()) - 15,))
        core.point(
            self.db, 2,
            {'message_id': 4545, 'date': int(time.time()),
             'location': {'latitude': 40.5, 'longitude': 71.4, 'live_period': 3600}},
        )

    def tearDown(self):
        self.db.close()

    def message(self, number, text=None, location=None, photo=None, user=2):
        value = {
            'message_id': number, 'date': int(time.time()),
            'from': {'id': user}, 'chat': {'id': user, 'type': 'private'},
        }
        if text is not None:
            value['text'] = text
        if location is not None:
            value['location'] = location
        if photo is not None:
            value['photo'] = [{'file_id': photo}]
        return {'update_id': number, 'message': value}

    def add_prospect(self, beginning=5000):
        values = [
            ('🏪 Мижоз қўшиш', {}),
            (None, {'location': {'latitude': 40.63, 'longitude': 71.23}}),
            (None, {'photo': 'telegram-photo-id'}),
            ('+998901234567', {}),
            ('Мижоз Алишер', {}),
            ('Дўкон А', {}),
            ('Қўқон', {}),
            ('Кейинроқ оламан', {}),
            ('🗺 Товарсиз харитага сақлаш', {}),
            ('🟠 Таклиф берилган', {}),
            ('✅ Тасдиқлаш', {}),
        ]
        with patch.object(bot, 'send') as send:
            for offset, (text, extra) in enumerate(values):
                bot.handle(self.db, self.message(beginning + offset, text, **extra))
        self.assertIn('товарсиз сақланди', send.call_args.args[1])
        return self.db.execute("SELECT id FROM clients WHERE name='Мижоз Алишер'").fetchone()[0]

    @staticmethod
    def map_data(page):
        match = re.search(r'<script id="data" type="application/json">(.*?)</script>', page.decode(), re.S)
        if not match:
            raise AssertionError('Map JSON not found')
        return json.loads(match.group(1))

    def test_product_free_customer_is_visible_only_on_both_maps(self):
        with patch.object(bot, 'ADMINS', {1}):
            cid = self.add_prospect()
            record = self.db.execute('SELECT * FROM clients WHERE id=?', (cid,)).fetchone()
            self.assertEqual(record['map_only'], 1)
            self.assertEqual(record['comment'], 'Кейинроқ оламан')
            self.assertEqual(record['photo'], 'telegram-photo-id')
            self.assertEqual((record['lat'], record['lon']), (40.63, 71.23))
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events WHERE client=?', (cid,)).fetchone()[0], 0)
            self.assertEqual(core.client_debt_usd(self.db, cid), 0)
            self.assertEqual(core.agent_stock(self.db, 2, 1), 0)
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM clients WHERE map_only=0').fetchone()[0], 0)
            with patch.object(bot, 'send') as send:
                bot.report_clients(self.db, 2)
                self.assertIn(str(cid)+' ·',str(send.call_args.args[2]))
            with patch.object(bot, 'BOT_USERNAME', 'agent_bot_test'):
                agent = self.map_data(reports.agent_clients_map_html(
                    self.db, 2, action_url=lambda verb, customer: bot.agent_action_link(
                        {'pay': 'p', 'return': 'r', 'delivery': 'd', 'visit': 'v'}[verb], 2, customer)))
            self.assertEqual([x['id'] for x in agent['shops']], [cid])
            self.assertEqual(agent['shops'][0]['icon'],'🟠')
            self.assertIn('Кейинроқ оламан',agent['shops'][0]['history'])
            shop = agent['shops'][0]
            self.assertTrue(shop['prospect'])
            self.assertEqual((shop['debt'], shop['stock']), ('0.00', 0))
            self.assertIn('start=d_2_', shop['delivery_url'])
            self.assertNotIn('pay_url', shop)
            self.assertNotIn('return_url', shop)
            admin = self.map_data(reports.admin_clients_map_html(self.db, 1))
            self.assertEqual([x['id'] for x in admin['shops']], [cid])
            self.assertEqual(admin['shops'][0]['owner'], 'Agent')
            self.assertNotIn('delivery_url', admin['shops'][0])
            shared = self.map_data(reports.agent_clients_map_html(self.db, 3))
            self.assertEqual([x['id'] for x in shared['shops']], [cid])
            self.assertTrue(shared['shops'][0]['prospect'])

    def test_first_delivery_promotes_prospect_preserving_identity(self):
        with patch.object(bot, 'ADMINS', {1}):
            cid = self.add_prospect(6000)
            core.set_product_price(self.db, 1, 1, core.money('2.00'))
            core.record(self.db, 1, 2, None, 'load', 1, 5, currency='USD')
            with patch.object(bot, 'BOT_USERNAME', 'agent_bot_test'), patch.object(bot, 'send'):
                payload = bot.agent_action_payload('d', 2, cid)
                with self.assertRaises(ValueError):
                    bot.handle(self.db, self.message(6020, '/start ' + payload, user=3))
                bot.handle(self.db, self.message(6021, '/start ' + payload))
                self.assertEqual(bot.state(self.db, 2)['action'], 'delivery')
                for i, text in enumerate(['Грунтовка 7/1 — 1 кг', 'Дона', '2', '✅ Тасдиқлаш'], 6022):
                    bot.handle(self.db, self.message(i, text))
            self.assertEqual(self.db.execute('SELECT map_only FROM clients WHERE id=?', (cid,)).fetchone()[0], 0)
            self.assertEqual(core.agent_stock(self.db, 2, 1), 3)
            self.assertEqual(core.client_stock(self.db, 2, cid, 1), 2)
            self.assertEqual(core.client_debt_usd(self.db, cid), core.money('4.00'))
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM clients WHERE id=?', (cid,)).fetchone()[0], 1)
            with patch.object(bot, 'send') as send:
                bot.report_clients(self.db, 2)
                self.assertIn(str(cid) + ' ·', str(send.call_args.args[2]))
            after = self.map_data(reports.agent_clients_map_html(self.db, 2))
            self.assertFalse(after['shops'][0]['prospect'])


if __name__ == '__main__':
    unittest.main()
