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

    def test_admin_gets_premium_test_launchers(self):
        flat = [b for row in bot.menu(self.db, 1) for b in row]
        self.assertIn('🧪 Agent Premium TEST', flat)
        self.assertIn('🧪 Kassir Premium TEST', flat)
        with patch.object(bot, 'api') as api:
            bot.handle(self.db, self.msg(2, '🧪 Kassir Premium TEST', 1))
        self.assertIn('theme=premium', str(api.call_args))
        with self.assertRaises(ValueError):
            bot.handle(self.db, self.msg(3, '🧪 Agent Premium TEST', 2))


if __name__ == '__main__':
    unittest.main()
