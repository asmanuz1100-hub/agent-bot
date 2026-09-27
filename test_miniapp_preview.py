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

    def test_android_map_avoids_canvas_overlays_and_forces_tile_visibility(self):
        for term in (
            'className:"client-map-icon"',
            'class="client-map-pin"',
            'L.marker([c.lat,c.lon]',
            'className:"route-point-icon"',
            'L.polyline(seg.map(function(p){return[p.lat,p.lon]}),{color:"#2367f5"',
            'html.tg-android img.leaflet-tile',
            'visibility:visible!important',
            'mix-blend-mode:normal!important',
            'document.documentElement.classList.add("tg-android")',
            'tg.setBackgroundColor("#f4f7fd")'
        ):
            self.assertIn(term,self.html)
        self.assertNotIn('renderer:mapCanvas',self.html)
        self.assertNotIn('renderer:routeCanvas',self.html)
        self.assertNotIn('mapCanvas=L.canvas',self.html)
        self.assertNotIn('routeCanvas=L.canvas',self.html)

    def test_client_and_route_maps_match_working_manager_base_map(self):
        for term in (
            'id="mapShell"','id="mapStatus"',
            'function installManagerParityTiles',
            'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
            'maxZoom:17,updateWhenIdle:true,keepBuffer:1',
            'function installClientMapTiles',
            'mapTiles=installManagerParityTiles(L,map)',
            'installManagerParityTiles(L,routeMap)',
            'function fitClientMap()',
            'map.invalidateSize(false)',
            'setTimeout(fitClientMap,120)',
            'setTimeout(fitClientMap,500)'
        ):
            self.assertIn(term,self.html)
        self.assertNotIn('function installResilientTiles',self.html)
        self.assertNotIn('basemaps.cartocdn.com',self.html)
        self.assertNotIn('tile.openstreetmap.fr/hot',self.html)

    def test_photo_step_supports_live_camera_and_gallery_picker(self):
        for term in (
            'id="cameraLive"','id="takePhoto"','id="captureLivePhoto"',
            'id="galleryInput"','id="galleryPhoto"',
            '🖼 Galereyadan tanlash',
            'if(b.id==="galleryPhoto")',
            'e.target.id==="galleryInput"',
            'capture="environment"'
        ):
            self.assertIn(term,self.html)

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
        self.assertIn('balanceUzs',self.html)
        self.assertIn('Xarajat faqat shu so‘m balansidan yechiladi.',self.html)
        self.assertIn('Xarajat summasi (UZS)',self.html)
        self.assertIn('name="expectedRate"',self.html)
        self.assertIn('USD ekv.: ',self.html)
        self.assertIn('rateUzsPerUsd',self.html)
        self.assertIn('fmtSom((data.expenseWallet||{}).balanceUzs||0)+" UZS"',self.html)

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

    def test_android_wizard_inputs_force_visible_text_and_show_live_mirrors(self):
        for term in (
            '-webkit-text-fill-color:#101e39!important',
            'caret-color:#2367f5!important',
            'input::placeholder,textarea::placeholder',
            'input:-webkit-autofill',
            '-webkit-box-shadow:0 0 0 1000px #fff inset!important',
            '.wizard-input{color:#101e39!important',
            '-webkit-appearance:none!important',
            'forced-color-adjust:none!important',
            'id="phone" name="phone" type="tel"',
            'id="person" name="person" type="text"',
            'id="phoneMirror" class="wizard-live-value"',
            'id="personMirror" class="wizard-live-value"',
            'id="shopMirror" class="wizard-live-value"',
            'function updateWizardMirrors()',
            'Telefon: ','Mijoz: ','Do‘kon: ',
            'if(formAction==="client")updateWizardMirrors()'
        ):
            self.assertIn(term,self.html)

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
            "href=\"tel:'+esc(dialPhone(c))+'\""
        ):
            self.assertIn(term,self.html)
        self.assertIn('Number(c.debtUsd||0)',self.html)
        self.assertIn('qty<0?"red":qty>0?"green":""',self.html)

    def test_call_uses_native_tel_link_and_phone_normalization(self):
        self.assertIn('function dialPhone(c)',self.html)
        self.assertIn("href=\"tel:'+esc(dialPhone(c))+'\"",self.html)
        self.assertIn('/^998\\d{9}$/.test(digits)',self.html)
        self.assertNotIn('window.location.href="tel:"+digits',self.html)

    def test_first_paint_uses_quick_snapshot_and_heavy_tabs_load_on_demand(self):
        for term in (
            'request(heavy?"snapshot":"quick_snapshot")',
            'var heavy=current==="cash"||current==="reports"',
            'fullDataLoaded=heavy',
            'if((page==="cash"||page==="reports")&&!fullDataLoaded)',
            'request("quick_snapshot")',
            'function applySnapshotUi()'
        ):
            self.assertIn(term,self.html)
        self.assertNotIn('renderHome();renderClients();renderDetail();renderCash();renderReports();',self.html)

    def test_customer_photos_use_android_safe_eager_then_native_lazy_loading(self):
        for term in (
            'function shopRow(c,eager)',
            'loading="eager" fetchpriority="high"',
            'loading="lazy"',
            'list.map(function(c,i){return shopRow(c,i<8)}',
            'target.map(function(c){return shopRow(c,true)}',
            'decoding="async"'
        ):
            self.assertIn(term,self.html)
        self.assertNotIn('IntersectionObserver',self.html)
        self.assertNotIn('data-photo-src=',self.html)

    def test_android_webview_uses_platform_specific_readable_header(self):
        for term in (
            '<meta name="color-scheme" content="light">',
            'maximum-scale=1',
            'html.tg-android{color-scheme:only light!important',
            'html.tg-android .app>header{background:#f4f7fd!important',
            'html.tg-android .app>header .logo,html.tg-android .app>header .greet{color:#101e39!important',
            'tg.setHeaderColor(String(tg.platform||"").toLowerCase()==="android"?"#f4f7fd":"#101e39")'
        ):
            self.assertIn(term,self.html)


    def test_leaflet_loader_matches_working_manager_loader(self):
        for term in (
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
            'js.async=true',
            'window.L?resolve(window.L):reject(Error("Xarita kutubxonasi mavjud emas."))'
        ):
            self.assertIn(term,self.html)
        self.assertNotIn('function loadExternalScript(url,timeout)',self.html)

    def test_agent_home_shows_cashier_debt_collection_tasks(self):
        for term in (
            'id="collectionTaskSection"',
            'id="collectionTaskList"',
            '📌 Kassir topshiriqlari',
            'data.collectionTasks||[]',
            'Qarz undirish · ',
            'currentDebtUsd',
            'Mijoz kartasini ochish →',
            "data-client=\"'+t.clientId+'\""
        ):
            self.assertIn(term,self.html)

    def test_client_card_layout_does_not_overlap_content(self):
        self.assertNotIn('\\n.customer-hero{',self.html)
        self.assertIn('.customer-hero{position:relative',self.html)
        self.assertIn('.client-actions{position:static',self.html)
        self.assertNotIn('.client-actions{position:sticky',self.html)

    def test_report_is_compact_and_includes_stock_summary(self):
        for term in (
            'class="report-kpis"','id="reportStockTotal"','id="reportNegativeCount"',
            'class="report-stock-list"','class="report-stock-item"',
            'Berilgan tovar','Agent xarajati','Jami qoldiq','Minus qoldiq',
            'products.reduce(function(sum,x)','negative=products.filter',
            'an-bn||String(a.name).localeCompare'
        ):
            self.assertIn(term,self.html)
        self.assertIn('min-height:82px',self.html)
        self.assertIn('qty<0?"red":qty>0?"green":""',self.html)

    def test_premium_agent_report_has_full_finance_product_client_and_trend_analytics(self):
        for term in (
            'class="report-hero"','id="reportDeliveryUsd"','id="reportHeroPaid"',
            'id="reportHeroDebt"','id="reportHeroReturn"','id="reportFlow"',
            'data-report-trend="deliveryUsd"','data-report-trend="paymentsUsd"',
            'data-report-trend="visits"','id="reportTrend"','id="reportProducts"',
            'id="reportClientTotal"','id="reportClientDebt"','id="reportClientBar"',
            'Mahsulotlar kesimi','Mijozlar holati','Pul harakati','7 kunlik dinamika',
            'analytics.products&&analytics.products[period]','p.handoverAcceptedUsd',
            'p.expenseUsd','p.deliveryUsd','p.returnUsd','p.soldQty'
        ):
            self.assertIn(term,self.html)
        self.assertIn('Number(c.agentId)===Number(data.me&&data.me.id)',self.html)
        self.assertIn('reportTrend="deliveryUsd"',self.html)
        self.assertIn('if(b.dataset.reportTrend)',self.html)

    def test_product_report_defaults_to_top_three_and_can_expand_all(self):
        for term in (
            'id="reportProductsToggle"','Barchasi',
            'reportProductsExpanded=false','movement.slice(0,3)',
            'reportProductsExpanded?movement:movement.slice(0,3)',
            'movement.length>3?"flex":"none"',
            'reportProductsExpanded?"Yopish":"Barchasi · "+movement.length+" ta"',
            'b.id==="reportProductsToggle"',
            'reportProductsExpanded=!reportProductsExpanded',
            'period=b.dataset.period;reportProductsExpanded=false'
        ):
            self.assertIn(term,self.html)
        self.assertIn('TOP 3 · berilgan · sotilgan · qaytgan',self.html)

    def test_agent_stock_defaults_to_three_and_can_expand_all(self):
        for term in (
            'id="reportStockToggle"','reportStockExpanded=false',
            'sortedStock.slice(0,3)',
            'reportStockExpanded?sortedStock:sortedStock.slice(0,3)',
            'sortedStock.length>3?"flex":"none"',
            'reportStockExpanded?"Yopish":"Barchasi · "+sortedStock.length+" ta"',
            'b.id==="reportStockToggle"',
            'reportStockExpanded=!reportStockExpanded',
            'reportProductsExpanded=false;reportStockExpanded=false'
        ):
            self.assertIn(term,self.html)

    def test_agent_report_keeps_stock_and_route_sections_after_analytics_upgrade(self):
        for term in (
            'id="reportStockTotal"','id="reportNegativeCount"',
            'id="productStock"','Agent qoldig‘i',
            'id="routeSummary"','id="myRoute"','id="routeMap"',
            'GPS va ish vaqti'
        ):
            self.assertIn(term,self.html)

    def test_gps_report_has_day_week_month_km_hours_points_shifts_and_map(self):
        for term in (
            'data-route-period="day"','data-route-period="week"','data-route-period="month"',
            'id="routeKm"','id="routeHours"','id="routePoints"','id="routeShifts"',
            'id="routeFirst"','id="routeLast"','id="routeStops"','id="routeGaps"',
            'id="routeMapEmpty"','1 kun · 7 kun · 30 kun',
            'request("route",{period:routePeriod})','workTime(r.workSeconds)',
            'Number(r.gpsPoints||0)','Number(r.shiftCount||0)',
            'r.segments&&r.segments.length','Boshlanish · ','Oxirgi GPS · '
        ):
            self.assertIn(term,self.html)
        self.assertIn('if(b.dataset.routePeriod)',self.html)
        self.assertIn('routeLoadedKey=""',self.html)

    def test_client_card_can_open_profile_edit_without_financial_fields(self):
        for term in (
            'data-action="client_edit"','Mijoz ma’lumotlarini tahrirlash',
            'name="clientId"','id="editShop"','id="editPerson"',
            'id="editPhone"','id="editAddress"','id="editNote"',
            'editClient.profileComment','Savdo, to‘lov, qarz va mahsulot tarixi o‘zgarmaydi',
            'formAction==="client_edit"'
        ):
            self.assertIn(term,self.html)
        self.assertIn('await loadClientDetail(selected)',self.html)

    def test_payment_supports_usd_or_cashier_rate_uzs_conversion(self):
        for term in (
            'id="paymentCurrency"','value="USD"','value="UZS"',
            'cashierRateUzsPerUsd','id="paymentExpectedRate"',
            'id="paymentConversion"','function updatePaymentConversion()',
            'Kassir belgilagan kurs','Kassir kursi bo‘yicha USD ekvivalenti',
            'Summa (UZS)','Summa (USD)'
        ):
            self.assertIn(term,self.html)
        self.assertIn('som/rate',self.html)
        self.assertIn('payload.currency==="UZS"',self.html)
        self.assertIn('updatePaymentConversion();return',self.html)

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
        self.assertIn('Qaytarish miqdori mijozdagi qoldiqdan ko‘p:',self.html)

    def test_javascript_parses(self):
        if not shutil.which("node"):
            self.skipTest("node unavailable")
        scripts=re.findall(r"<script(?:\\s[^>]*)?>(.*?)</script>",self.html,re.S|re.I)
        js=max(scripts,key=len)
        p=subprocess.run(["node","--check"],input=js,text=True,capture_output=True,timeout=12)
        self.assertEqual(p.returncode,0,p.stderr)

if __name__=="__main__":
    unittest.main()
