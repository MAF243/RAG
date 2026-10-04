# Teman Belajar — Asisten Materi Kuliah Pribadi

Aplikasi belajar dari materi PDF milikmu: tanya jawab, penjelasan konsep, rangkuman, flashcard, dan latihan soal dengan sumber halaman. Dibangun dengan Gemini, FastAPI, Streamlit, Chroma, dan OCR. Dirancang untuk satu server pribadi; hasil belajar tersimpan lokal dan bisa dibuka kembali.

## Fitur belajar versi 2.1

- **Mata kuliah dan semester:** kelompokkan materi lama maupun baru. Satu PDF boleh dipakai di beberapa mata kuliah.
- **Percakapan tersimpan:** lanjutkan sesi lama dari Rak belajar setelah browser/server dibuka ulang.
- **Penjelasan dan rangkuman:** pilih topik serta tingkat dasar, menengah, atau persiapan ujian.
- **Flashcard:** pikirkan jawaban sebelum membukanya, lalu tandai Belum ingat / Sudah ingat / Mudah.
- **Latihan soal:** 3–10 soal pilihan ganda; kunci dan pembahasan diberikan setelah semua soal dijawab. Penilaian dilakukan server berdasarkan kunci set soal yang tersimpan.
- **Rak belajar dan catatan:** hasil otomatis disimpan, dapat diberi catatan pribadi dan diunduh sebagai Markdown tanpa memanggil AI lagi.
- **Progres:** lihat jumlah hasil, set soal yang dikerjakan, rata-rata skor percobaan terbaru, dan kartu yang perlu diulang.
- **Cakupan yang jelas:** setiap bahan menunjukkan halaman sumber serta apakah seluruh potongan teks atau hanya sebagian yang masuk ke konteks.

### Alur pertama kali belajar

1. Jalankan aplikasi, lalu buat mata kuliah di sidebar, misalnya **Rekayasa Perangkat Lunak — Semester 3**.
2. Pilih mata kuliah tersebut dan unggah PDF per pertemuan. Untuk PDF yang sudah tersimpan, buka **Atur materi mata kuliah**, pilih file, lalu simpan pengelompokan.
3. Pilih **Materi yang dipelajari**. Mulai dari satu pertemuan agar konteksnya terarah.
4. Gunakan **Tanya materi** untuk pertanyaan bebas. Contoh: “Apa hubungan ilmu dan akal menurut materi ini?” atau “Jelaskan konsep normalisasi dari dasar.”
5. Buka **Bahan belajar** untuk membuat penjelasan/rangkuman, kartu, atau soal. Isi topik jika ingin fokus pada konsep tertentu.
6. Coba jawab tanpa membuka materi, periksa pembahasan dan sumber, lalu tulis pemahamanmu sendiri di catatan.
7. Keesokan hari, buka **Rak belajar** atau **Progres** untuk melanjutkan. Pengulangan yang tersimpan tidak membutuhkan panggilan model baru.

Nama file yang sama diberi penanda tambahan agar tidak tertukar. Dokumen di folder repo tidak otomatis diindeks; unggah melalui UI terlebih dahulu.

### Catatan kualitas belajar

Jawaban, kunci soal, dan pembahasan dibuat AI dan tetap perlu dibandingkan dengan materi dosen. Validasi format dan ID sumber bukan jaminan kebenaran akademik. Skor adalah hasil latihan terhadap kunci AI, bukan nilai resmi atau ukuran pasti penguasaan materi.

Tanpa topik, sistem mengambil cuplikan tersebar dari materi terpilih (default maksimum 16 potongan dan 18.000 karakter). Jika topik diisi, sistem mencari cuplikan yang relevan. Rangkuman hanya mencakup cuplikan tersebut, bukan otomatis seluruh PDF. Untuk dokumen panjang, pelajari per topik/pertemuan. Teks dalam gambar atau tabel yang gagal diekstrak tidak masuk konteks.

Jadwal kartu bersifat sederhana dan berdasarkan penilaian sendiri: **Belum ingat** → 10 menit; **Sudah ingat** → 1 hari pertama, lalu interval dua kali lipat (maksimal 30 hari); **Mudah** → 3 hari pertama, lalu tiga kali lipat (maksimal 60 hari). Kartu baru langsung dihitung perlu diulang. Jadwal hanya tampil dalam aplikasi; tidak ada notifikasi otomatis. Waktu pada UI ditampilkan dalam WIB.

## Fondasi versi 2.0

