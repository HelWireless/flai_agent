"""
对话查询服务 - 从数据库获取对话历史
"""
import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy.exc import OperationalError, DBAPIError
from typing import List, Dict, Optional, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
import yaml
import urllib
from ..custom_logger import custom_logger

# 常量定义
TYPE_TEXT = (1, 2)      # 文字对话类型
TYPE_VOICE = (3, 4)     # 语音对话类型


class DialogueQuery:
    """对话查询服务"""
    
    def __init__(self, db: Optional[Session] = None, if_test: bool = False):
        if not if_test:
            self.db = db
        else:
            self.engine = self._load_config()
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.db = next(self._get_db())
    
    def _load_config(self):
        """加载数据库配置（测试模式）"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "config.yaml")
        
        try:
            with open(config_path, "r", encoding="utf-8") as config_file:
                config = yaml.safe_load(config_file)
                encoded_password = urllib.parse.quote(config["database"]["password"])
                host = config["database"]["host"]
                username = config["database"]["username"]
                database_name = config["database"].get("database_name", "pillow_customer_prod")
                DATABASE_URI = f'mysql+pymysql://{username}:{encoded_password}@{host}/{database_name}'
                
                engine = create_engine(DATABASE_URI, pool_recycle=3600, pool_pre_ping=True)
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
    
    def _get_db(self):
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((OperationalError, DBAPIError))
    )
    def query_with_retry(self, db_session: Session, query_func, *args, **kwargs):
        return query_func(db_session, *args, **kwargs)
    
    def _query_dialogue_history(
        self, db_session: Session, user_id: str, table_name: str,
        if_voice: bool = False, character_id: Optional[str] = None
    ) -> List:
        """统一的对话历史查询（合并了两个重复方法）"""
        type_num = TYPE_VOICE if if_voice else TYPE_TEXT
        
        if character_id:
            where_clause = "account_id = :user_id AND third_character_id = :character_id"
            params = {"user_id": user_id, "character_id": character_id, "type_num": type_num}
        else:
            where_clause = "account_id = :user_id"
            params = {"user_id": user_id, "type_num": type_num}
        
        result = db_session.execute(
            text(f"""
                SELECT message, text, create_time
                FROM {table_name}
                WHERE {where_clause}
                AND create_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                AND type in :type_num
                ORDER BY create_time DESC
                LIMIT 20
            """),
            params
        )
        return result.fetchall()
    
    def _query_nickname(self, db_session: Session, user_id: str) -> str:
        """查询用户昵称"""
        result = db_session.execute(
            text("SELECT name FROM t_account WHERE id = :user_id"),
            {"user_id": user_id}
        )
        row = result.fetchone()
        return row[0] if row else '陌生人'
    
    def get_user_pillow_dialogue_history(
        self, user_id: str, if_voice: bool = False
    ) -> Tuple[List[Dict], str]:
        """获取用户与默认角色的对话历史"""
        try:
            results = self.query_with_retry(self.db, self._query_dialogue_history, 
                                           user_id, "t_dialogue", if_voice)
            nickname = self.query_with_retry(self.db, self._query_nickname, user_id)
        except Exception as e:
            results = []
            nickname = '陌生人'
            custom_logger.error(f"Failed to execute query after retries: {e}")
        return self._process_query_results(results), nickname
    
    def get_user_third_character_dialogue_history(
        self, user_id: str, character_id: str, if_voice: bool = False
    ) -> Tuple[List[Dict], str]:
        """获取用户与第三方角色的对话历史"""
        results = self.query_with_retry(self.db, self._query_dialogue_history,
                                       user_id, "t_third_character_dialogue", if_voice, character_id)
        nickname = self.query_with_retry(self.db, self._query_nickname, user_id)
        return self._process_query_results(results, reverse=False), nickname
    
    def _process_query_results(self, query_results: List, reverse: bool = True) -> List[Dict]:
        """处理查询结果，转换为对话格式"""
        temp_dict = {}
        
        for query_result in query_results:
            user_msg, assistant_msg, timestamp = query_result
            
            if timestamp not in temp_dict:
                temp_dict[timestamp] = {"user": "", "assistant": ""}
            
            if user_msg:
                temp_dict[timestamp]["user"] = user_msg
            if assistant_msg:
                if temp_dict[timestamp]["assistant"]:
                    temp_dict[timestamp]["assistant"] += " " + assistant_msg
                else:
                    temp_dict[timestamp]["assistant"] = assistant_msg
        
        # 排序并取最近7轮对话
        sorted_keys = sorted(temp_dict.keys(), reverse=reverse)
        processed_results = []
        
        for key in sorted_keys[:7]:
            if temp_dict[key]["user"]:
                processed_results.append({"role": "user", "content": temp_dict[key]["user"]})
            if temp_dict[key]["assistant"]:
                processed_results.append({"role": "assistant", "content": temp_dict[key]["assistant"]})
        
        return processed_results


if __name__ == "__main__":
    dialogue_query = DialogueQuery(if_test=True)
    result, user_nickname = dialogue_query.get_user_pillow_dialogue_history('1000003')
    tmp, _ = dialogue_query.get_user_third_character_dialogue_history("1000003", "c1s2c6_0016")
    print(f"默认角色: {len(result)} 条, 昵称: {user_nickname}")
    print(f"第三方角色: {len(tmp)} 条")
