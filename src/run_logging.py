import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path


AUTO_RUN_LOG = "__auto_run_log__"


def add_run_log_argument(parser):
    """Add a --run_log argument to the given argparse parser."""
    parser.add_argument(
        "--run_log",
        nargs="?",
        const=AUTO_RUN_LOG,
        default=None,
        metavar="PATH",
        help=(
            "Write a JSON run log with CLI arguments, runtime configuration, "
            "effective settings, and seed. If PATH is omitted, a timestamped "
            "file is created under logs/."
        ),
    )


def utc_timestamp() -> str:
    """Get the current UTC timestamp as an ISO 8601 string without microseconds."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_run_log_path(log_argument, tool_name: str):
    """Determine the run log path based on the log_argument value."""
    if log_argument is None:
        return None

    if log_argument == AUTO_RUN_LOG:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return Path("logs") / f"{tool_name}_{timestamp}.json"

    return Path(log_argument)


def write_run_log(
    path,
    *,
    tool_name: str,
    args,
    runtime_config_path: str,
    runtime_config: dict,
    effective_settings: dict,
    run_started_at_utc: str,
    status: str,
    additional_configs: dict | None = None,
    result: dict | None = None,
):
    """Write a JSON run log with CLI arguments, runtime configuration, effective settings, and seed."""
    if path is None:
        return None

    payload = {
        "tool": tool_name,
        "status": status,
        "run_started_at_utc": run_started_at_utc,
        "log_written_at_utc": utc_timestamp(),
        "cwd": os.getcwd(),
        "command": sys.argv,
        "python_version": platform.python_version(),
        "arguments": vars(args),
        "run_log_path": str(path),
        "runtime_config_path": runtime_config_path,
        "runtime_config": runtime_config,
        "effective_settings": effective_settings,
    }

    if additional_configs:
        payload["additional_configs"] = additional_configs

    if result is not None:
        payload["result"] = result

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_make_json_safe(payload), handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    return path


def _make_json_safe(value):
    """Recursively convert non-JSON-serializable values to JSON-safe types."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _make_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_make_json_safe(item) for item in value]
    if isinstance(value, set):
        return [_make_json_safe(item) for item in sorted(value, key=str)]
    return value
