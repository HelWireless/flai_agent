import base64
import uuid
import requests
from time import time
from ..custom_logger import custom_logger  # 导入自定义logger

class SpeechAPI:
    def __init__(self, config_, user_id=uuid.uuid4()):
        self.config = config_
        self.uid = user_id
        self.timestamp = int(time())
        self.req_id = f"{self.uid}_{self.timestamp}"

    def generate_request_body(self, text):
        request_body = {
            "app": {
                "appid": self.config["appid"],
                "token": self.config["access_token"],
                "cluster": self.config["cluster"]
            },
            "user": {
                "uid": self.uid
            },
            "audio": {
                "voice_type": self.config["voice_type"],
                "encoding": "mp3",
                "speed_ratio": 1.0,
                "volume_ratio": 1.0,
                "pitch_ratio": 1.0
            },
            "request": {
                "reqid": self.req_id,
                "text": text,
                "text_type": "plain",
                "operation": "query",
                "with_frontend": 1,
                "frontend_type": "unitTson"
            }
        }
        return request_body

    def send_request(self, api_url, request_body, output_path):
        headers = {
            "Authorization": f"Bearer;{self.config['access_token']}"
        }
        try:
            (f"Sending request to {api_url} with headers {headers} and body {request_body}")
            response = requests.post(api_url, json=request_body, headers=headers)
            custom_logger.info(f"HTTP status code: {response.status_code}")
            if response.status_code == 200:
                response_json = response.json()
                if "data" in response_json:
                    data = response_json["data"]
                    with open(output_path, "wb") as file_to_save:  # 保存为 MP3 文件
                        file_to_save.write(base64.b64decode(data))
                    custom_logger.info("MP3 文件已保存为 output.mp3")
                else:
                    custom_logger.error("响应中没有找到数据")
            else:
                custom_logger.error(f"HTTP 请求失败: {response.status_code}")
        except Exception as e:
            custom_logger.error(f"An error occurred: {e}")


if __name__ == "__main__":
    speech_api = SpeechAPI()
    text = "请输入要合成的文本"
    request_body = speech_api.generate_request_body(text)
    api_url = "https://openspeech.bytedance.com/api/v1/tts"
    speech_api.send_request(api_url, request_body)
