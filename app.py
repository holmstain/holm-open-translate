import os
import json
import io
import zipfile
import uuid
import logging
import re
import math
import time
import threading
from email.utils import parsedate_to_datetime
from collections import Counter
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template_string, request, send_file, make_response
from openai import OpenAI, APIConnectionError, APIStatusError
from werkzeug.utils import secure_filename
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="assets")

API_KEY = os.getenv("NVIDIA_API_KEY")
BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL_NAME = "nvidia/riva-translate-4b-instruct-v2"

client = OpenAI(base_url=BASE_URL, api_key=API_KEY or "not-configured", timeout=30.0, max_retries=0)

BASE_OUTPUT_DIR = os.path.join(os.getcwd(), "outputs")
os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

TARGET_LANGUAGES = {
    "en": "English", "ar": "Arabic","bg": "Bulgarian","cs": "Czech","da": "Danish","de": "German","el": "Greek","es-ES": "European Spanish","es-419": "Latin America Spanish","et": "Estonian",
    "fi": "Finnish","fr": "French","hi": "Hindi","hu": "Hungarian","id": "Indonesian","it": "Italian","ja": "Japanese","ko": "Korean","lt": "Lithuanian","lv": "Latvian",
    "nl": "Dutch","no": "Norwegian","pl": "Polish","pt-PT": "European Portuguese","pt-BR": "Brazil Portuguese","ro": "Romanian","ru": "Russian","sk": "Slovak","sl": "Slovenian",
    "sv": "Swedish","th": "Thai","tr": "Turkish","uk": "Ukrainian","vi": "Vietnamese","zh-CN": "Simplified Chinese","zh-TW": "Traditional Chinese","hr": "Croatian",
}

# Admission gate: shared across every concurrent translation task.
# - cooldown_until: when a 429/Retry-After is seen the cooldown spreads to all
#   in-flight and newly arriving translation tasks until it expires.
# - emergency_lock: a single fail-fast lock. Once set by a terminal provider
#   error, no new HTTP starts are admitted; existing requests finish then wait.
# Request limits (managed via constants).
MAX_UPLOAD_FILES = 10
MAX_TARGET_LANGUAGES = 8


class AdmissionGate:
    def __init__(self):
        self._lock = threading.Lock()
        self._cooldown_until = 0.0
        self._emergency_lock = False
        self._active = 0

    def active_count(self):
        with self._lock:
            return self._active

    def admit(self, request_id):
        """Block new starts while cooldown or emergency lock is active.
        Returns True when the caller may proceed, False when rejected."""
        with self._lock:
            now = time.monotonic()
            if self._emergency_lock or now < self._cooldown_until:
                logger.info(
                    "admission_rejected request_id=%s category=admission status=429 attempt=1 wait=%.1f elapsed=0.0 active=%d",
                    request_id, max(0.0, self._cooldown_until - now), self._active,
                )
                return False
            self._active += 1
            return True

    def release(self):
        with self._lock:
            self._active = max(0, self._active - 1)

    def set_cooldown(self, wait, request_id):
        """Spread a 429/Retry-After cooldown to all concurrent tasks."""
        with self._lock:
            now = time.monotonic()
            until = now + wait
            if until > self._cooldown_until:
                self._cooldown_until = until
            logger.info(
                "admission_cooldown request_id=%s category=http status=429 attempt=1 wait=%.1f elapsed=0.0 active=%d",
                request_id, wait, self._active,
            )

    def set_terminal(self, request_id):
        """Terminal provider error: fail-fast, block new starts."""
        with self._lock:
            self._emergency_lock = True
            logger.info(
                "admission_terminal request_id=%s category=http status=terminal attempt=1 wait=0.0 elapsed=0.0 active=%d",
                request_id, self._active,
            )


ADMISSION_GATE = AdmissionGate()

# Load UI locale bundles from locales/*.json for template rendering.
LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
LOCALES = {}
for _filename in os.listdir(LOCALES_DIR):
    if _filename.endswith(".json"):
        with open(os.path.join(LOCALES_DIR, _filename), encoding="utf-8") as _fh:
            LOCALES[_filename[:-5]] = json.load(_fh)


def log_request(request_id, category, status, attempt, wait, elapsed):
    """Request-correlation log. Never logs API keys, source text, or provider payloads."""
    logger.info(
        "request_id=%s category=%s status=%s attempt=%d wait=%.2f elapsed=%.2f active=%d",
        request_id, category, status, attempt, wait, elapsed, ADMISSION_GATE.active_count(),
    )


def get_user_session_id():
    session_id = request.cookies.get("user_session")
    try:
        parsed_session_id = uuid.UUID(session_id)
        if str(parsed_session_id) == session_id.lower():
            return str(parsed_session_id)
    except (AttributeError, TypeError, ValueError):
        pass
    return str(uuid.uuid4())

# Public locale codes remain stable in filenames; NVIDIA uses es-us.
PROVIDER_CODES = {code: code.lower() for code in TARGET_LANGUAGES}
PROVIDER_CODES["es-419"] = "es-us"
PLACEHOLDER_PATTERN = re.compile(
    r"\{\{[^{}]+\}\}|\$\{[^{}]+\}|\{[^{}]+\}|%(?:\([^)]+\)|\d+\$)?[-+#0 ]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diuoxXfFeEgGcsra%]"
)


class TranslationError(Exception):
    """The provider did not return a complete, usable translation."""


class TransientTranslationError(TranslationError):
    """A temporary upstream failure persisted beyond the bounded retry policy."""


