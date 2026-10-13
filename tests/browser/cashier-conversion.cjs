const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
const out=path.join(root,'test-results','cashier-conversion');
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const width of [390,1440])for(const colorScheme of ['light','dark']){
   const page=await browser.newPage({viewport:{width,height:844},colorScheme,reducedMotion:'reduce'});
   const errors=[],seen=new Set();
   const state={name:'E2E TEST',rate:12500,balance:10000,categories:['💰 Дивиденд'],
    pending:[],history:[],expenses:[],agents:[],daily:'',conversions:[],
    summary:{wallets:{cashUsd:10000,cashUzs:0,cardUsd:5000,cardUzs:0},grandTotalUsd:15000}};
   page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(scheme=>{localStorage.setItem('pmTheme',scheme);window.Telegram={WebApp:{colorScheme:scheme,initData:'test-only',ready(){},expand(){},
    onEvent(){},setHeaderColor(){},setBackgroundColor(){},initDataUnsafe:{user:{id:3,first_name:'Test'}}}}},colorScheme);
   await page.route('**/*',async route=>{
    const u=new URL(route.request().url());
    if(u.pathname==='/api/cashier'){
     const p=route.request().postDataJSON();
     if(p.action==='convert'){
      if(seen.has(p.requestId))return route.fulfill({json:{ok:true,duplicate:true}});
      const prefix=p.payFrom==='cash'?'cash':'card',usd=p.fromCurrency==='USD';
      const amount=usd?Math.round(Number(p.amount)*100):Number(p.amount),rate=Number(p.rate);
      const target=usd?Math.round(amount*rate/100):Math.round(amount*100/rate);
      const from=prefix+(usd?'Usd':'Uzs'),to=prefix+(usd?'Uzs':'Usd');
      if(amount>state.summary.wallets[from])return route.fulfill({status:400,json:{error:'Танланган манба ва валютада пул етарли эмас.'}});
      seen.add(p.requestId);state.summary.wallets[from]-=amount;state.summary.wallets[to]+=target;
      state.conversions.unshift({id:seen.size,from_currency:p.fromCurrency,amount_from:amount,
       amount_to:target,pay_from:p.payFrom,rate_uzs_per_usd:rate,note:p.note||'',ts:Math.floor(Date.now()/1000)});
      return route.fulfill({json:{ok:true}});
     }
     return route.fulfill({json:state});
    }
    if(u.hostname==='telegram.org')return route.fulfill({body:''});
    if(u.hostname==='app.test'&&u.pathname==='/')return route.fulfill({path:path.join(root,'cashier-miniapp.html')});
    if(u.pathname.startsWith('/app/premium-kit/')){
     const f=path.join(root,'miniapps/premium-kit',path.basename(u.pathname));
     if(fs.existsSync(f))return route.fulfill({path:f});
    }
    return route.abort();
   });
   await page.goto('https://app.test/');
   await page.waitForSelector('#app:not(.hidden)');
   await page.locator('[data-pm-tab="more"]').click();
   await page.locator('[data-pm-more="conversion"]').click();
   await page.waitForSelector('#conversion:not(.hidden)');
   assert.equal(await page.locator('html').getAttribute('data-pmt'),colorScheme);
   await page.locator('#conversionAmount').fill('1.234');
   await page.locator('#conversionForm button').click();
   assert.equal(await page.locator('#review[open]').count(),0);
   await page.locator('#conversionAmount').fill('25');
   await page.locator('#conversionRate').fill('12500');
   assert.ok((await page.locator('#conversionPreview').innerText()).includes('312,500'));
   await page.screenshot({path:path.join(out,width+'-'+colorScheme+'.png'),fullPage:true});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1));
   async function submit(currency,amount,source){
    await page.waitForFunction(()=>!document.querySelector('#confirm').disabled);
    await page.locator('#conversionSource').selectOption(source);
    await page.locator('#conversionCurrency').selectOption(currency);
    await page.locator('#conversionAmount').fill(amount);
    await page.locator('#conversionForm button').click();
    await page.waitForSelector('#review[open]');
    await page.evaluate(()=>{document.querySelector('#confirm').click();document.querySelector('#confirm').click()});
   }
   await submit('USD','200','cash');
   await page.waitForFunction(()=>document.querySelector('#reviewNotice').textContent.includes('yetarli emas'));
   assert.equal(seen.size,0);
   await page.locator('#cancel').click();
   await submit('USD','25','cash');
   await page.waitForSelector('#review:not([open])',{state:'attached'});
   assert.equal(seen.size,1);
   await submit('UZS','312500','cash');
   await page.waitForSelector('#review:not([open])',{state:'attached'});
   await submit('USD','10','card');
   await page.waitForSelector('#review:not([open])',{state:'attached'});
   await page.waitForFunction(()=>document.querySelector('#conversionHistory').textContent.includes('125,000'));
   assert.deepEqual(state.summary.wallets,{cashUsd:10000,cashUzs:0,cardUsd:4000,cardUzs:125000});
   assert.equal(seen.size,3);
   assert.deepEqual(errors,[]);
   await page.close();
  }
  console.log('Conversion UI passed: mobile/desktop, light/dark, both currencies/sources, insufficient funds, double-click');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
