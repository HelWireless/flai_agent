import requests
from typing import Optional
import os
import yaml

class SpeechAPI:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url

    def text_to_speech(self, text: str, voice: str = "default") -> Optional[bytes]:
        """
        将文本转换为语音
        """
        url = f"{self.base_url}/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "tts-1",  # 假设使用的是类似OpenAI的模型名称
            "input": text,
            "voice": voice
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            return response.content
        else:
            print(f"Error: {response.status_code}, {response.text}")
            return None

    def speech_to_text(self, audio_file) -> Optional[str]:
        """
        将语音转换为文本
        """
        url = f"{self.base_url}/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        files = {
            "file": audio_file,
            "model": "whisper-1"  # 假设使用的是类似OpenAI的模型名称
        }
        
        response = requests.post(url, headers=headers, files=files)
        
        if response.status_code == 200:
            return response.json()["text"]
        else:
            print(f"Error: {response.status_code}, {response.text}")
            return None

# 读取配置文件
def load_config(config_path):
    # 获取当前工作目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 拼接绝对路径
    absolute_path = os.path.join(current_dir, config_path)
    with open(absolute_path, 'r', encoding='utf-8') as file:  # 修改这里，添加 encoding='utf-8'
        config = yaml.safe_load(file)
    return config

def synthesize_speech(config, text, speaker_id):
    # 确保 'access_token' 存在于 config 字典中
    if 'access_token' not in config:
        raise KeyError("The 'access_token' key is missing from the config dictionary.")
    
    url = "https://openspeech.bytedance.com/api/v1/mega_tts/synthesize"
    headers = {
        "Authorization": f"Bearer;{config['access_token']}",
        "Content-Type": "application/json"
    }
    payload = {
        "appid": config['appid'],
        "text": text,
        "speaker_id": speaker_id,
        "cluster": "volcano_mega",
        "voice_type": speaker_id
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        result = response.json()
        if result["BaseResp"]["StatusCode"] == 0:
            audio_data = base64.b64decode(result["audio"])
            with open("output.wav", "wb") as audio_file:
                audio_file.write(audio_data)
            print("语音合成成功，音频已保存为 output.wav")
        else:
            print(f"语音合成失败: {result['BaseResp']['StatusMessage']}")
    else:
        print(f"HTTP 请求失败: {response.status_code}")

# 测试部分
if __name__ == "__main__":
    config_path = 'config.yaml'
    config = load_config(config_path)
    text = "你好，这是一个语音合成示例。"
    speaker_id = "S_LDfNJ5E11"
    synthesize_speech(config, text, speaker_id)

