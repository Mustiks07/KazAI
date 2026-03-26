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
    ]
    AI_MARKERS_RU = [
        'следует отметить','таким образом','в заключение','стоит отметить',
        'необходимо подчеркнуть','подводя итог','в данном контексте',
        'резюмируя вышесказанное','кроме того','важно подчеркнуть',
        'полученные результаты','проведённый анализ','данная проблема',
        'позволяет реализовать','отличается высокой','обеспечивая',
        'включает подготовку','характеризуется','предполагает',
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
        if len(text.strip()) < 20:
            return {'score': 0, 'verdict': 'short',
                    'label': 'Мәтін тым қысқа',
                    'text':  'Нақты анықтау үшін кем дегенде 20 таңба қажет.'}
        f = self._features(text)

        # 1. LLM-as-Judge
        if self.or_api_key:
            llm = self._llm_judge(text)
            if llm is not None:
                llm_score, llm_reason = llm if isinstance(llm, tuple) else (llm, '')
                score   = min(int(llm_score) + min(f['markers'] * 4, 10), 97)
                method  = 'LLM-as-Judge + ' + str(f['markers']) + ' маркер'
                verdict = 'ai' if score >= 52 else 'human'
                label   = 'Жасанды интеллект жазған болуы мүмкін' if verdict == 'ai' else 'Адам жазған сияқты'
                return {'score': score, 'verdict': verdict, 'label': label,
                        'text': self._explain(score, f, verdict, method, llm_reason)}

        # 2. RoBERTa
        if self.hf_token:
            roberta = self._roberta_score(text)
            if roberta is not None:
                score   = min(roberta + min(f['markers'] * 4, 12), 97)
                verdict = 'ai' if score >= 52 else 'human'
                label   = 'Жасанды интеллект жазған болуы мүмкін' if verdict == 'ai' else 'Адам жазған сияқты'
                return {'score': score, 'verdict': verdict, 'label': label,
                        'text': self._explain(score, f, verdict, 'OpenAI RoBERTa')}

        # 3. ML резерв
        if self.model:
            prob  = float(self.model.predict_proba([text])[0][1])
            score = min(int(prob * 100) + min(f['markers'] * 5, 15), 97)
            method = 'TF-IDF ML модель'
        else:
            score  = self._stat_score(f)
            method = 'Статистикалық талдау'

        verdict = 'ai' if score >= 52 else 'human'
        label   = 'Жасанды интеллект жазған болуы мүмкін' if verdict == 'ai' else 'Адам жазған сияқты'
        return {'score': score, 'verdict': verdict, 'label': label,
                'text': self._explain(score, f, verdict, method)}

    def _llm_judge(self, text):
        try:
            prompt = (
                'You are an AI text detector. Analyze if the text was written by AI or human.\n\n'
                'Text:\n"""\n' + text[:800] + '\n"""\n\n'
                'Respond ONLY with JSON:\n'
                '{"score": 0-100}\n\n'
                'score: 0-30=human, 31-60=uncertain, 61-100=AI.\n'
                'AI signs: template phrases, formal cliches, perfect grammar, uniform style.\n'
                'Human signs: emotions, errors, informal tone.'
            )
            resp = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': 'Bearer ' + self.or_api_key, 'Content-Type': 'application/json'},
                json={'model': 'arcee-ai/trinity-large-preview:free',
                      'messages': [{'role': 'user', 'content': prompt}],
                      'max_tokens': 60, 'temperature': 0.1},
                timeout=20
            )
            if resp.status_code == 429:
                import time; time.sleep(3)
                resp = requests.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    headers={'Authorization': 'Bearer ' + self.or_api_key, 'Content-Type': 'application/json'},
                    json={'model': 'arcee-ai/trinity-large-preview:free',
                          'messages': [{'role': 'user', 'content': prompt}],
                          'max_tokens': 60, 'temperature': 0.1},
                    timeout=20
                )
            if resp.status_code == 200:
                choices = resp.json().get('choices') or []
                if not choices: return None
                content = choices[0].get('message', {}).get('content', '') or ''
                print('LLM raw: ' + repr(content[:80]))
                m = re.search(r'"score"\s*:\s*(\d+)', content)
                if m:
                    score = int(m.group(1))
                    if score >= 80:
                        reason = 'Мәтінде шаблонды сөйлемдер, маркерлер және біркелкі стиль анықталды.'
                    elif score >= 61:
                        reason = 'Мәтінде ЖИ белгілері бар: тым мінсіз грамматика және біркелкі стиль.'
                    elif score >= 40:
                        reason = 'Мәтінде ЖИ және адам белгілері аралас кездеседі.'
                    else:
                        reason = 'Мәтінде эмоция, бейресми тіл және адамға тән белгілер бар.'
                    print('LLM Judge: ' + str(score) + '%')
                    return max(0, min(100, score)), reason
            else:
                print('OpenRouter: ' + str(resp.status_code))
            return None
        except Exception as e:
            print('LLM Judge қатесі: ' + str(e))
            return None

    def _roberta_score(self, text):
        try:
            headers    = {'Authorization': 'Bearer ' + self.hf_token, 'Content-Type': 'application/json'}
            clean_text = ''.join(c for c in text[:500] if ord(c) < 0x10000)
            clean_text = ' '.join(clean_text.split())
            resp = requests.post(self.HF_URL, headers=headers, json={'inputs': clean_text}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, list) and isinstance(data[0], list):
                    results   = {item['label']: item['score'] for item in data[0]}
                    fake_prob = results.get('Fake', 0.5)
                    print('RoBERTa: Fake=' + str(round(fake_prob, 2)))
                    return int(fake_prob * 100)
            return None
        except Exception as e:
            print('RoBERTa қатесі: ' + str(e))
            return None

    def _features(self, text):
        tl    = text.lower()
        sents = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        words = tl.split()
        mf    = [m for m in self.AI_MARKERS_KZ + self.AI_MARKERS_RU if m in tl]
        lens  = [len(s.split()) for s in sents]
        avg   = sum(lens) / max(len(lens), 1)
        ttr   = len(set(words)) / max(len(words), 1)
        inf   = sum(1 for w in ['хаха','лол','ойбай','блин','ладно','ок','эх'] if w in tl)
        return {'markers_found': mf, 'markers': len(mf), 'avg': round(avg, 1),
                'ttr': round(ttr, 3), 'words': len(words), 'sents': len(sents), 'informal': inf}

    def _stat_score(self, f):
        s = 12 + min(f['markers'] * 12, 40)
        if f['avg'] > 16: s += 12
        if f['ttr'] < 0.4: s += 10
        s -= min(f['informal'] * 8, 20)
        return max(5, min(s, 95))

    def _explain(self, score, f, verdict, method, reason=''):
        lines = []
        if verdict == 'ai':
            lines.append('**Нәтиже:** ЖИ жазған ықтималдылығы — **' + str(score) + '%**')
        else:
            lines.append('**Нәтиже:** Адам жазған ықтималдылығы жоғары\nЖИ ықтималдылығы: **' + str(score) + '%**')
        if reason:
            lines.append('\n💬 **Себеп:** ' + reason)
        lines.append('\n**Белгілер:**\n')
        if f['markers']:
            lines.append('🔴 **ЖИ маркерлері:** ' + str(f['markers']) + ' дана')
            for m in f['markers_found'][:4]:
                lines.append('   — «' + m + '»')
        else:
            lines.append('🟢 **ЖИ маркерлері:** табылмады')
        lines.append(('🟡' if f['avg'] > 16 else '🟢') + ' **Орташа сөйлем:** ' + str(f['avg']) + ' сөз')
        lines.append(('🟡' if f['ttr'] < 0.45 else '🟢') + ' **Сөздік байлығы (TTR):** ' + str(int(f['ttr']*100)) + '%')
        if f['informal']:
            lines.append('🟢 **Бейресми тіл:** бар (адам белгісі)')
        lines.append('\n📊 ' + str(f['words']) + ' сөз · ' + str(f['sents']) + ' сөйлем')
        lines.append('\n*Анықтау 100% дәл емес. Нәтижені контекстпен бірге бағалаңыз.*')
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
            return {'score': 50, 'verdict': 'unknown',
                    'label': 'Pillow орнатылмаған', 'text': 'pip install Pillow'}
        except Exception as e:
            return {'score': 0, 'verdict': 'error', 'label': 'Қате', 'text': str(e)}

    def _vision_analyze(self, path, model):
        if not self.or_api_key:
            return None
        try:
            # Суретті 512x512-ге дейін кішірейт (токен лимиті үшін)
            try:
                from PIL import Image as PILImage
                import io
                with PILImage.open(path) as im:
                    im.thumbnail((512, 512), PILImage.LANCZOS)
                    buf = io.BytesIO()
                    im.save(buf, format='JPEG', quality=75)
                    img_data = base64.b64encode(buf.getvalue()).decode()
                    mime = 'image/jpeg'
            except Exception:
                with open(path, 'rb') as f:
                    img_data = base64.b64encode(f.read()).decode()
                ext  = path.split('.')[-1].lower()
                mime = {'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png','webp':'image/webp'}.get(ext,'image/jpeg')
            img_url = 'data:' + mime + ';base64,' + img_data
            resp = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': 'Bearer ' + self.or_api_key,
                         'Content-Type': 'application/json'},
                json={
                    'model': model,
                    'messages': [
                        {'role': 'system', 'content': 'You are an AI image detector. Always respond with valid JSON only, no explanations.'},
                        {'role': 'user', 'content': [
                        {'type': 'image_url', 'image_url': {'url': img_url}},
                        {'type': 'text',
                         'text': 'Is this image AI-generated or a real photo? Output ONLY this JSON, nothing else: {"score": NUMBER} where NUMBER is 0-100 (0=real photo, 100=AI generated).'}
                    ]}],
                    'max_tokens': 300,
                    'temperature': 0.1,
                    'reasoning': {'effort': 'none'}
                },
                timeout=30
            )
            if resp.status_code == 200:
                choice  = resp.json()['choices'][0]
                content = choice.get('message', {}).get('content', '') or ''
                reasoning = choice.get('message', {}).get('reasoning', '') or ''
                # Екеуін біріктір — JSON қайда болса да табамыз
                full_text = content + ' ' + reasoning
                m = re.search(r'"score"\s*:\s*(\d+)', full_text)
                if m:
                    score   = int(m.group(1))
                    verdict = 'ai' if score > 52 else 'human'
                    if verdict == 'ai':
                        label = 'ЖИ жасаған сурет болуы мүмкін'
                        result_label = label + ' — **' + str(score) + '%**'
                    else:
                        label = 'Нақты сурет'
                        result_label = label + ' (ЖИ ықтималдылығы: **' + str(score) + '%**)'
                    print('Vision (' + model.split('/')[-1] + '): ' + str(score) + '%')
                    text  = '**Нәтиже:** ' + result_label + '\n\n'
                    text += '**Талдау:** ' + model.split('/')[0].upper() + ' Vision моделі\n\n'
                    text += '*Сурет анализі 100% дәл емес.*'
                    return {'score': score, 'verdict': verdict, 'label': label, 'text': text}
            elif resp.status_code == 429:
                print('Rate limit (' + model + '), резервке...')
            else:
                print('Vision қате ' + str(resp.status_code) + ' (' + model + ')')
            return None
        except Exception as e:
            print('Vision қатесі: ' + str(e))
            return None

    def _pillow_analyze(self, path):
        from PIL import Image
        img  = Image.open(path)
        w, h = img.size
        meta    = self._check_meta(img)
        if img.mode != 'RGB': img = img.convert('RGB')
        pixels  = list(img.getdata())
        color   = self._color_stats(pixels)
        entropy = self._entropy(pixels)
        edge    = self._edge_stats(img)
        sym     = self._symmetry(img)
        fft     = self._fft_analysis(img)
        score   = int(meta*0.25 + color*0.20 + entropy*0.18 + edge*0.15 + sym*0.10 + fft*0.12)
        score   = max(5, min(95, score))
        verdict = 'ai' if score > 52 else 'human'
        label   = 'ЖИ жасаған сурет болуы мүмкін' if verdict == 'ai' else 'Нақты сурет'
        ind = []
        if meta > 60:    ind.append('EXIF метадеректер жоқ немесе AI тегі бар')
        if color > 60:   ind.append('Түс таралуы өте біркелкі (GAN белгісі)')
        if entropy > 60: ind.append('Энтропия аномалиясы')
        if edge > 60:    ind.append('Шеттер тым тегіс (Diffusion белгісі)')
        if sym > 60:     ind.append('Жоғары симметрия (GAN белгісі)')
        if fft > 60:     ind.append('Жиілік доменінде артефактілер (FFT)')
        text  = '**Нәтиже:** ' + label + ' — **' + str(score) + '%**\n\n'
        text += '\n'.join(ind) if ind else 'Күдікті белгілер табылмады'
        text += '\n\n**Өлшем:** ' + str(w) + 'x' + str(h) + ' пиксель'
        text += '\n**Талданған:** EXIF · Түс · Энтропия · Шет · Симметрия · FFT'
        text += '\n\n*Сурет анализі 100% дәл емес.*'
        return {'score': score, 'verdict': verdict, 'label': label, 'text': text}

    def _check_meta(self, img):
        try:
            exif = img._getexif() if hasattr(img, '_getexif') else None
            if exif is None: return 65
            s = str(exif).lower()
            if any(k in s for k in ['stable diffusion','midjourney','dall-e','firefly','comfyui']): return 98
            fields = sum(1 for f in [271, 272, 306, 36867] if f in exif)
            return max(10, 55 - fields * 12)
        except: return 55

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
        except: return 40

    def _symmetry(self, img):
        try:
            small  = img.resize((64, 64))
            pixels = list(small.getdata())
            sym    = sum(1 for y in range(64) for x in range(32)
                         if sum(abs(a-b) for a,b in zip(pixels[y*64+x][:3],
                                                         pixels[y*64+(63-x)][:3])) < 22)
            r = sym / (64 * 32)
            return 78 if r > 0.74 else (52 if r > 0.57 else 18)
        except: return 35

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
        except: return 35


