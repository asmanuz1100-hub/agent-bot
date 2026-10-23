// Admin web end-to-end: savdo buyurtmasi (band → qisman yetkazish → aralash to'lov), kassada mijozdan to'lov va
// bekor qilish, ishdan ketgan ishchiga yakuniy oylik. Real backend: rahbar-web-server.py RW_E2E=1 (vaqtinchalik SQLite).
// Run: NODE_PATH=<dir with playwright> node tests/browser/admin-e2e.cjs
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');

function startServer(){
  return new Promise((resolve,reject)=>{
    const p=spawn('python3',[path.join(__dirname,'rahbar-web-server.py')],{cwd:root,env:{...process.env,RW_E2E:'1'}});
    let buf='';p.stdout.on('data',d=>{buf+=d;if(buf.includes('\n')){try{resolve({proc:p,...JSON.parse(buf.split('\n')[0])})}catch(e){reject(e)}}});
    p.stderr.on('data',d=>{if(process.env.DEBUG)process.stderr.write(d)});
    p.on('exit',c=>reject(new Error('server exited '+c)));
  });
}
const step=(n)=>console.log('✓',n);

(async()=>{
  const srv=await startServer();
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM||undefined});
  const errors=[];
  try{
    const page=await (await browser.newContext({viewport:{width:1440,height:900}})).newPage();
    page.on('pageerror',e=>errors.push(e.message));
    await page.route(/fonts\.(googleapis|gstatic)\.com|\/tiles\//,r=>r.fulfill({status:200,body:''}));
    let token='';page.on('request',r=>{const h=r.headers().authorization;if(h&&r.url().includes('/api/manager'))token=h});
    const api=async(action,args)=>{const r=await page.request.post(new URL('/api/manager',srv.url).href,{headers:{authorization:token,'content-type':'application/json',origin:new URL(srv.url).origin},data:{action,...args}});
      const d=await r.json();if(!r.ok())throw new Error(action+': '+d.error);return d};
    // OK bosiladi; keyingi oyna (tasdiq) ochilishi yoki oyna yopilishi kutiladi
    const modalOk=async()=>{const h=await page.innerHTML('#modalBody');await page.click('#modalBody .foot .btn.pri, #modalBody .foot .btn.danger');
      await page.waitForFunction(h0=>document.getElementById('modalOv').hidden||document.getElementById('modalBody').innerHTML!==h0,h);await page.waitForTimeout(250)};
    const fill=async(vals)=>{await page.waitForSelector('#modalOv:not([hidden]) form');for(const [k,v] of Object.entries(vals)){const el=page.locator(`#modalBody [name="${k}"]`);if(await el.evaluate(e=>e.tagName)==='SELECT')await el.selectOption(String(v));else await el.fill(String(v))}};
    await page.goto(srv.url);
    await page.fill('#lgLogin',srv.login);await page.fill('#lgPass',srv.password);await page.press('#lgPass','Enter');
    await page.waitForSelector('#exBody .kpi',{timeout:20000});step('login');

    // 1) Savdo: buyurtma — band qilinadi, ombordan chiqmaydi
    await page.evaluate(()=>{location.hash='sales'});await page.waitForSelector('#shTabs');
    await page.click('#shTabs [data-t="pos"]');await page.waitForSelector('#shCq');
    await page.fill('#shCq','Mijoz 2');await page.waitForSelector('#shCres [data-c]');await page.click('#shCres [data-c]');
    await page.click('#shProds [data-add]');await page.fill('#shCart [data-q="0"]','10');await page.dispatchEvent('#shCart [data-q="0"]','change');
    await page.waitForSelector('#shOrder:not([disabled])');await page.click('#shOrder');await modalOk();
    await page.waitForSelector('#drawer.on #soDel');
    const oid=+(await page.textContent('#drawerBody h2')).replace(/\D/g,'');
    let o=(await api('shop',{op:'orders',orderOp:'view',orderId:oid})).order;
    assert.equal(o.delivery,'none');assert.equal(o.total,10000);assert.equal(o.lines[0].available,40);step('buyurtma band qilindi #'+oid);
    // qisman yetkazish 4 dona
    await page.click('#soDel');await fill({['p'+o.lines[0].pack]:4});await modalOk();await modalOk();
    await page.waitForFunction(()=>/Qisman yetkazildi/.test(document.getElementById('drawerBody').textContent));
    // aralash to'lov: $20 + 125 000 so'm ($10)
    await page.click('#soPay');await fill({usd:20,uzs:125000,rate:12500});await modalOk();await modalOk();
    await page.waitForFunction(()=>/Qisman to‘langan/.test(document.getElementById('drawerBody').textContent));
    o=(await api('shop',{op:'orders',orderOp:'view',orderId:oid})).order;
    assert.deepEqual([o.delivered,o.paid,o.due,o.lines[0].delivered],[4000,3000,7000,4]);step('qisman yetkazish va aralash to‘lov');
    await page.keyboard.press('Escape');

    // 2) Kassa: mijozdan to'g'ridan to'lov → qarz kamayadi → bekor qilish qarzni tiklaydi
    await page.evaluate(()=>{location.hash='cash'});await page.waitForSelector('#cbCard [data-cb="client"]',{timeout:20000});
    const before=(await api('cashbook',{op:'view'})).debtors.find(c=>c.id===2);
    await page.click('#cbCard [data-cb="client"]');await fill({clientId:2,pocket:'cash',currency:'USD',amount:5});await modalOk();await modalOk();
    await page.waitForTimeout(500);
    let cb=await api('cashbook',{op:'view'});const after=cb.debtors.find(c=>c.id===2);
    assert.equal(before.debtUsd-after.debtUsd,500);
    const mv=cb.journal.find(x=>x.type==='income'&&x.client===2&&x.status==='active');assert.ok(mv);step('mijozdan to‘lov: qarz −$5');
    await page.click(`#cbCard [data-cbi="${cb.journal.indexOf(mv)}"]`);await page.waitForSelector('#modalBody [name="reason"]');
    await page.fill('#modalBody [name="reason"]','E2E: noto‘g‘ri summa');await page.click('#modalBody .foot .btn.danger');
    await page.waitForTimeout(600);
    cb=await api('cashbook',{op:'view'});
    assert.equal(cb.debtors.find(c=>c.id===2).debtUsd,before.debtUsd);
    assert.equal(cb.journal.find(x=>x.move===mv.move).status,'cancelled');step('bekor qilish qarzni tikladi, yozuv tarixda');

    // 3) Ishdan ketgan ishchiga yakuniy oylik — qayta ishga olmasdan
    const ov=await api('hr',{op:'overview',closed:true});const w=ov.workers.find(x=>x.name==='Ketgan Usta');
    await page.evaluate(()=>{location.hash='staff'});await page.waitForSelector('#stView [data-v="workers"]');
    await page.click('#stView [data-v="workers"]');await page.waitForSelector('#wkOff');await page.check('#wkOff');
    await page.click(`[data-w="${w.id}"]`);await page.waitForSelector('#empTabs');
    await page.click('#empTabs [data-t="pay"]');await page.waitForSelector('#drawerBody [data-pk="salary"]');
    assert.equal(await page.locator('#drawerBody [data-pk="advance"]').count(),0);
    await page.click('#drawerBody [data-pk="salary"]');await fill({amount:4000000});await modalOk();
    if(await page.locator('#modalOv:not([hidden]) form').count())await modalOk();
    await page.waitForTimeout(700);
    const wk=(await api('hr',{op:'worker',id:w.id})).worker;
    assert.equal(wk.payroll.remaining,0);assert.equal(wk.active,false);step('yakuniy oylik to‘landi, ishchi yopiq qoldi');
    // 4) Xodimlar: ruxsatlar, web login, Mini App kirishi shu yerda; Ta'minot — Ombor ichida
    await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.getElementById('drawer').classList.contains('on'));
    await page.evaluate(()=>{location.hash='staff'});await page.click('#stView [data-v="list"]');
    // qatorni bosish — bitta kartochka: kirish, ruxsatlar, akkaunt
    await page.click('tr[data-sid="4"] td:first-child');await page.waitForSelector('#drawerBody [data-scard="4"] [data-ca="app"]');
    await page.click('#drawerBody [data-ca="app"]');await modalOk();
    await page.waitForFunction(()=>/O‘chiq/.test(document.querySelector('#drawerBody [data-scard="4"]')?.textContent||''));
    assert.equal((await api('staff_list',{})).staff.find(x=>x.id===4).miniapp,false);
    await page.click('#drawerBody [data-ca="app"]');await modalOk();
    await page.waitForFunction(()=>/Yoqiq/.test(document.querySelector('#drawerBody [data-scard="4"]')?.textContent||''));
    await page.click('#drawerBody [data-perm="warehouse.view"]');await page.click('#drawerBody [data-ca="psave"]');
    await page.waitForFunction(()=>document.querySelector('#drawerBody [data-perm="warehouse.view"]')?.checked===true&&/individual/.test(document.getElementById('drawerBody').textContent));
    assert.ok((await api('perms_staff',{id:4})).staff.perms.find(q=>q.key==='warehouse.view').on);
    assert.ok(await page.locator('#drawerBody [data-ca="transfer"]').count());
    await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.getElementById('drawer').classList.contains('on'));
    await page.click('tr[data-sid="5"] td:first-child');await page.waitForSelector('#drawerBody [data-scard="5"] [data-ca="login"]');
    await page.keyboard.press('Escape');
    step('xodimlar: ruxsat, Mini App, web login');
    await page.evaluate(()=>{location.hash='warehouse'});await page.waitForSelector('#whView [data-v="supply"]');
    await page.click('#whView [data-v="supply"]');await page.waitForSelector('#spView [data-v="wh"]');
    assert.equal(await page.evaluate(()=>location.hash),'#supply');
    assert.equal(await page.locator('#nav button.on, #nav [aria-current="page"]').first().textContent().then(t=>/Ombor/.test(t)),true);
    step('ta’minot ombor ichida');
    assert.deepEqual(errors,[]);
    console.log('admin-e2e: OK');
  }catch(e){try{const pg=browser.contexts()[0].pages()[0];console.error('toast:',await pg.evaluate(()=>[...document.querySelectorAll('.toast,#toasts *')].map(t=>t.textContent).join(' | ')));
    console.error('modal:',await pg.evaluate(()=>document.getElementById('modalOv').hidden?'':document.getElementById('modalBody').textContent.slice(0,300)))}catch(_){}throw e}
  finally{await browser.close();srv.proc.kill()}
})().catch(e=>{console.error(e);process.exit(1)});
