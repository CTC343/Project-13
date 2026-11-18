// Test the page's pure filtering logic against a small in-memory DOM substitute.
// This does not launch a browser, access the network, or use browser automation.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const work = __dirname;
const inventory = JSON.parse(fs.readFileSync(path.join(work, 'ui_inventory.json'), 'utf8'));
const file = fs.readFileSync(path.join(work, '项目函数阅读手册_2026-11-14', '开始阅读.html'), 'utf8');
const script = file.match(/<script>([\s\S]*)<\/script>/)[1];
const elements = {
  search: {value: '', addEventListener() {}},
  results: {hidden: true, textContent: ''},
  empty: {hidden: true},
  print: {addEventListener() {}},
};
const intro = {hidden: false};
const sections = inventory.map(s => ({
  id: s.id, dataset: {path:s.path, count:s.count}, hidden:true,
  cards: s.cards.map(c => ({...c, hidden:false})),
  querySelectorAll(){return this.cards},
  querySelector(){return {textContent:s.purpose}},
}));
const document = {
  getElementById: id => elements[id],
  querySelector: () => intro,
  querySelectorAll: selector => selector === '.file-section' ? sections : [],
  addEventListener() {}, title:'',
};
const location = {hash:''};
const window = {addEventListener(){}, scrollTo(){}, print(){}};
const ctx=vm.createContext({document,location,window});
vm.runInContext(script,ctx);
assert.equal(intro.hidden,false);
assert.equal(sections.filter(s=>!s.hidden).length,0);
location.hash='#f-client-security-c'; vm.runInContext('show()',ctx);
assert.deepEqual(sections.filter(s=>!s.hidden).map(s=>s.dataset.path),['client/security.c']);
location.hash='#all'; vm.runInContext('show()',ctx);
assert.equal(sections.filter(s=>!s.hidden).length,40);
elements.search.value='security.c'; vm.runInContext('show()',ctx);
assert(sections.some(s=>s.dataset.path==='client/security.c'&&!s.hidden));
elements.search.value='session_key'; vm.runInContext('show()',ctx);
assert(sections.some(s=>s.dataset.path==='server/secure_channel.py'&&!s.hidden));
elements.search.value='!!!不存在的函数!!!'; vm.runInContext('show()',ctx);
assert.equal(elements.empty.hidden,false);
assert.equal(sections.filter(s=>!s.hidden).length,0);
elements.search.value=''; location.hash='#home'; vm.runInContext('show()',ctx);
assert.equal(intro.hidden,false);
console.log('PASS: script syntax, home, file navigation, all files, global search, no-result state');
