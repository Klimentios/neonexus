/* NEONEXUS skin switcher. Loaded in <head> so the skin is set before first paint.
   Skins: clean (light, default), breach, blackwall. */
(function () {
  var SKINS = ['clean', 'breach', 'blackwall'];
  var LABEL = { clean: 'Clean', breach: 'BREACH', blackwall: 'BLACKWALL', night: 'NIGHT' };
  var KEY = 'neonexus-skin-v2';  // v2: NIGHT (the old yellow look) retired, everyone starts on Clean
  // the mark redrawn in each skin's colours (night keeps the original file)
  var MARK = { breach: ['#ff2a6d', '#00eaff', '#06050a'], blackwall: ['#ff1838', '#f4ece6', '#040203'] };
  var origLogo = null;
  function cleanUri() {
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">' +
      '<rect x="3" y="3" width="58" height="58" rx="14" fill="#fff" stroke="#15305c" stroke-width="4"/>' +
      '<path fill="#15305c" d="M18 16h8l13 19V16h8v32h-8L26 29v19h-8z"/></svg>';
    return 'data:image/svg+xml,' + encodeURIComponent(svg);
  }
  function markUri(c) {
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">' +
      '<path fill="' + c[2] + '" d="M10 2h44l8 8v44l-8 8H2V10z"/>' +
      '<path fill="none" stroke="' + c[0] + '" stroke-width="3" d="M11 3h42l8 8v42l-8 8H3V11z"/>' +
      '<path fill="' + c[1] + '" opacity=".85" transform="translate(-1.5 0)" d="M15 15h8l18 22V15h8v34h-8L23 27v22h-8z"/>' +
      '<path fill="' + c[0] + '" transform="translate(1.5 0)" d="M15 15h8l18 22V15h8v34h-8L23 27v22h-8z"/>' +
      '<path fill="' + c[1] + '" d="M9 9h5v5H9zm41 0h5v5h-5zM9 50h5v5H9zm41 0h5v5h-5z"/>' +
      '<path stroke="' + c[1] + '" stroke-width="2" d="M27 8h10M27 56h10"/></svg>';
    return 'data:image/svg+xml,' + encodeURIComponent(svg);
  }
  function paintLogo(skin) {
    var img = document.querySelector('.header-logo');
    if (!img) return;
    if (origLogo === null) origLogo = img.getAttribute('src');
    img.setAttribute('src', skin === 'clean' ? cleanUri() : MARK[skin] ? markUri(MARK[skin]) : origLogo);
  }
  var root = document.documentElement;

  function read() {
    try { var s = localStorage.getItem(KEY); if (SKINS.indexOf(s) >= 0) return s; } catch (e) {}
    return 'clean';
  }
  function apply(skin) {
    if (skin === 'night') root.removeAttribute('data-skin'); else root.setAttribute('data-skin', skin);
    paintLogo(skin);
    var btn = document.getElementById('skin-toggle');
    if (btn) {
      btn.querySelector('span').textContent = LABEL[skin];
      btn.title = 'Skin: ' + LABEL[skin] + ' (click for next)';
    }
  }
  var current = read();
  apply(current);

  function mount() {
    var host = document.querySelector('.header-right');
    if (!host || document.getElementById('skin-toggle')) return;
    var btn = document.createElement('button');
    btn.id = 'skin-toggle';
    btn.type = 'button';
    btn.className = 'skin-toggle';
    btn.setAttribute('aria-label', 'Switch skin');
    btn.innerHTML = '<i aria-hidden="true"></i><span></span>';
    btn.addEventListener('click', function () {
      current = SKINS[(SKINS.indexOf(current) + 1) % SKINS.length];
      setTimeout(fire, 0);
      try { localStorage.setItem(KEY, current); } catch (e) {}
      apply(current);
    });
    host.insertBefore(btn, host.firstChild);
    apply(current);
  }
  // Agents are shown by their maker's mark (drawn here, no external files): the
  // portrait atlas was decorative art and read as if the agents were characters.
  function svgWrap(bg, body, badge) {
    return '<svg class="agent-face" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
      '<rect width="100" height="100" fill="' + bg + '"/>' + body + (badge || '') + '</svg>';
  }
  function claudeMark(color) {
    var rays = '', n = 12;
    for (var i = 0; i < n; i++) {
      var a = (i / n) * Math.PI * 2 + 0.2, len = i % 3 === 0 ? 31 : i % 3 === 1 ? 25 : 28;
      var x = 50 + Math.cos(a) * len, y = 50 + Math.sin(a) * len;
      rays += '<line x1="50" y1="50" x2="' + x.toFixed(1) + '" y2="' + y.toFixed(1) + '"/>';
    }
    return '<g stroke="' + color + '" stroke-width="8.5" stroke-linecap="round">' + rays + '</g>';
  }
  function openaiMark(color) {
    var g = '';
    for (var i = 0; i < 6; i++) {
      g += '<rect x="40" y="16" width="20" height="40" rx="10" transform="rotate(' + (i * 60) + ' 50 50) translate(0 2)"/>';
    }
    return '<g fill="none" stroke="' + color + '" stroke-width="5.5">' + g + '</g>';
  }
  function geminiMark(id) {
    return '<defs><linearGradient id="' + id + '" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#1c7df2"/>' +
      '<stop offset=".55" stop-color="#7a6cf0"/><stop offset="1" stop-color="#e36fa6"/></linearGradient></defs>' +
      '<path fill="url(#' + id + ')" d="M50 12C52.5 34 66 47.5 88 50C66 52.5 52.5 66 50 88C47.5 66 34 52.5 12 50C34 47.5 47.5 34 50 12Z"/>';
  }
  function antigravityMark(id) {
    return '<defs><linearGradient id="' + id + '" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#4285f4"/>' +
      '<stop offset=".35" stop-color="#ea4335"/><stop offset=".65" stop-color="#fbbc04"/><stop offset="1" stop-color="#34a853"/></linearGradient></defs>' +
      '<path d="M22 76 L50 22 L78 76" fill="none" stroke="url(#' + id + ')" stroke-width="11" stroke-linecap="round" stroke-linejoin="round"/>' +
      '<circle cx="50" cy="62" r="7" fill="url(#' + id + ')"/>';
  }
  var chatBadge = '<circle cx="78" cy="78" r="17" fill="#fff" stroke="#e5e8ef" stroke-width="2"/>' +
    '<path d="M70 72h16v10h-9l-5 4v-4h-2z" fill="#5e6778"/>';
  var uid = 0;
  function brandFace(name) {
    var raw = String(name || '').toLowerCase().trim().replace(/\s+/g, '-');
    var key = raw.replace(/-\d+$/, '').replace(/^squad-/, '');
    var squad = /^squad-/.test(raw) ? (raw.match(/-(\d+)$/) || [, ''])[1] : '';
    var num = squad ? '<circle cx="78" cy="22" r="15" fill="#15305c"/><text x="78" y="28" text-anchor="middle" font-family="Inter,Arial,sans-serif" font-weight="800" font-size="17" fill="#fff">' + squad + '</text>' : '';
    var chat = /chat$/.test(key) ? chatBadge : '';
    var id = 'nxg' + (++uid);
    if (key === 'claude' || key === 'claudechat' || key === 'claude-chat') return svgWrap('#f6efe9', claudeMark('#d97757'), chat + num);
    if (key === 'codex') return svgWrap('#111317', openaiMark('#ffffff'), num);
    if (key === 'gptchat' || key === 'gpt-chat' || key === 'gpt') return svgWrap('#ffffff', openaiMark('#10a37f'), chat + num);
    if (key === 'gemini' || key === 'geminichat' || key === 'gemini-chat') return svgWrap('#ffffff', geminiMark(id), chat + num);
    if (key === 'antigravity' || key === 'agy') return svgWrap('#ffffff', antigravityMark(id), num);
    if (key === 'user' || key === 'you') return svgWrap('#15305c', '<text x="50" y="64" text-anchor="middle" font-family="Inter,Arial,sans-serif" font-weight="800" font-size="40" fill="#fff">U</text>');
    return null;
  }
  function monogram(name) {
    var key = String(name || '').toLowerCase().trim().replace(/\s+/g, '-').replace(/-\d+$/, '');
    var colors = (typeof baseColors !== 'undefined' && baseColors) || {};
    var c = (colors[key] && colors[key].color) || '#64748b';
    var label = (colors[key] && colors[key].label) || key;
    var txt = label.replace(/[^A-Za-z0-9А-Яа-я]/g, '').slice(0, 2);
    txt = txt.charAt(0).toUpperCase() + txt.slice(1);
    return svgWrap(c, '<text x="50" y="64" text-anchor="middle" font-family="Inter,Arial,sans-serif" font-weight="800" font-size="38" fill="#fff">' + txt + '</text>');
  }
  function wrapFaces() {
    if (!window.agentFaceSvg || window.agentFaceSvg.nxWrapped) return;
    var portrait = window.agentFaceSvg;
    window.agentFaceSvg = function (name) { return brandFace(name) || (current === 'clean' ? monogram(name) : portrait(name)); };
    window.agentFaceSvg.nxWrapped = true;
  }
  function boot() { wrapFaces(); mount(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
  // Settings → Appearance → Theme: the same choice as the header button
  document.addEventListener('DOMContentLoaded', function () {
    var sel = document.getElementById('setting-skin');
    if (!sel) return;
    sel.value = current;
    sel.addEventListener('change', function () { window.neonexusSkin.set(sel.value); });
    document.addEventListener('click', function (e) {
      if (e.target && e.target.closest && e.target.closest('#skin-toggle')) setTimeout(function () { sel.value = current; }, 0);
    });
  });
  window.neonexusSkin = { list: SKINS.slice(), get: function () { return current; },
    set: function (s) { if (SKINS.indexOf(s) >= 0) { current = s; try { localStorage.setItem(KEY, s); } catch (e) {} apply(s); fire(); } } };
  // tell the rest of the page (VS Code follows light / dark)
  function fire() { try { document.dispatchEvent(new CustomEvent('neonexus-skin', { detail: current })); } catch (e) {} }
})();
