import unittest
import core
import bot

class ManagerMiniAppButtonTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Admin'),(2,'agent','Agent'),(3,'cashier','Cashier')])

    def tearDown(self):
        self.db.close()

    def test_manager_webapp_button_only_for_admin(self):
        admin_rows=bot.menu(self.db,1)
        web_buttons=[b for row in admin_rows for b in row if isinstance(b,dict) and b.get('web_app')]
        self.assertEqual(len(web_buttons),1)
        self.assertEqual(web_buttons[0]['text'],'📱 Раҳбар Mini App')
        self.assertTrue(web_buttons[0]['web_app']['url'].startswith('https://'))
        self.assertIn('asman-manager-miniapp-test.onrender.com',web_buttons[0]['web_app']['url'])
        agent_buttons=[b for row in bot.menu(self.db,2) for b in row if isinstance(b,dict) and b.get('web_app')]
        self.assertEqual(len(agent_buttons),1)
        self.assertEqual(agent_buttons[0]['text'],'📱 Agent Mini App')
        self.assertFalse(any(isinstance(b,dict) and b.get('web_app') for row in bot.menu(self.db,3) for b in row))

if __name__=='__main__':
    unittest.main()
