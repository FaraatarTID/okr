from pathlib import Path

from scripts import verify_secret_hygiene
from tests._test_credentials import credential_password


def test_verify_secret_hygiene_flags_inline_password(tmp_path: Path) -> None:
    sample = tmp_path / "fixture.py"
    payload = (
        'password = "' + credential_password("inline_disallowed") + '"\n'
    )
    sample.write_text(payload, encoding="utf-8")

    findings = verify_secret_hygiene._scan_file(sample)
    assert len(findings) == 1
    assert str(sample) in findings[0]


def test_verify_secret_hygiene_allows_structured_test_password_helper(tmp_path: Path) -> None:
    sample = tmp_path / "fixture.py"
    sample.write_text(
        'from tests._test_credentials import credential_password as test_password\n'
        'password = test_password("admin")\n',
        encoding="utf-8",
    )

    findings = verify_secret_hygiene._scan_file(sample)
    assert findings == []


def test_verify_secret_hygiene_allows_hashed_password_fixture(tmp_path: Path) -> None:
    sample = tmp_path / "fixture.py"
    sample.write_text(
        'password_hash = crud.hash_password("E2E-Atlas-Password-123")\n',
        encoding="utf-8",
    )

    findings = verify_secret_hygiene._scan_file(sample)
    assert findings == []
