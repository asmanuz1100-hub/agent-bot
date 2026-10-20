# AIBI — Smart Business Platform: rebrending

Platforma nomi **AIBI** (ilovalar va panel). Kompaniya ma'lumotlari (ASMAN SILICAT nomi, akt sverka
rekvizitlari, hujjat va fayl nomlari, Rahbar Web'dagi kompaniya brendi) **o'zgarmagan**.

## Display nomlar
| Ilova | Nom | Qayerda |
|---|---|---|
| Agent Mini App | AIBI Agent | `miniapps/agent/index.html`, `premium-kit/premium.js`, bot menyu tugmasi |
| Rahbar Mini App | AIBI Manager | `miniapps/rahbar-premium/index.html`, `bot.py` (`/app/rahbar` yo'naltirish) |
| Kassir Mini App | AIBI Cashier | `cashier-miniapp.html`, bot menyu tugmasi |
| Ombor Mini App | AIBI Warehouse | `miniapps/ombor/index.html`, bot menyu tugmasi |
| Savdo Mini App | AIBI Savdo | `miniapps/savdo/index.html`, bot menyu tugmasi |
| Web panel | AIBI Dashboard | `miniapps/rahbar-web/*` (+ `manifest.webmanifest`) |
| Mobil ilova (Expo) | AIBI Agent | `~/asman-mobile/app.json` (bundle ID `uz.asman.agent` o'zgarmagan) |

O'zgarmagan (ataylab): API endpointlar, mini app manzillari (`/app/...`), bot reply-tugmalari matni
(`📱 Agent Mini App` va h.k. — eski klaviaturalar ishlashi uchun), `ASMANOffline` va kesh kalitlari
(agentlarning oflayn navbati yo'qolmasligi uchun), Telegram user ID va auth.

## Assetlar — `miniapps/premium-kit/aibi/`
Generator: `python3 scripts/brand/build_aibi_assets.py` (Pillow). Bitta geometriyadan SVG va PNG.
- `aibi-mark.svg`, `aibi-mark-{1024,512,192,64}.png` — belgi (shaffof fon)
- `aibi-icon-{dark,light}.svg` va `-{1024,512,192,180,120,64,32,16}.png` — ilova ikonkalari
- `aibi-logo-{dark,light}.svg` — belgi + AIBI + SMART BUSINESS PLATFORM
- `aibi-adaptive-foreground.png`, `aibi-adaptive-background.png` — Android adaptive icon
- `aibi-splash.png`, `favicon.ico` (16/32/64)
- `aibi.css` — umumiy tokenlar: ranglar, Aurora gradient, shrift, `.aibi-wm` logotip bloki
- `apps/{agent,manager,cashier,warehouse,dashboard}-{192,180,64,32}.png` va `.ico` — har bir ilovaning o'z ikonkasi
  (foydalanuvchi to'plamidan, `python3 scripts/brand/build_app_icons.py`)
- `telegram-profile-512.png` — BotFather profil rasmi
- `preview.html` — barcha assetlar bitta sahifada

Belgi va ikonkalar — foydalanuvchi bergan **AIBI Professional Brand Kit**dan: vektor belgi
`source/aibi-symbol.svg` (SVG'lar shu vektordan), shaffof 1024 PNG `source/aibi-mark-source.png`
(PNG o'lchamlar shundan, chekka bo'shlig'i bilan), ilova ikonkalari `source/apps/*.png` (1024 px).
Kit README'sida yozilganidek, bu asl manba emas — mos qayta chizilgan tahrirlanadigan vektor.
Belgining o'ng tomonida ikki bo'lak tutashgan joyda ingichka pog'ona bor (kitning o'zida) — dizayner
tuzatgan versiyani `source/`ga qo'yib, ikkala generatorni qayta ishga tushirish kifoya. So'z belgisi: «AIBI».

## Telegram BotFather (qo'lda, bot egasi bajaradi)
`@username` o'zgartirilmaydi.
1. @BotFather → `/mybots` → botni tanlang.
2. **Edit Bot → Edit Name** → `AIBI` (yoki `AIBI Agent`).
3. **Edit Bot → Edit Botpic** → `miniapps/premium-kit/aibi/telegram-profile-512.png` yuboring (dizayn to'plamidagi Telegram profil ikonkasi).
4. **Edit Bot → Edit About** → `AIBI — Smart Business Platform. Savdo, mijozlar, ombor va kassa bitta joyda.`
5. **Edit Bot → Edit Description** → bot ochilganda ko'rinadigan matn (ixtiyoriy).
6. Agar Mini App'lar BotFather'da alohida ro'yxatdan o'tgan bo'lsa (`/myapps`): har birining nomi va
   rasmini (640×360) yangilang. Manzillarni **o'zgartirmang**.
Menyu tugmasi matni (`AIBI Agent`, `AIBI Cashier`, ...) deploydan keyin bot o'zi yangilaydi.

## Production deploy oldidan
- [ ] GitHub `Tests` va `WebView browser regressions` yashil
- [ ] Telegram Android'da: Agent, Kassir, Ombor, Savdo, Rahbar ochiladi; logotip yorug' va tungi rejimda ko'rinadi
- [ ] Agent oflayn navbati: oflayn amal qilib, internet qaytgach yuborilishini tekshirish
- [ ] Rahbar Web: kompaniya logotipi yuklangan bo'lsa, u chiqadi (AIBI faqat standart holatda)
- [ ] Akt sverka PDF/Excel'da kompaniya nomi o'zgarmagan
- [ ] Deploydan keyin Render loglari: xato yo'q
