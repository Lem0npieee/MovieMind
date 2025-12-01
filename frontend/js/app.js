/**
 * MovieMind - 前端主应用程序
 */

// API 基础 URL
const API_BASE_URL = 'http://localhost:5000/api';
const AUTH_STORAGE_KEY = 'moviemind_user';

// 当前状态
let currentPage = 1;
let currentFilters = {};
let currentUser = null;

/**
 * 初始化应用
 */
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initFilters();
    initSearch();
    initAISearch();
    initAuth();
    loadMovies();
    loadGenres();
});

/**
 * 导航功能
 */
function initNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');
    const pageSections = document.querySelectorAll('.page-section');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetPage = e.target.dataset.page;

            // 更新导航状态
            navLinks.forEach(l => l.classList.remove('active'));
            e.target.classList.add('active');

            // 切换页面
            pageSections.forEach(section => {
                section.classList.remove('active');
            });
            document.getElementById(`page-${targetPage}`).classList.add('active');

            // 加载相应页面的数据
            if (targetPage === 'stats') {
                loadStatistics();
            }
        });
    });
}

/**
 * 初始化筛选功能
 */
function initFilters() {
    document.getElementById('btn-filter').addEventListener('click', () => {
        const genre = document.getElementById('filter-genre').value;
        const yearRange = document.getElementById('filter-year').value;
        const minRating = document.getElementById('filter-rating').value;

        currentFilters = { genre, minRating };

        if (yearRange) {
            const [start, end] = yearRange.split('-');
            currentFilters.year_start = start;
            currentFilters.year_end = end;
        }

        currentPage = 1;
        loadMovies();
    });

    document.getElementById('btn-reset').addEventListener('click', () => {
        document.getElementById('filter-genre').value = '';
        document.getElementById('filter-year').value = '';
        document.getElementById('filter-rating').value = '';
        currentFilters = {};
        currentPage = 1;
        loadMovies();
    });
}

/**
 * 初始化搜索功能
 */
function initSearch() {
    document.getElementById('btn-keyword-search').addEventListener('click', () => {
        const keyword = document.getElementById('keyword-search').value.trim();
        if (keyword) {
            searchMovies(keyword);
        }
    });

    document.getElementById('keyword-search').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const keyword = e.target.value.trim();
            if (keyword) {
                searchMovies(keyword);
            }
        }
    });
}

/**
 * 初始化 AI 搜索功能
 */
function initAISearch() {
    document.getElementById('btn-ai-search').addEventListener('click', () => {
        const query = document.getElementById('ai-query').value.trim();
        if (query) {
            performAISearch(query);
        }
    });

    // 示例查询按钮
    document.querySelectorAll('.example-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const query = e.target.textContent;
            document.getElementById('ai-query').value = query;
            performAISearch(query);
        });
    });
}

/**
 * 加载电影列表
 */
