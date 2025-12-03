const API_BASE_URL = 'http://localhost:5000/api';
const PLACEHOLDER_POSTER = 'https://via.placeholder.com/240x360?text=No+Image';
const AUTH_STORAGE_KEY = 'moviemind_user';
const THEME_STORAGE_KEY = 'moviemind_theme';

let currentUser = null;
let reviewsData = [];
let currentReviewRating = 0;

const params = new URLSearchParams(window.location.search);
const movieId = params.get('id');

const loadingOverlay = document.getElementById('page-loading');
const introElement = document.getElementById('movie-intro');
const castGrid = document.getElementById('cast-grid');
const posterWrapper = document.querySelector('.poster-wrapper');
const posterImg = document.getElementById('movie-poster');
const posterFallback = document.getElementById('poster-fallback');
const reviewForm = document.getElementById('review-form');
const reviewMessage = document.getElementById('review-message');
const reviewCount = document.getElementById('review-count');
const reviewList = document.getElementById('review-list');
const reviewEmpty = document.getElementById('review-empty');
const reviewNotice = document.getElementById('review-form-notice');
const reviewRatingInput = document.getElementById('review-rating');
const reviewContentInput = document.getElementById('review-content');
const reviewSubmitBtn = document.getElementById('review-submit');
const ratingStars = document.querySelectorAll('.rating-star-btn');
const ratingHint = document.getElementById('review-rating-text');
const ratingStarsGroup = document.getElementById('review-stars');

// 初始化主题
initTheme();

if (!movieId) {
    showError('缺少电影 ID，请从首页选择电影进入详情页。');
} else {
    currentUser = loadUserFromStorage();
    updateReviewFormState();
    loadMovieDetail(movieId);
    loadReviews(movieId);
}

if (reviewForm) {
    reviewForm.addEventListener('submit', handleReviewSubmit);
}

initRatingStars();

async function loadMovieDetail(id) {
    try {
        const response = await fetch(`${API_BASE_URL}/movies/${id}`);
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || '电影详情加载失败');
        }
        renderMovieDetail(result.data);
    } catch (error) {
        console.error(error);
        showError(error.message || '加载电影详情失败');
    } finally {
        hideLoading();
    }
}

function renderMovieDetail(movie) {
    document.title = `${movie.cn_title} - MovieMind`;
    document.getElementById('movie-title').textContent = movie.cn_title;
    document.getElementById('movie-original-title').textContent = movie.original_title || '';
    document.getElementById('movie-rank').textContent = movie.rank ? `豆瓣TOP ${movie.rank}` : '豆瓣TOP250';
    const ratingNum = Number(movie.rating);
    document.getElementById('movie-rating').textContent = !isNaN(ratingNum) ? ratingNum.toFixed(1) : (movie.rating ? String(movie.rating) : '--');
    const ratingCount = movie.comment_count || movie.review_count || movie.reviewCount || 0;
    document.getElementById('movie-rating-count').textContent = ratingCount ? `${ratingCount} 人评价` : '';
    document.getElementById('movie-year').textContent = movie.year || '未知';
    document.getElementById('movie-duration').textContent = movie.durations || '—';
    document.getElementById('movie-language').textContent = movie.languages || '—';
    document.getElementById('movie-countries').textContent = movie.countries || '—';
    document.getElementById('movie-genres').textContent = formatArray(movie.genres);
    document.getElementById('movie-directors').textContent = formatArray(movie.directors);
    document.getElementById('movie-actors').textContent = formatArray(movie.actors);
    document.getElementById('movie-release').textContent = movie.release_date || '—';

    const tagsContainer = document.getElementById('movie-tags');
    tagsContainer.innerHTML = '';
    const genres = normalizeToArray(movie.genres);
    if (genres.length) {
        genres.forEach(tag => {
            const pill = document.createElement('span');
            pill.className = 'tag-pill';
            pill.textContent = tag;
            tagsContainer.appendChild(pill);
        });
    }

    introElement.textContent = movie.introduction?.trim() || movie.description?.trim() || '暂无剧情简介，稍后再来看看~';

    renderPoster(movie.poster_url, movie.cn_title);
    renderCast(normalizeToArray(movie.directors), normalizeToArray(movie.actors));
    updateLinks(movie);
}

