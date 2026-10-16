const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
const out=path.join(root,'test-results','agent-payment-flow');fs.mkdirSync(out,{recursive:true});
const fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'agent-flow-fixture.json')));
(async()=>{const browser=await chromium.launch({headless:true});try{
for(const theme of ['light','dark']){
const page=await browser.newPage({viewport:{width:390,height:844},colorScheme:theme});
const errors=[],payments=[],sent=[];const state=structuredClone(fixture);
page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
await page.addInitScript(theme=>{localStorage.setItem('pmTheme',theme);window.Telegram={WebApp:{initData:'test-only',initDataUnsafe:{user:{id:2}},colorScheme:theme,ready(){},expand(){},onEvent(){},setHeaderColor(){},setBackgroundColor(){},BackButton:{show(){},hide(){},onClick(){}}}}},theme);
await page.route('**/*',async route=>{const u=new URL(route.request().url());
if(u.pathname==='/api/agent'){
const p=route.request().postDataJSON();if(p.action==='payment'){payments.push(p);return route.fulfill({json:{ok:true,message:'Saqlandi'}})}
if(p.action==='card_handover'){sent.push(p);state.snapshot.summary.cardPending[0].heldByAgent=false;return route.fulfill({json:{ok:true,message:'Yuborildi'}})}
return route.fulfill({json:p.action==='client_detail'?state.detail:state.snapshot});}
if(u.pathname==='/api/cashier'){const p=route.request().postDataJSON();return route.fulfill({json:p.action==='handover_detail'?state.handover:state.cashier})}
let file=u.pathname==='/cashier/'?'cashier-miniapp.html':u.pathname==='/app/agent/'?'miniapps/agent/index.html':u.pathname.startsWith('/app/')?'miniapps/'+u.pathname.slice(5):null;
if(file&&fs.existsSync(path.join(root,file)))return route.fulfill({path:path.join(root,file)});
return route.fulfill({status:200,body:''});});
await page.goto('https://asman.test/app/agent/');
await page.locator('#myOrders .card').first().waitFor();assert.match(await page.locator('#myOrders').innerText(),/Buyurtmalarim/);
await page.locator('[data-page="clients"]:visible').first().click();
await page.locator('[data-client="1"]:visible').first().click();
await page.locator('[data-action="payment"]:visible').first().click();
await page.locator('#paymentAmount').fill('120000');await page.locator('#paymentUsd').fill('10');
await page.locator('#addPayment').click();await page.locator('[data-extra-amount]').fill('50');
await page.locator('#submitForm').click();assert.match(await page.locator('#review').innerText(),/120000 UZS.*50 USD/);
await page.screenshot({path:path.join(out,theme+'-mixed.png')});
await page.locator('#submitForm').click();await page.waitForFunction(()=>document.querySelector('#page-form:not(.active)'));
assert.equal(payments.length,1);assert.deepEqual(payments[0].parts.map(p=>[p.currency,p.amount]),[['UZS','120000'],['USD','50']]);
await page.locator('[data-page="cash"]:visible').first().click();await page.locator('[data-card-handover]').waitFor();
await page.locator('[data-card-handover]').click();await page.waitForFunction(()=>!document.querySelector('[data-card-handover]'));
assert.equal(sent.length,1);
await page.goto('https://asman.test/cashier/');await page.locator('[data-history]').waitFor({state:'attached'});
// Open the existing More sheet and history tab, exactly as a cashier does.
await page.locator('[data-pm-tab="more"]').click();await page.locator('[data-pm-more="history"]').click();
await page.locator('[data-history]').first().click();await page.locator('dialog[open]').waitFor();
assert.match(await page.locator('#reviewText').innerText(),/25.00/);assert.equal(await page.locator('#confirm').isVisible(),false);
await page.screenshot({path:path.join(out,theme+'-history.png')});
assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
await page.close();console.log(theme+' agent mixed payment, card custody, orders and cashier history OK');
}
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
