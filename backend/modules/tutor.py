import re
import json
import os


class KazakhTutor:
    """
    Қазақ тілі репетиторы модулі.
    Грамматика ережелері мен морфология талдауы.
    """

    def __init__(self):
        self.rules = self._load_rules()
        self.vocab = self._load_vocab()
        print(f"✅ Репетитор базасы: {len(self.rules)} ереже")

    def _load_rules(self):
        path = os.path.join(os.path.dirname(__file__), '../data/grammar_rules.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_vocab(self):
        path = os.path.join(os.path.dirname(__file__), '../data/kazakh_vocab.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def analyze(self, text: str) -> dict:
        """
        Analyze text for grammar errors and language questions.
        """
        text_lower = text.lower()

        # 1. Check grammar rules
        for rule in self.rules:
            for trigger in rule['triggers']:
                if trigger.lower() in text_lower:
                    return {
                        'found': True,
                        'answer': self._format_rule(rule),
                        'type': 'grammar_rule'
                    }

        # 2. Check for translation request
        if any(w in text_lower for w in ['аудар', 'перевод', 'translate', 'қазақша', 'орысша']):
            words = self._extract_words_to_translate(text)
            if words:
                return {
                    'found': True,
                    'answer': self._translate(words),
                    'type': 'translation'
                }

        # 3. Check for grammar correction request
        if any(w in text_lower for w in ['тексер', 'дұрыс па', 'қате бар', 'correct']):
            sentence = self._extract_sentence(text)
            if sentence:
                errors = self._check_errors(sentence)
                return {
                    'found': True,
                    'answer': self._format_check(sentence, errors),
                    'type': 'grammar_check'
                }

        # 4. General language question
        return {
            'found': False,
            'answer': '',
            'type': 'unknown'
        }

    def _format_rule(self, rule: dict) -> str:
        lines = [f"**{rule['title']}**\n"]

        if rule.get('explanation'):
            lines.append(rule['explanation'] + '\n')

        if rule.get('examples'):
            lines.append('\n**Мысалдар:**')
            for ex in rule['examples']:
                lines.append(f"{'❌' if ex.get('wrong') else '✅'} {ex['text']}"
                             + (f" — {ex['note']}" if ex.get('note') else ''))

        if rule.get('table'):
            lines.append('\n**Жіктелуі:**')
            for row in rule['table']:
                lines.append(f"**{row['person']}** → {row['suffix']} → *{row['example']}*")

        if rule.get('tip'):
            lines.append(f'\n💡 **Кеңес:** {rule["tip"]}')

        return '\n'.join(lines)

    def _format_check(self, sentence: str, errors: list) -> str:
        if not errors:
            return f"✅ **Сөйлем дұрыс!**\n\n«{sentence}»\n\nГрамматикалық қате табылмады."

        lines = [f"🔍 **Тексеру нәтижесі:** «{sentence}»\n"]
        lines.append(f"⚠️ {len(errors)} қате табылды:\n")

        for i, err in enumerate(errors, 1):
            lines.append(f"**{i}. {err['type']}**")
            lines.append(f"❌ «{err['wrong']}» → ✅ «{err['correct']}»")
            lines.append(f"📖 {err['rule']}\n")

        return '\n'.join(lines)

    def _translate(self, words: list) -> str:
        results = []
        for word in words[:5]:
            kaz = self.vocab.get('kaz_to_rus', {}).get(word.lower())
            rus = self.vocab.get('rus_to_kaz', {}).get(word.lower())
            if kaz:
                results.append(f"**{word}** → {kaz}")
            elif rus:
                results.append(f"**{word}** → {rus}")

        if results:
            return '**Аударма:**\n\n' + '\n'.join(results)
        return '**Сөздік аудармасы:**\n\nБұл сөздер сөздікте табылмады. Нақты сөйлемді жіберіңіз!'

    def _extract_sentence(self, text: str) -> str:
        # Extract quoted text or text after colon
        quoted = re.findall(r'[«»"""](.+?)[«»"""]', text)
        if quoted:
            return quoted[0]
        # After colon
        if ':' in text:
            return text.split(':', 1)[1].strip()
        return text

    def _extract_words_to_translate(self, text: str) -> list:
        # Remove instruction words and return remaining
        stop = ['аудар', 'перевод', 'translate', 'қазақша', 'орысша', 'мына', 'сөзді', 'сөзін']
        words = text.split()
        return [w for w in words if w.lower() not in stop and len(w) > 2]

    def _check_errors(self, sentence: str) -> list:
        errors = []
        words = sentence.split()

        # Common verb conjugation errors
        verb_patterns = [
            {
                'wrong_pattern': r'\b(мен|сен|ол|біз|сіз|олар)\s+\w+(ды|ді|ты|ті)\b',
                'type': 'Етістік жіктелуі',
                'rule': 'Жіктеулік жалғауы тұлғаға қарай өзгереді'
            }
        ]

        # Check specific common mistakes from rules
        common_mistakes = {
            'барды': ('бардым', 'Мен барды → Мен бардым (жіктеулік жалғауы)', 'Етістік жіктелуі'),
            'келді': ('келдім', 'Мен келді → Мен келдім', 'Етістік жіктелуі'),
            'жазды': ('жаздым', 'Мен жазды → Мен жаздым', 'Етістік жіктелуі'),
        }

        text_lower = sentence.lower()
        if 'мен' in text_lower or 'мен' in sentence:
            for wrong, (correct, explanation, err_type) in common_mistakes.items():
                if wrong in text_lower:
                    errors.append({
                        'type': err_type,
                        'wrong': wrong,
                        'correct': correct,
                        'rule': explanation
                    })

        return errors
