from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from scripts.create_eval_fixture import CASES
from scripts.evaluate import score_case


def test_ui_sources_survive_rerun_and_document_switch_clears_history(monkeypatch):
    docs = [
        {"id": "a" * 32, "name": "doc.pdf", "pages": 1},
        {"id": "b" * 32, "name": "other.pdf", "pages": 1},
    ]

    def request(method, url, **kwargs):
        if url.endswith("/documents"):
            data = {"documents": docs}
        else:
            data = {
                "jawaban": "Jawaban [S1]",
                "referensi": [
                    {
                        "id": "S1",
                        "source": "doc.pdf",
                        "page": 1,
                        "text": "Bukti asli",
                        "cited": True,
                    }
                ],
                "metrics": {"latency_ms": 10},
            }
        return SimpleNamespace(ok=True, json=lambda: data)

    monkeypatch.setattr("requests.request", request)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "ui" / "app.py")).run()
    assert not app.exception
    app.button[0].click().run()
    app.multiselect[0].select("a" * 32).run()
    app.chat_input[0].set_value("Pertanyaan?").run()
    assert not app.exception
    assert len(app.session_state.messages) == 2
    app.run()
    assert any("Bukti asli" in element.value for element in app.text)
    app.multiselect[0].unselect("a" * 32).select("b" * 32).run()
    assert app.session_state.messages == []


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
