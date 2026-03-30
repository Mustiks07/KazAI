// ════════════════════════════════════
// APP.JS — KazAI негізгі логикасы
// ════════════════════════════════════

// ── Avatar SVG ──
const AV = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><rect width="40" height="40" rx="8" fill="#1d4ed8"/><text x="50%" y="54%" dominant-baseline="middle" text-anchor="middle" font-family="monospace" font-weight="700" font-size="20" fill="white">K</text></svg>')}`;

// ── State ──
let currentChatId = null;
let mod           = 'all';
let mic = null, isRec = false, file = null, sbOpen = true;
let msgCount = 0, totalTokens = 0, fontSize = 14, selectedPlan = 'pro';
let todayMsgs = 0, currentPlan = 'free';
const DAILY_LIMIT = 20;

const modeCfg = {
  all:  {label:'Жалпы чат',        color:'#3b82f6', hint:'Сұрағыңызды жазыңыз немесе / теріңіз...'},
  gov:  {label:'Мемл. қызметтер',  color:'#10b981', hint:'Қандай мемлекеттік қызмет?'},
  tutor:{label:'Қазақ тілі',       color:'#f59e0b', hint:'Тексергіңіз келген мәтін немесе сұрақ...'},
  det:  {label:'ЖИ анықтауы',      color:'#ef4444', hint:'Тексергіңіз келген мәтінді жазыңыз...'},
};

// ── Gov FAQ ──
const GOV_FAQ = [
  {icon:'💳', text:'ИИН алу',              q:'ИИН алу үшін не қажет?'},
  {icon:'🔐', text:'ЭЦП алу',              q:'ЭЦП электрондық қолтаңба қалай алынады?'},
  {icon:'📘', text:'Паспорт алу',           q:'Паспорт алу немесе жаңарту қалай?'},
  {icon:'🪪', text:'Жеке куәлік',           q:'Жеке куәлік алу немесе жаңарту?'},
  {icon:'🏠', text:'Тіркеу анықтамасы',     q:'Тіркеу анықтамасы (прописка) қалай алынады?'},
  {icon:'👶', text:'Балаға жәрдемақы',      q:'Балаға жәрдемақы қалай рәсімделеді?'},
  {icon:'🚗', text:'Автокөлік тіркеу',      q:'Автокөлікті тіркеу мемлекеттік нөмір алу?'},
  {icon:'🏥', text:'Дәрігерге жазылу',      q:'Дәрігерге онлайн жазылу қалай?'},
  {icon:'💼', text:'Жұмыссыздық жәрдемақы',q:'Жұмыссыздық жәрдемақысы қалай алынады?'},
  {icon:'💍', text:'Неке тіркеу',           q:'Некені тіркеу ЗАГС қалай жасалады?'},
  {icon:'🎓', text:'ЖК ашу (бизнес)',       q:'Жеке кәсіпкер ЖК ашу қалай тіркеледі?'},
  {icon:'🏢', text:'ЦОН жұмыс уақыты',     q:'ЦОН мекенжайы мен жұмыс уақыты?'},
  {icon:'📱', text:'eGov Mobile',           q:'eGov Mobile қосымшасын қалай пайдалану?'},
  {icon:'⚖️', text:'Жол айыппұлы',          q:'Жол айыппұлдарын тексеру және төлеу?'},
  {icon:'🏦', text:'Зейнетақы ЕНПФ',        q:'Зейнетақы ЕНПФ жинақтарымды қалай тексеремін?'},
];

// ════════════════════════════════════
// INIT — Auth модулімен байланыс
// ════════════════════════════════════
function initApp() {
  // Аватарларды орнату
  document.querySelectorAll('[data-av]').forEach(el => el.src = AV);

  // Auth модулін іске қосу
  Auth.init(onLoginSuccess, onLogoutSuccess);

  // Параметрлерді жүктеу
  setTheme(localStorage.getItem('kaz_theme') || 'dark');
  setMod('all', document.getElementById('btn-all'), true);

  // Modal overlay жабу
  document.querySelectorAll('.modal-overlay').forEach(m => {
    m.addEventListener('click', e => { if(e.target === m) m.classList.remove('show'); });
  });

  selectPlan('pro');
}

