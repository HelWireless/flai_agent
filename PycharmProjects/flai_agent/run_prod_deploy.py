import mysql.connector
from mysql.connector import Error
import os

def execute_sql_file(cursor, filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        queries = file.read().split(';')
        for query in queries:
            query = query.strip()
            if query:
                cursor.execute(query)

prod_db_name = "pillow_customer_prod"
db_config = {
    "host": "81.68.235.167",
    "user": "pillow",
    "password": "1234QWERasdf!@#$",
    "database": prod_db_name,
}

print(f"Connecting to database: {prod_db_name}")

try:
    conn = mysql.connector.connect(**db_config)
    if conn.is_connected():
        print(f"✅ Connected to {prod_db_name}")
        cursor = conn.cursor()
        
        prod_sql = "scripts/deploy_to_production.sql"
        if os.path.exists(prod_sql):
            execute_sql_file(cursor, prod_sql)
            print(f"✅ {prod_sql} executed")
        else:
            print(f"File not found: {prod_sql}")
            
        cursor.execute(f"USE {prod_db_name}")
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"✅ Found {len(tables)} tables")
        for table in tables:
            print(f"  - {table[0]}")
        
        conn.commit()

except Error as e:
    print(f"Error: {e}")
finally:
    if conn.is_connected():
        cursor.close()
        conn.close()
        print("Database connection closed")
