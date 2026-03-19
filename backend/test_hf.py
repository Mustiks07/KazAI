import requests, os
from dotenv import load_dotenv
load_dotenv('../.env')

token = os.getenv('HUGGINGFACE_TOKEN')
headers = {"Authorization": f"Bearer {token}"}

texts = [
    "Укладка декоративной штукатурки это комплексная отделочная услуга включающая подготовку поверхности",
    "штукатурку нанес сам первый раз получилось криво пришлось переделывать",
    "следует отметить что данная проблема имеет важное значение в рамках исследования",
    "блин забыл совсем купить молоко жена расстроилась",
]

models = [
    "valurank/distilroberta-ai-text-detection",
    "Hello-SimpleAI/chatgpt-detector-roberta-chinese",
    "roberta-base-openai-detector",
]

for model in models:
    url = f"https://router.huggingface.co/hf-inference/models/{model}"
    r = requests.post(url, headers=headers, json={"inputs": texts[0]}, timeout=30)
    print(f"{r.status_code} — {model}")
    if r.status_code == 200:
        print(f"  ✅ {r.text[:200]}")
    else:
        print(f"  ❌ {r.text[:100]}")