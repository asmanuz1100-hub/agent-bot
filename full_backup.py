"""Primary-admin full backup builder for ASMAN Agent Bot.

Exports operational PostgreSQL/SQLite tables plus customer photos. Secrets are
never written into the archive.
"""
from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import time
import zipfile
from pathlib import Path

TABLES = (
    "users", "clients", "deleted_clients", "sessions", "shifts", "points", "events", "handovers",
    "cashier_expenses", "cashier_incomes", "cashier_fx_rates", "agent_funds",
    "return_allocations", "failed_updates", "role_audit", "client_edits",
    "client_visits", "collection_tasks", "delivery_edits", "processed", "meta",
    "products", "agent_features", "card_payments", "visit_stock",
)

SECRET_NAMES = (
    "BOT_TOKEN", "ADMIN_IDS", "DATABASE_URL", "POSTGRES_PASSWORD",
    "WEBHOOK_SECRET", "OPENAI_API_KEY",
)


def _rowdict(row):
    return {key: row[key] for key in row.keys()}


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _image_ext(content: bytes) -> str:
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return ".webp"
    return ".bin"


def _clients_csv(rows):
    if not rows:
        return b""
    out = io.StringIO()
    columns = list(rows[0].keys())
    writer = csv.DictWriter(out, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")


def _safe_select_all(db, table):
    # Table names are from the fixed constant above, never user input.
    try:
        rows = db.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
    except Exception:
        rows = db.execute(f"SELECT * FROM {table}").fetchall()
    return [_rowdict(row) for row in rows]


def build_archives(db, photo_fetcher, photo_chunk_bytes=38_000_000):
    """Return (paths, summary) for data ZIP + one or more photo ZIPs."""
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    temp_dir = Path(tempfile.mkdtemp(prefix="asman-full-backup-"))
    paths = []
    table_counts = {}
    table_data = {}

    for table in TABLES:
        rows = _safe_select_all(db, table)
        table_counts[table] = len(rows)
        table_data[table] = rows

    clients = table_data.get("clients", [])
    manifest = {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "database_schema": os.getenv("DB_SCHEMA", "agentbot"),
        "table_counts": table_counts,
        "clients_total": len(clients),
        "clients_with_photo": sum(1 for row in clients if row.get("photo")),
        "secrets_included": False,
    }

    data_path = temp_dir / f"ASMAN-full-data-{stamp}.zip"
    with zipfile.ZipFile(data_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("BACKUP_MANIFEST.json", _json_bytes(manifest))
        zf.writestr(
            "README.txt",
            (
                "ASMAN Agent Bot full operational backup.\n"
                "Includes database table exports and a customer CSV.\n"
                "Customer photos are stored in the separate photo ZIP file(s).\n"
                "No passwords, BOT_TOKEN, database URL or API keys are included.\n"
                "Keep this backup private because it contains customer personal data.\n"
            ).encode("utf-8"),
        )
        zf.writestr(
            "SECRETS_TO_MIGRATE.env.example",
            ("# Values intentionally excluded from backup\n" +
             "".join(f"{name}=\n" for name in SECRET_NAMES)).encode("utf-8"),
        )
        for table, rows in table_data.items():
            zf.writestr(f"database/{table}.json", _json_bytes(rows))
        zf.writestr("customers/clients.csv", _clients_csv(clients))
    paths.append(str(data_path))

    photo_rows = [row for row in clients if row.get("photo")]
    photo_manifest = []
    photo_paths = []
    current_zip = None
    current_path = None
    current_raw = 0
    part = 0

    def open_photo_zip():
        nonlocal current_zip, current_path, current_raw, part
        if current_zip is not None:
            current_zip.writestr("PHOTO_MANIFEST.json", _json_bytes(photo_manifest))
            current_zip.close()
        part += 1
        current_raw = 0
        current_path = temp_dir / f"ASMAN-customer-photos-{stamp}-part-{part:02d}.zip"
        photo_paths.append(str(current_path))
        current_zip = zipfile.ZipFile(current_path, "w", compression=zipfile.ZIP_STORED)

    if photo_rows:
        open_photo_zip()

    for row in photo_rows:
        cid = int(row["id"])
        file_id = str(row["photo"])
        entry = {
            "client_id": cid,
            "shop_name": row.get("shop_name"),
            "client_name": row.get("name"),
            "telegram_file_id": file_id,
            "status": "pending",
        }
        try:
            content = photo_fetcher(file_id)
            ext = _image_ext(content)
            if current_raw and current_raw + len(content) > int(photo_chunk_bytes):
                open_photo_zip()
            filename = f"photos/client-{cid:04d}{ext}"
            current_zip.writestr(filename, content)
            current_raw += len(content)
            entry.update(status="ok", filename=filename, bytes=len(content))
        except Exception as exc:
            entry.update(status="error", error=type(exc).__name__)
        photo_manifest.append(entry)

    if current_zip is not None:
        current_zip.writestr("PHOTO_MANIFEST.json", _json_bytes(photo_manifest))
        current_zip.close()

    paths.extend(photo_paths)
    ok_photos = sum(1 for x in photo_manifest if x.get("status") == "ok")
    failed_photos = sum(1 for x in photo_manifest if x.get("status") == "error")
    summary = {
        "clients": len(clients),
        "tables": table_counts,
        "photos_ok": ok_photos,
        "photos_failed": failed_photos,
        "archives": [os.path.basename(path) for path in paths],
        "temp_dir": str(temp_dir),
    }
    return paths, summary


def cleanup(paths):
    dirs = set()
    for raw in paths:
        path = Path(raw)
        dirs.add(path.parent)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
    for directory in dirs:
        try:
            directory.rmdir()
        except Exception:
            pass
