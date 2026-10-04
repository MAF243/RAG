import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from services.errors import ServiceError


class Catalog:
    """Only ready records are retrievable; unfinished collections are never visible."""

    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL,
                sha256 TEXT NOT NULL, status TEXT NOT NULL, pages INTEGER DEFAULT 0,
                chunks INTEGER DEFAULT 0, created_at TEXT NOT NULL,
                embedding_model TEXT NOT NULL, UNIQUE(owner, sha256))""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, document_id, owner, name, digest, model, quota):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM documents WHERE owner=? AND sha256=?", (owner, digest)
            ).fetchone()
            if existing:
                if existing["status"] == "ready":
                    return dict(existing)
                raise ServiceError("Dokumen yang sama sedang diproses. Coba lagi nanti.", 409)
            count = db.execute("SELECT COUNT(*) FROM documents WHERE owner=?", (owner,)).fetchone()[
                0
            ]
            if count >= quota:
                raise ServiceError(
                    "Batas jumlah dokumen tercapai. Hapus dokumen yang tidak digunakan.", 409
                )
            db.execute(
                "INSERT INTO documents(id,owner,name,sha256,status,created_at,embedding_model) VALUES(?,?,?,?,?,?,?)",
                (
                    document_id,
                    owner,
                    name,
                    digest,
                    "processing",
                    datetime.now(timezone.utc).isoformat(),
                    model,
                ),
            )
        return None

    def ready(self, document_id, pages, chunks):
        with self.connect() as db:
            db.execute(
                "UPDATE documents SET status='ready', pages=?, chunks=? WHERE id=?",
                (pages, chunks, document_id),
            )

    def list(self, owner):
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM documents WHERE owner=? AND status='ready' ORDER BY created_at DESC",
                    (owner,),
                )
            ]

    def get(self, document_id, owner):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM documents WHERE id=? AND owner=? AND status='ready'",
                (document_id, owner),
            ).fetchone()
        if row is None:
            raise ServiceError("Dokumen tidak ditemukan atau tidak dapat diakses.", 404)
        return dict(row)

    def hide(self, document_id):
        with self.connect() as db:
            db.execute("UPDATE documents SET status='deleting' WHERE id=?", (document_id,))

    def remove(self, document_id):
        with self.connect() as db:
            db.execute("DELETE FROM documents WHERE id=?", (document_id,))

    def unfinished(self):
        with self.connect() as db:
            return [
                dict(row) for row in db.execute("SELECT * FROM documents WHERE status!='ready'")
            ]
