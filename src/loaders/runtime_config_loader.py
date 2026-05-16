import yaml


class RuntimeConfigLoader:
    SECTION_ALIASES = {
        "categorization": "model_training",
        "training": "model_training",
        "dbpedia": "token_enhancement",
    }

    def __init__(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as handle:
            self.config = yaml.safe_load(handle) or {}

    def get_section(self, section: str) -> dict:
        canonical_section = self.SECTION_ALIASES.get(section, section)
        value = self.config.get(canonical_section, self.config.get(section, {}))
        return value if isinstance(value, dict) else {}
