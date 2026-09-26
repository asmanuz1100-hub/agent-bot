import unittest
from pathlib import Path


class ManagerProductDiagramUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path("manager-miniapp/index.html").read_text(encoding="utf-8")

    def test_product_movement_uses_diagram_ui(self):
        self.assertIn("Mahsulot harakati · diagramma", self.html)
        self.assertIn('data-product-metric="deliveredUsd"', self.html)
        self.assertIn('data-product-metric="deliveredQty"', self.html)
        self.assertIn('data-product-metric="soldQty"', self.html)
        self.assertIn('data-product-metric="returnedQty"', self.html)
        self.assertIn('id="report-product-total"', self.html)
        self.assertIn('id="report-product-leader"', self.html)
        self.assertIn('class="product-chart"', self.html)

    def test_product_diagram_uses_real_report_product_fields(self):
        for field in ("deliveredUsd", "deliveredQty", "soldQty", "returnedQty"):
            self.assertIn(field, self.html)
        self.assertIn("rankedProducts=products.slice().sort", self.html)
        self.assertIn("value/productTotal*100", self.html)
        self.assertIn("value/productMax*100", self.html)
        self.assertIn('data-report-product="', self.html)

    def test_product_metric_switch_rerenders_report(self):
        self.assertIn("state.reportProductMetric=b.dataset.productMetric", self.html)
        self.assertIn('document.querySelectorAll("[data-product-metric]")', self.html)
        self.assertIn("renderReport();return", self.html)


if __name__ == "__main__":
    unittest.main()
