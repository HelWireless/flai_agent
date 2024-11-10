import yaml

# 加载配置
with open("src/config.yaml", "r", encoding="utf-8") as config_file:
    config = yaml.safe_load(config_file)

api_base = config["llm"]["api_base"]

COMPLETION_MODEL = config["llm"]["completion_model"]

input = {"id": "a2ffc9c6-7b64-5e3a-ad12-ed248ce1b2df", "model": "qwen",
         "messages": [{"role": "system", "content": "你是情绪判断专家，你会根据用户的要求来进行情绪判断。"},
                      {"role": "user", "content": "你好啊"}]}
