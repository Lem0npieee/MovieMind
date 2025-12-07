import sys
sys.path.insert(0, '.')
from database.db_manager import DatabaseManager

db = DatabaseManager()

# 检查电影总数
result = db.execute_query("SELECT COUNT(*) as total FROM movie")
print(f"电影总数: {result[0]['total']}")

# 检查2000年后的电影数量
result = db.execute_query("SELECT COUNT(*) as total FROM movie WHERE year >= 2000")
print(f"2000年后电影数: {result[0]['total']}")

# 查看前5条电影数据
result = db.execute_query("SELECT movie_id, cn_title, year, rank FROM movie LIMIT 5")
print(f"\n前5条电影数据:")
for row in result:
    print(f"  ID: {row['movie_id']}, 标题: {row['cn_title']}, 年份: {row['year']}, rank: {row['rank']}")

# 执行AI生成的完整SQL
sql = """SELECT m.movie_id, m.rank, m.cn_title, m.original_title, m.year, m.rating, m.poster_url, 
    COALESCE(STRING_AGG(DISTINCT d.name, ', '), '') AS directors, 
    COALESCE(STRING_AGG(DISTINCT a.name, ', '), '') AS actors 
FROM movie m 
LEFT JOIN movie_director md ON m.movie_id = md.movie_id 
LEFT JOIN director d ON md.director_id = d.director_id 
LEFT JOIN movie_actor ma ON m.movie_id = ma.movie_id 
LEFT JOIN actor a ON ma.actor_id = a.actor_id 
WHERE m.year >= 2000 
GROUP BY m.movie_id 
ORDER BY m.rank 
LIMIT 50"""

print(f"\n执行AI生成的SQL...")
result = db.execute_query(sql)
print(f"查询结果数量: {len(result)}")

if len(result) > 0:
    print("\n前3条结果:")
    for i, row in enumerate(result[:3]):
        print(f"{i+1}. {row['cn_title']} ({row['year']}) - 评分: {row['rating']}, rank: {row['rank']}")

db.close()
