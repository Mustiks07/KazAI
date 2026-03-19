from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(100), nullable=False)
    email          = db.Column(db.String(120), unique=True, nullable=False)
    password_hash  = db.Column(db.String(256))
    plan           = db.Column(db.String(20), default='free')  # free | pro | ultra
    total_messages = db.Column(db.Integer, default=0)
    daily_count    = db.Column(db.Integer, default=0)
    last_reset     = db.Column(db.Date, default=date.today)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    chats = db.relationship('Chat', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def reset_daily_if_needed(self):
        """Reset daily counter if it's a new day."""
        today = date.today()
        if self.last_reset != today:
            self.daily_count = 0
            self.last_reset = today
            db.session.commit()

    def to_dict(self):
        self.reset_daily_if_needed()
        return {
            'id':             self.id,
            'name':           self.name,
            'email':          self.email,
            'plan':           self.plan,
            'total_messages': self.total_messages,
            'daily_count':    self.daily_count,
            'daily_limit':    20 if self.plan == 'free' else None,
            'created_at':     self.created_at.isoformat()
        }


class Chat(db.Model):
    __tablename__ = 'chats'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title      = db.Column(db.String(200), default='Жаңа чат')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = db.relationship('Message', backref='chat', lazy=True)

    def to_dict(self):
        return {
            'id':         self.id,
            'title':      self.title,
            'created_at': self.created_at.isoformat(),
            'msg_count':  len(self.messages)
        }


class Message(db.Model):
    __tablename__ = 'messages'

    id         = db.Column(db.Integer, primary_key=True)
    chat_id    = db.Column(db.Integer, db.ForeignKey('chats.id'), nullable=False)
    role       = db.Column(db.String(20))   # user | assistant
    content    = db.Column(db.Text)
    module     = db.Column(db.String(20))   # gov | tutor | det | general
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':         self.id,
            'role':       self.role,
            'content':    self.content,
            'module':     self.module,
            'created_at': self.created_at.isoformat()
        }
