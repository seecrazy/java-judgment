/* 主题切换 + 首页搜索（索引由 build.py 生成） */
(function () {
  'use strict';
  var root = document.documentElement;
  var saved = null;
  try { saved = localStorage.getItem('theme'); } catch (e) {}
  var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  root.dataset.theme = saved || (prefersDark ? 'dark' : 'light');

  var btn = document.getElementById('themeToggle');
  if (btn) {
    btn.addEventListener('click', function () {
      root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('theme', root.dataset.theme); } catch (e) {}
    });
  }

  /* “/” 聚焦搜索（仅首页有搜索框；其他页面跳回首页搜索锚点） */
  document.addEventListener('keydown', function (e) {
    if (e.key !== '/') return;
    var tag = document.activeElement && document.activeElement.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;
    var box = document.getElementById('q');
    if (box) { e.preventDefault(); box.focus(); return; }
    if (location.pathname.endsWith('/') || /index\.html$/.test(location.pathname)) return;
    e.preventDefault();
    location.href = 'index.html#q';
  });

  var q = document.getElementById('q');
  var out = document.getElementById('results');
  if (!q || !out) return;
  var data = null;

  function escHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function render() {
    var v = q.value.trim().toLowerCase();
    if (!v) { out.hidden = true; out.innerHTML = ''; return; }
    var hits = (data || []).filter(function (c) {
      var hay = (c.title + ' ' + c.summary + ' ' + (c.keywords || []).join(' ') + ' ' + c.lineName).toLowerCase();
      return hay.indexOf(v) !== -1;
    });
    out.hidden = false;
    if (!hits.length) {
      out.innerHTML = '<p class="empty">没有命中。试试：G1 / 拒绝策略 / 击穿 / 死锁 / 秒杀 / 虚拟线程。</p>';
      return;
    }
    out.innerHTML = hits.map(function (h) {
      var meta = h.status === 'done'
        ? (h.lineName + ' · ' + h.rounds.join('/') + ' · 信号 ' + h.signal)
        : (h.lineName + ' · 写作中');
      return '<a class="result' + (h.status === 'planned' ? ' planned' : '') + '" href="ch/' + h.id + '.html">' +
        '<span class="r-title">' + escHtml(h.title) + '</span>' +
        '<span class="r-meta">' + escHtml(meta) + '</span></a>';
    }).join('');
  }

  q.addEventListener('focus', function () {
    if (data) return;
    fetch('search.json').then(function (r) { return r.json(); }).then(function (j) {
      data = j; render();
    }).catch(function () { data = []; });
  });
  q.addEventListener('input', render);
  q.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { q.value = ''; render(); q.blur(); }
  });
})();
