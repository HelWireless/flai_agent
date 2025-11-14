from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import yaml
import os
import urllib
from pathlib import Path

# 获取当前脚本的目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 更可靠地构建config.yaml的绝对路径
# 首先尝试从项目根目录查找config文件夹
project_root = Path(__file__).parent.parent
config_path = project_root / "config" / "config.yaml"

# 如果上面的路径不存在，尝试其他可能的路径
if not config_path.exists():
    # 尝试从当前工作目录下的config文件夹查找
    config_path = Path.cwd() / "config" / "config.yaml"

# 再次检查，如果仍然找不到，尝试直接使用相对路径
if not config_path.exists():
    config_path = Path("config") / "config.yaml"

print(f"正在尝试加载配置文件: {config_path}")
print(f"配置文件是否存在: {config_path.exists()}")

config = {}

try:
    with open(config_path, "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
        print("配置文件加载成功")
except FileNotFoundError:
    print(f"无法找到配置文件: {config_path}")
    print("请确保已创建配置文件，可以通过复制 config/config.yaml.example 到 config/config.yaml 来创建")
except yaml.YAMLError as e:
    print(f"YAML 解析错误: {e}")
except UnicodeDecodeError:
    print(f"文件编码错误,请确保 {config_path} 使用 UTF-8 编码")
except Exception as e:
    print(f"加载配置文件时发生未知错误: {e}")

# 确保config存在且包含database键再尝试访问
if config and "database" in config and "password" in config["database"]:
    encoded_password = urllib.parse.quote(config["database"]["password"])
    host = config["database"]["host"]
    username = config["database"]["username"]
    database_name = config["database"].get("database_name", "pillow_customer_prod")
    DATABASE_URI = f'mysql+pymysql://{username}:{encoded_password}@{host}/{database_name}'
    engine = create_engine(DATABASE_URI, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    print("数据库配置加载成功")
else:
    print("警告: 数据库配置不完整，将使用空数据库配置")
    engine = None
    SessionLocal = None

def get_db():
    if SessionLocal is None:
        raise RuntimeError("数据库未正确配置，请检查配置文件")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()