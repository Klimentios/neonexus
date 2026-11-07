/* NEONEXUS shell: the reference layout (CLEAN skin) plus two real views for every skin.
   - Agents: each agent's own CLI side by side (split), live, with input, keys and
     approval buttons. Talks to /api/agent-term/NAME and /api/agent-panes/NAME/answer.
   - Projects: goals, done criteria with evidence, progress, accept/reopen (/api/projects).
   Every button opens something that exists; nothing here is a mock. */
(function () {
  'use strict';
  const ru = () => (window.NX_LANG || document.documentElement.lang) === 'ru';
  // t(english, russian, ...args) with {0} placeholders: the current language from i18n.js, English fallback
  const t = (en, rus, ...args) => (window.nxT ? window.nxT(en, rus, ...args) : (ru() ? rus : en));
  const $ = (sel, root = document) => root.querySelector(sel);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };
  const store = {
    get(k, d) { try { const v = localStorage.getItem('nx-' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem('nx-' + k, JSON.stringify(v)); } catch (e) {} },
  };
  async function api(path, opts = {}) {
    const r = await fetch(path, {
      ...opts,
      headers: { 'Content-Type': 'application/json', 'X-Session-Token': window.SESSION_TOKEN, ...(opts.headers || {}) },
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || data.result || ('HTTP ' + r.status));
    return data;
  }
  const icon = (d) => `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const I = {
    team: icon('<circle cx="9" cy="8" r="3.2"/><path d="M3 19c.6-3.2 3-5 6-5s5.4 1.8 6 5"/><circle cx="17" cy="9" r="2.4"/><path d="M16 14c2.6.2 4.4 1.8 5 4.6"/>'),
    chat: icon('<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/>'),
    folder: icon('<path d="M3 6.5h6l2 2h10V19H3z"/>'),
    task: icon('<rect x="4" y="4" width="16" height="16" rx="3"/><path d="m8.5 12 2.5 2.5 5-5"/>'),
    agents: icon('<rect x="3" y="4" width="8" height="7" rx="1.5"/><rect x="13" y="4" width="8" height="7" rx="1.5"/><rect x="3" y="13" width="8" height="7" rx="1.5"/><rect x="13" y="13" width="8" height="7" rx="1.5"/>'),
    code: icon('<path d="m8 8-4 4 4 4M16 8l4 4-4 4M13.5 5l-3 14"/>'),
    book: icon('<path d="M4 5.5C6.5 4 9.5 4 12 5.5 14.5 4 17.5 4 20 5.5V19c-2.5-1.5-5.5-1.5-8 0-2.5-1.5-5.5-1.5-8 0z"/><path d="M12 5.5V19"/>'),
    plus: icon('<path d="M12 5v14M5 12h14"/>'),
    bolt: icon('<path d="M13 3 5 14h6l-1 7 8-11h-6z"/>'),
    pin: icon('<path d="M9 4h6l-1 5 3 3H7l3-3z"/><path d="M12 12v8"/>'),
    split: icon('<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/>'),
    grid: icon('<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16M3 12h18"/>'),
    one: icon('<rect x="3" y="4" width="18" height="16" rx="2"/>'),
    x: icon('<path d="M6 6l12 12M18 6 6 18"/>'),
    send: icon('<path d="M4 12 20 4l-6 16-2.5-6.5z"/>'),
    max: icon('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>'),
    mic: icon('<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>'),
    stop: icon('<rect x="6" y="6" width="12" height="12" rx="2"/>'),
    plug: icon('<path d="M9 3v5M15 3v5"/><path d="M6 8h12v3a6 6 0 0 1-12 0z"/><path d="M12 17v4"/>'),
    copy: icon('<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>'),
  };
  const ROLE = {
    claude: ['Claude Code · build', 'Claude Code · разработка'],
    codex: ['Codex · build', 'Codex · разработка'],
    gemini: ['Antigravity · research', 'Antigravity · исследования'],
    claudechat: ['Claude · chat', 'Claude · чат'],
    gptchat: ['GPT · chat', 'GPT · чат'],
    geminichat: ['Gemini · chat', 'Gemini · чат'],
  };
  const role = (n) => { const r = ROLE[n] || ROLE[n.replace(/-\d+$/, '').replace(/^squad-/, '')]; return r ? t(r[0], r[1]) : (n.startsWith('squad-') ? t('Squad member', 'Субагент') : ''); };

  // ---------- agent state (shared with chat.js' activityState) ----------
  function agents() {
    const status = (typeof activityState !== 'undefined' && activityState.status) || {};
    const blocked = (typeof activityState !== 'undefined' && activityState.blocked) || {};
    const bases = (typeof baseColors !== 'undefined' && baseColors) || {};
    const all = new Map();
    for (const [n, info] of Object.entries(bases)) if (info.listed !== false) all.set(n, { name: n, label: info.label || n, available: false, busy: false });
    for (const [n, info] of Object.entries(status)) if (n !== 'paused') all.set(n, { name: n, label: info.label || (bases[n] || {}).label || n, available: !!info.available, busy: !!info.busy });
    for (const a of all.values()) {
      a.state = !a.available ? 'offline' : blocked[a.name] === 'approval' ? 'approval' : blocked[a.name] === 'quota' ? 'quota' : blocked[a.name] === 'signin' ? 'signin' : a.busy ? 'working' : 'online';
    }
    const order = { working: 0, approval: 1, online: 2, signin: 3, quota: 4, offline: 5 };
    return [...all.values()].sort((a, b) => order[a.state] - order[b.state] || a.label.localeCompare(b.label));
  }
  const STATE = {
    online: ['Online', 'В сети'], working: ['Working', 'Работает'], approval: ['Needs approval', 'Ждёт разрешения'],
    quota: ['Out of quota', 'Лимит исчерпан'], signin: ['Sign-in needed', 'Нужен вход'], offline: ['Offline', 'Не в сети'],
  };
  const stateText = (s) => t(STATE[s][0], STATE[s][1]);
  const face = (n) => (window.agentFaceSvg ? window.agentFaceSvg(n) : '');

  // ---------- views ----------
  let view = 'chat';
  const views = {};
  function setView(next) {
    const codeBtn = $('#workspace-toggle');
    const codeOn = codeBtn && codeBtn.classList.contains('active');
    if (next === 'editor') next = 'code';  // the old "simple editor" is the Code tab now
    if (next === 'code' && !codeOn) codeBtn?.click();
    if (next !== 'code' && codeOn) codeBtn.click();
    view = next;
    const tl = $('#timeline');
    if (tl && next !== 'code') tl.hidden = next !== 'chat' && next !== 'codemode';
    for (const [k, node] of Object.entries(views)) node.hidden = k !== next;
    document.body.dataset.nxView = next;
    try { history.replaceState(null, '', next === 'chat' ? location.pathname + location.search : '#' + next); } catch (e) { /* ignore */ }
    document.querySelectorAll('[data-nx-view]').forEach((b) => b.classList.toggle('active', b.dataset.nxView === next));
    const crumb = $('#nx-crumb');
    if (crumb) crumb.textContent = '/ ' + viewName(next);
    if (next === 'agents') Split.start(); else Split.stop();
    if (next === 'projects') Projects.load();
    if (next === 'connect') Connect.load();
    if (next === 'code') IDE.load();
    if (next === 'codemode') CM.enter();
  }
  const viewName = (v) => ({ chat: t('Team', 'Команда'), agents: t('Agents', 'Агенты'), projects: t('Projects', 'Проекты'), code: t('Code', 'Код'), codemode: t('Code mode', 'Code mode'), connect: t('Connect AI', 'Подключить ИИ') }[v] || v);

  // ---------- ANSI -> HTML for the terminals ----------
  const PAL = ['#1b1f27', '#e5534b', '#57ab5a', '#c69026', '#539bf5', '#b083f0', '#39c5cf', '#d1d7e0',
    '#636e7b', '#ff938a', '#6bc46d', '#daaa3f', '#6cb6ff', '#dcbdfb', '#56d4dd', '#f0f3f6'];
  function xterm(n) {
    if (n < 16) return PAL[n];
    if (n < 232) { n -= 16; const c = (v) => [0, 95, 135, 175, 215, 255][v]; return `rgb(${c(Math.floor(n / 36))},${c(Math.floor(n / 6) % 6)},${c(n % 6)})`; }
    const g = 8 + (n - 232) * 10; return `rgb(${g},${g},${g})`;
  }
  // Safe in text and in quoted attributes ("..." and '...').
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  // Colors that go into a style="" attribute: only #hex or rgb(r,g,b), else the fallback.
  const safeColor = (c, fallback = '') => (typeof c === 'string' &&
    (/^#[0-9a-fA-F]{3,8}$/.test(c) || /^rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)$/.test(c))) ? c : fallback;
  function ansiHtml(src) {
    let out = '', st = {}, open = false;
    const flush = () => {
      if (open) { out += '</span>'; open = false; }
      let fg = safeColor(st.fg), bg = safeColor(st.bg);
      if (st.inv) [fg, bg] = [bg || 'var(--nx-term-bg)', fg || 'var(--nx-term-fg)'];
      const css = (fg ? `color:${fg};` : '') + (bg ? `background:${bg};` : '') + (st.b ? 'font-weight:700;' : '') +
        (st.d ? 'opacity:.6;' : '') + (st.i ? 'font-style:italic;' : '') + (st.u ? 'text-decoration:underline;' : '');
      if (css) { out += `<span style="${css}">`; open = true; }
    };
    const parts = src.split(/\x1b\[([0-9;:]*)m/);
    for (let i = 0; i < parts.length; i++) {
      if (i % 2 === 0) { out += esc(parts[i]); continue; }
      const codes = parts[i] === '' ? [0] : parts[i].split(/[;:]/).map(Number);
      for (let j = 0; j < codes.length; j++) {
        const c = codes[j];
        if (c === 0) st = {};
        else if (c === 1) st.b = 1; else if (c === 2) st.d = 1; else if (c === 3) st.i = 1; else if (c === 4) st.u = 1; else if (c === 7) st.inv = 1;
        else if (c === 22) { st.b = 0; st.d = 0; } else if (c === 23) st.i = 0; else if (c === 24) st.u = 0; else if (c === 27) st.inv = 0;
        else if (c >= 30 && c <= 37) st.fg = PAL[c - 30]; else if (c >= 90 && c <= 97) st.fg = PAL[c - 82];
        else if (c >= 40 && c <= 47) st.bg = PAL[c - 40]; else if (c >= 100 && c <= 107) st.bg = PAL[c - 92];
        else if (c === 39) st.fg = null; else if (c === 49) st.bg = null;
        else if ((c === 38 || c === 48) && codes[j + 1] === 5) { st[c === 38 ? 'fg' : 'bg'] = xterm(codes[j + 2] || 0); j += 2; }
        else if ((c === 38 || c === 48) && codes[j + 1] === 2) { st[c === 38 ? 'fg' : 'bg'] = `rgb(${codes[j + 2] | 0},${codes[j + 3] | 0},${codes[j + 4] | 0})`; j += 4; }
      }
      flush();
    }
    if (open) out += '</span>';
    return out;
  }


  // Send into the current channel as the user through the normal composer path, without
  // the composer's own @mention toggles (they would wake agents nobody asked here).
  function sendAs(text) {
    const input = document.getElementById('input'); if (!input || typeof sendMessage !== 'function') return false;
    const toggles = (typeof activeMentions !== 'undefined' && activeMentions instanceof Set) ? [...activeMentions] : [];
    if (toggles.length) activeMentions.clear();
    const keep = input.value; input.value = text;
    try { sendMessage(); } finally { input.value = keep; toggles.forEach((n) => activeMentions.add(n)); }
    return true;
  }

  // ---------- Split: agents' own terminals ----------
  const Split = {
    timer: null, panes: new Map(),
    layout: store.get('split-layout', 'grid'),
    picked: store.get('split-agents', null),
    build() {
      const root = el('section', 'nx-view nx-agents-view'); root.id = 'nx-view-agents'; root.hidden = true;
      const bar = el('div', 'nx-viewbar');
      bar.innerHTML = `<div class="nx-viewbar-title"><strong>${t('Agent terminals', 'Терминалы агентов')}</strong><span>${t('Each agent in its own CLI. Type to it, approve, interrupt.', 'Каждый агент в своём CLI. Пишите ему, разрешайте, прерывайте.')}</span></div>`;
      const pick = el('div', 'nx-pick'); pick.id = 'nx-split-pick';
      const lay = el('div', 'nx-seg');
      for (const [k, ic, lbl] of [['one', I.one, t('One', 'Один')], ['split', I.split, t('Split', 'Сплит')], ['grid', I.grid, t('Grid', 'Сетка')]]) {
        const b = el('button', 'nx-seg-btn' + (this.layout === k ? ' active' : '')); b.type = 'button'; b.innerHTML = ic; b.title = lbl;
        b.addEventListener('click', () => { this.layout = k; store.set('split-layout', k); lay.querySelectorAll('button').forEach((x) => x.classList.toggle('active', x === b)); this.render(); });
        lay.append(b);
      }
      bar.append(pick, lay);
      const grid = el('div', 'nx-term-grid'); grid.id = 'nx-term-grid';
      root.append(bar, grid);
      return root;
    },
    chosen() {
      const list = agents().filter((a) => a.state !== 'offline');
      if (!this.picked) this.picked = list.filter((a) => !/chat$/.test(a.name)).map((a) => a.name).slice(0, 4);
      return list.filter((a) => this.picked.includes(a.name));
    },
    renderPicker() {
      const pick = $('#nx-split-pick'); if (!pick) return;
      pick.replaceChildren();
      for (const a of agents().filter((x) => x.state !== 'offline')) {
        const b = el('button', 'nx-chip' + (this.picked && this.picked.includes(a.name) ? ' on' : '')); b.type = 'button';
        b.innerHTML = `<span class="nx-face">${face(a.name)}</span><span>${esc(a.label)}</span><i class="nx-dot s-${a.state}"></i>`;
        b.addEventListener('click', () => {
          const p = new Set(this.picked || []); p.has(a.name) ? p.delete(a.name) : p.add(a.name);
          this.picked = [...p]; store.set('split-agents', this.picked); this.render();
        });
        pick.append(b);
      }
    },
    focus(name) {
      this.picked = [...new Set([name, ...(this.picked || [])])]; store.set('split-agents', this.picked);
      this.layout = this.layout === 'one' ? 'one' : this.layout; this.solo = name;
      setView('agents');
    },
    render() {
      this.renderPicker();
      const grid = $('#nx-term-grid'); if (!grid) return;
      let list = this.chosen();
      if (this.layout === 'one') list = list.filter((a) => a.name === (this.solo || list[0]?.name)).slice(0, 1).concat(list.length && !list.some((a) => a.name === this.solo) ? [list[0]] : []).slice(0, 1);
      grid.dataset.layout = this.layout; grid.dataset.count = String(list.length);
      const keep = new Set(list.map((a) => a.name));
      for (const [n, p] of this.panes) if (!keep.has(n)) { p.root.remove(); this.panes.delete(n); }
      if (!list.length) {
        if (!$('.nx-empty', grid)) grid.append(el('div', 'nx-empty', t('Pick agents above to watch their terminals.', 'Выберите агентов сверху, чтобы видеть их терминалы.')));
        return;
      }
      $('.nx-empty', grid)?.remove();
      for (const a of list) {
        let p = this.panes.get(a.name);
        if (!p) { p = this.pane(a); this.panes.set(a.name, p); }
        grid.append(p.root);
        p.update(a);
      }
    },
    pane(a) {
      const root = el('article', 'nx-term');
      const head = el('header', 'nx-term-head');
      head.innerHTML = `<span class="nx-face">${face(a.name)}</span><div class="nx-term-id"><strong>${esc(a.label)} <span class="nx-badge"></span></strong><small>${esc(role(a.name))}</small></div>`;
      const tools = el('div', 'nx-term-tools');
      const keyBtn = (label, key, title) => { const b = el('button', 'nx-mini', label); b.type = 'button'; b.title = title; b.addEventListener('click', () => this.key(a.name, key)); return b; };
      const restartBtn = el('button', 'nx-mini', '↻'); restartBtn.type = 'button';
      restartBtn.title = t('Restart this agent (its chat history in the room stays)', 'Перезапустить агента (история в комнате сохранится)');
      restartBtn.addEventListener('click', () => { if (confirm(t('Restart {0}? It loses what it was doing in its terminal; the room history stays.', 'Перезапустить {0}? Незаконченная работа в его терминале прервётся, история комнаты останется.', a.label))) restartAgent(a.name, restartBtn); });
      const maxBtn = el('button', 'nx-mini nx-ico'); maxBtn.type = 'button'; maxBtn.innerHTML = I.max; maxBtn.title = t('Only this agent', 'Только этот агент');
      maxBtn.addEventListener('click', () => { this.solo = a.name; this.layout = this.layout === 'one' ? 'grid' : 'one'; store.set('split-layout', this.layout); $('#nx-view-agents .nx-seg')?.querySelectorAll('button').forEach((x, i) => x.classList.toggle('active', ['one', 'split', 'grid'][i] === this.layout)); this.render(); });
      tools.append(keyBtn('Esc', 'Escape', t('Send Escape', 'Отправить Escape')), keyBtn('^C', 'C-c', t('Interrupt (Ctrl-C)', 'Прервать (Ctrl-C)')), keyBtn('↑', 'Up', 'Up'), keyBtn('↓', 'Down', 'Down'), keyBtn('⏎', 'Enter', 'Enter'), restartBtn, maxBtn);
      head.append(tools);
      const ask = el('div', 'nx-ask'); ask.hidden = true;
      const screen = el('pre', 'nx-screen'); screen.tabIndex = 0;
      const form = el('form', 'nx-term-input');
      const ta = el('textarea'); ta.rows = 1; ta.placeholder = t('Message {0}… (Enter to send)', 'Сообщение для {0}… (Enter — отправить)', a.label);
      const send = el('button', 'nx-send'); send.type = 'submit'; send.innerHTML = I.send; send.title = t('Send to its terminal', 'Отправить в терминал');
      form.append(ta, send);
      ta.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); } });
      ta.addEventListener('input', () => { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 140) + 'px'; });
      form.addEventListener('submit', async (e) => {
        e.preventDefault(); const text = ta.value; if (!text.trim()) return;
        send.disabled = true;
        try { await api(`/api/agent-term/${encodeURIComponent(a.name)}/input`, { method: 'POST', body: JSON.stringify({ text, submit: true }) }); ta.value = ''; ta.style.height = 'auto'; p.stick = true; setTimeout(() => this.poll(a.name), 400); }
        catch (err) { toast(err.message); } finally { send.disabled = false; }
      });
      root.append(head, ask, screen, form);
      const p = {
        root, screen, ask, stick: true, last: '',
        update: (info) => {
          const badge = $('.nx-badge', head); badge.className = 'nx-badge s-' + info.state; badge.textContent = stateText(info.state);
          root.dataset.state = info.state;
        },
      };
      screen.addEventListener('scroll', () => { p.stick = screen.scrollTop + screen.clientHeight >= screen.scrollHeight - 30; });
      return p;
    },
    async poll(name) {
      const p = this.panes.get(name); if (!p) return;
      try {
        const d = await api(`/api/agent-term/${encodeURIComponent(name)}?lines=300`);
        if (d.screen !== p.last) {
          p.last = d.screen; p.screen.innerHTML = ansiHtml(d.screen || '');
          if (p.stick) p.screen.scrollTop = p.screen.scrollHeight;
        }
        this.asking(name, p, d);
      } catch (err) {
        p.screen.textContent = t('Terminal not reachable: ', 'Терминал недоступен: ') + err.message;
      }
    },
    asking(name, p, d) {
      if (d.state === 'approval') {
        p.ask.hidden = false; p.ask.className = 'nx-ask approval';
        if (p.ask.dataset.q !== d.detail) {
          p.ask.dataset.q = d.detail; p.ask.replaceChildren();
          const q = el('div', 'nx-ask-q'); q.textContent = d.detail;
          const row = el('div', 'nx-ask-row');
          const yes = el('button', 'nx-btn primary', t('Allow', 'Разрешить')); yes.type = 'button';
          const no = el('button', 'nx-btn', t('Deny', 'Отклонить')); no.type = 'button';
          const answer = async (ans) => { yes.disabled = no.disabled = true; try { await api(`/api/agent-panes/${encodeURIComponent(name)}/answer`, { method: 'POST', body: JSON.stringify({ answer: ans }) }); } catch (err) { toast(err.message); } setTimeout(() => this.poll(name), 500); };
          yes.addEventListener('click', () => answer('allow')); no.addEventListener('click', () => answer('deny'));
          row.append(el('strong', '', t('Asks for permission', 'Просит разрешения')), yes, no); p.ask.append(row, q);
        }
      } else if (d.state === 'quota') {
        if (p.ask.dataset.q === 'quota:' + d.detail) return;
        p.ask.hidden = false; p.ask.className = 'nx-ask quota'; p.ask.dataset.q = 'quota:' + d.detail; p.ask.replaceChildren();
        const back = quotaBack(d.detail);
        const row = el('div', 'nx-ask-row');
        row.append(el('strong', '', back
          ? t('Subscription limit used up. It comes back {0}.', 'Лимит подписки исчерпан. Вернётся {0}.', back)
          : t('Subscription limit used up. It comes back on its own; you can use other agents meanwhile.', 'Лимит подписки исчерпан. Он вернётся сам, пока работайте с другими агентами.')));
        p.ask.append(row);
      } else if (d.state === 'signin') {
        if (p.ask.dataset.q === 'signin') return;
        p.ask.hidden = false; p.ask.className = 'nx-ask quota'; p.ask.dataset.q = 'signin'; p.ask.replaceChildren();
        const row = el('div', 'nx-ask-row');
        const go = el('button', 'nx-btn primary', t('Sign in again', 'Войти заново')); go.type = 'button';
        const re = el('button', 'nx-btn', t('Restart', 'Перезапустить')); re.type = 'button';
        go.addEventListener('click', async () => {
          go.disabled = true;
          try {
            const r = await api(`/api/council/signin/${encodeURIComponent(name)}`, { method: 'POST' });
            toast(r.how === 'browser' ? t('Finish signing in in the browser window that opened. The agent restarts by itself.', 'Завершите вход в открывшемся окне браузера. Агент перезапустится сам.')
              : r.how === 'terminal' ? t('Follow the sign-in steps in this terminal.', 'Следуйте шагам входа в этом терминале.')
              : t('Restarting — the agent will ask you to sign in.', 'Перезапускаю — агент попросит войти.'));
          } catch (err) { toast(err.message); }
          setTimeout(() => { go.disabled = false; }, 4000);
        });
        re.addEventListener('click', () => restartAgent(name, re));
        row.append(el('strong', '', t('Signed out of its account', 'Вышел из аккаунта')), go, re);
        p.ask.append(row);
      } else { p.ask.hidden = true; p.ask.dataset.q = ''; }
    },
    async key(name, key) { try { await api(`/api/agent-term/${encodeURIComponent(name)}/input`, { method: 'POST', body: JSON.stringify({ key }) }); setTimeout(() => this.poll(name), 300); } catch (err) { toast(err.message); } },
    tick() { if (document.hidden) return; this.render(); for (const n of this.panes.keys()) this.poll(n); },
    start() { this.stop(); this.tick(); this.timer = setInterval(() => this.tick(), 1600); },
    stop() { clearInterval(this.timer); this.timer = null; },
  };

  // "Resets in 117h4m0s" / "resets 5pm" → a date people read at a glance
  function quotaBack(detail) {
    const m = /resets? in\s*(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?/i.exec(detail || '');
    if (m && (m[1] || m[2] || m[3])) {
      const ms = ((+m[1] || 0) * 1440 + (+m[2] || 0) * 60 + (+m[3] || 0)) * 60000;
      const when = new Date(Date.now() + ms);
      try { return when.toLocaleString(window.NX_LANG || undefined, { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }); } catch (e) { return when.toLocaleString(); }
    }
    const at = /resets?(?: at)?\s+(\d{1,2}(?::\d{2})?\s*[ap]m)/i.exec(detail || '');
    return at ? at[1] : '';
  }
  async function restartAgent(name, btn) {
    if (btn) btn.disabled = true;
    try { await api(`/api/council/restart/${encodeURIComponent(name)}`, { method: 'POST' }); toast(t('Restarting {0}…', 'Перезапускаю {0}…', name)); } catch (err) { toast(err.message); }
    setTimeout(() => { if (btn) btn.disabled = false; }, 5000);
  }

  // ---------- Code mode: task → builder → reviewer → your accept, VS Code beside the chat ----------
  const CM = {
    tasks: [], folders: [], current: null, ideTimer: null, src: '',
    build() {
      const root = el('section', 'nx-view nx-cm'); root.id = 'nx-view-codemode'; root.hidden = true;
      const bar = el('div', 'nx-cm-bar'); bar.id = 'nx-cm-bar';
      const frame = el('div', 'nx-cm-frame'); frame.id = 'nx-cm-frame';
      root.append(bar, frame); return root;
    },
    owns(ch) { return this.tasks.some((x) => x.channel === ch); },
    async load() {
      try { const r = await api('/api/codemode'); this.tasks = r.tasks || []; this.folders = r.folders || []; } catch (e) { this.tasks = []; }
    },
    async open(forceNew) {
      await this.load();
      if (forceNew || !this.tasks.length) return this.dialog();
      if (!this.current || !this.tasks.some((x) => x.id === this.current)) this.current = this.tasks[0].id;
      setView('codemode');
    },
    async enter() {
      if (!this.tasks.length) await this.load();
      if (!this.tasks.length) { setView('chat'); return this.dialog(); }
      if (!this.current || !this.tasks.some((x) => x.id === this.current)) this.current = this.tasks[0].id;
      const tk = this.tasks.find((x) => x.id === this.current);
      if (typeof switchChannel === 'function' && window.activeChannel !== tk.channel) switchChannel(tk.channel);
      this.renderBar(tk); this.ide(tk);
    },
    renderBar(tk) {
      const bar = $('#nx-cm-bar'); if (!bar) return;
      bar.replaceChildren();
      const pick = el('select', 'nx-cm-pick'); pick.title = t('Code mode tasks', 'Задачи Code mode');
      for (const x of this.tasks) { const o = el('option', '', `${x.status === 'accepted' ? '✓ ' : ''}${x.task.slice(0, 60)}`); o.value = x.id; pick.append(o); }
      pick.value = tk.id;
      pick.addEventListener('change', () => { this.current = pick.value; this.src = ''; this.enter(); });
      const meta = el('small', 'nx-cm-meta', `${tk.folder}/ · ${tk.builder}${tk.reviewer ? ' → ' + tk.reviewer : ''}`);
      const changes = el('button', 'nx-btn primary', t('Review changes', 'Посмотреть изменения')); changes.type = 'button';
      changes.addEventListener('click', () => this.review(tk));
      const nu = el('button', 'nx-btn', t('New task', 'Новая задача')); nu.type = 'button'; nu.addEventListener('click', () => this.dialog());
      const box = el('div', 'nx-cm-title'); box.append(pick, meta);
      bar.append(box, changes, nu);
    },
    // VS Code on the task's own folder; until it is ready a note, the chat works anyway
    async ide(tk) {
      const frame = $('#nx-cm-frame'); if (!frame) return;
      clearInterval(this.ideTimer);
      const show = (st) => {
        if (st.phase === 'ready' && st.login) {
          const want = tk.folder;
          if (this.src !== want) {
            this.src = want;
            const f = el('iframe', 'nx-vscode-frame'); f.title = 'VS Code'; f.allow = 'clipboard-read; clipboard-write';
            f.src = st.login + '&sub=' + encodeURIComponent(want);
            frame.replaceChildren(f);
          }
          return true;
        }
        this.src = '';
        const pct = st.phase === 'download' && st.progress ? ` ${st.progress}%` : '';
        frame.replaceChildren(el('div', 'nx-cm-wait', st.phase === 'error'
          ? t('VS Code is unavailable: ', 'VS Code недоступен: ') + (st.error || '') + ' ' + t('The agents still work; open Code & files to see the folder.', 'Агенты работают и так; папку видно в «Код и файлы».')
          : t('VS Code is getting ready…', 'VS Code готовится…') + pct));
        return st.phase === 'error';
      };
      ideTheme();
      let st; try { st = await api('/api/ide/start', { method: 'POST' }); } catch (e) { st = { phase: 'error', error: e.message }; }
      if (!show(st)) this.ideTimer = setInterval(async () => {
        if (view !== 'codemode') return clearInterval(this.ideTimer);
        const s2 = await api('/api/ide').catch(() => null); if (s2 && show(s2)) clearInterval(this.ideTimer);
      }, 1500);
    },
    dialog() {
      // only agents that can work right now (not offline, signed out or out of quota)
      const ready = (a) => ['online', 'working', 'approval'].includes(a.state) && !a.name.startsWith('squad-');
      const coders = agents().filter((a) => ready(a) && !/chat$/.test(a.name));
      const all = agents().filter(ready);
      if (!coders.length) { toast(t('No coding agent is online. Connect one first.', 'Ни один агент-кодер не в сети. Сначала подключите его.')); setView('connect'); return; }
      dialog(t('Code mode', 'Code mode'), [
        { name: 'task', label: t('What should be built or fixed?', 'Что нужно сделать или исправить?'), type: 'textarea', required: true,
          placeholder: t('e.g. A script that renames photos by the date they were taken, with tests', 'например: скрипт, который переименовывает фото по дате съёмки, с тестами') },
        { name: 'builder', label: t('Who writes the code', 'Кто пишет код'), type: 'select', options: coders.map((a) => [a.name, `${a.label} · ${stateText(a.state)}`]) },
        { name: 'reviewer', label: t('Who reviews it', 'Кто проверяет'), type: 'select', options: [...all.map((a) => [a.name, `${a.label} · ${stateText(a.state)}`]), ['', t('Nobody — I review myself', 'Никто — проверю сам')]] },
        { name: 'folder', label: t('Folder in your workspace (empty = a new folder named after the task)', 'Папка в рабочей папке (пусто — новая, по названию задачи)'), placeholder: this.folders.slice(0, 4).join(', ') },
      ], async (v) => {
        const tk = await api('/api/codemode', { method: 'POST', body: JSON.stringify(v) });
        await this.load(); this.current = tk.id; this.src = '';
        setView('codemode'); Projects.load();
        toast(t('{0} got the task.', '{0} получил задачу.', tk.builder));
      }, t('Start', 'Начать'));
      // a reviewer different from the builder by default
      setTimeout(() => {
        const d = $('dialog.nx-dialog:last-of-type'); if (!d) return;
        const b = $('[name=builder]', d), r = $('[name=reviewer]', d);
        const pickReviewer = () => { if (r.value === b.value) r.value = [...r.options].map((o) => o.value).find((x) => x && x !== b.value) || ''; };
        b.addEventListener('change', pickReviewer); pickReviewer();
      }, 0);
    },
    async review(tk) {
      let ch; try { ch = await api(`/api/codemode/${encodeURIComponent(tk.id)}/changes`); } catch (err) { return toast(err.message); }
      const d = el('dialog', 'nx-dialog nx-cm-review');
      const f = el('form'); f.method = 'dialog';
      f.append(el('h3', '', t('Changes since the start', 'Изменения с начала задачи')));
      f.append(el('p', 'nx-cmeta', ch.files.length ? t('{0} files changed in {1}/', 'Изменено файлов: {0} в {1}/', ch.files.length, tk.folder) : t('No changes yet.', 'Изменений пока нет.')));
      const pre = el('pre', 'nx-diff');
      for (const line of (ch.diff || '').split('\n')) {
        const cls = line.startsWith('+++') || line.startsWith('---') ? 'f' : line.startsWith('+') ? 'a' : line.startsWith('-') ? 'd' : line.startsWith('@@') ? 'h' : line.startsWith('diff ') ? 'f' : '';
        const s = el('span', cls, line + '\n'); pre.append(s);
      }
      if (ch.truncated) pre.append(el('span', 'h', '… ' + t('(shortened)', '(сокращено)')));
      if (ch.files.length) f.append(pre);
      const note = el('textarea'); note.rows = 2; note.placeholder = t('What should change? (for Send back)', 'Что поправить? (для «Доработать»)');
      if (tk.status !== 'accepted') f.append(note);
      const row = el('div', 'nx-actions');
      const close = el('button', 'nx-btn', t('Close', 'Закрыть')); close.type = 'button'; close.addEventListener('click', () => d.close());
      row.append(close);
      if (tk.status !== 'accepted') {
        const back = el('button', 'nx-btn', t('Send back', 'Доработать')); back.type = 'button';
        back.addEventListener('click', async () => { try { await api(`/api/codemode/${encodeURIComponent(tk.id)}/send-back`, { method: 'POST', body: JSON.stringify({ note: note.value }) }); d.close(); toast(t('Sent back to {0}.', 'Вернул {0} на доработку.', tk.builder)); } catch (err) { toast(err.message); } });
        const ok = el('button', 'nx-btn primary', t('Accept', 'Принять')); ok.type = 'button';
        ok.addEventListener('click', async () => { try { await api(`/api/codemode/${encodeURIComponent(tk.id)}/accept`, { method: 'POST' }); d.close(); await this.load(); this.enter(); Projects.load(); toast(t('Accepted and committed.', 'Принято и закоммичено.')); } catch (err) { toast(err.message); } });
        row.append(back, ok);
      }
      f.append(row); d.append(f);
      d.addEventListener('close', () => d.remove());
      document.body.append(d); d.showModal();
    },
  };

  // VS Code follows the skin: dark in Breach / Blackwall, light in Clean
  const ideTheme = () => api('/api/ide/theme', { method: 'POST', body: JSON.stringify({ dark: (document.documentElement.dataset.skin || 'clean') !== 'clean' }) }).catch(() => {});
  document.addEventListener('neonexus-skin', ideTheme);

  // ---------- Projects ----------
  const Projects = {
    list: [],
    build() {
      const root = el('section', 'nx-view nx-projects-view'); root.id = 'nx-view-projects'; root.hidden = true;
      const bar = el('div', 'nx-viewbar');
      bar.innerHTML = `<div class="nx-viewbar-title"><strong>${t('Projects', 'Проекты')}</strong><span>${t('Goals with done criteria. Agents tick them with evidence; you accept.', 'Цели и критерии готовности. Агенты отмечают с доказательствами, принимаете вы.')}</span></div>`;
      const add = el('button', 'nx-btn primary'); add.type = 'button'; add.innerHTML = I.plus + `<span>${t('New project', 'Новый проект')}</span>`;
      add.addEventListener('click', () => newProject());
      bar.append(add);
      const body = el('div', 'nx-projects'); body.id = 'nx-projects';
      root.append(bar, body);
      return root;
    },
    async load() {
      try { this.list = (await api('/api/projects')).projects || []; } catch (e) { this.list = []; }
      this.render(); Rail.render(); Side.renderProjects();
    },
    render() {
      const box = $('#nx-projects'); if (!box) return;
      box.replaceChildren();
      if (!this.list.length) { box.append(el('div', 'nx-empty', t('No projects yet. Create one, or ask an agent to project_create.', 'Проектов пока нет. Создайте или попросите агента (project_create).'))); return; }
      for (const p of this.list) box.append(this.card(p));
      if (this.focus) { $(`[data-project="${CSS.escape(this.focus)}"]`, box)?.scrollIntoView({ block: 'start' }); this.focus = null; }
    },
    card(p) {
      const done = p.criteria.filter((c) => c.done).length, total = p.criteria.length;
      const pct = total ? Math.round((done / total) * 100) : 0;
      const card = el('article', 'nx-card nx-project'); card.dataset.project = p.id; card.dataset.nxDropProject = p.id;
      const head = el('header', 'nx-project-head');
      head.innerHTML = `<div><h3>${esc(p.title)}</h3><small>#${esc(p.channel)} · ${t('lead', 'ведёт')} ${esc(p.lead || '—')}${p.mode ? ' · ' + esc(p.mode) : ''}</small></div><span class="nx-status st-${p.status}">${esc(statusText(p.status))}</span>`;
      const goal = el('p', 'nx-goal', p.goal);
      const team = el('div', 'nx-members');
      for (const m of [p.lead, ...(p.members || [])].filter((x, i, arr) => x && arr.indexOf(x) === i)) {
        const f = el('button', 'nx-face nx-face-btn'); f.type = 'button'; f.innerHTML = face(m);
        f.title = m === p.lead ? m : t('{0} — click to remove from the project', '{0} — нажмите, чтобы убрать из проекта', m);
        if (m !== p.lead) f.addEventListener('click', () => {
          if (confirm(t('Remove {0} from "{1}"?', 'Убрать {0} из «{1}»?', m, p.title))) this.patch(p, { remove_members: [m] });
        });
        team.append(f);
      }
      team.append(el('small', '', t('drag an agent here to add it', 'перетащите агента сюда, чтобы добавить')));
      const prog = el('div', 'nx-progress'); prog.innerHTML = `<div class="nx-progress-top"><span>${t('Progress', 'Прогресс')}</span><b>${done}/${total} · ${pct}%</b></div><div class="nx-bar"><i style="width:${pct}%"></i></div>`;
      const crit = el('ul', 'nx-criteria');
      for (const c of p.criteria) {
        const li = el('li', c.done ? 'done' : '');
        const box = el('input'); box.type = 'checkbox'; box.checked = c.done; box.disabled = p.status === 'done';
        box.title = t('Tick as the human (no evidence needed)', 'Отметить от себя (без доказательства)');
        box.addEventListener('change', async () => { try { await api(`/api/projects/${encodeURIComponent(p.id)}/criteria/${c.id}`, { method: 'POST', body: JSON.stringify({ done: box.checked }) }); this.load(); } catch (err) { toast(err.message); box.checked = !box.checked; } });
        const txt = el('div'); txt.append(el('span', '', c.text));
        if (c.done && c.evidence) txt.append(el('small', '', `${c.by}: ${c.evidence}`));
        const rm = el('button', 'nx-crit-rm', '×'); rm.type = 'button'; rm.title = t('Remove this criterion', 'Удалить этот критерий');
        rm.addEventListener('click', () => this.patch(p, { remove_criteria: [c.id] }));
        li.append(box, txt, rm); crit.append(li);
      }
      const actions = el('div', 'nx-actions');
      if (p.status === 'review') actions.append(this.action(p, 'done', t('Accept project', 'Принять проект'), true));
      if (p.status === 'done') actions.append(this.action(p, 'active', t('Reopen', 'Вернуть в работу')));
      if (p.status === 'active') actions.append(this.action(p, 'paused', t('Pause', 'Пауза')));
      if (p.status === 'paused') actions.append(this.action(p, 'active', t('Resume', 'Продолжить')));
      if (p.status === 'active' || p.status === 'paused') actions.append(this.action(p, 'done', t('Mark done', 'Завершить')));
      const edit = el('button', 'nx-btn', t('Edit', 'Изменить')); edit.type = 'button';
      edit.addEventListener('click', () => this.edit(p));
      const del = el('button', 'nx-btn nx-danger', t('Delete', 'Удалить')); del.type = 'button';
      del.addEventListener('click', async () => {
        if (!confirm(t('Delete the project "{0}"? Its criteria and journal will be gone. Files in the workspace stay.', 'Удалить проект «{0}»? Критерии и журнал пропадут. Файлы в рабочей папке останутся.', p.title))) return;
        try { await api(`/api/projects/${encodeURIComponent(p.id)}`, { method: 'DELETE' }); toast(t('Project deleted', 'Проект удалён')); this.load(); } catch (err) { toast(err.message); }
      });
      actions.append(edit, del);
      const open = el('button', 'nx-btn', t('Open channel', 'Открыть канал')); open.type = 'button';
      open.addEventListener('click', () => { if (typeof switchChannel === 'function') switchChannel(p.channel); setView('chat'); });
      actions.append(open);
      card.append(head, goal, team, prog, crit);
      if (p.journal && p.journal.length) {
        const j = el('details', 'nx-journal'); j.append(el('summary', '', t('Journal', 'Журнал')));
        for (const e of p.journal.slice(-8).reverse()) j.append(el('div', '', `${e.by}: ${e.text}`));
        card.append(j);
      }
      card.append(actions);
      return card;
    },
    async patch(p, body) {
      try { await api(`/api/projects/${encodeURIComponent(p.id)}`, { method: 'PATCH', body: JSON.stringify(body) }); this.load(); } catch (err) { toast(err.message); }
    },
    edit(p) {
      dialog(t('Edit project', 'Изменить проект'), [
        { name: 'title', label: t('Title', 'Название'), required: true, value: p.title },
        { name: 'goal', label: t('Goal — what must exist at the end', 'Цель — что должно получиться'), type: 'textarea', required: true, value: p.goal },
        { name: 'add', label: t('Add done criteria, one per line', 'Добавить критерии готовности, по одному в строке'), type: 'textarea' },
      ], async (v) => {
        await api(`/api/projects/${encodeURIComponent(p.id)}`, { method: 'PATCH', body: JSON.stringify({ title: v.title, goal: v.goal, add_criteria: (v.add || '').split('\n').map((s) => s.trim()).filter(Boolean) }) });
        this.load();
      }, t('Save', 'Сохранить'));
    },
    action(p, status, label, primary) {
      const b = el('button', 'nx-btn' + (primary ? ' primary' : ''), label); b.type = 'button';
      b.addEventListener('click', async () => { try { await api(`/api/projects/${encodeURIComponent(p.id)}`, { method: 'PATCH', body: JSON.stringify({ status }) }); this.load(); } catch (err) { toast(err.message); } });
      return b;
    },
  };
  const statusText = (s) => ({ active: t('Active', 'В работе'), paused: t('Paused', 'Пауза'), review: t('Review', 'На проверке'), done: t('Done', 'Принят') }[s] || s);


  // ---------- Connect AI ----------
  const Connect = {
    data: null,
    build() {
      const root = el('section', 'nx-view nx-connect-view'); root.id = 'nx-view-connect'; root.hidden = true;
      const bar = el('div', 'nx-viewbar');
      bar.innerHTML = `<div class="nx-viewbar-title"><strong>${t('Connect AI', 'Подключить нейросети')}</strong><span>${t('Subscriptions, API keys, local models and other apps — each becomes a member of the room.', 'Подписки, API-ключи, локальные модели и другие приложения — каждое становится участником комнаты.')}</span></div>`;
      const body = el('div', 'nx-connect'); body.id = 'nx-connect';
      root.append(bar, body); return root;
    },
    async load() {
      try { this.data = await api('/api/connect'); } catch (e) { this.data = null; toast(e.message); }
      this.render();
    },
    section(title, sub) {
      const sec = el('section', 'nx-csec');
      sec.innerHTML = `<header><h3>${title}</h3><p>${sub}</p></header>`;
      const grid = el('div', 'nx-cgrid'); sec.append(grid); return [sec, grid];
    },
    render() {
      const box = $('#nx-connect'); if (!box) return; box.replaceChildren();
      const d = this.data; if (!d) { box.append(el('div', 'nx-empty', t('Could not load.', 'Не удалось загрузить.'))); return; }

      // connected models first
      if (d.agents.length) {
        const [sec, grid] = this.section(t('Your connected models', 'Подключённые модели'), t('They answer in the room when you @mention them.', 'Отвечают в комнате, когда вы упоминаете их через @.'));
        for (const a of d.agents) {
          const c = el('article', 'nx-ccard');
          c.innerHTML = `<div class="nx-ctop"><span class="nx-cmark" style="background:${safeColor(a.color, '#888')}">${esc(a.label.slice(0, 2))}</span><div><strong>${esc(a.label)}</strong><small>@${esc(a.name)} · ${esc(a.model)}</small></div><span class="nx-status ${a.online ? 'st-done' : 'st-review'}">${a.online ? t('In the room', 'В комнате') : a.running ? t('Starting…', 'Запускается…') : t('Stopped', 'Остановлена')}</span></div><p class="nx-cmeta">${esc(a.base_url)}${a.has_key ? ' · ' + t('key saved', 'ключ сохранён') : ''}</p>`;
          const row = el('div', 'nx-actions');
          const test = el('button', 'nx-btn', t('Test', 'Проверить')); test.type = 'button';
          test.addEventListener('click', async () => { test.disabled = true; try { const r = await api('/api/connect/probe', { method: 'POST', body: JSON.stringify({ base_url: a.base_url, name: a.name }) }); toast(r.ok ? t('Reachable · {0} models', 'Доступна · моделей: {0}', r.models.length) : r.error); } catch (e) { toast(e.message); } test.disabled = false; });
          const rs = el('button', 'nx-btn', t('Restart', 'Перезапустить')); rs.type = 'button';
          rs.addEventListener('click', async () => { await api(`/api/connect/agents/${a.name}/restart`, { method: 'POST' }).catch((e) => toast(e.message)); setTimeout(() => this.load(), 2500); });
          const rm = el('button', 'nx-btn', t('Remove', 'Удалить')); rm.type = 'button';
          rm.addEventListener('click', async () => { if (!confirm(t('Remove {0} and its saved key?', 'Удалить {0} и сохранённый ключ?', a.label))) return; await api(`/api/connect/agents/${a.name}`, { method: 'DELETE' }).catch((e) => toast(e.message)); this.load(); });
          row.append(test, rs, rm); c.append(row); grid.append(c);
        }
        box.append(sec);
      }

      // subscriptions
      const [s1, g1] = this.section(t('Subscriptions (official CLIs)', 'Подписки (официальные CLI)'), t('Your paid plan, no API bills. Install, then sign in once in its own terminal.', 'Ваш тариф, без счетов за API. Установите и один раз войдите в его терминале.'));
      for (const c of d.clis) {
        const card = el('article', 'nx-ccard');
        const st = c.in_team ? ['st-done', t('In the team', 'В команде')] : c.installed ? ['st-active', t('Installed', 'Установлен')] : ['', t('Not installed', 'Не установлен')];
        card.innerHTML = `<div class="nx-ctop"><span class="nx-cmark nx-cvendor">${esc(c.vendor.slice(0, 2))}</span><div><strong>${esc(c.label)}</strong><small>${esc(c.vendor)} · ${esc(c.plan)}</small></div><span class="nx-status ${st[0]}">${st[1]}</span></div>`;
        const row = el('div', 'nx-actions');
        if (!c.installed && c.npm) {
          const b = el('button', 'nx-btn primary', c.install === 'running' ? t('Installing…', 'Устанавливается…') : t('Install', 'Установить')); b.type = 'button'; b.disabled = c.install === 'running' || !d.npm;
          b.title = d.npm ? `npm install -g ${c.npm}` : t('Needs Node.js (nodejs.org)', 'Нужен Node.js (nodejs.org)');
          b.addEventListener('click', () => this.install(c, b, card));
          row.append(b);
          if (!d.npm) card.append(el('p', 'nx-cmeta', t('Install Node.js first: nodejs.org', 'Сначала установите Node.js: nodejs.org')));
        } else if (!c.installed) {
          card.append(el('p', 'nx-cmeta', t('Install it with its own installer, then reload.', 'Установите его родным установщиком и обновите страницу.')));
        }
        if (c.in_team) {
          const name = c.command === 'agy' ? 'gemini' : c.id;
          const open = el('button', 'nx-btn', t('Open terminal / sign in', 'Терминал / вход')); open.type = 'button';
          open.addEventListener('click', () => Split.focus(name)); row.append(open);
        } else if (c.installed) {
          const add = el('button', 'nx-btn primary', t('Add to team', 'Добавить в команду')); add.type = 'button';
          add.addEventListener('click', async () => {
            add.disabled = true;
            try {
              const r = await api(`/api/connect/team/${encodeURIComponent(c.id)}`, { method: 'POST' });
              toast(t('{0} is joining the room — sign in once in its terminal if it asks.', '{0} входит в комнату — если попросит, войдите один раз в его терминале.', r.label));
              setTimeout(() => this.load(), 1500);
            } catch (err) { toast(err.message); add.disabled = false; }
          });
          row.append(add);
        }
        card.append(row); g1.append(card);
      }
      box.append(s1);

      // API
      const [s2, g2] = this.section(t('API key', 'По API-ключу'), t('Pay-per-use with the provider. The key stays on this computer and goes only to that provider.', 'Оплата по факту у провайдера. Ключ остаётся на этом компьютере и уходит только этому провайдеру.'));
      for (const p of d.providers) g2.append(this.tile(p, 'api'));
      box.append(s2);

      // Local
      const [s3, g3] = this.section(t('Local or your own server', 'Локально или на своём сервере'), t('Any OpenAI-compatible server: Ollama, LM Studio, llama.cpp, vLLM, or your GPU box.', 'Любой OpenAI-совместимый сервер: Ollama, LM Studio, llama.cpp, vLLM или ваш GPU-сервер.'));
      for (const p of d.local) g3.append(this.tile(p, 'local'));
      box.append(s3);

      // MCP
      const [s4, g4] = this.section(t('Other apps over MCP', 'Другие приложения по MCP'), t('Claude Desktop, Cursor, VS Code and others can join the room as a member.', 'Claude Desktop, Cursor, VS Code и другие могут войти в комнату как участник.'));
      const snippet = JSON.stringify({ mcpServers: { neonexus: d.mcp.bridge } }, null, 2);
      const mc = el('article', 'nx-ccard nx-cwide');
      mc.innerHTML = `<p class="nx-cmeta">${t('Add this to the app\'s MCP settings (change COUNCIL_SENDER to the name it should have in the room):', 'Добавьте это в MCP-настройки приложения (COUNCIL_SENDER — имя в комнате):')}</p><pre class="nx-code">${esc(snippet)}</pre>`;
      const cp = el('button', 'nx-btn'); cp.type = 'button'; cp.innerHTML = I.copy + `<span>${t('Copy', 'Скопировать')}</span>`;
      cp.addEventListener('click', () => { navigator.clipboard?.writeText(snippet).then(() => toast(t('Copied', 'Скопировано'))); });
      const row = el('div', 'nx-actions'); row.append(cp); mc.append(row); g4.append(mc);
      box.append(s4);
    },
    tile(p, kind) {
      const b = el('button', 'nx-tile'); b.type = 'button';
      b.innerHTML = `<span class="nx-cmark nx-cvendor">${esc(p.label.slice(0, 2))}</span><span><strong>${esc(p.label)}</strong><small>${esc(p.base_url || t('your URL', 'ваш адрес'))}</small></span>${I.plus}`;
      b.addEventListener('click', () => this.form(p, kind));
      return b;
    },
    async install(c, b, card) {
      if (!confirm(t('Install {0}?\n\nRuns: npm install -g {1}', 'Установить {0}?\n\nКоманда: npm install -g {1}', c.label, c.npm))) return;
      b.disabled = true; b.textContent = t('Installing…', 'Устанавливается…');
      try { await api(`/api/connect/install/${c.id}`, { method: 'POST' }); } catch (e) { toast(e.message); b.disabled = false; return; }
      const log = el('pre', 'nx-code nx-log'); card.append(log);
      const tick = setInterval(async () => {
        const s = await api(`/api/connect/install/${c.id}`).catch(() => ({}));
        log.textContent = (s.log || '').split('\n').slice(-8).join('\n'); log.scrollTop = log.scrollHeight;
        if (s.state && s.state !== 'running') { clearInterval(tick); toast(s.state === 'done' ? t('{0} installed', '{0} установлен', c.label) : t('Install failed — see the log', 'Установка не удалась — смотрите лог')); setTimeout(() => this.load(), 800); }
      }, 1500);
    },
    form(p, kind) {
      const d = el('dialog', 'nx-dialog');
      const f = el('form'); f.method = 'dialog';
      f.innerHTML = `<h3>${t('Connect', 'Подключить')} ${esc(p.label)}</h3>
        <label><span>${t('Server URL (OpenAI-compatible)', 'Адрес сервера (OpenAI-совместимый)')}</span><input name="base_url" required placeholder="https://…/v1" value="${esc(p.base_url || '')}"></label>
        <label><span>${kind === 'api' ? t('API key', 'API-ключ') : t('Key (if your server needs one)', 'Ключ (если сервер требует)')}</span><input name="key" type="password" autocomplete="off" ${kind === 'api' ? 'required' : ''} placeholder="${kind === 'api' ? 'sk-…' : t('optional', 'необязательно')}"></label>
        <div class="nx-actions nx-left"><button type="button" class="nx-btn" data-probe>${t('Check & load models', 'Проверить и загрузить модели')}</button><span class="nx-probe-msg"></span></div>
        <label><span>${t('Model', 'Модель')}</span><input name="model" list="nx-models" required placeholder="${t('pick after the check, or type', 'выберите после проверки или впишите')}"><datalist id="nx-models"></datalist></label>
        <div class="nx-two"><label><span>${t('Name in the room (@name)', 'Имя в комнате (@имя)')}</span><input name="name" required pattern="[a-z][a-z0-9-]{1,23}" value="${esc(p.id === 'custom' || p.id === 'remote' ? '' : p.id)}"></label>
        <label><span>${t('Display name', 'Подпись')}</span><input name="label" value="${esc(p.label)}"></label></div>
        <label><span>${t('Role / instructions (optional)', 'Роль и инструкции (необязательно)')}</span><textarea name="system_prompt" placeholder="${t('e.g. You review code and point out risks.', 'например: Ты ревьюер кода и указываешь на риски.')}"></textarea></label>
        <div class="nx-err"></div>`;
      const row = el('div', 'nx-actions');
      const cancel = el('button', 'nx-btn', t('Cancel', 'Отмена')); cancel.type = 'button'; cancel.addEventListener('click', () => d.close());
      const ok = el('button', 'nx-btn primary', t('Connect to the room', 'Подключить к комнате')); ok.type = 'submit';
      row.append(cancel, ok); f.append(row); d.append(f);
      const msg = $('.nx-probe-msg', f), err = $('.nx-err', f), list = $('#nx-models', f);
      const probeNow = async () => {
        const v = Object.fromEntries(new FormData(f)); msg.textContent = t('Checking…', 'Проверяю…');
        try {
          const r = await api('/api/connect/probe', { method: 'POST', body: JSON.stringify({ base_url: v.base_url, key: v.key }) });
          if (!r.ok) { msg.textContent = '✗ ' + r.error; msg.className = 'nx-probe-msg bad'; return; }
          list.replaceChildren(...r.models.map((m) => { const o = el('option'); o.value = m; return o; }));
          msg.textContent = '✓ ' + t('works · {0} models', 'работает · моделей: {0}', r.models.length); msg.className = 'nx-probe-msg good';
          if (!f.model.value && r.models.length) f.model.value = r.models[0];
        } catch (e) { msg.textContent = '✗ ' + e.message; msg.className = 'nx-probe-msg bad'; }
      };
      $('[data-probe]', f).addEventListener('click', probeNow);
      f.addEventListener('submit', async (e) => {
        e.preventDefault(); ok.disabled = true; err.textContent = '';
        const v = Object.fromEntries(new FormData(f));
        try {
          await api('/api/connect/agents', { method: 'POST', body: JSON.stringify({ ...v, kind, provider: p.id }) });
          d.close(); toast(t('{0} is joining the room — mention @{1}', '{0} входит в комнату — упомяните @{1}', v.label || v.name, v.name));
          setTimeout(() => this.load(), 2500);
        } catch (x) { err.textContent = x.message; } finally { ok.disabled = false; }
      });
      d.addEventListener('close', () => d.remove());
      document.body.append(d); d.showModal();
      if (kind === 'local' && p.base_url) probeNow();
    },
  };


  // ---------- Voice room: talk to the agents, one by one or as a group ----------
  const Voice = {
    open: false, mode: store.get('voice-mode', 'group'), handsFree: store.get('voice-free', false),
    picked: null, state: 'idle', rec: null, heard: '', lastId: 0, pending: [], queue: [], speaking: null,
    audio: null, raf: 0, level: 0, phase: 0, timer: null, waitSince: 0, root: null,
    // the language you speak, not the UI language: from the browser/system (ru → ru-RU)
    lang() {
      const langs = navigator.languages || [navigator.language || 'en-US'];
      const sys = langs.find((l) => /^ru/i.test(l)) || langs.find((l) => /^(en|uk|de|fr|es|it|pt|zh|ja|ko|tr|pl)/i.test(l)) || 'en-US';
      const def = /^ru/i.test(sys) ? 'ru-RU' : /^uk/i.test(sys) ? 'uk-UA' : sys.includes('-') ? sys : sys + '-' + sys.toUpperCase();
      return store.get('voice-lang2', def);
    },
    supported() { return !!(window.SpeechRecognition || window.webkitSpeechRecognition) && 'speechSynthesis' in window; },
    members() { return agents().filter((a) => a.state === 'online' || a.state === 'working'); },
    chosen() {
      const list = this.members();
      if (!this.picked) this.picked = list.filter((a) => /chat$/.test(a.name)).map((a) => a.name).slice(0, 3);
      if (!this.picked.length && list[0]) this.picked = [list[0].name];
      return list.filter((a) => this.picked.includes(a.name));
    },
    show() {
      if (this.root) { this.root.hidden = false; this.open = true; this.render(); this.loop(); return; }
      const r = el('div', 'nx-voice'); this.root = r; this.open = true;
      r.innerHTML = `<div class="nx-vtop"><div><strong>${t('Voice room', 'Голосовая комната')}</strong><span>#${esc(window.activeChannel || 'general')}</span></div>
        <div class="nx-seg nx-vmode"><button data-m="group" type="button">${t('Group', 'Вместе')}</button><button data-m="turns" type="button">${t('In turn', 'По очереди')}</button></div>
        <select class="nx-vlang" title="Language you speak"><option value="ru-RU">Русский</option><option value="en-US">English</option><option value="uk-UA">Українська</option><option value="de-DE">Deutsch</option><option value="es-ES">Español</option></select>
        <button class="nx-vclose" type="button" title="${t('Close', 'Закрыть')}">${I.x}</button></div>
        <div class="nx-vwho"></div>
        <div class="nx-vapps"><span>${t('Or talk in their own voice apps (opens beside the room, your own login):', 'Или говорите в их собственных голосовых режимах (окно рядом с комнатой, ваш вход):')}</span>
          <button type="button" data-app="https://chatgpt.com/">ChatGPT ↗</button><button type="button" data-app="https://claude.ai/new">Claude ↗</button><button type="button" data-app="https://gemini.google.com/app">Gemini ↗</button></div>
        <div class="nx-vstage"><canvas width="560" height="560"></canvas><div class="nx-vface"></div></div>
        <div class="nx-vstatus"></div><div class="nx-vlive"></div>
        <form class="nx-vdict"><textarea rows="2" placeholder=""></textarea><button type="submit" class="nx-send" title="Send">${I.send}</button></form>
        <div class="nx-vctrl"><label class="nx-vfree"><input type="checkbox"> ${t('Hands-free', 'Без рук')}</label>
          <button class="nx-vmic" type="button">${I.mic}</button>
          <button class="nx-vskip" type="button">${I.stop}<span>${t('Stop', 'Стоп')}</span></button></div>
        <div class="nx-vlog"></div>`;
      document.body.append(r);
      $('.nx-vclose', r).addEventListener('click', () => this.hide());
      // their voice modes are the best; open them as a side window (no automation of their sites)
      r.querySelectorAll('[data-app]').forEach((b) => b.addEventListener('click', () => {
        const w = Math.min(520, Math.round(screen.availWidth * 0.36)), h = screen.availHeight;
        const left = (screen.availLeft || 0) + screen.availWidth - w;
        const win = window.open(b.dataset.app, 'nx-voice-app', `popup=yes,width=${w},height=${h},left=${left},top=0`);
        if (!win) window.open(b.dataset.app, '_blank', 'noopener');
      }));
      r.querySelectorAll('.nx-vmode button').forEach((b) => b.addEventListener('click', () => { this.mode = b.dataset.m; store.set('voice-mode', this.mode); this.render(); }));
      const lang = $('.nx-vlang', r); if (![...lang.options].some((o) => o.value === this.lang())) { const o = el('option', '', this.lang()); o.value = this.lang(); lang.append(o); } lang.value = this.lang(); lang.addEventListener('change', () => store.set('voice-lang2', lang.value));
      const free = $('.nx-vfree input', r); free.checked = this.handsFree; free.addEventListener('change', () => { this.handsFree = free.checked; store.set('voice-free', this.handsFree); });
      $('.nx-vmic', r).addEventListener('click', () => (this.state === 'listening' ? this.finishListening() : this.listen()));
      $('.nx-vskip', r).addEventListener('click', () => this.stopAll());
      document.addEventListener('keydown', (e) => {
        if (!this.open) return;
        if (e.key === 'Escape') this.hide();
        if (e.code === 'Space' && !e.repeat && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || '')) { e.preventDefault(); this.state === 'listening' ? this.finishListening() : this.listen(); }
      });
      // System dictation (macOS: press Fn twice, Windows: Win+H) types live into this
      // field on the device; a short pause or Enter sends it to the agents.
      const mac = /Mac/i.test(navigator.platform || navigator.userAgent);
      const dict = $('.nx-vdict textarea', r);
      dict.placeholder = mac ? t('Press Fn twice and speak — macOS writes as you talk. Or type. Enter sends.', 'Нажмите Fn дважды и говорите — macOS пишет по ходу речи. Или печатайте. Enter — отправить.')
        : t('Press Win+H and speak, or type. Enter sends.', 'Нажмите Win+H и говорите, или печатайте. Enter — отправить.');
      const sendDict = () => { const text = dict.value.trim(); clearTimeout(this.dictTimer); if (!text) return; dict.value = ''; speechSynthesis.cancel(); this.queue = []; this.log('you', text); this.ask(text); };
      dict.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendDict(); } });
      dict.addEventListener('input', () => {
        clearTimeout(this.dictTimer);
        if (this.handsFree && dict.value.trim()) this.dictTimer = setTimeout(sendDict, 2200);  // hands-free: a pause sends
      });
      $('.nx-vdict', r).addEventListener('submit', (e) => { e.preventDefault(); sendDict(); });
      setTimeout(() => dict.focus(), 50);
      speechSynthesis.getVoices();
      this.render(); this.loop();
      if (!this.supported()) this.status(t('This browser has no speech recognition. Use Chrome, Edge or Safari.', 'В этом браузере нет распознавания речи. Откройте в Chrome, Edge или Safari.'));
      else this.status(t('Tap the mic or press Space and speak.', 'Нажмите микрофон или пробел и говорите.'));
    },
    hide() { this.stopAll(); this.open = false; if (this.root) this.root.hidden = true; cancelAnimationFrame(this.raf); this.micOff(); },
    status(text) { if (this.root) $('.nx-vstatus', this.root).textContent = text; },
    render() {
      if (!this.root) return;
      this.root.querySelectorAll('.nx-vmode button').forEach((b) => b.classList.toggle('active', b.dataset.m === this.mode));
      this.chosen();
      const who = $('.nx-vwho', this.root); who.replaceChildren();
      for (const a of this.members()) {
        const b = el('button', 'nx-chip' + (this.picked && this.picked.includes(a.name) ? ' on' : '')); b.type = 'button';
        b.innerHTML = `<span class="nx-face">${face(a.name)}</span><span>${esc(a.label)}</span>`;
        b.addEventListener('click', () => { const p = new Set(this.chosen().map((x) => x.name)); p.has(a.name) ? p.delete(a.name) : p.add(a.name); this.picked = [...p]; this.render(); });
        who.append(b);
      }
      if (!this.members().length) who.append(el('span', 'nx-muted', t('No agent is online to talk to.', 'Нет агентов в сети, с кем можно поговорить.')));
      const f = $('.nx-vface', this.root);
      f.innerHTML = this.speaking ? face(this.speaking) : '';
      this.root.dataset.state = this.state;
    },
    log(who, text) {
      const box = $('.nx-vlog', this.root); if (!box) return;
      const row = el('div', 'nx-vline');
      row.innerHTML = `<span class="nx-face">${who === 'you' ? '<b>U</b>' : face(who)}</span><p></p>`;
      $('p', row).textContent = text; box.prepend(row);
      while (box.children.length > 12) box.lastChild.remove();
    },
    // --- microphone level for the waves ---
    async micOn() {
      if (this.audio) return;
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const an = ctx.createAnalyser(); an.fftSize = 512; ctx.createMediaStreamSource(stream).connect(an);
        this.audio = { stream, ctx, an, buf: new Uint8Array(an.fftSize) };
      } catch (e) { /* level is decoration; recognition still works */ }
    },
    micOff() { if (!this.audio) return; this.audio.stream.getTracks().forEach((tr) => tr.stop()); this.audio.ctx.close(); this.audio = null; },
    // --- listening ---
    listen() {
      if (!this.supported()) return;
      if (!this.chosen().length) { this.status(t('Pick who to talk to above.', 'Выберите собеседников сверху.')); return; }
      speechSynthesis.cancel(); this.queue = []; this.speaking = null;
      const R = window.SpeechRecognition || window.webkitSpeechRecognition;
      const rec = new R(); this.rec = rec; this.heard = '';
      // Safari's continuous mode often never reports anything: there, one phrase per turn
      const safari = /^((?!chrome|android|crios|fxios|edg).)*safari/i.test(navigator.userAgent);
      rec.lang = this.lang(); rec.interimResults = true; rec.continuous = !safari;
      this.gotSpeech = false;
      clearTimeout(this.noSpeech); clearTimeout(this.maxTurn);
      this.noSpeech = setTimeout(() => {
        if (this.state !== 'listening' || this.gotSpeech) return;
        this.heard = ''; this.finishListening();
        this.status(t('No speech recognised. Allow the microphone for this site; in Safari also turn on Dictation (System Settings → Keyboard). Chrome works best.',
          'Речь не распознана. Разрешите микрофон для этого сайта; в Safari ещё включите Диктовку (Настройки → Клавиатура). Лучше всего работает Chrome.'));
      }, 7000);
      this.maxTurn = setTimeout(() => this.finishListening(), 30000);
      rec.onresult = (ev) => {
        this.gotSpeech = true;
        let fin = '', tmp = '';
        for (const res of ev.results) (res.isFinal ? (fin += res[0].transcript) : (tmp += res[0].transcript));
        this.heard = (fin + ' ' + tmp).trim();
        $('.nx-vlive', this.root).textContent = this.heard;
        clearTimeout(this.silence);
        this.silence = setTimeout(() => this.finishListening(), 1200);  // a pause ends the turn
      };
      rec.onerror = (ev) => { if (ev.error !== 'no-speech' && ev.error !== 'aborted') this.status(t('Mic error: ', 'Ошибка микрофона: ') + ev.error); };
      rec.onend = () => { if (this.state === 'listening') this.finishListening(); };
      try { rec.start(); } catch (e) { return; }
      this.state = 'listening'; this.micOn(); this.render();
      $('.nx-vlive', this.root).textContent = '…';
      this.status(safari ? t('Listening… (Safari shows the text when you pause; Chrome shows it live)', 'Слушаю… (Safari покажет текст после паузы; Chrome — сразу по ходу речи)') : t('Listening… pause to send', 'Слушаю… пауза — отправка'));
    },
    finishListening() {
      clearTimeout(this.silence); clearTimeout(this.noSpeech); clearTimeout(this.maxTurn);
      if (this.state !== 'listening') return;
      this.state = 'idle';
      try { this.rec && this.rec.stop(); } catch (e) {}
      this.rec = null; this.micOff();
      const text = this.heard.trim(); $('.nx-vlive', this.root).textContent = '';
      if (!text) { this.render(); if (!this.root.querySelector('.nx-vstatus').textContent.includes('Dictation') && !this.root.querySelector('.nx-vstatus').textContent.includes('Диктовку')) this.status(t('Nothing heard. Tap the mic to try again.', 'Ничего не услышал. Нажмите микрофон ещё раз.')); return; }
      this.log('you', text); this.ask(text);
    },
    // --- asking the agents through the normal room ---
    hint() { return this.lang().startsWith('ru')
      ? '(голосовой режим: ответь 1–3 короткими фразами для озвучки, без кода и списков)'
      : '(voice mode: answer in 1-3 short spoken sentences, no code or lists)'; },
    send(text) { return sendAs(text); },
    async ask(text) {
      const who = this.chosen(); if (!who.length) return;
      await this.syncId();
      if (this.mode === 'group') {
        this.pending = who.map((a) => a.name);
        this.send(who.map((a) => '@' + a.name).join(' ') + ' ' + text + ' ' + this.hint());
      } else {
        this.turns = who.map((a) => a.name).slice(1); this.topic = text;
        this.pending = [who[0].name];
        this.send(`@${who[0].name} ${text} ${this.hint()}`);
      }
      this.state = 'thinking'; this.waitSince = Date.now(); this.render();
      this.status(t('Thinking: ', 'Думают: ') + this.pending.map((n) => (agents().find((a) => a.name === n) || {}).label || n).join(', '));
      this.poll();
    },
    async syncId() {
      try {
        const ch = encodeURIComponent(window.activeChannel || 'general');
        const msgs = await api(`/api/messages?channel=${ch}&limit=1`);
        const last = Array.isArray(msgs) ? msgs[msgs.length - 1] : null; this.lastId = last ? last.id : this.lastId;
      } catch (e) {}
    },
    poll() {
      clearInterval(this.timer);
      this.timer = setInterval(async () => {
        if (!this.open) return clearInterval(this.timer);
        try {
          const ch = encodeURIComponent(window.activeChannel || 'general');
          const msgs = await api(`/api/messages?channel=${ch}&since_id=${this.lastId}`);
          for (const m of msgs || []) {
            this.lastId = Math.max(this.lastId, m.id);
            if (!m.sender || ['join', 'leave', 'summary', 'system'].includes(m.type)) continue;
            if (!this.pending.includes(m.sender)) continue;
            this.pending = this.pending.filter((n) => n !== m.sender);
            this.queue.push(m); this.log(m.sender, this.speakable(m.text));
          }
        } catch (e) {}
        if (!this.speaking && this.queue.length) this.speakNext();
        if (this.pending.length && Date.now() - this.waitSince > 150000) {
          this.status(t('No answer from ', 'Нет ответа от ') + this.pending.join(', ')); this.pending = [];
        }
        if (!this.pending.length && !this.queue.length && !this.speaking) {
          clearInterval(this.timer);
          if (this.state !== 'listening') { this.state = 'idle'; this.render(); this.status(t('Your turn.', 'Ваша очередь.')); const d = $('.nx-vdict textarea', this.root); if (d) d.focus(); if (this.handsFree && this.supported() && !d) setTimeout(() => this.open && this.listen(), 500); }
        }
      }, 1000);
    },
    speakable(text) {
      return String(text || '').replace(/```[\s\S]*?```/g, ru() ? ' (код в чате) ' : ' (code in the chat) ')
        .replace(/`([^`]+)`/g, '$1').replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/https?:\/\/\S+/g, '')
        .replace(/[*_#>|~]+/g, '').replace(/@[\w-]+/g, '').replace(/\s+/g, ' ').trim();
    },
    voiceFor(name) {
      const lang = this.lang().slice(0, 2);
      const voices = speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith(lang));
      if (!voices.length) return null;
      const order = this.chosen().map((a) => a.name); const i = Math.max(0, order.indexOf(name));
      return voices[i % voices.length];
    },
    speakNext() {
      const m = this.queue.shift(); if (!m) return;
      let text = this.speakable(m.text);
      if (text.length > 700) text = text.slice(0, 700).replace(/\s\S*$/, '') + (ru() ? '… остальное в чате.' : '… the rest is in the chat.');
      const u = new SpeechSynthesisUtterance(text);
      u.lang = this.lang(); const v = this.voiceFor(m.sender); if (v) u.voice = v;
      u.rate = 1.04;
      u.onboundary = () => { this.level = 1; };
      u.onend = u.onerror = () => {
        this.speaking = null; this.render();
        if (this.mode === 'turns' && this.turns && this.turns.length && !this.queue.length) {
          const next = this.turns.shift(); this.pending = [next]; this.waitSince = Date.now();
          this.send(`@${next} ${ru() ? 'твоя очередь: ответь на обсуждение выше, тема —' : 'your turn: respond to the discussion above, topic —'} «${this.topic}» ${this.hint()}`);
          this.state = 'thinking'; this.render(); this.status(t('Thinking: ', 'Думает: ') + next); this.poll();
        } else if (this.queue.length) this.speakNext();
      };
      this.speaking = m.sender; this.state = 'speaking'; this.render();
      this.status((agents().find((a) => a.name === m.sender) || {}).label || m.sender);
      speechSynthesis.speak(u);
    },
    stopAll() {
      clearTimeout(this.silence); clearTimeout(this.noSpeech); clearTimeout(this.maxTurn); clearInterval(this.timer);
      try { this.rec && this.rec.abort(); } catch (e) {}
      this.rec = null; speechSynthesis.cancel(); this.queue = []; this.pending = []; this.turns = []; this.speaking = null;
      this.state = 'idle'; this.micOff(); this.render(); this.status(t('Stopped.', 'Остановлено.'));
    },
    // --- the orb ---
    loop() {
      cancelAnimationFrame(this.raf);
      const cv = $('canvas', this.root); if (!cv) return; const g = cv.getContext('2d');
      const draw = () => {
        if (!this.open) return;
        const W = cv.width, H = cv.height, cx = W / 2, cy = H / 2;
        let lvl = 0;
        if (this.audio) { this.audio.an.getByteTimeDomainData(this.audio.buf); let sum = 0; for (const b of this.audio.buf) sum += ((b - 128) / 128) ** 2; lvl = Math.min(1, Math.sqrt(sum / this.audio.buf.length) * 6); }
        if (this.state === 'speaking') { this.level = Math.max(this.level * 0.94, 0.35 + 0.25 * Math.sin(this.phase * 3)); lvl = this.level; }
        if (this.state === 'thinking') lvl = 0.18 + 0.12 * Math.sin(this.phase * 2);
        this.phase += 0.03;
        const css = getComputedStyle(document.documentElement);
        const accent = (css.getPropertyValue('--accent') || '#15305c').trim(), info = (css.getPropertyValue('--info') || '#1f437e').trim();
        g.clearRect(0, 0, W, H);
        const base = 150 + lvl * 40;
        for (let k = 0; k < 4; k++) {
          g.beginPath();
          for (let i = 0; i <= 120; i++) {
            const a = (i / 120) * Math.PI * 2;
            const wob = Math.sin(a * (3 + k) + this.phase * (1.4 + k * 0.5)) * (6 + lvl * 34) * (1 - k * 0.18);
            const r = base + k * 12 + wob;
            const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
            i ? g.lineTo(x, y) : g.moveTo(x, y);
          }
          g.closePath(); g.globalAlpha = 0.5 - k * 0.1; g.lineWidth = 3 - k * 0.5;
          g.strokeStyle = k % 2 ? info : accent; g.stroke();
        }
        g.globalAlpha = 1;
        const grd = g.createRadialGradient(cx, cy, 10, cx, cy, base);
        grd.addColorStop(0, this.state === 'listening' ? 'rgba(34,165,90,.28)' : 'rgba(31,67,126,.18)'); grd.addColorStop(1, 'rgba(31,67,126,0)');
        g.fillStyle = grd; g.beginPath(); g.arc(cx, cy, base, 0, Math.PI * 2); g.fill();
        this.raf = requestAnimationFrame(draw);
      };
      draw();
    },
  };


  // ---------- drag an agent onto a project or channel to bring it in ----------
  function draggableAgent(node, name) {
    node.draggable = true; node.dataset.nxAgent = name;
    node.addEventListener('dragstart', (e) => { e.dataTransfer.setData('text/nx-agent', name); e.dataTransfer.effectAllowed = 'copy'; document.body.classList.add('nx-dragging'); });
    node.addEventListener('dragend', () => document.body.classList.remove('nx-dragging'));
  }
  function dropTarget(e) {
    const proj = e.target.closest && e.target.closest('[data-nx-drop-project]');
    if (proj) return { project: proj.dataset.nxDropProject, node: proj };
    const row = e.target.closest && e.target.closest('#channel-sidebar-list .channel-sidebar-row');
    if (row) { const name = (row.textContent || '').replace(/^\s*#\s*/, '').trim().split(/\s/)[0]; if (name) return { channel: name, node: row }; }
    return null;
  }
  let hot = null;
  document.addEventListener('dragover', (e) => {
    if (!e.dataTransfer || ![...e.dataTransfer.types].includes('text/nx-agent')) return;
    const tg = dropTarget(e); if (hot && (!tg || tg.node !== hot)) { hot.classList.remove('nx-drop-hot'); hot = null; }
    if (tg) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; hot = tg.node; hot.classList.add('nx-drop-hot'); }
  });
  document.addEventListener('drop', async (e) => {
    const name = e.dataTransfer && e.dataTransfer.getData('text/nx-agent'); if (!name) return;
    const tg = dropTarget(e); if (hot) { hot.classList.remove('nx-drop-hot'); hot = null; }
    document.body.classList.remove('nx-dragging');
    if (!tg) return; e.preventDefault();
    const label = (agents().find((a) => a.name === name) || {}).label || name;
    if (tg.project) {
      const p = Projects.list.find((x) => x.id === tg.project); if (!p) return;
      try { await api(`/api/projects/${encodeURIComponent(p.id)}`, { method: 'PATCH', body: JSON.stringify({ add_members: [name] }) }); } catch (err) { if (!/nothing to change/.test(err.message)) { toast(err.message); return; } }
      inviteTo(p.channel, name, ru()
        ? `ты в команде проекта «${p.title}». Цель: ${p.goal} Критерии: ${p.criteria.map((c, i) => `${i + 1}) ${c.text}`).join('; ') || 'пока нет'}. Прочитай project_status("${p.id}") и разговор выше, скажи коротко, что возьмёшь на себя.`
        : `you're on the team for project "${p.title}". Goal: ${p.goal} Done criteria: ${p.criteria.map((c, i) => `${i + 1}) ${c.text}`).join('; ') || 'none yet'}. Read project_status("${p.id}") and the conversation above, then say briefly what you'll take on.`);
      toast(t('{0} joined {1}', '{0} в проекте «{1}»', label, p.title)); Projects.load();
    } else if (tg.channel) {
      inviteTo(tg.channel, name, ru()
        ? `присоединяйся к нам в #${tg.channel}: прочитай разговор выше и скажи коротко, чем поможешь.`
        : `join us in #${tg.channel}: read the conversation above and say briefly how you can help.`);
      toast(t('{0} invited to #{1}', '{0} приглашён в #{1}', label, tg.channel));
    }
  });
  function inviteTo(channel, name, text) {
    if (typeof switchChannel === 'function' && window.activeChannel !== channel) switchChannel(channel);
    setView('chat');
    setTimeout(() => sendAs(`@${name} ${text}`), 400);
  }


  // ---------- Code: full VS Code (open-source code-server) inside the tab; built-in Monaco until it is up ----------
  // Nothing to download or accept: the editor, file tree and terminal run inside the room.
  const IDE = {
    open: new Set(['']), obs: null,
    timer: null, frame: null, src: '',
    async load() {
      this.tree();
      const files = $('#code-files');
      if (files && !this.obs) {
        this.obs = new MutationObserver(() => this.tree());
        this.obs.observe(files, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
      }
      // full VS Code (open-source code-server) comes up in the background; until then the
      // built-in editor works and the toolbar shows a quiet "preparing" note
      ideTheme();
      let st; try { st = await api('/api/ide/start', { method: 'POST' }); } catch (e) { st = { phase: 'error', error: e.message }; }
      this.show(st);
      clearInterval(this.timer);
      if (!['ready', 'error'].includes(st.phase)) this.timer = setInterval(async () => {
        if (view !== 'code') return;
        const s2 = await api('/api/ide').catch(() => null); if (!s2) return;
        this.show(s2); if (['ready', 'error'].includes(s2.phase)) { clearInterval(this.timer); this.timer = null; }
      }, 1500);
    },
    show(st) {
      const center = $('#center-workspace'); const footer = center && $('#center-workspace > footer');
      if (!this.frame && center) {
        this.frame = el('section', 'nx-vscode');
        center.insertBefore(this.frame, footer || null);
      }
      const bar = $('#code-workspace .code-toolbar');
      let note = bar && $('.nx-code-note', bar);
      if (bar && !note) { note = el('span', 'nx-code-note'); bar.append(note); }
      if (st.phase === 'ready' && st.login) {
        if (!this.src) {  // log in once; VS Code keeps its own session cookie after that
          this.src = st.login;
          const f = el('iframe', 'nx-vscode-frame'); f.src = st.login; f.title = 'VS Code';
          f.allow = 'clipboard-read; clipboard-write';
          this.frame.replaceChildren(f);
        }
        document.body.classList.add('nx-vscode-on');
        if (note) note.textContent = '';
        return;
      }
      document.body.classList.remove('nx-vscode-on');
      if (!note) return;
      const pct = st.phase === 'download' && st.progress ? ` ${st.progress}%` : '';
      note.textContent = st.phase === 'error'
        ? t('Full VS Code is unavailable: ', 'Полный VS Code недоступен: ') + (st.error || '')
        : t('Full VS Code is getting ready…', 'Полный VS Code готовится…') + pct;
      note.classList.toggle('err', st.phase === 'error');
    },
    // the bundle lists flat paths; show them as a folder tree like VS Code's explorer
    tree() {
      const files = $('#code-files'); if (!files) return;
      const btns = [...files.querySelectorAll(':scope > button[title]')];
      const sig = btns.map((x) => x.title + (x.classList.contains('selected') ? '*' : '')).join('|') + [...this.open].join(',');
      if (this.sig === sig && $('.nx-tree', files)) return;
      this.sig = sig;
      this.obs?.disconnect();
      $('.nx-tree', files)?.remove();
      btns.forEach((x) => { x.hidden = true; });
      const root = { dirs: new Map(), files: [] };
      for (const btn of btns) {
        const parts = btn.title.split('/'); let n = root;
        for (const d of parts.slice(0, -1)) { if (!n.dirs.has(d)) n.dirs.set(d, { dirs: new Map(), files: [] }); n = n.dirs.get(d); }
        n.files.push([parts[parts.length - 1], btn]);
      }
      const ul = el('div', 'nx-tree');
      const walk = (n, path, depth) => {
        for (const [name, sub] of [...n.dirs].sort((x, y) => x[0].localeCompare(y[0]))) {
          const p = path ? path + '/' + name : name; const isOpen = this.open.has(p);
          const row = el('button', 'nx-tree-row nx-tree-dir' + (isOpen ? ' open' : ''), ''); row.type = 'button';
          row.style.paddingLeft = (8 + depth * 14) + 'px';
          row.innerHTML = `<span class="nx-tree-chev">›</span><span>${esc(name)}</span>`;
          row.addEventListener('click', () => { isOpen ? this.open.delete(p) : this.open.add(p); this.tree(); });
          ul.append(row);
          if (isOpen) walk(sub, p, depth + 1);
        }
        for (const [name, btn] of n.files.sort((x, y) => x[0].localeCompare(y[0]))) {
          const row = el('button', 'nx-tree-row nx-tree-file' + (btn.classList.contains('selected') ? ' selected' : ''), ''); row.type = 'button';
          row.style.paddingLeft = (22 + depth * 14) + 'px'; row.title = btn.title;
          const ext = (name.split('.').pop() || '').toLowerCase();
          row.innerHTML = `<span class="nx-tree-ext" data-ext="${esc(ext)}">${esc(ext.slice(0, 3) || '·')}</span><span>${esc(name)}</span>`;
          row.addEventListener('click', () => btn.click());
          ul.append(row);
        }
      };
      walk(root, '', 0);
      if (!btns.length) ul.append(el('p', 'nx-tree-empty', t('No files yet. Agents\' work will appear here.', 'Файлов пока нет. Здесь появится работа агентов.')));
      files.prepend(ul);
      this.obs?.observe(files, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
    },
  };

  // ---------- dialogs ----------
  function dialog(title, fields, onSubmit, okLabel) {
    const d = el('dialog', 'nx-dialog');
    const f = el('form'); f.method = 'dialog';
    f.append(el('h3', '', title));
    for (const fl of fields) {
      const lab = el('label'); lab.append(el('span', '', fl.label));
      const input = fl.type === 'textarea' ? el('textarea') : fl.type === 'select' ? el('select') : el('input');
      input.name = fl.name; if (fl.placeholder) input.placeholder = fl.placeholder; if (fl.required) input.required = true;
      if (fl.type === 'select') for (const [v, l] of fl.options) { const o = el('option', '', l); o.value = v; input.append(o); }
      if (fl.value) input.value = fl.value;
      lab.append(input); f.append(lab);
    }
    const err = el('div', 'nx-err');
    const row = el('div', 'nx-actions');
    const cancel = el('button', 'nx-btn', t('Cancel', 'Отмена')); cancel.type = 'button'; cancel.addEventListener('click', () => d.close());
    const ok = el('button', 'nx-btn primary', okLabel || t('Create', 'Создать')); ok.type = 'submit';
    row.append(cancel, ok); f.append(err, row); d.append(f);
    f.addEventListener('submit', async (e) => {
      e.preventDefault(); ok.disabled = true; err.textContent = '';
      try { await onSubmit(Object.fromEntries(new FormData(f))); d.close(); } catch (x) { err.textContent = x.message; } finally { ok.disabled = false; }
    });
    d.addEventListener('close', () => d.remove());
    document.body.append(d); d.showModal(); $('input,textarea', f)?.focus();
  }
  function newProject() {
    const leads = agents().filter((a) => !/chat$/.test(a.name) && !a.name.startsWith('squad-'));
    dialog(t('New project', 'Новый проект'), [
      { name: 'title', label: t('Title', 'Название'), required: true },
      { name: 'goal', label: t('Goal — what must exist at the end', 'Цель — что должно получиться'), type: 'textarea', required: true },
      { name: 'criteria', label: t('Done criteria, one per line', 'Критерии готовности, по одному в строке'), type: 'textarea', placeholder: t('tests pass\nscreenshot of the running app', 'тесты проходят\nскриншот работающего приложения') },
      { name: 'lead', label: t('Lead agent', 'Ведущий агент'), type: 'select', options: [['', '—'], ...leads.map((a) => [a.name, a.label])] },
      { name: 'mode', label: t('Mode', 'Режим'), type: 'select', options: [['', '—'], ['dev', 'dev'], ['game', 'game'], ['ops', 'ops'], ['media', 'media'], ['research', 'research']] },
    ], async (v) => {
      const p = await api('/api/projects', { method: 'POST', body: JSON.stringify({ title: v.title, goal: v.goal, criteria: (v.criteria || '').split('\n').map((s) => s.trim()).filter(Boolean), lead: v.lead, mode: v.mode, channel: window.activeChannel || 'general' }) });
      Projects.focus = p.id; setView('projects');
    });
  }
  function newTask() {
    dialog(t('New task', 'Новая задача'), [
      { name: 'title', label: t('Task', 'Задача'), required: true },
      { name: 'body', label: t('Details (optional)', 'Подробности (необязательно)'), type: 'textarea' },
    ], async (v) => {
      await api('/api/jobs', { method: 'POST', body: JSON.stringify({ title: v.title, body: v.body || '', channel: window.activeChannel || 'general', created_by: 'user' }) });
      Rail.loadJobs();
    });
  }
  let toastTimer;
  function toast(msg) {
    let n = $('#nx-toast'); if (!n) { n = el('div'); n.id = 'nx-toast'; document.body.append(n); }
    n.textContent = msg; n.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => n.classList.remove('show'), 3600);
  }

  // ---------- header context ----------
  function buildHeader() {
    const left = $('.header-left'); if (!left || $('#nx-crumb')) return;
    const crumb = el('span', 'nx-crumb'); crumb.id = 'nx-crumb'; left.append(crumb);
    // a top nav as well as the side nav: keep both
    const nav = el('nav', 'nx-nav'); nav.id = 'nx-nav'; nav.setAttribute('aria-label', t('Main', 'Главное меню'));
    for (const [k, ic, label] of [
      ['chat', I.team, t('Team', 'Команда')], ['projects', I.folder, t('Projects', 'Проекты')],
      ['tasks', I.task, t('Tasks', 'Задачи')], ['agents', I.agents, t('Agents', 'Агенты')],
      ['code', I.code, t('Code', 'Код')], ['codemode', I.split, t('Code mode', 'Code mode')], ['rules', I.book, t('Rules', 'Правила')],
      ['connect', I.plug, t('Connect AI', 'Подключить ИИ')],
    ]) nav.append(navButton(k, ic, label, 'nx-pill' + (k === 'connect' ? ' nx-pill-cta' : '')));
    left.after(nav);
  }
  function navButton(k, ic, label, cls) {
    const b = el('button', cls); b.type = 'button'; b.innerHTML = ic + `<span>${label}</span>`;
    if (['chat', 'projects', 'agents', 'code', 'connect'].includes(k)) { b.dataset.nxView = k; b.addEventListener('click', () => setView(k)); }
    else if (k === 'codemode') { b.dataset.nxView = k; b.addEventListener('click', () => CM.open()); }
    else if (k === 'tasks') { b.dataset.nxRail = 'jobs'; b.addEventListener('click', () => Rail.toggle('jobs')); }
    else if (k === 'rules') { b.dataset.nxRail = 'rules'; b.addEventListener('click', () => Rail.toggle('rules')); }
    if (k === 'tasks') { const n = el('em', 'nx-count'); n.dataset.nxJobs = '1'; b.append(n); }
    return b;
  }

  // ---------- left side nav (CLEAN) ----------
  const Side = {
    build() {
      const side = $('#channel-sidebar'); if (!side || $('#nx-sidenav')) return;
      const nav = el('nav', 'nx-sidenav'); nav.id = 'nx-sidenav';
      for (const [k, ic, label] of [
        ['chat', I.team, t('Team', 'Команда')], ['projects', I.folder, t('Projects', 'Проекты')],
        ['tasks', I.task, t('Tasks', 'Задачи')], ['agents', I.agents, t('Agents', 'Агенты')],
        ['code', I.code, t('Code & files', 'Код и файлы')], ['codemode', I.split, t('Code mode', 'Code mode')],
        ['rules', I.book, t('Rules & decisions', 'Правила и решения')],
        ['connect', I.plug, t('Connect AI', 'Подключить ИИ')],
      ]) nav.append(navButton(k, ic, label, 'nx-side-item'));
      side.prepend(nav);
      const proj = el('section', 'nx-side-projects'); proj.id = 'nx-side-projects';
      side.append(proj);
    },
    renderProjects() {
      const box = $('#nx-side-projects'); if (!box) return;
      box.replaceChildren(el('h4', '', t('Projects', 'Проекты')));
      for (const p of Projects.list.filter((x) => x.status !== 'done').slice(0, 8)) {
        const b = el('button', 'nx-side-project'); b.type = 'button'; b.dataset.nxDropProject = p.id;
        b.innerHTML = I.folder + `<span>${esc(p.title)}</span>` + (p.status === 'review' ? '<i class="nx-dot s-approval"></i>' : '');
        b.addEventListener('click', () => { Projects.focus = p.id; setView('projects'); });
        box.append(b);
      }
      const add = el('button', 'nx-side-add'); add.type = 'button'; add.innerHTML = I.plus + `<span>${t('New project', 'Новый проект')}</span>`;
      add.addEventListener('click', newProject); box.append(add);
    },
  };

  // ---------- hero + agent chips + channel tabs ----------
  function buildCenter() {
    const center = $('#center-workspace'); if (!center || $('#nx-top')) return;
    const top = el('div', 'nx-top'); top.id = 'nx-top';
    if (!store.get('hero-closed', false)) {
      const hero = el('section', 'nx-hero'); hero.id = 'nx-hero';
      hero.innerHTML = `<div class="nx-hero-text"><h2>${t('NEONEXUS team', 'Команда NEONEXUS')}</h2><p>${t('People and AI agents building together — code, video, games and products, on your own subscriptions.', 'Люди и AI-агенты работают вместе над кодом, видео, играми и продуктами — на ваших подписках.')}</p></div><div class="nx-hero-art" aria-hidden="true"><i></i><i></i><i></i><b>N</b></div>`;
      const acts = el('div', 'nx-hero-actions');
      const a1 = el('button', 'nx-btn primary'); a1.type = 'button'; a1.innerHTML = I.plus + `<span>${t('New project', 'Новый проект')}</span>`; a1.addEventListener('click', newProject);
      const a2 = el('button', 'nx-btn'); a2.type = 'button'; a2.innerHTML = I.task + `<span>${t('Create task', 'Создать задачу')}</span>`; a2.addEventListener('click', newTask);
      const a3 = el('button', 'nx-btn'); a3.type = 'button'; a3.innerHTML = I.agents + `<span>${t('Agent terminals', 'Терминалы агентов')}</span>`; a3.addEventListener('click', () => setView('agents'));
      const a4 = el('button', 'nx-btn'); a4.type = 'button'; a4.innerHTML = I.plug + `<span>${t('Connect AI', 'Подключить ИИ')}</span>`; a4.addEventListener('click', () => setView('connect'));
      const a5 = el('button', 'nx-btn'); a5.type = 'button'; a5.innerHTML = I.mic + `<span>${t('Talk by voice', 'Поговорить голосом')}</span>`; a5.addEventListener('click', () => Voice.show());
      const a0 = el('button', 'nx-btn primary'); a0.type = 'button'; a0.innerHTML = I.split + `<span>${t('Code mode', 'Code mode')}</span>`; a0.addEventListener('click', () => CM.open(true));
      acts.append(a0, a1, a4, a5, a2, a3); $('.nx-hero-text', hero).append(acts);
      const close = el('button', 'nx-hero-close'); close.type = 'button'; close.innerHTML = I.x; close.title = t('Hide', 'Скрыть');
      close.addEventListener('click', () => { hero.remove(); store.set('hero-closed', true); });
      hero.append(close); top.append(hero);
    }
    const chips = el('div', 'nx-chips'); chips.id = 'nx-chips';
    top.append(chips);
    const head = el('div', 'nx-chanbar');
    head.innerHTML = `<div class="nx-chan"><strong id="nx-chan-name"># general</strong><small id="nx-chan-sub"></small></div>`;
    const tabs = el('nav', 'nx-tabs'); tabs.setAttribute('aria-label', t('Workspace views', 'Разделы рабочего пространства'));
    for (const [k, ic, label] of [['chat', I.chat, t('Chat', 'Чат')], ['code', I.code, t('Code', 'Код')], ['agents', I.split, t('Agents', 'Агенты')], ['projects', I.folder, t('Projects', 'Проекты')], ['connect', I.plug, t('Connect', 'Подключить')], ['voice', I.mic, t('Voice', 'Голос')]]) {
      const b = el('button', 'nx-tab'); b.type = 'button'; b.dataset.nxView = k; b.innerHTML = ic + `<span>${label}</span>`; b.title = label; b.setAttribute('aria-label', label);
      b.addEventListener('click', () => (k === 'voice' ? Voice.show() : setView(k))); if (k === 'voice') b.removeAttribute('data-nx-view'); tabs.append(b);
    }
    const pin = el('button', 'nx-tab nx-ico'); pin.type = 'button'; pin.innerHTML = I.pin; pin.title = t('Pinned', 'Закреплённые');
    pin.addEventListener('click', () => typeof togglePinsPanel === 'function' && togglePinsPanel());
    head.append(pin, tabs);
    top.append(head);
    center.prepend(top);
    views.agents = Split.build(); views.projects = Projects.build(); views.connect = Connect.build(); views.codemode = CM.build();
    const footer = $('footer', center);
    center.insertBefore(views.agents, footer); center.insertBefore(views.projects, footer); center.insertBefore(views.connect, footer); center.insertBefore(views.codemode, footer);
  }
  function renderChips() {
    const box = $('#nx-chips'); if (!box) return;
    box.replaceChildren(el('span', 'nx-chips-label', t('Agents', 'Агенты')));
    for (const a of agents()) {
      const b = el('button', 'nx-chip'); b.type = 'button'; b.title = `${a.label} — ${stateText(a.state)}`;
      b.innerHTML = `<span class="nx-face">${face(a.name)}</span><span>${esc(a.label)}</span><i class="nx-dot s-${a.state}"></i>`;
      if (a.state === 'offline') b.disabled = true;
      b.addEventListener('click', () => Split.focus(a.name));
      draggableAgent(b, a.name);
      box.append(b);
    }
    if (!agents().length) {  // first run: nothing connected yet — one clear next step
      const go = el('button', 'nx-chip nx-chip-connect', t('+ Connect your first AI', '+ Подключите первый ИИ')); go.type = 'button';
      go.title = t('Claude, ChatGPT/Codex, Gemini with your subscription, an API key or a local model', 'Claude, ChatGPT/Codex, Gemini по подписке, по API-ключу или локальная модель');
      go.addEventListener('click', () => setView('connect'));
      box.append(go);
    }
    const ch = window.activeChannel || 'general';
    const name = $('#nx-chan-name'); if (name) name.textContent = '# ' + ch;
    const sub = $('#nx-chan-sub');
    if (sub) {
      const proj = Projects.list.find((p) => p.channel === ch && p.status !== 'done');
      sub.textContent = proj ? `${t('Project', 'Проект')}: ${proj.title} · ${statusText(proj.status)}` : t('Team room · agents and you', 'Комната команды · агенты и вы');
    }
  }

  // ---------- right rail cards (CLEAN) ----------
  const Rail = {
    jobs: [], mode: null,
    build() {
      const rail = $('#right-rail'); if (!rail || $('#nx-rail')) return;
      const box = el('div', 'nx-rail'); box.id = 'nx-rail';
      box.innerHTML = `<section class="nx-card" id="nx-team"></section><section class="nx-card" id="nx-tasks"></section><section class="nx-card" id="nx-proj"></section>`;
      rail.prepend(box);
    },
    toggle(mode) {
      this.mode = this.mode === mode ? null : mode;
      document.body.dataset.nxRail = this.mode || '';
      document.querySelectorAll('[data-nx-rail]').forEach((b) => b.classList.toggle('active', b.dataset.nxRail === this.mode));
      if (this.mode === 'jobs' && typeof toggleJobsPanel === 'function' && $('#jobs-panel')?.classList.contains('hidden')) toggleJobsPanel();
      if (this.mode === 'rules' && typeof toggleRulesPanel === 'function' && $('#rules-panel')?.classList.contains('hidden')) toggleRulesPanel();
    },
    async loadJobs() {
      try { const d = await api('/api/jobs'); this.jobs = Array.isArray(d) ? d : d.jobs || []; } catch (e) { this.jobs = []; }
      this.render();
    },
    render() {
      const team = $('#nx-team');
      if (team) {
        const list = agents();
        // how many can answer right now — not a limit: add as many AIs as you like
        const on = list.filter((a) => ['online', 'working', 'approval'].includes(a.state)).length;
        team.innerHTML = `<header><h3>${I.team}<span>${t('Team', 'Команда')}</span><em title="${esc(t('Agents ready to answer now. There is no limit on how many you add.', 'Агенты, готовые ответить сейчас. Ограничений на количество нет.'))}">${esc(t('{0} online', 'в сети: {0}', on))}</em></h3></header>`;
        const you = el('div', 'nx-member');
        const uname = (document.getElementById('setting-username')?.value || 'user');
        you.innerHTML = `<span class="nx-face nx-you">${esc(uname.slice(0, 1).toUpperCase())}</span><div><strong>${esc(uname)}</strong><small>${t('You · decides and accepts', 'Вы · решаете и принимаете')}</small></div><i class="nx-dot s-online"></i>`;
        team.append(you);
        for (const a of list) {
          const row = el('button', 'nx-member'); row.type = 'button'; row.disabled = a.state === 'offline';
          row.innerHTML = `<span class="nx-face">${face(a.name)}</span><div><strong>${esc(a.label)} <span class="nx-st s-${a.state}">· ${stateText(a.state)}</span></strong><small>${esc(role(a.name))}</small></div>`;
          row.addEventListener('click', () => Split.focus(a.name));
          draggableAgent(row, a.name);
          team.append(row);
        }
        const more = el('button', 'nx-member nx-add-ai'); more.type = 'button';
        more.innerHTML = `<span class="nx-face nx-plus">${I.plus}</span><div><strong>${esc(t('Add an AI', 'Добавить ИИ'))}</strong><small>${esc(t('subscription, API key or local model', 'подписка, API-ключ или локальная модель'))}</small></div>`;
        more.addEventListener('click', () => setView('connect'));
        team.append(more);
      }
      const tasks = $('#nx-tasks');
      if (tasks) {
        const open = this.jobs.filter((j) => j.status === 'open');
        tasks.innerHTML = `<header><h3>${I.task}<span>${t('Active tasks', 'Активные задачи')}</span><em>${open.length}</em></h3></header>`;
        const add = el('button', 'nx-icon-btn'); add.type = 'button'; add.innerHTML = I.plus; add.title = t('New task', 'Новая задача'); add.addEventListener('click', newTask);
        $('header', tasks).append(add);
        for (const j of open.slice(0, 7)) {
          const row = el('label', 'nx-task');
          const box = el('input'); box.type = 'checkbox';
          box.title = t('Mark done', 'Отметить выполненной');
          box.addEventListener('change', async () => { try { await api(`/api/jobs/${j.id}`, { method: 'PATCH', body: JSON.stringify({ status: 'done' }) }); this.loadJobs(); } catch (err) { toast(err.message); box.checked = false; } });
          const txt = el('span', '', j.title);
          txt.addEventListener('click', (e) => { e.preventDefault(); if (typeof openJobConversation === 'function') { this.toggle('jobs'); openJobConversation(j.id); } });
          row.append(box, txt); tasks.append(row);
        }
        if (!open.length) tasks.append(el('div', 'nx-muted', t('No open tasks.', 'Открытых задач нет.')));
        document.querySelectorAll('[data-nx-jobs]').forEach((n) => { n.textContent = open.length || ''; });
      }
      const proj = $('#nx-proj');
      if (proj) {
        const ch = window.activeChannel || 'general';
        const p = Projects.list.find((x) => x.channel === ch && x.status !== 'done') || Projects.list.find((x) => x.status !== 'done');
        if (!p) { proj.innerHTML = `<header><h3>${I.folder}<span>${t('Project', 'Проект')}</span></h3></header><div class="nx-muted">${t('No active project.', 'Нет активного проекта.')}</div>`; }
        else {
          const done = p.criteria.filter((c) => c.done).length, total = p.criteria.length, pct = total ? Math.round(done / total * 100) : 0;
          proj.innerHTML = `<header><h3>${I.folder}<span>${esc(p.title)}</span></h3></header><div class="nx-progress"><div class="nx-progress-top"><span>${t('Progress', 'Прогресс')} · ${esc(statusText(p.status))}</span><b>${pct}%</b></div><div class="nx-bar"><i style="width:${pct}%"></i></div></div>`;
          const open = el('button', 'nx-link', t('Open project →', 'Открыть проект →')); open.type = 'button';
          open.addEventListener('click', () => { Projects.focus = p.id; setView('projects'); });
          proj.append(open);
        }
      }
    },
  };


  // ---------- Help that matches this layout (Clean) ----------
  function showHelp() {
    const d = el('dialog', 'nx-dialog nx-help');
    const items = [
      [I.team, t('Team chat', 'Командный чат'), t('The room where you and the agents talk. Write <kbd>@claude</kbd> or click a pill above the input to wake an agent.', 'Комната, где вы и агенты общаетесь. Напишите <kbd>@claude</kbd> или нажмите плашку над полем ввода, чтобы позвать агента.')],
      [I.agents, t('Agents', 'Агенты'), t('Each agent\'s own CLI, live, side by side. Type to it, send <kbd>Esc</kbd> or <kbd>^C</kbd>, Allow or Deny its permission requests.', 'Живой терминал каждого агента, рядом друг с другом. Пишите ему, отправляйте <kbd>Esc</kbd> или <kbd>^C</kbd>, разрешайте или отклоняйте запросы.')],
      [I.folder, t('Projects', 'Проекты'), t('A goal with done criteria. Agents tick criteria with evidence; only you accept the project.', 'Цель и критерии готовности. Агенты отмечают их с доказательствами, принимаете проект только вы.')],
      [I.task, t('Tasks', 'Задачи'), t('Tracked work from the chat. Hover a message → convert to task, or press + in Active tasks.', 'Отслеживаемая работа из чата. Наведите на сообщение → «в задачу» или нажмите + в «Активных задачах».')],
      [I.code, t('Code & files', 'Код и файлы'), t('Editor and a real shell in the lab folder the agents work in.', 'Редактор и настоящий терминал в папке, где работают агенты.')],
      [I.book, t('Rules & decisions', 'Правила и решения'), t('How agents should work in this room; active rules are re-sent to them automatically.', 'Как агентам работать в этой комнате; активные правила им напоминаются автоматически.')],
      [I.bolt, t('Sessions', 'Сессии'), t('The ▷ button next to the input starts a structured multi-agent workflow (brainstorm, review…).', 'Кнопка ▷ у поля ввода запускает сценарий для нескольких агентов (мозговой штурм, ревью…).')],
      [I.pin, t('Scheduling & pins', 'Расписание и закрепы'), t('The clock next to Send schedules a message. The pin keeps important messages at hand.', 'Часы рядом с «Отправить» планируют сообщение. Скрепка хранит важные сообщения под рукой.')],
    ];
    d.innerHTML = `<h3>${t('How NEONEXUS works', 'Как устроен NEONEXUS')}</h3><div class="nx-help-grid">${items.map(([ic, h, p]) => `<div class="nx-help-item"><h4>${ic}${h}</h4><p>${p}</p></div>`).join('')}</div>`;
    const row = el('div', 'nx-actions'); const ok = el('button', 'nx-btn primary', t('Got it', 'Понятно')); ok.type = 'button';
    ok.addEventListener('click', () => d.close()); row.append(ok); d.append(row);
    d.addEventListener('close', () => d.remove()); document.body.append(d); d.showModal();
  }
  document.addEventListener('click', (e) => {
    if (document.documentElement.dataset.skin !== 'clean') return;
    if (e.target.closest && e.target.closest('#help-btn')) { e.preventDefault(); e.stopImmediatePropagation(); showHelp(); }
  }, true);

  // ---------- boot ----------
  function settingsClose() {
    const bar = $('#settings-bar'); if (!bar || $('.nx-sheet-close', bar)) return;
    const x = el('button', 'nx-sheet-close'); x.type = 'button'; x.innerHTML = I.x; x.title = t('Close', 'Закрыть');
    x.addEventListener('click', () => typeof toggleSettings === 'function' && toggleSettings());
    bar.prepend(x);
    // the agent list loads once at page start; reload it whenever the sheet opens
    new MutationObserver(() => {
      if (!bar.classList.contains('hidden')) $('#agent-settings-refresh')?.click();
    }).observe(bar, { attributes: true, attributeFilter: ['class'] });
  }
  function boot() {
    settingsClose();
    buildHeader(); Side.build(); buildCenter(); Rail.build();
    // #projects, #agents, #code, #connect: the screen survives a reload and can be linked to
    const fromHash = () => { const v = location.hash.slice(1); return ['chat', 'agents', 'projects', 'code', 'connect', 'codemode'].includes(v) ? v : 'chat'; };
    setView(fromHash());
    window.addEventListener('hashchange', () => { if (fromHash() !== view) setView(fromHash()); });
    Projects.load(); Rail.loadJobs();
    let lastSig = '';
    setInterval(() => {
      if (document.body.classList.contains('nx-dragging')) return;  // don't replace the drag source
      const sig = JSON.stringify([agents().map((a) => a.name + a.state), Rail.jobs.map((j) => j.id + j.status),
        Projects.list.map((p) => p.id + p.status + p.criteria.filter((c) => c.done).length), window.activeChannel]);
      if (sig === lastSig) return;
      lastSig = sig; renderChips(); Rail.render();
    }, 2000);
    setInterval(() => { Projects.load(); Rail.loadJobs(); }, 20000);
    renderChips();
    // keep the channel label in step with switchChannel
    if (typeof window.switchChannel === 'function' && !window.switchChannel.nxWrapped) {
      const orig = window.switchChannel;
      window.switchChannel = function (...args) { const r = orig.apply(this, args); if (view !== 'chat' && !(view === 'codemode' && CM.owns(args[0]))) setView('chat'); setTimeout(renderChips, 0); return r; };
      window.switchChannel.nxWrapped = true;
    }
  }
  window.neonexusShell = { setView, focusAgent: (n) => Split.focus(n), voice: () => Voice.show(), voiceAsk: (text, who) => { if (who) Voice.picked = who; return Voice.ask(text); }, voiceState: () => ({ state: Voice.state, pending: Voice.pending, speaking: Voice.speaking, queue: Voice.queue.length }) };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 0));
  else setTimeout(boot, 0);
})();