function renderPoster(url, title) {
    const hasPoster = Boolean(url);
    const finalUrl = hasPoster ? url : PLACEHOLDER_POSTER;

    posterImg.onload = () => {
        posterFallback.style.display = 'none';
    };

    posterImg.onerror = () => {
        if (posterImg.src !== PLACEHOLDER_POSTER) {
            posterImg.src = PLACEHOLDER_POSTER;
            return;
        }
        posterFallback.style.display = 'flex';
    };

    posterFallback.style.display = hasPoster ? 'none' : 'flex';
    posterImg.alt = title || '电影海报';
    posterImg.src = finalUrl;
}

function renderCast(directors, actors) {
    castGrid.innerHTML = '';
    const items = [];

    directors.slice(0, 2).forEach(name => {
        items.push({ name, role: '导演' });
    });
    actors.slice(0, 6).forEach(name => {
        items.push({ name, role: '主演' });
    });

    if (!items.length) {
        const empty = document.createElement('p');
        empty.className = 'panel-subtitle';
        empty.textContent = '暂无演职人员信息';
        castGrid.appendChild(empty);
        return;
    }

    items.forEach((person) => {
        const card = document.createElement('div');
        card.className = 'cast-card';
        card.innerHTML = `
            <div class="cast-avatar">${getInitials(person.name)}</div>
            <div class="cast-name">${person.name}</div>
            <div class="cast-role">${person.role}</div>
        `;
        castGrid.appendChild(card);
    });
}

function updateLinks(movie) {
    const doubanLink = document.getElementById('douban-link');
    if (movie.douban_id) {
        doubanLink.href = `https://movie.douban.com/subject/${movie.douban_id}/`;
        doubanLink.textContent = '查看豆瓣详情';
    } else {
        doubanLink.href = '#';
        doubanLink.textContent = '等待豆瓣链接';
        doubanLink.classList.add('disabled');
    }
}

function formatArray(value) {
    if (!value) return '—';
    if (Array.isArray(value)) {
        return value.filter(Boolean).join(' / ') || '—';
    }
    return value;
}

function normalizeToArray(value) {
    if (!value) return [];
    if (Array.isArray(value)) return value.filter(Boolean);
    if (typeof value === 'string') {
        return value.split(/[,/]/).map(item => item.trim()).filter(Boolean);
    }
    return [];
}

function getInitials(name = '') {
    const clean = name.trim();
    if (!clean) return '—';
    if (/^[A-Za-z ]+$/.test(clean)) {
        const parts = clean.split(' ').filter(Boolean);
        return parts.slice(0, 2).map(part => part[0]).join('').toUpperCase();
    }
    return clean.slice(0, 2);
}

function showError(message) {
    const main = document.querySelector('.detail-main');
    main.innerHTML = `<div class="panel"><p class="panel-subtitle">${message}</p></div>`;
    hideLoading();
}

function hideLoading() {
    if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
    }
}

async function loadReviews(id) {
    if (!reviewList) return;
    try {
        const response = await fetch(`${API_BASE_URL}/reviews/${id}?per_page=30`);
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || '无法加载评论');
        }
        reviewsData = result.data || [];
        const total = result.pagination?.total ?? reviewsData.length;
        if (reviewCount) {
            reviewCount.textContent = `${total} 条观众评论`;
            reviewCount.dataset.count = total;
        }
        renderReviews();
    } catch (error) {
        console.error(error);
        if (reviewCount) {
            reviewCount.textContent = '评论加载失败';
        }
        if (reviewMessage) {
            showReviewMessage('error', error.message || '评论加载失败');
        }
    }
}

function renderReviews() {
    if (!reviewList) return;
    reviewList.innerHTML = '';

    if (!reviewsData.length) {
        if (reviewEmpty) reviewEmpty.style.display = 'block';
        return;
    }

    if (reviewEmpty) reviewEmpty.style.display = 'none';

    reviewsData.forEach(review => {
        const item = document.createElement('li');
        item.className = 'review-item';
        item.innerHTML = `
            <div class="review-meta">
                <span class="review-author">${review.username || '匿名用户'}</span>
                <div class="rating-display" aria-label="评分">
                    ${renderStarIcons(review.user_rating)}
                </div>
            </div>
            <p class="review-content">${escapeHtml(review.comment || '暂无内容')}</p>
            <div class="review-footer">
                <span>#${review.comment_id || review.review_id}</span>
                <span>${formatDate(review.created_at)}</span>
            </div>
        `;
        reviewList.appendChild(item);
    });
}

