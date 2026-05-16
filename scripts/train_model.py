import argparse
import os
import json

from src.loaders.profile_loader import ProfileLoader
from src.modeling.structure_trainer import StructureTrainer
from src.modeling.token_categorizer import TokenCategorizer
from src.loaders.resource_loader import ResourceLoader
from src.loaders.runtime_config_loader import RuntimeConfigLoader
from src.run_logging import add_run_log_argument, resolve_run_log_path, utc_timestamp, write_run_log

RESOURCES_CONFIG_PATH = "configs/resources.yaml"

def load_profiles(profiles_dir):
    """Load all JSON profiles from a directory into ProfileLoader instances."""
    profiles = []
    for filename in os.listdir(profiles_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(profiles_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    profiles.append(ProfileLoader(json.load(f)))
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse {file_path}")
    return profiles

parser = argparse.ArgumentParser()
parser.add_argument("--profiles_dir", required=True)
parser.add_argument("--output_model", default="pcfg_model.json")
parser.add_argument("-l","--language",choices=["en", "cz", "de"], default="en", help="Language of the training data.")
parser.add_argument("--runtime_config", default="configs/runtime.yaml", help="Path to runtime configuration file.")
add_run_log_argument(parser)

args = parser.parse_args()

# Loading configurations and setting up logging
run_started_at_utc = utc_timestamp()
runtime_config = RuntimeConfigLoader(args.runtime_config)
model_training_config = runtime_config.get_section("model_training")
run_log_path = resolve_run_log_path(args.run_log, "train_model")
additional_configs = {}

# Logging set up
if run_log_path:
    additional_configs["resources"] = {
        "path": RESOURCES_CONFIG_PATH,
        "config": ResourceLoader(RESOURCES_CONFIG_PATH).config,
    }
effective_model_training_config = {
    "embedding_fallback_threshold": model_training_config.get("embedding_fallback_threshold", 0.2),
    "max_password_length": model_training_config.get("max_password_length", 25),
}
effective_settings = {
    "profiles_dir": args.profiles_dir,
    "output_model": args.output_model,
    "language": args.language,
    "resources_config_path": RESOURCES_CONFIG_PATH,
    "model_training_config": model_training_config,
    "effective_model_training_config": effective_model_training_config,
    "seed": model_training_config.get("seed"),
    "seed_used": False,
}
write_run_log(
    run_log_path,
    tool_name="train_model",
    args=args,
    runtime_config_path=args.runtime_config,
    runtime_config=runtime_config.config,
    effective_settings=effective_settings,
    run_started_at_utc=run_started_at_utc,
    status="started",
    additional_configs=additional_configs,
)

# Loading profiles 
profiles = load_profiles(args.profiles_dir)

# Setting up the token categorizer
categorizer = TokenCategorizer(
    language=args.language,
    embedding_fallback_threshold=effective_model_training_config["embedding_fallback_threshold"],
)

# Setting up the structure trainer and training the model
trainer = StructureTrainer(
    categorizer,
    profiles,
    max_password_length=effective_model_training_config["max_password_length"],
)

# Compute Structures
trainer.train()
# Save structures to json
trainer.save_model(args.output_model)

print(f"Structure model saved to {args.output_model}")

# Save run log 
saved_log_path = write_run_log(
    run_log_path,
    tool_name="train_model",
    args=args,
    runtime_config_path=args.runtime_config,
    runtime_config=runtime_config.config,
    effective_settings=effective_settings,
    run_started_at_utc=run_started_at_utc,
    status="completed",
    additional_configs=additional_configs,
    result={
        "profiles_loaded": len(profiles),
        "output_model": args.output_model,
    },
)
if saved_log_path:
    print(f"Run log saved to {saved_log_path}")
