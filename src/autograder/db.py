"""
PostgreSQL + pgvector persistence for GRADE.

Requires ``GRADE_DATABASE_URL`` or ``DATABASE_URL`` and
``pip install -e ".[api]"`` or ``pip install 'psycopg[binary]' pgvector``.

Connections use ``_connection_dsn()`` which may set ``hostaddr`` from automatic DNS resolution,
``GRADE_DATABASE_HOSTADDR`` (manual IP when system DNS fails), or related env vars
(``GRADE_PG_SKIP_HOSTADDR_RESOLVE``, ``GRADE_PG_PREFER_ADDR_FAMILY``).
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import uuid
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Json

try:
    from pgvector.psycopg import Vector, register_vector
except ImportError:  # pragma: no cover - optional deps
    Vector = None  # type: ignore[misc, assignment]
    register_vector = None  # type: ignore[misc, assignment]


def _dsn() -> str:
    url = (os.environ.get("GRADE_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError(
            "GRADE_DATABASE_URL or DATABASE_URL must be set (PostgreSQL is required; SQLite is not supported)."
        )
    return url


def _host_is_numeric(host: str) -> bool:
    """True if host is already an IP literal (IPv4/IPv6), not a DNS name."""
    h = host.strip("[]")
    if "%" in h:
        h = h.split("%", 1)[0]
    try:
        ipaddress.ip_address(h)
        return True
    except ValueError:
        return False


def _parse_manual_hostaddr(raw: str) -> Optional[str]:
    """Normalize GRADE_DATABASE_HOSTADDR to a string libpq accepts (IPv4 or IPv6)."""
    s = raw.strip()
    if not s:
        return None
    s = s.strip("[]")
    if "%" in s:
        s = s.split("%", 1)[0]
    try:
        return str(ipaddress.ip_address(s))
    except ValueError:
        return None


def _connection_dsn() -> str:
    """
    Connection string for psycopg, with optional DNS pre-resolution.

    Resolves the hostname with Python's ``getaddrinfo`` and sets ``hostaddr`` so libpq
    connects by IP while ``host`` stays the original name (TLS/SNI). This often fixes
    Windows setups where libpq fails DNS but Python succeeds.

    Set ``GRADE_PG_SKIP_HOSTADDR_RESOLVE=1`` to disable automatic resolution.

    If **system DNS fails** but you can resolve the host elsewhere (e.g. ``nslookup``), set
    ``GRADE_DATABASE_HOSTADDR`` to that IPv4 or IPv6 literal; TLS still uses the hostname from the URL.

    Optional ``GRADE_PG_PREFER_ADDR_FAMILY`` may be ``ipv4`` (default) or ``ipv6`` when both exist.
    """
    raw = _dsn()
    flag = (os.environ.get("GRADE_PG_SKIP_HOSTADDR_RESOLVE") or "").strip().lower()
    if flag in ("1", "true", "yes"):
        return raw
    try:
        parts = conninfo_to_dict(raw)
    except Exception:
        return raw
    if parts.get("hostaddr"):
        return raw
    manual = _parse_manual_hostaddr(os.environ.get("GRADE_DATABASE_HOSTADDR") or "")
    if manual:
        merged = dict(parts)
        merged["hostaddr"] = manual
        try:
            return make_conninfo(**merged)
        except Exception:
            return raw
    host = parts.get("host")
    if not host or _host_is_numeric(host):
        return raw
    port_s = parts.get("port")
    try:
        port = int(port_s) if port_s is not None and str(port_s).strip() != "" else 5432
    except (TypeError, ValueError):
        port = 5432
    prefer = (os.environ.get("GRADE_PG_PREFER_ADDR_FAMILY") or "").strip().lower()
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except OSError:
        return raw
    if not infos:
        return raw
    if prefer == "ipv6":
        infos.sort(key=lambda a: (0 if a[0] == socket.AF_INET6 else 1))
    elif prefer == "ipv4":
        infos.sort(key=lambda a: (0 if a[0] == socket.AF_INET else 1))
    else:
        infos.sort(key=lambda a: (0 if a[0] == socket.AF_INET else 1))
    ip = infos[0][4][0]
    merged = dict(parts)
    merged["hostaddr"] = ip
    try:
        return make_conninfo(**merged)
    except Exception:
        return raw


def _pg_connect(
    *,
    row_factory=None,
    autocommit: bool = False,
    connect_timeout: int | None = None,
):
    """
    Open a psycopg connection.

    ``prepare_threshold=0`` disables server-side prepared statements, which break on
    Supabase pooler / PgBouncer (transaction mode, port 6543) with
    ``DuplicatePreparedStatement: prepared statement "_pg3_0" already exists``.
    """
    kw: Dict[str, Any] = {"prepare_threshold": 0}
    if row_factory is not None:
        kw["row_factory"] = row_factory
    if autocommit:
        kw["autocommit"] = True
    if connect_timeout is not None:
        kw["connect_timeout"] = connect_timeout
    conn = psycopg.connect(_connection_dsn(), **kw)
    # Belt-and-suspenders for PgBouncer / Supabase pooler (port 6543).
    conn.prepare_threshold = 0
    return conn


def _pg_execute(cur, query: str, params: Any = None) -> None:
    """Run SQL without server-side prepared statements (required for transaction pooler)."""
    cur.execute(query, params, prepare=False)


def _register_pgvector(conn) -> None:
    """
    Register pgvector psycopg adapters.

    ``pgvector.psycopg.register_vector`` uses ``TypeInfo.fetch``, which prepares statements
    and breaks on Supabase / PgBouncer transaction poolers (port 6543).
    """
    if register_vector is None:
        return
    from psycopg.types import TypeInfo
    from pgvector.psycopg.bit import register_bit_info
    from pgvector.psycopg.halfvec import register_halfvec_info
    from pgvector.psycopg.sparsevec import register_sparsevec_info
    from pgvector.psycopg.vector import register_vector_info

    def _type_info(name: str) -> Optional[TypeInfo]:
        with conn.cursor() as cur:
            _pg_execute(
                cur,
                "SELECT oid, typarray FROM pg_type WHERE typname = %s",
                (name,),
            )
            row = cur.fetchone()
        if not row:
            return None
        oid = row["oid"] if isinstance(row, dict) else row[0]
        array_oid = row["typarray"] if isinstance(row, dict) else row[1]
        return TypeInfo(name=name, oid=int(oid), array_oid=int(array_oid))

    for typname, reg_fn in (
        ("vector", register_vector_info),
        ("bit", register_bit_info),
        ("halfvec", register_halfvec_info),
        ("sparsevec", register_sparsevec_info),
    ):
        info = _type_info(typname)
        if info is not None:
            reg_fn(conn, info)


def _require_vector_deps() -> None:
    if Vector is None or register_vector is None:
        raise RuntimeError(
            "Install PostgreSQL dependencies: pip install 'psycopg[binary]' pgvector"
        )


def get_conn():
    """Return an open psycopg connection (caller must close)."""
    _require_vector_deps()
    conn = _pg_connect(row_factory=dict_row)
    _register_pgvector(conn)
    return conn


def _connection_target_redacted() -> Optional[str]:
    """Host/port/dbname for status UI (no password)."""
    try:
        parts = conninfo_to_dict(_dsn())
    except Exception:
        return None
    host = parts.get("host") or "?"
    port = parts.get("port") or "5432"
    db = parts.get("dbname") or parts.get("database") or "?"
    return f"{host}:{port}/{db}"


def database_status() -> Dict[str, Any]:
    """
    Live connectivity probe for PostgreSQL + pgvector (RAG + evaluation persistence).

    Used by ``/health``, ``/api/integrations``, and ``/api/database/status``.
    """
    required_tables = (
        "answer_keys",
        "answer_key_chunks",
        "sheets",
        "rag_chunks",
        "evaluation_results",
    )
    out: Dict[str, Any] = {
        "configured": False,
        "connected": False,
        "postgres_deps_installed": Vector is not None and register_vector is not None,
        "pgvector_extension": False,
        "schema_ready": False,
        "rag_ready": False,
        "evaluation_ready": False,
        "tables": {t: False for t in required_tables},
        "target": None,
        "error": None,
        "counts": {
            "answer_keys": 0,
            "sheets": 0,
            "rag_chunks": 0,
            "evaluation_results": 0,
        },
    }
    try:
        _dsn()
        out["configured"] = True
        out["target"] = _connection_target_redacted()
    except RuntimeError as e:
        out["error"] = str(e)
        return out

    if not out["postgres_deps_installed"]:
        out["error"] = "Install psycopg + pgvector: pip install -e \".[api]\""
        return out

    try:
        with _pg_connect(row_factory=dict_row, connect_timeout=8) as conn:
            with conn.cursor() as cur:
                _pg_execute(cur,
                    "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') AS ok"
                )
                out["pgvector_extension"] = bool((cur.fetchone() or {}).get("ok"))

                for table in required_tables:
                    _pg_execute(cur,
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_schema = 'public' AND table_name = %s
                        ) AS ok
                        """,
                        (table,),
                    )
                    out["tables"][table] = bool((cur.fetchone() or {}).get("ok"))

                out["schema_ready"] = all(out["tables"].values())
                out["rag_ready"] = (
                    out["schema_ready"]
                    and out["pgvector_extension"]
                    and out["tables"]["rag_chunks"]
                )
                out["evaluation_ready"] = out["schema_ready"] and out["tables"]["evaluation_results"]

                if out["tables"]["answer_keys"]:
                    _pg_execute(cur,"SELECT COUNT(*)::bigint AS c FROM public.answer_keys")
                    out["counts"]["answer_keys"] = int((cur.fetchone() or {}).get("c") or 0)
                if out["tables"]["sheets"]:
                    _pg_execute(cur,"SELECT COUNT(*)::bigint AS c FROM public.sheets")
                    out["counts"]["sheets"] = int((cur.fetchone() or {}).get("c") or 0)
                if out["tables"]["rag_chunks"]:
                    _pg_execute(cur,"SELECT COUNT(*)::bigint AS c FROM public.rag_chunks")
                    out["counts"]["rag_chunks"] = int((cur.fetchone() or {}).get("c") or 0)
                if out["tables"]["evaluation_results"]:
                    _pg_execute(cur,
                        "SELECT COUNT(*)::bigint AS c FROM public.evaluation_results"
                    )
                    out["counts"]["evaluation_results"] = int((cur.fetchone() or {}).get("c") or 0)

        out["connected"] = True
        if out["connected"] and not out["schema_ready"]:
            missing = [t for t in required_tables if not out["tables"][t]]
            out["error"] = f"Schema incomplete; missing tables: {', '.join(missing)}. Run init_db or migrations."
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


