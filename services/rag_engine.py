import os
import wandb
import fitz
from rapidocr_onnxruntime import RapidOCR
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# Inisialisasi Weights & Biases (W&B)
wandb.login(key=os.getenv("WANDB_API_KEY"))
wandb.init(project="rag-gemini-vs-pure-ai", name="eksperimen-dokumen")

class RAGService:
    def __init__(self):
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        self.persist_directory = "./chroma_db"
        
        self.vectorstore = Chroma(
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )

    def proses_dokumen(self, file_path: str):
        print(f"Memproses dokumen baru: {file_path}")
        
        # Bersihkan ingatan lama
        try:
            if self.vectorstore:
                self.vectorstore.delete_collection()
        except Exception:
            pass
        
        # --- TEKNIK OCR PROFESIONAL (PAGE RENDERING) ---
        print("📸 Merender halaman menjadi gambar dan memulai OCR...")
        doc = fitz.open(file_path)
        ocr_engine = RapidOCR()
        extracted_text = ""
        
        # Looping setiap halaman di PDF
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Ambil screenshot halaman (Resolusi DPI 150 cukup untuk teks)
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            
            # Pindai screenshot tersebut
            result, _ = ocr_engine(img_bytes)
            if result:
                for line in result:
                    extracted_text += line[1] + " "
            extracted_text += "\n\n"
            print(f"Halaman {page_num + 1} selesai di-scan.")
            
        if not extracted_text.strip():
            raise ValueError("Dokumen kosong atau OCR gagal mengenali teks.")

        # Bungkus teks hasil OCR menjadi format yang dipahami LangChain
        docs = [Document(page_content=extracted_text, metadata={"source": file_path})]
        # ----------------------------------------------

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(docs)
        
        self.vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=self.embeddings,
            persist_directory=self.persist_directory
        )
        return {"status": "success", "message": f"{len(splits)} potongan teks berhasil di-scan."}

    def tanya_bot(self, pertanyaan: str):
        print("Meminta jawaban AI murni...")
        pure_ai_response = self.llm.invoke(pertanyaan)
        jawaban_murni = pure_ai_response.content

        print("Meminta jawaban AI RAG...")
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": 3})
        
        system_prompt = (
            "Gunakan potongan konteks berikut untuk menjawab pertanyaan.\n"
            "Jika jawaban tidak ada di konteks, katakan Anda tidak tahu.\n\n"
            "Konteks:\n{context}"
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        
        question_answer_chain = create_stuff_documents_chain(self.llm, prompt)
        rag_chain = create_retrieval_chain(retriever, question_answer_chain)
        
        response = rag_chain.invoke({"input": pertanyaan})
        jawaban_rag = response["answer"]
        sumber_dokumen = response["context"]
        
        referensi = [doc.page_content for doc in sumber_dokumen]

        # W&B TRACKING
        wandb.log({
            "Pertanyaan": pertanyaan,
            "Jawaban AI Murni": jawaban_murni,
            "Jawaban AI RAG": jawaban_rag
        })

        return {
            "jawaban": jawaban_rag,
            "referensi": referensi
        }