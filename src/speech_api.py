import requests
from typing import Optional

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

# 初始化 SpeechAPI 实例
speech_api = SpeechAPI("your-speech-api-key", "https://api.example.com")
