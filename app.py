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

app = Flask(__name__)

API_KEY = os.getenv("NVIDIA_API_KEY")
BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL_NAME = "nvidia/riva-translate-4b-instruct-v2"

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

BASE_OUTPUT_DIR = os.path.join(os.getcwd(), "outputs")
os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

TARGET_LANGUAGES = {
    "ar": "Arabic", "de": "German", "es": "Spanish",
    "fr": "French", "ja": "Japanese", "ko": "Korean",
    "nl": "Dutch", "pl": "Polish", "pt": "Portuguese",
    "zh": "Chinese", "tr": "Turkish", "it": "Italian", "ru": "Russian"
}

def get_user_session_id():
    session_id = request.cookies.get("user_session")
    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id

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
    <title>Holm JSON Translator Pro</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { background-color: #0b0f19; color: #f1f5f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card { background-color: #1e293b; border: 1px solid #334155; border-radius: 1rem; }
        .form-check-input:checked { background-color: #6366f1; border-color: #6366f1; }
        .btn-primary { background-color: #6366f1; border: none; }
        .btn-primary:hover { background-color: #4f46e5; }
        .table-dark { background-color: #1e293b; }
    </style>
</head>
<body class="py-5">
    <div class="container" style="max-width: 900px;">
        <div class="text-center mb-5">
            <h1 class="fw-bold text-indigo-400"><i class="fa-solid fa-shield-halved"></i> Holm Secure JSON Translator</h1>
            <p class="text-muted">Kişiye özel izole edilmiş, güvenli çoklu dil yerelleştirme paneli.</p>
        </div>

        <div class="card p-4 shadow-lg mb-5">
            <h4 class="fw-semibold mb-3 text-light"><i class="fa-solid fa-upload"></i> Yeni Çeviri Başlat</h4>
            <form action="/translate" method="post" enctype="multipart/form-data">
                <div class="mb-4">
                    <label class="form-label text-muted small fw-bold">1. JSON Dosyalarını Seçin</label>
                    <input class="form-control bg-dark text-white border-secondary py-2" type="file" name="files" multiple accept=".json" required>
                </div>

                <div class="mb-4">
                    <label class="form-label text-muted small fw-bold mb-2">2. Hedef Dilleri Seçin</label>
                    <div class="row g-2 p-3 bg-dark rounded border border-secondary" style="max-height: 200px; overflow-y: auto;">
                        {% for code, name in languages.items() %}
                        <div class="col-6 col-sm-4">
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" name="languages" value="{{ code }}" id="lang_{{ code }}">
                                <label class="form-check-label text-light small" for="lang_{{ code }}">
                                    {{ name }} <span class="text-muted">({{ code }})</span>
                                </label>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>

                <button type="submit" class="btn btn-primary w-100 py-3 fw-bold shadow-sm">
                    <i class="fa-solid fa-wand-magic-sparkles"></i> Çeviriyi Başlat ve İndir
                </button>
            </form>
        </div>

        <div class="card p-4 shadow-lg">
            <h4 class="fw-semibold mb-3 text-light"><i class="fa-solid fa-clock-rotate-left"></i> Size Özel Son Çeviriler</h4>
            {% if history %}
            <div class="table-responsive">
                <table class="table table-dark table-hover align-middle mb-0">
                    <thead>
                        <tr class="text-muted small">
                            <th>Arşiv Adı</th>
                            <th>Tarih</th>
                            <th class="text-end">İşlem</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in history %}
                        <tr>
                            <td class="fw-medium text-indigo-300"><i class="fa-regular fa-file-zipper"></i> {{ item.filename }}</td>
                            <td class="text-muted small">{{ item.date }}</td>
                            <td class="text-end">
                                <a href="/download/{{ item.filename }}" class="btn btn-sm btn-outline-light px-3">
                                    <i class="fa-solid fa-download"></i> İndir
                                </a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% else %}
            <p class="text-muted small mb-0 text-center py-3">Bu oturuma ait geçmiş çeviri arşivi bulunmuyor.</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

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
        return "Lütfen en az bir dosya ve dil seçin!", 400

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
    user_dir = os.path.join(BASE_OUTPUT_DIR, session_id)
    file_path = os.path.join(user_dir, filename)
    
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    
    return "Yetkisiz erişim veya dosya bulunamadı!", 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)