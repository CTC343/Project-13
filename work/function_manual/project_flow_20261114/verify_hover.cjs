const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const assert=require('node:assert/strict');
const work=__dirname;
const maps=JSON.parse(fs.readFileSync(path.join(work,'hover_merged_map.json'),'utf8'));
const template=fs.readFileSync(path.join(work,'hover_files.js'),'utf8');
const original=JSON.parse(fs.readFileSync(path.join(work,'hover_original_hash.json'),'utf8'));
const crypto=require('node:crypto');
assert.equal(crypto.createHash('sha256').update(fs.readFileSync(original.path)).digest('hex'),original.sha256);

for(const [slug,map] of Object.entries(maps)){
 const listeners={}; const winListeners={}; const elements=[];
 let now=1000,scheduled=null;
 const DateMock={now:()=>now};
 function element(tag){
  const e={tagName:tag,hidden:false,style:{},attrs:{},offsetWidth:450,offsetHeight:560,innerHTML:'',
    setAttribute(k,v){this.attrs[k]=v},contains(other){return other===this||other?.parent===this}};
  return e;
 }
 const document={head:{appendChild(e){elements.push(e)}},body:{appendChild(e){elements.push(e)}},
  createElement:element,addEventListener(type,handler){(listeners[type]??=[]).push(handler)}};
 const window={innerWidth:1000,innerHeight:700,addEventListener(k,v){winListeners[k]=v}};
 const context=vm.createContext({document,window,Date:DateMock,setTimeout(fn){scheduled=fn;return 1},clearTimeout(){scheduled=null}});
 vm.runInContext(template.replace('__SOURCE_MAP__',JSON.stringify(map)),context);
 const tip=elements.find(e=>e.tagName==='aside');assert(tip);
 const fire=(type,e)=>{for(const handler of listeners[type]||[])handler(e)};
 for(const [id,entry] of Object.entries(map)){
  const node={closest(){return this},getAttribute(){return id},getBoundingClientRect(){return {left:900,right:970,top:650}}};
  fire('pointerover',{target:node});
  assert.equal(tip.hidden,false,[slug,id].join(':'));
  for(const f of entry.files)assert(tip.innerHTML.includes(f.path),[slug,id,f.path].join(':'));
  assert(parseFloat(tip.style.left)>=12);
  assert(parseFloat(tip.style.left)+450<=1000-12);
  assert(parseFloat(tip.style.top)+560<=700-12);
  fire('pointerout',{target:node,relatedTarget:tip});assert.equal(scheduled,null);
  fire('pointerover',{target:tip});assert.equal(scheduled,null);
  fire('scroll',{target:{parent:tip}});assert.equal(tip.hidden,false);
  fire('keydown',{key:'Escape'});assert.equal(tip.hidden,true);
  fire('focusin',{target:node});assert.equal(tip.hidden,false);
  fire('pointerdown',{target:node});assert.equal(tip.hidden,true);
  fire('focusin',{target:node});assert.equal(tip.hidden,true);
  now+=700;
  fire('pointerover',{target:node});assert.equal(tip.hidden,false);
  fire('scroll',{target:document});assert.equal(tip.hidden,true);
 }
 const target=Object.keys(map)[0];
 fire('pointerover',{target:{closest(){return {getAttribute(){return target},getBoundingClientRect(){return {left:0,right:60,top:0}}}}}});
 winListeners.resize();assert.equal(tip.hidden,true);
}
const listen=maps['01-overview'].listen.files.map(f=>f.path);
assert(listen.includes('server/server.py'));
assert(listen.includes('client/network.c'));
assert(listen.includes('client/network.h'));
const referenced=new Set(Object.values(maps).flatMap(m=>Object.values(m)).flatMap(n=>n.files.map(f=>f.path)));
for(const f of ['client/network.c','client/protocol.c','server/protocol.py'])assert(referenced.has(f));
console.log('PASS: all module/file tooltips, viewport placement, hover handoff, scrolling, keyboard/Esc, native click preservation, TCP references and original hash');