async function loadMovies() {
    showLoading(true);

    const params = new URLSearchParams({
        page: currentPage,
        per_page: 20,
        ...currentFilters
    });

    try {
        const response = await fetch(`${API_BASE_URL}/movies?${params}`);
        const data = await response.json();

        if (data.success) {
            displayMovies(data.data);
            displayPagination(data.pagination);
        } else {
            showError('加载电影失败: ' + data.error);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    } finally {
        showLoading(false);
    }
}

/**
 * 显示电影列表
 */
function displayMovies(movies) {
    const grid = document.getElementById('movies-grid');
    grid.innerHTML = '';

    if (movies.length === 0) {
        grid.innerHTML = '<p style="text-align: center; grid-column: 1/-1; padding: 2rem;">没有找到符合条件的电影</p>';
        return;
    }

    movies.forEach(movie => {
        const card = createMovieCard(movie);
        grid.appendChild(card);
    });
}

/**
 * 创建电影卡片
 */
function createMovieCard(movie) {
    const card = document.createElement('div');
    card.className = 'movie-card';
    card.onclick = () => window.location.href = `movie_detail.html?id=${movie.movie_id}`;

    card.innerHTML = `
        <img src="${movie.poster_url || 'https://via.placeholder.com/180x270?text=No+Image'}" 
             alt="${movie.cn_title}" 
             class="movie-poster">
        <div class="movie-info">
            <div class="movie-rank">No.${movie.rank}</div>
            <div class="movie-title">${movie.cn_title}</div>
            <div class="movie-year">${movie.year || '未知'}</div>
            <div class="movie-rating">${movie.rating || 'N/A'}</div>
        </div>
    `;

    return card;
}

/**
 * 显示分页
 */
function displayPagination(pagination) {
    const container = document.getElementById('pagination');
    container.innerHTML = '';

    const { page, total_pages } = pagination;

    // 上一页按钮
    if (page > 1) {
        const prevBtn = document.createElement('button');
        prevBtn.textContent = '‹ 上一页';
        prevBtn.onclick = () => {
            currentPage--;
            loadMovies();
        };
        container.appendChild(prevBtn);
    }

    // 页码按钮
    const startPage = Math.max(1, page - 2);
    const endPage = Math.min(total_pages, page + 2);

    for (let i = startPage; i <= endPage; i++) {
        const pageBtn = document.createElement('button');
        pageBtn.textContent = i;
        pageBtn.className = i === page ? 'active' : '';
        pageBtn.onclick = () => {
            currentPage = i;
            loadMovies();
        };
        container.appendChild(pageBtn);
    }

    // 下一页按钮
    if (page < total_pages) {
        const nextBtn = document.createElement('button');
        nextBtn.textContent = '下一页 ›';
        nextBtn.onclick = () => {
            currentPage++;
            loadMovies();
        };
        container.appendChild(nextBtn);
    }
}

/**
 * 加载电影类型列表
 */
async function loadGenres() {
    try {
        const response = await fetch(`${API_BASE_URL}/genres`);
        const data = await response.json();

        if (data.success) {
            const select = document.getElementById('filter-genre');
            data.data.forEach(genre => {
                const option = document.createElement('option');
                option.value = genre.name;
                option.textContent = `${genre.name} (${genre.movie_count})`;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('加载类型失败:', error);
    }
}

/**
 * 搜索电影
 */
async function searchMovies(keyword) {
    showLoading(true);

    try {
        const response = await fetch(`${API_BASE_URL}/search?keyword=${encodeURIComponent(keyword)}`);
        const data = await response.json();

        if (data.success) {
            displayMovies(data.data);
            document.getElementById('pagination').innerHTML = '';
        } else {
            showError('搜索失败: ' + data.error);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    } finally {
        showLoading(false);
    }
}

/**
 * AI 智能搜索
 */
async function performAISearch(query) {
    const resultDiv = document.getElementById('ai-result');
    const interpretationDiv = document.getElementById('ai-interpretation');
    const moviesDiv = document.getElementById('ai-movies');

    resultDiv.style.display = 'block';
    interpretationDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>AI 正在分析您的需求...</p></div>';
    moviesDiv.innerHTML = '';

    try {
        const response = await fetch(`${API_BASE_URL}/ai-search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query })
        });

        const data = await response.json();

        if (data.success) {
            interpretationDiv.innerHTML = `
                <p><strong>AI 理解:</strong> ${data.query_info.interpretation}</p>
                ${data.query_info.generated_sql ? `<p style="font-size: 0.9rem; color: #636e72; margin-top: 0.5rem;">SQL: <code>${data.query_info.generated_sql}</code></p>` : ''}
            `;

            if (data.data.length > 0) {
                data.data.forEach(movie => {
                    const card = createMovieCard(movie);
                    moviesDiv.appendChild(card);
                });
            } else {
                moviesDiv.innerHTML = '<p style="text-align: center; padding: 2rem;">未找到符合条件的电影</p>';
            }
        } else {
            interpretationDiv.innerHTML = `<p style="color: red;">搜索失败: ${data.error}</p>`;
        }
    } catch (error) {
        interpretationDiv.innerHTML = `<p style="color: red;">网络错误: ${error.message}</p>`;
    }
}

/**
 * 初始化账号管理
 */
function initAuth() {
    currentUser = loadUserFromStorage();
    updateAuthStatus();

    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegisterSubmit);
    }

    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLoginSubmit);
    }

    const logoutBtn = document.getElementById('btn-logout');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
}

function loadUserFromStorage() {
    try {
        const saved = localStorage.getItem(AUTH_STORAGE_KEY);
        return saved ? JSON.parse(saved) : null;
    } catch (error) {
        console.warn('读取本地用户数据失败', error);
        return null;
    }
}

function saveUserToStorage(user) {
    try {
        if (!user) {
            localStorage.removeItem(AUTH_STORAGE_KEY);
            return;
        }
        localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
    } catch (error) {
        console.warn('保存用户数据失败', error);
    }
}

function updateAuthStatus() {
    const statusText = document.getElementById('auth-status-text');
    const logoutBtn = document.getElementById('btn-logout');
    if (!statusText || !logoutBtn) return;

    if (currentUser) {
        const emailText = currentUser.email ? `（${currentUser.email}）` : '';
        statusText.textContent = `已登录：${currentUser.username}${emailText}`;
        logoutBtn.style.display = 'inline-flex';
    } else {
        statusText.textContent = '请先登录或注册以保存个性化数据';
        logoutBtn.style.display = 'none';
    }
}

function showAuthMessage(type, message) {
    const messageBox = document.getElementById('auth-message');
    if (!messageBox) {
        alert(message);
        return;
    }
    const typeClass = type === 'error' ? 'error' : type === 'success' ? 'success' : '';
    messageBox.className = `auth-message ${typeClass}`.trim();
    messageBox.textContent = message;
    messageBox.style.display = 'block';

    if (messageBox._hideTimer) {
        clearTimeout(messageBox._hideTimer);
    }
    messageBox._hideTimer = setTimeout(() => {
        messageBox.style.display = 'none';
    }, 4000);
}

async function handleRegisterSubmit(event) {
    event.preventDefault();
    const username = document.getElementById('register-username').value.trim();
    const email = document.getElementById('register-email').value.trim();
    const password = document.getElementById('register-password').value.trim();

    if (!username || !email || !password) {
        showAuthMessage('error', '请完整填写注册信息');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password })
        });

        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || '注册失败，请稍后重试');
        }

        currentUser = result.data;
        saveUserToStorage(currentUser);
        updateAuthStatus();
        event.target.reset();
        showAuthMessage('success', '注册成功，已自动登录！');
    } catch (error) {
        showAuthMessage('error', error.message || '注册失败，请稍后重试');
    }
}

async function handleLoginSubmit(event) {
    event.preventDefault();
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value.trim();

    if (!username || !password) {
        showAuthMessage('error', '请输入用户名和密码');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || '登录失败，请稍后重试');
        }

        currentUser = result.data;
        saveUserToStorage(currentUser);
        updateAuthStatus();
        showAuthMessage('success', `欢迎回来，${currentUser.username}!`);
    } catch (error) {
        showAuthMessage('error', error.message || '登录失败，请稍后重试');
    }
}

function handleLogout() {
    currentUser = null;
    saveUserToStorage(null);
    updateAuthStatus();
    showAuthMessage('success', '已成功退出登录');
}

/**
 * 显示电影详情
 */
async function showMovieDetail(movieId) {
    const modal = document.getElementById('movie-modal');
    const detailDiv = document.getElementById('movie-detail');

    modal.style.display = 'block';
    detailDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载中...</p></div>';

    try {
        const response = await fetch(`${API_BASE_URL}/movies/${movieId}`);
        const data = await response.json();

        if (data.success) {
            const movie = data.data;
            detailDiv.innerHTML = `
                <h2>${movie.cn_title}</h2>
                <p><strong>原名:</strong> ${movie.original_title || '未知'}</p>
                <p><strong>排名:</strong> No.${movie.rank}</p>
                <p><strong>评分:</strong> ⭐ ${movie.rating}</p>
                <p><strong>年份:</strong> ${movie.year}</p>
                <p><strong>导演:</strong> ${movie.directors || '未知'}</p>
                <p><strong>主演:</strong> ${movie.actors || '未知'}</p>
                <p><strong>类型:</strong> ${movie.genres ? movie.genres.join(' / ') : '未知'}</p>
                <p><strong>简介:</strong> ${movie.description || '暂无简介'}</p>
                <p><strong>评论数:</strong> ${movie.review_count || 0} 条</p>
            `;
        }
    } catch (error) {
        detailDiv.innerHTML = `<p style="color: red;">加载失败: ${error.message}</p>`;
    }

    // 关闭模态框
    document.querySelector('.close').onclick = () => {
        modal.style.display = 'none';
    };

    window.onclick = (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    };
}

/**
 * 加载统计数据
 */
async function loadStatistics() {
    try {
        const response = await fetch(`${API_BASE_URL}/stats`);
        const data = await response.json();

        if (data.success) {
            renderCharts(data.data);
        }
    } catch (error) {
        console.error('加载统计数据失败:', error);
    }
}

/**
 * 渲染图表
 */
function renderCharts(stats) {
    // 年代分布图表
    if (stats.year_distribution) {
        const ctx1 = document.getElementById('chart-year').getContext('2d');
        new Chart(ctx1, {
            type: 'bar',
            data: {
                labels: stats.year_distribution.map(d => d.decade),
                datasets: [{
                    label: '电影数量',
                    data: stats.year_distribution.map(d => d.count),
                    backgroundColor: 'rgba(0, 184, 148, 0.7)'
                }]
            }
        });
    }

    // 类型分布图表
    if (stats.genre_distribution) {
        const ctx2 = document.getElementById('chart-genre').getContext('2d');
        new Chart(ctx2, {
            type: 'pie',
            data: {
                labels: stats.genre_distribution.map(d => d.name),
                datasets: [{
                    data: stats.genre_distribution.map(d => d.count),
                    backgroundColor: [
                        '#00b894', '#0984e3', '#6c5ce7', '#fd79a8',
                        '#fdcb6e', '#e17055', '#74b9ff', '#a29bfe',
                        '#55efc4', '#ffeaa7'
                    ]
                }]
            }
        });
    }

    // 评分分布图表
    if (stats.rating_distribution) {
        const ctx3 = document.getElementById('chart-rating').getContext('2d');
        new Chart(ctx3, {
            type: 'line',
            data: {
                labels: stats.rating_distribution.map(d => d.rating_group + '分'),
                datasets: [{
                    label: '电影数量',
                    data: stats.rating_distribution.map(d => d.count),
                    borderColor: '#0984e3',
                    backgroundColor: 'rgba(9, 132, 227, 0.1)',
                    fill: true
                }]
            }
        });
    }
}

/**
 * 显示/隐藏加载动画
 */
function showLoading(show) {
    const loading = document.getElementById('loading');
    loading.style.display = show ? 'block' : 'none';
}

/**
 * 显示错误信息
 */
function showError(message) {
    alert(message);
}
