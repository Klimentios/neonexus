/* NEONEXUS interface languages. Loaded first, before every other script.
 *
 * The language is the one picked in Settings, else the system language, else English.
 * Strings are written in English in the code; static/i18n/<lang>.js maps English → language.
 * Russian comes from the code itself (t('English', 'Русский')) plus static/i18n/source.json.
 * Messages from people and agents are never translated.
 */
(() => {
  const LANGS = {
    en: 'English', ru: 'Русский', zh: '中文', es: 'Español', fr: 'Français', de: 'Deutsch',
    pt: 'Português', ja: '日本語', ko: '한국어', tr: 'Türkçe', ar: 'العربية', hi: 'हिन्दी',
  };
  const KEY = 'agentchattr-language';
  let saved = '';
  try { saved = localStorage.getItem(KEY) || ''; } catch (e) { /* private mode */ }
  const system = (navigator.languages || [navigator.language || 'en'])
    .map((l) => String(l).toLowerCase().split('-')[0]).find((l) => LANGS[l]);
  const lang = LANGS[saved] ? saved : (system || 'en');

  window.NX_LANGS = LANGS;
  window.NX_LANG = lang;
  window.NX_DICT = window.NX_DICT || {};
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';

  // the dictionary of the current language, loaded synchronously while the page parses
  if (lang !== 'en') {
    document.write(`<script src="/static/i18n/${lang}.js?v=10"><\/script>`);
  }

  const fill = (s, args) => (args.length ? String(s).replace(/\{(\d+)\}/g, (m, i) => (args[i] ?? m)) : s);

  /** Translate an English UI string. `ru` is the Russian text written next to it in the code. */
  window.nxT = (en, ru, ...args) => {
    let s = en;
    if (lang === 'ru') s = ru ?? (window.NX_DICT.ru || {})[en] ?? en;
    else if (lang !== 'en') s = (window.NX_DICT[lang] || {})[en] ?? en;
    return fill(s, args);
  };

  /** Switch the interface language and reload (Settings → Language). */
  window.nxSetLang = (next) => {
    if (!LANGS[next]) return;
    try { localStorage.setItem(KEY, next); } catch (e) { /* ignore */ }
    location.reload();
  };
})();