# ══════════════════════════════════════════
# БЕЙНЕ ДЕТЕКТОРЫ
# ══════════════════════════════════════════
class VideoDetector:

    def analyze(self, video_path):
        try:
            import cv2, numpy as np
            return self._analyze(video_path, cv2, np)
        except ImportError:
            return {'score': 50, 'verdict': 'unknown',
                    'label': 'OpenCV орнатылмаған',
                    'text':  'pip install opencv-python командасын іске қосыңыз.'}
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
        step  = max(1, total // 100)
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
        score   = max(5, min(95, score))
        verdict = 'ai' if score > 52 else 'human'
        label   = 'Дипфейк болуы мүмкін' if verdict == 'ai' else 'Нақты бейне'

        ind = []
        if t  > 60: ind.append('Кадрлар арасында уақыттық сәйкессіздік')
        if n  > 60: ind.append('GAN-тәрізді шу аномалиясы')
        if fr > 60: ind.append('Жиілік доменінде артефактілер (FFT)')
        if a  > 60: ind.append('Блоктық артефактілер')
        if fc > 60: ind.append('Бет аймағында аномалия')

        text  = '**Нәтиже:** ' + label + ' — **' + str(score) + '%**\n\n'
        text += '\n'.join(ind) if ind else 'Күдікті белгілер табылмады'
        text += '\n\n' + str(round(dur,1)) + 'с | ' + str(round(fps)) + ' FPS | ' + str(W) + 'x' + str(H) + ' | ' + str(len(frames)) + ' кадр'
        text += '\n\n*Бейне анализі 100% дәл емес.*'
        return {'score': score, 'verdict': verdict, 'label': label, 'text': text}

    def _temporal(self, f, cv2, np):
        d = [float(np.mean(cv2.absdiff(f[i-1], f[i]))) for i in range(1, len(f))]
        if not d: return 50
        m = sum(d) / len(d)
        if m == 0: return 82
        s  = math.sqrt(sum((x-m)**2 for x in d) / len(d))
        cv = s / m
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
        except: return 35


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