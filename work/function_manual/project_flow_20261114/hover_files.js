/* A DOM-only source-file aid. The canonical SVG and its interactions stay intact. */
(() => {
  'use strict';
  const sourceMap = __SOURCE_MAP__;
  const style = document.createElement('style');
  style.textContent = `
    #p13-file-hover{position:fixed;z-index:2147483000;width:min(450px,calc(100vw - 24px));max-height:calc(100vh - 28px);display:flex;flex-direction:column;background:#fff;color:#20382f;border:1px solid #b9d4c6;border-radius:12px;box-shadow:0 14px 48px #102a2930;font:12px/1.65 'Segoe UI','Microsoft YaHei',sans-serif;overflow:hidden;text-align:left;pointer-events:auto}
    #p13-file-hover[hidden]{display:none!important}
    #p13-file-hover .p13-header{padding:14px 17px 11px;border-bottom:1px solid #e3ebe6;background:#f1f7f3;flex:none}
    #p13-file-hover .p13-eyebrow{font-size:10px;letter-spacing:1px;color:#57816b;margin:0 0 3px}
    #p13-file-hover h2{font-size:15px;line-height:1.5;margin:0;font-weight:650;color:inherit}
    #p13-file-hover .p13-body{overflow:auto;overscroll-behavior:contain;padding:4px 17px 9px;max-height:440px}
    #p13-file-hover .p13-group{font-size:10px;font-weight:700;letter-spacing:.7px;color:#638472;margin:12px 0 3px}
    #p13-file-hover .p13-row{padding:8px 0;border-bottom:1px solid #edf1ee}
    #p13-file-hover .p13-row:last-child{border-bottom:0}
    #p13-file-hover .p13-fileline{display:flex;align-items:baseline;justify-content:space-between;gap:12px}
    #p13-file-hover code{font:12px/1.6 Consolas,'Microsoft YaHei',monospace;overflow-wrap:anywhere;color:#155d46;background:none;padding:0}
    #p13-file-hover .p13-kind{font-size:10px;color:#788c80;flex:none}
    #p13-file-hover .p13-role{margin:3px 0 0;color:#52685b;font-size:12px}
    #p13-file-hover .p13-note{padding:9px 17px;border-top:1px solid #e3ebe6;background:#f8faf8;font-size:11px;color:#6b7f72;flex:none}
    html[data-theme="dark"] #p13-file-hover{background:#14261f;color:#e0eee5;border-color:#3b6651;box-shadow:0 14px 48px #0008}
    html[data-theme="dark"] #p13-file-hover .p13-header{background:#1b3327;border-color:#304e3e}
    html[data-theme="dark"] #p13-file-hover .p13-eyebrow,html[data-theme="dark"] #p13-file-hover .p13-group{color:#a2cfb3}
    html[data-theme="dark"] #p13-file-hover code{color:#91dfb5}
    html[data-theme="dark"] #p13-file-hover .p13-role{color:#bdcfc4}
    html[data-theme="dark"] #p13-file-hover .p13-kind{color:#9bb5a6}
    html[data-theme="dark"] #p13-file-hover .p13-row{border-color:#294136}
    html[data-theme="dark"] #p13-file-hover .p13-note{background:#182d23;border-color:#304e3e;color:#a6bdae}
    @media print{#p13-file-hover{display:none!important}}
  `;
  document.head.appendChild(style);
  const tip = document.createElement('aside');
  tip.id = 'p13-file-hover';
  tip.hidden = true;
  tip.setAttribute('role', 'tooltip');
  tip.setAttribute('aria-label', '模块对应的主要源文件');
  document.body.appendChild(tip);
  let timer = 0;
  let activeNode = null;
  let suppressUntil = 0;
  const esc = text => String(text).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clear = () => { if (timer) { clearTimeout(timer); timer = 0; } };
  const hide = () => { clear(); tip.hidden = true; activeNode = null; };
  const soon = () => { clear(); timer = setTimeout(hide, 170); };
  function nodeAt(target) {
    return target && target.closest ? target.closest('svg [data-node-id]') : null;
  }
  function show(node) {
    if (!node || Date.now() < suppressUntil) return;
    const item = sourceMap[node.getAttribute('data-node-id')];
    if (!item) return;
    clear();
    if (activeNode === node && !tip.hidden) return;
    activeNode = node;
    const groups = [['server/','服务端 · PYTHON'],['client/','客户端 · C']];
    let rows = '';
    for (const [prefix, title] of groups) {
      const files = item.files.filter(f => f.path.startsWith(prefix));
      if (!files.length) continue;
      rows += '<div class="p13-group">' + title + '</div>';
      for (const f of files) rows += '<div class="p13-row"><div class="p13-fileline"><code>' + esc(f.path) + '</code><span class="p13-kind">' + esc(f.kind) + '</span></div><p class="p13-role">' + esc(f.role) + '</p></div>';
    }
    tip.innerHTML = '<header class="p13-header"><p class="p13-eyebrow">对应源文件 · ' + item.files.length + ' 个</p><h2>' + esc(item.label) + '</h2></header><div class="p13-body">' + rows + '</div><footer class="p13-note">' + esc(item.note || '主要实现、调用协作与接口声明分别标注；声明不代表已有实现。') + '<br>可移入提示框滚动或复制；Esc 关闭。点击模块仍查看原有关联。</footer>';
    tip.hidden = false;
    const box = node.getBoundingClientRect();
    const width = tip.offsetWidth;
    const height = tip.offsetHeight;
    const vw = window.innerWidth, vh = window.innerHeight;
    let left = box.right + 12;
    if (left + width > vw - 12) left = box.left - width - 12;
    left = Math.max(12, Math.min(left, vw - width - 12));
    const top = Math.max(12, Math.min(box.top - 15, vh - height - 12));
    tip.style.left = left + 'px'; tip.style.top = top + 'px';
  }
  document.addEventListener('pointerover', e => {
    if (tip.contains(e.target)) { clear(); return; }
    const node = nodeAt(e.target);
    if (node) show(node);
  });
  document.addEventListener('pointerout', e => {
    const node = nodeAt(e.target);
    if (!node && !tip.contains(e.target)) return;
    if (e.relatedTarget && (tip.contains(e.relatedTarget) || nodeAt(e.relatedTarget) === activeNode)) return;
    soon();
  });
  document.addEventListener('focusin', e => { const node = nodeAt(e.target); if (node) show(node); });
  document.addEventListener('focusout', e => { if (!e.relatedTarget || !tip.contains(e.relatedTarget)) soon(); });
  document.addEventListener('pointerdown', e => {
    if (nodeAt(e.target)) { suppressUntil = Date.now() + 600; hide(); }
    else if (!tip.contains(e.target)) hide();
  }, true);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') hide(); });
  document.addEventListener('scroll', e => { if (!tip.contains(e.target)) hide(); }, true);
  window.addEventListener('resize', hide);
  window.addEventListener('blur', hide);
})();
