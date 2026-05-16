# Used for experiments, to measure metrics Success@N, password recall@N, and average profile recall@N on the clone profiles.
import argparse
import json
from pathlib import Path

DEFAULT_ITERATIONS = [100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000]


def load_true_passwords(profile: dict) -> set[str]:
    """Extract the set of true passwords from the profile's previous_passwords field."""
    passwords = profile.get("previous_passwords", [])
    if isinstance(passwords, list):
        return {p.strip() for p in passwords if isinstance(p, str) and p.strip()}
    if isinstance(passwords, str):
        return {p.strip() for p in passwords.split(",") if p.strip()}
    return set()


def find_matching_wordlist(directory: Path, clone_id: str) -> Path | None:
    """Find a wordlist file in the directory that matches the given clone_id, either as an exact filename or as a stem."""
    exact_matches = sorted(path for path in directory.glob(f"{clone_id}.*") if path.is_file())
    if exact_matches:
        return exact_matches[0]

    for path in sorted(directory.iterdir()):
        if path.is_file() and path.stem == clone_id:
            return path
    return None


def load_wordlist_prefix_hits(wordlist_path: Path, thresholds: list[int], true_passwords: set[str]) -> dict[int, int]:
    """Load the wordlist and count how many true passwords are found within the top N guesses for each specified threshold N."""
    if not thresholds:
        return {}

    threshold_set = set(thresholds)
    max_threshold = max(thresholds)
    hits_by_threshold: dict[int, int] = {}
    seen_passwords: set[str] = set()
    matched_passwords: set[str] = set()
    unique_count = 0

    with wordlist_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            password = line.strip()
            if not password or password in seen_passwords:
                continue

            seen_passwords.add(password)
            unique_count += 1
            if password in true_passwords:
                matched_passwords.add(password)

            if unique_count in threshold_set:
                hits_by_threshold[unique_count] = len(matched_passwords)

            if unique_count >= max_threshold:
                break

    final_hits = len(matched_passwords)
    for threshold in thresholds:
        if threshold not in hits_by_threshold:
            hits_by_threshold[threshold] = final_hits

    return hits_by_threshold


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure success@N on the clone profiles.")
    parser.add_argument("--profiles-dir", default="data/uk/test")
    parser.add_argument("--wordlists-dir", required=True)
    parser.add_argument(
        "--iterations",
        help="Comma-separated guess cutoffs to evaluate, e.g. 100,1000,10000,100000,1000000",
    )
    parser.add_argument("--log-every", type=int, default=1)
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument("--show-passwords", action="store_true")
    args = parser.parse_args()

    profiles_dir = Path(args.profiles_dir)
    wordlists_dir = Path(args.wordlists_dir)
    if not profiles_dir.is_dir():
        raise FileNotFoundError(f"Profiles directory not found: {profiles_dir}")
    if not wordlists_dir.is_dir():
        raise FileNotFoundError(f"Wordlists directory not found: {wordlists_dir}")

    if args.iterations:
        iterations = [int(value.strip()) for value in args.iterations.split(",") if value.strip()]
        if not iterations:
            raise ValueError("Expected at least one value in --iterations")
    else:
        iterations = DEFAULT_ITERATIONS

    profile_paths = sorted(profiles_dir.glob("*.json"))
    stats_by_iteration = {
        num_passwords: {
            "total_profiles": 0,
            "successful_profiles": 0,
            "profiles_with_at_least_2_hits": 0,
            "profiles_with_at_least_3_hits": 0,
            "total_true_passwords": 0,
            "total_cracked_passwords": 0,
            "cracked_fraction_sum": 0.0,
        }
        for num_passwords in iterations
    }

    for index, profile_path in enumerate(profile_paths, start=1):
        with profile_path.open("r", encoding="utf-8") as handle:
            profile = json.load(handle)

        clone_id = profile.get("id") or profile_path.stem
        true_passwords = load_true_passwords(profile)
        if not true_passwords:
            print(f"[{index}] {profile_path.name}: skipped, no previous_passwords")
            continue

        wordlist_path = find_matching_wordlist(wordlists_dir, clone_id)
        if wordlist_path is None:
            print(f"[{index}] {profile_path.name}: skipped, no matching wordlist file for id={clone_id}")
            continue

        hits_by_iteration = load_wordlist_prefix_hits(wordlist_path, iterations, true_passwords)
        profile_true_count = len(true_passwords)

        for num_passwords in iterations:
            profile_cracked_count = hits_by_iteration[num_passwords]
            profile_cracked_fraction = profile_cracked_count / profile_true_count if profile_true_count else 0.0
            stats = stats_by_iteration[num_passwords]
            stats["total_profiles"] += 1
            stats["total_true_passwords"] += profile_true_count
            stats["total_cracked_passwords"] += profile_cracked_count
            stats["cracked_fraction_sum"] += profile_cracked_fraction
            if profile_cracked_count >= 1:
                stats["successful_profiles"] += 1
            if profile_cracked_count >= 2:
                stats["profiles_with_at_least_2_hits"] += 1
            if profile_cracked_count >= 3:
                stats["profiles_with_at_least_3_hits"] += 1

        if args.log_every > 0 and index % args.log_every == 0:
            final_threshold = iterations[-1]
            final_cracked_count = hits_by_iteration[final_threshold]
            print(
                f"[{index}] {profile_path.name}: generated<={final_threshold} "
                f"true_passwords={profile_true_count} "
                f"cracked={final_cracked_count}/{profile_true_count} "
                f"hit={'yes' if final_cracked_count >= 1 else 'no'}"
            )
            print(f"  wordlist={wordlist_path}")
            if args.show_passwords:
                print(f"  true_sample={sorted(true_passwords)[:args.sample_size]}")

    for num_passwords in iterations:
        print(f"=== Iteration N={num_passwords} ===")
        stats = stats_by_iteration[num_passwords]
        total_profiles = stats["total_profiles"]
        success_at_n = stats["successful_profiles"] / total_profiles if total_profiles else 0.0
        profiles_with_at_least_2_hits_at_n = (
            stats["profiles_with_at_least_2_hits"] / total_profiles if total_profiles else 0.0
        )
        profiles_with_at_least_3_hits_at_n = (
            stats["profiles_with_at_least_3_hits"] / total_profiles if total_profiles else 0.0
        )
        password_recall = (
            stats["total_cracked_passwords"] / stats["total_true_passwords"]
            if stats["total_true_passwords"]
            else 0.0
        )
        average_profile_recall = stats["cracked_fraction_sum"] / total_profiles if total_profiles else 0.0

        print(f"Profiles evaluated: {total_profiles}")
        print(f"Successful cracks: {stats['successful_profiles']}")
        print(f"success@{num_passwords}: {success_at_n:.4f}")
        print(
            f"profiles_with_at_least_2_hits@{num_passwords}: "
            f"{profiles_with_at_least_2_hits_at_n:.4f}"
        )
        print(
            f"profiles_with_at_least_3_hits@{num_passwords}: "
            f"{profiles_with_at_least_3_hits_at_n:.4f}"
        )
        print(f"Passwords cracked: {stats['total_cracked_passwords']}/{stats['total_true_passwords']}")
        print(f"password_recall@{num_passwords}: {password_recall:.4f}")
        print(f"average_profile_recall@{num_passwords}: {average_profile_recall:.4f}")


if __name__ == "__main__":
    main()
