import yaml

class ResourceLoader:
    def __init__(self, config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    def get_language_resources(self, language: str):
        languages = self.config.get("languages", {})

        if language not in languages:
            raise ValueError(f"Language '{language}' not found in config")

        return languages[language]
    
    def get_dbpedia_sparql_url(self):
        return self.config.get("dbpedia_sparql_url")