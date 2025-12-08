"""
客户端相关表初始化：收藏表等
"""

CREATE_CLIENT_TABLES_SQL = """
-- 用户收藏表
CREATE TABLE IF NOT EXISTS favorite (
    favorite_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    movie_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES "user"(user_id) ON DELETE CASCADE,
    FOREIGN KEY (movie_id) REFERENCES movie(movie_id) ON DELETE CASCADE,
    UNIQUE(user_id, movie_id)
);

CREATE INDEX IF NOT EXISTS idx_favorite_user ON favorite(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_favorite_movie ON favorite(movie_id);
"""

if __name__ == '__main__':
    import psycopg2
    import importlib.util

    config_path = '../backend/config.py'
    spec = importlib.util.spec_from_file_location("config", config_path)
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    Config = config_module.Config

    try:
        conn = psycopg2.connect(**Config.DB_CONFIG)
        cur = conn.cursor()
        print("开始创建客户端表...")
        cur.execute(CREATE_CLIENT_TABLES_SQL)
        conn.commit()
        print("✓ 客户端表创建完成")
    except Exception as e:
        print("创建失败", e)
        conn.rollback()
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
