import io
import json
import os
import tempfile
import zipfile
from unittest.mock import patch

from app import app, TARGET_LANGUAGES


def test_new_interface_languages_are_translation_targets():
    assert TARGET_LANGUAGES["en"] == "English"
    assert TARGET_LANGUAGES["zh-TW"] == "Traditional Chinese"

    page = app.test_client().get("/").get_data(as_text=True)
    assert 'value="en"' in page
    assert 'value="zh-TW"' in page
    assert "Traditional Chinese" in page


def test_uploaded_json_is_translated_to_english_and_traditional_chinese():
    source = {"greeting": "Hello", "nested": ["Save {name}", 3]}

    def translate_text(text, language):
        return f"{text} [{language}]"

    with tempfile.TemporaryDirectory() as output_dir:
        with patch("app.BASE_OUTPUT_DIR", output_dir), patch(
            "app.translate_text", side_effect=translate_text
        ):
            client = app.test_client()
            client.set_cookie("user_session", "test-session")
            response = client.post(
                "/translate",
                data={
                    "languages": ["en", "zh-TW"],
                    "files": (io.BytesIO(json.dumps(source).encode("utf-8")), "common.json"),
                },
                content_type="multipart/form-data",
            )

        assert response.status_code == 200
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            assert set(archive.namelist()) == {"common_en.json", "common_zh-TW.json"}
            english = json.loads(archive.read("common_en.json"))
            traditional_chinese = json.loads(archive.read("common_zh-TW.json"))

        assert english == {
            "greeting": "Hello [English]",
            "nested": ["Save {name} [English]", 3],
        }
        assert traditional_chinese == {
            "greeting": "Hello [Traditional Chinese]",
            "nested": ["Save {name} [Traditional Chinese]", 3],
        }

        saved_files = os.listdir(os.path.join(output_dir, "test-session"))
        assert len(saved_files) == 1
        assert os.path.isfile(os.path.join(output_dir, "test-session", saved_files[0]))
