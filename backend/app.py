"""
MovieMind - 主应用入口
基于 Flask 的豆瓣 Top 250 电影智能检索系统
"""
import sys
sys.path.append('..')
from flask import Flask, jsonify, request
from flask_cors import CORS
from config import Config
from database.db_manager import DatabaseManager
from utils.intro_loader import get_movie_introduction
import logging

# 初始化 Flask 应用
app = Flask(__name__)
app.config.from_object(Config)

# 启用跨域访问，开发阶段允许所有来源访问 /api/*
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=False)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 初始化数据库管理器
db_manager = DatabaseManager()


def serialize_user(user: dict) -> dict:
    """格式化用户信息，便于前端展示"""
    if not user:
        return {}

    def _serialize_value(value):
        return value.isoformat() if hasattr(value, 'isoformat') else value

    return {
        'user_id': user.get('user_id'),
        'username': user.get('username'),
        'email': user.get('email'),
        'created_at': _serialize_value(user.get('created_at')),
        'last_login': _serialize_value(user.get('last_login'))
    }


@app.route('/')
def index():
    """首页路由"""
    return jsonify({
        'message': 'Welcome to MovieMind API',
        'version': '1.0.0',
        'endpoints': {
            'movies': '/api/movies',
            'movie_detail': '/api/movies/<id>',
            'search': '/api/search',
            'ai_search': '/api/ai-search',
            'genres': '/api/genres',
            'celebrities': '/api/celebrities',
            'register': '/api/auth/register',
            'login': '/api/auth/login'
        }
    })


@app.route('/api/auth/register', methods=['POST'])
def register_user():
    """注册新用户"""
    try:
        data = request.get_json() or {}
        username = (data.get('username') or '').strip()
        password = (data.get('password') or '').strip()
        email = (data.get('email') or '').strip()

        if not username or not password or not email:
            return jsonify({'success': False, 'error': '用户名、邮箱和密码均不能为空'}), 400

        if len(password) < 6:
            return jsonify({'success': False, 'error': '密码至少需要 6 个字符'}), 400

        if db_manager.get_user_by_username(username):
            return jsonify({'success': False, 'error': '该用户名已被注册'}), 409

        user = db_manager.create_user(username, password, email)
        return jsonify({'success': True, 'data': serialize_user(user)})
    except Exception as e:
        logger.error(f"注册用户失败: {str(e)}")
        return jsonify({'success': False, 'error': '注册失败，请稍后重试'}), 500


@app.route('/api/auth/login', methods=['POST'])
def login_user():
    """用户登录"""
    try:
        data = request.get_json() or {}
        username = (data.get('username') or '').strip()
        password = (data.get('password') or '').strip()

        if not username or not password:
            return jsonify({'success': False, 'error': '请输入用户名和密码'}), 400

        user = db_manager.verify_user_credentials(username, password)
        if not user:
            return jsonify({'success': False, 'error': '用户名或密码不正确'}), 401

        return jsonify({'success': True, 'data': serialize_user(user)})
    except Exception as e:
        logger.error(f"用户登录失败: {str(e)}")
        return jsonify({'success': False, 'error': '登录失败，请稍后重试'}), 500


