import copy
import json

import pytest
from conftest import ingest, make_pdf
from langchain_core.messages import AIMessage

from services.study_service import StudyService


class LearningLLM:
    def __init__(self):
        self.calls = []
        self.transform = lambda value: value

    def invoke(self, messages, **kwargs):
        self.calls.append(messages)
        request = json.loads(messages[-1].content)
        if "schema" not in request:
            return AIMessage(content="Penjelasan materi [S1]")
        kind, count = request["mode"], request["jumlah"]
        output = {"title": "Belajar pendaftaran"}
        if kind in ("summary", "explain"):
            output["sections"] = [
                {
                    "heading": "Konsep utama",
                    "body": "Pendaftaran memerlukan kartu identitas dan rapor.",
                    "source_ids": ["S1"],
                }
            ]
        if kind == "flashcards":
            output["cards"] = [
                {
                    "front": f"Pertanyaan {i + 1}?",
                    "back": "Kartu identitas dan rapor.",
                    "source_ids": ["S1"],
                }
                for i in range(count)
            ]
        if kind == "quiz":
            output["questions"] = [
                {
                    "question": f"Apa syarat pendaftaran {i + 1}?",
                    "options": ["Kartu identitas", "Paspor", "SIM", "Tiket"],
                    "correct_index": i % 4,
                    "explanation": "Pembahasan sesuai cuplikan materi.",
                    "source_ids": ["S1"],
                }
                for i in range(count)
            ]
        return AIMessage(content=json.dumps(self.transform(output)))


@pytest.fixture
def learning(client, service, pdf_bytes):
    service.llm = LearningLLM()
    doc_id = ingest(service, pdf_bytes)
    return client, service, doc_id


def generate(client, doc_id, kind="quiz", **kwargs):
    return client.post(
        "/api/v1/study/generate",
        json={"document_ids": [doc_id], "kind": kind, "count": 3, **kwargs},
    )


@pytest.mark.parametrize("kind", ["explain", "summary", "flashcards", "quiz"])
def test_generate_grounded_material_is_saved(learning, kind):
    client, service, doc_id = learning
    response = generate(client, doc_id, kind)
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["kind"] == kind
    assert item["payload"]["references"][0]["page"] == 1
    assert item["payload"]["coverage"]["complete"]
    assert len(service.llm.calls) == 1
    assert client.get(f"/api/v1/study/items/{item['id']}").json()["id"] == item["id"]


def test_course_scope_and_cross_owner_access(learning):
    client, service, doc_id = learning
    course = client.post(
        "/api/v1/study/courses", json={"name": "Rekayasa Perangkat Lunak", "semester": "3"}
    ).json()
    course_id = course["id"]
    assert generate(client, doc_id, course_id=course_id).status_code == 409
    assert (
        client.put(
            f"/api/v1/study/courses/{course_id}/documents", json={"document_ids": [doc_id]}
        ).status_code
        == 200
    )
    item = generate(client, doc_id, "summary", course_id=course_id).json()
    bob = {"X-API-Key": "b" * 32}
    assert client.get("/api/v1/study/courses", headers=bob).json()["courses"] == []
    assert client.get(f"/api/v1/study/items/{item['id']}", headers=bob).status_code == 404
    assert (
        client.patch(
            f"/api/v1/study/items/{item['id']}/notes", headers=bob, json={"notes": "hack"}
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/v1/study/courses/{course_id}/documents",
            headers=bob,
            json={"document_ids": [doc_id]},
        ).status_code
        == 404
    )
    assert generate(client, doc_id, "summary", course_id=course_id).status_code == 201
    assert client.delete(f"/api/v1/study/courses/{course_id}").status_code == 200
    assert client.get(f"/api/v1/study/items/{item['id']}").json()["course_id"] is None
    assert service.list_documents("alice")


def test_quiz_answers_hidden_until_attempt_and_progress_uses_latest(learning):
    client, _, doc_id = learning
    item = generate(client, doc_id).json()
    question = item["payload"]["content"]["questions"][0]
    assert "correct_index" not in question and "explanation" not in question
    path = f"/api/v1/study/items/{item['id']}/attempts"
    assert client.post(path, json={"answers": [0]}).status_code == 422
    assert client.post(path, json={"answers": [0, -1, 9]}).status_code == 422
    result = client.post(path, json={"answers": [0, 1, 3]}).json()
    assert result["correct"] == 2 and result["total"] == 3
    assert result["feedback"][2]["correct_index"] == 2
    client.post(path, json={"answers": [0, 1, 2]})
    progress = client.get("/api/v1/study/progress").json()
    assert progress["quiz_sets_completed"] == 1
    assert progress["mean_latest_quiz_score"] == 100
    assert client.get(f"/api/v1/study/items/{item['id']}").json()["latest_attempt"]["score"] == 100
    assert (
        client.post(path, headers={"X-API-Key": "b" * 32}, json={"answers": [0, 1, 2]}).status_code
        == 404
    )


