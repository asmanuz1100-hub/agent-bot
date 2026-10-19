/* ASMAN Agent Mini App offline shell cache.
   Data writes are queued by index.html in IndexedDB; this worker only keeps the UI shell available.
   - Pages and unversioned files (offline.js, Leaflet, logos): network first, cached copy when offline.
   - Files with ?v= in the URL never change, so they come from the cache; older versions are dropped.
   - Map tiles go to their own cache, capped at TILE_LIMIT, so a phone's storage does not fill up.
   - /api/ requests are never cached. */
const CACHE_NAME="asman-agent-shell-20261019-v4";
const TILE_CACHE="asman-agent-tiles-v1";
const TILE_LIMIT=400;
const SHELL=[
  "./",
  "./index.html",
  "./offline.js",
  "./vendor/leaflet/leaflet.css",
  "./vendor/leaflet/leaflet.js"
];

self.addEventListener("install",event=>{
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache=>cache.addAll(SHELL))
      .then(()=>self.skipWaiting())
  );
});

self.addEventListener("activate",event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(key=>key!==CACHE_NAME&&key!==TILE_CACHE).map(key=>caches.delete(key))))
      .then(()=>self.clients.claim())
  );
});

function save(cacheName,req,res){
  if(!res||!res.ok)return;
  const copy=res.clone();
  caches.open(cacheName).then(cache=>cache.put(req,copy)).catch(()=>{});
}

async function trimTiles(){
  const cache=await caches.open(TILE_CACHE);
  const keys=await cache.keys();
  for(let i=0;i<keys.length-TILE_LIMIT;i++)await cache.delete(keys[i]);
}

async function dropOtherVersions(url){
  const cache=await caches.open(CACHE_NAME);
  for(const key of await cache.keys()){
    const k=new URL(key.url);
    if(k.pathname===url.pathname&&k.search!==url.search)await cache.delete(key);
  }
}

self.addEventListener("fetch",event=>{
  const req=event.request;
  if(req.method!=="GET")return;
  const url=new URL(req.url);
  if(url.origin!==self.location.origin||url.pathname.startsWith("/api/"))return;

  if(req.mode==="navigate"){
    event.respondWith(
      fetch(req)
        .then(res=>{
          const copy=res.clone();
          caches.open(CACHE_NAME).then(cache=>cache.put("./index.html",copy)).catch(()=>{});
          return res;
        })
        .catch(()=>caches.match("./index.html").then(res=>res||caches.match("./")))
    );
    return;
  }

  if(url.pathname.startsWith("/tiles/")){
    event.respondWith(
      caches.open(TILE_CACHE).then(cache=>cache.match(req)).then(hit=>hit||fetch(req).then(res=>{
        if(res&&res.ok){
          const copy=res.clone();
          caches.open(TILE_CACHE).then(cache=>cache.put(req,copy)).then(trimTiles).catch(()=>{});
        }
        return res;
      }))
    );
    return;
  }

  if(url.searchParams.has("v")){
    event.respondWith(
      caches.match(req).then(hit=>hit||fetch(req).then(res=>{
        if(res&&res.ok){save(CACHE_NAME,req,res);dropOtherVersions(url).catch(()=>{})}
        return res;
      }))
    );
    return;
  }

  event.respondWith(
    fetch(req)
      .then(res=>{save(CACHE_NAME,req,res);return res})
      .catch(()=>caches.match(req).then(hit=>hit||Response.error()))
  );
});
