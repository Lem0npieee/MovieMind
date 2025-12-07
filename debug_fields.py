import sys
sys.path.insert(0, '.')
sys.path.insert(0, './backend')
from database.db_manager import DatabaseManager

db = DatabaseManager()

# 执行简化的SQL查询看看返回的字段
sql = """SELECT m.movie_id, m.rank, m.cn_title, m.year, m.rating 
FROM movie m 
WHERE m.year >= 2000 
ORDER BY m.rank 
LIMIT 3"""

print("执行简化SQL查询...")
result = db.execute_query(sql)
print(f"查询结果数量: {len(result)}")

if len(result) > 0:
    print("\n第一条记录的所有字段:")
    for key, value in result[0].items():
        print(f"  {key}: {value} (类型: {type(value).__name__})")
    
    print("\n完整结果:")
    for i, row in enumerate(result):
        print(f"{i+1}. movie_id={row.get('movie_id')}, rank={row.get('rank')}, cn_title={row.get('cn_title')}, year={row.get('year')}, rating={row.get('rating')}")

# 执行完整的AI SQL
sql_full = """SELECT m.movie_id, m.rank, m.cn_title, m.original_title, m.year, m.rating, m.poster_url, 
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
LIMIT 3"""

print("\n\n执行完整AI SQL查询...")
result_full = db.execute_query(sql_full)
print(f"查询结果数量: {len(result_full)}")

if len(result_full) > 0:
    print("\n第一条记录的所有字段:")
    for key, value in result_full[0].items():
        print(f"  {key}: {value[:50] if isinstance(value, str) and len(value) > 50 else value} (类型: {type(value).__name__})")

db.close()
