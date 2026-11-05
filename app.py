import os
import json
import io
import zipfile
import uuid
from datetime import datetime
from flask import Flask, render_template_string, request, send_file, make_response
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="assets")

API_KEY = os.getenv("NVIDIA_API_KEY")
BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL_NAME = "nvidia/riva-translate-4b-instruct-v2"

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

BASE_OUTPUT_DIR = os.path.join(os.getcwd(), "outputs")
os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

TARGET_LANGUAGES = {
    "en": "English",
    "ar": "Arabic", "de": "German", "es": "Spanish",
    "fr": "French", "ja": "Japanese", "ko": "Korean",
    "nl": "Dutch", "pl": "Polish", "pt": "Portuguese",
    "zh": "Chinese", "zh-TW": "Traditional Chinese",
    "tr": "Turkish", "it": "Italian", "ru": "Russian"
}

def get_user_session_id():
    session_id = request.cookies.get("user_session")
    try:
        parsed_session_id = uuid.UUID(session_id)
        if str(parsed_session_id) == session_id.lower():
            return str(parsed_session_id)
    except (AttributeError, TypeError, ValueError):
        pass
    return str(uuid.uuid4())

def translate_text(text, lang_name):
    if not isinstance(text, str) or not text.strip():
        return text
    
    prompt = f"Translate the following UI text strictly into {lang_name}. Return ONLY the translated text, nothing else:\n\n{text}"
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=256
        )
        translated = completion.choices[0].message.content.strip()
        return translated if translated else text
    except Exception:
        return text