async function handleReviewSubmit(event) {
    event.preventDefault();
    if (!currentUser) {
        showReviewMessage('error', '请先登录再发表评论');
        return;
    }

    const ratingValue = currentReviewRating;
    const commentText = (reviewContentInput?.value || '').trim();

    if (isNaN(ratingValue) || ratingValue < 0 || ratingValue > 5) {
        showReviewMessage('error', '评分必须在 0-5 之间');
        return;
    }

    if (!commentText) {
        showReviewMessage('error', '评论内容不能为空');
        return;
    }

    showReviewMessage('info', '正在提交评论...');
    if (reviewSubmitBtn) {
        reviewSubmitBtn.disabled = true;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/reviews/${movieId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: currentUser.user_id,
                rating: ratingValue,
                comment: commentText
            })
        });

        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || '发表评论失败');
        }

        const newReview = result.data;
        reviewsData = [newReview, ...reviewsData];
        if (reviewCount) {
            const current = Number(reviewCount.dataset.count || reviewsData.length);
            const updated = current + 1;
            reviewCount.dataset.count = updated;
            reviewCount.textContent = `${updated} 条观众评论`;
        }
        renderReviews();
        reviewForm.reset();
        setReviewRating(0);
        showReviewMessage('success', '发布成功，感谢你的分享！');
    } catch (error) {
        console.error(error);
        showReviewMessage('error', error.message || '发表评论失败');
    } finally {
        if (reviewSubmitBtn) {
            reviewSubmitBtn.disabled = false;
        }
    }
}

function showReviewMessage(type, message) {
    if (!reviewMessage) return;
    reviewMessage.className = `review-message ${type === 'success' ? 'success' : type === 'error' ? 'error' : ''}`.trim();
    reviewMessage.textContent = message;
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

function updateReviewFormState() {
    if (!reviewNotice || !reviewSubmitBtn || !reviewRatingInput || !reviewContentInput) return;
    if (currentUser) {
        reviewNotice.textContent = `以 ${currentUser.username} 的身份发表评论`;
        reviewSubmitBtn.disabled = false;
        reviewRatingInput.disabled = false;
        reviewContentInput.disabled = false;
        setStarsDisabled(false);
    } else {
        reviewNotice.textContent = '登录后才能打分和发表评论';
        reviewSubmitBtn.disabled = true;
        reviewRatingInput.disabled = true;
        reviewContentInput.disabled = true;
        setStarsDisabled(true);
    }
}

function formatDate(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function initRatingStars() {
    if (!ratingStars.length) return;
    ratingStars.forEach(star => {
        star.addEventListener('click', () => {
            if (star.disabled) return;
            const value = Number(star.dataset.value);
            if (currentReviewRating === 1 && value === 1) {
                setReviewRating(0);
            } else {
                setReviewRating(value);
            }
        });
    });
    setReviewRating(0);
}

function setReviewRating(value) {
    currentReviewRating = Math.max(0, Math.min(5, Number(value) || 0));
    if (reviewRatingInput) {
        reviewRatingInput.value = currentReviewRating;
    }
    if (ratingHint) {
        ratingHint.textContent = `当前：${currentReviewRating} 星`;
    }
    if (ratingStarsGroup) {
        ratingStarsGroup.setAttribute('aria-valuenow', currentReviewRating);
    }
    ratingStars.forEach(star => {
        star.classList.toggle('active', Number(star.dataset.value) <= currentReviewRating);
    });
}

function setStarsDisabled(disabled) {
    ratingStars.forEach(star => {
        star.disabled = disabled;
        if (disabled) {
            star.classList.remove('active');
        } else {
            star.classList.toggle('active', Number(star.dataset.value) <= currentReviewRating);
        }
    });
}

function renderStarIcons(value) {
    const rating = Math.max(0, Math.min(5, Math.round(Number(value) || 0)));
    let html = '';
    for (let i = 1; i <= 5; i++) {
        const activeClass = i <= rating ? 'active' : '';
        html += `<span class="star-icon ${activeClass}">★</span>`;
    }
    return html;
}

// ========== 主题切换功能 ==========
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
        });
    }
}

function applyTheme(theme) {
    if (theme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        const icon = document.querySelector('#theme-toggle .icon');
        if (icon) icon.textContent = '☀️';
    } else {
        document.documentElement.removeAttribute('data-theme');
        const icon = document.querySelector('#theme-toggle .icon');
        if (icon) icon.textContent = '🌙';
    }
}