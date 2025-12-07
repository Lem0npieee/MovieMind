import sys
sys.path.append('..')
from database.db_manager import DatabaseManager

db = DatabaseManager()

print("测试完整统计数据...\n")

try:
    stats = db.get_statistics()
    
    for key, value in stats.items():
        print(f"\n{key}:")
        if isinstance(value, list):
            print(f"  数量: {len(value)}")
            if len(value) > 0:
                print(f"  示例: {value[0]}")
        else:
            print(f"  值: {value}")
            
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