def translate_recursive_parallel(data, lang_name):
    if isinstance(data, dict):
        return {k: translate_recursive_parallel(v, lang_name) for k, v in data.items()}
    elif isinstance(data, list):
        return [translate_recursive_parallel(item, lang_name) for item in data]
    elif isinstance(data, str):
        return translate_text(data, lang_name)
    else:
        return data

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#eef4ff">
    <title>Holm Translate</title>
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
    <style>
        :root {
            color-scheme: light;
            --ink: #17243b;
            --muted: #64748b;
            --accent: #2864db;
            --accent-dark: #174ab5;
            --glass: rgba(255, 255, 255, 0.72);
            --glass-border: rgba(255, 255, 255, 0.88);
            --line: rgba(89, 113, 151, 0.16);
        }

        :root[data-theme="dark"] {
            color-scheme: dark;
            --ink: #e7edf8;
            --muted: #b0bdd2;
            --accent: #82aaff;
            --accent-dark: #a9c2ff;
            --glass: rgba(24, 33, 51, 0.83);
            --glass-border: rgba(164, 184, 218, 0.2);
            --line: rgba(172, 190, 220, 0.15);
        }

        * { box-sizing: border-box; }

        body {
            min-height: 100vh;
            margin: 0;
            padding: 48px 0;
            overflow-x: hidden;
            color: var(--ink);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background:
                radial-gradient(ellipse at 12% 8%, rgba(166, 202, 255, 0.64), transparent 34rem),
                radial-gradient(ellipse at 92% 38%, rgba(199, 188, 255, 0.42), transparent 34rem),
                linear-gradient(145deg, #f3f7ff 0%, #edf2fb 48%, #f7f8fc 100%);
            transition: background-color .2s ease, color .2s ease;
        }

        :root[data-theme="dark"] body {
            background:
                radial-gradient(ellipse at 12% 8%, rgba(39, 72, 131, 0.36), transparent 34rem),
                radial-gradient(ellipse at 92% 38%, rgba(71, 54, 117, 0.3), transparent 34rem),
                linear-gradient(145deg, #0d1422 0%, #111a2b 48%, #101521 100%);
        }

        .app-shell { max-width: 860px; }

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
            color: #43536b;
            border: 1px solid rgba(255,255,255,.8);
            border-radius: 999px;
            background: rgba(255,255,255,.58);
            box-shadow: 0 5px 16px rgba(42, 63, 96, .05), inset 0 1px 0 #fff;
            font-size: 12px;
            font-weight: 600;
        }

        .privacy-pill i { color: #328365; }

        .control-pill {
            display: inline-flex;
            min-height: 40px;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 7px 11px;
            color: #43536b;
            border: 1px solid rgba(255,255,255,.82);
            border-radius: 999px;
            background: rgba(255,255,255,.62);
            box-shadow: 0 5px 16px rgba(42, 63, 96, .05), inset 0 1px 0 #fff;
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
            border-color: rgba(80, 119, 185, .35);
            background: rgba(255,255,255,.88);
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
            color: #192742;
            font-size: clamp(2.15rem, 5vw, 3.25rem);
            font-weight: 720;
            letter-spacing: -.055em;
            line-height: 1.08;
        }

        .intro p {
            margin: 14px auto 0;
            color: #61708a;
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

        .translate-panel { padding: clamp(22px, 5vw, 36px); }
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
            color: #1d2b45;
            font-size: 17px;
            font-weight: 700;
            letter-spacing: -.02em;
        }

        .section-heading p {
            margin: 4px 0 0;
            color: var(--muted);
            font-size: 13px;
        }

        .step-block { margin-bottom: 25px; }

        .step-label {
            display: flex;
            align-items: center;
            gap: 9px;
            margin-bottom: 11px;
            color: #34445e;
            font-size: 13px;
            font-weight: 650;
        }

        .step-number {
            display: grid;
            width: 23px;
            height: 23px;
            place-items: center;
            color: #42669f;
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
            color: #53637c;
            border: 1px solid rgba(104, 128, 166, .2);
            border-radius: 15px;
            background: rgba(255,255,255,.58);
            font-size: 13px;
        }

        .file-control::file-selector-button {
            min-height: 36px;
            margin: 0 12px 0 0;
            padding: 0 13px;
            color: #315a9f;
            border: 1px solid rgba(80, 119, 185, .19);
            border-radius: 10px;
            background: rgba(229, 238, 253, .86);
            font: inherit;
            font-weight: 650;
            cursor: pointer;
            transition: background .18s ease, border-color .18s ease;
        }

        .file-control::file-selector-button:hover {
            border-color: rgba(80, 119, 185, .34);
            background: #dce9fc;
        }

        .field-hint { margin: 8px 0 0; color: #718099; font-size: 12px; }

        .language-grid {
            max-height: 220px;
            overflow-y: auto;
            padding: 12px;
            border: 1px solid rgba(104, 128, 166, .15);
            border-radius: 17px;
            background: rgba(241, 245, 252, .58);
            scrollbar-color: #c2cfe3 transparent;
            scrollbar-width: thin;
        }

        .language-option {
            display: flex;
            min-height: 44px;
            align-items: center;
            gap: 9px;
            padding: 8px 10px;
            border: 1px solid transparent;
            border-radius: 11px;
            cursor: pointer;
            transition: background .18s ease, border-color .18s ease;
        }

        .language-option:hover {
            border-color: rgba(104, 128, 166, .11);
            background: rgba(255,255,255,.7);
        }

        .language-option .form-check-input {
            flex: 0 0 auto;
            width: 17px;
            height: 17px;
            margin: 0;
            border-color: #aab8cd;
            cursor: pointer;
        }

        .language-option .form-check-input:checked {
            border-color: var(--accent);
            background-color: var(--accent);
        }

        .language-option .form-check-label {
            color: #33435c;
            font-size: 13px;
            cursor: pointer;
        }

        .language-code { color: #8491a5; font-size: 11px; }

        .btn-translate {
            display: flex;
            min-height: 56px;
            align-items: center;
            justify-content: center;
            gap: 10px;
            color: #fff;
            border: 1px solid rgba(255,255,255,.32);
            border-radius: 15px;
            background: linear-gradient(135deg, #3979ed, #245bd0);
            box-shadow: 0 10px 23px rgba(38, 94, 207, .25), inset 0 1px 0 rgba(255,255,255,.28);
            font-size: 14px;
            font-weight: 680;
            letter-spacing: .005em;
            transition: transform .18s ease, box-shadow .18s ease, background .18s ease;
        }

        .btn-translate:hover {
            color: #fff;
            background: linear-gradient(135deg, #2e6fe2, #1d50bd);
            box-shadow: 0 13px 28px rgba(38, 94, 207, .3), inset 0 1px 0 rgba(255,255,255,.28);
            transform: translateY(-1px);
        }

        .btn-translate:active { transform: translateY(0); }

        :root[data-theme="dark"] h1,
        :root[data-theme="dark"] .section-heading h2 { color: #edf3ff; }

        :root[data-theme="dark"] .intro p,
        :root[data-theme="dark"] .section-heading p,
        :root[data-theme="dark"] .field-hint,
        :root[data-theme="dark"] .empty-state { color: #b0bdd2; }

        :root[data-theme="dark"] .privacy-pill,
        :root[data-theme="dark"] .control-pill {
            color: #dce6f6;
            border-color: rgba(174, 193, 224, .2);
            background: rgba(30, 43, 64, .75);
            box-shadow: 0 5px 16px rgba(0, 0, 0, .14), inset 0 1px 0 rgba(255,255,255,.06);
        }

        :root[data-theme="dark"] .language-select { color: #e7edf8; }
        :root[data-theme="dark"] .language-select option { color: #e7edf8; background: #182133; }
        :root[data-theme="dark"] .theme-toggle:hover,
        :root[data-theme="dark"] .language-control:focus-within { background: rgba(55, 73, 103, .85); }

        :root[data-theme="dark"] .glass-panel {
            box-shadow: 0 24px 70px rgba(0, 0, 0, .25), 0 3px 12px rgba(0, 0, 0, .12), inset 0 1px 0 rgba(255,255,255,.06);
        }

        :root[data-theme="dark"] .heading-icon {
            color: #9dbbff;
            border-color: rgba(176, 195, 228, .2);
            background: linear-gradient(145deg, rgba(62, 82, 117, .9), rgba(38, 54, 81, .86));
            box-shadow: 0 5px 14px rgba(0, 0, 0, .16), inset 0 1px 0 rgba(255,255,255,.08);
        }

        :root[data-theme="dark"] .step-label,
        :root[data-theme="dark"] .language-option .form-check-label { color: #dce6f6; }

        :root[data-theme="dark"] .step-number {
            color: #bfd1f1;
            border-color: rgba(166, 190, 230, .2);
            background: rgba(56, 76, 108, .7);
        }

        :root[data-theme="dark"] .file-control,
        :root[data-theme="dark"] .language-grid {
            color: #dce6f6;
            border-color: rgba(172, 190, 220, .2);
            background: rgba(15, 23, 38, .55);
        }

        :root[data-theme="dark"] .file-control::file-selector-button {
            color: #d5e2fb;
            border-color: rgba(156, 183, 230, .25);
            background: rgba(55, 75, 110, .7);
        }

        :root[data-theme="dark"] .file-control::file-selector-button:hover,
        :root[data-theme="dark"] .language-option:hover { background: rgba(66, 87, 124, .4); }

        :root[data-theme="dark"] .language-option:hover { border-color: rgba(172, 190, 220, .16); }
        :root[data-theme="dark"] .language-option .form-check-input { border-color: #9aaac3; background-color: #26344c; }
        :root[data-theme="dark"] .language-code { color: #9eacc2; }
        :root[data-theme="dark"] .history-table { --bs-table-color: #dce6f6; --bs-table-hover-color: #f0f5ff; --bs-table-hover-bg: rgba(255,255,255,.05); }
        :root[data-theme="dark"] .history-table thead th,
        :root[data-theme="dark"] .archive-date { color: #aebbd0; }
        :root[data-theme="dark"] .archive-name { color: #b8ceff; }
        :root[data-theme="dark"] .archive-name i,
        :root[data-theme="dark"] .empty-icon { color: #a4bcf1; }
        :root[data-theme="dark"] .btn-download {
            color: #d3e0fa;
            border-color: rgba(156, 183, 230, .25);
            background: rgba(42, 57, 82, .7);
        }
        :root[data-theme="dark"] .btn-download:hover {
            color: #fff;
            border-color: rgba(156, 183, 230, .45);
            background: rgba(62, 82, 116, .9);
        }
        :root[data-theme="dark"] .empty-icon {
            border-color: rgba(172, 190, 220, .17);
            background: rgba(48, 65, 94, .55);
        }

        .history-heading { margin-bottom: 18px; }

        .history-table {
            --bs-table-bg: transparent;
            --bs-table-color: #34445e;
            --bs-table-hover-bg: rgba(255,255,255,.48);
            --bs-table-hover-color: #1d2b45;
            margin: 0;
        }

        .history-table thead th {
            padding: 11px 12px;
            color: #7a879b;
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
        }

        .archive-name {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            color: #315b9d;
            font-weight: 620;
            overflow-wrap: anywhere;
        }

        .archive-name i { color: #668bc7; }

        .archive-date { color: #738198; white-space: nowrap; }

        .btn-download {
            min-height: 36px;
            padding: 6px 12px;
            color: #315a9f;
            border: 1px solid rgba(80, 119, 185, .22);
            border-radius: 10px;
            background: rgba(255,255,255,.55);
            font-size: 12px;
            font-weight: 620;
            white-space: nowrap;
            transition: background .18s ease, border-color .18s ease;
        }

        .btn-download:hover {
            color: #214c91;
            border-color: rgba(80, 119, 185, .38);
            background: rgba(255,255,255,.9);
        }

        .empty-state {
            padding: 28px 16px 14px;
            color: #6d7b91;
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
            color: #7893bd;
            border: 1px solid rgba(112, 142, 189, .14);
            border-radius: 15px;
            background: rgba(237, 243, 252, .8);
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
                <img class="brand-logo" src="{{ url_for('static', filename='holm-translate-logo.png') }}" alt="">
                <span>Holm Translate</span>
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
                <button class="control-pill theme-toggle" id="theme-toggle" type="button" aria-label="Koyu temayı aç" aria-pressed="false">
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
                    <input class="form-control file-control" id="json-files" type="file" name="files" multiple accept=".json" aria-describedby="file-hint" required>
                    <p class="field-hint" id="file-hint" data-i18n="fileHint">Bir veya daha fazla .json dosyası seçebilirsiniz.</p>
                </div>

                <fieldset class="step-block border-0 p-0">
                    <legend class="step-label">
                        <span class="step-number">2</span> <span data-i18n="stepLanguages">Hedef dilleri seçin</span>
                    </legend>
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

                <button type="submit" class="btn btn-translate w-100">
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
        const translations = {
            tr: {
                pageTitle: "Holm Translate — JSON çeviri çalışma alanı",
                interfaceLanguage: "Arayüz dili", themeDark: "Koyu temayı aç", themeLight: "Açık temayı aç",
                privacy: "Kişisel çalışma alanı", eyebrow: "JSON yerelleştirme",
                headline: "Uygulamanızda Dil bariyerlerini ortadan kaldırın.",
                intro: "JSON dosyalarınızı seçin, hedef dilleri belirleyin. Çeviri arşiviniz hazır olduğunda indirin.",
                newTranslation: "Yeni çeviri oluştur", startHint: "Başlamak için dosyalarınızı ve dilleri seçin.",
                stepFiles: "JSON dosyalarını ekleyin", fileHint: "Bir veya daha fazla .json dosyası seçebilirsiniz.",
                stepLanguages: "Hedef dilleri seçin", submit: "Çeviriyi başlat ve arşivi indir",
                recent: "Son çeviriler", recentHint: "Bu oturuma ait arşivleriniz.",
                archive: "Arşiv adı", date: "Tarih", action: "İşlem", download: "İndir",
                emptyHistory: "Bu oturuma ait bir arşiv henüz yok.<br>İlk çeviriniz tamamlandığında burada görünecek.",
                targets: { en: "İngilizce", ar: "Arapça", de: "Almanca", es: "İspanyolca", fr: "Fransızca", ja: "Japonca", ko: "Korece", nl: "Felemenkçe", pl: "Lehçe", pt: "Portekizce", zh: "Çince", "zh-TW": "Geleneksel Çince", tr: "Türkçe", it: "İtalyanca", ru: "Rusça" }
            },
            en: {
                pageTitle: "Holm Translate — JSON translation workspace",
                interfaceLanguage: "Interface language", themeDark: "Switch to dark mode", themeLight: "Switch to light mode",
                privacy: "Private workspace", eyebrow: "JSON localization",
                headline: "Break down language barriers in your app.",
                intro: "Choose your JSON files and target languages. Download your translation archive when it is ready.",
                newTranslation: "Create a translation", startHint: "Choose your files and languages to get started.",
                stepFiles: "Add JSON files", fileHint: "You can select one or more .json files.",
                stepLanguages: "Choose target languages", submit: "Translate and download archive",
                recent: "Recent translations", recentHint: "Your archives from this session.",
                archive: "Archive", date: "Date", action: "Action", download: "Download",
                emptyHistory: "There are no archives in this session yet.<br>Your first translation will appear here.",
                targets: { en: "English", ar: "Arabic", de: "German", es: "Spanish", fr: "French", ja: "Japanese", ko: "Korean", nl: "Dutch", pl: "Polish", pt: "Portuguese", zh: "Chinese", "zh-TW": "Traditional Chinese", tr: "Turkish", it: "Italian", ru: "Russian" }
            },
            de: {
                pageTitle: "Holm Translate — JSON-Übersetzungsbereich",
                interfaceLanguage: "Oberflächensprache", themeDark: "Dunkelmodus aktivieren", themeLight: "Hellmodus aktivieren",
                privacy: "Privater Arbeitsbereich", eyebrow: "JSON-Lokalisierung",
                headline: "Sprachbarrieren in Ihrer App überwinden.",
                intro: "Wählen Sie Ihre JSON-Dateien und Zielsprachen aus. Laden Sie das Übersetzungsarchiv herunter, sobald es fertig ist.",
                newTranslation: "Übersetzung erstellen", startHint: "Wählen Sie Dateien und Sprachen, um zu beginnen.",
                stepFiles: "JSON-Dateien hinzufügen", fileHint: "Sie können eine oder mehrere .json-Dateien auswählen.",
                stepLanguages: "Zielsprachen auswählen", submit: "Übersetzen und Archiv herunterladen",
                recent: "Letzte Übersetzungen", recentHint: "Ihre Archive aus dieser Sitzung.",
                archive: "Archiv", date: "Datum", action: "Aktion", download: "Herunterladen",
                emptyHistory: "In dieser Sitzung gibt es noch keine Archive.<br>Ihre erste Übersetzung wird hier angezeigt.",
                targets: { en: "Englisch", ar: "Arabisch", de: "Deutsch", es: "Spanisch", fr: "Französisch", ja: "Japanisch", ko: "Koreanisch", nl: "Niederländisch", pl: "Polnisch", pt: "Portugiesisch", zh: "Chinesisch", "zh-TW": "Traditionelles Chinesisch", tr: "Türkisch", it: "Italienisch", ru: "Russisch" }
            },
            fr: {
                pageTitle: "Holm Translate — espace de traduction JSON",
                interfaceLanguage: "Langue de l’interface", themeDark: "Activer le thème sombre", themeLight: "Activer le thème clair",
                privacy: "Espace de travail privé", eyebrow: "Localisation JSON",
                headline: "Brisez les barrières linguistiques dans votre application.",
                intro: "Choisissez vos fichiers JSON et les langues cibles. Téléchargez votre archive de traduction lorsqu’elle est prête.",
                newTranslation: "Créer une traduction", startHint: "Choisissez vos fichiers et vos langues pour commencer.",
                stepFiles: "Ajouter des fichiers JSON", fileHint: "Vous pouvez sélectionner un ou plusieurs fichiers .json.",
                stepLanguages: "Choisir les langues cibles", submit: "Traduire et télécharger l’archive",
                recent: "Traductions récentes", recentHint: "Vos archives de cette session.",
                archive: "Archive", date: "Date", action: "Action", download: "Télécharger",
                emptyHistory: "Aucune archive pour cette session pour le moment.<br>Votre première traduction apparaîtra ici.",
                targets: { en: "Anglais", ar: "Arabe", de: "Allemand", es: "Espagnol", fr: "Français", ja: "Japonais", ko: "Coréen", nl: "Néerlandais", pl: "Polonais", pt: "Portugais", zh: "Chinois", "zh-TW": "Chinois traditionnel", tr: "Turc", it: "Italien", ru: "Russe" }
            },
            es: {
                pageTitle: "Holm Translate — espacio de traducción JSON",
                interfaceLanguage: "Idioma de la interfaz", themeDark: "Activar modo oscuro", themeLight: "Activar modo claro",
                privacy: "Espacio de trabajo privado", eyebrow: "Localización JSON",
                headline: "Derriba las barreras del idioma en tu aplicación.",
                intro: "Elige tus archivos JSON y los idiomas de destino. Descarga el archivo de traducción cuando esté listo.",
                newTranslation: "Crear una traducción", startHint: "Elige tus archivos e idiomas para comenzar.",
                stepFiles: "Añadir archivos JSON", fileHint: "Puedes seleccionar uno o varios archivos .json.",
                stepLanguages: "Elegir idiomas de destino", submit: "Traducir y descargar el archivo",
                recent: "Traducciones recientes", recentHint: "Tus archivos de esta sesión.",
                archive: "Archivo", date: "Fecha", action: "Acción", download: "Descargar",
                emptyHistory: "Aún no hay archivos en esta sesión.<br>Tu primera traducción aparecerá aquí.",
                targets: { en: "Inglés", ar: "Árabe", de: "Alemán", es: "Español", fr: "Francés", ja: "Japonés", ko: "Coreano", nl: "Neerlandés", pl: "Polaco", pt: "Portugués", zh: "Chino", "zh-TW": "Chino tradicional", tr: "Turco", it: "Italiano", ru: "Ruso" }
            },
            pl: {
                pageTitle: "Holm Translate — przestrzeń tłumaczeń JSON",
                interfaceLanguage: "Język interfejsu", themeDark: "Włącz ciemny motyw", themeLight: "Włącz jasny motyw",
                privacy: "Prywatna przestrzeń robocza", eyebrow: "Lokalizacja JSON",
                headline: "Pokonaj bariery językowe w swojej aplikacji.",
                intro: "Wybierz pliki JSON i języki docelowe. Pobierz archiwum tłumaczeń, gdy będzie gotowe.",
                newTranslation: "Utwórz tłumaczenie", startHint: "Wybierz pliki i języki, aby rozpocząć.",
                stepFiles: "Dodaj pliki JSON", fileHint: "Możesz wybrać jeden lub więcej plików .json.",
                stepLanguages: "Wybierz języki docelowe", submit: "Przetłumacz i pobierz archiwum",
                recent: "Ostatnie tłumaczenia", recentHint: "Archiwa z tej sesji.",
                archive: "Archiwum", date: "Data", action: "Akcja", download: "Pobierz",
                emptyHistory: "W tej sesji nie ma jeszcze archiwów.<br>Pierwsze tłumaczenie pojawi się tutaj.",
                targets: { en: "Angielski", ar: "Arabski", de: "Niemiecki", es: "Hiszpański", fr: "Francuski", ja: "Japoński", ko: "Koreański", nl: "Niderlandzki", pl: "Polski", pt: "Portugalski", zh: "Chiński", "zh-TW": "Chiński tradycyjny", tr: "Turecki", it: "Włoski", ru: "Rosyjski" }
            },
            pt: {
                pageTitle: "Holm Translate — espaço de tradução JSON",
                interfaceLanguage: "Idioma da interface", themeDark: "Ativar modo escuro", themeLight: "Ativar modo claro",
                privacy: "Espaço de trabalho privado", eyebrow: "Localização JSON",
                headline: "Quebre as barreiras linguísticas em sua aplicação.",
                intro: "Escolha seus arquivos JSON e os idiomas de destino. Baixe o arquivo de tradução quando estiver pronto.",
                newTranslation: "Criar tradução", startHint: "Escolha seus arquivos e idiomas para começar.",
                stepFiles: "Adicionar arquivos JSON", fileHint: "Você pode selecionar um ou mais arquivos .json.",
                stepLanguages: "Escolher idiomas de destino", submit: "Traduzir e baixar arquivo",
                recent: "Traduções recentes", recentHint: "Seus arquivos desta sessão.",
                archive: "Arquivo", date: "Data", action: "Ação", download: "Baixar",
                emptyHistory: "Ainda não há arquivos nesta sessão.<br>Sua primeira tradução aparecerá aqui.",
                targets: { en: "Inglês", ar: "Árabe", de: "Alemão", es: "Espanhol", fr: "Francês", ja: "Japonês", ko: "Coreano", nl: "Holandês", pl: "Polonês", pt: "Português", zh: "Chinês", "zh-TW": "Chinês tradicional", tr: "Turco", it: "Italiano", ru: "Russo" }
            },
            ja: {
                pageTitle: "Holm Translate — JSON翻訳ワークスペース",
                interfaceLanguage: "表示言語", themeDark: "ダークモードに切り替え", themeLight: "ライトモードに切り替え",
                privacy: "プライベートワークスペース", eyebrow: "JSONローカライズ",
                headline: "アプリにおける言語の壁を取り払っていきましょう、",
                intro: "JSONファイルと翻訳先の言語を選択してください。翻訳アーカイブの準備ができたらダウンロードできます。",
                newTranslation: "翻訳を作成", startHint: "ファイルと言語を選択して開始します。",
                stepFiles: "JSONファイルを追加", fileHint: "1つ以上の.jsonファイルを選択できます。",
                stepLanguages: "翻訳先の言語を選択", submit: "翻訳してアーカイブをダウンロード",
                recent: "最近の翻訳", recentHint: "このセッションのアーカイブ",
                archive: "アーカイブ", date: "日付", action: "操作", download: "ダウンロード",
                emptyHistory: "このセッションにはまだアーカイブがありません。<br>最初の翻訳が完了すると、ここに表示されます。",
                targets: { en: "英語", ar: "アラビア語", de: "ドイツ語", es: "スペイン語", fr: "フランス語", ja: "日本語", ko: "韓国語", nl: "オランダ語", pl: "ポーランド語", pt: "ポルトガル語", zh: "中国語", "zh-TW": "繁体字中国語", tr: "トルコ語", it: "イタリア語", ru: "ロシア語" }
            },
            "zh-TW": {
                pageTitle: "Holm Translate — JSON 翻譯工作區",
                interfaceLanguage: "介面語言", themeDark: "切換為深色模式", themeLight: "切換為淺色模式",
                privacy: "私人工作區", eyebrow: "JSON 在地化",
                headline: "跨越語言隔閡。在您的應用程式中。",
                intro: "選擇 JSON 檔案和目標語言。翻譯封存檔準備完成後即可下載。",
                newTranslation: "建立翻譯", startHint: "選擇檔案和語言以開始。",
                stepFiles: "新增 JSON 檔案", fileHint: "可選擇一個或多個 .json 檔案。",
                stepLanguages: "選擇目標語言", submit: "開始翻譯並下載封存檔",
                recent: "最近的翻譯", recentHint: "此工作階段的封存檔。",
                archive: "封存檔", date: "日期", action: "操作", download: "下載",
                emptyHistory: "此工作階段目前沒有封存檔。<br>完成第一次翻譯後，檔案會顯示在這裡。",
                targets: { en: "英文", ar: "阿拉伯文", de: "德文", es: "西班牙文", fr: "法文", ja: "日文", ko: "韓文", nl: "荷蘭文", pl: "波蘭文", pt: "葡萄牙文", zh: "簡體中文", "zh-TW": "繁體中文", tr: "土耳其文", it: "義大利文", ru: "俄文" }
            }
        };

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
                element.innerHTML = copy[element.dataset.i18n];
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
    </script>
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

    resp = make_response(render_template_string(HTML_TEMPLATE, languages=TARGET_LANGUAGES, history=history))
    resp.set_cookie("user_session", session_id)
    return resp

@app.route('/translate', methods=['POST'])
def translate():
    session_id = get_user_session_id()
    user_dir = os.path.join(BASE_OUTPUT_DIR, session_id)
    os.makedirs(user_dir, exist_ok=True)

    uploaded_files = request.files.getlist('files')
    selected_langs = request.form.getlist('languages')

    if not uploaded_files or not selected_langs:
        return "Please select at least one file and language!", 400

    memory_file = io.BytesIO()

    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in uploaded_files:
            if not file.filename.endswith('.json'):
                continue

            base_name = os.path.splitext(file.filename)[0]
            try:
                file.stream.seek(0)
                source_data = json.load(file)
            except Exception:
                continue

            for code in selected_langs:
                lang_name = TARGET_LANGUAGES.get(code)
                translated_data = translate_recursive_parallel(source_data, lang_name)
                output_filename = f"{base_name}_{code}.json"
                json_bytes = json.dumps(translated_data, ensure_ascii=False, indent=2).encode('utf-8')
                zf.writestr(output_filename, json_bytes)

    memory_file.seek(0)
    
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_filename = f"ceviri_arsivi_{timestamp_str}.zip"
    save_path = os.path.join(user_dir, zip_filename)
    
    with open(save_path, 'wb') as f_out:
        f_out.write(memory_file.getvalue())

    memory_file.seek(0)
    
    resp = make_response(send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=zip_filename
    ))
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
    app.run(host='0.0.0.0', port=5000, debug=True)