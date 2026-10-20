"""AI yordamchi: ixcham ma'lumot, xato holatlari va Claude'ga yuboriladigan so'rov shakli (soxta mijoz bilan)."""
import json
import os
import tempfile
import types
import unittest
import unittest.mock

import ai_assistant
import core


class FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        return types.SimpleNamespace(stop_reason='end_turn', content=[types.SimpleNamespace(type='text', text='Bugun 16 dona.')])


class AiAssistantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = core.connect(os.path.join(self.tmp.name, 'a.sqlite3'))
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [(1, 'admin', 'R'), (2, 'agent', 'Ali')])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_snapshot_is_json_and_has_sections(self):
        snap = ai_assistant.snapshot(self.db)
        for key in ('report_today', 'report_week', 'report_month', 'today_overview', 'warehouse'):
            self.assertIn(key, snap)
        json.dumps(snap, default=float)

    def test_ask_sends_data_and_returns_answer(self):
        fake = FakeMessages()
        client = types.SimpleNamespace(beta=types.SimpleNamespace(messages=fake))
        r = ai_assistant.ask(self.db, 'Bugun nechta tovar sotildi?', [{'role': 'assistant', 'text': 'x'}, {'role': 'user', 'text': 'oldingi'}], client=client)
        self.assertEqual(r['answer'], 'Bugun 16 dona.')
        call = fake.calls[0]
        self.assertEqual(call['model'], ai_assistant.MODEL)
        self.assertEqual(call['messages'][0], {'role': 'user', 'content': 'oldingi'})
        self.assertIn('<data>', call['messages'][-1]['content'])

    def test_errors(self):
        with self.assertRaises(ValueError):
            ai_assistant.ask(self.db, '  ')
        with unittest.mock.patch.dict(os.environ, {'ANTHROPIC_API_KEY': ''}):
            with self.assertRaisesRegex(ValueError, 'ANTHROPIC_API_KEY'):
                ai_assistant.ask(self.db, 'salom')


if __name__ == '__main__':
    unittest.main()
