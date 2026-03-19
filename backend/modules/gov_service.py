import json
import os
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


class GovService:
    """
    Мемлекеттік қызметтер модулі.
    TF-IDF негізінде FAQ базасынан іздейді.
    """

    def __init__(self):
        self.faq = self._load_faq()
        self.vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4))
        self._build_index()

    def _load_faq(self):
        path = os.path.join(os.path.dirname(__file__), '../data/gov_faq.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _build_index(self):
        """Build TF-IDF index from FAQ questions."""
        questions = []
        for item in self.faq:
            # Combine question + keywords for better matching
            combined = item['question'] + ' ' + ' '.join(item.get('keywords', []))
            questions.append(combined.lower())

        self.vectors = self.vectorizer.fit_transform(questions)
        print(f"✅ Мемлекеттік қызметтер базасы: {len(self.faq)} жазба")

    def search(self, query: str) -> dict:
        """
        Find the best matching FAQ entry.
        Returns: {answer, confidence, title, source_url}
        """
        query_vec = self.vectorizer.transform([query.lower()])
        similarities = cosine_similarity(query_vec, self.vectors).flatten()
        best_idx = np.argmax(similarities)
        confidence = float(similarities[best_idx])

        if confidence < 0.1:
            return {
                'answer': self._fallback(query),
                'confidence': 0.0,
                'title': 'Жалпы',
                'source_url': 'https://egov.kz'
            }

        item = self.faq[best_idx]
        return {
            'answer': item['answer'],
            'confidence': confidence,
            'title': item['title'],
            'source_url': item.get('url', 'https://egov.kz')
        }

    def _fallback(self, query: str) -> str:
        return (
            "Бұл сұрақ бойынша нақты ақпарат табылмады.\n\n"
            "**Ұсыныстар:**\n"
            "- 🌐 [egov.kz](https://egov.kz) — барлық мемлекеттік қызметтер\n"
            "- 📞 **1414** — мемлекеттік қызметтер анықтамасы\n"
            "- 🏢 Жақын ЦОН-ға хабарласыңыз\n\n"
            "Сұрақты нақтырақ жазсаңыз көмектесе аламын!"
        )
