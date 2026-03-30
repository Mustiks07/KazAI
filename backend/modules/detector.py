import re, os, math, pickle, requests, json, base64
from collections import Counter


# ══════════════════════════════════════════
# МӘТІН ДЕТЕКТОРЫ
# ══════════════════════════════════════════
class TextDetector:
    HF_URL     = "https://router.huggingface.co/hf-inference/models/openai-community/roberta-base-openai-detector"
    MODEL_PATH = os.path.join(os.path.dirname(__file__), '../models/ai_detector.pkl')

    AI_MARKERS_KZ = [
        'сонымен қатар','атап айтқанда','маңызды рөл атқарады',
        'қорытындылай келе','жоғарыда айтылғандай','тиімді болып табылады',
        'аталған мәселе','осы орайда','айта кету керек','тұжырымдай келе',
        'болып табылады','практикалық маңызы','теориялық негіздері',
        'негізгі мақсат','ерекше атап өту','зерттеу барысында',
        'жүргізілген талдау','жан-жақты қарастырылған',
    ]
    AI_MARKERS_RU = [
        'следует отметить','таким образом','в заключение','стоит отметить',
        'необходимо подчеркнуть','подводя итог','в данном контексте',
        'резюмируя вышесказанное','кроме того','важно подчеркнуть',
        'полученные результаты','проведённый анализ','данная проблема',
        'позволяет реализовать','отличается высокой','обеспечивая',
        'включает подготовку','характеризуется','предполагает',
        'представляет собой','является неотъемлемой','способствует развитию',
        'в рамках данного','на основании вышеизложенного',
    ]
    AI_MARKERS_EN = [
        'furthermore','moreover','in conclusion','it is worth noting',
        'it should be noted','in this context','to summarize',
        'plays a crucial role','it is important to emphasize',
        'as mentioned above','based on the above',
    ]

    # Адам жазған мәтінге тән белгілер
    HUMAN_MARKERS = [
        'хаха','лол','ойбай','блин','ладно','ок','эх','кстати','вообще',
        'короче','ну','типа','прикол','да ладно','не знаю','наверное',
        'кажется','честно говоря','по-моему','мне кажется',
        'айтайын', 'білемін', 'ойлаймын', 'сезінемін',
    ]

    def __init__(self):
        self.hf_token   = os.getenv('HUGGINGFACE_TOKEN', '')
        self.or_api_key = os.getenv('OPENROUTER_API_KEY', '')
        self.model      = None
        if self.or_api_key:
            print("✅ OpenRouter — LLM-as-Judge мәтін детектор режимі")
        if self.hf_token:
            print("✅ HuggingFace токені — RoBERTa резерв режимі")
        try:
            with open(self.MODEL_PATH, 'rb') as f:
                self.model = pickle.load(f)
            print("✅ Резерв ML модель жүктелді")
        except FileNotFoundError:
            pass

    def analyze(self, text):
        text = text.strip()
        if len(text) < 30:
            return {
                'score': 0,
                'verdict': 'short',
                'label': 'Мәтін тым қысқа',
                'text': '⚠️ Нақты талдау үшін кем дегенде 30 таңба қажет.\n\nТолығырақ мәтін жіберіңіз.',
            }

        f = self._features(text)

        # 1. LLM-as-Judge — НЕГІЗГІ (OpenRouter бар болса)
        if self.or_api_key:
            llm = self._llm_judge(text)
            if llm is not None:
                llm_score, llm_reason, llm_detail = llm
                # Маркерлер бонус/штраф: нақты калибровка
                marker_bonus = min(f['markers'] * 3, 12)
                human_penalty = min(f['human_markers'] * 4, 15)
                score = max(2, min(97, int(llm_score) + marker_bonus - human_penalty))
                verdict = 'ai' if score >= 50 else 'human'
                label = 'Жасанды интеллект жазған болуы мүмкін' if verdict == 'ai' else 'Адам жазған сияқты'
                return {
                    'score': score,
                    'verdict': verdict,
                    'label': label,
                    'text': self._explain(score, f, verdict, 'LLM-as-Judge', llm_reason, llm_detail),
                }

        # 2. RoBERTa
        if self.hf_token:
            roberta = self._roberta_score(text)
            if roberta is not None:
                score = max(2, min(97, roberta + min(f['markers'] * 3, 10) - min(f['human_markers'] * 4, 12)))
                verdict = 'ai' if score >= 50 else 'human'
                label = 'Жасанды интеллект жазған болуы мүмкін' if verdict == 'ai' else 'Адам жазған сияқты'
                return {
                    'score': score,
                    'verdict': verdict,
                    'label': label,
                    'text': self._explain(score, f, verdict, 'OpenAI RoBERTa'),
                }

        # 3. ML резерв
        if self.model:
            try:
                prob  = float(self.model.predict_proba([text])[0][1])
                score = max(2, min(97, int(prob * 100) + min(f['markers'] * 4, 12) - min(f['human_markers'] * 3, 10)))
                method = 'TF-IDF ML модель'
            except Exception:
                score  = self._stat_score(f)
                method = 'Статистикалық талдау'
        else:
            score  = self._stat_score(f)
            method = 'Статистикалық талдау'

        verdict = 'ai' if score >= 50 else 'human'
        label   = 'Жасанды интеллект жазған болуы мүмкін' if verdict == 'ai' else 'Адам жазған сияқты'
        return {
            'score': score,
            'verdict': verdict,
            'label': label,
            'text': self._explain(score, f, verdict, method),
        }

    def _llm_judge(self, text):
        """
        LLM-as-Judge: нақты, толық анықтама жасайды.
        JSON форматы: {"score": 0-100, "reason": "...", "signs": [...]}
        """
        # Тілді анықтау
        kz_chars = sum(1 for c in text if c in 'әіңғүұқөһ')
        lang_hint = "Kazakh" if kz_chars > 3 else "Russian or mixed"

        prompt = f"""You are an expert AI text detector. Your task is to determine if the text below was written by AI (ChatGPT, Claude, etc.) or by a human.

Text language: {lang_hint}

TEXT TO ANALYZE:
\"\"\"
{text[:1200]}
\"\"\"

Analyze carefully:

AI-WRITTEN signs:
- Template phrases and clichés ("it is worth noting", "таким образом", "сонымен қатар")
- Unnaturally perfect grammar and punctuation
- Formal academic tone even for simple topics
- Overly structured with headers/bullets for simple answers
- No personal opinions, emotions, or hesitations
- Uniform sentence length (all ~15-20 words)
- Generic examples, no specific personal details
- Starts with restating the question

HUMAN-WRITTEN signs:
- Informal language, slang, typos
- Emotional expressions, personal opinions
- Short or unfinished sentences
- Specific personal details or anecdotes
- Topic jumps, digressions
- First-person perspective with genuine voice
- Inconsistent style

Respond ONLY with valid JSON, no markdown, no explanation outside JSON:
{{"score": <0-100>, "reason": "<1-2 sentences in same language as text explaining WHY>", "signs": ["<sign1>", "<sign2>", "<sign3>"]}}

score meaning: 0-25=clearly human, 26-45=likely human, 46-55=uncertain, 56-75=likely AI, 76-100=clearly AI"""

        models_to_try = [
            'arcee-ai/trinity-large-preview:free',
            'meta-llama/llama-3.2-3b-instruct:free',
        ]

        for model in models_to_try:
            try:
                resp = requests.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    headers={
                        'Authorization': 'Bearer ' + self.or_api_key,
                        'Content-Type': 'application/json',
                    },
                    json={
                        'model': model,
                        'messages': [{'role': 'user', 'content': prompt}],
                        'max_tokens': 200,
                        'temperature': 0.05,
                    },
                    timeout=25,
                )

                if resp.status_code == 429:
                    import time; time.sleep(2)
                    continue

                if resp.status_code != 200:
                    print(f'OpenRouter [{model}]: {resp.status_code}')
                    continue

                choices = resp.json().get('choices') or []
                if not choices:
                    continue

                content = choices[0].get('message', {}).get('content', '') or ''
                print(f'LLM raw [{model}]: {repr(content[:120])}')

                # JSON табу — кейде model markdown оромайды
                json_match = re.search(r'\{.*?"score"\s*:\s*(\d+).*?\}', content, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(0))
                        score  = max(0, min(100, int(data.get('score', 50))))
                        reason = data.get('reason', '')
                        signs  = data.get('signs', [])
                        print(f'LLM Judge [{model}]: score={score}')
                        return score, reason, signs
                    except json.JSONDecodeError:
                        pass

                # Fallback — тек score-ды табу
                m = re.search(r'"score"\s*:\s*(\d+)', content)
                if m:
                    score = max(0, min(100, int(m.group(1))))
                    print(f'LLM Judge fallback [{model}]: score={score}')
                    return score, '', []

            except requests.Timeout:
                print(f'LLM Judge timeout [{model}]')
                continue
            except Exception as e:
                print(f'LLM Judge error [{model}]: {e}')
                continue

        return None

    def _roberta_score(self, text):
        try:
            headers    = {'Authorization': 'Bearer ' + self.hf_token, 'Content-Type': 'application/json'}
            clean_text = ''.join(c for c in text[:512] if ord(c) < 0x10000)
            clean_text = ' '.join(clean_text.split())
            resp = requests.post(self.HF_URL, headers=headers, json={'inputs': clean_text}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, list) and isinstance(data[0], list):
                    results   = {item['label']: item['score'] for item in data[0]}
                    fake_prob = results.get('Fake', 0.5)
                    print(f'RoBERTa: Fake={round(fake_prob, 2)}')
                    return int(fake_prob * 100)
            return None
        except Exception as e:
            print(f'RoBERTa қатесі: {e}')
            return None

    def _features(self, text):
        tl    = text.lower()
        sents = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 5]
        words = tl.split()

        ai_found = [m for m in (self.AI_MARKERS_KZ + self.AI_MARKERS_RU + self.AI_MARKERS_EN) if m in tl]
        human_found = [m for m in self.HUMAN_MARKERS if m in tl]

        lens = [len(s.split()) for s in sents] if sents else [0]
        avg  = sum(lens) / max(len(lens), 1)
        # Сөйлем ұзындығының дисперсиясы — адам жазса жоғары болады
        variance = sum((l - avg) ** 2 for l in lens) / max(len(lens), 1)
        ttr  = len(set(words)) / max(len(words), 1)

        # Знак пунктуации идеалды болса — ЖИ белгісі
        punct_ratio = sum(1 for c in text if c in '.,;:') / max(len(text), 1)

        return {
            'markers_found': ai_found,
            'markers': len(ai_found),
            'human_found': human_found,
            'human_markers': len(human_found),
            'avg': round(avg, 1),
            'variance': round(variance, 1),
            'ttr': round(ttr, 3),
            'words': len(words),
            'sents': len(sents),
            'punct_ratio': round(punct_ratio, 4),
        }

    def _stat_score(self, f):
        """API жоқта статистикалық есептеу"""
        s = 15  # база

        # ЖИ маркерлері
        s += min(f['markers'] * 10, 35)

        # Адам маркерлері — кемітеді
        s -= min(f['human_markers'] * 8, 25)

        # Ұзын біртекті сөйлемдер
        if f['avg'] > 18: s += 12
        elif f['avg'] > 14: s += 6

        # Сөйлем ұзындығы дисперсиясы — аз болса ЖИ
        if f['variance'] < 10 and f['sents'] > 3: s += 10
        elif f['variance'] > 50: s -= 8

        # TTR (vocabulary richness) — ЖИ кейде жоғары
        if f['ttr'] < 0.35: s += 8
        elif f['ttr'] > 0.75: s -= 5

        return max(5, min(90, s))

    def _explain(self, score, f, verdict, method, reason='', signs=None):
        lines = []

        # Негізгі нәтиже
        if verdict == 'ai':
            confidence = 'Жоғары' if score >= 75 else ('Орташа' if score >= 55 else 'Төмен')
            lines.append(f'**Нәтиже:** ЖИ жазған ықтималдылығы жоғары\n**Сенімділік деңгейі:** {confidence} ({score}%)')
        else:
            confidence = 'Жоғары' if score <= 25 else ('Орташа' if score <= 45 else 'Төмен')
            lines.append(f'**Нәтиже:** Адам жазған мәтін\n**Сенімділік деңгейі:** {confidence} (ЖИ ықтималдылығы: {score}%)')

        # LLM-нің нақты себебі
        if reason:
            lines.append(f'\n💬 **Талдау:** {reason}')

        # LLM анықтаған белгілер
        if signs:
            lines.append('\n**Анықталған белгілер:**')
            for s in signs[:4]:
                icon = '🔴' if verdict == 'ai' else '🟢'
                lines.append(f'{icon} {s}')

        # Статистика бөлімі
        lines.append('\n**Статистика:**')

        if f['markers']:
            lines.append(f'🔴 **ЖИ маркерлері:** {f["markers"]} дана')
            for m in f['markers_found'][:3]:
                lines.append(f'   — «{m}»')
        else:
            lines.append('🟢 **ЖИ маркерлері:** табылмады')

        if f['human_markers']:
            lines.append(f'🟢 **Адам белгілері:** {f["human_markers"]} дана (бейресми тіл)')

        avg_icon = '🔴' if f['avg'] > 18 else ('🟡' if f['avg'] > 13 else '🟢')
        lines.append(f'{avg_icon} **Орташа сөйлем ұзындығы:** {f["avg"]} сөз')

        var_icon = '🔴' if f['variance'] < 8 and f['sents'] > 3 else '🟢'
        lines.append(f'{var_icon} **Сөйлем алуандылығы:** {"төмен (бір қалып)" if f["variance"] < 8 else "қалыпты"}')

        ttr_icon = '🟡' if f['ttr'] < 0.4 else '🟢'
        lines.append(f'{ttr_icon} **Сөздік байлығы (TTR):** {int(f["ttr"]*100)}%')

        lines.append(f'\n📊 **{f["words"]} сөз · {f["sents"]} сөйлем** · Метод: {method}')
        lines.append('\n*⚠️ Анықтау 100% дәл емес. Нәтижені контекстпен бірге бағалаңыз.*')

        return '\n'.join(lines)


