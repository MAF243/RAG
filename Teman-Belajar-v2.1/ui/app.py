import os

import requests
import streamlit as st
from dotenv import load_dotenv

from ui.study_views import KINDS, show_learning_item, show_message, unique_label

load_dotenv()
API_URL = os.getenv("RAG_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
TIMEOUT = (5, float(os.getenv("RAG_UI_TIMEOUT", "300")))
st.set_page_config(page_title="Teman Belajar", page_icon="📚", layout="wide")
st.title("📚 Teman Belajar")
st.caption("Pahami materi kuliah, uji ingatanmu, dan lanjutkan belajar dari tempat terakhir.")

DEFAULTS = {
    "messages": [],
    "documents": [],
    "courses": [],
    "selection": [],
    "active_course": None,
    "session_id": None,
    "study_item": None,
    "library": None,
    "progress": None,
    "loaded": False,
}
for name, value in DEFAULTS.items():
    st.session_state.setdefault(name, value)
if target := st.session_state.pop("next_page", None):
    st.session_state.page = target
if item := st.session_state.pop("resume_item", None):
    st.session_state.course_selection = item["course_id"]
    st.session_state.document_selection = item["document_ids"]
    st.session_state.active_course = item["course_id"]
    st.session_state.selection = sorted(item["document_ids"])
    st.session_state.session_id = item["id"]
    st.session_state.messages = item["payload"]["messages"]


def clear_account():
    for key in list(st.session_state):
        if key != "api_key":
            del st.session_state[key]


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
                else "Input belum sesuai. Periksa isian dan pilihan materi."
            )
            return None
        return data
    except requests.Timeout:
        st.error(
            "Waktu tunggu habis. Proses mungkin masih berjalan; muat ulang daftar materi atau rak belajar sebelum mencoba lagi."
        )
    except requests.RequestException:
        st.error(
            "Belum terhubung ke backend. Pastikan server sudah berjalan, lalu klik Muat ruang belajar."
        )
    return None


def invalidate():
    st.session_state.library = None
    st.session_state.progress = None


def refresh_workspace():
    docs = call_api("GET", "/documents")
    courses = call_api("GET", "/study/courses")
    if docs is not None and courses is not None:
        st.session_state.documents = docs["documents"]
        st.session_state.courses = courses["courses"]
    invalidate()
    st.session_state.loaded = True


def refresh_item(item_id):
    result = call_api("GET", f"/study/items/{item_id}")
    if result:
        st.session_state.study_item = result
    invalidate()


