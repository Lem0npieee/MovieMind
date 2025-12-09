/**
 * MovieMind - 前端主应用程序
 */

// API 基础 URL
const API_BASE_URL = 'http://localhost:5000/api';
const AUTH_STORAGE_KEY = 'moviemind_user';
const THEME_STORAGE_KEY = 'moviemind_theme';

// 当前状态
let currentPage = 1;
let currentFilters = {};
let currentUser = null;
const accountButton = document.getElementById('account-display');
const accountName = document.getElementById('account-name');
const accountDropdown = document.getElementById('account-dropdown');
const accountHomeBtn = document.getElementById('account-home');
const accountLogoutBtn = document.getElementById('account-logout');

/**
 * 初始化应用
 */
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initNavigation();
    initFilters();
    initSearch();
    initAISearch();
    initRecommend();
    initAuth();
    loadMovies();
    loadGenres();
});

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

/**
 * 应用主题
 */
function applyTheme(theme) {
    const root = document.documentElement;
    const toggleBtn = document.getElementById('theme-toggle');
    
    if (theme === 'light') {
        root.setAttribute('data-theme', 'light');
        if (toggleBtn) {
            toggleBtn.querySelector('.icon').textContent = '☀️';
            toggleBtn.setAttribute('data-tooltip', '切换到迷影模式');
        }
    } else {
        root.removeAttribute('data-theme');
        if (toggleBtn) {
            toggleBtn.querySelector('.icon').textContent = '🌙';
            toggleBtn.setAttribute('data-tooltip', '切换到明亮模式');
        }
    }
}

/**
 * 导航功能
 */
function initNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');
    const pageSections = document.querySelectorAll('.page-section');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetPage = e.currentTarget.dataset.page;
            if (!targetPage) return;

            // 更新导航状态
            navLinks.forEach(l => l.classList.remove('active'));
            e.currentTarget.classList.add('active');

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
        const country = document.getElementById('filter-country').value;
        const yearRange = document.getElementById('filter-year').value;
        const ratingRange = document.getElementById('filter-rating').value;

        currentFilters = { genre };
        
        // 国家/地区筛选
        if (country) {
            currentFilters.country = country;
        }
        
        // 解析评分区间
        if (ratingRange) {
            if (ratingRange.includes('+')) {
                // 9.8+ 表示9.8以上
                currentFilters.min_rating = parseFloat(ratingRange.replace('+', ''));
            } else if (ratingRange.includes('-')) {
                // 8.0-8.3 表示区间
                const [min, max] = ratingRange.split('-').map(parseFloat);
                currentFilters.min_rating = min;
                currentFilters.max_rating = max;
            }
        }

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
        document.getElementById('filter-country').value = '';
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
    interpretationDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>正在将自然语言转换为 SQL 并执行查询...</p></div>';
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
                <p><strong>查询理解:</strong> ${data.query_info.interpretation}</p>
                ${data.query_info.generated_sql ? `<p style="font-size: 0.9rem; color: #636e72; margin-top: 0.5rem; word-break: break-all;"><strong>生成的SQL:</strong> <code>${data.query_info.generated_sql}</code></p>` : ''}
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
 * 初始化AI推荐功能
 */
function initRecommend() {
    document.getElementById('btn-recommend').addEventListener('click', () => {
        const query = document.getElementById('recommend-query').value.trim();
        if (query) {
            performRecommend(query);
        }
    });

    // 示例查询按钮
    document.querySelectorAll('.example-btn-recommend').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const query = e.target.textContent;
            document.getElementById('recommend-query').value = query;
            performRecommend(query);
        });
    });
}

/**
 * AI 智能推荐
 */
