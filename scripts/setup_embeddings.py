import argparse
import bz2
import shutil
import sys
import time
import zlib
from pathlib import Path

import requests
import yaml


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESOURCES_CONFIG = WORKSPACE_ROOT / "configs" / "resources.yaml"

FASTTEXT_URLS = {
    "cc.en.300.bin": "https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.en.300.bin.gz",
    "cc.cs.300.bin": "https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.cs.300.bin.gz",
    "cc.de.300.bin": "https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.de.300.bin.gz",
}

WIKIPEDIA2VEC_URLS = {
    "enwiki_20180420_100d.pkl": "https://wikipedia2vec.s3.amazonaws.com/models/en/2018-04-20/enwiki_20180420_100d.pkl.bz2",
    "dewiki_20180420_100d.pkl": "https://wikipedia2vec.s3.amazonaws.com/models/de/2018-04-20/dewiki_20180420_100d.pkl.bz2",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download embedding models referenced in configs/resources.yaml."
    )
    parser.add_argument(
        "--resources-config",
        default=str(DEFAULT_RESOURCES_CONFIG),
        help="Path to resources YAML file.",
    )
    parser.add_argument(
        "--languages",
        nargs="*",
        help="Language keys from the resources config to install. Defaults to all configured languages.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files even if the target already exists.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without writing files.",
    )
    return parser.parse_args()


def load_resources_config(path: Path) -> dict:
    """Load the resources configuration from a YAML file."""
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid resources config: {path}")
    return data


def resolve_target(path_text: str) -> Path:
    """Resolve a target path from the resources config, interpreting it as relative to the workspace root if it's not absolute."""
    path = Path(path_text)
    if not path.is_absolute():
        path = WORKSPACE_ROOT / path
    return path.resolve()


def infer_download_url(target: Path) -> tuple[str, str]:
    """Infer the download URL and compression type based on the target filename."""
    filename = target.name
    if filename in FASTTEXT_URLS:
        return FASTTEXT_URLS[filename], "gzip"
    if filename in WIKIPEDIA2VEC_URLS:
        return WIKIPEDIA2VEC_URLS[filename], "bz2"
    raise ValueError(
        f"No known download source for {filename}. Extend scripts/setup_embeddings.py if you add new model names."
    )


def iter_model_targets(resources_config: dict, languages: list[str] | None):
    """Iterate over configured embedding model targets, yielding information about the language, field name, target path, download URL, and compression type."""
    configured_languages = resources_config.get("languages", {})
    if not isinstance(configured_languages, dict):
        raise ValueError("resources config is missing a valid 'languages' section")

    selected = languages or list(configured_languages.keys())
    for language in selected:
        if language not in configured_languages:
            raise ValueError(f"Language '{language}' not found in resources config")

        language_config = configured_languages[language]
        if not isinstance(language_config, dict):
            continue

        for field_name in ("w2v_model", "fasttext_model"):
            relative_target = language_config.get(field_name)
            if not relative_target:
                continue

            target = resolve_target(relative_target)
            url, compression = infer_download_url(target)
            yield {
                "language": language,
                "field_name": field_name,
                "relative_target": relative_target,
                "target": target,
                "url": url,
                "compression": compression,
            }


def print_progress(prefix: str, downloaded_bytes: int, total_bytes: int | None) -> None:
    """Print a progress message for the download, showing the amount downloaded and percentage if total size is known."""
    downloaded_mb = downloaded_bytes / (1024 * 1024)
    if total_bytes:
        total_mb = total_bytes / (1024 * 1024)
        percent = downloaded_bytes / total_bytes * 100
        message = f"\r{prefix}: {downloaded_mb:.1f}/{total_mb:.1f} MiB ({percent:5.1f}%)"
    else:
        message = f"\r{prefix}: {downloaded_mb:.1f} MiB"
    sys.stdout.write(message)
    sys.stdout.flush()


def download_and_extract(url: str, destination: Path, compression: str, timeout: int) -> None:
    """Download a file from the given URL, decompressing it on the fly, and save it to the destination path."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".part")
    if temp_path.exists():
        temp_path.unlink()

    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        total_bytes = response.headers.get("Content-Length")
        total_bytes = int(total_bytes) if total_bytes else None
        downloaded_bytes = 0
        last_report = 0.0

        if compression == "gzip":
            decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
            flush_decompressor = lambda: decompressor.flush()
        elif compression == "bz2":
            decompressor = bz2.BZ2Decompressor()
            flush_decompressor = lambda: b""
        else:
            raise ValueError(f"Unsupported compression type: {compression}")
        try:
            with open(temp_path, "wb") as output_handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    downloaded_bytes += len(chunk)
                    output_handle.write(decompressor.decompress(chunk))
                    now = time.monotonic()
                    if now - last_report >= 0.25:
                        print_progress(f"Downloading {destination.name}", downloaded_bytes, total_bytes)
                        last_report = now

                if downloaded_bytes:
                    print_progress(f"Downloading {destination.name}", downloaded_bytes, total_bytes)
                output_handle.write(flush_decompressor())
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    shutil.move(temp_path, destination)
    sys.stdout.write("\n")


def main():
    args = parse_args()
    resources_config = load_resources_config(Path(args.resources_config))
    planned_downloads = list(iter_model_targets(resources_config, args.languages))

    if not planned_downloads:
        print("No embedding models are configured for download.")
        return

    for item in planned_downloads:
        target = item["target"]
        relative_target = item["relative_target"]
        if target.exists() and not args.force:
            print(f"Skipping existing file: {relative_target}")
            continue

        print(f"{item['language']} {item['field_name']}: {relative_target}")
        print(f"  source: {item['url']}")
        if args.dry_run:
            continue

        download_and_extract(
            url=item["url"],
            destination=target,
            compression=item["compression"],
            timeout=args.timeout,
        )
        print(f"Saved: {relative_target}")


if __name__ == "__main__":
    main()
