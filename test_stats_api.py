import sys
sys.path.insert(0, '.')
sys.path.insert(0, './backend')
from database.db_manager import DatabaseManager
import json

db = DatabaseManager()

stats = db.get_statistics()

print("Statistics keys:", stats.keys())
print("\nCountry distribution:")
print(f"Type: {type(stats['country_distribution'])}")
print(f"Length: {len(stats['country_distribution'])}")
print(f"Data: {stats['country_distribution']}")

print("\n\nJSON serialized:")
print(json.dumps(stats['country_distribution'], default=str, indent=2))

db.close()
