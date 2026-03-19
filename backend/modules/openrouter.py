import os
import requests
import json
from dotenv import load_dotenv

# .env файлын жүктейміз — қайда болса да табады
for path in ['.env', '../.env', '../../.env',
             os.path.join(os.path.dirname(__file__), '../../.env'),
             os.path.join(os.path.dirname(__file__), '../../../.env')]:
    if os.path.exists(path):
        load_dotenv(path)
        break


class OpenRouterClient:
    """
    OpenRouter API клиенті.
    Бесплатные модели: google/gemini-2.0-flash-exp:free және т.б.
    """

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    # Приоритет: бесплатные сначала, потом платные (дешёвые)
    MODELS = [
           "stepfun/step-3.5-flash:free"
                 

    ]

    SYSTEM_PROMPTS = {
        'general': (
            "Сен KazAI — қазақ тіліндегі жасанды интеллект көмекшісің. "
            "Қазақстан азаматтарына қазақша немесе орысша жауап бер. "
            "Қысқа, нақты, пайдалы жауаптар бер. Markdown қолдан."
        ),
        'gov': (
            "Сен Қазақстанның мемлекеттік қызметтері бойынша маман көмекшісің. "
            "egov.kz, ЦОН, мемлекеттік қызметтер туралы нақты ақпарат бер. "
            "Қадамдарды нөмірлеп жаз. Мерзімдер мен бағаларды көрсет."
        ),
        'tutor': (
            "Сен қазақ тілі репетиторысың. "
            "Грамматика қателерін тауып, дұрыс нұсқасын және ережені түсіндір. "
            "Мысалдармен дәлелде. Ынталандыратын тон қолдан."
        ),
    }

    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY', '')
        if not self.api_key:
            print("⚠️  OPENROUTER_API_KEY табылмады — .env файлын тексеріңіз")
        else:
            print(f"✅ OpenRouter API кілті жүктелді: {self.api_key[:12]}...")

    def ask(self, text: str, context: str = 'general', chat_history: list = None) -> str:
        if not self.api_key:
            return (
                "⚠️ OpenRouter API кілті конфигурацияланбаған.\n\n"
                "`.env` файлын ашып `OPENROUTER_API_KEY=sk-or-v1-...` жазыңыз."
            )

        system_prompt = self.SYSTEM_PROMPTS.get(context, self.SYSTEM_PROMPTS['general'])

        messages = [{'role': 'system', 'content': system_prompt}]
        if chat_history:
            messages.extend(chat_history[-6:])
        messages.append({'role': 'user', 'content': text})

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://kazai.onrender.com',
            'X-Title': 'KazAI',
        }

        for model in self.MODELS:
            try:
                payload = {
                    'model': model,
                    'messages': messages,
                    'max_tokens': 1024,
                    'temperature': 0.7,
                }
                resp = requests.post(
                    self.BASE_URL, headers=headers,
                    json=payload, timeout=30
                )

                if resp.status_code == 200:
                    data = resp.json()
                    content = data['choices'][0]['message']['content']
                    print(f"✅ OpenRouter [{model}] жауап берді")
                    return content

                elif resp.status_code == 429:
                    print(f"⏳ Rate limit [{model}], келесі модельге өту...")
                    continue

                elif resp.status_code == 401:
                    print(f"❌ API кілті жарамсыз!")
                    return "❌ API кілті жарамсыз. OpenRouter-дан жаңа кілт алыңыз."

                else:
                    print(f"⚠️ [{model}] қате {resp.status_code}: {resp.text[:200]}")
                    continue

            except requests.Timeout:
                print(f"⏱ Timeout [{model}]")
                continue
            except Exception as e:
                print(f"❌ [{model}] exception: {e}")
                continue

        return "Кешіріңіз, қазір ИИ қолжетімсіз. Кейінірек қайталап көріңіз."
