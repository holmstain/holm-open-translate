import os
import tempfile
import uuid
from unittest.mock import patch

from app import app


def test_download_rejects_path_from_untrusted_session_cookie():
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = os.path.join(temp_dir, "outputs")
        outside_file = os.path.join(temp_dir, "private.txt")
        with open(outside_file, "w", encoding="utf-8") as file:
            file.write("private")

        with patch("app.BASE_OUTPUT_DIR", output_dir):
            client = app.test_client()
            client.set_cookie("user_session", temp_dir)
            response = client.get("/download/private.txt")

        assert response.status_code == 403


def test_download_still_serves_archive_from_valid_session():
    with tempfile.TemporaryDirectory() as output_dir:
        session_id = str(uuid.uuid4())
        session_dir = os.path.join(output_dir, session_id)
        os.makedirs(session_dir)
        archive_path = os.path.join(session_dir, "translation.zip")
        with open(archive_path, "wb") as archive:
            archive.write(b"archive")

        with patch("app.BASE_OUTPUT_DIR", output_dir):
            client = app.test_client()
            client.set_cookie("user_session", session_id)
            response = client.get("/download/translation.zip")

        assert response.status_code == 200
        assert response.data == b"archive"
