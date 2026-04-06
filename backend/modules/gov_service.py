import json
import os
import re
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

logger = logging.getLogger(__name__)


class GovService:
    """
    Мемлекеттік қызметтер модулі.
    TF-IDF + кілт сөздер негізінде FAQ базасынан іздейді.
    """

    def __init__(self):
        self.faq = self._load_faq()
        self.vectorizer = TfidfVectorizer(
            analyzer='char_wb',
            ngram_range=(2, 5),
            max_features=10000,
        )
        self._build_index()

    def _load_faq(self):
        path = os.path.join(os.path.dirname(__file__), '../data/gov_faq.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info("Мемлекеттік қызметтер базасы: %d жазба", len(data))
                return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error("gov_faq.json жүктелмеді: %s", e)
            return []

    def _build_index(self):
        """TF-IDF индексін құру — сұрақ + кілт сөздер + тақырып."""
        if not self.faq:
            self.vectors = None
            return

        documents = []
        for item in self.faq:
            # Тақырып, сұрақ, кілт сөздерді біріктіру — іздеу дәлдігін арттыру
            parts = [
                item.get('title', ''),
                item.get('question', ''),
                ' '.join(item.get('keywords', [])),
            ]
            combined = ' '.join(parts).lower()
            documents.append(combined)

        self.vectors = self.vectorizer.fit_transform(documents)

    def search(self, query: str) -> dict:
        """
        FAQ базасынан ең жақсы жауапты табу.
        Гибридті іздеу: TF-IDF + кілт сөздер бонусы.
        """
        if not self.faq or self.vectors is None:
            return self._empty_result(query)

        query_lower = query.lower()

        # 1. TF-IDF косинустық ұқсастық
        query_vec = self.vectorizer.transform([query_lower])
        tfidf_scores = cosine_similarity(query_vec, self.vectors).flatten()

        # 2. Кілт сөздер бонусы — нақты сәйкестік үшін
        keyword_scores = np.zeros(len(self.faq))
        for i, item in enumerate(self.faq):
            keywords = item.get('keywords', [])
            matches = 0
            for kw in keywords:
                if kw.lower() in query_lower:
                    matches += 1
            if matches > 0:
                keyword_scores[i] = min(matches * 0.15, 0.5)

        # 3. Тақырып сәйкестігі бонусы
        title_scores = np.zeros(len(self.faq))
        for i, item in enumerate(self.faq):
            title = item.get('title', '').lower()
            if title and title in query_lower:
                title_scores[i] = 0.3

        # Гибридті ұпай
        combined_scores = tfidf_scores + keyword_scores + title_scores

        best_idx = int(np.argmax(combined_scores))
        confidence = float(combined_scores[best_idx])

        if confidence < 0.1:
            return self._empty_result(query)

        item = self.faq[best_idx]
        return {
            'answer': item['answer'],
            'confidence': confidence,
            'title': item.get('title', ''),
            'source_url': item.get('url', 'https://egov.kz'),
        }

    def get_categories(self) -> list:
        """Барлық тақырыптар тізімі (frontend үшін)."""
        return [{'id': item['id'], 'title': item['title']} for item in self.faq]

    def _empty_result(self, query: str) -> dict:
        return {
            'answer': (
                "Бұл сұрақ бойынша нақты ақпарат базада табылмады.\n\n"
                "**Ұсыныстар:**\n"
                "- 🌐 [egov.kz](https://egov.kz) — барлық мемлекеттік қызметтер\n"
                "- 📱 **eGov Mobile** — мобильді қосымша\n"
                "- 📞 **1414** — мемлекеттік қызметтер анықтамасы (тегін)\n"
                "- 🏢 Жақын ЦОН-ға хабарласыңыз\n\n"
                "Сұрақты нақтырақ жазсаңыз, көмектесе аламын!"
            ),
            'confidence': 0.0,
            'title': 'Жалпы',
            'source_url': 'https://egov.kz',
        }
