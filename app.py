import json
import os
import random
import smtplib
import threading
import uuid
from datetime import date, datetime, time, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, make_response, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "")
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if not SECRET_KEY:
    if DEBUG_MODE:
        SECRET_KEY = "dev-only-insecure-key-do-not-use-in-prod"
    else:
        raise RuntimeError("FLASK_SECRET_KEY obligatoire en production (.env)")

app = Flask(__name__)
app.secret_key = SECRET_KEY
_session_secure = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="None" if ALLOWED_ORIGINS else "Lax",
    SESSION_COOKIE_SECURE=True if ALLOWED_ORIGINS else _session_secure,
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    MAX_CONTENT_LENGTH=512 * 1024,
)

if ALLOWED_ORIGINS:
    pass  # cross-origin : cookies Secure + SameSite=None déjà appliqués


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin and origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, OPTIONS"
    return response


@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        origin = request.headers.get("Origin")
        if origin and origin in ALLOWED_ORIGINS:
            resp = make_response("", 204)
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, OPTIONS"
            return resp
        return "", 204

DATA_FILE = BASE_DIR / "data.json"
_data_lock = threading.Lock()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
LOCAL_IP = os.getenv("LOCAL_IP", "127.0.0.1")
APP_URL = os.getenv("APP_URL", f"http://{LOCAL_IP}:{PORT}")
RESET_HOUR = int(os.getenv("RESET_HOUR", "14"))
VOTE_OPEN_HOUR = int(os.getenv("VOTE_OPEN_HOUR", "9"))

FOODS = [
    {"id": "pancakes", "name": "Pancakes", "emoji": "🥞", "rare": False, "weight": 12},
    {"id": "crepe", "name": "Crêpes", "emoji": "🫓", "rare": False, "weight": 12},
    {"id": "gateau", "name": "Gâteau", "emoji": "🎂", "rare": False, "weight": 12},
    {"id": "cookies", "name": "Cookies", "emoji": "🍪", "rare": False, "weight": 12},
    {"id": "brownies", "name": "Brownies", "emoji": "🍫", "rare": False, "weight": 12},
    {"id": "muffins", "name": "Muffins", "emoji": "🧁", "rare": False, "weight": 12},
    {"id": "cupcake", "name": "Cupcake", "emoji": "🧁", "rare": False, "weight": 12},
    {"id": "madeleine", "name": "Madeleine", "emoji": "🍰", "rare": False, "weight": 12},
    {"id": "cheesecake", "name": "Cheesecake", "emoji": "🧀", "rare": True, "weight": 3},
    {"id": "tiramisu", "name": "Tiramisu", "emoji": "☕", "rare": True, "weight": 3},
    {"id": "cinnamon_roll", "name": "Cinnamon roll", "emoji": "🌀", "rare": True, "weight": 3},
]

APP_NAME = "Team DRC"

PERSONS = ["jade", "david", "thibault", "lorenzo"]
PERSON_NAMES = {
    "jade": "Jade",
    "david": "David",
    "thibault": "Thibault",
    "lorenzo": "Lolo",
}

NICKNAMES = {
    "jade": "Radé",
    "david": "Davee",
    "thibault": "riz souflée",
    "lorenzo": "lolo",
}

DEFAULT_EMAILS = {
    "jade": "forlinijade@gmail.com",
    "thibault": "thibault@teamdrc.fr",
    "david": "david.fanti@free.fr",
    "lorenzo": "fortinilorenzo40@gmail.com",
}

DEFAULT_AVATARS = {
    "jade": {"emoji": "🌸", "bg": "#ff6b6b", "bg2": "#c92a2a", "border": "#ff8787", "role": "Le feu au cul", "photo": "/avatars/jade.png"},
    "david": {"emoji": "🎯", "bg": "#ffe66d", "bg2": "#f59f00", "border": "#ffd43b", "role": "Le café en IV", "photo": "/avatars/david.png"},
    "thibault": {"emoji": "⚡", "bg": "#4ecdc4", "bg2": "#087f5b", "border": "#63e6be", "role": "Croustillant garanti", "photo": "/avatars/thibault.png"},
    "lorenzo": {"emoji": "👑", "bg": "#a78bfa", "bg2": "#7048e8", "border": "#b197fc", "role": "Le boss du tupperware", "photo": "/avatars/lorenzo.png"},
}

DEFAULT_PINS = {
    "jade": "4827",
    "thibault": "9153",
    "david": "6374",
    "lorenzo": "2846",
}

