import os
import json
from openai import OpenAI

# NVIDIA NIM API Bilgileri (Çalıştığı test edilen anahtarın)
API_KEY = "[REDACTED_NVIDIA_API_KEY]"
BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL_NAME = "nvidia/riva-translate-4b-instruct-v2"

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

target_languages = {
    "ar": "Arabic",
    "de": "German",
    "es": "Spanish",
    "fr": "French",
    "ja": "Japanese",
    "ko": "Korean",
    "nl": "Dutch",
    "pl": "Polish",
    "pt": "Portuguese",
    "zh": "Chinese",
    "tr": "Turkish",
    "it": "Italian",
    "ru": "Russian"
}

source_filename = "common.json"

if not os.path.exists(source_filename):
    print(f"Hata: Kaynak dosya ({source_filename}) bulunamadı!")
    exit()

with open(source_filename, "r", encoding="utf-8") as f:
    source_data = json.load(f)

def translate_recursive(data, lang_name):
    """JSON içindeki tüm metin değerlerini güvenle çevirir, anahtarları korur."""
    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            new_dict[k] = translate_recursive(v, lang_name)
        return new_dict
    elif isinstance(data, list):
        return [translate_recursive(item, lang_name) for item in data]
    elif isinstance(data, str):
        prompt = f"Translate the following UI text strictly into {lang_name}. Return ONLY the translated text, nothing else:\n\n{data}"
        try:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=256
            )
            translated = completion.choices[0].message.content.strip()
            return translated if translated else data
        except Exception as e:
            print(f"Çeviri hatası ('{data}'): {e}")
            return data
    else:
        return data

print(f"Kaynak dosya okundu ({source_filename}), güvenli çeviri süreci başlatılıyor...\n")

for code, lang_name in target_languages.items():
    output_filename = f"{code}.json"
    print(f"-> {lang_name} ({output_filename}) çevriliyor...")
    
    # Veriyi çevir
    translated_data = translate_recursive(source_data, lang_name)
    
    # Dosyaya kaydet
    with open(output_filename, "w", encoding="utf-8") as out_f:
        json.dump(translated_data, out_f, ensure_ascii=False, indent=2)
        
    print(f"   [BAŞARILI] {output_filename} kaydedildi.")

print("\nTüm çeviri işlemleri başarıyla tamamlandı!")