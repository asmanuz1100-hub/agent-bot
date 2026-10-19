# Rahbar Premium Web — Phase 0 audit

Sana: 2026-10-19 · Branch: `feature/rahbar-web-premium` · Asos: `main` @ `ebc46f6`

Bu hujjat repo holatini va topshiriqdagi talablarni solishtiradi. «Tayyor» deb faqat
kodda haqiqatan bor va test/brauzerda tekshirilgan narsa yozilgan.

## 1. Texnik holat

| Qism | Hozir |
|---|---|
| Backend | Python 3.12, standart `http.server` (framework yo‘q), bitta jarayon: `bot.py` (Telegram webhook + HTTP API + statik fayllar) |
| Ma’lumotlar bazasi | Production: Render PostgreSQL (`DB_SCHEMA=agentbot`), lokal/test: SQLite. Sxema `core.py`da `CREATE TABLE IF NOT EXISTS` + `ALTER … ADD COLUMN IF NOT EXISTS` (faqat qo‘shuvchi migratsiyalar) |
| Frontend | Build bosqichisiz vanilla HTML/CSS/JS: `miniapps/agent`, `miniapps/rahbar-premium`, `miniapps/ombor`, `cashier-miniapp.html`, `miniapps/rahbar-web` |
| Xarita | Leaflet 1.9.4 + o‘z tile proksisi `/tiles/{z}/{x}/{y}.png` |
| Deploy | Render `asman-agent-test`, `main`ga push → avtomatik deploy (build: `unittest discover`) |
| Testlar | 434 `unittest` (SQLite, PG testlari `DATABASE_URL` bo‘lsa), `tests/browser/*.cjs` Playwright (Node 22 kerak) |

**Texnologiya qarori.** React/TypeScript/Tailwind/shadcn qo‘shish uchun Node build bosqichi,
`package.json`, Render build o‘zgarishi kerak bo‘ladi. Hozirgi barcha ilovalar build’siz
ishlaydi va deploy Python-only. Shu sabab Rahbar Web ham build’siz vanilla JS’da qoladi
(topshiriqdagi «mos kelmaydigan texnologiyani sababsiz qo‘shma» qoidasi). Ikonlar Lucide
uslubidagi inline SVG (kutubxona emas), grafiklar o‘z SVG kodimiz, xarita Leaflet.
Kelajakda SaaS uchun React’ga o‘tish alohida qaror sifatida ko‘rib chiqiladi.

## 2. Autentifikatsiya va rollar

| Ilova | Kirish | Ruxsat tekshiruvi |
|---|---|---|
| Agent / Kassir / Ombor / Rahbar Mini App | Telegram `initData` HMAC (`manager_api.verify_init_data`), 1 soat | Backendda `role()`; Rahbar API faqat `admin` |
| Rahbar Web | Login + parol (`web_auth.py`, PBKDF2-SHA256 310k), 30 kunlik sessiya, 5 xato → 15 daqiqa blok | Har so‘rovda sessiya → `role()=='admin'`; xavfli amallar (akkaunt almashtirish, bloklash, kassirni yopish) faqat `ADMIN_IDS` |
| Parol berish | Botda `/webparol [login]`, o‘chirish `/webyopish` | Faqat admin |

Origin tekshiruvi: `/api/manager`, `/api/web` faqat o‘z domenidan (`SELF_MINIAPP_ORIGINS`).

## 3. API inventari (Rahbar uchun)

`POST /api/manager` (`action`): `dashboard`, `route`, `client_detail`, `client_edit_preview|commit`,
`client_delete_preview|commit`, `client_blacklist`, `client_export`, `all_clients_export`,
`warehouse`, `product_add|update|photo`, `custom_map`, `order_status`, `agent_management`,
`agent_detail`, `agent_period_detail` (today/week/month/custom ≤31 kun), `period_report`,
`insights`, `agent_add_*`, `agent_rename_*`, `agent_feature_set`, `staff_list`, `cashier_*`,
`agent_transfer_*`, `agent_deactivate_*`.
`POST /api/web`: `login`, `logout`, `me`, `change_password`.
GPS: faqat Telegram **jonli lokatsiya** (`edited_message` → `points` jadvali, `core.py:1710`).
WebSocket/push yo‘q; Web panel 30 s (fon rejimida 60 s) da `dashboard`ni qayta so‘raydi.

## 4. Talablar bo‘yicha holat

