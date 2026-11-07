/* Interface language only. User and agent messages remain untouched. */
(() => {
  const labels = new Map(Object.entries({
    'Type a message... (use @name to mention agents)':'Напишите сообщение... (@имя — упомянуть агента)',
    'Jobs':'Задачи','Rules':'Правила','Pinned messages':'Закреплённые сообщения','Settings':'Настройки','Help':'Справка',
    'Terminal connected':'Терминал подключён','Terminal not connected':'Терминал не подключён',
    'USER':'ВЫ','user':'Вы','Use default':'По умолчанию',
    'Voice typing (local speech-to-text)':'Голосовой ввод (локальное распознавание)',
    'USER':'ВЫ','ACTIVE':'АКТИВНО','LIVE STATUS AND LATEST VISIBLE REPLIES':'СТАТУС И ПОСЛЕДНИЕ ОТВЕТЫ',
    'Add channel':'Добавить канал','Create Job':'Создать задачу','Add Rule':'Добавить правило','Clear chat in this channel':'Очистить чат в этом канале',
    'Start a session':'Начать сессию','Voice typing':'Голосовой ввод','Schedule message':'Запланировать сообщение',
    'Shown next to agentchattr, to tell this server apart from others':'Отображается рядом с названием, чтобы отличать серверы',
    'Max agent-to-agent hops before pausing':'Максимум переходов между агентами до паузы',
    'Show channels in a sidebar instead of a top bar':'Показывать каналы сбоку или сверху',
    'How often to re-send active rules to agents':'Как часто повторно отправлять активные правила агентам',
    'Name':'Имя','This server':'Этот сервер','Font':'Шрифт','Monospace':'Моноширинный','Sans':'Без засечек',
    'Loop guard':'Лимит цикла','History':'История','All':'Все','Contrast':'Контраст','Normal':'Обычный','High':'Высокий',
    'Channels':'Каналы','Top bar':'Верхняя панель','Sidebar':'Боковая панель','Rule refresh':'Обновление правил',
    'On rule changes':'При изменении правил','Every 5 triggers':'Каждые 5 запусков','Every 10 triggers':'Каждые 10 запусков',
    'Every 20 triggers':'Каждые 20 запусков','Every 50 triggers':'Каждые 50 запусков',
    'Project History':'История проекта','Export History':'Экспорт истории','Import History':'Импорт истории',
    'Pinned':'Закреплённые','No pinned messages':'Закреплённых сообщений нет','Jobs':'Задачи','Rules':'Правила','Remind agents':'Напомнить агентам',
    'AGENTS':'АГЕНТЫ','AGENTS // LIVE':'АГЕНТЫ // СЕЙЧАС','OFFLINE':'НЕ В СЕТИ','ONLINE':'В СЕТИ','WORKING':'РАБОТАЕТ','AUTH REQUIRED':'НУЖЕН ВХОД',
    'No recent reply':'Нет недавнего ответа','Processing a request…':'Выполняет запрос…','Finish sign-in in the agent terminal':'Завершите вход в терминале агента',
    'LIVE STATUS AND LATEST VISIBLE REPLIES':'СТАТУС И ПОСЛЕДНИЕ ОТВЕТЫ',
    '// CHANNEL':'// КАНАЛ','MULTI-AGENT CHAT':'МУЛЬТИЧАТ АГЕНТОВ','PLAN · BUILD · REVIEW':'ПЛАН · КОД · ПРОВЕРКА',
    '// NO SIGNAL':'// НЕТ СООБЩЕНИЙ','START THE CONVERSATION':'НАЧНИТЕ РАЗГОВОР',
    'Send a message or mention an agent to begin.':'Напишите сообщение или упомяните агента.',
    'Create your first job':'Создать первую задачу','Track work items with threaded conversations. Use @mentions to loop in agents.':'Ведите задачи в отдельных обсуждениях. Упоминайте агентов через @.',
    'No rules yet':'Правил пока нет','Tell your agents how to work':'Задайте правила работы агентов',
    'New rules are sent on the next agent trigger':'Новые правила передаются при следующем запуске агента',
    'TO DO':'К РАБОТЕ','ACTIVE':'В РАБОТЕ','CLOSED':'ЗАКРЫТЫ','Clear Chat':'Очистить чат',
    'Send':'Отправить','Message...':'Сообщение...','Loading messages...':'Загрузка сообщений…',
    'Enter to send · Shift+Enter for newline · Paste or drop files · Mic for voice · Type / or @ for autocomplete':'Enter — отправить · Shift+Enter — новая строка · Вставьте файл · / или @ — команды и агенты',
    'Default sound':'Звук по умолчанию','Background alerts':'Фоновые уведомления',
    'Soft Chime':'Мягкий сигнал','Bright Ping':'Звонкий сигнал','Gentle Pop':'Тихий щелчок','Alert Tone':'Сигнал тревоги',
    'Pluck':'Щипок','Click':'Щелчок','Warm Bell':'Колокольчик','None':'Без звука'
    ,'General':'Основное','Appearance':'Вид интерфейса','Chat and rules':'Чат и правила'
    ,'Notifications':'Уведомления','Data and history':'Данные и история'
    ,'Agents and tools':'Агенты и инструменты'
    ,'Subscription CLIs · model changes restart the selected agent':'Подписочные CLI · смена модели перезапускает агента'
    ,'Refresh':'Обновить','Online':'В сети','Offline':'Не в сети'
    ,'Tools:':'Инструменты:','Model':'Модель','Effort':'Усилие','CLI default':'По умолчанию CLI'
    ,'Apply':'Применить','Role in prompts':'Роль в запросах','Save role':'Сохранить роль'
    ,'Working instructions':'Рабочие инструкции','Save instructions':'Сохранить инструкции'
    ,'Installed locally:':'Установлено локально:','CLI permissions still apply.':'Права CLI действуют отдельно.'
  }));
  const originals = new WeakMap();
  const attrOriginals = new WeakMap();
  // every part of the interface; never people's and agents' messages, code, terminals or files
  const roots = ['body'];
  const blocked = 'script,style,#messages,#jobs-conv-messages,.msg-text,textarea,input,code,pre,.monaco-editor,.xterm,#code-terminal,#code-files,.nx-term,.nx-vscode,.nx-tree,.nx-plist,.nx-pcard h3,.nx-crit,.nx-rail-task';
  // the language comes from i18n.js (Settings choice, else the system language)
  const language = window.NX_LANG || 'en';
  const dict = (window.NX_DICT || {})[language] || {};
  const tr = (key) => (language === 'en' ? undefined : language === 'ru' ? (labels.get(key) ?? dict[key]) : dict[key]);
  const known = (key) => labels.has(key) || key in dict;
  function translateNode(node) {
    if (node.parentElement?.closest(blocked)) return;
    let raw = originals.has(node) ? originals.get(node) : node.textContent;
    if (originals.has(node) && node.textContent !== raw && node.textContent !== raw.replace(raw.trim(), tr(raw.trim()) || raw.trim())) raw = node.textContent;
    const key = raw.trim();
    if (!known(key)) return;
    originals.set(node, raw);
    const next = tr(key) ? raw.replace(key, tr(key)) : raw;
    if (node.textContent !== next) node.textContent = next;
  }
  function apply() {
    for (const selector of roots) {
      const root = document.querySelector(selector); if (!root) continue;
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) translateNode(walker.currentNode);
      for (const el of root.querySelectorAll('[title],[placeholder],[aria-label]')) {
        let saved = attrOriginals.get(el);
        if (!saved) { saved = {}; attrOriginals.set(el,saved); }
        for (const attr of ['title','placeholder','aria-label']) {
          if (!el.hasAttribute(attr)) continue;
          if (!(attr in saved)) saved[attr] = el.getAttribute(attr);
          const original = saved[attr];
          const translated = tr(original);
          if (translated) el.setAttribute(attr, translated);
        }
      }
    }
    const counter = document.getElementById('rules-counter');
    if (counter) {
      const word = language === 'en' ? 'active' : (tr('active') || (language === 'ru' ? 'активных' : 'active'));
      const next = counter.textContent.replace(/\bactive\b|\bACTIVE\b|активных/i, word);
      if (counter.textContent !== next) counter.textContent = next;
    }
    const picker = document.getElementById('setting-language'); if (picker) picker.value = language;
  }
  document.addEventListener('DOMContentLoaded', () => {
    const picker = document.getElementById('setting-language');
    if (picker && window.NX_LANGS) {
      picker.replaceChildren(...Object.entries(window.NX_LANGS).map(([code, name]) => new Option(name, code)));
      picker.value = language;
    }
    picker?.addEventListener('change', () => window.nxSetLang ? window.nxSetLang(picker.value) : null);
    // one pass per frame however many changes arrive (the chat streams a lot of them)
    let queued = false;
    const schedule = () => { if (queued || language === 'en') return; queued = true; requestAnimationFrame(() => { queued = false; apply(); }); };
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, {childList:true,subtree:true,characterData:true});
    apply();
  });
})();
