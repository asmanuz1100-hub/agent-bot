"""Korxona bo'limlari: yoqish/o'chirish, server cheklovi (web, Mini App, bot), audit, ma'lumot saqlanishi."""
import hashlib
import hmac
import json
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from urllib.parse import urlencode

import bot
import core
import hr
import modules
import web_auth

TOKEN = '123:TEST'


def signed_init_data(user_id):
    fields = {'auth_date': str(int(time.time())), 'query_id': 'AAE', 'user': json.dumps({'id': user_id, 'first_name': 'T'})}
    check = '\n'.join(f'{k}={v}' for k, v in sorted(fields.items()))
    key = hmac.new(b'WebAppData', TOKEN.encode(), hashlib.sha256).digest()
    fields['hash'] = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class ModuleUnitTests(unittest.TestCase):
    def test_history_sql_has_no_literal_percent_for_postgres(self):
        # psycopg treats a bare % in the SQL text as a placeholder: LIKE patterns must be parameters.
        seen, db = [], self.db

        class Spy:
            def execute(self, sql, *a):
                seen.append(sql)
                return db.execute(sql, *a)
        modules.history(Spy())
        sql = core._pg_sql(seen[0])
        self.assertNotRegex(sql.replace('%s', ''), '%')

    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali'), (3, 'cashier', 'Kassir'), (5, 'warehouse', 'Ombor')])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_default_all_enabled_and_toggle_audited(self):
        self.assertTrue(all(modules.state(self.db).values()))   # eski korxonalar o'zgarishsiz
        modules.set_enabled(self.db, 1, 'cash', False)
        modules.set_enabled(self.db, 1, 'cash', False)         # takror — tarixga ikkinchi yozuv tushmaydi
        self.assertFalse(modules.enabled(self.db, 'cash'))
        modules.set_enabled(self.db, 1, 'cash', True)
        h = modules.history(self.db)
        self.assertEqual([(x['module'], x['on']) for x in h], [('cash', True), ('cash', False)])
        self.assertEqual(h[0]['who'], 'Rahbar')
        with self.assertRaises(ValueError):
            modules.set_enabled(self.db, 1, 'settings', False)  # sozlamalarni yopib bo'lmaydi

    def test_require_action_and_dependency(self):
        modules.require_action(self.db, 'dashboard')            # doim ochiq
        modules.require_action(self.db, 'staff_list')
        modules.set_enabled(self.db, 1, 'cash', False)
        with self.assertRaises(modules.ModuleClosed):
            modules.require_action(self.db, 'cash_period')
        modules.require_action(self.db, 'hr', 'overview')       # oylik ko'rish ochiq
        modules.require_action(self.db, 'hr', 'attendance_set')
        with self.assertRaisesRegex(modules.ModuleClosed, 'Kassa'):
            modules.require_action(self.db, 'hr', 'pay_add')    # pul to'lash kassaga bog'liq
        with self.assertRaisesRegex(modules.ModuleClosed, 'Kassa'):
            modules.require_action(self.db, 'supply', 'pay')
        modules.require_action(self.db, 'supply', 'purchase')
        self.assertTrue(modules.enabled(self.db, 'warehouse'))  # bog'liq bo'lim yashirincha yoqilmaydi/o'chmaydi
        self.assertFalse(modules.enabled(self.db, 'cash'))

    def test_bot_blocks_closed_role_but_not_admin(self):
        modules.set_enabled(self.db, 1, 'cash', False)
        self.db.commit()
        msg = lambda uid, text: {'update_id': 1, 'message': {'message_id': 1, 'date': int(time.time()), 'from': {'id': uid},
                                                           'chat': {'id': uid, 'type': 'private'}, 'text': text}}
        with patch.object(bot, 'send') as send, patch.object(bot, 'ADMINS', {1}):
            bot.handle(self.db, msg(3, '📱 Кассир Mini App'))
            self.assertIn('Kassa', send.call_args[0][1])
            send.reset_mock()
            bot.handle(self.db, msg(5, '/start'))                # ombor yoqiq — bloklanmaydi
            self.assertNotIn('o‘chirilgan', ' '.join(str(c) for c in send.call_args_list))

    def test_data_survives_disable_enable(self):
        wid = hr.add_worker(self.db, 1, {'name': 'Ishchi', 'salary': '1000'})
        modules.set_enabled(self.db, 1, 'hr', False)
        modules.set_enabled(self.db, 1, 'hr', True)
        self.assertEqual(hr.salary_for(self.db, wid, hr.this_month()), 1000)


