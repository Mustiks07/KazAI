from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import json
import re
import logging
import secrets
from datetime import timedelta
from dotenv import load_dotenv

# .env жүктеу
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.env"))

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

from database import db, User, Chat, Message
from modules.gov_service import GovService
from modules.tutor import KazakhTutor
from modules.detector import AIDetector
from modules.openrouter import OpenRouterClient

FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../frontend')
app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# Config
_default_secret = secrets.token_hex(32)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', _default_secret)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET', _default_secret)
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=7)
app.config['JWT_TOKEN_LOCATION'] = ['headers']
app.config['JWT_HEADER_NAME'] = 'Authorization'
app.config['JWT_HEADER_TYPE'] = 'Bearer'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kazai.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30 MB

db.init_app(app)
jwt = JWTManager(app)

# Rate Limiting — спамнан қорғау
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri="memory://",
)

# ── Валидация хелперлері ──
MAX_TEXT_LENGTH = 5000  # Максималды мәтін ұзындығы
MAX_NAME_LENGTH = 100
EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def _validate_text(text, max_len=MAX_TEXT_LENGTH):
    """Мәтінді тексеру — тым ұзын немесе бос."""
    if not text or not text.strip():
        return None, 'Мәтін жоқ'
    text = text.strip()
    if len(text) > max_len:
        return None, f'Мәтін тым ұзын (макс. {max_len} таңба)'
    return text, None

def _validate_email(email):
    """Email форматын тексеру."""
    if not email or not EMAIL_RE.match(email):
        return None, 'Жарамды email енгізіңіз'
    if len(email) > 254:
        return None, 'Email тым ұзын'
    return email.strip().lower(), None

# Modules
gov       = GovService()
tutor     = KazakhTutor()
detector  = AIDetector()
ai_client = OpenRouterClient()

# ─────────────────────────────────────
# SERVE FRONTEND
# ─────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(FRONTEND, 'index.html')

