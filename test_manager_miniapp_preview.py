"""Manager Mini App smoke tests for the uploaded five-screen design."""
from pathlib import Path
import re, shutil, subprocess, unittest

HTML=Path(__file__).parent/"manager-miniapp"/"index.html"

class ManagerMiniAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=HTML.read_text(encoding="utf-8")

    def test_complete_uploaded_design(self):
        for term in (
            "ASMAN - Rahbar paneli (To'liq versiya)",
            "page-home","page-map","page-customers","page-cash","page-report",
            "Rahbar paneli","Agentlar xaritasi","Mijozlar ro'yxati",
            "Kassa nazorati","Hisobotlar",
            "8+ kun tashrifsiz mijozlar",
            "Telegram.WebApp.ready()","Telegram.WebApp.expand()",
        ):
            self.assertIn(term,self.html)
        self.assertNotIn("BOT_TOKEN",self.html)
        self.assertNotIn("fetch('/api/",self.html)

    def test_all_bottom_navigation_targets_exist(self):
        for target in ("home","map","customers","cash","report"):
            self.assertIn(f"id=\"page-{target}\"",self.html)
            self.assertIn(f"id=\"nav-{target}\"",self.html)
        self.assertIn("L.map('map'",self.html)
        self.assertIn("openstreetmap.org",self.html)

    def test_inline_javascript_parses(self):
        if not shutil.which("node"):
            self.skipTest("node unavailable")
        scripts=re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>",self.html,re.S|re.I)
        js=max(scripts,key=len)
        p=subprocess.run(["node","--check"],input=js,text=True,capture_output=True,timeout=12)
        self.assertEqual(p.returncode,0,p.stderr)

if __name__=="__main__":
    unittest.main()