with st.sidebar:
    st.header("Ruang belajar saya")
    with st.expander("Koneksi pribadi"):
        st.text_input(
            "API key (kosong untuk penggunaan lokal)",
            type="password",
            key="api_key",
            value=os.getenv("RAG_CLIENT_API_KEY", ""),
            on_change=clear_account,
        )
    if st.button("Muat ruang belajar") or not st.session_state.loaded:
        refresh_workspace()
    course_map = {course["id"]: course for course in st.session_state.courses}
    if st.session_state.get("course_selection") not in course_map:
        st.session_state.course_selection = None
    course_id = st.selectbox(
        "Mata kuliah",
        [None, *course_map],
        format_func=lambda key: (
            "Semua materi"
            if key is None
            else unique_label(key, course_map, lambda row: f"{row['name']} · {row['semester']}")
        ),
        key="course_selection",
    )
    with st.expander("Tambah mata kuliah"):
        with st.form("new-course", clear_on_submit=True):
            course_name = st.text_input("Nama mata kuliah", max_chars=100)
            semester = st.text_input(
                "Semester / periode", placeholder="Semester 3 · 2026", max_chars=60
            )
            create = st.form_submit_button("Buat mata kuliah")
        if create:
            if not course_name.strip():
                st.warning("Isi nama mata kuliah terlebih dahulu.")
            elif call_api(
                "POST", "/study/courses", json={"name": course_name, "semester": semester}
            ):
                refresh_workspace()
                st.rerun()
    all_docs = {doc["id"]: doc for doc in st.session_state.documents}
    if course_id:
        with st.expander("Atur materi mata kuliah"):
            assigned = st.multiselect(
                "Materi yang termasuk mata kuliah ini",
                list(all_docs),
                default=[key for key in course_map[course_id]["document_ids"] if key in all_docs],
                format_func=lambda key: unique_label(key, all_docs, lambda row: row["name"]),
                key=f"assign-{course_id}",
            )
            if st.button("Simpan pengelompokan"):
                if call_api(
                    "PUT", f"/study/courses/{course_id}/documents", json={"document_ids": assigned}
                ):
                    refresh_workspace()
                    st.rerun()
    uploaded = st.file_uploader("Tambahkan materi PDF", type=["pdf"])
    if st.button("Proses materi", disabled=uploaded is None):
        with st.spinner("Membaca materi dan menyiapkan sumber…"):
            result = call_api(
                "POST",
                "/upload",
                files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
            )
            if result:
                document_id = result["document"]["id"]
                if course_id:
                    ids = list(dict.fromkeys(course_map[course_id]["document_ids"] + [document_id]))
                    call_api(
                        "PUT", f"/study/courses/{course_id}/documents", json={"document_ids": ids}
                    )
                    st.session_state.pop(f"assign-{course_id}", None)
                refresh_workspace()
                st.session_state.document_selection = [document_id]
                st.rerun()
    by_id = {
        key: doc
        for key, doc in all_docs.items()
        if not course_id or key in course_map[course_id]["document_ids"]
    }
    if "document_selection" in st.session_state:
        st.session_state.document_selection = [
            key for key in st.session_state.document_selection if key in by_id
        ]
    selected = st.multiselect(
        "Materi yang dipelajari",
        list(by_id),
        format_func=lambda key: unique_label(
            key, by_id, lambda row: f"{row['name']} ({row['pages']} hal.)"
        ),
        max_selections=10,
        key="document_selection",
    )
    if (
        sorted(selected) != st.session_state.selection
        or course_id != st.session_state.active_course
    ):
        st.session_state.messages = []
        st.session_state.session_id = None
        st.session_state.selection = sorted(selected)
        st.session_state.active_course = course_id
        st.session_state.study_item = None
        invalidate()
    st.caption(
        "Teks materi dan pertanyaan diproses melalui Google Gemini. Hasil belajar disimpan lokal di server pribadimu."
    )
    with st.expander("Kelola penyimpanan"):
        delete_id = st.selectbox(
            "Hapus materi",
            list(all_docs),
            format_func=lambda key: unique_label(key, all_docs, lambda row: row["name"]),
            index=None,
        )
        confirmed = st.checkbox(
            "Hapus materi beserta percakapan dan hasil belajar yang memakai materi ini"
        )
        if st.button("Hapus materi", disabled=not delete_id or not confirmed):
            if call_api("DELETE", f"/documents/{delete_id}"):
                refresh_workspace()
                st.session_state.study_item = None
                st.session_state.messages = []
                st.session_state.session_id = None
                st.rerun()
        if course_id:
            remove_course = st.checkbox(
                "Hapus pengelompokan mata kuliah ini; materi dan hasil belajar tetap disimpan"
            )
            if st.button("Hapus mata kuliah", disabled=not remove_course):
                if call_api("DELETE", f"/study/courses/{course_id}"):
                    refresh_workspace()
                    st.rerun()

page = st.radio(
    "Kegiatan belajar",
    ["Tanya materi", "Bahan belajar", "Rak belajar", "Progres"],
    horizontal=True,
    key="page",
)
if page == "Tanya materi":
    if st.button("Percakapan baru"):
        st.session_state.messages = []
        st.session_state.session_id = None
    if not selected:
        st.info(
            "Pilih materi di sidebar. Kamu juga bisa membuka percakapan sebelumnya dari Rak belajar."
        )
    else:
        st.caption(
            "Coba: “Jelaskan konsep ini dari dasar”, “Apa perbedaan X dan Y?”, atau “Bagian mana yang menjelaskan contoh penerapannya?”"
        )
    for message in st.session_state.messages:
        show_message(message)
    if prompt := st.chat_input(
        "Apa yang ingin kamu pahami dari materi ini?", disabled=not selected, max_chars=4000
    ):
        show_message({"role": "user", "content": prompt})
        with st.spinner("Mencari penjelasan dari materi…"):
            result = call_api(
                "POST",
                "/study/chat",
                json={
                    "pertanyaan": prompt,
                    "document_ids": selected,
                    "course_id": course_id,
                    "session_id": st.session_state.session_id,
                },
            )
        if result:
            st.session_state.messages = result["payload"]["messages"]
            st.session_state.session_id = result["id"]
            invalidate()
            show_message(st.session_state.messages[-1])
            st.caption("Percakapan tersimpan otomatis di Rak belajar.")
