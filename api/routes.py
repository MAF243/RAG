import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from services.rag_engine import RAGService

# Inisialisasi Router dan RAG Service
router = APIRouter()
rag_service = RAGService()

# 1. Pydantic Model untuk validasi input JSON
class ChatRequest(BaseModel):
    pertanyaan: str

# 2. Endpoint untuk mengunggah dan memproses PDF
@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    # Validasi ekstensi file
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Hanya menerima file PDF!")
    
    # Simpan file secara sementara di direktori proyek
    temp_file_path = f"./{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        buffer.write(await file.read())
        
    try:
        # Kirim file ke otak AI (RAG Service) yang kita buat sebelumnya
        hasil = rag_service.proses_dokumen(temp_file_path)
        return hasil
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan saat memproses: {str(e)}")
    finally:
        # Hapus file PDF setelah selesai diproses agar server tidak penuh
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# 3. Endpoint untuk mengobrol dengan AI
@router.post("/chat")
async def chat_bot(request: ChatRequest):
    try:
        # Kirim pertanyaan ke RAG Service
        hasil = rag_service.tanya_bot(request.pertanyaan)
        return {
            "pertanyaan": request.pertanyaan, 
            "jawaban": hasil["jawaban"],
            "referensi": hasil["referensi"] # Data referensi ditambahkan di sini
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))