async function performRecommend(query) {
    const resultDiv = document.getElementById('recommend-result');
    const interpretationDiv = document.getElementById('recommend-interpretation');
    const moviesDiv = document.getElementById('recommend-movies');

    resultDiv.style.display = 'block';
    interpretationDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>AI 正在理解你的需求并推荐最适合的电影...</p></div>';
    moviesDiv.innerHTML = '';

    try {
        const response = await fetch(`${API_BASE_URL}/ai-recommend`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query })
        });

        const data = await response.json();

        if (data.success) {
            // 格式化推荐理由，处理分点显示
            let reasoningHtml = '';
            if (data.recommendation_info.reasoning) {
                const reasoning = data.recommendation_info.reasoning
                    .replace(/(\d+\.\s*《)/g, '<br>$1')  // 在数字编号前换行
                    .replace(/；(\d+)/g, '；<br>$1')     // 在分号+数字前换行
                    .trim();
                reasoningHtml = `<p style="font-size: 0.9rem; color: #636e72; margin-top: 0.5rem; line-height: 1.8;"><strong>推荐理由:</strong> ${reasoning}</p>`;
            }
            
            interpretationDiv.innerHTML = `
                <p><strong>AI 理解:</strong> ${data.recommendation_info.interpretation}</p>
                ${reasoningHtml}
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
            interpretationDiv.innerHTML = `<p style="color: red;">推荐失败: ${data.error}</p>`;
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
    updateAccountDisplay();

    setupAccountDropdown();

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

function setupAccountDropdown() {
    if (!accountButton || !accountDropdown) return;

    const closeDropdown = () => accountDropdown.classList.remove('open');

    accountButton.addEventListener('click', (e) => {
        e.stopPropagation();
        if (!currentUser) {
            window.location.href = 'auth.html';
            return;
        }
        accountDropdown.classList.toggle('open');
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
            currentUser = null;
            saveUserToStorage(null);
            updateAuthStatus();
            updateAccountDisplay();
            window.location.href = 'auth.html';
        });
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
        updateAccountDisplay();
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
        updateAccountDisplay();
        showAuthMessage('success', `欢迎回来，${currentUser.username}!`);
    } catch (error) {
        showAuthMessage('error', error.message || '登录失败，请稍后重试');
    }
}

function handleLogout() {
    currentUser = null;
    saveUserToStorage(null);
    updateAuthStatus();
    updateAccountDisplay();
    showAuthMessage('success', '已成功退出登录');
}

function updateAccountDisplay() {
    if (!accountButton) return;

    const labelTarget = accountName || accountButton;
    const label = currentUser && currentUser.username ? currentUser.username : '点击登录';

    if (labelTarget === accountButton) {
        accountButton.textContent = label;
    } else {
        accountName.textContent = label;
    }
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
            console.log('Statistics data:', data.data);
            console.log('Country distribution:', data.data.country_distribution);
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
        const yearChart = new Chart(ctx1, {
            type: 'bar',
            data: {
                labels: stats.year_distribution.map(d => d.decade),
                datasets: [{
                    label: '电影数量',
                    data: stats.year_distribution.map(d => d.count),
                    backgroundColor: 'rgba(0, 184, 148, 0.7)'
                }]
            },
            options: {
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const decade = stats.year_distribution[index].decade;
                        
                        // 映射年代标签到筛选值
                        const decadeMapping = {
                            '1950年前': '1900-1949',
                            '1950s': '1950-1959',
                            '1960s': '1960-1969',
                            '1970s': '1970-1979',
                            '1980s': '1980-1989',
                            '1990s': '1990-1999',
                            '2000s': '2000-2009',
                            '2010s': '2010-2019',
                            '2020s': '2020-2029'
                        };
                        
                        const yearRange = decadeMapping[decade];
                        if (yearRange) {
                            // 跳转到首页并设置筛选条件
                            const navLinks = document.querySelectorAll('.nav-link');
                            const pageSections = document.querySelectorAll('.page-section');
                            
                            // 切换到首页
                            navLinks.forEach(l => l.classList.remove('active'));
                            document.querySelector('[data-page="home"]').classList.add('active');
                            pageSections.forEach(section => section.classList.remove('active'));
                            document.getElementById('page-home').classList.add('active');
                            
                            // 设置年代筛选条件
                            document.getElementById('filter-year').value = yearRange;
                            
                            // 触发筛选
                            document.getElementById('btn-filter').click();
                            
                            // 滚动到顶部
                            window.scrollTo({ top: 0, behavior: 'smooth' });
                        }
                    }
                }
            }
        });
        // 添加鼠标悬停样式提示
        ctx1.canvas.style.cursor = 'pointer';
    }

    // 类型分布图表
    if (stats.genre_distribution) {
        const ctx2 = document.getElementById('chart-genre').getContext('2d');
        const genreChart = new Chart(ctx2, {
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
            },
            options: {
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const genreName = stats.genre_distribution[index].name;
                        
                        // 跳转到首页并设置筛选条件
                        const navLinks = document.querySelectorAll('.nav-link');
                        const pageSections = document.querySelectorAll('.page-section');
                        
                        // 切换到首页
                        navLinks.forEach(l => l.classList.remove('active'));
                        document.querySelector('[data-page="home"]').classList.add('active');
                        pageSections.forEach(section => section.classList.remove('active'));
                        document.getElementById('page-home').classList.add('active');
                        
                        // 设置类型筛选条件
                        document.getElementById('filter-genre').value = genreName;
                        
                        // 触发筛选
                        document.getElementById('btn-filter').click();
                        
                        // 滚动到顶部
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                    }
                }
            }
        });
        // 添加鼠标悬停样式提示
        ctx2.canvas.style.cursor = 'pointer';
    }

    // 评分分布图表 - 4个固定区间
    if (stats.rating_distribution) {
        const ctx3 = document.getElementById('chart-rating').getContext('2d');
        const ratingChart = new Chart(ctx3, {
            type: 'bar',
            data: {
                labels: stats.rating_distribution.map(d => d.range),
                datasets: [{
                    label: '电影数量',
                    data: stats.rating_distribution.map(d => d.count),
                    backgroundColor: '#0984e3',
                    borderColor: '#0652a1',
                    borderWidth: 1
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const ratingRange = stats.rating_distribution[index].range;
                        
                        // 跳转到首页并设置筛选条件
                        const navLinks = document.querySelectorAll('.nav-link');
                        const pageSections = document.querySelectorAll('.page-section');
                        
                        // 切换到首页
                        navLinks.forEach(l => l.classList.remove('active'));
                        document.querySelector('[data-page="home"]').classList.add('active');
                        pageSections.forEach(section => section.classList.remove('active'));
                        document.getElementById('page-home').classList.add('active');
                        
                        // 设置评分筛选条件
                        document.getElementById('filter-rating').value = ratingRange;
                        
                        // 触发筛选
                        document.getElementById('btn-filter').click();
                        
                        // 滚动到顶部
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                    }
                }
            }
        });
        // 添加鼠标悬停样式提示
        ctx3.canvas.style.cursor = 'pointer';
    }

    // 国家/地区分布图表
    if (stats.country_distribution) {
        const ctx4 = document.getElementById('chart-country').getContext('2d');
        const countryChart = new Chart(ctx4, {
            type: 'doughnut',
            data: {
                labels: stats.country_distribution.map(d => d.country),
                datasets: [{
                    data: stats.country_distribution.map(d => d.count),
                    backgroundColor: [
                        '#e74c3c', '#3498db', '#2ecc71', '#f39c12',
                        '#9b59b6', '#1abc9c', '#e67e22', '#34495e',
                        '#95a5a6', '#d35400'
                    ]
                }]
            },
            options: {
                plugins: {
                    legend: {
                        position: 'right'
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const countryName = stats.country_distribution[index].country;
                        
                        // 跳转到首页并设置筛选条件
                        const navLinks = document.querySelectorAll('.nav-link');
                        const pageSections = document.querySelectorAll('.page-section');
                        
                        // 切换到首页
                        navLinks.forEach(l => l.classList.remove('active'));
                        document.querySelector('[data-page="home"]').classList.add('active');
                        pageSections.forEach(section => section.classList.remove('active'));
                        document.getElementById('page-home').classList.add('active');
                        
                        // 设置国家筛选条件
                        document.getElementById('filter-country').value = countryName;
                        
                        // 触发筛选
                        document.getElementById('btn-filter').click();
                        
                        // 滚动到顶部
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                    }
                }
            }
        });
        // 添加鼠标悬停样式提示
        ctx4.canvas.style.cursor = 'pointer';
    }

    // 导演作品排行图表
    if (stats.director_ranking) {
        const ctx5 = document.getElementById('chart-director').getContext('2d');
        const directorChart = new Chart(ctx5, {
            type: 'bar',
            data: {
                labels: stats.director_ranking.map(d => d.name),
                datasets: [{
                    label: '作品数量',
                    data: stats.director_ranking.map(d => d.count),
                    backgroundColor: 'rgba(155, 89, 182, 0.7)',
                    borderColor: 'rgba(155, 89, 182, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y',
                maintainAspectRatio: false,
                scales: {
                    x: {
                        beginAtZero: true
                    },
                    y: {
                        ticks: {
                            font: {
                                size: 11
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const directorName = stats.director_ranking[index].name;
                        window.location.href = `celebrity.html?name=${encodeURIComponent(directorName)}&from=stats`;
                    }
                }
            }
        });
        // 添加鼠标悬停样式提示
        ctx5.canvas.style.cursor = 'pointer';
    }

    // 演员出镜排行图表
    if (stats.actor_ranking) {
        const ctx6 = document.getElementById('chart-actor').getContext('2d');
        const actorChart = new Chart(ctx6, {
            type: 'bar',
            data: {
                labels: stats.actor_ranking.map(d => d.name),
                datasets: [{
                    label: '出镜次数',
                    data: stats.actor_ranking.map(d => d.count),
                    backgroundColor: 'rgba(231, 76, 60, 0.7)',
                    borderColor: 'rgba(231, 76, 60, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y',
                maintainAspectRatio: false,
                scales: {
                    x: {
                        beginAtZero: true
                    },
                    y: {
                        ticks: {
                            font: {
                                size: 11
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const actorName = stats.actor_ranking[index].name;
                        window.location.href = `celebrity.html?name=${encodeURIComponent(actorName)}&from=stats`;
                    }
                }
            }
        });
        // 添加鼠标悬停样式提示
        ctx6.canvas.style.cursor = 'pointer';
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