ANCHOR_DATE = date(2026, 6, 23)  # mardi — lolo
ANCHOR_INDEX = 3  # → 30/06 Jade, 07/07 David, 14/07 Thibault


def migrate_legacy_ids(data: dict) -> dict:
    """Renomme davide → david dans les données existantes."""
    renames = {"davide": "david"}

    for old, new in renames.items():
        for section in ("accounts", "emails", "avatars"):
            bucket = data.get(section, {})
            if old in bucket and new not in bucket:
                bucket[new] = bucket.pop(old)

        for draw in data.get("roulette_draws", {}).values():
            if draw.get("spun_by") == old:
                draw["spun_by"] = new

        for session in data.get("rating_sessions", {}).values():
            if session.get("baker_id") == old:
                session["baker_id"] = new
            votes = session.get("votes", {})
            if old in votes:
                votes[new] = votes.pop(old)

    return data


def ensure_defaults(data):
    data = migrate_legacy_ids(data)
    accounts = data.setdefault("accounts", {})
    for pid in PERSONS:
        acc = accounts.setdefault(pid, {})
        acc.setdefault("email", DEFAULT_EMAILS[pid])
        if pid in DEFAULT_PINS and not acc.get("pin_hash"):
            acc["pin_hash"] = generate_password_hash(DEFAULT_PINS[pid])
            acc.setdefault("created_at", datetime.now().isoformat())
    emails = data.setdefault("emails", {})
    for pid, addr in DEFAULT_EMAILS.items():
        emails.setdefault(pid, addr)
    for pid in ("jade", "david"):
        addr = DEFAULT_EMAILS[pid]
        accounts.setdefault(pid, {})["email"] = addr
        emails[pid] = addr
    return data


