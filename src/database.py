from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import yaml
import os

# 获取当前脚本的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 构建config.yaml的绝对路径
config_path = os.path.join(current_dir, "config.yaml")

try:
    with open(config_path, "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
except FileNotFoundError:
    print(f"无法找到配置文件: {config_path}")
    # 可以在这里添加更多的错误处理逻辑
except yaml.YAMLError as e:
    print(f"YAML 解析错误: {e}")
except UnicodeDecodeError:
    print(f"文件编码错误,请确保 {config_path} 使用 UTF-8 编码")

DATABASE_URL = config["database"]["url"]
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

