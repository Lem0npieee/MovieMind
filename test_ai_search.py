import sys
sys.path.insert(0, '.')
sys.path.insert(0, './backend')
from database.db_manager import DatabaseManager
import json

db = DatabaseManager()

# 模拟ai_search调用
user_input = "2000年之后的电影"
print(f"测试查询: {user_input}\n")

result = db.ai_search(user_input)

print(f"返回的键: {result.keys()}\n")
print(f"movies数量: {len(result['movies'])}")
print(f"SQL: {result['sql'][:100]}...")
print(f"interpretation: {result['interpretation']}\n")

if len(result['movies']) > 0:
    print("前3条电影数据:")
    for i, movie in enumerate(result['movies'][:3]):
        print(f"{i+1}. {movie}")
else:
    print("movies列表为空!")

db.close()