def provider_completion(request_id, **kwargs):
    """Retry only the current provider call; SDK retries stay disabled.

    Admission gate: a 429/Retry-After spreads a cooldown to every concurrent
    translation task and trips the single emergency fail-fast lock. A terminal
    provider error trips the emergency lock so no new HTTP starts are admitted;
    in-flight requests finish then wait.
    """
    start = time.monotonic()
    for attempt in range(1, 4):
        if not ADMISSION_GATE.admit(request_id):
            raise TransientTranslationError() from None
        try:
            result = client.chat.completions.create(**kwargs)
        except (APIConnectionError, APIStatusError) as exc:
            ADMISSION_GATE.release()
            status = exc.status_code if isinstance(exc, APIStatusError) else None
            elapsed = time.monotonic() - start
            if status is not None and status not in {429, 500, 502, 503, 504}:
                # Terminal provider error: fail-fast, block new starts.
                ADMISSION_GATE.set_terminal(request_id)
                log_request(request_id, "http", status, attempt, 0.0, elapsed)
                logger.warning(
                    "Terminal provider error category=%s status=%s attempt=%d",
                    category, status, attempt,
                )
                raise
            category = "http" if status is not None else "connection_or_timeout"
            wait = 0.0
            if isinstance(exc, APIStatusError):
                retry_after = exc.response.headers.get("retry-after")
                if retry_after is not None:
                    try:
                        wait = float(retry_after)
                    except ValueError:
                        try:
                            date = parsedate_to_datetime(retry_after)
                            if date.tzinfo is None:
                                date = date.replace(tzinfo=timezone.utc)
                            wait = (date - datetime.now(timezone.utc)).total_seconds()
                        except (TypeError, ValueError, OverflowError):
                            wait = 0.0
                if not (math.isfinite(wait) and wait >= 0):
                    wait = 0.0
            if wait > 5:
                # Long server-directed delay: do not retry early.
                if status == 429:
                    ADMISSION_GATE.set_cooldown(wait, request_id)
                else:
                    ADMISSION_GATE.set_terminal(request_id)
                log_request(request_id, category, status, attempt, wait, elapsed)
                logger.warning(
                    "Temporary provider failure category=%s status=%s attempt=%d/3 wait=%.1f",
                    category, status, attempt, wait,
                )
                raise TransientTranslationError() from None
            if attempt == 3:
                if status == 429 and wait > 0:
                    ADMISSION_GATE.set_cooldown(wait, request_id)
                else:
                    ADMISSION_GATE.set_terminal(request_id)
                log_request(request_id, category, status, attempt, wait, elapsed)
                logger.warning(
                    "Temporary provider failure category=%s status=%s attempt=%d/3",
                    category, status, attempt,
                )
                raise TransientTranslationError() from None
            delay = wait or (0.5 * (2 ** (attempt - 1)))
            log_request(request_id, category, status, attempt, delay, elapsed)
            logger.warning(
                "Temporary provider failure category=%s status=%s attempt=%d/3",
                category, status, attempt,
            )
            time.sleep(delay)
        except Exception:
            ADMISSION_GATE.release()
            raise
        else:
            ADMISSION_GATE.release()
            return result


def translate_text(text, target_language, source_language="en", request_id=None):
    if source_language == target_language or not isinstance(text, str) or not text.strip():
        return text
    if source_language != "en" and target_language != "en":
        intermediate = translate_text(text, "en", source_language, request_id)
        return translate_text(intermediate, target_language, "en", request_id)
    if request_id is None:
        request_id = str(uuid.uuid4())
    completion = provider_completion(
        request_id,
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": f"{PROVIDER_CODES[source_language]}-{PROVIDER_CODES[target_language]}"},
            {"role": "user", "content": text},
        ],
        temperature=0.0,
        max_tokens=4096,
    )
    choice = completion.choices[0]
    translated = choice.message.content
    if choice.finish_reason != "stop" or not isinstance(translated, str) or not translated.strip():
        raise TranslationError("Provider returned an incomplete or empty translation")
    if Counter(PLACEHOLDER_PATTERN.findall(text)) != Counter(PLACEHOLDER_PATTERN.findall(translated)):
        raise TranslationError("Provider changed localization placeholders")
    return translated.strip()


