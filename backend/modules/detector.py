import re
import math
import os
from collections import Counter


# ══════════════════════════════════════════════════════
# ТЕКСТ ДЕТЕКТОРЫ
# ══════════════════════════════════════════════════════

class TextDetector:
    """Мәтінді талдау — ЖИ белгілерін іздейді"""

    AI_MARKERS_KZ = [
        'сонымен қатар', 'атап айтқанда', 'маңызды рөл атқарады',
        'қорытындылай келе', 'жоғарыда айтылғандай', 'осылайша',
        'бұл мәселе', 'тиімді болып табылады', 'аталған мәселе',
        'осы орайда', 'негізінде'
    ]

    AI_MARKERS_RU = [
        'moreover', 'furthermore', 'in conclusion', 'it is worth noting',
        'следует отметить', 'таким образом', 'в заключение', 'стоит отметить',
        'необходимо подчеркнуть', 'подводя итог', 'немаловажно',
        'в данном контексте', 'резюмируя вышесказанное'
    ]

    def analyze(self, text: str) -> dict:
        if len(text.strip()) < 20:
            return {
                'score': 0,
                'verdict': 'short',
                'label': '⚠️ Мәтін тым қысқа',
                'details': [],
                'text': 'Анықтау үшін кем дегенде 20 таңба қажет.',
                'type': 'text'
            }

        features = self._extract_features(text)
        score = self._calculate_score(features)
        verdict = 'ai' if score > 55 else 'human'
        label = '🤖 Жасанды интеллект жасаған' if verdict == 'ai' else '✅ Адам жазған'

        return {
            'score': score,
            'verdict': verdict,
            'label': label,
            'features': features,
            'text': self._explain(score, features, verdict),
            'type': 'text'
        }

    def _extract_features(self, text):
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        words = text.lower().split()

        all_markers = self.AI_MARKERS_KZ + self.AI_MARKERS_RU
        markers_found = [m for m in all_markers if m in text.lower()]

        sent_lengths = [len(s.split()) for s in sentences]
        avg_len = sum(sent_lengths) / max(len(sent_lengths), 1)
        variance = self._variance(sent_lengths)

        ttr = len(set(words)) / max(len(words), 1)

        starters = [s.split()[0].lower() for s in sentences if s.split()]
        repetitive = sum(1 for c in Counter(starters).values() if c > 2)

        formal_patterns = [
            r'\b(является|представляет собой|осуществляет|реализует)\b',
            r'\b(болып табылады|атқарады|жүзеге асырады)\b',
        ]
        formal_count = sum(len(re.findall(p, text.lower())) for p in formal_patterns)

        ends = [s[-1] if s else '' for s in sentences]
        punct_score = 1 if (ends.count('.') / max(len(ends), 1)) > 0.9 else 0

        # Burstiness — разнообразие длин предложений
        cv = math.sqrt(variance) / avg_len if avg_len > 0 else 0

        return {
            'markers_found': markers_found,
            'marker_count': len(markers_found),
            'avg_sentence_length': round(avg_len, 1),
            'length_variance': round(variance, 2),
            'burstiness': round(cv, 3),
            'vocabulary_richness': round(ttr, 3),
            'sentence_count': len(sentences),
            'word_count': len(words),
            'repetitive_starters': repetitive,
            'formal_count': formal_count,
            'punctuation_score': punct_score,
        }

    def _calculate_score(self, f):
        score = 15
        score += min(f['marker_count'] * 12, 35)

        if f['burstiness'] < 0.2:
            score += 20  # очень однородные предложения → AI
        elif f['burstiness'] < 0.4:
            score += 10

        if f['vocabulary_richness'] < 0.4:
            score += 10
        elif f['vocabulary_richness'] > 0.7:
            score -= 5

        score += min(f['formal_count'] * 5, 15)
        score += min(f['repetitive_starters'] * 5, 10)

        if f['word_count'] > 200:
            score += 5

        score += f['punctuation_score'] * 5

        return max(0, min(score, 97))

    def _explain(self, score, f, verdict):
        lines = []
        if verdict == 'ai':
            lines.append(f"**Нәтиже:** ЖИ жазған ықтималдылығы — {score}%\n")
        else:
            lines.append(f"**Нәтиже:** Адам жазған ықтималдылығы жоғары (ЖИ белгілері: {score}%)\n")

        lines.append("**Талданған белгілер:**")

        if f['marker_count'] > 0:
            lines.append(f"🔴 ЖИ маркерлері: {f['marker_count']} дана")
            for m in f['markers_found'][:3]:
                lines.append(f"   • «{m}»")

        bust = f['burstiness']
        if bust < 0.2:
            lines.append(f"🔴 Сөйлем ұзындығы өте бірқалыпты (burstiness: {bust}) — ЖИ белгісі")
        elif bust < 0.4:
            lines.append(f"🟡 Сөйлем ұзындығы біршама бірқалыпты (burstiness: {bust})")
        else:
            lines.append(f"🟢 Сөйлем ұзындығы табиғи (burstiness: {bust})")

        lines.append(f"📊 Сөздік байлығы (TTR): {f['vocabulary_richness']:.0%}")
        lines.append(f"📝 Жалпы: {f['word_count']} сөз, {f['sentence_count']} сөйлем")
        lines.append("\n💡 **Ескерту:** Бұл анықтау 100% дәл емес.")
        return '\n'.join(lines)

    def _variance(self, values):
        if not values:
            return 0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)


