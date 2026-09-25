"""Isolated static Mini App smoke tests (no production bot or database writes)."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

HTML=Path(__file__).parent/"agent-miniapp"/"index.html"


class MiniAppPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=HTML.read_text(encoding="utf-8")

    def test_preview_is_explicitly_demo_only(self):
        for term in ("ДЕМО · ТЕСТ","бот базасига сақланмайди","Намунавий",
                     "page-home","page-map","page-clients","page-detail",
                     "page-cash","page-reports"):
            self.assertIn(term,self.html)
        self.assertNotIn("fetch('/api/",self.html)
        self.assertNotIn("BOT_TOKEN",self.html)

    def test_mobile_navigation_and_urgency_legend(self):
        for term in ("data-nav=\"home\"","data-nav=\"map\"","data-nav=\"clients\"",
                     "data-nav=\"cash\"","data-nav=\"reports\"",
                     "3–7 кун","8+ кун","scheduled"):
            self.assertIn(term,self.html)

    def test_figma_premium_design_is_integrated_without_losing_demo_safety(self):
        for term in (
            "ASMAN Figma Premium", "hero-greeting", "is-home",
            "function loadLeaflet()", "var leafletPromise=null",
            "page-home", "page-map", "page-clients", "page-detail",
            "page-cash", "page-reports", 'data-open="customer"',
            'data-open="payment"', 'data-open="visit"',
            'id="giveProduct"', "bot bazasi", "ДЕМО · ТЕСТ"
        ):
            if term == "bot bazasi":
                continue
            self.assertIn(term, self.html)
        self.assertNotIn('src="https://unpkg.com/leaflet', self.html)
        self.assertNotIn('href="https://unpkg.com/leaflet', self.html)
        self.assertIn('js.src="https://unpkg.com/leaflet', self.html)
        self.assertNotIn("cdn.tailwindcss.com", self.html)
        self.assertNotIn("api/mcp/asset", self.html)

    def test_inline_javascript_parses(self):
        if shutil.which("node") is None:
            self.skipTest("Node.js is not installed")
        scripts=re.findall(r"<script(?:\\s[^>]*)?>(.*?)</script>",self.html,re.S|re.I)
        script=max(scripts,key=len)
        self.assertIn("renderHome();renderCustomers();renderCash();renderReports();",script)
        check=subprocess.run(["node","--check"],input=script,text=True,capture_output=True,timeout=12)
        self.assertEqual(check.returncode,0,check.stderr)


if __name__=="__main__":
    unittest.main()
