import sys
sys.path.append('..')
from database.db_manager import DatabaseManager

db = DatabaseManager()

# 测试拆分国家查询
country_query = """
    WITH split_countries AS (
        SELECT 
            TRIM(UNNEST(string_to_array(countries, '/'))) as country
        FROM movie
        WHERE countries IS NOT NULL
    )
    SELECT country, COUNT(*) as count
    FROM split_countries
    WHERE country != ''
    GROUP BY country
    ORDER BY count DESC
    LIMIT 10
"""

try:
    result = db.execute_query(country_query)
    print("查询成功!")
    print(f"结果数量: {len(result)}")
    for row in result:
        print(f"{row['country']}: {row['count']}")
except Exception as e:
    print(f"查询失败: {e}")