# ══════════════════════════════════════════
# СУРЕТ ДЕТЕКТОРЫ
# ══════════════════════════════════════════
class ImageDetector:

    def __init__(self):
        self.or_api_key = os.getenv('OPENROUTER_API_KEY', '')

    def analyze(self, image_path):
        # 1. NVIDIA Nemotron VL (негізгі)
        result = self._vision_analyze(image_path, 'nvidia/nemotron-nano-12b-v2-vl:free')
        if result is not None:
            return result
        # 2. Google Gemma Vision (резерв)
        result = self._vision_analyze(image_path, 'google/gemma-3-27b-it:free')
        if result is not None:
            return result
        # 3. Pillow статистика (соңғы резерв)
        try:
            from PIL import Image
            return self._pillow_analyze(image_path)
        except ImportError:
            return {
                'score': 50, 'verdict': 'unknown',
                'label': 'Pillow орнатылмаған',
                'text': '⚠️ Сурет талдауы үшін: `pip install Pillow`',
            }
        except Exception as e:
            return {'score': 0, 'verdict': 'error', 'label': 'Қате', 'text': str(e)}

    def _vision_analyze(self, path, model):
        if not self.or_api_key:
            return None
        try:
            # Суретті кішірейт
            try:
                from PIL import Image as PILImage
                import io
                with PILImage.open(path) as im:
                    im.thumbnail((768, 768), PILImage.LANCZOS)
                    buf = io.BytesIO()
                    fmt = 'JPEG' if im.mode == 'RGB' else 'PNG'
                    if im.mode not in ('RGB', 'RGBA', 'L'):
                        im = im.convert('RGB')
                        fmt = 'JPEG'
                    im.save(buf, format=fmt, quality=80)
                    img_data = base64.b64encode(buf.getvalue()).decode()
                    mime = 'image/jpeg' if fmt == 'JPEG' else 'image/png'
            except Exception:
                with open(path, 'rb') as f:
                    img_data = base64.b64encode(f.read()).decode()
                ext  = path.split('.')[-1].lower()
                mime = {'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png','webp':'image/webp'}.get(ext, 'image/jpeg')

            img_url = f'data:{mime};base64,{img_data}'

            prompt = """Analyze this image carefully and determine if it was AI-generated (by Midjourney, DALL-E, Stable Diffusion, etc.) or if it's a real photograph.

Look for these AI-generation artifacts:
- Unnatural skin texture (too smooth, plastic-looking)
- Wrong or impossible hands/fingers (extra fingers, merged, malformed)
- Blurry or nonsensical text/signs
- Physically impossible reflections or shadows
- Too-perfect lighting without natural imperfections
- Background inconsistencies or melting/dissolving elements
- Uncanny valley effect in faces
- Objects that don't make physical sense
- Watermarks or stylistic patterns typical of AI generators
- Overly saturated or stylized colors typical of AI art

For real photos look for:
- Natural imperfections, noise, grain
- Consistent lighting with real physics
- Normal human features
- Real-world context and natural textures

Respond ONLY with this exact JSON format, no other text:
{"score": <0-100>, "reason": "<1-2 sentences explaining the main evidence>", "artifacts": ["<artifact1>", "<artifact2>"]}

Where score: 0-30=real photo, 31-55=likely real, 56-75=likely AI, 76-100=clearly AI-generated"""

            resp = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': 'Bearer ' + self.or_api_key,
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model,
                    'messages': [
                        {
                            'role': 'system',
                            'content': 'You are an expert AI image detector. Always respond with valid JSON only.',
                        },
                        {
                            'role': 'user',
                            'content': [
                                {'type': 'image_url', 'image_url': {'url': img_url}},
                                {'type': 'text', 'text': prompt},
                            ],
                        },
                    ],
                    'max_tokens': 250,
                    'temperature': 0.05,
                    'reasoning': {'effort': 'none'},
                },
                timeout=40,
            )

            if resp.status_code == 429:
                print(f'Rate limit ({model}), резервке...')
                return None
            if resp.status_code != 200:
                print(f'Vision қате {resp.status_code} ({model})')
                return None

            choice  = resp.json()['choices'][0]
            content = choice.get('message', {}).get('content', '') or ''
            print(f'Vision raw [{model}]: {repr(content[:150])}')

            # JSON парсинг
            json_match = re.search(r'\{.*?"score"\s*:\s*(\d+).*?\}', content, re.DOTALL)
            if json_match:
                try:
                    data      = json.loads(json_match.group(0))
                    score     = max(2, min(97, int(data.get('score', 50))))
                    reason    = data.get('reason', '')
                    artifacts = data.get('artifacts', [])
                    verdict   = 'ai' if score > 50 else 'human'
                    label     = 'ЖИ жасаған сурет болуы мүмкін' if verdict == 'ai' else 'Нақты фотосурет'
                    model_name = model.split('/')[0].upper()

                    text = f'**Нәтиже:** {label} — **{score}%**\n\n'
                    if reason:
                        text += f'💬 **Талдау:** {reason}\n\n'
                    if artifacts:
                        text += '**Анықталған белгілер:**\n'
                        icon = '🔴' if verdict == 'ai' else '🟢'
                        for a in artifacts[:3]:
                            text += f'{icon} {a}\n'
                        text += '\n'
                    text += f'**Талдау моделі:** {model_name} Vision\n'
                    text += '\n*⚠️ Сурет анализі 100% дәл емес.*'

                    return {'score': score, 'verdict': verdict, 'label': label, 'text': text}
                except json.JSONDecodeError:
                    pass

            # Fallback — тек score
            m = re.search(r'"score"\s*:\s*(\d+)', content)
            if m:
                score   = max(2, min(97, int(m.group(1))))
                verdict = 'ai' if score > 50 else 'human'
                label   = 'ЖИ жасаған сурет болуы мүмкін' if verdict == 'ai' else 'Нақты фотосурет'
                text    = f'**Нәтиже:** {label} — **{score}%**\n\n*⚠️ Сурет анализі 100% дәл емес.*'
                return {'score': score, 'verdict': verdict, 'label': label, 'text': text}

            return None

        except Exception as e:
            print(f'Vision қатесі [{model}]: {e}')
            return None

    def _pillow_analyze(self, path):
        """Pillow негізіндегі статистикалық талдау"""
        from PIL import Image
        img  = Image.open(path)
        w, h = img.size
        meta    = self._check_meta(img)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        pixels  = list(img.getdata())
        color   = self._color_stats(pixels)
        entropy = self._entropy(pixels)
        edge    = self._edge_stats(img)
        sym     = self._symmetry(img)
        fft     = self._fft_analysis(img)
        score   = int(meta*0.25 + color*0.20 + entropy*0.18 + edge*0.15 + sym*0.10 + fft*0.12)
        score   = max(5, min(90, score))
        verdict = 'ai' if score > 52 else 'human'
        label   = 'ЖИ жасаған сурет болуы мүмкін' if verdict == 'ai' else 'Нақты фотосурет'

        ind = []
        if meta > 60:    ind.append('EXIF метадеректер жоқ немесе AI тегі бар')
        if color > 60:   ind.append('Түс таралуы өте біркелкі (GAN белгісі)')
        if entropy > 60: ind.append('Энтропия аномалиясы')
        if edge > 60:    ind.append('Шеттер тым тегіс (Diffusion белгісі)')
        if sym > 60:     ind.append('Жоғары симметрия (GAN белгісі)')
        if fft > 60:     ind.append('Жиілік доменінде артефактілер (FFT)')

        text  = f'**Нәтиже:** {label} — **{score}%**\n\n'
        text += '**Статистикалық белгілер:**\n'
        if ind:
            for i in ind:
                text += f'🔴 {i}\n'
        else:
            text += '🟢 Күдікті белгілер табылмады\n'
        text += f'\n**Өлшем:** {w}×{h} пиксель\n'
        text += '**Метод:** EXIF · Түс · Энтропия · Шет · Симметрия · FFT\n'
        text += '\n*⚠️ Сурет анализі 100% дәл емес. Vision AI моделі жоқ болса нақтырақ нәтиже беру мүмкін емес.*'
        return {'score': score, 'verdict': verdict, 'label': label, 'text': text}

    def _check_meta(self, img):
        try:
            exif = img._getexif() if hasattr(img, '_getexif') else None
            if exif is None: return 62
            s = str(exif).lower()
            if any(k in s for k in ['stable diffusion','midjourney','dall-e','firefly','comfyui','invokeai']):
                return 98
            fields = sum(1 for f in [271, 272, 306, 36867] if f in exif)
            return max(10, 55 - fields * 12)
        except:
            return 55

    def _color_stats(self, pixels):
        sample = pixels[::max(1, len(pixels)//2000)]
        ch = list(zip(*sample))
        if len(ch) < 3: return 50
        stds = []
        for c in ch[:3]:
            mean = sum(c) / len(c)
            stds.append(math.sqrt(sum((v-mean)**2 for v in c) / len(c)))
        avg = sum(stds) / 3
        if avg < 20: return 88
        if avg < 35: return 68
        if avg < 55: return 48
        if avg < 75: return 28
        return 15

    def _entropy(self, pixels):
        sample = pixels[::max(1, len(pixels)//1000)]
        br     = [(p[0]+p[1]+p[2])//3 for p in sample]
        freq   = Counter(br); total = len(br)
        e      = -sum((c/total)*math.log2(c/total) for c in freq.values() if c > 0)
        n      = e / 8.0
        if n > 0.97: return 75
        if n > 0.92: return 55
        if n > 0.82: return 38
        return 20

    def _edge_stats(self, img):
        try:
            small  = img.resize((128, 128))
            pixels = list(small.getdata()); W = 128
            diffs  = [sum(abs(a-b) for a,b in zip(pixels[y*W+x][:3], pixels[y*W+x+1][:3]))
                      for y in range(W-1) for x in range(W-1)]
            avg = sum(diffs) / len(diffs)
            if avg < 6:  return 75
            if avg < 12: return 58
            if avg < 25: return 38
            if avg > 85: return 62
            return 18
        except:
            return 40

    def _symmetry(self, img):
        try:
            small  = img.resize((64, 64))
            pixels = list(small.getdata())
            sym    = sum(1 for y in range(64) for x in range(32)
                         if sum(abs(a-b) for a,b in zip(pixels[y*64+x][:3],
                                                         pixels[y*64+(63-x)][:3])) < 22)
            r = sym / (64 * 32)
            return 78 if r > 0.74 else (52 if r > 0.57 else 18)
        except:
            return 35

    def _fft_analysis(self, img):
        try:
            gray     = img.convert('L').resize((64, 64))
            pixels   = list(gray.getdata()); N = 64
            rows     = [[pixels[y*N+x] for x in range(N)] for y in range(N)]
            row_vars = []
            for row in rows:
                mean = sum(row) / N
                var  = sum((v-mean)**2 for v in row) / N
                row_vars.append(var)
            avg_var  = sum(row_vars) / len(row_vars)
            meta_var = sum((v-avg_var)**2 for v in row_vars) / len(row_vars)
            cv = math.sqrt(meta_var) / (avg_var + 1e-6)
            if cv < 0.25: return 72
            if cv < 0.45: return 52
            if cv < 0.70: return 35
            return 18
        except:
            return 35


# ══════════════════════════════════════════
# БЕЙНЕ ДЕТЕКТОРЫ
# ══════════════════════════════════════════
class VideoDetector:

    def analyze(self, video_path):
        try:
            import cv2, numpy as np
            return self._analyze(video_path, cv2, np)
        except ImportError:
            return {
                'score': 50, 'verdict': 'unknown',
                'label': 'OpenCV орнатылмаған',
                'text': '⚠️ Бейне талдауы үшін: `pip install opencv-python-headless`',
            }
        except Exception as e:
            return {'score': 0, 'verdict': 'error', 'label': 'Қате', 'text': str(e)}

    def _analyze(self, path, cv2, np):
        cap   = cv2.VideoCapture(path)
        if not cap.isOpened():
            return {'score': 0, 'verdict': 'error', 'label': 'Файл ашылмады', 'text': ''}
        fps   = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        W     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        H     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        dur   = total / fps if fps > 0 else 0
        step  = max(1, total // 80)
        frames = []; idx = 0
        while True:
            ret, frame = cap.read()
            if not ret: break
            if idx % step == 0: frames.append(frame)
            idx += 1
        cap.release()
        if len(frames) < 4:
            return {'score': 50, 'verdict': 'unknown', 'label': 'Бейне тым қысқа', 'text': ''}

        t  = self._temporal(frames, cv2, np)
        n  = self._noise(frames, cv2, np)
        fr = self._frequency(frames, cv2, np)
        a  = self._artifacts(frames, cv2, np)
        fc = self._face(frames, cv2, np)

        score   = int(t*0.30 + n*0.25 + fr*0.20 + a*0.15 + fc*0.10)
        score   = max(5, min(92, score))
        verdict = 'ai' if score > 52 else 'human'
        label   = 'Дипфейк болуы мүмкін' if verdict == 'ai' else 'Нақты бейне'

        ind = []
        if t  > 60: ind.append('Кадрлар арасында уақыттық сәйкессіздік')
        if n  > 60: ind.append('GAN-тәрізді шу аномалиясы')
        if fr > 60: ind.append('Жиілік доменінде артефактілер (FFT)')
        if a  > 60: ind.append('Блоктық артефактілер анықталды')
        if fc > 60: ind.append('Бет аймағында аномалия')

        text  = f'**Нәтиже:** {label} — **{score}%**\n\n'
        if ind:
            text += '**Анықталған белгілер:**\n'
            for i in ind:
                text += f'🔴 {i}\n'
            text += '\n'
        else:
            text += '🟢 Күдікті белгілер табылмады\n\n'
        text += f'📊 **{round(dur,1)}с · {round(fps)} FPS · {W}×{H} · {len(frames)} кадр**\n'
        text += '\n*⚠️ Бейне анализі 100% дәл емес.*'
        return {'score': score, 'verdict': verdict, 'label': label, 'text': text}

    def _temporal(self, f, cv2, np):
        d = [float(np.mean(cv2.absdiff(f[i-1], f[i]))) for i in range(1, len(f))]
        if not d: return 50
        m = sum(d) / len(d)
        if m == 0: return 82
        s  = math.sqrt(sum((x-m)**2 for x in d) / len(d))
        cv = s / (m + 1e-6)
        if cv > 0.9: return 80
        if cv > 0.6: return 58
        if cv < 0.04: return 75
        return 25

    def _noise(self, f, cv2, np):
        sc = [float(np.var(cv2.Laplacian(cv2.cvtColor(x, cv2.COLOR_BGR2GRAY), cv2.CV_64F)))
              for x in f[::5]]
        if not sc: return 50
        avg = sum(sc) / len(sc)
        if avg < 25:  return 82
        if avg < 70:  return 62
        if avg < 180: return 42
        return 18

    def _frequency(self, f, cv2, np):
        sc = []
        for x in f[::8]:
            g  = cv2.cvtColor(x, cv2.COLOR_BGR2GRAY).astype(float)
            m  = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(g))))
            sc.append(float(np.std(m) / (np.mean(m) + 1e-6)))
        if not sc: return 50
        avg = sum(sc) / len(sc)
        if avg < 0.28: return 78
        if avg < 0.48: return 58
        if avg < 0.75: return 35
        return 18

    def _artifacts(self, f, cv2, np):
        sc = []
        for x in f[::10]:
            g  = cv2.cvtColor(x, cv2.COLOR_BGR2GRAY).astype(float)
            h, w = g.shape; bd = cnt = 0
            for y in range(0, h-8, 8):
                for xi in range(0, w-8, 8):
                    bd  += abs(g[y+7, xi] - g[y, xi]) + abs(g[y, xi+7] - g[y, xi])
                    cnt += 2
            if cnt: sc.append(bd / cnt)
        if not sc: return 50
        avg = sum(sc) / len(sc)
        if avg > 22: return 72
        if avg > 13: return 52
        return 20

    def _face(self, f, cv2, np):
        try:
            cas    = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            counts = [len(cas.detectMultiScale(cv2.cvtColor(x, cv2.COLOR_BGR2GRAY), 1.1, 4))
                      for x in f[::10]]
            if not counts or max(counts) == 0: return 35
            ch = sum(1 for i in range(1, len(counts)) if counts[i] != counts[i-1])
            r  = ch / max(len(counts) - 1, 1)
            if r > 0.5:  return 70
            if r > 0.25: return 50
            return 25
        except:
            return 35


# ══════════════════════════════════════════
# БАСТЫ ДЕТЕКТОР
# ══════════════════════════════════════════
class AIDetector:
    def __init__(self):
        self.text_detector  = TextDetector()
        self.image_detector = ImageDetector()
        self.video_detector = VideoDetector()

    def analyze(self, text):
        return self.text_detector.analyze(text)

    def analyze_image(self, image_path):
        return self.image_detector.analyze(image_path)

    def analyze_video(self, video_path):
        return self.video_detector.analyze(video_path)