elif page == "Bahan belajar":
    st.subheader("Belajar sesuai kebutuhanmu")
    with st.form("generate-study"):
        kind = st.selectbox(
            "Saya ingin…",
            ["explain", "summary", "flashcards", "quiz"],
            format_func=lambda key: KINDS[key],
        )
        topic = st.text_input(
            "Topik atau bab (opsional)",
            placeholder="Contoh: normalisasi database atau perbedaan ilmu dan akal",
            max_chars=1000,
        )
        level = st.selectbox(
            "Tingkat penjelasan",
            ["dasar", "menengah", "persiapan_ujian"],
            format_func=lambda key: {
                "dasar": "Mulai dari dasar",
                "menengah": "Perdalam pemahaman",
                "persiapan_ujian": "Persiapan ujian",
            }[key],
        )
        count = st.select_slider("Jumlah kartu / soal", options=list(range(3, 11)), value=5)
        st.caption(
            "Tanpa topik, dokumen panjang diwakili sejumlah cuplikan dari berbagai halaman. Untuk cakupan yang terarah, isi topik atau pilih PDF per pertemuan."
        )
        generate = st.form_submit_button("Buat bahan belajar", disabled=not selected)
    if generate:
        with st.spinner("Menyusun bahan belajar beserta sumbernya…"):
            item = call_api(
                "POST",
                "/study/generate",
                json={
                    "document_ids": selected,
                    "course_id": course_id,
                    "kind": kind,
                    "topic": topic,
                    "level": level,
                    "count": count,
                },
            )
        if item:
            st.session_state.study_item = item
            invalidate()
            st.success("Tersimpan otomatis. Kamu bisa membukanya kembali dari Rak belajar.")
    if st.session_state.study_item:
        show_learning_item(st.session_state.study_item, call_api, refresh_item)
elif page == "Rak belajar":
    st.subheader("Lanjutkan yang sudah kamu pelajari")
    if st.button("Segarkan rak belajar"):
        st.session_state.library = None
    if st.session_state.library is None:
        data = call_api("GET", "/study/items", params={"course_id": course_id} if course_id else {})
        st.session_state.library = data["items"] if data else []
    kind_filter = st.selectbox(
        "Jenis hasil",
        [None, *KINDS],
        format_func=lambda key: "Semua" if key is None else KINDS[key],
    )
    library = {
        item["id"]: item
        for item in st.session_state.library
        if not kind_filter or item["kind"] == kind_filter
    }
    if not library:
        st.info(
            "Belum ada hasil di rak ini. Mulai percakapan atau buat bahan belajar terlebih dahulu."
        )
    item_id = st.selectbox(
        "Hasil tersimpan",
        list(library),
        format_func=lambda key: unique_label(
            key, library, lambda row: f"{KINDS[row['kind']]} · {row['title']}"
        ),
        index=None,
    )
    if st.button("Buka hasil", disabled=not item_id):
        refresh_item(item_id)
    if item := st.session_state.study_item:
        if item["kind"] == "chat" and st.button("Lanjutkan percakapan ini"):
            st.session_state.resume_item = item
            st.session_state.next_page = "Tanya materi"
            st.rerun()
        show_learning_item(item, call_api, refresh_item)
        with st.expander("Hapus hasil ini"):
            if st.checkbox(
                "Saya ingin menghapus hasil belajar dan progres terkait",
                key=f"confirm-{item['id']}",
            ) and st.button("Hapus hasil belajar"):
                if call_api("DELETE", f"/study/items/{item['id']}"):
                    st.session_state.study_item = None
                    invalidate()
                    st.rerun()
else:
    st.subheader("Progres belajarmu")
    if st.button("Perbarui progres"):
        st.session_state.progress = None
    if st.session_state.progress is None:
        st.session_state.progress = call_api(
            "GET", "/study/progress", params={"course_id": course_id} if course_id else {}
        )
    if progress := st.session_state.progress:
        columns = st.columns(4)
        for column, label, value in zip(
            columns,
            [
                "Hasil tersimpan",
                "Set soal dikerjakan",
                "Rata-rata skor terakhir",
                "Kartu perlu diulang",
            ],
            [
                progress["saved_items"],
                progress["quiz_sets_completed"],
                f"{progress['mean_latest_quiz_score']:g}%"
                if progress["mean_latest_quiz_score"] is not None
                else "—",
                progress["cards_due"],
            ],
        ):
            column.metric(label, value)
        st.info(
            "Saran sesi singkat: pahami satu topik → tutup materi dan jawab flashcard → kerjakan latihan → tulis kembali bagian yang belum dipahami."
        )
        st.caption(
            "Skor dihitung dari percobaan terbaru pada setiap set soal. Jadwal kartu berdasarkan penilaianmu sendiri, bukan penilaian otomatis penguasaan materi."
        )
