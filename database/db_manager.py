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
        
        # 评分分布
        rating_query = """
            SELECT 
                FLOOR(rating) as rating_group,
                COUNT(*) as count
            FROM movie
            GROUP BY rating_group
            ORDER BY rating_group
        """
        stats['rating_distribution'] = self.execute_query(rating_query)
        
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
1. 最多返回50条记录
2. 按rank升序排列
3. 使用LEFT JOIN获取导演和演员信息
4. 使用GROUP BY和STRING_AGG聚合导演/演员
5. 对于关键词，使用ILIKE进行模糊匹配
6. 对于评分、大海等主题，可以在description、cn_title、original_title中搜索
7. 使用PostgreSQL兼容语法：COALESCE, STRING_AGG, ILIKE, EXISTS子查询等

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
    "sql": "SELECT m.movie_id, m.rank, m.cn_title, m.original_title, m.year, m.rating, m.poster_url, COALESCE(STRING_AGG(DISTINCT d.name, ', '), '') AS directors, COALESCE(STRING_AGG(DISTINCT a.name, ', '), '') AS actors FROM movie m LEFT JOIN movie_director md ON m.movie_id = md.movie_id LEFT JOIN director d ON md.director_id = d.director_id LEFT JOIN movie_actor ma ON m.movie_id = ma.movie_id LEFT JOIN actor a ON ma.actor_id = a.actor_id WHERE m.rating >= 9.0 AND (m.cn_title ILIKE '%大海%' OR m.original_title ILIKE '%sea%' OR m.description ILIKE '%大海%' OR m.description ILIKE '%海洋%' OR m.description ILIKE '%海边%') GROUP BY m.movie_id ORDER BY m.rank LIMIT 50",
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
    "sql": "SELECT m.movie_id, m.rank, m.cn_title, m.original_title, m.year, m.rating, m.poster_url, COALESCE(STRING_AGG(DISTINCT d.name, ', '), '') AS directors, COALESCE(STRING_AGG(DISTINCT a.name, ', '), '') AS actors FROM movie m LEFT JOIN movie_director md ON m.movie_id = md.movie_id LEFT JOIN director d ON md.director_id = d.director_id LEFT JOIN movie_actor ma ON m.movie_id = ma.movie_id LEFT JOIN actor a ON ma.actor_id = a.actor_id WHERE m.rating >= 8.5 AND EXISTS (SELECT 1 FROM movie_genre mg JOIN genre g ON mg.genre_id = g.genre_id WHERE mg.movie_id = m.movie_id AND g.name ILIKE '%科幻%') AND (m.description ILIKE '%烧脑%' OR m.cn_title ILIKE '%烧脑%') GROUP BY m.movie_id ORDER BY m.rank LIMIT 50",
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
            # 如果不是JSON，尝试提取SQL和解释
            logger.warning(f"AI响应不是有效JSON: {response}")
            
            sql_start = response.upper().find('SELECT')
            if sql_start != -1:
                sql_candidate = response[sql_start:]
                for terminator in ['```', '\n\n', '\r\n\r\n']:
                    idx = sql_candidate.find(terminator)
                    if idx != -1:
                        sql_candidate = sql_candidate[:idx]
                        break
                sql_candidate = sql_candidate.strip().rstrip(',')
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
                return result[:50]
            if result:
                logger.warning(f"查询结果格式异常: {type(result)}")
            return result or []
        except Exception as e:
            logger.error(f"执行AI SQL失败: {str(e)}\nSQL: {sql_query}")
            return []
