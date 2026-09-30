import io

import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from config import Settings
from main import create_app
from services.rag_engine import RAGService


class FakeEmbeddings:
    def __init__(self):
        self.fail = False
        self.queries = []
        self.batch_calls = 0
        self.fail_after = None

    def embed_documents(self, texts):
        self.batch_calls += 1
        if self.fail or (self.fail_after is not None and self.batch_calls > self.fail_after):
            raise RuntimeError("provider-secret-should-not-leak")
        return [[1.0, 0.0, 0.0] for text in texts]

    def embed_query(self, text):
        self.queries.append(text)
        return [0.0, 1.0, 0.0] if "UNRELATED" in text else [1.0, 0.0, 0.0]


class FakeLLM:
    def __init__(self):
        self.calls = []
        self.answer = "Pendaftaran dibuka pada bulan Januari. [S1]"

    def invoke(self, messages):
        self.calls.append(messages)
        return AIMessage(
            content=self.answer,
            usage_metadata={"input_tokens": 30, "output_tokens": 10, "total_tokens": 40},
        )


def make_pdf(*texts):
    with fitz.open() as pdf:
        for text in texts:
            page = pdf.new_page()
            page.insert_textbox(fitz.Rect(40, 40, 550, 800), text, fontsize=11)
        return pdf.tobytes()


@pytest.fixture
def pdf_bytes():
    return make_pdf(
        "Pendaftaran siswa dibuka pada bulan Januari. Semua pendaftar harus membawa kartu identitas dan rapor terakhir."
    )


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        api_keys={"alice": "a" * 32, "bob": "b" * 32},
        requests_per_minute=500,
    )


@pytest.fixture
def service(settings):
    instance = RAGService(
        settings, FakeEmbeddings(), FakeLLM(), ocr_factory=lambda: lambda image: (None, None)
    )

    yield instance
    instance.close()


@pytest.fixture
def client(settings, service):
    with TestClient(create_app(settings, service), raise_server_exceptions=False) as test_client:
        test_client.headers["X-API-Key"] = "a" * 32
        yield test_client


def ingest(service, pdf_bytes, owner="alice", name="panduan.pdf"):
    return service.proses_dokumen(io.BytesIO(pdf_bytes), name, owner)["document"]["id"]
