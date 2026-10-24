# AIBI SaaS — arxitektura va amalga oshirish rejasi

Holat (2026-10-23, kod asosida):

| Talab | Hozir | Fayl |
|---|---|---|
| Login/parol | Bor (`web_auth`: hash, sessiya tokeni, bloklash) | `web_auth.py` |
| Rollar va huquqlar | Bor (admin, agent, cashier, sales…; per-user huquqlar) | `perms.py` |
| Modullarni yoqish/o‘chirish | Bor (rahbar paneli orqali) | `modules.py` |
| Korxona brendingi | Bor (nom, rekvizit, logo) | `branding.py` |
| Bir nechta korxona (tenant) | **Yo‘q** — barcha jadval bitta korxonaga tegishli | — |
| Korxonani ro‘yxatdan o‘tkazish | **Yo‘q** | — |
| Tarif / obuna | **Yo‘q** | — |
| Android, iOS, Web uchun yagona backend | Bor: `/api/web` (login), `/api/agent`, `/api/shop`, `/api/manager` | `bot.py` |

## Tanlangan yondashuv: har bir korxona — alohida PostgreSQL sxemasi

Kodning hamma joyi bitta korxona deb yozilgan (yuzlab SQL so‘rov). Har bir jadvalga
`company_id` qo‘shish xavfli: bitta unutilgan `WHERE` boshqa korxona ma'lumotini ochib qo‘yadi.
Shuning uchun:

1. **Boshqaruv bazasi** (`aibi_control` sxemasi): `companies(id, slug, name, schema, plan, status, trial_until)`,
   `subscriptions`, `logins(login, company_id)` — loginni korxonaga bog‘lash uchun.
2. **Har bir korxona** — o‘z sxemasi (`c_asman`, `c_<slug>`); jadvallar hozirgi `core.connect` yaratadigan bilan bir xil.
3. So‘rov kelganda: login → `aibi_control.logins` → korxona sxemasi → `SET search_path` → mavjud kod o‘zgarishsiz ishlaydi.
4. Sessiya tokeni korxona sxemasi ichida saqlanadi — token boshqa korxonaga o‘tolmaydi.
5. Telegram bot faqat ASMAN (`c_asman`) uchun qoladi; yangi korxonalar faqat AIBI ilova/web orqali.

## Bosqichlar (har biri alohida PR, production’ga zararsiz)

1. `aibi_control` sxemasi va `companies` jadvali; ASMAN `public` sxemasida qoladi (`schema='public'`). Kod o‘zgarmaydi.
2. `request_db()` ichida `search_path` tanlash; yagona tenant bilan testlar o‘tishi shart.
3. Korxonani ro‘yxatdan o‘tkazish (super-admin) + bo‘sh sxema yaratish + birinchi rahbar logini.
4. Tarif: `plan` → yoqilgan modullar chegarasi (`modules.py` ga yuqori chegara sifatida).
5. Obuna muddati tugaganda faqat o‘qish rejimi.

## Orqaga qaytarish

Har bosqich qo‘shimcha (additive): yangi sxema/jadval qo‘shiladi, mavjudlari o‘zgarmaydi.
Qaytarish = oldingi commitga deploy; `aibi_control` sxemasi qolsa ham ASMAN ishiga ta'sir qilmaydi.
Har migratsiyadan oldin to‘liq backup (rahbar panelidagi «To‘liq backup»).
