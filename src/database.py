from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import yaml

# 加载配置
with open("config.yaml", "r") as config_file:
    config = yaml.safe_load(config_file)

DATABASE_URL = config["database"]["url"]
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
