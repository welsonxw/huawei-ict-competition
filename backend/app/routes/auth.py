from flask import Blueprint, jsonify, request, session

from ..services.auth import authenticate, current_user

bp = Blueprint("auth", __name__)


@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    user = authenticate(str(data.get("username", "")).strip(), str(data.get("password", "")))
    if user is None:
        return jsonify(error="wrong username or password"), 401
    session.clear()
    session["uid"] = user.id
    return jsonify(user.to_dict())


@bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.get("/auth/me")
def me():
    user = current_user()
    return jsonify(user.to_dict() if user else None)
