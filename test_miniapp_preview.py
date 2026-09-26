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

    def test_admin_read_only_agent_selector(self):
        for term in ('id="adminPicker"','id="adminAgent"','adminAgentId',
                     'data.adminMode','data.readOnly','admin-readonly'):
            self.assertIn(term,self.html)

    def test_customer_row_opens_and_loads_real_detail_card(self):
        for term in ('if(page==="detail")renderDetail()','function loadClientDetail(',
                     'request("client_detail"','Tashriflar tarixi',
                     'So‘nggi operatsiyalar','loadClientDetail(selected)'):
            self.assertIn(term,self.html)

    def test_product_ui_uses_catalog_name_not_internal_sku_as_weight(self):
        for term in (
            "esc(p.name)+' · '+fmt(p.priceUsd)+' USD</option>'",
            'prod?prod.name:("SKU "+ev.pack)',
            'p?p.name:("SKU "+it.pack)',
            'Do‘kondagi mahsulot qoldig‘i',
        ):
            self.assertIn(term,self.html)
        self.assertNotIn("p.pack+' kg · '+fmt(p.priceUsd)",self.html)
        self.assertNotIn('it.pack+" kg × "',self.html)
        self.assertNotIn('[1,3,5].map(function(p)',self.html)

    def test_agent_expense_wallet_ui_is_present(self):
        for term in (
            'id="expenseBalance"','id="expenseList"','id="homeExpenseBalance"',
            'data-action="agent_expense"','agent_expense:"Xarajat qilish"',
            'data.expenseWallet','Xarajat hisobi tarixi',
            'Kassirdan ajratilgan mablag‘ qoldig‘i',
        ):
            self.assertIn(term,self.html)
        self.assertIn('wallet.history||[]',self.html)
        self.assertIn('(data.expenseWallet||{}).categories||[]',self.html)
        self.assertIn('Xarajat faqat shu balansdan yechiladi.',self.html)

    def test_new_client_uses_real_camera_capture_and_upload(self):
        for term in (
            'id="cameraInput"','capture="environment"','id="takePhoto"',
            'id="cameraPreview"','id="photoFileId"','photo_upload',
            'function compressCameraFile(','function uploadCameraFile(',
            'Avval do‘konning real fotosini oling.','Foto ✅'
        ):
            self.assertIn(term,self.html)
        self.assertIn('canvas.toDataURL("image/jpeg"',self.html)
        self.assertIn('data-action="client"',self.html)

    def test_javascript_parses(self):
        if not shutil.which("node"):
            self.skipTest("node unavailable")
        scripts=re.findall(r"<script(?:\\s[^>]*)?>(.*?)</script>",self.html,re.S|re.I)
        js=max(scripts,key=len)
        p=subprocess.run(["node","--check"],input=js,text=True,capture_output=True,timeout=12)
        self.assertEqual(p.returncode,0,p.stderr)

if __name__=="__main__":
    unittest.main()