- Upload baru tidak menghapus dokumen lama. Indeks baru baru terlihat setelah seluruh embedding berhasil; kegagalan parsial dibersihkan.
- Nama file hanya menjadi metadata. File sementara acak, batas byte request/file, jumlah halaman, ukuran render OCR, jumlah potongan, dan kuota dokumen diterapkan.
- PDF teks diekstrak langsung per halaman. OCR hanya digunakan saat teks terlalu sedikit atau mengandung karakter pengganti.
- Pilih hingga 10 dokumen untuk chat; setiap referensi memiliki nama file, halaman, ID potongan, dan ID kutipan `[S1]`.
- API key berbeda menghasilkan pemilik berbeda. Tidak ada `owner_id` yang bisa dipilih pengguna melalui payload.
- Chat biasa menggunakan satu panggilan generasi; jika tidak ada hasil yang melewati ambang relevansi, model tidak dipanggil.
- Riwayat terbatas dikirim ke model; dua pertanyaan pengguna sebelumnya ikut membantu pencarian. Pergantian pilihan dokumen mengosongkan percakapan UI.
- W&B hanya dijalankan oleh skrip evaluasi jika diminta. Tidak ada login W&B saat aplikasi diimpor.
- Pengujian otomatis menggunakan PDF dan Chroma sungguhan, dengan embedding/LLM pengganti tanpa API berbayar.

## Persyaratan

Gunakan **Python 3.12**. Dependensi langsung dikunci di `requirements.txt`; `requirements.lock` mengunci dependensi transitif. Lingkungan validasi: Linux, Python 3.12. Instalasi Windows/macOS belum diuji langsung.

Pada Linux minimal, OpenCV/RapidOCR mungkin memerlukan `libgl1` dan `libglib2.0-0` dari package manager OS.

```bash
git clone https://github.com/MAF243/RAG.git
cd RAG
python -m venv .venv
```

Aktifkan virtual environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# Linux / macOS
source .venv/bin/activate
```

```bash
python -m pip install -r requirements.lock
```

Salin `.env.example` menjadi `.env`:

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```bash
# Linux / macOS
cp .env.example .env
```

Isi `GOOGLE_API_KEY`. Model chat dan embedding dapat diganti melalui konfigurasi jika tersedia untuk akun Google milikmu. Jangan commit `.env`.

Cara praktis menjalankan kedua server dari satu terminal:

```bash
python run.py
```

Browser akan dibuka setelah server siap. Tekan **Ctrl+C** untuk menghentikan backend dan UI. Jika port sudah terpakai:

```bash
python run.py --backend-port 8001 --ui-port 8502
```

Gunakan `--no-browser` jika tidak ingin membuka browser otomatis. Jalankan dari virtual environment yang sudah dipasang dependensinya. Launcher membuka akses pada loopback saja.

Alternatif menjalankan manual, terminal pertama:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers
```

Terminal kedua:

```bash
python -m streamlit run ui/app.py --server.address 127.0.0.1
```

Buka UI di `http://localhost:8501` dan dokumentasi API di `http://127.0.0.1:8000/docs`. Unggah PDF, pilih dokumen, lalu bertanya. Klik **Muat ruang belajar** untuk menyegarkan daftar materi dan mata kuliah. Percakapan baru tersimpan otomatis dan dapat dibuka lagi melalui **Rak belajar**.

## Konfigurasi penting

