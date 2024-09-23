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
import os

class SpeechAPI:
    def __init__(self, config_path):
        self.config = self.load_config(config_path)

    def load_config(self, config_path):
        with open(config_path, 'r', encoding='utf-8') as file:  # 添加 encoding='utf-8'
            config = yaml.safe_load(file)["speech_api"]
        return config

    def generate_request_body(self, text):
        request_body = {
            "app": {
                "appid": self.config["appid"],
                "token": self.config["access_token"],
                "cluster": self.config["cluster"]
            },
            "user": {
                "uid": str(uuid.uuid4())
            },
            "audio": {
                "voice_type": self.config["voice_type"],
                "encoding": "mp3",
                "speed_ratio": 1.0,
                "volume_ratio": 1.0,
                "pitch_ratio": 1.0
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": text,
                "text_type": "plain",
                "operation": "query",
                "with_frontend": 1,
                "frontend_type": "unitTson"
            }
        }
        return request_body

    def send_request(self, api_url, request_body):
        headers = {
            "Authorization": f"Bearer;{self.config['access_token']}"
        }
        try:
            print(f"Sending request to {api_url} with headers {headers} and body {request_body}")
            response = requests.post(api_url, json=request_body, headers=headers)
            print(f"HTTP status code: {response.status_code}")
            print(f"Response body: {response.text}")
            if response.status_code == 200:
                response_json = response.json()
                if "data" in response_json:
                    data = response_json["data"]
                    with open("output.mp3", "wb") as file_to_save:  # 保存为 MP3 文件
                        file_to_save.write(base64.b64decode(data))
                    print("MP3 文件已保存为 output.mp3")
                else:
                    print("响应中没有找到数据")
            else:
                print(f"HTTP 请求失败: {response.status_code}")
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    config_path = 'src/config.yaml'  # 使用相对路径
    speech_api = SpeechAPI(config_path)
    text = input("请输入要合成的文本: ")
    request_body = speech_api.generate_request_body(text)
    api_url = "https://openspeech.bytedance.com/api/v1/tts"
    speech_api.send_request(api_url, request_body)