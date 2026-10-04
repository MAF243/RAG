from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import ingest
from streamlit.testing.v1 import AppTest
from test_study import LearningLLM


def button(app, label):
    return next(widget for widget in app.button if widget.label == label)


def selectbox(app, label):
    return next(widget for widget in app.selectbox if widget.label == label)


@pytest.fixture
def study_app(monkeypatch, client, service, pdf_bytes):
    service.llm = LearningLLM()
    doc_id = ingest(service, pdf_bytes)

    def request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        response = client.request(method, "/api/v1" + url.split("/api/v1", 1)[1], **kwargs)
        return SimpleNamespace(
            ok=response.is_success, status_code=response.status_code, json=response.json
        )

    monkeypatch.setattr("requests.request", request)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "ui" / "app.py")).run()
    assert not app.exception
    app.multiselect(key="document_selection").select(doc_id).run()
    return app, client, doc_id


def test_quiz_ui_checks_then_restores_saved_feedback(study_app):
    app, client, _ = study_app
    app.radio(key="page").set_value("Bahan belajar").run()
    selectbox(app, "Saya ingin…").set_value("quiz")
    app.select_slider[0].set_value(3)
    button(app, "Buat bahan belajar").click().run()
    assert not app.exception
    item = app.session_state.study_item
    assert len(item["payload"]["content"]["questions"]) == 3
    assert not any("Pembahasan sesuai" in text.value for text in app.markdown)
    for index in range(3):
        app.radio(key=f"answer-{item['id']}-{index}").set_value(index)
    button(app, "Periksa jawaban").click().run()
    assert not app.exception
    assert app.metric[0].value == "100%"
    assert client.get(f"/api/v1/study/items/{item['id']}").json()["latest_attempt"]["correct"] == 3
    app.radio(key="page").set_value("Rak belajar").run()
    selectbox(app, "Hasil tersimpan").set_value(item["id"]).run()
    button(app, "Buka hasil").click().run()
    assert not app.exception
    assert app.metric[0].value == "100%"


def test_flashcard_ui_reviews_and_shows_progress(study_app):
    app, client, _ = study_app
    app.radio(key="page").set_value("Bahan belajar").run()
    selectbox(app, "Saya ingin…").set_value("flashcards")
    app.select_slider[0].set_value(3)
    button(app, "Buat bahan belajar").click().run()
    assert not app.exception
    button(app, "Sudah ingat").click().run()
    assert not app.exception
    assert app.session_state.study_item["reviews"][0]["interval_days"] == 1
    app.radio(key="page").set_value("Progres").run()
    assert not app.exception
    assert app.metric[3].value == "2"


def test_ui_create_course_assign_and_resume_chat(study_app):
    app, client, doc_id = study_app
    next(widget for widget in app.text_input if widget.label == "Nama mata kuliah").set_value(
        "Ilmu dan Akal"
    )
    next(widget for widget in app.text_input if widget.label == "Semester / periode").set_value(
        "Semester 3"
    )
    button(app, "Buat mata kuliah").click().run()
    assert not app.exception
    course = client.get("/api/v1/study/courses").json()["courses"][0]
    selectbox(app, "Mata kuliah").set_value(course["id"]).run()
    app.multiselect(key=f"assign-{course['id']}").select(doc_id)
    button(app, "Simpan pengelompokan").click().run()
    assert not app.exception
    app.multiselect(key="document_selection").select(doc_id).run()
    app.chat_input[0].set_value("Apa isi materi?").run()
    assert not app.exception
    session_id = app.session_state.session_id
    app.radio(key="page").set_value("Rak belajar").run()
    selectbox(app, "Hasil tersimpan").set_value(session_id).run()
    button(app, "Buka hasil").click().run()
    button(app, "Lanjutkan percakapan ini").click().run()
    assert not app.exception
    assert app.session_state.session_id == session_id
    assert app.session_state.page == "Tanya materi"
    assert len(app.session_state.messages) == 2
