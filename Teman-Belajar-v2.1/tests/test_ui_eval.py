from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from scripts.create_eval_fixture import CASES
from scripts.evaluate import score_case


def test_ui_sources_survive_rerun_and_document_switch_clears_history(
    monkeypatch, client, service, pdf_bytes
):
    from conftest import ingest, make_pdf
    from test_study import LearningLLM

    first = ingest(service, pdf_bytes)
    second = ingest(
        service,
        make_pdf(
            "Dokumen kedua memiliki teks yang cukup panjang untuk diproses secara native tanpa OCR."
        ),
    )
    service.llm = LearningLLM()

    def request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        response = client.request(method, "/api/v1" + url.split("/api/v1", 1)[1], **kwargs)
        return SimpleNamespace(
            ok=response.is_success, status_code=response.status_code, json=response.json
        )

    monkeypatch.setattr("requests.request", request)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "ui" / "app.py")).run()
    assert not app.exception
    app.multiselect(key="document_selection").select(first).run()
    app.chat_input[0].set_value("Pertanyaan?").run()
    assert not app.exception
    assert len(app.session_state.messages) == 2
    app.run()
    assert not app.exception
    assert any("Pendaftaran" in element.value for element in app.text), (
        app.session_state.messages,
        [element.value for element in app.text],
    )
    app.multiselect(key="document_selection").unselect(first).select(second).run()
    assert app.session_state.messages == []
    assert client.get("/api/v1/study/items").json()["items"]


def test_evaluation_proxies_and_negative_cases():
    assert len(CASES) == 30
    assert sum(page is None for _, page, _ in CASES) == 5
    case = {
        "expected_sources": [{"source": "doc.pdf", "page": 2}],
        "expected_keywords": ["Januari"],
        "expected_abstain": False,
    }
    answer = {
        "jawaban": "Januari [S1]",
        "referensi": [{"source": "doc.pdf", "page": 2, "cited": True}],
    }
    assert score_case(case, answer) == {
        "keyword_coverage": 1,
        "source_recall": 1,
        "citation_precision": 1,
        "abstention_correct": True,
    }
