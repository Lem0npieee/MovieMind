import sys
sys.path.insert(0, '.')
sys.path.insert(0, './backend')
from database.db_manager import DatabaseManager

db = DatabaseManager()

# 简单测试
print("简单测试:")
result = db.execute_query("SELECT countries as country, COUNT(*) as count FROM movie WHERE countries IS NOT NULL GROUP BY countries ORDER BY count DESC LIMIT 10")
print(f"结果数量: {len(result)}")
for row in result:
    print(f"  {row['country']}: {row['count']}")

db.close()
