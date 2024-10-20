import os
from typing import List, Dict
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import sessionmaker, Session
import yaml
import urllib

class DialogueQuery:
    def __init__(self, db=None, if_test: bool = False):
        if not if_test:
            self.db = db
        else:
            self.engine = self.load_config()
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.db = self.get_db()

    def load_config(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "config.yaml")
        
        try:
            with open(config_path, "r", encoding="utf-8") as config_file:
                config = yaml.safe_load(config_file)
                encoded_password = urllib.parse.quote(config["database"]["password"])
                host = config["database"]["host"]
                username = config["database"]["username"]
                DATABASE_URI = f'mysql+mysqldb://{username}:{encoded_password}@{host}/pillow_customer_prod'
                engine = create_engine(DATABASE_URI)
                return engine
        except FileNotFoundError:
            print(f"无法找到配置文件: {config_path}")
            raise
        except yaml.YAMLError as e:
            print(f"YAML 解析错误: {e}")
            raise
        except UnicodeDecodeError:
            print(f"文件编码错误,请确保 {config_path} 使用 UTF-8 编码")
            raise

    def get_db(self):
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def get_user_dialogue_history(self, user_id: str) -> List[Dict[str, str]]:
        db = next(self.get_db())
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
        return self._process_query_results(query_results)

    def _process_query_results(self, query_results):
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

# 示例用法
if __name__ == "__main__":
    dialogue_query = DialogueQuery(if_test=True)
    result = dialogue_query.get_user_dialogue_history('1000009')
    print(result)
