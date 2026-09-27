"""Session-cookie login with two roles: farmer (scans, plots) and expert (review queue, export)."""
import os
import secrets
from functools import wraps
from pathlib import Path

from flask import jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import Plot, Scan, User

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


def can_access_plot(user, plot):
    """Experts see every plot; a farmer sees only plots they own."""
    return user is not None and plot is not None and (user.role == "expert" or plot.owner_id == user.id)


def can_access_scan(user, scan):
    if user is None or scan is None:
        return False
    if user.role == "expert" or scan.user_id == user.id:
        return True
    return scan.plot is not None and scan.plot.owner_id == user.id


def visible_plots(user):
    q = Plot.query
    return q if user.role == "expert" else q.filter(Plot.owner_id == user.id)


def visible_scans(user):
    q = Scan.query
    if user.role == "expert":
        return q
    owned = db.session.query(Plot.id).filter(Plot.owner_id == user.id)
    return q.filter(db.or_(Scan.user_id == user.id, Scan.plot_id.in_(owned)))
