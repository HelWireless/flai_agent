import yaml
from openai import OpenAI

# 加载配置
with open("src/config.yaml", "r", encoding="utf-8") as config_file:
    config = yaml.safe_load(config_file)

# OpenAI 配置
client = OpenAI(
    api_key=config["deepseek"]["api_key"],
    base_url=config["deepseek"]["base_url"]
)
COMPLETION_MODEL = config["deepseek"]["completion_model"]



response = client.chat.completions.create(
model=COMPLETION_MODEL,
messages=[
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "你好"}
]
)

print(response.choices[0].message.content)