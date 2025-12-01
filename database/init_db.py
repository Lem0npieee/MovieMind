"""
数据库初始化脚本 - 创建所有表结构
"""

# 创建数据库表的 SQL 语句
CREATE_TABLES_SQL = """
-- 1. 用户表 (User)
CREATE TABLE IF NOT EXISTS "user" (
    user_id SERIAL PRIMARY KEY,
    external_id VARCHAR(50) UNIQUE,
    username VARCHAR(100) NOT NULL,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(120) NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- 2. 电影表 (Movie) - 核心表
CREATE TABLE IF NOT EXISTS movie (
    movie_id SERIAL PRIMARY KEY,
    douban_id BIGINT UNIQUE NOT NULL,
    rank INTEGER UNIQUE NOT NULL,
    cn_title VARCHAR(200) NOT NULL,
    original_title VARCHAR(200),
    year INTEGER,
    rating DECIMAL(3,1),
    comment_count INTEGER,
    poster_url TEXT,
    description TEXT,
    countries TEXT,
    languages TEXT,
    durations TEXT,
    release_date TEXT,
    imdb_id VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_movie_rank ON movie(rank);
CREATE INDEX IF NOT EXISTS idx_movie_year ON movie(year);
CREATE INDEX IF NOT EXISTS idx_movie_rating ON movie(rating);
CREATE INDEX IF NOT EXISTS idx_movie_cn_title ON movie(cn_title);

-- 3. 导演表 (Director)
CREATE TABLE IF NOT EXISTS director (
    director_id SERIAL PRIMARY KEY,
    name VARCHAR(150) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. 演员表 (Actor)
CREATE TABLE IF NOT EXISTS actor (
    actor_id SERIAL PRIMARY KEY,
    name VARCHAR(150) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. 电影-导演关联表 (Movie_Director)
CREATE TABLE IF NOT EXISTS movie_director (
    id SERIAL PRIMARY KEY,
    movie_id INTEGER NOT NULL,
    director_id INTEGER NOT NULL,
    FOREIGN KEY (movie_id) REFERENCES movie(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (director_id) REFERENCES director(director_id) ON DELETE CASCADE,
    UNIQUE(movie_id, director_id)
);

-- 6. 电影-演员关联表 (Movie_Actor)
CREATE TABLE IF NOT EXISTS movie_actor (
    id SERIAL PRIMARY KEY,
    movie_id INTEGER NOT NULL,
    actor_id INTEGER NOT NULL,
    FOREIGN KEY (movie_id) REFERENCES movie(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (actor_id) REFERENCES actor(actor_id) ON DELETE CASCADE,
    UNIQUE(movie_id, actor_id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_movie_director_movie ON movie_director(movie_id);
CREATE INDEX IF NOT EXISTS idx_movie_actor_movie ON movie_actor(movie_id);

-- 7. 类型表 (Genre)
CREATE TABLE IF NOT EXISTS genre (
    genre_id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

-- 8. 电影-类型关联表 (Movie_Genre)
CREATE TABLE IF NOT EXISTS movie_genre (
    mg_id SERIAL PRIMARY KEY,
    movie_id INTEGER NOT NULL,
    genre_id INTEGER NOT NULL,
    FOREIGN KEY (movie_id) REFERENCES movie(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genre(genre_id) ON DELETE CASCADE,
    UNIQUE(movie_id, genre_id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_movie_genre_movie ON movie_genre(movie_id);
CREATE INDEX IF NOT EXISTS idx_movie_genre_genre ON movie_genre(genre_id);

-- 9. 评论/打分表 (Review)
CREATE TABLE IF NOT EXISTS review (
    review_id SERIAL PRIMARY KEY,
    douban_review_id VARCHAR(50) UNIQUE,
    movie_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    user_rating DECIMAL(2,1),
    comment TEXT,
    useful_count INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    spoiler BOOLEAN,
    status VARCHAR(20),
    FOREIGN KEY (movie_id) REFERENCES movie(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_review_movie ON review(movie_id);
CREATE INDEX IF NOT EXISTS idx_review_created ON review(created_at);

-- 10. AI 对话日志表 (ChatLog)
CREATE TABLE IF NOT EXISTS chat_log (
    log_id SERIAL PRIMARY KEY,
    user_input TEXT NOT NULL,
    ai_response TEXT,
    query_sql TEXT,
    result_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_chat_log_created ON chat_log(created_at);
"""

# 清空所有表数据（慎用！）
TRUNCATE_TABLES_SQL = """
TRUNCATE TABLE chat_log CASCADE;
TRUNCATE TABLE review CASCADE;
TRUNCATE TABLE movie_actor CASCADE;
TRUNCATE TABLE movie_director CASCADE;
TRUNCATE TABLE movie_genre CASCADE;
TRUNCATE TABLE actor CASCADE;
TRUNCATE TABLE director CASCADE;
TRUNCATE TABLE genre RESTART IDENTITY CASCADE;
TRUNCATE TABLE movie CASCADE;
TRUNCATE TABLE "user" CASCADE;
"""

# 删除所有表（慎用！）
DROP_TABLES_SQL = """
DROP TABLE IF EXISTS chat_log CASCADE;
DROP TABLE IF EXISTS review CASCADE;
DROP TABLE IF EXISTS movie_genre CASCADE;
DROP TABLE IF EXISTS movie_actor CASCADE;
DROP TABLE IF EXISTS movie_director CASCADE;
DROP TABLE IF EXISTS actor CASCADE;
DROP TABLE IF EXISTS director CASCADE;
DROP TABLE IF EXISTS genre CASCADE;
DROP TABLE IF EXISTS movie CASCADE;
DROP TABLE IF EXISTS "user" CASCADE;
"""


if __name__ == '__main__':
    import psycopg2
    import sys
    import importlib.util
    
    # 明确导入 config.py
    config_path = '../backend/config.py'
    spec = importlib.util.spec_from_file_location("config", config_path)
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    Config = config_module.Config
    
    print("Config 类属性:", dir(Config))
    print("DB_CONFIG 存在:", hasattr(Config, 'DB_CONFIG'))
    if hasattr(Config, 'DB_CONFIG'):
        print("DB_CONFIG 值:", Config.DB_CONFIG)
    
    try:
        # 连接数据库
        conn = psycopg2.connect(**Config.DB_CONFIG)
        cursor = conn.cursor()
        
        print("开始创建数据库表...")
        
        # 执行建表语句
        cursor.execute(CREATE_TABLES_SQL)
        conn.commit()
        
        print("✓ 数据库表创建成功！")
        
        # 查看创建的表
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        print(f"\n当前数据库中的表（共 {len(tables)} 个）:")
        for table in tables:
            print(f"  - {table[0]}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"✗ 数据库初始化失败: {str(e)}")
        sys.exit(1)
