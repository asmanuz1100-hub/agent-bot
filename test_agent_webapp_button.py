import unittest
import core
import bot

class AgentMiniAppButtonTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Admin'),(2,'agent','Agent'),(3,'cashier','Cashier')])

    def tearDown(self):
        self.db.close()

    @staticmethod
    def web_buttons(rows):
        return [b for row in rows for b in row if isinstance(b,dict) and b.get('web_app')]

    def test_agent_and_manager_buttons_are_role_specific(self):
        admin=self.web_buttons(bot.menu(self.db,1))
        agent=self.web_buttons(bot.menu(self.db,2))
        cashier=self.web_buttons(bot.menu(self.db,3))

        self.assertEqual(admin,[])
        self.assertIn('📱 Раҳбар Mini App',[b for row in bot.menu(self.db,1) for b in row])
        self.assertEqual([(b['text'],b['web_app']['url']) for b in agent],
                         [('📱 Agent Mini App',bot.AGENT_MINIAPP_URL)])
        self.assertEqual(cashier,[])
        self.assertTrue(bot.AGENT_MINIAPP_URL.startswith('https://'))
        self.assertIn('asman-agent-miniapp-v2-test.onrender.com',bot.AGENT_MINIAPP_URL)

if __name__=='__main__':
    unittest.main()
