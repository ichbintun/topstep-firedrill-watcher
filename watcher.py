#!/usr/bin/env python3
"""
Theo doi trang Topstep Fire Drill va gui canh bao khi noi dung thay doi.

Logic:
  1. Tai HTML -> boc tag -> chuan hoa text -> bo cac con so bien dong (payout counter).
  2. So sanh hash voi lan chay truoc (state.json).
  3. Canh bao:
       - HIGH: cau "Missed your shot" (dau hieu drill da ket thuc) BIEN MAT
               -> rat co the dang co fire drill moi / giveaway dang mo.
       - NORMAL: hash doi (trang co sua noi dung bat ky).
  4. Gui email (Gmail SMTP) va/hoac Telegram neu co secret.

Zero dependency: chi dung thu vien chuan cua Python.
"""

import difflib
import hashlib
import html
import json
import os
import re
import smtplib
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

URL = os.environ.get("WATCH_URL", "https://www.topstep.com/fire-drill")
STATE_PATH = Path(__file__).resolve().parent / "state.json"

# Cau nay chi xuat hien khi drill DA ket thuc. Mat cau nay = co bien dong dang chu y.
DORMANT_MARKERS = [
    "missed your tuanchung",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
VN_TZ = timezone(timedelta(hours=7))


# ---------------------------------------------------------------- fetch

def fetch(url: str, attempts: int = 3) -> str:
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
        except Exception as exc:  # noqa: BLE001
            last = exc
            if i < attempts - 1:
                time.sleep(5 * (i + 1))
    raise RuntimeError(f"Khong tai duoc {url}: {last}")


# ------------------------------------------------------- normalize text

TAG_BLOCK = re.compile(
    r"<(script|style|noscript|svg|template)\b.*?</\1>", re.I | re.S
)
TAG_ANY = re.compile(r"<[^>]+>")
# Cac mau so bien dong lien tuc -> thay bang placeholder de khong bao dong gia.
VOLATILE = [
    (re.compile(r"\$\s?[\d,]+(?:\.\d+)?"), "$<num>"),          # payout counter
    (re.compile(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b"), "<num>"),  # 1,234,567
    (re.compile(r"\b\d{2}:\d{2}(?::\d{2})?\b"), "<time>"),      # countdown
    (re.compile(r"\b\d{10,}\b"), "<id>"),                       # cache-busting id
]


def to_text(raw_html: str) -> str:
    s = TAG_BLOCK.sub(" ", raw_html)
    s = TAG_ANY.sub("\n", s)
    s = html.unescape(s)
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in s.splitlines()]
    lines = [ln for ln in lines if ln]
    s = "\n".join(lines)
    for pat, rep in VOLATILE:
        s = pat.sub(rep, s)
    return s


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ----------------------------------------------------------- notify

def send_email(subject: str, body: str) -> bool:
    user = os.environ.get("GMAIL_USER", "").strip()
    pwd = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    to = os.environ.get("MAIL_TO", "").strip() or user
    if not (user and pwd and to):
        print("[email] thieu GMAIL_USER / GMAIL_APP_PASSWORD -> bo qua", file=sys.stderr)
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.set_content(body)
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=30) as smtp:
        smtp.login(user, pwd)
        smtp.send_message(msg)
    print(f"[email] da gui tới {to}")
    return True


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat):
        return False
    data = urllib.parse.urlencode(
        {"chat_id": chat, "text": text[:4000], "disable_web_page_preview": "false"}
    ).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=data
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()
    print("[telegram] da gui")
    return True


# ----------------------------------------------------------------- main

def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text("utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )


def main() -> int:
    now_vn = datetime.now(VN_TZ).strftime("%Y-%m-%d %H:%M:%S (GMT+7)")
    raw = fetch(URL)
    text = to_text(raw)
    h = digest(text)

    state = load_state()
    prev_hash = state.get("hash")
    prev_text = state.get("text", "")

    low = text.lower()
    dormant = any(m in low for m in DORMANT_MARKERS)
    prev_dormant = state.get("dormant")

    changed = prev_hash is not None and prev_hash != h
    first_run = prev_hash is None

    # Dau hieu manh nhat: truoc do dang "drill da ket thuc", gio khong con cau do.
    went_live = (prev_dormant is True) and (dormant is False)

    print(f"[{now_vn}] hash={h[:12]} changed={changed} dormant={dormant} first_run={first_run}")

    alert_subject = None
    if went_live:
        alert_subject = "FIRE DRILL CO THE DANG LIVE - Topstep"
    elif changed:
        alert_subject = "Trang Topstep Fire Drill vua thay doi"
    elif first_run and not dormant:
        alert_subject = "Topstep Fire Drill: trang KHONG o trang thai 'da ket thuc'"

    if alert_subject:
        diff = ""
        if prev_text:
            d = list(
                difflib.unified_diff(
                    prev_text.splitlines(),
                    text.splitlines(),
                    fromfile="truoc",
                    tofile="bay gio",
                    lineterm="",
                    n=1,
                )
            )
            diff = "\n".join(d[:120]) or "(khong co dong text nao khac)"
        body = (
            f"Thoi diem phat hien: {now_vn}\n"
            f"URL: {URL}\n"
            f"Trang thai 'drill da ket thuc': {'CON' if dormant else 'KHONG CON'}"
            f" (lan truoc: {prev_dormant})\n\n"
            f"--- Thay doi noi dung ---\n{diff}\n\n"
            f"Mo trang ngay: {URL}\n"
            f"TopstepTV: https://www.topstep.com/topsteptv\n"
        )
        prefix = "[!!!] " if went_live else "[*] "
        try:
            send_email(prefix + alert_subject, body)
        except Exception as exc:  # noqa: BLE001
            print(f"[email] LOI: {exc}", file=sys.stderr)
        try:
            send_telegram(prefix + alert_subject + "\n\n" + body)
        except Exception as exc:  # noqa: BLE001
            print(f"[telegram] LOI: {exc}", file=sys.stderr)
    else:
        print("Khong co thay doi.")

    save_state(
        {
            "hash": h,
            "dormant": dormant,
            "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "checked_at_vn": now_vn,
            "url": URL,
            "text": text,
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
