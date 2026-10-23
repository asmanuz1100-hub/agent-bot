/* Boshqaruv paneli (web). Telegram'siz: login + parol, so'ng /api/manager bilan bir xil amallar. */
(function(){'use strict';
var API='/api/manager',AUTH='/api/web';
var TOKEN=store('rw-token')||'';
var S={dash:null,me:null,primary:false,page:'',loadedTs:0,maps:{},timer:0,cache:{},modules:null};
/* Sahifa -> korxona bo'limi (server modules.py). Ro'yxatda yo'q sahifa doim ochiq. */
var PAGE_MODULE={sales:'sales',cash:'cash',warehouse:'warehouse',supply:'warehouse',team:'agents',agents:'agents',reports:'reports',insights:'reports'};
function modOn(k){return !k||!S.modules||S.modules[k]!==false}
function pageOn(p){return modOn(PAGE_MODULE[p])}
var $=function(id){return document.getElementById(id)};

/* ---------- helpers ---------- */
function store(k,v){try{if(v===undefined)return localStorage.getItem(k);if(v===null)localStorage.removeItem(k);else localStorage.setItem(k,v)}catch(e){return null}}
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
/* Ikonlar: Lucide (ISC litsenziya, lucide-static 0.460.0) — yagona 24×24 setka, 1.75 chiziq. */
var ICONS={
 home:'<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
 compass:'<polygon points="3 11 22 2 13 21 11 13 3 11"/>',
 store:'<path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7"/><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><path d="M15 22v-4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4"/><path d="M2 7h20"/><path d="M22 7v3a2 2 0 0 1-2 2a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 16 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 12 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 8 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 4 12a2 2 0 0 1-2-2V7"/>',
 wallet:'<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
 chart:'<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
 report:'<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M8 18v-1"/><path d="M12 18v-6"/><path d="M16 18v-3"/>',
 analytics:'<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M7 16c.5-2 1.5-7 4-7 2 0 2 3 4 3 2.5 0 4.5-5 5-7"/>',
 target:'<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
 box:'<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M12 22V12"/><path d="m3.3 7 7.703 4.734a2 2 0 0 0 1.994 0L20.7 7"/><path d="m7.5 4.27 9 5.15"/>',
 users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
 settings:'<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
 refresh:'<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
 moon:'<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
 sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
 search:'<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
 x:'<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
 download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
 alert:'<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
 clock:'<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
 plus:'<path d="M5 12h14"/><path d="M12 5v14"/>',
 userplus:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" x2="19" y1="8" y2="14"/><line x1="22" x2="16" y1="11" y2="11"/>',
 pin:'<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
 phone:'<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
 edit:'<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
 trash:'<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
 ban:'<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
 check:'<path d="M20 6 9 17l-5-5"/>',
 checkc:'<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
 swap:'<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="m16 21 4-4-4-4"/><path d="M20 17H4"/>',
 coins:'<circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/>',
 'in':'<path d="M17 7 7 17"/><path d="M17 17H7V7"/>',
 out:'<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
 truck:'<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/>',
 cart:'<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
 walk:'<path d="M4 16v-2.38C4 11.5 2.97 10.5 3 8c.03-2.72 1.49-6 4.5-6C9.37 2 10 3.8 10 5.5c0 3.11-2 5.66-2 8.68V16a2 2 0 1 1-4 0Z"/><path d="M20 20v-2.38c0-2.12 1.03-3.12 1-5.62-.03-2.72-1.49-6-4.5-6C14.63 6 14 7.8 14 9.5c0 3.11 2 5.66 2 8.68V20a2 2 0 1 0 4 0Z"/><path d="M16 17h4"/><path d="M4 13h4"/>',
 route:'<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/>',
 bell:'<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
 receipt:'<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 17.5v-11"/>',
 card:'<rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/>',
 cash:'<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
 dollar:'<circle cx="12" cy="12" r="10"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 18V6"/>',
 bank:'<line x1="3" x2="21" y1="22" y2="22"/><line x1="6" x2="6" y1="18" y2="11"/><line x1="10" x2="10" y1="18" y2="11"/><line x1="14" x2="14" y1="18" y2="11"/><line x1="18" x2="18" y1="18" y2="11"/><polygon points="12 2 20 7 4 7"/>',
 calendar:'<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
 hourglass:'<path d="M5 22h14"/><path d="M5 2h14"/><path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22"/><path d="M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2"/>',
 timer:'<line x1="10" x2="14" y1="2" y2="2"/><line x1="12" x2="15" y1="14" y2="11"/><circle cx="12" cy="14" r="8"/>',
 warehouse:'<path d="M22 8.35V20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8.35A2 2 0 0 1 3.26 6.5l8-3.2a2 2 0 0 1 1.48 0l8 3.2A2 2 0 0 1 22 8.35Z"/><path d="M6 18h12"/><path d="M6 14h12"/><rect width="12" height="12" x="6" y="10"/>',
 sparkle:'<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/>',
 help:'<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
 list:'<path d="M3 12h.01"/><path d="M3 18h.01"/><path d="M3 6h.01"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M8 6h13"/>',
 map:'<path d="M14.106 5.553a2 2 0 0 0 1.788 0l3.659-1.83A1 1 0 0 1 21 4.619v12.764a1 1 0 0 1-.553.894l-4.553 2.277a2 2 0 0 1-1.788 0l-4.212-2.106a2 2 0 0 0-1.788 0l-3.659 1.83A1 1 0 0 1 3 19.381V6.618a1 1 0 0 1 .553-.894l4.553-2.277a2 2 0 0 1 1.788 0z"/><path d="M15 5.764v15"/><path d="M9 3.236v15"/>',
 file:'<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
 logout:'<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
 trend:'<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
 stop:'<rect width="18" height="18" x="3" y="3" rx="2"/>',
 note:'<path d="M13.4 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7.4"/><path d="M2 6h4"/><path d="M2 10h4"/><path d="M2 14h4"/><path d="M2 18h4"/><path d="M21.378 5.626a1 1 0 1 0-3.004-3.004l-5.01 5.012a2 2 0 0 0-.506.854l-.837 2.87a.5.5 0 0 0 .62.62l2.87-.837a2 2 0 0 0 .854-.506z"/>',
 menu:'<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>',
 panel:'<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/>',
 building:'<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/>',
 image:'<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
 upload:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
 info:'<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
 xcircle:'<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
 chevron:'<path d="m9 18 6-6-6-6"/>',
 orders:'<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/>',
 staff:'<path d="M16 10h2"/><path d="M16 14h2"/><path d="M6.17 15a3 3 0 0 1 5.66 0"/><circle cx="9" cy="11" r="2"/><rect x="2" y="5" width="20" height="14" rx="2"/>',
 grid:'<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>',
 palette:'<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>',
 shield:'<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
 user:'<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>',
 sliders:'<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/><line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/><line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/><line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="16" x2="16" y1="18" y2="22"/>',
 mic:'<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/>',
 volume:'<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.364 18.364a9 9 0 0 0 0-12.728"/>',
 send:'<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
 fuel:'<line x1="3" x2="15" y1="22" y2="22"/><line x1="4" x2="14" y1="9" y2="9"/><path d="M14 22V4a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v18"/><path d="M14 13h2a2 2 0 0 1 2 2v2a2 2 0 0 0 2 2a2 2 0 0 0 2-2V9.83a2 2 0 0 0-.59-1.42L18 5"/>',
 food:'<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/><path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>',
 briefcase:'<path d="M12 12h.01"/><path d="M16 6V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/><path d="M22 13a18.15 18.15 0 0 1-20 0"/><rect width="20" height="14" x="2" y="6" rx="2"/>',
 worker:'<path d="M10 10V5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v5"/><path d="M14 6a6 6 0 0 1 6 6v3"/><path d="M4 15v-3a6 6 0 0 1 6-6"/><rect x="2" y="15" width="20" height="4" rx="1"/>'
};
function ic(name,cls){var p=ICONS[name];return p?'<svg class="ico '+(cls||'')+'" viewBox="0 0 24 24" aria-hidden="true">'+p+'</svg>':''}
/* Eski emoji belgilar → ikon va rang (KPI kartalar uchun). */
var EMO={'🧭':['compass','blue'],'📦':['box','blue'],'💰':['coins','green'],'👣':['walk','violet'],'🏦':['bank','cyan'],'➕':['userplus','green'],
 '🧾':['receipt','red'],'🛒':['cart','amber'],'🚚':['truck','cyan'],'📅':['calendar','violet'],'💵':['cash','green'],'💳':['card','blue'],'💲':['dollar','green'],
 '🏬':['warehouse','violet'],'🏪':['store','blue'],'🆕':['sparkle','blue'],'❓':['help','amber'],'⚠️':['alert','red'],'⏳':['hourglass','amber'],'⏱':['timer','cyan']};
function tone(icon,color,size){return '<div class="tone t-'+(color||'blue')+'">'+ic(icon,size||'lg')+'</div>'}
function num(n,d){n=Number(n||0);return n.toLocaleString('en-US',{minimumFractionDigits:d||0,maximumFractionDigits:d==null?2:d}).replace(/,/g,' ')}
function usd(n){n=Number(n||0);return (n<0?'−':'')+'$'+num(Math.abs(n),Math.abs(n)%1?2:0)}
function uzs(n){return num(n,0)+' so‘m'}
var TZ='Asia/Tashkent';
function dfmt(ts,opt){if(!ts)return '—';return new Date(ts*1000).toLocaleString('ru-RU',Object.assign({timeZone:TZ},opt))}
function dt(ts){return dfmt(ts,{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'})}
function dday(ts){return dfmt(ts,{day:'2-digit',month:'2-digit',year:'numeric'})}
function hm(ts){return dfmt(ts,{hour:'2-digit',minute:'2-digit'})}
function ago(ts){if(!ts)return '—';var s=Math.max(0,Date.now()/1000-ts);if(s<60)return 'hozir';if(s<3600)return Math.floor(s/60)+' daq oldin';if(s<86400)return Math.floor(s/3600)+' soat oldin';return Math.floor(s/86400)+' kun oldin'}
function hours(sec){var h=Math.floor((sec||0)/3600),m=Math.round(((sec||0)%3600)/60);return h?h+' soat '+m+' daq':m+' daq'}
function initial(name){return esc(String(name||'?').trim().charAt(0).toUpperCase()||'?')}
function avatar(name,url,cls){return '<span class="av '+(cls||'')+'"'+(url?' style="background-image:url(\''+esc(url)+'\')"':'')+'>'+(url?'':initial(name))+'</span>'}
function pill(text,cls){return '<span class="pill '+(cls||'')+'">'+text+'</span>'}
function today(){return new Date(Date.now()+5*3600e3).toISOString().slice(0,10)}
function toast(msg,err){var t=$('toast');t.innerHTML=ic(err?'xcircle':/…$/.test(msg)?'clock':'checkc')+'<span>'+esc(msg)+'</span>';t.className='toast on'+(err?' err':'');clearTimeout(toast.t);toast.t=setTimeout(function(){t.className='toast'+(err?' err':'')},err?4200:2600)}
function debounce(fn,ms){var t;return function(){var a=arguments,self=this;clearTimeout(t);t=setTimeout(function(){fn.apply(self,a)},ms)}}

/* Grafik ranglari CSS tokenlaridan olinadi (yorug'/to'q mavzuga mos). Ma'no: forest=yashil (to'lov, ijobiy),
   orange=qizil (qarz, xato), yellow=to'q sariq (kutilmoqda), pri=ko'k (asosiy), gray/ink=neytral. */
var C={pri:'#007AFF',forest:'#16A34A',yellow:'#F59E0B',orange:'#E5484D',ink:'#111827',gray:'#94A3B8',violet:'#7C5CFC',cyan:'#0EA5B7'};
var AGE={fresh:['0–2 kun','p-ok',C.forest],yellow:['3–4 kun','p-warn',C.yellow],red:['5+ kun','p-bad',C.orange],scheduled:['Rejada','p-pri',C.pri],unknown:['Noma’lum','',C.gray]};
var AG_ST={active:['Faol','p-ok',C.forest],late:['Kechikkan','p-warn',C.yellow],offline:['Yopiq','',C.gray]};
var KIND={delivery:ic('box','sm')+' Tovar berildi',payment:ic('coins','sm')+' To‘lov',sold:ic('cart','sm')+' Sotildi',return:ic('in','sm')+' Qaytarildi',order:ic('note','sm')+' Buyurtma',visit:ic('walk','sm')+' Tashrif'};
var VISIT={active:'Faol',interested:'Qiziqdi',thinking:'O‘ylab ko‘radi',refused:'Rad etdi',closed:'Yopilgan',no_answer:'Javob yo‘q'};
var FIELD={name:'Mijoz ismi',shop_name:'Do‘kon nomi',phone:'Telefon',address:'Manzil',comment:'Izoh',payment_due:'To‘lov sanasi'};
function syncColors(){
  var cs=getComputedStyle(document.documentElement),g=function(n,d){return (cs.getPropertyValue(n)||'').trim()||d};
  C.pri=g('--c-blue',C.pri);C.forest=g('--c-green',C.forest);C.yellow=g('--c-amber',C.yellow);C.orange=g('--c-red',C.orange);
  C.ink=g('--c-ink',C.ink);C.gray=g('--c-gray',C.gray);C.violet=g('--c-violet',C.violet);C.cyan=g('--c-teal',C.cyan);
  AGE.fresh[2]=C.forest;AGE.yellow[2]=C.yellow;AGE.red[2]=C.orange;AGE.scheduled[2]=C.pri;AGE.unknown[2]=C.gray;
  AG_ST.active[2]=C.forest;AG_ST.late[2]=C.yellow;AG_ST.offline[2]=C.gray;
}
syncColors();

/* ---------- API ---------- */
function relogin(msg){TOKEN='';store('rw-token',null);S.dash=null;showLogin(msg||'Sessiya tugagan. Qayta kiring.')}
async function post(url,body){
  var ctl=new AbortController(),timer=setTimeout(function(){ctl.abort()},60000);
  try{
    var r=await fetch(url,{method:'POST',cache:'no-store',signal:ctl.signal,
      headers:Object.assign({'Content-Type':'application/json'},TOKEN?{'Authorization':'Bearer '+TOKEN}:{}),body:JSON.stringify(body)});
    var d;try{d=await r.json()}catch(e){throw new Error('Server noto‘g‘ri javob qaytardi.')}
    if(r.status===401&&d.relogin){relogin(d.error);throw new Error(d.error)}
    if(!r.ok)throw new Error(d.error||('Xato '+r.status));
    return d;
  }catch(e){
    if(e.name==='AbortError')throw new Error('Server javob bermadi. Qayta urinib ko‘ring.');
    if(e instanceof TypeError)throw new Error('Internet aloqasi yo‘q yoki server ishlamayapti.');
    throw e;
  }finally{clearTimeout(timer)}
}
function api(action,args){return post(API,Object.assign({action:action},args||{})).then(function(d){if(d&&d.modules){var ch=JSON.stringify(d.modules)!==JSON.stringify(S.modules);S.modules=d.modules;if(ch&&!$('shell').hidden){renderNav();if(!pageOn(S.page))location.hash='home'}}return d})}
function auth(action,args){return post(AUTH,Object.assign({action:action},args||{}))}

/* ---------- login ---------- */
function showLogin(msg){
  $('shell').hidden=true;$('login').hidden=false;closeDrawer();closeModal();
  $('lgErr').textContent=msg||'';$('lgPass').value='';setTimeout(function(){($('lgLogin').value?$('lgPass'):$('lgLogin')).focus()},30);
}
$('loginForm').addEventListener('submit',async function(e){
  e.preventDefault();var b=$('lgBtn');b.disabled=true;$('lgErr').textContent='';
  try{
    var d=await auth('login',{login:$('lgLogin').value.trim(),password:$('lgPass').value});
    TOKEN=d.token;store('rw-token',TOKEN);store('rw-login',$('lgLogin').value.trim());await boot();
  }catch(err){$('lgErr').textContent=err.message}
  finally{b.disabled=false}
});

/* Sessiya faqat server aniq «relogin» desa tugaydi (post() → relogin()). Tarmoq/server xatosida token saqlanadi:
   avval sahifa yangilanganda vaqtinchalik xato ham login oynasini ochib yuborardi. */
async function boot(attempt){
  if(!TOKEN){$('lgLogin').value=store('rw-login')||'';showLogin();return}
  var me;
  try{me=await auth('me')}catch(e){
    if(!TOKEN)return;   // relogin() allaqachon login oynasini ko'rsatdi
    if((attempt||0)<2){setTimeout(function(){boot((attempt||0)+1)},800*((attempt||0)+1));return}
    bootError(e.message);return}
  S.me=me.me;S.login=me.login;S.primary=!!me.primaryAdmin;applyBrand(me.brand);
  $('bootErr')&&$('bootErr').remove();
  $('login').hidden=true;$('shell').hidden=false;
  $('meName').textContent=S.me.name||S.login;$('meRole').textContent=roleLabel();
  $('meAv').outerHTML=avatar(S.me.name,S.me.photoUrl).replace('class="av ','id="meAv" class="av ');
  renderNav();route();
  clearInterval(S.timer);S.timer=setInterval(autoRefresh,30000);S.tick=0;
}

function bootError(msg){
  var el=$('bootErr');if(!el){el=document.createElement('div');el.id='bootErr';el.className='login';document.body.appendChild(el)}
  $('login').hidden=true;
  el.innerHTML='<div class="login-card err-state" role="alert">'+tone('alert','red')+'<h1>Server bilan aloqa yo‘q</h1><p class="muted">'+esc(msg)+'</p><p class="hint">Sessiyangiz saqlangan — qayta urinish uchun parol shart emas.</p><button class="btn pri block" id="bootRetry">'+ic('refresh','sm')+' Qayta urinish</button><button class="btn block" id="bootOut">Boshqa akkaunt bilan kirish</button></div>';
  $('bootRetry').onclick=function(){this.disabled=true;boot()};
  $('bootOut').onclick=function(){el.remove();TOKEN='';store('rw-token',null);showLogin()};
}
function roleLabel(){return S.primary?'Asosiy rahbar':'Rahbar'}

/* ---------- brend (Sozlamalar → Kompaniya) ---------- */
var BRAND=(function(){try{return JSON.parse(store('rw-brand')||'{}')||{}}catch(e){return {}}})();
function brandName(){return BRAND.name||'AIBI Dashboard'}
function fileSlug(){var n=String(BRAND.name||'').toLowerCase().replace(/[^a-z0-9Ѐ-ӿ]+/gi,'-').replace(/^-+|-+$/g,'');return n||'hisobot'}
function brandMark(){return BRAND.logo?'<img src="'+esc(BRAND.logo)+'" alt="">':'<img src="/app/premium-kit/aibi/aibi-icon-dark.svg?v=3" alt="AIBI">'}
function applyBrand(b){
  if(b){BRAND={name:b.name||'',logo:b.logo||'',details:b.details||{}};store('rw-brand',JSON.stringify(BRAND))}
  $('brandName').textContent=brandName();$('brandSub').textContent=BRAND.name?'AIBI Dashboard':'Smart Business Platform';
  $('brandMark').innerHTML=brandMark();$('lgMark').innerHTML=brandMark();$('lgBrand').textContent=brandName();
  ['brandMark','lgMark'].forEach(function(id){$(id).classList.toggle('has-logo',!!BRAND.logo)});
}
applyBrand();

/* ---------- navigation ---------- */
var PAGES=[
  ['home','home','Asosiy','Bugungi jonli holat',0,'Dashboard'],
  ['team','users','Agentlar','KPI, pul, topshirish, GPS va marshrutlar'],
  ['agents','compass','Agentlar','Jonli GPS xarita, marshrut va mijozlar',9],
  ['clients','store','Mijozlar','Barcha mijozlar va qarzdorlik'],
  ['warehouse','orders','Buyurtmalar','Kanban, ro‘yxat, katalog va ombor qoldig‘i',0,'Buyurtmalar'],
  ['supply','warehouse','Ta’minot','Ta’minotchilar, xarid, xom ashyo va ishlab chiqarish',0,'Ta’minot'],
  ['sales','cart','Savdo','Sotuvlar, cheklar, top mahsulot va mijozlar',0],
  ['cash','wallet','Moliya va qarzdorlik','Kassa, agentlardagi pul, qarzdorlar, konvertatsiya',1,'Moliya'],
  ['reports','report','Hisobot','Davr bo‘yicha natijalar',1],
  ['insights','analytics','Tahlil','Bugungi reja, mijozlar reytingi va hududlar',1],
  ['staff','staff','Xodimlar','Tizim foydalanuvchilari, sex ishchilari, davomat va oylik',2],
  ['settings','settings','Sozlamalar','Kompaniya, akkaunt va xavfsizlik',2]
];
/* Guruhlar: barcha bo'limlar mavjud rahbar huquqlari doirasida (server /api/manager rolni tekshiradi). */
var NAV_GROUPS=['Ish jarayoni','Moliya va tahlil','Boshqaruv'];
function renderNav(){
  var d=S.dash,badge={};
  if(d){badge.warehouse=d.warehouse&&d.warehouse.newOrders;badge.cash=d.summary&&d.summary.pendingCount}
  $('nav').innerHTML=NAV_GROUPS.map(function(g,gi){return '<div class="nav-grp"><span class="lbl nav-h">'+g+'</span>'+PAGES.filter(function(p){return (p[4]||0)===gi&&pageOn(p[0])}).map(function(p){var lb=p[5]||p[2],cur=navKey()===p[0];
    return '<button data-p="'+p[0]+'" class="'+(cur?'on':'')+'"'+(cur?' aria-current="page"':'')+' data-tip="'+esc(lb)+'">'+ic(p[1])+'<span class="lbl">'+lb+'</span>'+(badge[p[0]]?'<span class="badge" aria-label="'+badge[p[0]]+' ta yangi">'+badge[p[0]]+'</span>':'')+'</button>'}).join('')+'</div>'}).join('')+'<i class="nav-ind" aria-hidden="true"></i>';
  moveInd();
}
function navKey(){return S.page==='agents'?'team':S.page}
/* Agentlar bo'limi ichidagi tablar: ro'yxat/KPI va jonli GPS xarita (avval alohida bo'limlar edi). */
function agTabs(cur){return '<div class="seg ag-tabs" role="tablist" aria-label="Agentlar ko‘rinishi"><button role="tab" data-h="team" class="'+(cur==='team'?'on':'')+'" aria-selected="'+(cur==='team')+'">'+ic('users','sm')+' Ro‘yxat va KPI</button><button role="tab" data-h="agents" class="'+(cur==='agents'?'on':'')+'" aria-selected="'+(cur==='agents')+'">'+ic('map','sm')+' GPS xarita</button></div>'}
function bindAgTabs(page){var t=page.querySelector('.ag-tabs');if(t)t.onclick=function(e){var b=e.target.closest('button');if(b&&b.dataset.h!==S.page)location.hash=b.dataset.h}}
/* Faol bo'lim indikatori: silliq siljiydi (transform). */
function moveInd(){var ind=document.querySelector('.nav-ind'),b=document.querySelector('#nav button.on');if(!ind)return;
  if(!b){ind.style.opacity=0;return}var n=$('nav'),prev=S.indY;
  S.indY=b.offsetTop;ind.style.height=b.offsetHeight+'px';ind.style.opacity=1;
  if(prev==null){ind.style.transition='none';ind.style.transform='translateY('+S.indY+'px)';ind.offsetWidth;ind.style.transition=''}
  else{ind.style.transition='none';ind.style.transform='translateY('+prev+'px)';ind.offsetWidth;ind.style.transition='';ind.style.transform='translateY('+S.indY+'px)'}}
$('nav').addEventListener('click',function(e){var b=e.target.closest('button[data-p]');if(b){location.hash=b.dataset.p;sideOpen(false)}});
$('meBtn').onclick=function(){location.hash='settings'};
/* Sidebar: kompyuterda yig'iladi (faqat ikonlar), planshet/mobilda chapdan chiqadigan panel. */
$('railToggle').innerHTML=ic('panel');$('menuBtn').innerHTML=ic('menu');$('refreshBtn').innerHTML=ic('refresh');
$('railFeed').insertAdjacentHTML('afterbegin',ic('bell'));$('railSearch').innerHTML=ic('search')+'<span class="lbl">Qidirish</span><kbd class="lbl">Ctrl K</kbd>';
function setMini(m){var r=$('rail');r.classList.toggle('mini',m);r.classList.toggle('wide',!m);$('railToggle').setAttribute('aria-expanded',!m);
  setTimeout(function(){moveInd();Object.keys(S.maps).forEach(function(k){try{S.maps[k].invalidateSize()}catch(e){}})},300)}
setMini(store('rw-rail')==='0');
$('railToggle').onclick=function(){var m=!$('rail').classList.contains('mini');setMini(m);store('rw-rail',m?'0':'1')};
function sideOpen(on){document.body.classList.toggle('side-open',on);$('menuBtn').setAttribute('aria-expanded',on)}
$('menuBtn').onclick=function(){sideOpen(!document.body.classList.contains('side-open'))};$('sideOv').onclick=function(){sideOpen(false)};
$('railSearch').onclick=function(){sideOpen(false);$('gq').focus();$('gq').select()};
$('railFeed').onclick=function(){openFeedDrawer()};
function openFeedDrawer(){
  $('railDot').hidden=true;S.feedSeen=(S.feed||[]).length;
  openDrawer('<div class="dh"><div class="tone t-blue">'+ic('bell','lg')+'</div><div><h2>Jonli lenta</h2><div class="muted">Panel ochiq turganda kelgan hodisalar · har 30 soniyada tekshiriladi</div></div></div><div class="card"><div class="list" id="feed"></div></div>');
  renderFeed();
}
window.addEventListener('hashchange',route);
function route(){
  if($('shell').hidden)return;
  var p=(location.hash||'').slice(1)||'home';if(!PAGES.some(function(x){return x[0]===p})||!pageOn(p))p='home';
  S.page=p;var meta=PAGES.find(function(x){return x[0]===p});
  $('pageTitle').textContent=meta[2];$('pageSub').textContent=meta[3];document.title=meta[2]+' · '+brandName();
  closeDrawer();renderNav();destroyMaps();S.routeTs=Date.now();
  var pg=$('page');pg.classList.remove('enter');void pg.offsetWidth;pg.classList.add('enter');var tr=$('pageTitle').parentNode;tr.classList.remove('enter');void tr.offsetWidth;tr.classList.add('enter');
  render();
}
function destroyMaps(){Object.keys(S.maps).forEach(function(k){if(k==='drawer')return;var m=S.maps[k];delete S.maps[k];try{m.stop();m.off();m.remove()}catch(e){}})}
async function render(force){
  var p=S.page,page=$('page');
  var needDash=['home','agents','clients','cash','insights','team','sales'].indexOf(p)>=0;
  if(needDash&&(!S.dash||force)){
    if(!S.dash)page.innerHTML='<div class="grid g4">'+'<div class="skel"></div>'.repeat(4)+'</div>';
    try{await loadDash()}catch(e){if(TOKEN){page.innerHTML=errState(e.message);page.querySelector('[data-retry]').onclick=function(){render(true)}}return}
    if(S.page!==p)return;
  }
  ({home:pageHome,team:pageTeam,agents:pageAgents,clients:pageClients,cash:pageCash,sales:pageSales,reports:pageReports,insights:pageInsights,warehouse:pageWarehouse,supply:pageSupply,staff:pageStaff,settings:pageSettings})[p](page,force);
}
async function loadDash(){S.dash=await api('dashboard');S.loadedTs=Date.now();stamp();renderNav();return S.dash}
function stamp(){var u=$('updated');u.className='live';u.innerHTML=S.loadedTs?'<i></i>Jonli<span> · '+new Date(S.loadedTs).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit',second:'2-digit'})+'</span>':''}
async function refresh(){var b=$('refreshBtn');b.disabled=true;try{S.dash=null;S.cache={};await render(true);toast('Ma’lumotlar yangilandi')}finally{b.disabled=false}}
$('refreshBtn').onclick=refresh;
function autoRefresh(){
  if($('shell').hidden||!TOKEN)return;
  S.tick++;if(document.hidden&&S.tick%2)return;   // fon rejimida har 60 soniyada
  var prev=S.dash;
  loadDash().then(function(d){
    notifyAll(diffDash(prev,d));
    if(!$('modalOv').hidden)return;
    if(S.page==='home'&&$('dashSide')){$('dashSide').innerHTML=homeSide(d);bindSide();renderOps();if(EX.period!=="yesterday"&&S.tick%2===0)exRender(true)}
    else if(S.page==='cash'){if($('ksList'))cashList();if($('debtBody'))debtList()}else if(S.page==='agents')updateAgentsLive();
  }).catch(function(){var u=$('updated');u.className='live off';u.innerHTML='<i></i>Aloqa yo‘q'});
}
/* Jonli o'zgarishlar: oldingi va yangi holatni solishtirib, faqat yangi hodisalar haqida xabar beradi. */
function diffDash(prev,d){
  var ev=[];if(!prev||!d)return ev;
  var seen={};prev.transactions.forEach(function(t){seen[t.type+t.id]=t.state});
  d.transactions.forEach(function(t){if(t.type!=='handover')return;var was=seen[t.type+t.id];
    if(was===undefined&&t.state==='pending')ev.push(['Kassaga topshiriq',t.agent+': '+usd(t.amountUsd)+' tasdiq kutmoqda','cash']);
    else if(was==='pending'&&t.state==='accepted')ev.push(['Kassir qabul qildi',t.agent+': '+usd(t.amountUsd),'cash'])});
  var dn=(d.warehouse.newOrders||0)-(prev.warehouse.newOrders||0);
  if(dn>0)ev.push(['Yangi buyurtma',dn+' ta yangi buyurtma omborda','warehouse']);
  var old={};prev.clients.forEach(function(c){old[c.id]=1});
  d.clients.forEach(function(c){if(!old[c.id]&&(c.createdTs||0)>=prev.generatedTs-300)ev.push(['Yangi mijoz',c.name+' · '+c.agent,'clients'])});
  var pa={};prev.agents.forEach(function(a){pa[a.id]=a});
  d.agents.forEach(function(a){var o=pa[a.id];if(!o)return;
    if(!o.shiftOpen&&a.shiftOpen)ev.push(['Ish boshlandi',a.name+' smenani ochdi','agents']);
    if(o.shiftOpen&&!a.shiftOpen)ev.push(['Ish tugadi',a.name+' smenani yopdi','agents'])});
  return ev;
}
var unseen=0,audioCtx=null;
document.addEventListener('pointerdown',function(){if(!audioCtx&&window.AudioContext&&store('rw-sound')!=='0'){try{audioCtx=new AudioContext()}catch(e){}}},{once:false,passive:true});
function beep(){
  if(store('rw-sound')==='0'||!audioCtx)return;
  try{var t=audioCtx.currentTime;[0,0.16].forEach(function(dt,i){var o=audioCtx.createOscillator(),g=audioCtx.createGain();o.frequency.value=i?1046:784;g.gain.setValueAtTime(0.0001,t+dt);g.gain.exponentialRampToValueAtTime(0.18,t+dt+0.02);g.gain.exponentialRampToValueAtTime(0.0001,t+dt+0.14);o.connect(g).connect(audioCtx.destination);o.start(t+dt);o.stop(t+dt+0.15)})}catch(e){}
}
function notifyAll(ev){
  if(!ev.length)return;
  if(ev.length>4)ev=ev.slice(0,3).concat([['Yana o‘zgarishlar',(ev.length-3)+' ta boshqa hodisa','home']]);
  beep();
  ev.forEach(function(e,i){setTimeout(function(){toast(e[0]+' — '+e[1])},i*2800)});
  S.feed=ev.map(function(e){return {t:e[0],b:e[1],p:e[2],ts:Date.now()/1000}}).concat(S.feed||[]).slice(0,30);renderFeed();
  if($('railDot'))$('railDot').hidden=false;
  if(document.hidden){unseen+=ev.length;document.title='('+unseen+') '+document.title.replace(/^\(\d+\) /,'')}
  if(store('rw-notify')==='1'&&window.Notification&&Notification.permission==='granted'&&document.hidden){
    ev.forEach(function(e){try{var n=new Notification(e[0],{body:e[1],icon:'/app/premium-kit/emblem.png',tag:'panel-'+e[2]+'-'+e[1]});n.onclick=function(){window.focus();location.hash=e[2];n.close()}}catch(x){}});
  }
}
document.addEventListener('visibilitychange',function(){if(!document.hidden&&unseen){unseen=0;document.title=document.title.replace(/^\(\d+\) /,'')}});
function renderFeed(){
  var el=$('feed');if(!el)return;var f=S.feed||[];
  var FI={cash:['coins','amber'],warehouse:['box','blue'],clients:['store','green'],agents:['compass','violet'],settings:['bell','cyan'],home:['bell','cyan']};
  el.innerHTML=f.length?f.map(function(e){var fi=FI[e.p]||FI.home;return '<div class="li click" data-go="'+e.p+'"><div class="tone t-'+fi[1]+'" style="width:34px;height:34px;border-radius:10px">'+ic(fi[0])+'</div><div class="t"><b>'+esc(e.t.replace(/^[^A-Za-z\u0400-\u04FFʻʼ‘’]+\s*/,''))+'</b><small>'+esc(e.b)+' · '+ago(e.ts)+'</small></div></div>'}).join(''):'<div class="muted small">Panel ochiq turganda yangi buyurtma, kassaga topshiriq, yangi mijoz va smena o‘zgarishlari shu yerda chiqadi.</div>';
  bindGo(el);
}
function themeIcon(){var dk=document.documentElement.dataset.theme==='dark',t=dk?'Kunduzgi rejim':'Tungi rejim';$('themeBtn').innerHTML=ic(dk?'sun':'moon');$('themeBtn').setAttribute('aria-label',t);$('themeBtn').dataset.tip=t}
/* Rejim almashishi: ranglar yumshoq o'tadi (faqat almashish paytida, .theming sinfi orqali). */
$('themeBtn').onclick=function(){var d=document.documentElement;d.classList.add('theming');d.dataset.theme=d.dataset.theme==='dark'?'light':'dark';store('rw-theme',d.dataset.theme);themeIcon();syncColors();
  clearTimeout(S.thT);S.thT=setTimeout(function(){d.classList.remove('theming')},450);if(S.page)render()};
themeIcon();
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'){if(!$('modalOv').hidden)closeModal();else closeDrawer();return}
  if(/INPUT|TEXTAREA|SELECT/.test((e.target.tagName||''))||e.metaKey||e.ctrlKey||e.altKey)return;
  if(e.key==='/'){var s=document.querySelector('.page input[type=search]');if(s){e.preventDefault();s.focus()}}
  else if(e.key==='r'||e.key==='R')refresh();
});

/* ---------- Yordamchi (Siri uslubi): savol matn yoki ovoz bilan → server joriy ma'lumotdan javob beradi ----------
   Faqat tizim ma'lumotlari bo'yicha; boshqa mavzular server tomonda rad etiladi (offTopic) va tarixga qo'shilmaydi. */
var AI={msgs:[],busy:false,speak:store('rw-ai-speak')==='1',rec:null,open:false};
var AI_HINTS=['Bugun nechta tovar sotildi?','Agentlar bugun qanday ishlayapti?','Omborda nima o‘zgardi?','Eng ko‘p qarz kimda?','Bu hafta o‘tgan haftadan yaxshimi?'];
var SRC=window.SpeechRecognition||window.webkitSpeechRecognition;
$('asClose').innerHTML=ic('x');$('aiSend').innerHTML=ic('send');$('aiMic').innerHTML=ic('mic');$('aiSpk').innerHTML=ic('volume');
if(!SRC){$('aiMic').hidden=true}
$('aiSpk').classList.toggle('on',AI.speak);$('aiSpk').setAttribute('aria-pressed',AI.speak);
$('aiHints').innerHTML=AI_HINTS.map(function(h){return '<button type="button" class="as-hint">'+esc(h)+'</button>'}).join('');
function aiState(st,txt){var p=$('asPanel');['listening','thinking','speaking'].forEach(function(k){p.classList.toggle(k,st===k)});
  $('asEdge').classList.toggle('on',st==='listening'||st==='thinking');$('asEdge').classList.toggle('think',st==='thinking');
  $('aiBtn').classList.toggle('busy',!!st);$('asState').textContent=txt||'Savdo, agentlar, ombor va kassa bo‘yicha'}
function openAi(){if(AI.open)return closeAi();AI.open=true;var p=$('asPanel');p.hidden=false;p.classList.remove('closing');$('aiBtn').setAttribute('aria-expanded','true');aiRender();setTimeout(function(){$('aiQ').focus()},80)}
function closeAi(){if(!AI.open)return;AI.open=false;if(AI.rec)AI.rec.abort();if(window.speechSynthesis)speechSynthesis.cancel();aiState('');var p=$('asPanel');p.classList.add('closing');$('aiBtn').setAttribute('aria-expanded','false');
  setTimeout(function(){if(!AI.open){p.hidden=true;p.classList.remove('closing')}},matchMedia('(prefers-reduced-motion: reduce)').matches?0:220)}
$('aiBtn').onclick=openAi;$('asClose').onclick=closeAi;
document.addEventListener('keydown',function(e){if((e.metaKey||e.ctrlKey)&&(e.key==='j'||e.key==='J')&&!$('shell').hidden){e.preventDefault();openAi()}else if(e.key==='Escape'&&AI.open&&$('modalOv').hidden){closeAi()}});
$('aiHints').onclick=function(e){var b=e.target.closest('.as-hint');if(b)aiAsk(b.textContent)};
$('aiForm').onsubmit=function(e){e.preventDefault();aiAsk($('aiQ').value)};
$('aiQ').onkeydown=function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();aiAsk(this.value)}};
$('aiQ').oninput=function(){this.style.height='auto';this.style.height=Math.min(120,this.scrollHeight)+'px'};
$('aiSpk').onclick=function(){AI.speak=!AI.speak;store('rw-ai-speak',AI.speak?'1':'0');this.classList.toggle('on',AI.speak);this.setAttribute('aria-pressed',AI.speak);if(!AI.speak&&window.speechSynthesis){speechSynthesis.cancel();aiState('')}};
$('aiMic').onclick=function(){aiListen()};
function aiRender(){var el=$('aiLog');
  $('asPanel').classList.toggle('fresh',!AI.msgs.length&&!AI.busy);
  el.innerHTML=AI.msgs.length?AI.msgs.map(function(m){return '<div class="as-msg '+m.role+(m.err?' err':'')+(m.off?' off':'')+'">'+esc(m.text).replace(/\n/g,'<br>')+'</div>'}).join('')+(AI.busy?'<div class="as-msg assistant typing"><i></i><i></i><i></i></div>':'')
    :'<div class="as-hello"><b>Nima bilan yordam beray?</b><span>Savdo, agentlar, mijozlar, qarz, kassa yoki ombor haqida so‘rang.</span></div>';
  el.scrollTop=el.scrollHeight;$('aiSend').disabled=AI.busy}
async function aiAsk(q){q=String(q||'').trim();if(!q||AI.busy)return;$('aiQ').value='';$('aiQ').style.height='';
  var hist=AI.msgs.filter(function(m){return !m.err&&!m.off}).map(function(m){return {role:m.role,text:m.text}});
  AI.msgs.push({role:'user',text:q});AI.busy=true;aiState('thinking','O‘ylayapman…');aiRender();
  try{var r=await api('ai_ask',{question:q,history:hist});
    if(r.offTopic)AI.msgs[AI.msgs.length-1].off=true;
    AI.msgs.push({role:'assistant',text:r.answer,off:!!r.offTopic});AI.busy=false;aiState('');aiSay(r.answer)}
  catch(e){AI.msgs.push({role:'assistant',text:e.message,err:true});AI.busy=false;aiState('')}
  finally{AI.busy=false;aiRender()}}
function aiSay(t){if(!AI.speak||!window.speechSynthesis)return;try{speechSynthesis.cancel();var u=new SpeechSynthesisUtterance(t.slice(0,1500));
  var vs=speechSynthesis.getVoices(),v=vs.find(function(x){return /^uz/i.test(x.lang)})||vs.find(function(x){return /^(ru|tr)/i.test(x.lang)});if(v){u.voice=v;u.lang=v.lang}else u.lang='uz-UZ';
  u.onstart=function(){aiState('speaking','Gapiryapman…')};u.onend=u.onerror=function(){aiState('')};speechSynthesis.speak(u)}catch(e){}}
function aiListen(){
  if(!SRC)return;if(AI.rec){AI.rec.stop();return}
  if(window.speechSynthesis)speechSynthesis.cancel();
  var r=new SRC();r.lang='uz-UZ';r.interimResults=true;r.maxAlternatives=1;AI.rec=r;aiState('listening','Tinglayapman…');$('aiMic').classList.add('rec');
  var fin='';r.onresult=function(e){var t='';for(var i=e.resultIndex;i<e.results.length;i++){if(e.results[i].isFinal)fin+=e.results[i][0].transcript;else t+=e.results[i][0].transcript}$('aiQ').value=(fin+t).trim()};
  r.onerror=function(e){if(e.error!=='aborted')toast(e.error==='not-allowed'?'Mikrofonga ruxsat berilmadi':'Ovozni tanib bo‘lmadi — yozib yuboring',true)};
  r.onend=function(){AI.rec=null;$('aiMic').classList.remove('rec');if(!AI.busy)aiState('');if(fin.trim())aiAsk(fin)};
  try{r.start()}catch(e){AI.rec=null;$('aiMic').classList.remove('rec');aiState('')}}

document.addEventListener('pointermove',function(e){var c=e.target.closest&&e.target.closest('.lift,.kpi,.grid>.card');if(!c)return;var r=c.getBoundingClientRect();c.style.setProperty('--mx',(e.clientX-r.left)+'px');c.style.setProperty('--my',(e.clientY-r.top)+'px')},{passive:true});
/* Suzuvchi tooltip: faqat ikonkali tugmalar va yig'ilgan sidebar uchun (body'ga qo'shiladi, kesilmaydi) */
(function(){var tip=document.createElement('div');tip.className='ftip';tip.setAttribute('aria-hidden','true');document.body.appendChild(tip);var tm;
  function want(el){return el&&el.dataset&&el.dataset.tip&&(el.closest('.rail.mini')||el.classList.contains('icon-btn'))}
  function show(el){var r=el.getBoundingClientRect(),side=!!el.closest('.rail');tip.textContent=el.dataset.tip;tip.classList.remove('on');
    clearTimeout(tm);tm=setTimeout(function(){var w=tip.offsetWidth,h=tip.offsetHeight;
      if(side){tip.style.left=(r.right+10)+'px';tip.style.top=(r.top+r.height/2-h/2)+'px'}
      else{tip.style.left=Math.max(8,Math.min(innerWidth-w-8,r.left+r.width/2-w/2))+'px';tip.style.top=(r.bottom+8)+'px'}
      tip.classList.add('on')},250)}
  function hide(){clearTimeout(tm);tip.classList.remove('on')}
  document.addEventListener('pointerover',function(e){var el=e.target.closest&&e.target.closest('[data-tip]');if(want(el))show(el)});
  document.addEventListener('pointerout',function(e){var el=e.target.closest&&e.target.closest('[data-tip]');if(el&&!el.contains(e.relatedTarget))hide()});
  document.addEventListener('focusin',function(e){var el=e.target;if(want(el)&&el.matches(':focus-visible'))show(el)});
  document.addEventListener('focusout',hide);document.addEventListener('pointerdown',hide);window.addEventListener('scroll',hide,true);
})();
/* ---------- raqamlar animatsiyasi: KPI qiymatlari 0 dan sanab chiqadi (faqat sahifa ochilganda) ---------- */
function countUp(root){
  if(matchMedia('(prefers-reduced-motion: reduce)').matches||Date.now()-(S.routeTs||0)>4000)return;
  root.querySelectorAll('.kpi b, .stat-strip b, .hero b.big, .mini b, .hero-stats b').forEach(function(el){
    if(el.dataset.cu||el.children.length)return;var txt=el.textContent,m=txt.match(/-?[\d  ]*\d(?:[.,]\d+)?/);if(!m)return;
    var raw=m[0].replace(/[\s ]/g,'').replace(',','.'),to=parseFloat(raw);if(!isFinite(to)||Math.abs(to)<2)return;
    var dec=(raw.split('.')[1]||'').length,pre=txt.slice(0,m.index),post=txt.slice(m.index+m[0].length),t0=performance.now(),D=700;el.dataset.cu=1;
    var fmt=function(v){return pre+num(v,dec)+post};
    (function step(t){var k=Math.min(1,(t-t0)/D),e=1-Math.pow(1-k,3);el.textContent=fmt(to*e);if(k<1)requestAnimationFrame(step);else el.textContent=txt})(t0)});
}
new MutationObserver(function(){if(S.cuT)return;S.cuT=requestAnimationFrame(function(){S.cuT=0;countUp($('page'))})}).observe($('page'),{childList:true,subtree:true});

/* ---------- global qidiruv (Ctrl/Cmd+K) ---------- */
var GS={items:[],sel:0};
function gsearch(q){
  var box=$('gres');q=String(q||'').trim().toLowerCase();
  if(q.length<2||!S.dash){box.hidden=true;return}
  var norm=function(v){return String(v||'').toLowerCase()},digits=q.replace(/\D/g,'');
  var ag=S.dash.agents.filter(function(a){return norm(a.name).indexOf(q)>=0||String(a.id)===q}).slice(0,5).map(function(a){return {k:'agent',id:a.id,t:a.name,s:(AG_ST[a.status]||AG_ST.offline)[0]+' · '+a.clients+' mijoz',ph:a.photoUrl}});
  var cl=S.dash.clients.filter(function(c){var hay=norm(c.name+' '+c.person+' '+c.address+' '+c.region+' '+c.agent);return hay.indexOf(q)>=0||(digits.length>=4&&String(c.phone||'').replace(/\D/g,'').indexOf(digits)>=0)}).slice(0,8)
    .map(function(c){return {k:'client',id:c.id,t:c.name,s:[c.region,c.agent,c.debtUsd>0?'qarz '+usd(c.debtUsd):''].filter(Boolean).join(' · '),ph:c.thumbUrl}});
  var pg=PAGES.filter(function(p){return p[4]!==9&&pageOn(p[0])&&norm(p[2]).indexOf(q)>=0}).map(function(p){return {k:'page',id:p[0],t:p[2],s:p[3],icon:p[1]}});
  GS.items=pg.concat(ag,cl);GS.sel=0;
  var row=function(it,i){return '<div class="it'+(i===GS.sel?' on':'')+'" data-i="'+i+'" role="option">'+(it.k==='page'?'<div class="tone t-blue" style="width:32px;height:32px">'+ic(it.icon)+'</div>':avatar(it.t,it.ph,it.k==='client'?'sq':''))+'<div class="t"><b>'+esc(it.t)+'</b><small>'+esc(it.s||'')+'</small></div></div>'};
  var html='',i=0,grp=function(name,arr){if(!arr.length)return;html+='<div class="grp">'+name+'</div>';arr.forEach(function(it){html+=row(it,i++)})};
  grp('Sahifalar',pg);grp('Agentlar',ag);grp('Mijozlar',cl);
  box.innerHTML=html||'<div class="empty" style="padding:20px">Hech narsa topilmadi</div>';box.hidden=false;
}
function gpick(i){var it=GS.items[i];if(!it)return;$('gres').hidden=true;$('gq').value='';$('gq').blur();
  if(it.k==='page')location.hash=it.id;else if(it.k==='agent')openAgent(it.id);else openClient(it.id)}
$('gq').addEventListener('input',debounce(function(){gsearch(this.value)},120));
$('gq').addEventListener('focus',function(){if(!S.dash)loadDash().catch(function(){});gsearch(this.value)});
$('gq').addEventListener('keydown',function(e){
  var n=GS.items.length;if(e.key==='ArrowDown'||e.key==='ArrowUp'){if(!n)return;e.preventDefault();GS.sel=(GS.sel+(e.key==='ArrowDown'?1:n-1))%n;
    $('gres').querySelectorAll('.it').forEach(function(el){el.classList.toggle('on',+el.dataset.i===GS.sel);if(+el.dataset.i===GS.sel)el.scrollIntoView({block:'nearest'})})}
  else if(e.key==='Enter'){e.preventDefault();gpick(GS.sel)}
  else if(e.key==='Escape'){$('gres').hidden=true;this.blur()}});
$('gres').addEventListener('mousedown',function(e){var it=e.target.closest('.it');if(it){e.preventDefault();gpick(+it.dataset.i)}});
$('gq').addEventListener('blur',function(){setTimeout(function(){$('gres').hidden=true},120)});
document.addEventListener('keydown',function(e){if((e.metaKey||e.ctrlKey)&&(e.key==='k'||e.key==='K')){e.preventDefault();$('gq').focus();$('gq').select()}});

/* ---------- modal / drawer ---------- */
var modalResolve=null;
function modal(html){clearTimeout(S.mT);$('modalOv').classList.remove('closing');$('modalBody').innerHTML=html;$('modalOv').hidden=false;var f=$('modalBody').querySelector('input,select,textarea,button.pri');if(f)setTimeout(function(){f.focus()},30);return new Promise(function(r){modalResolve=r})}
function closeModal(v){var ov=$('modalOv');if(ov.hidden||ov.classList.contains('closing'))return;ov.classList.add('closing');
  S.mT=setTimeout(function(){ov.hidden=true;ov.classList.remove('closing')},matchMedia('(prefers-reduced-motion: reduce)').matches?0:170);var r=modalResolve;modalResolve=null;if(r)r(v||null)}
$('modalOv').addEventListener('click',function(e){if(e.target===$('modalOv'))closeModal()});
$('modalBody').addEventListener('click',function(e){var b=e.target.closest('[data-m]');if(!b)return;if(b.dataset.m==='cancel')closeModal()});
$('modalBody').addEventListener('submit',function(e){e.preventDefault();var o={};new FormData(e.target).forEach(function(v,k){o[k]=v});closeModal(o)});
function confirmBox(title,body,okText,danger){return modal('<form><h3>'+esc(title)+'</h3><div>'+body+'</div><div class="foot"><button type="button" class="btn" data-m="cancel">Bekor qilish</button><button class="btn '+(danger?'danger':'pri')+'">'+esc(okText||'Tasdiqlash')+'</button></div></form>').then(function(v){return !!v})}
function formBox(title,fields,okText,note){
  return modal('<form><h3>'+esc(title)+'</h3>'+(note?'<p class="muted">'+note+'</p>':'')+'<div class="form">'+fields.map(function(f){
    var a=' name="'+f.name+'"'+(f.required?' required':'')+(f.type?' type="'+f.type+'"':'')+(f.step?' step="'+f.step+'"':'')+(f.placeholder?' placeholder="'+esc(f.placeholder)+'"':'');
    var input=f.options?'<select'+a+'>'+f.options.map(function(o){return '<option value="'+esc(o[0])+'"'+(String(o[0])===String(f.value)?' selected':'')+'>'+esc(o[1])+'</option>'}).join('')+'</select>'
      :f.area?'<textarea rows="3"'+a+'>'+esc(f.value||'')+'</textarea>':'<input'+a+' value="'+esc(f.value==null?'':f.value)+'">';
    return '<label>'+esc(f.label)+input+'</label>'}).join('')+'</div><div class="foot"><button type="button" class="btn" data-m="cancel">Bekor qilish</button><button class="btn pri">'+esc(okText||'Saqlash')+'</button></div></form>');
}
async function run(fn,okMsg){try{var r=await fn();if(okMsg)toast(okMsg);return r}catch(e){toast(e.message,true);return null}}
function drawerSkel(){return '<div class="dh"><span class="skel" style="width:60px;height:60px;border-radius:18px"></span><div style="flex:1;display:grid;gap:8px"><span class="skel-line lg"></span><span class="skel-line"></span></div></div><div class="grid g3">'+'<div class="skel" style="height:84px"></div>'.repeat(3)+'</div><div class="skel" style="height:220px;margin-top:16px"></div>'}
function openDrawer(html){$('drawerBody').innerHTML=html;$('drawer').classList.add('on');$('drawerOv').classList.add('on');$('drawer').inert=false;$('drawer').scrollTop=0}
function closeDrawer(){$('drawer').classList.remove('on');$('drawerOv').classList.remove('on');$('drawer').inert=true;if(S.maps.drawer){try{S.maps.drawer.remove()}catch(e){}delete S.maps.drawer}}
$('drawerOv').onclick=closeDrawer;$('drawerX').onclick=closeDrawer;
function download(d){
  var bin=atob(d.base64),arr=new Uint8Array(bin.length);for(var i=0;i<bin.length;i++)arr[i]=bin.charCodeAt(i);
  var url=URL.createObjectURL(new Blob([arr],{type:d.mime})),a=document.createElement('a');a.href=url;a.download=d.filename;document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(url)},4000);
}

/* ---------- charts ---------- */
var CHARTS={},chartSeq=0;
function smooth(pts,lo,hi){
  var cl=function(y){return lo==null?y:Math.max(lo,Math.min(hi,y))};
  if(pts.length<2)return pts.length?'M'+pts[0][0]+','+pts[0][1]:'';
  var d='M'+pts[0][0]+','+pts[0][1];
  for(var i=0;i<pts.length-1;i++){var p0=pts[i-1]||pts[i],p1=pts[i],p2=pts[i+1],p3=pts[i+2]||p2,t=.18;
    d+=' C'+(p1[0]+(p2[0]-p0[0])*t)+','+cl(p1[1]+(p2[1]-p0[1])*t)+' '+(p2[0]-(p3[0]-p1[0])*t)+','+cl(p2[1]-(p3[1]-p1[1])*t)+' '+p2[0]+','+p2[1]}
  return d;
}
function niceTop(max){if(max<=0)return 1;var e=Math.pow(10,Math.floor(Math.log10(max))),f=max/e;return (f<=1?1:f<=2?2:f<=2.5?2.5:f<=5?5:10)*e}
/* Silliq maydon grafigi: bir nechta qator, gradient to'ldirish, sichqoncha bilan tooltip. */
function areaChart(series,keys,colors,fmt,names){
  if(!series||!series.length)return '<div class="empty">Ma’lumot yo‘q</div>';
  fmt=fmt||num;var W=800,H=250,pl=56,pr=12,pt=14,pb=28,max=0,id='c'+(++chartSeq);
  series.forEach(function(s){keys.forEach(function(k){max=Math.max(max,Number(s[k]||0))})});
  var top=niceTop(max),n=series.length,step=n>1?(W-pl-pr)/(n-1):0;
  var X=function(i){return n>1?pl+i*step:(pl+W-pr)/2},Y=function(v){return pt+(H-pt-pb)*(1-Math.max(0,v)/top)};
  var out='<defs>'+keys.map(function(k,j){return '<linearGradient id="'+id+'g'+j+'" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="'+colors[j]+'" stop-opacity=".16"/><stop offset="1" stop-color="'+colors[j]+'" stop-opacity="0"/></linearGradient>'}).join('')+'</defs>';
  for(var i=0;i<=4;i++){var y=pt+(H-pt-pb)*(1-i/4);out+='<line class="grid-l" x1="'+pl+'" x2="'+(W-pr)+'" y1="'+y+'" y2="'+y+'"/><text x="'+(pl-10)+'" y="'+(y+4)+'" text-anchor="end">'+esc(fmt(top*i/4))+'</text>'}
  var every=Math.ceil(n/12);
  series.forEach(function(s,i){if(i%every===0||(i===n-1&&(n-1)%every>=every/2))out+='<text x="'+X(i)+'" y="'+(H-8)+'" text-anchor="middle">'+esc(s.day)+'</text>'});
  keys.forEach(function(k,j){var pts=series.map(function(s,i){return [X(i),Y(Number(s[k]||0))]}),line=smooth(pts,pt,H-pb);
    out+='<path d="'+line+' L'+pts[pts.length-1][0]+','+(H-pb)+' L'+pts[0][0]+','+(H-pb)+' Z" fill="url(#'+id+'g'+j+')"/>';
    out+='<path class="ln" d="'+line+'" fill="none" stroke="'+colors[j]+'" stroke-width="2.2" stroke-linecap="round"/>';
    out+='<circle class="hdot" data-k="'+j+'" r="5" cx="-99" cy="-99" fill="'+colors[j]+'" stroke="var(--card-solid)" stroke-width="2.5"/>'});
  out+='<line class="cross" x1="-99" x2="-99" y1="'+pt+'" y2="'+(H-pb)+'"/>';
  CHARTS[id]={series:series,keys:keys,colors:colors,fmt:fmt,names:names||keys,X:X,Y:Y,n:n,W:W,pl:pl,pr:pr};
  var lbl=(names||keys).join(', ')+': '+series.length+' nuqta, '+esc(series[0].day)+' – '+esc(series[series.length-1].day)+'. Eng katta qiymat '+esc(fmt(max));
  return '<div class="chartbox" data-chart="'+id+'"><svg class="chart" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" role="img" aria-label="'+lbl+'"><title>'+lbl+'</title>'+out+'</svg><div class="ctip"></div></div>';
}
var barChart=function(series,keys,colors,fmt){return areaChart(series,keys,colors,fmt,keys.map(function(k){return {deliveredUsd:'Realizatsiya',paymentsUsd:'To‘lovlar',visits:'Tashriflar'}[k]||k}))};
document.addEventListener('mousemove',function(e){
  var box=e.target.closest&&e.target.closest('.chartbox');
  document.querySelectorAll('.chartbox.hov').forEach(function(b){if(b!==box)b.classList.remove('hov')});
  if(!box)return;var c=CHARTS[box.dataset.chart];if(!c)return;
  var svg=box.querySelector('svg'),r=svg.getBoundingClientRect(),sx=(e.clientX-r.left)/r.width*c.W;
  var i=c.n>1?Math.round((sx-c.pl)/((c.W-c.pl-c.pr)/(c.n-1))):0;i=Math.max(0,Math.min(c.n-1,i));
  var s=c.series[i],x=c.X(i);box.classList.add('hov');
  var cr=svg.querySelector('.cross');cr.setAttribute('x1',x);cr.setAttribute('x2',x);
  svg.querySelectorAll('.hdot').forEach(function(d){var k=c.keys[+d.dataset.k];d.setAttribute('cx',x);d.setAttribute('cy',c.Y(Number(s[k]||0)))});
  var tip=box.querySelector('.ctip');tip.innerHTML='<b>'+esc(s.day)+'</b>'+c.keys.map(function(k,j){return '<div><span><i style="background:'+c.colors[j]+'"></i> '+esc(c.names[j])+'</span>&nbsp;&nbsp;<b style="display:inline;margin:0">'+esc(c.fmt(Number(s[k]||0)))+'</b></div>'}).join('');
  var px=x/c.W*r.width,tw=tip.offsetWidth;tip.style.left=Math.max(0,Math.min(r.width-tw,px+14>r.width-tw?px-tw-14:px+14))+'px';tip.style.top='8px';
});
/* Donut: [[nom, qiymat, rang], …] */
function donut(parts,center,sub){
  var total=parts.reduce(function(a,p){return a+Math.max(0,p[1])},0),R=70,r=48,cx=84,cy=84,a0=-Math.PI/2,out='';
  if(!total)out='<circle cx="84" cy="84" r="59" fill="none" stroke="var(--line2)" stroke-width="22"/>';
  parts.forEach(function(p){if(p[1]<=0)return;var a1=a0+p[1]/total*Math.PI*2-(parts.length>1?.02:0),big=a1-a0>Math.PI?1:0;
    if(p[1]===total){out+='<circle cx="84" cy="84" r="59" fill="none" stroke="'+p[2]+'" stroke-width="22"><title>'+esc(p[0])+': '+p[1]+'</title></circle>'}
    else out+='<path d="M'+(cx+R*Math.cos(a0))+','+(cy+R*Math.sin(a0))+' A'+R+','+R+' 0 '+big+' 1 '+(cx+R*Math.cos(a1))+','+(cy+R*Math.sin(a1))+' L'+(cx+r*Math.cos(a1))+','+(cy+r*Math.sin(a1))+' A'+r+','+r+' 0 '+big+' 0 '+(cx+r*Math.cos(a0))+','+(cy+r*Math.sin(a0))+' Z" fill="'+p[2]+'"><title>'+esc(p[0])+': '+p[1]+'</title></path>';
    a0=a1+(parts.length>1?.02:0)});
  out+='<text x="84" y="82" text-anchor="middle" font-size="24" font-weight="800">'+esc(center)+'</text><text x="84" y="102" text-anchor="middle" font-size="11" style="fill:var(--mu)">'+esc(sub||'')+'</text>';
  return '<div class="donut-wrap"><svg class="donut" viewBox="0 0 168 168">'+out+'</svg><div class="donut-legend">'+parts.map(function(p){return '<div><i style="background:'+p[2]+'"></i><span>'+esc(p[0])+'</span><b>'+(p[3]!=null?p[3]:num(p[1]))+'</b><small class="muted" style="width:44px;text-align:right">'+(p[4]!=null?p[4]:total?Math.round(p[1]/total*1000)/10:0)+'%</small></div>'}).join('')+'</div></div>';
}
/* Mini grafik (KPI kartalar uchun). */
function spark(values,color){
  if(!values||values.length<2)return '';
  var max=Math.max.apply(null,values.concat([0])),min=Math.min.apply(null,values.concat([0])),W=92,H=34,rg=max-min||1;
  var pts=values.map(function(v,i){return [i*(W/(values.length-1)),H-3-(v-min)/rg*(H-6)]}),d=smooth(pts),gid='s'+(++chartSeq);
  return '<svg class="spark" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none"><defs><linearGradient id="'+gid+'" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="'+color+'" stop-opacity=".35"/><stop offset="1" stop-color="'+color+'" stop-opacity="0"/></linearGradient></defs><path d="'+d+' L'+W+','+H+' L0,'+H+' Z" fill="url(#'+gid+')"/><path d="'+d+'" fill="none" stroke="'+color+'" stroke-width="2" stroke-linecap="round"/></svg>';
}
function delta(cur,prev){if(!prev)return '';var p=Math.round((cur-prev)/Math.abs(prev)*100);return '<span class="delta '+(p>=0?'up':'down')+'">'+(p>=0?'↑':'↓')+Math.abs(p)+'%</span>'}
function legend(items){return '<div class="legend">'+items.map(function(i){return '<span><i style="background:'+i[1]+'"></i>'+esc(i[0])+'</span>'}).join('')+'</div>'}
function errState(msg){return '<div class="card err-state"><div class="tone t-red">'+ic('alert','lg')+'</div><h3>Ma’lumotni yuklab bo‘lmadi</h3><p class="muted">'+esc(msg)+'</p><button class="btn pri" data-retry>'+ic('refresh','sm')+' Qayta urinish</button></div>'}
function emptyState(text,icon){return '<div class="empty"><span class="empty-ico">'+ic(icon||'list')+'</span><span>'+esc(text)+'</span></div>'}
function kpi(icon,label,value,sub,cls,go,spark){var m=EMO[icon]||[icon,'blue'];
  return '<div class="card kpi'+(spark?' has-spark':'')+(go?' click" data-go="'+go:'')+'">'+tone(m[0],m[1])+'<div><small>'+label+'</small><b>'+value+'</b><em class="'+(cls||'')+'">'+(sub||'')+'</em></div>'+(spark||'')+'</div>'}
function bindGo(root){root.querySelectorAll('[data-go]').forEach(function(el){el.onclick=function(){var g=el.dataset.go.split(':');
  if(g[1]==='debt'){CL.debt='debt';CL.age='';CL.sort='debtUsd';CL.dir=-1}
  else if(g[1]==='new'){CL.debt='';CL.age='';CL.sort='createdTs';CL.dir=-1}
  else if(g[1])S.cache.clientAge=g[1];
  if(g[0]==='clients'&&S.page==='home'){CL.agent=EX.agent||'';CL.page=0}
  location.hash=g[0]}})}

/* ---------- maps ---------- */
function safeInv(m,key,ms){setTimeout(function(){if(S.maps[key]===m&&m._container&&m._container.isConnected){try{m.invalidateSize()}catch(e){}}},ms)}
function makeMap(el,key){
  if(!window.L){el.innerHTML='<div class="empty">Xarita yuklanmadi (internetni tekshiring).</div>';return null}
  var m=L.map(el,{zoomControl:true,attributionControl:true}).setView([40.45,71.6],9);
  L.tileLayer('/tiles/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(m);
  S.maps[key]=m;return m;
}
function agentIcon(a,on){var c=(AG_ST[a.status]||AG_ST.offline)[2];return L.divIcon({className:'',html:'<div class="pin" style="background:'+c+(on?';outline:3px solid '+C.pri:'')+'"><b>'+initial(a.name)+'</b></div>',iconSize:[34,34],iconAnchor:[17,34]})}

/* ================= PAGES ================= */

/* ----- Asosiy ----- */
/* ----- Asosiy: Executive Dashboard V2 (1816 kompozitsiya + 1817 grafiklar) ----- */
var EX=(function(){try{return Object.assign({period:'today',from:'',to:'',agent:'',region:'',currency:'all',group:'auto'},JSON.parse(store('rw-ex')||'{}'))}catch(e){return {period:'today',from:'',to:'',agent:'',region:'',currency:'all',group:'auto'}}})();
/* Moliyadagi bilan bir xil: Bugun · Hafta · Oy (30 kun) · Davr. */
var EX_PERIODS=[['today','Bugun'],['d7','Hafta'],['d30','Oy'],['custom','Davr']];
if(!EX_PERIODS.some(function(p){return p[0]===EX.period}))EX.period='today';
var OPS={f:''};
function exKey(){return JSON.stringify([EX.period,EX.from,EX.to,EX.agent,EX.region,EX.group])}
async function loadEx(force){
  var key='ex'+exKey();if(!force&&S.cache[key])return S.cache[key];
  var d=await api('executive',{period:EX.period,from:EX.from,to:EX.to,agentId:EX.agent?+EX.agent:undefined,region:EX.region||undefined,group:EX.group});
  S.cache[key]=d;S.ex=d;return d;
}
function exDelta(k){
  var d=k.delta;if(!d)return k.prev==null?'':'<span class="delta flat">—</span>';
  if(d.kind==='new')return '<span class="delta up">yangi</span>';
  var good=k.key==='debt'?d.pct<=0:d.pct>=0,cls=d.pct===0?'flat':good?'up':'down';
  return '<span class="delta '+cls+'">'+(d.pct>0?'↑':d.pct<0?'↓':'')+Math.abs(d.pct)+'%</span>';
}
function greet(){var h=new Date(Date.now()+5*3600e3).getUTCHours();return h<5?'Xayrli tun':h<11?'Xayrli tong':h<17?'Xayrli kun':'Xayrli kech'}
function pageHome(page,force){
  var name=(S.me&&S.me.name||'').split(' ')[0];
  $('pageTitle').textContent=greet()+(name?', '+name:'');
  var nd=new Date(Date.now()+5*3600e3),WD=['yakshanba','dushanba','seshanba','chorshanba','payshanba','juma','shanba'],MO=['yanvar','fevral','mart','aprel','may','iyun','iyul','avgust','sentyabr','oktyabr','noyabr','dekabr'];
  $('pageSub').textContent=nd.getUTCDate()+'-'+MO[nd.getUTCMonth()]+' '+nd.getUTCFullYear()+', '+WD[nd.getUTCDay()];
  page.innerHTML=
   '<div class="toolbar" id="exBar">'+
     '<div class="seg" id="exSeg" role="tablist" aria-label="Davr">'+EX_PERIODS.map(function(p){return '<button role="tab" data-p="'+p[0]+'" class="'+(EX.period===p[0]?'on':'')+'" aria-selected="'+(EX.period===p[0])+'">'+p[1]+'</button>'}).join('')+'</div>'+
     '<span id="exCustom" class="actions period-c"'+(EX.period==='custom'?'':' hidden')+'><input type="date" id="exFrom" value="'+esc(EX.from||today())+'" max="'+today()+'" style="width:auto" aria-label="Boshlanish sanasi"><input type="date" id="exTo" value="'+esc(EX.to||today())+'" max="'+today()+'" style="width:auto" aria-label="Tugash sanasi"><button class="btn ink sm" id="exGo">Qo‘llash</button></span>'+
     '<select id="exRegion" aria-label="Hudud"><option value="">Barcha hududlar</option></select>'+
     '<select id="exAgent" aria-label="Agent"><option value="">Barcha agentlar</option></select>'+
     '<select id="exCur" aria-label="Valyuta" title="Yig‘ilgan pul qaysi valyutada ko‘rsatilsin">'+[['all','Pul: hammasi (USD)'],['usd','Naqd dollar'],['uzs','Naqd so‘m'],['card','Karta']].map(function(o){return '<option value="'+o[0]+'"'+(EX.currency===o[0]?' selected':'')+'>'+o[1]+'</option>'}).join('')+'</select>'+
     '<button class="btn sm" id="exReset" title="Filtrlarni tozalash">'+ic('x','sm')+' Tozalash</button>'+
     '<span class="grow"></span><span class="muted small" id="exLabel"></span>'+
   '</div>'+
   '<div class="dash"><div class="dash-main" id="exBody">'+
     '<div class="grid g4">'+'<div class="skel"></div>'.repeat(4)+'</div><div class="grid g3">'+'<div class="skel" style="height:86px"></div>'.repeat(3)+'</div><div class="skel" style="height:320px"></div>'+
   '</div><aside class="dash-side" id="dashSide" aria-label="Faollik paneli">'+homeSide(S.dash)+'</aside></div>';
  var save=function(){store('rw-ex',JSON.stringify(EX))},reload=function(){save();exRender(true)};
  $('exSeg').onclick=function(e){var b=e.target.closest('button');if(!b)return;$('exSeg').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b);x.setAttribute('aria-selected',x===b)});
    if(b.dataset.p==='custom'){$('exCustom').hidden=false;$('exFrom').focus();return}$('exCustom').hidden=true;EX.period=b.dataset.p;reload()};
  $('exGo').onclick=function(){var f=$('exFrom').value,t=$('exTo').value;if(!f||!t){toast('Ikkala sanani tanlang',true);return}EX.period='custom';EX.from=f;EX.to=t;reload()};
  $('exRegion').onchange=function(){EX.region=this.value;reload()};
  $('exAgent').onchange=function(){EX.agent=this.value;reload()};
  $('exCur').onchange=function(){EX.currency=this.value;save();exRender(false)};
  $('exReset').onclick=function(){EX={period:'today',from:'',to:'',agent:'',region:'',currency:'all',group:'auto'};save();pageHome(page)};
  bindSide();
  exRender(!!force);
}
async function exRender(force){
  var d;try{d=await loadEx(force)}catch(e){if(S.page!=='home')return;$('exBody').innerHTML=errState(e.message);$('exBody').querySelector('[data-retry]').onclick=function(){exRender(true)};return}
  if(S.page!=='home'||!$('exBody'))return;
  var fill=function(sel,items,cur,ph){sel.innerHTML='<option value="">'+ph+'</option>'+items.map(function(o){return '<option value="'+esc(o[0])+'"'+(String(cur)===String(o[0])?' selected':'')+'>'+esc(o[1])+'</option>'}).join('')};
  fill($('exRegion'),d.options.regions.map(function(r){return [r.key,r.name]}),EX.region,'Barcha hududlar');
  fill($('exAgent'),d.options.agents.map(function(a){return [a.id,a.name]}),EX.agent,'Barcha agentlar');
  var r=d.range;$('exLabel').textContent=r.label+(r.prevLabel?' · taqqoslash: '+r.prevLabel:'');
  var col=function(k){return d.series.map(function(x){return Number(x[k]||0)})},K={};d.kpis.forEach(function(k){K[k.key]=k});
  var c=d.collections,cur=EX.currency,coll=K.collected,collVal=usd(coll.value),collSub=exDelta(coll)+' oldingi davrga nisbatan';
  if(cur==='usd'){collVal=usd(c.cashUsd);collSub='Naqd dollarda olingan'}
  else if(cur==='uzs'){collVal=uzs(c.cashUzs);collSub='≈ '+usd(c.cashUzsAsUsd)+' to‘lov kunidagi kurs bilan'}
  else if(cur==='card'){collVal=usd(c.cardUsd);collSub='Karta orqali (kassir tasdiqlagan)'}
  var prevTxt=function(k,money){return k.prev!=null?' <span class="muted">oldin '+(money?usd(k.prev):num(k.prev))+'</span>':''};
  var sp=function(key,color){return d.series.length>1?spark(col(key),color):''};
  var ac=d.agentsCash;
  // Undiruv darajasi: yig'ilgan pul / realizatsiya (davr bo'yicha)
  var rate=K.realization.value>0?Math.min(999,Math.round(coll.value/K.realization.value*100)):null;
  var aging=d.debtAging,amax=Math.max.apply(null,aging.map(function(b){return b.usd}).concat([1])),atot=aging.reduce(function(a,b){return a+b.usd},0);
  var regs=d.regionSales.filter(function(x){return x.realizationUsd>0}),rtot=regs.reduce(function(a,x){return a+x.realizationUsd},0),RC=[C.pri,C.cyan,C.violet,C.ink,C.gray,C.violet,C.cyan,C.gray];
  var ag=d.agents.filter(function(a){return a.realizationUsd||a.paymentsUsd||a.visits}).slice(0,8),gmax=Math.max.apply(null,ag.map(function(a){return Math.max(a.realizationUsd,a.paymentsUsd)}).concat([1]));
  var groups=[['auto','Avto'],['day','Kun'],['week','Hafta'],['month','Oy']];
  var kcard=function(cls,icon,label,value,sub,go,sparkHtml){var m=EMO[icon]||[icon,'blue'];return '<div class="card kpi lift click '+cls+(sparkHtml?' has-spark':'')+'" data-go="'+go+'" tabindex="0" role="button">'+tone(m[0],m[1])+'<div><small>'+label+'</small><b>'+value+'</b><em>'+sub+'</em></div>'+(sparkHtml||'')+'</div>'};
  $('exBody').innerHTML=
   '<div class="grid g4 kpis">'+
     kcard('','📦','Realizatsiya',usd(K.realization.value),exDelta(K.realization)+prevTxt(K.realization,1),'reports',sp('realizationUsd',C.pri))+
     kcard('','💰','Yig‘ilgan pul',collVal,cur==='all'?exDelta(coll)+prevTxt(coll,1):collSub,'cash',cur==='all'?sp('paymentsUsd',C.forest):'')+
     kcard('c-orange','🧾','Umumiy qarzdorlik',usd(K.debt.value),exDelta(K.debt)+' davr boshiga nisbatan'+(d.advanceUsd?' · avans '+usd(d.advanceUsd):''),'clients:debt')+
     kcard('c-ink','💵','Agentlardagi pul',usd(ac.cashUsd),'+ '+uzs(ac.cashUzs)+(ac.pendingUsd||ac.pendingUzs?' · kassirda kutilmoqda: '+usd(ac.pendingUsd)+(ac.pendingUzs?' + '+uzs(ac.pendingUzs):''):''),'cash')+
   '</div>'+
   '<div class="grid g3 kpis sm">'+
     kcard('','🧭','Faol agentlar',num(K.activeAgents.value),exDelta(K.activeAgents)+prevTxt(K.activeAgents),'agents')+
     kcard('','➕','Yangi mijozlar',num(K.newClients.value),exDelta(K.newClients)+prevTxt(K.newClients),'clients:new')+
     kcard('','👣','Tashriflar',num(K.visits.value),exDelta(K.visits)+prevTxt(K.visits),'reports')+
   '</div>'+
   '<div class="card"><div class="card-h"><div><h3>'+ic('trend')+' Savdo</h3><div class="stat-strip" style="margin-top:8px"><div><b style="font-size:28px">'+usd(K.realization.value)+'</b>'+(K.realization.delta&&K.realization.delta.kind==='pct'?'<span class="pill-badge'+(K.realization.delta.pct<0?' o':'')+'">'+(K.realization.delta.pct>=0?'+':'')+K.realization.delta.pct+'%</span>':'')+'<small>'+esc(r.label)+' realizatsiya · yig‘ilgan '+usd(coll.value)+'</small></div></div></div>'+
     '<div class="acts"><div class="seg" id="exGrp">'+groups.map(function(g){return '<button data-g="'+g[0]+'" class="'+(EX.group===g[0]?'on':'')+'">'+g[1]+'</button>'}).join('')+'</div><button class="round-btn" data-go="reports" title="Hisobotga o‘tish">'+ic('out','sm')+'</button></div></div>'+
     legend([['Realizatsiya',C.pri],['Yig‘ilgan pul',C.forest]])+'<div style="margin-top:8px">'+areaChart(d.series,['realizationUsd','paymentsUsd'],[C.pri,C.forest],usd,['Realizatsiya','Yig‘ilgan pul'])+'</div></div>'+
   '<div class="grid g-main">'+
     '<div class="card"><div class="card-h"><div><h3>'+ic('clock')+' Qarzdorlik yoshi</h3><small class="muted">To‘lanmagan tovar, berilgan kunidan beri (FIFO)</small></div><button class="round-btn" data-go="clients:debt" title="Qarzdor mijozlar">'+ic('out','sm')+'</button></div>'+
       (atot?'<div class="aging">'+aging.map(function(b,i){return '<div class="col'+(i===aging.length-1?' last':'')+'" title="'+esc(b.label)+' kun: '+usd(b.usd)+'"><i style="height:'+Math.max(3,b.usd/amax*100)+'%"></i></div>'}).join('')+'</div><div class="aging-x">'+aging.map(function(b){return '<span>'+esc(b.label)+'</span>'}).join('')+'</div>'+
       '<div class="list aging-rows">'+aging.map(function(b,i){return '<div class="li'+(i===aging.length-1?' last':'')+'"><i></i><div class="t"><b>'+esc(b.label)+' kun</b></div><span class="muted small">'+b.clients+' mijoz</span>&nbsp;&nbsp;<b class="num">'+usd(b.usd)+'</b></div>'}).join('')+'</div>':emptyState('To‘lanmagan qarz yo‘q','checkc'))+'</div>'+
     '<div class="card c-forest"><div class="card-h"><h3>'+ic('target')+' Undiruv darajasi</h3></div>'+
       '<div class="quota">'+quotaRing(rate)+'</div><p class="small" style="margin:8px 0 0;opacity:.85;text-align:center">'+esc(r.label)+': yig‘ilgan '+usd(coll.value)+' / realizatsiya '+usd(K.realization.value)+'</p></div>'+
   '</div>'+
   '<div class="grid g2">'+
     '<div class="card"><div class="card-h"><h3>'+ic('map')+' Hududlar bo‘yicha savdo</h3><span class="muted small">'+usd(rtot)+'</span></div>'+
       (regs.length?'<div class="segbar">'+regs.slice(0,8).map(function(x,i){return '<i style="flex:'+Math.max(x.realizationUsd,rtot*.02)+';background:'+RC[i%RC.length]+'" title="'+esc(x.name)+': '+usd(x.realizationUsd)+'"></i>'}).join('')+'</div>'+
       '<div class="list seglist">'+regs.slice(0,8).map(function(x,i){return '<div class="li"><i style="background:'+RC[i%RC.length]+'"></i><div class="t"><b>'+esc(x.name)+'</b></div><span class="muted small">'+Math.round(x.realizationUsd/rtot*100)+'% · pul '+usd(x.paymentsUsd)+'</span>&nbsp;&nbsp;<b class="num">'+usd(x.realizationUsd)+'</b></div>'}).join('')+'</div>':emptyState('Bu davrda savdo yo‘q','map'))+'</div>'+
     '<div class="card"><div class="card-h"><h3>'+ic('chart')+' Agentlar KPI reytingi</h3>'+legend([['Realizatsiya',C.pri],['Pul',C.forest]])+'</div>'+
       (ag.length?ag.map(function(a,i){return '<div class="hbar" data-agent="'+a.agentId+'"><span class="nm">'+(i+1)+'. '+esc(a.agent)+'</span><div style="display:grid;gap:4px"><div class="track"><i style="width:'+(Math.max(0,a.realizationUsd)/gmax*100)+'%;background:'+C.pri+'"></i></div><div class="track"><i style="width:'+(a.paymentsUsd/gmax*100)+'%;background:'+C.forest+'"></i></div></div><b>'+usd(a.realizationUsd)+(a.collectionPct!=null?' <span class="pill '+(a.collectionPct>=70?'p-ok':a.collectionPct>=40?'p-warn':'p-bad')+'">'+Math.round(a.collectionPct)+'%</span>':'')+'</b></div>'}).join(''):emptyState('Bu davrda agent faoliyati yo‘q','compass'))+'</div>'+
   '</div>'+
   '<div class="grid g2">'+
     '<div class="card"><div class="card-h"><h3>'+ic('receipt')+' Qarzdorlik dinamikasi</h3><span class="muted small">Har '+({hour:'soat',day:'kun',week:'hafta',month:'oy'}[d.group]||'davr')+' oxirida</span></div>'+areaChart(d.series,['debtUsd'],[C.orange],usd,['Umumiy qarz'])+'</div>'+
     '<div class="card"><div class="card-h"><h3>'+ic('compass')+' GPS monitoring</h3><button class="round-btn" data-go="agents" title="GPS markazga o‘tish">'+ic('out','sm')+'</button></div><div class="mini-map" id="miniMap"></div><div id="miniAg"></div></div>'+
   '</div>'+
   '<div class="card flush"><div class="card-h"><h3>'+ic('list')+' So‘nggi muhim operatsiyalar</h3><div class="acts"><div class="seg" id="opsSeg">'+[['','Hammasi'],['in','Kirim'],['out','Chiqim'],['pending','Kutilmoqda']].map(function(x){return '<button data-f="'+x[0]+'" class="'+(OPS.f===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div><button class="round-btn" data-go="cash" title="Moliyaga o‘tish">'+ic('out','sm')+'</button></div></div><div class="tbl-wrap" id="opsBody" style="margin-top:10px"></div></div>';
  $('exGrp').onclick=function(e){var b=e.target.closest('button');if(!b)return;EX.group=b.dataset.g;store('rw-ex',JSON.stringify(EX));exRender(false)};
  $('opsSeg').onclick=function(e){var b=e.target.closest('button');if(!b)return;OPS.f=b.dataset.f;$('opsSeg').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});renderOps()};
  $('exBody').querySelectorAll('[role=button][data-go]').forEach(function(el){el.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();el.click()}})});
  bindGo($('exBody'));bindAgentLinks($('exBody'));renderOps();miniMap();
  if($('calCard')){$('calCard').innerHTML=calendarHtml(d.calendar);bindSide()}
}
function quotaRing(p){
  var v=p==null?0:Math.min(100,p),R=58,L=2*Math.PI*R,off=L*(1-v/100);
  return '<svg viewBox="0 0 150 150" role="img" aria-label="Undiruv '+(p==null?'—':p+'%')+'"><circle cx="75" cy="75" r="'+R+'" fill="none" stroke="rgba(255,255,255,.18)" stroke-width="12"/>'+
    '<circle cx="75" cy="75" r="'+R+'" fill="none" stroke="'+C.yellow+'" stroke-width="12" stroke-linecap="round" stroke-dasharray="'+L+'" stroke-dashoffset="'+off+'" transform="rotate(-90 75 75)" style="transition:stroke-dashoffset .8s var(--ease)"/>'+
    '<text x="75" y="80" text-anchor="middle" font-size="30" font-weight="600" fill="#fff">'+(p==null?'—':p+'%')+'</text><text x="75" y="100" text-anchor="middle" font-size="11" fill="rgba(255,255,255,.75)">undirildi</text></svg>';
}
function renderOps(){
  var el=$('opsBody');if(!el||!S.dash)return;
  var ST={pending:['Kutilmoqda','p-warn'],accepted:['Qabul qilindi','p-ok'],rejected:['Rad etildi','p-bad'],expense:['Chiqim','p-bad']};
  var rows=S.dash.transactions.filter(function(t){if(OPS.f==='in')return t.type==='handover';if(OPS.f==='out')return t.type==='expense';if(OPS.f==='pending')return t.state==='pending';return true}).slice(0,8);
  el.innerHTML=rows.length?'<table class="ops"><thead><tr><th>Sana</th><th>Operatsiya</th><th>Kim</th><th class="right">Summa</th><th>Holat</th></tr></thead><tbody>'+rows.map(function(t){var h=t.type==='handover',st=ST[t.state]||[esc(t.state),''];
    return '<tr><td class="num">'+dt(t.acceptedTs||t.ts)+'</td><td>'+catCell(h,h?'Kassaga topshiriq':t.category)+(h&&t.amountUzs?' <small class="muted">'+uzs(t.amountUzs)+'</small>':'')+'</td><td><b>'+esc(h?t.agent:(t.recipient||'—'))+'</b>'+(t.cashier?'<br><small class="muted">'+esc(t.cashier)+'</small>':'')+'</td><td class="right num '+(h?(t.state==='accepted'?'ok':''):'bad')+'">'+(h?'+':'−')+usd(t.amountUsd)+'</td><td>'+pill('<span class="dot"></span>'+st[0],st[1])+'</td></tr>'}).join('')+'</tbody></table>':emptyState('Operatsiya yo‘q','list');
}
function miniMap(){
  var el=$('miniMap');if(!el||!window.L)return;
  if(S.maps.mini){try{S.maps.mini.remove()}catch(e){}}
  var m=L.map(el,{zoomControl:false,attributionControl:false,dragging:true,scrollWheelZoom:false}).setView([40.45,71.6],9);
  L.tileLayer('/tiles/{z}/{x}/{y}.png',{maxZoom:19}).addTo(m);S.maps.mini=m;
  var pts=[];S.dash.agents.forEach(function(a){if(a.lat==null)return;pts.push([a.lat,a.lon]);L.marker([a.lat,a.lon],{icon:agentIcon(a),title:a.name,alt:a.name}).addTo(m).bindTooltip(esc(a.name)+' · '+(a.lastGpsTs?ago(a.lastGpsTs):'GPS yo‘q')).on('click',function(){GPS.agent=a.id;gpsSave();location.hash='agents'})});
  if(pts.length)m.fitBounds(pts,{padding:[30,30],maxZoom:13,animate:false});safeInv(m,'mini',80);
  var by={active:0,late:0,offline:0};S.dash.agents.forEach(function(a){by[a.status]=(by[a.status]||0)+1});
  var stale=S.dash.agents.filter(function(a){return a.shiftOpen&&a.lastGpsTs&&Date.now()/1000-a.lastGpsTs>STALE}).length;
  $('miniAg').innerHTML='<div class="actions">'+pill('<span class="dot"></span>Faol '+by.active,'p-ok')+pill('<span class="dot"></span>Kechikkan '+by.late,'p-warn')+pill('Yopiq '+by.offline)+(stale?pill(ic('alert','sm')+' GPS eskirgan: '+stale,'p-bad'):'')+'</div>';
}
/* O'ng panel (1816 Activity/Calendar): kassa, kalendar, diqqat, jonli lenta — filtrdan qat'i nazar hozirgi holat */
function homeSide(d){
  var s=d.summary,c=d.cash,cal=S.ex&&S.ex.calendar;
  var overdue=d.clients.filter(function(x){return x.age==='red'&&!x.blacklisted});
  var pend=d.transactions.filter(function(t){return t.type==='handover'&&t.state==='pending'});
  var alerts='';
  if(overdue.length)alerts+='<div class="alert r" data-go="clients:red"><div class="tone">'+ic('clock')+'</div><div><b>'+overdue.length+' mijozga 5+ kun tashrif yo‘q</b><small>Qizil — uzoq vaqt tashrif bo‘lmagan</small></div></div>';
  if(pend.length)alerts+='<div class="alert y" data-go="cash"><div class="tone">'+ic('hourglass')+'</div><div><b>'+pend.length+' topshiriq tasdiq kutmoqda</b><small>Jami '+usd(s.pendingUsd)+'</small></div></div>';
  if(d.warehouse.newOrders)alerts+='<div class="alert b" data-go="warehouse"><div class="tone">'+ic('box')+'</div><div><b>'+d.warehouse.newOrders+' yangi buyurtma</b><small>Ochiq: '+d.warehouse.openOrders+'</small></div></div>';
  if(!alerts)alerts=emptyState('Diqqat talab qiladigan holat yo‘q','checkc');
  return '<div class="card hero"><div style="position:relative"><small>'+ic('wallet','sm')+' Umumiy kassa qoldig‘i</small><b class="big">'+usd(c.balanceUsd)+'</b><div class="muted small">Naqd va karta, USD ekvivalentida</div></div>'+
      '<div class="hero-stats" style="grid-template-columns:1fr 1fr"><div><small>Bugun qabul</small><b>'+usd(c.acceptedTodayUsd)+'</b></div><div><small>Bugun xarajat</small><b>'+usd(c.expensesTodayUsd)+'</b></div></div></div>'+
    '<div class="card" id="calCard">'+calendarHtml(cal)+'</div>'+
    '<div class="card"><div class="card-h"><h3>'+ic('alert')+' Diqqat</h3></div>'+alerts+'</div>'+
    '<div class="card"><div class="card-h"><h3>'+ic('bell')+' Jonli lenta</h3><span class="live" style="padding:4px 9px"><i></i>30 s</span></div><div class="list" id="feed"></div></div>';
}
function calendarHtml(cal){
  if(!cal)return '<div class="card-h"><h3>'+ic('calendar')+' Kalendar</h3></div><div class="skel" style="height:220px;border:0"></div>';
  var MN=['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr'];
  var vals=Object.keys(cal.values).map(function(k){return cal.values[k].realizationUsd}),max=Math.max.apply(null,vals.concat([0]));
  var t=today(),ym=cal.year+'-'+String(cal.month).padStart(2,'0'),sel=EX.period==='custom'&&EX.from===EX.to?EX.from:(EX.period==='today'?t:'');
  var html='<div class="cal-head"><b>'+ic('calendar')+' '+MN[cal.month-1]+' '+cal.year+'</b><span class="muted small">kunlik realizatsiya</span></div><div class="cal">'+['Du','Se','Ch','Pa','Ju','Sh','Ya'].map(function(x){return '<span>'+x+'</span>'}).join('');
  for(var i=0;i<cal.firstWeekday;i++)html+='<span></span>';
  for(var dd=1;dd<=cal.days;dd++){var key=ym+'-'+String(dd).padStart(2,'0'),v=(cal.values[dd]||{}).realizationUsd||0,lv=v<=0?0:max?Math.ceil(v/max*3):0;
    html+='<button data-day="'+key+'" class="'+(lv?'h'+lv:'')+(key===t?' today':'')+(key===sel?' sel':'')+'"'+(key>t?' disabled':'')+' title="'+key+(v?': '+usd(v):'')+'">'+dd+'</button>'}
  return html+'</div><p class="hint" style="margin-top:10px">Kunni bosing — dashboard o‘sha kun bo‘yicha ko‘rsatiladi.</p>';
}
function bindSide(){
  var side=$('dashSide');if(!side)return;bindGo(side);renderFeed();
  side.querySelectorAll('[data-day]').forEach(function(b){b.onclick=function(){EX.period='custom';EX.from=EX.to=b.dataset.day;store('rw-ex',JSON.stringify(EX));pageHome($('page'))}});
}
function agentReportTable(rows){
  if(!rows||!rows.length)return '<div class="empty">Agentlar yo‘q</div>';
  return '<table><thead><tr><th>Agent</th><th class="right">Realizatsiya</th><th class="right">To‘lov</th><th class="right">Tashrif</th><th class="right">Yangi</th><th class="right">Ish vaqti</th><th class="right">Masofa</th></tr></thead><tbody>'+
   rows.map(function(a){return '<tr class="click" data-agent="'+a.agentId+'"><td><b>'+esc(a.agent)+'</b></td><td class="right num">'+usd(a.deliveredUsd)+'</td><td class="right num">'+usd(a.paymentsUsd)+'</td><td class="right num">'+a.visits+'</td><td class="right num">'+a.newClients+'</td><td class="right num">'+hours(a.workSeconds)+'</td><td class="right num">'+num(a.distanceKm,1)+' km</td></tr>'}).join('')+'</tbody></table>';
}
function bindAgentLinks(root){root.querySelectorAll('[data-agent]').forEach(function(el){el.onclick=function(){openAgent(+el.dataset.agent)}})}
function bindClientLinks(root){root.querySelectorAll('[data-client]').forEach(function(el){el.onclick=function(e){if(e.target.closest('a[href]'))return;openClient(+el.dataset.client)}})}

/* ----- Agentlar ----- */
/* ----- GPS Control Center: chapda agentlar, markazda xarita, o'ngda tanlangan agent ----- */
var GPS=(function(){try{return Object.assign({agent:null,region:'',status:'',q:'',clients:true,day:''},JSON.parse(store('rw-gps')||'{}'))}catch(e){return {agent:null,region:'',status:'',q:'',clients:true,day:''}}})();
var STALE=300;  // dashboard qoidasi: oxirgi GPS 5 daqiqadan eski bo'lsa "kechikkan"
function gpsSave(){store('rw-gps',JSON.stringify(GPS))}
function agentRegions(){
  // Agent hududi = mijozlari joylashgan hududlar (agentlarda alohida hudud maydoni yo'q).
  var m={};S.dash.clients.forEach(function(c){var k=(c.region||'').trim();if(!k)return;(m[c.agentId]=m[c.agentId]||{})[k]=((m[c.agentId]||{})[k]||0)+1});return m;
}
function gpsAgents(){
  var q=GPS.q.trim().toLowerCase(),reg=agentRegions();
  return S.dash.agents.filter(function(a){
    if(GPS.status&&a.status!==GPS.status)return false;
    if(GPS.region&&!(reg[a.id]&&reg[a.id][GPS.region]))return false;
    if(q&&a.name.toLowerCase().indexOf(q)<0)return false;return true})
   .sort(function(a,b){return (b.shiftOpen-a.shiftOpen)||(b.done-a.done)||a.name.localeCompare(b.name)});
}
function pageAgents(page){
  var regions=Array.from(new Set(S.dash.clients.map(function(c){return (c.region||'').trim()}).filter(Boolean))).sort();
  if(GPS.agent&&!S.dash.agents.some(function(a){return a.id===GPS.agent}))GPS.agent=null;
  page.innerHTML='<div class="toolbar">'+agTabs('agents')+'</div><div class="gps">'+
   '<div class="card gps-list"><div class="gps-tools"><input type="search" id="gpsQ" placeholder="Agent qidirish…" value="'+esc(GPS.q)+'">'+
     '<div class="seg" id="gpsSt">'+[['','Hammasi'],['active','Faol'],['late','Kechikkan'],['offline','Yopiq']].map(function(x){return '<button data-s="'+x[0]+'" class="'+(GPS.status===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
     '<select id="gpsRegion" aria-label="Hudud"><option value="">Barcha hududlar</option>'+regions.map(function(r){return '<option'+(GPS.region===r?' selected':'')+'>'+esc(r)+'</option>'}).join('')+'</select></div>'+
     '<div class="list" id="gpsList"></div></div>'+
   '<div class="gps-map"><div class="map" id="agMap"></div>'+
     '<div class="map-legend"><label><input type="checkbox" id="gpsCl"'+(GPS.clients?' checked':'')+'> Mijozlar</label>'+
     [[C.forest,'0–2 kun'],[C.yellow,'3–4 kun'],[C.orange,'5+ kun'],[C.pri,'Rejada'],[C.gray,'Noma’lum']].map(function(x){return '<span><i style="background:'+x[0]+'"></i>'+x[1]+'</span>'}).join('')+'</div></div>'+
   '<div class="card gps-detail" id="gpsDetail"></div></div>';
  bindAgTabs(page);
  $('gpsQ').oninput=debounce(function(){GPS.q=this.value;gpsSave();gpsListRender()},150);
  $('gpsSt').onclick=function(e){var b=e.target.closest('button');if(!b)return;GPS.status=b.dataset.s;gpsSave();$('gpsSt').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});gpsListRender();gpsMarkers(true)};
  $('gpsRegion').onchange=function(){GPS.region=this.value;gpsSave();gpsListRender();gpsMarkers(true);gpsClientLayer(true);if(!GPS.agent)gpsDetail();gpsFitClients()};
  $('gpsCl').onchange=function(){GPS.clients=this.checked;gpsSave();gpsClientLayer(true)};
  var m=makeMap($('agMap'),'agents');S.agMarkers={};S.gpsLayers={};
  if(m){S.gpsLayers.route=L.layerGroup().addTo(m);gpsClientLayer(false);gpsMarkers(true);safeInv(m,'agents',60)}
  gpsListRender();gpsDetail();
}
function agentPopup(a){return '<b>'+esc(a.name)+'</b><br>'+(a.locationSource==='live'?'Jonli GPS':'Oxirgi ma’lum joy')+' · '+ago(a.lastGpsTs)}
function gpsListRender(){
  var rows=gpsAgents(),rep={};(S.dash.reports.today.agents||[]).forEach(function(r){rep[r.agentId]=r});
  $('gpsList').innerHTML=(GPS.agent?'<div class="li click" data-all="1"><div class="tone t-blue" style="width:32px;height:32px">'+ic('users')+'</div><div class="t"><b>Barcha agentlar</b><small>Tanlovni bekor qilish</small></div></div>':'')+
   (rows.length?rows.map(function(a){var st=AG_ST[a.status]||AG_ST.offline,r=rep[a.id]||{},stale=a.shiftOpen&&a.lastGpsTs&&Date.now()/1000-a.lastGpsTs>STALE;
    return '<div class="li click gps-ag'+(GPS.agent===a.id?' on':'')+'" data-gid="'+a.id+'"><span class="ring" style="--ring:'+st[2]+'">'+avatar(a.name,a.photoUrl)+'</span><div class="t"><b>'+esc(a.name)+'</b>'+
      '<small>'+(a.lastGpsTs?(stale?'<span class="warn">'+ic('alert','sm')+' GPS '+ago(a.lastGpsTs)+'</span>':ic('pin','sm')+' '+ago(a.lastGpsTs)):'GPS yo‘q')+'</small>'+
      '<small>'+a.done+' tashrif · '+usd(r.deliveredUsd||0)+' · '+usd(r.paymentsUsd||0)+'</small></div>'+pill('<span class="dot"></span>'+st[0],st[1])+'</div>'}).join(''):emptyState('Agent topilmadi','users'));
  $('gpsList').querySelectorAll('[data-gid]').forEach(function(el){el.onclick=function(){gpsSelect(+el.dataset.gid)}});
  var all=$('gpsList').querySelector('[data-all]');if(all)all.onclick=function(){gpsSelect(null)};
}
function gpsFitClients(){var m=S.maps.agents,l=S.gpsLayers&&S.gpsLayers.clients;if(!m||!l||!l.getBounds)return;var b=l.getBounds();if(b.isValid())m.fitBounds(b,{padding:[40,40],maxZoom:14})}
function gpsSelect(id){
  GPS.agent=id;GPS.day='';gpsSave();gpsListRender();gpsMarkers(false);gpsClientLayer(true);gpsDetail();
  var mk=id&&S.agMarkers[id],m=S.maps.agents;if(mk&&m)m.flyTo(mk.getLatLng(),14,{duration:.5});
}
function gpsMarkers(fit){
  var m=S.maps.agents;if(!m)return;var keep=gpsAgents().map(function(a){return a.id}),pts=[];
  S.dash.agents.forEach(function(a){var mk=S.agMarkers[a.id];
    if(a.lat==null||keep.indexOf(a.id)<0){if(mk){m.removeLayer(mk);delete S.agMarkers[a.id]}return}
    var icon=agentIcon(a,GPS.agent===a.id);
    if(mk){mk.setLatLng([a.lat,a.lon]);mk.setIcon(icon);mk.setPopupContent(agentPopup(a))}
    else S.agMarkers[a.id]=L.marker([a.lat,a.lon],{icon:icon,zIndexOffset:1000,title:a.name,alt:a.name}).addTo(m).bindPopup(agentPopup(a)).on('click',function(){gpsSelect(a.id)});
    pts.push([a.lat,a.lon])});
  if(fit&&!GPS.agent&&pts.length)m.fitBounds(pts,{padding:[50,50],maxZoom:13});
}
function gpsClientLayer(rebuild){
  var m=S.maps.agents;if(!m)return;
  if(S.gpsLayers.clients){m.removeLayer(S.gpsLayers.clients);S.gpsLayers.clients=null}
  if(!GPS.clients)return;
  var grp=window.L&&L.markerClusterGroup?L.markerClusterGroup({showCoverageOnHover:false,maxClusterRadius:46,spiderfyOnMaxZoom:true,
    iconCreateFunction:function(cl){var ms=cl.getAllChildMarkers(),n=ms.length,c={fresh:0,yellow:0,red:0};ms.forEach(function(x){c[x.options.age]=(c[x.options.age]||0)+1});
      var col=c.red?C.orange:c.yellow?C.yellow:C.forest,sz=n<10?34:n<50?40:48;
      return L.divIcon({className:'',html:'<div class="ccl" style="--c:'+col+';width:'+sz+'px;height:'+sz+'px"><b>'+n+'</b>'+(c.red?'<i>'+c.red+'</i>':'')+'</div>',iconSize:[sz,sz]})}}):L.layerGroup();
  S.dash.clients.forEach(function(c){
    if(c.lat==null)return;if(GPS.agent&&c.agentId!==GPS.agent)return;if(GPS.region&&(c.region||'').trim()!==GPS.region)return;
    var col=c.blacklisted?C.ink:(AGE[c.age]||AGE.unknown)[2];
    grp.addLayer(L.marker([c.lat,c.lon],{age:c.age,title:c.name+' — '+(AGE[c.age]||AGE.unknown)[0],alt:c.name,icon:L.divIcon({className:'',html:'<div class="cdot" style="background:'+col+'"></div>',iconSize:[14,14],iconAnchor:[7,7]})})
      .bindTooltip(esc(c.name)+' · '+(AGE[c.age]||AGE.unknown)[0]+(c.debtUsd>0?' · qarz '+usd(c.debtUsd):'')).on('click',function(){openClient(c.id)}));
  });
  S.gpsLayers.clients=grp.addTo(m);
}
async function gpsDetail(){
  var el=$('gpsDetail');if(!el)return;var d=S.dash;
  if(!GPS.agent){
    var by={active:0,late:0,offline:0};d.agents.forEach(function(a){by[a.status]=(by[a.status]||0)+1});
    var stale=d.agents.filter(function(a){return a.shiftOpen&&a.lastGpsTs&&Date.now()/1000-a.lastGpsTs>STALE});
    var cl=d.clients.filter(function(c){return !GPS.region||(c.region||'').trim()===GPS.region}),cnt={fresh:0,yellow:0,red:0,scheduled:0,unknown:0};cl.forEach(function(c){cnt[c.age]=(cnt[c.age]||0)+1});
    el.innerHTML='<div class="card-h"><h3>'+ic('compass')+' Umumiy holat</h3>'+(GPS.region?pill(esc(GPS.region),'p-pri'):'')+'</div>'+
     '<div class="grid g3" style="gap:8px;margin-bottom:14px"><div class="mini"><small>Faol</small><b class="ok">'+by.active+'</b></div><div class="mini"><small>Kechikkan</small><b class="warn">'+by.late+'</b></div><div class="mini"><small>Yopiq</small><b>'+by.offline+'</b></div></div>'+
     (stale.length?'<div class="banner">'+ic('alert','sm')+' '+stale.length+' agentdan GPS kechikmoqda: '+stale.map(function(a){return esc(a.name)+' ('+ago(a.lastGpsTs)+')'}).join(', ')+'</div>':'')+
     '<div class="card-h" style="margin-top:6px"><h3>'+ic('store')+' Mijozlar ('+num(cl.length)+')</h3></div>'+donut([['0–2 kun',cnt.fresh,C.forest],['3–4 kun',cnt.yellow,C.yellow],['5+ kun',cnt.red,C.orange],['Rejada',cnt.scheduled,C.pri],['Noma’lum',cnt.unknown,C.gray]],num(cl.length),'mijoz')+
     '<p class="hint" style="margin-top:12px">Agentni tanlang: uning bugungi marshruti, tashriflari, savdosi va smena vaqtlari shu yerda chiqadi. GPS Telegram jonli lokatsiyasidan keladi va panel har 30 soniyada yangilanadi.</p>';
    if(S.gpsLayers&&S.gpsLayers.route)S.gpsLayers.route.clearLayers();return;
  }
  var a=d.agents.find(function(x){return x.id===GPS.agent});if(!a){GPS.agent=null;return gpsDetail()}
  var st=AG_ST[a.status]||AG_ST.offline,r=(d.reports.today.agents||[]).find(function(x){return x.agentId===a.id})||{};
  var day=GPS.day||today(),isToday=day===today(),stale=a.shiftOpen&&a.lastGpsTs&&Date.now()/1000-a.lastGpsTs>STALE;
  el.innerHTML='<div class="dh" style="margin:0 0 12px">'+avatar(a.name,a.photoUrl,'lg')+'<div style="min-width:0"><h2 style="font-size:18px">'+esc(a.name)+'</h2><div>'+pill('<span class="dot"></span>'+st[0],st[1])+'</div></div></div>'+
   (stale?'<div class="banner">'+ic('alert','sm')+' GPS kechikmoqda: oxirgi nuqta '+ago(a.lastGpsTs)+' ('+hm(a.lastGpsTs)+'). Xaritada oxirgi ma’lum joy ko‘rsatilgan.</div>':'')+
   '<dl class="kv" style="grid-template-columns:120px 1fr;margin-bottom:12px"><dt>Oxirgi GPS</dt><dd>'+(a.lastGpsTs?dt(a.lastGpsTs)+' <span class="muted">('+ago(a.lastGpsTs)+')</span>':'—')+'</dd>'+
   '<dt>Joylashuv</dt><dd>'+(a.lat!=null?(a.locationSource==='live'?'Jonli':'Oxirgi ma’lum')+' · <a href="https://www.google.com/maps/search/?api=1&query='+a.lat+','+a.lon+'" target="_blank" rel="noopener">xaritada ↗</a>':'—')+'</dd>'+
   '<dt>Smena</dt><dd id="gpsShift"><span class="skel-line" aria-label="Yuklanmoqda"></span></dd></dl>'+
   '<div class="toolbar" style="margin-bottom:10px"><div class="seg" id="gpsDay"><button data-d="today" class="'+(isToday?'on':'')+'">Bugun</button><button data-d="pick" class="'+(isToday?'':'on')+'">Kun</button></div><input type="date" id="gpsDate" value="'+day+'" max="'+today()+'" style="width:auto"'+(isToday?' hidden':'')+'></div>'+
   (isToday?'<div class="grid g3" style="gap:8px;margin-bottom:12px"><div class="mini"><small>Realizatsiya</small><b>'+usd(r.deliveredUsd||0)+'</b></div><div class="mini"><small>Yig‘ilgan pul</small><b>'+usd(r.paymentsUsd||0)+'</b></div><div class="mini"><small>Tashrif</small><b>'+a.done+'</b></div>'+
     '<div class="mini"><small>Yangi mijoz</small><b>'+(r.newClients||0)+'</b></div><div class="mini"><small>Ish vaqti</small><b>'+num((r.workSeconds||0)/3600,1)+' soat</b></div><div class="mini"><small>Masofa</small><b>'+num(r.distanceKm||0,1)+' km</b></div></div>':'')+
   '<div id="gpsInfo" class="muted small"></div><div id="gpsVisits"></div>'+
   '<div class="actions" style="margin-top:12px"><button class="btn sm" id="gpsCard">'+ic('file','sm')+' To‘liq karta</button></div>';
  $('gpsCard').onclick=function(){openAgent(a.id)};
  $('gpsDay').onclick=function(e){var b=e.target.closest('button');if(!b)return;if(b.dataset.d==='today'){GPS.day='';gpsSave();gpsDetail()}else{$('gpsDate').hidden=false;$('gpsDay').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)})}};
  $('gpsDate').onchange=function(){GPS.day=this.value===today()?'':this.value;gpsSave();gpsDetail()};
  var dd=await api('agent_period_detail',{agentId:a.id,period:'custom',from:day,to:day}).catch(function(e){if($('gpsInfo'))$('gpsInfo').innerHTML='<span class="bad">'+esc(e.message)+'</span>';if($('gpsShift'))$('gpsShift').innerHTML='<span class="muted">—</span>';return null});
  if(!dd||GPS.agent!==a.id||!$('gpsShift'))return;
  $('gpsShift').innerHTML=dd.shifts.length?dd.shifts.map(function(sh){return hm(sh.start)+' – '+(sh.end?hm(sh.end):'<span class="ok">davom etmoqda</span>')}).join('<br>'):'<span class="muted">Bu kunda smena yo‘q</span>';
  var lay=S.gpsLayers&&S.gpsLayers.route,m=S.maps.agents;if(lay)lay.clearLayers();var bounds=[],km=0;
  dd.route.segments.forEach(function(sg,i){var pts=sg.map(function(p){return [p.lat,p.lon]});bounds=bounds.concat(pts);for(var j=1;j<sg.length;j++)km+=hav(sg[j-1],sg[j]);
    if(lay){if(pts.length>1)L.polyline(pts,{color:C.pri,weight:4,opacity:.85}).addTo(lay).bindTooltip(hm(sg[0].ts)+' – '+hm(sg[sg.length-1].ts));
      L.circleMarker(pts[0],{radius:5,color:'#fff',fillColor:C.forest,fillOpacity:1,weight:2}).addTo(lay).bindTooltip('Boshlanish '+hm(sg[0].ts));
      L.circleMarker(pts[pts.length-1],{radius:5,color:'#fff',fillColor:C.orange,fillOpacity:1,weight:2}).addTo(lay).bindTooltip('Oxirgi nuqta '+hm(sg[sg.length-1].ts))}});
  dd.visits.forEach(function(v){if(v.lat==null||!lay)return;bounds.push([v.lat,v.lon]);L.marker([v.lat,v.lon],{zIndexOffset:900,title:'Tashrif: '+v.name,alt:v.name,icon:L.divIcon({className:'',html:'<div class="vpin">'+ic('check','sm')+'</div>',iconSize:[22,22],iconAnchor:[11,11]})}).addTo(lay).bindTooltip('Tashrif: '+esc(v.name)+' · '+hm(v.ts)).on('click',function(){openClient(v.clientId)})});
  if(m&&bounds.length)m.fitBounds(bounds.concat(a.lat!=null&&isToday?[[a.lat,a.lon]]:[]),{padding:[40,40],maxZoom:15});
  $('gpsInfo').innerHTML=num(dd.route.gpsTotal)+' GPS nuqta · ~'+num(km,1)+' km · '+dd.visitsTotal+' tashrif · '+dd.newClientsTotal+' yangi mijoz';
  var ev=dd.visits.map(function(v){return {ts:v.ts,id:v.clientId,t:VISIT[v.status]||v.status||'Tashrif',n:v.name,ic:'walk'}}).concat(dd.newClients.map(function(c){return {ts:c.ts,id:c.id,t:'Yangi mijoz',n:c.name,ic:'userplus'}})).sort(function(x,y){return y.ts-x.ts});
  $('gpsVisits').innerHTML='<div class="card-h" style="margin:14px 0 4px"><h3>'+ic('walk')+' Tashrif buyurilgan mijozlar</h3></div>'+(ev.length?'<div class="list">'+ev.map(function(e){return '<div class="li click" data-client="'+e.id+'"><div class="t"><b>'+esc(e.n)+'</b><small>'+ic(e.ic,'sm')+' '+esc(e.t)+' · '+hm(e.ts)+'</small></div></div>'}).join('')+'</div>':emptyState('Bu kunda tashrif yo‘q','walk'));
  bindClientLinks($('gpsVisits'));
}
function updateAgentsLive(){
  if(!S.maps.agents||!$('gpsList'))return;
  gpsMarkers(false);gpsListRender();
  if(!GPS.agent)gpsDetail();
}

/* Agent kartasi */
async function openAgent(id){
  openDrawer(''+drawerSkel()+'');
  var a=await run(function(){return api('agent_detail',{agentId:id})});if(!a){closeDrawer();return}
  renderAgent(a);
}
function renderAgent(a){
  var dashA=S.dash&&S.dash.agents.find(function(x){return x.id===a.id})||{};
  var P=a.periods,cols=[['today','Bugun'],['week','7 kun'],['month','30 kun']];
  var stat=function(k,f){return '<tr><td class="muted">'+k+'</td>'+cols.map(function(c){return '<td class="right num">'+f(P[c[0]])+'</td>'}).join('')+'</tr>'};
  var stocks=a.stocks.filter(function(s){return s.qty});
  openDrawer(
   '<div class="dh">'+avatar(a.name,a.photoUrl||dashA.photoUrl,'lg')+'<div><h2>'+esc(a.name)+'</h2><div class="muted">ID '+a.id+' · '+a.clients+' mijoz · '+(a.active?(a.shiftOpen?pill('<span class="dot"></span>Smena ochiq · '+hm(a.shiftStart),'p-ok'):pill('Smena yopiq')):pill('Bloklangan','p-bad'))+'</div></div></div>'+
   '<div class="grid g3" style="margin-bottom:14px">'+
     '<div class="card"><small class="muted">Qo‘lidagi pul</small><b style="display:block;font-size:20px">'+usd(a.cashUsd)+'</b>'+(a.legacyCashUzs?'<small class="muted">+ '+uzs(a.legacyCashUzs)+'</small>':'')+'</div>'+
     '<div class="card"><small class="muted">Kassaga kutilmoqda</small><b style="display:block;font-size:20px">'+usd(a.pendingHandoverUsd)+'</b></div>'+
     '<div class="card"><small class="muted">Oxirgi GPS</small><b style="display:block;font-size:16px">'+(a.lastGpsTs?ago(a.lastGpsTs):'—')+'</b><small class="muted">'+(a.lastGpsTs?dt(a.lastGpsTs):'')+'</small></div>'+
   '</div>'+
   '<div class="card" style="margin-bottom:14px"><div class="card-h"><h3>Marshrut</h3><div class="actions"><div class="seg" id="rtSeg">'+[['last','Oxirgi smena'],['today','Bugun'],['week','7 kun'],['day','Kun']].map(function(x){return '<button data-r="'+x[0]+'" class="'+(x[0]==='last'?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div><input type="date" id="rtDay" value="'+today()+'" max="'+today()+'" style="width:auto" hidden></div></div>'+
     '<div id="drMap" style="height:320px;border-radius:12px;overflow:hidden"></div><div id="drInfo" class="muted small" style="padding-top:8px"></div><div id="drVisits"></div></div>'+
   '<div class="card flush" style="margin-bottom:14px"><table><thead><tr><th>Ko‘rsatkich</th>'+cols.map(function(c){return '<th class="right">'+c[1]+'</th>'}).join('')+'</tr></thead><tbody>'+
     stat('Realizatsiya',function(p){return usd(p.deliveredUsd)})+stat('To‘lovlar',function(p){return usd(p.paymentsUsd)})+stat('Qaytarilgan',function(p){return usd(p.returnsUsd)})+
     stat('Tashriflar',function(p){return p.visits})+stat('Yangi mijozlar',function(p){return p.newClients})+stat('Ish vaqti',function(p){return hours(p.workSeconds)})+stat('Masofa',function(p){return num(p.distanceKm,1)+' km'})+
   '</tbody></table></div>'+
   '<div class="grid g2" style="margin-bottom:14px">'+
     '<div class="card"><div class="card-h"><h3>Qo‘lidagi tovar</h3></div>'+(stocks.length?'<div class="list">'+stocks.map(function(s){return '<div class="li"><div class="t"><b>'+esc(s.name)+'</b></div><b class="num">'+s.qty+'</b></div>'}).join('')+'</div>':'<div class="muted">Tovar yo‘q</div>')+'</div>'+
     '<div class="card"><div class="card-h"><h3>Huquqlar</h3></div>'+a.features.map(function(f){return '<div class="switch"><span>'+esc(f.label)+'</span><button class="tog'+(f.enabled?' on':'')+'" data-feat="'+esc(f.key)+'" data-on="'+(f.enabled?1:0)+'" aria-label="'+esc(f.label)+'"'+(a.active?'':' disabled')+'></button></div>'}).join('')+'</div>'+
   '</div>'+
   '<div class="actions">'+(a.active?'<button class="btn" id="agRename">'+ic('edit')+' Nomini o‘zgartirish</button>':'')+
     (S.primary&&a.active?'<button class="btn" id="agTransfer">'+ic('swap')+' Akkauntni almashtirish</button><button class="btn danger" id="agBlock">'+ic('ban')+' Bloklash</button>':'')+'</div>'+
   (a.audit.length?'<div class="card" style="margin-top:14px"><div class="card-h"><h3>Akkaunt tarixi</h3></div><div class="list">'+a.audit.map(function(x){return '<div class="li"><div class="t"><b>'+esc(x.action)+'</b><small>'+esc(x.actor)+' · '+dt(x.ts)+(x.newId&&x.oldId!==x.newId?' · '+esc(x.oldId)+' → '+esc(x.newId):'')+'</small></div></div>'}).join('')+'</div></div>':''));
  agentRouteMap(a);
  $('drawerBody').querySelectorAll('[data-feat]').forEach(function(b){b.onclick=async function(){
    var on=b.dataset.on!=='1',f=a.features.find(function(x){return x.key===b.dataset.feat});
    if(!await confirmBox('Huquqni o‘zgartirish','<p><b>'+esc(a.name)+'</b> uchun «'+esc(f.label)+'» '+(on?'yoqiladi':'o‘chiriladi')+'.</p>'))return;
    var r=await run(function(){return api('agent_feature_set',{agentId:a.id,feature:f.key,enabled:on,confirm:true})},'Saqlandi');if(r)renderAgent(r.agent)}});
  var rn=$('agRename');if(rn)rn.onclick=async function(){
    var v=await formBox('Agent nomi',[{name:'name',label:'Yangi nom',value:a.name,required:true}]);if(!v)return;
    var p=await run(function(){return api('agent_rename_preview',{agentId:a.id,name:v.name})});if(!p)return;
    if(!await confirmBox('Tasdiqlang','<div class="diff"><s>'+esc(p.oldName||a.name)+'</s> → <ins>'+esc(p.newName)+'</ins></div>'))return;
    var r=await run(function(){return api('agent_rename_commit',{agentId:a.id,name:v.name,confirm:true})},'Nom o‘zgartirildi');if(r){S.dash=null;renderAgent(r.agent)}};
  var tr=$('agTransfer');if(tr)tr.onclick=async function(){
    var v=await formBox('Akkauntni almashtirish',[{name:'newId',label:'Yangi Telegram ID',required:true,placeholder:'123456789'}],'Davom etish','Agent yangi Telegram akkauntga o‘tadi. Mijozlar, qarz va tarix saqlanadi.');if(!v)return;
    var p=await run(function(){return api('agent_transfer_preview',{agentId:a.id,newId:v.newId})});if(!p)return;
    if(!await confirmBox('Tasdiqlang','<p>'+esc(a.name)+': <b>'+esc(p.agentId)+'</b> → <b>'+esc(p.newId)+'</b></p>','Almashtirish',true))return;
    var r=await run(function(){return api('agent_transfer_commit',{agentId:a.id,newId:v.newId,confirm:true})},'Akkaunt almashtirildi');if(r){S.dash=null;renderAgent(r.agent)}};
  var bl=$('agBlock');if(bl)bl.onclick=async function(){
    var p=await run(function(){return api('agent_deactivate_preview',{agentId:a.id})});if(!p)return;
    if(!await confirmBox('Agentni bloklash','<p><b>'+esc(a.name)+'</b> botga kira olmaydi. Tarix saqlanadi.</p>'+(p.warning?'<p class="bad">'+esc(p.warning)+'</p>':''),'Bloklash',true))return;
    var r=await run(function(){return api('agent_deactivate_commit',{agentId:a.id,confirm:true})},'Agent bloklandi');if(r){S.dash=null;renderAgent(r.agent)}};
}
var RT_ST={visit:[C.pri,'Tashrif'],newc:[C.forest,'Yangi mijoz']};
async function agentRouteMap(a){
  var seg=$('rtSeg'),day=$('rtDay');
  seg.onclick=function(e){var b=e.target.closest('button');if(!b)return;seg.querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});day.hidden=b.dataset.r!=='day';drawRoute(a,b.dataset.r)};
  day.onchange=function(){drawRoute(a,'day')};
  drawRoute(a,'last');
}
function drawerMap(a){
  var el=$('drMap');if(!el||!window.L)return null;
  if(S.maps.drawer){try{S.maps.drawer.remove()}catch(e){}}
  var m=L.map(el).setView(a.lat!=null?[a.lat,a.lon]:[40.45,71.6],a.lat!=null?14:9);
  L.tileLayer('/tiles/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(m);S.maps.drawer=m;
  [120,320,600].forEach(function(t){safeInv(m,'drawer',t)});
  return m;
}
async function drawRoute(a,mode){
  var m=drawerMap(a);if(!m)return;var info=$('drInfo'),list=$('drVisits');info.textContent='Yuklanmoqda…';list.innerHTML='';
  var bounds=[];
  if(a.lat!=null&&(mode==='last'||mode==='today'))L.marker([a.lat,a.lon],{title:a.name,alt:a.name,icon:agentIcon(Object.assign({status:a.shiftOpen?'active':'offline'},a))}).addTo(m).bindTooltip('Oxirgi joy · '+ago(a.lastGpsTs));
  if(mode==='last'){
    if(!a.active){info.textContent='Agent bloklangan: oxirgi smena ko‘rsatilmaydi.';return}
    var r=await api('route',{agentId:a.id}).catch(function(e){info.textContent=e.message;return null});
    if(!r||S.maps.drawer!==m)return;
    var pts=r.points.map(function(p){return [p.lat,p.lon]});
    if(pts.length>1){L.polyline(pts,{color:C.pri,weight:4,opacity:.85}).addTo(m);L.circleMarker(pts[0],{radius:6,color:'#fff',fillColor:C.forest,fillOpacity:1,weight:2}).addTo(m).bindTooltip('Boshlanish '+hm(r.points[0].ts));m.fitBounds(pts,{padding:[24,24]})}
    info.textContent=r.start?('Oxirgi smena: '+dt(r.start)+(r.end?' – '+hm(r.end):' (ochiq)')+' · '+pts.length+' GPS nuqta'):'Smena tarixi yo‘q';
    return;
  }
  var args={agentId:a.id,period:mode==='day'?'custom':mode};
  if(mode==='day'){args.from=args.to=$('rtDay').value||today()}
  var d=await api('agent_period_detail',args).catch(function(e){info.textContent=e.message;return null});
  if(!d||S.maps.drawer!==m)return;
  var colors=[C.pri,C.violet,C.cyan,C.ink,C.gray,C.pri];
  d.route.segments.forEach(function(sg,i){var pts=sg.map(function(p){return [p.lat,p.lon]});bounds=bounds.concat(pts);
    if(pts.length>1)L.polyline(pts,{color:colors[i%colors.length],weight:4,opacity:.85}).addTo(m).bindTooltip(hm(sg[0].ts)+' – '+hm(sg[sg.length-1].ts));
    L.circleMarker(pts[0],{radius:5,color:'#fff',fillColor:C.forest,fillOpacity:1,weight:2}).addTo(m).bindTooltip('Boshlanish '+dt(sg[0].ts))});
  var dot=function(x,kind){if(x.lat==null)return;bounds.push([x.lat,x.lon]);
    L.circleMarker([x.lat,x.lon],{radius:7,color:'#fff',weight:2,fillColor:RT_ST[kind][0],fillOpacity:.95}).addTo(m).bindTooltip(RT_ST[kind][1]+': '+esc(x.name)+' · '+hm(x.ts)).on('click',function(){openClient(x.clientId||x.id)})};
  d.visits.forEach(function(v){dot(v,'visit')});d.newClients.forEach(function(c){dot(c,'newc')});
  if(bounds.length)m.fitBounds(bounds,{padding:[24,24],maxZoom:16});
  var km=0;d.route.segments.forEach(function(sg){for(var i=1;i<sg.length;i++)km+=hav(sg[i-1],sg[i])});
  var lbl=String(d.label||'').split(' – ');info.innerHTML=esc(lbl.length===2&&lbl[0]===lbl[1]?lbl[0]:d.label)+' · '+num(d.route.gpsTotal)+' GPS nuqta'+(d.route.sampled?' ('+d.route.gpsShown+' tasi chizildi)':'')+' · ~'+num(km,1)+' km · '+d.visitsTotal+' tashrif · '+d.newClientsTotal+' yangi mijoz'+
    ' &nbsp; '+legend([['Tashrif',C.pri],['Yangi mijoz',C.forest]]).replace('class="legend"','class="legend" style="display:inline-flex"');
  var ev=d.visits.map(function(v){return {ts:v.ts,id:v.clientId,t:ic('walk','sm')+' '+(VISIT[v.status]||v.status||'Tashrif'),n:v.name,note:v.note}}).concat(d.newClients.map(function(c){return {ts:c.ts,id:c.id,t:ic('userplus','sm')+' Yangi mijoz',n:c.name,note:c.address}})).sort(function(x,y){return y.ts-x.ts});
  list.innerHTML=ev.length?'<div class="list" style="margin-top:10px;max-height:320px;overflow:auto">'+ev.map(function(e){return '<div class="li click" data-client="'+e.id+'"><div class="t"><b>'+esc(e.n)+'</b><small>'+e.t+' · '+dt(e.ts)+(e.note?' · '+esc(e.note):'')+'</small></div></div>'}).join('')+'</div>':'<div class="muted small" style="padding-top:8px">Bu davrda tashrif yoki yangi mijoz yo‘q.</div>';
  bindClientLinks(list);
}
function hav(p,q){var R=6371,r=Math.PI/180,dl=(q.lat-p.lat)*r,dn=(q.lon-p.lon)*r,x=Math.sin(dl/2)*Math.sin(dl/2)+Math.cos(p.lat*r)*Math.cos(q.lat*r)*Math.sin(dn/2)*Math.sin(dn/2);return 2*R*Math.asin(Math.sqrt(x))}

/* ----- Agentlar boshqaruvi ----- */
var TM={p:'today',q:'',sort:'realization',dir:-1,sel:[],from:'',to:''};
async function pageTeam(page){
  if(TM.p==='custom'&&!TM.from)TM.p='today';
  var d=S.dash,ck='tmc'+TM.from+TM.to,cust=TM.p==='custom'?S.cache[ck]:null;
  /* «Davr»: agentlar natijasi va topshirilgan pul tanlangan kunlar bo'yicha serverdan olinadi. */
  if(TM.p==='custom'&&!cust){page.innerHTML='<div class="toolbar">'+agTabs('team')+periodBar('tmP',TM)+'</div><div class="grid g4">'+'<div class="skel"></div>'.repeat(4)+'</div>';
    bindAgTabs(page);bindPeriod('tmP',TM,function(){pageTeam(page)});
    try{var pr=await Promise.all([api('period_report',{period:'custom',from:TM.from,to:TM.to}),api('cash_period',{from:TM.from,to:TM.to})]);S.cache[ck]={agents:pr[0].agents||[],tx:pr[1].transactions}}
    catch(e){if(S.page==='team'){page.querySelector('.grid').outerHTML=errState(e.message);page.querySelector('[data-retry]').onclick=function(){pageTeam(page)}}return}
    if(S.page==='team')pageTeam(page);return}
  var rep=cust?cust.agents:((d.reports[TM.p]||{}).agents||[]),since=cust?0:d.todayStart-({today:0,week:6,month:29}[TM.p])*86400;
  /* Agentlardagi pul alohida so'rovdan keladi: yuklanmoqda / xato / tayyor holatlari aniq ko'rsatiladi (abadiy «…» emas). */
  var cashKey='tmcash',cst=S.cache[cashKey],ex=cst&&!cst.error?cst:null,cerr=cst&&cst.error;
  var cashCell=function(v,sub){return ex?v+(sub||''):cerr?'<span class="muted" title="'+esc(cerr)+'">—</span>':'<span class="skel-line" aria-label="Yuklanmoqda"></span>'};
  var handed={};(cust?cust.tx:d.transactions).forEach(function(t){if(t.type==='handover'&&t.state==='accepted'&&(t.acceptedTs||t.ts)>=since){var h=handed[t.agentId]=handed[t.agentId]||[0,0];h[0]+=t.amountUsd;h[1]+=t.amountUzs||0}});
  var debt={},ov={};d.clients.forEach(function(c){if(c.debtUsd>0)debt[c.agentId]=(debt[c.agentId]||0)+c.debtUsd;if(c.age==='red'&&!c.blacklisted)ov[c.agentId]=(ov[c.agentId]||0)+1});
  var rows=d.agents.map(function(a){var r=rep.find(function(x){return x.agentId===a.id})||{},cash=ex?(ex.agents.find(function(x){return x.agentId===a.id})||{cashUsd:0,cashUzs:0,pendingUsd:0,pendingUzs:0}):null,h=handed[a.id]||[0,0];
    return {a:a,id:a.id,name:a.name,status:a.status,realization:r.deliveredUsd||0,payments:r.paymentsUsd||0,rate:(r.deliveredUsd>0?r.paymentsUsd/r.deliveredUsd*100:null),visits:r.visits||0,newClients:r.newClients||0,
      work:r.workSeconds||0,km:r.distanceKm||0,cashUsd:cash?cash.cashUsd:null,cashUzs:cash?cash.cashUzs:null,pendingUsd:cash?cash.pendingUsd:0,handedUsd:h[0],handedUzs:h[1],debt:debt[a.id]||0,overdue:ov[a.id]||0,clients:a.clients}});
  var q=TM.q.trim().toLowerCase();rows=rows.filter(function(r){return !q||r.name.toLowerCase().indexOf(q)>=0});
  var key=TM.sort,dir=TM.dir;rows.sort(function(x,y){var a=x[key],b=y[key];if(a==null)a=-1e15;if(b==null)b=-1e15;return (typeof a==='string'?a.localeCompare(b):a-b)*dir});
  var sum=function(k){return rows.reduce(function(t,r){return t+(r[k]||0)},0)};
  var leaders=rows.slice().sort(function(x,y){return y.realization-x.realization}).filter(function(r){return r.realization>0}).slice(0,3),LC=['','',''];
  var th=function(k,label,cls){return '<th class="sort '+(cls||'')+(TM.sort===k?(TM.dir>0?' asc':' desc'):'')+'" data-k="'+k+'">'+label+'</th>'};
  page.innerHTML=
   '<div class="toolbar">'+agTabs('team')+periodBar('tmP',TM)+
     '<input type="search" id="tmQ" placeholder="Agent qidirish…" value="'+esc(TM.q)+'"><span class="grow"></span>'+
     '<button class="btn sm" id="tmCmp"'+(TM.sel.length<2?' disabled':'')+'>'+ic('chart','sm')+' Taqqoslash ('+TM.sel.length+')</button><button class="btn sm" id="tmExp">'+ic('download','sm')+' Excel</button><button class="btn ink sm" id="tmAdd">'+ic('userplus','sm')+' Agent qo‘shish</button></div>'+
   '<div class="grid g4 kpis" style="margin-bottom:16px">'+
     kpi('📦','Realizatsiya',usd(sum('realization')),rows.length+' agent')+kpi('💰','Yig‘ilgan pul',usd(sum('payments')),sum('realization')>0?Math.round(sum('payments')/sum('realization')*100)+'% undirildi':'')+
     kpi('💵','Agentlardagi pul',ex?usd(sum('cashUsd')):cerr?'—':'<span class="skel-line lg" aria-label="Yuklanmoqda"></span>',ex?'+ '+uzs(sum('cashUzs'))+(sum('pendingUsd')?' · kutilmoqda '+usd(sum('pendingUsd')):''):cerr?'<span class="bad">Yuklab bo‘lmadi.</span> <a href="#" id="tmCashRetry">Qayta urinish</a>':'Hisoblanmoqda')+
     kpi('🏦','Kassirga topshirildi',usd(sum('handedUsd')),(sum('handedUzs')?uzs(sum('handedUzs'))+' · ':'')+'kassir qabul qilgan')+
   '</div>'+
   (leaders.length?'<div class="grid g3 kpis sm" style="margin-bottom:16px">'+leaders.map(function(r,i){return '<div class="card lift click '+LC[i]+'" data-agent="'+r.id+'" style="display:grid;gap:10px"><div class="card-h" style="margin:0"><small>'+(i+1)+'-o‘rin · '+(TM.p==='custom'?periodLabel(TM):{today:'bugun',week:'7 kun',month:'30 kun'}[TM.p])+'</small>'+pill('<span class="dot"></span>'+(AG_ST[r.status]||AG_ST.offline)[0])+'</div><div class="cell">'+avatar(r.name,r.a.photoUrl)+'<b style="font-size:17px">'+esc(r.name)+'</b></div><div class="stat-strip" style="gap:18px"><div><b>'+usd(r.realization)+'</b><small>realizatsiya</small></div><div><b>'+usd(r.payments)+'</b><small>pul</small></div><div><b>'+r.visits+'</b><small>tashrif</small></div></div></div>'}).join('')+'</div>':'')+
   '<div class="card flush"><div class="tbl-wrap"><table><thead><tr><th style="width:36px"></th>'+th('name','Agent')+th('realization','Realizatsiya','right')+th('payments','Pul','right')+th('rate','Undiruv','right')+th('visits','Tashrif','right')+th('newClients','Yangi','right')+th('work','Ish vaqti','right')+th('km','Masofa','right')+th('cashUsd','Qo‘lidagi pul','right')+th('handedUsd','Topshirildi','right')+th('debt','Portfel qarzi','right')+'</tr></thead><tbody>'+
    (rows.length?rows.map(function(r){var st=AG_ST[r.status]||AG_ST.offline;return '<tr class="click" data-agent="'+r.id+'"><td><input type="checkbox" data-sel="'+r.id+'" aria-label="Taqqoslash uchun tanlash"'+(TM.sel.indexOf(r.id)>=0?' checked':'')+'></td>'+
      '<td><div class="cell"><span class="ring" style="--ring:'+st[2]+'">'+avatar(r.name,r.a.photoUrl)+'</span><div class="t"><b>'+esc(r.name)+'</b><small>'+st[0]+' · '+r.clients+' mijoz'+(r.overdue?' · <span class="bad">'+r.overdue+' kechikkan</span>':'')+'</small></div></div></td>'+
      '<td class="right num">'+usd(r.realization)+'</td><td class="right num">'+usd(r.payments)+'</td><td class="right">'+(r.rate==null?'<span class="muted">—</span>':pill(Math.round(r.rate)+'%',r.rate>=70?'p-ok':r.rate>=40?'p-warn':'p-bad'))+'</td>'+
      '<td class="right num">'+r.visits+'</td><td class="right num">'+r.newClients+'</td><td class="right num">'+num(r.work/3600,1)+' soat</td><td class="right num">'+num(r.km,1)+' km</td>'+
      '<td class="right num">'+cashCell(usd(r.cashUsd),(r.cashUzs?'<br><small class="muted">'+uzs(r.cashUzs)+'</small>':'')+(r.pendingUsd?'<br><small class="warn">kutilmoqda '+usd(r.pendingUsd)+'</small>':''))+'</td>'+
      '<td class="right num">'+usd(r.handedUsd)+(r.handedUzs?'<br><small class="muted">'+uzs(r.handedUzs)+'</small>':'')+'</td><td class="right num '+(r.debt>0?'bad':'')+'">'+usd(r.debt)+'</td></tr>'}).join(''):'<tr><td colspan="12">'+emptyState('Agent topilmadi','users')+'</td></tr>')+
   '</tbody></table></div><div class="pager"><span>«Qo‘lidagi pul» — hozirgi holat; «Topshirildi» — tanlangan davrda kassir qabul qilgan pul; «Portfel qarzi» — agent mijozlarining musbat qoldiqlari.</span></div></div>';
  bindAgTabs(page);
  bindPeriod('tmP',TM,function(){pageTeam(page)});
  $('tmQ').oninput=debounce(function(){TM.q=this.value;pageTeam(page);var i=$('tmQ');i.focus();i.setSelectionRange(i.value.length,i.value.length)},250);
  page.querySelectorAll('th.sort').forEach(function(h){h.onclick=function(){var k=h.dataset.k;if(TM.sort===k)TM.dir=-TM.dir;else{TM.sort=k;TM.dir=k==='name'?1:-1}pageTeam(page)}});
  page.querySelectorAll('[data-sel]').forEach(function(cb){cb.onclick=function(e){e.stopPropagation();var id=+cb.dataset.sel,i=TM.sel.indexOf(id);if(i>=0)TM.sel.splice(i,1);else{if(TM.sel.length>=3){cb.checked=false;toast('Ko‘pi bilan 3 ta agent',true);return}TM.sel.push(id)}
    $('tmCmp').disabled=TM.sel.length<2;$('tmCmp').innerHTML=ic('chart','sm')+' Taqqoslash ('+TM.sel.length+')'}});
  $('tmCmp').onclick=function(){var pick=rows.filter(function(r){return TM.sel.indexOf(r.id)>=0});var M=[['Realizatsiya','realization',usd],['Yig‘ilgan pul','payments',usd],['Undiruv','rate',function(v){return v==null?'—':Math.round(v)+'%'}],['Tashrif','visits',num],['Yangi mijoz','newClients',num],['Ish vaqti','work',function(v){return num(v/3600,1)+' soat'}],['Masofa','km',function(v){return num(v,1)+' km'}],['Qo‘lidagi pul','cashUsd',function(v){return v==null?'—':usd(v)}],['Topshirildi','handedUsd',usd],['Portfel qarzi','debt',usd]];
    modal('<h3>Agentlarni taqqoslash · '+(TM.p==='custom'?periodLabel(TM):{today:'bugun',week:'7 kun',month:'30 kun'}[TM.p])+'</h3><div class="tbl-wrap" style="margin-top:10px"><table><thead><tr><th></th>'+pick.map(function(r){return '<th class="right">'+esc(r.name)+'</th>'}).join('')+'</tr></thead><tbody>'+M.map(function(m){var vals=pick.map(function(r){return r[m[1]]}),best=m[1]==='debt'?Math.min.apply(null,vals.filter(function(v){return v!=null})):Math.max.apply(null,vals.filter(function(v){return v!=null}));
      return '<tr><td class="muted">'+m[0]+'</td>'+pick.map(function(r){var v=r[m[1]];return '<td class="right num">'+(v!=null&&v===best&&pick.length>1?'<b class="ok">'+m[2](v)+'</b>':m[2](v))+'</td>'}).join('')+'</tr>'}).join('')+'</tbody></table></div><div class="foot"><button class="btn" data-m="cancel">Yopish</button></div>')};
  $('tmExp').onclick=function(){exportRows(fileSlug()+'-agentlar-kpi',['Agent','Holat','Realizatsiya USD','Pul USD','Undiruv %','Tashrif','Yangi mijoz','Ish vaqti soat','Masofa km','Qo‘lidagi USD','Qo‘lidagi so‘m','Topshirildi USD','Topshirildi so‘m','Portfel qarzi USD'],rows.map(function(r){return [r.name,(AG_ST[r.status]||AG_ST.offline)[0],r.realization,r.payments,r.rate==null?'':Math.round(r.rate),r.visits,r.newClients,Math.round(r.work/360)/10,r.km,r.cashUsd==null?'':r.cashUsd,r.cashUzs==null?'':r.cashUzs,r.handedUsd,r.handedUzs,r.debt]}))};
  $('tmAdd').onclick=function(){location.hash='staff'};
  bindAgentLinks(page);
  if($('tmCashRetry'))$('tmCashRetry').onclick=function(e){e.preventDefault();delete S.cache[cashKey];pageTeam(page)};
  if(!cst&&!S.tmCashBusy){S.tmCashBusy=true;var res;
    try{var e=await api('executive',{period:'today'});res=e&&e.agentsCash?e.agentsCash:{error:'Server agentlardagi pulni qaytarmadi.'}}
    catch(err){res={error:err.message}}
    finally{S.tmCashBusy=false}
    if(!TOKEN)return;S.cache[cashKey]=res;if(S.page==='team'&&$('tmP'))pageTeam(page)}
}

/* ----- Mijozlar ----- */
var CL={q:'',age:'',agent:'',debt:'',region:'',sort:'lastTs',dir:-1,page:0,view:store('rw-clview')||'table'};
var PAGE_SIZE=50;
function pageClients(page){
  if(S.cache.clientAge){CL.age=S.cache.clientAge;delete S.cache.clientAge}
  var d=S.dash,agents=d.agents.slice().sort(function(a,b){return a.name.localeCompare(b.name)});
  var regions=Array.from(new Set(d.clients.map(function(c){return c.region}).filter(Boolean))).sort();
  var cnt={fresh:0,yellow:0,red:0},dn=0,dsum=0;d.clients.forEach(function(c){if(cnt[c.age]!=null)cnt[c.age]++;if(c.debtUsd>0){dn++;dsum+=c.debtUsd}});
  var stat=function(age,icon,label,val,sub,color){return '<button class="st cl-stat'+(CL.age===age&&age?' on':'')+'" data-age="'+age+'"><span class="round-btn" style="color:'+color+'">'+ic(icon,'sm')+'</span><div><b>'+val+'</b><small>'+label+(sub?' · '+sub:'')+'</small></div></button>'};
  page.innerHTML='<div class="card" style="margin-bottom:14px"><div class="stat-strip" id="clStats">'+
     stat('','store','Jami mijozlar',num(d.clientCount),'',C.ink)+stat('fresh','checkc','Faol',num(cnt.fresh),'0–2 kun',C.forest)+stat('yellow','clock','E’tibor kerak',num(cnt.yellow),'3–4 kun',C.yellow)+
     stat('red','alert','Passiv',num(cnt.red),'5+ kun tashrifsiz',C.orange)+'<button class="st cl-stat'+(CL.debt==='debt'?' on':'')+'" data-debt="1"><span class="round-btn" style="color:'+C.orange+'">'+ic('receipt','sm')+'</span><div><b>'+usd(dsum)+'</b><small>'+num(dn)+' qarzdor</small></div></button>'+
   '</div></div>'+(d.clientsTruncated?'<div class="banner">Ro‘yxatda oxirgi '+num(d.clients.length)+' ta mijoz ko‘rsatilgan (jami '+num(d.clientCount)+'). To‘liq ro‘yxat uchun Excel eksportdan foydalaning.</div>':'')+
   '<div class="toolbar"><input type="search" id="clQ" placeholder="Qidirish: nom, telefon, manzil…  ( / )" value="'+esc(CL.q)+'">'+
   '<select id="clAgent" aria-label="Agent"><option value="">Barcha agentlar</option>'+agents.map(function(a){return '<option value="'+a.id+'"'+(String(CL.agent)===String(a.id)?' selected':'')+'>'+esc(a.name)+'</option>'}).join('')+'</select>'+
   '<select id="clDebt" aria-label="Qarz">'+[['','Qarz: barchasi'],['debt','Qarzi bor'],['big','Qarz $100+'],['none','Qarzsiz'],['black','Qora ro‘yxat']].map(function(o){return '<option value="'+o[0]+'"'+(CL.debt===o[0]?' selected':'')+'>'+o[1]+'</option>'}).join('')+'</select>'+
   (regions.length?'<select id="clRegion" aria-label="Hudud"><option value="">Barcha hududlar</option>'+regions.map(function(r){return '<option'+(CL.region===r?' selected':'')+'>'+esc(r)+'</option>'}).join('')+'</select>':'')+
   '<span class="grow"></span><div class="seg" id="clView"><button data-v="table" class="'+(CL.view==='table'?'on':'')+'">'+ic('list')+' Jadval</button><button data-v="cards" class="'+(CL.view==='cards'?'on':'')+'">'+ic('store')+' Kartalar</button><button data-v="map" class="'+(CL.view==='map'?'on':'')+'">'+ic('map')+' Xarita</button></div>'+
   '</div>'+
   '<div class="toolbar"><div class="seg" id="clAge"></div><span class="grow"></span><span class="muted small" id="clCount"></span><button class="btn sm" id="clView2" title="Ekrandagi (filtrlangan) qatorlar">'+ic('download','sm')+' Excel</button><button class="btn sm" id="clXlsx" title="Barcha mijozlar, to‘liq hisobot">'+ic('file','sm')+' Hammasi</button><button class="btn sm" id="clPdf" title="Barcha mijozlar, PDF">'+ic('file','sm')+' PDF</button></div>'+
   '<div id="clBody"></div>';
  var upd=function(){CL.page=0;clientsBody()};
  $('clQ').oninput=debounce(function(){CL.q=this.value;upd()},150);
  $('clAgent').onchange=function(){CL.agent=this.value;upd()};
  $('clDebt').onchange=function(){CL.debt=this.value;upd()};
  if($('clRegion'))$('clRegion').onchange=function(){CL.region=this.value;upd()};
  $('clStats').onclick=function(e){var b=e.target.closest('.cl-stat');if(!b)return;if(b.dataset.debt){CL.debt=CL.debt==='debt'?'':'debt';CL.sort=CL.debt?'debtUsd':CL.sort;CL.dir=-1}else CL.age=CL.age===b.dataset.age?'':b.dataset.age;CL.page=0;pageClients(page)};
  $('clView').onclick=function(e){var b=e.target.closest('button');if(!b)return;CL.view=b.dataset.v;store('rw-clview',CL.view);$('clView').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});clientsBody()};
  $('clAge').onclick=function(e){var b=e.target.closest('button');if(!b)return;CL.age=b.dataset.a;upd()};
  $('clXlsx').onclick=function(){exportAll('xlsx',this)};
  $('clView2').onclick=function(){var rows=sortedClients(filteredClients(false));exportRows(fileSlug()+'-mijozlar',['ID','Mijoz','Shaxs','Telefon','Manzil','Hudud','Agent','Qarz USD','Oxirgi aloqa','Kun','Reja','Holat','Qora ro‘yxat'],rows.map(function(c){return [c.id,c.name,c.person,c.phone,c.address,c.region,c.agent,c.debtUsd,c.lastTs?dday(c.lastTs):'',c.days==null?'':c.days,c.followup||'',(AGE[c.age]||AGE.unknown)[0],c.blacklisted?'Ha':'']}))};$('clPdf').onclick=function(){exportAll('pdf',this)};
  clientsBody();
}
async function exportAll(fmt,btn){btn.disabled=true;toast('Fayl tayyorlanmoqda…');var r=await run(function(){return api('all_clients_export',{format:fmt})});btn.disabled=false;if(r)download(r)}
function filteredClients(ignoreAge){
  var q=CL.q.trim().toLowerCase();
  return S.dash.clients.filter(function(c){
    if(!ignoreAge&&CL.age&&c.age!==CL.age)return false;
    if(CL.agent&&String(c.agentId)!==String(CL.agent))return false;
    if(CL.region&&c.region!==CL.region)return false;
    if(CL.debt==='debt'&&!(c.debtUsd>0))return false;if(CL.debt==='big'&&!(c.debtUsd>=100))return false;
    if(CL.debt==='none'&&c.debtUsd>0)return false;if(CL.debt==='black'&&!c.blacklisted)return false;
    if(q&&(c.name+' '+c.person+' '+c.phone+' '+c.address+' '+c.agent+' '+c.region+' #'+c.id).toLowerCase().indexOf(q)<0)return false;
    return true});
}
function clientsBody(){
  var base=filteredClients(true),counts={'':base.length};base.forEach(function(c){counts[c.age]=(counts[c.age]||0)+1});
  $('clAge').innerHTML=[['','Barchasi'],['fresh','0–2 kun'],['yellow','3–4 kun'],['red','5+ kun'],['scheduled','Rejada']].map(function(x){return '<button data-a="'+x[0]+'" class="'+(CL.age===x[0]?'on':'')+'">'+x[1]+'<b>'+(counts[x[0]]||0)+'</b></button>'}).join('');
  var rows=filteredClients(false),debt=rows.reduce(function(s,c){return s+(c.debtUsd||0)},0);
  $('clCount').textContent=num(rows.length)+' ta mijoz · qarz '+usd(debt);
  var body=$('clBody');
  if(S.maps.clients){try{S.maps.clients.remove()}catch(e){}delete S.maps.clients}
  if(CL.view==='cards'){
    sortedClients(rows);var N=24,pages=Math.max(1,Math.ceil(rows.length/N));if(CL.page>=pages)CL.page=pages-1;var sl=rows.slice(CL.page*N,(CL.page+1)*N);
    var tone2={fresh:'',yellow:'c-yellow',red:'c-orange',scheduled:'',unknown:''};
    body.innerHTML=(sl.length?'<div class="ccards">'+sl.map(function(c){var ag=AGE[c.age]||AGE.unknown,tc=c.blacklisted?'c-ink':tone2[c.age]||'';
      return '<article class="card ccard lift '+tc+'" data-client="'+c.id+'" tabindex="0"><div class="top"><small>'+(c.lastTs?'Aloqa '+dday(c.lastTs):'Aloqa yo‘q')+'</small>'+(tc?'':pill('<span class="dot"></span>'+ag[0],ag[1]))+'</div>'+
        '<div class="cell">'+(c.thumbUrl?'<span class="av sq" style="background-image:url(\''+esc(c.thumbUrl)+'\')"></span>':avatar(c.name,'','sq'))+'<div class="t"><b class="nm">'+esc(c.name)+'</b><small>'+esc(c.region||c.address||'')+'</small></div></div>'+
        '<small>'+ic('users','sm')+' '+esc(c.agent)+(c.phone?' · '+esc(c.phone.split(/[,\/\n]/)[0]):'')+'</small>'+
        '<div class="money"><div><small>Qarz</small><b>'+(c.debtUsd?usd(c.debtUsd):'—')+'</b></div><small>'+(c.days!=null?c.days+' kun':'')+(c.blacklisted?' · qora ro‘yxat':'')+'</small></div></article>'}).join('')+'</div>':emptyState('Mijoz topilmadi','store'))+
      (pages>1?'<div class="pager" style="border:0"><span>'+(CL.page*N+1)+'–'+Math.min(rows.length,(CL.page+1)*N)+' / '+num(rows.length)+'</span><span class="actions"><button class="btn sm" id="pgPrev"'+(CL.page?'':' disabled')+'>‹ Oldingi</button><button class="btn sm" id="pgNext"'+(CL.page<pages-1?'':' disabled')+'>Keyingi ›</button></span></div>':'');
    if($('pgPrev'))$('pgPrev').onclick=function(){CL.page--;clientsBody();scrollTo(0,0)};if($('pgNext'))$('pgNext').onclick=function(){CL.page++;clientsBody();scrollTo(0,0)};
    bindClientLinks(body);body.querySelectorAll('.ccard').forEach(function(el){el.onkeydown=function(e){if(e.key==='Enter'){el.click()}}});return;
  }
  if(CL.view==='map'){
    body.innerHTML='<div class="map" id="clMap" style="height:calc(100vh - 230px)"></div>';
    var m=makeMap($('clMap'),'clients');if(!m)return;var pts=[];
    rows.forEach(function(c){if(c.lat==null)return;pts.push([c.lat,c.lon]);
      L.circleMarker([c.lat,c.lon],{radius:7,color:'#fff',weight:2,fillColor:c.blacklisted?C.ink:(AGE[c.age]||AGE.unknown)[2],fillOpacity:.95}).addTo(m)
       .bindTooltip(esc(c.name)+(c.debtUsd>0?' · '+usd(c.debtUsd):'')).on('click',function(){openClient(c.id)})});
    if(pts.length)m.fitBounds(pts,{padding:[30,30],maxZoom:15,animate:false});safeInv(m,'clients',50);return;
  }
  sortedClients(rows);
  var pages=Math.max(1,Math.ceil(rows.length/PAGE_SIZE));if(CL.page>=pages)CL.page=pages-1;
  var slice=rows.slice(CL.page*PAGE_SIZE,(CL.page+1)*PAGE_SIZE);
  var th=function(k,label,cls){return '<th class="sort '+(cls||'')+(CL.sort===k?(CL.dir>0?' asc':' desc'):'')+'" data-k="'+k+'">'+label+'</th>'};
  /* Muhim ustunlar (Qarz, Holat) mijoz nomidan keyin turadi; ikkilamchi ustunlar tor ekranda yashirinadi
     (ularning ma'lumoti nom ostida ko'rinadi), jadval gorizontal suriladi va mijoz ustuni yopishqoq. */
  body.innerHTML='<div class="card flush"><div class="tbl-wrap"><table class="tbl-clients"><thead><tr>'+th('name','Mijoz','col-sticky')+th('debtUsd','Qarz','right')+th('age','Holat')+th('lastTs','Oxirgi aloqa','col-last')+th('agent','Agent','col-agent')+th('region','Hudud','col-region')+'<th class="col-phone">Telefon</th></tr></thead><tbody>'+
   (slice.length?slice.map(function(c){var ag=AGE[c.age]||AGE.unknown;return '<tr class="click" data-client="'+c.id+'"><td class="col-sticky"><div class="cell">'+(c.thumbUrl?'<span class="av sq" style="background-image:url(\''+esc(c.thumbUrl)+'\')"></span>':avatar(c.name,'','sq'))+'<div class="t"><b>'+esc(c.name)+(c.blacklisted?' '+ic('ban','sm bad')+'<span class="sr-only">qora ro‘yxatda</span>':'')+'</b><small>'+esc(c.person||c.address||'')+'</small><small class="only-narrow">'+esc([c.agent,c.region,c.lastTs?'aloqa '+dday(c.lastTs):''].filter(Boolean).join(' · '))+'</small></div></div></td>'+
     '<td class="right num '+(c.debtUsd>0?'bad':'')+'">'+(c.debtUsd?'<b>'+usd(c.debtUsd)+'</b>':'<span class="muted">—</span>')+'</td><td>'+pill('<span class="dot"></span>'+ag[0],ag[1])+'</td>'+
     '<td class="col-last"><span class="num">'+(c.lastTs?dday(c.lastTs):'—')+'</span><br><small class="muted">'+(c.days!=null?c.days+' kun':'')+(c.followup?' · reja '+esc(c.followup):'')+'</small></td>'+
     '<td class="col-agent">'+esc(c.agent)+'</td><td class="col-region">'+esc(c.region||'—')+'</td><td class="num col-phone">'+(c.phone?'<a href="tel:'+esc(c.phone.split(/[,\/\n]/)[0].trim())+'">'+esc(c.phone)+'</a>':'—')+'</td></tr>'}).join(''):'<tr><td colspan="7">'+emptyState('Mijoz topilmadi','store')+'</td></tr>')+
   '</tbody></table></div>'+(pages>1?'<div class="pager"><span>'+(CL.page*PAGE_SIZE+1)+'–'+Math.min(rows.length,(CL.page+1)*PAGE_SIZE)+' / '+num(rows.length)+'</span><span class="actions"><button class="btn sm" id="pgPrev"'+(CL.page?'':' disabled')+'>'+ic('chevron','sm flip')+' Oldingi</button><button class="btn sm" id="pgNext"'+(CL.page<pages-1?'':' disabled')+'>Keyingi '+ic('chevron','sm')+'</button></span></div>':'')+'</div>';
  body.querySelectorAll('th.sort').forEach(function(h){h.onclick=function(){var k=h.dataset.k;if(CL.sort===k)CL.dir=-CL.dir;else{CL.sort=k;CL.dir=(k==='name'||k==='agent'||k==='region')?1:-1}clientsBody()}});
  if($('pgPrev'))$('pgPrev').onclick=function(){CL.page--;clientsBody();scrollTo(0,0)};
  if($('pgNext'))$('pgNext').onclick=function(){CL.page++;clientsBody();scrollTo(0,0)};
  bindClientLinks(body);
}

function sortedClients(rows){
  var key=CL.sort,dir=CL.dir,txt=key==='name'||key==='agent'||key==='region';
  return rows.sort(function(a,b){var x=a[key],y=b[key];if(x==null)x=txt?'':-1;if(y==null)y=txt?'':-1;return (typeof x==='string'?x.localeCompare(y):x-y)*dir});
}
/* Mijoz kartasi */
async function openClient(id){
  openDrawer(''+drawerSkel()+'');
  var c=await run(function(){return api('client_detail',{clientId:id})});if(!c){closeDrawer();return}
  renderClient(c,'events');
}
function renderClient(c,tab){
  var t=c.totals;
  var tabs=[['events','Harakatlar',c.events.length],['debt','Qarz tarixi',''],['visits','Tashriflar',c.visits.length],['stock','Qoldiq',c.stocks.filter(function(s){return s.qty}).length],['edits','O‘zgarishlar',c.edits.length+(c.blacklistLog||[]).length]];
  var tabBody={
    events:function(){return c.events.length?'<table><thead><tr><th>Sana</th><th>Amal</th><th>Tovar</th><th class="right">Miqdor</th><th class="right">Summa</th><th>Kim</th></tr></thead><tbody>'+c.events.map(function(e){return '<tr><td class="num">'+dt(e.ts)+'</td><td>'+(KIND[e.kind]||esc(e.kind))+'</td><td>'+esc(e.product||'—')+(e.note?'<br><small class="muted">'+esc(e.note)+'</small>':'')+'</td><td class="right num">'+(e.qty||'—')+'</td><td class="right num">'+(e.amountUsd?usd(e.amountUsd):e.amountUzs?uzs(e.amountUzs):'—')+'</td><td>'+esc(e.actor)+'</td></tr>'}).join('')+'</tbody></table>':'<div class="empty">Harakat yo‘q</div>'},
    debt:function(){
      // Yurgan qoldiq: hozirgi qarzdan orqaga qarab (oxirgi 120 ta harakat) — qarz, avans va to'lovlarni bitta ketma-ketlikda ko'rsatadi.
      var fin=c.events.filter(function(e){return e.kind==='delivery'||e.kind==='payment'||e.kind==='return'});
      if(!fin.length)return emptyState('Moliyaviy harakat yo‘q','receipt');
      var bal=c.debtUsd,rows=fin.map(function(e){var sign=e.kind==='delivery'?1:-1,after=bal;bal=Math.round((bal-sign*e.amountUsd)*100)/100;return {e:e,sign:sign,after:after}});
      var ser=rows.slice().reverse().map(function(r){return {day:dday(r.e.ts),debtUsd:r.after}});
      return '<div style="padding:16px 18px 4px">'+legend([['Qoldiq (qarz)',C.orange]])+areaChart(ser,['debtUsd'],[C.orange],usd,['Qoldiq'])+'</div>'+
        (fin.length>=c.events.length&&c.events.length>=120?'<div class="banner" style="margin:0 18px 10px">Oxirgi 120 ta harakat ko‘rsatilgan; to‘liq tarix akt sverkada.</div>':'')+
        '<table><thead><tr><th>Sana</th><th>Harakat</th><th class="right">Summa</th><th class="right">Qoldiq</th></tr></thead><tbody>'+rows.map(function(r){return '<tr><td class="num">'+dt(r.e.ts)+'</td><td>'+(KIND[r.e.kind]||esc(r.e.kind))+(r.e.product?' <small class="muted">'+esc(r.e.product)+'</small>':'')+'</td><td class="right num '+(r.sign>0?'':'ok')+'">'+(r.sign>0?'+':'−')+usd(r.e.amountUsd)+'</td><td class="right num '+(r.after>0?'bad':'ok')+'">'+(r.after<0?'avans '+usd(-r.after):usd(r.after))+'</td></tr>'}).join('')+'</tbody></table>';
    },
    visits:function(){return c.visits.length?'<div class="list" style="padding:0 18px">'+c.visits.map(function(v){return '<div class="li">'+(v.thumbUrl?'<a href="'+esc(v.photoUrl)+'" target="_blank" rel="noopener"><span class="av sq" style="background-image:url(\''+esc(v.thumbUrl)+'\');width:48px;height:48px"></span></a>':'<span class="av sq">'+ic('walk')+'</span>')+'<div class="t"><b>'+esc(VISIT[v.status]||v.status||'Tashrif')+'</b><small>'+esc(v.note)+'</small><small>'+esc(v.actor)+' · '+dt(v.ts)+(v.followup?' · qayta: '+esc(v.followup):'')+'</small></div></div>'}).join('')+'</div>':'<div class="empty">Tashrif yo‘q</div>'},
    stock:function(){var s=c.stocks.filter(function(x){return x.qty});return s.length?'<table><thead><tr><th>Tovar</th><th class="right">Do‘konda</th></tr></thead><tbody>'+s.map(function(x){return '<tr><td>'+esc(x.name)+'</td><td class="right num">'+x.qty+'</td></tr>'}).join('')+'</tbody></table>':'<div class="empty">Do‘konda tovar qoldig‘i yo‘q</div>'},
    edits:function(){var rows=c.edits.map(function(e){return '<div class="li"><div class="t"><b>'+esc(FIELD[e.field]||e.field)+'</b><div class="diff"><s>'+esc(e.old||'—')+'</s> → <ins>'+esc(e.new||'—')+'</ins></div><small>'+esc(e.actor)+' · '+dt(e.ts)+'</small></div></div>'}).concat((c.blacklistLog||[]).map(function(l){return '<div class="li"><div class="t"><b>'+(l.action==='on'||l.action==='add'?ic('ban','sm')+' Qora ro‘yxatga':ic('checkc','sm')+' Qora ro‘yxatdan chiqdi')+'</b><small>'+esc(l.reason)+'</small><small>'+esc(l.actor)+' · '+dt(l.ts)+'</small></div></div>'}));return rows.length?'<div class="list" style="padding:0 18px">'+rows.join('')+'</div>':'<div class="empty">O‘zgarish yo‘q</div>'}
  };
  var live=S.dash&&S.dash.clients.find(function(x){return x.id===c.id}),ag=live?AGE[live.age]||AGE.unknown:null;
  var act=live?(live.age==='fresh'?['Faol','p-ok']:live.age==='yellow'?['E’tibor kerak','p-warn']:live.age==='red'?['Passiv','p-bad']:live.age==='scheduled'?['Rejada','p-pri']:['Noma’lum','']):null;
  var phone1=(c.phone||'').split(/[,\/\n]/)[0].trim();
  var row=function(icon,label,val,extra){return '<div class="crm-row">'+ic(icon,'sm')+'<div><small>'+label+'</small><span>'+val+'</span></div>'+(extra||'')+'</div>'};
  openDrawer(
   '<div class="crm-head"><div class="card crm-profile">'+
     '<div class="crm-ava"><span class="ring" style="--ring:'+(ag?ag[2]:C.gray)+';--p:100%;padding:4px">'+(c.thumbUrl?'<span class="av" style="width:96px;height:96px;background-image:url(\''+esc(c.thumbUrl)+'\')"></span>':avatar(c.name,'','" style="width:96px;height:96px;font-size:34px'))+'</span></div>'+
     '<h2>'+esc(c.name)+'</h2><small class="muted">'+esc(c.person||'')+(c.person&&c.region?' · ':'')+esc(c.region||'')+'</small>'+
     '<div class="actions" style="justify-content:center;margin:10px 0 4px">'+(act?pill('<span class="dot"></span>'+act[0],act[1]):'')+(c.blacklisted?pill(ic('ban','sm')+' Qora ro‘yxat','p-bad'):'')+pill(ic('users','sm')+' '+esc(c.agent))+'</div>'+
     '<div class="crm-acts">'+(phone1?'<a class="round-btn" href="tel:'+esc(phone1)+'" title="Qo‘ng‘iroq">'+ic('phone','sm')+'</a>':'')+(c.lat!=null?'<a class="round-btn" href="https://www.google.com/maps/search/?api=1&query='+c.lat+','+c.lon+'" target="_blank" rel="noopener" title="Xaritada">'+ic('pin','sm')+'</a>':'')+
       '<button class="round-btn" id="cEdit" title="Tahrirlash">'+ic('edit','sm')+'</button><button class="round-btn" id="cXlsx" title="Akt sverka Excel">'+ic('download','sm')+'</button><button class="round-btn" id="cPdf" title="Akt sverka PDF">'+ic('file','sm')+'</button>'+
       '<button class="round-btn" id="cBlack" title="'+(c.blacklisted?'Qora ro‘yxatdan chiqarish':'Qora ro‘yxatga')+'">'+ic(c.blacklisted?'checkc':'ban','sm')+'</button><button class="round-btn" id="cDel" title="O‘chirish" style="color:var(--bad)">'+ic('trash','sm')+'</button></div>'+
   '</div><div class="card crm-detail"><div class="card-h"><h3>Batafsil ma’lumot</h3><small class="muted">#'+c.id+'</small></div>'+
     row('store','Do‘kon',esc(c.shopName||'—'))+row('users','Mijoz',esc(c.person||'—'))+row('phone','Telefon',c.phone?esc(c.phone):'—')+row('pin','Manzil',esc(c.address||'—'))+
     row('calendar','To‘lov sanasi',esc(c.paymentDue||'—'))+row('clock','Oxirgi aloqa',live&&live.lastTs?dt(live.lastTs)+' <span class="muted">('+live.days+' kun)</span>':'—')+row('note','Izoh',esc(c.comment||'—'))+row('sparkle','Qo‘shilgan',dt(c.createdTs))+
   '</div></div>'+
   (c.blacklisted&&c.blacklistReason?'<div class="banner">Qora ro‘yxat sababi: '+esc(c.blacklistReason)+'</div>':'')+
   '<div class="grid g4 kpis" style="margin:14px 0">'+
     '<div class="card kpi '+(c.debtUsd>0?'c-orange':'c-forest')+'"><div><small>Qarz</small><b>'+usd(c.debtUsd)+'</b><em>'+(c.debtUsd>0?'to‘lanmagan':'yopiq')+'</em></div></div>'+
     '<div class="card kpi"><div><small>Berilgan</small><b>'+usd(t.deliveredUsd)+'</b><em>'+num(t.deliveredQty)+' dona</em></div></div>'+
     '<div class="card kpi"><div><small>To‘langan</small><b>'+usd(t.paidUsd)+'</b><em>'+(t.deliveredUsd>0?Math.round(t.paidUsd/t.deliveredUsd*100)+'%':'')+'</em></div></div>'+
     '<div class="card kpi"><div><small>Qaytarilgan</small><b>'+usd(t.returnedUsd)+'</b><em>sotildi '+num(t.soldQty)+' dona</em></div></div>'+
   '</div>'+
   (c.photoUrl?'<a href="'+esc(c.photoUrl)+'" target="_blank" rel="noopener"><img class="photo" style="margin-bottom:6px" src="'+esc(c.photoUrl)+'" alt="Do‘kon rasmi"></a>':'')+
   '<div class="tabs" id="cTabs">'+tabs.map(function(x){return '<button data-t="'+x[0]+'" class="'+(tab===x[0]?'on':'')+'">'+x[1]+' <span class="muted">'+x[2]+'</span></button>'}).join('')+'</div>'+
   '<div class="card flush"><div class="tbl-wrap" style="max-height:none">'+tabBody[tab]()+'</div></div>');
  $('cTabs').onclick=function(e){var b=e.target.closest('button');if(b)renderClient(c,b.dataset.t)};
  var exp=function(fmt,btn){btn.disabled=true;run(function(){return api('client_export',{clientId:c.id,format:fmt})}).then(function(r){btn.disabled=false;if(r)download(r)})};
  $('cXlsx').onclick=function(){exp('xlsx',this)};$('cPdf').onclick=function(){exp('pdf',this)};
  $('cEdit').onclick=async function(){
    var cur={name:c.person,shop_name:c.shopName,phone:c.phone,address:c.address,comment:c.comment,payment_due:c.paymentDue};
    var v=await formBox('Mijozni tahrirlash',[{name:'shop_name',label:'Do‘kon nomi',value:cur.shop_name},{name:'name',label:'Mijoz ismi',value:cur.name},{name:'phone',label:'Telefon',value:cur.phone},{name:'address',label:'Manzil',value:cur.address},{name:'payment_due',label:'To‘lov sanasi (YYYY-MM-DD)',value:cur.payment_due},{name:'comment',label:'Izoh',value:cur.comment,area:true}],'Davom etish');
    if(!v)return;var values={};Object.keys(v).forEach(function(k){if(String(cur[k]||'')!==v[k].trim())values[k]=v[k]});
    if(!Object.keys(values).length){toast('Hech narsa o‘zgarmadi');return}
    var p=await run(function(){return api('client_edit_preview',{clientId:c.id,values:values})});if(!p)return;
    if(!await confirmBox('O‘zgarishlarni tasdiqlang',p.changes.map(function(ch){return '<div class="diff"><b>'+esc(FIELD[ch.field]||ch.field)+':</b> <s>'+esc(ch.old||'—')+'</s> → <ins>'+esc(ch.new||'—')+'</ins></div>'}).join(''),'Saqlash'))return;
    var r=await run(function(){return api('client_edit_commit',{clientId:c.id,values:p.values,confirm:true})},'Mijoz ma’lumotlari saqlandi');
    if(r){S.dash=null;renderClient(r.client,tab)}};
  $('cBlack').onclick=async function(){
    var on=!c.blacklisted,reason='';
    if(on){var v=await formBox('Qora ro‘yxatga qo‘shish',[{name:'reason',label:'Sabab',required:true,area:true}],'Qo‘shish','Mijoz bazada va xaritada qoladi, agentlar unga tovar bera olmaydi.');if(!v)return;reason=v.reason}
    else if(!await confirmBox('Qora ro‘yxatdan chiqarish','<p><b>'+esc(c.name)+'</b> yana oddiy mijoz bo‘ladi.</p>'))return;
    var r=await run(function(){return api('client_blacklist',{clientId:c.id,on:on,reason:reason})});
    if(r){toast(r.message||'Saqlandi');S.dash=null;openClient(c.id)}};
  $('cDel').onclick=async function(){
    var p=await run(function(){return api('client_delete_preview',{clientId:c.id})});if(!p)return;
    if(!await confirmBox('Mijozni o‘chirish','<p><b>'+esc(p.name)+'</b> · qarz '+usd(p.debtUsd)+' · '+p.eventCount+' harakat · '+p.visitCount+' tashrif'+(p.openTasks?' · '+p.openTasks+' ochiq vazifa':'')+'</p><p class="muted">'+esc(p.warning)+'</p>','O‘chirish',true))return;
    var r=await run(function(){return api('client_delete_commit',{clientId:c.id,confirm:true})},'Mijoz arxivga o‘tkazildi');
    if(r){closeDrawer();S.dash=null;render(true)}};
}

/* ----- Kassa ----- */
var KS={f:'',p:'week',q:'',from:'',to:'',sort:'ts',dir:-1};
/* Yagona davr filtri: Bugun · Hafta · Oy · Davr (ikki sana). st={p,from,to}; onChange() o'zgarganda chaqiriladi. */
var PERIODS4=[['today','Bugun'],['week','Hafta'],['month','Oy'],['custom','Davr']];
function periodBar(id,st){return '<div class="seg" id="'+id+'" role="group" aria-label="Davr">'+PERIODS4.map(function(x){return '<button data-p="'+x[0]+'" class="'+(st.p===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
  '<span id="'+id+'C" class="actions period-c"'+(st.p==='custom'?'':' hidden')+'><input type="date" id="'+id+'F" value="'+esc(st.from||today())+'" max="'+today()+'" aria-label="Boshlanish sanasi"><input type="date" id="'+id+'T" value="'+esc(st.to||today())+'" max="'+today()+'" aria-label="Tugash sanasi"><button class="btn pri sm" id="'+id+'G">Ko‘rsatish</button></span>'}
function bindPeriod(id,st,onChange){
  $(id).onclick=function(e){var b=e.target.closest('button');if(!b)return;
    if(b.dataset.p==='custom'){$(id).querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});$(id+'C').hidden=false;$(id+'F').focus();return}
    st.p=b.dataset.p;onChange()};
  $(id+'G').onclick=function(){var f=$(id+'F').value,t=$(id+'T').value;if(!f||!t){toast('Ikkala sanani tanlang',true);return}if(f>t){var x=f;f=t;t=x}st.p='custom';st.from=f;st.to=t;onChange()};
}
function periodLabel(st){return st.p==='custom'?(dday(Date.parse(st.from+'T00:00:00+05:00')/1000)+' – '+dday(Date.parse(st.to+'T00:00:00+05:00')/1000)):({today:'Bugun',week:'Oxirgi 7 kun',month:'Oxirgi 30 kun'}[st.p])}
/* Qarzdorlik yoshi: mijoz qarzi qancha kundan beri to'lanmagan (eng eski berilgan tovardan boshlab — FIFO).
   Har guruh: kun oralig'i, izoh, ulush chizig'i (rang xavf darajasi), mijozlar soni va summa. */
function agingBlock(aging,go){
  var atot=aging.reduce(function(a,b){return a+b.usd},0);
  if(!atot)return emptyState('To‘lanmagan qarz yo‘q','checkc');
  var tone=['neutral','warn','late','bad'],hint=['Yangi qarz — normal holat','E’tibor bering — eslatish vaqti','Kechikkan — undirish kerak','Jiddiy kechikkan — xavfli qarz'];
  var old=aging.slice(1).reduce(function(a,b){return a+b.usd},0);
  return '<p class="aging-sum">'+(old>0?'<b class="bad">'+usd(old)+'</b> qarz 30 kundan ortiq to‘lanmagan ('+Math.round(old/atot*100)+'%).':'Barcha qarz <b>30 kundan yangi</b> — kechikkan qarz yo‘q.')+'</p>'+
    '<div class="stack aging-stack" aria-hidden="true">'+aging.map(function(b,i){return b.usd>0?'<i class="ag-'+tone[i]+'" style="flex:'+b.usd+'"></i>':''}).join('')+'</div>'+
    '<div class="aging-list">'+aging.map(function(b,i){var pc=Math.round(b.usd/atot*100);
      return '<div class="ag-row"><span class="ag-dot ag-'+tone[i]+'"></span><div class="t"><b>'+esc(b.label)+' kun</b><small>'+hint[i]+' · '+num(b.clients)+' mijoz · '+pc+'%</small></div><b class="num">'+usd(b.usd)+'</b><div class="ag-bar"><i class="ag-'+tone[i]+'" style="width:'+pc+'%"></i></div></div>'}).join('')+'</div>';
}
var DEBT={q:'',page:0};
/* ----- Moliya va qarzdorlik (1817 Revenue & Invoices) ----- */
async function pageCash(page){
  if(KS.p==='custom'&&!KS.from)KS.p='week';
  var d=S.dash,c=d.cash,w=c.wallets||{},per={today:'today',week:'d7',month:'d30',custom:'custom'}[KS.p];
  page.innerHTML=
   '<div class="toolbar">'+periodBar('ksP',KS)+'<span class="muted small">'+esc(periodLabel(KS))+'</span><span class="grow"></span><span class="muted small">USD va so‘m alohida yuritiladi; USD ekvivalenti faqat saqlangan kurs bilan.</span></div>'+
   '<div class="card" style="margin-bottom:16px"><div class="stat-strip" id="finStrip">'+
     '<div class="st"><span class="round-btn">'+ic('wallet','sm')+'</span><div><b>'+usd(c.balanceUsd)+'</b><small>Kassa qoldig‘i (USD ekv.)</small></div></div>'+
     '<div class="st"><span class="round-btn">'+ic('hourglass','sm')+'</span><div><b>'+usd(c.pendingUsd)+(c.pendingCount?'<span class="pill-badge y">'+c.pendingCount+'</span>':'')+'</b><small>Kassirda tasdiq kutmoqda</small></div></div>'+
     '<div class="st"><span class="round-btn">'+ic('receipt','sm')+'</span><div><b>'+usd(d.summary.debtUsd)+'</b><small>Mijozlar qarzi'+(d.summary.advanceUsd?' · avans '+usd(d.summary.advanceUsd):'')+'</small></div></div>'+
     '<div class="st" id="finAgents"><span class="round-btn">'+ic('users','sm')+'</span><div><b><span class="skel-line lg" aria-label="Yuklanmoqda"></span></b><small>Agentlardagi pul</small></div></div>'+
   '</div></div>'+
   '<div class="grid g4 kpis" style="margin-bottom:16px">'+
     '<div class="card kpi">'+tone('cash','blue')+'<div><small>Naqd so‘m</small><b>'+uzs(w.cashUzs)+'</b><em>kirim '+uzs(w.inCashUzs)+' · chiqim '+uzs(w.outCashUzs)+'</em></div></div>'+
     '<div class="card kpi">'+tone('dollar','blue')+'<div><small>Naqd dollar</small><b>'+usd(w.cashUsd)+'</b><em>kirim '+usd(w.inCashUsd)+' · chiqim '+usd(w.outCashUsd)+'</em></div></div>'+
     '<div class="card kpi">'+tone('card','blue')+'<div><small>Karta so‘m</small><b>'+uzs(w.cardUzs)+'</b><em>kirim '+uzs(w.inCardUzs)+(w.outCardUzs?' · chiqim '+uzs(w.outCardUzs):'')+'</em></div></div>'+
     '<div class="card kpi">'+tone('bank','blue')+'<div><small>Karta dollar</small><b>'+usd(w.cardUsd)+'</b><em>kirim '+usd(w.inCardUsd)+'</em></div></div>'+
   '</div>'+
   '<div id="finBody"><div class="grid g-main" style="margin-bottom:16px"><div class="skel" style="height:300px"></div><div class="skel" style="height:300px"></div></div></div>'+
   '<div class="card flush" style="margin-bottom:16px"><div class="card-h"><h3>'+ic('receipt')+' Qarzdor mijozlar</h3><div class="acts"><input type="search" id="debtQ" placeholder="Mijoz, agent, hudud…" value="'+esc(DEBT.q)+'" style="width:220px;border-radius:999px"><button class="btn sm" id="debtExp">'+ic('download','sm')+' Excel</button></div></div><div id="debtBody" style="margin-top:10px"></div></div>'+
   '<div class="card flush" style="margin-bottom:16px"><div class="card-h"><h3>'+ic('list')+' Kassa harakatlari</h3><div class="acts"><div class="seg" id="ksF">'+[['','Hammasi'],['in','Kirim'],['out','Chiqim'],['pending','Kutilmoqda']].map(function(x){return '<button data-f="'+x[0]+'" class="'+(KS.f===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
     '<input type="search" id="ksQ" placeholder="Qidirish…" value="'+esc(KS.q)+'" style="width:180px;border-radius:999px"><span class="muted small" id="ksSum"></span><button class="btn sm" id="ksExp">'+ic('download','sm')+' Excel</button></div></div><div id="ksList" style="margin-top:10px"></div></div>'+
   '<div class="grid g2"><div class="card"><div class="card-h"><h3>'+ic('coins')+' Xarajatlar tarkibi</h3></div><div id="ksBrk"></div></div><div class="card flush"><div class="card-h"><h3>'+ic('swap')+' Konvertatsiyalar</h3><span class="muted small">kassir</span></div><div id="finConv" style="margin-top:10px"><div class="skel" style="height:120px;margin:0 16px 16px"></div></div></div></div>';
  bindPeriod('ksP',KS,function(){S.cashTx=null;pageCash(page)});
  $('ksF').onclick=function(e){var b=e.target.closest('button');if(!b)return;KS.f=b.dataset.f;$('ksF').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});cashList()};
  $('ksQ').oninput=debounce(function(){KS.q=this.value;cashList()},150);
  $('ksExp').onclick=function(){var ST={pending:'Kutilmoqda',accepted:'Qabul qilindi',rejected:'Rad etildi',expense:'Chiqim'};
    exportRows(fileSlug()+'-kassa',['Sana','Turi','Agent / oluvchi','Kategoriya','Izoh','Kassir','USD','So‘m','Kurs','Holat'],S.cashRows.map(function(t){var h=t.type==='handover';return [dt(t.acceptedTs||t.ts),h?'Kirim':'Chiqim',h?t.agent:t.recipient,h?'':t.category,t.note||'',t.cashier||'',(h?1:-1)*t.amountUsd,t.amountUzs||'',t.rateUzsPerUsd||'',ST[t.state]||t.state]}))};
  $('debtQ').oninput=debounce(function(){DEBT.q=this.value;DEBT.page=0;debtList()},150);
  $('debtExp').onclick=function(){exportRows(fileSlug()+'-qarzdorlar',['ID','Mijoz','Telefon','Hudud','Agent','Qarz USD','Oxirgi aloqa','Kun','Holat'],debtRows().map(function(x){return [x.id,x.name,x.phone,x.region,x.agent,x.debtUsd,x.lastTs?dday(x.lastTs):'',x.days==null?'':x.days,(AGE[x.age]||AGE.unknown)[0]]}))};
  cashList();debtList();
  if(KS.p==='custom'&&!(S.cashTx&&S.cashTx.key===KS.from+KS.to)){$('ksList').innerHTML='<div class="skel" style="height:200px;margin:0 16px 16px"></div>';
    try{var cp=await api('cash_period',{from:KS.from,to:KS.to});S.cashTx={key:KS.from+KS.to,rows:cp.transactions}}catch(e){if(S.page==='cash'&&$('ksList'))$('ksList').innerHTML=errState(e.message);S.cashTx=null}
    if(S.page!=='cash'||!$('ksList'))return;if(S.cashTx)cashList()}
  var ex,exErr;try{ex=await api('executive',KS.p==='custom'?{period:'custom',from:KS.from,to:KS.to,group:'auto'}:{period:per,group:'auto'})}catch(e){exErr=e.message}
  if(S.page!=='cash'||!$('finBody'))return;
  if(!ex){if(!TOKEN)return;
    $('finAgents').innerHTML='<span class="round-btn">'+ic('users','sm')+'</span><div><b class="muted">—</b><small>Agentlardagi pul · yuklab bo‘lmadi</small></div>';
    $('finConv').innerHTML=emptyState('Yuklab bo‘lmadi','alert');
    $('finBody').innerHTML=errState(exErr||'');$('finBody').querySelector('[data-retry]').onclick=function(){pageCash(page)};return}
  var ac=ex.agentsCash;
  $('finAgents').innerHTML='<span class="round-btn">'+ic('users','sm')+'</span><div><b>'+usd(ac.cashUsd)+' <span class="muted" style="font-size:14px">+ '+uzs(ac.cashUzs)+'</span></b><small>Agentlardagi pul (USD va so‘m alohida)</small></div>';
  $('finBody').innerHTML=
   '<div class="grid g-main" style="margin-bottom:16px">'+
     '<div class="card"><div class="card-h"><div><h3>'+ic('trend')+' Tushum dinamikasi</h3><div class="stat-strip" style="margin-top:8px"><div><b style="font-size:26px">'+usd(ex.kpis[1].value)+'</b><small>'+esc(ex.range.label)+' yig‘ilgan pul · realizatsiya '+usd(ex.kpis[0].value)+'</small></div></div></div></div>'+
       legend([['Yig‘ilgan pul',C.forest],['Realizatsiya',C.pri]])+'<div style="margin-top:8px">'+areaChart(ex.series,['paymentsUsd','realizationUsd'],[C.forest,C.pri],usd,['Yig‘ilgan pul','Realizatsiya'])+'</div></div>'+
     '<div class="card"><div class="card-h"><div><h3>'+ic('clock')+' Qarzdorlik yoshi</h3><small class="muted">Qarz qancha kundan beri to‘lanmagan · bugungi holat</small></div></div>'+agingBlock(ex.debtAging)+'</div>'+
   '</div>'+
   '<div class="card flush" style="margin-bottom:16px"><div class="card-h"><h3>'+ic('users')+' Agentlardagi pul</h3><span class="muted small">kassir tasdiqlamagan topshiriqlar alohida</span></div><div class="tbl-wrap" style="margin-top:10px">'+
     (ac.agents.length?'<table><thead><tr><th>Agent</th><th class="right">Naqd dollar</th><th class="right">Naqd so‘m</th><th class="right">Kassirda kutilmoqda</th></tr></thead><tbody>'+ac.agents.map(function(a){return '<tr class="click" data-agent="'+a.agentId+'"><td><b>'+esc(a.agent)+'</b></td><td class="right num">'+usd(a.cashUsd)+'</td><td class="right num">'+uzs(a.cashUzs)+'</td><td class="right num">'+(a.pendingUsd||a.pendingUzs?usd(a.pendingUsd)+(a.pendingUzs?' + '+uzs(a.pendingUzs):''):'—')+'</td></tr>'}).join('')+
       '<tr><td><b>Jami</b></td><td class="right num"><b>'+usd(ac.cashUsd)+'</b></td><td class="right num"><b>'+uzs(ac.cashUzs)+'</b></td><td class="right num"><b>'+usd(ac.pendingUsd)+(ac.pendingUzs?' + '+uzs(ac.pendingUzs):'')+'</b></td></tr></tbody></table>':emptyState('Agentlarda pul yo‘q','users'))+'</div></div>';
  bindAgentLinks($('finBody'));
  $('finConv').innerHTML=ex.conversions.length?'<div class="tbl-wrap"><table><thead><tr><th>Sana</th><th>Manba</th><th class="right">Berildi</th><th class="right">Olindi</th><th class="right">Kurs</th></tr></thead><tbody>'+ex.conversions.map(function(x){var f=function(cur,v){return cur==='USD'?usd(v):uzs(v)};return '<tr><td class="num">'+dt(x.ts)+'<br><small class="muted">'+esc(x.cashier)+'</small></td><td>'+(x.payFrom==='card'?'Karta':'Naqd')+'</td><td class="right num">'+f(x.from,x.amountFrom)+'</td><td class="right num">'+f(x.to,x.amountTo)+'</td><td class="right num">'+num(x.rate)+'</td></tr>'}).join('')+'</tbody></table></div>':emptyState('Bu davrda konvertatsiya yo‘q','swap');
  if(!$('cbCard'))page.insertAdjacentHTML('beforeend','<div class="card" id="cbCard" style="margin-top:16px"><div class="loading">Kassa jurnali…</div></div>');
  cashbookCard();
}
/* ----- Kassa: hisoblar (naqd/karta/bank), kirim, o'tkazma, bekor qilish, kun yopish, jurnal (server: cashbook.py) ----- */
var CB={group:'',data:null};
var CB_GROUP={'':'Hammasi',income:'Kirimlar',expense:'Chiqimlar',internal:'Ichki harakat'};
function cbMoney(n,c){return c==='USD'?usd(n/100):uzs(n)}
async function cashbookCard(){
  var el=$('cbCard');if(!el)return;
  var d;try{d=CB.data=await api('cashbook',{op:'view'})}catch(e){if($('cbCard'))el.innerHTML=errState(e.message);return}
  if(!$('cbCard'))return;renderCashbook(el,d);
}
function renderCashbook(el,d){
  var b=d.balances,can=d.can||{};
  var rows=d.journal.filter(function(x){return !CB.group||x.group===CB.group||(CB.group==='expense'&&x.group==='expense')});
  el.innerHTML='<div class="card-h"><h3>'+ic('wallet')+' Kassa hisoblari va jurnal</h3><div class="actions">'+
      (can.income?'<button class="btn sm pri" data-cb="client">'+ic('in','sm')+' Mijozdan to‘lov</button><button class="btn sm" data-cb="income">'+ic('in','sm')+' Boshqa kirim</button>':'')+
      (can.transfer?'<button class="btn sm" data-cb="transfer">'+ic('swap','sm')+' O‘tkazma</button>':'')+
      (can.close?'<button class="btn sm" data-cb="close">'+ic('checkc','sm')+' Kunni yopish</button>':'')+'</div></div>'+
    '<div class="grid g3" style="margin-bottom:14px">'+d.pockets.map(function(p){return '<div class="card kpi">'+tone(p[0]==='cash'?'cash':p[0]==='card'?'card':'bank','blue')+'<div><small>'+esc(p[1])+'</small><b>'+uzs(b[p[0]+'_uzs'])+'</b><em>'+usd(b[p[0]+'_usd']/100)+'</em></div></div>'}).join('')+'</div>'+
    '<p class="hint" style="margin:-4px 0 12px">O‘tkazma va konvertatsiya — ichki harakat: daromad yoki xarajat emas. Oylik, dividend va ta’minotchi to‘lovi jurnalda alohida turda.</p>'+
    '<div class="seg" id="cbSeg" style="margin-bottom:10px">'+Object.keys(CB_GROUP).map(function(k){return '<button data-g="'+k+'" class="'+(CB.group===k?'on':'')+'">'+CB_GROUP[k]+'</button>'}).join('')+'</div>'+
    '<div class="tbl-wrap"><table><thead><tr><th>Sana</th><th>Tur</th><th>Kimdan → kimga</th><th class="right">Summa</th><th>Kim</th><th>Holat</th></tr></thead><tbody>'+
    (rows.length?rows.slice(0,120).map(function(x,i){return '<tr class="click" data-cbi="'+d.journal.indexOf(x)+'"><td class="num">'+dt(x.ts)+'</td><td>'+esc(x.label)+'</td><td class="small">'+esc(x.from||'—')+' → '+esc(x.to||'—')+'</td><td class="right num'+(x.group==='expense'?' bad':x.group==='income'?' ok':'')+'">'+cbMoney(x.amount,x.currency)+'</td><td class="small muted">'+esc(x.who)+'</td><td>'+(x.status==='active'?'':pill('Bekor qilingan','p-bad'))+'</td></tr>'}).join(''):'<tr><td colspan="6">'+emptyState('Harakat yo‘q','list')+'</td></tr>')+
    '</tbody></table></div>'+
    (d.closings.length?'<details class="mod-hist" style="margin-top:12px"><summary class="small muted">Kun yopishlar tarixi</summary><div class="tbl-wrap"><table><thead><tr><th>Kun</th><th>Hisob</th><th class="right">Tizimda</th><th class="right">Sanaldi</th><th class="right">Farq</th><th>Kim</th></tr></thead><tbody>'+
      d.closings.map(function(c){return '<tr><td class="num">'+esc(c.day)+'</td><td>'+esc(c.pocketLabel)+' '+c.currency+'</td><td class="right num">'+cbMoney(c.system,c.currency)+'</td><td class="right num">'+cbMoney(c.counted,c.currency)+'</td><td class="right num'+(c.diff?' bad':' ok')+'">'+(c.diff>0?'+':c.diff<0?'−':'')+cbMoney(Math.abs(c.diff),c.currency)+'</td><td class="small muted">'+esc(c.who)+'</td></tr>'}).join('')+'</tbody></table></div></details>':'');
  $('cbSeg').onclick=function(e){var x=e.target.closest('button');if(!x)return;CB.group=x.dataset.g;renderCashbook(el,d)};
  el.querySelectorAll('[data-cbi]').forEach(function(tr){tr.onclick=function(){cbDetail(d.journal[+tr.dataset.cbi],can)}});
  var call=async function(args,msg){var r=await run(function(){return api('cashbook',Object.assign({requestId:rid()},args))},msg);if(r){CB.data=r;S.dash=null;renderCashbook(el,r)}return r};
  var pockOpts=d.pockets;
  el.querySelectorAll('[data-cb]').forEach(function(x){x.onclick=async function(){var k=x.dataset.cb,v;
    if(k==='income'){v=await formBox('Kassaga kirim',[{name:'pocket',label:'Qaysi hisobga',options:pockOpts},{name:'currency',label:'Valyuta',options:[['UZS','So‘m'],['USD','Dollar']]},{name:'amount',label:'Summa',type:'number',step:'any',required:true},{name:'category',label:'Kirim turi',options:d.incomeCategories.filter(function(c){return c!==d.clientPayment}).map(function(c){return [c,c]})},{name:'counterparty',label:'Kimdan',required:true},{name:'note',label:'Izoh'}],'Kirim qilish','Agentdan pul qabul qilish — kassir ilovasida (topshiriq). Bu yerda boshqa tushumlar.');
      if(v&&await confirmBox('Kirimni tasdiqlang','<p><b>'+cbMoney(v.currency==='USD'?Math.round(parseFloat(v.amount)*100):+v.amount,v.currency)+'</b> → '+esc((pockOpts.find(function(p){return p[0]===v.pocket})||['',''])[1])+'<br>Kimdan: '+esc(v.counterparty)+'</p>','Tasdiqlash'))call(Object.assign({op:'income'},v),'Kirim saqlandi')}
    else if(k==='client'){
      if(!d.debtors.length){toast('Qarzi bor mijoz yo‘q.',false);return}
      v=await formBox('Mijozdan to‘lov — kassaga to‘g‘ridan',[{name:'clientId',label:'Mijoz (qarzi bilan)',options:d.debtors.map(function(c){return [String(c.id),c.name+(c.agent?' · '+c.agent:'')+' — qarz '+usd(c.debtUsd/100)]})},{name:'pocket',label:'Qaysi hisobga',options:pockOpts},{name:'currency',label:'Valyuta',options:[['UZS','So‘m'],['USD','Dollar']]},{name:'amount',label:'Summa',type:'number',step:'any',required:true},{name:'note',label:'Izoh'}],'Davom etish','Mijoz qarzi shu to‘lov bilan kamayadi. So‘m kassa kursi bo‘yicha dollarga o‘giriladi'+(d.rate?' (1 USD = '+num(d.rate,0)+' so‘m)':' — avval kassa kursini belgilang')+'. Agent orqali olingan pul bu yerda emas — agent topshirig‘i.');
      if(!v)return;var c=d.debtors.find(function(x){return String(x.id)===v.clientId})||{},amt=v.currency==='USD'?Math.round(parseFloat(v.amount)*100):+v.amount,eq=v.currency==='USD'?amt:(d.rate?Math.round(amt*100/d.rate):0);
      if(await confirmBox('To‘lovni tasdiqlang','<p><b>'+cbMoney(amt,v.currency)+'</b> → '+esc((pockOpts.find(function(p){return p[0]===v.pocket})||['',''])[1])+'<br>Mijoz: <b>'+esc(c.name||'')+'</b><br>Qarz: '+usd((c.debtUsd||0)/100)+' → <b>'+usd(Math.max((c.debtUsd||0)-eq,0)/100)+'</b></p>','Tasdiqlash'))
        call(Object.assign({op:'income',category:d.clientPayment},v),'To‘lov saqlandi, mijoz qarzi kamaydi')}
    else if(k==='transfer'){v=await formBox('Hisoblar orasida o‘tkazma',[{name:'fromPocket',label:'Qayerdan',options:pockOpts},{name:'toPocket',label:'Qayerga',options:pockOpts,value:'bank'},{name:'currency',label:'Valyuta',options:[['UZS','So‘m'],['USD','Dollar']]},{name:'amount',label:'Summa',type:'number',step:'any',required:true},{name:'note',label:'Izoh'}],'O‘tkazish','Bir valyutada. Valyuta almashtirish — konvertatsiya (kassir ilovasida).');
      if(v&&await confirmBox('O‘tkazmani tasdiqlang','<p><b>'+cbMoney(v.currency==='USD'?Math.round(parseFloat(v.amount)*100):+v.amount,v.currency)+'</b>: '+esc((pockOpts.find(function(p){return p[0]===v.fromPocket})||['',''])[1])+' → '+esc((pockOpts.find(function(p){return p[0]===v.toPocket})||['',''])[1])+'</p>','Tasdiqlash'))call(Object.assign({op:'transfer'},v),'O‘tkazma saqlandi')}
    else{var f=[];pockOpts.forEach(function(p){['uzs','usd'].forEach(function(c){f.push({name:p[0]+'_'+c,label:p[1]+' '+(c==='uzs'?'so‘m':'dollar')+' — tizimda '+cbMoney(b[p[0]+'_'+c],c.toUpperCase()),type:'number',step:'any'})})});f.push({name:'note',label:'Izoh'});
      v=await formBox('Kunni yopish — sanalgan pul',f,'Yopish','Faqat sanagan hisoblaringizni to‘ldiring. Farq yoziladi, qoldiq avtomatik tuzatilmaydi.');
      if(v){var counted={};Object.keys(v).forEach(function(key){if(key!=='note'&&v[key]!=='')counted[key]=v[key]});call({op:'close',counted:counted,note:v.note},'Kun yopildi')}}}});
}
async function cbDetail(x,can){
  var row=function(k,v){return v?'<dt>'+k+'</dt><dd>'+v+'</dd>':''};
  var html='<h3>'+esc(x.label)+' #'+x.id+'</h3><dl class="kv" style="margin:12px 0">'+row('Sana',dt(x.ts))+row('Kimdan',esc(x.from))+row('Kimga',esc(x.to))+row('Summa','<b>'+cbMoney(x.amount,x.currency)+'</b>'+(x.toAmount?' → '+cbMoney(x.toAmount,x.toCurrency):''))+row('Kurs',x.rate?'1 USD = '+num(x.rate,0)+' so‘m':'')+row('Turi',esc(x.category))+row('Izoh',esc(x.note))+row('Kiritdi',esc(x.who))+
    row('Holat',x.status==='active'?'Faol':'<span class="bad">Bekor qilingan</span> — '+esc(x.cancel.who)+', '+dt(x.cancel.ts)+'<br>Sabab: '+esc(x.cancel.reason))+'</dl>'+
    (x.type==='handover'?'<p class="hint">Agent topshirig‘i tafsilotlari — agent kartasida va kassir ilovasida.</p>':'');
  var cancellable=x.move&&x.status==='active'&&can.cancel;
  var v=await modal('<form>'+html+(cancellable?(x.client?'<p class="hint">Bekor qilinsa pul hisobdan chiqadi va mijoz qarzi qayta tiklanadi. Asl yozuv tarixda qoladi.</p>':'')+'<label>Bekor qilish sababi<input name="reason" maxlength="300"></label>':'')+'<div class="foot"><button type="button" class="btn" data-m="cancel">Yopish</button>'+(cancellable?'<button class="btn danger">Bekor qilish</button>':'')+'</div></form>');
  if(v&&cancellable){var r=await run(function(){return api('cashbook',{op:'cancel',id:x.move,reason:v.reason})},'Bekor qilindi');if(r){CB.data=r;S.dash=null;var el=$('cbCard');if(el)renderCashbook(el,r)}}
}
function debtRows(){
  var q=DEBT.q.trim().toLowerCase();
  return S.dash.clients.filter(function(x){return x.debtUsd>0&&(!q||(x.name+' '+x.agent+' '+x.region+' '+x.phone).toLowerCase().indexOf(q)>=0)}).sort(function(a,b){return b.debtUsd-a.debtUsd});
}
function debtList(){
  var el=$('debtBody');if(!el)return;var rows=debtRows(),N=15,pages=Math.max(1,Math.ceil(rows.length/N));if(DEBT.page>=pages)DEBT.page=pages-1;
  var slice=rows.slice(DEBT.page*N,(DEBT.page+1)*N),tot=rows.reduce(function(a,x){return a+x.debtUsd},0);
  el.innerHTML=rows.length?'<div class="tbl-wrap"><table><thead><tr><th>Mijoz</th><th>Agent</th><th>Hudud</th><th>Oxirgi aloqa</th><th>Holat</th><th class="right">Qarz</th></tr></thead><tbody>'+slice.map(function(x){var ag=AGE[x.age]||AGE.unknown;
    return '<tr class="click" data-client="'+x.id+'"><td><div class="cell">'+(x.thumbUrl?'<span class="av sq" style="background-image:url(\''+esc(x.thumbUrl)+'\')"></span>':avatar(x.name,'','sq'))+'<div class="t"><b>'+esc(x.name)+'</b><small>'+esc(x.phone||'')+'</small></div></div></td><td>'+esc(x.agent)+'</td><td>'+esc(x.region||'—')+'</td><td class="num">'+(x.lastTs?dday(x.lastTs):'—')+(x.days!=null?'<br><small class="muted">'+x.days+' kun</small>':'')+'</td><td>'+pill('<span class="dot"></span>'+ag[0],ag[1])+'</td><td class="right num bad"><b class="bad">'+usd(x.debtUsd)+'</b></td></tr>'}).join('')+'</tbody></table></div>'+
    '<div class="pager"><span>'+num(rows.length)+' qarzdor · jami '+usd(tot)+'</span><span class="actions"><button class="btn sm" id="dPrev"'+(DEBT.page?'':' disabled')+'>‹</button><span>'+(DEBT.page+1)+' / '+pages+'</span><button class="btn sm" id="dNext"'+(DEBT.page<pages-1?'':' disabled')+'>›</button></span></div>':emptyState('Qarzdor mijoz yo‘q','checkc');
  if($('dPrev'))$('dPrev').onclick=function(){DEBT.page--;debtList()};if($('dNext'))$('dNext').onclick=function(){DEBT.page++;debtList()};
  bindClientLinks(el);
}
/* Kassa kategoriyasi: ma'lumotdagi emoji olib tashlanadi, o'rniga yagona Lucide ikonka (yo'nalish rangi bilan). */
var CAT_ICON=[[/🚚|йўл|yo.l/i,'truck'],[/⛽|ёқилғи|yoqilg/i,'fuel'],[/🍽|тушлик|tushlik|овқат/i,'food'],[/👷|иш ҳақи|ish haq/i,'worker'],[/🏢|офис|ofis/i,'building'],
  [/💰|дивиденд|dividend/i,'coins'],[/👨‍💼|агентга|agentga/i,'users'],[/💵|савдодан/i,'cash'],[/🏦|банк|bank/i,'bank'],[/↩|қайтган/i,'swap'],[/📦|бошқа|boshqa/i,'box']];
function catClean(t){return String(t||'').replace(/^[^0-9A-Za-z\u0400-\u04FFʻʼ‘’]+/,'').trim()||'Xarajat'}
function catIcon(t){for(var i=0;i<CAT_ICON.length;i++)if(CAT_ICON[i][0].test(t||''))return CAT_ICON[i][1];return 'receipt'}
function catCell(isIn,label){return '<div class="cell cat"><span class="tone '+(isIn?'t-green':'t-red')+'" aria-hidden="true">'+ic(isIn?'in':catIcon(label),'sm')+'</span><span>'+esc(isIn?label:catClean(label))+'</span></div>'}
function cashList(){
  var d=S.dash,custom=KS.p==='custom',since=custom?0:d.todayStart-({today:0,week:6,month:29}[KS.p])*86400,q=KS.q.trim().toLowerCase();
  if(custom&&!S.cashTx)return;
  var rows=(custom?S.cashTx.rows:d.transactions).filter(function(t){var ts=t.acceptedTs||t.ts;if(ts<since&&!(KS.f==='pending'&&t.state==='pending'))return false;
    if(KS.f==='in'&&t.type!=='handover')return false;if(KS.f==='out'&&t.type!=='expense')return false;if(KS.f==='pending'&&t.state!=='pending')return false;
    if(q&&[t.agent,t.cashier,t.category,t.recipient,t.note].join(' ').toLowerCase().indexOf(q)<0)return false;return true});
  /* Ustun sarlavhasini bosib saralash: sana, turi, tafsilot, kassir, summa (kirim +, chiqim −), holat */
  var key={ts:function(t){return t.acceptedTs||t.ts},type:function(t){return t.type==='handover'?'Agentdan':catClean(t.category)},
    detail:function(t){return (t.type==='handover'?t.agent:t.recipient)||''},cashier:function(t){return t.cashier||''},
    amount:function(t){return (t.type==='handover'?1:-1)*t.amountUsd},state:function(t){return t.state}}[KS.sort]||function(t){return t.ts};
  rows=rows.slice().sort(function(a,b){var x=key(a),y=key(b);return (typeof x==='string'?x.localeCompare(y):x-y)*KS.dir});
  S.cashRows=rows;var tin=0,tout=0;rows.forEach(function(t){if(t.type==='handover'&&t.state==='accepted')tin+=t.amountUsd;if(t.type==='expense')tout+=t.amountUsd});
  $('ksSum').innerHTML=rows.length+' ta · <span class="ok">+'+usd(tin)+'</span> · <span class="bad">−'+usd(tout)+'</span>';
  var ST={pending:['Kutilmoqda','p-warn'],accepted:['Qabul qilindi','p-ok'],rejected:['Rad etildi','p-bad'],expense:['Chiqim','p-bad']};
  var th=function(k,l,c){return '<th class="sort '+(c||'')+(KS.sort===k?(KS.dir>0?' asc':' desc'):'')+'" data-k="'+k+'" tabindex="0" aria-sort="'+(KS.sort===k?(KS.dir>0?'ascending':'descending'):'none')+'">'+l+'</th>'};
  $('ksList').innerHTML='<div class="tbl-wrap"><table><thead><tr>'+th('ts','Sana')+th('type','Turi')+th('detail','Tafsilot')+th('cashier','Kassir')+th('amount','Summa','right')+th('state','Holat')+'</tr></thead><tbody>'+
   (rows.length?rows.slice(0,400).map(function(t){var st=ST[t.state]||[esc(t.state),''],h=t.type==='handover';
     return '<tr><td class="num">'+dt(t.acceptedTs||t.ts)+'</td><td>'+catCell(h,h?'Agentdan':t.category)+'</td><td>'+(h?'<b>'+esc(t.agent)+'</b>'+(t.amountUzs?'<br><small class="muted">'+uzs(t.amountUzs)+'</small>':''):'<b>'+esc(t.recipient||'—')+'</b>'+(t.note?'<br><small class="muted">'+esc(t.note)+'</small>':'')+(t.currency==='UZS'&&t.amountUzs?'<br><small class="muted">'+uzs(t.amountUzs)+' · kurs '+num(t.rateUzsPerUsd)+'</small>':''))+'</td><td>'+esc(t.cashier||'—')+'</td><td class="right num '+(h?(t.state==='accepted'?'ok':'muted'):'bad')+'">'+(h?'+':'−')+usd(t.amountUsd)+'</td><td>'+pill(st[0],st[1])+'</td></tr>'}).join(''):'<tr><td colspan="6" class="empty">Harakat yo‘q</td></tr>')+
   '</tbody></table></div>'+(rows.length>400?'<div class="pager">Birinchi 400 ta ko‘rsatildi</div>':'');
  $('ksList').querySelectorAll('th.sort').forEach(function(h){var go=function(){var k=h.dataset.k;if(KS.sort===k)KS.dir=-KS.dir;else{KS.sort=k;KS.dir=(k==='ts'||k==='amount')?-1:1}cashList()};h.onclick=go;h.onkeydown=function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}}});
  var cat={};rows.forEach(function(t){if(t.type==='expense')cat[catClean(t.category)]=(cat[catClean(t.category)]||0)+t.amountUsd});
  var list=Object.keys(cat).map(function(k){return [k,cat[k]]}).sort(function(a,b){return b[1]-a[1]}),total=list.reduce(function(s,x){return s+x[1]},0);
  var PAL=[C.pri,C.violet,C.cyan,C.ink,C.gray,C.pri,C.violet,C.cyan];
  $('ksBrk').innerHTML=list.length?donut(list.slice(0,7).concat(list.length>7?[['Boshqa',list.slice(7).reduce(function(a,x){return a+x[1]},0)]]:[]).map(function(x,i){return [x[0],Math.round(x[1]*100)/100,PAL[i],usd(x[1])]}),usd(total),'xarajat'):'<div class="empty">Bu davrda xarajat yo‘q</div>';
}

/* ----- Savdo: hisobot + kompyuterdan sotuv (shop.py) ----- */
var SH={tab:'report',d:null,cart:null,q:null,qErr:'',pq:'',seller:''};
function shNewCart(){return {client:null,items:[],dmode:'pct',discount:'',method:'cash_usd',paid:'',paidUzs:'',rate:'',note:'',rid:'web'+Date.now().toString(36)+Math.random().toString(36).slice(2,10)}}
function shApi(op,args){return api('shop',Object.assign({op:op},args||{}))}
async function shLoad(){SH.d=await shApi('dashboard');if(!SH.seller){var t=(SH.d.team||[]).find(function(u){return u.level==='head'})||(SH.d.team||[])[0];SH.seller=t?String(t.id):''}return SH.d}
async function pageSales(page,force){
  if(!SH.cart)SH.cart=shNewCart();
  page.innerHTML='<div class="toolbar"><div class="seg" id="shTabs" style="max-width:100%;overflow-x:auto">'+[['report','Hisobot'],['pos','Yangi sotuv'],['prices','Narxlar']].map(function(x){return '<button data-t="'+x[0]+'" class="'+(SH.tab===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div></div><div id="shBody"><div class="grid g3">'+'<div class="skel"></div>'.repeat(3)+'</div></div>';
  $('shTabs').onclick=function(e){var b=e.target.closest('button');if(!b)return;SH.tab=b.dataset.t;pageSales(page)};
  if(!SH.d||force){try{await shLoad()}catch(e){$('shBody').innerHTML=errState(e.message);$('shBody').querySelector('[data-retry]').onclick=function(){pageSales(page,true)};return}}
  if(S.page!=='sales')return;
  var body=$('shBody');
  if(SH.tab==='team')SH.tab='report';
  ({report:salesReport,pos:shPos,prices:shPrices})[SH.tab](body,force);
}
function shProduct(p){return (SH.d.products||[]).find(function(x){return x.pack===p})}
function shPayload(){var c=SH.cart,p={clientId:c.client?c.client.id:null,note:c.note,items:c.items.map(function(i){var o={pack:i.pack,qty:i.qty};if(i.price!=null&&i.price!=='')o.price=i.price;return o})};
  if(c.discount!==''&&Number(c.discount)>0)p[c.dmode==='pct'?'discountPct':'discount']=c.discount;return p}
var shQT=0;
function shRequote(){clearTimeout(shQT);if(!SH.cart.items.length){SH.q=null;SH.qErr='';shTotals();return}
  shQT=setTimeout(async function(){try{SH.q=(await shApi('quote',shPayload())).quote;SH.qErr=''}catch(e){SH.qErr=e.message}shCart();shTotals()},250)}
function shPos(el){
  var team=SH.d.team||[],c=SH.cart;
  if(!team.length){el.innerHTML='<div class="card">'+emptyState('Savdo xodimlari yo‘q. «Xodimlar» bo‘limidan «Savdo» rolida qo‘shing — sotuv ularning nomidan yoziladi.','users')+'</div>';return}
  if(!c.rate&&SH.d.rate)c.rate=String(SH.d.rate);
  el.innerHTML='<div class="grid g2" style="align-items:start;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr))">'+
    '<div class="card flush" style="min-width:0"><div class="card-h"><h3>'+ic('box')+' Mahsulotlar</h3><input id="shPq" type="search" placeholder="Qidirish…" value="'+esc(SH.pq)+'" style="width:220px;max-width:100%"></div><div class="tbl-wrap" style="margin-top:12px;max-height:620px" id="shProds"></div></div>'+
    '<div style="min-width:0"><div class="card" style="margin-bottom:16px"><div class="card-h"><h3>'+ic('users')+' Sotuvchi va mijoz</h3></div>'+
      '<label class="small muted">Sotuv kimning nomidan (naqd pul shu xodim hisobiga tushadi)</label><select id="shSeller">'+team.map(function(u){return '<option value="'+u.id+'"'+(String(u.id)===SH.seller?' selected':'')+'>'+esc(u.name)+'</option>'}).join('')+'</select>'+
      '<div id="shClient" style="margin-top:12px"></div></div>'+
    '<div class="card flush" style="margin-bottom:16px"><div class="card-h"><h3>'+ic('cart')+' Savatcha</h3>'+(c.items.length?'<button class="btn" id="shClr">Tozalash</button>':'')+'</div><div id="shCart" class="tbl-wrap" style="padding:0 20px 16px"></div></div>'+
    '<div class="card" id="shPay"></div></div></div>';
  $('shSeller').onchange=function(){SH.seller=this.value};
  $('shPq').oninput=function(){SH.pq=this.value;shProds()};
  if($('shClr'))$('shClr').onclick=function(){c.items=[];SH.q=null;shPos(el)};
  shProds();shClient();shCart();shTotals();
}
function shProds(){
  var c=SH.cart,pt=c.client?c.client.priceType:'retail',q=SH.pq.trim().toLowerCase();
  var ps=(SH.d.products||[]).filter(function(p){return !q||p.name.toLowerCase().indexOf(q)>=0});
  $('shProds').innerHTML='<table><thead><tr><th>Mahsulot</th><th class="right">Omborda</th><th class="right">'+(pt==='dealer'?'Diller':'Chakana')+'</th><th></th></tr></thead><tbody>'+ps.map(function(p){var pr=pt==='dealer'?p.dealerUsd:p.retailUsd,inC=c.items.find(function(i){return i.pack===p.pack});
    return '<tr><td>'+esc(p.name)+'</td><td class="right num '+(p.stock>0?'':'bad')+'">'+num(p.stock)+'</td><td class="right num">'+(pr>0?usd(pr):'<span class="bad">—</span>')+'</td><td class="right"><button class="btn'+(inC?' pri':'')+'" data-add="'+p.pack+'"'+(p.stock>0?'':' disabled')+'>'+(inC?inC.qty+' ta':ic('plus','sm'))+'</button></td></tr>'}).join('')+'</tbody></table>';
  $('shProds').querySelectorAll('[data-add]').forEach(function(b){b.onclick=function(){var p=+b.dataset.add,pr=shProduct(p),it=c.items.find(function(i){return i.pack===p});
    if(it)it.qty=Math.min(it.qty+1,pr.stock);else c.items.push({pack:p,qty:1,price:null});shProds();shCart();shRequote()}});
}
function shClient(){
  var c=SH.cart,el=$('shClient'),k=c.client;
  el.innerHTML=k?'<div class="li"><div class="t"><b>'+esc(k.name)+'</b><small>'+esc(k.phone||'')+' · '+(k.priceType==='dealer'?'Diller narx':'Chakana narx')+' · '+(k.debtUsd>0?'<span class="bad">qarz '+usd(k.debtUsd)+'</span>':'qarz yo‘q')+'</small></div><button class="btn" id="shCx">Almashtirish</button></div>'
    :'<div class="muted small">Chakana xaridor — faqat to‘liq to‘lov</div><div style="display:flex;gap:8px;margin-top:8px"><input id="shCq" type="search" placeholder="Mijoz: ism, do‘kon yoki telefon" style="flex:1"><button class="btn" id="shNew">'+ic('userplus','sm')+' Yangi</button></div><div id="shCres" class="list" style="max-height:220px;overflow:auto"></div>';
  if(k){$('shCx').onclick=function(){c.client=null;shClient();shProds();shRequote()};return}
  var t=0;$('shCq').oninput=function(){var v=this.value;clearTimeout(t);t=setTimeout(async function(){if(!v.trim()){$('shCres').innerHTML='';return}
    var r=await run(function(){return shApi('clients',{q:v})});if(!r)return;
    $('shCres').innerHTML=r.clients.slice(0,12).map(function(x){return '<div class="li click" data-c="'+x.id+'"><div class="t"><b>'+esc(x.name)+'</b><small>'+esc(x.phone)+' · '+(x.priceType==='dealer'?'Diller':'Chakana')+(x.debtUsd>0?' · qarz '+usd(x.debtUsd):'')+'</small></div></div>'}).join('')||'<div class="muted small" style="padding:8px">Topilmadi</div>';
    $('shCres').querySelectorAll('[data-c]').forEach(function(el2){el2.onclick=function(){c.client=r.clients.find(function(x){return x.id===+el2.dataset.c});shClient();shProds();shRequote()}})},250)};
  $('shNew').onclick=shNewClient;
}
async function shNewClient(){
  var v=await formBox('Yangi mijoz',[{name:'name',label:'Ism',required:1},{name:'shop',label:'Do‘kon nomi'},{name:'phone',label:'Telefon',value:'+998',required:1},{name:'region',label:'Hudud'},{name:'pt',label:'Narx turi',options:[['retail','Chakana'],['dealer','Diller']]}]);
  if(!v)return;
  var r=await run(function(){return shApi('add_client',{name:v.name,shopName:v.shop,phone:v.phone,region:v.region,priceType:v.pt})},'Mijoz qo‘shildi');
  if(!r)return;var k=r.client;SH.cart.client={id:k.id,name:k.shopName||k.name,phone:k.phone,priceType:k.priceType,debtUsd:k.debtUsd};shClient();shProds();shRequote();
}
function shCart(){
  var c=SH.cart,el=$('shCart');if(!el)return;
  if(!c.items.length){el.innerHTML='<div class="muted small">Chapdagi ro‘yxatdan mahsulot qo‘shing</div>';return}
  el.innerHTML='<table><thead><tr><th>Mahsulot</th><th class="right">Miqdor</th><th class="right">Narx $</th><th class="right">Jami</th><th></th></tr></thead><tbody>'+c.items.map(function(i,k){var p=shProduct(i.pack)||{name:'#'+i.pack},l=SH.q&&SH.q.lines[k];
    return '<tr><td>'+esc(p.name)+(l&&l.priceSource==='special'?' <span class="pill p-ok">maxsus</span>':'')+'</td><td class="right"><input data-q="'+k+'" value="'+i.qty+'" inputmode="numeric" style="width:70px;text-align:right"></td><td class="right"><input data-pr="'+k+'" value="'+esc(i.price==null?'':i.price)+'" placeholder="'+(l?l.listPriceUsd:'')+'" inputmode="decimal" style="width:80px;text-align:right"></td><td class="right num">'+(l?usd(l.priceUsd*i.qty):'…')+'</td><td><button class="btn" data-del="'+k+'" aria-label="O‘chirish">'+ic('x','sm')+'</button></td></tr>'}).join('')+'</tbody></table>';
  el.querySelectorAll('[data-q]').forEach(function(x){x.onchange=function(){var k=+x.dataset.q,p=shProduct(c.items[k].pack),n=Math.max(0,Math.min(parseInt(x.value,10)||0,p?p.stock:0));if(!n)c.items.splice(k,1);else c.items[k].qty=n;shProds();shCart();shRequote()}});
  el.querySelectorAll('[data-pr]').forEach(function(x){x.onchange=function(){c.items[+x.dataset.pr].price=x.value.trim().replace(',','.')||null;shRequote()}});
  el.querySelectorAll('[data-del]').forEach(function(x){x.onclick=function(){c.items.splice(+x.dataset.del,1);shProds();shCart();shRequote()}});
}
function shTotals(){
  var el=$('shPay');if(!el)return;var c=SH.cart,q=SH.q;
  if(!c.items.length){el.hidden=true;return}el.hidden=false;
  var tot=q?q.totalUsd:0,paid=c.method==='cash_uzs'?(Number(c.paidUzs)>0&&Number(c.rate)>0?Math.round(Number(c.paidUzs)/Number(c.rate)*100)/100:0):Number(String(c.paid).replace(',','.'))||0,debt=Math.max(0,Math.round((tot-paid)*100)/100);
  el.innerHTML='<div class="card-h"><h3>'+ic('wallet')+' Chegirma va to‘lov</h3></div>'+
    '<div style="display:flex;gap:8px;align-items:center"><div class="seg" id="shDm"><button data-d="pct" class="'+(c.dmode==='pct'?'on':'')+'">%</button><button data-d="usd" class="'+(c.dmode==='usd'?'on':'')+'">$</button></div><input id="shDisc" placeholder="Chegirma" value="'+esc(c.discount)+'" inputmode="decimal" style="flex:1"></div>'+
    '<dl class="kv" style="margin-top:12px"><dt>Jami narx</dt><dd class="num">'+(q?usd(q.subtotalUsd):'…')+'</dd><dt>Jami chegirma</dt><dd class="num">'+(q?'−'+usd(q.discountUsd)+(q.discountPct?' ('+q.discountPct+'%)':''):'…')+'</dd><dt><b>To‘lanishi kerak</b></dt><dd class="num"><b>'+(q?usd(tot):'…')+'</b></dd></dl>'+
    (SH.qErr?'<div class="bad small" style="margin-top:8px">'+esc(SH.qErr)+'</div>':'')+(q&&q.stockShort.length?'<div class="bad small" style="margin-top:8px">'+esc(q.stockShort.join('; '))+'</div>':'')+
    '<div style="margin-top:12px" class="seg" id="shPm">'+[['cash_usd','Naqd $'],['cash_uzs','Naqd so‘m'],['card','Karta']].map(function(x){return '<button data-m="'+x[0]+'" class="'+(c.method===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
    '<div style="display:flex;gap:8px;margin-top:8px">'+(c.method==='cash_uzs'?'<input id="shUz" placeholder="So‘m" value="'+esc(c.paidUzs)+'" inputmode="numeric" style="flex:1"><input id="shRt" placeholder="Kurs" value="'+esc(c.rate)+'" inputmode="numeric" style="width:110px">':'<input id="shPd" placeholder="To‘landi, $" value="'+esc(c.paid)+'" inputmode="decimal" style="flex:1">')+
      '<button class="btn" id="shFull">To‘liq</button><button class="btn" id="shNone">Qarzga</button></div>'+
    '<dl class="kv" style="margin-top:12px"><dt>To‘landi</dt><dd class="num ok">'+usd(paid)+'</dd><dt><b>Qoldiq (qarz)</b></dt><dd class="num '+(debt>0?'bad':'ok')+'"><b>'+usd(debt)+'</b></dd></dl>'+
    (debt>0&&!c.client?'<div class="bad small">Chakana xaridorga qarzga berilmaydi — mijozni tanlang.</div>':'')+
    '<input id="shNt" placeholder="Izoh (ixtiyoriy)" maxlength="300" value="'+esc(c.note)+'" style="margin-top:10px">'+
    '<button class="btn pri" id="shSave" style="width:100%;margin-top:12px"'+(!q||SH.qErr||q.stockShort.length?' disabled':'')+'>'+ic('check','sm')+' Sotuvni saqlash · '+(q?usd(tot):'')+'</button>';
  $('shDm').onclick=function(e){var b=e.target.closest('button');if(!b)return;c.dmode=b.dataset.d;c.discount='';shTotals();shRequote()};
  $('shDisc').onchange=function(){c.discount=this.value.trim().replace(',','.');shRequote()};
  $('shPm').onclick=function(e){var b=e.target.closest('button');if(!b)return;c.method=b.dataset.m;shTotals()};
  [['shPd','paid'],['shUz','paidUzs'],['shRt','rate']].forEach(function(x){var i=$(x[0]);if(i)i.onchange=function(){c[x[1]]=this.value.trim();shTotals()}});
  $('shNt').onchange=function(){c.note=this.value};
  $('shFull').onclick=function(){if(!q)return;if(c.method==='cash_uzs'){var r=Number(c.rate||SH.d.rate);if(!r)return toast('Kursni kiriting',true);c.rate=String(r);c.paidUzs=String(Math.round(tot*r))}else c.paid=String(tot);shTotals()};
  $('shNone').onclick=function(){c.paid='';c.paidUzs='';shTotals()};
  $('shSave').onclick=shSave;
}
async function shSave(){
  var c=SH.cart,p=Object.assign(shPayload(),{requestId:c.rid,sellerId:SH.seller,method:c.method});
  if(c.method==='cash_uzs'){if(c.paidUzs){p.paidUzs=c.paidUzs;p.rate=c.rate||SH.d.rate}}else if(c.paid)p.paid=String(c.paid).replace(',','.');
  if(!p.paid&&!p.paidUzs)delete p.method;
  var b=$('shSave');b.disabled=true;
  var r=await run(function(){return shApi('sell',p)},'Sotuv saqlandi');
  if(!r){b.disabled=false;return}
  SH.d=r;SH.cart=shNewCart();SH.q=null;S.cache={};shReceipt(r.receipt);shPos($('shBody'));
}
function shReceipt(r){
  modal('<form><h3>Sotuv № '+r.id+'</h3><div class="muted small">'+dt(r.ts)+' · '+esc(r.seller)+' · '+esc(r.client)+(r.phone?' · '+esc(r.phone):'')+'</div>'+
    '<div class="tbl-wrap" style="margin:12px 0"><table><thead><tr><th>Mahsulot</th><th class="right">Miqdor</th><th class="right">Narx</th><th class="right">Chegirma</th><th class="right">Jami</th></tr></thead><tbody>'+
    r.lines.map(function(l){return '<tr><td>'+esc(l.name)+'</td><td class="right num">'+num(l.qty)+'</td><td class="right num">'+usd(l.priceUsd)+'</td><td class="right num">'+(l.discountUsd?usd(l.discountUsd):'—')+'</td><td class="right num">'+usd(l.totalUsd)+'</td></tr>'}).join('')+'</tbody></table></div>'+
    '<dl class="kv"><dt>Jami narx</dt><dd class="num">'+usd(r.subtotalUsd)+'</dd><dt>Jami chegirma</dt><dd class="num">−'+usd(r.discountUsd)+'</dd><dt><b>To‘lanishi kerak</b></dt><dd class="num"><b>'+usd(r.totalUsd)+'</b></dd><dt>To‘langan</dt><dd class="num ok">'+usd(r.paidUsd)+(r.paidUzs?' · '+uzs(r.paidUzs):'')+'</dd><dt><b>Qoldiq (qarz)</b></dt><dd class="num '+(r.debtUsd>0?'bad':'ok')+'"><b>'+usd(r.debtUsd)+'</b></dd></dl>'+
    '<div class="foot"><button type="button" class="btn" onclick="window.print()">'+ic('download','sm')+' Chop etish</button><button type="button" class="btn pri" data-m="cancel">Yopish</button></div></form>');
}
function shPrices(el){
  var ps=SH.d.products||[];
  el.innerHTML='<div class="card flush"><div class="card-h"><h3>'+ic('dollar')+' Savdo narxlari</h3><span class="muted small">Chakana — ombor sotuvchilari va oddiy mijozlar · Diller — diller mijozlar · o‘zgartirish darhol saqlanadi</span></div>'+
    '<div class="tbl-wrap" style="margin-top:12px"><table><thead><tr><th>Mahsulot</th><th class="right">Omborda</th><th class="right">Chakana $</th><th class="right">Diller $</th></tr></thead><tbody>'+
    ps.map(function(p){return '<tr><td>'+esc(p.name)+'</td><td class="right num">'+num(p.stock)+'</td><td class="right"><input data-r="'+p.pack+'" value="'+(p.retailUsd||'')+'" inputmode="decimal" style="width:100px;text-align:right"></td><td class="right"><input data-d="'+p.pack+'" value="'+(p.dealerUsd||'')+'" inputmode="decimal" style="width:100px;text-align:right"></td></tr>'}).join('')+'</tbody></table></div></div>';
  el.querySelectorAll('[data-r],[data-d]').forEach(function(i){i.onchange=async function(){var pack=+(i.dataset.r||i.dataset.d);
    var r=await run(function(){return shApi('set_price',{pack:pack,retail:el.querySelector('[data-r="'+pack+'"]').value.replace(',','.'),dealer:el.querySelector('[data-d="'+pack+'"]').value.replace(',','.')})},'Narx saqlandi');
    if(r)SH.d=r}});
}
function shTeam(el){
  var tm=SH.d.team||[],L=SH.d.permLabels||{},keys=Object.keys(L);
  el.innerHTML='<div class="card flush"><div class="card-h"><h3>'+ic('users')+' Savdo jamoasi · funksiyalar</h3><span class="muted small">Xodimlar soni cheklanmagan — yangisini yuqoridagi «Xodim qo‘shish» orqali «Savdo» rolida qo‘shing. Katakchani bosing — darhol saqlanadi.</span></div>'+
    '<div class="tbl-wrap" style="margin-top:12px">'+(tm.length?'<table><thead><tr><th>Xodim</th>'+keys.map(function(k){return '<th style="text-align:center;min-width:92px;white-space:normal;font-size:11.5px">'+esc(L[k])+'</th>'}).join('')+'<th class="right">Chegirma limiti %</th><th class="right">Bugun</th><th class="right">Qo‘lidagi pul</th></tr></thead><tbody>'+
    tm.map(function(u){return '<tr><td><b>'+esc(u.name)+'</b><br><button class="btn" style="min-height:26px;padding:0 8px;font-size:11.5px;margin-top:4px" data-all="'+u.id+'">'+(u.perms.length===keys.length?'Hammasini o‘chirish':'Hammasini yoqish')+'</button></td>'+
      keys.map(function(k){return '<td style="text-align:center"><input type="checkbox" data-u="'+u.id+'" data-k="'+k+'"'+(u.perms.indexOf(k)>=0?' checked':'')+' aria-label="'+esc(u.name+': '+L[k])+'" style="width:18px;height:18px"></td>'}).join('')+
      '<td class="right"><input data-lim="'+u.id+'" value="'+u.maxDiscountPct+'" inputmode="numeric" style="width:70px;text-align:right"'+(u.perms.indexOf('discount')>=0?'':' disabled')+'></td>'+
      '<td class="right num">'+num(u.todayCount)+' ta · '+usd(u.todayUsd)+'</td><td class="right num">'+usd(u.cashUsd)+'<br><small class="muted">'+uzs(u.cashUzs)+'</small></td></tr>'}).join('')+'</tbody></table>':emptyState('Savdo xodimlari yo‘q','users'))+'</div></div>';
  function save(u,perms,lim){run(function(){return shApi('set_staff',{userId:u.id,perms:perms,maxDiscountPct:lim})},'Saqlandi').then(function(r){if(r)SH.d=r;shTeam(el)})}
  el.querySelectorAll('[data-k]').forEach(function(i){i.onchange=function(){var u=tm.find(function(x){return x.id===+i.dataset.u}),k=i.dataset.k;
    save(u,i.checked?u.perms.concat([k]):u.perms.filter(function(x){return x!==k}),u.maxDiscountPct)}});
  el.querySelectorAll('[data-all]').forEach(function(b){b.onclick=function(){var u=tm.find(function(x){return x.id===+b.dataset.all});save(u,u.perms.length===keys.length?[]:keys,u.maxDiscountPct)}});
  el.querySelectorAll('[data-lim]').forEach(function(i){i.onchange=function(){var u=tm.find(function(x){return x.id===+i.dataset.lim});save(u,u.perms,i.value)}});
}
/* ----- Savdo (Bito «Sotuvlar» kabi) ----- */
var SL={period:'month',from:'',to:'',agent:'',q:'',kind:''};
var SL_K={sold:['🛒','Savdo summasi'],net:['📦','Sof savdo'],returned:['🧾','Qaytarish'],checks:['receipt','Cheklar soni'],avgCheck:['💲','O‘rtacha chek'],qty:['box','Mahsulot soni']};
async function salesReport(page,force){
  var agents=(S.dash?S.dash.agents:[]).concat(SH.d&&SH.d.team||[]).slice().sort(function(a,b){return a.name.localeCompare(b.name)});
  page.innerHTML='<div class="toolbar"><div class="seg" id="slSeg">'+[['today','Bugun'],['yesterday','Kecha'],['d7','7 kun'],['month','Shu oy'],['d30','30 kun'],['all','Umumiy'],['custom','Davr']].map(function(x){return '<button data-p="'+x[0]+'" class="'+(SL.period===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
   '<span id="slCustom"'+(SL.period==='custom'?'':' hidden')+' class="actions"><input type="date" id="slFrom" value="'+esc(SL.from||today())+'" style="width:auto"><input type="date" id="slTo" value="'+esc(SL.to||today())+'" style="width:auto"><button class="btn pri" id="slGo">Ko‘rsatish</button></span>'+
   '<select id="slAgent" style="width:auto" aria-label="Agent"><option value="">Barcha agentlar</option>'+agents.map(function(a){return '<option value="'+a.id+'"'+(String(a.id)===String(SL.agent)?' selected':'')+'>'+esc(a.name)+'</option>'}).join('')+'</select>'+
   '<span class="grow"></span><span class="muted" id="slLabel"></span></div><div id="slBody"><div class="grid g3">'+'<div class="skel"></div>'.repeat(6)+'</div></div>';
  $('slSeg').onclick=function(e){var b=e.target.closest('button');if(!b)return;SL.period=b.dataset.p;if(SL.period==='custom'){$('slSeg').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});$('slCustom').hidden=false;return}salesReport(page)};
  if($('slGo'))$('slGo').onclick=function(){SL.from=$('slFrom').value;SL.to=$('slTo').value;salesReport(page)};
  $('slAgent').onchange=function(){SL.agent=this.value;salesReport(page)};
  if(SL.period==='custom'&&!SL.from)return;
  var key='sl'+SL.period+SL.from+SL.to+SL.agent,r=!force&&S.cache[key];
  if(!r){r=await run(function(){return api('sales',{period:SL.period,from:SL.from,to:SL.to,agentId:SL.agent||null})});if(!r){$('slBody').innerHTML='';return}S.cache[key]=r}
  if(S.page!=='sales')return;
  $('slLabel').textContent=r.range.label+(r.range.prevLabel?' · solishtirish: '+r.range.prevLabel:'');
  var pay=r.payments,ptot=pay.cashUsd+pay.cashUzsAsUsd+pay.cardUsd+pay.onCreditUsd;
  var share=function(v){return ptot>0?Math.round(v*1000/ptot)/10:0};
  var tbl=function(head,rows,empty){return '<div class="tbl-wrap" style="margin-top:12px">'+(rows.length?'<table><thead><tr>'+head+'</tr></thead><tbody>'+rows.join('')+'</tbody></table>':'<div class="empty">'+empty+'</div>')+'</div>'};
  var bar=function(p){return '<td><div class="share"><i style="width:'+Math.max(0,Math.min(100,p||0))+'%"></i></div><small class="muted">'+(p||0)+'%</small></td>'};
  $('slBody').innerHTML=
   '<div class="grid g3" style="margin-bottom:16px">'+r.kpis.map(function(k){var m=SL_K[k.key],money=k.key!=='checks'&&k.key!=='qty';
     return kpi(m[0],m[1],money?usd(k.value):num(k.value)+(k.key==='checks'?' ta':' dona'),exDelta(k)+(k.prev!=null?' <span class="muted small">oldin '+(money?usd(k.prev):num(k.prev))+'</span>':'')+(k.key==='qty'?'<br><span class="muted small">chekda o‘rtacha '+num(r.avgItemsPerCheck,1)+' dona</span>':''))}).join('')+'</div>'+
   '<div class="grid g2" style="margin-bottom:16px">'+
     '<div class="card"><div class="card-h"><h3>'+ic('wallet')+' To‘lov turlari bo‘yicha</h3></div>'+(ptot>0?'<div style="padding:8px 0">'+donut([['Qarzga',pay.onCreditUsd,C.orange,usd(pay.onCreditUsd)],['Naqd $',pay.cashUsd,C.forest,usd(pay.cashUsd)],['Naqd so‘m',pay.cashUzsAsUsd,C.cyan,usd(pay.cashUzsAsUsd)+' · '+uzs(pay.cashUzs)],['Karta',pay.cardUsd,C.pri,usd(pay.cardUsd)]].filter(function(x){return x[1]>0}),usd(ptot),'jami')+'</div>':'<div class="empty">Bu davrda savdo yoki to‘lov yo‘q</div>')+
       '<dl class="kv"><dt>Yig‘ilgan pul</dt><dd class="num">'+usd(pay.totalUsd)+'</dd><dt>Qarzga ketgan</dt><dd class="num bad">'+usd(pay.onCreditUsd)+' ('+share(pay.onCreditUsd)+'%)</dd></dl></div>'+
     '<div class="card flush"><div class="card-h"><h3>'+ic('box')+' Eng ko‘p sotilgan mahsulotlar</h3></div>'+tbl('<th>Mahsulot</th><th class="right">Dona</th><th class="right">Qaytgan</th><th class="right">Sof summa</th><th>Ulush</th>',
       r.topProducts.map(function(p){return '<tr><td>'+esc(p.name)+'</td><td class="right num">'+num(p.qty)+'</td><td class="right num muted">'+(p.returnedQty?num(p.returnedQty):'—')+'</td><td class="right num">'+usd(p.netUsd)+'</td>'+bar(p.sharePct)+'</tr>'}),'Bu davrda sotuv yo‘q')+'</div>'+
   '</div>'+
   '<div class="grid g2" style="margin-bottom:16px">'+
     '<div class="card flush"><div class="card-h"><h3>'+ic('store')+' Eng ko‘p xarid qilgan mijozlar</h3></div>'+tbl('<th>Mijoz</th><th class="right">Chek</th><th class="right">Dona</th><th class="right">Sof summa</th><th>Ulush</th>',
       r.topClients.map(function(c){return '<tr class="click" data-client="'+c.clientId+'"><td><b>'+esc(c.client)+'</b></td><td class="right num">'+num(c.checks)+'</td><td class="right num">'+num(c.qty)+'</td><td class="right num">'+usd(c.netUsd)+'</td>'+bar(c.sharePct)+'</tr>'}),'Bu davrda xaridor yo‘q')+'</div>'+
     '<div class="card flush"><div class="card-h"><h3>'+ic('users')+' Eng ko‘p savdo qilgan agentlar</h3></div>'+tbl('<th>Agent</th><th class="right">Chek</th><th class="right">Sof summa</th><th>Ulush</th>',
       r.agents.map(function(a){return '<tr class="click" data-agent="'+a.agentId+'"><td><b>'+esc(a.agent)+'</b></td><td class="right num">'+num(a.checks)+'</td><td class="right num">'+usd(a.netUsd)+'</td>'+bar(a.sharePct)+'</tr>'}),'Bu davrda savdo yo‘q')+'</div>'+
   '</div>'+
   '<div class="card flush"><div class="card-h"><h3>'+ic('receipt')+' Sotuvlar jurnali <span class="muted small">('+num(r.journalTotal)+' ta)</span></h3>'+
     '<span class="actions"><div class="seg" id="slKind">'+[['','Hammasi'],['sale','Sotuv'],['return','Qaytarish']].map(function(x){return '<button data-k="'+x[0]+'" class="'+(SL.kind===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div><input id="slQ" type="search" placeholder="Mijoz, telefon, mahsulot…" value="'+esc(SL.q)+'" style="width:220px"></span></div>'+
     '<div id="slJournal"></div>'+(r.journalTotal>r.journalLimit?'<div class="pager">Oxirgi '+r.journalLimit+' ta ko‘rsatildi — davrni qisqartiring</div>':'')+'</div>';
  slJournal(r);
  $('slKind').onclick=function(e){var b=e.target.closest('button');if(!b)return;SL.kind=b.dataset.k;this.querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});slJournal(r)};
  $('slQ').oninput=function(){SL.q=this.value;slJournal(r)};
  bindAgentLinks($('slBody'));bindClientLinks($('slBody'));
}
function slJournal(r){
  var q=SL.q.trim().toLowerCase(),rows=r.journal.filter(function(j){
    if(SL.kind&&j.kind!==SL.kind)return false;if(!q)return true;
    return (j.client+' '+j.phone+' '+j.agent+' '+j.items.map(function(i){return i.name}).join(' ')).toLowerCase().indexOf(q)>=0});
  var el=$('slJournal');if(!el)return;
  el.innerHTML='<div class="tbl-wrap" style="margin-top:12px">'+(rows.length?'<table><thead><tr><th>Sana</th><th>Turi</th><th>Mijoz</th><th>Agent</th><th>Mahsulotlar</th><th class="right">Dona</th><th class="right">Summa</th></tr></thead><tbody>'+
    rows.map(function(j){var ret=j.kind==='return';return '<tr class="click" data-client="'+j.clientId+'"><td class="num">'+dt(j.ts)+'</td><td>'+pill(ret?'Qaytarish':'Sotuv',ret?'p-warn':'p-ok')+'</td><td><b>'+esc(j.client)+'</b>'+(j.phone?'<br><small class="muted">'+esc(j.phone)+'</small>':'')+'</td><td>'+esc(j.agent)+'</td><td><small>'+j.items.map(function(i){return esc(i.name)+' × '+num(i.qty)}).join('<br>')+'</small></td><td class="right num">'+num(j.qty)+'</td><td class="right num '+(ret?'bad':'')+'">'+(ret?'−':'')+usd(j.amountUsd)+'</td></tr>'}).join('')+
    '</tbody></table>':'<div class="empty">Mos yozuv topilmadi</div>')+'</div>';
  bindClientLinks(el);
}

/* ----- Hisobot ----- */
var RP={period:'week',from:'',to:''};
/* Diagramma: 5 ta yetakchi + «Boshqalar». Foiz serverdagi sharePct (jadval bilan bir xil baza);
   avval faqat top-6 ning o'z yig'indisidan hisoblanardi va jadvaldagidan farq qilardi (masalan 46% va 35,3%). */
function prodParts(prod){
  var pos=prod.filter(function(p){return p.deliveredUsd>0}),pal=[C.pri,C.cyan,C.violet,C.yellow,C.gray];
  var parts=pos.slice(0,5).map(function(p,i){return [p.name,Math.round(p.deliveredUsd*100)/100,pal[i],usd(p.deliveredUsd),p.sharePct||0]});
  var rest=pos.slice(5);if(rest.length){var v=rest.reduce(function(a,p){return a+p.deliveredUsd},0),pc=rest.reduce(function(a,p){return a+(p.sharePct||0)},0);
    parts.push(['Boshqalar ('+rest.length+')',Math.round(v*100)/100,'var(--line2)',usd(v),Math.round(pc*10)/10])}
  return parts;
}
async function pageReports(page,force){
  page.innerHTML='<div class="toolbar"><div class="seg" id="rpSeg">'+[['today','Bugun'],['week','Hafta'],['month','Shu oy'],['custom','Davr']].map(function(x){return '<button data-p="'+x[0]+'" class="'+(RP.period===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
   '<span id="rpCustom"'+(RP.period==='custom'?'':' hidden')+' class="actions"><input type="date" id="rpFrom" value="'+esc(RP.from||today())+'" style="width:auto"><input type="date" id="rpTo" value="'+esc(RP.to||today())+'" style="width:auto"><button class="btn pri" id="rpGo">Ko‘rsatish</button></span>'+
   '<span class="grow"></span><span class="muted" id="rpLabel"></span></div><div id="rpBody"><div class="grid g4">'+'<div class="skel"></div>'.repeat(8)+'</div></div>';
  $('rpSeg').onclick=function(e){var b=e.target.closest('button');if(!b)return;RP.period=b.dataset.p;if(RP.period==='custom'){$('rpSeg').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});$('rpCustom').hidden=false;return}pageReports(page)};
  if($('rpGo'))$('rpGo').onclick=function(){RP.from=$('rpFrom').value;RP.to=$('rpTo').value;pageReports(page)};
  if(RP.period==='custom'&&!RP.from)return;
  var key=RP.period+RP.from+RP.to,r=!force&&S.cache['rp'+key];
  if(!r){try{r=await api('period_report',{period:RP.period,from:RP.from,to:RP.to})}
    catch(e){if(S.page!=='reports'||!$('rpBody')||!TOKEN)return;$('rpBody').innerHTML=errState(e.message);$('rpBody').querySelector('[data-retry]').onclick=function(){pageReports(page,true)};return}
    S.cache['rp'+key]=r}
  if(S.page!=='reports')return;
  $('rpLabel').textContent=r.label||'';
  var cash=r.cash||{},prod=(r.products||[]).filter(function(p){return p.deliveredUsd||p.deliveredQty});
  $('rpBody').innerHTML=
   '<div class="grid g4" style="margin-bottom:16px">'+
     kpi('📦','Realizatsiya',usd(r.deliveredUsd),r.deliveredQty+' dona · qaytgan '+usd(r.returnsUsd)+(r.topProduct?'<br>Top: '+esc(r.topProduct):''))+
     kpi('💰','Mijozdan olindi',usd(r.paymentsUsd),r.deliveredUsd?Math.round(r.paymentsUsd/r.deliveredUsd*100)+'% realizatsiyaga nisbatan':'')+
     kpi('🏦','Kassaga qabul',usd(r.acceptedCashUsd),'Xarajat '+usd(r.cashierExpensesUsd))+
     kpi('🛒','Do‘konda sotildi',num(r.soldQty)+' dona','Agentlar qayd etgan')+
     kpi('👣','Tashriflar',num(r.visits),'')+kpi('userplus','Yangi mijozlar',num(r.newClients),'')+
     kpi('⏱','Ish vaqti',num((r.workSeconds||0)/3600,1)+' soat',hours(r.workSeconds)+' · barcha agentlar')+kpi('🧭','Masofa',num(r.distanceKm,1)+' km','GPS bo‘yicha')+
   '</div>'+
   '<div class="card" style="margin-bottom:16px"><div class="card-h"><h3>Dinamika <span class="muted small">('+esc(r.seriesUnit||'')+')</span></h3>'+legend([['Realizatsiya',C.pri],['To‘lovlar',C.forest]])+'</div>'+barChart(r.series,['deliveredUsd','paymentsUsd'],[C.pri,C.forest],usd)+'</div>'+
   '<div class="card flush" style="margin-bottom:16px"><div class="card-h"><h3>Agentlar natijasi</h3></div><div class="tbl-wrap" style="margin-top:12px">'+agentReportTable(r.agents)+'</div></div>'+
   '<div class="grid g2">'+
     '<div class="card flush"><div class="card-h"><h3>'+ic('box')+' Mahsulotlar</h3></div>'+(prod.length?'<div style="padding:16px 20px 4px">'+donut(prodParts(prod),usd(r.deliveredUsd),'realizatsiya')+'<p class="hint" style="margin-top:10px">Ulush — mahsulotlar realizatsiyasi jamiga nisbatan; diagramma va jadvalda bir xil.</p></div>':'')+'<div class="tbl-wrap" style="margin-top:12px">'+(prod.length?'<table><thead><tr><th>Mahsulot</th><th class="right">Dona</th><th class="right">Summa</th><th>Ulush</th></tr></thead><tbody>'+prod.map(function(p){return '<tr><td>'+esc(p.name)+'</td><td class="right num">'+num(p.deliveredQty)+'</td><td class="right num">'+usd(p.deliveredUsd)+'</td><td><div class="share"><i style="width:'+(p.sharePct||0)+'%"></i></div><small class="muted">'+(p.sharePct||0)+'%</small></td></tr>'}).join('')+'</tbody></table>':'<div class="empty">Bu davrda sotuv yo‘q</div>')+'</div></div>'+
     '<div class="card"><div class="card-h"><h3>Kassa oqimi</h3></div><dl class="kv">'+
       '<dt>Naqd kirim</dt><dd class="num">'+uzs(cash.inCashUzs)+' · '+usd(cash.inCashUsd)+'</dd><dt>Karta kirim</dt><dd class="num">'+uzs(cash.inCardUzs)+' · '+usd(cash.inCardUsd)+'</dd>'+
       '<dt>Naqd chiqim</dt><dd class="num">'+uzs(cash.outCashUzs)+' · '+usd(cash.outCashUsd)+'</dd><dt>Karta chiqim</dt><dd class="num">'+uzs(cash.outCardUzs)+' · '+usd(cash.outCardUsd)+'</dd>'+
     '</dl></div>'+
   '</div>';
  bindAgentLinks($('rpBody'));
}

/* ----- Tahlil (insights) ----- */
var IN={period:'month',from:'',to:'',agent:'',q:'',tab:'plan',page:0};
var PRI={1:['Muhim','p-bad'],2:['O‘rta','p-warn'],3:['Past','p-pri']};
var KGRP={active:['Faol','p-ok'],low:['Faolligi past','p-warn'],passive:['Passiv','p-bad']};
function cents(c){return usd((c||0)/100)}
function grow(g){if(!g)return '';var cls=g.kind==='pct'?(g.pct>=0?'ok':'bad'):'muted';return '<span class="small '+cls+'" title="'+esc(g.text)+'">'+esc(g.kind==='pct'?g.text:g.kind==='started'?'yangi':g.kind==='zero'?'0':'—')+'</span>'}
async function pageInsights(page,force){
  var agents=(S.dash?S.dash.agents:[]).slice().sort(function(a,b){return a.name.localeCompare(b.name)});
  page.innerHTML='<div class="toolbar"><div class="seg" id="inSeg">'+[['today','Bugun'],['week','Hafta'],['month','Shu oy'],['custom','Davr']].map(function(x){return '<button data-p="'+x[0]+'" class="'+(IN.period===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
   '<span id="inCustom"'+(IN.period==='custom'?'':' hidden')+' class="actions"><input type="date" id="inFrom" value="'+esc(IN.from||today())+'" style="width:auto"><input type="date" id="inTo" value="'+esc(IN.to||today())+'" style="width:auto"><button class="btn pri" id="inGo">Ko‘rsatish</button></span>'+
   '<select id="inAgent" aria-label="Agent"><option value="">Barcha agentlar</option>'+agents.map(function(a){return '<option value="'+a.id+'"'+(String(IN.agent)===String(a.id)?' selected':'')+'>'+esc(a.name)+'</option>'}).join('')+'</select>'+
   '<span class="grow"></span><span class="muted" id="inLabel"></span></div><div id="inBody"><div class="grid g4">'+'<div class="skel"></div>'.repeat(4)+'</div></div>';
  $('inSeg').onclick=function(e){var b=e.target.closest('button');if(!b)return;IN.period=b.dataset.p;if(IN.period==='custom'){$('inSeg').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});$('inCustom').hidden=false;return}IN.page=0;pageInsights(page)};
  $('inGo').onclick=function(){IN.from=$('inFrom').value;IN.to=$('inTo').value;IN.page=0;pageInsights(page)};
  $('inAgent').onchange=function(){IN.agent=this.value;IN.page=0;pageInsights(page)};
  if(IN.period==='custom'&&!IN.from)return;
  var key='in'+IN.period+IN.from+IN.to+IN.agent,d=!force&&S.cache[key];
  if(!d){try{d=await api('insights',{period:IN.period,from:IN.from,to:IN.to,agentId:IN.agent?+IN.agent:undefined})}
    catch(e){if(S.page!=='insights'||!$('inBody')||!TOKEN)return;$('inBody').innerHTML=errState(e.message);$('inBody').querySelector('[data-retry]').onclick=function(){pageInsights(page,true)};return}
    S.cache[key]=d}
  if(S.page!=='insights')return;
  S.insights=d;$('inLabel').textContent=(d.label||'')+(d.compareLabel?' · taqqoslash: '+d.compareLabel:'');renderInsights();
}
function renderInsights(){
  var d=S.insights,sm=d.summary,plan=d.today||{items:[],total:0};
  var groups={active:0,low:0,passive:0},st={};
  d.clients.forEach(function(c){var k=c.kpi||{};if(k.status==='rated')groups[k.group]=(groups[k.group]||0)+1;else st[k.status]=(st[k.status]||0)+1});
  var tabs=[['plan',ic('target','sm')+' Bugun kimga',plan.total],['clients',ic('trend','sm')+' Mijozlar reytingi',d.clients.length],['regions',ic('map','sm')+' Hududlar',d.regions.length],['agents',ic('compass','sm')+' Agentlar',d.agents.length],['products',ic('box','sm')+' Mahsulotlar',d.products.length]];
  $('inBody').innerHTML=
   '<div class="grid g4" style="margin-bottom:16px">'+
     kpi('📦','Tovar berildi',cents(sm.deliveredCents),num(sm.deliveredQty)+' dona · '+(sm.deliveryGrowth?esc(sm.deliveryGrowth.text):''))+
     kpi('💰','To‘lov olindi',cents(sm.paidCents),sm.paymentGrowth?esc(sm.paymentGrowth.text):'')+
     kpi('🧾','Qarz (davr oxiri)',cents(sm.debtCents),sm.advanceCents?'Avans: '+cents(sm.advanceCents):'','bad')+
     kpi('🏪','Mijozlar',num(sm.clients),sm.rated+' baholangan · '+sm.prospects+' istiqbolli')+
   '</div>'+
   '<div class="card" style="margin-bottom:16px"><div class="card-h"><h3>Mijozlar faolligi</h3><span class="muted small">Ball: faollik + to‘lov intizomi + o‘sish (0–100)</span></div>'+
     '<div class="stack" style="margin-bottom:10px">'+[['active',C.forest],['low',C.yellow],['passive',C.orange]].map(function(g){return groups[g[0]]?'<i style="flex:'+groups[g[0]]+';background:'+g[1]+'"></i>':''}).join('')+'</div>'+
     '<div class="actions">'+Object.keys(KGRP).map(function(k){return pill(KGRP[k][0]+' · '+(groups[k]||0),KGRP[k][1])}).join('')+
       [['new','Yangi'],['prospect','Istiqbolli'],['nobase','Asos yo‘q'],['insufficient','Ma’lumot kam'],['incomplete','Hisob to‘liq emas'],['blacklisted','Qora ro‘yxat']].map(function(x){return st[x[0]]?pill(x[1]+' · '+st[x[0]]):''}).join('')+'</div></div>'+
   '<div class="tabs" id="inTabs">'+tabs.map(function(t){return '<button data-t="'+t[0]+'" class="'+(IN.tab===t[0]?'on':'')+'">'+t[1]+' <span class="muted">'+t[2]+'</span></button>'}).join('')+'</div>'+
   '<div id="inTab"></div>';
  $('inTabs').onclick=function(e){var b=e.target.closest('button');if(!b)return;IN.tab=b.dataset.t;IN.page=0;renderInsights()};
  ({plan:inPlan,clients:inClients,regions:inRegions,agents:inAgents,products:inProducts})[IN.tab]($('inTab'),d);
}
function inPlan(el,d){
  var p=d.today||{items:[],total:0};
  el.innerHTML='<div class="toolbar"><span class="muted">Davrdan qat’i nazar, joriy holat bo‘yicha. '+(p.total>p.items.length?'Eng muhim '+p.items.length+' tasi ko‘rsatildi (jami '+p.total+').':'')+'</span><span class="grow"></span><button class="btn" id="inExp">'+ic('download')+' Excel</button></div>'+
   '<div class="card flush"><div class="tbl-wrap"><table><thead><tr><th>Muhimlik</th><th>Mijoz</th><th>Agent</th><th>Sabab</th><th>Nima qilish kerak</th><th class="right">Qarz</th><th>Oxirgi tashrif</th></tr></thead><tbody>'+
   (p.items.length?p.items.map(function(i){var pr=PRI[i.priority]||PRI[3];return '<tr class="click" data-client="'+i.clientId+'"><td>'+pill(pr[0],pr[1])+'</td><td><b>'+esc(i.name)+'</b><br><small class="muted">'+esc(i.region)+'</small></td><td>'+esc(i.agent)+'</td><td>'+i.reasons.map(function(r){return esc(r.text)}).join('<br>')+'</td><td><b>'+esc(i.action)+'</b></td><td class="right num '+(i.debtNowCents>0?'bad':'')+'">'+(i.debtNowCents?cents(i.debtNowCents):'—')+'</td><td class="num">'+(i.lastVisitTs?dday(i.lastVisitTs):'—')+'</td></tr>'}).join(''):'<tr><td colspan="7" class="empty">'+ic('checkc','lg')+'<br>Bugun shoshilinch ish yo‘q</td></tr>')+
   '</tbody></table></div></div>';
  bindClientLinks(el);
  $('inExp').onclick=function(){exportRows(fileSlug()+'-bugungi-reja',['Muhimlik','Mijoz','Hudud','Agent','Sabab','Amal','Qarz USD','Oxirgi tashrif'],p.items.map(function(i){return [(PRI[i.priority]||PRI[3])[0],i.name,i.region,i.agent,i.reasons.map(function(r){return r.text}).join('; '),i.action,(i.debtNowCents||0)/100,i.lastVisitTs?dday(i.lastVisitTs):'']}))};
}
function inClients(el,d){
  var q=IN.q.trim().toLowerCase(),rows=d.clients.filter(function(c){return !q||(c.name+' '+c.agent+' '+c.region).toLowerCase().indexOf(q)>=0});
  var pages=Math.max(1,Math.ceil(rows.length/PAGE_SIZE));if(IN.page>=pages)IN.page=pages-1;
  var slice=rows.slice(IN.page*PAGE_SIZE,(IN.page+1)*PAGE_SIZE);
  var kp=function(k){if(!k)return '';if(k.status==='rated'){var g=KGRP[k.group]||['',''];return '<b class="num">'+k.score+'</b> '+pill(g[0],g[1])+(k.provisional?' <small class="muted" title="Taxminiy: davr hali tugamagan">~</small>':'')}return pill(esc(k.label),k.status==='blacklisted'?'p-bad':k.status==='new'?'p-pri':'')};
  el.innerHTML='<div class="toolbar"><input type="search" id="inQ" placeholder="Mijoz, agent yoki hudud…" value="'+esc(IN.q)+'"><span class="grow"></span><span class="muted small">'+num(rows.length)+' ta</span><button class="btn" id="inExp">'+ic('download')+' Excel</button></div>'+
   '<div class="card flush"><div class="tbl-wrap"><table><thead><tr><th class="right">#</th><th>Mijoz</th><th>Agent</th><th>Hudud</th><th>Ball</th><th class="right">Tovar</th><th class="right">To‘lov</th><th class="right">Qarz</th><th>O‘sish</th></tr></thead><tbody>'+
   (slice.length?slice.map(function(c){return '<tr class="click" data-client="'+c.id+'"><td class="right num muted">'+(c.rank||'')+'</td><td><b>'+esc(c.name)+'</b></td><td>'+esc(c.agent)+'</td><td>'+esc(c.region)+'</td><td>'+kp(c.kpi)+'</td><td class="right num">'+cents(c.deliveredCents)+'</td><td class="right num">'+cents(c.paidCents)+'</td><td class="right num '+(c.debtCents>0?'bad':'')+'">'+cents(c.debtCents)+'</td><td>'+grow(c.deliveryGrowth)+' / '+grow(c.paymentGrowth)+'</td></tr>'}).join(''):'<tr><td colspan="9" class="empty">Mijoz topilmadi</td></tr>')+
   '</tbody></table></div>'+(pages>1?'<div class="pager"><span>'+(IN.page*PAGE_SIZE+1)+'–'+Math.min(rows.length,(IN.page+1)*PAGE_SIZE)+' / '+num(rows.length)+'</span><span class="actions"><button class="btn sm" id="inPrev"'+(IN.page?'':' disabled')+'>‹ Oldingi</button><button class="btn sm" id="inNext"'+(IN.page<pages-1?'':' disabled')+'>Keyingi ›</button></span></div>':'')+'</div>';
  $('inQ').oninput=debounce(function(){IN.q=this.value;IN.page=0;inClients(el,d);var i=$('inQ');i.focus();i.setSelectionRange(i.value.length,i.value.length)},200);
  if($('inPrev'))$('inPrev').onclick=function(){IN.page--;inClients(el,d)};
  if($('inNext'))$('inNext').onclick=function(){IN.page++;inClients(el,d)};
  bindClientLinks(el);
  $('inExp').onclick=function(){exportRows(fileSlug()+'-mijozlar-reytingi',['O‘rin','Mijoz','Agent','Hudud','Ball','Guruh / holat','Tovar USD','To‘lov USD','Qarz USD','Tovar o‘sishi','To‘lov o‘sishi'],rows.map(function(c){var k=c.kpi||{};return [c.rank||'',c.name,c.agent,c.region,k.score==null?'':k.score,k.label||'',c.deliveredCents/100,c.paidCents/100,c.debtCents/100,c.deliveryGrowth?c.deliveryGrowth.text:'',c.paymentGrowth?c.paymentGrowth.text:'']}))};
}
function inRegions(el,d){
  el.innerHTML='<div class="toolbar"><span class="grow"></span><button class="btn" id="inExp">'+ic('download')+' Excel</button></div><div class="card flush"><div class="tbl-wrap"><table><thead><tr><th>Hudud</th><th class="right">Mijoz</th><th class="right">Istiqbolli</th><th class="right">Tovar</th><th class="right">To‘lov</th><th class="right">Qarz</th><th>O‘sish (tovar / to‘lov)</th></tr></thead><tbody>'+
   d.regions.map(function(r){return '<tr><td><b>'+esc(r.name)+'</b></td><td class="right num">'+r.clients+'</td><td class="right num">'+r.prospects+'</td><td class="right num">'+cents(r.deliveredCents)+'</td><td class="right num">'+cents(r.paidCents)+'</td><td class="right num '+(r.debtCents>0?'bad':'')+'">'+cents(r.debtCents)+'</td><td>'+grow(r.deliveryGrowth)+' / '+grow(r.paymentGrowth)+'</td></tr>'}).join('')+'</tbody></table></div></div>';
  $('inExp').onclick=function(){exportRows(fileSlug()+'-hududlar',['Hudud','Mijoz','Istiqbolli','Tovar USD','To‘lov USD','Qarz USD','Tovar o‘sishi','To‘lov o‘sishi'],d.regions.map(function(r){return [r.name,r.clients,r.prospects,r.deliveredCents/100,r.paidCents/100,r.debtCents/100,r.deliveryGrowth.text,r.paymentGrowth.text]}))};
}
function inAgents(el,d){
  el.innerHTML='<div class="toolbar"><span class="grow"></span><button class="btn" id="inExp">'+ic('download')+' Excel</button></div><div class="card flush"><div class="tbl-wrap"><table><thead><tr><th>Agent</th><th class="right">Mijozlar</th><th class="right">Tovar berdi</th><th class="right">Qaytarildi</th><th class="right">To‘lov oldi</th><th class="right">Portfel qarzi</th></tr></thead><tbody>'+
   d.agents.map(function(a){var o=a.operations;return '<tr class="click" data-agent="'+a.agentId+'"><td><b>'+esc(a.agent)+'</b></td><td class="right num">'+a.clients+'</td><td class="right num">'+cents(o.deliveredCents)+'</td><td class="right num">'+cents(o.returnedCents)+'</td><td class="right num">'+cents(o.paidCents)+'</td><td class="right num '+(a.debtCents>0?'bad':'')+'">'+cents(a.debtCents)+'</td></tr>'}).join('')+'</tbody></table></div></div>';
  bindAgentLinks(el);
  $('inExp').onclick=function(){exportRows(fileSlug()+'-agentlar',['Agent','Mijozlar','Tovar USD','Qaytarildi USD','To‘lov USD','Qarz USD'],d.agents.map(function(a){var o=a.operations;return [a.agent,a.clients,o.deliveredCents/100,o.returnedCents/100,o.paidCents/100,a.debtCents/100]}))};
}
function inProducts(el,d){
  el.innerHTML='<div class="toolbar"><span class="grow"></span><button class="btn" id="inExp">'+ic('download')+' Excel</button></div><div class="card flush"><div class="tbl-wrap"><table><thead><tr><th>Mahsulot</th><th class="right">Berildi</th><th class="right">Summa</th><th class="right">Qaytdi</th><th>O‘sish (dona / summa)</th></tr></thead><tbody>'+
   (d.products.length?d.products.map(function(p){return '<tr><td><b>'+esc(p.name)+'</b></td><td class="right num">'+num(p.deliveredQty)+'</td><td class="right num">'+cents(p.deliveredCents)+'</td><td class="right num">'+(p.returnedQty?num(p.returnedQty)+' · '+cents(p.returnedCents):'—')+'</td><td>'+grow(p.qtyGrowth)+' / '+grow(p.amountGrowth)+'</td></tr>'}).join(''):'<tr><td colspan="5" class="empty">Bu davrda tovar harakati yo‘q</td></tr>')+'</tbody></table></div></div>';
  $('inExp').onclick=function(){exportRows(fileSlug()+'-mahsulotlar',['Mahsulot','Berildi dona','Summa USD','Qaytdi dona','Qaytdi USD','Dona o‘sishi','Summa o‘sishi'],d.products.map(function(p){return [p.name,p.deliveredQty,p.deliveredCents/100,p.returnedQty,p.returnedCents/100,p.qtyGrowth.text,p.amountGrowth.text]}))};
}

/* ----- Excel eksport (ekranda ko'rinayotgan qatorlar) ----- */
function exportRows(name,head,rows){
  // UTF-16LE + BOM, tab bilan ajratilgan: Excel kirill/lotin harflarini va ustunlarni har qanday tilda to'g'ri ochadi.
  var cell=function(v){v=v==null?'':String(v);return /[\t\n"]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v};
  var text=[head].concat(rows).map(function(r){return r.map(cell).join('\t')}).join('\r\n');
  var buf=new Uint8Array(2+text.length*2);buf[0]=0xFF;buf[1]=0xFE;
  for(var i=0;i<text.length;i++){var c=text.charCodeAt(i);buf[2+i*2]=c&255;buf[3+i*2]=c>>8}
  var url=URL.createObjectURL(new Blob([buf],{type:'text/csv;charset=utf-16le'})),a=document.createElement('a');
  a.href=url;a.download=name+'-'+today()+'.csv';document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(url)},4000);
  toast(num(rows.length)+' qator yuklab olindi');
}

/* ----- Ta'minot: ta'minotchilar, xarid, xom ashyo, ishlab chiqarish (server: purchases.py) ----- */
var SP={view:store('rw-spview')||'suppliers',q:''};
function cents(n){return usd((n||0)/100)}
function spViewSeg(){return '<div class="seg" id="spView" aria-label="Ko‘rinish">'+[['suppliers','building','Ta’minotchilar'],['materials','box','Xom ashyo'],['purchases','receipt','Xaridlar'],['production','sliders','Ishlab chiqarish']].map(function(v){return '<button data-v="'+v[0]+'" class="'+(SP.view===v[0]?'on':'')+'">'+ic(v[1],'sm')+' '+v[2]+'</button>'}).join('')+'</div>'}
async function pageSupply(page,force){
  if(!S.cache.supply||force){if(!S.cache.supply)page.innerHTML='<div class="toolbar">'+spViewSeg()+'</div><div class="grid g4">'+'<div class="skel"></div>'.repeat(4)+'</div>';
    try{S.cache.supply=await api('supply',{op:'dashboard'})}catch(e){if(S.page==='supply'){page.innerHTML='<div class="toolbar">'+spViewSeg()+'</div>'+errState(e.message);bindSpView(page);page.querySelector('[data-retry]').onclick=function(){pageSupply(page,true)}}return}}
  if(S.page!=='supply')return;renderSupply(page,S.cache.supply);
}
function bindSpView(page){var el=$('spView');if(el)el.onclick=function(e){var b=e.target.closest('button');if(!b)return;SP.view=b.dataset.v;store('rw-spview',SP.view);renderSupply(page,S.cache.supply)}}
function spLines(lines){return lines.map(function(l){return esc(l.name)+' — '+esc(l.qty)+' '+esc(l.unit)+' × '+cents(l.price)}).join('<br>')}
function renderSupply(page,d){
  if(!d)return pageSupply(page,true);
  var sm=d.summary,can=!!d.canOperate,v=SP.view,body='';
  if(v==='suppliers'){
    body='<div class="card flush"><div class="card-h"><h3>'+ic('building')+' Ta’minotchilar</h3><span class="muted small">Qarz = xaridlar − to‘lovlar. Qatorni bosing — akt sverka</span></div><div class="tbl-wrap" style="margin-top:10px"><table><thead><tr><th>Nomi</th><th>Telefon</th><th>Izoh</th><th class="right">Bizning qarz</th>'+(can?'<th class="right">Amal</th>':'')+'</tr></thead><tbody>'+
      (d.suppliers.length?d.suppliers.map(function(s){return '<tr class="click" data-led="'+s.id+'"><td><b>'+esc(s.name)+'</b></td><td class="num">'+(s.phone?'<a href="tel:'+esc(s.phone)+'">'+esc(s.phone)+'</a>':'<span class="muted">—</span>')+'</td><td class="muted small">'+esc(s.note)+'</td><td class="right num'+(s.debt>0?' bad':'')+'">'+cents(s.debt)+'</td>'+
        (can?'<td class="right"><div class="actions" style="justify-content:flex-end"><button class="btn sm pri" data-pay="'+s.id+'"'+(s.debt>0?'':' disabled')+'>'+ic('coins','sm')+' To‘lash</button><button class="btn sm" data-sedit="'+s.id+'" aria-label="Tahrirlash">'+ic('edit','sm')+'</button></div></td>':'')+'</tr>'}).join('')
      :'<tr><td colspan="5">'+emptyState('Hali ta’minotchi yo‘q. «Ta’minotchi qo‘shish» tugmasini bosing.','building')+'</td></tr>')+'</tbody></table></div></div>';
  }else if(v==='materials'){
    body='<div class="grid g-main"><div class="card flush"><div class="card-h"><h3>'+ic('box')+' Xom ashyo qoldig‘i</h3><span class="muted small">Minimal qoldiqdan kam bo‘lsa qizil</span></div><div class="tbl-wrap" style="margin-top:10px"><table><thead><tr><th>Nomi</th><th class="right">Omborda</th><th class="right">Minimal</th>'+(can?'<th class="right">Amal</th>':'')+'</tr></thead><tbody>'+
      (d.materials.length?d.materials.map(function(m){return '<tr><td><b>'+esc(m.name)+'</b>'+(m.low?' '+pill('kam qoldi','p-bad'):'')+'</td><td class="right num'+(m.low||m.stockMilli<=0?' bad':'')+'">'+esc(m.stock)+' '+esc(m.unitLabel)+'</td><td class="right num muted">'+(m.min!=='0'?esc(m.min)+' '+esc(m.unitLabel):'—')+'</td>'+
        (can?'<td class="right"><div class="actions" style="justify-content:flex-end"><button class="btn sm" data-muse="'+m.id+'">'+ic('out','sm')+' Sarf</button><button class="btn sm danger" data-mwo="'+m.id+'">'+ic('trash','sm')+' Brak</button><button class="btn sm" data-medit="'+m.id+'" aria-label="Tahrirlash">'+ic('edit','sm')+'</button></div></td>':'')+'</tr>'}).join('')
      :'<tr><td colspan="4">'+emptyState('Hali xom ashyo yo‘q. «Xom ashyo qo‘shish» tugmasini bosing.','box')+'</td></tr>')+'</tbody></table></div></div>'+
      '<div class="card"><div class="card-h"><h3>'+ic('list')+' Xom ashyo harakati</h3></div><div class="list">'+(d.materialMoves.length?d.materialMoves.map(function(m){var t=m.kind==='in'?['in','t-green','+']:m.kind==='use'?['out','t-blue','−']:['trash','t-red','−'];
        return '<div class="li"><span class="tone '+t[1]+'" style="width:32px;height:32px;border-radius:9px">'+ic(t[0],'sm')+'</span><div class="t"><b>'+esc(m.label)+' · '+t[2]+esc(m.qty)+' '+esc(m.unit)+'</b><small>'+esc(m.name)+(m.note?' · '+esc(m.note):'')+(m.actorName?' · '+esc(m.actorName):'')+'</small></div><small class="muted num">'+ago(m.ts)+'</small></div>'}).join(''):emptyState('Harakat yo‘q','list'))+'</div></div></div>';
  }else if(v==='purchases'){
    body='<div class="card flush"><div class="card-h"><h3>'+ic('receipt')+' Oxirgi xaridlar</h3><span class="muted small">Mahsulot omborga, xom ashyo xom ashyo omboriga avtomatik kirim bo‘ladi</span></div><div class="tbl-wrap" style="margin-top:10px"><table><thead><tr><th>№</th><th>Sana</th><th>Ta’minotchi</th><th>Tarkibi</th><th class="right">Summa</th></tr></thead><tbody>'+
      (d.purchases.length?d.purchases.map(function(p){return '<tr><td class="num">#'+p.id+'</td><td class="num">'+dt(p.ts)+'</td><td><b>'+esc(p.supplierName)+'</b>'+(p.note?'<br><small class="muted">'+esc(p.note)+'</small>':'')+'</td><td class="small">'+spLines(p.lines)+'</td><td class="right num"><b>'+cents(p.total)+'</b></td></tr>'}).join('')
      :'<tr><td colspan="5">'+emptyState('Hali xarid kiritilmagan.','receipt')+'</td></tr>')+'</tbody></table></div></div>';
  }else{
    body='<div class="card flush"><div class="card-h"><h3>'+ic('sliders')+' Ishlab chiqarish</h3><span class="muted small">Xom ashyo sarflanadi, tayyor mahsulot omborga kirim bo‘ladi</span></div><div class="tbl-wrap" style="margin-top:10px"><table><thead><tr><th>№</th><th>Sana</th><th>Mahsulot</th><th class="right">Miqdor</th><th>Kim</th></tr></thead><tbody>'+
      (d.productions.length?d.productions.map(function(p){return '<tr><td class="num">#'+p.id+'</td><td class="num">'+dt(p.ts)+'</td><td><b>'+esc(p.name)+'</b>'+(p.note?'<br><small class="muted">'+esc(p.note)+'</small>':'')+'</td><td class="right num">'+num(p.qty)+' dona</td><td class="muted">'+esc(p.actorName)+'</td></tr>'}).join('')
      :'<tr><td colspan="5">'+emptyState('Hali ishlab chiqarish kiritilmagan.','sliders')+'</td></tr>')+'</tbody></table></div></div>';
  }
  page.innerHTML='<div class="toolbar">'+spViewSeg()+'<span class="grow"></span>'+(can?
      '<button class="btn pri" data-sop="purchase">'+ic('cart','sm')+' Yangi xarid</button><button class="btn" data-sop="produce">'+ic('sliders','sm')+' Ishlab chiqarish</button>'+
      '<button class="btn" data-sop="supplier_add">'+ic('plus','sm')+' Ta’minotchi</button><button class="btn" data-sop="material_add">'+ic('plus','sm')+' Xom ashyo</button>'
      :'<span class="pill">'+ic('shield','sm')+' Faqat ko‘rish — amallarni asosiy rahbar kiritadi</span>')+'</div>'+
    '<div class="grid g4 kpis" style="margin-bottom:16px">'+
      kpi('dollar','Ta’minotchilarga qarz',cents(sm.totalDebt),sm.suppliers+' ta ta’minotchi',sm.totalDebt>0?'bad':'')+
      kpi('cart','Shu oy xarid',cents(sm.monthBought),'')+kpi('coins','Shu oy to‘langan',cents(sm.monthPaid),'kassadan')+
      kpi('box','Kam qolgan xom ashyo',num(sm.lowMaterials),sm.materials+' xil xom ashyo',sm.lowMaterials?'bad':'')+'</div>'+body;
  bindSpView(page);
  page.querySelectorAll('[data-led]').forEach(function(tr){tr.onclick=function(e){if(e.target.closest('button,a'))return;openLedger(+tr.dataset.led)}});
  var call=async function(op,args,msg){try{var r=await api('supply',Object.assign({op:op,requestId:rid()},args));S.cache.supply=r;S.cache.stock=null;S.cache.wh=null;S.cache.whAll=null;toast(msg);renderSupply(page,r);return r}catch(e){toast(e.message,true);return null}};
  var supOpts=d.suppliers.map(function(s){return [s.id,s.name+(s.debt>0?' — qarz '+cents(s.debt):'')]});
  var prodOpts=d.products.map(function(p){return [p.pack,p.name+' — omborda '+num(p.stock)]});
  page.querySelectorAll('[data-sop]').forEach(function(b){b.onclick=async function(){var op=b.dataset.sop,v;
    if(op==='supplier_add'){v=await formBox('Yangi ta’minotchi',[{name:'name',label:'Nomi',required:true},{name:'phone',label:'Telefon',placeholder:'+998…'},{name:'note',label:'Izoh (nima yetkazadi, shartlar)'}],'Qo‘shish');if(v)call(op,v,'Ta’minotchi qo‘shildi')}
    else if(op==='material_add'){v=await formBox('Yangi xom ashyo',[{name:'name',label:'Nomi',required:true},{name:'unit',label:'O‘lchov birligi',options:d.units},{name:'minQty',label:'Minimal qoldiq (ixtiyoriy)',type:'number',step:'any'}],'Qo‘shish','Qoldiq shu miqdordan kamaysa, panelda ogohlantirish chiqadi.');if(v){v.minQty=v.minQty||'';call(op,v,'Xom ashyo qo‘shildi')}}
    else if(op==='purchase'){if(!d.suppliers.length){toast('Avval ta’minotchi qo‘shing.',true);return}purchaseForm(d,call)}
    else{if(!prodOpts.length){toast('Faol mahsulot yo‘q.',true);return}produceForm(d,prodOpts,call)}}});
  page.querySelectorAll('[data-pay]').forEach(function(b){b.onclick=async function(){var s=d.suppliers.find(function(x){return x.id===+b.dataset.pay});
    var v=await formBox('To‘lov: '+s.name,[{name:'amount',label:'Summa (USD)',type:'number',step:'0.01',required:true,value:(s.debt/100).toFixed(2)},{name:'payFrom',label:'Qayerdan',options:[['cash','Kassa — naqd'],['card','Kassa — karta']]},{name:'note',label:'Izoh'}],'To‘lash','Joriy qarz: '+cents(s.debt)+'. Summa kassadan xarajat bo‘lib chiqadi.');
    if(v)call('pay',Object.assign(v,{supplierId:s.id}),'To‘lov saqlandi')}});
  page.querySelectorAll('[data-sedit]').forEach(function(b){b.onclick=async function(){var s=d.suppliers.find(function(x){return x.id===+b.dataset.sedit});
    var v=await formBox('Ta’minotchini tahrirlash',[{name:'name',label:'Nomi',required:true,value:s.name},{name:'phone',label:'Telefon',value:s.phone},{name:'note',label:'Izoh',value:s.note}],'Saqlash');if(v)call('supplier_edit',Object.assign(v,{supplierId:s.id}),'Saqlandi')}});
  page.querySelectorAll('[data-medit]').forEach(function(b){b.onclick=async function(){var m=d.materials.find(function(x){return x.id===+b.dataset.medit});
    var v=await formBox('Xom ashyoni tahrirlash',[{name:'name',label:'Nomi',required:true,value:m.name},{name:'minQty',label:'Minimal qoldiq ('+m.unitLabel+')',type:'number',step:'any',value:m.min==='0'?'':m.min}],'Saqlash');if(v)call('material_edit',Object.assign(v,{materialId:m.id}),'Saqlandi')}});
  page.querySelectorAll('[data-muse],[data-mwo]').forEach(function(b){b.onclick=async function(){var wo=!!b.dataset.mwo,m=d.materials.find(function(x){return x.id===+(b.dataset.muse||b.dataset.mwo)});
    var v=await formBox((wo?'Brak / hisobdan chiqarish: ':'Sarf: ')+m.name,[{name:'qty',label:'Miqdor ('+m.unitLabel+')',type:'number',step:'any',required:true},{name:'note',label:wo?'Sabab':'Izoh',required:wo}],wo?'Hisobdan chiqarish':'Saqlash','Omborda: '+esc(m.stock)+' '+esc(m.unitLabel));
    if(v)call(wo?'material_writeoff':'material_use',Object.assign(v,{materialId:m.id}),'Saqlandi')}});
}
function lineRow(i,opts){return '<div class="sp-line" data-i="'+i+'"><select name="item_'+i+'" aria-label="Mahsulot yoki xom ashyo">'+opts+'</select><input name="qty_'+i+'" type="number" step="any" min="0" placeholder="Miqdor" aria-label="Miqdor" required><input name="price_'+i+'" type="number" step="0.01" min="0" placeholder="Narx $" aria-label="Bir birlik narxi, USD" required><button type="button" class="icon-btn ghost" data-rm aria-label="Qatorni o‘chirish">'+ic('x','sm')+'</button></div>'}
function itemOpts(d,withProducts){
  var m=d.materials.map(function(x){return '<option value="m:'+x.id+'">'+esc(x.name)+' ('+esc(x.unitLabel)+')</option>'}).join('');
  var p=withProducts?d.products.map(function(x){return '<option value="p:'+x.pack+'">'+esc(x.name)+' (dona)</option>'}).join(''):'';
  return (m?'<optgroup label="Xom ashyo">'+m+'</optgroup>':'')+(p?'<optgroup label="Tayyor mahsulot">'+p+'</optgroup>':'');
}
function bindLines(box,opts,first){var n=first;
  box.querySelector('[data-add]').onclick=function(){box.querySelector('.sp-lines').insertAdjacentHTML('beforeend',lineRow(n++,opts));sumLines(box)};
  box.addEventListener('click',function(e){var b=e.target.closest('[data-rm]');if(!b)return;var rows=box.querySelectorAll('.sp-line');if(rows.length>1){b.closest('.sp-line').remove();sumLines(box)}});
  box.addEventListener('input',function(){sumLines(box)});
}
function sumLines(box){var t=0;box.querySelectorAll('.sp-line').forEach(function(r){var q=parseFloat(r.querySelector('[name^=qty_]').value)||0,p=r.querySelector('[name^=price_]');p=p?parseFloat(p.value)||0:0;t+=q*p});var el=box.querySelector('[data-total]');if(el)el.textContent=usd(Math.round(t*100)/100)}
function collectLines(v,kind){var out=[];Object.keys(v).forEach(function(k){var m=/^item_(\d+)$/.exec(k);if(!m)return;var i=m[1],it=String(v[k]).split(':'),row={qty:v['qty_'+i]};
  if(kind==='purchase')row.price=v['price_'+i];if(it[0]==='m')row.material=+it[1];else row.pack=+it[1];out.push(row)});return out}
async function purchaseForm(d,call){
  var opts=itemOpts(d,true);
  var p=modal('<form class="sp-form"><h3>Yangi xarid</h3><p class="muted">Har qatorda bir birlik narxi (USD): mahsulot uchun 1 dona, xom ashyo uchun 1 kg / litr / …</p><div class="form">'+
    '<label>Ta’minotchi<select name="supplierId">'+d.suppliers.map(function(s){return '<option value="'+s.id+'">'+esc(s.name)+'</option>'}).join('')+'</select></label>'+
    '<div class="sp-lines">'+lineRow(0,opts)+'</div><button type="button" class="btn sm" data-add>'+ic('plus','sm')+' Qator qo‘shish</button>'+
    '<label>Izoh (hujjat raqami, partiya)<input name="note" maxlength="300"></label><div class="sp-total">Jami: <b data-total>$0</b></div></div>'+
    '<div class="foot"><button type="button" class="btn" data-m="cancel">Bekor qilish</button><button class="btn pri">Xaridni saqlash</button></div></form>');
  bindLines($('modalBody'),opts,1);
  var v=await p;if(!v)return;
  call('purchase',{supplierId:+v.supplierId,note:v.note,lines:collectLines(v,'purchase')},'Xarid saqlandi');
}
async function produceForm(d,prodOpts,call){
  var opts=itemOpts(d,false);
  if(!opts){toast('Avval xom ashyo qo‘shing va xarid qiling.',true);return}
  var row=function(i){return lineRow(i,opts).replace(/<input name="price_[^>]*>/,'')};
  var p=modal('<form class="sp-form"><h3>Ishlab chiqarish</h3><p class="muted">Sarflangan xom ashyo ombordan chiqadi, tayyor mahsulot omborga kirim bo‘ladi.</p><div class="form">'+
    '<label>Tayyor mahsulot<select name="pack">'+prodOpts.map(function(o){return '<option value="'+o[0]+'">'+esc(o[1])+'</option>'}).join('')+'</select></label>'+
    '<label>Miqdor (dona)<input name="pack_qty" type="number" min="1" step="1" required></label>'+
    '<b class="small">Sarflangan xom ashyo</b><div class="sp-lines sp-noprice">'+row(0)+'</div><button type="button" class="btn sm" data-add>'+ic('plus','sm')+' Xom ashyo qo‘shish</button>'+
    '<label>Izoh (smena, partiya)<input name="note" maxlength="300"></label></div>'+
    '<div class="foot"><button type="button" class="btn" data-m="cancel">Bekor qilish</button><button class="btn pri">Saqlash</button></div></form>');
  var box=$('modalBody'),n=1;
  box.querySelector('[data-add]').onclick=function(){box.querySelector('.sp-lines').insertAdjacentHTML('beforeend',row(n++))};
  box.addEventListener('click',function(e){var b=e.target.closest('[data-rm]');if(b&&box.querySelectorAll('.sp-line').length>1)b.closest('.sp-line').remove()});
  var v=await p;if(!v)return;
  call('produce',{pack:+v.pack,qty:+v.pack_qty,note:v.note,inputs:collectLines(v,'produce')},'Ishlab chiqarish saqlandi');
}
async function openLedger(id){
  openDrawer(drawerSkel());
  var r=await run(function(){return api('supply',{op:'ledger',supplierId:id})});if(!r){closeDrawer();return}
  var s=r.supplier;
  openDrawer('<div class="dh"><span class="tone t-violet" style="width:60px;height:60px;border-radius:18px">'+ic('building','lg')+'</span><div><h2>'+esc(s.name)+'</h2><small class="muted">'+(s.phone?esc(s.phone)+' · ':'')+'Akt sverka</small></div></div>'+
    '<div class="grid g3" style="margin:14px 0">'+kpi('dollar','Bizning qarz',cents(r.debt),'',r.debt>0?'bad':'')+'</div>'+
    '<div class="card flush"><div class="tbl-wrap"><table><thead><tr><th>Sana</th><th>Hujjat</th><th class="right">Xarid</th><th class="right">To‘lov</th></tr></thead><tbody>'+
    (r.items.length?r.items.map(function(i){var buy=i.type==='purchase';return '<tr><td class="num">'+dt(i.ts)+'</td><td>'+(buy?'<b>Xarid #'+i.id+'</b><br><small class="muted">'+spLines(i.lines)+'</small>':'<b>To‘lov #'+i.id+'</b><br><small class="muted">'+(i.payFrom==='card'?'Karta':'Naqd')+'</small>')+(i.note?'<br><small class="muted">'+esc(i.note)+'</small>':'')+'</td><td class="right num">'+(buy?cents(i.amount):'')+'</td><td class="right num ok">'+(buy?'':cents(i.amount))+'</td></tr>'}).join('')
      :'<tr><td colspan="4">'+emptyState('Harakat yo‘q','list')+'</td></tr>')+'</tbody></table></div></div>');
}

/* ----- Ombor ----- */
var WH={status:'open',view:store('rw-whview')||'board',q:'',agent:'',open:{}};
/* Kanban ustunlari = backenddagi buyurtma statuslari (core.ORDER_STATUSES). Rang semantik. */
var KB=[['new','Yangi','c-yellow',C.yellow],['preparing','Tayyorlanmoqda','',C.pri],['loaded','Agentga berildi','c-forest',C.forest],['delivered','Yetkazildi','',C.gray],['rejected','Rad etildi','c-orange',C.orange]];
function whViewSeg(){return '<div class="seg" id="whView" aria-label="Ko‘rinish">'+[['board','orders','Buyurtmalar'],['stock','warehouse','Ombor'],['list','list','Ro‘yxat va katalog']].map(function(v){return '<button data-v="'+v[0]+'" class="'+(WH.view===v[0]?'on':'')+'">'+ic(v[1],'sm')+' '+v[2]+'</button>'}).join('')+'</div>'}
function bindWhView(page){var el=$('whView');if(el)el.onclick=function(e){var b=e.target.closest('button');if(!b)return;WH.view=b.dataset.v;store('rw-whview',WH.view);pageWarehouse(page,true)}}
var NEXT={new:[['preparing','Tayyorlashga olish'],['rejected','Rad etish']],preparing:[['new','Yangiga qaytarish'],['rejected','Rad etish']],loaded:[['delivered','Yetkazildi']],rejected:[['new','Qayta ochish']],delivered:[]};
async function pageWarehouse(page,force){
  if(WH.view==='board')return pageBoard(page,force);
  if(WH.view==='stock')return pageStock(page,force);
  if(!S.cache.wh||force||S.cache.wh.filter!==WH.status||WH.status==='all'){if(WH.status==='all')WH.status='open';page.innerHTML='<div class="loading">Ombor yuklanmoqda…</div>';var w=await run(function(){return api('warehouse',{status:WH.status})});if(!w)return;S.cache.wh=w}
  if(S.page!=='warehouse')return;renderWarehouse(page,S.cache.wh);
}
/* ----- Ombor: qoldiq va amallar (Ombor Mini App bilan bir xil server funksiyalari) ----- */
var MV={in:['Kirim','in','t-green'],issue:['Agentga berildi','truck','t-blue'],agent_return:['Agentdan qabul','swap','t-cyan'],writeoff:['Brak / hisobdan chiqarildi','trash','t-red']};
function rid(){return 'w'+Date.now().toString(36)+Math.random().toString(36).slice(2,10)}
async function pageStock(page,force){
  if(!S.cache.stock||force){if(!S.cache.stock)page.innerHTML='<div class="toolbar">'+whViewSeg()+'</div><div class="grid g4">'+'<div class="skel"></div>'.repeat(4)+'</div>';
    try{S.cache.stock=await api('stock',{op:'dashboard'})}catch(e){if(S.page==='warehouse'){page.innerHTML='<div class="toolbar">'+whViewSeg()+'</div>'+errState(e.message);bindWhView(page);page.querySelector('[data-retry]').onclick=function(){pageStock(page,true)}}return}}
  if(S.page!=='warehouse'||WH.view!=='stock')return;renderStock(page,S.cache.stock);
}
function renderStock(page,w){
  var prods=w.products.filter(function(p){return p.active!==false||p.stock}),tot=prods.reduce(function(a,p){return a+p.stock},0),T=w.today||{};
  var unit=function(p,n){return p.block?num(n)+' dona <small class="muted">('+Math.floor(n/p.block)+' blok + '+(n%p.block)+')</small>':num(n)+' dona'};
  var can=!!w.canOperate;
  page.innerHTML='<div class="toolbar">'+whViewSeg()+'<span class="grow"></span>'+(can?
     '<button class="btn pri" data-op="receive">'+ic('in','sm')+' Kirim</button><button class="btn" data-op="issue">'+ic('truck','sm')+' Agentga berish</button>'+
     '<button class="btn" data-op="take_back">'+ic('swap','sm')+' Agentdan qaytarish</button><button class="btn danger" data-op="writeoff">'+ic('trash','sm')+' Brak</button>'
     :'<span class="pill">'+ic('shield','sm')+' Faqat ko‘rish — tovar harakatini omborchi yoki asosiy rahbar kiritadi</span>')+'</div>'+
   '<div class="grid g4 kpis" style="margin-bottom:16px">'+
     kpi('🏬','Omborda jami',num(tot)+' dona',prods.length+' xil mahsulot')+kpi('box','Bugun kirim',num(T['in']||0)+' dona','')+
     kpi('🚚','Bugun agentlarga',num(T.issue||0)+' dona','')+kpi('⏳','Kutilayotgan so‘rov',num(w.requests.length),'agentlardan')+'</div>'+
   (w.requests.length?'<div class="card flush" style="margin-bottom:16px"><div class="card-h"><h3>'+ic('bell')+' Agent so‘rovlari</h3><span class="muted small">tasdiqlang yoki rad eting</span></div><div class="tbl-wrap" style="margin-top:10px"><table><thead><tr><th>№</th><th>Turi</th><th>Agent</th><th>Mahsulot</th><th class="right">Miqdor</th><th>Sana</th><th class="right">Amal</th></tr></thead><tbody>'+
     w.requests.map(function(r){var p=prods.find(function(x){return x.pack===r.pack})||{name:'#'+r.pack};return '<tr><td class="num">#'+r.id+'</td><td>'+pill(r.kind==='need'?'Tovar so‘rovi':'Omborga qaytarish',r.kind==='need'?'p-pri':'p-warn')+'</td><td><b>'+esc(r.agent_name)+'</b>'+(r.note?'<br><small class="muted">'+esc(r.note)+'</small>':'')+'</td><td>'+esc(p.name)+'</td><td class="right num">'+num(r.qty)+' dona</td><td class="num">'+dt(r.ts)+'</td>'+
       '<td class="right">'+(can?'<div class="actions" style="justify-content:flex-end"><button class="btn sm pri" data-dec="'+r.id+'" data-ok="1">'+ic('check','sm')+' Qabul</button><button class="btn sm danger" data-dec="'+r.id+'">'+ic('x','sm')+' Rad</button></div>':'<span class="muted small">omborchida</span>')+'</td></tr>'}).join('')+'</tbody></table></div></div>':'')+
   '<div class="grid g-main"><div class="card flush"><div class="card-h"><h3>'+ic('warehouse')+' Qoldiq</h3><input type="search" id="stQ2" placeholder="Mahsulot…" style="max-width:220px"></div><div class="tbl-wrap" style="margin-top:10px"><table><thead><tr><th>Mahsulot</th><th class="right">Omborda</th><th class="right">Buyurtmalarga kerak</th><th class="right">Agentlarda</th></tr></thead><tbody id="stBody">'+
     prods.map(function(p){var ag=w.agents.reduce(function(a,x){return a+(x.stock[String(p.pack)]||0)},0),short=p.demand>p.stock;
       return '<tr data-name="'+esc(p.name.toLowerCase())+'"><td><b>'+esc(p.name)+'</b>'+(p.active===false?' '+pill('nofaol'):'')+'</td><td class="right num'+(p.stock<=0?' bad':'')+'">'+unit(p,p.stock)+'</td><td class="right num'+(short?' bad':'')+'">'+(p.demand?num(p.demand)+' dona'+(short?' '+ic('alert','sm'):''):'<span class="muted">—</span>')+'</td><td class="right num">'+num(ag)+' dona</td></tr>'}).join('')+'</tbody></table></div></div>'+
   '<div class="card"><div class="card-h"><h3>'+ic('list')+' Oxirgi harakatlar</h3></div><div class="list">'+(w.moves.length?w.moves.slice(0,25).map(function(m){var k=MV[m.kind]||[m.kind,'box','t-blue'],p=prods.find(function(x){return x.pack===m.pack})||{name:'#'+m.pack};
       return '<div class="li"><span class="tone '+k[2]+'" style="width:32px;height:32px;border-radius:9px">'+ic(k[1],'sm')+'</span><div class="t"><b>'+esc(k[0])+' · '+num(m.qty)+' dona</b><small>'+esc(p.name)+(m.agent_name?' · '+esc(m.agent_name):'')+(m.note?' · '+esc(m.note):'')+'</small></div><small class="muted num">'+ago(m.ts)+'</small></div>'}).join(''):emptyState('Harakat yo‘q','list'))+'</div></div></div>';
  bindWhView(page);
  $('stQ2').oninput=function(){var q=this.value.trim().toLowerCase();$('stBody').querySelectorAll('tr').forEach(function(tr){tr.hidden=q&&tr.dataset.name.indexOf(q)<0})};
  var popts=prods.filter(function(p){return p.active!==false}).map(function(p){return [p.pack,p.name+' — omborda '+num(p.stock)]}),aopts=w.agents.map(function(a){return [a.id,a.name]});
  var done=function(r,msg){if(r){S.cache.stock=r;S.cache.whAll=null;S.cache.wh=null;toast(msg);renderStock(page,r)}};
  var call=async function(op,args,msg){try{done(await api('stock',Object.assign({op:op,requestId:rid()},args)),msg)}catch(e){toast(e.message,true)}};
  var units=[['Дона','Dona'],['Блок','Blok']];
  page.querySelectorAll('[data-op]').forEach(function(b){b.onclick=async function(){var op=b.dataset.op,v;
    if(op==='receive'){v=await formBox('Omborga kirim',[{name:'pack',label:'Mahsulot',options:popts},{name:'qty',label:'Miqdor',type:'number',required:true},{name:'unit',label:'O‘lchov',options:units},{name:'note',label:'Izoh (yetkazib beruvchi, hujjat)'}],'Kirim qilish');if(v)call('receive',v,'Kirim saqlandi')}
    else if(op==='issue'){v=await formBox('Agentga tovar berish',[{name:'agent',label:'Agent',options:aopts},{name:'pack',label:'Mahsulot',options:popts},{name:'qty',label:'Miqdor',type:'number',required:true},{name:'unit',label:'O‘lchov',options:units},{name:'note',label:'Izoh'}],'Berish','Agent qoldig‘iga qo‘shiladi va unga Telegram orqali xabar boradi.');if(v)call('issue',v,'Agentga berildi')}
    else if(op==='take_back'){v=await formBox('Agentdan omborga qaytarish',[{name:'agent',label:'Agent',options:aopts},{name:'pack',label:'Mahsulot',options:popts},{name:'qty',label:'Miqdor',type:'number',required:true},{name:'unit',label:'O‘lchov',options:units},{name:'note',label:'Izoh'}],'Qabul qilish');if(v)call('take_back',v,'Omborga qabul qilindi')}
    else{v=await formBox('Brak / hisobdan chiqarish',[{name:'pack',label:'Mahsulot',options:popts},{name:'qty',label:'Miqdor',type:'number',required:true},{name:'unit',label:'O‘lchov',options:units},{name:'note',label:'Sabab',required:true}],'Hisobdan chiqarish');if(v)call('writeoff',v,'Hisobdan chiqarildi')}}});
  page.querySelectorAll('[data-dec]').forEach(function(b){b.onclick=async function(){var ok=!!b.dataset.ok;
    if(!await confirmBox(ok?'So‘rovni qabul qilish':'So‘rovni rad etish','<p>So‘rov #'+b.dataset.dec+(ok?' qabul qilinadi va qoldiq yangilanadi.':' rad etiladi.')+' Agentga xabar boradi.</p>',ok?'Qabul qilish':'Rad etish',!ok))return;
    call('decide',{id:+b.dataset.dec,accepted:ok},ok?'Qabul qilindi':'Rad etildi')}});
}
async function pageBoard(page,force){
  if(!S.cache.whAll||force){if(!S.cache.whAll)page.innerHTML='<div class="toolbar">'+whViewSeg()+'</div><div class="kanban">'+'<div class="skel" style="height:420px"></div>'.repeat(5)+'</div>';
    var w=await run(function(){return api('warehouse',{status:'all'})});if(!w)return;S.cache.whAll=w;S.cache.wh=null}
  if(S.page!=='warehouse')return;renderBoard(page,S.cache.whAll);
}
function orderSum(o){return o.totalCents/100}
function renderBoard(page,w){
  var q=WH.q.trim().toLowerCase(),agents={};w.orders.forEach(function(o){agents[o.agentId]=o.agentName});
  var rows=w.orders.filter(function(o){if(WH.agent&&String(o.agentId)!==String(WH.agent))return false;if(q&&(o.clientName+' '+o.agentName+' #'+o.id+' '+o.items.map(function(i){return i.name}).join(' ')).toLowerCase().indexOf(q)<0)return false;return true});
  var open=rows.filter(function(o){return o.status==='new'||o.status==='preparing'||o.status==='loaded'});
  page.innerHTML=
   '<div class="card" style="margin-bottom:16px"><div class="stat-strip">'+
     '<div class="st"><span class="round-btn">'+ic('box','sm')+'</span><div><b>'+open.length+'</b><small>Ochiq buyurtmalar</small></div></div>'+
     '<div class="st"><span class="round-btn">'+ic('dollar','sm')+'</span><div><b>'+usd(open.reduce(function(a,o){return a+orderSum(o)},0))+'</b><small>Ochiq buyurtmalar summasi</small></div></div>'+
     '<div class="st"><span class="round-btn">'+ic('sparkle','sm')+'</span><div><b>'+(w.counts.new||0)+(w.counts.new?'<span class="pill-badge y">yangi</span>':'')+'</b><small>Tasdiq kutmoqda</small></div></div>'+
     '<div class="st"><span class="round-btn">'+ic('help','sm')+'</span><div><b>'+(w.demand||[]).length+'</b><small>Katalogda yo‘q nomlar</small></div></div>'+
   '</div></div>'+
   '<div class="toolbar">'+whViewSeg()+'<input type="search" id="kbQ" placeholder="Buyurtma, mijoz, agent, tovar…" value="'+esc(WH.q)+'">'+
     '<select id="kbAgent" aria-label="Agent"><option value="">Barcha agentlar</option>'+Object.keys(agents).map(function(id){return '<option value="'+id+'"'+(String(WH.agent)===id?' selected':'')+'>'+esc(agents[id])+'</option>'}).join('')+'</select>'+
     '<span class="grow"></span><span class="muted small">Kartani sudrab statusini o‘zgartiring — faqat ruxsat etilgan o‘tishlar ishlaydi. «Agentga berildi»ni omborchi qo‘yadi.</span></div>'+
   '<div class="kanban" id="kanban">'+KB.map(function(col){var list=rows.filter(function(o){return o.status===col[0]}).sort(function(a,b){return (b.updatedTs||b.ts)-(a.updatedTs||a.ts)}),
       all=list,full=WH.open[col[0]]||!!q;list=full?all:all.slice(0,3);
     return '<section class="kcol" data-st="'+col[0]+'" aria-label="'+col[1]+'"><header><span class="dot" style="color:'+col[3]+'"></span><b>'+col[1]+'</b><span class="pill">'+all.length+'</span><small class="muted">'+usd(all.reduce(function(a,o){return a+orderSum(o)},0))+'</small></header>'+
       '<div class="kbody">'+(list.length?list.map(function(o){return '<article class="kcard card lift '+col[2]+'" draggable="true" tabindex="0" data-oid="'+o.id+'" data-st="'+o.status+'" aria-label="Buyurtma #'+o.id+'">'+
         '<div class="kc-top"><small>#'+o.id+' · '+dday(o.ts)+'</small><span class="round-btn sm-dots" aria-hidden="true">'+ic('list','sm')+'</span></div>'+
         '<b class="kc-title">'+esc(o.clientName)+'</b><small>'+esc(o.agentName)+' · '+o.items.length+' xil tovar'+(o.unmapped?' · <u>'+o.unmapped+' katalogda yo‘q</u>':'')+'</small>'+
         '<div class="kc-foot"><b>'+usd(orderSum(o))+'</b><small>'+(o.updatedTs&&o.updatedTs!==o.ts?ago(o.updatedTs):'')+'</small></div></article>'}).join(''):'<div class="kempty">Bo‘sh</div>')+'</div>'+
       (all.length>3&&!q?'<button class="kmore" data-more="'+col[0]+'">'+(full?ic('chevron','sm flip')+' Yig‘ish':'Barchasini ko‘rish ('+all.length+') '+ic('chevron','sm'))+'</button>':'')+'</section>'}).join('')+'</div>';
  $('kbQ').oninput=debounce(function(){WH.q=this.value;renderBoard(page,w);var i=$('kbQ');i.focus();i.setSelectionRange(i.value.length,i.value.length)},200);
  $('kbAgent').onchange=function(){WH.agent=this.value;renderBoard(page,w)};
  page.querySelectorAll('[data-more]').forEach(function(b){b.onclick=function(){var k=b.dataset.more;WH.open[k]=!WH.open[k];renderBoard(page,w)}});
  bindWhView(page);
  var kb=$('kanban'),drag=null;
  kb.querySelectorAll('.kcard').forEach(function(card){
    var o=w.orders.find(function(x){return String(x.id)===card.dataset.oid});
    card.onclick=function(){orderModal(o,page)};
    card.onkeydown=function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();orderModal(o,page)}};
    card.addEventListener('dragstart',function(e){drag=o;e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',String(o.id));card.classList.add('dragging');
      var ok=(NEXT[o.status]||[]).map(function(n){return n[0]});kb.querySelectorAll('.kcol').forEach(function(c){c.classList.toggle('can',ok.indexOf(c.dataset.st)>=0);c.classList.toggle('cant',ok.indexOf(c.dataset.st)<0&&c.dataset.st!==o.status)})});
    card.addEventListener('dragend',function(){card.classList.remove('dragging');kb.querySelectorAll('.kcol').forEach(function(c){c.classList.remove('can','cant','over')});drag=null});
  });
  kb.querySelectorAll('.kcol').forEach(function(col){
    col.addEventListener('dragover',function(e){if(drag&&col.classList.contains('can')){e.preventDefault();col.classList.add('over')}});
    col.addEventListener('dragleave',function(){col.classList.remove('over')});
    col.addEventListener('drop',function(e){e.preventDefault();var o=drag;col.classList.remove('over');if(!o)return;
      var to=col.dataset.st,allowed=(NEXT[o.status]||[]).find(function(n){return n[0]===to});
      if(!allowed){if(to!==o.status)toast('Bu o‘tishga ruxsat yo‘q: '+o.statusLabel+' → '+(KB.find(function(k){return k[0]===to})||[])[1],true);return}
      moveOrder(o,to,page)});
  });
}
async function moveOrder(o,to,page,note){
  if(to==='rejected'&&note==null){var v=await formBox('Buyurtma #'+o.id+' ni rad etish',[{name:'note',label:'Sabab',area:true,required:true}],'Rad etish');if(!v)return;note=v.note}
  var r=await run(function(){return api('order_status',{orderId:o.id,to:to,note:note||'',status:'all'})});
  if(!r)return;S.cache.whAll=r.warehouse;S.cache.wh=null;renderBoard(page,r.warehouse);
  var back=(NEXT[to]||[]).find(function(n){return n[0]===o.status});
  toast('#'+o.id+': '+(KB.find(function(k){return k[0]===to})||[])[1]+(back?' — bekor qilish uchun kartani qaytaring':''));
}
function orderModal(o,page){
  var col=KB.find(function(k){return k[0]===o.status})||KB[0],stages=['new','preparing','loaded','delivered'],idx=stages.indexOf(o.status);
  modal('<div class="omodal '+col[2]+'"><div class="card-h" style="margin-bottom:6px"><small>Buyurtma #'+o.id+' · '+dt(o.ts)+'</small><button class="round-btn" data-m="cancel" aria-label="Yopish">'+ic('x','sm')+'</button></div>'+
    '<h3 style="font-size:24px">'+esc(o.clientName)+'</h3><small>'+esc(o.agentName)+'</small>'+
    '<div class="ostages">'+stages.map(function(st,i){return '<div class="'+(o.status==='rejected'?'':i<=idx?'done':'')+'"><i></i><small>'+(KB.find(function(k){return k[0]===st})||[])[1]+'</small></div>'}).join('')+'</div>'+
    (o.status==='rejected'?'<div class="pill" style="margin-bottom:10px">Rad etilgan</div>':'')+
    '<div class="oitems">'+o.items.map(function(i){return '<div><span>'+esc(i.name)+(i.custom?' <u>katalogda yo‘q</u>':'')+'</span><span class="num">'+i.qty+' × '+(i.priceCents?usd(i.priceCents/100):'—')+'</span></div>'}).join('')+'<div class="otot"><span>Jami</span><b>'+usd(orderSum(o))+'</b></div></div>'+
    (o.note?'<p class="small">'+ic('note','sm')+' '+esc(o.note)+'</p>':'')+(o.adminNote?'<p class="small">'+ic('edit','sm')+' '+esc(o.adminNote)+'</p>':'')+
    '<div class="actions" style="margin-top:14px">'+(NEXT[o.status]||[]).map(function(n){return '<button class="btn sm" data-to="'+n[0]+'">'+esc(n[1])+'</button>'}).join('')+(o.status==='preparing'?'<span class="small" style="opacity:.8">«Agentga berildi»ni omborchi Ombor ilovasida qo‘yadi</span>':'')+'</div></div>');
  $('modalBody').querySelectorAll('[data-to]').forEach(function(b){b.onclick=function(){var to=b.dataset.to;closeModal();moveOrder(o,to,page)}});
}
function renderWarehouse(page,w){
  var cnt=w.counts,lab=w.statusLabels,st=w.stock||{};
  var tabs=[['open','Ochiq',(cnt.new||0)+(cnt.preparing||0)+(cnt.loaded||0)]].concat(Object.keys(lab).map(function(k){return [k,lab[k],cnt[k]||0]}));
  var SC={new:'p-pri',preparing:'p-warn',loaded:'p-ok',delivered:'',rejected:'p-bad'};
  page.innerHTML=
   '<div class="grid g4" style="margin-bottom:16px">'+kpi('🆕','Yangi buyurtma',num(cnt.new||0),'Tayyorlanmoqda: '+(cnt.preparing||0))+kpi('🚚','Agentga berildi',num(cnt.loaded||0),'Yetkazilishi kutilmoqda')+kpi('🏬','Ombordagi tovar',num(st.stockTotal||0)+' dona','Bugun berildi: '+num(st.issuedToday||0))+kpi('❓','Katalogda yo‘q',num((w.demand||[]).length),'Agentlar so‘ragan nomlar','warn')+'</div>'+
   '<div class="toolbar">'+whViewSeg()+'<div class="seg" id="whSeg">'+tabs.map(function(t){return '<button data-s="'+t[0]+'" class="'+(w.filter===t[0]?'on':'')+'">'+esc(t[1])+'<b>'+t[2]+'</b></button>'}).join('')+'</div><span class="grow"></span><button class="btn pri" id="whAdd">'+ic('plus')+' Yangi mahsulot</button></div>'+
   '<div class="grid g-main"><div class="card flush"><div class="tbl-wrap"><table><thead><tr><th>#</th><th>Sana</th><th>Agent / mijoz</th><th>Tovarlar</th><th class="right">Summa</th><th>Holat</th><th></th></tr></thead><tbody>'+
    (w.orders.length?w.orders.map(function(o){return '<tr><td class="num">'+o.id+'</td><td class="num">'+dt(o.ts)+'</td><td><b>'+esc(o.agentName)+'</b><br><small class="muted">'+esc(o.clientName)+'</small></td><td>'+o.items.map(function(i){return esc(i.name)+' × '+i.qty+(i.custom?' <span class="pill p-warn">katalogda yo‘q</span>':'')}).join('<br>')+(o.note?'<br><small class="muted">'+ic('note','sm')+' '+esc(o.note)+'</small>':'')+(o.adminNote?'<br><small class="muted">'+ic('edit','sm')+' '+esc(o.adminNote)+'</small>':'')+'</td><td class="right num">'+usd(o.totalCents/100)+'</td><td>'+pill(esc(o.statusLabel),SC[o.status])+'</td><td class="actions">'+(NEXT[o.status]||[]).map(function(n){return '<button class="btn sm'+(n[0]==='rejected'?' danger':'')+'" data-o="'+o.id+'" data-to="'+n[0]+'">'+n[1]+'</button>'}).join('')+'</td></tr>'}).join(''):'<tr><td colspan="7" class="empty">Buyurtma yo‘q</td></tr>')+
   '</tbody></table></div></div>'+
   '<div class="grid" style="align-content:start">'+
    ((w.demand||[]).length?'<div class="card"><div class="card-h"><h3>Katalogda yo‘q tovarlar</h3></div><div class="list">'+w.demand.map(function(d,i){return '<div class="li"><div class="t"><b>'+esc(d.name)+'</b><small>'+d.qty+' dona · '+d.orders+' buyurtma · '+d.clients+' mijoz</small></div><button class="btn sm" data-dm="'+i+'">Bog‘lash</button></div>'}).join('')+'</div></div>':'')+
    '<div class="card"><div class="card-h"><h3>Ombor qoldig‘i</h3><span class="muted small">Shu oy berildi: '+num(st.issuedMonth||0)+'</span></div>'+((st.products||[]).length?'<div class="list">'+st.products.map(function(p){return '<div class="li"><div class="t"><b>'+esc(p.name)+'</b><small>Bugun '+p.issuedToday+' · oy '+p.issuedMonth+'</small></div><b class="num '+(p.stock<0?'bad':'')+'">'+num(p.stock)+'</b></div>'}).join('')+'</div>':'<div class="muted">Ma’lumot yo‘q</div>')+'</div>'+
   '</div></div>'+
   '<div class="card flush" style="margin-top:16px"><div class="card-h"><h3>Mahsulotlar katalogi</h3></div><div class="tbl-wrap" style="margin-top:12px"><table><thead><tr><th>Kod</th><th>Nomi</th><th class="right">Narx</th><th class="right">Og‘irlik</th><th class="right">Blokda</th><th>Holat</th><th></th></tr></thead><tbody>'+
    w.catalog.map(function(p){return '<tr><td class="num">'+p.pack+'</td><td><div class="cell">'+(p.thumbUrl||p.photoUrl?'<span class="av sq" style="background-image:url(\''+esc(p.thumbUrl||p.photoUrl)+'\')"></span>':'')+'<b>'+esc(p.name)+'</b></div></td><td class="right num">'+usd(p.priceUsd)+'</td><td class="right num">'+(p.weightKg?num(p.weightKg)+' kg':'—')+'</td><td class="right num">'+(p.blockUnits||'—')+'</td><td>'+(p.active?pill('Faol','p-ok'):pill('Yashirin'))+'</td><td><button class="btn sm" data-pe="'+p.pack+'">Tahrirlash</button></td></tr>'}).join('')+
   '</tbody></table></div></div>';
  $('whSeg').onclick=function(e){var b=e.target.closest('button');if(!b)return;WH.status=b.dataset.s;pageWarehouse(page,true)};bindWhView(page);
  page.querySelectorAll('[data-o]').forEach(function(b){b.onclick=async function(){
    var to=b.dataset.to,label=b.textContent,v=await formBox('Buyurtma #'+b.dataset.o+': '+label,[{name:'note',label:'Izoh (ixtiyoriy)',area:true}],label);if(!v)return;
    var r=await run(function(){return api('order_status',{orderId:+b.dataset.o,to:to,note:v.note,status:WH.status})},'Holat o‘zgartirildi');if(r){S.cache.wh=r.warehouse;renderWarehouse(page,r.warehouse)}}});
  page.querySelectorAll('[data-pe]').forEach(function(b){b.onclick=async function(){
    var p=w.catalog.find(function(x){return String(x.pack)===b.dataset.pe});
    var v=await formBox('Mahsulot #'+p.pack,[{name:'name',label:'Nomi',value:p.name,required:true},{name:'priceUsd',label:'Narx (USD)',value:p.priceUsd,type:'number',step:'0.01',required:true},{name:'weightKg',label:'Og‘irlik (kg)',value:p.weightKg||'',type:'number',step:'0.01'},{name:'active',label:'Holat',value:p.active?'1':'0',options:[['1','Faol (agentlarga ko‘rinadi)'],['0','Yashirin']]}]);if(!v)return;
    var args={pack:p.pack,status:WH.status,active:v.active==='1'};if(v.name!==p.name)args.name=v.name;if(Number(v.priceUsd)!==Number(p.priceUsd))args.priceUsd=v.priceUsd;if(v.weightKg&&Number(v.weightKg)!==Number(p.weightKg||0))args.weightKg=v.weightKg;
    var r=await run(function(){return api('product_update',args)},'Mahsulot saqlandi');if(r){S.cache.wh=r.warehouse;renderWarehouse(page,r.warehouse)}}});
  page.querySelectorAll('[data-dm]').forEach(function(b){b.onclick=async function(){
    var d=w.demand[+b.dataset.dm],opts=w.catalog.filter(function(p){return p.active}).map(function(p){return [p.pack,p.pack+' · '+p.name]});
    var v=await formBox('«'+d.name+'» ni bog‘lash',[{name:'pack',label:'Katalogdagi mahsulot',options:opts}],'Bog‘lash','Ochiq buyurtmalardagi shu nom tanlangan mahsulotga almashtiriladi.');if(!v)return;
    var r=await run(function(){return api('custom_map',{name:d.name,pack:+v.pack,status:WH.status})});if(r){toast(r.mapped+' ta qator bog‘landi');S.cache.wh=r.warehouse;renderWarehouse(page,r.warehouse)}}});
  $('whAdd').onclick=async function(){
    var v=await formBox('Yangi mahsulot',[{name:'name',label:'Nomi',required:true,placeholder:'Emal oq — 3 kg'},{name:'weightKg',label:'Og‘irlik (kg)',type:'number',step:'0.01',required:true},{name:'priceUsd',label:'Narx (USD)',type:'number',step:'0.01',required:true},{name:'blockUnits',label:'Blokda nechta (ixtiyoriy)',type:'number',step:'1'}],'Davom etish');if(!v)return;
    if(!await confirmBox('Mahsulotni qo‘shish','<p><b>'+esc(v.name)+'</b> · '+esc(v.weightKg)+' kg · '+usd(v.priceUsd)+(v.blockUnits?' · blokda '+esc(v.blockUnits):'')+'</p>','Qo‘shish'))return;
    var r=await run(function(){return api('product_add',{name:v.name,weightKg:v.weightKg,priceUsd:v.priceUsd,blockUnits:v.blockUnits||0,confirm:true,status:WH.status})},'Mahsulot qo‘shildi');if(r){S.cache.wh=r.warehouse;renderWarehouse(page,r.warehouse)}};
}

/* ----- Xodimlar ----- */
/* Xodimlar: barcha rollar bitta joyda. Amallar mavjud huquqlarga mos: qo'shish/nom — har bir rahbar;
   admin qo'shish, akkaunt almashtirish, yopish/ochish, web login — faqat asosiy rahbar (server ham tekshiradi). */
var ST={role:'',q:'',showOff:false,view:store('rw-stview')||'list'};
/* ----- Sex ishchilari: kartochka, davomat, oylik (server: hr.py). Tizim foydalanuvchilari bu yerda yo'q ----- */
var HR={month:'',day:'',tab:'card',data:null,closed:false,q:''};
var ATT_TONE={present:'p-ok',late:'p-warn',absent:'p-bad',off:'',sick:'p-warn',vacation:'p-pri'};
var ATT_SHORT={present:'K',late:'Kc',absent:'Y',off:'D',sick:'B',vacation:'T'};
function stViewSeg(){return '<div class="seg" id="stView" aria-label="Ko‘rinish">'+[['list','shield','Tizim foydalanuvchilari'],['workers','users','Sex ishchilari'],['att','calendar','Davomat'],['pay','wallet','Oylik']].filter(function(v){return v[0]==='list'||modOn('hr')}).map(function(v){return '<button data-v="'+v[0]+'" class="'+((ST.view||'list')===v[0]?'on':'')+'">'+ic(v[1],'sm')+' '+v[2]+'</button>'}).join('')+'</div>'}
function bindStView(page){var el=$('stView');if(el)el.onclick=function(e){var b=e.target.closest('button');if(!b)return;ST.view=b.dataset.v;store('rw-stview',ST.view);pageStaff(page,true)}}
function som(n){return num(n||0,0)+' so‘m'}
/* Ishchi valyutasida: so'm butun, dollar sentda saqlanadi */
function wm(n,cur){return cur==='USD'?usd((n||0)/100):som(n)}
function wmIn(n,cur){return cur==='USD'?((n||0)/100).toFixed(2):String(n||'')}
function curName(c){return c==='USD'?'dollar':'so‘m'}
function monthLabel(m){var p=String(m||'').split('-');var names=['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentabr','Oktabr','Noyabr','Dekabr'];return p.length===2?names[+p[1]-1]+' '+p[0]:m}
function shiftMonth(m,d){var p=m.split('-').map(Number),y=p[0],mo=p[1]+d;while(mo<1){mo+=12;y--}while(mo>12){mo-=12;y++}return y+'-'+String(mo).padStart(2,'0')}
function monthNav(id,m){return '<div class="seg month-nav" id="'+id+'"><button data-d="-1" aria-label="Oldingi oy">‹</button><button class="on" disabled>'+esc(monthLabel(m))+'</button><button data-d="1" aria-label="Keyingi oy">›</button></div>'}
function workerFields(c,month,isNew){c=c||{};return [{name:'name',label:'Ism familiya',required:true,value:c.name||''},{name:'department',label:'Bo‘lim',value:c.department,placeholder:'masalan: quyish sexi, qadoqlash'},{name:'position',label:'Lavozim / ish turi',value:c.position,placeholder:'masalan: quyuvchi, qadoqlovchi'},{name:'phone',label:'Telefon',value:c.phone,placeholder:'+998 90 123 45 67'},{name:'hire_date',label:'Ishga kirgan sana',type:'date',value:c.hire_date},{name:'currency',label:'Oylik valyutasi',options:[['UZS','So‘m'],['USD','Dollar ($)']],value:c.currency||'UZS'},{name:'salary',label:'Oylik (tanlangan valyutada)',type:'number',step:'any',value:c.salary?wmIn(c.salary,c.currency):''},{name:'salaryFrom',label:'Oylik qaysi oydan',type:'month',value:month},{name:'birth_date',label:'Tug‘ilgan sana',type:'date',value:c.birth_date},{name:'address',label:'Manzil',value:c.address},{name:'passport',label:'Hujjat (pasport seriya va raqami)',value:c.passport},{name:'emergency',label:'Favqulodda aloqa (ism, telefon)',value:c.emergency},{name:'note',label:'Izoh',area:true,value:c.note}]}
async function addWorker(after){var v=await formBox('Yangi sex ishchisi',workerFields({},HR.month||today().slice(0,7),true),'Qo‘shish','Telegram kerak emas — ishchi tizimdan foydalanmaydi, faqat davomat va oylik uchun.');
  if(!v)return;if(!v.salary)delete v.salary;var r=await run(function(){return api('hr',Object.assign({op:'worker_add',requestId:rid()},v))},'Ishchi qo‘shildi');if(r){HR.data=null;if(after)after(r)}}
async function hrLoad(){return api('hr',{op:'overview',month:HR.month||undefined,day:HR.day||undefined,closed:HR.closed})}
async function pageHr(page,force){
  if(!HR.data||force){page.innerHTML='<div class="toolbar">'+stViewSeg()+'</div><div class="grid g4">'+'<div class="skel"></div>'.repeat(4)+'</div>';
    try{HR.data=await hrLoad()}catch(e){if(S.page!=='staff')return;page.innerHTML='<div class="toolbar">'+stViewSeg()+'</div>'+errState(e.message);bindStView(page);page.querySelector('[data-retry]').onclick=function(){pageHr(page,true)};return}}
  if(S.page!=='staff')return;HR.month=HR.data.month;HR.day=HR.data.day;
  ({workers:renderWorkers,att:renderAtt,pay:renderPay})[ST.view](page,HR.data);
}
function noWorkers(){return '<div class="card">'+emptyState('Hali sex ishchisi qo‘shilmagan. «Ishchi qo‘shish» tugmasini bosing.','users')+'</div>'}
function renderWorkers(page,d){
  var q=HR.q.trim().toLowerCase(),rows=d.workers.filter(function(w){return !q||(w.name+' '+w.position+' '+w.phone).toLowerCase().indexOf(q)>=0});
  page.innerHTML='<div class="toolbar">'+stViewSeg()+'</div><div class="toolbar"><input type="search" id="wkQ" placeholder="Ism, lavozim, telefon…" value="'+esc(HR.q)+'"><span class="grow"></span><label class="chk"><input type="checkbox" id="wkOff"'+(HR.closed?' checked':'')+'> Ishdan ketganlar ('+d.totals.closed+')</label>'+(d.canEdit===false?'':'<button class="btn pri" id="wkAdd">'+ic('userplus','sm')+' Ishchi qo‘shish</button>')+'</div>'+
    (d.workers.length?'<div class="card flush"><div class="tbl-wrap"><table><thead><tr><th>Ishchi</th><th>Telefon</th><th>Ishga kirgan</th><th class="right">Oylik</th><th class="right">Bu oy ishladi</th><th class="right">Qolgan oylik</th><th>Holat</th></tr></thead><tbody>'+
    (rows.length?rows.map(function(w){return '<tr class="click" data-w="'+w.id+'"><td><div class="cell"><span class="av">'+initial(w.name)+'</span><div class="t"><b>'+esc(w.name)+'</b><small>'+esc([w.department,w.position].filter(Boolean).join(' · ')||'—')+'</small></div></div></td><td class="num">'+(w.phone?esc(w.phone):'<span class="muted">—</span>')+'</td><td class="num">'+(w.hireDate?esc(w.hireDate):'<span class="muted">—</span>')+'</td><td class="right num">'+(!w.payroll?'<span class="muted">—</span>':w.payroll.salary?wm(w.payroll.salary,w.currency):'<span class="muted">belgilanmagan</span>')+'</td><td class="right num">'+w.attendance.worked+' kun</td><td class="right num'+(w.payroll&&w.payroll.remaining>0?' bad':'')+'">'+(w.payroll?wm(w.payroll.remaining,w.currency):'—')+'</td><td>'+(w.active?pill('<span class="dot"></span>Ishlayapti','p-ok'):pill('<span class="dot"></span>Ketgan','p-bad'))+'</td></tr>'}).join('')
      :'<tr><td colspan="7">'+emptyState('Topilmadi','users')+'</td></tr>')+'</tbody></table></div></div>':noWorkers());
  bindStView(page);
  $('wkQ').oninput=debounce(function(){HR.q=this.value;renderWorkers(page,d);var i=$('wkQ');i.focus();i.setSelectionRange(i.value.length,i.value.length)},200);
  $('wkOff').onchange=function(){HR.closed=this.checked;pageHr(page,true)};
  if($('wkAdd'))$('wkAdd').onclick=function(){addWorker(function(r){pageHr(page,true);renderWorker(r.worker,r)})};
  page.querySelectorAll('[data-w]').forEach(function(tr){tr.onclick=function(){openWorker(+tr.dataset.w,'card')}});
}
function renderAtt(page,d){
  var T=d.totals,opts=d.statuses,list=d.workers.filter(function(w){return w.active});
  page.innerHTML='<div class="toolbar">'+stViewSeg()+'</div><div class="toolbar"><input type="date" id="attDay" value="'+esc(d.day)+'" max="'+today()+'" aria-label="Kun"><span class="grow"></span>'+(list.length?'<button class="btn" id="attAll">'+ic('checkc','sm')+' Belgilanmaganlarni «Keldi»</button><button class="btn pri" id="attSave" disabled>'+ic('check','sm')+' Saqlash</button>':'')+'</div>'+
    (list.length?'<div class="grid g4 kpis" style="margin-bottom:16px">'+kpi('users','Ishchilar',num(T.count),'')+kpi('checkc','Keldi',num(T.present),'kechikkanlar bilan')+kpi('xcircle','Kelmadi',num(T.absent),'',T.absent?'bad':'')+kpi('clock','Belgilanmagan',num(T.unmarked),'',T.unmarked?'bad':'')+'</div>'+
    '<div class="card flush"><div class="card-h"><h3>'+ic('calendar')+' Davomat · '+esc(d.day)+'</h3><span class="muted small">Ismni bossangiz — oylik kalendar</span></div><div class="tbl-wrap" style="margin-top:10px"><table><thead><tr><th>Ishchi</th><th>Holat</th><th>Izoh</th><th class="right">Oy bo‘yicha</th></tr></thead><tbody>'+
    list.map(function(e){var m=e.day||{};return '<tr data-id="'+e.id+'"><td><b class="click-name" data-emp="'+e.id+'">'+esc(e.name)+'</b>'+(e.position?'<br><small class="muted">'+esc(e.position)+'</small>':'')+'</td>'+
      '<td><select data-st aria-label="Holat"><option value="">— belgilanmagan —</option>'+opts.map(function(o){return '<option value="'+o[0]+'"'+(m.status===o[0]?' selected':'')+'>'+esc(o[1])+'</option>'}).join('')+'</select></td>'+
      '<td><input data-note maxlength="200" value="'+esc(m.note||'')+'" placeholder="Izoh" aria-label="Izoh"></td>'+
      '<td class="right small muted num">'+e.attendance.worked+' kun ishladi'+(e.attendance.absent?' · <span class="bad">'+e.attendance.absent+' kelmadi</span>':'')+'</td></tr>'}).join('')+'</tbody></table></div></div>':noWorkers());
  bindStView(page);
  $('attDay').onchange=async function(){HR.day=this.value;HR.data=null;pageHr(page,true)};
  if(!list.length)return;
  var dirty=function(){$('attSave').disabled=false};
  page.querySelectorAll('[data-st],[data-note]').forEach(function(el){el.onchange=dirty;el.oninput=dirty});
  $('attAll').onclick=function(){page.querySelectorAll('tbody tr').forEach(function(tr){var s=tr.querySelector('[data-st]');if(!s.value)s.value='present'});dirty()};
  $('attSave').onclick=async function(){var items=[];page.querySelectorAll('tbody tr').forEach(function(tr){var s=tr.querySelector('[data-st]').value,n=tr.querySelector('[data-note]').value,e=list.find(function(x){return String(x.id)===tr.dataset.id}),m=e.day||{};
      if(s!==(m.status||'')||(s&&n!==(m.note||'')))items.push({id:+tr.dataset.id,status:s||'clear',note:n})});
    if(!items.length){toast('O‘zgarish yo‘q');return}
    var r=await run(function(){return api('hr',{op:'attendance_bulk',day:d.day,month:d.day.slice(0,7),items:items})},'Davomat saqlandi');if(r){HR.data=r;renderAtt(page,r)}};
  page.querySelectorAll('[data-emp]').forEach(function(b){b.onclick=function(){openWorker(+b.dataset.emp,'att',d.day.slice(0,7))}});
}
function renderPay(page,d){
  if(d.salaryHidden){page.innerHTML='<div class="toolbar">'+stViewSeg()+'</div><div class="card">'+emptyState('Oylik summalarini ko‘rish uchun ruxsat kerak. Admin Sozlamalar → Xodimlar va ruxsatlar bo‘limida beradi.','shield')+'</div>';bindStView(page);return}
  var T=d.totals,list=d.workers.filter(function(w){return w.active});
  page.innerHTML='<div class="toolbar">'+stViewSeg()+'</div><div class="toolbar">'+monthNav('payMonth',d.month)+'<span class="grow"></span><span class="muted small">Qatorni bosing — avans, oylik to‘lovi, bonus yoki jarima</span></div>'+
    (list.length?['UZS','USD'].filter(function(c){return list.some(function(w){return w.currency===c})}).map(function(c){var Q=d.money[c],n=list.filter(function(w){return w.currency===c}).length,f=function(v){return c==='USD'?usd(v/100):num(v,0)},u=c==='USD'?'$':'so‘m';
      return '<div class="grid g4 kpis" style="margin-bottom:16px">'+kpi('wallet','Oylik fondi, '+u,f(Q.salary),n+' ishchi · '+curName(c)+'da')+kpi('cash','Hisoblandi, '+u,f(Q.due),'oylik + bonus − jarima')+kpi('coins','To‘landi, '+u,f(Q.paid),'avans + oylik')+kpi('hourglass','To‘lanishi qolgan, '+u,f(Q.remaining),Q.overpaid?'ortiqcha berilgan: '+f(Q.overpaid):'',Q.remaining>0?'bad':'')+'</div>'}).join('')+
    '<div class="card flush"><div class="card-h"><h3>'+ic('wallet')+' Oylik hisobi · '+esc(monthLabel(d.month))+'</h3><span class="muted small">Oylik miqdori ishchi kartochkasida</span></div><div class="tbl-wrap" style="margin-top:10px"><table><thead><tr><th>Ishchi</th><th class="right">Oldingi oy</th><th class="right">Oylik</th><th class="right">Bonus</th><th class="right">Jarima</th><th class="right">Avans</th><th class="right">Oylik to‘landi</th><th class="right">Qoldi</th><th class="right">Ish kuni</th></tr></thead><tbody>'+
    list.map(function(e){var p=e.payroll,f=function(v){return wm(v,e.currency)};return '<tr class="click" data-emp="'+e.id+'"><td><b>'+esc(e.name)+'</b><br><small class="muted">'+esc([e.department,e.position].filter(Boolean).join(' · ')||'—')+'</small></td><td class="right num'+(p.carry<0?' bad':'')+'">'+(p.carry?(p.carry<0?'−':'')+f(Math.abs(p.carry)):'—')+'</td><td class="right num">'+(p.salary?f(p.salary):'<span class="muted">belgilanmagan</span>')+'</td><td class="right num ok">'+(p.bonus?'+'+f(p.bonus):'—')+'</td><td class="right num bad">'+(p.penalty?'−'+f(p.penalty):'—')+'</td><td class="right num">'+(p.advance?f(p.advance):'—')+'</td><td class="right num">'+(p.paidSalary?f(p.paidSalary):'—')+'</td><td class="right num'+(p.remaining>0?' bad':'')+'"><b>'+(p.overpaid?'−'+f(p.overpaid)+'</b><br><small>ortiqcha</small>':f(p.remaining)+'</b>')+'</td><td class="right num muted">'+e.attendance.worked+'</td></tr>'}).join('')+'</tbody></table></div></div>':noWorkers());
  bindStView(page);
  $('payMonth').onclick=function(e){var b=e.target.closest('[data-d]');if(!b)return;HR.month=shiftMonth(d.month,+b.dataset.d);HR.data=null;pageHr(page,true)};
  page.querySelectorAll('[data-emp]').forEach(function(tr){tr.onclick=function(){openWorker(+tr.dataset.emp,'pay',d.month)}});
}
async function openWorker(id,tab,month){
  HR.tab=tab||HR.tab||'card';openDrawer(drawerSkel());
  var r=await run(function(){return api('hr',{op:'worker',id:id,month:month||HR.month||undefined})});if(!r){closeDrawer();return}
  renderWorker(r.worker,r);
}
function renderWorker(e,fl){
  /* Ruxsatlar serverdan: canPay (avans/oylik), canCalc (bonus/jarima), canEdit, salaryHidden */
  fl=fl||{};var canPay=!!fl.canPay,canCalc=!!fl.canCalc,canEdit=fl.canEdit!==false,hid=!!fl.salaryHidden;
  var c=e.card,P=e.payroll||{},tab=HR.tab,cu=e.currency,M=function(v){return wm(v,cu)};
  var tabs='<div class="seg" id="empTabs" style="margin:4px 0 14px">'+[['card','user','Kartochka'],['att','calendar','Davomat'],['pay','wallet','Oylik']].map(function(t){return '<button data-t="'+t[0]+'" class="'+(tab===t[0]?'on':'')+'">'+ic(t[1],'sm')+' '+t[2]+'</button>'}).join('')+'</div>';
  var body='';
  if(tab==='card'){
    var row=function(k,v){return '<dt>'+k+'</dt><dd>'+(v?esc(v):'<span class="muted">—</span>')+'</dd>'};
    body='<div class="card"><dl class="kv">'+row('Bo‘lim',c.department)+row('Lavozim',c.position)+row('Telefon',c.phone)+row('Ishga kirgan',c.hire_date)+'<dt>Oylik</dt><dd>'+(hid?'<span class="muted">ruxsat yo‘q</span>':e.salary?M(e.salary):'<span class="muted">belgilanmagan</span>')+'</dd>'+row('Tug‘ilgan sana',c.birth_date)+row('Manzil',c.address)+row('Hujjat (pasport)',c.passport)+row('Favqulodda aloqa',c.emergency)+row('Izoh',c.note)+'</dl>'+
      ((e.salaryHistory||[]).length>1?'<p class="small muted" style="margin-top:10px">Oylik tarixi: '+e.salaryHistory.map(function(h){return esc(monthLabel(h.from))+' dan '+M(h.amount)}).join(' · ')+'</p>':'')+
      (canEdit?'<div class="actions" style="margin-top:14px">'+(e.active?'<button class="btn pri" id="empEdit">'+ic('edit','sm')+' Tahrirlash</button><button class="btn danger" id="empClose">'+ic('ban','sm')+' Ishdan ketdi</button>':'<button class="btn pri" id="empOpen">'+ic('checkc','sm')+' Qayta ishga olish</button>')+'</div>':'')+'</div>';
  }else if(tab==='att'){
    var A=e.attendance,pad=e.calendar[0].dow;
    body=monthNav('empMonth',e.month)+'<div class="grid g4 kpis" style="margin:12px 0">'+kpi('checkc','Ishladi',A.worked+' kun',A.late?A.late+' kechikdi':'')+kpi('xcircle','Kelmadi',A.absent+' kun','',A.absent?'bad':'')+kpi('calendar','Dam / ta’til',(A.off+A.vacation)+' kun','')+kpi('alert','Kasal',A.sick+' kun','')+'</div>'+
      '<div class="att-cal">'+['Du','Se','Ch','Pa','Ju','Sh','Ya'].map(function(x){return '<b>'+x+'</b>'}).join('')+'<i></i>'.repeat(pad)+
      e.calendar.map(function(x){return '<button class="att-d '+(x.status?ATT_TONE[x.status]||'':'')+'" data-day="'+x.day+'"'+(x.future||!e.active||!canEdit?' disabled':'')+' title="'+esc(x.day+(x.status?' · '+(e.statuses.find(function(s){return s[0]===x.status})||['',''])[1]:'')+(x.note?' · '+x.note:''))+'"><span>'+(+x.day.slice(8))+'</span><small>'+(x.status?ATT_SHORT[x.status]:'')+'</small></button>'}).join('')+'</div>'+
      '<p class="small muted" style="margin-top:8px">K — keldi, Kc — kechikdi, Y — kelmadi, D — dam olish, B — kasal, T — ta’til. Kunni bosib o‘zgartiring.</p>';
  }else if(hid){
    body='<div class="card">'+emptyState('Oylik summalarini ko‘rish uchun ruxsat kerak. Admin Sozlamalar → Xodimlar va ruxsatlar bo‘limida beradi.','shield')+'</div>';
  }else{
    body=monthNav('empMonth',e.month)+'<div class="card" style="margin:12px 0"><dl class="kv">'+(P.carry?'<dt>Oldingi oylardan</dt><dd class="num'+(P.carry<0?' bad">−'+M(-P.carry)+' <small>(ortiqcha berilgan)</small>':'">'+M(P.carry))+'</dd>':'')+'<dt>Oylik</dt><dd class="num">'+M(P.salary)+'</dd><dt>Bonus</dt><dd class="num'+(P.bonus?' ok">+'+M(P.bonus):'">—')+'</dd><dt>Jarima</dt><dd class="num'+(P.penalty?' bad">−'+M(P.penalty):'">—')+'</dd><dt><b>Hisoblandi</b></dt><dd class="num"><b>'+M(P.due)+'</b></dd><dt>Avans</dt><dd class="num">'+M(P.advance)+'</dd><dt>Oylik to‘landi</dt><dd class="num">'+M(P.paidSalary)+'</dd>'+(P.overpaid?'<dt><b>Ortiqcha berilgan</b></dt><dd class="num bad"><b>'+M(P.overpaid)+'</b> <small>keyingi oydan ushlanadi</small></dd>':'<dt><b>To‘lanishi qolgan</b></dt><dd class="num'+(P.remaining>0?' bad':'')+'"><b>'+M(P.remaining)+'</b></dd>')+'</dl>'+
      ((canPay||canCalc)&&e.active?'<div class="actions" style="margin-top:14px">'+(canPay?'<button class="btn pri" data-pk="salary"'+(P.remaining>0?'':' disabled')+'>'+ic('coins','sm')+' Oylik to‘lash</button><button class="btn" data-pk="advance">'+ic('cash','sm')+' Avans</button>':'')+(canCalc?'<button class="btn" data-pk="bonus">'+ic('plus','sm')+' Bonus</button><button class="btn danger" data-pk="penalty">'+ic('ban','sm')+' Jarima</button>':'')+'</div>':'')+(canPay&&!e.active&&P.remaining>0?'<div class="actions" style="margin-top:14px"><button class="btn pri" data-pk="salary">'+ic('coins','sm')+' Yakuniy hisob: qolgan oylikni to‘lash</button></div><p class="small muted" style="margin-top:8px">Ishdan ketgan: yangi oylik hisoblanmaydi, avans berilmaydi. Qayta ishga olish shart emas.</p>':'')+(!canPay&&e.active?'<p class="small muted" style="margin-top:10px">Avans va oylik to‘lash uchun «Avans va oylik to‘lash» ruxsati kerak.</p>':'')+'</div>'+
      '<div class="card flush"><div class="card-h"><h3>'+ic('list')+' Yozuvlar</h3></div><div class="list" style="padding:0 20px 10px">'+(e.payments.length?e.payments.map(function(x){var neg=x.kind==='penalty';return '<div class="li"><div class="t"><b>'+esc(x.label)+' · <span class="num '+(neg?'bad':x.kind==='bonus'?'ok':'')+'">'+(neg?'−':'')+M(x.amount)+'</span></b><small>'+[x.cash?'Kassadan'+(x.paidCurrency&&x.paidCurrency!==cu?' '+wm(x.paidAmount,x.paidCurrency)+(x.rate?' (kurs '+num(x.rate,0)+')':''):''):'',esc(x.note),esc(x.actorName)].filter(Boolean).join(' · ')+'</small></div><small class="muted num">'+dt(x.ts)+'</small></div>'}).join(''):emptyState('Bu oy yozuv yo‘q','list'))+'</div></div>';
  }
  openDrawer('<div class="dh"><span class="av lg">'+initial(e.name)+'</span><div><h2>'+esc(e.name)+'</h2><small class="muted">Sex ishchisi'+(c.position?' · '+esc(c.position):'')+(c.phone?' · <a href="tel:'+esc(c.phone)+'">'+esc(c.phone)+'</a>':'')+(e.active?'':' · <span class="bad">ishdan ketgan</span>')+'</small></div></div>'+tabs+body);
  var reload=async function(m){var r=await run(function(){return api('hr',{op:'worker',id:e.id,month:m||e.month})});if(r)renderWorker(r.worker,r)};
  var after=function(r){if(r){HR.data=null;renderWorker(r.worker,r);if(S.page==='staff'&&ST.view!=='list')pageHr($('page'),true)}};
  $('empTabs').onclick=function(ev){var b=ev.target.closest('button');if(!b)return;HR.tab=b.dataset.t;renderWorker(e,fl)};
  if($('empMonth'))$('empMonth').onclick=function(ev){var b=ev.target.closest('[data-d]');if(b)reload(shiftMonth(e.month,+b.dataset.d))};
  if($('empEdit'))$('empEdit').onclick=async function(){
    var v=await formBox('Kartochka: '+e.name,workerFields(Object.assign({name:e.name,salary:e.salary,currency:cu},c),e.month).filter(function(f){return f.name!=='currency'||e.canChangeCurrency}),'Saqlash','Oylik o‘zgarsa, tanlangan oydan boshlab amal qiladi — o‘tgan oylar hisobi o‘zgarmaydi.'+(e.canChangeCurrency?'':' '+(e.currencyLock||'Valyutani o‘zgartirib bo‘lmaydi.')));
    if(!v)return;if(!v.salary)delete v.salary;after(await run(function(){return api('hr',Object.assign({op:'worker_save',id:e.id,month:e.month,requestId:rid()},v))},'Saqlandi'))};
  if($('empClose'))$('empClose').onclick=async function(){if(await confirmBox('Ishdan ketdi','<p><b>'+esc(e.name)+'</b> ro‘yxatdan olinadi. Davomat va oylik tarixi saqlanadi, keyin qayta ishga olish mumkin.</p>','Tasdiqlash',true))after(await run(function(){return api('hr',{op:'worker_close',id:e.id,month:e.month})},'Saqlandi'))};
  if($('empOpen'))$('empOpen').onclick=async function(){after(await run(function(){return api('hr',{op:'worker_open',id:e.id,month:e.month})},'Qayta ishga olindi'))};
  document.querySelectorAll('#drawerBody .att-d').forEach(function(b){b.onclick=async function(){var x=e.calendar.find(function(y){return y.day===b.dataset.day});
    var v=await formBox('Davomat · '+x.day,[{name:'status',label:'Holat',options:[['clear','— belgilanmagan —']].concat(e.statuses),value:x.status||'clear'},{name:'note',label:'Izoh',value:x.note}],'Saqlash');
    if(v)after(await run(function(){return api('hr',{op:'attendance_set',id:e.id,day:x.day,status:v.status,note:v.note,month:e.month})},'Saqlandi'))}});
  document.querySelectorAll('#drawerBody [data-pk]').forEach(function(b){b.onclick=async function(){var k=b.dataset.pk,cash=k==='advance'||k==='salary',label=(e.payKinds.find(function(x){return x[0]===k})||['',''])[1];
    if(cash&&!e.cashRate){toast('Avval kassada 1 USD kursini belgilang.',true);return}
    var f=[];
    if(cash)f.push({name:'payCurrency',label:'Qaysi valyutada beriladi',options:[[cu,cu==='USD'?'Dollar ($)':'So‘m'],[cu==='USD'?'UZS':'USD',cu==='USD'?'So‘m (kurs bo‘yicha $ ga o‘giriladi)':'Dollar (kurs bo‘yicha so‘mga o‘giriladi)']],value:cu});
    f.push({name:'amount',label:'Summa',type:'number',step:'any',required:true,value:k==='salary'&&P.remaining>0?wmIn(P.remaining,cu):''});
    if(cash)f.push({name:'payFrom',label:'Qayerdan',options:[['cash','Kassa — naqd'],['card','Kassa — karta']]});
    f.push({name:'note',label:k==='penalty'?'Sabab':'Izoh',required:k==='penalty'});
    var v=await formBox(label+' · '+e.name+' · '+monthLabel(e.month),f,label,(cash?'Kassadan «Иш ҳақи» xarajati bo‘lib chiqadi (kurs: 1 USD = '+num(e.cashRate,0)+' so‘m). ':'Kassaga ta’sir qilmaydi — faqat hisoblangan oylikni o‘zgartiradi. ')+'Oylik '+curName(cu)+'da, qoldi: '+M(P.remaining)+'.');
    if(!v)return;after(await run(function(){return api('hr',Object.assign({op:'pay_add',id:e.id,kind:k,month:e.month,expectedRate:e.cashRate,requestId:rid()},v))},'Saqlandi'))}});
}
var ROLE_ICON={admin:['shield','blue'],sales:['trend','cyan'],cashier:['coins','green'],agent:['compass','violet'],warehouse:['warehouse','amber']};
var ROLE_NOTE={admin:'Web panel (login/parol) va Telegram bot',sales:'Savdo Mini App (Telegram): sotuv, chegirma, qarz, kassa',cashier:'Kassir Mini App (Telegram)',agent:'Agent Mini App (Telegram, GPS)',warehouse:'Ombor Mini App (Telegram)'};
async function pageStaff(page,force){
  if((ST.view==='workers'||ST.view==='att'||ST.view==='pay')&&!modOn('hr'))ST.view='list';
  if(ST.view==='workers'||ST.view==='att'||ST.view==='pay')return pageHr(page,force);
  if(!S.cache.staff||force){if(!S.cache.staff)page.innerHTML='<div class="grid g3">'+'<div class="skel"></div>'.repeat(6)+'</div>';
    try{S.cache.staff=await api('staff_list')}catch(e){if(S.page!=='staff'||!TOKEN)return;page.innerHTML=errState(e.message);page.querySelector('[data-retry]').onclick=function(){pageStaff(page,true)};return}}
  if(S.page!=='staff')return;renderStaff(page,S.cache.staff);
}
function renderStaff(page,s){
  var all=s.staff||[],roles=s.roles||[],P=S.primary,cnt={'':0};
  all.forEach(function(x){if(x.active){cnt[x.role]=(cnt[x.role]||0)+1;cnt['']++}});
  var q=ST.q.trim().toLowerCase();
  var rows=all.filter(function(x){return (!ST.role||x.role===ST.role)&&(ST.showOff||x.active)&&(!q||(x.name+' '+x.id+' '+x.webLogin).toLowerCase().indexOf(q)>=0)});
  var off=all.filter(function(x){return !x.active&&(!ST.role||x.role===ST.role)}).length;
  var act=function(k,id,icon,label,cls){return '<button class="icon-btn'+(cls?' '+cls:'')+'" data-act="'+k+'" data-id="'+id+'" aria-label="'+esc(label)+'" data-tip="'+esc(label)+'">'+ic(icon)+'</button>'};
  page.innerHTML=
   '<div class="grid g6 kpis-roles" style="margin-bottom:16px">'+roles.map(function(r){var t=ROLE_ICON[r.key]||['users','blue'];return '<button class="card kpi click st-role'+(ST.role===r.key?' on':'')+'" data-role="'+r.key+'">'+tone(t[0],t[1])+'<div><small>'+esc(r.label)+'</small><b>'+(cnt[r.key]||0)+'</b></div></button>'}).join('')+'</div>'+
   '<div class="toolbar">'+stViewSeg()+'</div><div class="toolbar"><div class="seg" id="stRole">'+[['','Hammasi']].concat(roles.map(function(r){return [r.key,r.label]})).map(function(x){return '<button data-r="'+x[0]+'" class="'+(ST.role===x[0]?'on':'')+'">'+esc(x[1])+'<b>'+(cnt[x[0]]||0)+'</b></button>'}).join('')+'</div>'+
    '<input type="search" id="stQ" placeholder="Ism, Telegram ID, login…" value="'+esc(ST.q)+'"><span class="grow"></span>'+
    '<label class="chk"><input type="checkbox" id="stOff"'+(ST.showOff?' checked':'')+'> Yopilganlar ('+off+')</label>'+
    '<button class="btn pri" id="stAdd">'+ic('userplus','sm')+' Xodim qo‘shish</button></div>'+
   '<div class="card flush"><div class="tbl-wrap"><table><thead><tr><th>Xodim</th><th>Rol</th><th>Telegram ID</th><th>Web login</th><th>Holat</th><th class="right">Amallar</th></tr></thead><tbody>'+
   (rows.length?rows.map(function(x){var t=ROLE_ICON[x.role]||['users','blue'],ag=x.role==='agent';
     var acts=x.active?
       act('rename',x.id,'edit','Nomini o‘zgartirish')+
       (P&&x.role==='admin'&&!x.primary?act('login',x.id,'shield',x.webLogin?'Yangi parol berish':'Login va parol berish'):'')+
       (P&&x.webLogin&&!x.primary?act('logout',x.id,'logout','Web kirishni o‘chirish'):'')+
       (P&&x.role!=='admin'?act('transfer',x.id,'swap','Akkauntni almashtirish'):'')+
       (P&&!x.primary?act('off',x.id,'ban','Akkauntni yopish','danger'):'')
      :(P?act('on',x.id,'checkc','Qayta ochish'):'');
     return '<tr'+(ag?' class="click" data-agent="'+x.id+'"':'')+'><td><div class="cell"><div class="tone t-'+t[1]+'" style="width:34px;height:34px">'+ic(t[0])+'</div><div class="t"><b>'+esc(x.name)+'</b><small>'+esc(ROLE_NOTE[x.role]||'')+'</small></div></div></td>'+
      '<td>'+pill(esc(x.roleLabel)+(x.primary?' · asosiy':''),x.role==='admin'?'p-pri':'')+'</td><td class="num">'+x.id+'</td>'+
      '<td>'+(x.webLogin?'<code>'+esc(x.webLogin)+'</code>':'<span class="muted">—</span>')+'</td>'+
      '<td>'+(x.active?pill('<span class="dot"></span>Faol','p-ok'):pill('<span class="dot"></span>Yopilgan','p-bad'))+'</td>'+
      '<td class="right"><div class="actions" style="justify-content:flex-end;flex-wrap:nowrap">'+acts+'</div></td></tr>'}).join('')
    :'<tr><td colspan="6">'+emptyState('Xodim topilmadi','users')+'</td></tr>')+
   '</tbody></table></div><div class="pager"><span>Agent qatorini bossangiz — to‘liq karta (KPI, huquqlar, qoldiq). '+(P?'':'Akkaunt almashtirish, yopish va login/parol — asosiy rahbar huquqi.')+'</span></div></div>'+
   (!ST.role||ST.role==='sales'?'<div id="stSales" style="margin-top:16px"></div>':'');
  if($('stSales'))(SH.d?Promise.resolve(SH.d):shLoad()).then(function(){if($('stSales'))shTeam($('stSales'))}).catch(function(e){if($('stSales'))$('stSales').innerHTML=errState(e.message)});
  var re=function(){renderStaff(page,S.cache.staff)};
  page.querySelectorAll('.st-role').forEach(function(b){b.onclick=function(){ST.role=ST.role===b.dataset.role?'':b.dataset.role;re()}});
  $('stRole').onclick=function(e){var b=e.target.closest('button');if(!b)return;ST.role=b.dataset.r;re()};
  $('stQ').oninput=debounce(function(){ST.q=this.value;re();var i=$('stQ');i.focus();i.setSelectionRange(i.value.length,i.value.length)},200);
  $('stOff').onchange=function(){ST.showOff=this.checked;re()};
  bindStView(page);
  bindAgentLinks(page);
  var call=async function(action,args,ok){var r=await run(function(){return api(action,Object.assign({confirm:true},args))},ok);
    if(r&&r.staff){S.cache.staff=r.staff;S.dash=null;SH.d=null;re()}return r};
  var find=function(id){return all.find(function(x){return String(x.id)===String(id)})};
  $('stAdd').onclick=async function(){
    var opts=roles.filter(function(r){return r.key!=='admin'||P}).map(function(r){return [r.key,r.label]});
    var v=await formBox('Yangi xodim',[{name:'role',label:'Bo‘lim / rol',options:opts,value:ST.role&&opts.some(function(o){return o[0]===ST.role})?ST.role:'agent'},{name:'name',label:'Ismi',required:true},{name:'id',label:'Telegram ID',required:true,placeholder:'123456789'}],'Qo‘shish','Xodim botga /start yozib Telegram ID sini bilib oladi va sizga yuboradi.');
    if(!v)return;await call('staff_add',{role:v.role,id:v.id,name:v.name},'Xodim qo‘shildi')};
  page.querySelectorAll('[data-act]').forEach(function(b){b.onclick=async function(e){e.stopPropagation();var x=find(b.dataset.id);if(!x)return;var k=b.dataset.act;
    if(k==='rename'){var v=await formBox('Nomini o‘zgartirish',[{name:'name',label:'Yangi ism',value:x.name,required:true}]);if(v)await call('staff_rename',{id:x.id,name:v.name},'Saqlandi')}
    else if(k==='transfer'){var v2=await formBox('Akkauntni almashtirish',[{name:'newId',label:'Yangi Telegram ID',required:true}],'Almashtirish',esc(x.name)+' ('+esc(x.roleLabel)+') yangi Telegram akkauntga o‘tadi. Eski akkaunt yopiladi; mijozlar, qoldiq va tarix saqlanadi.');if(v2)await call('staff_transfer',{id:x.id,newId:v2.newId},'Akkaunt almashtirildi')}
    else if(k==='off'){if(await confirmBox('Akkauntni yopish','<p><b>'+esc(x.name)+'</b> ('+esc(x.roleLabel)+') tizimga kira olmaydi. Tarix va hisoblar o‘chirilmaydi, keyin qayta ochish mumkin.</p>','Yopish',true))await call('staff_deactivate',{id:x.id},'Akkaunt yopildi')}
    else if(k==='on'){if(await confirmBox('Qayta ochish','<p><b>'+esc(x.name)+'</b> yana ishlay oladi.</p>','Ochish'))await call('staff_activate',{id:x.id},'Akkaunt ochildi')}
    else if(k==='logout'){if(await confirmBox('Web kirishni o‘chirish','<p><b>'+esc(x.name)+'</b> uchun login o‘chiriladi va barcha brauzerlardan chiqariladi.</p>','O‘chirish',true))await call('staff_login_revoke',{id:x.id},'Web kirish o‘chirildi')}
    else if(k==='login'){var v3=await formBox(x.webLogin?'Yangi parol berish':'Login va parol berish',[{name:'login',label:'Login (bo‘sh qoldirsangiz — avtomatik)',value:x.webLogin||'',placeholder:'masalan: aziz.admin'}],'Parol yaratish','Eski parol va barcha kirishlar bekor qilinadi. Yangi parol faqat bir marta ko‘rsatiladi.');
      if(!v3)return;var r=await call('staff_login_issue',{id:x.id,login:v3.login},'Parol yaratildi');
      if(r&&r.password)modal('<h3>Kirish ma’lumotlari</h3><p class="muted">'+esc(x.name)+' uchun. Faqat hozir ko‘rinadi — xavfsiz yo‘l bilan yuboring.</p><dl class="kv" style="margin:14px 0"><dt>Sayt</dt><dd><code>'+esc(r.url)+'</code></dd><dt>Login</dt><dd><code>'+esc(r.login)+'</code></dd><dt>Parol</dt><dd><code id="pwShow">'+esc(r.password)+'</code></dd></dl><div class="foot"><button class="btn" id="pwCopy">'+ic('file','sm')+' Nusxalash</button><button class="btn pri" data-m="cancel">Tayyor</button></div>').then(function(){});
      if($('pwCopy'))$('pwCopy').onclick=function(){try{navigator.clipboard.writeText('Sayt: '+r.url+'\nLogin: '+r.login+'\nParol: '+r.password);toast('Nusxalandi')}catch(err){toast('Nusxalab bo‘lmadi',true)}}}
  }});
}

/* ----- Sozlamalar ----- */
var BR_FIELDS=[['legalName','Yuridik nomi',160,1],['inn','STIR (INN)',20],['phone','Telefon',80],['address','Manzil',240,1],['bank','Bank rekvizitlari (h/r, bank, MFO)',240,1],['director','Rahbar F.I.Sh.',120]];
var PERM_ROLES=['admin','cashier','warehouse','sales','agent'];
async function permCard(can){
  var el=$('permCard');if(!el)return;
  var st;try{st=(await api('staff_list')).staff}catch(e){el.innerHTML='<p class="bad">'+esc(e.message)+'</p>';return}
  if(!$('permCard'))return;
  var list=(Array.isArray(st)?st:st.staff||[]).filter(function(x){return x.active&&PERM_ROLES.indexOf(x.role)>=0});
  var label=function(x){return x.primary?'Admin':x.role==='admin'?'Rahbar':x.role==='sales'?'Sotuvchi':x.role==='warehouse'?'Omborchi':x.roleLabel};
  el.innerHTML='<div class="card-h"><h3>'+ic('shield')+' Xodimlar va ruxsatlar</h3>'+(can?'':'<span class="pill">'+ic('shield','sm')+' Faqat ko‘rish</span>')+'</div>'+
    '<p class="hint" style="margin:-4px 0 10px">Har bir rolning standart huquqlari bor; Admin ularni xodim bo‘yicha alohida yoqadi yoki o‘chiradi. O‘zgarish darhol, ochiq sessiyalarda ham kuchga kiradi. Amal uchun bo‘lim yoqilgan va ruxsat bo‘lishi kerak. Filial modeli yo‘q — kassa va ombor butun korxona doirasida.</p>'+
    '<div class="tbl-wrap"><table><thead><tr><th>Xodim</th><th>Rol</th><th class="right"></th></tr></thead><tbody>'+
    list.map(function(x){return '<tr class="click" data-pid="'+x.id+'"><td><b>'+esc(x.name)+'</b><br><small class="muted num">'+x.id+'</small></td><td>'+pill(esc(label(x)),x.primary?'p-pri':'')+'</td><td class="right"><span class="muted small">'+(x.primary?'barcha huquq':x.role==='sales'?'Savdo jamoasida':x.role==='agent'?'agent kartasida':'Ruxsatlar')+'</span> '+ic('chevron','sm')+'</td></tr>'}).join('')+'</tbody></table></div>';
  el.querySelectorAll('[data-pid]').forEach(function(tr){tr.onclick=function(){var x=list.find(function(y){return String(y.id)===tr.dataset.pid});
    if(x.role==='sales'){location.hash='staff';ST.view='list';ST.role='sales';return}
    if(x.role==='agent'){openAgent(x.id);return}
    permModal(x.id,can)}});
}
async function permModal(id,can){
  var r=await run(function(){return api('perms_staff',{id:id})});if(!r)return;var s=r.staff,ch={};
  var groups={};s.perms.forEach(function(p){(groups[p.sectionLabel]=groups[p.sectionLabel]||[]).push(p)});
  var edit=can&&s.editable;
  var p=modal('<form class="perm-form"><h3>'+esc(s.roleLabel)+' · ruxsatlar</h3><p class="muted">'+(s.role==='primary'?'Admin (asosiy rahbar) barcha huquqqa ega — o‘zgartirib bo‘lmaydi.':edit?'Belgi — rol standarti. O‘zgartirilganlari «individual» deb ko‘rsatiladi.':'Faqat ko‘rish.')+'</p>'+
    Object.keys(groups).map(function(g){return '<div class="perm-grp"><b>'+esc(g)+'</b>'+groups[g].map(function(x){return '<label class="switch"><span>'+esc(x.label)+(x.override!=null?' <small class="pill p-warn">individual</small>':'')+(x['default']?' <small class="muted">· standart</small>':'')+'</span><input type="checkbox" data-perm="'+x.key+'"'+(x.on?' checked':'')+(edit?'':' disabled')+'></label>'}).join('')+'</div>'}).join('')+
    (s.history.length?'<details class="mod-hist"><summary class="small muted">O‘zgarishlar tarixi</summary><div class="list">'+s.history.map(function(h){return '<div class="li"><div class="t"><b>'+esc(h.label)+' — '+(h.on?'berildi':'olindi')+'</b><small>'+esc(h.who)+'</small></div><small class="muted num">'+dt(h.ts)+'</small></div>'}).join('')+'</div></details>':'')+
    '<div class="foot"><button type="button" class="btn" data-m="cancel">Yopish</button>'+(edit?'<button type="button" class="btn" id="permReset">Standartga qaytarish</button><button class="btn pri">Saqlash</button>':'')+'</div></form>');
  var box=$('modalBody');
  box.querySelectorAll('[data-perm]').forEach(function(c){c.onchange=function(){ch[c.dataset.perm]=c.checked}});
  if($('permReset'))$('permReset').onclick=function(){s.perms.forEach(function(x){if(x.override!=null)ch[x.key]=null});closeModal({})};
  var v=await p;if(!v||!Object.keys(ch).length)return;
  var x=await run(function(){return api('perms_set',{id:id,changes:ch})},'Ruxsatlar saqlandi');if(x)permModal(id,can);
}
async function modulesCard(can){
  var el=$('modCard');if(!el)return;
  var r;try{r=await api('modules')}catch(e){el.querySelector('.loading').outerHTML='<p class="bad">'+esc(e.message)+'</p>';return}
  if(!$('modCard'))return;
  el.innerHTML='<div class="card-h"><h3>'+ic('grid')+' Korxona bo‘limlari</h3>'+(can?'':'<span class="pill">'+ic('shield','sm')+' Faqat ko‘rish — asosiy rahbar o‘zgartiradi</span>')+'</div>'+
    '<p class="hint" style="margin:-4px 0 10px">O‘chirilgan bo‘lim menyuda chiqmaydi, uning ilovasi va server amallari yopiladi. Ma’lumot va tarix o‘chmaydi — qayta yoqsangiz hammasi joyida. Sozlamalar, Asosiy sahifa, Mijozlar va Xodimlar doim ochiq.</p>'+
    '<div class="mod-grid">'+r.items.map(function(m){return '<div class="switch"><span><b>'+esc(m.label)+'</b><br><small class="muted">'+esc(m.description)+'</small></span><button class="tog'+(m.enabled?' on':'')+'" data-mod="'+m.key+'" aria-pressed="'+m.enabled+'" aria-label="'+esc(m.label)+'"'+(can?'':' disabled')+'></button></div>'}).join('')+'</div>'+
    (r.history.length?'<details class="mod-hist"><summary class="small muted">O‘zgarishlar tarixi</summary><div class="list">'+r.history.map(function(h){return '<div class="li"><div class="t"><b>'+esc(h.label)+' — '+(h.on?'yoqildi':'o‘chirildi')+'</b><small>'+esc(h.who)+'</small></div><small class="muted num">'+dt(h.ts)+'</small></div>'}).join('')+'</div></details>':'');
  el.querySelectorAll('[data-mod]').forEach(function(b){b.onclick=async function(){var on=!b.classList.contains('on'),m=r.items.find(function(x){return x.key===b.dataset.mod});
    if(!on&&!await confirmBox('«'+m.label+'» bo‘limini o‘chirish','<p>Menyu, ilova va server amallari yopiladi. Ma’lumotlar o‘chirilmaydi, qayta yoqsangiz hammasi joyida bo‘ladi.</p>'+(m.key==='cash'?'<p class="bad">Kassa o‘chsa, oylik/avans va ta’minotchiga to‘lov ham yopiladi.</p>':'')+(m.key==='agents'?'<p class="bad">Agentlar Telegram bot va ilovadan foydalana olmay qoladi.</p>':''),'O‘chirish',true))return;
    b.disabled=true;var x=await run(function(){return api('module_set',{module:m.key,enabled:on})},on?'Bo‘lim yoqildi':'Bo‘lim o‘chirildi');b.disabled=false;
    if(x){S.dash=null;S.cache={};modulesCard(can)}}});
}
function pageSettings(page){
  var me=S.me||{};
  var canBrand=S.primary;
  page.innerHTML='<div class="grid g2" style="max-width:1080px">'+
   '<form class="card" id="brForm"><div class="card-h"><h3>'+ic('building')+' Kompaniya</h3>'+(canBrand?'':'<span class="pill">'+ic('shield','sm')+' Faqat ko‘rish</span>')+'</div>'+
    '<div class="brand-edit"><span class="brand-mark xl'+(BRAND.logo?' has-logo':'')+'" id="brPrev">'+brandMark()+'</span><div class="form" style="display:grid;gap:10px;flex:1;min-width:0">'+
    '<label>Brend nomi (panelda)<input name="name" maxlength="60" value="'+esc(BRAND.name)+'" placeholder="Masalan: kompaniyangiz nomi"'+(canBrand?'':' disabled')+'></label>'+
    (canBrand?'<div class="actions"><label class="btn sm file-btn">'+ic('upload','sm')+' Logotip yuklash<input type="file" id="brFile" accept="image/png,image/jpeg,image/webp" hidden></label><button type="button" class="btn sm" id="brClear"'+(BRAND.logo?'':' disabled')+'>'+ic('trash','sm')+' Logotipni olib tashlash</button></div>':'')+
    '</div></div>'+
    '<div class="card-h" style="margin:18px 0 8px"><h3>'+ic('file')+' Hujjat rekvizitlari</h3><small class="muted">akt sverka (PDF, Excel)</small></div>'+
    '<div class="form br-grid">'+BR_FIELDS.map(function(f){var v=(BRAND.details||{})[f[0]]||'';return '<label'+(f[3]?' class="wide"':'')+'>'+f[1]+'<input name="d_'+f[0]+'" maxlength="'+f[2]+'" value="'+esc(v)+'"'+(canBrand?'':' disabled')+'></label>'}).join('')+'</div>'+
    '<p class="hint" style="margin-top:12px">Hujjat sarlavhasida yuridik nom (bo‘lmasa brend nomi) va rekvizitlar chiqadi; rahbar F.I.Sh. imzo qatoriga yoziladi. Bo‘sh qolsa, hujjatlar avvalgidek chiqadi. Nom va logotip yon panel, kirish oynasi va brauzer sarlavhasida ham ko‘rinadi. PNG/JPEG/WebP, 200 KB gacha, kvadrat rasm tavsiya etiladi.'+(canBrand?'':' O‘zgartirish — asosiy rahbar huquqi.')+'</p>'+
    (canBrand?'<div class="actions" style="margin-top:14px"><button class="btn pri" id="brSave">Saqlash</button></div>':'')+'</form>'+
   '<div class="card"><div class="dh" style="margin-right:0">'+avatar(me.name,me.photoUrl,'lg')+'<div><h2>'+esc(me.name||'—')+'</h2><div class="muted">'+roleLabel()+' · Telegram ID '+esc(me.id)+'</div></div></div>'+
    '<dl class="kv"><dt>Web login</dt><dd><b>'+esc(S.login)+'</b></dd><dt>Telefon</dt><dd>'+esc(me.phone||'—')+'</dd></dl>'+
    '<p class="hint" style="margin-top:14px">Loginni o‘zgartirish yoki parolni unutgan bo‘lsangiz: botda <code>/webparol</code> yoki <code>/webparol yangi_login</code>. Web kirishni butunlay o‘chirish: <code>/webyopish</code>.</p>'+
    '<div class="actions" style="margin-top:16px"><button class="btn danger" id="stLogout">Chiqish</button></div></div>'+
   '<div class="card" id="modCard" style="grid-column:1/-1"><div class="card-h"><h3>'+ic('grid')+' Korxona bo‘limlari</h3>'+(canBrand?'':'<span class="pill">'+ic('shield','sm')+' Faqat ko‘rish</span>')+'</div><div class="loading">Yuklanmoqda…</div></div>'+
   '<div class="card" id="permCard" style="grid-column:1/-1"><div class="loading">Yuklanmoqda…</div></div>'+
   '<div class="card"><div class="card-h"><h3>'+ic('bell')+' Bildirishnomalar</h3></div>'+
    '<div class="switch"><span>Brauzer bildirishnomasi<br><small class="muted">Panel boshqa oynada bo‘lsa ham xabar chiqadi</small></span><button class="tog'+(store('rw-notify')==='1'&&window.Notification&&Notification.permission==='granted'?' on':'')+'" id="tgNotify" aria-label="Brauzer bildirishnomasi"></button></div>'+
    '<div class="switch"><span>Ovozli signal</span><button class="tog'+(store('rw-sound')!=='0'?' on':'')+'" id="tgSound" aria-label="Ovozli signal"></button></div>'+
    '<p class="hint" style="margin-top:10px">Panel har 30 soniyada yangilanadi (fon rejimida — har 60 soniyada). Xabarlar: yangi buyurtma, kassaga topshiriq va uning qabuli, yangi mijoz, agent smenani ochishi/yopishi.</p>'+
    '<div class="actions"><button class="btn sm" id="tgTest">Sinab ko‘rish</button></div></div>'+
   '<form class="card" id="pwForm"><div class="card-h"><h3>Parolni almashtirish</h3></div><div class="form" style="display:grid;gap:12px">'+
    '<label>Joriy parol<input type="password" name="old" autocomplete="current-password" required></label>'+
    '<label>Yangi parol<input type="password" name="new" autocomplete="new-password" minlength="8" required></label>'+
    '<label>Yangi parol (takror)<input type="password" name="new2" autocomplete="new-password" minlength="8" required></label>'+
    '<div class="form-err" id="pwErr"></div><button class="btn pri">Saqlash</button>'+
    '<p class="hint">Kamida 8 belgi. Parol almashganda boshqa kompyuterlardagi kirishlar yopiladi.</p></div></form>'+
   '</div>';
  modulesCard(canBrand);
  permCard(canBrand);
  if(canBrand){var logo=BRAND.logo;
    $('brFile').onchange=function(){var f=this.files[0];this.value='';if(!f)return;
      if(!/^image\/(png|jpeg|webp)$/.test(f.type)){toast('Faqat PNG, JPEG yoki WebP rasm',true);return}
      if(f.size>200000){toast('Logotip 200 KB dan kichik bo‘lsin',true);return}
      var rd=new FileReader();rd.onload=function(){logo=rd.result;$('brPrev').innerHTML='<img src="'+esc(logo)+'" alt="">';$('brPrev').classList.add('has-logo');$('brClear').disabled=false};rd.readAsDataURL(f)};
    $('brClear').onclick=function(){logo='';$('brPrev').innerHTML=ic('grid');$('brPrev').classList.remove('has-logo');this.disabled=true};
    $('brForm').onsubmit=async function(e){e.preventDefault();var b=$('brSave');b.disabled=true;
      var r=await run(function(){return api('branding_save',{name:$('brForm').elements.name.value,logo:logo,details:BR_FIELDS.reduce(function(o,f){o[f[0]]=$('brForm').elements['d_'+f[0]].value;return o},{})})},'Kompaniya ma’lumotlari saqlandi');
      b.disabled=false;if(r&&r.brand){applyBrand(r.brand);document.title=$('pageTitle').textContent+' · '+brandName()}}}
  $('stLogout').onclick=async function(){await auth('logout').catch(function(){});TOKEN='';store('rw-token',null);S.dash=null;S.cache={};showLogin()};
  $('tgNotify').onclick=async function(){var b=this;
    if(b.classList.contains('on')){store('rw-notify','0');b.classList.remove('on');return}
    if(!window.Notification){toast('Bu brauzer bildirishnomani qo‘llamaydi',true);return}
    var p=Notification.permission==='granted'?'granted':await Notification.requestPermission();
    if(p==='granted'){store('rw-notify','1');b.classList.add('on');toast('Bildirishnomalar yoqildi')}else toast('Brauzer ruxsat bermadi. Manzil satridagi qulf belgisidan ruxsat bering.',true)};
  $('tgSound').onclick=function(){var on=!this.classList.contains('on');store('rw-sound',on?'1':'0');this.classList.toggle('on',on);if(on&&!audioCtx&&window.AudioContext){try{audioCtx=new AudioContext()}catch(e){}}};
  $('tgTest').onclick=function(){var h=document.hidden;notifyAll([['Sinov','Bildirishnoma ishlayapti','settings']]);if(store('rw-notify')==='1'&&window.Notification&&Notification.permission==='granted'&&!h){try{new Notification('Sinov',{body:'Bildirishnoma ishlayapti',icon:'/app/premium-kit/emblem.png'})}catch(e){}}};
  $('pwForm').onsubmit=async function(e){
    e.preventDefault();var f=new FormData(this),err=$('pwErr');err.textContent='';
    if(f.get('new')!==f.get('new2')){err.textContent='Yangi parollar bir xil emas.';return}
    var r=await run(function(){return auth('change_password',{old:f.get('old'),new:f.get('new')})},'Parol almashtirildi');if(r)this.reset();
  };
}

boot();
})();
