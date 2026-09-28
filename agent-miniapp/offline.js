/* ASMAN Agent Mini App offline-first queue and snapshot cache. */
(function(global){
"use strict";

var DB_NAME="asman-agent-offline-v2";
var DB_VERSION=1;
var dbPromise=null;
var syncing=false;
var cfg={};

function clone(value){
  return value==null?value:JSON.parse(JSON.stringify(value));
}
function makeId(){
  if(global.crypto&&crypto.randomUUID)return crypto.randomUUID();
  return "q_"+Date.now().toString(36)+"_"+Math.random().toString(36).slice(2);
}
function openDb(){
  if(dbPromise)return dbPromise;
  dbPromise=new Promise(function(resolve,reject){
    if(!global.indexedDB){reject(Error("IndexedDB mavjud emas."));return}
    var req=indexedDB.open(DB_NAME,DB_VERSION);
    req.onupgradeneeded=function(){
      var db=req.result;
      if(!db.objectStoreNames.contains("kv"))db.createObjectStore("kv",{keyPath:"key"});
      if(!db.objectStoreNames.contains("queue")){
        var q=db.createObjectStore("queue",{keyPath:"id"});
        q.createIndex("createdAt","createdAt",{unique:false});
      }
    };
    req.onsuccess=function(){resolve(req.result)};
    req.onerror=function(){reject(req.error||Error("Offline baza ochilmadi."))};
  });
  return dbPromise;
}
async function storeGet(store,key){
  var db=await openDb();
  return new Promise(function(resolve,reject){
    var tx=db.transaction(store,"readonly"),req=tx.objectStore(store).get(key);
    req.onsuccess=function(){resolve(req.result||null)};
    req.onerror=function(){reject(req.error||Error("Offline ma'lumot o'qilmadi."))};
  });
}
async function storePut(store,value){
  var db=await openDb();
  return new Promise(function(resolve,reject){
    var tx=db.transaction(store,"readwrite"),req=tx.objectStore(store).put(value);
    req.onsuccess=function(){resolve(value)};
    req.onerror=function(){reject(req.error||Error("Offline ma'lumot saqlanmadi."))};
  });
}
async function storeDelete(store,key){
  var db=await openDb();
  return new Promise(function(resolve,reject){
    var tx=db.transaction(store,"readwrite"),req=tx.objectStore(store).delete(key);
    req.onsuccess=function(){resolve()};
    req.onerror=function(){reject(req.error||Error("Offline ma'lumot o'chirilmadi."))};
  });
}
async function storeAll(store){
  var db=await openDb();
  return new Promise(function(resolve,reject){
    var tx=db.transaction(store,"readonly"),req=tx.objectStore(store).getAll();
    req.onsuccess=function(){resolve(req.result||[])};
    req.onerror=function(){reject(req.error||Error("Offline navbat o'qilmadi."))};
  });
}
async function emitStatus(){
  var rows=[];
  try{rows=await storeAll("queue")}catch(_e){}
  var failed=rows.filter(function(x){return x.status==="error"}).length;
  var state={
    online:navigator.onLine!==false,
    pending:rows.length,
    failed:failed,
    syncing:syncing,
    lastError:rows.find(function(x){return x.status==="error"})?.lastError||""
  };
  if(cfg.onStatus)try{cfg.onStatus(state)}catch(_e){}
  return state;
}
async function saveSnapshot(snapshot,actorId){
  if(!snapshot)return;
  var savedAt=Date.now(),value=clone(snapshot),actor=Number(actorId||0);
  await storePut("kv",{key:"snapshot:last",savedAt:savedAt,actorId:actor,value:value});
  if(actor>0)await storePut("kv",{key:"snapshot:actor:"+actor,savedAt:savedAt,actorId:actor,value:value});
}
async function loadSnapshot(actorId){
  var actor=Number(actorId||0),row=null;
  if(actor>0)row=await storeGet("kv","snapshot:actor:"+actor);
  else row=await storeGet("kv","snapshot:last");
  if(!row||!row.value)return null;
  if(actor>0&&Number(row.actorId||0)!==actor)return null;
  var value=clone(row.value);
  value._offlineCached=true;
  value._offlineSavedAt=row.savedAt;
  return value;
}
async function enqueue(record){
  record=record||{};
  var payload=clone(record.payload||{});
  var createdAt=Number(record.createdAt||Date.now());
  if(!payload.offlineTs)payload.offlineTs=Math.floor(createdAt/1000);
  if(record.photoData)delete payload.photoFileId;
  var row={
    id:record.id||makeId(),
    action:String(record.action||""),
    payload:payload,
    nonce:String(record.nonce||makeId()).replace(/-/g,""),
    photoData:record.photoData||null,
    tempClientId:record.tempClientId==null?null:Number(record.tempClientId),
    agentId:Number(record.agentId||0),
    createdAt:createdAt,
    attempts:Number(record.attempts||0),
    status:"pending",
    lastError:""
  };
  await storePut("queue",row);
  await emitStatus();
  return row;
}
async function remapQueuedClient(tempId,realId){
  var rows=await storeAll("queue");
  for(var i=0;i<rows.length;i++){
    var row=rows[i],changed=false;
    if(row.payload&&Number(row.payload.clientId)===Number(tempId)){
      row.payload.clientId=Number(realId);changed=true;
    }
    if(changed)await storePut("queue",row);
  }
  if(cfg.onRemap)await cfg.onRemap(Number(tempId),Number(realId));
}
function sameAgent(row){
  if(!row.agentId||!cfg.currentAgent)return true;
  var current=Number(cfg.currentAgent()||0);
  return !current||current===Number(row.agentId);
}
async function sync(){
  if(syncing||navigator.onLine===false)return false;
  if(!cfg.request||!cfg.canSync||!cfg.canSync())return false;
  var hadRows=false;
  syncing=true;await emitStatus();
  try{
    var rows=await storeAll("queue");
    rows.sort(function(a,b){return Number(a.createdAt)-Number(b.createdAt)});
    hadRows=rows.some(sameAgent);
    for(var i=0;i<rows.length;i++){
      var row=rows[i];
      if(!sameAgent(row))continue;
      try{
        var payload=clone(row.payload||{});
        if(row.photoData){
          var photo=await cfg.request("photo_upload",{imageData:row.photoData});
          if(!photo||!photo.photoFileId)throw Error("Offline foto serverga yuklanmadi.");
          payload.photoFileId=photo.photoFileId;
          row.photoData=null;
          row.payload=clone(payload);
          row.status="pending";
          row.lastError="";
          await storePut("queue",row);
        }
        var outgoing=Object.assign({},payload,{nonce:row.nonce});
        var result=await cfg.request(row.action,outgoing);
        if(row.tempClientId!=null&&result&&result.clientId){
          await remapQueuedClient(row.tempClientId,result.clientId);
        }
        await storeDelete("queue",row.id);
      }catch(err){
        if(cfg.isNetworkError&&cfg.isNetworkError(err))break;
        row.attempts=Number(row.attempts||0)+1;
        row.status="error";
        row.lastError=String(err&&err.message||"Sinxronlash xatosi");
        await storePut("queue",row);
        break;
      }
    }
  }finally{
    syncing=false;
    var state=await emitStatus();
    if(hadRows&&state.pending===0&&cfg.onSynced)try{await cfg.onSynced()}catch(_e){}
  }
  return true;
}
async function clearFailed(){
  var rows=await storeAll("queue");
  for(var i=0;i<rows.length;i++){
    if(rows[i].status==="error"){
      rows[i].status="pending";rows[i].lastError="";
      await storePut("queue",rows[i]);
    }
  }
  await emitStatus();
}
function configure(options){
  cfg=Object.assign({},cfg,options||{});
  emitStatus();
}
global.addEventListener("online",function(){emitStatus();sync()});
global.addEventListener("offline",function(){emitStatus()});

global.ASMANOffline={
  configure:configure,
  saveSnapshot:saveSnapshot,
  loadSnapshot:loadSnapshot,
  enqueue:enqueue,
  sync:sync,
  status:emitStatus,
  clearFailed:clearFailed
};
})(window);