| Variabel | Default | Fungsi |
|---|---|---|
| `GOOGLE_API_KEY` | kosong | Kredensial Gemini server; tanpa key health/list tetap tersedia |
| `RAG_MODEL` | `gemini-2.5-flash` | Model generasi |
| `RAG_EMBEDDING_MODEL` | `models/gemini-embedding-001` | Model embedding |
| `RAG_DATA_DIR` | `data/v2` | Katalog SQLite dan indeks Chroma |
| `RAG_API_KEYS` | `{}` | JSON pemilik → API key rahasia |
| `RAG_API_URL` | `http://127.0.0.1:8000/api/v1` | URL backend untuk UI/evaluasi |
| `RAG_CLIENT_API_KEY` | kosong | Key bawaan UI/evaluasi; gunakan hanya untuk UI pribadi |
| `RAG_MAX_UPLOAD_MB` | `20` | Ukuran maksimum satu PDF; request boleh memiliki overhead multipart 64 KiB |
| `RAG_MAX_PAGES` | `100` | Maksimum halaman per PDF |
| `RAG_MAX_DOCUMENTS_PER_OWNER` | `50` | Kuota dokumen pemilik |
| `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | `1000` / `200` | Ukuran/overlap karakter per potongan, dalam satu halaman |
| `RAG_TOP_K` | `5` | Maksimum potongan akhir yang dikirim ke model |
| `RAG_MAX_COSINE_DISTANCE` | `0.65` | Batas jarak pencarian; lebih kecil lebih ketat |
| `RAG_NATIVE_MIN_CHARS` | `40` | Ambang jumlah karakter alfanumerik sebelum mencoba OCR |
| `RAG_REQUEST_TIMEOUT` | `60` | Timeout client provider dalam detik; retry bisa memperpanjang total waktu |
| `RAG_UI_TIMEOUT` | `300` | Timeout baca respons UI, detik |
| `RAG_REQUESTS_PER_MINUTE` | `30` | Batas request API per pemilik per proses |

Konfigurasi tambahan tersedia di `config.py`. Ambang cosine bukan confidence score; kalibrasikan menggunakan dokumen dan pertanyaan representatif.

## Autentikasi dan penggunaan bersama

Buat key acak:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Masukkan key berbeda untuk setiap pemilik di `.env`, misalnya:

```dotenv
RAG_API_KEYS={"mushab":"GANTI_DENGAN_KEY_ACAK_PERTAMA","pengguna2":"GANTI_DENGAN_KEY_ACAK_KEDUA"}
```

Kirim key di header `X-API-Key` atau masukkan melalui sidebar UI. Mengubah key sidebar membersihkan tampilan lokal dan memuat ruang belajar pemilik key baru. Riwayat yang sudah disimpan di server tetap dimiliki pemilik sebelumnya. Nama pemilik yang sama mempertahankan akses saat key dirotasi. Jangan mengisi `RAG_CLIENT_API_KEY` milik pribadi pada UI publik yang digunakan bersama, karena semua pengunjung dapat memakai identitas tersebut.

Tanpa key, backend hanya menerima koneksi lokal dan semuanya menggunakan pemilik `local`. Mode ini **bukan isolasi antar sesi browser**. Selalu aktifkan key ketika berada di belakang reverse proxy atau membuka akses jaringan. Gunakan HTTPS, batas body/timeouts pada reverse proxy, dan jangan mempercayai forwarded headers dari sumber sembarang.

Katalog/Chroma memakai satu proses backend. File lock menolak proses kedua yang membuka direktori data sama; jangan gunakan beberapa worker/replika. Untuk skala lebih besar, pindahkan penyimpanan ke layanan database, rate limiting ke penyimpanan bersama, dan ingestion ke worker antrean. Saat ini ingestion sinkron dijalankan di threadpool, maksimal satu upload diproses sekaligus; request lainnya menerima `429` dan dapat mencoba lagi. Ini belum merupakan sistem background job.

## API

Seluruh `/api/v1/*` menggunakan autentikasi dan pembatasan request. `/` dan `/health` tidak memanggil Gemini. Health tidak menjamin provider tersedia.

| Metode | Path | Fungsi |
|---|---|---|
| POST | `/api/v1/upload` | Multipart `file`, menghasilkan `document.id` |
| GET | `/api/v1/documents` | Daftar dokumen siap milik pemanggil |
| DELETE | `/api/v1/documents/{id}` | Hapus satu dokumen milik pemanggil |
| POST | `/api/v1/chat` | Tanya dokumen yang dipilih |

Contoh request chat:

```json
{
  "pertanyaan": "Apa syarat pendaftaran?",
  "document_ids": ["ID_HEKSADESIMAL_32_KARAKTER_DARI_UPLOAD"],
  "history": [{"role": "user", "content": "Saya ingin bertanya tentang pendaftaran siswa."}]
}
```

`history` opsional: maksimal 10 pesan, 4.000 karakter per pesan, total 12.000 karakter. Pertanyaan maksimal 4.000 karakter. `document_ids` wajib berisi 1–10 ID unik. Tidak menerima pesan `system` dari klien.

Respons chat berisi `jawaban`, `referensi` (objek `id`, `source`, `page`, `text`, `document_id`, `chunk_id`, `distance`, `cited`), serta `metrics` (latensi dan token generasi jika dilaporkan provider). Token embedding belum dihitung. `cited=false` berarti potongan ditemukan tetapi tidak dikutip model. ID kutipan yang tidak tersedia menyebabkan jawaban ditahan; validitas ID tidak membuktikan kebenaran klaim.

Status umum: `400` PDF invalid, `401` key salah, `403` akses anonim nonlokal, `404` dokumen tidak dapat diakses, `409` konflik/kuota, `413` terlalu besar, `422` payload tidak valid, `429` sibuk/rate limit, `503` konfigurasi/provider/pemrosesan gagal. Detail exception internal tidak dikirim ke klien.

## Migrasi dari versi awal

1. Cadangkan `.env`, PDF sumber, dan `chroma_db/` lama.
2. Instal ulang dependensi di virtual environment baru, lalu isi konfigurasi baru.
3. Unggah ulang PDF melalui aplikasi. Indeks lama tidak memiliki metadata pemilik/halaman yang memadai untuk migrasi otomatis.
4. Data baru menggunakan `data/v2/`; aplikasi tidak menghapus atau membaca indeks `chroma_db/` lama.

**Kontrak API berubah** walaupun prefix tetap `/api/v1`: chat sekarang mewajibkan `document_ids`, upload mengembalikan objek `document`, dan referensi menjadi objek terstruktur. UI dalam repo sudah disesuaikan. Jika mengganti model embedding, gunakan direktori data baru dan unggah ulang PDF.

PDF upload tidak dipertahankan setelah proses selesai; teks hasil ekstraksi tersimpan di Chroma. Simpan PDF asli sendiri jika membutuhkan pembukaan halaman asli. Teks dokumen dikirim ke Google untuk embedding, dan potongan terpilih/pertanyaan/riwayat dikirim untuk generasi. Jangan mengunggah materi yang tidak boleh diproses layanan tersebut. W&B tidak menerima isi percakapan saat aplikasi berjalan normal.

## Upgrade dari 2.0 dan penyimpanan pribadi

Versi 2.1 memakai `RAG_DATA_DIR` yang sama. Tabel belajar ditambahkan otomatis ke `catalog.sqlite3`; PDF yang sudah diindeks di versi 2.0 tidak perlu diunggah ulang. Hentikan server dan cadangkan seluruh `data/v2/` sebelum memperbarui kode. Pertahankan `.env` dan folder data saat menyalin pembaruan. Jangan menyalin paket ZIP sebagai subfolder di dalam repo: salin isinya langsung ke root repo atau terapkan patch Git.

Yang tersimpan: metadata mata kuliah, hubungan materi, percakapan beserta cuplikan sumber, rangkuman, kartu, soal/kunci, skor latihan, jadwal kartu, dan catatan. Semua akses tetap dibatasi pemilik API key. Mode lokal tanpa key menggunakan satu pemilik `local`. Mengganti nama pemilik atau direktori data akan menampilkan ruang belajar berbeda.

**Menghapus materi juga menghapus hasil belajar, percakapan, catatan, skor, dan ulasan kartu yang menggunakan materi tersebut**, termasuk hasil yang memakai beberapa PDF sekaligus. Ini mencegah salinan teks materi tertinggal di riwayat setelah sumber dihapus. UI meminta konfirmasi. Menghapus mata kuliah hanya menghapus pengelompokan; materi dan hasil tetap dapat ditemukan melalui **Semua materi**.

Batas awal: 100 mata kuliah, 500 hasil tersimpan per pemilik, dan 50 pertanyaan per percakapan. Konteks percakapan memakai maksimal 10 pesan terakhir / 12.000 karakter; riwayat lebih panjang tetap tersimpan, tetapi tidak seluruhnya dikirim ke model. File ekspor Markdown menyimpan salinan hasil di tempat unduhan pengguna; penghapusan di aplikasi tidak menghapus file ekspor tersebut.

## Endpoint belajar tambahan

Endpoint lama tetap tersedia; fitur baru memakai prefix `/api/v1/study` dengan `X-API-Key` yang sama.

| Metode | Path di bawah `/api/v1/study` | Fungsi |
|---|---|---|
| GET / POST | `/courses` | Daftar / buat mata kuliah |
| PUT | `/courses/{id}/documents` | Atur daftar materi mata kuliah |
| DELETE | `/courses/{id}` | Hapus pengelompokan |
| POST | `/chat` | Chat tersimpan; kirim `session_id` untuk melanjutkan |
| POST | `/generate` | Buat penjelasan/rangkuman/kartu/soal |
| GET | `/items` | Daftar hasil; filter opsional `course_id` |
| GET / DELETE | `/items/{id}` | Buka / hapus hasil |
| PATCH | `/items/{id}/notes` | Simpan catatan pribadi |
| POST | `/items/{id}/attempts` | Kirim seluruh jawaban soal sebagai indeks 0–3 |
| POST | `/items/{id}/reviews` | Nilai kartu: `again`, `good`, atau `easy` |
| GET | `/progress` | Progres pemilik, filter opsional `course_id` |

Contoh generate:

```json
{
  "document_ids": ["ID_HEKSADESIMAL_32_KARAKTER_DARI_UPLOAD"],
  "course_id": null,
  "kind": "quiz",
  "topic": "normalisasi database",
  "level": "dasar",
  "count": 5
}
```

`kind`: `explain`, `summary`, `flashcards`, `quiz`. `level`: `dasar`, `menengah`, `persiapan_ujian`. `count` 3–10 digunakan untuk soal/kartu. Jika sumber tidak cukup, API mengembalikan `422`; jika keluaran model tidak memenuhi format atau memakai ID sumber rekaan, `502` dan hasil tidak disimpan. Keluaran belajar maksimal 8.192 token per panggilan; chat biasa tetap mengikuti batas model sebelumnya. Tidak ada panggilan model ketika memeriksa kuis, mengulas kartu, membuka hasil lama, atau menyimpan catatan.

Konfigurasi tambahan: `RAG_STUDY_CONTEXT_CHUNKS=16` dan `RAG_STUDY_CONTEXT_CHARS=18000`. Endpoint belajar tetap memakai pembatasan request bersama; jika sering mencapai `429` saat mengulas banyak kartu, sesuaikan `RAG_REQUESTS_PER_MINUTE` untuk pemakaian pribadimu.

## Pengujian dan evaluasi

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
ruff check .
ruff format --check .
```

CI GitHub Actions menjalankan pemeriksaan yang sama tanpa secret. Tests mencakup upload gagal, rollback batch parsial, isolasi pemilik, path upload, batas ukuran tanpa Content-Length, OCR fallback, sumber halaman, chat satu panggilan, abstention, restart recovery, dan referensi UI setelah rerun. Kualitas model Gemini belum dapat disimpulkan dari test dengan model pengganti.

Buat PDF sintetis tiga halaman beserta **30 pertanyaan berlabel**, termasuk lima pertanyaan yang tidak terjawab dalam dokumen:

```bash
python scripts/create_eval_fixture.py
python scripts/evaluate.py evaluations/generated/cases.jsonl
```

Backend harus berjalan dan mempunyai Google API key. Untuk mode autentikasi, set `RAG_CLIENT_API_KEY` di `.env`. Evaluasi mengunggah PDF ke akun tersebut dan menyimpannya sebagai dokumen biasa; hapus melalui UI bila selesai. Hasil tersimpan lokal di `evaluations/results.json` dan tidak masuk Git.

Metrik: cakupan kata kunci, recall halaman sumber, ketepatan halaman yang dikutip, kecocokan abstention, latensi, dan token generasi per kasus. Kata kunci dan deteksi abstention berbasis frasa adalah **proxy sederhana**, bukan pengganti penilaian manual akurasi/faithfulness. Dataset sintetis juga belum mewakili kualitas PDF scan, tabel, bahasa Arab, atau dokumen milikmu.

Perbandingan AI murni dan W&B bersifat opsional dan menggunakan panggilan model tambahan:

```bash
python -m pip install -r requirements-eval.txt
python scripts/evaluate.py evaluations/generated/cases.jsonl --compare-baseline --wandb
```

Secara default W&B hanya menerima metrik agregat. `--log-content` mengizinkan pengiriman pertanyaan dan jawaban ke W&B. File hasil lokal tetap memuat isi jawaban dan referensi, sehingga perlu dijaga seperti dokumen asalnya.

## Batasan yang masih perlu dievaluasi

- Ekstraksi native menggunakan heuristik sederhana; halaman campuran teks/gambar dan tabel kompleks dapat memerlukan parser yang lebih baik.
- RapidOCR bawaan tidak menjamin akurasi semua bahasa, termasuk tulisan Arab. Uji model OCR pada contoh yang representatif.
- Riwayat membantu pertanyaan lanjutan, tetapi belum menggunakan query rewriting/reranker/hybrid retrieval.
- Instruksi prompt dan validasi ID kutipan mengurangi beberapa risiko, tetapi tidak menjamin bebas prompt injection atau halusinasi.
- Belum ada login akun, background job, atau streaming jawaban. Riwayat belajar tersimpan lokal di server; belum ada sinkronisasi antarkomputer. API key adalah mekanisme akses untuk pilot kecil.
- Pemrosesan PDF/OCR belum memiliki isolasi proses dan hard timeout CPU. Layanan publik yang menerima dokumen tidak tepercaya membutuhkan worker terisolasi dan pembatasan sumber daya.