@app.route('/api/movies', methods=['GET'])
def get_movies():
    """获取电影列表（支持分页和筛选）"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        genre = request.args.get('genre', None)
        year_start = request.args.get('year_start', None, type=int)
        year_end = request.args.get('year_end', None, type=int)
        min_rating = request.args.get('min_rating', None, type=float)
        
        movies, total = db_manager.get_movies(
            page=page,
            per_page=per_page,
            genre=genre,
            year_start=year_start,
            year_end=year_end,
            min_rating=min_rating
        )
        
        return jsonify({
            'success': True,
            'data': movies,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
    except Exception as e:
        logger.error(f"获取电影列表失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/movies/<int:movie_id>', methods=['GET'])
def get_movie_detail(movie_id):
    """获取电影详情"""
    try:
        movie = db_manager.get_movie_by_id(movie_id)
        if movie:
            introduction = get_movie_introduction(str(movie.get('douban_id')))
            movie['introduction'] = introduction or movie.get('description') or ''
            return jsonify({'success': True, 'data': movie})
        else:
            return jsonify({'success': False, 'error': '电影不存在'}), 404
    except Exception as e:
        logger.error(f"获取电影详情失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/search', methods=['GET'])
def search_movies():
    """搜索电影（关键词搜索）"""
    try:
        keyword = request.args.get('keyword', '')
        if not keyword:
            return jsonify({'success': False, 'error': '请提供搜索关键词'}), 400
        
        movies = db_manager.search_movies(keyword)
        return jsonify({'success': True, 'data': movies})
    except Exception as e:
        logger.error(f"搜索电影失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai-search', methods=['POST'])
def ai_search():
    """AI 智能搜索（自然语言转 SQL）"""
    try:
        data = request.get_json()
        user_input = data.get('query', '')
        
        if not user_input:
            return jsonify({'success': False, 'error': '请提供搜索内容'}), 400
        
        # TODO: 集成 DEEPSEEK API 进行自然语言处理
        result = db_manager.ai_search(user_input)
        
        return jsonify({
            'success': True,
            'data': result['movies'],
            'query_info': {
                'original_query': user_input,
                'generated_sql': result.get('sql', ''),
                'interpretation': result.get('interpretation', '')
            }
        })
    except Exception as e:
        logger.error(f"AI 搜索失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/genres', methods=['GET'])
def get_genres():
    """获取所有电影类型"""
    try:
        genres = db_manager.get_all_genres()
        return jsonify({'success': True, 'data': genres})
    except Exception as e:
        logger.error(f"获取类型列表失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/celebrities', methods=['GET'])
def get_celebrities():
    """获取影人列表"""
    try:
        role = request.args.get('role', None)  # 导演/演员/编剧
        celebrities = db_manager.get_celebrities(role=role)
        return jsonify({'success': True, 'data': celebrities})
    except Exception as e:
        logger.error(f"获取影人列表失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reviews/<int:movie_id>', methods=['GET'])
def get_reviews(movie_id):
    """获取电影评论"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        reviews, total = db_manager.get_reviews(movie_id, page, per_page)
        
        return jsonify({
            'success': True,
            'data': reviews,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total
            }
        })
    except Exception as e:
        logger.error(f"获取评论失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reviews/<int:movie_id>', methods=['POST'])
def create_review(movie_id):
    """新增用户评论"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        rating = data.get('rating')
        comment = (data.get('comment') or '').strip()

        if user_id is None:
            return jsonify({'success': False, 'error': '请先登录后再发表评论'}), 401

        try:
            rating_value = int(round(float(rating)))
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': '评分必须是数字'}), 400

        if rating_value < 0 or rating_value > 5:
            return jsonify({'success': False, 'error': '评分需在 0-5 之间'}), 400

        if not comment:
            return jsonify({'success': False, 'error': '评论内容不能为空'}), 400

        review = db_manager.create_review(movie_id, user_id, rating_value, comment)
        return jsonify({'success': True, 'data': review})
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        logger.error(f"创建评论失败: {str(e)}")
        return jsonify({'success': False, 'error': '发表评论失败，请稍后再试'}), 500


@app.route('/api/stats', methods=['GET'])
def get_statistics():
    """获取统计数据（用于数据可视化）"""
    try:
        stats = db_manager.get_statistics()
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        logger.error(f"获取统计数据失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/celebrities/<path:name>', methods=['GET'])
def get_celebrity_detail(name):
    """获取影人详情及其参与的所有电影"""
    try:
        from urllib.parse import unquote
        # URL 解码中文名字
        decoded_name = unquote(name)
        
        if not decoded_name:
            return jsonify({'success': False, 'error': '请提供影人姓名'}), 400
        
        celebrity = db_manager.get_celebrity_by_name(decoded_name)
        
        if not celebrity:
            return jsonify({'success': False, 'error': f'未找到影人 "{decoded_name}" 的相关信息'}), 404
        
        return jsonify({'success': True, 'data': celebrity})
    except Exception as e:
        logger.error(f"获取影人详情失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': '资源不存在'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': '服务器内部错误'}), 500


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
