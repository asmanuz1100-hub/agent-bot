"""Agents no longer add clients, give goods, take money or hand over cash through the bot."""
import time
import unittest
from unittest.mock import patch

import bot
import core


class BotMiniAppOnlyTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'Admin'), (2, 'agent', 'Ali'), (3, 'cashier', 'Kassir')])
        self.db.commit()

    def msg(self, i, txt, uid):
        return {'update_id': i, 'message': {'message_id': i, 'date': int(time.time()), 'from': {'id': uid},
                                             'chat': {'id': uid, 'type': 'private'}, 'text': txt}}

    def test_agent_menu_has_no_bot_money_or_goods_buttons(self):
        flat = [b for row in bot.menu(self.db, 2) for b in row]
        for label in ('🏪 Мижоз қўшиш', '📦 Товар бериш', '💰 Пул олиш', '🏦 Кассага топшириш'):
            self.assertNotIn(label, flat)
        self.assertIn('📱 Agent Mini App', flat)

    def test_old_button_text_points_to_mini_app(self):
        with patch.object(bot, 'api') as api, patch.object(bot, 'send'):
            bot.handle(self.db, self.msg(1, '💰 Пул олиш', 2))
        self.assertIsNone(bot.state(self.db, 2))
        self.assertIn('Agent Mini App', str(api.call_args))

    def test_only_premium_launchers_old_test_buttons_still_work(self):
        flat = [b for row in bot.menu(self.db, 1) for b in row]
        self.assertNotIn('🧪 Agent Premium TEST', flat)
        self.assertNotIn('🧪 Kassir Premium TEST', flat)
        self.assertNotIn('🧪 Rahbar Premium TEST', flat)
        with patch.object(bot, 'api') as api, patch.object(bot, 'send'):
            bot.handle(self.db, self.msg(2, '🧪 Kassir Premium TEST', 1))
        self.assertIn('theme=premium', str(api.call_args))
        with self.assertRaises(ValueError):
            bot.handle(self.db, self.msg(3, '🧪 Agent Premium TEST', 2))


    def test_rahbar_button_opens_premium_and_old_app_redirects(self):
        with patch.object(bot, 'api') as api:
            bot.handle(self.db, self.msg(4, '📱 Раҳбар Mini App', 1))
        self.assertIn('/app/rahbar-premium/', str(api.call_args))
        code, body, ctype, _ = bot.miniapp_response('/app/rahbar/', 'v=1')
        self.assertEqual(code, 200)
        self.assertIn(b'/app/rahbar-premium/', body)
        self.assertNotIn(b'/app/rahbar-premium/', bot.miniapp_response('/app/rahbar/', 'classic=1')[1][:4000])

    def test_agent_and_cashier_apps_default_to_premium(self):
        for rel in ('agent/index.html',):
            text = (bot.MINIAPP_DIR / rel).read_text(encoding='utf-8')
            self.assertIn('theme=classic', text)
            self.assertNotIn('PREMIUM TEST', text)
        text = open('cashier-miniapp.html', encoding='utf-8').read()
        self.assertIn('theme=classic', text)
        self.assertNotIn('PREMIUM TEST', text)


if __name__ == '__main__':
    unittest.main()
