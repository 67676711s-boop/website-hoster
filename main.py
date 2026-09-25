import json
import os
import re
from contextlib import asynccontextmanager
from datetime import timezone
from html import escape
from pathlib import Path
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from starlette.middleware.sessions import SessionMiddleware

from database import AsyncSessionLocal, init_db
from moderation import Giveaway, MessageLog, ModLog, Warning
from invites import InviteJoin
from panels import GuildPanelConfig
from settings import GuildSettings

load_dotenv()

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback")
SESSION_SECRET = os.getenv("SESSION_SECRET")
DISCORD_API = "https://discord.com/api/v10"
BASE_DIR = Path(__file__).resolve().parents[1]
TRANSCRIPT_ROOT = BASE_DIR / "transcripts"

for name, value in {
    "DISCORD_CLIENT_ID": CLIENT_ID,
    "DISCORD_CLIENT_SECRET": CLIENT_SECRET,
    "DISCORD_TOKEN": DISCORD_TOKEN,
    "SESSION_SECRET": SESSION_SECRET,
}.items():
    if not value:
        raise RuntimeError(f"{name} is missing from .env")

DEFAULT_WELCOME = "Welcome {user} to **{server}**!"
DEFAULT_TICKET_TITLE = "Support Tickets"
DEFAULT_TICKET_DESCRIPTION = "Need help from the staff team? Click the button below to create a private support ticket."
DEFAULT_TICKET_BUTTON = "Create Ticket"
DEFAULT_TICKET_NAME = "ticket-{user}"
DEFAULT_TICKET_WELCOME_TITLE = "Support Ticket"
DEFAULT_TICKET_WELCOME_DESCRIPTION = "Please describe what you need help with."
DEFAULT_APP_TITLE = "Staff Applications"
DEFAULT_APP_DESCRIPTION = "Interested in joining the staff team? Click the button below to submit a staff application."
DEFAULT_APP_BUTTON = "Apply for Staff"
DEFAULT_APP_FORM_TITLE = "Staff Application"
DEFAULT_APP_DM = "Thanks for applying for staff in **{server}**. Your application has been received and sent to the staff team for review."
DEFAULT_QUESTIONS = [
    "Why do you want to become staff?",
    "Do you have previous moderation experience?",
    "How would you handle a disagreement with another staff member?",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="ServerGuard Dashboard", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="serverguard_session",
    max_age=86400,
    same_site="lax",
    https_only=False,
    path="/",
)


CSS = """
:root{--bg:#090d18;--panel:#101827;--panel2:#131e31;--line:#25324a;--text:#e7eefc;--muted:#91a0b8;--accent:#7c6cff;--accent2:#5e9bff;--good:#4ade80;--warn:#fbbf24;--bad:#fb7185;}
*{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at top,#18213a 0,#090d18 48%);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;line-height:1.45}
a{color:inherit}.wrap{max-width:1280px;margin:auto;padding:28px}
.top{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:16px 22px;border-bottom:1px solid var(--line);background:rgba(9,13,24,.8);backdrop-filter:blur(10px);position:sticky;top:0;z-index:5}
.brand{display:flex;align-items:center;gap:11px;font-weight:800;font-size:19px}.brand-dot{width:12px;height:12px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 0 22px #7c6cff88}
.nav{display:flex;gap:10px;flex-wrap:wrap}.btn,.btn2{display:inline-block;padding:10px 14px;border-radius:10px;text-decoration:none;border:1px solid var(--line);background:var(--panel2);cursor:pointer;color:var(--text);font-weight:700}.btn{background:linear-gradient(135deg,var(--accent),var(--accent2));border-color:transparent}.danger{background:#7f1d1d;border-color:#991b1b}.muted{color:var(--muted)} .tiny{font-size:12px;color:var(--muted)}
.hero{padding:54px 0 26px}.hero h1{font-size:46px;line-height:1.05;margin:0 0 14px}.hero p{max-width:760px;color:var(--muted);font-size:18px}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}.card{grid-column:span 12;background:linear-gradient(180deg,rgba(16,24,39,.95),rgba(16,24,39,.8));border:1px solid var(--line);border-radius:18px;padding:20px;box-shadow:0 12px 30px #00000022}.col6{grid-column:span 6}.col4{grid-column:span 4}.col3{grid-column:span 3}.stat{font-size:30px;font-weight:800}.stat-label{color:var(--muted);font-size:13px}.server-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:16px}.server{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px}.server h3{margin:0 0 6px}.badge{display:inline-block;padding:5px 9px;border-radius:999px;font-size:12px;font-weight:800;background:#1e293b;color:#bfdbfe}.badge.good{background:#12341f;color:#86efac}.badge.warn{background:#3b2b0a;color:#fde68a}
section h2{margin-top:0}.section-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}.row{display:grid;grid-template-columns:1fr 1fr;gap:14px}.row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px} label{display:block;font-weight:700;margin:12px 0 7px} input,select,textarea{width:100%;padding:11px 12px;border-radius:10px;background:#0b1220;color:var(--text);border:1px solid #334155} textarea{min-height:90px;resize:vertical} select[multiple]{min-height:150px}.check{display:flex;align-items:center;gap:8px;margin:11px 0;color:var(--text)}.check input{width:auto}.save{margin-top:14px;width:100%;padding:12px;border:0;border-radius:10px;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;font-weight:800;cursor:pointer}.notice{padding:12px 14px;border-radius:11px;border:1px solid var(--line);background:#0d1727;margin-bottom:16px}.notice.good{border-color:#166534;background:#0b2115}.notice.bad{border-color:#7f1d1d;background:#271015}
.table{width:100%;border-collapse:collapse}.table th,.table td{border-bottom:1px solid var(--line);padding:10px 8px;text-align:left;vertical-align:top}.table th{color:#cbd5e1;font-size:13px}.code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;background:#0b1220;border:1px solid var(--line);padding:2px 6px;border-radius:6px}.footer{margin:38px 0 16px;color:var(--muted);font-size:13px;text-align:center}
@media(max-width:900px){.col6,.col4,.col3{grid-column:span 12}.row,.row3{grid-template-columns:1fr}.hero h1{font-size:36px}.top{position:static}}
"""


