// ════════════════════════════════════
// AUTH MODULE
// ChatGPT стиліндегі auth overlay
// ════════════════════════════════════

const Auth = (() => {

  // ── State ──
  let _token = localStorage.getItem('kaz_token') || null;
  let _user  = null;
  let _onLogin  = null;  // callback
  let _onLogout = null;  // callback

  // ── Public getters ──
  const getToken = () => _token;
  const getUser  = () => _user;
  const isLoggedIn = () => !!_token && !!_user;
  const isDemoMode = () => _user?.email === 'demo@kazai.kz';

  // ── Init ──
  function init(onLogin, onLogout) {
    _onLogin  = onLogin;
    _onLogout = onLogout;
    _renderOverlay();
    _bindEvents();

    // Автоматты кіру (токен бар болса)
    if (_token) {
      _autoLogin();
    } else {
      _showOverlay();
    }
  }

  // ── Auto login ──
  async function _autoLogin() {
    try {
      const data = await apiCall('/api/auth/me');
      _loginSuccess(data);
    } catch(e) {
      console.warn('Auto-login failed:', e.message);
      if (e.message.includes('401') || e.message.includes('422')) {
        _token = null;
        localStorage.removeItem('kaz_token');
      }
      _showOverlay();
    }
  }

  // ── Overlay render ──
  function _renderOverlay() {
    const el = document.createElement('div');
    el.id = 'authOverlay';
    el.innerHTML = `
      <div class="auth-card">
        <div class="auth-logo">
          <div class="auth-logo-av"><img id="authLogoAv" src="" alt=""></div>
          <div class="auth-logo-name">KazAI</div>
        </div>

        <div id="authStep1">
          <div class="auth-title">Қош келдіңіз</div>
          <div class="auth-sub">Кіріңіз немесе тіркеліңіз — тарих сақталады,<br>толық мүмкіндік ашылады.</div>

          <button class="auth-oauth-btn" id="btnGoogle">
            <svg width="18" height="18" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
            Google арқылы кіру
          </button>

          <div class="auth-divider"><span>немесе email арқылы</span></div>

          <div class="auth-forms-wrap">
            <!-- Email step -->
            <div id="emailStep">
              <label class="auth-label">Email</label>
              <input class="auth-inp" type="email" id="authEmail" placeholder="email@example.com">
              <div class="auth-error" id="authErr"></div>
              <button class="auth-submit" id="btnContinue">Жалғастыру →</button>
            </div>

            <!-- Password step (login) -->
            <div id="passStep" style="display:none">
              <button class="auth-back" id="btnBack">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
                <span id="backEmail"></span>
              </button>
              <label class="auth-label">Пароль</label>
              <input class="auth-inp" type="password" id="authPass" placeholder="••••••••" onkeydown="if(event.key==='Enter')Auth._submitLogin()">
              <div class="auth-error" id="passErr"></div>
              <button class="auth-submit" id="btnLogin">Кіру →</button>
              <div class="auth-switch">Аккаунт жоқ па? <a onclick="Auth._showRegister()">Тіркелу</a></div>
            </div>

            <!-- Register step -->
            <div id="regStep" style="display:none">
              <button class="auth-back" id="btnBackReg">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
                Артқа
              </button>
              <label class="auth-label">Аты-жөні</label>
              <input class="auth-inp" type="text" id="regName" placeholder="Аруана Сейткали">
              <label class="auth-label">Пароль</label>
              <input class="auth-inp" type="password" id="regPass" placeholder="Кем дегенде 6 таңба" onkeydown="if(event.key==='Enter')Auth._submitRegister()">
              <div class="auth-error" id="regErr"></div>
              <button class="auth-submit" id="btnRegister">Тіркелу →</button>
              <div class="auth-switch">Аккаунт бар ма? <a onclick="Auth._showLogin()">Кіру</a></div>
            </div>
          </div>

          <!-- Демо кнопка -->
          <button class="auth-demo" id="btnDemo">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            Тіркелмей демо режимде кіру
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(el);
  }

  // ── Bind events ──
  function _bindEvents() {
    document.getElementById('btnGoogle').onclick   = _googleLogin;
    document.getElementById('btnContinue').onclick = _checkEmail;
    document.getElementById('btnBack').onclick     = _showEmailStep;
    document.getElementById('btnBackReg').onclick  = _showEmailStep;
    document.getElementById('btnLogin').onclick    = _submitLogin;
    document.getElementById('btnRegister').onclick = _submitRegister;
    document.getElementById('btnDemo').onclick     = _demoLogin;

    document.getElementById('authEmail').onkeydown = (e) => {
      if(e.key === 'Enter') _checkEmail();
    };
  }

  // ── Show / hide overlay ──
  function _showOverlay() {
    const el = document.getElementById('authOverlay');
    if(el) el.classList.remove('hidden');
  }

  function _hideOverlay() {
    const el = document.getElementById('authOverlay');
    if(el) {
      el.classList.add('hidden');
      setTimeout(() => el.remove(), 300);
    }
  }

  // ── Email check → кіру немесе тіркелу бетіне ──
  async function _checkEmail() {
    const email = document.getElementById('authEmail').value.trim();
    const errEl = document.getElementById('authErr');
    if(!email || !email.includes('@')) { errEl.textContent = 'Жарамды email енгізіңіз'; return; }
    errEl.textContent = '';
    // Email бар болса → парольге өту, жоқ болса → тіркелуге
    // Қарапайым: email болса passStep, болмаса regStep
    // Бізде backend жоқ check үшін, сондықтан passStep шығарамыз
    document.getElementById('backEmail').textContent = email;
    _showPassStep();
  }

  function _showEmailStep() {
    document.getElementById('emailStep').style.display = '';
    document.getElementById('passStep').style.display = 'none';
    document.getElementById('regStep').style.display = 'none';
    document.getElementById('authErr').textContent = '';
    document.getElementById('passErr').textContent = '';
  }

  function _showPassStep() {
    document.getElementById('emailStep').style.display = 'none';
    document.getElementById('passStep').style.display = '';
    document.getElementById('regStep').style.display = 'none';
    setTimeout(() => document.getElementById('authPass')?.focus(), 50);
  }

  function _showRegister() {
    const email = document.getElementById('authEmail').value.trim();
    document.getElementById('emailStep').style.display = 'none';
    document.getElementById('passStep').style.display = 'none';
    document.getElementById('regStep').style.display = '';
    setTimeout(() => document.getElementById('regName')?.focus(), 50);
  }

  function _showLogin() { _showPassStep(); }

  // ── Login ──
  async function _submitLogin() {
    const email = document.getElementById('authEmail').value.trim();
    const pass  = document.getElementById('authPass').value;
    const errEl = document.getElementById('passErr');
    if(!pass){ errEl.textContent = 'Парольді енгізіңіз'; return; }
    errEl.textContent = 'Жүктелуде...';
    try {
      const data = await apiCall('/api/auth/login', 'POST', {email, password: pass});
      _token = data.token;
      localStorage.setItem('kaz_token', _token);
      _loginSuccess(data.user);
    } catch(e) {
      errEl.textContent = e.message === 'HTTP 401' ? 'Email немесе пароль қате' : e.message;
    }
  }

  // ── Register ──
  async function _submitRegister() {
    const email = document.getElementById('authEmail').value.trim();
    const name  = document.getElementById('regName').value.trim();
    const pass  = document.getElementById('regPass').value;
    const errEl = document.getElementById('regErr');
    if(!name){ errEl.textContent = 'Атыңызды енгізіңіз'; return; }
    if(pass.length < 6){ errEl.textContent = 'Пароль кем дегенде 6 таңба'; return; }
    errEl.textContent = 'Тіркелуде...';
    try {
      const data = await apiCall('/api/auth/register', 'POST', {name, email, password: pass});
      _token = data.token;
      localStorage.setItem('kaz_token', _token);
      _loginSuccess(data.user);
      showToast('Тіркелу сәтті! KazAI-ға қош келдіңіз 🎉', 'success');
    } catch(e) {
      errEl.textContent = e.message;
    }
  }

  // ── Demo login ──
  async function _demoLogin() {
    const e = 'demo@kazai.kz', p = 'demo123';
    try {
      let data;
      try {
        data = await apiCall('/api/auth/login', 'POST', {email: e, password: p});
      } catch {
        data = await apiCall('/api/auth/register', 'POST', {name: 'Демо Пайдаланушы', email: e, password: p});
      }
      _token = data.token;
      localStorage.setItem('kaz_token', _token);
      _loginSuccess(data.user);
      showToast('Демо режим — тарих сақталмайды', 'info');
    } catch(err) {
      showToast('Демо кіру қатесі: ' + err.message, 'error');
    }
  }

  // ── Google (placeholder) ──
  function _googleLogin() {
    showToast('Google OAuth жақында қосылады', 'info');
  }

  // ── Login success ──
  function _loginSuccess(user) {
    _user = user;
    _hideOverlay();
    _updateHeaderButtons();
    if (_onLogin) _onLogin(user);
  }

  // ── Logout ──
  function logout() {
    _token = null;
    _user  = null;
    localStorage.removeItem('kaz_token');
    _updateHeaderButtons();
    _renderOverlay();
    _bindEvents();
    _showOverlay();
    if (_onLogout) _onLogout();
    showToast('Сіз жүйеден шықтыңыз', 'info');
  }

  // ── Header кнопкаларын жаңарту ──
  // Кірген кезде: аты + logout
  // Шыққан кезде: Войти + Зарегистрироваться
  function _updateHeaderButtons() {
    const container = document.getElementById('hdrAuthArea');
    if (!container) return;

    if (_user) {
      // Кірген — пайдаланушы атын көрсет
      container.innerHTML = `
        <button class="hdr-user-label" onclick="openModal('profileModal')">
          ${_user.name.split(' ')[0]}
        </button>
      `;
    } else {
      // Шыққан — Войти / Зарегистрироваться кнопкалары
      container.innerHTML = `
        <div class="hdr-auth-btns">
          <button class="hdr-login-btn" onclick="Auth.showLoginOverlay()">Кіру</button>
          <button class="hdr-register-btn" onclick="Auth.showRegisterOverlay()">
            <span>Тіркелу</span>
          </button>
        </div>
      `;
    }
  }

  // ── Public: overlay-ді қолмен ашу ──
  function showLoginOverlay() {
    if (document.getElementById('authOverlay')) {
      document.getElementById('authOverlay').classList.remove('hidden');
    } else {
      _renderOverlay();
      _bindEvents();
    }
    _showEmailStep();
  }

  function showRegisterOverlay() {
    showLoginOverlay();
    // Email step-те тұрып, register-ге өтетін animation
    setTimeout(() => {
      document.getElementById('authEmail').value = '';
      _showRegister();
    }, 100);
  }

  // ── API helper (auth module үшін) ──
  async function apiCall(endpoint, method = 'GET', body = null) {
    const headers = {'Content-Type': 'application/json'};
    if (_token) headers['Authorization'] = `Bearer ${_token}`;
    const opts = {method, headers};
    if (body) opts.body = JSON.stringify(body);
    const res  = await fetch(endpoint, opts);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  // ── Public API ──
  return {
    init,
    logout,
    getToken,
    getUser,
    isLoggedIn,
    isDemoMode,
    showLoginOverlay,
    showRegisterOverlay,
    // Internal (HTML onclick үшін)
    _submitLogin,
    _submitRegister,
    _showRegister,
    _showLogin,
  };

})();