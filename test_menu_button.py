"""Chat menyu tugmasi har deployda joriy Mini App manziliga yangilanadi (eski o'chirilgan servis emas)."""
import unittest

import bot
import core


class MenuButtonTests(unittest.TestCase):
    def test_roles_get_current_urls(self):
        self.assertEqual(bot.menu_button_for('agent')['web_app']['url'], bot.AGENT_MINIAPP_URL)
        self.assertEqual(bot.menu_button_for('admin')['web_app']['url'], bot.AGENT_MINIAPP_URL)
        self.assertEqual(bot.menu_button_for('cashier')['web_app']['url'], bot.CASHIER_MINIAPP_URL)
        self.assertEqual(bot.menu_button_for('none'), {'type': 'commands'})
        for host in bot.LEGACY_MINIAPP_HOSTS:
            self.assertNotIn(host, bot.AGENT_MINIAPP_URL)

    def test_sync_sets_default_and_each_staff_chat(self):
        db = core.connect(':memory:')
        db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                       [(1, 'admin', 'R'), (2, 'agent', 'A'), (3, 'cashier', 'K'), (4, 'client', 'X')])
        calls = []
        old = bot.api
        bot.api = lambda method, **data: calls.append((method, data)) or True
        try:
            bot.sync_menu_buttons(bot.menu_button_users(db))
        finally:
            bot.api = old
            db.close()
        self.assertEqual(calls[0][1], {'menu_button': bot.menu_button_for('agent')})
        by_chat = {d.get('chat_id'): d['menu_button'] for _, d in calls[1:]}
        self.assertEqual(set(by_chat), {1, 2, 3})
        self.assertEqual(by_chat[3]['web_app']['url'], bot.CASHIER_MINIAPP_URL)


if __name__ == '__main__':
    unittest.main()
