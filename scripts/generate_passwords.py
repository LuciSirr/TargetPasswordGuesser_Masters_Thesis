import argparse
import json
import re
import sys

from src.generation.password_generator import PasswordGenerator
from src.loaders.profile_loader import ProfileLoader
from src.loaders.resource_loader import ResourceLoader
from src.loaders.runtime_config_loader import RuntimeConfigLoader
from src.expansion.token_enhancer import TokenEnhancer
from src.run_logging import add_run_log_argument, resolve_run_log_path, utc_timestamp, write_run_log
import unicodedata

RESOURCES_CONFIG_PATH = "configs/resources.yaml"

def remove_accents(text):
    """Remove accents from the input text using Unicode normalization."""
    nfkd = unicodedata.normalize('NFD', text)
    return "".join(c for c in nfkd if unicodedata.category(c) != 'Mn')

parser = argparse.ArgumentParser(
    description="Generate passwords according to input grammar and profile."
)

parser.add_argument("-g", "--grammar", required=True, help="Path to the grammar JSON file.")
parser.add_argument("-p", "--profile", required=True, help="Path to the profile JSON file.")
parser.add_argument("-n", "--num-passwords", type=int, default=20, help="Number of passwords to generate.")
parser.add_argument("-e", "--enhance-profile", action="store_true", help="Whether to enhance the profile with additional tokens.")
parser.add_argument("-l","--language",choices=["en", "cz", "de"], default="en", help="Language of the profile.")
parser.add_argument("--runtime_config", default="configs/runtime.yaml", help="Path to runtime configuration file.")
parser.add_argument("--seed", type=int, default=None, help="Seed for reproducible random-mode generation.")
parser.add_argument("-v", "--verbose", action="store_true", help="Print status messages during profile enhancement and generation.")
add_run_log_argument(parser)

args = parser.parse_args()


def log(message: str) -> None:
    """Print a log message if verbose mode is enabled."""
    if args.verbose:
        print(message)


# Loading configurations and setting up logging
run_started_at_utc = utc_timestamp()
runtime_config = RuntimeConfigLoader(args.runtime_config)
generation_config = runtime_config.get_section("generation")
token_enhancement_config = runtime_config.get_section("token_enhancement")
mode = generation_config.get("mode", "random")
unique = generation_config.get("unique", False)

# Logging setup
seed = args.seed if args.seed is not None else generation_config.get("seed")
if args.seed is not None:
    seed_source = "cli"
elif generation_config.get("seed") is not None:
    seed_source = "runtime_config"
else:
    seed_source = "unset"
run_log_path = resolve_run_log_path(args.run_log, "generate_passwords")
resources_config_path = RESOURCES_CONFIG_PATH if args.enhance_profile else None
additional_configs = {}
if run_log_path and args.enhance_profile:
    additional_configs["resources"] = {
        "path": RESOURCES_CONFIG_PATH,
        "config": ResourceLoader(RESOURCES_CONFIG_PATH).config,
    }
effective_settings = {
    "grammar": args.grammar,
    "profile": args.profile,
    "num_passwords": args.num_passwords,
    "enhance_profile": args.enhance_profile,
    "language": args.language,
    "verbose": args.verbose,
    "resources_config_path": resources_config_path,
    "generation_config": generation_config,
    "token_enhancement_config": token_enhancement_config,
    "mode": mode,
    "unique": unique,
    "seed": seed,
    "seed_source": seed_source,
}
write_run_log(
    run_log_path,
    tool_name="generate_passwords",
    args=args,
    runtime_config_path=args.runtime_config,
    runtime_config=runtime_config.config,
    effective_settings=effective_settings,
    run_started_at_utc=run_started_at_utc,
    status="started",
    additional_configs=additional_configs,
)

# Loading structure model json
with open(args.grammar, "r", encoding="utf-8") as f:
    grammar = json.load(f)

# Loading profile json
with open(args.profile, "r", encoding="utf-8") as f:
    profile = json.load(f)

# Loading profile and enhancing it if requested
profile_loader = ProfileLoader(profile)
if args.enhance_profile:
    log("Enhancing profile...")
    enhancer = TokenEnhancer(
        profile_loader,
        language=args.language,
        token_enhancement_config=token_enhancement_config,
        verbose=args.verbose,
    )
    enhancer.expand_name("self")
    log("Expanded self names: " + ", ".join(profile_loader.get_self_first()))
    enhancer.expand_name("partner")
    log("Expanded partner names: " + ", ".join(profile_loader.get_partner_first()))
    enhancer.expand_name("children")
    log("Expanded children names: " + ", ".join(profile_loader.get_children_first()))
    enhancer.expand_region_names()
    log("Expanded region variants: " + ", ".join(profile_loader.get_region()))
    enhancer.expand_interests()
    log("Expanded interests: " + ", ".join(profile_loader.get_interests()))

# Generating passwords
generator = PasswordGenerator(grammar, profile_loader, seed=seed)
log(f"Generating {args.num_passwords} passwords in {mode} mode...")
passwords = generator.generate_passwords_iter(
    args.num_passwords,
    mode=mode,
    unique=unique,
)


# Output generated passwords and log the count
generated_count = 0
for password in passwords:
    print(re.sub(r"\s+", "",remove_accents(password)))
    generated_count += 1
    log(f"Generated password {generated_count}: {password}")

# Logging
saved_log_path = write_run_log(
    run_log_path,
    tool_name="generate_passwords",
    args=args,
    runtime_config_path=args.runtime_config,
    runtime_config=runtime_config.config,
    effective_settings=effective_settings,
    run_started_at_utc=run_started_at_utc,
    status="completed",
    additional_configs=additional_configs,
    result={
        "generated_passwords": generated_count,
        "requested_passwords": args.num_passwords,
    },
)

if saved_log_path:
    print(f"Run log saved to {saved_log_path}", file=sys.stderr)
