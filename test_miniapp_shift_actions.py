"""Telegram WebApp keyboard shift controls use the existing bot shift workflow."""
import time
import unittest
from unittest.mock import patch

import bot
import core


class AgentMiniAppShiftTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1,'admin','Admin'),(2,'agent','Agent'),(3,'cashier','Cashier')])

    def tearDown(self):
        self.db.close()

    @staticmethod
    def webapp_update(payload,uid=2,update_id=1,ts=None):
        ts=int(time.time()) if ts is None else ts
        return {'update_id':update_id,
                'message':{'message_id':update_id,'date':ts,
                           'from':{'id':uid},
                           'chat':{'id':uid,'type':'private'},
                           'web_app_data':{'data':payload,'button_text':'📱 Agent Mini App'}}}

    def test_start_and_end_from_webapp_use_real_shift_table_and_report(self):
        now=int(time.time())
        with patch.object(bot,'send') as send, patch.object(bot,'ADMINS',{1}), \
             patch.object(bot.reports,'shift_summary',return_value={'text':'Test report'}):
            bot.handle(self.db,self.webapp_update('asman.shift.start.v1',ts=now))
            shift=self.db.execute('SELECT * FROM shifts WHERE agent=2 AND end IS NULL').fetchone()
            self.assertIsNotNone(shift)
            self.assertEqual(shift['start'],now)
            self.assertIsNone(shift['live_id'])
            self.assertIn('жонли локация',send.call_args.args[1])
            self.assertIn('📱 Agent Mini App',[button for row in send.call_args.args[2] for button in row])
            with self.assertRaisesRegex(ValueError,'аллақачон'):
                bot.handle(self.db,self.webapp_update('asman.shift.start.v1',update_id=2,ts=now+1))
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM shifts WHERE agent=2').fetchone()[0],1)
            bot.handle(self.db,self.webapp_update('asman.shift.end.v1',update_id=3,ts=now+100))
            closed=self.db.execute('SELECT * FROM shifts WHERE agent=2').fetchone()
            self.assertEqual(closed['end'],now+100)
            self.assertTrue(any('Telegramда жонли локация' in call.args[1]
                                for call in send.call_args_list if len(call.args)>1))
            bot.handle(self.db,self.webapp_update('asman.shift.end.v1',update_id=4,ts=now+101))
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM shifts WHERE agent=2 AND end IS NULL').fetchone()[0],0)

    def test_reject_invalid_payload_or_non_agent_without_creating_shift(self):
        with patch.object(bot,'send'):
            for payload,uid in [('asman.shift.start.v1',1),
                                ('asman.shift.end.v1',3),
                                ('asman.shift.start.v1;DROP TABLE shifts',2),
                                ('{"action":"shift"}',2)]:
                with self.assertRaises(ValueError):
                    bot.handle(self.db,self.webapp_update(payload,uid=uid))
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM shifts').fetchone()[0],0)


if __name__=='__main__':
    unittest.main()
