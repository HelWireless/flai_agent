import requests
import json

url = "http://localhost:8000/pillow/chat-pillow"
data = {
    "userId": "test_user",
    "message": "你好",
    "message_count": 1,
    "character_id": "default"
}

try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
