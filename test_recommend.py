import sys
sys.path.insert(0, '.')
sys.path.insert(0, './backend')
from database.db_manager import DatabaseManager

db = DatabaseManager()

# 测试AI推荐
user_input = "我失恋了，想看治愈的电影"
print(f"测试推荐查询: {user_input}\n")

result = db.ai_recommend(user_input)

print(f"返回的键: {result.keys()}\n")
print(f"movies数量: {len(result['movies'])}")
print(f"interpretation: {result['interpretation']}")
print(f"reasoning: {result['reasoning'][:100] if result['reasoning'] else 'None'}...\n")

if len(result['movies']) > 0:
    print("推荐的电影:")
    for i, movie in enumerate(result['movies']):
        print(f"{i+1}. {movie.get('cn_title')} ({movie.get('year')}) - 评分: {movie.get('rating')}")
else:
    print("movies列表为空!")

db.close()
