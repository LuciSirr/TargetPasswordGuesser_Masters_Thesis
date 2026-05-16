import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml


UI_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = UI_DIR.parent.parent
INDEX_PATH = UI_DIR / "index.html"
STYLE_PATH = UI_DIR / "styles.css"
SCRIPT_PATH = UI_DIR / "app.js"
DEFAULT_RUNTIME_CONFIG_PATH = WORKSPACE_ROOT / "configs" / "runtime.yaml"
DEFAULT_RESOURCES_CONFIG_PATH = WORKSPACE_ROOT / "configs" / "resources.yaml"


DEFAULT_PROFILE = {
    "id": "",
    "self_first_name": "",
    "self_last_name": "",
    "partner_first_name": "",
    "partner_last_name": "",
    "birth_date": "",
    "age": "",
    "gender": "",
    "marital_status": "",
    "nationality": "",
    "region": "",
    "company": "",
    "employment": "",
    "sector": "",
    "education": "",
    "favorite_hobby": "",
    "car_brand": "",
    "interests": [],
    "previous_passwords": [],
    "children": [],
    "pets": [],
}


DEFAULT_RUNTIME_CONFIG = {
    "model_training": {
        "max_password_length": 25,
        "embedding_fallback_threshold": 0.2,
    },
    "generation": {
        "mode": "deterministic",
        "unique": True,
    },
    "token_enhancement": {
        "dbpedia": {
            "graph_depth": 1,
            "graph_width": 5,
            "threshold_dbp": 0.3,
            "category_weight": 0.7,
            "type_weight": 0.3,
            "request_timeout": 30,
            "request_delay": 0.1,
        },
        "embeddings": {
            "threshold_w2v": 0.4,
            "threshold_fasttext": 0.35,
        },
        "max_expansion": 5,
    },
}


DEFAULT_RESOURCES_CONFIG = {
    "dbpedia_sparql_url": "https://dbpedia.org/sparql",
    "languages": {
        "en": {
            "w2v_model": "models/embeddings/enwiki_20180420_100d.pkl",
            "fasttext_model": "",
        },
        "cz": {
            "w2v_model": "",
            "fasttext_model": "models/embeddings/cc.cs.300.bin",
            "name_diminutives": "resources/czech_name_diminutives.json",
        },
        "de": {
            "w2v_model": "models/embeddings/dewiki_20180420_100d.pkl",
            "fasttext_model": "models/embeddings/cc.de.300.bin",
        },
    },
}


STATIC_FILES = {
    "/static/styles.css": STYLE_PATH,
    "/static/app.js": SCRIPT_PATH,
}


