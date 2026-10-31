"""Savdo web paneli (kompyuter): savdo xodimi login/parol bilan kiradi va /api/shop ni Bearer sessiya orqali ishlatadi."""
import json
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

import bot
import core
import web_auth


class SavdoWebPasswordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = core.connect(os.path.join(self.tmp.name, 'w.sqlite3'))
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [(1, 'admin', 'Rahbar'), (5, 'sales', 'Sotuvchi')])
        self.sent = []
        self.saved = bot.send
        bot.send = lambda uid, text, *a, **k: self.sent.append((uid, text))

    def tearDown(self):
        bot.send = self.saved
        self.db.close()
        self.tmp.cleanup()

    def test_sales_gets_savdo_web_link(self):
        bot.handle_web_password(self.db, 5, 'sales', '/webparol sotuv')
        uid, text = self.sent[-1]
        self.assertEqual(uid, 5)
        self.assertIn('SAVDO WEB PANEL', text)
        self.assertIn('/app/savdo-web/', text)
        self.assertNotIn('/app/rahbar-web/', text)

    def test_admin_still_gets_rahbar_web_link(self):
        bot.handle_web_password(self.db, 1, 'admin', '/webparol')
        self.assertIn('/app/rahbar-web/', self.sent[-1][1])


class SavdoWebHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = os.path.join(cls.tmp.name, 'api.sqlite3')
        db = core.connect(path)
        db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                       [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali'), (5, 'sales', 'Sotuvchi')])
        _, cls.admin_pw = web_auth.issue_password(db, 1, 'boss')
        _, cls.agent_pw = web_auth.issue_password(db, 2, 'ali')
        _, cls.sales_pw = web_auth.issue_password(db, 5, 'sotuv')
        db.commit()
        db.close()
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            cls.port = s.getsockname()[1]
        cls.saved = (bot.TOKEN, bot.api, os.environ.get('PORT'), os.environ.get('WEBHOOK_SECRET'))
        bot.TOKEN = '123:TEST'
        cls.sent = []
        bot.api = lambda method, **k: cls.sent.append(k) or {}
        os.environ['PORT'] = str(cls.port)
        os.environ['WEBHOOK_SECRET'] = 'test-secret'
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

    def post(self, path, token=None, native=False, **payload):
        headers = {'Content-Type': 'application/json'}
        if native:
            headers['X-Asman-Client'] = 'mobile'
        else:
            headers['Origin'] = sorted(bot.SELF_MINIAPP_ORIGINS)[0]
        if token:
            headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', json.dumps(payload).encode(), headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b'{}')

    def login(self, name, password, panel='savdo'):
        return self.post('/api/web', action='login', login=name, password=password, panel=panel)

    def test_page_is_served_without_telegram(self):
        with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/app/savdo-web/', timeout=10) as r:
            body = r.read().decode()
        self.assertIn('AIBI Savdo Web', body)
        self.assertNotIn('telegram-web-app.js', body)

    def test_sales_logs_in_and_uses_shop_api(self):
        code, data = self.login('sotuv', self.sales_pw)
        self.assertEqual(code, 200, data)
        token = data['token']
        code, me = self.post('/api/web', token, action='me', panel='savdo')
        self.assertEqual((code, me['me']['id']), (200, 5), me)
        code, dash = self.post('/api/shop', token, action='dashboard')
        self.assertEqual(code, 200, dash)
        self.assertEqual(dash['me']['id'], 5)
        self.post('/api/web', token, action='logout', panel='savdo')
        code, data = self.post('/api/shop', token, action='dashboard')
        self.assertEqual(code, 401)
        self.assertTrue(data.get('relogin'))

    def test_sales_cannot_enter_rahbar_panel(self):
        code, _ = self.login('sotuv', self.sales_pw, panel=None)
        self.assertEqual(code, 403)

    def test_agent_cannot_enter_savdo_panel(self):
        code, _ = self.login('ali', self.agent_pw)
        self.assertEqual(code, 403)

    def test_admin_can_use_savdo_panel(self):
        code, data = self.login('boss', self.admin_pw)
        self.assertEqual(code, 200, data)
        self.assertTrue(data['otp'])             # rahbarga brauzerda kod so'raladi
        self.assertNotIn('token', data)
        msg = self.sent[-1]
        self.assertEqual(msg['chat_id'], 1)
        otp = msg['text'].split(': ', 1)[1][:6]
        code, data = self.post('/api/web', action='verify_otp', challenge=data['challenge'], code=otp, panel='savdo')
        self.assertEqual(code, 200, data)
        code, dash = self.post('/api/shop', data['token'], action='dashboard')
        self.assertEqual(code, 200, dash)
        code, again = self.post('/api/web', action='login', login='boss', password=self.admin_pw, panel='savdo', device=data['device'])
        self.assertIn('token', again)            # ishonchli brauzerda kod qayta so'ralmaydi

    def test_sales_gets_no_code(self):
        code, data = self.login('sotuv', self.sales_pw)
        self.assertEqual(code, 200, data)
        self.assertIn('token', data)

    def test_old_phone_app_admin_still_logs_in(self):
        # Eski APK kod oynasini bilmaydi: native ilovada kod hali so'ralmaydi.
        code, data = self.post('/api/web', native=True, action='login', login='boss', password=self.admin_pw, panel='savdo')
        self.assertEqual(code, 200, data)
        self.assertIn('token', data)

    def test_phone_app_logs_in_as_sales_only(self):
        code, data = self.post('/api/web', native=True, action='login', login='sotuv', password=self.sales_pw, panel='savdo')
        self.assertEqual(code, 200, data)
        self.assertEqual(data['role'], 'sales')
        code, dash = self.post('/api/shop', data['token'], native=True, action='dashboard')
        self.assertEqual(code, 200, dash)
        # Telefon ilovasi rahbar paneli login'idan foydalana olmaydi.
        code, _ = self.post('/api/web', native=True, action='login', login='boss', password=self.admin_pw)
        self.assertEqual(code, 403)
        # Origin ham, belgi ham bo'lmasa — rad etiladi.
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}/api/web', json.dumps({'action': 'login', 'panel': 'savdo'}).encode(),
                                     {'Content-Type': 'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(e.exception.code, 403)

    def test_shop_rejects_missing_or_bad_token(self):
        self.assertEqual(self.post('/api/shop', 'x' * 43, action='dashboard')[0], 401)
        self.assertEqual(self.post('/api/shop', action='dashboard')[0], 401)


if __name__ == '__main__':
    unittest.main()