def translate_recursive_parallel(data, target_language, source_language="en", request_id=None):
    """Translate JSON string values; preserve keys, containers and scalar types."""
    if isinstance(data, dict):
        return {k: translate_recursive_parallel(v, target_language, source_language, request_id) for k, v in data.items()}
    if isinstance(data, list):
        return [translate_recursive_parallel(v, target_language, source_language, request_id) for v in data]
    if isinstance(data, str):
        return translate_text(data, target_language, source_language, request_id)
    return data

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#eef4ff">
    <title>Holm Open Translate</title>
    <link rel="icon" type="image/png" href="{{ url_for('favicon', v=1) }}">
    <script>
        (() => {
            let theme;
            try {
                theme = localStorage.getItem("holm-theme");
            } catch (error) {
                theme = null;
            }
            if (theme !== "light" && theme !== "dark") {
                theme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
            }
            document.documentElement.dataset.theme = theme;
        })();
    </script>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            color-scheme: light;
            --bg: #F8FAFC;
            --fg: #0F172A;
            --primary: #1E293B;
            --on-primary: #FFFFFF;
            --secondary: #475569;
            --on-secondary: #FFFFFF;
            --accent: #22C55E;
            --on-accent: #0F172A;
            --card: #FFFFFF;
            --card-fg: #0F172A;
            --muted: #F1F5F9;
            --muted-fg: #64748B;
            --border: #E2E8F0;
            --destructive: #EF4444;
            --on-destructive: #FFFFFF;
            --ring: #22C55E;
            --ink: var(--fg);
            --muted-text: var(--muted-fg);
            --accent-color: var(--accent);
            --glass: rgba(255,255,255,0.72);
            --glass-border: rgba(71,85,105,0.20);
            --line: rgba(71,85,105,0.12);
        }

        :root[data-theme="dark"] {
            color-scheme: dark;
            --bg: #0F172A;
            --fg: #F8FAFC;
            --primary: #1E293B;
            --on-primary: #FFFFFF;
            --secondary: #334155;
            --on-secondary: #FFFFFF;
            --accent: #22C55E;
            --on-accent: #0F172A;
            --card: #1B2336;
            --card-fg: #F8FAFC;
            --muted: #272F42;
            --muted-fg: #94A3B8;
            --border: #475569;
            --destructive: #EF4444;
            --on-destructive: #000000;
            --ring: #FFFFFF;
            --ink: var(--fg);
            --muted-text: var(--muted-fg);
            --accent-color: var(--accent);
            --glass: rgba(27, 35, 54, 0.78);
            --glass-border: rgba(71, 85, 105, 0.32);
            --line: rgba(71, 85, 105, 0.22);
        }

        * { box-sizing: border-box; }

        body {
            min-height: 100vh;
            margin: 0;
            padding: 48px 0;
            overflow-x: hidden;
            color: var(--ink);
            background: var(--bg);
            font-family: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            transition: background-color .2s ease, color .2s ease;
        }

        :root[data-theme="dark"] body {
            background:
                radial-gradient(ellipse at 12% 8%, rgba(34, 197, 94, 0.06), transparent 34rem),
                radial-gradient(ellipse at 92% 38%, rgba(30, 41, 59, 0.5), transparent 34rem),
                linear-gradient(145deg, #0b1120 0%, #0f172a 48%, #111827 100%);
        }

        h1, h2, .section-heading h2, .brand, .step-label, .eyebrow {
            font-family: "JetBrains Mono", monospace;
        }

        .app-shell { max-width: 1300px; }

        .topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 48px;
        }

        .topbar-controls {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 8px;
            flex-wrap: wrap;
        }

        .brand {
            display: inline-flex;
            align-items: center;
            gap: 11px;
            color: var(--ink);
            font-size: 15px;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        .brand-logo {
            width: 42px;
            height: 46px;
            flex: none;
            object-fit: contain;
        }

        .privacy-pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 9px 13px;
            color: var(--card-fg);
            border: 1px solid var(--glass-border);
            border-radius: 999px;
            background: var(--glass);
            box-shadow: 0 5px 16px rgba(0, 0, 0, .12), inset 0 1px 0 rgba(255,255,255,.12);
            font-size: 12px;
            font-weight: 600;
        }

        .privacy-pill i { color: var(--accent-color); }

        .control-pill {
            display: inline-flex;
            min-height: 40px;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 7px 11px;
            color: var(--card-fg);
            border: 1px solid var(--glass-border);
            border-radius: 999px;
            background: var(--glass);
            box-shadow: 0 5px 16px rgba(0, 0, 0, .12), inset 0 1px 0 rgba(255,255,255,.12);
            font-size: 12px;
            font-weight: 620;
        }

        .language-select {
            max-width: 150px;
            min-height: 40px;
            padding: 7px 30px 7px 12px;
            color: inherit;
            border: 0;
            outline: 0;
            background: transparent;
            font: inherit;
            cursor: pointer;
        }

        .language-control { padding: 0 4px 0 10px; }

        .theme-toggle {
            min-width: 42px;
            min-height: 42px;
            cursor: pointer;
        }

        .theme-toggle:hover, .language-control:focus-within {
            border-color: var(--accent-color);
            background: rgba(255,255,255,.15);
        }

        .intro { max-width: 660px; margin: 0 auto 30px; text-align: center; }

        .eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 14px;
            color: var(--accent);
            font-size: 11px;
            font-weight: 750;
            letter-spacing: .14em;
            text-transform: uppercase;
        }

        .eyebrow::before, .eyebrow::after {
            width: 18px;
            height: 1px;
            content: "";
            background: currentColor;
            opacity: .48;
        }

        h1 {
            margin: 0;
            color: var(--card-fg);
            font-size: clamp(2.15rem, 5vw, 3.25rem);
            font-weight: 720;
            letter-spacing: -.055em;
            line-height: 1.08;
        }

        .intro p {
            margin: 14px auto 0;
            color: var(--muted-fg);
            font-size: 16px;
            line-height: 1.65;
        }

        .glass-panel {
            position: relative;
            overflow: hidden;
            border: 1px solid var(--glass-border);
            border-radius: 26px;
            background: var(--glass);
            box-shadow: 0 24px 70px rgba(48, 69, 106, .11), 0 3px 12px rgba(48, 69, 106, .04), inset 0 1px 0 #fff;
            -webkit-backdrop-filter: blur(24px) saturate(155%);
            backdrop-filter: blur(24px) saturate(155%);
        }

        .translate-panel {padding: clamp(22px, 5vw, 36px); min-width: 100%; }
        .history-panel { margin-top: 20px; padding: clamp(22px, 4vw, 30px); }

        .section-heading {
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 28px;
        }

        .heading-icon {
            display: grid;
            flex: 0 0 44px;
            width: 44px;
            height: 44px;
            place-items: center;
            color: #2864db;
            border: 1px solid rgba(255,255,255,.92);
            border-radius: 15px;
            background: linear-gradient(145deg, rgba(255,255,255,.96), rgba(226,237,255,.76));
            box-shadow: 0 5px 14px rgba(41, 90, 177, .1), inset 0 1px 0 #fff;
        }

        .section-heading h2 {
            margin: 0;
            color: var(--card-fg);
            font-size: 17px;
            font-weight: 700;
            letter-spacing: -.02em;
        }

        .section-heading p {
            margin: 4px 0 0;
            color: var(--muted-fg);
            font-size: 13px;
        }

        .step-block { margin-bottom: 25px; }

        .step-label {
            display: flex;
            align-items: center;
            gap: 9px;
            margin-bottom: 11px;
            color: var(--card-fg);
            font-size: 13px;
            font-weight: 650;
        }

        .step-number {
            display: grid;
            width: 23px;
            height: 23px;
            place-items: center;
            color: var(--accent-color);
            border: 1px solid rgba(88, 127, 190, .16);
            border-radius: 50%;
            background: rgba(224, 235, 252, .75);
            font-size: 11px;
            font-weight: 700;
        }

        .file-control {
            width: 100%;
            min-height: 58px;
            padding: 10px 12px;
            color: var(--card-fg);
            border: 1px solid var(--border);
            border-radius: 15px;
            background: var(--glass);
            font-size: 13px;
        }

        .file-control::file-selector-button {
            min-height: 36px;
            margin: 0 12px 0 0;
            padding: 0 13px;
            color: var(--accent-color);
            border: 1px solid var(--border);
            border-radius: 10px;
            background: var(--muted);
            font: inherit;
            font-weight: 650;
            cursor: pointer;
            transition: background .18s ease, border-color .18s ease;
        }

        .file-control::file-selector-button:hover {
            border-color: var(--accent-color);
            background: var(--glass);
        }

        .field-hint { margin: 8px 0 0; color: var(--muted-fg); font-size: 12px; }

        .language-grid {
            max-height: 600px;
            overflow-y: auto;
            padding: 12px;
            border: 1px solid var(--border);
            border-radius: 17px;
            background: var(--glass);
            scrollbar-color: #c2cfe3 transparent;
            scrollbar-width: thin;
        }

        .language-option {
            display: flex;
            min-height: 40px;
            align-items: center;
            gap: 9px;
            padding: 8px 10px;
            border: 1px solid transparent;
            border-radius: 11px;
            cursor: pointer;
            transition: background .18s ease, border-color .18s ease;
        }

        .language-option:hover {
            border-color: var(--border);
            background: rgba(255,255,255,.12);
        }

        .language-option .form-check-input {
            flex: 0 0 auto;
            width: 17px;
            height: 17px;
            margin: 0;
            border-color: var(--border);
            cursor: pointer;
            accent-color: var(--accent-color);
        }

        .language-option .form-check-input:checked {
            border-color: var(--accent-color);
            background-color: var(--accent-color);
        }

        .language-option .form-check-label {
            color: var(--card-fg);
            font-size: 13px;
            cursor: pointer;
        }

        .language-code { color: var(--muted-fg); font-size: 11px; }

        .btn-translate {
            display: flex;
            min-height: 56px;
            align-items: center;
            justify-content: center;
            gap: 10px;
            color: var(--on-accent);
            border: 1px solid rgba(255,255,255,.32);
            border-radius: 15px;
            background: linear-gradient(135deg, #22C55E, #16A34A);
            box-shadow: 0 10px 23px rgba(34, 197, 94, .25), inset 0 1px 0 rgba(255,255,255,.28);
            font-size: 14px;
            font-weight: 680;
            letter-spacing: .005em;
            transition: transform .18s ease, box-shadow .18s ease, background .18s ease;
        }

        .btn-translate:hover {
            color: var(--on-accent);
            background: linear-gradient(135deg, #4ADE80, #15803D);
            box-shadow: 0 13px 28px rgba(34, 197, 94, .3), inset 0 1px 0 rgba(255,255,255,.28);
            transform: translateY(-1px);
        }

        .btn-translate:active { transform: translateY(0); }

        :root[data-theme="dark"] h1,
        :root[data-theme="dark"] .section-heading h2 { color: var(--card-fg); }

        :root[data-theme="dark"] .intro p,
        :root[data-theme="dark"] .section-heading p,
        :root[data-theme="dark"] .field-hint,
        :root[data-theme="dark"] .empty-state { color: var(--muted-fg); }

        :root[data-theme="dark"] .privacy-pill,
        :root[data-theme="dark"] .control-pill {
            color: var(--card-fg);
            border-color: var(--border);
            background: var(--glass);
            box-shadow: 0 5px 16px rgba(0, 0, 0, .25), inset 0 1px 0 rgba(255,255,255,.06);
        }

        :root[data-theme="dark"] .language-select { color: var(--fg); }
        :root[data-theme="dark"] .language-select option { color: var(--fg); background: var(--muted); }
        :root[data-theme="dark"] .theme-toggle:hover,
        :root[data-theme="dark"] .language-control:focus-within { background: rgba(71, 85, 105, .45); }

        :root[data-theme="dark"] .glass-panel {
            box-shadow: 0 24px 70px rgba(0, 0, 0, .35), 0 3px 12px rgba(0, 0, 0, .2), inset 0 1px 0 rgba(255,255,255,.08);
        }

        :root[data-theme="dark"] .heading-icon {
            color: var(--accent-color);
            border-color: rgba(71, 85, 105, .4);
            background: linear-gradient(145deg, rgba(30, 41, 59, .9), rgba(15, 23, 38, .86));
            box-shadow: 0 5px 14px rgba(0, 0, 0, .25), inset 0 1px 0 rgba(255,255,255,.08);
        }

        :root[data-theme="dark"] .step-label,
        :root[data-theme="dark"] .language-option .form-check-label { color: var(--card-fg); }

        :root[data-theme="dark"] .step-number {
            color: var(--muted-fg);
            border-color: rgba(71, 85, 105, .3);
            background: rgba(30, 41, 59, .7);
        }

        :root[data-theme="dark"] .file-control,
        :root[data-theme="dark"] .language-grid {
            color: var(--card-fg);
            border-color: var(--border);
            background: var(--muted);
        }

        :root[data-theme="dark"] .file-control::file-selector-button {
            color: var(--card-fg);
            border-color: rgba(71, 85, 105, .35);
            background: rgba(30, 41, 59, .7);
        }

        :root[data-theme="dark"] .file-control::file-selector-button:hover,
        :root[data-theme="dark"] .language-option:hover { background: rgba(55, 65, 81, .5); }

        :root[data-theme="dark"] .language-option:hover { border-color: rgba(71, 85, 105, .25); }
        :root[data-theme="dark"] .language-option .form-check-input { border-color: var(--border); background-color: var(--muted); }
        :root[data-theme="dark"] .language-code { color: var(--muted-fg); }
        :root[data-theme="dark"] .history-table { --bs-table-color: var(--card-fg); --bs-table-hover-color: #fff; --bs-table-hover-bg: rgba(255,255,255,.05); }
        :root[data-theme="dark"] .history-table thead th,
        :root[data-theme="dark"] .archive-date { color: var(--muted-fg); }
        :root[data-theme="dark"] .archive-name { color: var(--card-fg); }
        :root[data-theme="dark"] .archive-name i,
        :root[data-theme="dark"] .empty-icon { color: var(--accent-color); }
        :root[data-theme="dark"] .btn-download {
            color: var(--card-fg);
            border-color: var(--border);
            background: var(--glass);
        }
        :root[data-theme="dark"] .btn-download:hover {
            color: #fff;
            border-color: var(--accent-color);
            background: var(--accent-color);
        }
        :root[data-theme="dark"] .empty-icon {
            border-color: rgba(71, 85, 105, .25);
            background: var(--muted);
        }

        /* Progress bar (shadcn Progress eşdeğeri — ui-ux-pro-max tokenları ile) */
        .progress-container {
            width: 100%;
            height: 8px;
            border-radius: 999px;
            background: var(--muted);
            overflow: hidden;
            margin: 10px 0 4px;
            border: 1px solid var(--border);
            transition: border-color .2s ease, background-color .2s ease;
        }

        .progress-bar {
            height: 100%;
            width: 0%;
            background: linear-gradient(135deg, var(--accent-color), var(--accent-color));
            border-radius: 999px;
            transition: width .3s ease, background-color .3s ease;
        }

        .progress-bar[data-error="true"] {
            background: linear-gradient(135deg, var(--destructive), var(--destructive));
        }

        .progress-label {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            font-weight: 600;
            color: var(--card-fg);
            margin-bottom: 2px;
            letter-spacing: .02em;
            transition: color .2s ease;
        }

        .progress-status {
            font-size: 11px;
            color: var(--muted-fg);
            margin-bottom: 6px;
            min-height: 14px;
            transition: color .2s ease;
        }

        .progress-wrap {
            display: none;
            margin-top: 16px;
            padding: 14px 16px;
            border: 1px solid var(--border);
            border-radius: 15px;
            background: var(--glass);
            backdrop-filter: blur(12px);
            box-shadow: 0 10px 30px rgba(0,0,0,.15);
            transition: border-color .2s ease, background-color .2s ease;
        }

        .progress-success {
            display: none;
            align-items: center;
            gap: 10px;
            padding-top: 8px;
        }

        .progress-success .fa-check-circle {
            color: var(--accent-color);
            font-size: 18px;
        }

        .progress-success #progress-success-text {
            color: var(--card-fg);
            font-weight: 600;
        }

        .history-heading { margin-bottom: 18px; }

        .history-table {
            --bs-table-bg: transparent;
            --bs-table-color: var(--card-fg);
            --bs-table-hover-bg: rgba(255,255,255,.12);
            --bs-table-hover-color: var(--fg);
            margin: 0;
        }

        .history-table thead th {
            padding: 11px 12px;
            color: var(--muted-fg);
            border-bottom: 1px solid var(--line);
            font-size: 11px;
            font-weight: 700;
            letter-spacing: .07em;
            text-transform: uppercase;
        }

        .history-table tbody td {
            padding: 14px 12px;
            border-color: var(--line);
            font-size: 13px;
            color: var(--card-fg);
        }

        .archive-name {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            color: var(--accent-color);
            font-weight: 620;
            overflow-wrap: anywhere;
        }

        .archive-name i { color: var(--muted-fg); }

        .archive-date { color: var(--muted-fg); white-space: nowrap; }

        .btn-download {
            min-height: 36px;
            padding: 6px 12px;
            color: var(--card-fg);
            border: 1px solid var(--border);
            border-radius: 10px;
            background: var(--glass);
            font-size: 12px;
            font-weight: 620;
            white-space: nowrap;
            transition: background .18s ease, border-color .18s ease;
        }

        .btn-download:hover {
            color: #fff;
            border-color: var(--accent-color);
            background: var(--accent-color);
        }

        .empty-state {
            padding: 28px 16px 14px;
            color: var(--muted-fg);
            text-align: center;
            font-size: 13px;
            line-height: 1.6;
        }

        .empty-icon {
            display: grid;
            width: 44px;
            height: 44px;
            margin: 0 auto 12px;
            place-items: center;
            color: var(--muted-fg);
            border: 1px solid var(--border);
            border-radius: 15px;
            background: var(--muted);
        }

        :focus-visible {
            outline: 3px solid rgba(40, 100, 219, .52);
            outline-offset: 3px;
        }

        @media (max-width: 575.98px) {
            body { padding: 24px 0 36px; }
            .app-shell { padding-right: 18px; padding-left: 18px; }
            .topbar { margin-bottom: 38px; }
            .topbar { align-items: flex-start; }
            .topbar-controls { max-width: 210px; }
            .privacy-pill { order: 1; }
            .privacy-pill { padding: 8px 10px; font-size: 11px; }
            .control-pill { min-height: 38px; }
            .language-select { max-width: 130px; }
            .intro { margin-bottom: 24px; }
            .intro p { max-width: 330px; font-size: 15px; }
            .glass-panel { border-radius: 22px; }
            .history-table thead th, .history-table tbody td { padding-right: 8px; padding-left: 8px; }
        }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                scroll-behavior: auto !important;
                transition-duration: .01ms !important;
                animation-duration: .01ms !important;
                animation-iteration-count: 1 !important;
            }
        }
    </style>