class HttpBase(unittest.TestCase):
    """Haqiqiy HTTP server (vaqtinchalik SQLite). Testlarsiz — boshqa fayllar meros oladi."""
    USERS = [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali'), (3, 'cashier', 'Kassir'), (4, 'admin', 'Ikkinchi')]

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = cls.db_path = os.path.join(cls.tmp.name, 'm.sqlite3')
        db = core.connect(path)
        db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', cls.USERS)
        _, cls.password = web_auth.issue_password(db, 1, 'boss')
        _, cls.password2 = web_auth.issue_password(db, 4, 'second')
        db.commit()
        db.close()
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            cls.port = s.getsockname()[1]
        cls.saved = (bot.TOKEN, bot.api, os.environ.get('PORT'), os.environ.get('WEBHOOK_SECRET'), set(bot.ADMINS))
        bot.TOKEN = TOKEN
        bot.api = lambda *a, **k: {}
        bot.ADMINS.clear()
        bot.ADMINS.add(1)
        os.environ['PORT'] = str(cls.port)
        os.environ['WEBHOOK_SECRET'] = 'test-secret'
        threading.Thread(target=lambda: bot.serve_webhook(core.connect(path, initialize=False), f'http://127.0.0.1:{cls.port}'),
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
        bot.ADMINS.clear()
        bot.ADMINS.update(cls.saved[4])
        for key, value in (('PORT', cls.saved[2]), ('WEBHOOK_SECRET', cls.saved[3])):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def post(self, path, token=None, **payload):
        headers = {'Content-Type': 'application/json', 'Origin': sorted(bot.SELF_MINIAPP_ORIGINS)[0]}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', json.dumps(payload).encode(), headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b'{}')

    def token(self, login='boss', password=None):
        code, d = self.post('/api/web', action='login', login=login, password=password or self.password)
        self.assertEqual(code, 200, d)
        return d['token']



class ModuleHttpTests(HttpBase):
    def test_toggle_closes_menu_api_miniapp_and_reopens(self):
        t = self.token()
        code, d = self.post('/api/manager', t, action='dashboard')
        self.assertEqual(code, 200, d)
        self.assertTrue(d['modules']['cash'])
        # ikkinchi darajali rahbar bo'limni o'chira olmaydi
        t2 = self.token('second', self.password2)
        code, d = self.post('/api/manager', t2, action='module_set', module='cash', enabled=False)
        self.assertEqual(code, 403, d)
        code, d = self.post('/api/manager', t, action='hr', op='worker_add', name='Usta', salary='1000', requestId='modtest001')
        self.assertEqual(code, 200, d)
        wid = d['worker']['id']
        try:
            code, d = self.post('/api/manager', t, action='module_set', module='cash', enabled=False)
            self.assertEqual(code, 200, d)
            self.assertFalse(next(m for m in d['items'] if m['key'] == 'cash')['enabled'])
            self.assertFalse(d['modules']['cash'])
            code, d = self.post('/api/manager', t, action='cash_period')
            self.assertEqual((code, d.get('moduleClosed')), (403, True))
            code, d = self.post('/api/manager', t, action='hr', op='pay_add', id=wid, kind='advance', amount='10', requestId='modtest002')
            self.assertEqual(code, 403, d)
            self.assertIn('Kassa', d['error'])
            code, d = self.post('/api/manager', t, action='hr', op='overview')
            self.assertEqual(code, 200, d)                       # oylik hisobini ko'rish ochiq
            self.assertFalse(d['modules']['cash'])
            code, d = self.post('/api/cashier', initData=signed_init_data(3), action='dashboard')
            self.assertEqual(code, 403, d)                       # kassir ilovasi ham yopiq
            self.assertIn('Kassa', d['error'])
            code, d = self.post('/api/manager', t, action='dashboard')
            self.assertEqual(code, 200, d)                       # asosiy sahifa doim ochiq
            code, d = self.post('/api/manager', t, action='modules')
            self.assertEqual(code, 200, d)
        finally:
            code, d = self.post('/api/manager', t, action='module_set', module='cash', enabled=True)
            self.assertEqual(code, 200, d)
        code, d = self.post('/api/cashier', initData=signed_init_data(3), action='dashboard')
        self.assertEqual(code, 200, d)
        code, d = self.post('/api/manager', t, action='hr', op='worker', id=wid)
        self.assertEqual(d['worker']['salary'], 1000)            # ma'lumot joyida

    def test_agent_app_closed_with_agents_module(self):
        t = self.token()
        try:
            self.post('/api/manager', t, action='module_set', module='agents', enabled=False)
            code, d = self.post('/api/agent', initData=signed_init_data(2), action='dashboard')
            self.assertEqual(code, 403, d)
            self.assertIn('Agentlar', d['error'])
            code, d = self.post('/api/manager', t, action='agent_management')
            self.assertEqual(code, 403, d)
        finally:
            self.post('/api/manager', t, action='module_set', module='agents', enabled=True)
        code, d = self.post('/api/manager', t, action='agent_management')
        self.assertEqual(code, 200, d)


if __name__ == '__main__':
    unittest.main()


class WebBackupHttpTests(HttpBase):
    def test_primary_admin_prepares_and_downloads_backup(self):
        import io, zipfile
        t2 = self.token('second', self.password2)
        code, d = self.post('/api/manager', t2, action='full_backup', op='start')
        self.assertEqual(code, 403, d)                       # faqat asosiy rahbar
        t = self.token()
        with patch.object(bot, 'customer_photo_bytes', return_value=b'\xff\xd8\xff photo'):
            code, d = self.post('/api/manager', t, action='full_backup', op='start')
            self.assertEqual(code, 200, d)
            for _ in range(100):
                code, d = self.post('/api/manager', t, action='full_backup', op='status')
                if d.get('status') != 'running':
                    break
                time.sleep(.1)
        self.assertEqual(d['status'], 'ready', d)
        self.assertNotIn('path', d)                          # server yo'li panelga chiqmaydi
        headers = {'Content-Type': 'application/json', 'Origin': sorted(bot.SELF_MINIAPP_ORIGINS)[0], 'Authorization': 'Bearer ' + t}
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}/api/manager',
                                     json.dumps({'action': 'full_backup', 'op': 'download'}).encode(), headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            self.assertEqual(r.headers['Content-Type'], 'application/zip')
            body = r.read()
        with zipfile.ZipFile(io.BytesIO(body)) as outer:
            names = outer.namelist()
            data = next(n for n in names if n.startswith('ASMAN-full-data-'))
            with zipfile.ZipFile(io.BytesIO(outer.read(data))) as inner:
                self.assertIn('database/clients.json', inner.namelist())
                self.assertNotIn('database/web_accounts.json', inner.namelist())
        bot._web_backup_drop()
