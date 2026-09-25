"""Agent Mini App smoke tests: real authenticated UI, not demo fixtures."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

HTML=Path(__file__).parent/"agent-miniapp"/"index.html"

class LiveAgentMiniAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=HTML.read_text(encoding="utf-8")

    def test_real_signed_api_no_embedded_credentials_or_demo_records(self):
        for part in ('https://asman-agent-test.onrender.com/api/agent',
                     'tg.initData','readOnly','data.me.shiftOpen','data.clients',
                     'data.products','data.events','data.handovers','data.period'):
            if part=='readOnly':
                continue
            self.assertIn(part,self.html)
        for secret in ('BOT_TOKEN','Alibek Karimov','Saxovat Market','ДЕМО · ТЕСТ'):
            self.assertNotIn(secret,self.html)
        self.assertIn('id="gate"',self.html)

    def test_live_workflows_and_real_map(self):
        for term in ('id="startShift"','id="endShift"','shift_start','shift_end',
                     '"client"','"visit"','"delivery"','"payment"','"return"',
                     '"handover"','nonce:nonce','window.confirm',
                     'function renderMap(','function renderCash(',
                     'function renderReports(','function showMyRoute(',
                     'id="page-home"','id="page-map"','id="page-clients"',
                     'id="page-detail"','id="page-cash"','id="page-reports"'):
            self.assertIn(term,self.html)
        self.assertNotIn('cdn.tailwindcss.com',self.html)
        self.assertNotIn('api/mcp/asset',self.html)
        self.assertNotRegex(self.html,r'<script\\s+src="https://unpkg\\.com/leaflet')

    def test_javascript_parses(self):
        if not shutil.which("node"):
            self.skipTest("node unavailable")
        scripts=re.findall(r"<script(?:\\s[^>]*)?>(.*?)</script>",self.html,re.S|re.I)
        js=max(scripts,key=len)
        p=subprocess.run(["node","--check"],input=js,text=True,capture_output=True,timeout=12)
        self.assertEqual(p.returncode,0,p.stderr)

if __name__=="__main__":
    unittest.main()
