import unittest
from unittest.mock import patch
import core
import bot

class AgentMiniAppButtonTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Admin'),(2,'agent','Agent'),(3,'cashier','Cashier')])

    def tearDown(self):
        self.db.close()

    def test_agent_button_requests_signed_inline_webapp_for_agent_and_admin(self):
        agent_rows=bot.menu(self.db,2)
        self.assertIn('📱 Agent Mini App',[b for row in agent_rows for b in row])
        self.assertFalse(any(isinstance(b,dict) and b.get('web_app') for row in agent_rows for b in row))
        self.assertIn('📱 Раҳбар Mini App',[b for row in bot.menu(self.db,1) for b in row])
        self.assertIn('📱 Agent Mini App',[b for row in bot.menu(self.db,1) for b in row])
        self.assertFalse(any(isinstance(b,dict) and b.get('web_app') for row in bot.menu(self.db,3) for b in row))
        self.assertTrue(bot.AGENT_MINIAPP_URL.startswith('https://'))
        self.assertIn('asman-agent-miniapp-v2-test.onrender.com',bot.AGENT_MINIAPP_URL)
        with patch.object(bot,'api') as api:
            message={'from':{'id':2},'chat':{'id':2,'type':'private'},
                     'text':'📱 Agent Mini App','date':1234}
            bot.handle(self.db,{'message':message})
            button=api.call_args.kwargs['reply_markup']['inline_keyboard'][0][0]
            self.assertEqual(button['web_app']['url'],bot.AGENT_MINIAPP_URL)
            self.assertNotIn('url',button)
        with patch.object(bot,'api') as api:
            message={'from':{'id':1},'chat':{'id':1,'type':'private'},
                     'text':'📱 Agent Mini App','date':1234}
            bot.handle(self.db,{'message':message})
            button=api.call_args.kwargs['reply_markup']['inline_keyboard'][0][0]
            self.assertEqual(button['web_app']['url'],bot.AGENT_MINIAPP_URL)
            self.assertIn('Админ назорат режими',api.call_args.kwargs['text'])

if __name__=='__main__':
    unittest.main()