# ══════════════════════════════════════════════════════
# СУРЕТ ДЕТЕКТОРЫ
# ══════════════════════════════════════════════════════

class ImageDetector:
    """Суретті талдау — ЖИ жасаған ба, жоқ па"""

    def analyze(self, image_path: str) -> dict:
        try:
            from PIL import Image
            return self._analyze_pil(image_path)
        except ImportError:
            return {
                'score': 50,
                'verdict': 'unknown',
                'label': '⚠️ Pillow орнатылмаған',
                'text': 'pip install Pillow командасын іске қосыңыз',
                'type': 'image'
            }
        except Exception as e:
            return {
                'score': 0,
                'verdict': 'error',
                'label': '❌ Қате',
                'text': str(e),
                'type': 'image'
            }

    def _analyze_pil(self, path):
        from PIL import Image

        img = Image.open(path)
        w, h = img.size

        # 1. Метадеректер тексеру
        meta_score = self._check_meta(img)

        # 2. Түс статистикасы
        if img.mode != 'RGB':
            img = img.convert('RGB')
        pixels = list(img.getdata())
        color_score = self._color_stats(pixels)

        # 3. Энтропия
        entropy_score = self._entropy(pixels)

        # 4. Симметрия (GAN суреттер көбінесе симметриялы)
        sym_score = self._symmetry(img)

        score = int(
            meta_score   * 0.25 +
            color_score  * 0.30 +
            entropy_score * 0.25 +
            sym_score    * 0.20
        )
        score = max(5, min(95, score))

        verdict = 'ai' if score > 55 else 'human'
        label = '🤖 ЖИ жасаған сурет' if verdict == 'ai' else '✅ Нақты сурет'

        indicators = []
        if meta_score > 60:
            indicators.append('🔴 EXIF метадеректер жоқ немесе күдікті')
        if color_score > 60:
            indicators.append('🟡 Түс таралуы біркелкі (ЖИ белгісі)')
        if entropy_score > 60:
            indicators.append('🟡 Энтропия аномалиясы анықталды')
        if sym_score > 60:
            indicators.append('🟡 Жоғары симметрия (GAN белгісі)')

        explanation = f"**Нәтиже:** {label} — {score}%\n\n"
        explanation += '\n'.join(indicators) if indicators else '🟢 Күдікті белгілер табылмады'
        explanation += f"\n\n📐 Өлшем: {w}×{h} пиксель"
        explanation += "\n\n💡 **Ескерту:** Сурет анализі 100% дәл емес."

        return {
            'score': score,
            'verdict': verdict,
            'label': label,
            'text': explanation,
            'type': 'image',
            'details': {
                'resolution': f'{w}x{h}',
                'metadata_anomaly': round(meta_score),
                'color_distribution': round(color_score),
                'entropy': round(entropy_score),
                'symmetry': round(sym_score),
            }
        }

    def _check_meta(self, img):
        try:
            exif = img._getexif() if hasattr(img, '_getexif') else None
            if exif is None:
                return 70
            exif_str = str(exif).lower()
            if any(kw in exif_str for kw in ['stable diffusion', 'midjourney', 'dall-e', 'firefly', 'adobe firefly']):
                return 98
            return 25
        except:
            return 60

    def _color_stats(self, pixels):
        sample = pixels[::max(1, len(pixels)//1000)]
        channels = list(zip(*sample))
        if len(channels) < 3:
            return 50
        stds = []
        for ch in channels[:3]:
            mean = sum(ch) / len(ch)
            std = math.sqrt(sum((v - mean)**2 for v in ch) / len(ch))
            stds.append(std)
        avg_std = sum(stds) / 3
        if avg_std < 30:
            return 80
        elif avg_std < 50:
            return 55
        elif avg_std < 80:
            return 35
        return 20

    def _entropy(self, pixels):
        sample = pixels[::max(1, len(pixels)//500)]
        brightness = [(p[0] + p[1] + p[2]) // 3 for p in sample]
        freq = Counter(brightness)
        total = len(brightness)
        entropy = -sum((c/total) * math.log2(c/total) for c in freq.values() if c > 0)
        norm = entropy / 8.0
        if norm > 0.95:
            return 70
        elif norm > 0.85:
            return 45
        return 25

    def _symmetry(self, img):
        try:
            small = img.resize((64, 64))
            pixels = list(small.getdata())
            sym = 0
            for y in range(64):
                for x in range(32):
                    left = pixels[y * 64 + x]
                    right = pixels[y * 64 + (63 - x)]
                    diff = sum(abs(a - b) for a, b in zip(left[:3], right[:3]))
                    if diff < 30:
                        sym += 1
            ratio = sym / (64 * 32)
            return 70 if ratio > 0.7 else (45 if ratio > 0.5 else 20)
        except:
            return 40


# ══════════════════════════════════════════════════════
# БЕЙНЕ ДЕТЕКТОРЫ
# ══════════════════════════════════════════════════════

class VideoDetector:
    """Бейнені талдау — дипфейк белгілерін іздейді"""

    def analyze(self, video_path: str) -> dict:
        try:
            import cv2
            return self._analyze_cv2(video_path)
        except ImportError:
            return {
                'score': 50,
                'verdict': 'unknown',
                'label': '⚠️ OpenCV орнатылмаған',
                'text': 'pip install opencv-python командасын іске қосыңыз',
                'type': 'video'
            }
        except Exception as e:
            return {
                'score': 0,
                'verdict': 'error',
                'label': '❌ Қате',
                'text': str(e),
                'type': 'video'
            }

    def _analyze_cv2(self, path):
        import cv2
        import numpy as np

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return {'score': 0, 'verdict': 'error', 'label': '❌ Файл ашылмады', 'text': '', 'type': 'video'}

        fps = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total / fps if fps > 0 else 0

        # Максимум 80 кадр алу
        step = max(1, total // 80)
        frames = []
        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % step == 0:
                frames.append(frame)
            idx += 1
        cap.release()

        if len(frames) < 3:
            return {'score': 50, 'verdict': 'unknown', 'label': '⚠️ Бейне тым қысқа', 'text': '', 'type': 'video'}

        temporal = self._temporal(frames)
        noise = self._noise(frames)
        artifacts = self._artifacts(frames)

        score = int(temporal * 0.40 + noise * 0.35 + artifacts * 0.25)
        score = max(5, min(95, score))

        verdict = 'ai' if score > 55 else 'human'
        label = '🤖 Дипфейк болуы мүмкін' if verdict == 'ai' else '✅ Нақты бейне'

        indicators = []
        if temporal > 60:
            indicators.append('🔴 Кадрлар арасында уақыттық сәйкессіздік')
        if noise > 60:
            indicators.append('🟡 GAN-тәрізді шу аномалиясы')
        if artifacts > 60:
            indicators.append('🟡 Сығу артефактілері анықталды')

        explanation = f"**Нәтиже:** {label} — {score}%\n\n"
        explanation += '\n'.join(indicators) if indicators else '🟢 Күдікті белгілер табылмады'
        explanation += f"\n\n🎬 Ұзақтық: {duration:.1f}с | FPS: {fps:.0f} | {w}×{h}"
        explanation += f"\n📊 Талданған кадрлар: {len(frames)}"
        explanation += "\n\n💡 **Ескерту:** Бейне анализі 100% дәл емес."

        return {
            'score': score,
            'verdict': verdict,
            'label': label,
            'text': explanation,
            'type': 'video',
            'details': {
                'duration': f'{duration:.1f}s',
                'fps': round(fps),
                'resolution': f'{w}x{h}',
                'temporal_score': round(temporal),
                'noise_score': round(noise),
                'artifact_score': round(artifacts),
            }
        }

    def _temporal(self, frames):
        import cv2
        import numpy as np
        diffs = [np.mean(cv2.absdiff(frames[i-1], frames[i])) for i in range(1, len(frames))]
        if not diffs:
            return 50
        mean = sum(diffs) / len(diffs)
        std = math.sqrt(sum((d - mean)**2 for d in diffs) / len(diffs))
        cv = std / mean if mean > 0 else 0
        return 75 if cv > 0.8 else (50 if cv > 0.5 else 25)

    def _noise(self, frames):
        import cv2
        import numpy as np
        scores = []
        for f in frames[::5]:
            gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            lap = cv2.Laplacian(gray, cv2.CV_64F)
            scores.append(float(np.var(lap)))
        if not scores:
            return 50
        avg = sum(scores) / len(scores)
        return 70 if avg < 50 else (45 if avg < 200 else 25)

    def _artifacts(self, frames):
        import cv2
        import numpy as np
        scores = []
        for f in frames[::10]:
            gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(float)
            h, w = gray.shape
            bd = 0
            cnt = 0
            for y in range(0, h-8, 8):
                for x in range(0, w-8, 8):
                    bd += abs(gray[y+7, x] - gray[y, x])
                    bd += abs(gray[y, x+7] - gray[y, x])
                    cnt += 2
            if cnt:
                scores.append(bd / cnt)
        if not scores:
            return 50
        avg = sum(scores) / len(scores)
        return 65 if avg > 15 else (40 if avg > 8 else 20)


# ══════════════════════════════════════════════════════
# БАСТЫ ДЕТЕКТОР (app.py пайдаланатын класс)
# ══════════════════════════════════════════════════════

class AIDetector:
    """
    KazAI үшін бірыңғай детектор.
    Мәтін, сурет және бейнені анықтайды.
    app.py өзгертусіз жұмыс істейді.
    """

    def __init__(self):
        self.text_detector  = TextDetector()
        self.image_detector = ImageDetector()
        self.video_detector = VideoDetector()

    def analyze(self, text: str) -> dict:
        """Мәтін анализі — app.py /api/chat (module='det') шақырады"""
        return self.text_detector.analyze(text)

    def analyze_image(self, image_path: str) -> dict:
        """Сурет анализі — /api/detect/image эндпоинті шақырады"""
        return self.image_detector.analyze(image_path)

    def analyze_video(self, video_path: str) -> dict:
        """Бейне анализі — /api/detect/video эндпоинті шақырады"""
        return self.video_detector.analyze(video_path)