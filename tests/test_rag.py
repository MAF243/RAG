import io

import chromadb
import pytest
from conftest import FakeEmbeddings, FakeLLM, ingest, make_pdf

from services.errors import ServiceError
from services.rag_engine import NO_ANSWER, RAGService


def test_upload_keeps_existing_documents(service, pdf_bytes):
    first = ingest(service, pdf_bytes)
    second = ingest(
        service,
        make_pdf(
            "Dokumen kedua memiliki informasi lain yang cukup panjang untuk dibaca secara native tanpa OCR."
        ),
        name="kedua.pdf",
    )
    assert {d["id"] for d in service.list_documents("alice")} == {first, second}


def test_failed_embedding_preserves_old_index_and_cleans_new(service, pdf_bytes):
    first = ingest(service, pdf_bytes)
    service.embeddings.fail = True
    with pytest.raises(RuntimeError):
        ingest(
            service,
            make_pdf(
                "Dokumen kedua gagal diproses oleh penyedia embedding sehingga indeks lama harus tetap tersedia."
            ),
        )
    assert [d["id"] for d in service.list_documents("alice")] == [first]
    assert len(service.client.list_collections()) == 1
    assert service.catalog.unfinished() == []
    assert service.tanya_bot("Kapan pendaftaran?", [first], "alice")["referensi"]


def test_partial_batch_failure_is_rolled_back(service):
    service.settings.chunk_size = 100
    service.settings.chunk_overlap = 0
    service.embeddings.fail_after = 1
    content = "Ini adalah teks dokumen panjang untuk menguji kegagalan batch embedding. " * 35
    with pytest.raises(RuntimeError):
        ingest(service, make_pdf(*([content] * 5)))
    assert service.embeddings.batch_calls == 2
    assert service.client.list_collections() == []
    assert service.list_documents("alice") == []


def test_same_file_deduplicated_per_owner(service, pdf_bytes):
    first = ingest(service, pdf_bytes)
    duplicate = service.proses_dokumen(io.BytesIO(pdf_bytes), "salinan.pdf", "alice")
    assert duplicate["duplicate"] is True
    assert duplicate["document"]["id"] == first
    assert ingest(service, pdf_bytes, owner="bob") != first


def test_owner_cannot_read_or_delete_other_document(service, pdf_bytes):
    doc_id = ingest(service, pdf_bytes)
    for action in (
        lambda: service.tanya_bot("Apa isinya?", [doc_id], "bob"),
        lambda: service.delete_document(doc_id, "bob"),
    ):
        with pytest.raises(ServiceError) as exc:
            action()
        assert exc.value.status_code == 404
    assert service.embeddings.queries == []
    assert service.list_documents("bob") == []


def test_native_text_preserves_page_and_only_one_generation(service):
    pdf = make_pdf(
        "Halaman pertama menjelaskan pendaftaran siswa pada bulan Januari dan persyaratan dokumen identitas.",
        "Halaman kedua menjelaskan pembayaran biaya pendidikan dan jadwal kegiatan untuk siswa baru.",
    )
    doc_id = ingest(service, pdf)
    assert service._ocr is None
    reply = service.tanya_bot("Apa persyaratannya?", [doc_id], "alice")
    assert {ref["page"] for ref in reply["referensi"]} == {1, 2}
    assert all(ref["source"] == "panduan.pdf" for ref in reply["referensi"])
    assert len(service.llm.calls) == 1
    assert reply["referensi"][0]["cited"]
    assert reply["metrics"]["usage"]["total_tokens"] == 40


def test_low_relevance_does_not_call_llm(service, pdf_bytes):
    doc_id = ingest(service, pdf_bytes)
    reply = service.tanya_bot("UNRELATED", [doc_id], "alice")
    assert reply["jawaban"] == NO_ANSWER
    assert reply["referensi"] == []
    assert service.llm.calls == []


def test_history_used_for_retrieval_and_answer(service, pdf_bytes):
    doc_id = ingest(service, pdf_bytes)
    service.tanya_bot(
        "Apa syaratnya?", [doc_id], "alice", [{"role": "user", "content": "Pendaftaran siswa"}]
    )
    assert "Pendaftaran siswa" in service.embeddings.queries[-1]
    assert service.llm.calls[-1][1].content == "Pendaftaran siswa"


def test_invalid_citation_fails_closed(service, pdf_bytes):
    doc_id = ingest(service, pdf_bytes)
    service.llm.answer = "Jawaban palsu [S999]"
    assert service.tanya_bot("Kapan?", [doc_id], "alice")["jawaban"] == NO_ANSWER


def test_ocr_fallback(service):
    service._ocr_factory = lambda: (
        lambda image: ([[[], "Teks hasil pemindaian dari halaman pertama dokumen.", 0.99]], None)
    )
    doc_id = ingest(service, make_pdf(""))
    result = service.client.get_collection(service._collection_name(doc_id)).get()
    assert result["metadatas"][0]["extraction"] == "ocr"
    assert result["metadatas"][0]["page"] == 1


def test_page_limit_and_oversized_ocr_render(service):
    service.settings.max_pages = 1
    with pytest.raises(ServiceError, match="halaman"):
        ingest(service, make_pdf("Satu", "Dua"))
    service.settings.max_render_pixels = 1000
    with pytest.raises(ServiceError, match="terlalu besar"):
        ingest(service, make_pdf(""))
    assert service.list_documents("alice") == []


def test_empty_and_corrupt_pdf_rejected(service):
    for content in (b"not a pdf", b"%PDF- broken", make_pdf("")):
        with pytest.raises(ServiceError):
            ingest(service, content)
    assert service.list_documents("alice") == []


def test_restart_keeps_ready_and_recovers_unfinished(service, settings, pdf_bytes):
    ready_id = ingest(service, pdf_bytes)
    pending_id = "f" * 32
    service.catalog.reserve(
        pending_id, "alice", "pending.pdf", "digest", settings.embedding_model, 50
    )
    service.client.create_collection(service._collection_name(pending_id), embedding_function=None)
    service.close()
    recovered = RAGService(settings, FakeEmbeddings(), FakeLLM())
    assert [d["id"] for d in recovered.list_documents("alice")] == [ready_id]
    with pytest.raises(chromadb.errors.NotFoundError):
        recovered.client.get_collection(service._collection_name(pending_id))

    recovered.close()


def test_delete_removes_only_selected_document(service, pdf_bytes):
    alice = ingest(service, pdf_bytes)
    bob = ingest(service, pdf_bytes, owner="bob")
    service.delete_document(alice, "alice")
    assert service.list_documents("alice") == []
    assert service.list_documents("bob")[0]["id"] == bob


def test_second_backend_cannot_open_same_data_directory(service, settings):
    with pytest.raises(RuntimeError, match="satu worker"):
        RAGService(settings, FakeEmbeddings(), FakeLLM())
