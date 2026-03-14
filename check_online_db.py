import pymysql
import sys

# 线上数据库配置
config = {
    "host": "81.68.235.167",
    "user": "pillow",
    "password": "1234QWERasdf!@#$",
}

def check_db_info():
    try:
        print(f"Connecting to {config['host']}...")
        connection = pymysql.connect(
            host=config['host'],
            user=config['user'],
            password=config['password']
        )
        
        with connection.cursor() as cursor:
            # 1. 列出所有数据库
            print("\n--- Databases ---")
            cursor.execute("SHOW DATABASES")
            databases = cursor.fetchall()
            for db in databases:
                print(f"- {db[0]}")
            
            # 2. 列出 pillow_customer_prod 库中的所有表
            target_db = "pillow_customer_prod"
            print(f"\n--- Tables in {target_db} ---")
            try:
                cursor.execute(f"USE {target_db}")
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                if not tables:
                    print("No tables found.")
                for table in tables:
                    print(f"- {table[0]}")
            except Exception as e:
                print(f"Error accessing {target_db}: {e}")
                
    except Exception as e:
        print(f"❌ Connection error: {e}")
    finally:
        if 'connection' in locals() and connection:
            connection.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    check_db_info()
