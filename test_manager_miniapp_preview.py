"""Manager Mini App smoke tests."""
from pathlib import Path
import re, shutil, subprocess, unittest
HTML=Path(__file__).parent/"manager-miniapp"/"index.html"
class ManagerMiniAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.html=HTML.read_text(encoding="utf-8")
    def test_demo_only_and_key_sections(self):
        for term in ("ДЕМО · ТЕСТ","ишчи бот базасига","page-home","page-agents","page-agentmap","page-clients","page-cash","page-reports"):
            self.assertIn(term,self.html)
        self.assertNotIn("BOT_TOKEN",self.html)
        self.assertNotIn("fetch('/api/",self.html)
    def test_js_syntax(self):
        if not shutil.which("node"): self.skipTest("node unavailable")
        scripts=re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>",self.html,re.S|re.I)
        js=max(scripts,key=len)
        p=subprocess.run(["node","--check"],input=js,text=True,capture_output=True,timeout=12)
        self.assertEqual(p.returncode,0,p.stderr)
if __name__=="__main__": unittest.main()
