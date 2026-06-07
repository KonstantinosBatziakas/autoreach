"""
AutoReach Authentication Module
================================
Handles:
  - Email + password register / login
  - OAuth2 for GitHub, Discord, Google
      → exchange code on the backend, never expose client_secret to the app
      → on success: redirect to  autoreach://callback?token=<JWT>
      → on failure: redirect to  autoreach://callback?error=<message>

Required environment variables (set in Render → Environment):
  SECRET_KEY          – random 32-byte hex string, used to sign JWTs
  GITHUB_CLIENT_ID
  GITHUB_CLIENT_SECRET
  DISCORD_CLIENT_ID
  DISCORD_CLIENT_SECRET
  GOOGLE_CLIENT_ID
  GOOGLE_CLIENT_SECRET
  BASE_URL            – your public URL, e.g. https://app.autoreach.dev
"""

import os
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
import requests as req_lib
from flask import Blueprint, request, jsonify, redirect
from db import get_db, init_db

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')
BASE_URL   = os.getenv('BASE_URL', 'https://app.autoreach.dev')

GITHUB_CLIENT_ID     = os.getenv('GITHUB_CLIENT_ID', '')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET', '')
DISCORD_CLIENT_ID     = os.getenv('DISCORD_CLIENT_ID', '')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET', '')
GOOGLE_CLIENT_ID     = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')

FLUTTER_SCHEME = 'autoreach://callback'

