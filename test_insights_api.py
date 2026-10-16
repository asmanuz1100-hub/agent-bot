"""HTTP darajasida ruxsat: agent boshqa agent portfelini so'ray olmaydi."""
import hashlib
import hmac
import json
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request

import bot
import core

TOKEN = '123:TEST'


def init_data(uid):
    d = {'auth_date': str(int(time.time())), 'query_id': 'q',
         'user': json.dumps({'id': uid, 'first_name': 'T'}, separators=(',', ':'))}
    dcs = '\n'.join(f'{k}={v}' for k, v in sorted(d.items()))
    key = hmac.new(b'WebAppData', TOKEN.encode(), hashlib.sha256).digest()
    d['hash'] = hmac.new(key, dcs.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(d)


class InsightsApiPermissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = os.path.join(cls.tmp.name, 'api.sqlite3')
        db = core.connect(path)
        db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                       [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali'), (3, 'agent', 'Vali')])
        db.execute('UPDATE products SET price=10000 WHERE pack=1')
        core.record(db, 1, 2, None, 'load', 1, 50, source=1, currency='USD')
        core.record(db, 1, 3, None, 'load', 1, 50, source=2, currency='USD')
        for cid, agent in ((10, 2), (11, 3)):
            db.execute("INSERT INTO clients(id,agent,name,shop_name,region,phone,created_ts) VALUES(?,?,?,?,?,?,?)",
                       (cid, agent, 'X', f'Shop{cid}', 'Qo‘qon', f'+9989000000{cid}', int(time.time())))
            core.record(db, agent, agent, cid, 'delivery', 1, 5, 0, '', 100 + cid, currency='USD')
        db.commit()
        db.close()
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            cls.port = s.getsockname()[1]
        cls.saved = (bot.TOKEN, bot.api, os.environ.get('PORT'), os.environ.get('WEBHOOK_SECRET'))
        bot.TOKEN = TOKEN
        bot.api = lambda *a, **k: {}
        os.environ['PORT'] = str(cls.port)
        os.environ['WEBHOOK_SECRET'] = 'test-secret'
        # SQLite connection must live in the server thread.
        base = f'http://127.0.0.1:{cls.port}'
        threading.Thread(target=lambda: bot.serve_webhook(core.connect(path, initialize=False), base),
                         daemon=True).start()
        for _ in range(50):
            try:
                socket.create_connection(('127.0.0.1', cls.port), timeout=.2).close()
                break
            except OSError:
                time.sleep(.1)

    @classmethod
    def tearDownClass(cls):
        bot.TOKEN, bot.api = cls.saved[0], cls.saved[1]
        for key, value in (('PORT', cls.saved[2]), ('WEBHOOK_SECRET', cls.saved[3])):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def post(self, path, uid, **payload):
        body = json.dumps({'initData': init_data(uid), **payload}).encode()
        origin = sorted(bot.SELF_MINIAPP_ORIGINS)[0]
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', body,
                                     {'Content-Type': 'application/json', 'Origin': origin})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw or b'{}')
            except ValueError:
                return e.code, {'raw': raw.decode('utf-8', 'replace')}

    def test_agent_cannot_request_other_agent_portfolio(self):
        code, data = self.post('/api/agent', 2, action='insights', period='month', agentId=3)
        self.assertEqual(code, 200, data)
        self.assertEqual(data['scope']['agentId'], 2)
        self.assertEqual({c['id'] for c in data['clients']}, {10})
        self.assertEqual({a['agentId'] for a in data['agents']}, {2})
        self.assertTrue(all(i['agentId'] == 2 for i in data['today']['items']))

    def test_agent_cannot_use_manager_api(self):
        code, _ = self.post('/api/manager', 2, action='insights', period='month')
        self.assertIn(code, (401, 403))

    def test_admin_can_filter_agent(self):
        code, data = self.post('/api/manager', 1, action='insights', period='month', agentId=3)
        self.assertEqual(code, 200, data)
        self.assertEqual({c['id'] for c in data['clients']}, {11})


if __name__ == '__main__':
    unittest.main()
