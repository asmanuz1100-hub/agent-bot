# ASMAN кассир бўлими — алоҳида тест версия

Ушбу тармоқ **асосий ишчи ботга ўрнатилмаган**. Pull request #20 тест кодини main'га қўшмайди; merge ёки production deploy фақат алоҳида тасдиқ ва текширувдан кейин.

## Функциялар
- Агент кассага USD пул топширса, барча кассирларга агент, сумма ва топшириш ID билан хабарнома, «🔎 Кўриб чиқиш» тугмаси келади.
- Кассир аввал топширишни очиб, санаб олиб, қабул қилади ёки рад этади. Пул кассага фақат қабул қилинганда қўшилади; иккинчи марта қабул қилинмайди.
- Агент ва админ кассир қарори ҳақида хабарнома олади. Рад этилса, агент тўғри суммани қайта юбориши мумкин.
- «🧾 Харажат киритиш»: кассир тур, USD сумма, кимга/нима учун берилгани ва изоҳни киритиб мустақил сақлайди. Админга хабарнома келади.
- «📥 Касса»да USD ҳисобий қолдиқ, тасдиқ кутилаётган пул, бугун қабул қилинган пул ва харажатлар; «📋 Харажатлар тарихи»да охирги 25 харажат.

## Пул ҳисоби
USD касса қолдиғи = тасдиқланган USD handovers - cashier_expenses. Мижоздан агент олган пул фақат агент ҳисобида туради; кассир қабул қилмагунича кассага қўшилмайди. Мавжуд ўтмишдаги банк/қўлдаги касса ва сўм маблағлари бу ҳисобга кирмайди. Тестда бошланғич қолдиқ 0; аввал тест агенти пул олиб, топшириши керак.

## Тест
`python -m unittest discover -v`

Telegram орқали тест қилишда **алоҳида тест бот токени, алоҳида SQLite файл ёки алоҳида PostgreSQL схема/база ва алоҳида Render сервис** керак. Ишчи BOT_TOKEN, DATABASE_URL ва webhook'ни такрор уламанг: Telegram'да бир бот учун иккинчи webhook ишчи сервисга халақит қилиши мумкин. Ишчи маълумотларни бу тестга импорт қилманг.

PostgreSQL'да connect() янги cashier_expenses жадвалини яратади; тикланган PostgreSQL базада миграция ва реал Telegram webhook ишлаши алоҳида синовдан ўтказилиши шарт. Ботнинг асосий маълумотлар захирасини алоҳида сақланг.

## Cashier Mini App

Cashiers can send `/start`, then choose `📱 Кассир Mini App` and open the
inline Telegram Web App button. The panel is served by the bot at `/cashier/`;
no extra Render service or frontend branch is required. `CASHIER_MINIAPP_URL`
may override the launcher URL; by default it uses the bot's webhook/public URL.

Each `/api/cashier` request verifies signed Telegram initData and the current
cashier role. The panel supports pending handover review and acceptance/rejection,
USD/UZS expenses, internal FX rates, recent history and today's report. There is
no manual income action. USD balance follows the existing normalized cash ledger.
A review is required within 15 minutes before a decision. Expense retries reuse
an operation ID; stale UZS rates and overspending are rejected by core rules.
Notifications run after commit, so delivery failure cannot undo a saved operation.

Validation: `python -m unittest discover -v`. On macOS set `PDF_FONT_PATH` to a
Cyrillic-capable TTF if the existing report tests cannot locate a Linux font.
