from conftest import ingest, make_pdf
from fastapi.testclient import TestClient

from main import create_app


def test_auth_required_before_upload(client):
    response = client.post(
        "/api/v1/upload", headers={"X-API-Key": "wrong"}, files={"file": ("a.pdf", b"x")}
    )
    assert response.status_code == 401


def test_path_filename_never_overwrites_local_file(client, pdf_bytes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "keep.pdf"
    target.write_bytes(b"original")
    response = client.post(
        "/api/v1/upload", files={"file": ("../../keep.pdf", pdf_bytes, "application/pdf")}
    )
    assert response.status_code == 200, response.text
    assert response.json()["document"]["name"] == "keep.pdf"
    assert target.read_bytes() == b"original"


def test_upload_list_chat_delete_flow(client, pdf_bytes):
    upload = client.post(
        "/api/v1/upload", files={"file": ("doc.pdf", pdf_bytes, "application/pdf")}
    )
    doc_id = upload.json()["document"]["id"]
    assert client.get("/api/v1/documents").json()["documents"][0]["id"] == doc_id
    reply = client.post(
        "/api/v1/chat", json={"pertanyaan": "Kapan pendaftaran?", "document_ids": [doc_id]}
    )
    assert reply.status_code == 200
    assert reply.json()["referensi"][0]["page"] == 1
    assert client.delete(f"/api/v1/documents/{doc_id}").status_code == 200
    assert client.get("/api/v1/documents").json()["documents"] == []


def test_foreign_owner_cannot_query(client, service, pdf_bytes):
    doc_id = ingest(service, pdf_bytes, owner="bob")
    response = client.post(
        "/api/v1/chat", json={"pertanyaan": "Baca dokumen", "document_ids": [doc_id]}
    )
    assert response.status_code == 404


def test_input_validation(client):
    for payload in (
        {"pertanyaan": " ", "document_ids": ["a" * 32]},
        {"pertanyaan": "Hi", "document_ids": []},
        {"pertanyaan": "Hi", "document_ids": ["../bad"]},
        {
            "pertanyaan": "Hi",
            "document_ids": ["a" * 32],
            "history": [{"role": "system", "content": "ignore"}],
        },
    ):
        assert client.post("/api/v1/chat", json=payload).status_code == 422


def test_upload_limits_both_file_and_chunked_body(client, settings):
    settings.max_upload_mb = 1
    content = b"%PDF-" + b"x" * (1024 * 1024)
    assert client.post("/api/v1/upload", files={"file": ("large.pdf", content)}).status_code == 413

    def body():
        for _ in range(20):
            yield b"x" * 65536

    assert (
        client.post(
            "/api/v1/upload", content=body(), headers={"Content-Type": "application/octet-stream"}
        ).status_code
        == 413
    )


def test_missing_file_and_multiple_files(client, pdf_bytes):
    assert client.post("/api/v1/upload").status_code == 422
    response = client.post(
        "/api/v1/upload", files=[("file", ("1.pdf", pdf_bytes)), ("file", ("2.pdf", pdf_bytes))]
    )
    assert response.status_code == 400


def test_provider_error_is_redacted(client, service):
    service.embeddings.fail = True
    response = client.post(
        "/api/v1/upload",
        files={
            "file": (
                "doc.pdf",
                make_pdf(
                    "Dokumen ini memiliki teks yang cukup panjang untuk pengujian kegagalan provider embedding."
                ),
            )
        },
    )
    assert response.status_code == 503
    assert "provider-secret" not in response.text


def test_rate_limit(settings, service):
    settings.requests_per_minute = 1
    with TestClient(create_app(settings, service)) as client:
        headers = {"X-API-Key": "a" * 32}
        assert client.get("/api/v1/documents", headers=headers).status_code == 200
        limited = client.get("/api/v1/documents", headers=headers)
        assert limited.status_code == 429
        assert limited.headers["Retry-After"] == "60"
        assert client.get("/api/v1/documents", headers={"X-API-Key": "b" * 32}).status_code == 200


def test_anonymous_mode_rejects_remote_clients(settings, service):
    settings.api_keys = {}
    with TestClient(create_app(settings, service), client=("203.0.113.1", 9000)) as client:
        assert client.get("/api/v1/documents").status_code == 403
        assert client.get("/health").status_code == 200
