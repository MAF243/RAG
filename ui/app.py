import streamlit as st
import requests

# Konfigurasi URL API Backend (FastAPI) Anda
API_URL = "http://127.0.0.1:8000/api/v1"

# Pengaturan halaman
st.set_page_config(page_title="RAG AI Chatbot", page_icon="🤖", layout="wide")
st.title("🤖 Chatbot Asisten Dokumen")
st.markdown("Unggah file PDF Anda, lalu tanyakan apa saja seputar isi dokumen tersebut!")

# --- SIDEBAR: Untuk Upload File ---
with st.sidebar:
    st.header("📂 Upload Dokumen")
    uploaded_file = st.file_uploader("Pilih file PDF", type=["pdf"])
    
    if st.button("Proses Dokumen"):
        if uploaded_file is not None:
            with st.spinner("Memproses dan mengingat dokumen..."):
                try:
                    # Mengirim file ke endpoint FastAPI
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    response = requests.post(f"{API_URL}/upload", files=files)
                    
                    if response.status_code == 200:
                        st.success("✅ Dokumen berhasil diproses! AI siap ditanya.")
                    else:
                        st.error(f"Gagal: {response.json().get('detail', 'Error tidak diketahui')}")
                except requests.exceptions.ConnectionError:
                    st.error("🚨 Gagal terhubung ke server. Pastikan FastAPI sudah menyala!")
        else:
            st.warning("Silakan unggah file PDF terlebih dahulu.")

# --- MAIN PAGE: Ruang Obrolan (Chat) ---
# Menyimpan riwayat percakapan di dalam memory Streamlit
if "messages" not in st.session_state:
    st.session_state.messages = []

# Menampilkan riwayat percakapan sebelumnya
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Kolom input untuk user bertanya
if prompt := st.chat_input("Tanyakan sesuatu tentang dokumen..."):
    # Tampilkan pertanyaan user di layar
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Kirim pertanyaan ke backend dan tampilkan jawaban AI
    with st.chat_message("assistant"):
        with st.spinner("Berpikir..."):
            try:
                response = requests.post(f"{API_URL}/chat", json={"pertanyaan": prompt})
                
                if response.status_code == 200:
                    data = response.json()
                    jawaban_ai = data.get("jawaban", "Maaf, tidak ada jawaban.")
                    referensi = data.get("referensi", [])
                    
                    # 1. Tampilkan Jawaban Utama
                    st.markdown(jawaban_ai)
                    
                    # 2. Tampilkan Fitur Source Citation (Bonus)
                    if referensi:
                        with st.expander("📚 Lihat Sumber Rujukan Dokumen Asli"):
                            for i, ref in enumerate(referensi):
                                st.info(f"**Potongan {i+1}:**\n{ref}")
                                
                    # Simpan ke riwayat
                    st.session_state.messages.append({"role": "assistant", "content": jawaban_ai})
                else:
                    st.error(f"Terjadi kesalahan server: {response.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("🚨 Gagal terhubung ke server Back-End!")