def _clean_nested(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, nested_value in value.items():
            result = _clean_nested(nested_value)
            if result is not None:
                cleaned[key] = result
        return cleaned
    if isinstance(value, list):
        cleaned = []
        for item in value:
            result = _clean_nested(item)
            if result is not None:
                cleaned.append(result)
        return cleaned
    if value == "":
        return None
    return value


def normalize_profile(profile: dict) -> dict:
    normalized = {}
    for key, default_value in DEFAULT_PROFILE.items():
        value = profile.get(key, default_value)
        if key in {"interests", "previous_passwords"}:
            if isinstance(value, list):
                normalized[key] = [str(item).strip() for item in value if str(item).strip()]
            else:
                normalized[key] = []
            continue
        if key in {"children", "pets"}:
            entries = value if isinstance(value, list) else []
            normalized[key] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                cleaned = {k: str(v).strip() for k, v in entry.items() if str(v).strip()}
                if cleaned:
                    normalized[key].append(cleaned)
            continue
        if key == "age":
            normalized[key] = value if isinstance(value, int) else None
            continue
        normalized[key] = "" if value is None else str(value).strip()
    return _clean_nested(normalized)


def normalize_runtime_config(config: dict) -> dict:
    merged = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
    for section, section_value in (config or {}).items():
        if isinstance(section_value, dict) and isinstance(merged.get(section), dict):
            for key, nested_value in section_value.items():
                if isinstance(nested_value, dict) and isinstance(merged[section].get(key), dict):
                    merged[section][key].update(nested_value)
                else:
                    merged[section][key] = nested_value
        else:
            merged[section] = section_value
    return _clean_nested(merged)


def normalize_resources_config(config: dict) -> dict:
    merged = json.loads(json.dumps(DEFAULT_RESOURCES_CONFIG))
    for key, value in (config or {}).items():
        if key == "languages" and isinstance(value, dict):
            for language, lang_config in value.items():
                if not isinstance(lang_config, dict):
                    continue
                base = merged.setdefault("languages", {}).setdefault(language, {})
                base.update(lang_config)
        else:
            merged[key] = value
    return _clean_nested(merged)


def safe_workspace_path(raw_path: str) -> Path:
    if not raw_path:
        raise ValueError("A target path is required.")
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = WORKSPACE_ROOT / candidate
    resolved = candidate.resolve()
    resolved.relative_to(WORKSPACE_ROOT)
    return resolved


def load_yaml_or_default(path: Path, fallback: dict) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
            return data if isinstance(data, dict) else fallback
    return fallback


def load_json_or_default(path: Path, fallback: dict) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else fallback
    return fallback


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


class ProfileGuiHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._send_file(INDEX_PATH, "text/html; charset=utf-8")
            return

        if parsed.path in STATIC_FILES:
            self._send_static(parsed.path)
            return

        if parsed.path == "/api/defaults":
            self._send_json(
                {
                    "profile": DEFAULT_PROFILE,
                    "runtime_config": normalize_runtime_config(
                        load_yaml_or_default(DEFAULT_RUNTIME_CONFIG_PATH, DEFAULT_RUNTIME_CONFIG)
                    ),
                    "resources_config": normalize_resources_config(
                        load_yaml_or_default(DEFAULT_RESOURCES_CONFIG_PATH, DEFAULT_RESOURCES_CONFIG)
                    ),
                }
            )
            return

        if parsed.path == "/api/load":
            try:
                params = parse_qs(parsed.query)
                response = {}

                profile_path = params.get("profile_path", [""])[0]
                runtime_path = params.get("runtime_config_path", [""])[0]
                resources_path = params.get("resources_config_path", [""])[0]

                if profile_path:
                    response["profile"] = normalize_profile(
                        load_json_or_default(safe_workspace_path(profile_path), DEFAULT_PROFILE)
                    )
                if runtime_path:
                    response["runtime_config"] = normalize_runtime_config(
                        load_yaml_or_default(safe_workspace_path(runtime_path), DEFAULT_RUNTIME_CONFIG)
                    )
                if resources_path:
                    response["resources_config"] = normalize_resources_config(
                        load_yaml_or_default(safe_workspace_path(resources_path), DEFAULT_RESOURCES_CONFIG)
                    )

                self._send_json(response)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/save":
            self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_json_body()
            section = payload.get("section", "")
            target_path = safe_workspace_path(payload.get("path", ""))
            raw_section_payload = payload.get("payload", {})

            if section == "profile":
                write_json(target_path, normalize_profile(raw_section_payload))
            elif section == "runtime":
                write_yaml(target_path, normalize_runtime_config(raw_section_payload))
            elif section == "resources":
                write_yaml(target_path, normalize_resources_config(raw_section_payload))
            else:
                raise ValueError("Unknown save section.")

            self._send_json({"saved": str(target_path.relative_to(WORKSPACE_ROOT))})
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def log_message(self, fmt, *args):
        return

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw_body.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Invalid JSON payload.")
        return data

    def _send_static(self, route: str) -> None:
        file_path = STATIC_FILES[route]
        mime_type, _ = mimetypes.guess_type(str(file_path))
        self._send_file(file_path, mime_type or "application/octet-stream")

    def _send_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(
        description="Run a localhost GUI for creating profile JSON and YAML config files."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8765, help="Port to serve on.")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ProfileGuiHandler)
    print(f"Profile GUI running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
