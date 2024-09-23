#coding=utf-8

'''
requires Python 3.6 or later
pip install requests pyyaml
'''
import base64
import json
import uuid
import requests
import yaml

def load_config(config_path):
    with open(config_path, 'r', encoding='utf-8') as file:  # 添加 encoding='utf-8'
        config = yaml.safe_load(file)
    return config

# 加载配置文件
config = load_config('config.yaml')

appid = config['appid']
access_token = config['access_token']
cluster = config['cluster']
voice_type = config['voice_type']
host = config['host']
api_url = f"https://{host}/api/v1/tts"

header = {
    "Authorization": f"Bearer {access_token}",
    "Resource-Id": "VoiceCloning7406618528462278963"  # 添加 Resource-Id
}

request_json = {
    "app": {
        "appid": appid,
        "token": access_token,  # 使用变量 access_token
        "cluster": cluster
    },
    "user": {
        "uid": "388808087185088"
    },
    "audio": {
        "voice_type": voice_type,
        "encoding": "mp3",
        "speed_ratio": 1.0,
        "volume_ratio": 1.0,
        "pitch_ratio": 1.0,
    },
    "request": {
        "reqid": str(uuid.uuid4()),
        "text": "字节跳动语音合成",
        "text_type": "plain",
        "operation": "query",
        "with_frontend": 1,
        "frontend_type": "unitTson"
    }
}

if __name__ == '__main__':
    try:
        print(f"Sending request to {api_url} with headers {header} and body {request_json}")
        resp = requests.post(api_url, json=request_json, headers=header)  # 使用 json=request_json
        print(f"HTTP status code: {resp.status_code}")
        print(f"Response body: {resp.text}")
        if resp.status_code == 200 and "data" in resp.json():
            data = resp.json()["data"]
            with open("test_submit.mp3", "wb") as file_to_save:  # 使用 with 语句确保文件正确关闭
                file_to_save.write(base64.b64decode(data))
        else:
            print(f"HTTP 请求失败: {resp.status_code}")
    except Exception as e:
        print(f"An error occurred: {e}")  # 打印错误信息