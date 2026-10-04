# Catatan perubahan

## 2.1.0 — Teman Belajar pribadi

- Pengelompokan PDF per mata kuliah dan semester tanpa mengindeks ulang materi versi 2.0.
- Percakapan permanen, penjelasan konsep, rangkuman, flashcard, dan kuis pilihan ganda.
- Rak belajar, catatan pribadi, ekspor Markdown, skor latihan, dan jadwal ulasan kartu.
- Konteks belajar dengan informasi halaman/cakupan; keluaran model divalidasi sebelum disimpan.
- Jawaban kuis dipisahkan dari payload soal sampai pengguna menyerahkan percobaan.
- Penghapusan materi membersihkan hasil belajar terkait; penghapusan mata kuliah hanya melepas pengelompokan.
- `python run.py` untuk menjalankan backend dan UI pada localhost dari satu terminal.
- API lama tetap tersedia. Endpoint baru berada di `/api/v1/study`.

Versi aplikasi ini belum otomatis diberi tag Git atau dipublikasikan.

## 2.0 — Fondasi RAG

Upload aman, indeks terpisah per dokumen, isolasi pemilik, OCR selektif,
sumber halaman, konfigurasi terkunci, dan evaluasi. Pembaruan ini berada pada
commit `209e383` sebelum perapian folder oleh `cb7534f`.

## v1.0 — Versi awal

Tag Git `v1.0` menunjuk commit `a0a5bc8`: chatbot PDF awal dengan Gemini,
FastAPI, Streamlit, OCR, dan eksperimen W&B.
