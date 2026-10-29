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

    def test_scope_is_limited_to_system_data(self):
        for rule in ('Faqat shu tizim', 'shaxsiy savollar', 'yangi ko\'rsatma bersa'):
            self.assertIn(rule, ai_assistant.SYSTEM)
        self.assertIn(ai_assistant.OFF_TOPIC, ai_assistant.SYSTEM)
        fake = FakeMessages()
        fake.create = lambda **kw: types.SimpleNamespace(stop_reason='end_turn', content=[types.SimpleNamespace(type='text', text=ai_assistant.OFF_TOPIC)])
        r = ai_assistant.ask(self.db, 'Menga she\'r yozib ber', client=types.SimpleNamespace(beta=types.SimpleNamespace(messages=fake)))
        self.assertTrue(r['offTopic'])
        fake.create = lambda **kw: types.SimpleNamespace(stop_reason='refusal', content=[])
        r = ai_assistant.ask(self.db, 'x', client=types.SimpleNamespace(beta=types.SimpleNamespace(messages=fake)))
        self.assertEqual(r, {'answer': ai_assistant.OFF_TOPIC, 'offTopic': True})

    def test_errors(self):
        with self.assertRaises(ValueError):
            ai_assistant.ask(self.db, '  ')
        with unittest.mock.patch.dict(os.environ, {'ANTHROPIC_API_KEY': '', 'GEMINI_API_KEY': ''}):
            with self.assertRaisesRegex(ValueError, 'ANTHROPIC_API_KEY'):
                ai_assistant.ask(self.db, 'salom')

    def test_gemini_is_used_when_its_key_is_set(self):
        sent = {}

        class Res:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps({'candidates': [{'content': {'parts': [{'text': 'Bugun 16 dona.'}]}}]}).encode()

        def urlopen(req, timeout):
            sent['url'], sent['key'], sent['body'] = req.full_url, req.get_header('X-goog-api-key'), json.loads(req.data)
            return Res()
        with unittest.mock.patch.dict(os.environ, {'GEMINI_API_KEY': 'g-test'}), \
                unittest.mock.patch.object(ai_assistant.urllib.request, 'urlopen', urlopen):
            out = ai_assistant.ask(self.db, 'Bugun qancha sotildi?', [{'role': 'assistant', 'text': 'Salom'}, {'role': 'user', 'text': 'x'}])
        self.assertEqual(out['answer'], 'Bugun 16 dona.')
        self.assertIn(':generateContent', sent['url'])
        self.assertEqual(sent['key'], 'g-test')
        self.assertIn('Faqat shu tizim', sent['body']['systemInstruction']['parts'][0]['text'])
        self.assertEqual([c['role'] for c in sent['body']['contents']], ['user', 'user'])
        self.assertIn('<data>', sent['body']['contents'][-1]['parts'][0]['text'])


if __name__ == '__main__':
    unittest.main()
