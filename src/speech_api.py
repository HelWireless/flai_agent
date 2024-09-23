import requests
from typing import Optional
import os
import yaml
import base64

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
    if 'access_token' not in config["speech_api"]:
        raise KeyError("The 'access_token' key is missing from the config dictionary.")
    
    url = "https://openspeech.bytedance.com/api/v1/tts"
    headers = {
        "Authorization": f"Bearer;{config['speech_api']['access_token']}",
        "Content-Type": "application/json"
    }
    payload = {
        "appid": config['speech_api']['appid'],
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

