import re
import json
import os
import logging

logger = logging.getLogger(__name__)


class KazakhTutor:
    """
    Қазақ тілі репетиторы модулі.
    Грамматика ережелері, морфология талдауы, аударма.
    """

    def __init__(self):
        self.rules = self._load_rules()
        self.vocab = self._load_vocab()
        logger.info("Репетитор базасы: %d ереже, %d сөз",
                     len(self.rules),
                     len(self.vocab.get('kaz_to_rus', {})) + len(self.vocab.get('rus_to_kaz', {})))

    def _load_rules(self):
        path = os.path.join(os.path.dirname(__file__), '../data/grammar_rules.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error("Грамматика ережелері жүктелмеді: %s", e)
            return []

    def _load_vocab(self):
        path = os.path.join(os.path.dirname(__file__), '../data/kazakh_vocab.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("Сөздік жүктелмеді: %s", e)
            return {"kaz_to_rus": {}, "rus_to_kaz": {}}

    def analyze(self, text: str) -> dict:
        """
        Мәтінді талдау — грамматика, аударма, тексеру.
        """
        text_lower = text.lower().strip()

        # 1. Грамматика ережелерін тексеру
        for rule in self.rules:
            for trigger in rule.get('triggers', []):
                if trigger.lower() in text_lower:
                    return {
                        'found': True,
                        'answer': self._format_rule(rule),
                        'type': 'grammar_rule'
                    }

        # 2. Аударма сұрағын тексеру
        if self._is_translation_request(text_lower):
            words = self._extract_words_to_translate(text)
            result = self._translate(words, text)
            if result:
                return {
                    'found': True,
                    'answer': result,
                    'type': 'translation'
                }

        # 3. Грамматика тексеру сұрағы
        if self._is_check_request(text_lower):
            sentence = self._extract_sentence(text)
            if sentence and len(sentence) > 3:
                errors = self._check_errors(sentence)
                return {
                    'found': True,
                    'answer': self._format_check(sentence, errors),
                    'type': 'grammar_check'
                }

        # 4. «Не деген сөз» / «Қалай жазылады» сұрақтары
        word_query = self._extract_word_query(text_lower)
        if word_query:
            return {
                'found': True,
                'answer': word_query,
                'type': 'word_info'
            }

        # 5. Табылмады — AI-ға жіберу
        return {
            'found': False,
            'answer': '',
            'type': 'unknown'
        }

    def _is_translation_request(self, text_lower):
        triggers = [
            'аудар', 'перевод', 'translate', 'қазақша',
            'орысша', 'ағылшынша', 'қалай аударылады',
            'переведи', 'аударма', 'мағынасы',
        ]
        return any(w in text_lower for w in triggers)

    def _is_check_request(self, text_lower):
        triggers = [
            'тексер', 'дұрыс па', 'қате бар', 'correct',
            'проверь', 'тексеріп бер', 'дұрыс жазылған ба',
            'қатесі бар ма', 'грамматика тексер',
            'сөйлемді тексер', 'мәтінді тексер',
        ]
        return any(w in text_lower for w in triggers)

    def _extract_word_query(self, text_lower):
        """«Не деген сөз», «Қалай жазылады» сұрақтарын өңдеу."""
        patterns = [
            (r'["\']?(\w+)["\']?\s+не деген сөз', 'meaning'),
            (r'не деген сөз\s+["\']?(\w+)["\']?', 'meaning'),
            (r'["\']?(\w+)["\']?\s+қалай жазылады', 'spelling'),
            (r'["\']?(\w+)["\']?\s+мағынасы', 'meaning'),
            (r'["\']?(\w+)["\']?\s+деген не', 'meaning'),
        ]
        for pattern, query_type in patterns:
            match = re.search(pattern, text_lower)
            if match:
                word = match.group(1)
                kaz = self.vocab.get('kaz_to_rus', {}).get(word)
                rus = self.vocab.get('rus_to_kaz', {}).get(word)
                if kaz:
                    return f"**«{word}»** сөзінің аудармасы: **{kaz}**"
                elif rus:
                    return f"**«{word}»** сөзінің қазақша аудармасы: **{rus}**"
                else:
                    return f"**«{word}»** сөзі сөздікте табылмады. AI көмекшіден сұраңыз."
        return None

    def _format_rule(self, rule: dict) -> str:
        lines = [f"**{rule.get('title', '')}**\n"]

        if rule.get('explanation'):
            lines.append(rule['explanation'] + '\n')

        if rule.get('examples'):
            lines.append('\n**Мысалдар:**')
            for ex in rule['examples']:
                icon = '❌' if ex.get('wrong') else '✅'
                line = f"{icon} {ex['text']}"
                if ex.get('note'):
                    line += f" — {ex['note']}"
                lines.append(line)

        if rule.get('table'):
            lines.append('\n**Кесте:**')
            for row in rule['table']:
                # Әр түрлі кестелерге бейімделу (person/verb/type/case кілттері)
                parts = []
                for key, val in row.items():
                    if key == 'example':
                        parts.append(f"*{val}*")
                    else:
                        parts.append(f"**{val}**")
                lines.append(' → '.join(parts))

        if rule.get('tip'):
            lines.append(f"\n💡 **Кеңес:** {rule['tip']}")

        return '\n'.join(lines)

    def _format_check(self, sentence: str, errors: list) -> str:
        if not errors:
            return (
                f"✅ **Сөйлем дұрыс!**\n\n"
                f"«{sentence}»\n\n"
                f"Грамматикалық қате табылмады. Жарайсыз! 👏"
            )

        lines = [f"🔍 **Тексеру нәтижесі:** «{sentence}»\n"]
        lines.append(f"⚠️ **{len(errors)} қате табылды:**\n")

        for i, err in enumerate(errors, 1):
            lines.append(f"**{i}. {err['type']}**")
            lines.append(f"❌ «{err['wrong']}» → ✅ «{err['correct']}»")
            lines.append(f"📖 {err['rule']}\n")

        lines.append("💡 **Кеңес:** Жіктеулік жалғауларына назар аударыңыз!")
        return '\n'.join(lines)

    def _translate(self, words: list, original_text: str) -> str:
        """Сөздерді аудару — кеңейтілген."""
        results = []

        for word in words[:10]:
            word_lower = word.lower().strip('.,!?;:«»""')
            if len(word_lower) < 2:
                continue

            # Қазақша → Орысша
            kaz = self.vocab.get('kaz_to_rus', {}).get(word_lower)
            if kaz:
                results.append(f"**{word}** (қаз) → {kaz}")
                continue

            # Орысша → Қазақша
            rus = self.vocab.get('rus_to_kaz', {}).get(word_lower)
            if rus:
                results.append(f"**{word}** (рус) → {rus}")
                continue

        if results:
            return '**Аударма нәтижесі:**\n\n' + '\n'.join(results)

        if words:
            return (
                "**Аударма:**\n\n"
                f"«{'  '.join(words[:5])}» — сөздікте табылмады.\n\n"
                "💡 Толық сөйлемді жіберіңіз — AI көмекші аударып береді."
            )
        return None

    def _extract_sentence(self, text: str) -> str:
        """Тексерілетін сөйлемді бөліп алу."""
        # Тырнақша ішіндегі мәтін
        quoted = re.findall(r'[«»""\'"](.+?)[«»""\'"]', text)
        if quoted:
            return quoted[0].strip()

        # Қос нүкте кейінгі мәтін
        if ':' in text:
            after = text.split(':', 1)[1].strip()
            if len(after) > 3:
                return after

        # «Тексер» сөзінен кейінгі мәтін
        for trigger in ['тексер', 'проверь', 'дұрыс па']:
            if trigger in text.lower():
                idx = text.lower().index(trigger) + len(trigger)
                after = text[idx:].strip(' :,')
                if len(after) > 3:
                    return after

        return text

    def _extract_words_to_translate(self, text: str) -> list:
        stop = {
            'аудар', 'аударыңыз', 'аударып', 'аударшы', 'аударма',
            'перевод', 'переведи', 'translate',
            'қазақша', 'орысша', 'ағылшынша',
            'мына', 'сөзді', 'сөзін', 'мәтінді', 'маған',
            'бер', 'беріңіз', 'берші',
        }
        words = text.split()
        return [w for w in words if w.lower().strip('.,!?') not in stop and len(w) > 1]

    def _check_errors(self, sentence: str) -> list:
        """Грамматикалық қателерді тексеру — кеңейтілген."""
        errors = []
        text_lower = sentence.lower()
        words = sentence.split()

        # ── 1. Етістік жіктелуі (Мен + 3-жақ етістік) ──
        verb_errors = {
            'барды':  ('бардым',  'Мен барды → Мен бардым (1-жақ жіктеулік жалғауы -м/-мын)'),
            'келді':  ('келдім',  'Мен келді → Мен келдім'),
            'жазды':  ('жаздым',  'Мен жазды → Мен жаздым'),
            'оқыды':  ('оқыдым',  'Мен оқыды → Мен оқыдым'),
            'жүрді':  ('жүрдім',  'Мен жүрді → Мен жүрдім'),
            'тұрды':  ('тұрдым',  'Мен тұрды → Мен тұрдым'),
            'алды':   ('алдым',   'Мен алды → Мен алдым'),
            'берді':  ('бердім',  'Мен берді → Мен бердім'),
            'көрді':  ('көрдім',  'Мен көрді → Мен көрдім'),
            'білді':  ('білдім',  'Мен білді → Мен білдім'),
            'айтты':  ('айттым',  'Мен айтты → Мен айттым'),
            'жасады': ('жасадым', 'Мен жасады → Мен жасадым'),
            'істеді': ('істедім', 'Мен істеді → Мен істедім'),
            'ойнады': ('ойнадым', 'Мен ойнады → Мен ойнадым'),
            'сөйледі':('сөйледім','Мен сөйледі → Мен сөйледім'),
        }

        # Мен + 3-жақ
        if 'мен' in text_lower:
            for wrong, (correct, explanation) in verb_errors.items():
                if wrong in text_lower:
                    errors.append({
                        'type': 'Етістік жіктелуі (1-жақ)',
                        'wrong': wrong,
                        'correct': correct,
                        'rule': explanation
                    })

        # Сен + 3-жақ
        sen_fixes = {
            'барды': ('бардың', 'Сен барды → Сен бардың (2-жақ: -ң/-сың)'),
            'келді': ('келдің', 'Сен келді → Сен келдің'),
            'жазды': ('жаздың', 'Сен жазды → Сен жаздың'),
            'оқыды': ('оқыдың', 'Сен оқыды → Сен оқыдың'),
        }
        if 'сен' in text_lower and 'мен' not in text_lower:
            for wrong, (correct, explanation) in sen_fixes.items():
                if wrong in text_lower:
                    errors.append({
                        'type': 'Етістік жіктелуі (2-жақ)',
                        'wrong': wrong,
                        'correct': correct,
                        'rule': explanation
                    })

        # ── 2. Буын үндестігі (жуан/жіңішке сәйкессіздік) ──
        harmony_errors = {
            'баладер': ('балалар', 'Буын үндестігі: жуан сөз + жуан жалғау (а→а)'),
            'кітаптер': ('кітаптар', 'Буын үндестігі: жуан сөз + жуан жалғау'),
            'үйлар': ('үйлер', 'Буын үндестігі: жіңішке сөз + жіңішке жалғау (ү→е)'),
            'көздар': ('көздер', 'Буын үндестігі: жіңішке сөз + жіңішке жалғау'),
        }
        for wrong, (correct, explanation) in harmony_errors.items():
            if wrong in text_lower:
                errors.append({
                    'type': 'Буын үндестігі',
                    'wrong': wrong,
                    'correct': correct,
                    'rule': explanation
                })

        # ── 3. Көптік жалғау қателері ──
        plural_errors = {
            'адамдер': ('адамдар', 'Көптік жалғау: жуан дыбыстан кейін -дар'),
            'жолдер': ('жолдар', 'Көптік жалғау: жуан дыбыстан кейін -дар'),
            'сөзлер': ('сөздер', 'Көптік жалғау: з-дан кейін -дер'),
        }
        for wrong, (correct, explanation) in plural_errors.items():
            if wrong in text_lower:
                errors.append({
                    'type': 'Көптік жалғау',
                    'wrong': wrong,
                    'correct': correct,
                    'rule': explanation
                })

        # ── 4. Жалпы қателер ──
        common_errors = {
            'керегі жоқ': None,  # дұрыс
            'кереқ': ('керек', 'Емле: «керек» дұрыс жазылуы — қ емес, к'),
            'калай': ('қалай', 'Емле: «қалай» — қ әрпімен жазылады'),
            'кашан': ('қашан', 'Емле: «қашан» — қ әрпімен жазылады'),
            'болмай ды': ('болмайды', 'Емле: «болмайды» — бірге жазылады'),
        }
        for wrong, fix in common_errors.items():
            if fix and wrong in text_lower:
                errors.append({
                    'type': 'Емле қатесі',
                    'wrong': wrong,
                    'correct': fix[0],
                    'rule': fix[1]
                })

        return errors
