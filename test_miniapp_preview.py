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

    def test_admin_full_agent_selector_and_write_mode(self):
        for term in ('id="adminPicker"','id="adminAgent"','adminAgentId',
                     'data.adminMode','admin-full','ADMIN · TO‘LIQ REJIM',
                     'Admin to‘liq rejimi: ishlash uchun agentni tanlang.'):
            self.assertIn(term,self.html)
        self.assertNotIn('admin-readonly',self.html)
        self.assertNotIn('Admin nazorat rejimi xavfsiz emas.',self.html)

    def test_customer_row_opens_and_loads_real_detail_card(self):
        for term in ('if(page==="detail")renderDetail()','function loadClientDetail(',
                     'request("client_detail"','Tashriflar tarixi',
                     'So‘nggi operatsiyalar','loadClientDetail(selected)'):
            self.assertIn(term,self.html)

    def test_product_picker_allows_negative_stock_display(self):
        self.assertIn("qoldiq '+p.agentStock",self.html)
        self.assertNotIn('qoldiq yetarli emas',self.html.lower())

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

    def test_new_client_fast_wizard_has_five_large_steps(self):
        for term in (
            'class="client-wizard-progress"','data-step="1">📍','data-step="2">📷',
            'data-step="3">📞','data-step="4">🏪','data-step="5">📦',
            'function renderClientWizardStep()','function clientWizardValidate(step)',
            'function advanceClientWizard()','id="wizardBack"',
            'id="locationStatus"','class="wizard-input"',
        ):
            self.assertIn(term,self.html)

    def test_fast_wizard_product_step_supports_delivery_or_prospect(self):
        for term in (
            'data-client-product-mode="delivery"','data-client-product-mode="none"',
            'id="clientProductItems"','id="clientProspectOptions"',
            'function clientPackLine(i)','id="clientAddItem"',
            'payload.productMode=clientProductMode',
            'Mahsulot berildimi yoki yo‘qmi',
        ):
            self.assertIn(term,self.html)
        self.assertIn('payload.items.push({pack:Number(fd.get("clientPack"+j)),qty:q})',self.html)
        self.assertIn('Mijoz xaritada prospekt sifatida saqlanadi',self.html)

    def test_fast_wizard_keeps_camera_as_required_second_step(self):
        self.assertIn('capture="environment"',self.html)
        self.assertIn('if(step===2)',self.html)
        self.assertIn('Avval do‘konning real fotosini oling.',self.html)
        self.assertIn('Foto ✅',self.html)

    def test_premium_home_control_center_is_present(self):
        for term in (
            'id="homeCommand"','id="homeCashAvailable"','id="homeUrgentCount"',
            'id="homeNextClient"','BUGUNGI HOLAT','class="quick-grid"',
            'Lokatsiya → foto → telefon → mahsulot',
            'homeCommandTitle'
        ):
            if isinstance(term,str):
                self.assertIn(term,self.html)
        self.assertIn('var urgent=data.clients.filter',self.html)
        self.assertIn('btn.dataset.client=next.id',self.html)

    def test_premium_client_card_has_debt_contact_stock_and_timeline(self):
        for term in (
            'class="customer-hero','class="profile-grid"',
            'USD qarz','id="callClient"','id="navigateClient"',
            'Do‘kondagi mahsulot qoldig‘i','class="stock-item"',
            'class="timeline-item"','Tashriflar tarixi','So‘nggi operatsiyalar',
            'window.location.href="tel:"+digits'
        ):
            self.assertIn(term,self.html)
        self.assertIn('Number(c.debtUsd||0)',self.html)
        self.assertIn('qty<0?"red":qty>0?"green":""',self.html)

    def test_client_card_layout_does_not_overlap_content(self):
        self.assertNotIn('\\n.customer-hero{',self.html)
        self.assertIn('.customer-hero{position:relative',self.html)
        self.assertIn('.client-actions{position:static',self.html)
        self.assertNotIn('.client-actions{position:sticky',self.html)

    def test_report_is_compact_and_includes_stock_summary(self):
        for term in (
            'class="report-kpis"','id="reportStockTotal"','id="reportNegativeCount"',
            'class="report-stock-list"','class="report-stock-item"',
            'Berilgan tovar','Xarajat balansi','Jami qoldiq','Minus qoldiq',
            'products.reduce(function(sum,x)','negative=products.filter',
            'an-bn||String(a.name).localeCompare'
        ):
            self.assertIn(term,self.html)
        self.assertIn('min-height:82px',self.html)
        self.assertIn('qty<0?"red":qty>0?"green":""',self.html)

    def test_fast_delivery_cart_has_steppers_totals_and_negative_stock_warning(self):
        for term in (
            'class="delivery-cart"','class="delivery-row"',
            'class="qty-stepper"','data-qty-step="-1"','data-qty-step="1"',
            'id="deliveryTotalQty"','id="deliveryGrandTotal"',
            'id="deliveryWarning"','function updateDeliveryCart()',
            'Qoldiq minusga tushadi:','Agent qoldiq: ',
            'Qoldiq yetmasa ham berish mumkin'
        ):
            self.assertIn(term,self.html)
        self.assertIn('stock<qty',self.html)
        self.assertIn('stock-qty',self.html)

    def test_delivery_cart_payload_survives_middle_row_removal(self):
        self.assertIn('querySelectorAll(".delivery-row").forEach(function(row)',self.html)
        self.assertIn('data-remove-delivery',self.html)
        self.assertIn('row.remove();updateDeliveryCart()',self.html)
        self.assertNotIn('while(fd.has("pack"+i))',self.html)

    def test_delivery_cart_return_mode_uses_customer_stock(self):
        self.assertIn('formAction==="return"',self.html)
        self.assertIn('Mijozda: ',self.html)
        self.assertIn('Qaytarish uchun qoldiq yetarli emas:',self.html)

    def test_javascript_parses(self):
        if not shutil.which("node"):
            self.skipTest("node unavailable")
        scripts=re.findall(r"<script(?:\\s[^>]*)?>(.*?)</script>",self.html,re.S|re.I)
        js=max(scripts,key=len)
        p=subprocess.run(["node","--check"],input=js,text=True,capture_output=True,timeout=12)
        self.assertEqual(p.returncode,0,p.stderr)

if __name__=="__main__":
    unittest.main()
