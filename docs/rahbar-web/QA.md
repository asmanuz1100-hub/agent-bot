# Rahbar Web — Phase 5 QA hisoboti

Sana: 2026-10-20 · Branch: `feature/rahbar-web-design-v2` (PR #139)

| Tekshiruv | Natija |
|---|---|
| `python3 -m unittest discover -p 'test_*.py'` | 456 test, OK (33 ta Postgres testi `DATABASE_URL` yo‘qligi sababli o‘tkazib yuborildi) |
| `tests/browser/webview.cjs` (Agent/Kassir, android/ios/tdesktop × light/dark) | OK |
| `tests/browser/manager-filters.cjs` (Rahbar Mini App filtrlari) | OK |
| `tests/browser/agent-payment-flow.cjs` | OK |
| `tests/browser/cashier-category.cjs` | OK |
| `tests/browser/cashier-conversion.cjs` | OK |
| `tests/browser/rahbar-web.cjs` (yangi) | OK — 10 sahifa × 2 tema, axe WCAG 2 A/AA: 0 ta buzilish |

Playwright 1.62.1 + Chromium headless shell, axe-core 4.10.3, Node 24.

## Moliyaviy moslik (`test_financial_consistency.py`, yangi)

Ssenariy: naqd dollar, so‘m (kelishilgan kurs 12 700), qaytarish, karta to‘lovi kassir tasdiqlashidan oldin va keyin,
kassirga dollar topshirish (kutilmoqda → qabul qilindi).

| Tekshiriladi | Manbalar | Natija |
|---|---|---|
| Har bir mijoz qarzi | `core.client_debt_usd`, Agent `snapshot`, Kassir qarzdorlari, Rahbar `dashboard` va `client_detail`, Tahlil `insights` | bir xil |
| Umumiy qarz va avans | Rahbar summary, Kassir jami, Web `executive` KPI, qarz yoshi yig‘indisi, Tahlil | bir xil; avans umumiy qarzni kamaytirmaydi |
| Karta to‘lovi | kassir tasdiqlaguncha qarz kamaymaydi, tasdiqdan keyin ortiqchasi avans | to‘g‘ri |
| Qarz yoshi | FIFO: eski partiya birinchi yopiladi | to‘g‘ri |
| Agentdagi pul | Agent summary, Rahbar `agent_detail`, Web `agentsCash`, `core.cash_usd/cash_som` | bir xil; USD va so‘m alohida |
| Kassirga topshirish | kutilmoqda: Rahbar, Kassir, Web bir xil; qabuldan keyin agentdagi pul kamayadi | to‘g‘ri |
| Kassa hamyonlari | Rahbar va Kassir `cashier_flows` | bir xil |
| Davr ko‘rsatkichlari | Web `executive` = `dashboard.reports` = `period_report` | bir xil |

## Topilgan va tuzatilgan muammolar

| # | Muammo | Tuzatish |
|---|---|---|
| 1 | Yopiq drawer `aria-hidden` bo‘lsa ham ichidagi tugma fokuslanardi | `inert` + `visibility:hidden` |
| 2 | Grafik SVG’larida matnli tavsif yo‘q edi | `aria-label` + `<title>` (seriya, davr, eng katta qiymat) |
| 3 | Xarita markerlari nomsiz tugma edi | agent/mijoz/tashrif markerlariga `title`/`alt` |
| 4 | Kontrast yetarli emas: ikkilamchi matn, oq matn to‘q sariq/yashil kartalarda, to‘q temadagi asosiy tugma, `--bad` matn | `--mu #5F6762`, kartalar uchun `--forest-card`/`--orange-card`, `--pri-btn`, `--bad #B5401F` (hammasi ≥ 4.5:1) |
| 5 | Ba’zi `select`larda nom yo‘q edi | `aria-label` |
| 6 | Kanban ko‘rinish tugmalarida noto‘g‘ri `role=tablist`; ikonka-tugmada nom yo‘q | rol olib tashlandi, `aria-label` |
| 7 | Sahifadan tez chiqilganda Leaflet `_leaflet_pos` xatosi | xaritani olib tashlashdan oldin `stop()/off()`, kechiktirilgan `invalidateSize` faqat mavjud xaritada |
| 8 | Grafik nuqtalari kursor yo‘qligida ekran chetida ko‘rinardi | faqat hover paytida ko‘rinadi |

## Cheklovlar

- Brauzer testlari Chromium simulyatsiyasi; haqiqiy Telegram (Android/iOS) va Safari/Firefox’da qo‘lda tekshirish kerak.
- PostgreSQL testlari (`test_pg_flows.py`) lokal muhitda `DATABASE_URL` bo‘lmagani uchun o‘tkazilmadi — Render build’ida ishlaydi.
- axe avtomatik tekshiruv; ekran o‘quvchi (VoiceOver/NVDA) bilan qo‘lda tekshiruv o‘tkazilmagan.
