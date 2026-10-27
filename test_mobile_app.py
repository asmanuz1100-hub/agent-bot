"""ASMAN mobil ilova (Android/iOS): login/parol, /api/agent Bearer sessiya, GPS va pul oqimi.

Mobil ilova Telegram bot bilan bitta baza va bitta biznes logikadan foydalanadi:
yozuvlar agent_api.mutate orqali o'tadi, qarz va kassa ikki marta hisoblanmaydi."""
import json
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

import agent_api
import bot
import core
import web_auth


class MobilePointTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [(2, 'agent', 'Ali'), (4, 'agent', 'Other')])
        self.now = 1_800_000_000

    def tearDown(self):
        self.db.close()

    def test_point_needs_open_shift_and_good_accuracy(self):
        with self.assertRaisesRegex(ValueError, 'boshlang'):
            agent_api.mobile_point(self.db, 2, {'lat': 40.5, 'lon': 70.9, 'accuracy': 10}, self.now)
        self.db.execute('INSERT INTO shifts(id,agent,start) VALUES(5,2,?)', (self.now - 60,))
        for bad in ({'lat': 40.5, 'lon': 70.9, 'accuracy': 900}, {'lat': 140, 'lon': 70.9, 'accuracy': 5},
                    {'lat': 40.5, 'lon': 70.9}, {'lat': 'x', 'lon': 70.9, 'accuracy': 5}):
            with self.assertRaisesRegex(ValueError, 'GPS'):
                agent_api.mobile_point(self.db, 2, bad, self.now)
        with self.assertRaises(ValueError):
            agent_api.mobile_point(self.db, 4, {'lat': 40.5, 'lon': 70.9, 'accuracy': 5}, self.now)

    def test_point_claims_shift_and_unlocks_live_ready(self):
        self.db.execute('INSERT INTO shifts(id,agent,start) VALUES(5,2,?)', (self.now - 60,))
        self.assertFalse(agent_api._live_ready(self.db, 2, now=self.now)[0])
        out = agent_api.mobile_point(self.db, 2, {'lat': 40.5, 'lon': 70.9, 'accuracy': 12}, self.now)
        self.assertTrue(out['saved'])
        self.assertEqual(self.db.execute('SELECT live_id FROM shifts WHERE id=5').fetchone()[0], -5)
        self.assertTrue(agent_api._live_ready(self.db, 2, now=self.now)[0])
        # Too frequent pings are accepted but not stored twice.
        self.assertFalse(agent_api.mobile_point(self.db, 2, {'lat': 40.5, 'lon': 70.9, 'accuracy': 12}, self.now + 5)['saved'])
        self.assertTrue(agent_api.mobile_point(self.db, 2, {'lat': 40.6, 'lon': 70.9, 'accuracy': 12}, self.now + 20)['saved'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM points WHERE shift=5').fetchone()[0], 2)

    def test_telegram_live_shift_keeps_its_live_id(self):
        self.db.execute('INSERT INTO shifts(id,agent,start,live_id) VALUES(6,2,?,777)', (self.now - 60,))
        agent_api.mobile_point(self.db, 2, {'lat': 40.5, 'lon': 70.9, 'accuracy': 12}, self.now)
        self.assertEqual(self.db.execute('SELECT live_id FROM shifts WHERE id=6').fetchone()[0], 777)


class MobilePasswordCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = core.connect(os.path.join(self.tmp.name, 'c.sqlite3'))
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali'), (3, 'cashier', 'Kassir'), (5, 'disabled', 'Eski')])
        self.sent = []
        self.saved = bot.send, bot.api
        bot.send = lambda uid, text, keys=None: self.sent.append((uid, text))
        bot.api = lambda *a, **k: {}

    def tearDown(self):
        bot.send, bot.api = self.saved
        self.db.close()
        self.tmp.cleanup()

    def password(self):
        return self.sent[-1][1].split('Parol: ')[1].split()[0]

    def test_staff_get_own_login_but_disabled_users_do_not(self):
        bot.handle_mobile_password(self.db, 2, 'agent', '/mobilparol')
        self.assertIn('Login: agent2', self.sent[-1][1])
        self.assertEqual(web_auth.login(self.db, 'agent2', self.password())[0], 2)
        bot.handle_mobile_password(self.db, 3, 'cashier', '/mobilparol')
        self.assertEqual(web_auth.login(self.db, 'cashier3', self.password())[0], 3)
        with self.assertRaisesRegex(ValueError, 'rolingiz'):
            bot.handle_mobile_password(self.db, 5, 'disabled', '/mobilparol')

    def test_reissue_keeps_login_and_revoke_signs_out(self):
        bot.handle_mobile_password(self.db, 2, 'agent', '/mobilparol ali')
        _, token = web_auth.login(self.db, 'ali', self.password())
        bot.handle_mobile_password(self.db, 2, 'agent', '/mobilparol')
        self.assertIn('Login: ali', self.sent[-1][1])
        with self.assertRaises(ValueError):
            web_auth.session_user(self.db, token)
        bot.handle_mobile_password(self.db, 2, 'agent', '/mobilyopish')
        self.assertIsNone(web_auth.account(self.db, 2))

    def test_disabled_user_is_refused(self):
        with self.assertRaises(ValueError):
            bot.handle_mobile_password(self.db, 5, 'disabled', '/mobilparol')


class MobileHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = os.path.join(cls.tmp.name, 'api.sqlite3')
        db = core.connect(cls.path)
        db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                       [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali'), (3, 'cashier', 'Kassir'), (4, 'agent', 'Vali')])
        db.execute('UPDATE products SET price=? WHERE pack=1', (250,))
        core.record(db, 1, 2, None, 'load', 1, 30, source=7001, currency='USD')
        _, cls.agent_password = web_auth.issue_password(db, 2, 'ali')
        _, cls.vali_password = web_auth.issue_password(db, 4, 'vali')
        _, cls.cashier_password = web_auth.issue_password(db, 3, 'kassa')
        _, cls.admin_password = web_auth.issue_password(db, 1, 'boss')
        db.commit()
        db.close()
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            cls.port = s.getsockname()[1]
        db = core.connect(cls.path, initialize=False)
        db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [(5, 'agent', 'Gani')])
        core.record(db, 1, 5, None, 'load', 1, 20, source=7201, currency='USD')
        _, cls.gani_password = web_auth.issue_password(db, 5, 'gani')
        db.commit()
        db.close()
        cls.saved = (bot.TOKEN, bot.api, os.environ.get('PORT'), os.environ.get('WEBHOOK_SECRET'))
        bot.TOKEN = '123:TEST'
        bot.api = lambda *a, **k: {}
        os.environ['PORT'] = str(cls.port)
        os.environ['WEBHOOK_SECRET'] = 'test-secret'
        base = f'http://127.0.0.1:{cls.port}'
        threading.Thread(target=lambda: bot.serve_webhook(core.connect(cls.path, initialize=False), base),
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

    def post(self, path, token=None, native=True, origin=None, **payload):
        headers = {'Content-Type': 'application/json'}
        if native:
            headers['X-Asman-Client'] = 'mobile'
        if origin:
            headers['Origin'] = origin
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

    def login(self, name, password):
        code, data = self.post('/api/web', action='login', app='mobile', login=name, password=password)
        self.assertEqual(code, 200, data)
        return data

    def db(self):
        return core.connect(self.path, initialize=False)

    def test_only_agents_log_in_to_mobile_and_not_to_web_panel(self):
        self.assertEqual(self.login('ali', self.agent_password)['role'], 'agent')
        code, data = self.post('/api/web', action='login', app='mobile', login='kassa', password=self.cashier_password)
        self.assertEqual(code, 403, data)
        code, data = self.post('/api/web', action='login', app='mobile', login='boss', password=self.admin_password)
        self.assertEqual(code, 403, data)
        code, _ = self.post('/api/web', action='login', login='ali', password=self.agent_password)
        self.assertEqual(code, 403)
        token = self.login('ali', self.agent_password)['token']
        code, me = self.post('/api/web', token, action='me', app='mobile')
        self.assertEqual((code, me['role'], me['me']['id']), (200, 'agent', 2))

    def test_agent_api_requires_a_valid_session(self):
        code, data = self.post('/api/agent', action='snapshot')
        self.assertEqual(code, 401)
        code, data = self.post('/api/agent', 'x' * 43, action='snapshot')
        self.assertEqual(code, 401)
        self.assertTrue(data.get('relogin'))
        # Without the mobile client header the old browser rules apply (Origin required).
        token = self.login('ali', self.agent_password)['token']
        code, _ = self.post('/api/agent', token, native=False, action='snapshot')
        self.assertEqual(code, 403)
        code, _ = self.post('/api/agent', token, origin='https://evil.example', action='snapshot')
        self.assertEqual(code, 403)
        # Rahbar tokeni agent API'ni faqat admin rejimida ochadi (agentni tanlaydi), o'zi agent bo'lmaydi.
        code, data = self.post('/api/web', native=False, origin=sorted(bot.SELF_MINIAPP_ORIGINS)[0],
                               action='login', login='boss', password=self.admin_password)
        self.assertEqual(code, 200, data)
        code, out = self.post('/api/agent', data['token'], action='snapshot')
        self.assertEqual(code, 200, out)
        self.assertTrue(out.get('adminMode'), out)

    def test_logout_ends_the_session(self):
        token = self.login('ali', self.agent_password)['token']
        self.assertEqual(self.post('/api/agent', token, action='quick_snapshot')[0], 200)
        self.assertEqual(self.post('/api/web', token, action='logout')[0], 200)
        self.assertEqual(self.post('/api/agent', token, action='quick_snapshot')[0], 401)

    def test_shift_gps_payment_and_handover_from_the_app(self):
        token = self.login('vali', self.vali_password)['token']
        call = lambda **p: self.post('/api/agent', token, **p)
        code, out = call(action='location', lat=40.5, lon=70.9, accuracy=10)
        self.assertEqual(code, 400)
        self.assertIn('boshlang', out['error'])
        code, out = call(action='shift_start', requestId='m_shift_start_0001')
        self.assertEqual(code, 200, out)
        code, out = call(action='location', lat=40.54, lon=70.94, accuracy=9)
        self.assertEqual((code, out['saved']), (200, True), out)
        db = self.db()
        try:
            core.record(db, 1, 4, None, 'load', 1, 10, source=7101, currency='USD')
            cid = agent_api.mutate(db, 4, 'add_client', {'shopName': 'Mobil do‘kon', 'name': 'Sobir',
                                   'phone': '+998901110022', 'lat': 40.54, 'lon': 70.94}, 'm_client_000001')['clientId']
            db.commit()
        finally:
            db.close()
        code, out = call(action='delivery', clientId=cid, items=[{'pack': 1, 'qty': 4}], requestId='m_deliv_000001')
        self.assertEqual(code, 200, out)
        pay = dict(action='payment', clientId=cid, currency='USD', method='cash', amount='6', requestId='m_pay_0000001')
        code, out = call(**pay)
        self.assertEqual(code, 200, out)
        # The same request sent again (lost reply, retry) must not count twice.
        code, again = call(**pay)
        self.assertEqual((code, again.get('duplicate')), (200, True), again)
        code, snap = call(action='snapshot')
        self.assertEqual(code, 200, snap)
        client = next(c for c in snap['clients'] if c['id'] == cid)
        self.assertEqual(client['debtUsd'], 4)
        self.assertEqual(snap['summary']['cashOnHandUsd'], 6)
        # Money stays with the agent until the cashier accepts the handover.
        code, out = call(action='handover', currency='USD', amount='6', requestId='m_hand_0000001')
        self.assertEqual(code, 200, out)
        db = self.db()
        try:
            row = db.execute('SELECT status FROM handovers WHERE id=?', (out['handoverId'],)).fetchone()
            self.assertEqual(row['status'], 'pending')
        finally:
            db.close()
        code, out = call(action='shift_end', requestId='m_shift_end_00001')
        self.assertEqual(code, 200, out)
        code, out = call(action='location', lat=40.54, lon=70.94, accuracy=9)
        self.assertEqual(code, 400)

    def test_two_currency_payment_return_and_cashier_accept_stay_consistent(self):
        """Agent, kassir va qarz raqamlari bitta hisob-kitob mantig'idan: sotuv qarzni oshiradi,
        to'lov va qaytarish kamaytiradi, so'm va dollar alohida, topshirish ikki marta sanalmaydi."""
        token = self.login('gani', self.gani_password)['token']
        call = lambda **p: self.post('/api/agent', token, **p)
        self.assertEqual(call(action='shift_start', requestId='g_shift_start_01')[0], 200)
        self.assertEqual(call(action='location', lat=40.54, lon=70.94, accuracy=8)[0], 200)
        db = self.db()
        try:
            cid = agent_api.mutate(db, 5, 'add_client', {'shopName': 'Gani do‘kon', 'name': 'Olim',
                                   'phone': '+998901110033', 'lat': 40.54, 'lon': 70.94}, 'g_client_000001')['clientId']
            db.commit()
        finally:
            db.close()
        debt = lambda snap: next(c for c in snap['clients'] if c['id'] == cid)['debtUsd']
        # 5 x $2.50 = $12.50 qarz.
        code, out = call(action='delivery', clientId=cid, items=[{'pack': 1, 'qty': 5}], requestId='g_deliv_000001')
        self.assertEqual(code, 200, out)
        code, snap = call(action='snapshot')
        self.assertEqual(debt(snap), 12.5)
        # Bitta tashrifda: 25 000 so'm (kurs 12 500 = $2) va $3 naqd.
        code, out = call(action='payment', clientId=cid, requestId='g_pay_00000001',
                         parts=[{'currency': 'UZS', 'method': 'cash', 'amount': '25000', 'rate': '12500'},
                                {'currency': 'USD', 'method': 'cash', 'amount': '3'}])
        self.assertEqual(code, 200, out)
        code, snap = call(action='snapshot')
        self.assertEqual(debt(snap), 7.5)
        self.assertEqual((snap['summary']['cashOnHandUzs'], snap['summary']['cashOnHandUsd']), (25000, 3))
        # 1 dona qaytarildi: qarz $2.50 ga kamayadi, pul balansi o'zgarmaydi.
        code, out = call(action='return', clientId=cid, items=[{'pack': 1, 'qty': 1}], requestId='g_ret_00000001')
        self.assertEqual(code, 200, out)
        code, snap = call(action='snapshot')
        self.assertEqual(debt(snap), 5)
        self.assertEqual((snap['summary']['cashOnHandUzs'], snap['summary']['cashOnHandUsd']), (25000, 3))
        # So'mni kassirga topshirish: kassir qabul qilmaguncha mavjud qoldiqdan chegiriladi.
        code, out = call(action='handover', currency='UZS', amount='25000', requestId='g_hand_0000001')
        self.assertEqual(code, 200, out)
        hid = out['handoverId']
        code, snap = call(action='snapshot')
        self.assertEqual((snap['summary']['cashAvailableUzs'], snap['summary']['cashAvailableUsd']), (0, 3))
        code, out = call(action='handover', currency='UZS', amount='1000', requestId='g_hand_0000002')
        self.assertEqual(code, 400, out)
        db = self.db()
        try:
            before = core.cashier_balance_usd(db)
            core.accept(db, 3, hid)
            db.commit()
            with self.assertRaises(ValueError):
                core.accept(db, 3, hid)
            self.assertEqual(core.cashier_balance_usd(db) - before, 200)
        finally:
            db.close()
        code, snap = call(action='snapshot')
        # Pul agentdan chiqdi, dollar qoldig'i aralashmadi, qarz o'zgarmadi.
        self.assertEqual((snap['summary']['cashOnHandUzs'], snap['summary']['cashOnHandUsd']), (0, 3))
        self.assertEqual(debt(snap), 5)

    def test_aibi_app_login_opens_each_role_its_own_api(self):
        """AIBI APK: har bir rol o'z Mini App API'siga login tokeni bilan kiradi, boshqasiga emas."""
        site = sorted(bot.SELF_MINIAPP_ORIGINS)[0]
        def aibi_login(name, password):
            code, data = self.post('/api/web', action='login', app='aibi', login=name, password=password)
            self.assertEqual(code, 200, data)
            return data
        cashier = aibi_login('kassa', self.cashier_password)
        self.assertEqual(cashier['role'], 'cashier')
        # Mini App sahifasi ichidan (WebView, o'z Origin'i bilan) Bearer token bilan.
        code, data = self.post('/api/cashier', cashier['token'], native=False, origin=site, action='dashboard')
        self.assertEqual(code, 200, data)
        code, _ = self.post('/api/cashier', 'y' * 43, native=False, origin=site, action='dashboard')
        self.assertEqual(code, 401)
        code, _ = self.post('/api/manager', cashier['token'], native=False, origin=site, action='dashboard')
        self.assertEqual(code, 403)
        agent = aibi_login('ali', self.agent_password)
        code, _ = self.post('/api/cashier', agent['token'], native=False, origin=site, action='dashboard')
        self.assertEqual(code, 403)
        code, data = self.post('/api/agent', agent['token'], native=False, origin=site, action='snapshot')
        self.assertEqual(code, 200, data)
        boss = aibi_login('boss', self.admin_password)
        self.assertEqual(boss['role'], 'admin')
        code, data = self.post('/api/manager', boss['token'], native=False, origin=site, action='dashboard')
        self.assertEqual(code, 200, data)
        # Rahbar ilovada barcha panellarni ochadi: agent (admin rejimi), kassa, ombor, savdo.
        for path in ('/api/agent', '/api/cashier', '/api/warehouse', '/api/shop'):
            code, data = self.post(path, boss['token'], native=False, origin=site, action='dashboard')
            self.assertEqual(code, 200, (path, data))
        db = self.db()
        try:
            db.execute("INSERT INTO users(id,role,name) VALUES(6,'disabled','Eski')")
            _, old = web_auth.issue_password(db, 6, 'eski')
            db.commit()
        finally:
            db.close()
        code, _ = self.post('/api/web', action='login', app='aibi', login='eski', password=old)
        self.assertEqual(code, 403)

    def test_apk_download_and_bot_button(self):
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}/download/aibi.apk')
        with urllib.request.urlopen(req, timeout=30) as r:
            self.assertEqual(r.headers['Content-Type'], 'application/vnd.android.package-archive')
            head = r.read(4)
            self.assertEqual(int(r.headers['Content-Length']), bot.APP_APK_FILE.stat().st_size)
        self.assertEqual(head, b'PK\x03\x04')
        size = bot.APP_APK_FILE.stat().st_size
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}/download/aibi.apk', method='HEAD')
        with urllib.request.urlopen(req, timeout=10) as r:
            self.assertEqual((r.status, int(r.headers['Content-Length']), r.headers['Accept-Ranges']), (200, size, 'bytes'))
        # Uzilgan yuklash davom ettiriladi: oxirgi 10 bayt.
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}/download/aibi.apk', headers={'Range': f'bytes={size - 10}-'})
        with urllib.request.urlopen(req, timeout=10) as r:
            self.assertEqual(r.status, 206)
            self.assertEqual(r.headers['Content-Range'], f'bytes {size - 10}-{size - 1}/{size}')
            self.assertEqual(r.read(), bot.APP_APK_FILE.read_bytes()[-10:])
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}/download/aibi.apk', headers={'Range': f'bytes={size}-'})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(e.exception.code, 416)
        calls = []
        saved = bot.api
        bot.api = lambda method, **k: calls.append((method, k)) or {}
        files = []
        saved_file = bot.send_app_file
        bot.send_app_file = files.append
        try:
            db = self.db()
            try:
                bot.handle(db, {'update_id': 990001, 'message': {'chat': {'id': 3, 'type': 'private'}, 'from': {'id': 3}, 'text': '/ilova'}})
            finally:
                db.close()
        finally:
            bot.api, bot.send_app_file = saved, saved_file
        self.assertEqual(files, [3])
        msg = [k for m, k in calls if m == 'sendMessage' and 'reply_markup' in k]
        self.assertTrue(msg, calls)
        self.assertEqual(msg[-1]['reply_markup']['inline_keyboard'][0][0]['url'], bot.app_download_url())

    def test_every_staff_menu_has_the_app_button(self):
        db = self.db()
        try:
            db.executemany('INSERT OR IGNORE INTO users(id,role,name) VALUES(?,?,?)', [(7, 'warehouse', 'Omborchi'), (8, 'sales', 'Sotuvchi')])
            for uid in (1, 2, 3, 7, 8):
                self.assertIn(['📲 Ilova'], bot.menu(db, uid), uid)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