# ---------------------------------------------------------------------------
# Natural-sort backfill (tests / one-off migration helpers)
# ---------------------------------------------------------------------------


def _natural_question_id_key(question_id: str) -> List[Any]:
    """Sort key so Q2 < Q10 (lexicographic order would place Q10 before Q2)."""
    parts = re.split(r"(\d+)", question_id)
    out: List[Any] = []
    for p in parts:
        if not p:
            continue
        out.append(int(p) if p.isdigit() else p.lower())
    return out


def _backfill_answer_keys_sort_order_natural(conn) -> None:
    """Reassign sort_order per exam_id by natural order of question_id (legacy data fix)."""
    with conn.cursor() as cur:
        _pg_execute(cur,"SELECT DISTINCT exam_id FROM public.answer_keys")
        exams = cur.fetchall()
        for row in exams:
            exam_id = row["exam_id"] if isinstance(row, dict) else row[0]
            _pg_execute(cur,
                "SELECT id, question_id FROM public.answer_keys WHERE exam_id = %s",
                (exam_id,),
            )
            rows = cur.fetchall()
            ordered = sorted(
                rows,
                key=lambda r: _natural_question_id_key(
                    r["question_id"] if isinstance(r, dict) else r[1]
                ),
            )
            for i, row in enumerate(ordered):
                row_id = row["id"] if isinstance(row, dict) else row[0]
                _pg_execute(cur,
                    "UPDATE public.answer_keys SET sort_order = %s WHERE id = %s",
                    (i, row_id),
                )
    conn.commit()