Belgilar: ✅ tayyor · 🟡 qisman · ❌ yo‘q

### 4.1 Executive dashboard
| Talab | Holat | Izoh |
|---|---|---|
| 6 ta KPI (realizatsiya, yig‘ilgan pul, qarz, faol agent, yangi mijoz, tashrif) | ✅ | real `dashboard` |
| Oldingi davr bilan solishtirish, % | ✅ Phase 2 | 6 ta KPI, teng oyna (bugun ↔ kecha shu soatgacha, oy ↔ o‘tgan oy shu kunlar) |
| Trend | ✅ Phase 2 | realizatsiya, pul, qarz sparkline |
| Kunlik / haftalik / oylik savdo | ✅ Phase 2 | soatlik/kunlik/haftalik/oylik guruhlash |
| Pul yig‘ish dinamikasi | ✅ | `paymentsUsd` seriyasi |
| Qarzdorlik dinamikasi | ✅ Phase 2 | `executive` har bo‘lim oxiridagi musbat qoldiqlar |
| Agentlar samaradorligi | ✅ | |
| Filtrlar: sana, hudud, agent, valyuta, davr | ✅ Phase 2 | davr: bugun/kecha/7/30/joriy oy/tanlangan/umumiy; valyuta faqat yig‘ilgan pulga (USD/UZS qo‘shilmaydi) |

### 4.2 GPS Control Center
| Talab | Holat | Izoh |
|---|---|---|
| Agentlar xaritada, oxirgi GPS, yangilanish vaqti, ishlayaptimi | ✅ | `dashboard.agents` |
| Kunlik yo‘nalish, tashrif buyurilgan mijozlar | ✅ | agent kartasida, `agent_period_detail` |
| Agentning bugungi savdosi, yig‘ilgan pul, smena boshi | ✅ | agent kartasida |
| Smena tugash vaqti | 🟡 | faqat «oxirgi smena» rejimida |
| 3 panelli maket (ro‘yxat / xarita / agent) | ❌ | hozir 2 panel + o‘ng drawer |
| Hudud bo‘yicha filtr | ❌ | |
| Mijoz markerlari yashil/sariq/qizil | 🟡 | Mijozlar xaritasida bor (0–2 / 3–4 / 5+ kun, `manager_api.dashboard`), GPS sahifasida yo‘q |
| Markerlarni guruhlash (cluster) | ❌ | |

### 4.3 Agentlar
✅ ro‘yxat, holat, bugungi faoliyat, tashrif, yangi mijoz, realizatsiya, yig‘ilgan pul, agentdagi pul,
marshrut, ish vaqti, masofa, KPI taqqoslash jadvali (Hisobot).
🟡 kassirga topshirilgan pul (faqat kutilayotgani), agent bo‘yicha qarzdorlik (Tahlil’da).

### 4.4 Mijozlar
✅ ro‘yxat, karta, telefon, do‘kon, manzil, GPS, hudud, agent, oxirgi tashrif, tashriflar, savdo/to‘lov/qaytarish
tarixi (`events`), foto, izoh, qidiruv (ism/telefon/do‘kon/hudud/agent), xarita, qarzdor filtri, uzoq tashrifsiz filtri.
🟡 faol/passiv (faqat Tahlil reytingida). ❌ qarzdorlik tarixi (yurgan qoldiq) mijoz kartasida.

### 4.5 Savdo va qarzdorlik, 4.6 Kassa
✅ bitta formula, USD ledger, so‘m to‘lov kelishilgan kurs bilan USD’ga o‘tkaziladi (`record_client_payment`, `fx_rate` saqlanadi),
karta to‘lovi kassir tasdiqlaguncha qarzni kamaytirmaydi, kassa hamyonlari (naqd so‘m / naqd $ / karta so‘m / karta $),
kutilayotgan topshirishlar, xarajat kategoriyalari.
🟡 avans alohida faqat Tahlil’da. ❌ Web’da konvertatsiya tarixi ko‘rinishi (Kassir ilovasida bor).

### 4.7 Hisobotlar
✅ Bugun, 7 kun, joriy oy, tanlangan davr; Excel/CSV eksport.
❌ «Kecha», «30 kun», «Umumiy» davrlari; hudud filtri.

## 5. Hisoblash auditi — topilmalar

