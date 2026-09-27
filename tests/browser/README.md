# WebView regression checks

Run with Node 22 and Playwright 1.62.1:

```sh
npm install --no-save --package-lock=false playwright@1.62.1
npx playwright install chromium
node tests/browser/webview.cjs
```

The same suite detects which frontend is present on the branch. All API calls,
Telegram initialization, camera uploads and map tiles are synthetic; it never
writes to a production account. Actual Leaflet JS/CSS run in Chromium.

The six profiles combine Telegram android/ios/tdesktop platform values with
light/dark media preferences. They check contrast, theme events, form input,
page overflow and, for Agent, delayed CSS, map reopening/resizing, SVG routes,
GPS validation, photo upload, client review and the submitted payload.

These are browser simulations, not real Android Telegram or iOS devices. They
cannot verify vendor force-dark behavior, a physical camera or the native IME.
Final device acceptance: Android Telegram light and dark themes; open map,
rotate/expand; enter phone/name with keyboard; take a photo; review and save a
test client; open cashier expense review and cancel. Repeat on iOS/desktop.

Optional SCREENSHOT_DIR writes screenshots for visual inspection. WEBVIEW_HTML
can select a prior HTML revision to demonstrate regression failures.
