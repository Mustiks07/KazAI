from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import os
from datetime import timedelta
from dotenv import load_dotenv

# .env жүктеу
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.env"))

from database import db, User, Chat, Message
from modules.gov_service import GovService
from modules.tutor import KazakhTutor
from modules.detector import AIDetector
from modules.openrouter import OpenRouterClient

FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../frontend')
app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# Config
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'kazai-secret-2024')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET', 'kazai-jwt-2024')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)
app.config['JWT_TOKEN_LOCATION'] = ['headers']
app.config['JWT_HEADER_NAME'] = 'Authorization'
app.config['JWT_HEADER_TYPE'] = 'Bearer'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kazai.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB лимит

db.init_app(app)
jwt = JWTManager(app)

# Modules
gov     = GovService()
tutor   = KazakhTutor()
detector = AIDetector()
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
def register():
    data = request.json
    name  = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not name or not email or not password:
        return jsonify({'error': 'Барлық өрістерді толтырыңыз'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Пароль кем дегенде 6 таңба'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Бұл email тіркелген'}), 400

    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({'token': token, 'user': user.to_dict()}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Email немесе пароль қате'}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({'token': token, 'user': user.to_dict()})

@app.route('/api/auth/me', methods=['GET'])
@jwt_required(locations=["headers"])
def me():
    user = User.query.get(int(get_jwt_identity()))
    return jsonify(user.to_dict())

# ─────────────────────────────────────
# CHAT
# ─────────────────────────────────────
@app.route('/api/chat', methods=['POST'])
@jwt_required(locations=["headers"])
def chat():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    data = request.json

    text    = data.get('text', '').strip()
    module  = data.get('module', 'auto')  # auto | gov | tutor | det
    chat_id = data.get('chat_id')

    if not text:
        return jsonify({'error': 'Мәтін жоқ'}), 400
    
    print(f"📨 Chat request: module={module}, text={text[:50]}, chat_id={chat_id}")

    # Check daily limit for free users
    # Тест режимі: лимит өшірілген
    # if user.plan == 'free' and user.daily_count >= 20:
    #     return jsonify({'error': 'limit', 'message': 'Бүгінгі лимит таусылды'}), 429

    # ── Route to the right module ──
    response_data = {}

    if module == 'det':
        response_data = detector.analyze(text)

    elif module == 'gov':
        result = gov.search(text)
        if result['confidence'] > 0.3:
            response_data = {'text': result['answer'], 'source': 'gov_db'}
        else:
            ai_resp = ai_client.ask(text, context='gov')
            response_data = {'text': ai_resp, 'source': 'ai'}

    elif module == 'tutor':
        result = tutor.analyze(text)
        if result['found']:
            response_data = {'text': result['answer'], 'source': 'tutor_db'}
        else:
            ai_resp = ai_client.ask(text, context='tutor')
            response_data = {'text': ai_resp, 'source': 'ai'}

    else:  # auto
        # Try to detect which module fits
        detected = _detect_module(text)
        if detected == 'gov':
            result = gov.search(text)
            if result['confidence'] > 0.4:
                response_data = {'text': result['answer'], 'source': 'gov_db'}
            else:
                response_data = {'text': ai_client.ask(text, context='gov'), 'source': 'ai'}
        elif detected == 'tutor':
            result = tutor.analyze(text)
            response_data = {'text': result['answer'], 'source': 'tutor_db'}
        else:
            response_data = {'text': ai_client.ask(text, context='general'), 'source': 'ai'}

    # ── Save to DB ──
    if not chat_id:
        title = text[:40] + ('…' if len(text) > 40 else '')
        new_chat = Chat(user_id=user_id, title=title)
        db.session.add(new_chat)
        db.session.flush()
        chat_id = new_chat.id

    db.session.add(Message(chat_id=chat_id, role='user', content=text, module=module))
    db.session.add(Message(chat_id=chat_id, role='assistant',
                           content=response_data.get('text', ''), module=module))

    user.daily_count += 1
    user.total_messages += 1
    db.session.commit()

    return jsonify({
        'response': response_data,
        'chat_id': chat_id,
        'usage': {'today': user.daily_count, 'limit': 20 if user.plan == 'free' else None}
    })

def _detect_module(text):
    """Simple keyword router."""
    text_lower = text.lower()
    gov_keys = ['иин', 'эцп', 'паспорт', 'жәрдемақы', 'egov', 'дәрігер',
                'автокөлік', 'тіркеу', 'мемлекеттік', 'қызмет']
    tutor_keys = ['тексер', 'грамматика', 'аудар', 'қате', 'сөйлем',
                  'жіктеу', 'айтылым', 'барды', 'бардым']
    det_keys = ['жасанды ма', 'ии жасады', 'анықта', 'generated', 'chatgpt жазды']

    if any(k in text_lower for k in det_keys):
        return 'det'
    if any(k in text_lower for k in gov_keys):
        return 'gov'
    if any(k in text_lower for k in tutor_keys):
        return 'tutor'
    return 'general'

# ─────────────────────────────────────
# HISTORY
# ─────────────────────────────────────
@app.route('/api/history', methods=['GET'])
@jwt_required(locations=["headers"])
def history():
    user_id = int(get_jwt_identity())
    chats = Chat.query.filter_by(user_id=user_id).order_by(Chat.created_at.desc()).limit(50).all()
    return jsonify([c.to_dict() for c in chats])

@app.route('/api/history/<int:chat_id>/messages', methods=['GET'])
@jwt_required(locations=["headers"])
def chat_messages(chat_id):
    user_id = int(get_jwt_identity())
    chat = Chat.query.filter_by(id=chat_id, user_id=user_id).first_or_404()
    msgs = Message.query.filter_by(chat_id=chat.id).order_by(Message.created_at).all()
    return jsonify([m.to_dict() for m in msgs])

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
    plan = request.json.get('plan', 'pro')
    user = User.query.get(user_id)
    user.plan = plan
    db.session.commit()
    return jsonify({'ok': True, 'plan': plan})

# ─────────────────────────────────────
# STATS
# ─────────────────────────────────────
@app.route('/api/stats', methods=['GET'])
@jwt_required(locations=["headers"])
def stats():
    user = User.query.get(int(get_jwt_identity()))
    return jsonify({
        'total_messages': user.total_messages,
        'daily_count': user.daily_count,
        'plan': user.plan,
        'member_since': user.created_at.isoformat()
    })


# ─────────────────────────────────────
# СУРЕТ ДЕТЕКТОРЫ
# ─────────────────────────────────────
@app.route('/api/detect/image', methods=['POST'])
@jwt_required(optional=True)
def detect_image():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл жоқ'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Файл таңдалмаған'}), 400
    import tempfile, os as _os
    suffix = _os.path.splitext(file.filename)[1] or '.jpg'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        result = detector.analyze_image(tmp.name)
    _os.unlink(tmp.name)
    return jsonify({'response': result, 'chat_id': None})

# ─────────────────────────────────────
# БЕЙНЕ ДЕТЕКТОРЫ
# ─────────────────────────────────────
@app.route('/api/detect/video', methods=['POST'])
@jwt_required(optional=True)
def detect_video():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл жоқ'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Файл таңдалмаған'}), 400
    import tempfile, os as _os
    suffix = _os.path.splitext(file.filename)[1] or '.mp4'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        result = detector.analyze_video(tmp.name)
    _os.unlink(tmp.name)
    return jsonify({'response': result, 'chat_id': None})

# ─────────────────────────────────────
# INIT DB + RUN
# ─────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ База деректер дайын")
    app.run(debug=True, host='0.0.0.0', port=5000)