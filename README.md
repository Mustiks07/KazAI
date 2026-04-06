# KazAI — Қазақ тіліндегі AI көмекші

Қазақстан азаматтарына арналған көпмодальды жасанды интеллект көмекші.

## Мүмкіндіктер

### 1. Жалпы чат
- Кез-келген сұрақтарға қазақша/орысша жауап
- Чат контексті — AI алдыңғы хабарларды есте сақтайды
- 8 AI модельмен fallback жүйесі (Gemini, Llama, DeepSeek, Qwen)

### 2. Мемлекеттік қызметтер
- 80+ FAQ жазба — ИИН, ЭЦП, паспорт, жәрдемақы, салық, т.б.
- TF-IDF + кілт сөздер гибридті іздеу жүйесі
- egov.kz сілтемелерімен толық нұсқаулықтар
- Табылмаса — AI толықтырады

### 3. Қазақ тілі репетиторы
- 30+ грамматика ережесі (септіктер, жіктеу, жұрнақтар, емле)
- 250+ сөздік (қазақша ↔ орысша)
- Сөйлем тексеру — қателерді тауып, түзетеді
- Аударма функциясы

### 4. AI детекторы
- Мәтінді тексеру — адам жазды ма, AI жазды ма?
- Сурет және бейне анализі
- LLM-as-Judge + RoBERTa + статистикалық анализ

## Технологиялар

| Қабат | Технологиялар |
|-------|---------------|
| Backend | Python 3.11, Flask 3.0, SQLAlchemy |
| AI | OpenRouter API (Gemini, Llama, DeepSeek, Qwen) |
| ML | scikit-learn (TF-IDF), HuggingFace (RoBERTa) |
| Frontend | Vanilla JS, CSS Custom Properties |
| Деректер қоры | SQLite |
| Деплой | Render.com, Gunicorn |

## Жергілікті іске қосу

```bash
# 1. Виртуал ортаны жасау
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 2. Тәуелділіктерді орнату
pip install -r requirements.txt

# 3. .env файлын жасау
cp .env.example .env
# .env файлын ашып OPENROUTER_API_KEY жазыңыз

# 4. Іске қосу
cd backend
python app.py
```

Браузерде: **http://localhost:5000**

## API

| Метод | URL | Сипаттама |
|-------|-----|-----------|
| POST | `/api/auth/register` | Тіркелу |
| POST | `/api/auth/login` | Кіру |
| GET | `/api/auth/me` | Профиль |
| POST | `/api/chat` | Чат (контекстпен) |
| GET | `/api/history` | Чат тарихы |
| DELETE | `/api/history/:id` | Чатты жою |
| POST | `/api/detect/image` | Сурет анализі |
| POST | `/api/detect/video` | Бейне анализі |
| GET | `/api/stats` | Статистика |
| GET | `/api/health` | Сервер күйі |

## Архитектура

```
Пайдаланушы сұрағы
       ↓
Flask роутер (_detect_module) — кеңейтілген keyword scoring
       ↓
┌──────────────────────────────────────────┐
│ Мемлекеттік қызмет?  → TF-IDF + keywords │
│ Грамматика сұрағы?   → Ережелер + морфология │
│ AI анықтау?          → LLM-Judge + RoBERTa │
│ Жалпы сұрақ?         → OpenRouter (8 модель) │
└──────────────────────────────────────────┘
       ↓
LRU кэш (30 мин) → SQLite сақтау
       ↓
JSON жауап (контекстпен)
```
