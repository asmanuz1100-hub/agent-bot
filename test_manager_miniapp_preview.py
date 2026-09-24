"""Manager Mini App smoke tests for uploaded design prototype."""
from pathlib import Path
import re, shutil, subprocess, unittest

HTML=Path(__file__).parent/"manager-miniapp"/"index.html"

class ManagerMiniAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=HTML.read_text(encoding="utf-8")

    def test_uploaded_design_sections_exist(self):
        for term in (
            "ASMAN - Rahbar paneli va Xarita",
            "page-home",
            "page-map",
            "Rahbar paneli",
            "Agentlar xaritasi",
            "Bugungi nazorat",
            "8+ kun tashrifsiz mijozlar",
            "Kassa tasdigʻini kutayotgan",
            "Telegram.WebApp.ready()",
            "Telegram.WebApp.expand()",
        ):
            self.assertIn(term,self.html)
        self.assertNotIn("BOT_TOKEN",self.html)
        self.assertNotIn("fetch('/api/",self.html)

    def test_navigation_and_map_present(self):
        for term in (
            "switchPage('home')",
            "switchPage('map')",
            "id=\"map\"",
            "L.map('map'",
            "openstreetmap.org",
            "Bosh sahifa",
            "Agentlar",
            "Mijozlar",
            "Kassa",
            "Hisobot",
        ):
            self.assertIn(term,self.html)

    def test_inline_javascript_parses(self):
        if not shutil.which("node"):
            self.skipTest("node unavailable")
        scripts=re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>",self.html,re.S|re.I)
        js=max(scripts,key=len)
        p=subprocess.run(["node","--check"],input=js,text=True,capture_output=True,timeout=12)
        self.assertEqual(p.returncode,0,p.stderr)

if __name__=="__main__":
    unittest.main()