def load_data():
    with _data_lock:
        if DATA_FILE.exists():
            with open(DATA_FILE, encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
    data.setdefault("roulette_draws", {})
    data.setdefault("messages", [])
    data.setdefault("notifications", {})
    data.setdefault("rating_sessions", {})
    data.setdefault("food_averages", {})
    return ensure_defaults(data)


def save_data(data):
    with _data_lock:
        tmp = DATA_FILE.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(DATA_FILE)


def get_tuesday_index(d: date) -> int:
    anchor = ANCHOR_DATE
    diff_weeks = round((d - anchor).days / 7)
    return (ANCHOR_INDEX + diff_weeks) % len(PERSONS)


def person_for_tuesday(d: date) -> str:
    return PERSONS[get_tuesday_index(d)]


def get_period_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now()
    today = now.date()
    days_since_tue = (today.weekday() - 1) % 7
    this_tuesday = today - timedelta(days=days_since_tue)
    period = datetime.combine(this_tuesday, time(RESET_HOUR, 0))
    if now >= period:
        return period
    return datetime.combine(this_tuesday - timedelta(days=7), time(RESET_HOUR, 0))


def get_next_reset(now: datetime | None = None) -> datetime:
    now = now or datetime.now()
    period = get_period_start(now)
    return period + timedelta(days=7)


def get_target_tuesday(period_start: datetime) -> date:
    return period_start.date() + timedelta(days=7)


def period_key(period_start: datetime) -> str:
    return period_start.isoformat()


def weighted_food_pick():
    pool = []
    for food in FOODS:
        pool.extend([food] * food["weight"])
    chosen = random.choice(pool)
    return {
        "id": chosen["id"],
        "name": chosen["name"],
        "emoji": chosen["emoji"],
        "rare": chosen["rare"],
    }


def display_name(person_id: str) -> str:
    return NICKNAMES.get(person_id, PERSON_NAMES.get(person_id, person_id))


def is_valid_draw(draw: dict | None) -> bool:
    """Un tirage n'est valide que si le responsable du mardi cible l'a effectué."""
    if not draw or not draw.get("target_tuesday"):
        return False
    target = date.fromisoformat(draw["target_tuesday"])
    return draw.get("spun_by") == person_for_tuesday(target)


def find_draw_for_tuesday(target: date) -> dict | None:
    data = load_data()
    target_iso = target.isoformat()
    for draw in data.get("roulette_draws", {}).values():
        if draw.get("target_tuesday") == target_iso and is_valid_draw(draw):
            return draw
    return None


def get_today_rating_session(create_if_missing: bool = False) -> dict | None:
    window = vote_window_status()
    if not window.get("open"):
        return None

    today = date.today()
    baker = person_for_tuesday(today)
    draw = find_draw_for_tuesday(today)
    if not draw:
        return None
    food = draw["food"]

    data = load_data()
    sessions = data.setdefault("rating_sessions", {})
    key = today.isoformat()

    if key not in sessions and create_if_missing:
        sessions[key] = {
            "tuesday": key,
            "baker_id": baker,
            "baker_name": display_name(baker),
            "food": food,
            "votes": {},
            "average": None,
            "completed": False,
            "results_email_sent": False,
            "created_at": datetime.now().isoformat(),
        }
        save_data(data)

    return sessions.get(key)


def vote_window_status(now: datetime | None = None) -> dict:
    now = now or datetime.now()
    today = now.date()
    opens_at = datetime.combine(today, time(VOTE_OPEN_HOUR, 0))

    if today.weekday() != 1:
        return {"open": False, "reason": "not_tuesday"}

    draw = find_draw_for_tuesday(today)
    if not draw:
        return {"open": False, "reason": "no_draw", "food": None}

    if now < opens_at:
        return {
            "open": False,
            "reason": "too_early",
            "opens_at": opens_at.isoformat(),
            "food": draw["food"],
            "baker": display_name(person_for_tuesday(today)),
        }

    return {
        "open": True,
        "opens_at": opens_at.isoformat(),
        "food": draw["food"],
        "baker": display_name(person_for_tuesday(today)),
    }


def check_and_open_voting():
    window = vote_window_status()
    if not window.get("open"):
        return

    today = date.today()
    key = today.isoformat()
    get_today_rating_session(create_if_missing=True)

    data = load_data()
    notifs = data.setdefault("notifications", {})
    notify_key = f"vote_open_{key}"
    if notifs.get(notify_key):
        return

    food = window["food"]
    baker = window["baker"]
    food_label = f"{food['emoji']} {food['name']}"
    tuesday_str = today.strftime("%d/%m")
    subject = f"⭐ {APP_NAME} — C'est l'heure de noter !"
    plain = (
        f"Les votes sont ouverts pour le plat du mardi {tuesday_str}.\n"
        f"{food_label} par {baker}\n"
        f"Connecte-toi et note de 1 à 10 sur l'app."
    )
    html = email_layout(
        "⭐ Vote ouvert",
        "🍽️",
        f"<p>Le mardi <strong>{tuesday_str}</strong>, c'est l'heure de noter le plat !</p>"
        f'<div style="text-align:center;margin:20px 0;padding:16px;background:#242336;border-radius:12px">'
        f'<div style="font-size:32px">{food["emoji"]}</div>'
        f'<div style="font-size:18px;font-weight:700;margin-top:8px">{food["name"]}</div>'
        f'<div style="color:#94a1b2;margin-top:4px">par {baker}</div></div>'
        f"<p>Connecte-toi sur l'app et donne une note de <strong>1 à 10</strong>. "
        f"Le chef ne vote pas — les 3 autres suffisent.</p>",
    )
    notify_all(plain, subject=subject, html=html)
    notifs[notify_key] = datetime.now().isoformat()
    save_data(data)


def finalize_rating_if_ready(session_key: str) -> dict | None:
    data = load_data()
    session = data.get("rating_sessions", {}).get(session_key)
    if not session or session.get("completed"):
        return session

    baker = session["baker_id"]
    voters_needed = [p for p in PERSONS if p != baker]
    votes = session.get("votes", {})
    if not all(v in votes for v in voters_needed):
        return session

    avg = sum(votes[v] for v in voters_needed) / len(voters_needed)
    session["average"] = round(avg, 1)
    session["completed"] = True
    session["completed_at"] = datetime.now().isoformat()

    food_id = session["food"]["id"]
    fa = data.setdefault("food_averages", {})
    stat = fa.setdefault(
        food_id,
        {
            "name": session["food"]["name"],
            "emoji": session["food"]["emoji"],
            "total": 0.0,
            "sessions": 0,
            "average": None,
        },
    )
    stat["total"] = round(stat["total"] + session["average"], 2)
    stat["sessions"] += 1
    stat["average"] = round(stat["total"] / stat["sessions"], 1)

    if not session.get("results_email_sent"):
        food = session["food"]
        lines_plain = [f"  · {display_name(v)} : {votes[v]}/10" for v in voters_needed]
        lines_html = "".join(
            f'<tr><td style="padding:6px 0;color:#94a1b2">{display_name(v)}</td>'
            f'<td style="padding:6px 0;text-align:right;font-weight:700">{votes[v]}/10</td></tr>'
            for v in voters_needed
        )
        tuesday_str = session["tuesday"]
        avg = session["average"]
        subject = f"⭐ {APP_NAME} — {avg}/10 pour {food['name']}"
        plain = (
            f"Notes du mardi {tuesday_str}\n\n"
            f"Plat : {food['emoji']} {food['name']}\n"
            f"Par : {session['baker_name']}\n"
            f"Moyenne : {avg}/10\n\n"
            f"Détail :\n" + "\n".join(lines_plain)
        )
        html = email_layout(
            f"Moyenne : {avg}/10",
            food["emoji"],
            f"<p>Résultat des votes pour le mardi <strong>{tuesday_str}</strong></p>"
            f'<div style="text-align:center;margin:16px 0;padding:16px;background:#242336;border-radius:12px">'
            f'<div style="font-size:36px">{food["emoji"]}</div>'
            f'<div style="font-size:20px;font-weight:800;margin-top:8px">{food["name"]}</div>'
            f'<div style="color:#94a1b2;margin-top:4px">par {session["baker_name"]}</div>'
            f'<div style="font-size:28px;font-weight:800;color:#ff8906;margin-top:12px">{avg}/10</div></div>'
            f'<table width="100%" style="margin-top:12px">{lines_html}</table>',
        )
        notify_all(plain, subject=subject, html=html)
        session["results_email_sent"] = True

    save_data(data)
    return session


def rating_status_for_user(user_id: str | None) -> dict:
    check_and_open_voting()
    window = vote_window_status()
    data = load_data()
    food_averages = data.get("food_averages", {})

    if not window.get("open"):
        base = {"active": False, "food_averages": food_averages, "vote_window": window}
        if window.get("reason") == "too_early" and window.get("food"):
            base["pending"] = True
            base["opens_at"] = window["opens_at"]
            base["preview"] = {"food": window["food"], "baker": window.get("baker")}
        return base

    session = get_today_rating_session()
    if not session:
        return {"active": False, "food_averages": food_averages, "vote_window": window}

    baker = session["baker_id"]
    votes = session.get("votes", {})
    voters_needed = [p for p in PERSONS if p != baker]
    can_vote = bool(
        user_id
        and user_id != baker
        and not session.get("completed")
        and user_id not in votes
    )

    return {
        "active": True,
        "vote_window": window,
        "session": {
            **session,
            "votes_detail": {display_name(k): v for k, v in votes.items()},
            "voters_needed": [display_name(p) for p in voters_needed],
            "votes_count": len(votes),
            "votes_total": len(voters_needed),
        },
        "can_vote": can_vote,
        "has_voted": bool(user_id and user_id in votes),
        "is_baker": user_id == baker if user_id else False,
        "food_averages": food_averages,
    }


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Connecte-toi d'abord"}), 401
        return f(*args, **kwargs)
    return wrapper


def get_account(person_id: str):
    data = load_data()
    return data.get("accounts", {}).get(person_id)


def add_system_message(text: str):
    data = load_data()
    msg = {
        "id": str(uuid.uuid4()),
        "author": "system",
        "text": text,
        "ts": datetime.now().isoformat(),
    }
    messages = data.setdefault("messages", [])
    messages.append(msg)
    data["messages"] = messages[-200:]
    save_data(data)
    return msg


def email_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD and EMAIL_FROM)


