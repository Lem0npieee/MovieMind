const API_BASE_URL = 'http://localhost:5000/api';
const AUTH_STORAGE_KEY = 'moviemind_user';
const PLACEHOLDER_POSTER = 'https://via.placeholder.com/120x160?text=No+Image';

let currentUser = null;
const favState = { mode: 'recent', items: [], total: 0 };
const reviewState = { mode: 'recent', items: [], total: 0 };

const favListEl = document.getElementById('fav-list');
const favEmptyEl = document.getElementById('fav-empty');
const reviewListEl = document.getElementById('review-list');
const reviewEmptyEl = document.getElementById('review-empty');
const favEmptyDefaultText = favEmptyEl ? favEmptyEl.textContent : '';
const reviewEmptyDefaultText = reviewEmptyEl ? reviewEmptyEl.textContent : '';
const favToggleBtn = document.getElementById('view-all-fav');
const reviewToggleBtn = document.getElementById('view-all-review');
const usernameEl = document.getElementById('uh-username');
const levelEl = document.getElementById('uh-level');
const favCountEl = document.getElementById('uh-fav-count');
const reviewCountEl = document.getElementById('uh-review-count');
const lastActiveEl = document.getElementById('uh-last-active');

const accountButton = document.getElementById('account-display');
const accountNameEl = document.getElementById('account-name');
const accountDropdown = document.getElementById('account-dropdown');
const accountHomeBtn = document.getElementById('account-home');
const accountLogoutBtn = document.getElementById('account-logout');

(function init() {
    const params = new URLSearchParams(window.location.search);
    favState.mode = params.get('favorites') === 'all' ? 'all' : 'recent';
    reviewState.mode = params.get('reviews') === 'all' ? 'all' : 'recent';

    currentUser = loadUserFromStorage();
    if (!currentUser) {
        window.location.href = 'auth.html';
        return;
    }

    initAccountDropdown();
    hydrateUserHeader();
    bindControls();
    loadFavorites();
    loadReviews();
})();

function bindControls() {
    if (favToggleBtn) {
        favToggleBtn.addEventListener('click', () => {
            favState.mode = favState.mode === 'all' ? 'recent' : 'all';
            favToggleBtn.textContent = favState.mode === 'all' ? '返回概览' : '查看全部收藏';
            loadFavorites();
        });
        favToggleBtn.textContent = favState.mode === 'all' ? '返回概览' : '查看全部收藏';
    }

    if (reviewToggleBtn) {
        reviewToggleBtn.addEventListener('click', () => {
            reviewState.mode = reviewState.mode === 'all' ? 'recent' : 'all';
            reviewToggleBtn.textContent = reviewState.mode === 'all' ? '返回概览' : '查看全部评价';
            loadReviews();
        });
        reviewToggleBtn.textContent = reviewState.mode === 'all' ? '返回概览' : '查看全部评价';
    }
}

function hydrateUserHeader() {
    if (usernameEl) {
        usernameEl.textContent = currentUser.username || '未命名用户';
    }
    if (levelEl) {
        levelEl.textContent = currentUser.user_id ? `Lv${Math.max(1, Math.min(9, Number(currentUser.user_id) || 1))}` : 'Lv1';
    }
    if (lastActiveEl) {
        const ts = currentUser.last_login || currentUser.created_at;
        lastActiveEl.textContent = ts ? formatDate(ts) : '—';
    }
}

async function loadFavorites() {
    if (!currentUser || !favListEl) return;
    const limit = favState.mode === 'all' ? 200 : 6;
    const params = new URLSearchParams({ limit, offset: 0 });
    try {
        const res = await fetch(`${API_BASE_URL}/users/${currentUser.user_id}/favorites?${params}`);
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.error || '无法获取收藏');
        }
        favState.items = data.data || [];
        favState.total = data.total || favState.items.length;
        renderFavorites();
    } catch (err) {
        console.error(err);
        renderFavorites(true);
    }
}

async function loadReviews() {
    if (!currentUser || !reviewListEl) return;
    const limit = reviewState.mode === 'all' ? 200 : 6;
    const params = new URLSearchParams({ limit, offset: 0 });
    try {
        const res = await fetch(`${API_BASE_URL}/users/${currentUser.user_id}/reviews?${params}`);
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.error || '无法获取评价');
        }
        reviewState.items = data.data || [];
        reviewState.total = data.total || reviewState.items.length;
        renderReviews();
    } catch (err) {
        console.error(err);
        renderReviews(true);
    }
}

