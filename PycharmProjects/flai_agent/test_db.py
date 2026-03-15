print("测试数据库连接...")

try:
    from src.database import SessionLocal
    print("导入成功")
    
    db = SessionLocal()
    print("获取session成功")
    
    # 测试查询
    result = db.execute("SELECT 1")
    print(f"查询结果: {result.fetchone()}")
    
    db.close()
    print("数据库连接测试成功！")
    
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
