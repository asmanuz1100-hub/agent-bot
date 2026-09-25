import unittest
from unittest.mock import patch
import core
import bot

class ManagerMiniAppButtonTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Admin'),(2,'agent','Agent'),(3,'cashier','Cashier')])

    def tearDown(self):
        self.db.close()

    def test_manager_button_requests_signed_inline_webapp_for_admin_only(self):
        admin_rows=bot.menu(self.db,1)
        self.assertIn('📱 Раҳбар Mini App',[b for row in admin_rows for b in row])
        self.assertFalse(any(isinstance(b,dict) and b.get('web_app') for row in admin_rows for b in row))
        agent_buttons=[b for row in bot.menu(self.db,2) for b in row if isinstance(b,dict) and b.get('web_app')]
        self.assertEqual(agent_buttons,[])
        self.assertIn('📱 Agent Mini App',[b for row in bot.menu(self.db,2) for b in row])
        self.assertFalse(any(isinstance(b,dict) and b.get('web_app') for row in bot.menu(self.db,3) for b in row))
        with patch.object(bot,'api') as api:
            message={'from':{'id':1},'chat':{'id':1,'type':'private'},'text':'📱 Раҳбар Mini App','date':1234}
            bot.handle(self.db,{'message':message})
            button=api.call_args.kwargs['reply_markup']['inline_keyboard'][0][0]
            self.assertEqual(button['web_app']['url'],bot.MANAGER_MINIAPP_URL)
            self.assertNotIn('url',button)
        with patch.object(bot,'api') as api:
            message={'from':{'id':2},'chat':{'id':2,'type':'private'},'text':'📱 Раҳбар Mini App','date':1234}
            with self.assertRaises(ValueError):
                bot.handle(self.db,{'message':message})
            api.assert_not_called()

if __name__=='__main__':
    unittest.main()