def test_flashcard_review_persists_and_updates_due(learning):
    client, service, doc_id = learning
    item = generate(client, doc_id, "flashcards").json()
    assert client.get("/api/v1/study/progress").json()["cards_due"] == 3
    path = f"/api/v1/study/items/{item['id']}/reviews"
    assert client.post(path, json={"card_index": 0, "rating": "good"}).json()["interval_days"] == 1
    assert client.get("/api/v1/study/progress").json()["cards_due"] == 2
    restored = StudyService(service).store.item(item["id"], "alice")
    assert restored["reviews"][0]["interval_days"] == 1
    assert client.post(path, json={"card_index": 0, "rating": "good"}).json()["interval_days"] == 2
    assert client.post(path, json={"card_index": 0, "rating": "again"}).json()["interval_days"] == 0
    assert client.post(path, json={"card_index": 8, "rating": "good"}).status_code == 404


def test_chat_can_be_resumed_after_reopening_store(learning):
    client, service, doc_id = learning
    first = client.post(
        "/api/v1/study/chat", json={"document_ids": [doc_id], "pertanyaan": "Apa syaratnya?"}
    ).json()
    restored = StudyService(service).store.item(first["id"], "alice")
    assert len(restored["payload"]["messages"]) == 2
    second = client.post(
        "/api/v1/study/chat",
        json={"document_ids": [doc_id], "pertanyaan": "Jelaskan lagi", "session_id": first["id"]},
    ).json()
    assert len(second["payload"]["messages"]) == 4
    assert service.llm.calls[-1][1].content == "Apa syaratnya?"
    assert (
        client.post(
            "/api/v1/study/chat",
            headers={"X-API-Key": "b" * 32},
            json={"document_ids": [doc_id], "pertanyaan": "Baca", "session_id": first["id"]},
        ).status_code
        == 404
    )


def test_notes_and_document_delete_cleanup_saved_sources(learning):
    client, service, doc_id = learning
    item = generate(client, doc_id, "summary").json()
    path = f"/api/v1/study/items/{item['id']}"
    assert (
        client.patch(path + "/notes", json={"notes": "Catatan dengan bahasa sendiri"}).status_code
        == 200
    )
    assert (
        StudyService(service).store.item(item["id"], "alice")["notes"]
        == "Catatan dengan bahasa sendiri"
    )
    assert client.delete(f"/api/v1/documents/{doc_id}").status_code == 200
    assert client.get(path).status_code == 404
    assert client.get("/api/v1/study/items").json()["items"] == []


def test_unknown_citation_and_invalid_schema_not_saved(learning):
    client, service, doc_id = learning

    def wrong_source(output):
        output["sections"][0]["source_ids"] = ["S999"]
        return output

    service.llm.transform = wrong_source
    assert generate(client, doc_id, "summary").status_code == 502
    service.llm.transform = lambda value: {"arbitrary": "invalid"}
    assert generate(client, doc_id, "summary").status_code == 502
    assert client.get("/api/v1/study/items").json()["items"] == []


def test_irrelevant_topic_and_model_abstention(learning):
    client, service, doc_id = learning
    assert generate(client, doc_id, "summary", topic="UNRELATED").status_code == 422
    assert service.llm.calls == []
    service.llm.transform = lambda output: {"title": "Belum cukup", "insufficient_evidence": True}
    assert generate(client, doc_id).status_code == 422
    assert client.get("/api/v1/study/items").json()["items"] == []


def test_summary_sampling_reports_partial_coverage(learning):
    client, service, _ = learning
    content = "Materi halaman ini menjelaskan konsep yang cukup panjang untuk diekstrak tanpa OCR."
    doc_id = ingest(service, make_pdf(*[f"Halaman {i}. {content}" for i in range(25)]))
    item = generate(client, doc_id, "summary").json()
    coverage = item["payload"]["coverage"]
    assert coverage["total_chunks"] == 25
    assert coverage["selected_chunks"] == 16
    assert coverage["complete"] is False
    assert coverage["pages"][0]["pages"][0] == 1
    assert coverage["pages"][0]["pages"][-1] == 25


def test_quiz_schema_rejects_duplicate_options(learning):
    client, service, doc_id = learning

    def duplicate(output):
        output["questions"][0]["options"] = ["A", "A", "C", "D"]
        return output

    service.llm.transform = duplicate
    assert generate(client, doc_id).status_code == 502


def test_chat_optimistic_update_prevents_lost_messages(learning):
    client, service, doc_id = learning
    item = client.post(
        "/api/v1/study/chat", json={"document_ids": [doc_id], "pertanyaan": "Apa syaratnya?"}
    ).json()
    store = StudyService(service).store
    updated = copy.deepcopy(item["payload"])
    store.update_chat(item["id"], "alice", updated, 0)
    from services.errors import ServiceError

    with pytest.raises(ServiceError, match="berubah"):
        store.update_chat(item["id"], "alice", updated, 0)


def test_existing_v2_material_survives_study_schema_upgrade(service, pdf_bytes):
    doc_id = ingest(service, pdf_bytes)
    with service.catalog.connect() as db:
        assert (
            db.execute("SELECT name FROM sqlite_master WHERE name='study_items'").fetchone() is None
        )
    study = StudyService(service)
    assert study.store.courses("alice") == []
    assert service.catalog.get(doc_id, "alice")["status"] == "ready"
    assert (
        service.tanya_bot("Kapan pendaftaran?", [doc_id], "alice")["referensi"][0]["document_id"]
        == doc_id
    )
