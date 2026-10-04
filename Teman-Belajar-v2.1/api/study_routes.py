from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from api.routes import DocumentID, Text, invoke

router = APIRouter(
    prefix="/study", dependencies=[Depends(APIKeyHeader(name="X-API-Key", auto_error=False))]
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CourseInput(StrictModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    semester: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] = ""


class DocumentSelection(StrictModel):
    document_ids: list[DocumentID] = Field(max_length=50)

    @model_validator(mode="after")
    def unique_documents(self):
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("Materi tidak boleh berulang")
        return self


class StudyScope(DocumentSelection):
    document_ids: list[DocumentID] = Field(min_length=1, max_length=10)
    course_id: DocumentID | None = None


class GenerateInput(StudyScope):
    kind: Literal["explain", "summary", "flashcards", "quiz"]
    topic: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ""
    level: Literal["dasar", "menengah", "persiapan_ujian"] = "dasar"
    count: int = Field(default=5, ge=3, le=10)


class StudyChatInput(StudyScope):
    pertanyaan: Text
    session_id: DocumentID | None = None


class NotesInput(StrictModel):
    notes: Annotated[str, StringConstraints(max_length=8000)]


class AttemptInput(StrictModel):
    answers: list[Annotated[int, Field(strict=True, ge=0, le=3)]] = Field(
        min_length=1, max_length=10
    )


class ReviewInput(StrictModel):
    card_index: int = Field(ge=0, le=9)
    rating: Literal["again", "good", "easy"]


@router.get("/courses")
def courses(request: Request):
    return {"courses": invoke(request.app.state.study.store.courses, request.state.owner)}


@router.post("/courses", status_code=201)
def create_course(payload: CourseInput, request: Request):
    return invoke(
        request.app.state.study.store.create_course,
        request.state.owner,
        payload.name,
        payload.semester,
    )


@router.put("/courses/{course_id}/documents")
def course_documents(course_id: DocumentID, payload: DocumentSelection, request: Request):
    return invoke(
        request.app.state.study.store.set_documents,
        course_id,
        request.state.owner,
        payload.document_ids,
    )


@router.delete("/courses/{course_id}")
def delete_course(course_id: DocumentID, request: Request):
    invoke(request.app.state.study.store.delete_course, course_id, request.state.owner)
    return {"status": "success"}


@router.post("/generate", status_code=201)
def generate(payload: GenerateInput, request: Request):
    return invoke(
        request.app.state.study.generate,
        request.state.owner,
        payload.document_ids,
        payload.course_id,
        payload.kind,
        payload.topic,
        payload.level,
        payload.count,
    )


@router.post("/chat")
def chat(payload: StudyChatInput, request: Request):
    return invoke(
        request.app.state.study.chat,
        request.state.owner,
        payload.document_ids,
        payload.course_id,
        payload.pertanyaan,
        payload.session_id,
    )


@router.get("/items")
def items(request: Request, course_id: DocumentID | None = None):
    return {"items": invoke(request.app.state.study.store.items, request.state.owner, course_id)}


@router.get("/items/{item_id}")
def item(item_id: DocumentID, request: Request):
    study = request.app.state.study
    return study.public_item(invoke(study.store.item, item_id, request.state.owner))


@router.patch("/items/{item_id}/notes")
def notes(item_id: DocumentID, payload: NotesInput, request: Request):
    invoke(request.app.state.study.store.notes, item_id, request.state.owner, payload.notes)
    return {"status": "success"}


@router.delete("/items/{item_id}")
def delete_item(item_id: DocumentID, request: Request):
    invoke(request.app.state.study.store.delete_item, item_id, request.state.owner)
    return {"status": "success"}


@router.post("/items/{item_id}/attempts")
def attempt(item_id: DocumentID, payload: AttemptInput, request: Request):
    return invoke(
        request.app.state.study.store.attempt, item_id, request.state.owner, payload.answers
    )


@router.post("/items/{item_id}/reviews")
def review(item_id: DocumentID, payload: ReviewInput, request: Request):
    return invoke(
        request.app.state.study.store.review_card,
        item_id,
        request.state.owner,
        payload.card_index,
        payload.rating,
    )


@router.get("/progress")
def progress(request: Request, course_id: DocumentID | None = None):
    return invoke(request.app.state.study.store.progress, request.state.owner, course_id)