</head>
<body>
    <main class="container app-shell">
        <header class="topbar">
            <div class="brand">
                <img class="brand-logo" src="{{ url_for('static', filename='holm-translate-logo.png') }}" alt="Holm Open Translate logo">
                <span>Holm Open Translate</span>
            </div>
            <div class="topbar-controls">
                <label class="control-pill language-control">
                    <i class="fa-solid fa-globe" aria-hidden="true"></i>
                    <span class="visually-hidden" data-i18n="interfaceLanguage">Arayüz dili</span>
                    <select class="language-select" id="interface-language" aria-label="Arayüz dili">
                        <option value="tr">Türkçe</option>
                        <option value="es">Español</option>
                        <option value="en">English</option>
                        <option value="fr">Français</option>
                        <option value="pl">Polski</option>
                        <option value="pt">Português</option>
                        <option value="de">Deutsch</option>
                        <option value="ja">日本語</option>
                        <option value="zh-TW">繁體中文</option>
                    </select>
                </label>
                <button class="control-pill theme-toggle" id="theme-toggle" type="button" data-i18n="themeDark" aria-pressed="false">
                    <i class="fa-solid fa-moon" aria-hidden="true"></i>
                    <span class="visually-hidden" id="theme-label">Koyu tema</span>
                </button>
                <div class="privacy-pill"><i class="fa-solid fa-shield-halved" aria-hidden="true"></i> <span data-i18n="privacy">Kişisel çalışma alanı</span></div>
            </div>
        </header>

        <section class="intro" aria-labelledby="page-title">
            <div class="eyebrow" data-i18n="eyebrow">JSON yerelleştirme</div>
            <h1 id="page-title" data-i18n="headline">Uygulamanızda Dil bariyerlerini ortadan kaldırın.</h1>
            <p data-i18n="intro">JSON dosyalarınızı seçin, hedef dilleri belirleyin. Çeviri arşiviniz hazır olduğunda indirin.</p>
        </section>

        <section class="glass-panel translate-panel" aria-labelledby="translate-title">
            <div class="section-heading">
                <span class="heading-icon" aria-hidden="true"><i class="fa-solid fa-arrow-up-from-bracket"></i></span>
                <div>
                    <h2 id="translate-title" data-i18n="newTranslation">Yeni çeviri oluştur</h2>
                    <p data-i18n="startHint">Başlamak için dosyalarınızı ve dilleri seçin.</p>
                </div>
            </div>

            <form action="/translate" method="post" enctype="multipart/form-data">
                <div class="step-block">
                    <label class="step-label" for="json-files">
                        <span class="step-number">1</span> <span data-i18n="stepFiles">JSON dosyalarını ekleyin</span>
                    </label>
                    <input class="form-control file-control" id="json-files" type="file" name="files" multiple accept=".json,.txt,.pdf" aria-describedby="file-hint file-limit-hint" required>
                    <p class="field-hint" id="file-hint" data-i18n="fileHint">Bir veya daha fazla .json dosyası seçebilirsiniz.</p>
                    <p class="field-hint" id="file-limit-hint" data-i18n="fileLimitHint">En fazla 10 JSON dosyası seçilebilir.</p>
                </div>

                <div class="step-block">
                    <label class="step-label" for="source-language" data-i18n="sourceLanguage">Kaynak dil</label>
                    <select class="form-select file-control" id="source-language" name="source_language" aria-describedby="source-hint">
                        {% for code, name in languages.items() %}
                        <option value="{{ code }}" {% if code == 'en' %}selected{% endif %}>{{ name }} ({{ code }})</option>
                        {% endfor %}
                    </select>
                    <p class="field-hint" id="source-hint" data-i18n="sourceHint">Dosyanın gerçek dilini seçin. Tüm listelenen dil çiftleri desteklenir. İngilizce dışındaki çiftler İngilizce üzerinden iki adımda çevrilir; süre ve API kullanımı artabilir.</p>
                </div>

                <fieldset class="step-block border-0 p-0">
                    <legend class="step-label">
                        <span class="step-number">2</span> <span data-i18n="stepLanguages">Hedef dilleri seçin</span>
                    </legend>
                    <p class="field-hint" id="language-limit-hint" data-i18n="languageLimitHint">En fazla 8 hedef dil seçilebilir.</p>
                    <div class="row g-1 language-grid">
                        {% for code, name in languages.items() %}
                        <div class="col-6 col-sm-4">
                            <label class="language-option" for="lang_{{ code }}" data-target-language="{{ code }}">
                                <input class="form-check-input" type="checkbox" name="languages" value="{{ code }}" id="lang_{{ code }}">
                                <span class="form-check-label"><span data-target-name>{{ name }}</span> <span class="language-code">({{ code }})</span></span>
                            </label>
                        </div>
                        {% endfor %}
                    </div>
                </fieldset>

                <div class="progress-wrap" id="progress-wrap" role="status" aria-live="polite" tabindex="-1">
                    <div class="progress-status" id="progress-status" data-i18n="progressPreparing">Dosya hazırlanıyor…</div>
                    <div class="progress-label">
                        <span id="progress-label" data-i18n="progressUpload">Yükleniyor</span>
                        <span id="progress-percent">0%</span>
                    </div>
                    <div class="progress-container">
                        <div class="progress-bar" id="progress-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                    <div class="progress-success" id="progress-success" style="display:none; align-items:center; gap:10px;">
                        <i class="fa-solid fa-check-circle" aria-hidden="true" style="color:var(--accent-color); font-size:18px;"></i>
                        <span id="progress-success-text" data-i18n="progressDone" style="color:var(--card-fg); font-weight:600;"></span>
                    </div>
                </div>

                <button type="submit" class="btn btn-translate w-100" id="translate-btn">
                    <i class="fa-solid fa-wand-magic-sparkles" aria-hidden="true"></i>
                    <span data-i18n="submit">Çeviriyi başlat ve arşivi indir</span>
                </button>
            </form>
        </section>

        <section class="glass-panel history-panel" aria-labelledby="history-title">
            <div class="section-heading history-heading">
                <span class="heading-icon" aria-hidden="true"><i class="fa-solid fa-clock-rotate-left"></i></span>
                <div>
                    <h2 id="history-title" data-i18n="recent">Son çeviriler</h2>
                    <p data-i18n="recentHint">Bu oturuma ait arşivleriniz.</p>
                </div>
            </div>
            {% if history %}
            <div class="table-responsive">
                <table class="table table-hover align-middle history-table">
                    <thead>
                        <tr class="text-muted small">
                            <th data-i18n="archive">Arşiv Adı</th>
                            <th data-i18n="date">Tarih</th>
                            <th class="text-end" data-i18n="action">İşlem</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in history %}
                        <tr>
                            <td><span class="archive-name"><i class="fa-regular fa-file-zipper" aria-hidden="true"></i>{{ item.filename }}</span></td>
                            <td class="archive-date">{{ item.date }}</td>
                            <td class="text-end">
                                <a href="/download/{{ item.filename }}" class="btn btn-download">
                                    <i class="fa-solid fa-download" aria-hidden="true"></i> <span data-i18n="download">İndir</span>
                                </a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% else %}
            <div class="empty-state">
                <span class="empty-icon" aria-hidden="true"><i class="fa-regular fa-folder-open"></i></span>
                <span data-i18n="emptyHistory">Bu oturuma ait bir arşiv henüz yok.<br>İlk çeviriniz tamamlandığında burada görünecek.</span>
            </div>
            {% endif %}
        </section>
    </main>
    <script>
        const translations = {{ locales | tojson | safe }};

        const languageSelect = document.getElementById("interface-language");
        const themeToggle = document.getElementById("theme-toggle");
        const themeLabel = document.getElementById("theme-label");
        const supportedLanguages = Object.keys(translations);

        function initialLanguage() {
            try {
                const saved = localStorage.getItem("holm-language");
                if (supportedLanguages.includes(saved)) return saved;
            } catch (error) {
                // Continue with the browser language when storage is unavailable.
            }

            const browserLanguage = navigator.languages
                .map((language) => language.toLowerCase())
                .map((language) => language.startsWith("zh") ? "zh-TW" : language.split("-")[0])
                .find((language) => supportedLanguages.includes(language));
            return browserLanguage || "tr";
        }

        function setLanguage(language) {
            const copy = translations[language] || translations.tr;
            document.documentElement.lang = language === "pt" ? "pt" : language;
            document.title = copy.pageTitle;
            document.querySelectorAll("[data-i18n]").forEach((element) => {
                element.innerHTML = copy[element.dataset.i18n] || translations.en[element.dataset.i18n] || translations.tr[element.dataset.i18n];
            });
            document.querySelectorAll("[data-target-language]").forEach((element) => {
                const name = copy.targets[element.dataset.targetLanguage];
                if (name) element.querySelector("[data-target-name]").textContent = name;
            });
            languageSelect.value = language;
            languageSelect.setAttribute("aria-label", copy.interfaceLanguage);
            try {
                localStorage.setItem("holm-language", language);
            } catch (error) {
                // The selected language remains active for this page view.
            }
            updateThemeLabel(copy);
        }

        function updateThemeLabel(copy = translations[languageSelect.value] || translations.tr) {
            const darkTheme = document.documentElement.dataset.theme === "dark";
            const label = darkTheme ? copy.themeLight : copy.themeDark;
            themeToggle.setAttribute("aria-label", label);
            themeToggle.setAttribute("aria-pressed", String(darkTheme));
            themeLabel.textContent = label;
            themeToggle.querySelector("i").className = darkTheme ? "fa-solid fa-sun" : "fa-solid fa-moon";
            document.querySelector('meta[name="theme-color"]').content = darkTheme ? "#111a2b" : "#eef4ff";
        }

        languageSelect.addEventListener("change", () => {
            setLanguage(languageSelect.value);
        });

        themeToggle.addEventListener("click", () => {
            const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
            document.documentElement.dataset.theme = theme;
            try {
                localStorage.setItem("holm-theme", theme);
            } catch (error) {
                // The selected theme remains active for this page view.
            }
            updateThemeLabel();
        });

        setLanguage(initialLanguage());

        /* Request feedback follows the actual response; the server has no percentage API. */
        (function () {
            const form = document.querySelector('form[action="/translate"]');
            const btn = document.getElementById("translate-btn");
            const wrap = document.getElementById("progress-wrap");
            const bar = document.getElementById("progress-bar");
            const pct = document.getElementById("progress-percent");
            const status = document.getElementById("progress-status");
            const label = document.getElementById("progress-label");
            const success = document.getElementById("progress-success");
            const successText = document.getElementById("progress-success-text");
            if (!form || !btn) return;

            form.addEventListener("submit", async function (event) {
                event.preventDefault();
                if (btn.disabled) return;
                const copy = translations[languageSelect.value] || translations.tr;
                const originalLabel = btn.innerHTML;
                const formData = new FormData(form);
                const fileInput = document.getElementById("json-files");
                const fileCount = Math.max(1, (fileInput && fileInput.files ? fileInput.files.length : 1));
                const langCount = Math.max(1, form.querySelectorAll('input[name="languages"]:checked').length);
                const totalTasks = fileCount * langCount;
                const msPerTask = 3000;
                const totalMs = totalTasks * msPerTask;
                const startTime = Date.now();
                let animationFrame;
                let completed = false;
                btn.disabled = true;
                form.setAttribute("aria-busy", "true");
                btn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>';
                wrap.style.display = "block";
                success.style.display = "none";
                bar.style.display = "block";
                bar.removeAttribute("data-error");
                status.style.display = "block";
                status.textContent = copy.progressWaiting || translations.en.progressWaiting;
                status.setAttribute("role", "status");
                label.textContent = copy.progressTranslating;
                pct.textContent = "0%";
                bar.style.width = "0%";
                bar.setAttribute("aria-valuenow", "0");
                function updateProgress() {
                    if (completed) return;
                    const elapsed = Date.now() - startTime;
                    let pctValue = Math.min(100, Math.round((elapsed / totalMs) * 100));
                    bar.style.width = pctValue + "%";
                    bar.setAttribute("aria-valuenow", String(pctValue));
                    pct.textContent = pctValue + "%";
                    if (pctValue < 100) {
                        animationFrame = requestAnimationFrame(updateProgress);
                    }
                }
                animationFrame = requestAnimationFrame(updateProgress);
                try {
                    const response = await fetch(form.action, { method: "POST", body: formData });
                    if (!response.ok) throw new Error(await response.text());
                    if (!(response.headers.get("Content-Type") || "").includes("application/zip")) {
                        throw new Error(copy.progressError || translations.en.progressError);
                    }
                    completed = true;
                    bar.style.width = "100%";
                    bar.setAttribute("aria-valuenow", "100");
                    pct.textContent = "100%";
                    const blob = await response.blob();
                    const disposition = response.headers.get("Content-Disposition") || "";
                    const match = disposition.match(/filename="?([^";]+)"?/);
                    const filename = match ? match[1] : "translations.zip";
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement("a");
                    link.href = url;
                    link.download = filename;
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                    URL.revokeObjectURL(url);
                    successText.textContent = copy.progressDone || translations.en.progressDone;
                    const retryDownload = document.createElement("a");
                    retryDownload.href = "/download/" + encodeURIComponent(filename);
                    retryDownload.textContent = " · " + copy.download;
                    successText.appendChild(retryDownload);
                    status.style.display = "none";
                    label.textContent = "";
                    success.style.display = "flex";
                } catch (error) {
                    completed = true;
                    bar.style.width = "100%";
                    bar.setAttribute("aria-valuenow", "100");
                    pct.textContent = "100%";
                    bar.setAttribute("data-error", "true");
                    label.textContent = "";
                    status.setAttribute("role", "alert");
                    status.textContent = error.message || copy.progressError || translations.en.progressError;
                    wrap.focus();
                } finally {
                    form.removeAttribute("aria-busy");
                    btn.disabled = false;
                    btn.innerHTML = originalLabel;
                }
            });
        })();
        <footer class="site-footer">
                 <p class="site-footer-text text-center small" data-i18n="footerText">© 2026 Holm Open Translate v. 0.1.61 MIT License</p>
        </footer>
