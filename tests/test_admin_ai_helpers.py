from __future__ import annotations

from types import SimpleNamespace

from src.ui import dialogs_admin_ai_helpers


class _FakeCol:
    def __init__(self, *, parent):
        self._parent = parent

    def metric(self, label, value):
        self._parent.metric_calls.append((str(label), str(value)))

    def button(self, _label, key=None, **_kwargs):
        lookup = str(key or "")
        return bool(self._parent.button_presses.get(lookup, False))


class _FakeSpinner:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSt:
    def __init__(self):
        self.session_state = {}
        self.button_presses = {}
        self.metric_calls = []
        self.markdown_calls = []
        self.caption_calls = []
        self.info_calls = []
        self.warning_calls = []
        self.error_calls = []
        self.success_calls = []
        self.json_calls = []
        self.download_calls = []
        self.rerun_calls = 0

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def caption(self, value):
        self.caption_calls.append(str(value))

    def columns(self, spec, **_kwargs):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeCol(parent=self) for _ in range(count)]

    def info(self, value):
        self.info_calls.append(str(value))

    def warning(self, value):
        self.warning_calls.append(str(value))

    def error(self, value):
        self.error_calls.append(str(value))

    def success(self, value):
        self.success_calls.append(str(value))

    def json(self, value):
        self.json_calls.append(value)

    def download_button(self, **kwargs):
        self.download_calls.append(dict(kwargs))

    def spinner(self, _value):
        return _FakeSpinner()

    def rerun(self):
        self.rerun_calls += 1


def _patch_ai_provider(monkeypatch):
    import src.services.ai_provider as ai_provider

    monkeypatch.setattr(
        ai_provider,
        "get_ai_provider_runtime_status",
        lambda: SimpleNamespace(provider="gemini", ready=True, message="AI configured"),
    )
    monkeypatch.setattr(ai_provider, "is_external_ai_allowed", lambda: True)
    monkeypatch.setattr(
        ai_provider,
        "run_ai_health_check",
        lambda *, live_probe: {"status": "ok", "live_probe": bool(live_probe)},
    )


def test_render_ai_health_includes_pdf_diagnostics_for_chromium_runtime_error(
    monkeypatch,
):
    fake_st = _FakeSt()
    _patch_ai_provider(monkeypatch)

    import src.services.pdf_service as pdf_service

    monkeypatch.setattr(
        pdf_service,
        "get_pdf_runtime_diagnostics",
        lambda: {
            "environment": "Secure mode",
            "platform": "Linux",
            "method": "chromium",
            "supported_method": True,
            "playwright_available": False,
            "pdfshift_available": True,
            "pdfshift_api_key_configured": False,
            "chromium_executable_path": "",
            "chromium_executable_detected": False,
            "streamlit_cloud_runtime": True,
        },
    )
    monkeypatch.setattr(dialogs_admin_ai_helpers, "st", fake_st)

    dialogs_admin_ai_helpers.render_ai_health_tab_content()

    assert ("Method", "chromium") in fake_st.metric_calls
    assert ("Playwright", "Missing") in fake_st.metric_calls
    assert ("PDFShift Key", "Missing") in fake_st.metric_calls
    assert any(
        "PDF_METHOD=chromium but Playwright is not installed." in msg
        for msg in fake_st.error_calls
    )
    assert any(
        isinstance(payload, dict) and payload.get("method") == "chromium"
        for payload in fake_st.json_calls
    )


def test_render_ai_health_includes_pdf_diagnostics_for_pdfshift_ready(monkeypatch):
    fake_st = _FakeSt()
    _patch_ai_provider(monkeypatch)

    import src.services.pdf_service as pdf_service

    monkeypatch.setattr(
        pdf_service,
        "get_pdf_runtime_diagnostics",
        lambda: {
            "environment": "Secure mode",
            "platform": "Linux",
            "method": "pdfshift",
            "supported_method": True,
            "playwright_available": True,
            "pdfshift_available": True,
            "pdfshift_api_key_configured": True,
            "chromium_executable_path": "/usr/bin/chromium",
            "chromium_executable_detected": True,
            "streamlit_cloud_runtime": True,
        },
    )
    monkeypatch.setattr(dialogs_admin_ai_helpers, "st", fake_st)

    dialogs_admin_ai_helpers.render_ai_health_tab_content()

    assert ("Method", "pdfshift") in fake_st.metric_calls
    assert ("PDFShift Key", "Set") in fake_st.metric_calls
    assert "PDFShift runtime appears configured." in fake_st.success_calls