// ════════════════════════════════════
// AUTH CALLBACKS
// ════════════════════════════════════
function onLoginSuccess(user) {
  currentPlan = user.plan || 'free';
  todayMsgs   = user.daily_count || 0;
  updateUserUI(user);
  loadHistoryFromServer();
  showToast(`Сәлеметсіз, ${user.name.split(' ')[0]}! 👋`, 'success');
}

function onLogoutSuccess() {
  currentChatId = null;
  currentPlan   = 'free';
  todayMsgs     = 0;
  clearChatMessages();
  document.getElementById('histList').innerHTML = '';
  updateUserUI(null);
}

function updateUserUI(user) {
  // Header auth area — Auth.js өзі жаңартады
  // Sidebar
  if (user) {
    document.getElementById('sbUser').textContent = user.email;
    document.getElementById('wTitle').textContent = `Сәлем, ${user.name.split(' ')[0]}! 👋`;
    updatePlanUI();
  } else {
    document.getElementById('sbUser').textContent = '—';
    document.getElementById('wTitle').textContent = 'KazAI-ға қош келдіңіз';
  }
}

function updatePlanUI() {
  const p = currentPlan;
  const badge = document.getElementById('sbPlan');
  badge.className = `sb-plan-badge ${p}`;
  badge.textContent = p === 'free' ? 'Free · 20/күн' : p === 'pro' ? '✨ Pro · Шексіз' : '🔥 Ultra';
  document.getElementById('quotaBar').style.display = p !== 'free' ? 'none' : 'flex';
  if (p === 'free') updateQuota();
}

function updateQuota() {
  const pct = Math.min(todayMsgs / DAILY_LIMIT * 100, 100);
  document.getElementById('quotaFill').style.width = pct + '%';
  document.getElementById('quotaTxt').textContent = `${todayMsgs}/${DAILY_LIMIT} сұрақ`;
  document.getElementById('limitBanner').style.display = (pct >= 100 && currentPlan === 'free') ? 'flex' : 'none';
}

