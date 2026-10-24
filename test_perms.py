"""Xodim ruxsatlari: rol standarti, individual o'zgartirish, audit, himoyalar va server tekshiruvi."""
import unittest

import core
import hr
import perms
from test_modules import HttpBase, signed_init_data

PRIMARY = {1}


class PermUnitTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'Admin'), (4, 'admin', 'Rahbar'), (3, 'cashier', 'Kassir'),
                             (5, 'warehouse', 'Ombor'), (6, 'sales', 'Sotuvchi'), (2, 'agent', 'Ali')])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_role_defaults(self):
        self.assertEqual(perms.effective(self.db, 1, PRIMARY), set(perms.CATALOG))
        self.assertIn('cash.expense', perms.effective(self.db, 3, PRIMARY))
        self.assertNotIn('warehouse.receive', perms.effective(self.db, 3, PRIMARY))
        self.assertIn('warehouse.receive', perms.effective(self.db, 5, PRIMARY))
        rahbar = perms.effective(self.db, 4, PRIMARY)
        self.assertIn('hr.salary_view', rahbar)
        self.assertNotIn('hr.pay', rahbar)             # avvalgidek: pul to'lash faqat Admin
        self.assertNotIn('warehouse.receive', rahbar)
        self.assertEqual(perms.effective(self.db, 2, PRIMARY), set())

    def test_grant_revoke_reset_and_audit(self):
        perms.set_perms(self.db, 1, 4, {'hr.pay': True, 'reports.export': False}, PRIMARY)
        eff = perms.effective(self.db, 4, PRIMARY)
        self.assertIn('hr.pay', eff)
        self.assertNotIn('reports.export', eff)
        perms.set_perms(self.db, 1, 4, {'hr.pay': None}, PRIMARY)       # rol standartiga qaytadi
        self.assertNotIn('hr.pay', perms.effective(self.db, 4, PRIMARY))
        hist = perms.staff_view(self.db, 4, PRIMARY)['history']
        self.assertEqual([(h['perm'], h['on']) for h in hist][:3], [('hr.pay', False), ('reports.export', False), ('hr.pay', True)])
        self.assertEqual(hist[0]['who'], 'Admin')

    def test_protections(self):
        with self.assertRaises(perms.Denied):      # rahbar ruxsat bera olmaydi
            perms.set_perms(self.db, 4, 3, {'cash.view': False}, PRIMARY)
        with self.assertRaises(perms.Denied):      # o'ziga huquq bera olmaydi
            perms.set_perms(self.db, 1, 1, {'hr.pay': True}, PRIMARY)
        with self.assertRaises(perms.Denied):      # Admin (oxirgi admin) huquqsiz qolmaydi
            perms.set_perms(self.db, 1, 1, {'cash.view': False}, PRIMARY)
        with self.assertRaises(ValueError):        # sotuvchi/agent — o'z bo'limida
            perms.set_perms(self.db, 1, 6, {'cash.view': True}, PRIMARY)
        with self.assertRaises(ValueError):
            perms.set_perms(self.db, 1, 3, {'nonsense': True}, PRIMARY)
        with self.assertRaises(ValueError):        # kassir tovar harakatini kirita olmaydi (omborchi ishi)
            perms.set_perms(self.db, 1, 3, {'warehouse.receive': True}, PRIMARY)
        # kassirga omborni ko'rish — boshqa bo'limdan ishlaydigan ruxsat
        self.assertEqual({p['key'] for p in perms.staff_view(self.db, 3, PRIMARY)['perms'] if p['section'] != 'cash'}, {'warehouse.view'})
        self.assertFalse(perms.open_section(self.db, 3, 'warehouse', PRIMARY))
        perms.set_perms(self.db, 1, 3, {'warehouse.view': True}, PRIMARY)
        self.assertTrue(perms.open_section(self.db, 3, 'warehouse', PRIMARY))
        perms.set_perms(self.db, 1, 5, {'cash.view': True}, PRIMARY)
        self.assertTrue(perms.open_section(self.db, 5, 'cash', PRIMARY))

    def test_login_issued_by_rahbar_for_every_role(self):
        import staff
        login, pw = staff.issue_login(self.db, 1, 6)                 # sotuvchi
        self.assertTrue(login and pw)
        login3, pw3 = staff.issue_login(self.db, 1, 3)               # kassir ham — AIBI ilovasi uchun
        self.assertTrue(login3 and pw3)
        rows = {x['id']: x for x in staff.staff_list(self.db, PRIMARY)['staff']}
        self.assertEqual((rows[6]['webCapable'], rows[3]['webCapable'], rows[6]['webLogin'], rows[3]['webLogin']),
                         (True, True, login, login3))

    def test_manager_perm_mapping(self):
        self.assertEqual(perms.manager_perm('hr', 'pay_add', 'bonus'), 'hr.calculate')
        self.assertEqual(perms.manager_perm('hr', 'pay_add', 'advance'), 'hr.pay')
        self.assertEqual(perms.manager_perm('supply', 'pay'), 'warehouse.supply_pay')
        self.assertEqual(perms.manager_perm('stock', 'receive'), 'warehouse.receive')
        self.assertIsNone(perms.manager_perm('dashboard'))

    def test_strip_salary(self):
        wid = hr.add_worker(self.db, 1, {'name': 'Ishchi', 'salary': '1000'})
        d = perms.strip_salary(hr.handle(self.db, 1, 'worker', {'id': wid}))
        self.assertNotIn('payroll', d['worker'])
        self.assertNotIn('salary', d['worker'])
        d = perms.strip_salary(hr.handle(self.db, 1, 'overview', {}))
        self.assertNotIn('money', d)
        self.assertNotIn('payroll', d['workers'][0])


