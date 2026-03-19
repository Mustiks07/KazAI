# KazAI — Қазақ тіліндегі ЖИ көмекші

## 🗂 Жоба құрылымы

```
kazai/
├── backend/
│   ├── app.py              ← Flask сервер (негізгі файл)
│   ├── database.py         ← SQLite модельдер
│   ├── modules/
│   │   ├── openrouter.py   ← OpenRouter API клиенті
│   │   ├── gov_service.py  ← Мемлекеттік қызметтер (TF-IDF)
│   │   ├── tutor.py        ← Қазақ тілі репетиторы
│   │   └── detector.py     ← ЖИ контент детекторы
│   └── data/
│       ├── gov_faq.json    ← 15+ мемлекеттік қызмет FAQ
│       ├── grammar_rules.json ← 8 грамматика ережесі
│       └── kazakh_vocab.json  ← сөздік (қосымша)
├── frontend/
│   └── kazai.html          ← UI (барлығы бір файлда)
├── requirements.txt
├── render.yaml             ← Render.com деплой конфиги
├── .env.example            ← .env үлгісі
└── README.md
```

---

## 🚀 Жергілікті іске қосу (Windows)

### 1. Python виртуал ортасын жасаңыз
```bash
cd kazai
python -m venv venv
venv\Scripts\activate
```

### 2. Тәуелділіктерді орнатыңыз
```bash
pip install -r requirements.txt
```

### 3. .env файлын жасаңыз
```bash
copy .env.example .env
```
`.env` файлын ашып, өз OpenRouter API кілтіңізді жазыңыз:
```
OPENROUTER_API_KEY=sk-or-v1-ваш-ключ-здесь
```

### 4. Іске қосыңыз
```bash
cd backend
python app.py
```

✅ Браузерде ашыңыз: **http://localhost:5000**

---

## 🌐 Render.com деплой (интернетке шығару)

### 1. GitHub-қа жүктеңіз
```bash
git init
git add .
git commit -m "Initial KazAI commit"
git remote add origin https://github.com/СІЗДІҢ_АККАУНТ/kazai.git
git push -u origin main
```

### 2. Render.com-да жаңа сервис жасаңыз
1. render.com → New → Web Service
2. GitHub репоны байланыстырыңыз
3. Environment Variables қосыңыз:
   - `OPENROUTER_API_KEY` = сіздің кілт
   - `SECRET_KEY` = кез-келген ұзын string
   - `JWT_SECRET` = кез-келген ұзын string
4. Deploy!

5-10 минуттан кейін:  
**https://kazai.onrender.com** — сіздің URL!

---

## ⚙️ API эндпоинттері

| Метод | URL | Сипаттама |
|-------|-----|-----------|
| POST | `/api/auth/register` | Тіркелу |
| POST | `/api/auth/login` | Кіру |
| GET | `/api/auth/me` | Профиль |
| POST | `/api/chat` | Чат (негізгі) |
| GET | `/api/history` | Тарих |
| DELETE | `/api/history/:id` | Тарихты жою |
| POST | `/api/subscription` | Жоспарды өзгерту |
| GET | `/api/stats` | Статистика |

---

## 🧠 Архитектура

```
Пайдаланушы сұрағы
       ↓
Flask роутер (_detect_module)
       ↓
┌──────────────────────────────┐
│ Мемлекеттік қызмет сұрағы?  │ → gov_service.py (TF-IDF)
│ Грамматика сұрағы?           │ → tutor.py (ережелер)
│ ЖИ анықтау?                  │ → detector.py (статистика)
│ Жалпы сұрақ?                 │ → OpenRouter API (Gemini/Llama)
└──────────────────────────────┘
       ↓
SQLite-ге сақтау
       ↓
JSON жауап фронтке
```

---

## 📚 Конференция үшін маңызды

**Техникалық үлес:**
- Өз TF-IDF іздеу алгоритмі (sklearn)
- Морфологиялық талдау (туtor.py)
- Статистикалық ЖИ детектор (detector.py)
- Гибридті архитектура (өз модульдер + LLM)

**Қолданылған технологиялар:**
- Python 3.11, Flask 3.0
- SQLite (деректер қоры)
- scikit-learn (ML)
- OpenRouter API (LLM)
- JWT (авторизация)
- Render.com (деплой)
