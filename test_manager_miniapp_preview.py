"""Manager Mini App smoke tests for the optimized five-screen interactive build."""
from pathlib import Path
import re, shutil, subprocess, unittest

HTML=Path(__file__).parent/"manager-miniapp"/"index.html"

class ManagerMiniAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=HTML.read_text(encoding="utf-8")

    def test_complete_design_and_navigation(self):
        for term in (
            "ASMAN - Rahbar paneli (To'liq versiya)",
            "page-home","page-map","page-customers","page-cash","page-report",
            "Rahbar paneli","Agentlar xaritasi","Mijozlar ro'yxati",
            "Kassa nazorati","Hisobotlar",
            "8+ kun tashrifsiz mijozlar",
            'data-page="home"','data-page="map"','data-page="customers"',
            'data-page="cash"','data-page="report"',
        ):
            self.assertIn(term,self.html)

    def test_interactions_exist(self):
        for term in (
            "function switchPage(","function renderCustomers(","function renderCash(",
            "function renderReport(","function initMap(","function customerDetail(",
            "data-agent-filter","data-customer-filter","data-approve",
            "customerSearch","notifyBtn","profileBtn",
        ):
            self.assertIn(term,self.html)

    def test_performance_dependencies_are_light(self):
        self.assertNotIn("cdn.tailwindcss.com",self.html)
        self.assertNotIn("font-awesome",self.html.lower())
        self.assertNotIn("unsplash.com",self.html)
        self.assertIn("loadLeaflet()",self.html)
        self.assertIn("telegram.org/js/telegram-web-app.js",self.html)
        self.assertNotIn("BOT_TOKEN",self.html)
        self.assertNotIn("fetch('/api/",self.html)

    def test_inline_javascript_parses(self):
        if not shutil.which("node"):
            self.skipTest("node unavailable")
        scripts=re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>",self.html,re.S|re.I)
        js=max(scripts,key=len)
        p=subprocess.run(["node","--check"],input=js,text=True,capture_output=True,timeout=12)
        self.assertEqual(p.returncode,0,p.stderr)

if __name__=="__main__":
    unittest.main()
