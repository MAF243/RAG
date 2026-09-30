import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("RAG_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
TIMEOUT = (5, float(os.getenv("RAG_UI_TIMEOUT", "300")))
st.set_page_config(page_title="Asisten Dokumen", page_icon="📚", layout="wide")
st.title("📚 Asisten Dokumen")
st.caption("Pilih dokumen, ajukan pertanyaan, dan periksa halaman sumber jawabannya.")

st.session_state.setdefault("messages", [])
st.session_state.setdefault("documents", [])
st.session_state.setdefault("selection", [])


def call_api(method, path, **kwargs):
    key = st.session_state.get("api_key", "")
    try:
        response = requests.request(
            method,
            API_URL + path,
            headers={"X-API-Key": key} if key else {},
            timeout=TIMEOUT,
            **kwargs,
        )
        try:
            data = response.json()
        except ValueError:
            st.error("Server mengembalikan respons yang tidak valid.")
            return None
        if not response.ok:
            detail = data.get("detail", f"Request gagal ({response.status_code}).")
            st.error(
                detail
                if isinstance(detail, str)
                else "Input tidak valid. Periksa panjang pertanyaan dan pilihan dokumen."
            )
            return None
        return data
    except requests.Timeout:
        st.error(
            "Waktu tunggu habis. Pemrosesan server mungkin masih berjalan; klik Muat dokumen sebelum mencoba upload ulang."
        )
    except requests.RequestException:
        st.error("Tidak dapat menghubungi backend. Periksa koneksi dan alamat server.")
    return None


def clear_account():
    st.session_state.messages = []
    st.session_state.documents = []
    st.session_state.selection = []
    st.session_state.pop("document_selection", None)


def show_message(message):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("referensi"):
            with st.expander("Lihat sumber dan halaman"):
                for ref in message["referensi"]:
                    label = "dikutip dalam jawaban" if ref.get("cited") else "hasil pencarian"
                    st.markdown(
                        f"**[{ref['id']}] {ref['source']} — halaman {ref['page']}** ({label})"
                    )
                    st.text(ref["text"])
        if message.get("metrics"):
            st.caption(f"Waktu respons: {message['metrics']['latency_ms'] / 1000:.1f} detik")


with st.sidebar:
    st.header("Dokumen saya")
    st.text_input(
        "API key (kosong untuk penggunaan lokal)",
        type="password",
        key="api_key",
        value=os.getenv("RAG_CLIENT_API_KEY", ""),
        on_change=clear_account,
    )
    if st.button("Muat dokumen"):
        data = call_api("GET", "/documents")
        if data is not None:
            st.session_state.documents = data["documents"]
    uploaded = st.file_uploader("Upload PDF", type=["pdf"])
    st.caption(
        "PDF teks dibaca langsung; halaman scan menggunakan OCR. Teks diproses melalui Google Gemini."
    )
    if st.button("Proses dokumen", disabled=uploaded is None):
        with st.spinner("Membaca dan mengindeks dokumen…"):
            result = call_api(
                "POST",
                "/upload",
                files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
            )
        if result:
            st.success(
                "Dokumen sudah tersimpan." if result["duplicate"] else "Dokumen siap digunakan."
            )
            data = call_api("GET", "/documents")
            if data is not None:
                st.session_state.documents = data["documents"]
                st.session_state.document_selection = [result["document"]["id"]]
    by_id = {doc["id"]: doc for doc in st.session_state.documents}
    if "document_selection" in st.session_state:
        st.session_state.document_selection = [
            doc_id for doc_id in st.session_state.document_selection if doc_id in by_id
        ]
    selected = st.multiselect(
        "Dokumen untuk percakapan (maks. 10)",
        list(by_id),
        format_func=lambda doc_id: f"{by_id[doc_id]['name']} ({by_id[doc_id]['pages']} hal.)",
        key="document_selection",
        max_selections=10,
    )
    if sorted(selected) != st.session_state.selection:
        st.session_state.messages = []
        st.session_state.selection = sorted(selected)
    if st.button("Percakapan baru"):
        st.session_state.messages = []
    with st.expander("Hapus dokumen"):
        delete_id = st.selectbox(
            "Dokumen", list(by_id), format_func=lambda doc_id: by_id[doc_id]["name"], index=None
        )
        confirmed = st.checkbox("Saya ingin menghapus indeks dokumen ini")
        if st.button("Hapus", disabled=not delete_id or not confirmed):
            if call_api("DELETE", f"/documents/{delete_id}"):
                st.session_state.documents = [
                    doc for doc in st.session_state.documents if doc["id"] != delete_id
                ]
                st.rerun()

for message in st.session_state.messages:
    show_message(message)
if not selected:
    st.info("Unggah atau muat dokumen, lalu pilih dokumen di sidebar untuk mulai bertanya.")
if prompt := st.chat_input("Tanyakan isi dokumen…", disabled=not selected, max_chars=4000):
    history = []
    total = 0
    for item in reversed(st.session_state.messages[-10:]):
        if len(item["content"]) > 4000 or total + len(item["content"]) > 12000:
            break
        history.insert(0, {"role": item["role"], "content": item["content"]})
        total += len(item["content"])
    message = {"role": "user", "content": prompt}
    show_message(message)
    with st.spinner("Mencari bukti dalam dokumen…"):
        result = call_api(
            "POST",
            "/chat",
            json={"pertanyaan": prompt, "document_ids": selected, "history": history},
        )
    if result:
        st.session_state.messages.append(message)
        reply = {
            "role": "assistant",
            "content": result["jawaban"],
            "referensi": result["referensi"],
            "metrics": result["metrics"],
        }
        st.session_state.messages.append(reply)
        show_message(reply)
