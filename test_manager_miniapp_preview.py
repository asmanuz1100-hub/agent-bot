"""Manager Mini App smoke tests for the optimized Telegram UI Kit build."""
from pathlib import Path
import re, shutil, subprocess, unittest

HTML=Path(__file__).parent/"manager-miniapp"/"index.html"

class ManagerMiniAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=HTML.read_text(encoding="utf-8")

    def test_complete_design_and_navigation(self):
        for term in (
            "ASMAN · Rahbar paneli — Real ma’lumotlar",
            "page-home","page-map","page-customers","page-cash","page-report",
            "Rahbar paneli","Agentlar xaritasi","Mijozlar","Kassa","Hisobot",
            "Diqqat talab qiladigan holatlar","ASMAN · CONTROL CENTER",
            "home-pending-cash","home-client-count","home-new-clients",
            "cash-pending-inline","report-active-agents","report-overdue",
            'data-page="home"','data-page="map"','data-page="customers"',
            'data-page="cash"','data-page="report"',
        ):
            self.assertIn(term,self.html)

    def test_interactions_exist(self):
        for term in (
            "function switchPage(","function renderCustomers(","function renderCash(",
            "function renderReport(","function initMap(","function showCustomer(",
            "data-agent-filter","data-customer-filter","data-cash-tab",
            "data-report-tab","customer-search","function showRoute(",
        ):
            self.assertIn(term,self.html)

    def test_performance_dependencies_are_light(self):
        self.assertNotIn("cdn.tailwindcss.com",self.html)
        self.assertNotIn("font-awesome",self.html.lower())
        self.assertNotIn("unsplash.com",self.html)
        self.assertIn("function loadLeaflet()",self.html)
        self.assertIn("telegram.org/js/telegram-web-app.js",self.html)
        self.assertNotIn("BOT_TOKEN",self.html)
        self.assertIn("https://asman-agent-test.onrender.com/api/manager",self.html)
        self.assertIn("tg.initData",self.html)
        self.assertIn("data.readOnly",self.html)
        self.assertNotIn("Alibek Karimov",self.html)
        self.assertNotIn('data-approve=',self.html)
        self.assertIn('id="auth-gate"',self.html)

    def test_report_center_has_finance_route_and_agent_controls(self):
        for term in (
            'data-report-tab="today"','data-report-tab="week"','data-report-tab="month"',
            'data-report-tab="agents"','id="report-delivered"','id="report-payments"',
            'id="report-work"','id="report-distance"','id="report-accepted-cash"',
            'id="report-cash-expense"','id="report-current-debt"',
            'data-report-metric="visits"','data-report-metric="deliveredUsd"',
            'data-report-metric="paymentsUsd"','function showReportAgent(',
            'function reportKey()','function duration(',
        ):
            self.assertIn(term,self.html)

    def test_report_product_breakdown_controls_exist(self):
        for term in (
            'id="report-products"','id="report-top-product"',
            'data-report-product=','function showReportProduct(',
            'Mahsulot harakati','Sotilgani qayd etilgan',
        ):
            self.assertIn(term,self.html)

    def test_map_keeps_clients_and_last_known_agent_locations_visible(self):
        for term in (
            'class="map-legend"','prefs.showMapClients?customers.filter',
            'className:"client-map-icon"','class="client-map-pin"',
            'id="map-client-count"','data-customer="',
            'Kartochkani ochish','oxirgi GPS saqlangan',
            'a.locationSource==="last"||!a.shiftOpen',
        ):
            self.assertIn(term,self.html)
        self.assertNotIn('GPS koordinatasi kelgan agent yo‘q. Quyidagi ro‘yxatni tekshiring.',self.html)

    def test_customer_advanced_filters_and_manager_settings_exist(self):
        for term in (
            'id="customer-agent-filter"','id="customer-debt-filter"',
            'id="customer-status-filter"','id="customer-sort"',
            'id="customer-filter-reset"','id="customer-result-count"',
            'id="manager-settings"','function showManagerSettings(',
            'PREF_KEY="asman_manager_prefs_v1"','showMapClients',
            'refreshSeconds','startPage','function scheduleRefresh(',
        ):
            self.assertIn(term,self.html)

    def test_customer_control_module_has_detail_edit_history_and_exports(self):
        for term in (
            'request("client_detail"','data-client-edit=','data-client-export=',
            'Akt PDF','Akt Excel','Tovar va to‘lovlar tarixi',
            'Tashriflar tarixi','O‘zgartirishlar auditi',
            'request("client_edit_preview"','request("client_edit_commit"',
            'request("client_export"','function exportClient(',
            'function commitCustomerEdit(',
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
