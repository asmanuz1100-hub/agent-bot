const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
const clients=[
 {id:1,name:'Alpha',agentId:2,agent:'Ali',region:'East',age:'fresh',status:'active',debtUsd:100,lastTs:100,lat:40.5,lon:71},
 {id:2,name:'Beta',agentId:3,agent:'Vali',region:'West',age:'yellow',status:'waiting',debtUsd:0,lastTs:200,lat:40.6,lon:71},
 {id:3,name:'Gamma',agentId:2,agent:'Ali',region:'East',age:'red',status:'interested',debtUsd:200,lastTs:300,lat:40.7,lon:71},
 {id:4,name:'Delta',agentId:2,agent:'Ali',region:'West',age:'scheduled',status:'declined',debtUsd:50,lastTs:400,lat:null,lon:null},
 {id:5,name:'Blocked',agentId:3,agent:'Vali',region:'West',age:'fresh',status:'active',debtUsd:25,lastTs:500,lat:40.8,lon:71,blacklisted:true},
 {id:6,name:'Unknown',agentId:3,agent:'Vali',region:'West',age:'unknown',status:'active',debtUsd:0,lastTs:600,lat:40.9,lon:71}
];
(async()=>{const browser=await chromium.launch({headless:true});try{
for(const theme of ['light','dark']){
 const page=await browser.newPage({viewport:{width:390,height:844},colorScheme:theme}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(theme=>{localStorage.setItem('pmTheme',theme);window.Telegram={WebApp:{initData:'test-only',initDataUnsafe:{user:{id:1}},HapticFeedback:{impactOccurred(){},selectionChanged(){}},ready(){},expand(){},onEvent(){},setHeaderColor(){},setBackgroundColor(){},BackButton:{show(){},hide(){},onClick(){}}}}},theme);
 await page.route('**/*',route=>{const u=new URL(route.request().url());
  if(u.pathname==='/api/manager')return route.fulfill({json:{readOnly:true,clients,agents:[],transactions:[],summary:{},cash:{},reports:{today:{},week:{}},todayStart:0}});
  let file=u.pathname==='/app/rahbar-premium/'?'miniapps/rahbar-premium/index.html':u.pathname.startsWith('/app/')?'miniapps/'+u.pathname.slice(5):null;
  if(u.pathname.endsWith('leaflet.min.js'))file='miniapps/agent/vendor/leaflet/leaflet.js';
  if(u.pathname.endsWith('leaflet.min.css'))file='miniapps/agent/vendor/leaflet/leaflet.css';
  if(file&&fs.existsSync(path.join(root,file)))return route.fulfill({path:path.join(root,file)});
  return route.fulfill({status:200,body:''});
 });
 await page.goto('https://asman.test/app/rahbar-premium/');
 await page.waitForFunction(()=>window.PremiumReal&&PremiumReal.clients().length===6);
 await page.evaluate(()=>go(2));
 async function check(names){
  await page.waitForFunction(n=>document.querySelectorAll('#cllist .row').length===n,names.length);
  assert.deepEqual((await page.locator('#cllist .row .t > b').allTextContents()).sort(),[...names].sort());
  const gps=clients.filter(c=>names.includes(c.name)&&c.lat!=null).length;
  await page.waitForFunction(n=>document.querySelectorAll('#clientmap .leaflet-marker-icon').length===n,gps);
  assert.equal(await page.locator('#clientmap-count').innerText(),`${gps} / ${names.length} ta GPS nuqta`);
  assert.equal(await page.locator('#clResultCount').innerText(),`${names.length} mijoz`);
  const sum=clients.filter(c=>names.includes(c.name)).reduce((s,c)=>s+c.debtUsd,0);
  await page.waitForFunction(s=>document.querySelector('#clsum').innerText.includes(s),sum.toFixed(2)+' $');
 }
 const chip=label=>page.locator('#clch button').filter({hasText:label}).click();
 await check(clients.map(c=>c.name));
 for(const [label,names] of [['Qarzdorlar',['Alpha','Gamma','Delta']],['0–2 kun',['Alpha']],['3–4 kun',['Beta']],['5+ kun',['Gamma']],['Rejada',['Delta']],['Noma’lum',['Unknown']],['Qora ro‘yxat',['Blocked']]]){await chip(label);await check(names)}
 await page.locator('#clReset').click();await check(clients.map(c=>c.name));
 await page.locator('#clAdvancedAgent').selectOption('2');await check(['Alpha','Gamma','Delta']);assert.equal(await page.locator('#clAg').inputValue(),'2');
 await page.locator('#clReg').selectOption('East');await check(['Alpha','Gamma']);
 await page.locator('#clDebt').selectOption('debt');await page.locator('#clStatus').selectOption('active');await check(['Alpha']);
 await page.locator('#qi').fill('missing');await check([]);
 await page.locator('#qi').fill('Alpha');await check(['Alpha']);
 await page.locator('#clDebt').selectOption('clear');await check([]);
 await page.locator('#clReset').click();await check(clients.map(c=>c.name));
 await page.locator('#clAg').selectOption('3');assert.equal(await page.locator('#clAdvancedAgent').inputValue(),'3');await check(['Beta','Blocked','Unknown']);
 await page.locator('#clDebt').selectOption('clear');await check(['Beta','Unknown']);
 await page.locator('#clReset').click();await page.locator('#sortf').click();assert.equal((await page.locator('#cllist .row .t > b').allTextContents())[0],'Gamma');
 await page.locator('#clReset').click();assert.equal((await page.locator('#cllist .row .t > b').allTextContents())[0],'Unknown');
 await page.evaluate(()=>goCl(3));await check(['Gamma']);
 await page.locator('#clReset').click();await chip('0–2 kun');await page.evaluate(()=>PremiumReal.reload(true));await check(['Alpha']);
 await page.locator('#clReset').click();await page.locator('#clStatus').selectOption('waiting');await check(['Beta']);
 await page.locator('#clReset').click();await chip('Qarzdorlar');
 fs.mkdirSync(path.join(root,'test-results/manager-filters'),{recursive:true});
 await page.screenshot({path:path.join(root,'test-results/manager-filters',theme+'.png'),fullPage:true});
 assert.deepEqual(errors,[]);await page.close();console.log(theme+' filters, GPS pins, empty-state recovery, totals, reset, sorting and reload OK');
}
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
