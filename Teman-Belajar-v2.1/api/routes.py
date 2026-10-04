import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from services.errors import ServiceError

router = APIRouter(dependencies=[Depends(APIKeyHeader(name="X-API-Key", auto_error=False))])
logger = logging.getLogger(__name__)


def invoke(method, *args):
    try:
        return method(*args)
    except ServiceError:
        raise
    except Exception as exc:
        logger.error("Layanan gagal (%s)", type(exc).__name__)
        raise ServiceError(
            "Pemrosesan gagal. Coba lagi atau periksa konfigurasi layanan.", 503
        ) from None


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
DocumentID = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: Text


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pertanyaan: Text
    document_ids: list[DocumentID] = Field(min_length=1, max_length=10)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def bound_history(self):
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("document_ids tidak boleh berulang")
        if sum(len(message.content) for message in self.history) > 12000:
            raise ValueError("Riwayat melebihi 12000 karakter")
        return self


@router.post(
    "/upload",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                }
            },
        }
    },
)
async def upload_pdf(request: Request):
    # Authentication and total byte limit run before multipart parsing.
    async with request.form(max_files=1, max_fields=0) as form:
        file = form.get("file")
        if not isinstance(file, UploadFile):
            raise HTTPException(422, "Field file PDF wajib diisi.")
        return await run_in_threadpool(
            invoke,
            request.app.state.rag.proses_dokumen,
            file.file,
            file.filename,
            request.state.owner,
        )


@router.get("/documents")
def documents(request: Request):
    return {"documents": invoke(request.app.state.rag.list_documents, request.state.owner)}


@router.delete("/documents/{document_id}")
def delete_document(document_id: DocumentID, request: Request):
    invoke(request.app.state.rag.delete_document, document_id, request.state.owner)
    return {"status": "success"}


@router.post("/chat")
def chat_bot(payload: ChatRequest, request: Request):
    return invoke(
        request.app.state.rag.tanya_bot,
        payload.pertanyaan,
        payload.document_ids,
        request.state.owner,
        [message.model_dump() for message in payload.history],
    )
