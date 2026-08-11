import os
import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("AI_BUILDER_API_KEY")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Test models
for model_name in ["grok-4-fast", "gemini-3-flash-preview", "deepseek-v4-flash"]:
    chat_url = "https://space.ai-builders.com/backend/v1/chat/completions"
    chat_payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Say hello in 5 words."}]
    }

    try:
        c_res = requests.post(chat_url, json=chat_payload, headers=headers)
        print(f"Model [{model_name}] Status: {c_res.status_code}")
        if c_res.status_code == 200:
            print("Response:", c_res.json()["choices"][0]["message"]["content"])
            break
    except Exception as e:
        print("Chat Error:", e)
