"""Persistent personal study workspace, sharing the existing local SQLite catalog."""

import json
import uuid
from datetime import datetime, timedelta, timezone

from services.errors import ServiceError


def utcnow():
    return datetime.now(timezone.utc)


class StudyStore:
    def __init__(self, catalog):
        self.catalog = catalog
        with catalog.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS courses (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL,
                    semester TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS course_documents (
                    course_id TEXT REFERENCES courses(id) ON DELETE CASCADE,
                    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
                    PRIMARY KEY(course_id, document_id));
                CREATE TABLE IF NOT EXISTS study_items (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL,
                    course_id TEXT REFERENCES courses(id) ON DELETE SET NULL,
                    kind TEXT NOT NULL, title TEXT NOT NULL, payload TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS study_item_documents (
                    item_id TEXT REFERENCES study_items(id) ON DELETE CASCADE,
                    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
                    PRIMARY KEY(item_id, document_id));
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id TEXT PRIMARY KEY, item_id TEXT REFERENCES study_items(id) ON DELETE CASCADE,
                    score REAL NOT NULL, feedback TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS card_reviews (
                    item_id TEXT REFERENCES study_items(id) ON DELETE CASCADE,
                    card_index INTEGER NOT NULL, rating TEXT NOT NULL,
                    interval_days INTEGER NOT NULL, due_at TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL, PRIMARY KEY(item_id, card_index));
                CREATE TRIGGER IF NOT EXISTS remove_study_on_document_delete
                BEFORE DELETE ON documents BEGIN
                    DELETE FROM study_items WHERE id IN (
                        SELECT item_id FROM study_item_documents WHERE document_id=OLD.id
                    );
                END;
                CREATE INDEX IF NOT EXISTS study_owner_updated ON study_items(owner, updated_at);
            """)

    def course(self, course_id, owner):
        with self.catalog.connect() as db:
            row = db.execute(
                "SELECT * FROM courses WHERE id=? AND owner=?", (course_id, owner)
            ).fetchone()
            if row is None:
                raise ServiceError("Mata kuliah tidak ditemukan.", 404)
            result = {key: row[key] for key in ("id", "name", "semester", "created_at")}
            result["document_ids"] = [
                r[0]
                for r in db.execute(
                    "SELECT document_id FROM course_documents JOIN documents ON documents.id=document_id WHERE course_id=? AND documents.status='ready'",
                    (course_id,),
                )
            ]
        return result

    def courses(self, owner):
        with self.catalog.connect() as db:
            ids = [
                row[0]
                for row in db.execute(
                    "SELECT id FROM courses WHERE owner=? ORDER BY created_at", (owner,)
                )
            ]
        return [self.course(course_id, owner) for course_id in ids]

    def create_course(self, owner, name, semester):
        course_id = uuid.uuid4().hex
        with self.catalog.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                db.execute("SELECT COUNT(*) FROM courses WHERE owner=?", (owner,)).fetchone()[0]
                >= 100
            ):
                raise ServiceError("Maksimal 100 mata kuliah. Hapus yang tidak digunakan.", 409)
            db.execute(
                "INSERT INTO courses VALUES(?,?,?,?,?)",
                (course_id, owner, name, semester, utcnow().isoformat()),
            )
        return self.course(course_id, owner)

    def set_documents(self, course_id, owner, document_ids):
        with self.catalog.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute(
                "SELECT id FROM courses WHERE id=? AND owner=?", (course_id, owner)
            ).fetchone():
                raise ServiceError("Mata kuliah tidak ditemukan.", 404)
            for document_id in document_ids:
                if not db.execute(
                    "SELECT id FROM documents WHERE id=? AND owner=? AND status='ready'",
                    (document_id, owner),
                ).fetchone():
                    raise ServiceError("Materi tidak ditemukan atau tidak dapat diakses.", 404)
            db.execute("DELETE FROM course_documents WHERE course_id=?", (course_id,))
            db.executemany(
                "INSERT INTO course_documents VALUES(?,?)",
                [(course_id, document_id) for document_id in document_ids],
            )
        return self.course(course_id, owner)

    def delete_course(self, course_id, owner):
        self.course(course_id, owner)
        with self.catalog.connect() as db:
            db.execute("DELETE FROM courses WHERE id=? AND owner=?", (course_id, owner))

    def validate_scope(self, owner, document_ids, course_id=None):
        for document_id in document_ids:
            self.catalog.get(document_id, owner)
        if course_id and not set(document_ids).issubset(
            self.course(course_id, owner)["document_ids"]
        ):
            raise ServiceError("Pilih materi yang terdaftar pada mata kuliah ini.", 409)

    def save(self, owner, course_id, document_ids, kind, title, payload):
        item_id = uuid.uuid4().hex
        now = utcnow().isoformat()
        with self.catalog.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                db.execute("SELECT COUNT(*) FROM study_items WHERE owner=?", (owner,)).fetchone()[0]
                >= 500
            ):
                raise ServiceError(
                    "Rak belajar penuh (500 hasil). Hapus hasil yang tidak diperlukan.", 409
                )
            # Revalidate after model work: documents/course may have been deleted meanwhile.
            self.validate_scope(owner, document_ids, course_id)
            db.execute(
                "INSERT INTO study_items(id,owner,course_id,kind,title,payload,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    item_id,
                    owner,
                    course_id,
                    kind,
                    title[:160],
                    json.dumps(payload, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            db.executemany(
                "INSERT INTO study_item_documents VALUES(?,?)",
                [(item_id, document_id) for document_id in document_ids],
            )
        return self.item(item_id, owner)

    def item(self, item_id, owner):
        with self.catalog.connect() as db:
            row = db.execute(
                "SELECT * FROM study_items WHERE id=? AND owner=?", (item_id, owner)
            ).fetchone()
            if row is None:
                raise ServiceError("Hasil belajar tidak ditemukan.", 404)
            result = dict(row)
            result.pop("owner")
            result["payload"] = json.loads(result["payload"])
            result["document_ids"] = [
                r[0]
                for r in db.execute(
                    "SELECT document_id FROM study_item_documents WHERE item_id=? ORDER BY document_id",
                    (item_id,),
                )
            ]
            latest = db.execute(
                "SELECT feedback FROM quiz_attempts WHERE item_id=? ORDER BY created_at DESC LIMIT 1",
                (item_id,),
            ).fetchone()
            result["latest_attempt"] = json.loads(latest[0]) if latest else None
            result["reviews"] = [
                dict(r)
                for r in db.execute(
                    "SELECT card_index,rating,due_at,interval_days FROM card_reviews WHERE item_id=?",
                    (item_id,),
                )
            ]
        return result

    def items(self, owner, course_id=None):
        with self.catalog.connect() as db:
            query = "SELECT id,course_id,kind,title,created_at,updated_at FROM study_items WHERE owner=?"
            args = [owner]
            if course_id:
                self.course(course_id, owner)
                query += " AND course_id=?"
                args.append(course_id)
            return [dict(row) for row in db.execute(query + " ORDER BY updated_at DESC", args)]

    def update_chat(self, item_id, owner, payload, revision):
        with self.catalog.connect() as db:
            result = db.execute(
                "UPDATE study_items SET payload=?,revision=revision+1,updated_at=? WHERE id=? AND owner=? AND revision=?",
                (
                    json.dumps(payload, ensure_ascii=False),
                    utcnow().isoformat(),
                    item_id,
                    owner,
                    revision,
                ),
            )
            if result.rowcount != 1:
                raise ServiceError("Percakapan berubah. Muat ulang sebelum mengirim pesan.", 409)
        return self.item(item_id, owner)

    def notes(self, item_id, owner, notes):
        self.item(item_id, owner)
        with self.catalog.connect() as db:
            db.execute(
                "UPDATE study_items SET notes=?,updated_at=? WHERE id=? AND owner=?",
                (notes, utcnow().isoformat(), item_id, owner),
            )

    def delete_item(self, item_id, owner):
        self.item(item_id, owner)
        with self.catalog.connect() as db:
            db.execute("DELETE FROM study_items WHERE id=? AND owner=?", (item_id, owner))

    def attempt(self, item_id, owner, answers):
        item = self.item(item_id, owner)
        if item["kind"] != "quiz":
            raise ServiceError("Hasil ini bukan latihan soal.")
        questions = item["payload"]["content"]["questions"]
        if len(answers) != len(questions):
            raise ServiceError("Jawab semua soal sebelum memeriksa hasil.", 422)
        feedback = []
        for index, (question, answer) in enumerate(zip(questions, answers)):
            feedback.append(
                {
                    "question_index": index,
                    "selected_index": answer,
                    "correct_index": question["correct_index"],
                    "correct": answer == question["correct_index"],
                    "explanation": question["explanation"],
                    "source_ids": question["source_ids"],
                }
            )
        result = {
            "id": uuid.uuid4().hex,
            "correct": sum(row["correct"] for row in feedback),
            "total": len(questions),
            "feedback": feedback,
            "created_at": utcnow().isoformat(),
        }
        result["score"] = round(result["correct"] / result["total"] * 100, 1)
        with self.catalog.connect() as db:
            db.execute(
                "INSERT INTO quiz_attempts VALUES(?,?,?,?,?)",
                (
                    result["id"],
                    item_id,
                    result["score"],
                    json.dumps(result, ensure_ascii=False),
                    result["created_at"],
                ),
            )
        return result

    def review_card(self, item_id, owner, card_index, rating):
        item = self.item(item_id, owner)
        if item["kind"] != "flashcards" or card_index >= len(item["payload"]["content"]["cards"]):
            raise ServiceError("Kartu tidak ditemukan.", 404)
        now = utcnow()
        with self.catalog.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT interval_days FROM card_reviews WHERE item_id=? AND card_index=?",
                (item_id, card_index),
            ).fetchone()
            previous = old[0] if old else 0
            days = (
                0
                if rating == "again"
                else min(30, max(1, previous * 2))
                if rating == "good"
                else min(60, max(3, previous * 3))
            )
            due = now + (timedelta(minutes=10) if rating == "again" else timedelta(days=days))
            db.execute(
                "INSERT OR REPLACE INTO card_reviews VALUES(?,?,?,?,?,?)",
                (item_id, card_index, rating, days, due.isoformat(), now.isoformat()),
            )
        return {
            "card_index": card_index,
            "rating": rating,
            "due_at": due.isoformat(),
            "interval_days": days,
        }

    def progress(self, owner, course_id=None):
        items = self.items(owner, course_id)
        due = 0
        attempts = []
        now = utcnow().isoformat()
        for summary in items:
            item = self.item(summary["id"], owner)
            if item["kind"] == "flashcards":
                reviews = {row["card_index"]: row for row in item["reviews"]}
                due += sum(
                    index not in reviews or reviews[index]["due_at"] <= now
                    for index in range(len(item["payload"]["content"]["cards"]))
                )
            if item["latest_attempt"]:
                attempts.append(item["latest_attempt"]["score"])
        return {
            "saved_items": len(items),
            "quiz_sets_completed": len(attempts),
            "mean_latest_quiz_score": round(sum(attempts) / len(attempts), 1) if attempts else None,
            "cards_due": due,
        }
