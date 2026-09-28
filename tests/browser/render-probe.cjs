// Synthetic device diagnostic tests; every network request is intercepted.
const {chromium}=require('playwright');
const path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../../agent-miniapp');
const tile=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const colorScheme of ['light','dark']){
   const page=await browser.newPage({viewport:{width:393,height:800},deviceScaleFactor:2.75,isMobile:true,hasTouch:true,colorScheme,userAgent:'Mozilla/5.0 (Linux; Android 13; Test Device; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.0.0 Mobile Safari/537.36'});
   const errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(()=>{window.Telegram={WebApp:{platform:'android',version:'8.0',initData:'SENSITIVE_TEST',ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){}}}});
   await page.route('**/*',route=>{
    const req=route.request(),u=new URL(req.url());requests.push({method:req.method(),host:u.hostname,path:u.pathname});
    if(u.hostname==='telegram.org')return route.fulfill({body:''});
    if(u.hostname==='tile.openstreetmap.org')return route.fulfill({contentType:'image/png',body:tile});
    if(u.hostname==='app.test')return route.fulfill({path:path.join(root,u.pathname==='/'?'index.html':u.pathname)});
    return route.abort();
   });
   await page.goto('https://app.test/render-probe.html#tgWebAppData=SENSITIVE_FRAGMENT');
   await page.waitForSelector('body[data-probe-ready="true"]');
   assert.equal(await page.locator('.leaflet-marker-icon').count(),91);
   await page.locator('#phone').fill('98765');await page.locator('#person').fill('Ali');await page.locator('#shop').fill('Test Shop');
   const before=await page.locator('#phone').inputValue();
   for(const variant of ['root','flat','input','blend','layer','baseline']){
    await page.selectOption('#variant',variant);
    await page.waitForFunction(v=>JSON.parse(document.querySelector('#device').textContent).variant===v,variant);
    assert.equal(await page.locator('#phone').inputValue(),before,'switching must preserve input');
    const s=JSON.parse(await page.locator('#device').textContent());
    assert.equal(s.fields[0].length,5);assert.equal(s.telegramPlatform,'android');
    assert.ok(!JSON.stringify(s).includes('SENSITIVE'));assert.ok(!JSON.stringify(s).includes('98765'));
   }
   assert.equal(await page.locator('#variantStyles').textContent(),'','baseline must undo all overrides');
   assert.match(await page.locator('#back').getAttribute('href'),/#tgWebAppData=SENSITIVE_FRAGMENT$/);
   assert.deepEqual(errors,[]);
   assert.ok(requests.every(r=>r.method==='GET'&&!r.path.includes('/api/')),'diagnostics must not call business APIs');
   assert.ok(requests.every(r=>['app.test','telegram.org','tile.openstreetmap.org'].includes(r.host)));
   console.log('render probe',colorScheme,'passed (91 markers, independent modes, private values excluded, no business requests)');
   await page.close();
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