| # | Daraja | Topilma | Joyi | Tavsiya |
|---|---|---|---|---|
| F1 | **Yuqori** | Rahbar `summary.debtUsd` = barcha mijoz qoldiqlarining **sof** yig‘indisi: avansdagi (manfiy) mijozlar umumiy qarzni kamaytiradi. Kassir faqat musbat qarzlarni, Tahlil qarz va avansni alohida ko‘rsatadi. Bir xil «umumiy qarz» uch ekranda turlicha chiqishi mumkin | `manager_api.py:558` | `debtUsd` = faqat musbat qoldiqlar, `advanceUsd` alohida. **Phase 1’da tuzatildi**, test bilan |
| F2 | O‘rta | «Oy» ma’nosi har xil: `dashboard.reports.month` va `agent_detail` = oxirgi 30 kun, `period_report`/`insights` `month` = joriy kalendar oy | `manager_api.py:388`, `core.resolve_period` | Yorliqlarni aniq qilish («30 kun» / «Joriy oy»), Phase 6’da yagona davr moduli |
| F3 | O‘rta | Mijoz qarzi formulasi (`delivery − payment − return`) 9 joyda takrorlangan SQL. Hozir hammasi bir xil, lekin kelajakda ajralib ketish xavfi | `core`, `agent_api`, `cashier_api`, `manager_api`, `analytics`, `reports` | Phase 5: bitta `core.debt_sql()` manbaga yig‘ish, regression test |
| F4 | Past | Faqat so‘mda yozilgan eski hodisalar (`amount>0, amount_usd=0`) USD qarzga kirmaydi | `events` | Ataylab shunday (USD ledger). Tahlil `legacyEvents` sanog‘ini ko‘rsatadi; UI’da ogohlantirish qo‘shish |
| F5 | O‘rta (performance) | Web `dashboard` har 30 s da barcha mijozlar (≤5000) + 1200 tranzaksiyani qaytaradi | `manager_api.dashboard` | Phase 2: yengil `executive` endpoint (faqat KPI), ro‘yxatlar sahifalab |
| F6 | O‘rta (xavfsizlik) | Web sessiya tokeni `localStorage`da; XSS bo‘lsa o‘g‘irlanishi mumkin (hamma matn `esc()` orqali) | `rahbar-web/app.js` | Phase 8: HttpOnly + SameSite cookie, CSP sarlavhasi |

Valyuta: USD va UZS hech qayerda kurssiz qo‘shilmaydi — kassa hamyonlari alohida, umumiy kassa «USD ekvivalenti»
faqat saqlangan kurs bilan (`core.cashier_balance_usd`).

## 6. Qayta ishlatiladigan narsalar

`manager_api` (dashboard, client/agent detail, period report), `analytics.insights/today_plan`, `reports` (PDF/XLSX),
`web_auth`, Rahbar Web’dagi drawer/modal/toast/eksport/grafik/donut/xarita komponentlari, tile proksi.

## 7. Bosqichlar rejasi

| Phase | Natija | Backend o‘zgarishi |
|---|---|---|
| 1 Design system | Spetsifikatsiya ranglari (`#F8FAFC`, `#2563EB`…), Inter, yorug‘ rejim asosiy + to‘q, header’da global qidiruv, skeleton/empty/error holatlari, 1920→390 responsive; F1 tuzatish | F1 (faqat hisob, sxema emas) |
| 2 Executive dashboard | Filtrlar (davr: bugun/kecha/7/30/oy/tanlangan/umumiy, hudud, agent), har KPI’da oldingi davr %, haftalik/oylik savdo, qarz dinamikasi | Yangi read-only `executive` action |
| 3 GPS Control Center | 3 panel, hudud/agent filtri, mijoz markerlari rangi, cluster, smena boshi/oxiri | `agent_period_detail`ga smena vaqtlari |
| 4 Agents / Customers | Agent taqqoslash, kassirga topshirilgan jami, mijoz qarz tarixi (yurgan qoldiq) | `client_detail`ga balans tarixi |
| 5 Finance | Avans alohida, to‘lov turlari, konvertatsiyalar, F3 yagona formula | refactor + regression testlar |
| 6 Analytics | Yagona davr moduli (F2), hudud filtri, barcha hisobotlarda bir xil ko‘rsatkichlar | `resolve_period` kengaytirish |
| 7 QA | Unit/API/browser/responsive/regression | — |
| 8 Release | Cookie sessiya, CSP, performance, deploy checklist | F6 |

Har bosqich alohida commit; `main`ga faqat PR orqali va alohida ruxsat bilan.
