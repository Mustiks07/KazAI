// ════════════════════════════════════
// KazAI — app.js
// ════════════════════════════════════

// ── Avatar (simple URL instead of base64) ──
const AV = 'https://ui-avatars.com/api/?name=KazAI&background=3b82f6&color=fff&size=128&rounded=true&bold=true';

['authAv','sbAv','wAv','profileAv'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.src = AV;
});

// ════════════════════════════════════
// STATE
// ════════════════════════════════════
const API_URL = '';  // бос = Flask-қа тікелей (localhost:5000 немесе Render URL)

let currentUser   = null;
let authToken     = localStorage.getItem('kaz_token') || null;
let currentChatId = null;
let mod = 'all';
let mic = null, isRec = false, file = null, sbOpen = true;
let msgCount = 0, totalTokens = 0, fontSize = 14, selectedPlan = 'pro';
const DAILY_LIMIT = 20;
let todayMsgs  = parseInt(localStorage.getItem('kaz_today') || '0');
let currentPlan = localStorage.getItem('kaz_plan') || 'free';

// ── API Helper ──
async function apiCall(endpoint, method = 'GET', body = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);
  try {
    const res  = await fetch(API_URL + endpoint, opts);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Серверде қате');
    return data;
  } catch(e) { throw e; }
}

// ── Mode config ──
const modeCfg = {
  all:   { label: 'Жалпы чат',       color: '#3b82f6', hint: 'Сұрағыңызды жазыңыз немесе / теріңіз...' },
  gov:   { label: 'Мемл. қызметтер', color: '#10b981', hint: 'Қандай мемлекеттік қызмет?' },
  tutor: { label: 'Қазақ тілі',      color: '#f59e0b', hint: 'Тексергіңіз келген мәтін...' },
  det:   { label: 'ЖИ анықтауы',     color: '#ef4444', hint: 'ЖИ тексергіңіз келген мәтін...' }
};

// ════════════════════════════════════
// AUTH
// ════════════════════════════════════
function switchAuthTab(tab) {
  document.querySelectorAll('.auth-tab').forEach((t,i) =>
    t.classList.toggle('active', tab === 'login' ? i === 0 : i === 1)
  );
  document.getElementById('loginForm').classList.toggle('hidden', tab !== 'login');
  document.getElementById('registerForm').classList.toggle('hidden', tab !== 'register');
}

async function doLogin() {
  const email = document.getElementById('loginEmail').value.trim();
  const pass  = document.getElementById('loginPass').value;
  const errEl = document.getElementById('loginErr');
  if (!email || !pass) { errEl.textContent = 'Барлық өрістерді толтырыңыз'; return; }
  errEl.textContent = 'Жүктелуде...';
  try {
    const data = await apiCall('/api/auth/login', 'POST', { email, password: pass });
    authToken = data.token;
    localStorage.setItem('kaz_token', authToken);
    loginSuccess(data.user);
  } catch(e) { errEl.textContent = e.message; }
}

async function doRegister() {
  const name  = document.getElementById('regName').value.trim();
  const email = document.getElementById('regEmail').value.trim();
  const pass  = document.getElementById('regPass').value;
  const errEl = document.getElementById('regErr');
  if (!name || !email || !pass) { errEl.textContent = 'Барлық өрістерді толтырыңыз'; return; }
  if (pass.length < 6) { errEl.textContent = 'Пароль кем дегенде 6 таңба'; return; }
  errEl.textContent = 'Жүктелуде...';
  try {
    const data = await apiCall('/api/auth/register', 'POST', { name, email, password: pass });
    authToken = data.token;
    localStorage.setItem('kaz_token', authToken);
    loginSuccess(data.user);
    showToast('Тіркелу сәтті! KazAI-ға қош келдіңіз 🎉', 'success');
  } catch(e) { errEl.textContent = e.message; }
}

async function demoLogin() {
  const demoEmail = 'demo@kazai.kz';
  const demoPass  = 'demo123';
  try {
    let data;
    try {
      data = await apiCall('/api/auth/login', 'POST', { email: demoEmail, password: demoPass });
    } catch {
      data = await apiCall('/api/auth/register', 'POST', { name: 'Демо Пайдаланушы', email: demoEmail, password: demoPass });
    }
    authToken = data.token;
    localStorage.setItem('kaz_token', authToken);
    loginSuccess(data.user);
  } catch(e) {
    showToast('Демо кіру қатесі: ' + e.message, 'error');
  }
}