# ── JWT helpers ───────────────────────────────────────────────────────────────
def make_jwt(user_id: int, email: str, name: str) -> str:
    payload = {
        'sub': user_id,
        'email': email,
        'name': name,
        'iat': datetime.now(timezone.utc),
        'exp': datetime.now(timezone.utc) + timedelta(days=30),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except jwt.PyJWTError:
        return None

def jwt_required(f):
    """Decorator for Flask routes that need a valid JWT."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing token'}), 401
        payload = verify_jwt(auth_header[7:])
        if payload is None:
            return jsonify({'error': 'Invalid or expired token'}), 401
        request.user = payload
        return f(*args, **kwargs)
    return decorated

# ── Password helpers ──────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260_000)
    return f"{salt}${h.hex()}"

def check_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split('$')
        expected = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260_000)
        return hmac.compare_digest(h, expected.hex())
    except Exception:
        return False

# ── OAuth state helpers ───────────────────────────────────────────────────────
def new_state(provider: str) -> str:
    state = secrets.token_urlsafe(32)
    db = get_db()
    db.execute("DELETE FROM oauth_state WHERE created_at < datetime('now', '-10 minutes')")
    db.execute("INSERT INTO oauth_state (state, provider) VALUES (?, ?)", (state, provider))
    db.commit()
    db.close()
    return state

def consume_state(state: str) -> str | None:
    """Returns the provider if state is valid, else None. Deletes it."""
    db = get_db()
    row = db.execute(
        "SELECT provider FROM oauth_state WHERE state = ? AND created_at > datetime('now', '-10 minutes')",
        (state,)
    ).fetchone()
    if row:
        db.execute("DELETE FROM oauth_state WHERE state = ?", (state,))
        db.commit()
        db.close()
        return row['provider']
    db.close()
    return None

def upsert_user(provider, provider_id, email=None, name=None, avatar_url=None):
    db = get_db()
    db.execute("""
        INSERT INTO users (provider, provider_id, email, name, avatar_url)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(provider, provider_id) DO UPDATE SET
            email      = excluded.email,
            name       = excluded.name,
            avatar_url = excluded.avatar_url
    """, (provider, str(provider_id), email, name, avatar_url))
    db.commit()
    user = db.execute(
        "SELECT * FROM users WHERE provider = ? AND provider_id = ?",
        (provider, str(provider_id))
    ).fetchone()
    db.close()
    return user

# ── Email + Password ──────────────────────────────────────────────────────────
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    email    = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    name     = (data.get('name') or email.split('@')[0]).strip()

    if not email or '@' not in email:
        return jsonify({'error': 'Valid email required'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM users WHERE provider = 'email' AND provider_id = ?", (email,)
    ).fetchone()
    if existing:
        db.close()
        return jsonify({'error': 'Account already exists — please log in'}), 409

    db.execute("""
        INSERT INTO users (provider, provider_id, email, name, password_hash)
        VALUES ('email', ?, ?, ?, ?)
    """, (email, email, name, hash_password(password)))
    db.commit()
    user = db.execute(
        "SELECT * FROM users WHERE provider = 'email' AND provider_id = ?", (email,)
    ).fetchone()
    db.close()

    token = make_jwt(user['id'], user['email'], user['name'])
    return jsonify({'token': token, 'user': {'id': user['id'], 'email': email, 'name': name}}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email    = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE provider = 'email' AND provider_id = ?", (email,)
    ).fetchone()
    db.close()

    if not user or not check_password(password, user['password_hash'] or ''):
        return jsonify({'error': 'Invalid email or password'}), 401

    token = make_jwt(user['id'], user['email'], user['name'])
    return jsonify({'token': token, 'user': {'id': user['id'], 'email': user['email'], 'name': user['name']}})

# ── GitHub OAuth ──────────────────────────────────────────────────────────────
@auth_bp.route('/github')
def github_start():
    state = new_state('github')
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={BASE_URL}/auth/github/callback"
        f"&scope=user:email"
        f"&state={state}"
    )
    return redirect(url)

@auth_bp.route('/github/callback')
def github_callback():
    code  = request.args.get('code')
    state = request.args.get('state')

    if not consume_state(state):
        return redirect(f"{FLUTTER_SCHEME}?error=invalid_state")

    # Exchange code for access token
    resp = req_lib.post(
        'https://github.com/login/oauth/access_token',
        headers={'Accept': 'application/json'},
        json={'client_id': GITHUB_CLIENT_ID, 'client_secret': GITHUB_CLIENT_SECRET,
              'code': code, 'redirect_uri': f"{BASE_URL}/auth/github/callback"},
        timeout=10
    )
    access_token = resp.json().get('access_token')
    if not access_token:
        return redirect(f"{FLUTTER_SCHEME}?error=github_token_failed")

    # Get user info
    headers = {'Authorization': f'token {access_token}', 'Accept': 'application/json'}
    user_resp  = req_lib.get('https://api.github.com/user', headers=headers, timeout=10).json()
    email_resp = req_lib.get('https://api.github.com/user/emails', headers=headers, timeout=10).json()

    email = next((e['email'] for e in email_resp if e.get('primary') and e.get('verified')), None)
    if not email:
        email = user_resp.get('email')

    user = upsert_user(
        provider='github',
        provider_id=user_resp['id'],
        email=email,
        name=user_resp.get('name') or user_resp.get('login'),
        avatar_url=user_resp.get('avatar_url'),
    )
    token = make_jwt(user['id'], user['email'] or '', user['name'] or '')
    return redirect(f"{FLUTTER_SCHEME}?token={token}")

# ── Discord OAuth ─────────────────────────────────────────────────────────────
@auth_bp.route('/discord')
def discord_start():
    state = new_state('discord')
    url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={BASE_URL}/auth/discord/callback"
        f"&response_type=code"
        f"&scope=identify+email"
        f"&state={state}"
    )
    return redirect(url)

@auth_bp.route('/discord/callback')
def discord_callback():
    code  = request.args.get('code')
    state = request.args.get('state')

    if not consume_state(state):
        return redirect(f"{FLUTTER_SCHEME}?error=invalid_state")

    resp = req_lib.post(
        'https://discord.com/api/oauth2/token',
        data={
            'client_id': DISCORD_CLIENT_ID,
            'client_secret': DISCORD_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': f"{BASE_URL}/auth/discord/callback",
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=10
    )
    access_token = resp.json().get('access_token')
    if not access_token:
        return redirect(f"{FLUTTER_SCHEME}?error=discord_token_failed")

    user_resp = req_lib.get(
        'https://discord.com/api/users/@me',
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=10
    ).json()

    avatar_hash = user_resp.get('avatar')
    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{user_resp['id']}/{avatar_hash}.png"
        if avatar_hash else None
    )
    user = upsert_user(
        provider='discord',
        provider_id=user_resp['id'],
        email=user_resp.get('email'),
        name=user_resp.get('global_name') or user_resp.get('username'),
        avatar_url=avatar_url,
    )
    token = make_jwt(user['id'], user['email'] or '', user['name'] or '')
    return redirect(f"{FLUTTER_SCHEME}?token={token}")

# ── Google OAuth ──────────────────────────────────────────────────────────────
@auth_bp.route('/google')
def google_start():
    state = new_state('google')
    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={BASE_URL}/auth/google/callback"
        f"&response_type=code"
        f"&scope=openid+email+profile"
        f"&state={state}"
        f"&access_type=offline"
    )
    return redirect(url)

@auth_bp.route('/google/callback')
def google_callback():
    code  = request.args.get('code')
    state = request.args.get('state')

    if not consume_state(state):
        return redirect(f"{FLUTTER_SCHEME}?error=invalid_state")

    resp = req_lib.post(
        'https://oauth2.googleapis.com/token',
        json={
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': f"{BASE_URL}/auth/google/callback",
        },
        timeout=10
    )
    data = resp.json()
    access_token = data.get('access_token')
    if not access_token:
        return redirect(f"{FLUTTER_SCHEME}?error=google_token_failed")

    user_resp = req_lib.get(
        'https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=10
    ).json()

    user = upsert_user(
        provider='google',
        provider_id=user_resp['id'],
        email=user_resp.get('email'),
        name=user_resp.get('name'),
        avatar_url=user_resp.get('picture'),
    )
    token = make_jwt(user['id'], user['email'] or '', user['name'] or '')
    return redirect(f"{FLUTTER_SCHEME}?token={token}")

# ── Token verify (Flutter calls this to validate stored JWT) ──────────────────
@auth_bp.route('/me')
@jwt_required
def me():
    return jsonify(request.user)

# ── Init DB on import ─────────────────────────────────────────────────────────
# init_db() is called from app.py on startup via db.init_db()
# No need to call it again here.
