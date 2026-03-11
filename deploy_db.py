import mysql.connector
from mysql.connector import Error
import sys

prod_db = "pillow_customer_prod"
config = {
    'host': '81.68.235.167',
    'user': 'pillow',
    'password': '1234QWERasdf!@#$',
    'database': prod_db
}

try:
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()
    
    with open('scripts/deploy_to_production.sql', 'r', encoding='utf-8') as f:
        sql = f.read()
    
    for statement in sql.split(';'):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)
            cursor.fetchall()
    
    conn.commit()
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print(f"✅ Found {len(tables)} tables in {prod_db}")
    for t in tables:
        print(f"  - {t[0]}")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    cursor.close()
    conn.close()