# Applied on init_db when tables may be missing (idempotent; matches supabase/migrations).
_SCHEMA_STATEMENTS: List[str] = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    "COMMENT ON EXTENSION vector IS 'pgvector — embedding storage and similarity search for GRADE answer_keys'",
    """
CREATE TABLE IF NOT EXISTS public.sheets (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    exam_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
""".strip(),
    "COMMENT ON TABLE public.sheets IS 'Scanned answer sheets; path is filesystem or storage URI resolved by the API'",
    "ALTER TABLE public.sheets ADD COLUMN IF NOT EXISTS exam_id TEXT",
    """
CREATE INDEX IF NOT EXISTS idx_sheets_exam_created
    ON public.sheets (exam_id, created_at DESC)
""".strip(),
    """
CREATE TABLE IF NOT EXISTS public.answer_keys (
    id TEXT PRIMARY KEY,
    exam_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    expected_answer TEXT NOT NULL,
    embedding vector(128) NOT NULL,
    max_marks DOUBLE PRECISION NOT NULL CHECK (max_marks > 0),
    domain TEXT NOT NULL DEFAULT 'general',
    rubric_override JSONB,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
""".strip(),
    "COMMENT ON TABLE public.answer_keys IS 'Model answers; sort_order preserves upload / sheet row order'",
    "COMMENT ON COLUMN public.answer_keys.embedding IS '128-D document vector; granular chunks in answer_key_chunks'",
    """
CREATE INDEX IF NOT EXISTS idx_answer_keys_exam_sort
    ON public.answer_keys (exam_id, sort_order ASC, question_id ASC)
""".strip(),
    """
CREATE INDEX IF NOT EXISTS idx_answer_keys_embedding_hnsw
    ON public.answer_keys
    USING hnsw (embedding vector_cosine_ops)
""".strip(),
    """
CREATE TABLE IF NOT EXISTS public.answer_key_chunks (
    chunk_id TEXT PRIMARY KEY,
    answer_key_id TEXT NOT NULL REFERENCES public.answer_keys (id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    embedding vector(128) NOT NULL,
    char_start INTEGER,
    char_end INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_answer_key_chunks_key_index UNIQUE (answer_key_id, chunk_index)
)
""".strip(),
    "COMMENT ON TABLE public.answer_key_chunks IS 'Chunked model-answer text + embeddings for granular retrieval'",
    """
CREATE INDEX IF NOT EXISTS idx_answer_key_chunks_key_id
    ON public.answer_key_chunks (answer_key_id, chunk_index ASC)
""".strip(),
    """
CREATE INDEX IF NOT EXISTS idx_answer_key_chunks_embedding_hnsw
    ON public.answer_key_chunks
    USING hnsw (embedding vector_cosine_ops)
""".strip(),
    """
CREATE TABLE IF NOT EXISTS public.evaluation_results (
    id TEXT PRIMARY KEY,
    sheet_id TEXT NOT NULL,
    exam_id TEXT NOT NULL,
    per_question_scores JSONB NOT NULL,
    total_marks DOUBLE PRECISION NOT NULL,
    max_total DOUBLE PRECISION NOT NULL,
    confidence_flag BOOLEAN NOT NULL DEFAULT FALSE,
    grading_confidence TEXT,
    ocr_engine_used TEXT,
    prompt_hash TEXT,
    llm_model TEXT,
    flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_evaluation_results_sheet
        FOREIGN KEY (sheet_id) REFERENCES public.sheets (id) ON DELETE CASCADE
)
""".strip(),
    "COMMENT ON COLUMN public.evaluation_results.per_question_scores IS 'Array of question result objects (same shape as API questions[])'",
    "COMMENT ON COLUMN public.evaluation_results.flags IS 'JSON array of string flags'",
    """
CREATE INDEX IF NOT EXISTS idx_evaluation_results_sheet
    ON public.evaluation_results (sheet_id)
""".strip(),
    """
CREATE INDEX IF NOT EXISTS idx_evaluation_results_exam_created
    ON public.evaluation_results (exam_id, created_at DESC)
""".strip(),
    """
CREATE TABLE IF NOT EXISTS public.rag_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    embedding vector(128) NOT NULL,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
""".strip(),
    "COMMENT ON TABLE public.rag_chunks IS 'OCR/RAG text chunks with embed_text_local(128-D) vectors for retrieval'",
    """
CREATE INDEX IF NOT EXISTS idx_rag_chunks_document_id
    ON public.rag_chunks (document_id)
""".strip(),
    """
CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding_hnsw
    ON public.rag_chunks
    USING hnsw (embedding vector_cosine_ops)
""".strip(),
    """
CREATE INDEX IF NOT EXISTS idx_rag_chunks_text_fts
    ON public.rag_chunks
    USING gin (to_tsvector('english', text_content))
""".strip(),
]


