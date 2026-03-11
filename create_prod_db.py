import mysql.connector
from mysql.connector import Error

config = {
    "host": "81.68.235.167",
    "user": "pillow",
    "password": "1234QWERasdf!@#$",
}

try:
    connection = mysql.connector.connect(**config)
    if connection.is_connected():
        cursor = connection.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS pillow_customer_prod CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print("✅ Database pillow_customer_prod created")
        connection.commit()
except Error as e:
    print(f"Error: {e}")
finally:
    if connection.is_connected():
        cursor.close()
        connection.close()
