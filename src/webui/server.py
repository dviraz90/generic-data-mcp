from __future__ import annotations

import os
import re
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from src.app import build_registry
from src.config import Config
from src.tools import ToolRegistry

_STATIC_DIR = Path(__file__).parent / "static"
_MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB
_TABLE_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DEFAULT_PORT = 8765
_LOCAL_HOSTNAMES = frozenset({"127.0.0.1", "localhost", "::1"})
_SAFE_METHODS = frozenset({"GET", "HEAD"})


def _sanitize_table_name(raw: str) -> str:
    """Coerce an arbitrary string into a valid [A-Za-z_][A-Za-z0-9_]* table name.

    Non-conforming characters are replaced with underscores; a leading digit is
    prefixed with an underscore. Returns "" only when no usable characters exist.
    """
    if not raw:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", raw)
    if cleaned and cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned if _TABLE_NAME_RE.fullmatch(cleaned) else ""


def _upload_dir_for(config: Config) -> Path:
    """The directory uploaded files are saved into: <first allowed dir>/uploads."""
    return config.allowed_dirs[0] / "uploads"


def create_app(
    registry: ToolRegistry | None = None,
    config: Config | None = None,
) -> Flask:
    """Build the Flask ingestion-console app.

    Both ``registry`` and ``config`` are injectable for testability; when omitted
    they are built from the environment. ``config`` is still required (even when a
    registry is injected) so the app knows which allowed dir to save uploads into.
    """
    if config is None:
        config = Config.from_env()
    if registry is None:
        registry = build_registry(config)

    upload_dir = _upload_dir_for(config)

    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = _MAX_UPLOAD_BYTES
    app.config["UPLOAD_DIR"] = upload_dir

    def _forbidden(message: str):
        return jsonify({"success": False, "error": message}), 403

    @app.before_request
    def guard_request_origin():
        """Reject DNS-rebinding and cross-site requests.

        Binding to 127.0.0.1 only stops other machines; any web page the user
        visits can still make their browser talk to it. A foreign ``Host`` header
        means DNS rebinding; a missing or foreign ``Origin`` on a state-changing
        request means a cross-site form post (multipart posts skip CORS preflight).
        """
        hostname = urlsplit("//" + request.host).hostname
        if hostname not in _LOCAL_HOSTNAMES:
            return _forbidden(
                f"Host '{request.host}' is not allowed. Open the console at "
                "http://127.0.0.1:<port>/ or http://localhost:<port>/."
            )
        if request.method not in _SAFE_METHODS:
            if request.headers.get("Origin") != f"http://{request.host}":
                return _forbidden(
                    "Cross-origin request rejected. Use the console page itself "
                    "to upload files or run queries."
                )

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        # No inline script or style: markup injected via an ingested value can't run.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    def _respond(result):
        status = 200 if result.success else 400
        return jsonify(result.to_dict()), status

    @app.get("/")
    def index():
        return send_from_directory(_STATIC_DIR, "index.html")

    @app.get("/static/<path:filename>")
    def static_asset(filename: str):
        # send_from_directory rejects paths that escape _STATIC_DIR.
        return send_from_directory(_STATIC_DIR, filename)

    @app.get("/api/datasets")
    def list_datasets():
        return _respond(registry.call("list_datasets", {}))

    @app.get("/api/datasets/<name>")
    def describe_table(name: str):
        return _respond(registry.call("describe_table", {"table_name": name}))

    @app.post("/api/query")
    def query():
        body = request.get_json(silent=True) or {}
        sql = body.get("sql", "")
        return _respond(registry.call("query", {"sql": sql}))

    @app.post("/api/upload")
    def upload():
        file = request.files.get("file")
        if file is None or not file.filename:
            return jsonify({"success": False, "error": "No file provided. Attach a file under the 'file' field."}), 400

        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({"success": False, "error": "Invalid filename after sanitization."}), 400

        requested_table = request.form.get("table_name", "").strip()
        stem = Path(filename).stem
        table_name = _sanitize_table_name(requested_table) or _sanitize_table_name(stem)
        if not table_name:
            return jsonify({"success": False, "error": "Could not derive a valid table name. Provide a table_name matching [A-Za-z_][A-Za-z0-9_]*."}), 400

        upload_dir.mkdir(parents=True, exist_ok=True)
        saved_path = upload_dir / filename
        file.save(str(saved_path))

        result = registry.call(
            "ingest_file", {"path": str(saved_path), "table_name": table_name}
        )
        return _respond(result)

    return app


def main() -> None:
    config = Config.from_env()
    _upload_dir_for(config).mkdir(parents=True, exist_ok=True)
    app = create_app(config=config)

    port = int(os.environ.get("MCP_UI_PORT", _DEFAULT_PORT))
    url = f"http://127.0.0.1:{port}/"
    print(f"\n  generic-data-mcp upload console is running at:\n\n      {url}\n\n  Open it in your browser (Ctrl+C to stop).\n", flush=True)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    app.run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
