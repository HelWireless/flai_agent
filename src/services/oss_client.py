from pathlib import Path
import os
import yaml
import oss2
from ..custom_logger import custom_logger

def get_oss_bucket():
    # 配置文件在 src/ 目录
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    
    # 从config中获取OSS配置
    oss_config = config['oss_key']
    
    access_key_id = oss_config['access_key_id']
    access_key_secret = oss_config['access_key_secret']
    endpoint = oss_config['endpoint']
    bucket_name = oss_config['bucket_name'] 
    
    # 创建OSS认证对象
    auth = oss2.Auth(access_key_id, access_key_secret)
    
    # 创建Bucket对象
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    
    custom_logger.info(f"OSS bucket '{bucket_name}' created successfully")
    
    return bucket

# 使用示例
if __name__ == "__main__":
    bucket = get_oss_bucket()
    # 现在您可以使用这个bucket对象进行OSS操作

