import sys
sys.path.insert(0, '.')
sys.path.insert(0, './backend')
from database.db_manager import DatabaseManager
import json

db = DatabaseManager()

# 测试ai_search
result = db.ai_search("2000年之后的电影")

print(f"movies数量: {len(result['movies'])}\n")

if len(result['movies']) > 0:
    movie = result['movies'][0]
    print(f"第一部电影类型: {type(movie)}")
    print(f"第一部电影: {movie}\n")
    
    # 测试是否可以像字典一样访问
    print(f"movie_id访问测试: {movie.get('movie_id')}")
    print(f"cn_title访问测试: {movie.get('cn_title')}")
    print(f"rating访问测试: {movie.get('rating')}\n")
    
    # 测试JSON序列化
    try:
        json_str = json.dumps(movie, default=str)
        print(f"JSON序列化成功: {json_str[:100]}...")
    except Exception as e:
        print(f"JSON序列化失败: {e}")

db.close()