def init_db() -> None:
    _require_vector_deps()
    with _pg_connect( autocommit=True) as conn:
        with conn.cursor() as cur:
            for stmt in _SCHEMA_STATEMENTS:
                try:
                    _pg_execute(cur,stmt)
                except psycopg.Error as e:
                    msg = str(e).lower()
                    if any(
                        s in msg
                        for s in (
                            "already exists",
                            "duplicate",
                            "permission denied",
                            "must be owner",
                            "only superuser",
                        )
                    ):
                        continue
                    raise


def insert_sheet(filename: str, path: str, exam_id: Optional[str] = None) -> str:
    sheet_id = str(uuid.uuid4())
    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(cur,
                "INSERT INTO public.sheets (id, filename, path, exam_id) VALUES (%s, %s, %s, %s)",
                (sheet_id, filename, path, exam_id),
            )
    return sheet_id


def get_sheet(sheet_id: str) -> Optional[Dict[str, Any]]:
    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(cur,"SELECT * FROM public.sheets WHERE id = %s", (sheet_id,))
            row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    if d.get("created_at") is not None:
        d["created_at"] = str(d["created_at"])
    return d


def list_sheets(
    *,
    exam_id: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    limit = max(1, min(1000, int(limit)))
    offset = max(0, int(offset))
    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            if exam_id:
                _pg_execute(cur,
                    """
                    SELECT id, filename, path, exam_id, created_at
                    FROM public.sheets
                    WHERE exam_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (exam_id, limit, offset),
                )
            else:
                _pg_execute(cur,
                    """
                    SELECT id, filename, path, exam_id, created_at
                    FROM public.sheets
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
            rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        if d.get("created_at") is not None:
            d["created_at"] = str(d["created_at"])
        out.append(d)
    return out


def upsert_answer_key_chunks(
    answer_key_id: str,
    chunks: List[Dict[str, Any]],
) -> int:
    """Replace all chunk rows for one answer key."""
    if not chunks:
        with _pg_connect(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                _pg_execute(
                    cur,
                    "DELETE FROM public.answer_key_chunks WHERE answer_key_id = %s",
                    (answer_key_id,),
                )
            conn.commit()
        return 0

    _require_vector_deps()
    with _pg_connect(row_factory=dict_row) as conn:
        _register_pgvector(conn)
        with conn.cursor() as cur:
            _pg_execute(
                cur,
                "DELETE FROM public.answer_key_chunks WHERE answer_key_id = %s",
                (answer_key_id,),
            )
            for ch in chunks:
                _pg_execute(
                    cur,
                    """
                    INSERT INTO public.answer_key_chunks (
                        chunk_id, answer_key_id, chunk_index, text_content,
                        embedding, char_start, char_end
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        ch["chunk_id"],
                        answer_key_id,
                        int(ch["chunk_index"]),
                        ch["text_content"],
                        Vector(ch["embedding"]),
                        ch.get("char_start"),
                        ch.get("char_end"),
                    ),
                )
        conn.commit()
    return len(chunks)


def _attach_answer_chunks(keys: List[Dict[str, Any]]) -> None:
    """Add ``answer_chunks`` list to each key dict (mutates in place)."""
    if not keys:
        return
    ids = [str(k["id"]) for k in keys]
    by_key: Dict[str, List[Dict[str, Any]]] = {kid: [] for kid in ids}
    _require_vector_deps()
    with _pg_connect(row_factory=dict_row) as conn:
        _register_pgvector(conn)
        with conn.cursor() as cur:
            _pg_execute(
                cur,
                """
                SELECT answer_key_id, chunk_id, chunk_index, text_content, embedding,
                       char_start, char_end
                FROM public.answer_key_chunks
                WHERE answer_key_id = ANY(%s)
                ORDER BY answer_key_id, chunk_index ASC
                """,
                (ids,),
            )
            for row in cur.fetchall():
                item = dict(row)
                emb = item.pop("embedding", None)
                item["embedding"] = [float(x) for x in emb] if emb is not None else []
                kid = str(item.pop("answer_key_id"))
                by_key.setdefault(kid, []).append(item)
    for k in keys:
        k["answer_chunks"] = by_key.get(str(k["id"]), [])


def insert_answer_key(
    exam_id: str,
    question_id: str,
    expected_answer: str,
    embedding: Optional[List[float]],
    max_marks: float,
    domain: str,
    rubric_override: Optional[dict],
    sort_order: int = 0,
    *,
    answer_chunks: Optional[List[Dict[str, Any]]] = None,
) -> str:
    from autograder.key_chunks import aggregate_key_embedding, build_answer_key_chunks
    from autograder.embeddings import embed_text

    _require_vector_deps()
    key_id = str(uuid.uuid4())
    chunks = answer_chunks
    if chunks is None:
        chunks = build_answer_key_chunks(expected_answer, key_id=key_id)
    if not chunks:
        vec = embedding if embedding else embed_text(expected_answer)
        chunks = [
            {
                "chunk_id": f"{key_id}_c0",
                "chunk_index": 0,
                "text_content": expected_answer.strip(),
                "embedding": vec,
                "char_start": 0,
                "char_end": len(expected_answer.strip()),
            }
        ]
    if not embedding:
        embedding = aggregate_key_embedding(chunks) or embed_text(expected_answer)
    rub = Json(rubric_override) if rubric_override is not None else None
    with _pg_connect(row_factory=dict_row) as conn:
        _register_pgvector(conn)
        with conn.cursor() as cur:
            _pg_execute(cur,
                """
                INSERT INTO public.answer_keys(
                    id, exam_id, question_id, expected_answer, embedding, max_marks,
                    domain, rubric_override, sort_order
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    key_id,
                    exam_id,
                    question_id,
                    expected_answer,
                    Vector(embedding),
                    max_marks,
                    domain,
                    rub,
                    sort_order,
                ),
            )
    upsert_answer_key_chunks(key_id, chunks)
    return key_id


def delete_answer_keys_for_exam(exam_id: str) -> int:
    """Remove all answer keys for an exam (used before bundle re-upload)."""
    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(cur, "DELETE FROM public.answer_keys WHERE exam_id = %s", (exam_id,))
            n = cur.rowcount or 0
        conn.commit()
    return n


def list_answer_keys(exam_id: str) -> List[Dict[str, Any]]:
    _require_vector_deps()
    with _pg_connect(row_factory=dict_row) as conn:
        _register_pgvector(conn)
        with conn.cursor() as cur:
            _pg_execute(cur,
                """
                SELECT id, exam_id, question_id, expected_answer, embedding, max_marks,
                       domain, rubric_override, sort_order, created_at
                FROM public.answer_keys
                WHERE exam_id = %s
                ORDER BY sort_order ASC, question_id ASC
                """,
                (exam_id,),
            )
            rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        # pgvector/psycopg may yield numpy scalars; JSON needs plain Python float.
        emb = item.get("embedding")
        if emb is None:
            item["embedding"] = []
        else:
            item["embedding"] = [float(x) for x in emb]
        ro = item.get("rubric_override")
        if isinstance(ro, str):
            item["rubric_override"] = json.loads(ro) if ro else None
        if item.get("created_at") is not None:
            item["created_at"] = str(item["created_at"])
        out.append(item)
    try:
        _attach_answer_chunks(out)
    except Exception:
        for item in out:
            item.setdefault("answer_chunks", [])
    return out


def next_answer_key_sort_order_start(exam_id: str) -> int:
    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(cur,
                "SELECT COALESCE(MAX(sort_order), -1) AS m FROM public.answer_keys WHERE exam_id = %s",
                (exam_id,),
            )
            row = cur.fetchone()
    return int(row["m"]) + 1


def insert_evaluation_result(payload: Dict[str, Any]) -> str:
    result_id = str(uuid.uuid4())
    flags = payload.get("flags", [])
    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(cur,
                """
                INSERT INTO public.evaluation_results(
                    id, sheet_id, exam_id, per_question_scores, total_marks, max_total,
                    confidence_flag, grading_confidence, ocr_engine_used, prompt_hash,
                    llm_model, flags
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    result_id,
                    payload["sheet_id"],
                    payload["exam_id"],
                    Json(payload["questions"]),
                    payload["total_marks"],
                    payload["max_total"],
                    bool(payload["confidence_flag"]),
                    payload["grading_confidence"],
                    payload.get("ocr_engine_used", "mixed"),
                    payload["prompt_hash"],
                    payload["llm_model"],
                    Json(flags),
                ),
            )
    return result_id


def _coerce_json_field(val: Any) -> Any:
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        return json.loads(val)
    return val


def get_result(result_id: str) -> Optional[Dict[str, Any]]:
    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(cur,"SELECT * FROM public.evaluation_results WHERE id = %s", (result_id,))
            row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["questions"] = _coerce_json_field(d["per_question_scores"])
    d["flags"] = _coerce_json_field(d["flags"])
    if not isinstance(d["flags"], list):
        d["flags"] = []
    d["confidence_flag"] = bool(d["confidence_flag"])
    if d.get("created_at") is not None:
        d["created_at"] = str(d["created_at"])
    return d


def list_results(
    *,
    exam_id: Optional[str] = None,
    sheet_id: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    limit = max(1, min(1000, int(limit)))
    offset = max(0, int(offset))
    clauses: List[str] = []
    args: List[Any] = []
    if exam_id:
        clauses.append("exam_id = %s")
        args.append(exam_id)
    if sheet_id:
        clauses.append("sheet_id = %s")
        args.append(sheet_id)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT id, sheet_id, exam_id, total_marks, max_total, confidence_flag,
               grading_confidence, prompt_hash, llm_model, flags, created_at
        FROM public.evaluation_results
        {where_sql}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    args.extend([limit, offset])
    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(cur,sql, tuple(args))
            rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        d["flags"] = _coerce_json_field(d.get("flags"))
        if not isinstance(d.get("flags"), list):
            d["flags"] = []
        d["confidence_flag"] = bool(d.get("confidence_flag"))
        if d.get("created_at") is not None:
            d["created_at"] = str(d["created_at"])
        out.append(d)
    return out


def list_exams_with_counts(limit: int = 500) -> List[Dict[str, Any]]:
    limit = max(1, min(2000, int(limit)))
    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(cur,
                """
                WITH exams AS (
                    SELECT exam_id FROM public.answer_keys
                    UNION
                    SELECT exam_id FROM public.sheets WHERE exam_id IS NOT NULL
                    UNION
                    SELECT exam_id FROM public.evaluation_results
                )
                SELECT
                    e.exam_id AS exam_id,
                    e.exam_id AS title,
                    COALESCE(ak.key_count, 0) AS key_count,
                    COALESCE(sh.sheet_count, 0) AS sheet_count,
                    ev.last_eval_at AS last_eval_at
                FROM exams e
                LEFT JOIN (
                    SELECT exam_id, COUNT(*)::int AS key_count
                    FROM public.answer_keys
                    GROUP BY exam_id
                ) ak ON ak.exam_id = e.exam_id
                LEFT JOIN (
                    SELECT exam_id, COUNT(*)::int AS sheet_count
                    FROM public.sheets
                    WHERE exam_id IS NOT NULL
                    GROUP BY exam_id
                ) sh ON sh.exam_id = e.exam_id
                LEFT JOIN (
                    SELECT exam_id, MAX(created_at) AS last_eval_at
                    FROM public.evaluation_results
                    GROUP BY exam_id
                ) ev ON ev.exam_id = e.exam_id
                ORDER BY ev.last_eval_at DESC NULLS LAST, e.exam_id ASC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        if d.get("last_eval_at") is not None:
            d["last_eval_at"] = str(d["last_eval_at"])
        out.append(d)
    return out


def metrics_overview() -> Dict[str, Any]:
    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(cur,
                """
                SELECT
                    (SELECT COUNT(*)::int FROM public.sheets) AS sheets,
                    (SELECT COUNT(*)::int FROM public.answer_keys) AS keys,
                    (SELECT COUNT(*)::int FROM public.evaluation_results) AS results,
                    (SELECT COUNT(DISTINCT exam_id)::int FROM (
                        SELECT exam_id FROM public.answer_keys
                        UNION
                        SELECT exam_id FROM public.sheets WHERE exam_id IS NOT NULL
                        UNION
                        SELECT exam_id FROM public.evaluation_results
                    ) x) AS exams,
                    (SELECT COUNT(*)::int FROM public.evaluation_results
                     WHERE created_at >= NOW() - INTERVAL '24 hours') AS last_24h,
                    (SELECT COALESCE(AVG(
                        CASE WHEN max_total > 0 THEN total_marks / max_total ELSE 0 END
                    ), 0.0) FROM public.evaluation_results) AS avg_total_pct,
                    (SELECT COALESCE(AVG(
                        CASE WHEN confidence_flag THEN 1.0 ELSE 0.0 END
                    ), 0.0) FROM public.evaluation_results) AS low_confidence_rate
                """
            )
            row = cur.fetchone()
    d = dict(row or {})
    return {
        "sheets": int(d.get("sheets") or 0),
        "keys": int(d.get("keys") or 0),
        "results": int(d.get("results") or 0),
        "exams": int(d.get("exams") or 0),
        "last_24h": int(d.get("last_24h") or 0),
        "avg_total_pct": float(d.get("avg_total_pct") or 0.0),
        "low_confidence_rate": float(d.get("low_confidence_rate") or 0.0),
    }


def upsert_rag_chunks_batch(rows: List[Dict[str, Any]]) -> int:
    """
    Insert or update RAG chunks with 128-D embeddings (``embed_text_local``).

    Each row must include: ``chunk_id``, ``document_id``, ``chunk_index``, ``text_content``,
    ``embedding`` (128 floats), and optionally ``meta`` (dict, stored as JSONB).
    """
    if not rows:
        return 0
    _require_vector_deps()
    n = 0
    with _pg_connect(row_factory=dict_row) as conn:
        _register_pgvector(conn)
        with conn.cursor() as cur:
            for r in rows:
                cid = r["chunk_id"]
                did = r["document_id"]
                idx = int(r["chunk_index"])
                txt = r["text_content"]
                emb = r["embedding"]
                meta = Json(r.get("meta") or {})
                _pg_execute(cur,
                    """
                    INSERT INTO public.rag_chunks (
                        chunk_id, document_id, chunk_index, text_content, embedding, meta
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        document_id = EXCLUDED.document_id,
                        chunk_index = EXCLUDED.chunk_index,
                        text_content = EXCLUDED.text_content,
                        embedding = EXCLUDED.embedding,
                        meta = EXCLUDED.meta
                    """,
                    (cid, did, idx, txt, Vector(emb), meta),
                )
                n += 1
        conn.commit()
    return n


def _resolve_document_ids(
    document_id: Optional[str] = None,
    document_ids: Optional[List[str]] = None,
) -> Optional[List[str]]:
    out: List[str] = []
    if document_ids:
        for d in document_ids:
            if d and d not in out:
                out.append(d)
    if document_id and document_id not in out:
        out.append(document_id)
    return out if out else None


def search_rag_chunks_bm25(
    query: str,
    *,
    top_k: int = 10,
    document_id: Optional[str] = None,
    document_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Keyword search on ``rag_chunks.text_content`` (requires ``idx_rag_chunks_text_fts``)."""
    q = (query or "").strip()
    if not q:
        return []
    top_k = max(1, min(100, int(top_k)))
    doc_ids = _resolve_document_ids(document_id, document_ids)
    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            if doc_ids and len(doc_ids) == 1:
                _pg_execute(cur,
                    """
                    SELECT chunk_id, document_id, chunk_index, text_content, meta,
                           ts_rank_cd(
                               to_tsvector('english', text_content),
                               plainto_tsquery('english', %s)
                           ) AS bm25_score
                    FROM public.rag_chunks
                    WHERE document_id = %s
                      AND to_tsvector('english', text_content) @@ plainto_tsquery('english', %s)
                    ORDER BY bm25_score DESC
                    LIMIT %s
                    """,
                    (q, doc_ids[0], q, top_k),
                )
            elif doc_ids:
                _pg_execute(cur,
                    """
                    SELECT chunk_id, document_id, chunk_index, text_content, meta,
                           ts_rank_cd(
                               to_tsvector('english', text_content),
                               plainto_tsquery('english', %s)
                           ) AS bm25_score
                    FROM public.rag_chunks
                    WHERE document_id = ANY(%s::text[])
                      AND to_tsvector('english', text_content) @@ plainto_tsquery('english', %s)
                    ORDER BY bm25_score DESC
                    LIMIT %s
                    """,
                    (q, doc_ids, q, top_k),
                )
            else:
                _pg_execute(cur,
                    """
                    SELECT chunk_id, document_id, chunk_index, text_content, meta,
                           ts_rank_cd(
                               to_tsvector('english', text_content),
                               plainto_tsquery('english', %s)
                           ) AS bm25_score
                    FROM public.rag_chunks
                    WHERE to_tsvector('english', text_content) @@ plainto_tsquery('english', %s)
                    ORDER BY bm25_score DESC
                    LIMIT %s
                    """,
                    (q, q, top_k),
                )
            rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        m = d.get("meta")
        if isinstance(m, str):
            d["meta"] = json.loads(m) if m else {}
        d["distance"] = 1.0 - min(1.0, float(d.get("bm25_score") or 0.0))
        out.append(d)
    return out


def hybrid_search_rag_chunks(
    query: str,
    embedding: List[float],
    *,
    top_k: int = 5,
    document_id: Optional[str] = None,
    document_ids: Optional[List[str]] = None,
    vector_weight: float = 0.65,
) -> List[Dict[str, Any]]:
    """
    Merge vector ANN + BM25 ranks (reciprocal rank fusion style) for better sheet retrieval.
    """
    top_k = max(1, min(100, int(top_k)))
    fetch_k = min(100, max(top_k * 3, top_k + 5))
    doc_ids = _resolve_document_ids(document_id, document_ids)
    vec_hits = search_rag_chunks(embedding, top_k=fetch_k, document_ids=doc_ids)
    bm_hits = search_rag_chunks_bm25(query, top_k=fetch_k, document_ids=doc_ids)

    scores: Dict[str, float] = {}
    payload: Dict[str, Dict[str, Any]] = {}
    k_rrf = 60.0

    for rank, h in enumerate(vec_hits):
        cid = str(h.get("chunk_id") or "")
        if not cid:
            continue
        scores[cid] = scores.get(cid, 0.0) + vector_weight / (k_rrf + rank + 1)
        payload[cid] = h

    bm_w = 1.0 - vector_weight
    for rank, h in enumerate(bm_hits):
        cid = str(h.get("chunk_id") or "")
        if not cid:
            continue
        scores[cid] = scores.get(cid, 0.0) + bm_w / (k_rrf + rank + 1)
        if cid not in payload:
            payload[cid] = h

    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    out: List[Dict[str, Any]] = []
    for cid, fused in ordered:
        row = dict(payload[cid])
        row["fused_score"] = fused
        row["distance"] = 1.0 - fused
        out.append(row)
    return out


def search_rag_chunks(
    embedding: List[float],
    *,
    top_k: int = 5,
    document_id: Optional[str] = None,
    document_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Approximate nearest neighbors by cosine distance (``<=>``) on ``rag_chunks.embedding``.
    """
    _require_vector_deps()
    top_k = max(1, min(100, int(top_k)))
    q = Vector(embedding)
    doc_ids = _resolve_document_ids(document_id, document_ids)
    with _pg_connect(row_factory=dict_row) as conn:
        _register_pgvector(conn)
        with conn.cursor() as cur:
            if doc_ids and len(doc_ids) == 1:
                _pg_execute(cur,
                    """
                    SELECT chunk_id, document_id, chunk_index, text_content, meta,
                           (embedding <=> %s::vector) AS distance
                    FROM public.rag_chunks
                    WHERE document_id = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (q, doc_ids[0], q, top_k),
                )
            elif doc_ids:
                _pg_execute(cur,
                    """
                    SELECT chunk_id, document_id, chunk_index, text_content, meta,
                           (embedding <=> %s::vector) AS distance
                    FROM public.rag_chunks
                    WHERE document_id = ANY(%s::text[])
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (q, doc_ids, q, top_k),
                )
            else:
                _pg_execute(cur,
                    """
                    SELECT chunk_id, document_id, chunk_index, text_content, meta,
                           (embedding <=> %s::vector) AS distance
                    FROM public.rag_chunks
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (q, q, top_k),
                )
            rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        m = d.get("meta")
        if isinstance(m, str):
            d["meta"] = json.loads(m) if m else {}
        out.append(d)
    return out


def delete_rag_chunks_for_document(document_id: str) -> int:
    """Remove all chunks for a document. Returns deleted row count."""
    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(cur,
                "DELETE FROM public.rag_chunks WHERE document_id = %s",
                (document_id,),
            )
            n = cur.rowcount or 0
        conn.commit()
    return n


def get_rag_chunks_for_sheet(sheet_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Chunks for a sheet: ``document_id = sheet_{id}``, ``meta.sheet_id``, or legacy ``meta.source_path``.
    """
    limit = max(1, min(2000, int(limit)))
    doc_id = f"sheet_{sheet_id}"
    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(cur,"SELECT path FROM public.sheets WHERE id = %s", (sheet_id,))
            s = cur.fetchone()
            if not s:
                return []
            path = str(s.get("path") or "")
            _pg_execute(cur,
                """
                SELECT chunk_id, document_id, chunk_index, text_content, meta, created_at
                FROM public.rag_chunks
                WHERE document_id = %s
                   OR COALESCE(meta->>'sheet_id', '') = %s
                   OR (%s <> '' AND COALESCE(meta->>'source_path', '') = %s)
                ORDER BY chunk_index ASC
                LIMIT %s
                """,
                (doc_id, sheet_id, path, path, limit),
            )
            rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        m = d.get("meta")
        if isinstance(m, str):
            d["meta"] = json.loads(m) if m else {}
        if d.get("created_at") is not None:
            d["created_at"] = str(d["created_at"])
        out.append(d)
    return out
