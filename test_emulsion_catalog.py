import unittest

import agent_api
import core
import reports


class EmulsionCatalogTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Admin'),(2,'agent','Agent')])
        self.db.execute("""INSERT INTO clients(id,agent,name,phone,shop_name,created_ts,map_only)
            VALUES(10,2,'Buyer','+998901234567','Test shop',1,0)""")
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_emulsion_catalog_contains_20_factory_priced_skus(self):
        emulsion=[sku for sku in core.product_ids() if sku>=1000]
        self.assertEqual(len(emulsion),20)
        expected={
            1004:375,1007:565,1010:785,1020:1500,
            2004:390,2007:590,2010:820,2020:1565,
            3004:415,3007:635,3010:885,3020:1700,
            4004:530,4007:840,4010:1180,4020:2285,
            5004:545,5007:850,5010:1190,5020:2300,
        }
        for sku,price in expected.items():
            self.assertEqual(core.product_price(self.db,sku),price)
            self.assertIn(core.product_weight(sku),(4,7,10,20))
            self.assertIsNone(core.block_units(sku))

    def test_agent_api_exposes_name_weight_price_and_stock_for_emulsion(self):
        items=agent_api._products(self.db,2)
        item=next(x for x in items if x['pack']==3004)
        self.assertEqual(item['name'],'Эмульсия — Моющаяся / A-baza — 4 кг')
        self.assertEqual(item['weightKg'],4)
        self.assertEqual(item['priceUsd'],4.15)
        self.assertEqual(item['agentStock'],0)
        self.assertIsNone(item['blockUnits'])

    def test_emulsion_delivery_uses_factory_price_and_reconciliation_supports_sku(self):
        sku=4020
        core.record(self.db,1,2,None,'load',sku,3,0,'',9001,currency='USD')
        core.record(self.db,2,2,10,'delivery',sku,2,0,'',9002,currency='USD')
        row=self.db.execute("SELECT amount_usd,pack,qty FROM events WHERE source=9002").fetchone()
        self.assertEqual(row['pack'],sku)
        self.assertEqual(row['qty'],2)
        self.assertEqual(row['amount_usd'],4570)
        self.assertEqual(core.client_debt_usd(self.db,10),4570)
        act=reports.reconciliation(self.db,2,10)
        self.assertEqual(act['closing_stock'][sku],2)
        self.assertEqual(act['usd_closing'],4570)


if __name__=='__main__':
    unittest.main()
