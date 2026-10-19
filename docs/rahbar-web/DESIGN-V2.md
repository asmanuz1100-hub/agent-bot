# Rahbar Web — Premium Design V2

Sana: 2026-10-20 · Branch: `feature/rahbar-web-design-v2` (asos: `feature/rahbar-web-premium`, PR #138)

Referenslar: `1817.mp4` (Customer messaging / Sales CRM, _code_and_chill_) va `1816.mp4` (Admin Dashboard V7, @code.xr).
Ulardan faqat kompozitsiya, ritm va vizual uslub olinadi — rasmlar, matnlar, kod yoki brend ko‘chirilmaydi.

## 1. Joriy dizayn kamchiliklari (Phase 1–3 holati)

| # | Kamchilik | Ta’siri |
|---|---|---|
| 1 | Sovuq kulrang-ko‘k palitra (`#F8FAFC`), bir xil oq kartalar — vizual ierarxiya sust, «shablon» ko‘rinish | Muhim raqam (qarz, kassa) boshqalardan ajralmaydi |
| 2 | Keng (240 px) oq sidebar ekranning 1/6 qismini egallaydi, 9 ta bo‘lim bir xil vaznda | Xarita va jadvallar uchun joy kam |
| 3 | Bosh sahifada 6 KPI + 4 grafik + jonli bo‘lim bir ustunda — uzun scroll, «hozir nima bo‘lyapti» yon panelda emas | Rahbar jonli holatni ko‘rish uchun pastga tushishi kerak |
| 4 | Qarz yoshi (aging), hududlar bo‘yicha savdo, agentlardagi pul bosh sahifada yo‘q | Asosiy moliyaviy savollar javobsiz |
| 5 | Rangli semantik kartalar yo‘q — ogohlantirishlar oddiy ro‘yxat | Diqqat talab qilgan holat ko‘zga tashlanmaydi |
| 6 | Buyurtmalar faqat jadval; Kanban/Board yo‘q | Ombor jarayoni ko‘rinmaydi |
| 7 | To‘q rejim yorug‘ tokenlarning invertatsiyasi, alohida ishlangan tema emas | Kontrast va chuqurlik bir xil emas |
| 8 | Animatsiyalar minimal; drawer orqasida blur yo‘q, sidebar yig‘ilmaydi | «Premium» his kam |

## 2. Videolardan olinadigan elementlar

| Element | Manba | Bizdagi qo‘llanishi |
|---|---|---|
| Iliq krem fon `#F7F6F2`, katta yengil sarlavhalar | 1817 | Butun ilova foni, sahifa sarlavhasi |
| Ixcham qora vertikal ikonka paneli (yumaloq «pill») | 1817 | Chapdagi rail: qidiruv, lenta, yangilash, tema, sozlamalar, chiqish; bosilganda kengayadi (collapse/expand) |
| Yuqoridagi yumaloq pill tablar | 1817 | Asosiy bo‘limlar navigatsiyasi |
| Sariq / to‘q yashil / to‘q sariq kartalar | 1817 «Hot deals», Kanban | Semantik: sariq — e’tibor, yashil — yaxshi/yopilgan, to‘q sariq — xavf/qarz |
| Revenue grafigi (katta raqam + seriya + pill toggles) | 1817 | Savdo va pul yig‘ish grafigi |
| Aging bloklari + legend jadvali | 1817 Finance | Qarzdorlik yoshi (0–30 / 31–60 / 61–90 / 90+) |
| Segmentlangan ustun («Stage mix») | 1817 | Hududlar bo‘yicha savdo |
| Team quota halqasi yashil kartada | 1817 | Undiruv darajasi (yig‘ilgan / realizatsiya) |
| Invoices jadvali, filter pill’lar, toast «Undo» | 1817 | So‘nggi muhim operatsiyalar, kelajakda moliya jadvallari |
| Kanban + Board/List, rangli detail modal, blur fon | 1817 Pipeline | Phase 4: buyurtmalar (statuslar backenddan) |
| Grafit korpus, oq yumshoq KPI kartalar, nozik to‘q sariq aksent | 1816 | KPI kartalar, to‘q tema |
| O‘ng Activity / Calendar paneli | 1816 | Bosh sahifa o‘ng paneli: kalendar (kunlik realizatsiya), jonli lenta, diqqat |

## 3. Yangi sahifa arxitekturasi

```
┌ rail ┐┌──────────── header: sarlavha · pill tablar · qidiruv · jonli ────────────┐
│ logo ││ Asosiy · GPS · Mijozlar · Agentlar · Moliya · Buyurtmalar · Hisobot · Tahlil │
│ 🔍   │├──────────────────────────────────────────────┬───────────────────────────┤
│ 🔔   ││ asosiy kontent (sahifa)                      │ o‘ng panel (faqat Asosiy) │
│ ⟳    ││                                              │ kalendar · lenta · diqqat │
│ ◐    ││                                              │                           │
│ ⚙    │└──────────────────────────────────────────────┴───────────────────────────┘
└──────┘
```

| Sahifa | Holat | Bosqich |
|---|---|---|
| Executive Dashboard | qayta quriladi | Phase 2 (shu PR) |
| GPS Control Center | mavjud (Phase 3), yangi tokenlarga o‘tadi | Phase 3 V2 |
| Customers CRM | mavjud jadval + drawer; kartalar/aging qo‘shiladi | Phase 4 |
| Agent Management | yangi alohida sahifa (hozir Xodimlar + GPS) | Phase 4 |
| Finance & Debt | Kassa sahifasi kengayadi: aging, qarzdorlar, konvertatsiya | Phase 4 |
| Orders Kanban | Ombor buyurtmalari Board/List | Phase 4 |

Buyurtma statuslari backendda: `new → preparing → loaded → delivered`, `rejected`. Ruxsat etilgan o‘tishlar
`core.set_order_status`da; `loaded`ni faqat omborchi qo‘yadi. Kanbanda drag-and-drop faqat shu o‘tishlarga ruxsat beradi.
Moliyaviy yozuvlar (to‘lov, topshirish) karta sudrab o‘zgartirilmaydi.

## 4. Komponentlar va fayllar

| Fayl | O‘zgarish |
|---|---|
| `miniapps/rahbar-web/app.css` | V2 tokenlar (yorug‘ + alohida to‘q), rail, pill tablar, semantik kartalar, aging, segment bar, kalendar, o‘ng panel, blur, animatsiyalar, `prefers-reduced-motion` |
| `miniapps/rahbar-web/index.html` | Rail + header tablari tuzilmasi |
| `miniapps/rahbar-web/app.js` | Shell (rail/tablar/collapse), Executive Dashboard V2, kalendar, aging, hudud segmentlari |
| `executive.py` | Qo‘shimcha: agentlardagi pul (USD va so‘m alohida), kassirda tasdiq kutayotgan pul, qarz yoshi (FIFO), hududlar bo‘yicha savdo, oy kalendari |
| `test_executive.py` | Yangi hisoblar uchun testlar (aging yig‘indisi = umumiy qarz) |

**Qarz yoshi qoidasi.** Har mijoz uchun to‘lov va qaytarishlar eng eski yopilmagan tovar berishni yopadi (FIFO).
Yopilmay qolgan qism tovar berilgan sanadan bugungacha kun bo‘yicha guruhlanadi. Shu sabab barcha guruhlar yig‘indisi
umumiy qarzga (musbat qoldiqlar) teng bo‘ladi.

## 5. Ishlash tartibi va xavflar

1. Phase 1 — tokenlar va shell (rail, tablar), mavjud sahifalar yangi tokenlarda ishlashda davom etadi.
2. Phase 2 — Executive Dashboard V2 + `executive` kengaytmasi + testlar.
3. Phase 3 V2 — GPS sahifasini yangi uslubga moslash.
4. Phase 4 — Customers, Agents, Finance & Debt, Orders Kanban.
5. Phase 5 — QA: regression, API, brauzer, responsive (1440/1024/768/390), moliyaviy moslik.

| Xavf | Yumshatish |
|---|---|
| PR #138 hali merge bo‘lmagan, V2 uning ustiga qurilgan | V2 PR bazasi `feature/rahbar-web-premium`; #138 merge bo‘lsa bazani `main`ga almashtirish kifoya |
| Rangli kartalarda kontrast (sariq fon + matn) | Sariq kartada to‘q matn `#17221F`, yashil/to‘q sariqda oq; tekshiruv brauzerda |
| Katta ma’lumotda aging hisobi sekin | Bitta SQL o‘qish + Python FIFO O(n); 30 s kesh |
| Ikki uslubni aralashtirib yuborish | Yagona token to‘plami, rang faqat semantik vazifada |
| Telegram Mini App’lar buziladi | Faqat `rahbar-web` va read-only `executive` o‘zgaradi; Mini App fayllariga tegilmaydi |
