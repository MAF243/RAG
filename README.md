# 🤖 RAG AI Chatbot dengan Gemini, FastAPI, & OCR

Proyek ini adalah sistem Back-End *Retrieval-Augmented Generation* (RAG) cerdas yang memungkinkan pengguna berinteraksi dan melakukan tanya-jawab (Q&A) dengan dokumen PDF mereka. Sistem ini dilengkapi dengan teknologi OCR untuk membaca PDF hasil pemindaian (*scan*) dan pelacakan eksperimen menggunakan Weights & Biases.

## ✨ Fitur Utama
* **Smart PDF Retrieval (RAG):** AI dapat menjawab pertanyaan berdasarkan konteks dokumen dengan akurasi tinggi menggunakan model `gemini-2.5-flash`.
* **OCR Support:** Mampu membaca dan mengekstrak teks dari PDF bergambar (hasil *scan*) berkat integrasi **PyMuPDF** dan **RapidOCR**.
* **Source Citation:** Transparansi penuh! Sistem akan menampilkan potongan teks asli dari dokumen yang dijadikan rujukan oleh AI.
* **Experiment Tracking:** Menggunakan **Weights & Biases (W&B)** untuk mencatat dan membandingkan secara real-time antara "Jawaban AI Murni" (tanpa konteks) vs "Jawaban AI RAG".
* **Microservices Architecture:** Pemisahan *Back-End* (FastAPI) dan *Front-End* (Streamlit) yang siap untuk di-*deploy* secara terpisah.

## 🛠️ Tech Stack
* **Back-End:** FastAPI, Uvicorn
* **Front-End:** Streamlit
* **AI & LLM:** Google Gemini API (`gemini-2.5-flash` & `gemini-embedding-001`)
* **Orchestration:** LangChain & LangChain Classic
* **Vector Database:** ChromaDB (Local)
* **Document Processing:** PyMuPDF (`fitz`), RapidOCR-ONNXRuntime
* **Tracking & MLOps:** Weights & Biases (W&B)

---

## 🚀 Cara Instalasi & Menjalankan Proyek

### 1. Prasyarat
Pastikan Python 3.9+ sudah terinstal di komputer Anda. Anda juga membutuhkan API Key dari:
* [Google AI Studio](https://aistudio.google.com/) (Untuk Gemini)
* [Weights & Biases](https://wandb.ai/) (Untuk Experiment Tracking)

### 2. Setup Virtual Environment
Sangat disarankan menggunakan Virtual Environment untuk mengisolasi dependensi proyek.
```bash
# Membuat virtual environment
python -m venv venv

# Mengaktifkan virtual environment (Windows)
venv\Scripts\activate
# Mengaktifkan virtual environment (Mac/Linux)
source venv/bin/activate

3. Instalasi LibraryInstal seluruh kebutuhan library melalui file requirements.txt:Bashpip install -r requirements.txt

4. Konfigurasi Environment VariablesBuat sebuah file bernama .env di direktori utama (sejajar dengan main.py) dan masukkan API Key Anda:Cuplikan kodeGOOGLE_API_KEY=masukkan_google_api_key_anda_disini
WANDB_API_KEY=masukkan_wandb_api_key_anda_disini

5. Menjalankan Aplikasi
Proyek ini berjalan dengan dua server terpisah (Back-End dan Front-End). Buka dua terminal terpisah (pastikan venv aktif di keduanya).

Terminal 1: Jalankan Server Back-End (FastAPI)
```bash
python -m uvicorn main:app --reload
```
Back-End akan berjalan di: http://127.0.0.1:8000 (Kunjungi /docs untuk Swagger UI)

Terminal 2: Jalankan Front-End (Streamlit)
```bash
python -m streamlit run ui/app.py
```
Aplikasi web Streamlit akan otomatis terbuka di browser pada alamat http://localhost:8501

📡 Dokumentasi API (Endpoints)

Jika Anda ingin mengonsumsi API ini untuk Front-End lain (misal: React, Vue, atau Mobile App), berikut adalah endpoints yang tersedia:

| Method | Endpoint | Fungsi | Payload |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/upload` | Mengunggah, membaca (OCR), dan menyimpan PDF ke ChromaDB. | `multipart/form-data` (file) |
| `POST` | `/api/v1/chat` | Mengirim pertanyaan ke AI dan mendapatkan jawaban beserta rujukan. | `{"pertanyaan": "Teks"}` |
