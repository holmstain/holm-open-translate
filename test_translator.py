import os
import json
import unittest
import re
from app import translate_text, TARGET_LANGUAGES

class TestJSONTranslation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Test başlamadan önce kaynak dosyayı ve outputs klasörünü yükler."""
        cls.source_file = "common.json"
        cls.output_dir = "outputs"
        
        # Orijinal JSON dosyasını oku
        if os.path.exists(cls.source_file):
            with open(cls.source_file, "r", encoding="utf-8") as f:
                cls.source_data = json.load(f)
        else:
            cls.source_data = {}

    def get_all_keys_and_placeholders(self, data, prefix=""):
        """JSON içindeki tüm anahtarları ve metin içi {placeholder} değişkenlerini çıkarır."""
        keys_info = {}
        if isinstance(data, dict):
            for k, v in data.items():
                full_key = f"{prefix}.{k}" if prefix else k
                keys_info.update(self.get_all_keys_and_placeholders(v, full_key))
        elif isinstance(data, str):
            # {name}, %s gibi değişkenleri düzenli ifade (regex) ile bul
            placeholders = re.findall(r"\{.*?\}|%s|%d", data)
            keys_info[prefix] = placeholders
        return keys_info

    def test_01_api_live_translation(self):
        """1. NVIDIA NIM API'sinin canlı çeviri işlevini test eder."""
        print("\n[TEST] API canlı çeviri testi yapılıyor...")
        test_text = "Hello, welcome!"
        translated = translate_text(test_text, "Turkish")
        
        self.assertIsNotNone(translated, "API yanıtı None olamaz.")
        self.assertNotEqual(translated, "", "API boş metin döndürdü.")
        print(f"  -> Test Metni: '{test_text}' | Çeviri: '{translated}'")

    def test_02_output_files_exist_and_valid(self):
        """2. Oluşturulan dil dosyalarının varlığını ve geçerli JSON olup olmadığını kontrol eder."""
        print("\n[TEST] Çevrilmiş JSON dosyalarının yapısal kontrolü yapılıyor...")
        
        if not os.path.exists(self.output_dir):
            self.skipTest("Henüz hiç çeviri yapılmamış (outputs klasörü yok).")

        # Son üretilen ZIP/JSON'ların açıldığı veya kaydedildiği dosyaları denetle
        for code in TARGET_LANGUAGES.keys():
            file_path = os.path.join(self.output_dir, f"common_{code}.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        translated_json = json.load(f)
                        self.assertIsInstance(translated_json, dict, f"{file_path} bir JSON objesi değil.")
                    except json.JSONDecodeError:
                        self.fail(f"{file_path} geçerli bir JSON dosyası değil!")

    def test_03_keys_and_placeholders_integrity(self):
        """3. Çevrilen dosyaların anahtar kaybetmediğini ve {variable} yapılarını koruduğunu doğrular."""
        print("\n[TEST] Değişken (placeholder) ve Anahtar (keys) bütünlük testi yapılıyor...")
        
        if not self.source_data:
            self.skipTest("Kaynak common.json dosyası bulunamadı.")

        source_info = self.get_all_keys_and_placeholders(self.source_data)

        # Üretilen her dil dosyasını denetle
        for root, _, files in os.walk(self.output_dir):
            for file in files:
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        translated_data = json.load(f)
                    
                    translated_info = self.get_all_keys_and_placeholders(translated_data)

                    # 1. Eksik anahtar kontrolü
                    for key in source_info.keys():
                        self.assertIn(key, translated_info, f"Eksik Anahtar! '{file}' dosyası '{key}' anahtarını içermiyor.")

                    # 2. Değişken koruma kontrolü (örneğin {user_name} silindi mi?)
                    for key, expected_placeholders in source_info.items():
                        if key in translated_info:
                            actual_placeholders = translated_info[key]
                            for ph in expected_placeholders:
                                self.assertIn(
                                    ph, 
                                    actual_placeholders, 
                                    f"Bozuk Değişken! '{file}' içindeki '{key}' anahtarında '{ph}' değişkeni kaybolmuş!"
                                )

if __name__ == "__main__":
    unittest.main()