// Rahbar Web: login, every page, keyboard navigation, axe (WCAG 2 A/AA), horizontal overflow, console errors.
// Real backend: tests/browser/rahbar-web-server.py (temporary SQLite, fake data). Map tiles and Google Fonts are stubbed.
// Run: NODE_PATH=<dir with playwright, axe-core> node tests/browser/rahbar-web.cjs
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'test-results/rahbar-web');
const AXE=fs.readFileSync(require.resolve('axe-core/axe.min.js'),'utf8');
const PNG=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=','base64');
const PAGES=['home','agents','team','clients','cash','reports','insights','warehouse','staff','settings'];
const WIDTHS=[1440,1024,768,390];

function startServer(){
  return new Promise((resolve,reject)=>{
    const p=spawn('python3',[path.join(__dirname,'rahbar-web-server.py')],{cwd:root});
    let buf='';p.stdout.on('data',d=>{buf+=d;const line=buf.split('\n')[0];if(buf.includes('\n')){try{resolve({proc:p,...JSON.parse(line)})}catch(e){reject(e)}}});
    p.stderr.on('data',d=>{if(process.env.DEBUG)process.stderr.write(d)});
    p.on('exit',c=>reject(new Error('server exited '+c)));
  });
}
async function axe(page){
  await page.evaluate(src=>{if(!window.axe){const s=document.createElement('script');s.textContent=src;document.head.appendChild(s)}},AXE);
  return page.evaluate(async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa']},resultTypes:['violations']});
    return r.violations.map(v=>({id:v.id,impact:v.impact,help:v.help,count:v.nodes.length,targets:v.nodes.slice(0,3).map(n=>n.target.join(' '))}))});
}

(async()=>{
  const srv=await startServer();const failures=[];const report={};
  const browser=await chromium.launch({headless:true});
  fs.mkdirSync(out,{recursive:true});
  try{
    for(const theme of ['light','dark']){
      const ctx=await browser.newContext({viewport:{width:1440,height:900},colorScheme:theme});
      const page=await ctx.newPage(),errors=[];
      page.on('pageerror',e=>errors.push('pageerror: '+e.message));
      page.on('console',m=>{if(m.type()==='error'&&!/Failed to load resource/.test(m.text()))errors.push('console: '+m.text())});
      await page.route(/fonts\.(googleapis|gstatic)\.com/,r=>r.fulfill({status:200,contentType:'text/css',body:''}));
      await page.route(/\/tiles\//,r=>r.fulfill({status:200,contentType:'image/png',body:PNG}));
      await page.addInitScript(t=>{try{localStorage.setItem('rw-theme',t)}catch(e){}},theme);
      await page.goto(srv.url);
      // 1) Login: noto'g'ri parol xato ko'rsatadi, to'g'risi kiritadi
      await page.fill('#lgLogin',srv.login);await page.fill('#lgPass','wrong-password');await page.press('#lgPass','Enter');
      await page.waitForFunction(()=>document.getElementById('lgErr').textContent.trim().length>0);
      await page.fill('#lgPass',srv.password);await page.press('#lgPass','Enter');
      await page.waitForSelector('#exBody .kpi',{timeout:20000});
      // 2) Klaviatura: Tab fokus ko'rinadi, Ctrl+K qidiruv → Enter karta, Escape yopadi, KPI Enter bilan ochiladi
      await page.focus('#nav button');
      const ring=await page.evaluate(()=>{const s=getComputedStyle(document.activeElement);return s.outlineStyle!=='none'&&parseFloat(s.outlineWidth)>0});
      await page.keyboard.press('Tab');
      const focusVisible=await page.evaluate(()=>document.activeElement.matches(':focus-visible'));
      if(!focusVisible)failures.push(theme+': Tab fokus :focus-visible emas');
      void ring;
      await page.keyboard.press('Control+k');
      assert.equal(await page.evaluate(()=>document.activeElement.id),'gq','Ctrl+K qidiruvga fokus bermadi');
      await page.keyboard.type('Mijoz 1');await page.waitForSelector('#gres .it');
      await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');
      await page.waitForSelector('#drawer.on');await page.waitForSelector('#drawerBody .crm-profile, #drawerBody .dh');
      await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.getElementById('drawer').classList.contains('on'));
      await page.focus('#exBody .kpi[role=button]');await page.keyboard.press('Enter');
      await page.waitForFunction(()=>location.hash==='#reports');
      // 3) Har bir sahifa: axe, xato yo'q, gorizontal toshish yo'q
      report[theme]={};
      for(const p of PAGES){
        await page.evaluate(h=>{location.hash=h},p);await page.waitForTimeout(1800);
        const v=await axe(page);report[theme][p]=v;
        for(const x of v)if(x.impact==='serious'||x.impact==='critical')failures.push(`${theme}/${p}: axe ${x.id} (${x.impact}) ×${x.count} ${x.targets.join(' | ')}`);
        await page.screenshot({path:path.join(out,`${theme}-${p}.png`)});
      }
      // 4) Modal va Kanban klaviatura bilan
      await page.evaluate(()=>{location.hash='warehouse'});await page.waitForSelector('.kcard');
      await page.focus('.kcard');await page.keyboard.press('Enter');await page.waitForSelector('#modalOv:not([hidden]) .omodal');
      await page.keyboard.press('Escape');await page.waitForFunction(()=>document.getElementById('modalOv').hidden);
      // 5) Gorizontal toshish (faqat light — tema bilan bog'liq emas)
      if(theme==='light')for(const w of WIDTHS){
        await page.setViewportSize({width:w,height:w<500?844:900});
        for(const p of PAGES){await page.evaluate(h=>{location.hash=h},p);await page.waitForTimeout(900);
          const over=await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth);if(over>1)failures.push(`${w}px/${p}: ${over}px gorizontal toshish`)}
        await page.screenshot({path:path.join(out,`${theme}-home-${w}.png`)});
        await page.setViewportSize({width:1440,height:900});
      }
      if(errors.length)failures.push(...errors.map(e=>theme+': '+e));
      await ctx.close();
      console.log(theme+': login, keyboard (Tab, Ctrl+K, Enter, Escape), '+PAGES.length+' pages axe, kanban modal'+(theme==='light'?', overflow '+WIDTHS.join('/'):'')+' checked');
    }
  }finally{await browser.close();srv.proc.kill();fs.writeFileSync(path.join(out,'axe.json'),JSON.stringify(report,null,1))}
  const minor=Object.entries(report).flatMap(([t,ps])=>Object.entries(ps).flatMap(([p,v])=>v.filter(x=>x.impact!=='serious'&&x.impact!=='critical').map(x=>`${t}/${p}: ${x.id} (${x.impact})`)));
  if(minor.length)console.log('axe minor/moderate:\n  '+minor.join('\n  '));
  if(failures.length){console.error('FAILURES:\n  '+failures.join('\n  '));process.exit(1)}
  console.log('Rahbar Web QA passed');
})().catch(e=>{console.error(e);process.exit(1)});
