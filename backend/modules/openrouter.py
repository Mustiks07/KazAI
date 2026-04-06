import os
import requests
import json
import logging
import hashlib
import time
from collections import OrderedDict
from dotenv import load_dotenv

for path in ['.env', '../.env', '../../.env',
             os.path.join(os.path.dirname(__file__), '../../.env'),
             os.path.join(os.path.dirname(__file__), '../../../.env')]:
    if os.path.exists(path):
        load_dotenv(path)
        break

logger = logging.getLogger(__name__)


class LRUCache:
    """Простой LRU-кэш для ответов AI."""

    def __init__(self, max_size=200, ttl=3600):
        self._cache = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl  # секунд

    def _make_key(self, text, context):
        raw = f"{context}:{text.strip().lower()}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, text, context):
        key = self._make_key(text, context)
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry['time'] < self._ttl:
                self._cache.move_to_end(key)
                logger.info("Cache hit: %s...", text[:40])
                return entry['value']
            else:
                del self._cache[key]
        return None

    def put(self, text, context, value):
        key = self._make_key(text, context)
        self._cache[key] = {'value': value, 'time': time.time()}
        self._cache.move_to_end(key)
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)


class OpenRouterClient:
    """
    OpenRouter API клиенті — контекст, кэш, fallback модельдер.
    """

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    # Приоритет: качественные модели для казахского языка
    MODELS = [
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-4-maverick:free",
        "meta-llama/llama-4-scout:free",
        "deepseek/deepseek-chat-v3-0324:free",
        "google/gemma-3-27b-it:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
        "qwen/qwen3-32b:free",
        "meta-llama/llama-3.3-70b-instruct:free",
    ]

    SYSTEM_PROMPTS = {
        'general': (
            "Сен KazAI — қазақ тіліндегі жасанды интеллект көмекшісің. "
            "Қазақстан азаматтарына көмектесесің.\n\n"
            "ЕРЕЖЕЛЕР:\n"
            "1. Пайдаланушы қай тілде жазса, сол тілде жауап бер (қазақша/орысша/ағылшынша).\n"
            "2. Қысқа, нақты, пайдалы жауаптар бер.\n"
            "3. Markdown форматын қолдан: **қалың**, *курсив*, тізімдер, кодтар.\n"
            "4. Білмесеңіз — шынын айт, ойдан шығарма.\n"
            "5. Қазақстан контекстін ескер (заңдар, мәдениет, география).\n"
            "6. Сұрақтың мағынасына қарай толық жауап бер, бір-екі сөзбен емес."
        ),
        'gov': (
            "Сен Қазақстанның мемлекеттік қызметтері бойынша маман көмекшісің.\n\n"
            "ЕРЕЖЕЛЕР:\n"
            "1. egov.kz, eGov Mobile, ЦОН, мемлекеттік қызметтер туралы нақты ақпарат бер.\n"
            "2. Қадамдарды нөмірлеп, анық жаз.\n"
            "3. Мерзімдер мен бағаларды көрсет (мысалы: «3-5 жұмыс күні», «тегін»).\n"
            "4. Қажетті құжаттар тізімін бер.\n"
            "5. Ақпарат жоқ болса — 1414 нөміріне немесе egov.kz сайтына жіберіңіз деп айт.\n"
            "6. Жауап тілі — пайдаланушы қай тілде жазса, сол тілде.\n"
            "7. Ескірген ақпарат берме — білмесең, тексеруге кеңес бер."
        ),
        'tutor': (
            "Сен қазақ тілі репетиторысың — тәжірибелі, жылы, шыдамды мұғалім.\n\n"
            "ЕРЕЖЕЛЕР:\n"
            "1. Грамматика қателерін тауып, дұрыс нұсқасын және ережені түсіндір.\n"
            "2. Мысалдар бер — ❌ қате → ✅ дұрыс форматында.\n"
            "3. Ережені қысқа және түсінікті етіп жаз.\n"
            "4. Ынталандыр — жақсы жазылған болса, мақта.\n"
            "5. Қиын тақырыптарды қарапайым тілмен түсіндір.\n"
            "6. Аударма сұрағанда — контексті де түсіндір.\n"
            "7. Септіктер, жіктеулік жалғау, шақтар — мысалдармен түсіндір."
        ),
    }

    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY', '')
        self.cache = LRUCache(max_size=300, ttl=1800)  # 30 мин кэш

        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY табылмады — .env файлын тексерiңiз")
        else:
            logger.info("OpenRouter API кілті жүктелді: %s...", self.api_key[:12])

    def ask(self, text: str, context: str = 'general', chat_history: list = None) -> str:
        """
        AI-ға сұрақ жіберу.

        Args:
            text: Пайдаланушы мәтіні
            context: Контекст түрі (general/gov/tutor)
            chat_history: Алдыңғы хабарлар тізімі [{role, content}, ...]
        """
        if not self.api_key:
            return (
                "API кілті конфигурацияланбаған.\n\n"
                "`.env` файлын ашып `OPENROUTER_API_KEY=sk-or-v1-...` жазыңыз.\n"
                "Кілтті https://openrouter.ai сайтынан алуға болады."
            )

        # Кэш тексеру (тек history жоқ болса — жаңа чат)
        if not chat_history:
            cached = self.cache.get(text, context)
            if cached:
                return cached

        system_prompt = self.SYSTEM_PROMPTS.get(context, self.SYSTEM_PROMPTS['general'])

        messages = [{'role': 'system', 'content': system_prompt}]

        # Чат контекстін қосу — AI алдыңғы сөйлесуді есте сақтайды
        if chat_history:
            # Соңғы 10 хабарды жіберу (5 пар: user + assistant)
            recent = chat_history[-10:]
            for msg in recent:
                if msg.get('role') in ('user', 'assistant') and msg.get('content'):
                    messages.append({
                        'role': msg['role'],
                        'content': msg['content'][:500]  # Әр хабарды шектеу
                    })

        messages.append({'role': 'user', 'content': text})

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://kazai.onrender.com',
            'X-Title': 'KazAI',
        }

        last_error = None
        for model in self.MODELS:
            try:
                payload = {
                    'model': model,
                    'messages': messages,
                    'max_tokens': 1500,
                    'temperature': 0.7,
                }
                resp = requests.post(
                    self.BASE_URL, headers=headers,
                    json=payload, timeout=35
                )

                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get('choices', [])
                    if choices:
                        content = choices[0].get('message', {}).get('content', '')
                        if content and content.strip():
                            logger.info("OpenRouter [%s] жауап берді (%d таңба)",
                                        model.split('/')[-1], len(content))
                            # Кэшке сақтау
                            if not chat_history:
                                self.cache.put(text, context, content)
                            return content
                    logger.warning("[%s] бос жауап, келесіге...", model.split('/')[-1])
                    continue

                elif resp.status_code == 429:
                    logger.warning("Rate limit [%s], келесі модельге...", model.split('/')[-1])
                    last_error = "rate_limit"
                    continue

                elif resp.status_code == 401:
                    logger.error("API кілті жарамсыз!")
                    return "API кілті жарамсыз. OpenRouter-дан жаңа кілт алыңыз: https://openrouter.ai"

                elif resp.status_code in (503, 502):
                    logger.warning("[%s] қолжетімсіз (%d)", model.split('/')[-1], resp.status_code)
                    last_error = "unavailable"
                    continue

                else:
                    logger.warning("[%s] HTTP %d: %s", model.split('/')[-1],
                                   resp.status_code, resp.text[:150])
                    last_error = f"http_{resp.status_code}"
                    continue

            except requests.Timeout:
                logger.warning("Timeout [%s]", model.split('/')[-1])
                last_error = "timeout"
                continue
            except requests.ConnectionError:
                logger.error("Интернет байланысы жоқ")
                return "Интернет байланысын тексеріңіз."
            except Exception as e:
                logger.error("[%s] exception: %s", model.split('/')[-1], e)
                last_error = str(e)
                continue

        # Барлық модельдер сәтсіз болса
        if last_error == "rate_limit":
            return (
                "Барлық модельдер қазір бос емес.\n\n"
                "Бірнеше секунд күтіп, қайталап көріңіз.\n"
                "Мәселе жалғасса — кейінірек оралыңыз."
            )
        return (
            "Кешіріңіз, қазір AI қолжетімсіз.\n\n"
            "Интернетті тексеріңіз немесе кейінірек қайталап көріңіз."
        )
