// Exercise the real cashier HTML with premium transliteration and synthetic APIs.
// No production requests or financial writes.
const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const categories = ['🚚 Йўл харажати', '💰 Дивиденд'];
const snapshot = {
  name: 'Test cashier', balance: 100000, rate: 12500, categories,
  pending: [], history: [], expenses: [], agents: [], daily: '',
  summary: {wallets: {cashUsd: 100000, cashUzs: 1000000, cardUsd: 100000, cardUzs: 1000000}}
};

(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    for (const colorScheme of ['light', 'dark']) {
      const page = await browser.newPage({viewport: {width: 390, height: 844}, colorScheme});
      const errors = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.addInitScript(() => {
        window.Telegram = {WebApp: {
          initData: 'test-only', ready() {}, expand() {}, onEvent() {},
          setHeaderColor() {}, setBackgroundColor() {},
          initDataUnsafe: {user: {id: 3, first_name: 'Test'}}
        }};
      });
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.pathname === '/api/cashier') {
          const payload = route.request().postDataJSON();
          if (payload.action === 'expense') {
            writes.push(payload);
            return route.fulfill({status: categories.includes(payload.category) ? 200 : 400,
              json: categories.includes(payload.category) ? {ok: true} : {error: 'Харажат турини рўйхатдан танланг.'}});
          }
          return route.fulfill({json: snapshot});
        }
        if (url.pathname.startsWith('/api/')) {
          return route.fulfill({json: {profile: {name: 'Test cashier', role: 'cashier'}}});
        }
        if (url.hostname === 'telegram.org') return route.fulfill({body: ''});
        if (url.hostname === 'app.test' && url.pathname === '/') {
          return route.fulfill({path: path.join(root, 'cashier-miniapp.html')});
        }
        if (url.pathname.startsWith('/app/premium-kit/')) {
          const filename = path.join(root, 'miniapps/premium-kit', path.basename(url.pathname));
          if (fs.existsSync(filename)) return route.fulfill({path: filename});
        }
        return route.abort();
      });
      await page.goto('https://app.test/');
      await page.waitForSelector('#app:not(.hidden)');
      // Confirm premium is active and has changed the visible option labels.
      await page.waitForFunction(() =>
        document.documentElement.lang === 'uz-Latn' &&
        document.querySelector('#category option')?.textContent.includes('Yo'));
      await page.evaluate(() => document.querySelector('[data-tab="expense"]').click());
      for (const category of categories) {
        for (const currency of ['USD', 'UZS']) {
          for (const payFrom of ['cash', 'card']) {
            await page.waitForFunction(() => !document.querySelector('#confirm').disabled);
            await page.locator('#payFrom').selectOption(payFrom);
            await page.locator('#currency').selectOption(currency);
            await page.locator('#amount').fill(currency === 'USD' ? '10.00' : '125000');
            await page.locator('#category').selectOption(category);
            assert.equal(await page.locator('#category').inputValue(), category);
            await page.locator('#recipient').fill('E2E TEST');
            await page.locator('#expenseForm button').click();
            await page.waitForSelector('#review[open]');
            const request = page.waitForRequest(req =>
              req.url().endsWith('/api/cashier') && req.postDataJSON()?.action === 'expense');
            await page.locator('#confirm').click();
            const payload = (await request).postDataJSON();
            assert.equal(payload.category, category);
            assert.equal(payload.currency, currency);
            assert.equal(payload.payFrom, payFrom);
            await page.waitForSelector('#review:not([open])', {state: 'attached'});
          }
        }
      }
      assert.equal(writes.length, 8);
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('Cashier categories: premium light/dark, cash/card, USD/UZS, dividend passed');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