def page(title: str, body: str, *, authenticated: bool = False) -> HTMLResponse:
    nav = ""
    if authenticated:
        nav = "<div class='nav'><a class='btn2' href='/dashboard'>Servers</a><a class='btn2' href='/logout'>Logout</a></div>"
    return HTMLResponse(
        f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{escape(title)}</title><style>{CSS}</style></head>
<body><header class='top'><div class='brand'><span class='brand-dot'></span>ServerGuard</div>{nav}</header><div class='wrap'>{body}<div class='footer'>ServerGuard Dashboard • local admin panel • <a href='/terms'>Terms</a> • <a href='/privacy'>Privacy</a></div></div></body></html>"""
    )


async def discord_request(method: str, endpoint: str, *, payload=None, access_token=None):
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    else:
        headers["Authorization"] = f"Bot {DISCORD_TOKEN}"
    async with httpx.AsyncClient(timeout=15) as client:
        return await client.request(method, f"{DISCORD_API}{endpoint}", headers=headers, json=payload)


async def user_guilds(access_token: str) -> list[dict]:
    response = await discord_request("GET", "/users/@me/guilds", access_token=access_token)
    return response.json() if response.status_code == 200 else []


def can_manage(guild: dict) -> bool:
    if guild.get("owner") is True:
        return True
    try:
        perms = int(guild.get("permissions", 0))
    except (TypeError, ValueError):
        perms = 0
    return bool(perms & (1 << 3) or perms & (1 << 5))


async def find_server(request: Request, guild_id: str):
    token = request.session.get("access_token")
    if not token:
        return None
    for guild in await user_guilds(token):
        if str(guild.get("id")) == str(guild_id) and can_manage(guild):
            return guild
    return None


async def get_config(guild_id: int):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(GuildPanelConfig).where(GuildPanelConfig.guild_id == guild_id))
        return result.scalar_one_or_none()


async def get_settings(guild_id: int):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(GuildSettings).where(GuildSettings.guild_id == guild_id))
        return result.scalar_one_or_none()


async def get_roles(guild_id: str) -> list[dict]:
    response = await discord_request("GET", f"/guilds/{guild_id}/roles")
    return response.json() if response.status_code == 200 else []


async def get_channels(guild_id: str) -> list[dict]:
    response = await discord_request("GET", f"/guilds/{guild_id}/channels")
    return response.json() if response.status_code == 200 else []


def role_options(roles: list[dict], current: int | None = None, *, multiple: bool = False) -> str:
    selected = set(current or []) if multiple else ({current} if current is not None else set())
    output = "" if multiple else "<option value=''>None</option>"
    for role in sorted(roles, key=lambda item: int(item.get("position", 0)), reverse=True):
        if role.get("managed") or role.get("name") == "@everyone":
            continue
        rid = int(role["id"])
        mark = "selected" if rid in selected else ""
        output += f"<option value='{rid}' {mark}>{escape(role.get('name','Unnamed'))}</option>"
    return output


def channel_options(channels: list[dict], current: int | None = None, *, types=(0, 5), include_none=True) -> str:
    output = "<option value=''>None</option>" if include_none else ""
    for channel in sorted(channels, key=lambda item: item.get("position", 0)):
        if channel.get("type") not in types:
            continue
        cid = str(channel["id"])
        mark = "selected" if current is not None and str(current) == cid else ""
        output += f"<option value='{escape(cid)}' {mark}>#{escape(channel.get('name','unnamed'))}</option>"
    return output


def selected_options(items: list[dict], selected_ids: list[int], *, kind: str) -> str:
    selected = set(selected_ids)
    output = ""
    for item in sorted(items, key=lambda x: x.get("position", 0), reverse=(kind == "role")):
        if kind == "role":
            if item.get("managed") or item.get("name") == "@everyone":
                continue
            item_id = int(item["id"])
            label = item.get("name", "Unnamed")
        else:
            if item.get("type") not in (0, 5):
                continue
            item_id = int(item["id"])
            label = "#" + item.get("name", "unnamed")
        mark = "selected" if item_id in selected else ""
        output += f"<option value='{item_id}' {mark}>{escape(label)}</option>"
    return output


def parse_hex(value: str | None) -> int:
    value = (value or "").strip().lstrip("#")
    try:
        num = int(value, 16)
        return num if 0 <= num <= 0xFFFFFF else 0x5865F2
    except ValueError:
        return 0x5865F2


def check_session(request: Request):
    return request.session.get("user") and request.session.get("access_token")


@app.get("/", response_class=HTMLResponse)
async def home():
    return page(
        "ServerGuard",
        """
        <div class='hero'>
          <span class='badge good'>Discord moderation dashboard</span>
          <h1>Run your server from one clean panel.</h1>
          <p>Configure AutoMod, anti-raid alerts, welcome messages, logs, tickets, staff applications and more without editing Python files.</p>
          <a class='btn' href='/login'>Login with Discord</a>
        </div>
        <div class='grid'>
          <div class='card col4'><h3>🛡️ Security</h3><p class='muted'>Spam, links, attachments, invite blocking and join-rate alerts.</p></div>
          <div class='card col4'><h3>🎫 Tickets</h3><p class='muted'>Custom panels, support roles, required roles and saved HTML transcripts.</p></div>
          <div class='card col4'><h3>🎉 Giveaways</h3><p class='muted'>Button-entry giveaways with ending, rerolling and logging.</p></div>
          <div class='card col6'><h3>📜 Logs</h3><p class='muted'>Deleted/edited message logs plus moderation, timeout, ban, AutoMod, ticket and giveaway events.</p></div>
          <div class='card col6'><h3>👋 Welcome</h3><p class='muted'>Pick a welcome channel, message and optional automatic join role.</p></div>
        </div>
        """,
    )


@app.get("/login")
async def login():
    params = {"client_id": CLIENT_ID, "response_type": "code", "redirect_uri": REDIRECT_URI, "scope": "identify guilds"}
    return RedirectResponse("https://discord.com/oauth2/authorize?" + urlencode(params), status_code=307)


@app.get("/auth/callback")
async def callback(request: Request, code: str | None = None, error: str | None = None):
    if error:
        return page("Login failed", f"<div class='card'><h2>Login failed</h2><p class='muted'>{escape(error)}</p><a class='btn' href='/'>Try again</a></div>")
    if not code:
        return page("Login failed", "<div class='card'><h2>Login failed</h2><p class='muted'>No OAuth code was received.</p></div>")

    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(
            f"{DISCORD_API}/oauth2/token",
            data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_response.status_code != 200:
            return page("Login failed", "<div class='card'><h2>Discord rejected the authorization.</h2></div>")
        token = token_response.json().get("access_token")
        if not token:
            return page("Login failed", "<div class='card'><h2>No access token was returned.</h2></div>")
        user_response = await client.get(f"{DISCORD_API}/users/@me", headers={"Authorization": f"Bearer {token}"})
        if user_response.status_code != 200:
            return page("Login failed", "<div class='card'><h2>Could not retrieve your Discord account.</h2></div>")
        user = user_response.json()

    request.session.clear()
    request.session["user"] = {"id": user.get("id"), "username": user.get("username"), "global_name": user.get("global_name")}
    request.session["access_token"] = token
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not check_session(request):
        return RedirectResponse("/login", status_code=303)
    user = request.session["user"]
    manageable = [g for g in await user_guilds(request.session["access_token"]) if can_manage(g)]
    cards = []
    for guild in manageable:
        gid = str(guild["id"])
        bot_response = await discord_request("GET", f"/guilds/{gid}")
        connected = bot_response.status_code == 200
        status = "<span class='badge good'>Bot connected</span>" if connected else "<span class='badge warn'>Bot not in server</span>"
        action = f"<a class='btn' href='/server/{gid}'>Manage</a>" if connected else ""
        icon = guild.get("icon")
        icon_html = f"<img src='https://cdn.discordapp.com/icons/{gid}/{icon}.png?size=64' style='width:48px;height:48px;border-radius:14px;object-fit:cover' alt=''>" if icon else ""
        cards.append(f"<div class='server'><div style='display:flex;gap:12px;align-items:center'>{icon_html}<div><h3>{escape(guild.get('name','Unknown Server'))}</h3>{status}</div></div><div style='margin-top:14px'>{action}</div></div>")
    if not cards:
        cards = ["<div class='card'><h3>No manageable servers found</h3><p class='muted'>Your Discord account does not currently have Owner, Administrator or Manage Server access to a server visible to the dashboard.</p></div>"]
    name = escape(user.get("global_name") or user.get("username") or "User")
    return page(
        "Dashboard",
        f"<div class='hero'><h1>Welcome, {name} 👋</h1><p>Select a server to configure ServerGuard.</p></div><div class='server-grid'>{''.join(cards)}</div>",
        authenticated=True,
    )


async def ensure_config(guild_id: int) -> GuildPanelConfig:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(GuildPanelConfig).where(GuildPanelConfig.guild_id == guild_id))
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = GuildPanelConfig(guild_id=guild_id)
            db.add(obj)
            await db.commit()
            await db.refresh(obj)
        return obj


async def ensure_settings(guild_id: int) -> GuildSettings:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(GuildSettings).where(GuildSettings.guild_id == guild_id))
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = GuildSettings(guild_id=guild_id)
            db.add(obj)
            await db.commit()
            await db.refresh(obj)
        return obj


async def valid_role(guild_id: str, value):
    if not value:
        return None
    try:
        wanted = int(value)
    except (TypeError, ValueError):
        return None
    for role in await get_roles(guild_id):
        if int(role.get("id")) == wanted and not role.get("managed"):
            return wanted
    return None


async def valid_role_list(guild_id: str, values) -> list[int]:
    allowed = {int(r["id"]) for r in await get_roles(guild_id) if not r.get("managed") and r.get("name") != "@everyone"}
    out = []
    for value in values:
        try:
            rid = int(value)
        except (TypeError, ValueError):
            continue
        if rid in allowed:
            out.append(rid)
    return list(dict.fromkeys(out))


async def valid_channel(guild_id: str, value, *, types=(0, 5)):
    if not value:
        return None
    try:
        wanted = int(value)
    except (TypeError, ValueError):
        return None
    for channel in await get_channels(guild_id):
        if int(channel.get("id")) == wanted and channel.get("type") in types:
            return wanted
    return None


async def valid_channel_list(guild_id: str, values) -> list[int]:
    allowed = {int(c["id"]) for c in await get_channels(guild_id) if c.get("type") in (0, 5)}
    out = []
    for value in values:
        try:
            cid = int(value)
        except (TypeError, ValueError):
            continue
        if cid in allowed:
            out.append(cid)
    return list(dict.fromkeys(out))


@app.get("/server/{guild_id}", response_class=HTMLResponse)
async def server_page(request: Request, guild_id: str, saved: str | None = None, published: str | None = None, error: str | None = None):
    if not check_session(request):
        return RedirectResponse("/login", status_code=303)
    guild = await find_server(request, guild_id)
    if not guild:
        return page("Permission denied", "<div class='card'><h2>Permission denied</h2><a class='btn' href='/dashboard'>Back</a></div>", authenticated=True)
    bot_response = await discord_request("GET", f"/guilds/{guild_id}")
    if bot_response.status_code != 200:
        return page("Bot missing", "<div class='card'><h2>ServerGuard is not in this server.</h2><a class='btn' href='/dashboard'>Back</a></div>", authenticated=True)

    roles = await get_roles(guild_id)
    channels = await get_channels(guild_id)
    config = await ensure_config(int(guild_id))
    settings = await ensure_settings(int(guild_id))
    text_channels = [c for c in channels if c.get("type") in (0, 5)]
    categories = [c for c in channels if c.get("type") == 4]
    role_list = [r for r in roles if not r.get("managed") and r.get("name") != "@everyone"]

    async with AsyncSessionLocal() as db:
        warnings_count = await db.scalar(select(func.count(Warning.id)).where(Warning.guild_id == int(guild_id)))
        mod_count = await db.scalar(select(func.count(ModLog.id)).where(ModLog.guild_id == int(guild_id)))
        message_count = await db.scalar(select(func.count(MessageLog.id)).where(MessageLog.guild_id == int(guild_id)))
        giveaway_count = await db.scalar(select(func.count(Giveaway.id)).where(Giveaway.guild_id == int(guild_id)))
        invite_count = await db.scalar(select(func.count(InviteJoin.id)).where(InviteJoin.guild_id == int(guild_id)))
    warnings_count = warnings_count or 0
    mod_count = mod_count or 0
    message_count = message_count or 0
    giveaway_count = giveaway_count or 0
    invite_count = invite_count or 0

    notice = ""
    if saved:
        notice = f"<div class='notice good'>✅ {escape(saved.title())} settings saved.</div>"
    if published:
        notice = f"<div class='notice good'>✅ {escape(published.title())} panel published/updated.</div>"
    if error:
        notice = f"<div class='notice bad'>❌ {escape(error)}</div>"

    auto_role_opts = role_options(role_list, settings.auto_role_id)
    welcome_channel_opts = channel_options(text_channels, settings.welcome_channel_id)
    log_channel_opts = channel_options(text_channels, settings.log_channel_id)
    ignore_role_opts = selected_options(role_list, settings.get_ignore_role_ids(), kind="role")
    ignore_channel_opts = selected_options(text_channels, settings.get_ignore_channel_ids(), kind="channel")

    ticket_channel_opts = channel_options(text_channels, config.ticket_panel_channel_id, include_none=False)
    ticket_category_opts = "<option value=''>None</option>" + "".join(
        f"<option value='{c['id']}' {'selected' if config.ticket_category_id and int(config.ticket_category_id)==int(c['id']) else ''}>{escape(c.get('name','Unnamed'))}</option>"
        for c in sorted(categories, key=lambda x:x.get('position',0))
    )
    support_opts = role_options(role_list, config.ticket_support_role_id)
    required_opts = role_options(role_list, config.ticket_required_role_id)
    ticket_blacklist_opts = selected_options(role_list, config.get_blacklist_role_ids(), kind="role")

    app_channel_opts = channel_options(text_channels, config.application_panel_channel_id, include_none=False)
    review_opts = channel_options(text_channels, config.application_review_channel_id)
    reviewer_opts = role_options(role_list, config.application_reviewer_role_id)
    questions = config.get_questions() or DEFAULT_QUESTIONS
    questions += [""] * (20 - len(questions))
    question_boxes = "".join(f"<label>Question {i+1}</label><textarea name='question_{i+1}' maxlength='200'>{escape(questions[i])}</textarea>" for i in range(20))

    checks = {
        "welcome_enabled": "checked" if settings.welcome_enabled else "",
        "automod_enabled": "checked" if settings.automod_enabled else "",
        "block_links": "checked" if settings.block_links else "",
        "block_attachments": "checked" if settings.block_attachments else "",
        "block_invites": "checked" if settings.block_invites else "",
        "automod_ignore_bots": "checked" if settings.automod_ignore_bots else "",
        "log_deleted_messages": "checked" if settings.log_deleted_messages else "",
        "log_edited_messages": "checked" if settings.log_edited_messages else "",
        "log_mod_actions": "checked" if settings.log_mod_actions else "",
        "log_automod": "checked" if settings.log_automod else "",
        "log_giveaways": "checked" if settings.log_giveaways else "",
        "log_ticket_transcripts": "checked" if settings.log_ticket_transcripts else "",
        "log_invites": "checked" if settings.log_invites else "",
        "anti_raid_enabled": "checked" if settings.anti_raid_enabled else "",
        "ticket_transcript_enabled": "checked" if config.ticket_transcript_enabled else "",
        "application_dm_enabled": "checked" if config.application_dm_enabled else "",
    }

    body = f"""
    <div style='padding:28px 0 10px'><a class='btn2' href='/dashboard'>← Servers</a></div>
    {notice}
    <div class='hero'><span class='badge good'>Connected</span><h1>{escape(guild.get('name','Server'))}</h1><p>Configure everything from this page. The bot itself has no support-invite command; the old invite command is not included in this build.</p></div>

    <div class='grid'>
      <div class='card col3'><div class='stat'>{warnings_count}</div><div class='stat-label'>Warnings saved</div></div>
      <div class='card col3'><div class='stat'>{mod_count}</div><div class='stat-label'>Moderation logs</div></div>
      <div class='card col3'><div class='stat'>{message_count}</div><div class='stat-label'>Message logs</div></div>
      <div class='card col3'><div class='stat'>{giveaway_count}</div><div class='stat-label'>Giveaways</div></div>
      <div class='card col3'><div class='stat'>{invite_count}</div><div class='stat-label'>Tracked joins</div></div>
      <div class='card col12'><div class='nav'><a class='btn' href='/server/{guild_id}/logs'>Open Logs</a><a class='btn2' href='/server/{guild_id}/transcripts'>Ticket Transcripts</a></div><p class='tiny'>Transcript files are saved locally under <span class='code'>transcripts/{guild_id}/</span>.</p></div>

      <section class='card col6'><div class='section-head'><div><h2>👋 Welcome & Join</h2><p class='muted'>Send a welcome message and optionally add a role when someone joins.</p></div></div>
        <form method='post' action='/server/{guild_id}/settings/save'>
          <label class='check'><input type='hidden' name='welcome_enabled' value='0'><input type='checkbox' name='welcome_enabled' {checks['welcome_enabled']}> Enable welcome messages</label>
          <label>Welcome channel</label><select name='welcome_channel_id'>{welcome_channel_opts}</select>
          <label>Auto role</label><select name='auto_role_id'>{auto_role_opts}</select>
          <label>Welcome message</label><textarea name='welcome_message' maxlength='2000'>{escape(settings.welcome_message or DEFAULT_WELCOME)}</textarea>
          <p class='tiny'>Placeholders: <span class='code'>{'{user}'}</span> <span class='code'>{'{username}'}</span> <span class='code'>{'{server}'}</span> <span class='code'>{'{id}'}</span></p>
          <button class='save'>Save Welcome Settings</button>
        </form>
      </section>

      <section class='card col6'><h2>🛡️ Security</h2><p class='muted'>AutoMod removes selected message types. Anti-raid creates an alert when joins cross your threshold.</p>
        <form method='post' action='/server/{guild_id}/settings/save'>
          <label class='check'><input type='hidden' name='automod_enabled' value='0'><input type='checkbox' name='automod_enabled' {checks['automod_enabled']}> Enable AutoMod</label>
          <div class='row'><label class='check'><input type='hidden' name='block_links' value='0'><input type='checkbox' name='block_links' {checks['block_links']}> Block website links</label><label class='check'><input type='hidden' name='block_invites' value='0'><input type='checkbox' name='block_invites' {checks['block_invites']}> Block Discord invites</label></div>
          <label class='check'><input type='hidden' name='block_attachments' value='0'><input type='checkbox' name='block_attachments' {checks['block_attachments']}> Block file attachments / downloads</label>
          <label class='check'><input type='hidden' name='anti_raid_enabled' value='0'><input type='checkbox' name='anti_raid_enabled' {checks['anti_raid_enabled']}> Enable anti-raid join-rate alerts</label>
          <div class='row3'><div><label>Raid threshold</label><input type='number' name='anti_raid_threshold' value='{settings.anti_raid_threshold}' min='2' max='50'></div><div><label>Window (seconds)</label><input type='number' name='anti_raid_window_seconds' value='{settings.anti_raid_window_seconds}' min='3' max='120'></div><div><label>Log channel</label><select name='log_channel_id'>{log_channel_opts}</select></div></div>
          <button class='save'>Save Security Settings</button>
        </form>
      </section>

      <section class='card col6'><h2>🚫 AutoMod Ignore List</h2><p class='muted'>Pick roles/channels, enter user IDs, and optionally ignore bots.</p>
        <form method='post' action='/server/{guild_id}/settings/save'>
          <label class='check'><input type='hidden' name='automod_ignore_bots' value='0'><input type='checkbox' name='automod_ignore_bots' {checks['automod_ignore_bots']}> Ignore bot messages</label>
          <label>Ignore roles</label><select name='automod_ignore_role_ids' multiple>{ignore_role_opts}</select>
          <label>Ignore channels</label><select name='automod_ignore_channel_ids' multiple>{ignore_channel_opts}</select>
          <label>Ignore user IDs</label><textarea name='automod_ignore_user_ids'>{escape(chr(10).join(str(v) for v in settings.get_ignore_user_ids()))}</textarea>
          <button class='save'>Save AutoMod Exemptions</button>
        </form>
      </section>

      <section class='card col6'><h2>📜 Log Types</h2><p class='muted'>All selected events go to the configured log channel. Message logs can be large on busy servers.</p>
        <form method='post' action='/server/{guild_id}/settings/save'>
          <label>Log channel</label><select name='log_channel_id'>{log_channel_opts}</select>
          <label class='check'><input type='hidden' name='log_deleted_messages' value='0'><input type='checkbox' name='log_deleted_messages' {checks['log_deleted_messages']}> Deleted message logs</label>
          <label class='check'><input type='hidden' name='log_edited_messages' value='0'><input type='checkbox' name='log_edited_messages' {checks['log_edited_messages']}> Edited message logs</label>
          <label class='check'><input type='hidden' name='log_mod_actions' value='0'><input type='checkbox' name='log_mod_actions' {checks['log_mod_actions']}> Moderation / timeout / ban logs</label>
          <label class='check'><input type='hidden' name='log_automod' value='0'><input type='checkbox' name='log_automod' {checks['log_automod']}> AutoMod and anti-raid logs</label>
          <label class='check'><input type='hidden' name='log_giveaways' value='0'><input type='checkbox' name='log_giveaways' {checks['log_giveaways']}> Giveaway logs</label>
          <label class='check'><input type='hidden' name='log_ticket_transcripts' value='0'><input type='checkbox' name='log_ticket_transcripts' {checks['log_ticket_transcripts']}> Upload ticket transcripts to the log channel</label>
          <label class='check'><input type='hidden' name='log_invites' value='0'><input type='checkbox' name='log_invites' {checks['log_invites']}> Invite tracking logs</label>
          <button class='save'>Save Log Settings</button>
        </form>
      </section>

      <section class='card col12'><h2>🎫 Ticket Panel</h2><p class='muted'>Tickets create private channels. Closing a ticket saves an HTML transcript before the channel is deleted.</p>
        <form method='post' action='/server/{guild_id}/ticket/save'>
          <div class='row'><div><label>Panel title</label><input name='ticket_panel_title' value='{escape(config.ticket_panel_title or DEFAULT_TICKET_TITLE)}' maxlength='256'></div><div><label>Button label</label><input name='ticket_button_label' value='{escape(config.ticket_button_label or DEFAULT_TICKET_BUTTON)}' maxlength='80'></div></div>
          <label>Panel description</label><textarea name='ticket_panel_description' maxlength='4000'>{escape(config.ticket_panel_description or DEFAULT_TICKET_DESCRIPTION)}</textarea>
          <div class='row3'><div><label>Button emoji</label><input name='ticket_button_emoji' value='{escape(config.ticket_button_emoji or '🎫')}' maxlength='32'></div><div><label>Panel color</label><input name='ticket_panel_color' value='{escape(config.ticket_panel_color or '5865F2')}' maxlength='7'></div><div><label>Ticket channel template</label><input name='ticket_channel_name' value='{escape(config.ticket_channel_name or DEFAULT_TICKET_NAME)}' maxlength='100'></div></div>
          <p class='tiny'>Template placeholders: <span class='code'>{'{user}'}</span> <span class='code'>{'{username}'}</span> <span class='code'>{'{id}'}</span> <span class='code'>{'{ticket}'}</span>. Discord channel names normalize spaces to hyphens.</p>
          <div class='row3'><div><label>Panel channel</label><select name='ticket_panel_channel_id' required>{ticket_channel_opts}</select></div><div><label>Category</label><select name='ticket_category_id'>{ticket_category_opts}</select></div><div><label>Support role</label><select name='ticket_support_role_id'>{support_opts}</select></div></div>
          <div class='row'><div><label>Required role</label><select name='ticket_required_role_id'>{required_opts}</select></div><div><label>Blacklist roles</label><select name='ticket_blacklist_role_ids' multiple>{ticket_blacklist_opts}</select></div></div>
          <label>Welcome title</label><input name='ticket_welcome_title' value='{escape(config.ticket_welcome_title or DEFAULT_TICKET_WELCOME_TITLE)}' maxlength='256'>
          <label>Welcome message</label><textarea name='ticket_welcome_description' maxlength='4000'>{escape(config.ticket_welcome_description or DEFAULT_TICKET_WELCOME_DESCRIPTION)}</textarea>
          <label class='check'><input type='hidden' name='ticket_transcript_enabled' value='0'><input type='checkbox' name='ticket_transcript_enabled' {checks['ticket_transcript_enabled']}> Save ticket transcripts</label>
          <button class='save'>Save Ticket Settings</button>
        </form>
        <form method='post' action='/server/{guild_id}/ticket/publish'><button class='save'>Publish / Update Ticket Panel</button></form>
      </section>

      <section class='card col12'><h2>🛡️ Staff Applications</h2><p class='muted'>Up to 20 questions. The bot asks them 5 at a time because a Discord modal cannot show all 20 fields at once.</p>
        <form method='post' action='/server/{guild_id}/application/save'>
          <div class='row'><div><label>Panel title</label><input name='application_panel_title' value='{escape(config.application_panel_title or DEFAULT_APP_TITLE)}' maxlength='256'></div><div><label>Button label</label><input name='application_button_label' value='{escape(config.application_button_label or DEFAULT_APP_BUTTON)}' maxlength='80'></div></div>
          <label>Panel description</label><textarea name='application_panel_description' maxlength='4000'>{escape(config.application_panel_description or DEFAULT_APP_DESCRIPTION)}</textarea>
          <div class='row3'><div><label>Button emoji</label><input name='application_button_emoji' value='{escape(config.application_button_emoji or '🛡️')}' maxlength='32'></div><div><label>Panel color</label><input name='application_panel_color' value='{escape(config.application_panel_color or '5865F2')}' maxlength='7'></div><div><label>Form title</label><input name='application_form_title' value='{escape(config.application_form_title or DEFAULT_APP_FORM_TITLE)}' maxlength='45'></div></div>
          <div class='row3'><div><label>Panel channel</label><select name='application_panel_channel_id' required>{app_channel_opts}</select></div><div><label>Review channel</label><select name='application_review_channel_id'>{review_opts}</select></div><div><label>Reviewer role</label><select name='application_reviewer_role_id'>{reviewer_opts}</select></div></div>
          <label class='check'><input type='hidden' name='application_dm_enabled' value='0'><input type='checkbox' name='application_dm_enabled' {checks['application_dm_enabled']}> DM confirmation after submission</label>
          <label>DM confirmation</label><textarea name='application_dm_message' maxlength='2000'>{escape(config.application_dm_message or DEFAULT_APP_DM)}</textarea>
          <p class='tiny'>Placeholders: <span class='code'>{'{server}'}</span> <span class='code'>{'{username}'}</span> <span class='code'>{'{user}'}</span></p>
          {question_boxes}
          <button class='save'>Save Application Settings</button>
        </form>
        <form method='post' action='/server/{guild_id}/application/publish'><button class='save'>Publish / Update Application Panel</button></form>
      </section>

      <section class='card col12'><h2>✨ Commands included</h2><p class='muted'>There is intentionally no support-server invite command in this build.</p><div class='grid'>
        <div class='card col4'><h3>Moderation</h3><p class='tiny'><span class='code'>/warn</span> <span class='code'>/warnings</span> <span class='code'>/unwarn</span> <span class='code'>/kick</span> <span class='code'>/ban</span> <span class='code'>/timeout</span> <span class='code'>/untimeout</span> <span class='code'>/purge</span> <span class='code'>/slowmode</span> <span class='code'>/lock</span> <span class='code'>/unlock</span></p></div>
        <div class='card col4'><h3>Giveaways</h3><p class='tiny'><span class='code'>/giveaway start</span> <span class='code'>/giveaway end</span> <span class='code'>/giveaway reroll</span></p></div>
        <div class='card col4'><h3>Utility & Invites</h3><p class='tiny'><span class='code'>/help</span> <span class='code'>/ping</span> <span class='code'>/serverinfo</span> <span class='code'>/userinfo</span> <span class='code'>/avatar</span> <span class='code'>/modstats</span> <span class='code'>/role add</span> <span class='code'>/role remove</span> <span class='code'>/role create</span> <span class='code'>/invites view</span> <span class='code'>/invites leaderboard</span> <span class='code'>/invites refresh</span></p></div>
      </div></section>
    </div>
    """
    return page(f"{guild.get('name','Server')} - ServerGuard", body, authenticated=True)


@app.post("/server/{guild_id}/settings/save")
async def save_settings(request: Request, guild_id: str):
    if not await find_server(request, guild_id):
        return HTMLResponse("Permission denied", status_code=403)
    form = await request.form()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(GuildSettings).where(GuildSettings.guild_id == int(guild_id)))
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = GuildSettings(guild_id=int(guild_id))
            db.add(settings)

        if "welcome_enabled" in form:
            settings.welcome_enabled = any(str(v) not in ("0", "", "false") for v in form.getlist("welcome_enabled"))
        if "welcome_channel_id" in form:
            settings.welcome_channel_id = await valid_channel(guild_id, form.get("welcome_channel_id"))
        if "auto_role_id" in form:
            settings.auto_role_id = await valid_role(guild_id, form.get("auto_role_id"))
        if "welcome_message" in form:
            settings.welcome_message = str(form.get("welcome_message") or DEFAULT_WELCOME)[:2000]

        # Checkbox settings only change when their field is present in the submitted form.
        for field, attr in (
            ("automod_enabled", "automod_enabled"),
            ("block_links", "block_links"),
            ("block_attachments", "block_attachments"),
            ("block_invites", "block_invites"),
            ("automod_ignore_bots", "automod_ignore_bots"),
            ("log_deleted_messages", "log_deleted_messages"),
            ("log_edited_messages", "log_edited_messages"),
            ("log_mod_actions", "log_mod_actions"),
            ("log_automod", "log_automod"),
            ("log_giveaways", "log_giveaways"),
            ("log_ticket_transcripts", "log_ticket_transcripts"),
            ("log_invites", "log_invites"),
            ("anti_raid_enabled", "anti_raid_enabled"),
        ):
            if field in form:
                setattr(settings, attr, any(str(v) not in ("0", "", "false") for v in form.getlist(field)))

        if "automod_ignore_role_ids" in form:
            settings.automod_ignore_role_ids = json.dumps(
                await valid_role_list(guild_id, form.getlist("automod_ignore_role_ids"))
            )
        if "automod_ignore_channel_ids" in form:
            settings.automod_ignore_channel_ids = json.dumps(
                await valid_channel_list(guild_id, form.getlist("automod_ignore_channel_ids"))
            )
        if "automod_ignore_user_ids" in form:
            user_ids = []
            for line in str(form.get("automod_ignore_user_ids") or "").splitlines():
                value = re.sub(r"[^0-9]", "", line)
                if value:
                    user_ids.append(int(value))
            settings.automod_ignore_user_ids = json.dumps(list(dict.fromkeys(user_ids)))
        if "log_channel_id" in form:
            settings.log_channel_id = await valid_channel(guild_id, form.get("log_channel_id"))

        if "anti_raid_threshold" in form:
            try:
                settings.anti_raid_threshold = max(2, min(int(form.get("anti_raid_threshold") or 8), 50))
            except ValueError:
                settings.anti_raid_threshold = 8
        if "anti_raid_window_seconds" in form:
            try:
                settings.anti_raid_window_seconds = max(3, min(int(form.get("anti_raid_window_seconds") or 10), 120))
            except ValueError:
                settings.anti_raid_window_seconds = 10

        await db.commit()
    return RedirectResponse(f"/server/{guild_id}?saved=general", status_code=303)


@app.post("/server/{guild_id}/ticket/save")
async def save_ticket(request: Request, guild_id: str):
    if not await find_server(request, guild_id):
        return HTMLResponse("Permission denied", status_code=403)
    form = await request.form()
    panel_channel = await valid_channel(guild_id, form.get("ticket_panel_channel_id"))
    category = await valid_channel(guild_id, form.get("ticket_category_id"), types=(4,))
    support = await valid_role(guild_id, form.get("ticket_support_role_id"))
    required = await valid_role(guild_id, form.get("ticket_required_role_id"))
    blacklist = await valid_role_list(guild_id, form.getlist("ticket_blacklist_role_ids"))

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(GuildPanelConfig).where(GuildPanelConfig.guild_id == int(guild_id)))
        config = result.scalar_one_or_none()
        if config is None:
            config = GuildPanelConfig(guild_id=int(guild_id))
            db.add(config)
        config.ticket_panel_channel_id = panel_channel
        config.ticket_category_id = category
        config.ticket_support_role_id = support
        config.ticket_required_role_id = required
        config.ticket_blacklist_role_ids = json.dumps(blacklist)
        config.ticket_channel_name = str(form.get("ticket_channel_name") or DEFAULT_TICKET_NAME).strip()[:100]
        config.ticket_panel_title = str(form.get("ticket_panel_title") or DEFAULT_TICKET_TITLE).strip()[:256]
        config.ticket_panel_description = str(form.get("ticket_panel_description") or DEFAULT_TICKET_DESCRIPTION).strip()[:4000]
        config.ticket_button_label = str(form.get("ticket_button_label") or DEFAULT_TICKET_BUTTON).strip()[:80]
        config.ticket_button_emoji = str(form.get("ticket_button_emoji") or "🎫").strip()[:32]
        config.ticket_panel_color = str(form.get("ticket_panel_color") or "5865F2").strip()[:7]
        config.ticket_welcome_title = str(form.get("ticket_welcome_title") or DEFAULT_TICKET_WELCOME_TITLE).strip()[:256]
        config.ticket_welcome_description = str(form.get("ticket_welcome_description") or DEFAULT_TICKET_WELCOME_DESCRIPTION).strip()[:4000]
        config.ticket_transcript_enabled = "ticket_transcript_enabled" in form
        await db.commit()
    return RedirectResponse(f"/server/{guild_id}?saved=ticket", status_code=303)


@app.post("/server/{guild_id}/application/save")
async def save_application(request: Request, guild_id: str):
    if not await find_server(request, guild_id):
        return HTMLResponse("Permission denied", status_code=403)
    form = await request.form()
    panel_channel = await valid_channel(guild_id, form.get("application_panel_channel_id"))
    review_channel = await valid_channel(guild_id, form.get("application_review_channel_id"))
    reviewer = await valid_role(guild_id, form.get("application_reviewer_role_id"))
    questions = []
    for i in range(1, 21):
        question = str(form.get(f"question_{i}") or "").strip()[:200]
        if question:
            questions.append(question)
    if not questions:
        questions = DEFAULT_QUESTIONS

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(GuildPanelConfig).where(GuildPanelConfig.guild_id == int(guild_id)))
        config = result.scalar_one_or_none()
        if config is None:
            config = GuildPanelConfig(guild_id=int(guild_id))
            db.add(config)
        config.application_panel_channel_id = panel_channel
        config.application_review_channel_id = review_channel
        config.application_reviewer_role_id = reviewer
        config.application_panel_title = str(form.get("application_panel_title") or DEFAULT_APP_TITLE).strip()[:256]
        config.application_panel_description = str(form.get("application_panel_description") or DEFAULT_APP_DESCRIPTION).strip()[:4000]
        config.application_button_label = str(form.get("application_button_label") or DEFAULT_APP_BUTTON).strip()[:80]
        config.application_button_emoji = str(form.get("application_button_emoji") or "🛡️").strip()[:32]
        config.application_panel_color = str(form.get("application_panel_color") or "5865F2").strip()[:7]
        config.application_form_title = str(form.get("application_form_title") or DEFAULT_APP_FORM_TITLE).strip()[:45]
        config.application_questions = json.dumps(questions[:20])
        config.application_dm_enabled = "application_dm_enabled" in form
        config.application_dm_message = str(form.get("application_dm_message") or DEFAULT_APP_DM).strip()[:2000]
        await db.commit()
    return RedirectResponse(f"/server/{guild_id}?saved=application", status_code=303)


async def publish_panel(guild_id: int, kind: str):
    config = await get_config(guild_id)
    if not config:
        return "Save the settings first."
    if kind == "ticket":
        channel_id = config.ticket_panel_channel_id
        message_id = config.ticket_panel_message_id
        title = config.ticket_panel_title or DEFAULT_TICKET_TITLE
        description = config.ticket_panel_description or DEFAULT_TICKET_DESCRIPTION
        label = config.ticket_button_label or DEFAULT_TICKET_BUTTON
        emoji = config.ticket_button_emoji or "🎫"
        custom_id = "serverguard:ticket:open"
    else:
        channel_id = config.application_panel_channel_id
        message_id = config.application_panel_message_id
        title = config.application_panel_title or DEFAULT_APP_TITLE
        description = config.application_panel_description or DEFAULT_APP_DESCRIPTION
        label = config.application_button_label or DEFAULT_APP_BUTTON
        emoji = config.application_button_emoji or "🛡️"
        custom_id = "serverguard:application:open"
    if not channel_id:
        return "Choose a panel channel first."

    payload = {
        "embeds": [{"title": title[:256], "description": description[:4096], "color": parse_hex(config.ticket_panel_color if kind == "ticket" else config.application_panel_color)}],
        "components": [{"type": 1, "components": [{"type": 2, "style": 1, "label": label[:80], "custom_id": custom_id, "emoji": {"name": emoji[:32]} if emoji else None}]}],
    }
    # Discord rejects null button emoji objects, so remove it when blank.
    button = payload["components"][0]["components"][0]
    if not emoji:
        button.pop("emoji", None)

    response = None
    if message_id:
        response = await discord_request("PATCH", f"/channels/{channel_id}/messages/{message_id}", payload=payload)
        if response.status_code not in (200, 204):
            response = None
    if response is None:
        response = await discord_request("POST", f"/channels/{channel_id}/messages", payload=payload)
    if response.status_code not in (200, 201):
        return "ServerGuard could not publish the panel. Check the bot's channel permissions."
    data = response.json()
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(GuildPanelConfig).where(GuildPanelConfig.guild_id == guild_id))
        config = result.scalar_one()
        if kind == "ticket":
            config.ticket_panel_message_id = int(data["id"])
        else:
            config.application_panel_message_id = int(data["id"])
        await db.commit()
    return None


@app.post("/server/{guild_id}/ticket/publish")
async def ticket_publish(request: Request, guild_id: str):
    if not await find_server(request, guild_id):
        return HTMLResponse("Permission denied", status_code=403)
    error = await publish_panel(int(guild_id), "ticket")
    if error:
        return RedirectResponse(f"/server/{guild_id}?error={error}", status_code=303)
    return RedirectResponse(f"/server/{guild_id}?published=ticket", status_code=303)


@app.post("/server/{guild_id}/application/publish")
async def application_publish(request: Request, guild_id: str):
    if not await find_server(request, guild_id):
        return HTMLResponse("Permission denied", status_code=403)
    error = await publish_panel(int(guild_id), "application")
    if error:
        return RedirectResponse(f"/server/{guild_id}?error={error}", status_code=303)
    return RedirectResponse(f"/server/{guild_id}?published=application", status_code=303)


@app.get("/server/{guild_id}/logs", response_class=HTMLResponse)
async def server_logs(request: Request, guild_id: str):
    if not check_session(request):
        return RedirectResponse("/login", status_code=303)
    guild = await find_server(request, guild_id)
    if not guild:
        return page("Permission denied", "<div class='card'><h2>Permission denied</h2></div>", authenticated=True)
    gid = int(guild_id)
    async with AsyncSessionLocal() as db:
        mod = (await db.execute(select(ModLog).where(ModLog.guild_id == gid).order_by(ModLog.created_at.desc()).limit(50))).scalars().all()
        msg = (await db.execute(select(MessageLog).where(MessageLog.guild_id == gid).order_by(MessageLog.created_at.desc()).limit(50))).scalars().all()
        giveaways = (await db.execute(select(Giveaway).where(Giveaway.guild_id == gid).order_by(Giveaway.created_at.desc()).limit(50))).scalars().all()
        invite_rows = (await db.execute(select(InviteJoin).where(InviteJoin.guild_id == gid).order_by(InviteJoin.joined_at.desc()).limit(50))).scalars().all()
    events = [(row.created_at, "Moderation", row.action, row.reason or row.details or "", row.target_id) for row in mod]
    events += [(row.created_at, "Message", row.action, row.content or row.new_content or "", row.user_id) for row in msg]
    events += [(row.created_at, "Giveaway", "Created", row.prize, row.id) for row in giveaways]
    events += [(row.joined_at, "Invite", "Join", f"member={row.member_id} inviter={row.inviter_id or 'unknown'} code={row.invite_code or 'unknown'}", row.member_id) for row in invite_rows]
    events.sort(key=lambda x: x[0], reverse=True)
    rows = []
    for when, kind, action, details, target in events[:100]:
        stamp = int(when.replace(tzinfo=timezone.utc).timestamp())
        rows.append(f"<tr><td><t>{escape(when.strftime('%Y-%m-%d %H:%M:%S UTC'))}</t></td><td>{escape(kind)}</td><td><strong>{escape(action)}</strong></td><td>{escape(details[:500])}</td><td>{escape(str(target or '—'))}</td></tr>")
    table = "<table class='table'><thead><tr><th>Time</th><th>Type</th><th>Action</th><th>Details</th><th>ID</th></tr></thead><tbody>" + ("".join(rows) or "<tr><td colspan='5'>No logs yet.</td></tr>") + "</tbody></table>"
    body = f"<div style='padding:28px 0 10px'><a class='btn2' href='/server/{guild_id}'>← Server</a></div><div class='hero'><h1>📜 Logs</h1><p>{escape(guild.get('name','Server'))}</p></div><div class='card'>{table}</div>"
    return page("Logs", body, authenticated=True)


@app.get("/server/{guild_id}/transcripts", response_class=HTMLResponse)
async def transcripts(request: Request, guild_id: str):
    if not check_session(request):
        return RedirectResponse("/login", status_code=303)
    guild = await find_server(request, guild_id)
    if not guild:
        return page("Permission denied", "<div class='card'><h2>Permission denied</h2></div>", authenticated=True)
    root = TRANSCRIPT_ROOT / str(guild_id)
    root.mkdir(parents=True, exist_ok=True)
    files = sorted((p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".html"), key=lambda p: p.stat().st_mtime, reverse=True)
    rows = "".join(f"<tr><td>{escape(f.name)}</td><td>{f.stat().st_size//1024} KB</td><td><a class='btn2' href='/server/{guild_id}/transcripts/{escape(f.name)}'>Open</a></td></tr>" for f in files)
    body = f"<div style='padding:28px 0 10px'><a class='btn2' href='/server/{guild_id}'>← Server</a></div><div class='hero'><h1>📄 Ticket Transcripts</h1><p>Saved HTML transcripts for closed tickets.</p></div><div class='card'><table class='table'><thead><tr><th>File</th><th>Size</th><th></th></tr></thead><tbody>{rows or '<tr><td colspan=3>No transcripts yet.</td></tr>'}</tbody></table></div>"
    return page("Ticket Transcripts", body, authenticated=True)


@app.get("/server/{guild_id}/transcripts/{filename}")
async def transcript_file(request: Request, guild_id: str, filename: str):
    if not check_session(request):
        return RedirectResponse("/login", status_code=303)
    if not await find_server(request, guild_id):
        return HTMLResponse("Permission denied", status_code=403)
    if not re.fullmatch(r"[A-Za-z0-9._-]+", filename):
        return HTMLResponse("Bad filename", status_code=400)
    root = TRANSCRIPT_ROOT / str(guild_id)
    path = root / Path(filename).name
    if not path.exists() or path.parent != root:
        return HTMLResponse("Not found", status_code=404)
    return FileResponse(path)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("serverguard_session", path="/")
    return response


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ServerGuard Dashboard"}


@app.get("/terms", response_class=HTMLResponse)
async def terms():
    return page("Terms of Service", """
    <div class='hero'><h1>Terms of Service</h1><p>Template for your ServerGuard website.</p></div>
    <div class='card'><p>By using ServerGuard, you agree to use the bot and dashboard in a lawful and responsible way. Server owners are responsible for their own server configuration, moderation decisions, and compliance with Discord's rules.</p><p>Do not use ServerGuard to harass, abuse, or bypass platform safeguards. Features may fail when Discord permissions, rate limits, outages, or API restrictions apply.</p><p>Replace this template with terms written for your actual project before publishing it as legal terms.</p></div>
    """)


@app.get("/privacy", response_class=HTMLResponse)
async def privacy():
    return page("Privacy Policy", """
    <div class='hero'><h1>Privacy Policy</h1><p>Template for your ServerGuard website.</p></div>
    <div class='card'><p>ServerGuard may store Discord user IDs, server IDs, moderation records, message-log records, giveaway data, configuration settings, and ticket transcripts when those features are enabled.</p><p>Keep only the information you need, protect the database and transcript folder, and publish accurate retention/contact details for your project.</p><p>This page is a template and is not legal advice.</p></div>
    """)
