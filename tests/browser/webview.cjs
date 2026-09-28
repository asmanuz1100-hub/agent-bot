// Browser regression tests use synthetic API responses; no production writes.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),agent=fs.existsSync(path.join(root,'agent-miniapp/index.html'));
const pixel=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
const snapshot=agent?{me:{id:1,name:'Test Agent',shiftOpen:true},summary:{},clients:[{id:1,name:'Test shop',lat:40.54,lon:70.94,age:'fresh'}],products:[],events:[],handovers:[],period:{}}:{name:'Test cashier',balance:12345678900,categories:['Transport'],pending:[],history:[],expenses:[],agents:[]};
async function contrast(page,selector){
 const colors=await page.locator(selector).evaluate(el=>{const s=getComputedStyle(el);return [s.color,s.backgroundColor]});
 const luminance=c=>c.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
 const [a,b]=colors.map(luminance);assert.ok((Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=4.5,`${selector}: ${colors}`);
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
 for(const platform of ['android','ios','tdesktop'])for(const colorScheme of ['light','dark']){
 const page=await browser.newPage({viewport:{width:360,height:740},isMobile:platform!=='tdesktop',hasTouch:true,colorScheme});
 const errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));
 let releaseCss,cssRequestedResolve,scriptLoadedResolve;
 const cssGate=new Promise(r=>releaseCss=r),cssRequested=new Promise(r=>cssRequestedResolve=r),scriptLoaded=new Promise(r=>scriptLoadedResolve=r);
 await page.addInitScript(({platform})=>{window.events={};window.chromeCalls=[];window.Telegram={WebApp:{platform,initData:'test-only',ready(){},expand(){},setHeaderColor(c){window.chromeCalls.push(c)},setBackgroundColor(c){window.chromeCalls.push(c)},onEvent(n,f){window.events[n]=f}}};},{platform});
 await page.route('**/*',async route=>{
  const u=new URL(route.request().url());
  if(u.pathname.includes('/api/')){
   const req=route.request().postDataJSON();
   if(req.action==='route')return route.fulfill({json:{points:[{lat:40.54,lon:70.94},{lat:40.55,lon:70.95}],gpsPoints:2}});
   if(req.action==='photo_upload')return route.fulfill({json:{photoFileId:'test-photo'}});
   if(req.action==='client'){writes.push(req);return route.fulfill({json:{message:'Test saved'}})}
   return route.fulfill({json:snapshot});
  }
  if(u.hostname==='telegram.org')return route.fulfill({body:''});
  if(u.hostname==='tile.openstreetmap.org')return route.fulfill({body:pixel,contentType:'image/png'});
  if(u.pathname.endsWith('leaflet.css')){cssRequestedResolve();await cssGate;return route.fulfill({path:path.join(root,'agent-miniapp/vendor/leaflet/leaflet.css')});}
  if(u.pathname.endsWith('leaflet.js')){await route.fulfill({path:path.join(root,'agent-miniapp/vendor/leaflet/leaflet.js')});scriptLoadedResolve();return;}
  if(u.hostname==='app.test'&&u.pathname==='/')return route.fulfill({path:process.env.WEBVIEW_HTML||path.join(root,agent?'agent-miniapp/index.html':'cashier-miniapp.html')});
  return route.abort();
 });
 await page.goto('https://app.test/');
 await page.waitForSelector(agent?'#gate.hidden':'#app:not(.hidden)',{state:'attached'});
 if(agent){
  await contrast(page,'.app>header');
  await page.locator('nav [data-page="map"]').click();
  await Promise.all([cssRequested,scriptLoaded]);
  await page.waitForFunction(()=>!!window.L);
  assert.equal(await page.locator('#map.leaflet-container').count(),0,'map must wait for its stylesheet');
  releaseCss();
  await page.waitForSelector('#map .leaflet-marker-icon');
  await page.waitForFunction(()=>Array.from(document.querySelectorAll('#map img.leaflet-tile')).some(x=>x.complete&&x.naturalWidth));
  assert.equal(await page.locator('#map .leaflet-tile-pane').evaluate(e=>getComputedStyle(e).position),'absolute');
  await page.setViewportSize({width:412,height:780});
  await page.evaluate(()=>window.events.viewportChanged?.({isStateStable:true}));
  await page.locator('nav [data-page="home"]').click();
  await page.locator('nav [data-page="map"]').click();
  assert.equal(await page.locator('#map .leaflet-marker-icon').count(),1);
  await page.locator('nav [data-page="home"]').click();
  await page.locator('nav [data-page="reports"]').click();
  await page.waitForSelector('#routeMap svg path');
  assert.equal(await page.locator('#routeMap canvas').count(),0,'route map must avoid the Android Canvas compositor');
  await page.locator('nav [data-page="home"]').click();
  await page.locator('[data-action="client"]').first().click();
  await page.locator('#submitForm').click();
  assert.equal(await page.locator('.wizard-step.active').getAttribute('data-step'),'1','blank GPS must not advance');
  await page.locator('#lat').fill('40.54');await page.locator('#lon').fill('70.94');await page.locator('#submitForm').click();
  await page.locator('#cameraInput').setInputFiles({name:'shop.png',mimeType:'image/png',buffer:pixel});
  await page.waitForFunction(()=>document.getElementById('photoFileId').value==='test-photo');
  await page.locator('#submitForm').click();await page.locator('#phone').fill('+998901234567');
  await contrast(page,'#phone');
  assert.equal(await page.locator('nav').isVisible(),false,'keyboard focus hides fixed navigation');
  await page.locator('#submitForm').click();
  await page.locator('#person').fill('Али Test');await page.locator('#shop').fill('Baraka');await contrast(page,'#person');
  await page.evaluate(()=>window.events.themeChanged?.());
  assert.equal(await page.locator('#person').inputValue(),'Али Test');
  await page.locator('#submitForm').click();await page.locator('[data-client-product-mode="none"]').click();
  await page.locator('#submitForm').click();
  assert.match(await page.locator('#review').textContent(),/Baraka/);
  page.on('dialog',d=>d.accept());await page.locator('#submitForm').click();
  await page.waitForSelector('#page-home.active');
  assert.equal(writes.length,1);assert.equal(writes[0].phone,'+998901234567');assert.equal(writes[0].person,'Али Test');assert.equal(writes[0].photoFileId,'test-photo');
 }else{
  assert.equal(await page.locator('.tabs .active').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(23, 78, 59)','active tab must retain its component background');
  await contrast(page,'.tabs .active');await contrast(page,'.balance');
  await page.locator('[data-tab="expense"]').click();
  await page.locator('#amount').fill('10');await page.locator('#recipient').fill('Transport');await contrast(page,'#recipient');
  await page.locator('#expenseForm button').click();await page.waitForSelector('dialog[open]');
  await contrast(page,'dialog');await contrast(page,'#confirm');
  await page.evaluate(()=>window.events.themeChanged?.());
  await page.locator('#cancel').click();
  assert.equal(await page.locator('#recipient').inputValue(),'Transport');
 }
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no horizontal overflow');
 assert.deepEqual(errors,[]);assert.ok(await page.evaluate(()=>chromeCalls.length>=4),'theme event re-syncs host chrome');
 if(process.env.SCREENSHOT_DIR){fs.mkdirSync(process.env.SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,`${agent?'agent':'cashier'}-${platform}-${colorScheme}.png`),fullPage:true});}
 console.log(platform,colorScheme,'passed');await page.close();
 }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
