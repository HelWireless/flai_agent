import os
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text
import urllib.parse

def get_user_dialogue_history(db: Session, user_id: int) -> List[Dict[str, str]]:
    query = text("""
        SELECT
            t1.message AS user_message,
            t1.text AS assistant_response,
            t1.create_time
        FROM
            t_dialogue t1
        WHERE
            t1.account_id = :user_id
        AND
            t1.create_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        ORDER BY
            t1.create_time DESC, t1.id ASC
    """)
    
    query_results = db.execute(query, {"user_id": user_id}).fetchall()    
    return process_query_results(query_results)

def process_query_results(query_results):
    processed_results = []
    temp_dict = {}
    
    for result in query_results:
        user_msg = result[0]
        assistant_msg = result[1]
        timestamp = result[2]
        
        if timestamp not in temp_dict:
            temp_dict[timestamp] = {"user": "", "assistant": ""}
        
        if user_msg:
            temp_dict[timestamp]["user"] = user_msg
        if assistant_msg:
            if temp_dict[timestamp]["assistant"]:
                temp_dict[timestamp]["assistant"] += " " + assistant_msg
            else:
                temp_dict[timestamp]["assistant"] = assistant_msg
    
    # 按照 timestamp 排序并取最近的 3 条对话
    sorted_keys = sorted(temp_dict.keys(), reverse=True)
    for key in sorted_keys[:3]:
        if temp_dict[key]["user"]:
            processed_results.append({"role": "user", "content": temp_dict[key]["user"]})
        if temp_dict[key]["assistant"]:
            processed_results.append({"role": "assistant", "content": temp_dict[key]["assistant"]})
    
    return processed_results

# 测试函数
def test_get_user_dialogue_history(db: Session, user_id: str):
    conversation_history = get_user_dialogue_history(db, user_id)
    print(conversation_history)

# 示例用法
if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # 加载配置
    import yaml
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    password = config["database"]["password"]
    encoded_password = urllib.parse.quote(password)
    host = config["database"]["host"]
    username = config["database"]["username"]
    DATABASE_URI = f'mysql+mysqldb://{username}:{encoded_password}@{host}/pillow_customer_prod'
    engine = create_engine(DATABASE_URI)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 创建数据库会话
    db = SessionLocal()

    # 测试 user_id 为 1000008 的用户
    test_get_user_dialogue_history(db, 1000008)

    # 关闭数据库会话
    db.close()
