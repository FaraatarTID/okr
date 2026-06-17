from src.ui import styles


def _capture_markdown(monkeypatch):
    calls = []

    def _fake_markdown(body, unsafe_allow_html=False):
        calls.append((body, unsafe_allow_html))

    monkeypatch.setattr(styles.st, "markdown", _fake_markdown)
    return calls


def test_inject_style_block_forwards_unsafe_html(monkeypatch):
    calls = _capture_markdown(monkeypatch)

    styles._inject_style_block("<style>.x{color:red;}</style>")

    assert calls == [("<style>.x{color:red;}</style>", True)]


def test_inject_dialog_styles_emits_dialog_css(monkeypatch):
    calls = _capture_markdown(monkeypatch)

    styles.inject_dialog_styles()

    assert len(calls) == 1
    body, unsafe_allow_html = calls[0]
    assert unsafe_allow_html is True
    assert "<style>" in body
    assert '[data-testid="stDialog"] ::-webkit-scrollbar' in body
    assert '[data-testid="stDialog"] ::-webkit-scrollbar-thumb' in body


def test_apply_custom_fonts_emits_font_and_timer_css(monkeypatch):
    calls = _capture_markdown(monkeypatch)

    styles.apply_custom_fonts()

    assert len(calls) == 1
    body, unsafe_allow_html = calls[0]
    assert unsafe_allow_html is True
    assert "Vazirmatn" in body
    assert ".timer-display" in body
    assert "@media (max-width: 900px)" in body


def test_inject_atlas_styles_emits_atlas_theme_css(monkeypatch):
    calls = _capture_markdown(monkeypatch)

    styles.inject_atlas_styles()

    assert len(calls) == 1
    body, unsafe_allow_html = calls[0]
    assert unsafe_allow_html is True
    assert "--atlas-border: #e5dccb;" in body
    assert '[class*="st-key-atlas_spotlight_start_"]' in body
    assert ".atlas-score-band-green" in body