function googleLogin() { showToast('Google OAuth жақында қосылады', 'info'); }

function loginSuccess(user) {
  currentUser  = user;
  currentPlan  = user.plan || 'free';
  todayMsgs    = user.daily_count || 0;
  document.getElementById('authScreen').classList.add('hidden');
  document.getElementById('mainApp').style.display = 'flex';
  currentChatId = null;
  updateUserUI();
  loadHistoryFromServer();
  showToast(`Сәлеметсіз, ${user.name}! 👋`, 'success');
}

function doLogout() {
  closeModal('profileModal');
  document.getElementById('mainApp').style.display = 'none';
  document.getElementById('authScreen').classList.remove('hidden');
  authToken = null; currentUser = null; currentChatId = null;
  localStorage.removeItem('kaz_token');
  showToast('Сіз жүйеден шықтыңыз', 'info');
}

function updateUserUI() {
  if (!currentUser) return;
  const n = currentUser.name;
  const e = currentUser.email;
  document.getElementById('sbUser').textContent      = e;
  document.getElementById('hdrUserName').textContent = n.split(' ')[0];
  document.getElementById('profileName').textContent  = n;
  document.getElementById('profileEmail').textContent = e;
  document.getElementById('wTitle').textContent = `Сәлем, ${n.split(' ')[0]}! 👋`;
  updatePlanUI();
}

function updatePlanUI() {
  const p = currentPlan;
  const badge = document.getElementById('sbPlan');
  const prof  = document.getElementById('profilePlan');
  badge.className = `sb-plan-badge ${p}`;
  badge.textContent = p === 'free' ? 'Free · 20/күн' : p === 'pro' ? '✨ Pro · Шексіз' : '🔥 Ultra';
  prof.textContent  = p === 'free' ? 'Free' : '✨ ' + p.charAt(0).toUpperCase() + p.slice(1);
  if (p !== 'free') {
    document.getElementById('quotaBar').style.display = 'none';
  } else {
    document.getElementById('quotaBar').style.display = 'flex';
    updateQuota();
  }
}

function updateQuota() {
  const pct = Math.min(todayMsgs / DAILY_LIMIT * 100, 100);
  document.getElementById('quotaFill').style.width = pct + '%';
  document.getElementById('quotaTxt').textContent  = `${todayMsgs}/${DAILY_LIMIT} сұрақ`;
  document.getElementById('limitBanner').style.display = (pct >= 100 && currentPlan === 'free') ? 'flex' : 'none';
}

// ════════════════════════════════════
// MODALS
// ════════════════════════════════════
function openModal(id)  { document.getElementById(id).classList.add('show'); }
function closeModal(id) { document.getElementById(id).classList.remove('show'); }

document.querySelectorAll('.modal-overlay').forEach(m => {
  m.addEventListener('click', e => { if (e.target === m) m.classList.remove('show'); });
});

function selectPlan(p) {
  selectedPlan = p;
  document.querySelectorAll('.plan-card').forEach(c => c.classList.remove('selected'));
  document.getElementById(`plan${p.charAt(0).toUpperCase() + p.slice(1)}`).classList.add('selected');
}
selectPlan('pro');

function confirmPlan() {
  currentPlan = selectedPlan;
  localStorage.setItem('kaz_plan', currentPlan);
  if (currentUser) currentUser.plan = currentPlan;
  updatePlanUI();
  closeModal('plansModal');
  showToast(`${currentPlan.toUpperCase()} жоспары белсендірілді! 🎉`, 'success');
}

// ════════════════════════════════════
// SETTINGS
// ════════════════════════════════════
function setTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  document.getElementById('themeLight').classList.toggle('active', t === 'light');
  document.getElementById('themeDark').classList.toggle('active',  t === 'dark');
  const icon = document.getElementById('themeIcon');
  if (t === 'dark') {
    icon.innerHTML = '<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>';
  } else {
    icon.innerHTML = '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';
  }
  localStorage.setItem('kaz_theme', t);
}

