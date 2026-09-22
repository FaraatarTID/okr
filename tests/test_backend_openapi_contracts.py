from __future__ import annotations


def test_database_backup_is_a_documented_binary_download() -> None:
    from backend_app.main import app

    response = app.openapi()["paths"]["/v1/admin/db-backup"]["get"]["responses"]["200"]

    assert response["content"] == {
        "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
    }
    assert "Content-Disposition" in response["headers"]
