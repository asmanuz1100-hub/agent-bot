"""Ombor: manager-maintained catalog, agent orders (incl. products not yet in the catalog), 'sold' from the client card."""
import time
import unittest

import agent_api
import core
import manager_api


class CatalogAndOrdersTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [
            (1, 'admin', 'Admin'), (2, 'agent', 'Ali'), (3, 'cashier', 'Kassir'), (4, 'agent', 'Vali')])
        self.now = int(time.time()) - 60
        self.db.execute('UPDATE products SET price=? WHERE pack=1', (10000,))
        core.record(self.db, 1, 2, None, 'load', 1, 50, source=7001, currency='USD')
        self.cid = agent_api.mutate(self.db, 2, 'add_client', {
            'shopName': 'Baraka', 'name': 'Vali', 'phone': '+998901234567', 'address': 'Qo‘qon',
            'lat': 40.54, 'lon': 70.94, 'status': 'interested', 'note': 'x'}, 'client_create_1', self.now - 3600)['clientId']
        core.record(self.db, 2, 2, self.cid, 'delivery', 1, 12, 0, '', 8001, currency='USD')
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def m(self, action, payload, rid):
        p = {'clientId': self.cid}; p.update(payload)
        return agent_api.mutate(self.db, 2, action, p, 'req_' + rid + '_000000', self.now)

    # --- catalog --------------------------------------------------------------------------
    def test_admin_adds_product_and_agents_see_it(self):
        pack = core.add_product(self.db, 1, 'Emal PF-115 oq 2.7 kg', '2,7', 450)
        self.assertGreaterEqual(pack, core.CUSTOM_PRODUCT_START)
        self.assertIn(pack, core.active_product_ids())
        self.assertEqual(core.product_price(self.db, pack), 450)
        self.assertEqual(core.product_weight(pack), 2.7)
        names = [p['name'] for p in agent_api.dashboard(self.db, 2)['products']]
        self.assertIn('Emal PF-115 oq 2.7 kg', names)
        # survives a "restart": a new connection reloads the catalog from the DB
        core.PRODUCTS.pop(pack)
        core.refresh_catalog(self.db)
        self.assertEqual(core.product_name(pack), 'Emal PF-115 oq 2.7 kg')

    def test_only_admin_manages_catalog_and_no_duplicates(self):
        with self.assertRaisesRegex(ValueError, 'rahbar'):
            core.add_product(self.db, 2, 'Lak', 1, 100)
        with self.assertRaisesRegex(ValueError, 'katalogda bor'):
            core.add_product(self.db, 1, 'грунтовка 7/1 — 1 КГ', 1, 100)
        with self.assertRaisesRegex(ValueError, 'Asosiy mahsulot nomi'):
            core.update_product(self.db, 1, 1, name='Boshqa nom')

    def test_archived_product_is_hidden_but_history_kept(self):
        core.update_product(self.db, 1, 3, active=False)
        self.assertNotIn(3, core.active_product_ids())
        self.assertIn(3, core.product_ids())                 # reports/acts still know it
        with self.assertRaisesRegex(ValueError, 'arxivda'):
            self.m('order', {'items': [{'pack': 3, 'qty': 1}]}, 'o_arch')
        packs = [p['pack'] for p in agent_api.dashboard(self.db, 2)['products']]
        self.assertNotIn(3, packs)                           # no agent stock → hidden
        self.assertIn(1, packs)
        core.update_product(self.db, 1, 3, active=True)
        self.assertIn(3, core.active_product_ids())

    def test_price_update(self):
        core.update_product(self.db, 1, 1004, price_cents=399)
        self.assertEqual(core.product_price(self.db, 1004), 399)

    # --- sold -------------------------------------------------------------------------------
    def test_sold_reduces_client_stock_not_debt(self):
        debt = core.client_debt_usd(self.db, self.cid)
        out = self.m('sold', {'items': [{'pack': 1, 'qty': 5}]}, 's1')
        self.assertTrue(out['ok'])
        self.assertEqual(core.client_stock_total(self.db, self.cid, 1), 7)
        self.assertEqual(core.client_debt_usd(self.db, self.cid), debt)
        with self.assertRaisesRegex(ValueError, 'hisob bo‘yicha 7'):
            self.m('sold', {'items': [{'pack': 1, 'qty': 8}]}, 's2')

    # --- orders -----------------------------------------------------------------------------
    def test_order_flow_catalog_items(self):
        out = self.m('order', {'items': [{'pack': 1, 'qty': 10}, {'pack': 1004, 'qty': 2}], 'note': 'Ertaga'}, 'o1')
        oid = out['orderId']
        self.assertEqual(out['_notify'], {'kind': 'order', 'orderId': oid})
        w = manager_api.warehouse(self.db)
        self.assertEqual(w['counts']['new'], 1)
        self.assertEqual(w['orders'][0]['clientName'], 'Baraka')
        stock_before = core.agent_stock(self.db, 2, 1)
        core.set_order_status(self.db, 1, oid, 'preparing')
        core.set_order_status(self.db, 1, oid, 'loaded')
        self.assertEqual(core.agent_stock(self.db, 2, 1), stock_before + 10)   # loaded to the agent
        self.assertEqual(core.agent_stock(self.db, 2, 1004), 2)
        with self.assertRaisesRegex(ValueError, 'o‘tib bo‘lmaydi'):
            core.set_order_status(self.db, 1, oid, 'preparing')
        debt = core.client_debt_usd(self.db, self.cid)
        self.m('delivery', {'items': [{'pack': 1, 'qty': 10}], 'orderId': oid}, 'd1')
        self.assertEqual(self.db.execute('SELECT status FROM orders WHERE id=?', (oid,)).fetchone()[0], 'delivered')
        self.assertEqual(core.client_debt_usd(self.db, self.cid), debt + 100000)
        d = agent_api.client_detail(self.db, 2, self.cid, self.now)
        self.assertEqual(d['orders'][0]['status'], 'delivered')

    def test_order_idempotent_and_agent_cannot_change_status(self):
        a = self.m('order', {'items': [{'pack': 1, 'qty': 1}]}, 'o_same')
        b = self.m('order', {'items': [{'pack': 1, 'qty': 1}]}, 'o_same')
        self.assertTrue(b['duplicate'])
        with self.assertRaisesRegex(ValueError, 'rahbar'):
            core.set_order_status(self.db, 2, a['orderId'], 'loaded')

    def test_reject_needs_reason(self):
        oid = self.m('order', {'items': [{'pack': 1, 'qty': 1}]}, 'o_rej')['orderId']
        with self.assertRaisesRegex(ValueError, 'sababini'):
            core.set_order_status(self.db, 1, oid, 'rejected')
        core.set_order_status(self.db, 1, oid, 'rejected', 'Omborda yo‘q')
        self.assertEqual(manager_api.warehouse(self.db, 'rejected')['orders'][0]['adminNote'], 'Omborda yo‘q')

    def test_product_not_in_catalog_flow(self):
        o1 = self.m('order', {'items': [{'name': 'Emal PF-115 oq', 'qty': 5}, {'pack': 1, 'qty': 2}]}, 'o_c1')['orderId']
        agent_api.mutate(self.db, 4, 'add_client', {
            'shopName': 'Nur', 'name': 'Nur', 'phone': '+998907777777', 'address': 'Qo‘qon',
            'lat': 40.55, 'lon': 70.95, 'status': 'interested', 'note': 'x'}, 'client_create_2', self.now - 3000)
        cid2 = self.db.execute("SELECT id FROM clients WHERE shop_name='Nur'").fetchone()[0]
        o2 = agent_api.mutate(self.db, 4, 'order', {'clientId': cid2, 'items': [{'name': 'emal  pf-115 OQ', 'qty': 7}]},
                              'req_o_c2_000000', self.now)['orderId']
        demand = core.custom_demand(self.db)
        self.assertEqual(len(demand), 1)
        self.assertEqual((demand[0]['qty'], demand[0]['clients'], demand[0]['agents']), (12, 2, 2))
        with self.assertRaisesRegex(ValueError, 'katalogga qo‘shing'):
            core.set_order_status(self.db, 1, o1, 'loaded')
        pack = core.add_product(self.db, 1, 'Emal PF-115 oq 2.7 kg', 2.7, 450)
        self.assertEqual(core.map_custom_name(self.db, 1, 'Emal PF-115 oq', pack), 2)
        self.assertEqual(core.custom_demand(self.db), [])
        core.set_order_status(self.db, 1, o1, 'loaded')
        self.assertEqual(core.agent_stock(self.db, 2, pack), 5)
        v2 = core.order_view(self.db, self.db.execute('SELECT * FROM orders WHERE id=?', (o2,)).fetchone())
        self.assertEqual((v2['items'][0]['pack'], v2['items'][0]['qty'], v2['unmapped']), (pack, 7, 0))

    def test_typed_name_matching_catalog_is_attached(self):
        oid = self.m('order', {'items': [{'name': 'Грунтовка 7/1 — 3 кг', 'qty': 4}]}, 'o_match')['orderId']
        v = core.order_view(self.db, self.db.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone())
        self.assertEqual((v['items'][0]['pack'], v['unmapped']), (3, 0))

    def test_order_validation(self):
        with self.assertRaisesRegex(ValueError, '1–30'):
            self.m('order', {'items': []}, 'o_v1')
        with self.assertRaisesRegex(ValueError, 'ikki marta'):
            self.m('order', {'items': [{'pack': 1, 'qty': 1}, {'pack': 1, 'qty': 3}]}, 'o_v2')
        with self.assertRaisesRegex(ValueError, '2–120'):
            self.m('order', {'items': [{'name': 'x', 'qty': 1}]}, 'o_v3')

    def test_delivery_for_foreign_order_rejected(self):
        oid = self.m('order', {'items': [{'pack': 1, 'qty': 1}]}, 'o_f')['orderId']
        with self.assertRaisesRegex(ValueError, 'hali agentga berilmagan'):
            self.m('delivery', {'items': [{'pack': 1, 'qty': 1}], 'orderId': oid}, 'd_f')

    def test_dashboard_counters(self):
        self.m('order', {'items': [{'name': 'Lak yangi', 'qty': 1}]}, 'o_d')
        w = manager_api.dashboard(self.db)['warehouse']
        self.assertEqual((w['newOrders'], w['missingProducts']), (1, 1))


if __name__ == '__main__':
    unittest.main()
