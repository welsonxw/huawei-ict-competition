"""Session-cookie login with two roles: farmer (scans, plots) and expert (review queue, export)."""
import os
import secrets
from functools import wraps
from pathlib import Path

from flask import jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import User

ROLES = ("farmer", "expert")


def persistent_secret(path: Path) -> str:
    """Random per-install key shared by all workers, used when SECRET_KEY is not set."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_text().strip()
    key = secrets.token_hex(32)
    with os.fdopen(fd, "w") as fh:
        fh.write(key)
    return key


def create_user(username, password, role="farmer"):
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    user = User.query.filter_by(username=username).one_or_none() or User(username=username)
    user.password_hash = generate_password_hash(password)
    user.role = role
    db.session.add(user)
    db.session.commit()
    return user


def authenticate(username, password):
    user = User.query.filter_by(username=username).one_or_none()
    if user and check_password_hash(user.password_hash, password):
        return user
    return None


def current_user():
    uid = session.get("uid")
    return db.session.get(User, uid) if uid else None


def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify(error="login required"), 401
            if role and user.role != role:
                return jsonify(error=f"{role} role required"), 403
            return fn(*args, **kwargs)

        return wrapper

    return deco
