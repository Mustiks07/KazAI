import requests, os
from dotenv import load_dotenv
load_dotenv('../.env')

token = os.getenv('OPENROUTER_API_KEY')

models = [
    "arcee-ai/trinity-large-preview:free"
]

prompt = """Analyze this text and respond ONLY with JSON {"score": 0-100, "reason": "brief"}.
score: 0=human, 100=AI generated.

Text: "Следует отметить что данная проблема имеет важное значение в рамках исследования таким образом можно сделать вывод" """

print(f"{'Модель':<45} {'Статус':<8} {'Жауап'}")
print("-" * 90)

for model in models:
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 80, "temperature": 0.1},
            timeout=15
        )
        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content'] or ''
            print(f"{model:<45} ✅ {r.status_code}   {content[:60]}")
        else:
            print(f"{model:<45} ❌ {r.status_code}   {r.text[:50]}")
    except Exception as e:
        print(f"{model:<45} ⚠️  ERR   {str(e)[:50]}")