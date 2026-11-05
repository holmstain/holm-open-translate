from pathlib import Path

from app import app


def test_homepage_uses_brand_assets():
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b'href="/favicon.ico?v=1"' in response.data
    assert b'src="/assets/holm-translate-logo.png"' in response.data


def test_brand_assets_are_served_as_png():
    client = app.test_client()
    assets_dir = Path(__file__).parent / "assets"

    for url, filename in (
        ("/favicon.ico", "favicon.ico"),
        ("/assets/holm-translate-logo.png", "holm-translate-logo.png"),
    ):
        response = client.get(url)

        assert response.status_code == 200
        assert response.mimetype == "image/png"
        assert response.data == (assets_dir / filename).read_bytes()
