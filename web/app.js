(() => {
  'use strict';

  // ---------- token ----------
  const TOKEN = (() => {
    const fromUrl = new URLSearchParams(location.search).get('t');
    if (fromUrl) {
      try { sessionStorage.setItem('hx_token', fromUrl); } catch (e) {}
      return fromUrl;
    }
    try { return sessionStorage.getItem('hx_token') || ''; } catch (e) { return ''; }
  })();

  const S = {
    skills: [],
    categories: [],
    sources: [],
    collections: [],
    overrides: {},
    pins: [],
    projects: [],
    settings: { showBackups: false, sort: 'recent', theme: 'light' },
    statePath: '',
    revision: '',
    activeSource: 'all',
    activeCat: 'all',
    activeCollection: null,
    q: '',
    sort: 'recent',
    openKey: null,
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const esc = (value) => String(value == null ? '' : value).replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));

  const clamp = (n, min, max) => Math.max(min, Math.min(max, n));

  // ---------- api ----------
  async function api(url, options = {}) {
    const headers = Object.assign({ 'X-Token': TOKEN }, options.headers || {});
    if (options.body) headers['Content-Type'] = 'application/json';
    const res = await fetch(url, Object.assign({}, options, { headers }));
    if (res.status === 403) {
      toast('没有访问令牌，请用启动窗口里的完整链接打开');
      throw new Error('forbidden');
    }
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }

  // ---------- toast ----------
  let toastTimer = 0;
  function toast(message) {
    const node = $('#toast');
    node.textContent = message;
    node.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { node.hidden = true; }, 2100);
  }

  // ---------- theme ----------
  function applyTheme(theme) {
    const resolved = theme === 'auto'
      ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : theme;
    document.documentElement.dataset.theme = resolved === 'dark' ? 'dark' : 'light';
  }

  // ---------- boot ----------
  async function boot(force = false) {
    const data = await api('/api/bootstrap' + (force ? '?force=1' : ''));
    S.skills = data.skills || [];
    S.categories = data.categories || [];
    S.sources = data.sources || [];
    S.collections = data.collections || [];
    S.overrides = data.overrides || {};
    S.pins = data.pins || [];
    S.projects = data.projects || [];
    S.settings = Object.assign(S.settings, data.settings || {});
    S.statePath = data.statePath || '';
    S.revision = data.revision || '';
    S.sort = S.settings.sort || 'recent';
    $('#sort').value = S.sort;
    applyTheme(S.settings.theme || 'light');
    $('#statTotal').textContent = String(data.stats.total);
    $('#statSources').textContent = String(data.sources.length);
    $('#footVersion').textContent = `${data.app} v${data.version}`;
    renderAll();
  }

  // ---------- render ----------
  function renderAll() {
    renderSources();
    renderCategories();
    renderCollections();
    renderMobileFilters();
    renderGrid();
  }

  function renderMobileFilters() {
    const cat = $('#mobileCat');
    const src = $('#mobileSource');
    if (!cat || !src) return;
    cat.innerHTML = S.categories
      .map((c) => `<option value="${esc(c.id)}">${esc(c.label)}（${c.count}）</option>`).join('');
    src.innerHTML = `<option value="all">全部来源（${S.skills.length}）</option>`
      + S.sources.map((s) => `<option value="${esc(s.id)}">${esc(s.label)}（${s.count}）</option>`).join('');
    cat.value = S.activeCollection ? 'all' : S.activeCat;
    src.value = S.activeSource;
  }

  function renderSources() {
    const host = $('#sourceList');
    const rows = [{ id: 'all', label: '全部来源', count: S.skills.length }].concat(
      S.sources.map((s) => ({ id: s.id, label: s.label, count: s.count, color: s.color }))
    );
    host.innerHTML = rows.map((row) => `
      <button class="side-item ${S.activeSource === row.id ? 'active' : ''}" data-source="${esc(row.id)}">
        ${row.color ? `<span class="dot" style="background:${esc(row.color)}"></span>` : ''}
        <span class="name">${esc(row.label)}</span>
        <span class="count">${row.count}</span>
      </button>`).join('');
  }

  function renderCategories() {
    const host = $('#catList');
    const list = S.categories.filter((c) => c.id !== 'all');
    const all = S.categories.find((c) => c.id === 'all');
    host.innerHTML = `
      <button class="side-item ${S.activeCat === 'all' && !S.activeCollection ? 'active' : ''}" data-cat="all">
        <span class="name">全部技能</span><span class="count">${all ? all.count : S.skills.length}</span>
      </button>` + list.map((cat) => `
      <button class="side-item ${S.activeCat === cat.id && !S.activeCollection ? 'active' : ''}" data-cat="${esc(cat.id)}">
        <span class="name">${esc(cat.label)}</span><span class="count">${cat.count}</span>
      </button>`).join('');
  }

  function renderCollections() {
    const host = $('#collectionList');
    if (!S.collections.length) {
      host.innerHTML = '<div class="foot-line" style="padding:2px 9px 0">还没有自定义分类</div>';
      return;
    }
    const existing = new Set(S.skills.map((s) => s.key));
    host.innerHTML = S.collections.map((col) => {
      const count = col.keys.filter((k) => existing.has(k)).length;
      return `<button class="side-item ${S.activeCollection === col.id ? 'active' : ''}" data-collection="${esc(col.id)}">
        <span class="name">${esc(col.name)}</span><span class="count">${count}</span>
      </button>`;
    }).join('');
  }

  function visibleSkills() {
    let list = S.skills;
    if (S.activeCollection) {
      const col = S.collections.find((c) => c.id === S.activeCollection);
      if (!col) return [];
      const keys = new Set(col.keys);
      list = list.filter((s) => keys.has(s.key));
    } else if (S.activeCat === 'pinned') {
      const pins = new Set(S.pins);
      list = list.filter((s) => pins.has(s.key));
    } else if (S.activeCat === 'uncategorized') {
      list = list.filter((s) => s.category === 'other');
    } else if (S.activeCat !== 'all') {
      list = list.filter((s) => s.category === S.activeCat);
    }
    if (S.activeSource !== 'all') {
      list = list.filter((s) => (s.sources || [s.source]).includes(S.activeSource));
    }
    if (S.q) {
      const q = S.q.toLowerCase();
      list = list.filter((s) => [s.displayName, s.name, s.folder, s.description, s.path]
        .join(' ').toLowerCase().includes(q));
    }
    return sortList(list);
  }

  function sortList(list) {
    const copy = list.slice();
    if (S.sort === 'name') {
      copy.sort((a, b) => a.displayName.localeCompare(b.displayName, 'zh-Hans-CN'));
    } else if (S.sort === 'source') {
      copy.sort((a, b) => (a.sourceLabel || '').localeCompare(b.sourceLabel || '', 'zh-Hans-CN')
        || a.displayName.localeCompare(b.displayName, 'zh-Hans-CN'));
    } else {
      copy.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)
        || a.displayName.localeCompare(b.displayName, 'zh-Hans-CN'));
    }
    return copy;
  }

  function sourceColor(id) {
    const hit = S.sources.find((s) => s.id === id);
    return hit ? hit.color : '#8a93a0';
  }

  function renderGrid() {
    const list = visibleSkills();
    const grid = $('#grid');
    const empty = $('#empty');
    $('#crumbRoot').textContent = S.activeCollection
      ? (S.collections.find((c) => c.id === S.activeCollection) || {}).name || '我的分类'
      : (S.categories.find((c) => c.id === S.activeCat) || {}).label || '全部技能';

    const bits = [];
    if (S.activeSource !== 'all') {
      const src = S.sources.find((s) => s.id === S.activeSource);
      if (src) bits.push(src.label);
    }
    if (S.q) bits.push(`搜索「${S.q}」`);
    bits.push(`${list.length} 个`);
    $('#crumbSub').textContent = bits.join(' · ');

    if (!list.length) {
      grid.innerHTML = '';
      empty.hidden = false;
      $('#emptyText').textContent = S.q ? `没有匹配「${S.q}」的技能` : '这个分类下还没有技能';
      return;
    }
    empty.hidden = true;

    grid.innerHTML = list.map((skill) => {
      const pinned = S.pins.includes(skill.key);
      const color = sourceColor(skill.source);
      const desc = skill.description || '（SKILL.md 里没有说明）';
      return `<article class="card" data-key="${esc(skill.key)}">
        <div class="card-head">
          <span class="dot" style="background:${esc(color)}"></span>
          <h3 class="card-title">${esc(skill.displayName)}</h3>
          <button class="star ${pinned ? 'on' : ''}" data-act="pin" title="${pinned ? '取消收藏' : '收藏'}">★</button>
        </div>
        <div class="card-raw">${esc(skill.name)}</div>
        <p class="card-desc">${esc(desc)}</p>
        <div class="card-foot">
          <span class="tag cat">${esc(skill.categoryLabel)}</span>
          <span class="tag">${esc(skill.sourceLabel)}</span>
          ${skill.suite ? `<span class="tag">套件 · ${esc(skill.suite)}</span>` : ''}
          <span class="spacer"></span>
          <button class="more" data-act="menu" title="更多操作">⋯</button>
        </div>
      </article>`;
    }).join('');
  }

  // ---------- persist ----------
  async function persist(patch = {}) {
    const body = Object.assign({
      collections: S.collections,
      overrides: S.overrides,
      pins: S.pins,
      projects: S.projects,
      settings: S.settings,
    }, patch);
    const res = await api('/api/state', { method: 'POST', body: JSON.stringify(body) });
    if (res.state) {
      S.collections = res.state.collections;
      S.overrides = res.state.overrides;
      S.pins = res.state.pins;
      S.settings = res.state.settings;
    }
  }

  async function togglePin(key) {
    const index = S.pins.indexOf(key);
    if (index >= 0) S.pins.splice(index, 1);
    else S.pins.push(key);
    renderGrid();
    if (S.openKey === key) syncDrawerPin();
    try { await persist(); }
    catch (err) { toast('保存失败，请重试'); }
  }

  function syncDrawerPin() {
    const btn = $('#dPin');
    if (!btn) return;
    const on = S.pins.includes(S.openKey);
    btn.textContent = on ? '已收藏' : '收藏';
    btn.classList.toggle('primary', on);
  }

  // ---------- drawer ----------
  function openDrawer(key) {
    const skill = S.skills.find((s) => s.key === key);
    if (!skill) return;
    S.openKey = key;
    $('#dTitle').textContent = skill.displayName;
    $('#dRaw').textContent = skill.name;
    $('#dPath').textContent = skill.path;
    $('#dMeta').innerHTML = `
      <span class="tag cat">${esc(skill.categoryLabel)}</span>
      <span class="tag">${esc(skill.sourceLabel)}</span>
      ${skill.sources.length > 1 ? skill.sources.map((id) => `<span class="tag">${esc(id)}</span>`).join('') : ''}
      ${skill.suite ? `<span class="tag">套件 · ${esc(skill.suite)}</span>` : ''}
      ${skill.builtin ? '<span class="tag">内置</span>' : ''}`;
    $('#dBody').innerHTML = '<div class="loading">正在读取 SKILL.md…</div>';
    syncDrawerPin();
    renderDrawerCollections(skill);
    $('#overlay').hidden = false;
    $('#drawer').hidden = false;
    loadMarkdown(key);
  }

  async function loadMarkdown(key) {
    try {
      const detail = await api('/api/skill?key=' + encodeURIComponent(key));
      if (S.openKey !== key) return;
      const body = String(detail.markdown || '')
        .replace(/^\uFEFF?---\r?\n[\s\S]*?\r?\n---[ \t]*(\r?\n|$)/, '');
      $('#dBody').innerHTML = `<div class="md">${renderMarkdown(body)}</div>`;
    } catch (err) {
      if (S.openKey === key) $('#dBody').innerHTML = '<div class="loading">读取失败</div>';
    }
  }

  function renderDrawerCollections(skill) {
    const host = $('#dCollections');
    const mine = S.collections.filter((c) => c.keys.includes(skill.key));
    host.innerHTML = mine.map((c) => `<span class="tag cat">${esc(c.name)}</span>`).join('')
      + '<button class="btn small" id="dAddCol">＋ 加入分类</button>';
    const btn = $('#dAddCol');
    if (btn) btn.onclick = () => openCollectionPicker(skill.key);
  }

  function closeDrawer() {
    S.openKey = null;
    $('#drawer').hidden = true;
    $('#overlay').hidden = true;
  }

  // ---------- markdown ----------
  function inline(text) {
    let out = esc(text);
    out = out.replace(/`([^`]+?)`/g, (m, p1) => `<code>${p1}</code>`);
    out = out.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/(^|[^*])\*([^*\n]+?)\*/g, '$1<em>$2</em>');
    out = out.replace(/\[([^\]]+?)\]\((https?:\/\/[^\s)]+?)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return out;
  }

  function splitRow(line) {
    return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim());
  }

  function renderMarkdown(source) {
    const lines = String(source).replace(/\r\n?/g, '\n').split('\n');
    const html = [];
    let listType = null;
    const closeList = () => { if (listType) { html.push(`</${listType}>`); listType = null; } };

    for (let i = 0; i < lines.length;) {
      const line = lines[i];

      if (/^```/.test(line)) {
        closeList();
        const buf = [];
        i += 1;
        while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i += 1; }
        i += 1;
        html.push(`<pre><code>${esc(buf.join('\n'))}</code></pre>`);
        continue;
      }

      if (!line.trim()) { closeList(); i += 1; continue; }

      const heading = line.match(/^(#{1,4})\s+(.*)$/);
      if (heading) {
        closeList();
        const level = heading[1].length;
        html.push(`<h${level}>${inline(heading[2])}</h${level}>`);
        i += 1;
        continue;
      }

      if (/^\s*([-*_])\1{2,}\s*$/.test(line)) { closeList(); html.push('<hr>'); i += 1; continue; }

      if (/^\s*>\s?/.test(line)) {
        closeList();
        const buf = [];
        while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
          buf.push(lines[i].replace(/^\s*>\s?/, ''));
          i += 1;
        }
        html.push(`<blockquote>${buf.map(inline).join('<br>')}</blockquote>`);
        continue;
      }

      if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
        closeList();
        const head = splitRow(line);
        const rows = [];
        i += 2;
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) { rows.push(splitRow(lines[i])); i += 1; }
        html.push('<table><thead><tr>' + head.map((c) => `<th>${inline(c)}</th>`).join('') + '</tr></thead><tbody>'
          + rows.map((r) => '<tr>' + r.map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>').join('')
          + '</tbody></table>');
        continue;
      }

      const ul = line.match(/^\s*[-*+]\s+(.*)$/);
      const ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
      if (ul || ol) {
        const type = ul ? 'ul' : 'ol';
        if (listType !== type) { closeList(); html.push(`<${type}>`); listType = type; }
        html.push(`<li>${inline((ul || ol)[1])}</li>`);
        i += 1;
        continue;
      }

      closeList();
      const buf = [line];
      i += 1;
      while (i < lines.length && lines[i].trim()
        && !/^(#{1,4}\s|```|\s*[-*+]\s|\s*\d+[.)]\s|\s*>|\s*\|)/.test(lines[i])) {
        buf.push(lines[i]);
        i += 1;
      }
      html.push(`<p>${buf.map(inline).join('<br>')}</p>`);
    }
    closeList();
    return html.join('\n');
  }

  // ---------- copy ----------
  async function copyText(text, message) {
    try {
      await navigator.clipboard.writeText(text);
      toast(message || '已复制');
    } catch (err) {
      const area = document.createElement('textarea');
      area.value = text;
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.appendChild(area);
      area.select();
      try { document.execCommand('copy'); toast(message || '已复制'); }
      catch (e2) { toast('复制失败'); }
      document.body.removeChild(area);
    }
  }

  // ---------- menu ----------
  function hideMenu() { $('#menu').hidden = true; }

  function showMenu(anchor, skill) {
    S.openKeyForMenu = skill.key;
    const menu = $('#menu');
    const cats = S.categories.filter((c) => !['all', 'pinned', 'uncategorized', 'other'].includes(c.id));
    const current = S.overrides[skill.key] || skill.category;
    menu.innerHTML = `
      <button class="menu-item" data-mact="copyName">复制原始调用名</button>
      <button class="menu-item" data-mact="copyPath">复制文件路径</button>
      <button class="menu-item" data-mact="reveal">在资源管理器中打开</button>
      <div class="menu-sep"></div>
      <div class="menu-label">调整归类</div>
      <div class="menu-cats">
        ${cats.map((c) => `<button class="menu-cat ${c.id === current ? 'on' : ''}" data-cat-set="${esc(c.id)}">${esc(c.label)}</button>`).join('')}
      </div>
      <div class="menu-sep"></div>
      <button class="menu-item" data-mact="addTo">加入我的分类…</button>
      ${S.overrides[skill.key] ? '<button class="menu-item" data-mact="auto">恢复自动归类</button>' : ''}
    `;
    menu.hidden = false;
    const rect = anchor.getBoundingClientRect();
    const width = menu.offsetWidth;
    const height = menu.offsetHeight;
    menu.style.left = clamp(rect.right - width, 8, window.innerWidth - width - 8) + 'px';
    menu.style.top = clamp(rect.bottom + 6, 8, window.innerHeight - height - 8) + 'px';
  }

  async function setCategory(key, category) {
    if (category === 'other') delete S.overrides[key];
    else S.overrides[key] = category;
    hideMenu();
    try { await persist(); boot(); } catch (err) { toast('保存失败'); }
  }

  async function resetCategory(key) {
    delete S.overrides[key];
    hideMenu();
    try { await persist(); boot(); } catch (err) { toast('保存失败'); }
  }

  // ---------- modal ----------
  function openModal(title, body, onMount) {
    $('#modalTitle').textContent = title;
    $('#modalBody').innerHTML = body;
    $('#modal').hidden = false;
    if (onMount) onMount($('#modalBody'));
  }

  function closeModal() { $('#modal').hidden = true; }

  function newCollectionDialog(skillKey) {
    openModal('新建分类', `
      <div class="field">
        <label>分类名称</label>
        <input id="newColName" class="input" maxlength="20" placeholder="例如：公众号一条龙">
      </div>
      <div class="hint">分类只保存在本工具里，不会移动或修改任何技能文件。</div>
      <div class="modal-actions">
        <button class="btn" data-close>取消</button>
        <button class="btn primary" id="doCreateCol">创建</button>
      </div>`, (root) => {
      const input = $('#newColName', root);
      input.focus();
      const submit = async () => {
        const name = input.value.trim();
        if (!name) { input.focus(); return; }
        const id = 'c_' + Date.now().toString(36);
        S.collections.push({ id, name, keys: skillKey ? [skillKey] : [] });
        try {
          await persist();
          closeModal();
          renderCollections();
          if (skillKey && S.openKey === skillKey) {
            const skill = S.skills.find((s) => s.key === skillKey);
            if (skill) renderDrawerCollections(skill);
          }
          toast(`已创建「${name}」`);
        } catch (err) { toast('保存失败'); }
      };
      $('#doCreateCol', root).onclick = submit;
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit(); });
      $$('[data-close]', root).forEach((b) => { b.onclick = closeModal; });
    });
  }

  function openCollectionPicker(skillKey) {
    const rows = S.collections.length
      ? S.collections.map((c) => `
        <label class="row" style="cursor:pointer">
          <div><div class="row-label">${esc(c.name)}</div>
          <div class="row-hint">${c.keys.length} 个技能</div></div>
          <input type="checkbox" data-col="${esc(c.id)}" ${c.keys.includes(skillKey) ? 'checked' : ''}
            style="width:18px;height:18px;accent-color:var(--accent)">
        </label>`).join('')
      : '<div class="hint">还没有自定义分类，先新建一个。</div>';

    openModal('加入我的分类', `
      ${rows}
      <div class="field" style="margin-top:14px">
        <label>或者新建分类</label>
        <div style="display:flex;gap:8px">
          <input id="quickColName" class="input" style="flex:1" maxlength="20" placeholder="新分类名称">
          <button class="btn" id="quickCreate">新建并加入</button>
        </div>
      </div>
      <div class="modal-actions"><button class="btn primary" data-close>完成</button></div>`, (root) => {
      $$('[data-col]', root).forEach((box) => {
        box.onchange = async () => {
          const col = S.collections.find((c) => c.id === box.dataset.col);
          if (!col) return;
          if (box.checked && !col.keys.includes(skillKey)) col.keys.push(skillKey);
          if (!box.checked) col.keys = col.keys.filter((k) => k !== skillKey);
          try { await persist(); renderCollections(); } catch (err) { toast('保存失败'); }
        };
      });
      const create = async () => {
        const input = $('#quickColName', root);
        const name = input.value.trim();
        if (!name) { input.focus(); return; }
        S.collections.push({ id: 'c_' + Date.now().toString(36), name, keys: [skillKey] });
        try {
          await persist();
          closeModal();
          renderCollections();
          const skill = S.skills.find((s) => s.key === skillKey);
          if (skill && S.openKey === skillKey) renderDrawerCollections(skill);
          toast(`已加入「${name}」`);
        } catch (err) { toast('保存失败'); }
      };
      $('#quickCreate', root).onclick = create;
      $$('[data-close]', root).forEach((b) => { b.onclick = closeModal; });
    });
  }

  function openSettings() {
    openModal('设置', `
      <div class="row">
        <div><div class="row-label">显示备份技能</div>
        <div class="row-hint">扫描 _backup_* 目录，默认关闭</div></div>
        <label class="switch"><input type="checkbox" id="setBackups" ${S.settings.showBackups ? 'checked' : ''}><span></span></label>
      </div>
      <div class="row">
        <div><div class="row-label">界面主题</div>
        <div class="row-hint">跟随系统或固定浅色 / 深色</div></div>
        <select id="setTheme" class="select">
          <option value="light" ${S.settings.theme === 'light' ? 'selected' : ''}>浅色</option>
          <option value="dark" ${S.settings.theme === 'dark' ? 'selected' : ''}>深色</option>
          <option value="auto" ${S.settings.theme === 'auto' ? 'selected' : ''}>跟随系统</option>
        </select>
      </div>
      <div class="field">
        <label>数据文件</label>
        <div class="mono-box">${esc(S.statePath)}</div>
        <div class="hint">分类、收藏、设置都保存在这个 JSON 里。删除它等于恢复出厂设置，技能文件不受影响。</div>
      </div>
      <div class="field">
        <label>技能来源目录</label>
        <div class="hint">${S.sources.map((s) => `· ${esc(s.label)}：${s.count} 个`).join('<br>')}</div>
      </div>
      <div class="modal-actions">
        <button class="btn" id="setRescan">重新扫描</button>
        <button class="btn primary" data-close>完成</button>
      </div>`, (root) => {
      $('#setBackups', root).onchange = async (e) => {
        S.settings.showBackups = e.target.checked;
        try { await persist(); await boot(true); toast('已更新扫描范围'); }
        catch (err) { toast('保存失败'); }
      };
      $('#setTheme', root).onchange = async (e) => {
        S.settings.theme = e.target.value;
        applyTheme(S.settings.theme);
        try { await persist(); } catch (err) { toast('保存失败'); }
      };
      $('#setRescan', root).onclick = async () => {
        closeModal();
        await rescan();
      };
      $$('[data-close]', root).forEach((b) => { b.onclick = closeModal; });
    });
  }

  // ---------- actions ----------
  async function rescan() {
    try {
      await api('/api/refresh', { method: 'POST', body: JSON.stringify({}) });
      await boot(true);
      toast('已重新扫描');
    } catch (err) { toast('刷新失败'); }
  }

  async function revealSkill(key) {
    try {
      const res = await api('/api/reveal', { method: 'POST', body: JSON.stringify({ key }) });
      if (!res.ok) toast('打开失败，路径可能已不存在');
    } catch (err) { toast('打开失败'); }
  }

  async function openSkillFile(key) {
    try {
      const res = await api('/api/open', { method: 'POST', body: JSON.stringify({ key }) });
      if (!res.ok) toast('打开失败，可能没有关联的 Markdown 编辑器');
    } catch (err) { toast('打开失败'); }
  }

  // ---------- events ----------
  function bind() {
    $('#search').addEventListener('input', (() => {
      let timer = 0;
      return (e) => {
        clearTimeout(timer);
        const value = e.target.value.trim();
        timer = setTimeout(() => { S.q = value; renderGrid(); }, 120);
      };
    })());

    $('#sourceList').addEventListener('click', (e) => {
      const btn = e.target.closest('[data-source]');
      if (!btn) return;
      S.activeSource = btn.dataset.source;
      renderSources();
      renderMobileFilters();
      renderGrid();
    });

    $('#catList').addEventListener('click', (e) => {
      const btn = e.target.closest('[data-cat]');
      if (!btn) return;
      S.activeCat = btn.dataset.cat;
      S.activeCollection = null;
      renderCategories();
      renderCollections();
      renderMobileFilters();
      renderGrid();
    });

    $('#collectionList').addEventListener('click', (e) => {
      const btn = e.target.closest('[data-collection]');
      if (!btn) return;
      S.activeCollection = btn.dataset.collection;
      S.activeCat = 'all';
      renderCollections();
      renderCategories();
      renderMobileFilters();
      renderGrid();
    });

    $('#btnNewCollection').onclick = (e) => {
      e.stopPropagation();
      newCollectionDialog(null);
    };

    $('#mobileCat').onchange = (e) => {
      S.activeCat = e.target.value;
      S.activeCollection = null;
      renderCategories();
      renderCollections();
      renderGrid();
    };

    $('#mobileSource').onchange = (e) => {
      S.activeSource = e.target.value;
      renderSources();
      renderGrid();
    };

    $('#sort').onchange = async (e) => {
      S.sort = e.target.value;
      S.settings.sort = S.sort;
      renderGrid();
      try { await persist(); } catch (err) {}
    };

    $('#btnRefresh').onclick = rescan;
    $('#btnSettings').onclick = openSettings;
    $('#btnExport').onclick = () => {
      window.open('/api/export?t=' + encodeURIComponent(TOKEN), '_blank');
    };
    $('#btnClear').onclick = () => {
      S.q = '';
      S.activeSource = 'all';
      S.activeCat = 'all';
      S.activeCollection = null;
      $('#search').value = '';
      renderAll();
    };

    $('#grid').addEventListener('click', (e) => {
      const card = e.target.closest('[data-key]');
      if (!card) return;
      const key = card.dataset.key;
      const act = e.target.closest('[data-act]');
      if (act) {
        e.stopPropagation();
        if (act.dataset.act === 'pin') return togglePin(key);
        if (act.dataset.act === 'menu') {
          const skill = S.skills.find((s) => s.key === key);
          if (skill) showMenu(act, skill);
          return;
        }
      }
      openDrawer(key);
    });

    $('#dClose').onclick = closeDrawer;
    $('#overlay').onclick = closeDrawer;
    $('#dCopyName').onclick = () => {
      const skill = S.skills.find((s) => s.key === S.openKey);
      if (skill) copyText(skill.name, '已复制调用名');
    };

    $('#dBody').addEventListener('click', (e) => {
      const link = e.target.closest('a[href]');
      if (link) link.setAttribute('target', '_blank');
    });

    $$('[data-dact]').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (!S.openKey) return;
        const act = btn.dataset.dact;
        const skill = S.skills.find((s) => s.key === S.openKey);
        if (act === 'reveal') return revealSkill(S.openKey);
        if (act === 'open') return openSkillFile(S.openKey);
        if (act === 'copyPath') return copyText(skill ? skill.path : '', '已复制路径');
        if (act === 'pin') return togglePin(S.openKey);
      });
    });

    // menu
    $('#menu').addEventListener('click', async (e) => {
      const skill = S.skills.find((s) => s.key === S.openKeyForMenu);
      const catBtn = e.target.closest('[data-cat-set]');
      if (catBtn) {
        const key = S.openKeyForMenu;
        if (key) await setCategory(key, catBtn.dataset.catSet);
        return;
      }
      const item = e.target.closest('[data-mact]');
      if (!item || !skill) return;
      const act = item.dataset.mact;
      if (act === 'copyName') { hideMenu(); return copyText(skill.name, '已复制调用名'); }
      if (act === 'copyPath') { hideMenu(); return copyText(skill.path, '已复制路径'); }
      if (act === 'reveal') { hideMenu(); return revealSkill(skill.key); }
      if (act === 'addTo') { hideMenu(); return openCollectionPicker(skill.key); }
      if (act === 'auto') { return resetCategory(skill.key); }
    });

    document.addEventListener('click', (e) => {
      if (!e.target.closest('#menu') && !e.target.closest('[data-act="menu"]')) hideMenu();
    });

    // modal
    $('#modalClose').onclick = closeModal;
    $('#modal').addEventListener('click', (e) => {
      if (e.target.id === 'modal') closeModal();
    });

    // keyboard
    document.addEventListener('keydown', (e) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
      if (e.key === '/' && !typing) {
        e.preventDefault();
        $('#search').focus();
        return;
      }
      if (e.key === 'Escape') {
        if (!$('#menu').hidden) return hideMenu();
        if (!$('#modal').hidden) return closeModal();
        if (!$('#drawer').hidden) return closeDrawer();
      }
    });

    // auto refresh
    setInterval(async () => {
      if (document.hidden) return;
      try {
        const res = await api('/api/revision');
        if (res.revision && S.revision && res.revision !== S.revision) {
          await boot(true);
          toast('技能目录有变化，已刷新');
        }
      } catch (err) {}
    }, 8000);
  }

  // ---------- start ----------
  bind();
  boot().catch((err) => {
    $('#grid').innerHTML = `<div class="loading">加载失败：${esc(err.message)}<br>请确认服务仍在运行，并使用启动窗口里的完整链接。</div>`;
  });
})();