</body>
</html>
"""

@app.route('/favicon.ico')
def favicon():
    return send_file(os.path.join(app.static_folder, 'favicon.ico'), mimetype='image/png')

@app.route('/')
def index():
    session_id = get_user_session_id()
    user_dir = os.path.join(BASE_OUTPUT_DIR, session_id)
    
    history = []
    if os.path.exists(user_dir):
        files = sorted(os.listdir(user_dir), key=lambda x: os.path.getmtime(os.path.join(user_dir, x)), reverse=True)
        for f in files:
            if f.endswith('.zip'):
                file_path = os.path.join(user_dir, f)
                timestamp = os.path.getmtime(file_path)
                date_str = datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M:%S')
                history.append({"filename": f, "date": date_str})

    resp = make_response(render_template_string(HTML_TEMPLATE, languages=TARGET_LANGUAGES, history=history, locales=LOCALES))
    resp.set_cookie("user_session", session_id)
    return resp

@app.route('/translate', methods=['POST'])
def translate():
    request_id = str(uuid.uuid4())
    log_request(request_id, "request", "started", 1, 0.0, 0.0)
    uploaded_files = request.files.getlist('files')
    selected_langs = list(dict.fromkeys(request.form.getlist('languages')))
    source_language = request.form.get('source_language', 'en')
    if not uploaded_files or not selected_langs:
        log_request(request_id, "request", "rejected", 1, 0.0, 0.0)
        return "Please select at least one JSON file and target language.", 400
    if len(uploaded_files) > MAX_UPLOAD_FILES:
        log_request(request_id, "request", "rejected", 1, 0.0, 0.0)
        return f"En fazla {MAX_UPLOAD_FILES} JSON dosyası seçilebilir.", 400
    if len(selected_langs) > MAX_TARGET_LANGUAGES:
        log_request(request_id, "request", "rejected", 1, 0.0, 0.0)
        return f"En fazla {MAX_TARGET_LANGUAGES} hedef dil seçilebilir.", 400
    if source_language not in TARGET_LANGUAGES or any(code not in TARGET_LANGUAGES for code in selected_langs):
        log_request(request_id, "request", "rejected", 1, 0.0, 0.0)
        return "Select valid source and target languages.", 400

    ALLOWED_EXTENSIONS = {".json", ".txt", ".pdf"}
    source_items = []
    output_names = set()
    for file in uploaded_files:
        filename = secure_filename(file.filename or '')
        if not filename:
            log_request(request_id, "request", "rejected", 1, 0.0, 0.0)
            return "Her dosya için bir dosya adı gerekli.", 400
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            log_request(request_id, "request", "rejected", 1, 0.0, 0.0)
            return "Yalnızca .json, .txt ve .pdf dosyaları kabul edilir.", 400
        base_name = os.path.splitext(filename)[0]
        try:
            if ext == ".json":
                try:
                    source_data = json.load(file)
                except (ValueError, UnicodeError):
                    log_request(request_id, "request", "rejected", 1, 0.0, 0.0)
                    return "A file contains invalid or empty JSON. Correct it and try again.", 400
                out_ext = ".json"
                translator = translate_recursive_parallel
                is_json = True
            elif ext == ".txt":
                source_data = file.read().decode("utf-8")
                out_ext = ".txt"
                translator = translate_text
                is_json = False
            else:
                reader = PdfReader(io.BytesIO(file.read()))
                source_data = "\n".join((page.extract_text() or "") for page in reader.pages)
                out_ext = ".txt"
                translator = translate_text
                is_json = False
        except Exception:
            log_request(request_id, "request", "rejected", 1, 0.0, 0.0)
            return "Dosya okunamadı veya geçerli bir metin içermiyor.", 400
        for code in selected_langs:
            output_name = f"{base_name}_{code}{out_ext}"
            if output_name in output_names:
                log_request(request_id, "request", "rejected", 1, 0.0, 0.0)
                return "Uploaded files must have distinct names.", 400
            output_names.add(output_name)
            source_items.append((output_name, code, source_data, base_name, translator, is_json))

    memory_file = io.BytesIO()
    try:
        # Reuse one English intermediate per file for all selected targets in this request.
        english_sources = {}
        if source_language != "en" and any(code != source_language for code in selected_langs):
            for _, _, data, base_name, translator, _ in source_items:
                if base_name not in english_sources or english_sources[base_name][0] is not data:
                    english_sources[base_name] = (data, translator(data, "en", source_language, request_id))
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as archive:
            with ThreadPoolExecutor(max_workers=min(len(source_items), 8)) as executor:
                futures = {
                    executor.submit(
                        translator,
                        english_sources[base_name][1] if code != source_language and base_name in english_sources else data,
                        code,
                        "en" if code != source_language and base_name in english_sources else source_language,
                        request_id,
                    ): (output_name, is_json)
                    for output_name, code, data, base_name, translator, is_json in source_items
                }
                for future in as_completed(futures):
                    output_name, is_json = futures[future]
                    translated_data = future.result()
                    if is_json:
                        payload = json.dumps(translated_data, ensure_ascii=False, indent=2).encode('utf-8')
                    else:
                        payload = translated_data.encode('utf-8') if isinstance(translated_data, str) else str(translated_data).encode('utf-8')
                    archive.writestr(output_name, payload)
    except TransientTranslationError:
        log_request(request_id, "request", "failed", 1, 0.0, 0.0)
        return "Translation service is temporarily unavailable. Automatic retries could not complete; please try again later. No partial archive was saved.", 502
    except Exception:
        # Do not publish partial archives or log user text, credentials, or provider payloads.
        logger.warning("Translation request failed; archive was not published")
        log_request(request_id, "request", "failed", 1, 0.0, 0.0)
        return "Translation failed or returned incomplete text. Check the API configuration, language pair and placeholders, then retry.", 502

    log_request(request_id, "request", "completed", 1, 0.0, 0.0)
    session_id = get_user_session_id()
    user_dir = os.path.join(BASE_OUTPUT_DIR, session_id)
    os.makedirs(user_dir, exist_ok=True)
    zip_filename = f"ceviri_arsivi_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.zip"
    with open(os.path.join(user_dir, zip_filename), 'wb') as output:
        output.write(memory_file.getvalue())
    memory_file.seek(0)
    resp = make_response(send_file(memory_file, mimetype='application/zip', as_attachment=True, download_name=zip_filename))
    resp.set_cookie("user_session", session_id)
    return resp

@app.route('/download/<filename>')
def download_history(filename):
    session_id = get_user_session_id()
    user_dir = os.path.realpath(os.path.join(BASE_OUTPUT_DIR, session_id))
    file_path = os.path.realpath(os.path.join(user_dir, filename))
    
    if os.path.commonpath((user_dir, file_path)) == user_dir and os.path.isfile(file_path):
        return send_file(file_path, as_attachment=True)
    
    return "Unauthorized access or file not found!", 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)