function toggleThemeQuick() {
  const cur = document.documentElement.getAttribute('data-theme');
  setTheme(cur === 'dark' ? 'light' : 'dark');
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
    const style = document.createElement('style');
    style.id = 'noAnim';
    style.textContent = '*{animation:none!important;transition:none!important}';
    document.head.appendChild(style);
  } else {
    document.getElementById('noAnim')?.remove();
  }
}

function toggleCompact(el) {
  document.querySelectorAll('.msgs-inner').forEach(m =>
    m.style.gap = el.checked ? '10px' : '20px'
  );
}

// ════════════════════════════════════
// TOASTS
// ════════════════════════════════════
function showToast(msg, type = 'info') {
  const icons = { success: '✓', error: '✕', info: 'i' };
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<div class="toast-icon">${icons[type]}</div>${msg}`;
  document.getElementById('toasts').appendChild(t);
  setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 350); }, 3200);
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
  showToast('Жаңа чат бастады', 'info');
}

function loadHistory(el) {
  const chatId = el.dataset.chatId;
  if (chatId) loadHistoryChat(parseInt(chatId), el);
}

function delHistory(e, el) {
  e.stopPropagation();
  el.closest('.hi').remove();
  showToast('Тарихтан жойылды', 'info');
}

// ════════════════════════════════════
// SLASH COMMANDS
// ════════════════════════════════════
function onInput(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 130) + 'px';
  const v = el.value;
  const menu = document.getElementById('slashMenu');
  menu.classList.toggle('show', v === '/' || v.startsWith('/'));
}

function slashCmd(cmd) {
  document.getElementById('inp').value = '';
  document.getElementById('slashMenu').classList.remove('show');
  if (cmd === 'clear')  { clearChat();  return; }
  if (cmd === 'export') { exportChat(); return; }
  const btnMap = { gov: 'btn-gov', tutor: 'btn-tutor', det: 'btn-det' };
  if (btnMap[cmd]) setMod(cmd, document.getElementById(btnMap[cmd]));
  showToast(`/${cmd} режимі белсендірілді`, 'info');
}

document.addEventListener('click', e => {
  if (!e.target.closest('.input-outer')) document.getElementById('slashMenu').classList.remove('show');
});

// ════════════════════════════════════
// FALLBACK DATABASES
// ════════════════════════════════════
const govDB = [
  { k: ['ИИН','жеке сәйкестендіру'], r: `<strong>ИИН алу:</strong><br><br>1. egov.kz сайтына кіріңіз<br>2. «Жеке тұлғаларға» бөліміне өтіңіз<br>3. «ИИН алу» қызметін таңдаңыз<br>4. Жеке куәліктің деректерін енгізіңіз<br>5. SMS арқылы растаңыз<br><br>⏱ Мерзімі: 1 жұмыс күні · Тегін` },
  { k: ['ЭЦП','электрондық қолтаңба'], r: `<strong>ЭЦП алу:</strong><br><br>1. pki.gov.kz сайтына кіріңіз<br>2. «ЭЦП алу» батырмасын басыңыз<br>3. ИИН мен телефон нөмірін енгізіңіз<br>4. SMS кодын растаңыз<br>5. Сертификатты жүктеп алыңыз<br><br>⏱ Бірнеше минут · Тегін` },
  { k: ['жәрдемақы','балаға'], r: `<strong>Жәрдемақы рәсімдеу:</strong><br><br>1. egov.kz → «Әлеуметтік көмек»<br>2. «Балаға жәрдемақы» қызметін таңдаңыз<br>3. Туу туралы куәлікті жүктеңіз<br>4. Банктік шот нөмірін енгізіңіз<br><br>⏱ Қарастыру: 10 жұмыс күні` },
  { k: ['паспорт'], r: `<strong>Паспорт алу:</strong><br><br>1. egov.kz → «Құжаттар» → «Паспорт»<br>2. Өтінімді толтырыңыз<br>3. Мемлекеттік баж: 3 064 ₸<br>4. ЦОН-ға баруды тіркеңіз<br><br>⏱ Мерзімі: 15 жұмыс күні` },
  { k: ['дәрігер','поликлиника'], r: `<strong>Поликлиникаға тіркелу:</strong><br><br>1. egov.kz → «Денсаулық сақтау»<br>2. «Медициналық ұйымды таңдау»<br>3. Жақын орынды таңдаңыз<br><br>📱 eGov Mobile-да онлайн жазылуға болады` },
  { k: ['автокөлік','машина'], r: `<strong>Автокөлікті тіркеу:</strong><br><br>1. egov.kz → «Көлік»<br>2. Техпаспорт пен сату шартын дайындаңыз<br>3. Мемлекеттік баж: 1 532 ₸<br><br>⏱ Мерзімі: 1 жұмыс күні` }
];

const tutorDB = [
  { k: ['барды','бару'], r: `<strong>Өткен шақ жасалуы:</strong><br><br>❌ «Мен мектепке <strong>барды</strong>» — қате<br>✅ «Мен мектепке <strong>бардым</strong>» — дұрыс<br><br><strong>Жіктелуі:</strong><br>Мен → -дым/-дім · Сен → -дың/-дің<br>Ол → -ды/-ді · Біз → -дық/-дік` },
  { k: ['тексер','грамматика','қате'], r: `<strong>Грамматика тексеру:</strong><br><br>✅ Етістік жіктелуін тексеріңіз<br>✅ Септік жалғауларын тексеріңіз<br>✅ Бас әрпін ұмытпаңыз<br><br>💬 Нақты сөйлемді жіберсеңіз толық тексеремін!` },
  { k: ['айтылым','дыбыс'], r: `<strong>Ерекше дыбыстар:</strong><br><br>Ң — мұрын арқылы «нг»<br>Ғ — жұмсақ «г» · Қ — қатаң «к»<br>Ү — ерінді «ю» · Ұ — кең «у»` },
  { k: ['аудар','перевод'], r: `<strong>Аударма:</strong><br><br>Сәлем — Привет · Рақмет — Спасибо<br>Жақсы — Хорошо · Иә/Жоқ — Да/Нет<br>Сау болыңыз — До свидания · Мақтаймын — Молодец` }
];

const aiMarkers = ['сонымен қатар','атап айтқанда','moreover','furthermore','in conclusion','следует отметить','таким образом'];
const chipMap = {
  all:   ['Мемл. қызметтер','Қазақ тілі','ЖИ анықтауы'],
  gov:   ['ЭЦП алу','Жәрдемақы','Паспорт'],
  tutor: ['Сөйлемді тексер','Грамматика','Аударма'],
  det:   ['Басқа мәтін']
};

function route(t) {
  const s = t.toLowerCase();
  if (['жасанды ма','анықта','generated','ии жасады'].some(k => s.includes(k))) return 'det';
  if (govDB.some(e => e.k.some(k => s.includes(k.toLowerCase())))) return 'gov';
  if (tutorDB.some(e => e.k.some(k => s.includes(k.toLowerCase())))) return 'tutor';
  return 'all';
}

function respond(t, m) {
  if (m === 'gov') {
    for (const e of govDB)
      if (e.k.some(k => t.toLowerCase().includes(k.toLowerCase()))) return { r: e.r };
    return { r: `<strong>Мемлекеттік қызметтер:</strong><br><br>egov.kz-да 220+ қызмет бар.<br>Жиі: ИИН · ЭЦП · Жәрдемақы · Паспорт · Дәрігер<br><br>Нақтырақ сұраңыз!` };
  }
  if (m === 'tutor') {
    for (const e of tutorDB)
      if (e.k.some(k => t.toLowerCase().includes(k.toLowerCase()))) return { r: e.r };
    return { r: `<strong>Қазақ тілі:</strong><br><br>Мәтіні немесе сұрағыңызды нақтырақ жіберіңіз.<br>Грамматика · Жіктелуі · Аударма · Айтылым` };
  }
  if (m === 'det') return { det: true, score: detScore(t) };
  const lo = t.toLowerCase();
  if (['сәлем','салем','привет','hello'].some(g => lo.includes(g)))
    return { r: `Сәлеметсіз! Мен <strong>KazAI</strong> — қазақ тіліндегі ЖИ-көмекші.<br><br>Сізге қалай көмектесе аламын?<br>· 🏛️ Мемлекеттік қызметтер<br>· 📚 Қазақ тілі репетиторы<br>· 🔍 ЖИ контентін анықтау<br><br>Немесе / теріп командаларды қараңыз!` };
  return { r: `Сұрағыңызды қабылдадым. Нақтырақ жазыңыз немесе сол жақтан режимді таңдаңыз.<br><br>💡 <em>Кеңес: / теріп барлық командаларды көріңіз</em>` };
}

function detScore(t) {
  let s = 18 + Math.random() * 22;
  s += aiMarkers.filter(m => t.toLowerCase().includes(m)).length * 14;
  if (t.length > 200) s += 10;
  if (t.split('.').length > 5) s += 8;
  return Math.round(Math.min(s, 96));
}

// ── Markdown renderer ──
function renderMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code style="background:var(--s3);padding:1px 5px;border-radius:4px;font-family:monospace;font-size:13px">$1</code>')
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<div style="font-weight:700;font-size:14px;color:var(--hi);margin:10px 0 4px">$1</div>')
    .replace(/^## (.+)$/gm,  '<div style="font-weight:700;font-size:15px;color:var(--hi);margin:12px 0 5px">$1</div>')
    .replace(/^# (.+)$/gm,   '<div style="font-weight:700;font-size:17px;color:var(--hi);margin:12px 0 6px">$1</div>')
    .replace(/^[-•] (.+)$/gm, '<div style="display:flex;gap:7px;margin:3px 0"><span style="color:var(--blue);flex-shrink:0">•</span><span>$1</span></div>')
    .replace(/^(\d+)\. (.+)$/gm, '<div style="display:flex;gap:7px;margin:3px 0"><span style="color:var(--blue);font-weight:600;flex-shrink:0;min-width:16px">$1.</span><span>$2</span></div>')
    .replace(/^---$/gm, '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">')
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" style="color:var(--blue);text-decoration:underline">$1</a>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}

// ════════════════════════════════════
// MESSAGES
// ════════════════════════════════════
function addMsg(html, isUser, mType, isDet, score) {
  const w = document.getElementById('welcome');
  if (w) w.remove();
  const inner = document.getElementById('msgsInner');
  const t = new Date().toLocaleTimeString('kk-KZ', { hour: '2-digit', minute: '2-digit' });
  const d = document.createElement('div');
  d.className = `msg ${isUser ? 'user' : 'bot'}`;

  let bHTML = '';
  if (isDet && !isUser) {
    const ai  = score > 50;
    const col = ai ? '#fca5a5' : '#6ee7b7';
    const fc  = ai ? 'fai' : 'fhu';
    const v   = ai ? '⚠ Жасанды интеллект жасаған' : '✓ Адам жазған';
    bHTML = `Анықтау нәтижесі:<div class="det-card">
      <div class="det-hd">
        <span class="det-v" style="color:${col}">${v}</span>
        <span class="det-p" style="color:${col}">${score}%</span>
      </div>
      <div class="det-track"><div class="det-fill ${fc}" style="width:${score}%"></div></div>
      <div class="det-note">${ai ? `ЖИ белгілері анықталды. Ықтималдылық: ${score}%` : `Адам жазған сияқты. ЖИ ықтималдылығы: ${score}%`}</div>
    </div>`;
  } else {
    bHTML = isUser ? (html || '') : renderMarkdown(html || '');
  }

  const aM    = mType || mod;
  const chips = (!isUser && chipMap[aM])
    ? `<div class="chips">${chipMap[aM].map(c => `<span class="chip" onclick="quick('${c}')">${c}</span>`).join('')}</div>`
    : '';
  const actBtns = !isUser
    ? `<div class="msg-actions">
         <button class="msg-act-btn" onclick="copyMsg(this)">
           <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
             <rect x="9" y="9" width="13" height="13" rx="2"/>
             <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
           </svg>Көшіру</button>
         <button class="msg-act-btn" onclick="likeMsg(this)">👍</button>
         <button class="msg-act-btn" onclick="dislikeMsg(this)">👎</button>
       </div>`
    : '';

  if (isUser) {
    d.innerHTML = `<div class="msg-row"><div class="bubble">${bHTML}</div></div>
                   <div class="mtime">${t}</div>`;
  } else {
    d.innerHTML = `<div class="msg-row">
                     <div class="bot-av"><img src="${AV}" alt=""></div>
                     <div><div class="bubble">${bHTML}</div>${chips}${actBtns}</div>
                   </div>
                   <div class="mtime" style="padding-left:36px">${t}</div>`;
  }
  inner.appendChild(d);

  const wrap = document.getElementById('msgsWrap');
  if (document.getElementById('toggleScroll')?.checked) wrap.scrollTop = wrap.scrollHeight;

  msgCount++;
  totalTokens += Math.round((html || '').length / 4);
  document.getElementById('statMsgs').textContent   = msgCount;
  document.getElementById('statTokens').textContent = totalTokens > 999 ? Math.round(totalTokens / 1000) + 'k' : totalTokens;
  document.getElementById('statDays').textContent   = 1;

  if (isUser && currentPlan === 'free') {
    todayMsgs++;
    localStorage.setItem('kaz_today', todayMsgs);
    updateQuota();
  }
}

function addTyping() {
  const w = document.getElementById('welcome');
  if (w) w.remove();
  const inner = document.getElementById('msgsInner');
  const d = document.createElement('div');
  d.className = 'msg bot'; d.id = 'typing';
  d.innerHTML = `<div class="msg-row">
    <div class="bot-av"><img src="${AV}" alt=""></div>
    <div class="tbub"><span></span><span></span><span></span></div>
  </div>`;
  inner.appendChild(d);
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
    const body = { text: txt, module: mod, chat_id: currentChatId };
    const data = await apiCall('/api/chat', 'POST', body);
    rmTyping();

    if (!currentChatId && data.chat_id) {
      currentChatId = data.chat_id;
      addToSidebarHistory(txt, currentChatId);
    }

    const resp = data.response;
    if (resp.verdict) {
      addMsg(null, false, 'det', true, resp.score);
    } else {
      addMsg(resp.answer || resp.text || '...', false, mod);
    }

    if (data.usage) {
      todayMsgs = data.usage.today || todayMsgs + 1;
      localStorage.setItem('kaz_today', todayMsgs);
      updateQuota();
    }
  } catch(e) {
    rmTyping();
    console.warn('Backend error, using fallback:', e.message);
    _fallbackRespond(txt, f);
  }

  document.getElementById('sendBtn').disabled = false;
}

function _fallbackRespond(txt, f) {
  if (f) { addMsg(null, false, 'det', true, detScore(txt || f.name)); return; }
  const active = mod === 'all' ? route(txt) : mod;
  const res    = respond(txt, active);
  if (res.det) addMsg(null, false, 'det', true, res.score);
  else addMsg(res.r, false, active);
  todayMsgs++;
  localStorage.setItem('kaz_today', todayMsgs);
  updateQuota();
}

// ── File upload (image) ──
function onFile(e) {
  file = e.target.files[0];
  if (!file) return;
  document.getElementById('fname').textContent = file.name;
  document.getElementById('fprev').classList.add('show');
  setMod('det', document.getElementById('btn-det'));
}

// ── Video upload ──
function onVideo(e) {
  const vfile = e.target.files[0];
  if (!vfile) return;
  showToast(`📹 Видео жүктелуде: ${vfile.name}`, 'info');
  setMod('det', document.getElementById('btn-det'));

  const formData = new FormData();
  formData.append('video', vfile);
  if (authToken) formData.append('token', authToken);

  addMsg(`📹 Видео: ${vfile.name}`, true);
  addTyping();

  fetch(API_URL + '/api/detect/video', {
    method: 'POST',
    headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {},
    body: formData
  })
  .then(r => r.json())
  .then(data => {
    rmTyping();
    const score = data.score ?? Math.round(30 + Math.random() * 50);
    addMsg(null, false, 'det', true, score);
  })
  .catch(() => {
    rmTyping();
    addMsg(null, false, 'det', true, Math.round(30 + Math.random() * 50));
    showToast('Серверге қосылу мүмкін болмады, локальды нәтиже', 'info');
  });
}

function clearFile() {
  file = null;
  document.getElementById('fprev').classList.remove('show');
  document.getElementById('finp').value = '';
}

function addToSidebarHistory(txt, chatId) {
  const li = document.createElement('div');
  li.className = 'hi';
  li.dataset.chatId = chatId;
  li.innerHTML = `<div class="hd"></div>
    <span>${txt.substring(0, 28)}${txt.length > 28 ? '…' : ''}</span>
    <span class="hi-del" onclick="delHistory(event,this)">✕</span>`;
  li.onclick = () => loadHistoryChat(chatId, li);
  const hist = document.getElementById('histList');
  hist.insertBefore(li, hist.firstChild);
  if (hist.children.length > 10) hist.lastChild.remove();
}

function quick(t) { document.getElementById('inp').value = t; send(); }
function onKey(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }

function setMod(m, el, keepChat = false) {
  mod = m;
  document.querySelectorAll('.sb-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  const cfg = modeCfg[m];
  const dot = document.getElementById('modeDot');
  dot.style.background  = cfg.color;
  dot.style.boxShadow   = `0 0 6px ${cfg.color}`;
  document.getElementById('modeLbl').textContent    = cfg.label;
  document.getElementById('inp').placeholder        = cfg.hint;
  if (!keepChat && currentChatId !== null) {
    currentChatId = null;
    clearChatMessages();
  }
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
  const inner = document.getElementById('msgsInner');
  inner.innerHTML = '';
  const w = document.createElement('div');
  w.className = 'welcome'; w.id = 'welcome';
  w.innerHTML = `<div class="w-logo"><div class="w-avatar"><img src="${AV}" alt=""></div></div>
    <div>
      <div class="w-title">Жаңа чат</div>
      <div class="w-sub">Сұрағыңызды жазыңыз немесе режимді таңдаңыз.</div>
    </div>`;
  inner.appendChild(w);
}

function clearChat() {
  currentChatId = null;
  clearChatMessages();
  showToast('Чат тазаланды', 'info');
}

// ════════════════════════════════════
// HISTORY
// ════════════════════════════════════
async function loadHistoryFromServer() {
  if (!authToken) return;
  try {
    const chats = await apiCall('/api/history');
    const hist  = document.getElementById('histList');
    hist.innerHTML = '';
    chats.slice(0, 10).forEach(c => {
      const li = document.createElement('div');
      li.className = 'hi';
      li.dataset.chatId = c.id;
      li.innerHTML = `<div class="hd"></div><span>${c.title}</span>
        <span class="hi-del" onclick="delHistoryServer(event,this,${c.id})">✕</span>`;
      li.onclick = () => loadHistoryChat(c.id, li);
      hist.appendChild(li);
    });
  } catch(e) { console.warn('History load error:', e.message); }
}

async function loadHistoryChat(chatId, el) {
  try {
    const msgs = await apiCall(`/api/history/${chatId}/messages`);
    currentChatId = chatId;
    const inner   = document.getElementById('msgsInner');
    inner.innerHTML = '';
    msgs.forEach(m => addMsg(m.content, m.role === 'user', m.module || mod));
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

// ── Message actions ──
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
  a.href     = 'data:text/plain;charset=utf-8,' + encodeURIComponent(txt);
  a.download = 'kazai-chat.txt';
  a.click();
  showToast('Чат жүктелді', 'success');
}

// ════════════════════════════════════
// INIT
// ════════════════════════════════════
const savedTheme = localStorage.getItem('kaz_theme') || 'dark';
setTheme(savedTheme);
setMod('all', document.getElementById('btn-all'), true);

if (authToken) {
  apiCall('/api/auth/me').then(user => {
    loginSuccess(user);
  }).catch(e => {
    console.warn('Auto-login failed:', e.message);
    if (e.message && (e.message.includes('401') || e.message.includes('Unauthorized'))) {
      authToken = null;
      localStorage.removeItem('kaz_token');
    }
  });
}