function renderFavorites(hasError = false) {
    favListEl.innerHTML = '';
    if (favCountEl) {
        favCountEl.textContent = hasError ? '—' : String(favState.total || 0);
    }

    const empty = hasError || !favState.items.length;
    if (favEmptyEl) {
        favEmptyEl.style.display = empty ? 'block' : 'none';
        favEmptyEl.textContent = hasError ? '收藏加载失败，请稍后重试' : favEmptyDefaultText;
    }
    if (empty) return;

    favState.items.forEach(item => {
        const card = document.createElement('article');
        card.className = 'item-card';
        card.innerHTML = `
            <img class="item-cover" src="${sanitizePoster(item.poster_url)}" alt="${item.cn_title || item.original_title || '电影海报'}" onerror="this.src='${PLACEHOLDER_POSTER}'" />
            <div class="item-body">
                <a href="movie_detail.html?id=${item.movie_id}" class="item-title">${item.cn_title || item.original_title || '未命名电影'}</a>
                <div class="item-sub">评分 ${formatRating(item.rating)} · ${item.year || '—'} · 收藏于 ${formatDate(item.created_at)}</div>
                ${item.rank ? `<div class="item-sub">豆瓣 TOP ${item.rank}</div>` : ''}
            </div>
        `;
        favListEl.appendChild(card);
    });
}

function renderReviews(hasError = false) {
    reviewListEl.innerHTML = '';
    if (reviewCountEl) {
        reviewCountEl.textContent = hasError ? '—' : String(reviewState.total || 0);
    }

    const empty = hasError || !reviewState.items.length;
    if (reviewEmptyEl) {
        reviewEmptyEl.style.display = empty ? 'block' : 'none';
        reviewEmptyEl.textContent = hasError ? '评价加载失败，请稍后重试' : reviewEmptyDefaultText;
    }
    if (empty) return;

    reviewState.items.forEach(item => {
        const card = document.createElement('article');
        card.className = 'item-card';
        card.innerHTML = `
            <img class="item-cover" src="${sanitizePoster(item.poster_url)}" alt="${item.cn_title || '电影海报'}" onerror="this.src='${PLACEHOLDER_POSTER}'" />
            <div class="item-body">
                <a href="movie_detail.html?id=${item.movie_id}" class="item-title">${item.cn_title || '未命名电影'}</a>
                <div class="item-sub">我的评分 ${formatRating(item.user_rating)} · 观影于 ${formatDate(item.created_at)}</div>
                <p class="item-sub" style="margin: 0; line-height: 1.5;">${escapeHtml(truncate(item.comment, 96)) || '暂无评论内容'}</p>
            </div>
        `;
        reviewListEl.appendChild(card);
    });
}

function sanitizePoster(url) {
    if (!url || typeof url !== 'string') return PLACEHOLDER_POSTER;
    return url;
}

function formatRating(value) {
    const num = Number(value);
    if (Number.isNaN(num)) return '--';
    return num % 1 === 0 ? `${num.toFixed(0)}` : num.toFixed(1);
}

function formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

function truncate(text, maxLen) {
    if (!text) return '';
    if (text.length <= maxLen) return text;
    return `${text.slice(0, maxLen)}...`;
}

function escapeHtml(text) {
    return (text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function loadUserFromStorage() {
    try {
        const saved = localStorage.getItem(AUTH_STORAGE_KEY);
        return saved ? JSON.parse(saved) : null;
    } catch (err) {
        console.warn('读取用户信息失败', err);
        return null;
    }
}

function initAccountDropdown() {
    if (!accountButton) return;
    accountNameEl.textContent = currentUser.username || '点击登录';

    const closeDropdown = () => accountDropdown && accountDropdown.classList.remove('open');

    accountButton.addEventListener('click', (e) => {
        e.stopPropagation();
        if (!currentUser) {
            window.location.href = 'auth.html';
            return;
        }
        if (accountDropdown) accountDropdown.classList.toggle('open');
    });

    document.addEventListener('click', closeDropdown);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeDropdown();
    });

    if (accountHomeBtn) {
        accountHomeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            closeDropdown();
            window.location.href = 'user_home.html';
        });
    }

    if (accountLogoutBtn) {
        accountLogoutBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            closeDropdown();
            try { localStorage.removeItem(AUTH_STORAGE_KEY); } catch (err) {}
            window.location.href = 'auth.html';
        });
    }
}
