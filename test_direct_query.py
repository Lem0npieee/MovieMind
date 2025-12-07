import sys
sys.path.insert(0, '.')
sys.path.insert(0, './backend')
from database.db_manager import DatabaseManager

db = DatabaseManager()

# 直接执行查询
country_query = """
    SELECT countries as country, COUNT(*) as count
    FROM movie
    WHERE countries IS NOT NULL AND countries != ''
    GROUP BY countries
    ORDER BY count DESC
    LIMIT 10
"""

print("Direct query:")
result = db.execute_query(country_query)
print(f"Result length: {len(result)}")
print(f"Result: {result}")

db.close()