// ════════════════════════════════════
// API HELPER
// ════════════════════════════════════
async function apiCall(endpoint, method = 'GET', body = null) {
  const headers = {'Content-Type': 'application/json'};
  const token = Auth.getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const opts = {method, headers};
  if (body) opts.body = JSON.stringify(body);
  const res  = await fetch(endpoint, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

// ════════════════════════════════════
// TOASTS
// ════════════════════════════════════
function showToast(msg, type = 'info') {
  const icons = {success:'✓', error:'✕', info:'i'};
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<div class="toast-icon">${icons[type]}</div>${msg}`;
  document.getElementById('toasts').appendChild(t);
  setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 350); }, 3200);
}

// ════════════════════════════════════
// MODALS
// ════════════════════════════════════
function openModal(id)  { document.getElementById(id).classList.add('show'); }
function closeModal(id) { document.getElementById(id).classList.remove('show'); }

function selectPlan(p) {
  selectedPlan = p;
  document.querySelectorAll('.plan-card').forEach(c => c.classList.remove('selected'));
  document.getElementById(`plan${p.charAt(0).toUpperCase() + p.slice(1)}`).classList.add('selected');
}

function confirmPlan() {
  currentPlan = selectedPlan;
  const user = Auth.getUser();
  if (user) user.plan = currentPlan;
  if (Auth.getToken()) apiCall('/api/subscription', 'POST', {plan: currentPlan}).catch(() => {});
  updatePlanUI();
  closeModal('plansModal');
  showToast(`${currentPlan.toUpperCase()} жоспары белсендірілді! 🎉`, 'success');
}

// ════════════════════════════════════
// SETTINGS
// ════════════════════════════════════
function setTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  document.getElementById('themeLight')?.classList.toggle('active', t === 'light');
  document.getElementById('themeDark')?.classList.toggle('active', t === 'dark');
  const icon = document.getElementById('themeIcon');
  if (icon) icon.innerHTML = t === 'dark'
    ? '<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>'
    : '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>';
  localStorage.setItem('kaz_theme', t);
}

function toggleThemeQuick() {
  setTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
}

function setAccent(name, c1, c2) {
  document.querySelectorAll('.accent-dot').forEach(d => d.classList.remove('active'));
  event.target.classList.add('active');
  document.documentElement.style.setProperty('--blue', c1);
  document.documentElement.style.setProperty('--grad', `linear-gradient(135deg,${c1},${c2})`);
  showToast('Акцент түсі өзгертілді', 'info');
}

function changeFontSize(delta) {
  fontSize = Math.max(12, Math.min(18, fontSize + delta));
  document.getElementById('fsVal').textContent = fontSize;
  document.documentElement.style.setProperty('--msg-size', fontSize + 'px');
}

function toggleAnimations(el) {
  if (!el.checked) {
    const s = document.createElement('style'); s.id = 'noAnim';
    s.textContent = '*{animation:none!important;transition:none!important}';
    document.head.appendChild(s);
  } else { document.getElementById('noAnim')?.remove(); }
}

function toggleCompact(el) {
  document.querySelectorAll('.msgs-inner').forEach(m => m.style.gap = el.checked ? '10px' : '20px');
}

// ════════════════════════════════════
// SIDEBAR
// ════════════════════════════════════
function toggleSidebar() {
  sbOpen = !sbOpen;
  document.getElementById('sidebar').classList.toggle('closed', !sbOpen);
}

function newChat() {
  currentChatId = null;
  clearChatMessages();
  if (mod === 'gov') setTimeout(showGovFAQ, 150);
  showToast('Жаңа чат бастады', 'info');
}

function filterHistory(q) {
  document.querySelectorAll('#histList .hi').forEach(el => {
    const txt = el.querySelector('span')?.textContent || '';
    el.style.display = txt.toLowerCase().includes(q.toLowerCase()) ? 'flex' : 'none';
  });
}

// ════════════════════════════════════
// GOV FAQ CHIPS
// ════════════════════════════════════
function showGovFAQ() {
  document.getElementById('govFaqBlock')?.remove();
  const inner = document.getElementById('msgsInner');
  const block = document.createElement('div');
  block.id = 'govFaqBlock';
  block.className = 'gov-faq-block';

  const label = document.createElement('div');
  label.className = 'gov-faq-label';
  label.textContent = 'Жиі қойылатын сұрақтар';
  block.appendChild(label);

  const grid = document.createElement('div');
  grid.className = 'gov-faq-grid';

  GOV_FAQ.forEach(item => {
    const chip = document.createElement('button');
    chip.className = 'gov-faq-chip';
    chip.innerHTML = `<span class="gov-faq-chip-icon">${item.icon}</span><span>${item.text}</span>`;
    chip.onclick = () => {
      document.getElementById('govFaqBlock')?.remove();
      quick(item.q);
    };
    grid.appendChild(chip);
  });

  block.appendChild(grid);
  inner.appendChild(block);
  if (document.getElementById('toggleScroll')?.checked)
    document.getElementById('msgsWrap').scrollTop = 99999;
}

// ════════════════════════════════════
// SLASH COMMANDS
// ════════════════════════════════════
function onInput(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 130) + 'px';
  document.getElementById('slashMenu').classList.toggle('show', el.value === '/' || el.value.startsWith('/'));
}

function slashCmd(cmd) {
  document.getElementById('inp').value = '';
  document.getElementById('slashMenu').classList.remove('show');
  if (cmd === 'clear')  { clearChat(); return; }
  if (cmd === 'export') { exportChat(); return; }
  const map = {gov:'btn-gov', tutor:'btn-tutor', det:'btn-det'};
  if (map[cmd]) setMod(cmd, document.getElementById(map[cmd]));
  showToast(`/${cmd} режимі белсендірілді`, 'info');
}

document.addEventListener('click', e => {
  if (!e.target.closest('.input-outer')) document.getElementById('slashMenu')?.classList.remove('show');
});

// ════════════════════════════════════
// MARKDOWN RENDERER
// ════════════════════════════════════
function renderMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/```[\w]*\n?([\s\S]*?)```/g, '<pre style="background:var(--s2);border:1px solid var(--border);border-radius:8px;padding:12px;overflow-x:auto;margin:6px 0;font-size:13px"><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code style="background:var(--s3);padding:1px 6px;border-radius:4px;font-size:13px">$1</code>')
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<div style="font-weight:700;font-size:14px;color:var(--hi);margin:10px 0 4px">$1</div>')
    .replace(/^## (.+)$/gm,  '<div style="font-weight:700;font-size:15px;color:var(--hi);margin:12px 0 5px">$1</div>')
    .replace(/^# (.+)$/gm,   '<div style="font-weight:700;font-size:17px;color:var(--hi);margin:14px 0 6px">$1</div>')
    .replace(/^[-•] (.+)$/gm, '<div style="display:flex;gap:7px;margin:2px 0"><span style="color:var(--blue);flex-shrink:0">•</span><span>$1</span></div>')
    .replace(/^(\d+)\. (.+)$/gm, '<div style="display:flex;gap:7px;margin:2px 0"><span style="color:var(--blue);font-weight:600;flex-shrink:0;min-width:18px">$1.</span><span>$2</span></div>')
    .replace(/^---$/gm, '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">')
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener" style="color:var(--blue);text-decoration:underline">$1</a>')
    .replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
}

// ════════════════════════════════════
// DETECTOR CARD
// ════════════════════════════════════
function renderDetectorCard(score, text) {
  const isAI = score >= 50;
  const color = isAI ? '#fca5a5' : '#6ee7b7';
  const fillCls = isAI ? 'fai' : 'fhu';
  const verdict = isAI ? '⚠ Жасанды интеллект жазған болуы мүмкін' : '✓ Адам жазған мәтін';
  return `<div class="det-card">
    <div class="det-hd">
      <span class="det-v" style="color:${color}">${verdict}</span>
      <span class="det-p" style="color:${color}">${score}%</span>
    </div>
    <div class="det-track"><div class="det-fill ${fillCls}" style="width:${score}%"></div></div>
    <div class="det-note">${renderMarkdown(text || '')}</div>
  </div>`;
}

// ════════════════════════════════════
// MESSAGES
// ════════════════════════════════════
const chipM = {
  all:   ['Мемл. қызметтер', 'Қазақ тілі', 'ЖИ анықтауы'],
  gov:   ['ЭЦП алу', 'Жәрдемақы', 'Паспорт алу'],
  tutor: ['Сөйлемді тексер', 'Грамматика', 'Аударма'],
  det:   ['Басқа мәтін тексер'],
};

function addMsg(content, isUser, msgMod, detData) {
  document.getElementById('govFaqBlock')?.remove();
  const w = document.getElementById('welcome'); if (w) w.remove();
  const inner = document.getElementById('msgsInner');
  const t = new Date().toLocaleTimeString('kk-KZ', {hour:'2-digit', minute:'2-digit'});
  const d = document.createElement('div');
  d.className = `msg ${isUser ? 'user' : 'bot'}`;

  let bHTML = '';
  if (!isUser && detData) {
    bHTML = renderDetectorCard(detData.score, content);
  } else if (isUser) {
    bHTML = (content || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  } else {
    bHTML = renderMarkdown(content || '');
  }

  const aM = msgMod || mod;
  const chips = (!isUser && chipM[aM])
    ? `<div class="chips">${chipM[aM].map(c => `<span class="chip" onclick="quick('${c}')">${c}</span>`).join('')}</div>` : '';
  const actBtns = !isUser
    ? `<div class="msg-actions">
        <button class="msg-act-btn" onclick="copyMsg(this)">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>Көшіру
        </button>
        <button class="msg-act-btn" onclick="likeMsg(this)">👍</button>
        <button class="msg-act-btn" onclick="dislikeMsg(this)">👎</button>
      </div>` : '';

  if (isUser) {
    d.innerHTML = `<div class="msg-row"><div class="bubble">${bHTML}</div></div><div class="mtime">${t}</div>`;
  } else {
    d.innerHTML = `<div class="msg-row">
      <div class="bot-av"><img src="${AV}" alt=""></div>
      <div><div class="bubble">${bHTML}</div>${chips}${actBtns}</div>
    </div>
    <div class="mtime" style="padding-left:36px">${t}</div>`;
  }

  inner.appendChild(d);
  if (document.getElementById('toggleScroll')?.checked)
    document.getElementById('msgsWrap').scrollTop = 99999;

  msgCount++;
  totalTokens += Math.round((content || '').length / 4);
  document.getElementById('statMsgs').textContent = msgCount;
  document.getElementById('statTokens').textContent = totalTokens > 999 ? Math.round(totalTokens / 1000) + 'k' : totalTokens;
}

function addTyping() {
  document.getElementById('govFaqBlock')?.remove();
  const w = document.getElementById('welcome'); if (w) w.remove();
  const d = document.createElement('div'); d.className = 'msg bot'; d.id = 'typing';
  d.innerHTML = `<div class="msg-row">
    <div class="bot-av"><img src="${AV}" alt=""></div>
    <div class="tbub"><span></span><span></span><span></span></div>
  </div>`;
  document.getElementById('msgsInner').appendChild(d);
  document.getElementById('msgsWrap').scrollTop = 99999;
}
function rmTyping() { document.getElementById('typing')?.remove(); }

// ════════════════════════════════════
// SEND
// ════════════════════════════════════
async function send() {
  if (currentPlan === 'free' && todayMsgs >= DAILY_LIMIT) {
    showToast('Бүгінгі лимит таусылды! Pro-ға жаңартыңыз', 'error');
    openModal('plansModal'); return;
  }
  const inp = document.getElementById('inp');
  const txt = inp.value.trim();
  if (!txt && !file) return;

  addMsg(txt || (file ? `📎 ${file.name}` : ''), true);
  inp.value = ''; inp.style.height = 'auto';
  const f = file; clearFile();
  document.getElementById('sendBtn').disabled = true;
  addTyping();

  try {
    if (f && f.type.startsWith('video/')) {
      const fd = new FormData(); fd.append('file', f);
      const headers = {}; const token = Auth.getToken();
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch('/api/detect/video', {method:'POST', headers, body:fd});
      const data = await res.json(); rmTyping();
      if (!res.ok) throw new Error(data.error || 'Қате');
      _handleResponse(data, 'det');
      document.getElementById('sendBtn').disabled = false; return;
    }
    if (f && f.type.startsWith('image/')) {
      const fd = new FormData(); fd.append('file', f);
      const headers = {}; const token = Auth.getToken();
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch('/api/detect/image', {method:'POST', headers, body:fd});
      const data = await res.json(); rmTyping();
      if (!res.ok) throw new Error(data.error || 'Қате');
      _handleResponse(data, 'det');
      document.getElementById('sendBtn').disabled = false; return;
    }
    const data = await apiCall('/api/chat', 'POST', {text:txt, module:mod, chat_id:currentChatId});
    rmTyping();
    if (!currentChatId && data.chat_id) {
      currentChatId = data.chat_id;
      addToSidebarHistory(txt, currentChatId);
    }
    _handleResponse(data, mod);
  } catch(e) {
    rmTyping();
    showToast('Сервер қатесі: ' + e.message, 'error');
    addMsg('❌ Серверге қосылу мүмкін болмады. Flask сервері іске қосылған ба?', false, mod);
  }
  document.getElementById('sendBtn').disabled = false;
}

function _handleResponse(data, msgMod) {
  const resp = data.response;
  if (data.usage) { todayMsgs = data.usage.today || todayMsgs + 1; updateQuota(); }
  else { todayMsgs++; updateQuota(); }
  if (!resp) { addMsg('Жауап алу мүмкін болмады.', false, msgMod); return; }
  if (resp.verdict || (resp.score !== undefined && resp.score !== null)) {
    addMsg(resp.text || resp.label || '', false, msgMod, {
      score: resp.score || 0,
      verdict: resp.verdict || (resp.score >= 50 ? 'ai' : 'human'),
    });
  } else {
    addMsg(resp.text || resp.answer || '...', false, msgMod);
  }
}

function quick(t) { document.getElementById('inp').value = t; send(); }
function onKey(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }

function setMod(m, el, keepChat = false) {
  mod = m;
  document.querySelectorAll('.sb-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  const cfg = modeCfg[m];
  const dot = document.getElementById('modeDot');
  dot.style.background   = cfg.color;
  dot.style.boxShadow    = `0 0 6px ${cfg.color}`;
  document.getElementById('modeLbl').textContent     = cfg.label;
  document.getElementById('inp').placeholder         = cfg.hint;
  if (!keepChat && currentChatId !== null) { currentChatId = null; clearChatMessages(); }
  if (m === 'gov') setTimeout(showGovFAQ, 120);
}

function onFile(e) {
  file = e.target.files[0]; if (!file) return;
  document.getElementById('fname').textContent = file.name;
  document.getElementById('fprev').classList.add('show');
  setMod('det', document.getElementById('btn-det'), true);
}
function clearFile() {
  file = null;
  document.getElementById('fprev').classList.remove('show');
  document.getElementById('finp').value = '';
}

function toggleMic() {
  const btn = document.getElementById('micBtn');
  if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
    showToast('Chrome браузерін қолданыңыз', 'error'); return;
  }
  if (isRec) { mic?.stop(); isRec = false; btn.classList.remove('rec'); return; }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  mic = new SR(); mic.lang = 'kk-KZ'; mic.continuous = false; mic.interimResults = false;
  mic.onstart  = () => { isRec = true; btn.classList.add('rec'); showToast('Тыңдалуда...', 'info'); };
  mic.onresult = e => { document.getElementById('inp').value = e.results[0][0].transcript; };
  mic.onend    = () => { isRec = false; btn.classList.remove('rec'); };
  mic.start();
}

function clearChatMessages() {
  document.getElementById('govFaqBlock')?.remove();
  const inner = document.getElementById('msgsInner'); inner.innerHTML = '';
  const w = document.createElement('div'); w.className = 'welcome'; w.id = 'welcome';
  w.innerHTML = `
    <div class="w-logo"><div class="w-avatar"><img src="${AV}" alt=""></div></div>
    <div>
      <div class="w-title" id="wTitle">Жаңа чат</div>
      <div class="w-sub">Сұрағыңызды жазыңыз немесе режимді таңдаңыз.</div>
    </div>`;
  inner.appendChild(w);
}
function clearChat() { currentChatId = null; clearChatMessages(); showToast('Чат тазаланды', 'info'); }

// ════════════════════════════════════
// HISTORY
// ════════════════════════════════════
async function loadHistoryFromServer() {
  if (!Auth.getToken()) return;
  try {
    const chats = await apiCall('/api/history');
    const hist  = document.getElementById('histList'); hist.innerHTML = '';
    chats.slice(0, 15).forEach(c => {
      const li = document.createElement('div');
      li.className = 'hi'; li.dataset.chatId = c.id;
      li.innerHTML = `<div class="hd"></div><span>${c.title}</span>
        <span class="hi-del" onclick="delHistoryServer(event,this,${c.id})">✕</span>`;
      li.onclick = () => loadHistoryChat(c.id, li);
      hist.appendChild(li);
    });
  } catch(e) { console.warn('History:', e.message); }
}

let _loadingChatId = null;
async function loadHistoryChat(chatId, el) {
  if (_loadingChatId === chatId) return;
  _loadingChatId = chatId;
  setTimeout(() => { if (_loadingChatId === chatId) _loadingChatId = null; }, 1500);
  try {
    const msgs = await apiCall(`/api/history/${chatId}/messages`);
    currentChatId = chatId; document.getElementById('msgsInner').innerHTML = '';
    msgs.forEach(m => addMsg(m.content, m.role === 'user', m.module || mod, m.det_data || null));
    document.querySelectorAll('.hi').forEach(h => h.style.background = '');
    if (el) el.style.background = 'rgba(59,130,246,0.08)';
    showToast('Чат жүктелді', 'info');
  } catch(e) { showToast('Жүктеу қатесі: ' + e.message, 'error'); }
}

async function delHistoryServer(e, el, chatId) {
  e.stopPropagation();
  try {
    await apiCall(`/api/history/${chatId}`, 'DELETE');
    el.closest('.hi').remove();
    if (currentChatId === chatId) { currentChatId = null; clearChatMessages(); }
    showToast('Чат жойылды', 'info');
  } catch { showToast('Жою қатесі', 'error'); }
}

function addToSidebarHistory(txt, chatId) {
  const li = document.createElement('div');
  li.className = 'hi'; li.dataset.chatId = chatId;
  li.innerHTML = `<div class="hd"></div><span>${txt.substring(0,30)}${txt.length>30?'…':''}</span>
    <span class="hi-del" onclick="delHistoryServer(event,this,${chatId})">✕</span>`;
  li.onclick = () => loadHistoryChat(chatId, li);
  const hist = document.getElementById('histList');
  hist.insertBefore(li, hist.firstChild);
  if (hist.children.length > 15) hist.lastChild.remove();
}

// ════════════════════════════════════
// MESSAGE ACTIONS
// ════════════════════════════════════
function copyMsg(btn) {
  const bubble = btn.closest('.msg-row').querySelector('.bubble');
  navigator.clipboard?.writeText(bubble.innerText).then(() => showToast('Хабар көшірілді', 'success'));
}
function likeMsg(btn)    { btn.style.color = '#10b981'; showToast('Бағаңыз үшін рақмет! 🙏', 'success'); }
function dislikeMsg(btn) { btn.style.color = '#ef4444'; showToast('Кері байланыс жіберілді', 'info'); }

function exportChat() {
  const msgs = document.querySelectorAll('.bubble');
  if (!msgs.length) { showToast('Экспорт үшін хабарлар жоқ', 'error'); return; }
  let txt = `KazAI Чат Экспорты\n${new Date().toLocaleString()}\n${'─'.repeat(40)}\n\n`;
  msgs.forEach(m => {
    const isUser = m.closest('.msg.user');
    txt += (isUser ? '👤 Пайдаланушы' : '🤖 KazAI') + ': ' + m.innerText + '\n\n';
  });
  const a = document.createElement('a');
  a.href = 'data:text/plain;charset=utf-8,' + encodeURIComponent(txt);
  a.download = 'kazai-chat.txt'; a.click();
  showToast('Чат жүктелді', 'success');
}

// Profile modal helpers
function openProfileModal() {
  const user = Auth.getUser();
  if (!user) { Auth.showLoginOverlay(); return; }
  document.getElementById('profileName').textContent  = user.name;
  document.getElementById('profileEmail').textContent = user.email;
  document.getElementById('profilePlan').textContent  = currentPlan === 'free' ? 'Free' : '✨ ' + currentPlan;
  openModal('profileModal');
}
function doLogout() { closeModal('profileModal'); Auth.logout(); }

// ── START ──
window.addEventListener('DOMContentLoaded', initApp);