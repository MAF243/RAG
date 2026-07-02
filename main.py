from fastapi import FastAPI
from api.routes import router

# Membuat instance FastAPI
app = FastAPI(
    title="RAG Gemini API",
    description="REST API untuk Asisten AI berbasis dokumen menggunakan Gemini 1.5 Flash dan ChromaDB.",
    version="1.0.0"
)

# Mendaftarkan router dari folder api
# Prefix /api/v1 digunakan untuk versioning API (standar industri)
app.include_router(router, prefix="/api/v1")

# Endpoint dasar untuk mengecek apakah server menyala (Health Check)
@app.get("/")
def root():
    return {
        "status": "Online",
        "message": "Selamat datang di RAG Gemini API! Kunjungi http://127.0.0.1:8000/docs untuk mengetes API."
    }