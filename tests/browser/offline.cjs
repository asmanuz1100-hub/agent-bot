// Agent offline-first browser test. Synthetic API only; never touches production.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');

const root=path.resolve(__dirname,'../..');
const pixel=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
const snapshot={
  me:{id:1,name:'Offline Agent',shiftOpen:true,liveAttached:true},
  summary:{newClientsToday:0,goodsToday:0,paymentTodayUsd:0,cashAvailableUsd:0},
  clients:[],
  products:[{pack:1,name:'Gruntovka 1 kg',priceUsd:2,stock:20,agentStock:20}],
  events:[],handovers:[],period:{},collectionTasks:[],expenseWallet:{balanceUzs:0,history:[]},
  cashierRateUzsPerUsd:12800,generatedTs:Math.floor(Date.now()/1000)
};

(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:390,height:820},isMobile:true,hasTouch:true,serviceWorkers:'block'});
 const page=await context.newPage();
 const writes=[],uploads=[],actions=[];
 page.on('pageerror',e=>{throw e});
 await page.addInitScript(()=>{
   window.events={};window.fetchCalls=[];
   const originalFetch=window.fetch.bind(window);
   window.fetch=function(url,options){window.fetchCalls.push({url:String(url),body:options&&options.body||""});return originalFetch(url,options)};
   window.Telegram={WebApp:{
     platform:'android',initData:'offline-test-signed',
     ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},
     onEvent(n,f){window.events[n]=f}
   }};
 });
 await page.route('**/*',async route=>{
   const u=new URL(route.request().url());
   if(u.pathname.includes('/api/')){
     const req=route.request().postDataJSON();actions.push(req.action);
     if(req.action==='photo_upload'){uploads.push(req);return route.fulfill({json:{photoFileId:'offline-test-photo-id'}})}
     if(req.action==='client'){writes.push(req);return route.fulfill({json:{ok:true,clientId:77,message:'Synced'}})}
     return route.fulfill({json:snapshot});
   }
   if(u.hostname==='telegram.org')return route.fulfill({body:''});
   if(u.hostname==='app.test'&&u.pathname==='/')return route.fulfill({path:path.join(root,'agent-miniapp/index.html')});
   if(u.hostname==='app.test'&&u.pathname==='/offline.js')return route.fulfill({path:path.join(root,'agent-miniapp/offline.js'),contentType:'application/javascript'});
   if(u.hostname==='app.test'&&u.pathname==='/sw.js')return route.fulfill({path:path.join(root,'agent-miniapp/sw.js'),contentType:'application/javascript'});
   if(u.pathname.endsWith('/vendor/leaflet/leaflet.css'))return route.fulfill({path:path.join(root,'agent-miniapp/vendor/leaflet/leaflet.css')});
   if(u.pathname.endsWith('/vendor/leaflet/leaflet.js'))return route.fulfill({path:path.join(root,'agent-miniapp/vendor/leaflet/leaflet.js')});
   if(u.hostname==='tile.openstreetmap.org')return route.fulfill({body:pixel,contentType:'image/png'});
   return route.abort();
 });

 await page.goto('https://app.test/');
 await page.waitForSelector('#gate.hidden',{state:'attached'});
 await page.waitForFunction(()=>!!window.ASMANOffline);
 assert.equal(actions.filter(x=>x==='quick_snapshot').length,1,'startup must make only one quick_snapshot request');

 await page.locator('[data-action="client"]').first().click();
 await page.locator('#lat').fill('40.54');
 await page.locator('#lon').fill('70.94');
 await page.locator('#submitForm').click();

 await context.setOffline(true);
 await page.waitForFunction(()=>navigator.onLine===false);
 await page.locator('#cameraInput').setInputFiles({name:'offline-shop.png',mimeType:'image/png',buffer:pixel});
 await page.waitForFunction(()=>document.getElementById('photoFileId').value==='offline_local_photo');
 await page.locator('#submitForm').click();

 await page.locator('#phone').fill('+998901234567');
 await page.locator('#submitForm').click();
 await page.locator('#person').fill('Offline Ali');
 await page.locator('#shop').fill('Offline Shop');
 await page.locator('#region').fill('Bag‘dod');
 await page.locator('#submitForm').click();
 await page.locator('[data-client-product-mode="none"]').click();
 await page.locator('#submitForm').click();
 assert.match(await page.locator('#review').textContent(),/Offline Shop/);

 page.on('dialog',d=>d.accept());
 await page.locator('#submitForm').click();
 await page.waitForFunction(async()=>{const s=await window.ASMANOffline.status();return s.pending===1});
 assert.equal(writes.length,0,'offline save must not write to server');
 assert.equal(uploads.length,0,'offline photo must stay local until reconnect');
 assert.match(await page.locator('#offlineText').textContent(),/1 ta amal/);

 const queued=await page.evaluate(async()=>{
   const req=indexedDB.open('asman-agent-offline-v2');
   const db=await new Promise((resolve,reject)=>{req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)});
   return await new Promise((resolve,reject)=>{
     const q=db.transaction('queue','readonly').objectStore('queue').getAll();
     q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error);
   });
 });
 assert.equal(queued.length,1);
 assert.equal(queued[0].action,'client');
 assert.ok(queued[0].photoData&&queued[0].photoData.startsWith('data:image/'));
 assert.ok(Number(queued[0].payload.offlineTs)>0);

 const clientResponse=page.waitForResponse(response=>{
   if(!response.url().includes('/api/'))return false;
   try{return JSON.parse(response.request().postData()||'{}').action==='client'}catch(_e){return false}
 },{timeout:15000});
 await context.setOffline(false);
 await page.waitForFunction(()=>navigator.onLine===true);
 await clientResponse;
 await page.waitForFunction(async()=>{const s=await window.ASMANOffline.status();return s.pending===0&&!s.syncing},{timeout:15000});
 assert.equal(uploads.length,1,'photo uploads once after reconnect');
 const browserFetchCalls=await page.evaluate(()=>window.fetchCalls.slice());
 assert.equal(writes.length,1,'client writes once after reconnect; actions='+JSON.stringify(actions)+' fetchCalls='+JSON.stringify(browserFetchCalls));
 assert.equal(writes[0].photoFileId,'offline-test-photo-id');
 assert.ok(Number(writes[0].offlineTs)>0);
 assert.ok(writes[0].nonce,'idempotency nonce must survive offline queue');

 console.log('offline queue + photo + reconnect sync passed');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
