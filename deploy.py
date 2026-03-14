import os
prod_sql = "scripts/deploy_to_production.sql"
print(f"Executing {prod_sql}")
print(f"File exists: {os.path.exists(prod_sql)}")
with open(prod_sql, 'r', encoding='utf-8') as f:
    content = f.read()
print(f"File size: {len(content)} chars")
print("First 500 chars:")
print(content[:500])
