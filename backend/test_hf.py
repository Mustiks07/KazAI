import requests, os, base64
from dotenv import load_dotenv
load_dotenv('../.env')

token = os.getenv('OPENROUTER_API_KEY')

# Кішкентай тест сурет
test_img_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

r = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={
        "model": "nvidia/nemotron-nano-12b-v2-vl:free",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{test_img_b64}"}},
                {"type": "text", "text": 'Is this AI generated? Reply ONLY JSON: {"score": 0-100}'}
            ]
        }],
        "max_tokens": 50,
        "temperature": 0.1
    },
    timeout=20
)
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:300]}")