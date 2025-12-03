/**
 * Celebrity Detail Page - 影人详情页
 */

const API_BASE_URL = 'http://localhost:5000/api';
const PLACEHOLDER_POSTER = 'https://via.placeholder.com/240x360?text=No+Image';
const THEME_STORAGE_KEY = 'moviemind_theme';

// 从 URL 获取影人名字
const params = new URLSearchParams(window.location.search);
const celebrityName = params.get('name');

const loadingContainer = document.getElementById('loading-container');
const celebrityHero = document.getElementById('celebrity-hero');
const worksContainer = document.getElementById('works-container');
const emptyState = document.getElementById('empty-state');
const errorMessage = document.getElementById('error-message');

// 初始化主题
initTheme();

// 加载影人信息
if (!celebrityName) {
    showError('缺少影人姓名参数，请从电影详情页点击影人名字进入。');
} else {
    loadCelebrityDetail(celebrityName);
}

/**
 * 加载影人详情
 */
async function loadCelebrityDetail(name) {
    try {
        const encodedName = encodeURIComponent(name);
        const response = await fetch(`${API_BASE_URL}/celebrities/${encodedName}`);
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.error || '影人信息加载失败');
        }

        renderCelebrity(result.data);
    } catch (error) {
        console.error('加载影人信息失败:', error);
        showError(error.message || '加载影人信息失败，请稍后重试。');
    }
}

/**
 * 渲染影人信息
 */
function renderCelebrity(data) {
    // 隐藏加载状态
    loadingContainer.style.display = 'none';
    
    // 显示影人信息
    celebrityHero.style.display = 'block';
    worksContainer.style.display = 'block';

    // 设置页面标题
    document.title = `${data.name} - 影人详情 - MovieMind`;

    // 渲染名字
    document.getElementById('celebrity-name').textContent = data.name;

    // 渲染职业
    const rolesText = data.roles.join(' · ');
    document.getElementById('celebrity-roles').textContent = rolesText;

    // 渲染统计信息
    const directorCount = data.as_director ? data.as_director.length : 0;
    const actorCount = data.as_actor ? data.as_actor.length : 0;
    const statsText = `参与 ${data.total_movies} 部作品` +
        (directorCount > 0 ? `（导演 ${directorCount} 部` : '') +
        (actorCount > 0 ? (directorCount > 0 ? `，演员 ${actorCount} 部）` : `（演员 ${actorCount} 部）`) : (directorCount > 0 ? '）' : ''));
    document.getElementById('celebrity-stats').textContent = statsText;

    // 渲染作为导演的作品
    if (data.as_director && data.as_director.length > 0) {
        const directorWorks = document.getElementById('director-works');
        directorWorks.style.display = 'block';
        document.getElementById('director-count').textContent = `(${data.as_director.length})`;
        renderMovieGrid(data.as_director, 'director-movies-grid');
    }

    // 渲染作为演员的作品
    if (data.as_actor && data.as_actor.length > 0) {
        const actorWorks = document.getElementById('actor-works');
        actorWorks.style.display = 'block';
        document.getElementById('actor-count').textContent = `(${data.as_actor.length})`;
        renderMovieGrid(data.as_actor, 'actor-movies-grid');
    }
}

/**
 * 渲染电影网格
 */
function renderMovieGrid(movies, containerId) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';

    movies.forEach(movie => {
        const card = createMovieCard(movie);
        container.appendChild(card);
    });
}

/**
 * 创建电影卡片
 */
function createMovieCard(movie) {
    const card = document.createElement('div');
    card.className = 'movie-card';
    card.onclick = () => {
        window.location.href = `movie_detail.html?id=${movie.movie_id}`;
    };

    const posterUrl = movie.poster_url || PLACEHOLDER_POSTER;
    const rating = movie.rating ? parseFloat(movie.rating).toFixed(1) : 'N/A';

    card.innerHTML = `
        <img src="${posterUrl}" 
             alt="${movie.cn_title}" 
             class="movie-poster"
             onerror="this.src='${PLACEHOLDER_POSTER}'">
        <div class="movie-info">
            <div class="movie-rank">No.${movie.rank}</div>
            <div class="movie-title">${movie.cn_title}</div>
            <div class="movie-year">${movie.year || '未知'}</div>
            <div class="movie-rating">${rating}</div>
        </div>
    `;

    return card;
}

/**
 * 显示错误状态
 */
function showError(message) {
    loadingContainer.style.display = 'none';
    celebrityHero.style.display = 'none';
    worksContainer.style.display = 'none';
    emptyState.style.display = 'block';
    errorMessage.textContent = message;
}

/**
 * 获取名字首字母
 */
function getInitials(name = '') {
    const clean = name.trim();
    if (!clean) return '?';
    
    // 英文名：取前两个单词的首字母
    if (/^[A-Za-z ]+$/.test(clean)) {
        const parts = clean.split(' ').filter(Boolean);
        return parts.slice(0, 2).map(part => part[0]).join('').toUpperCase();
    }
    
    // 中文名：取前两个字
    return clean.slice(0, 2);
}

/**
 * 主题切换功能
 */
function initTheme() {
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY) || 'dark';
    applyTheme(savedTheme);

    const toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(newTheme);
            localStorage.setItem(THEME_STORAGE_KEY, newTheme);
            
            toggleBtn.style.transform = 'scale(0.9) rotate(180deg)';
            setTimeout(() => {
                toggleBtn.style.transform = '';
            }, 300);
        });
    }
}

function applyTheme(theme) {
    const root = document.documentElement;
    const toggleBtn = document.getElementById('theme-toggle');
    
    if (theme === 'light') {
        root.setAttribute('data-theme', 'light');
        if (toggleBtn) {
            toggleBtn.querySelector('.icon').textContent = '☀️';
        }
    } else {
        root.removeAttribute('data-theme');
        if (toggleBtn) {
            toggleBtn.querySelector('.icon').textContent = '🌙';
        }
    }
}
