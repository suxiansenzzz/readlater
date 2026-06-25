"""
ReadLater 身份认证模块
- bcrypt 密码哈希（原生 API，兼容 bcrypt 5.x）
- JWT Token (HttpOnly Cookie)
- 登录失败锁定（带 TTL 自动清理）
- 游客模式支持
"""
from __future__ import annotations

import os
import json
import time
import secrets
import logging
import sqlite3
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

import jwt
import bcrypt
from fastapi import Request, Response, HTTPException

logger = logging.getLogger("readlater.auth")

# ==================== 配置 ====================

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULT_CONFIG = {
    "secret_key": "",       # 启动时自动生成
    "token_expire_days": 7,
    "guest_enabled": True,
    "max_login_attempts": 5,
    "lockout_minutes": 15,
    "username": "admin",
}

_config_cache: Optional[Dict] = None


def load_config() -> Dict:
    """加载配置，首次使用自动生成密钥"""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("config.json 读取失败，使用默认配置: %s", e)

    # 首次运行：生成随机密钥
    if not config["secret_key"]:
        config["secret_key"] = secrets.token_hex(32)
        save_config(config)

    _config_cache = config
    return config


def save_config(config: Dict):
    """原子写入配置（先写临时文件再 rename）"""
    global _config_cache
    try:
        dir_name = os.path.dirname(CONFIG_PATH)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, CONFIG_PATH)  # 原子替换
        # 限制文件权限（仅属主可读写）
        try:
            os.chmod(CONFIG_PATH, 0o600)
        except OSError:
            pass
        _config_cache = config
    except OSError as e:
        logger.error("config.json 写入失败: %s", e)


def update_config(updates: Dict):
    """更新部分配置"""
    config = load_config()
    config.update(updates)
    save_config(config)


# ==================== 密码哈希（bcrypt 原生 API） ====================

def hash_password(password: str) -> str:
    """bcrypt 哈希密码，返回字符串"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# ==================== JWT Token ====================

def create_token(user_id: int, username: str, role: str = "admin") -> str:
    """签发 JWT"""
    config = load_config()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(days=config["token_expire_days"]),
    }
    return jwt.encode(payload, config["secret_key"], algorithm="HS256")


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """验证并解析 JWT，失败返回 None"""
    config = load_config()
    try:
        payload = jwt.decode(token, config["secret_key"], algorithms=["HS256"])
        return {
            "user_id": int(payload["sub"]),
            "username": payload.get("username", ""),
            "role": payload.get("role", "admin"),
        }
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ==================== 登录失败锁定（带 TTL 清理） ====================

# 内存存储：{ "ip": {"attempts": N, "locked_until": ts, "created": ts} }
_login_attempts: Dict[str, Dict] = {}
_CLEANUP_INTERVAL = 600   # 10 分钟清理一次
_RECORD_TTL = 3600        # 未锁定记录 1 小时过期
_last_cleanup = 0.0


def _cleanup_expired_records():
    """清理过期的登录失败记录"""
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < _CLEANUP_INTERVAL:
        return
    _last_cleanup = now

    expired_ips = []
    for ip, record in _login_attempts.items():
        locked_until = record.get("locked_until", 0)
        created = record.get("created", 0)
        # 锁定已过期，或记录超过 TTL
        if (locked_until and now >= locked_until) or \
           (not locked_until and now - created > _RECORD_TTL):
            expired_ips.append(ip)
    for ip in expired_ips:
        _login_attempts.pop(ip, None)


def check_login_allowed(ip: str) -> tuple[bool, int]:
    """
    检查该 IP 是否允许登录
    返回 (allowed, remaining_lockout_seconds)
    """
    _cleanup_expired_records()
    record = _login_attempts.get(ip)
    if record is None:
        return True, 0

    locked_until = record.get("locked_until", 0)
    if locked_until and time.time() < locked_until:
        remaining = int(locked_until - time.time())
        return False, remaining

    # 锁定已过期
    if locked_until and time.time() >= locked_until:
        _login_attempts.pop(ip, None)
        return True, 0

    return True, 0


def record_login_failure(ip: str):
    """记录一次登录失败"""
    config = load_config()
    now = time.time()
    if ip not in _login_attempts:
        _login_attempts[ip] = {"attempts": 0, "locked_until": 0, "created": now}

    _login_attempts[ip]["attempts"] += 1

    if _login_attempts[ip]["attempts"] >= config["max_login_attempts"]:
        lockout_seconds = config["lockout_minutes"] * 60
        _login_attempts[ip]["locked_until"] = now + lockout_seconds


def clear_login_attempts(ip: str):
    """登录成功，清除失败记录"""
    _login_attempts.pop(ip, None)


# ==================== Cookie 操作 ====================

COOKIE_NAME = "rl_token"
COOKIE_PATH = "/"


def set_auth_cookie(response: Response, token: str):
    """设置认证 Cookie（HttpOnly）"""
    config = load_config()
    max_age = config["token_expire_days"] * 86400
    # 生产环境 / HTTPS 时启用 secure
    is_secure = os.getenv("READLATER_HTTPS", "").lower() in ("1", "true", "yes")
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        path=COOKIE_PATH,
        secure=is_secure,
    )


def clear_auth_cookie(response: Response):
    """清除认证 Cookie"""
    is_secure = os.getenv("READLATER_HTTPS", "").lower() in ("1", "true", "yes")
    response.delete_cookie(
        key=COOKIE_NAME,
        path=COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=is_secure,
    )


def get_token_from_request(request: Request) -> Optional[str]:
    """从请求中提取 token（Cookie 优先，Authorization 备选）"""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """从请求中解析当前用户，未认证返回 None"""
    token = get_token_from_request(request)
    if not token:
        return None
    return decode_token(token)


def require_auth(request: Request) -> Dict[str, Any]:
    """强制要求认证，未认证抛 401"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="未认证，请先登录")
    return user


def require_admin(request: Request) -> Dict[str, Any]:
    """强制要求管理员权限"""
    user = require_auth(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="权限不足")
    return user


# ==================== 数据库操作 ====================

def init_users_table(conn: sqlite3.Connection):
    """创建用户表"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'admin',
            created_at TEXT NOT NULL,
            last_login TEXT,
            login_attempts INTEGER DEFAULT 0,
            locked_until TEXT
        )
    """)
    conn.commit()


def create_user(conn: sqlite3.Connection, username: str, password: str, role: str = "admin") -> int:
    """创建用户，返回 user_id"""
    password_hash = hash_password(password)
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        (username, password_hash, role, now),
    )
    conn.commit()
    return cursor.lastrowid


def get_user_by_username(conn: sqlite3.Connection, username: str) -> Optional[Dict]:
    """根据用户名查找用户"""
    row = conn.execute(
        "SELECT id, username, password_hash, role, created_at, last_login FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "password_hash": row["password_hash"],
        "role": row["role"],
        "created_at": row["created_at"],
        "last_login": row["last_login"],
    }


def update_last_login(conn: sqlite3.Connection, user_id: int):
    """更新最后登录时间"""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, user_id))
    conn.commit()


def update_password(conn: sqlite3.Connection, user_id: int, new_password: str):
    """更新密码"""
    password_hash = hash_password(new_password)
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
    conn.commit()


def has_any_user(conn: sqlite3.Connection) -> bool:
    """检查是否存在至少一个用户"""
    row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    return row[0] > 0
