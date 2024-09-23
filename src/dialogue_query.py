from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text

def get_user_dialogue_history(db: Session, user_id: str) -> List[Dict[str, str]]:
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
            t1.create_time >= DATE_SUB(CURDATE(), INTERVAL 17 DAY)
        ORDER BY
            t1.create_time DESC, t1.id ASC
    """)
    
    query_results = db.execute(query, {"user_id": user_id}).fetchall()
    
    return process_query_results(query_results)

def process_query_results(query_results) -> List[Dict[str, str]]:
    conversation_history = []
    current_conversation = {"user": "", "assistant": ""}
    current_time = None

    for result in query_results:
        user_msg = result["user_message"]
        assistant_rsp = result["assistant_response"]
        create_time = result["create_time"]

        if create_time != current_time:
            if current_time is not None:
                conversation_history.append(current_conversation)
            current_conversation = {"user": "", "assistant": ""}
            current_time = create_time

        if user_msg:
            current_conversation["user"] = user_msg
        if assistant_rsp:
            current_conversation["assistant"] += assistant_rsp

    if current_conversation:
        conversation_history.append(current_conversation)

    return conversation_history

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
    with open("config.yaml", "r") as config_file:
        config = yaml.safe_load(config_file)

    DATABASE_URL = config["database"]["url"]
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 创建数据库会话
    db = SessionLocal()

    # 测试 user_id 为 1000008 的用户
    test_get_user_dialogue_history(db, "1000008")

    # 关闭数据库会话
    db.close()
