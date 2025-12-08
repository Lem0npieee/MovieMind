const API_BASE_URL = 'http://localhost:5000/api';
const AUTH_STORAGE_KEY = 'moviemind_user';

const authForm = document.getElementById('auth-form');
const titleEl = document.getElementById('form-title');
const subtitleEl = document.getElementById('form-subtitle');
const emailGroup = document.getElementById('email-group');
const submitBtn = document.getElementById('submit-btn');
const switchBtn = document.getElementById('switch-btn');
const switchTip = document.getElementById('switch-tip');
const messageEl = document.getElementById('auth-message');
const usernameInput = document.getElementById('username');
const emailInput = document.getElementById('email');
const passwordInput = document.getElementById('password');

let mode = 'login'; // 'login' | 'register'

function setMode(next) {
    mode = next;
    const isLogin = mode === 'login';
    titleEl.textContent = isLogin ? '登录账号' : '创建账号';
    subtitleEl.textContent = isLogin ? '欢迎回来，填写信息后继续' : '注册后即可参与评论互动';
    emailGroup.style.display = isLogin ? 'none' : 'flex';
    submitBtn.textContent = isLogin ? '登录' : '注册';
    switchTip.textContent = isLogin ? '还没有账号？' : '已经有账号？';
    switchBtn.textContent = isLogin ? '立即注册' : '直接登录';
    clearMessage();
}

function showMessage(type, text) {
    messageEl.className = `message ${type || ''}`.trim();
    messageEl.textContent = text || '';
}

function clearMessage() {
    showMessage('', '');
}

function saveUser(user) {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
}

switchBtn.addEventListener('click', () => {
    setMode(mode === 'login' ? 'register' : 'login');
});

authForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearMessage();
    submitBtn.disabled = true;

    const username = usernameInput.value.trim();
    const password = passwordInput.value.trim();
    const email = emailInput.value.trim();

    if (!username || !password || (!email && mode === 'register')) {
        showMessage('error', '请完整填写信息');
        submitBtn.disabled = false;
        return;
    }

    if (mode === 'register' && password.length < 6) {
        showMessage('error', '密码至少 6 位');
        submitBtn.disabled = false;
        return;
    }

    const endpoint = mode === 'login' ? '/auth/login' : '/auth/register';
    const payload = mode === 'login' ? { username, password } : { username, password, email };

    try {
        const res = await fetch(`${API_BASE_URL}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.error || '操作失败，请稍后重试');
        }
        saveUser(data.data);
        showMessage('success', mode === 'login' ? '登录成功，正在跳转...' : '注册成功，已自动登录');
        setTimeout(() => {
            window.location.href = 'index.html';
        }, 800);
    } catch (err) {
        showMessage('error', err.message || '操作失败，请稍后重试');
    } finally {
        submitBtn.disabled = false;
    }
});

// 初始模式
setMode('login');
