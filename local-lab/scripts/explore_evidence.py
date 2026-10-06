"""Loopback-only, read-only HTTP explorer for generated Olist evidence."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from olist_contract import STAGES
from evidence_views import metadata_summary

RUN_RE = re.compile(r"olist_(?:(?:tiny|article_[1-9][0-9]*_[0-9]+_[0-9]+)_)?[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}")
PROJECT = Path(__file__).resolve().parent.parent


def browser_safe_numbers(value):
    """Keep metadata integers exact across JavaScript's finite integer range."""
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 9007199254740991:
        return str(value)
    if isinstance(value, dict):
        return {key: browser_safe_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [browser_safe_numbers(item) for item in value]
    return value


class EvidenceStore:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def read(self, run_id, name):
        if not RUN_RE.fullmatch(run_id) or name not in ["manifest.json", *[stage + ".json" for stage in STAGES]]:
            raise ValueError("Invalid evidence selection")
        path = (self.root / "runs" / run_id / name).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Evidence path escapes its configured root")
        return json.loads(path.read_text(encoding="utf-8"))

    def status(self):
        current = None
        pointer = self.root / "current.json"
        if pointer.exists():
            current = json.loads(pointer.read_text())["run_id"]
            if not isinstance(current, str) or not RUN_RE.fullmatch(current):
                raise ValueError("Invalid current-run pointer")
        runs = []
        for path in sorted((self.root / "runs").glob("*/manifest.json"), reverse=True)[:30]:
            if not RUN_RE.fullmatch(path.parent.name):
                continue
            manifest = self.read(path.parent.name, "manifest.json")
            updated = datetime.fromisoformat(manifest["updated_at"].replace("Z", "+00:00"))
            age = max(0, (datetime.now(timezone.utc) - updated).total_seconds())
            runs.append({**manifest, "preset_id": manifest.get("preset_id", "legacy100"),
                         "preset_label": manifest.get("preset_label", "Synthetic 100-row exercise"),
                         "is_legacy": manifest.get("evidence_schema_version", 0) < 4, "age_seconds": round(age),
                         "stale": manifest["status"] == "running" and age > 300,
                         "is_current": manifest["run_id"] == current})
        return {"state": "available" if runs else "missing", "current_run_id": current,
                "runs": runs, "served_at": datetime.now(timezone.utc).isoformat(),
                "evidence_kind": "Saved snapshots; refresh reads files and never queries tables"}


def make_handler(store, web_root):
    web_root = Path(web_root).resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, status, body, content_type="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            try:
                if path == "/api/status":
                    return self.respond(200, store.status())
                match = re.fullmatch(r"/api/runs/(" + RUN_RE.pattern + r")/stages/(create|insert|update|delete|evolve)", path)
                if match:
                    payload = store.read(match[1], match[2] + ".json")
                    for item in payload["formats"]:
                        item["metadata_summary"] = metadata_summary(item)
                    payload["browser_number_encoding"] = "Metadata integers outside JavaScript's exact range are decimal strings; captured files retain their original numeric types"
                    return self.respond(200, browser_safe_numbers(payload))
                assets = {"/": ("index.html", "text/html; charset=utf-8"),
                          "/legacy": ("index.html", "text/html; charset=utf-8"),
                          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                          "/style.css": ("style.css", "text/css; charset=utf-8")}
                if path in assets:
                    name, mime = assets[path]
                    return self.respond(200, (web_root / name).read_bytes(), mime)
                return self.respond(404, {"state": "missing", "message": "No such evidence resource"})
            except FileNotFoundError:
                return self.respond(404, {"state": "missing", "message": "This stage has no saved evidence yet"})
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                return self.respond(503, {"state": "invalid", "message": "Evidence is incomplete or invalid; retry refresh after the producer finishes"})

        def do_POST(self):
            self.respond(405, {"message": "The explorer is read-only; use notebook stages to generate evidence"})

    return Handler


def create_server(root=None, port=8765):
    root = root or PROJECT / "evidence" / "olist"
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(EvidenceStore(root), PROJECT / "web"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--evidence-dir", type=Path, default=PROJECT / "evidence" / "olist")
    args = parser.parse_args()
    server = create_server(args.evidence_dir, args.port)
    print(f"Olist evidence explorer: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