class PermHttpTests(HttpBase):
    USERS = HttpBase.USERS + [(5, 'warehouse', 'Omborchi')]

    def setUp(self):
        self.admin = self.token()
        self.rahbar = self.token('second', self.password2)

    def tearDown(self):
        # har test o'z o'zgarishlarini qaytaradi (bitta server, bitta baza)
        for uid in (3, 4, 5):
            code, d = self.post('/api/manager', self.admin, action='perms_staff', id=uid)
            changes = {p['key']: None for p in d['staff']['perms'] if p['override'] is not None}
            if changes:
                self.post('/api/manager', self.admin, action='perms_set', id=uid, changes=changes)

    def test_grant_takes_effect_in_open_session_and_api_blocks_bypass(self):
        code, d = self.post('/api/manager', self.rahbar, action='stock', op='receive', pack=1, qty=5, unit='Дона', requestId='permtest01')
        self.assertEqual((code, d.get('denied')), (403, True))
        code, d = self.post('/api/manager', self.admin, action='perms_set', id=4, changes={'warehouse.receive': True})
        self.assertEqual(code, 200, d)
        # o'sha token bilan — qayta kirmasdan
        code, d = self.post('/api/manager', self.rahbar, action='stock', op='receive', pack=1, qty=5, unit='Дона', requestId='permtest02')
        self.assertEqual(code, 200, d)
        self.assertTrue(d['canOperate'])
        self.assertIn('warehouse.receive', d['myPerms'])
        self.post('/api/manager', self.admin, action='perms_set', id=4, changes={'warehouse.receive': False})
        code, d = self.post('/api/manager', self.rahbar, action='stock', op='receive', pack=1, qty=5, unit='Дона', requestId='permtest03')
        self.assertEqual(code, 403, d)

    def test_rahbar_cannot_change_perms_or_self(self):
        code, d = self.post('/api/manager', self.rahbar, action='perms_set', id=3, changes={'cash.view': False})
        self.assertEqual(code, 400 if 'denied' not in d else 403, d)
        self.assertIn('Admin', d['error'])
        code, d = self.post('/api/manager', self.admin, action='perms_set', id=1, changes={'cash.view': False})
        self.assertNotEqual(code, 200, d)

    def test_salary_hidden_without_permission(self):
        code, d = self.post('/api/manager', self.admin, action='hr', op='worker_add', name='Maoshli', salary='5000', requestId='permtest10')
        self.assertEqual(code, 200, d)
        wid = d['worker']['id']
        self.post('/api/manager', self.admin, action='perms_set', id=4, changes={'hr.salary_view': False})
        code, d = self.post('/api/manager', self.rahbar, action='hr', op='worker', id=wid)
        self.assertEqual(code, 200, d)
        self.assertTrue(d['salaryHidden'])
        self.assertNotIn('payroll', d['worker'])
        code, d = self.post('/api/manager', self.admin, action='hr', op='worker', id=wid)
        self.assertEqual(d['worker']['salary'], 5000)

    def test_cashier_and_warehouse_miniapps_respect_individual_perms(self):
        code, d = self.post('/api/cashier', initData=signed_init_data(3), action='dashboard')
        self.assertEqual(code, 200, d)
        self.post('/api/manager', self.admin, action='perms_set', id=3, changes={'cash.expense': False})
        code, d = self.post('/api/cashier', initData=signed_init_data(3), action='expense', requestId='cashperm01',
                            currency='USD', amount='1', category='📦 Бошқа харажат', recipient='x')
        self.assertEqual(code, 403, d)
        self.assertIn('Xarajat', d['error'])
        code, d = self.post('/api/cashier', initData=signed_init_data(3), action='dashboard')
        self.assertEqual(code, 200, d)                           # ko'rish ochiq qoldi
        self.post('/api/manager', self.admin, action='perms_set', id=5, changes={'warehouse.receive': False})
        code, d = self.post('/api/warehouse', initData=signed_init_data(5), action='receive', pack=1, qty=1, requestId='whperm0001')
        self.assertEqual(code, 403, d)
        code, d = self.post('/api/warehouse', initData=signed_init_data(5), action='dashboard')
        self.assertEqual(code, 200, d)

    def test_cashier_gets_warehouse_view_but_not_issue_and_revoke_closes_open_session(self):
        init = signed_init_data(3)
        code, d = self.post('/api/warehouse', initData=init, action='dashboard')
        self.assertEqual(code, 403, d)
        code, d = self.post('/api/manager', self.admin, action='perms_set', id=3, changes={'warehouse.view': True})
        self.assertEqual(code, 200, d)
        code, d = self.post('/api/warehouse', initData=init, action='dashboard')
        self.assertEqual(code, 200, d)
        self.assertEqual(d['mode'], 'keeper')
        code, d = self.post('/api/warehouse', initData=init, action='issue', pack=1, qty=1, agent=2, requestId='whperm0101')
        self.assertEqual(code, 403, d)                           # chiqim taqiqlangan
        code, d = self.post('/api/manager', self.admin, action='perms_set', id=3, changes={'warehouse.issue': True})
        self.assertEqual(code, 400, d)                           # ishlamaydigan ruxsat saqlanmaydi
        self.post('/api/manager', self.admin, action='perms_set', id=3, changes={'warehouse.view': False})
        code, d = self.post('/api/warehouse', initData=init, action='dashboard')   # o'sha sessiya
        self.assertEqual(code, 403, d)

    def test_warehouse_keeper_gets_cash_view_read_only(self):
        init = signed_init_data(5)
        code, d = self.post('/api/cashier', initData=init, action='dashboard')
        self.assertEqual(code, 403, d)
        self.post('/api/manager', self.admin, action='perms_set', id=5, changes={'cash.view': True})
        code, d = self.post('/api/cashier', initData=init, action='dashboard')
        self.assertEqual(code, 200, d)
        self.assertEqual(d['myPerms'], ['cash.view'] + sorted(perms.DEFAULTS['warehouse']))
        code, d = self.post('/api/cashier', initData=init, action='expense', requestId='cashperm11',
                            currency='USD', amount='1', category='📦 Бошқа харажат', recipient='x')
        self.assertEqual(code, 403, d)

    def test_miniapp_access_toggle_blocks_initdata_but_not_web(self):
        init = signed_init_data(3)
        code, d = self.post('/api/manager', self.rahbar, action='access_set', id=3, miniapp=False)
        self.assertNotEqual(code, 200, d)                        # faqat asosiy Admin
        code, d = self.post('/api/manager', self.admin, action='access_set', id=3, miniapp=False)
        self.assertEqual(code, 200, d)
        self.assertFalse(next(x for x in d['staff'] if x['id'] == 3)['miniapp'])
        code, d = self.post('/api/cashier', initData=init, action='dashboard')
        self.assertEqual(code, 403, d)
        self.post('/api/manager', self.admin, action='access_set', id=3, miniapp=True)
        code, d = self.post('/api/cashier', initData=init, action='dashboard')
        self.assertEqual(code, 200, d)
        code, d = self.post('/api/manager', self.admin, action='access_set', id=1, miniapp=False)
        self.assertNotEqual(code, 200, d)                        # Admin o'zini yopa olmaydi


if __name__ == '__main__':
    unittest.main()
