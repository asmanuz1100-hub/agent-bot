"""Rahbar web paneli (kompyuter): login/parol, sessiya va /api/manager orqali ishlash."""
import json
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import bot
import core
import web_auth


class WebAuthUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = core.connect(os.path.join(self.tmp.name, 'w.sqlite3'))
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [(1, 'admin', 'Rahbar'), (2, 'admin', 'Ikkinchi')])

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_password_is_hashed_and_checked(self):
        login, password = web_auth.issue_password(self.db, 1)
        self.assertEqual(login, 'rahbar1')
        stored = self.db.execute('SELECT pw_hash FROM web_accounts WHERE user_id=1').fetchone()[0]
        self.assertNotIn(password, stored)
        self.assertTrue(web_auth.check_password(password, stored))
        self.assertFalse(web_auth.check_password(password + 'x', stored))

    def test_login_session_logout(self):
        login, password = web_auth.issue_password(self.db, 1, 'boss')
        uid, token = web_auth.login(self.db, 'BOSS', password)
        self.assertEqual(uid, 1)
        self.assertEqual(web_auth.session_user(self.db, token), 1)
        self.assertNotIn(token, json.dumps([tuple(r) for r in self.db.execute('SELECT * FROM web_sessions').fetchall()]))
        web_auth.logout(self.db, token)
        with self.assertRaises(ValueError):
            web_auth.session_user(self.db, token)

    def test_session_expires(self):
        _, password = web_auth.issue_password(self.db, 1)
        _, token = web_auth.login(self.db, 'rahbar1', password, now=1000)
        self.assertEqual(web_auth.session_user(self.db, token, now=1000 + 86400), 1)
        with self.assertRaises(ValueError):
            web_auth.session_user(self.db, token, now=1000 + web_auth.SESSION_DAYS * 86400 + 1)

    def test_lockout_after_repeated_failures(self):
        _, password = web_auth.issue_password(self.db, 1)
        for _ in range(web_auth.MAX_FAILS):
            with self.assertRaises(ValueError):
                web_auth.login(self.db, 'rahbar1', 'wrong-pass', now=5000)
        with self.assertRaisesRegex(ValueError, 'daqiqadan'):
            web_auth.login(self.db, 'rahbar1', password, now=5001)
        uid, _ = web_auth.login(self.db, 'rahbar1', password, now=5000 + web_auth.LOCK_SECONDS + 1)
        self.assertEqual(uid, 1)

    def test_reset_signs_out_everywhere_and_login_must_be_unique(self):
        _, password = web_auth.issue_password(self.db, 1, 'boss')
        _, token = web_auth.login(self.db, 'boss', password)
        web_auth.issue_password(self.db, 1)
        with self.assertRaises(ValueError):
            web_auth.session_user(self.db, token)
        with self.assertRaisesRegex(ValueError, 'band'):
            web_auth.issue_password(self.db, 2, 'boss')
        with self.assertRaises(ValueError):
            web_auth.issue_password(self.db, 2, 'a b')

    def test_change_password_keeps_current_session_only(self):
        _, password = web_auth.issue_password(self.db, 1)
        _, keep = web_auth.login(self.db, 'rahbar1', password)
        _, other = web_auth.login(self.db, 'rahbar1', password)
        with self.assertRaises(ValueError):
            web_auth.change_password(self.db, 1, 'wrong', 'new-password-1', keep)
        with self.assertRaises(ValueError):
            web_auth.change_password(self.db, 1, password, 'short', keep)
        web_auth.change_password(self.db, 1, password, 'new-password-1', keep)
        self.assertEqual(web_auth.session_user(self.db, keep), 1)
        with self.assertRaises(ValueError):
            web_auth.session_user(self.db, other)
        with self.assertRaises(ValueError):
            web_auth.login(self.db, 'rahbar1', password)
        self.assertEqual(web_auth.login(self.db, 'rahbar1', 'new-password-1')[0], 1)


class WebPanelDesignSystemTests(unittest.TestCase):
    """Phase 1: spetsifikatsiya ranglari, Inter shrifti, global qidiruv, emoji'siz menyu."""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'miniapps', 'rahbar-web')

    def read(self, name):
        with open(os.path.join(self.base, name), encoding='utf-8') as f:
            return f.read()

    def test_spec_tokens_and_font(self):
        css = self.read('app.css')
        for token in ('--bg:#F8FAFC', '--card:#FFFFFF', '--pri:#2563EB', '--tx:#0F172A', '--mu:#64748B',
                      '--line:#E2E8F0', '--ok:#16A34A', '--warn:#F59E0B', '--bad:#DC2626'):
            self.assertIn(token, css)
        self.assertIn('family=Inter', self.read('index.html'))

    def test_light_theme_is_default_and_search_is_present(self):
        html = self.read('index.html')
        self.assertIn("getItem('rw-theme')||'light'", html)
        self.assertIn('id="gq"', html)

    def test_navigation_uses_icons_not_emoji(self):
        js = self.read('app.js')
        pages = js[js.index('var PAGES=['):js.index('];', js.index('var PAGES=['))]
        self.assertNotRegex(pages, '[\U0001F300-\U0001FAFF\u2600-\u27BF]')


class AgentRouteAnyDayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = core.connect(os.path.join(self.tmp.name, 'r.sqlite3'))
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali')])
        # 2026-10-10 10:00 Toshkent: bitta smena, ikki GPS nuqta
        self.day = int(datetime(2026, 10, 10, 10, tzinfo=ZoneInfo('Asia/Tashkent')).timestamp())
        sid = self.db.execute('INSERT INTO shifts(agent,start,"end") VALUES(2,?,?)', (self.day, self.day + 7200)).lastrowid
        self.db.executemany('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,5)',
                            [(sid, self.day + 60, 40.5, 71.6), (sid, self.day + 600, 40.51, 71.61)])
        self.now = self.day + 9 * 86400

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_custom_day_returns_only_that_day(self):
        import manager_api
        d = manager_api.agent_period_detail(self.db, 2, 'custom', now=self.now, date_from='2026-10-10', date_to='2026-10-10')
        self.assertEqual(d['route']['gpsTotal'], 2)
        self.assertEqual(d['label'], '10.10.2026 – 10.10.2026')
        other = manager_api.agent_period_detail(self.db, 2, 'custom', now=self.now, date_from='2026-10-11', date_to='2026-10-11')
        self.assertEqual(other['route']['gpsTotal'], 0)

    def test_custom_range_is_limited(self):
        import manager_api
        with self.assertRaises(ValueError):
            manager_api.agent_period_detail(self.db, 2, 'custom', now=self.now, date_from='2026-08-01', date_to='2026-10-10')
        with self.assertRaises(ValueError):
            manager_api.agent_period_detail(self.db, 2, 'year', now=self.now)


class WebPanelBotCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = core.connect(os.path.join(self.tmp.name, 'c.sqlite3'))
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali')])
        self.sent = []
        self.saved = bot.send
        bot.send = lambda uid, text, keys=None: self.sent.append((uid, text))

    def tearDown(self):
        bot.send = self.saved
        self.db.close()
        self.tmp.cleanup()

    def test_admin_gets_login_and_password(self):
        bot.handle_web_password(self.db, 1, 'admin', '/webparol boss')
        uid, text = self.sent[-1]
        self.assertEqual(uid, 1)
        self.assertIn('Login: boss', text)
        self.assertIn('/app/rahbar-web/', text)
        password = text.split('Parol: ')[1].split()[0]
        self.assertEqual(web_auth.login(self.db, 'boss', password)[0], 1)
        bot.handle_web_password(self.db, 1, 'admin', '/webyopish')
        self.assertIsNone(web_auth.account(self.db, 1))

    def test_agent_cannot_get_web_password(self):
        with self.assertRaises(ValueError):
            bot.handle_web_password(self.db, 2, 'agent', '/webparol')


class WebPanelHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = os.path.join(cls.tmp.name, 'api.sqlite3')
        db = core.connect(path)
        db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                       [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali'), (3, 'admin', 'Sobiq')])
        _, cls.password = web_auth.issue_password(db, 1, 'boss')
        _, cls.agent_password = web_auth.issue_password(db, 2, 'ali')
        db.commit()
        db.close()
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            cls.port = s.getsockname()[1]
        cls.saved = (bot.TOKEN, bot.api, os.environ.get('PORT'), os.environ.get('WEBHOOK_SECRET'))
        bot.TOKEN = '123:TEST'
        bot.api = lambda *a, **k: {}
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

    def post(self, path, token=None, origin=None, **payload):
        headers = {'Content-Type': 'application/json', 'Origin': origin or sorted(bot.SELF_MINIAPP_ORIGINS)[0]}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', json.dumps(payload).encode(), headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw or b'{}')
            except ValueError:
                return e.code, {'raw': raw.decode('utf-8', 'replace')}

    def login(self, name='boss', password=None):
        return self.post('/api/web', action='login', login=name, password=password or self.password)

    def test_panel_page_is_served(self):
        with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/app/rahbar-web/', timeout=10) as r:
            body = r.read().decode()
        self.assertIn('Rahbar paneli', body)
        self.assertNotIn('telegram-web-app.js', body)

    def test_login_then_use_manager_api(self):
        code, data = self.login()
        self.assertEqual(code, 200, data)
        token = data['token']
        code, me = self.post('/api/web', token, action='me')
        self.assertEqual(code, 200, me)
        self.assertEqual((me['login'], me['me']['id']), ('boss', 1))
        code, dash = self.post('/api/manager', token, action='dashboard')
        self.assertEqual(code, 200, dash)
        self.assertIn('summary', dash)
        code, ex = self.post('/api/manager', token, action='executive', period='d7')
        self.assertEqual(code, 200, ex)
        self.assertEqual(len(ex['kpis']), 6)
        code, bad = self.post('/api/manager', token, action='executive', period='year')
        self.assertEqual(code, 400, bad)
        code, _ = self.post('/api/web', token, action='logout')
        self.assertEqual(code, 200)
        code, data = self.post('/api/manager', token, action='dashboard')
        self.assertEqual(code, 401)
        self.assertTrue(data.get('relogin'))

    def test_wrong_password_and_bad_token(self):
        code, data = self.login(password='nope-nope')
        self.assertEqual(code, 400)
        self.assertIn('noto‘g‘ri', data['error'])
        code, _ = self.post('/api/manager', 'x' * 43, action='dashboard')
        self.assertEqual(code, 401)
        code, _ = self.post('/api/manager', action='dashboard')
        self.assertEqual(code, 401)

    def test_non_admin_cannot_log_in(self):
        code, data = self.login('ali', self.agent_password)
        self.assertEqual(code, 403, data)

    def test_foreign_origin_is_rejected(self):
        code, _ = self.post('/api/web', origin='https://evil.example', action='login', login='boss', password=self.password)
        self.assertEqual(code, 403)


if __name__ == '__main__':
    unittest.main()
