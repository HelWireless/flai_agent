import logging
import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy.exc import OperationalError, DBAPIError
from typing import List, Dict
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import yaml
import urllib
from src.custom_logger import custom_logger  # 导入自定义logger


class DialogueQuery:
    def __init__(self, db=None, if_test: bool = False):
        if not if_test:
            self.db = db
        else:
            self.engine = self.load_config()
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.db = next(self.get_db())

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
                engine = create_engine(DATABASE_URI,pool_recycle=3600,pool_pre_ping=True)
                return engine
        except FileNotFoundError:
            custom_logger.error(f"无法找到配置文件: {config_path}")
            raise
        except yaml.YAMLError as e:
            custom_logger.error(f"YAML 解析错误: {e}")
            raise
        except UnicodeDecodeError:
            custom_logger.error(f"文件编码错误,请确保 {config_path} 使用 UTF-8 编码")
            raise

    def get_db(self):
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @retry(
        stop=stop_after_attempt(3),  # 最大尝试次数
        wait=wait_exponential(multiplier=1, min=4, max=10),  # 指数退避算法等待时间
        retry=retry_if_exception_type((OperationalError, DBAPIError))  # 遇到特定异常时重试
    )
    def query_with_retry(self, db_session, query_func, *args, **kwargs):
        return query_func(db_session, *args, **kwargs)

    def perform_query(self, db_session, user_id):
        result = db_session.execute(
            text("""
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
            """),
            {"user_id": user_id}  # 使用参数化查询来防止SQL注入
        )
        return result.fetchall()

    def nickname_query(self, db_session, user_id):
        result = db_session.execute(
            text("""
                    SELECT a.name 
                    FROM t_account a
                    WHERE a.id = :user_id
            """),
            {"user_id": user_id}  # 使用参数化查询来防止SQL注入
        )
        row = result.fetchone()
        return row[0] if row else '陌生人'  # 如果有结果，则返回第一项，否则返回None

    def get_user_dialogue_history(self, user_id: str):
        try:
            print("我在这里")
            results = self.query_with_retry(self.db, self.perform_query, user_id)
            nickname = self.query_with_retry(self.db, self.nickname_query, user_id)
        except Exception as e:
            results = []
            nickname = '陌生人'
            custom_logger.error(f"Failed to execute query after retries: {e}")
        return self._process_query_results(results), nickname

    def _process_query_results(self, query_results):
        processed_results = []
        temp_dict = {}

        for query_result in query_results:
            user_msg = query_result[0]
            assistant_msg = query_result[1]
            timestamp = query_result[2]

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
    result, user_nickname = dialogue_query.get_user_dialogue_history('1000009')
    # result = dialogue_query.perform_query('1000004')
    print(result)
    print("user_nickname", user_nickname)
