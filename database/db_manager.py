"""
数据库管理模块 - 负责所有数据库操作
"""
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import logging
from typing import List, Dict, Tuple, Optional
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import json
import time

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器 - 使用连接池管理数据库连接"""
    
    def __init__(self):
        """初始化数据库连接池"""
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                **Config.DB_CONFIG
            )
            logger.info("数据库连接池初始化成功")
        except Exception as e:
            logger.error(f"数据库连接池初始化失败: {str(e)}")
            raise
    
    def get_connection(self):
        """从连接池获取连接"""
        return self.connection_pool.getconn()
    
    def release_connection(self, conn):
        """释放连接回连接池"""
        self.connection_pool.putconn(conn)
    
    def execute_query(self, query: str, params: tuple = None, fetch_one: bool = False):
        """
        执行查询语句
        :param query: SQL 查询语句
        :param params: 查询参数
        :param fetch_one: 是否只返回一条记录
        :return: 查询结果
        """
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                if fetch_one:
                    result = cursor.fetchone()
                else:
                    result = cursor.fetchall()
                return result
        except Exception as e:
            logger.error(f"查询执行失败: {str(e)}\nSQL: {query}")
            raise
        finally:
            if conn:
                self.release_connection(conn)
    
    def execute_update(self, query: str, params: tuple = None):
        """
        执行更新语句（INSERT, UPDATE, DELETE）
        :param query: SQL 语句
        :param params: 参数
        :return: 影响的行数
        """
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"更新执行失败: {str(e)}\nSQL: {query}")
            raise
        finally:
            if conn:
                self.release_connection(conn)
    
    def get_movies(self, page: int = 1, per_page: int = 20, 
                   genre: str = None, year_start: int = None, 
                   year_end: int = None, min_rating: float = None) -> Tuple[List[Dict], int]:
        """
        获取电影列表（支持多条件筛选和分页）
        :return: (电影列表, 总数)
        """
        offset = (page - 1) * per_page
        
        # 构建查询条件
        conditions = []
        params = []
        
        if genre:
            conditions.append("EXISTS (SELECT 1 FROM movie_genre mg JOIN genre g ON mg.genre_id = g.genre_id WHERE mg.movie_id = m.movie_id AND g.name = %s)")
            params.append(genre)
        
        if year_start:
            conditions.append("m.year >= %s")
            params.append(year_start)
        
        if year_end:
            conditions.append("m.year <= %s")
            params.append(year_end)
        
        if min_rating:
            conditions.append("m.rating >= %s")
            params.append(min_rating)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # 查询总数
        count_query = f"SELECT COUNT(*) as total FROM movie m WHERE {where_clause}"
        count_result = self.execute_query(count_query, tuple(params), fetch_one=True)
        total = count_result['total'] if count_result else 0
        
        # 查询电影列表
        query = f"""
            SELECT m.movie_id, m.rank, m.cn_title, m.original_title, m.year,
                   m.rating, m.poster_url,
                   COALESCE(STRING_AGG(DISTINCT d.name, ', '), '') AS directors,
                   COALESCE(STRING_AGG(DISTINCT a.name, ', '), '') AS actors,
                   m.description
            FROM movie m
            LEFT JOIN movie_director md ON m.movie_id = md.movie_id
            LEFT JOIN director d ON md.director_id = d.director_id
            LEFT JOIN movie_actor ma ON m.movie_id = ma.movie_id
            LEFT JOIN actor a ON ma.actor_id = a.actor_id
            WHERE {where_clause}
            GROUP BY m.movie_id
            ORDER BY m.rank
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        movies = self.execute_query(query, tuple(params))
        
        return movies, total
    
    def get_movie_by_id(self, movie_id: int) -> Optional[Dict]:
        """获取电影详情"""
        query = """
            SELECT m.*,
                   COALESCE(ARRAY_AGG(DISTINCT g.name) FILTER (WHERE g.name IS NOT NULL), ARRAY[]::VARCHAR[]) AS genres,
                   COALESCE(ARRAY_AGG(DISTINCT d.name) FILTER (WHERE d.name IS NOT NULL), ARRAY[]::VARCHAR[]) AS directors,
                   COALESCE(ARRAY_AGG(DISTINCT a.name) FILTER (WHERE a.name IS NOT NULL), ARRAY[]::VARCHAR[]) AS actors,
                   COUNT(DISTINCT r.review_id) as review_count
            FROM movie m
            LEFT JOIN movie_genre mg ON m.movie_id = mg.movie_id
            LEFT JOIN genre g ON mg.genre_id = g.genre_id
            LEFT JOIN movie_director md ON m.movie_id = md.movie_id
            LEFT JOIN director d ON md.director_id = d.director_id
            LEFT JOIN movie_actor ma ON m.movie_id = ma.movie_id
            LEFT JOIN actor a ON ma.actor_id = a.actor_id
            LEFT JOIN review r ON m.movie_id = r.movie_id
            WHERE m.movie_id = %s
            GROUP BY m.movie_id
        """
        return self.execute_query(query, (movie_id,), fetch_one=True)
    
    def search_movies(self, keyword: str) -> List[Dict]:
        """关键词搜索电影"""
        query = """
            SELECT m.movie_id, m.rank, m.cn_title, m.original_title, m.year,
                   m.rating, m.poster_url,
                   COALESCE(STRING_AGG(DISTINCT d.name, ', '), '') AS directors,
                   COALESCE(STRING_AGG(DISTINCT a.name, ', '), '') AS actors
            FROM movie m
            LEFT JOIN movie_director md ON m.movie_id = md.movie_id
            LEFT JOIN director d ON md.director_id = d.director_id
            LEFT JOIN movie_actor ma ON m.movie_id = ma.movie_id
            LEFT JOIN actor a ON ma.actor_id = a.actor_id
            WHERE m.cn_title ILIKE %s 
               OR m.original_title ILIKE %s
               OR EXISTS (
                    SELECT 1 FROM movie_director md2
                    JOIN director d2 ON md2.director_id = d2.director_id
                    WHERE md2.movie_id = m.movie_id AND d2.name ILIKE %s
               )
               OR EXISTS (
                    SELECT 1 FROM movie_actor ma2
                    JOIN actor a2 ON ma2.actor_id = a2.actor_id
                    WHERE ma2.movie_id = m.movie_id AND a2.name ILIKE %s
               )
            GROUP BY m.movie_id
            ORDER BY m.rank
            LIMIT 50
        """
        search_pattern = f"%{keyword}%"
        return self.execute_query(query, (search_pattern, search_pattern, search_pattern, search_pattern))
    
    def ai_search(self, user_input: str) -> Dict:
        """
        AI 智能搜索（自然语言转 SQL）
        使用 DEEPSEEK API 理解用户查询并生成 SQL
        """
        try:
            # 如果没有API密钥，回退到关键词搜索
            if not Config.DEEPSEEK_API_KEY:
                logger.warning("DEEPSEEK API密钥未配置，使用关键词搜索")
                movies = self.search_movies(user_input)
                return {
                    'movies': movies,
                    'sql': f'SELECT * FROM movie WHERE cn_title ILIKE \'%{user_input}%\'',
                    'interpretation': f'关键词搜索: {user_input}'
                }
            
            # 构建prompt
            prompt = self._build_ai_search_prompt(user_input)
            
            # 调用DEEPSEEK API
            response = self._call_deepseek_api(prompt)
            
            if not response:
                # API调用失败，回退到关键词搜索
                logger.warning("DEEPSEEK API调用失败，使用关键词搜索")
                movies = self.search_movies(user_input)
                return {
                    'movies': movies,
                    'sql': f'SELECT * FROM movie WHERE cn_title ILIKE \'%{user_input}%\'',
                    'interpretation': f'关键词搜索: {user_input}'
                }
            
            # 解析AI响应
            sql_query, interpretation = self._parse_ai_response(response)
            
            if not sql_query:
                # 无法生成SQL，回退到关键词搜索
                logger.warning("无法生成SQL查询，使用关键词搜索")
                movies = self.search_movies(user_input)
                return {
                    'movies': movies,
                    'sql': f'SELECT * FROM movie WHERE cn_title ILIKE \'%{user_input}%\'',
                    'interpretation': f'关键词搜索: {user_input}'
                }
            
            # 执行生成的SQL查询
            movies = self._execute_ai_sql(sql_query)
            
            return {
                'movies': movies,
                'sql': sql_query,
                'interpretation': interpretation
            }
            
        except Exception as e:
            logger.error(f"AI搜索失败: {str(e)}")
            # 出错时回退到关键词搜索
            movies = self.search_movies(user_input)
            return {
                'movies': movies,
                'sql': f'SELECT * FROM movie WHERE cn_title ILIKE \'%{user_input}%\'',
                'interpretation': f'关键词搜索: {user_input}'
            }
    
    def ai_recommend(self, user_input: str) -> Dict:
        """
        AI 智能推荐（基于情感和场景）
        使用 DEEPSEEK API 理解用户的情感需求并推荐电影
        """
        try:
            # 如果没有API密钥，返回错误
            if not Config.DEEPSEEK_API_KEY:
                logger.warning("DEEPSEEK API密钥未配置")
                return {
                    'movies': [],
                    'interpretation': 'API密钥未配置',
                    'reasoning': '请配置DEEPSEEK_API_KEY环境变量'
                }
            
            # 构建推荐prompt
            prompt = self._build_recommend_prompt(user_input)
            
            # 调用DEEPSEEK API
            response = self._call_deepseek_api(prompt)
            
            if not response:
                logger.warning("DEEPSEEK API调用失败")
                return {
                    'movies': [],
                    'interpretation': 'API调用失败',
                    'reasoning': '无法连接到AI服务'
                }
            
            # 解析AI推荐响应
            movie_titles, interpretation, reasoning = self._parse_recommend_response(response)
            
            if not movie_titles:
                logger.warning("AI未返回推荐电影")
                return {
                    'movies': [],
                    'interpretation': interpretation or 'AI理解了你的需求',
                    'reasoning': reasoning or '但暂时没有找到合适的推荐'
                }
            
            # 根据电影名称从数据库查询
            movies = self._find_movies_by_titles(movie_titles)
            
            return {
                'movies': movies,
                'interpretation': interpretation,
                'reasoning': reasoning
            }
            
        except Exception as e:
            logger.error(f"AI推荐失败: {str(e)}")
            return {
                'movies': [],
                'interpretation': '推荐失败',
                'reasoning': str(e)
            }
    
    def get_all_genres(self) -> List[Dict]:
        """获取所有电影类型"""
        query = """
            SELECT g.genre_id, g.name, COUNT(mg.movie_id) as movie_count
            FROM genre g
            LEFT JOIN movie_genre mg ON g.genre_id = mg.genre_id
            GROUP BY g.genre_id, g.name
            ORDER BY movie_count DESC
        """
        return self.execute_query(query)
    
    def get_celebrities(self, role: str = None) -> List[Dict]:
        """获取影人列表"""
        role = (role or '').lower()
        if role in ('导演', 'director', 'directors'):
            query = """
                SELECT director_id AS id, name, 'director' AS role
                FROM director
                ORDER BY name
                LIMIT 100
            """
            return self.execute_query(query)
        if role in ('演员', 'actor', 'actors'):
            query = """
                SELECT actor_id AS id, name, 'actor' AS role
                FROM actor
                ORDER BY name
                LIMIT 100
            """
            return self.execute_query(query)

        query = """
            SELECT * FROM (
                SELECT director_id AS id, name, 'director' AS role
                FROM director
                ORDER BY name
                LIMIT 50
            ) d
            UNION ALL
            SELECT * FROM (
                SELECT actor_id AS id, name, 'actor' AS role
                FROM actor
                ORDER BY name
                LIMIT 50
            ) a
        """
        return self.execute_query(query)
    
    def get_reviews(self, movie_id: int, page: int = 1, per_page: int = 10) -> Tuple[List[Dict], int]:
        """获取电影评论"""
        offset = (page - 1) * per_page
        
        # 查询总数
        count_query = "SELECT COUNT(*) as total FROM review WHERE movie_id = %s"
        count_result = self.execute_query(count_query, (movie_id,), fetch_one=True)
        total = count_result['total'] if count_result else 0
        
        # 查询评论列表
        query = """
            SELECT 
                r.review_id,
                COALESCE(NULLIF(r.douban_review_id, ''), r.review_id::TEXT) AS comment_id,
                u.user_id,
                u.username,
                r.user_rating,
                r.comment,
                r.useful_count,
                r.created_at
            FROM review r
            JOIN "user" u ON r.user_id = u.user_id
            WHERE r.movie_id = %s
            ORDER BY CASE 
                WHEN r.douban_review_id ~ '^\\d+$' THEN r.douban_review_id::BIGINT
                ELSE r.review_id
            END DESC
            LIMIT %s OFFSET %s
        """
        reviews = self.execute_query(query, (movie_id, per_page, offset))
        
        return reviews, total

    def create_review(self, movie_id: int, user_id: int, rating: float, comment: str) -> Dict:
        """创建新的用户评论"""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # 确保电影存在
                cursor.execute("SELECT movie_id FROM movie WHERE movie_id = %s", (movie_id,))
                if not cursor.fetchone():
                    raise ValueError('电影不存在')

                # 查询用户信息
                cursor.execute('SELECT user_id, username FROM "user" WHERE user_id = %s', (user_id,))
                user = cursor.fetchone()
                if not user:
                    raise ValueError('用户不存在')

                rating_int = max(0, min(5, int(round(float(rating)))))

                generated_id = str(int(time.time() * 1000))
                cursor.execute(
                    '''
                    INSERT INTO review (
                        douban_review_id, movie_id, user_id, user_rating, comment,
                        useful_count, created_at, spoiler, status
                    )
                    VALUES (%s, %s, %s, %s, %s, 0, CURRENT_TIMESTAMP, NULL, 'published')
                    RETURNING review_id, douban_review_id, user_rating, comment, useful_count, created_at
                    ''',
                    (generated_id, movie_id, user_id, rating_int, comment)
                )
                review = cursor.fetchone()
                conn.commit()

                review['username'] = user['username']
                review['user_id'] = user['user_id']
                review['comment_id'] = review['douban_review_id'] or str(review['review_id'])
                return review
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"创建评论失败: {str(e)}")
            raise
        finally:
            if conn:
                self.release_connection(conn)
    
    def get_statistics(self) -> Dict:
        """获取统计数据（用于数据可视化）"""
        stats = {}
        
        # 年代分布
        year_query = """
            SELECT 
                CASE 
                    WHEN year < 1950 THEN '1950年前'
                    WHEN year < 1960 THEN '1950s'
                    WHEN year < 1970 THEN '1960s'
                    WHEN year < 1980 THEN '1970s'
                    WHEN year < 1990 THEN '1980s'
                    WHEN year < 2000 THEN '1990s'
                    WHEN year < 2010 THEN '2000s'
                    WHEN year < 2020 THEN '2010s'
                    ELSE '2020s'
                END as decade,
                COUNT(*) as count
            FROM movie
            GROUP BY decade
            ORDER BY decade
        """
        stats['year_distribution'] = self.execute_query(year_query)
        
        # 类型分布
        genre_query = """
            SELECT g.name, COUNT(mg.movie_id) as count
            FROM genre g
            JOIN movie_genre mg ON g.genre_id = mg.genre_id
            GROUP BY g.genre_id, g.name
            ORDER BY count DESC
            LIMIT 10
        """
        stats['genre_distribution'] = self.execute_query(genre_query)
        
        # 评分分布 - 按0.3分区间
        rating_query = """
            SELECT rating
            FROM movie
            WHERE rating IS NOT NULL
        """
        rating_data = self.execute_query(rating_query)
        
        # 创建0.3分区间的直方图数据
        bins = {}
        for row in rating_data:
            rating = float(row['rating'])  # 转换为float
            # 计算所属区间 (例如 8.7 -> 8.7, 8.9 -> 8.7, 9.0 -> 9.0)
            bin_start = (rating // 0.3) * 0.3
            bin_key = f"{bin_start:.1f}-{bin_start + 0.3:.1f}"
            bins[bin_key] = bins.get(bin_key, 0) + 1
        
        # 按区间排序
        stats['rating_distribution'] = [
            {'range': k, 'count': v}
            for k, v in sorted(bins.items(), key=lambda x: float(x[0].split('-')[0]))
        ]
        
        # 国家/地区分布 - 在Python层面拆分
        country_query = """
            SELECT countries
            FROM movie
            WHERE countries IS NOT NULL
        """
        country_data = self.execute_query(country_query)
        
        # 拆分并统计
        country_count = {}
        for row in country_data:
            countries = row['countries']
            # 按 / 拆分
            for country in countries.split('/'):
                country = country.strip()
                if country:
                    country_count[country] = country_count.get(country, 0) + 1
        
        # 转换为列表并排序
        stats['country_distribution'] = [
            {'country': k, 'count': v} 
            for k, v in sorted(country_count.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        # 导演作品数量排行
        director_query = """
            SELECT d.name, COUNT(md.movie_id) as count
            FROM director d
            JOIN movie_director md ON d.director_id = md.director_id
            GROUP BY d.director_id, d.name
            ORDER BY count DESC
            LIMIT 10
        """
        stats['director_ranking'] = self.execute_query(director_query)
        
        # 演员出镜次数排行
        actor_query = """
            SELECT a.name, COUNT(ma.movie_id) as count
            FROM actor a
            JOIN movie_actor ma ON a.actor_id = ma.actor_id
            GROUP BY a.actor_id, a.name
            ORDER BY count DESC
            LIMIT 10
        """
        stats['actor_ranking'] = self.execute_query(actor_query)
        
        return stats

    def create_user(self, username: str, password: str, email: str) -> Dict:
        """创建新用户并返回基本信息"""
        hashed_password = generate_password_hash(password)
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    'INSERT INTO "user" (username, password, email, external_id) '
                    'VALUES (%s, %s, %s, %s) '
                    'RETURNING user_id, username, email, created_at',
                    (username, hashed_password, email, None)
                )
                user = cursor.fetchone()
                conn.commit()
                return user
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"创建用户失败: {str(e)}")
            raise
        finally:
            if conn:
                self.release_connection(conn)

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """根据用户名查询用户（忽略大小写）"""
        query = 'SELECT user_id, username, email, password, last_login, created_at FROM "user" WHERE LOWER(username) = LOWER(%s) LIMIT 1'
        return self.execute_query(query, (username,), fetch_one=True)

    def verify_user_credentials(self, username: str, password: str) -> Optional[Dict]:
        """验证用户名和密码，返回用户信息"""
        user = self.get_user_by_username(username)
        if not user:
            return None
        if not self._verify_password(user['password'], password):
            return None
        self._update_last_login(user['user_id'])
        return self._sanitize_user_record(user)

    def _is_password_hash(self, value: Optional[str]) -> bool:
        if not value:
            return False
        return value.startswith('pbkdf2:') or value.startswith('scrypt:')

    def _verify_password(self, stored_password: str, provided_password: str) -> bool:
        try:
            if self._is_password_hash(stored_password):
                return check_password_hash(stored_password, provided_password)
            return stored_password == provided_password
        except ValueError:
            logger.warning("检测到无法解析的密码哈希，尝试按明文比较")
            return stored_password == provided_password

    def _sanitize_user_record(self, user: Dict) -> Dict:
        return {
            'user_id': user.get('user_id'),
            'username': user.get('username'),
            'email': user.get('email'),
            'last_login': user.get('last_login'),
            'created_at': user.get('created_at')
        }

    def _update_last_login(self, user_id: int):
        try:
            self.execute_update('UPDATE "user" SET last_login = CURRENT_TIMESTAMP WHERE user_id = %s', (user_id,))
        except Exception as e:
            logger.warning(f"更新用户最后登录时间失败: {str(e)}")
    
    def close(self):
        """关闭连接池"""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("数据库连接池已关闭")
    
    def _build_ai_search_prompt(self, user_input: str) -> str:
        """构建AI搜索的prompt"""
        return f"""你是一个专业的电影数据库查询助手。请根据用户用中文描述的电影需求，生成准确的SQL查询语句。

重要：数据库是openGauss（基于PostgreSQL），请使用PostgreSQL兼容的语法。

数据库表结构：
- movie表：movie_id(主键), rank(排名), cn_title(中文名), original_title(原名), year(年份), rating(评分), poster_url(海报), description(简介), countries(国家), languages(语言), durations(时长), release_date(上映日期)
- director表：director_id, name(导演名)
- actor表：actor_id, name(演员名)
- genre表：genre_id, name(类型名，如: 剧情, 喜剧, 动作, 科幻, 爱情, 动画, 犯罪, 惊悚, 冒险, 悬疑等)
- movie_director表：movie_id, director_id (电影-导演关联)
- movie_actor表：movie_id, actor_id (电影-演员关联)
- movie_genre表：movie_id, genre_id (电影-类型关联)

用户查询："{user_input}"

请分析用户查询，提取以下信息：
1. 电影类型（genre）：如科幻、爱情、喜剧等
2. 最低评分（min_rating）：如8.0分以上、9分等
3. 年份范围（year_start, year_end）：如2010年代、90年代等
4. 关键词（keywords）：电影名、导演名、演员名或主题关键词
5. 其他条件：如国家、语言等

生成SELECT查询，返回电影信息，包含：
- movie_id, rank, cn_title, original_title, year, rating, poster_url
- directors (导演，用逗号分隔)
- actors (演员，用逗号分隔)

查询要求：
1. 按rank升序排列
2. 使用LEFT JOIN获取导演和演员信息
3. 使用GROUP BY和STRING_AGG聚合导演/演员
4. 对于关键词，使用ILIKE进行模糊匹配
5. 对于评分、大海等主题，可以在description、cn_title、original_title中搜索
6. 使用PostgreSQL兼容语法：COALESCE, STRING_AGG, ILIKE, EXISTS子查询等

用自然语言解释查询意图。

返回JSON格式：
{{
    "sql": "完整的SELECT语句",
    "interpretation": "查询意图解释",
    "conditions": {{
        "genre": "提取的类型",
        "min_rating": "最低评分",
        "year_range": "年份范围",
        "keywords": ["关键词1", "关键词2"]
    }}
}}

示例1：
用户查询："我要和大海有关的电影，而且评分不能少于9分"
返回：
{{
    "sql": "SELECT m.movie_id, m.rank, m.cn_title, m.original_title, m.year, m.rating, m.poster_url, COALESCE(STRING_AGG(DISTINCT d.name, ', '), '') AS directors, COALESCE(STRING_AGG(DISTINCT a.name, ', '), '') AS actors FROM movie m LEFT JOIN movie_director md ON m.movie_id = md.movie_id LEFT JOIN director d ON md.director_id = d.director_id LEFT JOIN movie_actor ma ON m.movie_id = ma.movie_id LEFT JOIN actor a ON ma.actor_id = a.actor_id WHERE m.rating >= 9.0 AND (m.cn_title ILIKE '%大海%' OR m.original_title ILIKE '%sea%' OR m.description ILIKE '%大海%' OR m.description ILIKE '%海洋%' OR m.description ILIKE '%海边%') GROUP BY m.movie_id ORDER BY m.rank",
    "interpretation": "搜索评分9.0分以上的与大海相关的电影",
    "conditions": {{
        "genre": null,
        "min_rating": 9.0,
        "year_range": null,
        "keywords": ["大海", "海洋", "海边", "sea"]
    }}
}}

示例2：
用户查询："高分科幻烧脑电影"
返回：
{{
    "sql": "SELECT m.movie_id, m.rank, m.cn_title, m.original_title, m.year, m.rating, m.poster_url, COALESCE(STRING_AGG(DISTINCT d.name, ', '), '') AS directors, COALESCE(STRING_AGG(DISTINCT a.name, ', '), '') AS actors FROM movie m LEFT JOIN movie_director md ON m.movie_id = md.movie_id LEFT JOIN director d ON md.director_id = d.director_id LEFT JOIN movie_actor ma ON m.movie_id = ma.movie_id LEFT JOIN actor a ON ma.actor_id = a.actor_id WHERE m.rating >= 8.5 AND EXISTS (SELECT 1 FROM movie_genre mg JOIN genre g ON mg.genre_id = g.genre_id WHERE mg.movie_id = m.movie_id AND g.name ILIKE '%科幻%') AND (m.description ILIKE '%烧脑%' OR m.cn_title ILIKE '%烧脑%') GROUP BY m.movie_id ORDER BY m.rank",
    "interpretation": "搜索评分8.5分以上的科幻类型烧脑电影",
    "conditions": {{
        "genre": "科幻",
        "min_rating": 8.5,
        "year_range": null,
        "keywords": ["烧脑"]
    }}
}}

请确保SQL语法正确，可以在openGauss中直接执行。"""

    def _call_deepseek_api(self, prompt: str) -> Optional[str]:
        """调用DEEPSEEK API"""
        try:
            headers = {
                'Authorization': f'Bearer {Config.DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': 'deepseek-chat',
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': 0.1,  # 降低随机性，提高准确性
                'max_tokens': 1000
            }
            
            response = requests.post(
                Config.DEEPSEEK_API_URL,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                logger.error(f"DEEPSEEK API调用失败: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"DEEPSEEK API调用异常: {str(e)}")
            return None
    
    def _parse_ai_response(self, response: str) -> Tuple[Optional[str], str]:
        """解析AI响应"""
        try:
            # 尝试解析JSON响应
            parsed = json.loads(response.strip())
            sql = parsed.get('sql', '').strip()
            interpretation = parsed.get('interpretation', 'AI生成的查询').strip()
            
            if sql and sql.upper().startswith('SELECT'):
                return sql, interpretation
            else:
                logger.warning(f"AI返回的SQL无效: {sql}")
                return None, interpretation
                
        except json.JSONDecodeError:
            # 如果不是JSON,可能被包裹在代码块中,先尝试提取
            logger.warning(f"AI响应不是有效JSON: {response}")
            
            # 移除可能的markdown代码块标记
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            # 再次尝试解析JSON
            try:
                parsed = json.loads(cleaned_response)
                sql = parsed.get('sql', '').strip()
                interpretation = parsed.get('interpretation', 'AI生成的查询').strip()
                
                if sql and sql.upper().startswith('SELECT'):
                    return sql, interpretation
                else:
                    logger.warning(f"AI返回的SQL无效: {sql}")
                    return None, interpretation
            except json.JSONDecodeError:
                # 最后尝试从文本中直接提取SQL
                sql_start = cleaned_response.upper().find('SELECT')
                if sql_start != -1:
                    sql_candidate = cleaned_response[sql_start:]
                    # 查找SQL语句的结束位置(遇到引号、逗号或换行符)
                    end_pos = len(sql_candidate)
                    for terminator in ['"', '",', '\n\n', '\r\n\r\n']:
                        idx = sql_candidate.find(terminator)
                        if idx != -1 and idx < end_pos:
                            end_pos = idx
                    sql_candidate = sql_candidate[:end_pos].strip()
                    
                    if sql_candidate.upper().startswith('SELECT'):
                        return sql_candidate, "从文本中提取的查询"
                return None, "无法解析AI响应"
    
    def _execute_ai_sql(self, sql_query: str) -> List[Dict]:
        """执行AI生成的SQL查询"""
        try:
            if not sql_query or not sql_query.upper().strip().startswith('SELECT'):
                logger.error(f"拒绝执行非SELECT查询: {sql_query}")
                return []
            
            result = self.execute_query(sql_query)
            if result and isinstance(result[0], dict):
                return result
            if result:
                logger.warning(f"查询结果格式异常: {type(result)}")
            return result or []
        except Exception as e:
            logger.error(f"执行AI SQL失败: {str(e)}\nSQL: {sql_query}")
            return []
    
    def _build_recommend_prompt(self, user_input: str) -> str:
        """构建AI推荐的prompt"""
        return f"""你是一个专业的电影推荐助手。用户会描述他们的心情、场景或观影需求，你需要从豆瓣Top250电影中推荐最合适的电影。

用户描述："{user_input}"

请分析用户的情感需求和场景，从以下豆瓣Top250经典电影中推荐3-8部最合适的电影：
肖申克的救赎、霸王别姬、阿甘正传、泰坦尼克号、这个杀手不太冷、美丽人生、千与千寻、辛德勒的名单、盗梦空间、忠犬八公的故事、海上钢琴师、楚门的世界、三傻大闹宝莱坞、机器人总动员、放牛班的春天、大话西游之大圣娶亲、疯狂动物城、控方证人、熔炉、无间道、当幸福来敲门、怦然心动、触不可及、蝙蝠侠：黑暗骑士、教父、星际穿越、龙猫、乱世佳人、鬼子来了、指环王3：王者无敌、天堂电影院、哈尔的移动城堡、活着、飞屋环游记、窃听风暴、十二怒汉、哈利·波特与魔法石、少年派的奇幻漂流、罗马假日、天空之城、大话西游之月光宝盒、闻香识女人、搏击俱乐部、素媛、V字仇杀队、死亡诗社、指环王1：护戒使者、饮食男女、辩护人、指环王2：双塔奇兵、狮子王、美丽心灵、美国往事、钢琴家、本杰明·巴顿奇事、看不见的客人、西西里的美丽传说、穿条纹睡衣的男孩、拯救大兵瑞恩、低俗小说、沉默的羔羊、音乐之声、致命魔术、两杆大烟枪、阳光灿烂的日子、小鞋子、摔跤吧！爸爸、猫鼠游戏、绿皮书、告白、勇敢的心、禁闭岛、致命ID、布达佩斯大饭店、完美的世界、剪刀手爱德华、春光乍泄、心灵捕手、末代皇帝、摩登时代、加勒比海盗、入殓师、哪吒闹海、大闹天宫、射雕英雄传之东成西就、重庆森林、英雄本色、菊次郎的夏天、喜剧之王、倩女幽魂、阿凡达、超脱、教父2、东邪西毒、蝴蝶效应、海豚湾、风之谷、请以你的名字呼唤我、幽灵公主、杀人回忆、爱在黎明破晓前、一一、功夫、甜蜜蜜、天使爱美丽、神偷奶爸、侧耳倾听、被嫌弃的松子的一生、阿甘正传、驯龙高手、海蒂和爷爷、小森林 夏秋篇、小森林 冬春篇、神秘巨星、玛丽和马克思、七宗罪、爆裂鼓手、穿越时空的少女、头号玩家、傲慢与偏见、岁月神偷、恐怖直播、大佛普拉斯、血战钢锯岭、寻梦环游记、头脑特工队、摔跤吧！爸爸、疯狂的石头、让子弹飞、香水、海边的曼彻斯特、萤火之森、借东西的小人阿莉埃蒂、记忆碎片、七武士、消失的爱人、哈利·波特与死亡圣器(下)、模仿游戏、无人知晓、被解救的姜戈、天使爱美丽、玩具总动员3、惊魂记、黑天鹅、卢旺达饭店、第六感、勇敢的心、雨人、一个叫欧维的男人决定去死、小偷家族、爱在日落黄昏时、真爱至上、阳光姐妹淘、驴得水、虎口脱险、超能陆战队、恐怖游轮、房间、哈利·波特与阿兹卡班的囚徒、魂断蓝桥、达拉斯买家俱乐部、你的名字、彗星来的那一夜、教父3、东京物语、爱在午夜降临前、红辣椒、恋恋笔记本、忠犬八公物语、步履不停、贫民窟的百万富翁、冰川时代、谍影重重3、心迷宫、人工智能、电锯惊魂、罗生门、未麻的部屋、幸福终点站、7号房的礼物、色，戒、卡萨布兰卡、黑客帝国、花束般的恋爱、我是山姆、遗愿清单、海街日记、喜宴、雨中曲、城市之光、阿飞正传、伴我同行、黑客帝国3：矩阵革命、人生果实、疯狂的麦克斯4：狂暴之路、萤火虫之墓、上帝之城、谍影重重、战争之王、浪潮、釜山行、魔女宅急便、我不是药神、爱乐之城、初恋这件小事、唐伯虎点秋香、阳光普照、教父、哈利·波特与密室

推荐要求：
1. 深度理解用户的情感状态和场景需求
2. 选择最能匹配用户心情/需求的电影
3. 推荐3-8部电影（根据需求的明确程度决定）
4. 如果是负面情绪，推荐治愈、温暖、励志的电影；如果是正面情绪，推荐轻松、欢乐、有趣的电影
5. 如果提到特定场景（如旅行、失眠、聚会），推荐适合该场景的电影
6. 必须从上述列表中选择电影，使用电影的完整中文名称

返回JSON格式：
{{
    "movies": ["电影名1", "电影名2", "电影名3", ...],
    "interpretation": "对用户需求的理解",
    "reasoning": "推荐这些电影的理由"
}}

重要说明：
- reasoning字段格式要求：可以先用1-2句话说明整体推荐思路，然后分点说明每部电影，每部电影单独一点
- 分点说明后不要添加总结语句，直接结束即可

示例1：
用户描述："我失恋了，想看治愈的电影"
返回：
{{
    "movies": ["忠犬八公的故事", "当幸福来敲门", "怦然心动", "放牛班的春天", "天使爱美丽"],
    "interpretation": "你正经历失恋的痛苦，需要温暖和治愈",
    "reasoning": "这些电影充满了温暖和希望，能够抚慰受伤的心灵。1.《忠犬八公的故事》展现了无条件的爱与陪伴。2.《当幸福来敲门》告诉我们永不放弃的力量。3.《怦然心动》让我们相信美好爱情的存在。4.《放牛班的春天》用音乐治愈人心。5.《天使爱美丽》用奇妙的方式让我们重新发现生活的美好。"
}}

示例2：
用户描述："我今天心情很好，想看轻松搞笑的电影"
返回：
{{
    "movies": ["疯狂动物城", "三傻大闹宝莱坞", "大话西游之大圣娶亲", "虎口脱险", "超能陆战队"],
    "interpretation": "你心情愉悦，想要更多欢乐",
    "reasoning": "这些电影轻松幽默，能让好心情持续升温。1.《疯狂动物城》充满想象力和笑点。2.《三傻大闹宝莱坞》用印度式幽默讽刺教育体制。3.《大话西游之大圣娶亲》是经典无厘头喜剧。4.《虎口脱险》是法式幽默的巅峰之作。5.《超能陆战队》温馨又有趣。"
}}

请确保返回的是有效的JSON格式，电影名称必须完全匹配列表中的名称。"""

    def _parse_recommend_response(self, response: str) -> Tuple[List[str], str, str]:
        """解析AI推荐响应"""
        try:
            # 尝试解析JSON响应
            parsed = json.loads(response.strip())
            movies = parsed.get('movies', [])
            interpretation = parsed.get('interpretation', 'AI理解了你的需求')
            reasoning = parsed.get('reasoning', '')
            
            return movies, interpretation, reasoning
                
        except json.JSONDecodeError:
            # 如果不是JSON,可能被包裹在代码块中
            logger.warning(f"AI推荐响应不是有效JSON: {response}")
            
            # 移除可能的markdown代码块标记
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            # 再次尝试解析JSON
            try:
                parsed = json.loads(cleaned_response)
                movies = parsed.get('movies', [])
                interpretation = parsed.get('interpretation', 'AI理解了你的需求')
                reasoning = parsed.get('reasoning', '')
                
                return movies, interpretation, reasoning
            except json.JSONDecodeError:
                logger.error(f"无法解析AI推荐响应: {cleaned_response}")
                return [], "无法解析AI响应", ""
    
    def _find_movies_by_titles(self, titles: List[str]) -> List[Dict]:
        """根据电影名称列表查询数据库"""
        if not titles:
            return []
        
        try:
            # 构建查询条件
            conditions = " OR ".join([f"m.cn_title = %s" for _ in titles])
            
            query = f"""
                SELECT m.movie_id, m.rank, m.cn_title, m.original_title, m.year, 
                       m.rating, m.poster_url,
                       COALESCE(STRING_AGG(DISTINCT d.name, ', '), '') AS directors,
                       COALESCE(STRING_AGG(DISTINCT a.name, ', '), '') AS actors
                FROM movie m
                LEFT JOIN movie_director md ON m.movie_id = md.movie_id
                LEFT JOIN director d ON md.director_id = d.director_id
                LEFT JOIN movie_actor ma ON m.movie_id = ma.movie_id
                LEFT JOIN actor a ON ma.actor_id = a.actor_id
                WHERE {conditions}
                GROUP BY m.movie_id
                ORDER BY m.rank
            """
            
            result = self.execute_query(query, tuple(titles))
            return result if result else []
        except Exception as e:
            logger.error(f"根据电影名称查询失败: {str(e)}")
            return []
    
    def get_celebrity_by_name(self, name: str) -> Optional[Dict]:
        """
        根据影人姓名获取其所有作品信息
        :param name: 影人姓名
        :return: 包含该影人作为导演和演员的所有作品
        """
        if not name or not name.strip():
            return None
        
        name = name.strip()
        result = {
            'name': name,
            'roles': [],
            'as_director': [],
            'as_actor': [],
            'total_movies': 0
        }
        
        # 查询作为导演的电影
        director_query = """
            SELECT 
                d.director_id,
                m.movie_id, 
                m.rank, 
                m.cn_title, 
                m.original_title, 
                m.year, 
                m.rating, 
                m.poster_url,
                m.description,
                COALESCE(STRING_AGG(DISTINCT a.name, ', ') FILTER (WHERE a.name IS NOT NULL), '') as actors,
                COALESCE(STRING_AGG(DISTINCT g.name, ', ') FILTER (WHERE g.name IS NOT NULL), '') as genres
            FROM director d
            JOIN movie_director md ON d.director_id = md.director_id
            JOIN movie m ON md.movie_id = m.movie_id
            LEFT JOIN movie_actor ma ON m.movie_id = ma.movie_id
            LEFT JOIN actor a ON ma.actor_id = a.actor_id
            LEFT JOIN movie_genre mg ON m.movie_id = mg.movie_id
            LEFT JOIN genre g ON mg.genre_id = g.genre_id
            WHERE d.name = %s
            GROUP BY d.director_id, m.movie_id, m.rank
            ORDER BY m.rank
            LIMIT 100
        """
        
        # 查询作为演员的电影
        actor_query = """
            SELECT 
                a.actor_id,
                m.movie_id, 
                m.rank, 
                m.cn_title, 
                m.original_title, 
                m.year, 
                m.rating, 
                m.poster_url,
                m.description,
                COALESCE(STRING_AGG(DISTINCT d.name, ', ') FILTER (WHERE d.name IS NOT NULL), '') as directors,
                COALESCE(STRING_AGG(DISTINCT g.name, ', ') FILTER (WHERE g.name IS NOT NULL), '') as genres
            FROM actor a
            JOIN movie_actor ma ON a.actor_id = ma.actor_id
            JOIN movie m ON ma.movie_id = m.movie_id
            LEFT JOIN movie_director md ON m.movie_id = md.movie_id
            LEFT JOIN director d ON md.director_id = d.director_id
            LEFT JOIN movie_genre mg ON m.movie_id = mg.movie_id
            LEFT JOIN genre g ON mg.genre_id = g.genre_id
            WHERE a.name = %s
            GROUP BY a.actor_id, m.movie_id, m.rank
            ORDER BY m.rank
            LIMIT 100
        """
        
        try:
            as_director = self.execute_query(director_query, (name,))
            as_actor = self.execute_query(actor_query, (name,))
            
            if as_director:
                result['roles'].append('导演')
                result['as_director'] = as_director
                result['director_id'] = as_director[0]['director_id']
            
            if as_actor:
                result['roles'].append('演员')
                result['as_actor'] = as_actor
                result['actor_id'] = as_actor[0]['actor_id']
            
            # 计算总电影数（去重，因为可能在同一部电影中既是导演又是演员）
            director_movie_ids = {movie['movie_id'] for movie in as_director} if as_director else set()
            actor_movie_ids = {movie['movie_id'] for movie in as_actor} if as_actor else set()
            unique_movie_ids = director_movie_ids | actor_movie_ids
            result['total_movies'] = len(unique_movie_ids)
            
            # 如果该影人没有任何作品，返回 None
            if not result['roles']:
                return None
            
            return result
            
        except Exception as e:
            logger.error(f"查询影人信息失败: {str(e)}")
            return None