def get_emails() -> dict[str, str]:
    data = load_data()
    result = {}
    for pid in PERSONS:
        acc = data.get("accounts", {}).get(pid, {})
        email = (acc.get("email") or data.get("emails", {}).get(pid) or DEFAULT_EMAILS.get(pid, "")).strip().lower()
        if email and "@" in email:
            result[pid] = email
    return result


def authenticate_pin(pin: str) -> str | None:
    data = load_data()
    for pid in PERSONS:
        acc = data.get("accounts", {}).get(pid, {})
        pin_hash = acc.get("pin_hash")
        if pin_hash and check_password_hash(pin_hash, pin):
            return pid
    return None


def email_layout(title: str, emoji: str, body_html: str) -> str:
    app_url = APP_URL
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f0e17;font-family:'Segoe UI',Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0f0e17;padding:28px 14px">
<tr><td align="center">
<table role="presentation" width="100%" style="max-width:440px;background:#1a1926;border-radius:18px;border:1px solid rgba(255,255,255,0.08);overflow:hidden">
<tr><td style="background:linear-gradient(135deg,#ff8906 0%,#e53170 100%);padding:28px 20px;text-align:center">
<div style="font-size:42px;line-height:1">{emoji}</div>
<h1 style="margin:10px 0 0;color:#fffffe;font-size:22px;font-weight:800;letter-spacing:-0.02em">{title}</h1>
<div style="color:rgba(255,255,255,0.85);font-size:13px;margin-top:6px;font-weight:600">{APP_NAME}</div>
</td></tr>
<tr><td style="padding:26px 22px;color:#fffffe;font-size:15px;line-height:1.65">{body_html}</td></tr>
<tr><td style="padding:18px 22px 22px;background:#242336;text-align:center">
<a href="{app_url}" style="display:inline-block;background:#ff8906;color:#000;text-decoration:none;font-weight:800;font-size:14px;padding:12px 28px;border-radius:10px">Ouvrir l'app →</a>
<p style="margin:14px 0 0;color:#94a1b2;font-size:11px">Team DRC · Radé · Davee · riz souflée · lolo</p>
</td></tr>
</table>
</td></tr></table>
</body></html>"""


def send_email(to: str, subject: str, body: str, html: str | None = None) -> dict:
    if not email_configured():
        return {"ok": False, "error": "Email non configuré — remplis le fichier .env"}
    if not to or "@" not in to:
        return {"ok": False, "error": "Email invalide"}

    try:
        if html:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(body, "plain", "utf-8"))
            msg.attach(MIMEText(html, "html", "utf-8"))
        else:
            msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = to

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, [to], msg.as_string())

        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def broadcast_email(subject: str, body: str, html: str | None = None) -> list[dict]:
    results = []
    for pid, email in get_emails().items():
        r = send_email(email, subject, body, html=html)
        r["person"] = display_name(pid)
        results.append(r)
    return results


def notify_all(text: str, subject: str | None = None, html: str | None = None) -> list[dict]:
    if subject is None:
        subject = f"🍽️ {APP_NAME}"
    return broadcast_email(subject, text, html=html)


def check_and_send_reminders():
    data = load_data()
    now = datetime.now()
    period = get_period_start(now)
    key = period_key(period)
    target = get_target_tuesday(period)
    responsible = person_for_tuesday(target)
    draws = data.setdefault("roulette_draws", {})
    draw = draws.get(key)
    notifs = data.setdefault("notifications", {})

    if draw:
        return

    reminder_key = f"reminder_{key}"
    if not notifs.get(reminder_key) and now >= period:
        name = display_name(responsible)
        target_str = target.strftime("%d/%m")
        subject = f"🎰 {APP_NAME} — C'est l'heure de tirer !"
        plain = (
            f"C'est l'heure ! {name} doit tirer la roulette avant le mardi {target_str}.\n"
            f"C'est toi qui ramèneras ce qui sera tiré !"
        )
        html = email_layout(
            "Tire la roulette !",
            "🎰",
            f"<p><strong>{name}</strong>, c'est à toi de tirer la roulette !</p>"
            f'<p>Le plat tiré sera à ramener le mardi <strong>{target_str}</strong>.</p>'
            f"<p>Connecte-toi sur l'app et lance le tirage avant le deadline.</p>",
        )
        add_system_message(plain.replace("\n", " · "))
        notify_all(plain, subject=subject, html=html)
        notifs[reminder_key] = datetime.now().isoformat()
        save_data(data)


def get_roulette_status():
    check_and_send_reminders()
    data = load_data()
    now = datetime.now()
    period = get_period_start(now)
    key = period_key(period)
    target = get_target_tuesday(period)
    responsible = person_for_tuesday(target)
    raw_draw = data.get("roulette_draws", {}).get(key)
    draw = raw_draw if is_valid_draw(raw_draw) else None
    user_id = session.get("user_id")

    can_spin = draw is None

    return {
        "period_start": period.isoformat(),
        "next_reset": get_next_reset(now).isoformat(),
        "target_tuesday": target.isoformat(),
        "responsible": responsible,
        "responsible_name": display_name(responsible),
        "responsible_nickname": display_name(responsible),
        "draw": draw,
        "is_spun": draw is not None,
        "can_spin": can_spin,
        "window_open": now >= period,
        "logged_in": user_id,
        "logged_in_name": display_name(user_id) if user_id else None,
        "reset_hour": RESET_HOUR,
        "all_foods": FOODS,
    }


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api/auth/setup", methods=["POST"])
def auth_setup():
    body = request.get_json(silent=True) or {}
    person_id = body.get("person_id", "").strip()
    pin = body.get("pin", "").strip()

    if person_id not in PERSONS:
        return jsonify({"error": "Personne inconnue"}), 400
    if not pin or len(pin) < 4:
        return jsonify({"error": "PIN min 4 caractères"}), 400

    data = load_data()
    accounts = data.setdefault("accounts", {})
    acc = accounts.get(person_id, {})
    if acc.get("pin_hash"):
        return jsonify({"error": "Compte déjà créé, connecte-toi"}), 400

    accounts[person_id] = {
        "pin_hash": generate_password_hash(pin),
        "email": acc.get("email") or DEFAULT_EMAILS.get(person_id, ""),
        "created_at": acc.get("created_at") or datetime.now().isoformat(),
    }
    save_data(data)
    session["user_id"] = person_id
    return jsonify({"ok": True, "user_id": person_id, "name": display_name(person_id), "nickname": display_name(person_id)})


def send_welcome_pin_emails():
    """Envoie une fois le PIN à chaque membre par email."""
    data = load_data()
    notifs = data.setdefault("notifications", {})
    if notifs.get("pins_emailed"):
        return []
    if not email_configured():
        print("   PINs  → ⚠️  email non configuré")
        return []

    results = []
    for pid in PERSONS:
        pin = DEFAULT_PINS[pid]
        email = get_emails().get(pid)
        if not email:
            continue
        name = display_name(pid)
        subject = f"🔐 {APP_NAME} — Ton code de connexion"
        plain = (
            f"Salut {name},\n\n"
            f"Ton code PIN Team DRC : {pin}\n\n"
            f"Connecte-toi sur {APP_URL}\n"
            f"Entre ce code à 4 chiffres — on te reconnaît automatiquement.\n\n"
            f"— {APP_NAME}"
        )
        html = email_layout(
            f"Salut {name} !",
            "🔐",
            f"<p>Voici ton code PIN personnel :</p>"
            f'<div style="text-align:center;margin:20px 0;padding:20px;background:#242336;border-radius:12px;'
            f'font-size:36px;font-weight:800;letter-spacing:0.3em;color:#ff8906">{pin}</div>'
            f"<p>Entre ces 4 chiffres sur l'app — on te reconnaît automatiquement.</p>",
        )
        results.append(send_email(email, subject, plain, html=html))

    if any(r.get("ok") for r in results):
        notifs["pins_emailed"] = datetime.now().isoformat()
        save_data(data)
        ok = sum(1 for r in results if r.get("ok"))
        print(f"   PINs  → ✅ envoyés par email ({ok}/{len(results)})")
    else:
        print("   PINs  → ⚠️  échec envoi email")
    return results


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    body = request.get_json(silent=True) or {}
    pin = body.get("pin", "").strip()

    if not pin or len(pin) != 4 or not pin.isdigit():
        return jsonify({"error": "Code à 4 chiffres"}), 400

    person_id = authenticate_pin(pin)
    if not person_id:
        return jsonify({"error": "Code incorrect"}), 401

    session.permanent = True
    session["user_id"] = person_id
    return jsonify({"ok": True, "user_id": person_id, "name": display_name(person_id), "nickname": display_name(person_id)})


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.pop("user_id", None)
    return jsonify({"ok": True})


@app.route("/api/auth/me")
def auth_me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({
            "logged_in": False,
            "accounts_status": _accounts_status(),
            "email": get_email_status(public=True),
        })

    data = load_data()
    acc = data.get("accounts", {}).get(user_id, {})
    return jsonify({
        "logged_in": True,
        "user_id": user_id,
        "name": display_name(user_id),
        "nickname": display_name(user_id),
        "accounts_status": _accounts_status(),
        "user_email": acc.get("email") or DEFAULT_EMAILS.get(user_id, ""),
        "photo": DEFAULT_AVATARS.get(user_id, {}).get("photo"),
        "emoji": DEFAULT_AVATARS.get(user_id, {}).get("emoji", "👤"),
        "email": get_email_status(),
    })


def _accounts_status():
    data = load_data()
    return {pid: pid in data.get("accounts", {}) and bool(data["accounts"][pid].get("pin_hash")) for pid in PERSONS}


@app.route("/api/auth/pin", methods=["PUT"])
@login_required
def auth_change_pin():
    body = request.get_json(silent=True) or {}
    old_pin = body.get("old_pin", "")
    new_pin = body.get("new_pin", "").strip()

    if len(new_pin) < 4:
        return jsonify({"error": "Nouveau PIN min 4 caractères"}), 400

    data = load_data()
    user_id = session["user_id"]
    acc = data["accounts"][user_id]
    if not check_password_hash(acc["pin_hash"], old_pin):
        return jsonify({"error": "Ancien PIN incorrect"}), 401

    acc["pin_hash"] = generate_password_hash(new_pin)
    save_data(data)
    return jsonify({"ok": True})


def get_email_status(public: bool = False):
    configured = email_configured()
    if public:
        return {"mode": "email", "configured": configured}
    emails = get_emails()
    return {
        "mode": "email",
        "configured": configured,
        "from_email": EMAIL_FROM if configured else "",
        "registered_count": len(emails),
        "registered": {display_name(k): v for k, v in emails.items()},
        "emails": {pid: emails.get(pid, "") for pid in PERSONS},
    }


@app.route("/api/email/status")
def api_email_status():
    return jsonify(get_email_status())


@app.route("/api/email/addresses", methods=["GET"])
def api_email_addresses_get():
    return jsonify(get_email_status())


@app.route("/api/account/email", methods=["PUT"])
@login_required
def api_account_email():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Email invalide"}), 400
    data = load_data()
    user_id = session["user_id"]
    data["accounts"][user_id]["email"] = email
    data["emails"][user_id] = email
    save_data(data)
    return jsonify({"ok": True, "email": email})


@app.route("/api/email/addresses", methods=["PUT"])
@login_required
def api_email_addresses_put():
    body = request.get_json(silent=True) or {}
    addresses = body.get("emails", {})
    data = load_data()
    stored = {}
    for pid in PERSONS:
        if pid in addresses:
            stored[pid] = addresses[pid].strip().lower()
    data["emails"] = stored
    save_data(data)
    return jsonify(get_email_status())


@app.route("/api/email/test", methods=["POST"])
@login_required
def api_email_test():
    if not DEBUG_MODE:
        return jsonify({"error": "Endpoint désactivé en production"}), 403
    if not email_configured():
        return jsonify({"error": "Email non configuré (.env)"}), 400
    if not get_emails():
        return jsonify({"error": "Aucun email enregistré"}), 400
    results = notify_all(
        "Test OK ! Tu recevras ici les notifs roulette, votes et résultats.",
        subject=f"✅ {APP_NAME} — test email",
        html=email_layout(
            "Test email OK",
            "✅",
            "<p>Si tu lis ce message, les notifications Team DRC fonctionnent.</p>"
            "<p>Tu recevras ici : rappels roulette, résultats de tirage, ouverture des votes et notes finales.</p>",
        ),
    )
    ok = sum(1 for r in results if r.get("ok"))
    return jsonify({"ok": ok > 0, "sent": ok, "total": len(results), "results": results})


@app.route("/api/roulette")
def api_roulette():
    return jsonify(get_roulette_status())


@app.route("/api/roulette/spin", methods=["POST"])
@login_required
def api_roulette_spin():
    body = request.get_json(silent=True) or {}
    who = session["user_id"]

    if DEBUG_MODE and who == "lorenzo" and body.get("test_reset"):
        data = load_data()
        key = period_key(get_period_start())
        data.get("roulette_draws", {}).pop(key, None)
        save_data(data)

    status = get_roulette_status()
    if not status["can_spin"]:
        return jsonify({
            "error": "Tu ne peux pas tirer maintenant",
            "responsible": status["responsible_name"],
            "window_open": status["window_open"],
            "is_spun": status["is_spun"],
        }), 403

    if who != status["responsible"]:
        return jsonify({
            "error": f"Seul {status['responsible_name']} peut tirer cette semaine",
            "responsible": status["responsible_name"],
        }), 403

    data = load_data()
    period = get_period_start()
    key = period_key(period)
    target = get_target_tuesday(period)
    food = weighted_food_pick()

    draw = {
        "period_start": key,
        "target_tuesday": target.isoformat(),
        "food": food,
        "spun_by": who,
        "spun_by_name": display_name(who),
        "spun_at": datetime.now().isoformat(),
    }
    data.setdefault("roulette_draws", {})[key] = draw
    save_data(data)

    target_str = target.strftime("%d/%m")
    rare_txt = " ✨ RARE !" if food["rare"] else ""
    spinner = display_name(who)
    subject = f"🎰 {APP_NAME} — {food['emoji']} {food['name']}"
    plain = (
        f"{spinner} a tiré : {food['emoji']} {food['name']}{rare_txt} · "
        f"À ramener le mardi {target_str} !"
    )
    rare_badge = '<span style="background:#e53170;color:#fff;padding:2px 8px;border-radius:6px;font-size:12px;margin-left:6px">RARE</span>' if food["rare"] else ""
    html = email_layout(
        "Résultat de la roulette",
        food["emoji"],
        f"<p><strong>{spinner}</strong> a tiré au sort :</p>"
        f'<div style="text-align:center;margin:20px 0;padding:20px;background:#242336;border-radius:12px">'
        f'<div style="font-size:40px">{food["emoji"]}</div>'
        f'<div style="font-size:22px;font-weight:800;margin-top:8px">{food["name"]}{rare_badge}</div>'
        f'<div style="color:#94a1b2;margin-top:8px">À ramener le mardi <strong>{target_str}</strong></div></div>'
        f"<p>Les votes s'ouvriront le mardi matin à <strong>9h00</strong> après la dégustation.</p>",
    )
    add_system_message(plain)
    email_results = notify_all(plain, subject=subject, html=html)

    return jsonify({"draw": draw, "status": get_roulette_status(), "email_results": email_results})


@app.route("/api/food")
def api_food():
    return jsonify(get_roulette_status())


@app.route("/avatars/<path:filename>")
def serve_avatar(filename):
    safe = Path(filename).name
    if not safe or safe != filename:
        return jsonify({"error": "Fichier invalide"}), 400
    avatars_dir = BASE_DIR / "avatars"
    return send_from_directory(avatars_dir, safe)


@app.route("/api/ratings")
def api_ratings():
    user_id = session.get("user_id")
    return jsonify(rating_status_for_user(user_id))


@app.route("/api/ratings/vote", methods=["POST"])
@login_required
def api_ratings_vote():
    body = request.get_json(silent=True) or {}
    try:
        score = int(body.get("score", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Note invalide"}), 400
    if score < 1 or score > 10:
        return jsonify({"error": "Note entre 1 et 10"}), 400

    if not vote_window_status().get("open"):
        return jsonify({"error": "Votes fermés — ouverture mardi à 9h"}), 403

    user_id = session["user_id"]
    today_key = date.today().isoformat()
    session_data = get_today_rating_session()
    if not session_data:
        return jsonify({"error": "Pas de session de note"}), 404
    if session_data.get("completed"):
        return jsonify({"error": "Votes terminés"}), 400
    if user_id == session_data["baker_id"]:
        return jsonify({"error": "Le chef ne vote pas pour son propre plat"}), 403
    if user_id in session_data.get("votes", {}):
        return jsonify({"error": "Tu as déjà voté"}), 400

    data = load_data()
    data["rating_sessions"][today_key]["votes"][user_id] = score
    save_data(data)
    finalized = finalize_rating_if_ready(today_key)
    return jsonify(rating_status_for_user(user_id))


@app.route("/api/avatars", methods=["GET"])
def api_avatars_get():
    return jsonify(DEFAULT_AVATARS)


@app.route("/api/messages", methods=["GET"])
def api_messages_get():
    check_and_send_reminders()
    data = load_data()
    return jsonify(data.get("messages", [])[-100:])


@app.route("/api/messages", methods=["POST"])
@login_required
def api_messages_post():
    body = request.get_json(silent=True) or {}
    text = body.get("text", "").strip()
    author = session["user_id"]
    if not text or len(text) > 500:
        return jsonify({"error": "Message vide ou trop long"}), 400

    msg = {
        "id": str(uuid.uuid4()),
        "author": author,
        "text": text,
        "ts": datetime.now().isoformat(),
    }

    data = load_data()
    messages = data.setdefault("messages", [])
    messages.append(msg)
    data["messages"] = messages[-200:]
    save_data(data)

    notify_all(f"{display_name(author)} : {text}", subject=f"💬 {APP_NAME}")

    return jsonify(msg), 201


if __name__ == "__main__":
    load_data()
    print(f"\n🍽️  {APP_NAME}")
    print(f"   Local  → http://127.0.0.1:{PORT}")
    print(f"   Réseau → {APP_URL}")
    if DEBUG_MODE:
        print("   Mode  → ⚠️  DEBUG (test endpoints actifs)")
    if email_configured():
        print(f"   Email → ✅ {EMAIL_FROM}")
        if os.getenv("SEND_PIN_EMAILS", "false").lower() in ("1", "true", "yes"):
            send_welcome_pin_emails()
    else:
        print("   Email → ⚠️  configure .env (voir .env.example)")
    print()
    app.run(host=HOST, port=PORT, debug=DEBUG_MODE)