# ─────────────────────────────────────
# AUTH
# ─────────────────────────────────────
@app.route('/api/auth/register', methods=['POST'])
@limiter.limit("10 per minute")
def register():
    data = request.json or {}
    name     = data.get('name', '').strip()
    password = data.get('password', '')

    if not name or len(name) > MAX_NAME_LENGTH:
        return jsonify({'error': 'Атыңызды дұрыс енгізіңіз (1-100 таңба)'}), 400

    email, err = _validate_email(data.get('email', ''))
    if err:
        return jsonify({'error': err}), 400

    if not password or len(password) < 6:
        return jsonify({'error': 'Пароль кем дегенде 6 таңба'}), 400
    if len(password) > 128:
        return jsonify({'error': 'Пароль тым ұзын'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Бұл email тіркелген'}), 400

    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    logger.info("Жаңа пайдаланушы: %s (%s)", name, email)
    return jsonify({'token': token, 'user': user.to_dict()}), 201


@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("15 per minute")
def login():
    data  = request.json or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email және парольді енгізіңіз'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Email немесе пароль қате'}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({'token': token, 'user': user.to_dict()})


@app.route('/api/auth/me', methods=['GET'])
@jwt_required(locations=["headers"])
def me():
    user = db.session.get(User,int(get_jwt_identity()))
    if not user:
        return jsonify({'error': 'Пайдаланушы табылмады'}), 404
    return jsonify(user.to_dict())

# ─────────────────────────────────────
# CHAT
# ─────────────────────────────────────
@app.route('/api/chat', methods=['POST'])
@jwt_required(locations=["headers"])
@limiter.limit("30 per minute")
def chat():
    user_id = int(get_jwt_identity())
    user    = db.session.get(User,user_id)
    if not user:
        return jsonify({'error': 'Пайдаланушы табылмады'}), 404

    # Күнделікті есептегішті тексер
    user.reset_daily_if_needed()

    data    = request.json or {}
    module  = data.get('module', 'auto')
    chat_id = data.get('chat_id')

    # Мәтінді валидациялау
    text, err = _validate_text(data.get('text', ''))
    if err:
        return jsonify({'error': err}), 400

    # Модуль валидациясы
    if module not in ('all', 'auto', 'gov', 'tutor', 'det'):
        module = 'auto'

    # Free plan лимит тексеру
    if user.plan == 'free' and user.daily_count >= 20:
        return jsonify({'error': 'limit', 'message': 'Бүгінгі лимит таусылды (20/20). Pro жоспарына ауысыңыз!'}), 429

    logger.info("Chat: module=%s, user=%s, text=%r", module, user.email, text[:60])

    response_data = {}

    # Чат контекстін жүктеу (AI алдыңғы хабарларды есте сақтасын)
    chat_history = []
    if chat_id:
        prev_msgs = Message.query.filter_by(chat_id=chat_id)\
            .order_by(Message.created_at).all()
        for m in prev_msgs[-10:]:  # Соңғы 10 хабар
            if m.content and m.role in ('user', 'assistant'):
                chat_history.append({'role': m.role, 'content': m.content})

    # ── Детектор режимі ──
    if module == 'det':
        result = detector.analyze(text)
        response_data = {
            'verdict': result['verdict'],
            'score':   result['score'],
            'label':   result['label'],
            'text':    result['text'],
            'source':  'detector',
        }

    # ── Мемлекеттік қызметтер ──
    elif module == 'gov':
        result = gov.search(text)
        if result['confidence'] > 0.3:
            response_data = {
                'text': result['answer'],
                'source': 'gov_db',
                'title': result.get('title', ''),
                'source_url': result.get('source_url', ''),
            }
        else:
            ai_resp = ai_client.ask(text, context='gov', chat_history=chat_history)
            response_data = {'text': ai_resp, 'source': 'ai'}

    # ── Қазақ тілі репетиторы ──
    elif module == 'tutor':
        result = tutor.analyze(text)
        if result['found']:
            response_data = {'text': result['answer'], 'source': 'tutor_db'}
        else:
            ai_resp = ai_client.ask(text, context='tutor', chat_history=chat_history)
            response_data = {'text': ai_resp, 'source': 'ai'}

    # ── Авто — модульді анықтай ──
    else:
        detected = _detect_module(text)

        if detected == 'det':
            result = detector.analyze(text)
            response_data = {
                'verdict': result['verdict'],
                'score':   result['score'],
                'label':   result['label'],
                'text':    result['text'],
                'source':  'detector',
            }
        elif detected == 'gov':
            result = gov.search(text)
            if result['confidence'] > 0.4:
                response_data = {'text': result['answer'], 'source': 'gov_db'}
            else:
                response_data = {'text': ai_client.ask(text, context='gov', chat_history=chat_history), 'source': 'ai'}
        elif detected == 'tutor':
            result = tutor.analyze(text)
            if result['found']:
                response_data = {'text': result['answer'], 'source': 'tutor_db'}
            else:
                response_data = {'text': ai_client.ask(text, context='tutor', chat_history=chat_history), 'source': 'ai'}
        else:
            response_data = {'text': ai_client.ask(text, context='general', chat_history=chat_history), 'source': 'ai'}

    # ── DB-ге сақтау ──
    if not chat_id:
        title = text[:45] + ('…' if len(text) > 45 else '')
        new_chat = Chat(user_id=user_id, title=title)
        db.session.add(new_chat)
        db.session.flush()
        chat_id = new_chat.id

    # Хабарлар сақтау
    user_msg = Message(chat_id=chat_id, role='user', content=text, module=module)
    # Детектор жауабы үшін арнайы сақтау
    assistant_content = response_data.get('text', '')
    if response_data.get('verdict'):
        # Детектор нәтижесін JSON ретінде сақтаймыз
        assistant_content = json.dumps({
            'verdict': response_data['verdict'],
            'score':   response_data['score'],
            'label':   response_data['label'],
            'text':    response_data['text'],
        }, ensure_ascii=False)
    bot_msg = Message(chat_id=chat_id, role='assistant', content=assistant_content, module=module)

    db.session.add(user_msg)
    db.session.add(bot_msg)

    user.daily_count   += 1
    user.total_messages += 1
    db.session.commit()

    return jsonify({
        'response': response_data,
        'chat_id':  chat_id,
        'usage':    {
            'today': user.daily_count,
            'limit': 20 if user.plan == 'free' else None,
        },
    })


def _detect_module(text: str) -> str:
    """Сұрақ бойынша модульді анықтау — кеңейтілген"""
    t = text.lower()

    det_keys = [
        'жасанды ма', 'жасанды интеллект жазды', 'ии жазды', 'chatgpt жазды',
        'анықта', 'детектор', 'ai generated', 'generated', 'тексер мәтін',
        'нейросеть жазды', 'gpt жазды', 'робот жазды', 'ai жазды',
        'ии тексер', 'жасанды интеллект пен', 'адам жазды ма',
    ]
    gov_keys = [
        'иин', 'эцп', 'паспорт', 'жәрдемақы', 'egov', 'дәрігер', 'поликлиника',
        'автокөлік', 'тіркеу', 'мемлекеттік қызмет', 'цон', 'жеке куәлік',
        'загс', 'неке', 'туу туралы', 'балаға', 'зейнетақы', 'енпф',
        'жұмыссыздық', 'айыппұл', 'салық', 'жер учаске', 'лицензия',
        'анықтама', 'прописка', 'тіркеу анықтама', 'әскерге', 'шақыру қағаз',
        'декрет', 'мүгедектік', 'әлеуметтік', 'тұрғын үй', 'субсидия',
        'нотариус', 'сенімхат', 'мұрагерлік', 'азаматтық', 'кәсіпкер',
        'жеке кәсіпкер', 'тоо', 'жк ашу', 'бизнес ашу',
        '1414', 'электрондық үкімет',
    ]
    tutor_keys = [
        'грамматика', 'аудар', 'сөйлемді тексер', 'қате бар', 'дұрыс па',
        'жіктеу', 'айтылым', 'барды', 'бардым', 'септік',
        'қазақша', 'қазақ тілі', 'ереже', 'жалғау', 'жұрнақ',
        'көмектес етістік', 'есімше', 'көсемше', 'шылау',
        'сөйлем мүшесі', 'бастауыш', 'баяндауыш',
        'емле', 'дыбыс', 'буын', 'орфография',
        'мәтінді тексер', 'translate', 'перевод', 'аударма',
        'қалай жазылады', 'қалай айтылады', 'не деген сөз',
    ]

    # Сәйкестік санын тексеру — көп сәйкес болған модуль таңдалады
    det_score = sum(1 for k in det_keys if k in t)
    gov_score = sum(1 for k in gov_keys if k in t)
    tutor_score = sum(1 for k in tutor_keys if k in t)

    max_score = max(det_score, gov_score, tutor_score)
    if max_score == 0:
        return 'general'

    if det_score == max_score:
        return 'det'
    if gov_score == max_score:
        return 'gov'
    if tutor_score == max_score:
        return 'tutor'
    return 'general'

# ─────────────────────────────────────
# HISTORY
# ─────────────────────────────────────
@app.route('/api/history', methods=['GET'])
@jwt_required(locations=["headers"])
def history():
    user_id = int(get_jwt_identity())
    chats = Chat.query.filter_by(user_id=user_id)\
        .order_by(Chat.created_at.desc()).limit(50).all()
    return jsonify([c.to_dict() for c in chats])


@app.route('/api/history/<int:chat_id>/messages', methods=['GET'])
@jwt_required(locations=["headers"])
def chat_messages(chat_id):
    user_id = int(get_jwt_identity())
    chat = Chat.query.filter_by(id=chat_id, user_id=user_id).first_or_404()
    msgs = Message.query.filter_by(chat_id=chat.id)\
        .order_by(Message.created_at).all()
    result = []
    for m in msgs:
        d = m.to_dict()
        # Детектор хабарларын parse қылу
        if m.role == 'assistant' and m.module in ('det', 'auto'):
            try:
                parsed = json.loads(m.content)
                if isinstance(parsed, dict) and 'verdict' in parsed:
                    d['content'] = parsed.get('text', m.content)
                    d['det_data'] = {
                        'verdict': parsed['verdict'],
                        'score':   parsed['score'],
                        'label':   parsed.get('label',''),
                    }
            except Exception:
                pass
        result.append(d)
    return jsonify(result)


@app.route('/api/history/<int:chat_id>', methods=['DELETE'])
@jwt_required(locations=["headers"])
def delete_chat(chat_id):
    user_id = int(get_jwt_identity())
    chat = Chat.query.filter_by(id=chat_id, user_id=user_id).first_or_404()
    Message.query.filter_by(chat_id=chat.id).delete()
    db.session.delete(chat)
    db.session.commit()
    return jsonify({'ok': True})

# ─────────────────────────────────────
# SUBSCRIPTION
# ─────────────────────────────────────
@app.route('/api/subscription', methods=['POST'])
@jwt_required(locations=["headers"])
def upgrade():
    user_id = int(get_jwt_identity())
    plan    = request.json.get('plan', 'pro')
    if plan not in ('free', 'pro', 'ultra'):
        return jsonify({'error': 'Жарамсыз жоспар'}), 400
    user = db.session.get(User,user_id)
    user.plan = plan
    db.session.commit()
    return jsonify({'ok': True, 'plan': plan})

# ─────────────────────────────────────
# STATS
# ─────────────────────────────────────
@app.route('/api/stats', methods=['GET'])
@jwt_required(locations=["headers"])
def stats():
    user = db.session.get(User,int(get_jwt_identity()))
    user.reset_daily_if_needed()
    return jsonify({
        'total_messages': user.total_messages,
        'daily_count':    user.daily_count,
        'plan':           user.plan,
        'member_since':   user.created_at.isoformat(),
    })

# ─────────────────────────────────────
# СУРЕТ ДЕТЕКТОРЫ
# ─────────────────────────────────────
@app.route('/api/detect/image', methods=['POST'])
@jwt_required(optional=True)
@limiter.limit("10 per minute")
def detect_image():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл жоқ'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Файл таңдалмаған'}), 400

    # Файл типін тексеру
    allowed = {'jpg','jpeg','png','webp','gif','bmp'}
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in allowed:
        return jsonify({'error': f'Рұқсат берілген форматтар: {", ".join(allowed)}'}), 400

    import tempfile
    suffix = '.' + ext
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        result = detector.analyze_image(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    return jsonify({'response': result, 'chat_id': None})

# ─────────────────────────────────────
# БЕЙНЕ ДЕТЕКТОРЫ
# ─────────────────────────────────────
@app.route('/api/detect/video', methods=['POST'])
@jwt_required(optional=True)
@limiter.limit("5 per minute")
def detect_video():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл жоқ'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Файл таңдалмаған'}), 400

    allowed = {'mp4','avi','mov','mkv','webm'}
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in allowed:
        return jsonify({'error': f'Рұқсат берілген форматтар: {", ".join(allowed)}'}), 400

    import tempfile
    suffix = '.' + ext
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        result = detector.analyze_video(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    return jsonify({'response': result, 'chat_id': None})

# ─────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '2.1'})

# ── Глобальды қателер өңдеуші ──
@app.errorhandler(429)
def rate_limit_exceeded(e):
    return jsonify({
        'error': 'Сұраулар шектеуі асырылды. Біраз күтіп, қайталаңыз.',
        'retry_after': e.description
    }), 429

@app.errorhandler(413)
def request_too_large(e):
    return jsonify({'error': 'Файл тым үлкен (макс. 30 MB)'}), 413

@app.errorhandler(500)
def internal_error(e):
    logger.error("Серверлік қате: %s", e)
    return jsonify({'error': 'Серверлік қате. Кейінірек қайталаңыз.'}), 500

# ─────────────────────────────────────
# INIT DB + RUN
# ─────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        logger.info("База деректер дайын")
    app.run(debug=True, host='0.0.0.0', port=5000)