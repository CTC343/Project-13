const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const text=fs.readFileSync(path.join(__dirname,'交付文件','项目完整流程图.html'),'utf8');
const script=text.match(/<script>([\s\S]*)<\/script>/)[1];
const frame={srcdoc:'',title:''};
const caption={textContent:''};
const handlers={};
const controls={open:{addEventListener(k,v){handlers.open=v}},download:{addEventListener(k,v){handlers.download=v}}};
const buttons=Array.from({length:5},()=>({attrs:{},setAttribute(k,v){this.attrs[k]=v},addEventListener(){},focus(){}}));
const document={
 getElementById:id=>id==='diagram'?frame:id==='description'?caption:controls[id],
 querySelectorAll:()=>buttons,
 createElement:()=>({click(){},remove(){}}),body:{appendChild(){}},title:''
};
const location={hash:''};
const window={addEventListener(){},open(url){assert(url.startsWith('blob:'))}};
const context=vm.createContext({document,location,window,Uint8Array,TextDecoder,atob,URL,Blob});
vm.runInContext(script,context);
const ids=['01-overview','02-auth-channel','03-task-compute','04-results','05-lifecycle'];
for(const [i,id] of ids.entries()){
 location.hash='#'+id;vm.runInContext('fromHash()',context);
 assert(frame.srcdoc.includes('<svg'));
 assert.equal(frame.srcdoc,fs.readFileSync(path.join(__dirname,'交付文件',id+'.html'),'utf8'));
 assert.equal(buttons[i].attrs['aria-selected'],'true');
 assert(caption.textContent.length>15);
 handlers.open();handlers.download();
}
assert(!/<(?:script|link|iframe)[^>]+(?:src|href)="https?:/i.test(text));
console.log('PASS: all five embedded diagrams match checked HTML, tab routing, decoding, actions and offline packaging');
