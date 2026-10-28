# AIBI ilovasi sahifalari

`miniapps/aibi-*` — AIBI ilovasining (Android) o'z sahifalari. Ular **mustaqil**:
Telegram Mini App'lardan (`miniapps/agent`, `ombor`, `savdo`, `rahbar-premium`, `cashier-miniapp.html`)
nusxa olinmaydi va ularga bog'liq emas. Ilovadagi o'zgarish shu papkalarda qilinadi,
Telegram Mini App'dagi o'zgarish ilovaga o'tmaydi (va aksincha).

- Kirish: login/parol (rahbar web panelda beradi) → token. Bot kerak emas.
- `bridge.js` — token bilan API so'rovlari (`Authorization: Bearer`), Android tugmalari, haptika.
- `agent-shift.js` — agent smenasi (Ishni boshlash/tugatish) va ilova GPS'i.

| Sahifa | Manzil |
|---|---|
| Agent | `/app/aibi-agent/` |
| Kassa | `/app/aibi-kassa/` |
| Ombor | `/app/aibi-ombor/` |
| Savdo | `/app/aibi-savdo/` |
| Rahbar | `/app/aibi-rahbar/` |
