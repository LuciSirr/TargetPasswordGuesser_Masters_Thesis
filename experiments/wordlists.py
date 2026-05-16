# Used for generating wordlists for the clone profiles, creating one wordlist file per profile

import argparse
import json
import shlex
import subprocess
from pathlib import Path


def _tail_text(value: str, max_lines: int = 20) -> str:
    lines = value.strip().splitlines()
    if not lines:
        return ""
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(["..."] + lines[-max_lines:])


def _count_nonempty_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return sum(1 for line in handle if line.strip())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate one wordlist file per profile using scripts.generate_passwords."
    )
    parser.add_argument("--profiles-dir", default="data/uk/test")
    parser.add_argument("--model", default="models/pcfg/pcfg_model_en.json")
    parser.add_argument("--language", default="en", choices=["en", "cz", "de"])
    parser.add_argument("-n", "--num-passwords", type=int, default=10000)
    parser.add_argument("--enhance-profile", action="store_true")
    parser.add_argument("--output-root", default="experiments/wordlists")
    parser.add_argument("--series", default=None)
    parser.add_argument("--log-every", type=int, default=1)
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Regenerate wordlists even when a non-empty output file already exists.",
    )
    args = parser.parse_args()

    profiles_dir = Path(args.profiles_dir)
    if not profiles_dir.is_dir():
        raise FileNotFoundError(f"Profiles directory not found: {profiles_dir}")

    folder_name = args.series if args.series else args.language
    language_dir = Path(args.output_root) / folder_name
    language_dir.mkdir(parents=True, exist_ok=True)

    profile_paths = sorted(profiles_dir.glob("*.json"))
    if not profile_paths:
        raise ValueError(f"No JSON profiles found in: {profiles_dir}")

    written_count = 0
    skipped_existing_count = 0
    failed_count = 0

    for index, profile_path in enumerate(profile_paths, start=1):
        with profile_path.open("r", encoding="utf-8") as handle:
            profile = json.load(handle)

        profile_id = profile.get("id")
        if not profile_id:
            print(f"[{index}] {profile_path.name}: skipped, missing id")
            continue

        output_path = language_dir / f"{profile_id}.txt"
        if output_path.exists() and not args.overwrite_existing:
            existing_line_count = _count_nonempty_lines(output_path)
            if existing_line_count > 0:
                skipped_existing_count += 1
                if args.log_every > 0 and index % args.log_every == 0:
                    print(
                        f"[{index}/{len(profile_paths)}] skipped existing "
                        f"{existing_line_count}-line wordlist -> {output_path}"
                    )
                continue
            print(f"[{index}] {profile_path.name}: regenerating empty output -> {output_path}")

        command = [
            "python3",
            "-m",
            "scripts.generate_passwords",
            "-g",
            args.model,
            "-p",
            str(profile_path),
            "-n",
            str(args.num_passwords),
            "-l",
            args.language,
        ]
        if args.enhance_profile:
            command.append("-e")

        with output_path.open("w", encoding="utf-8") as output_handle:
            result = subprocess.run(
                command,
                stdout=output_handle,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

        if result.returncode != 0:
            print(f"[{index}] {profile_path.name}: generator failed")
            print(f"  command={shlex.join(command)}")
            print(f"  returncode={result.returncode}")
            if result.returncode < 0:
                print(f"  signal={-result.returncode}")
            if result.stderr.strip():
                print("  stderr_tail:")
                print(_tail_text(result.stderr))
            if output_path.exists():
                with output_path.open("r", encoding="utf-8", errors="ignore") as handle:
                    stdout_tail = _tail_text(handle.read())
                if stdout_tail:
                    print("  stdout_tail:")
                    print(stdout_tail)
            output_path.unlink(missing_ok=True)
            failed_count += 1
            continue

        written_count += 1
        if args.log_every > 0 and index % args.log_every == 0:
            line_count = _count_nonempty_lines(output_path)
            print(f"[{index}/{len(profile_paths)}] wrote {line_count} passwords -> {output_path}")

    print(
        f"Saved wordlists to {language_dir} "
        f"(written={written_count}, skipped_existing={skipped_existing_count}, failed={failed_count})"
    )


if __name__ == "__main__":
    main()
