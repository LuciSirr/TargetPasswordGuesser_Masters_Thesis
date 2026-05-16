import re
import json
import unicodedata
from unittest import loader

from src.loaders.resource_loader import ResourceLoader
from datetime import datetime
from src.expansion.wiki2vec_dbepedia_expander import W2vDbpediaExpander
from nicknames import NickNamer


def _strip_accents(value: str) -> str:
    """Return the input with diacritics removed."""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))

class TokenEnhancer:
    def __init__(
        self,
        profile_loader,
        language="en",
        token_enhancement_config: dict | None = None,
        verbose: bool = False,
    ):
        self.pl = profile_loader
        self.current_year = datetime.now().year
        self.language = language
        self.verbose = verbose
        self.token_enhancement_config = token_enhancement_config or {}
        self.dbpedia_config = self._get_nested_config("dbpedia")
        self.embeddings_config = self._get_nested_config("embeddings")

        # Personal info
        self.self_first = self.pl.get_self_first()
        self.self_last = self.pl.get_self_last()
        self.partner_first = self.pl.get_partner_first()
        self.partner_last = self.pl.get_partner_last()
        self.pets = self.pl.get_pets()
        self.region = self.pl.get_region()
        self.interests = self.pl.get_interests()

        # Load resources for semantic token expansion
        loader = ResourceLoader("configs/resources.yaml")

        resources = loader.get_language_resources(self.language)
        self.name_diminutives_path = resources.get("name_diminutives")
        
        # Initialize the Wiki2Vec and DBpedia expander
        self.expander = W2vDbpediaExpander(
            wiki2vec_path=resources.get("w2v_model"),
            fasttext_path=resources.get("fasttext_model"),
            dbpedia_sparql_url=loader.get_dbpedia_sparql_url(),
            graph_width=self.dbpedia_config.get("graph_width", 3),
            request_timeout=self.dbpedia_config.get("request_timeout", 30),
            request_delay=self.dbpedia_config.get("request_delay", 0.1),
            verbose=verbose,
        )

    def _get_nested_config(self, key: str) -> dict:
        """Helper method to safely retrieve nested configuration sections as dictionaries."""
        value = self.token_enhancement_config.get(key, {})
        return value if isinstance(value, dict) else {}

    def _get_max_expansion(self) -> int:
        """Get the maximum number of expansions to perform for interests."""
        value = self.token_enhancement_config.get("max_expansion", 5)
        return value if isinstance(value, int) else 5

    def _expand_name_list(self, name_list):
        """Expand a list of names using language-specific rules and resources."""
        if isinstance(name_list, str):
            name_list = [name_list]
        elif not isinstance(name_list, list):
            name_list = [str(name_list)]

        if not name_list:
            return []

        variants = name_list.copy()

        # For czech use local diminitives dictionary
        if (self.language == "cz"):
            if self.name_diminutives_path:
                with open(self.name_diminutives_path, "r", encoding="utf-8") as f:
                    names_dict = json.load(f)
                for name in name_list:
                    variants.extend(names_dict.get(name, []))

        # for other languages use the nicknames library
        else:
            # Initialize nickname engine
            nn = NickNamer()
            for name in name_list:
                nicks = nn.nicknames_of(name)
                if nicks:
                    variants.extend(list(nicks))

        return list(set(variants))
        
    def expand_name(self, role: str) -> None:
        """
        Expand first-name variants for "self", "partner", or "children".
        """
        if role == "children":
            children = self.pl.profile.get("children") or []
            if not isinstance(children, list):
                return

            for child in children:
                if not isinstance(child, dict):
                    continue
                name_list = child.get("first_name") or []
                child["first_name"] = self._expand_name_list(name_list)
            return

        if role == "self":
            profile_key = "self_first_name"
        elif role == "partner":
            profile_key = "partner_first_name"
        else:
            return

        name_list = self.pl.profile.get(profile_key) or []
        self.pl.profile[profile_key] = self._expand_name_list(name_list)

    def expand_region_names(self) -> None:
        """Expand region names using string manipulations to create common variants and abbreviations."""
        if not self.region:
            self.region = ["Region"]
        else:
            # use various string mutations to create variants and abbreviations of the region name
            region_base = self.region.lower().replace(" region", "").strip()
            parts = [p for p in re.split(r"\s+", region_base) if p]
            region_clean = "".join(parts)
            region_clean_ascii = _strip_accents(region_clean)
            acronym_upper = "".join(p[0].upper() for p in parts if p)
            acronym_lower = acronym_upper.lower()
            variants = [
                region_clean,
                region_clean_ascii,
                region_clean.title(),
                region_clean_ascii.title(),
                region_clean_ascii.upper(),
                parts[0].capitalize(),
                parts[0].upper(),
                acronym_upper,
                acronym_lower,
            ]
            self.region = list(set(variants + ([self.region] if isinstance(self.region, str) else self.region)))

        self.pl.profile["region"] = self.region

    def expand_interests(self) -> None:
        """Expand interests using DBpedia and Wiki2Vec."""
        expanded = []
        for interest in self.interests:
            try:
                expansions = self.expander.expand(
                    interest,
                    dbpedia_traversal_depth=self.dbpedia_config.get("graph_depth", 2),
                    threshold_w2v=self.embeddings_config.get("threshold_w2v", 0.4),
                    threshold_fasttext=self.embeddings_config.get("threshold_fasttext", 0.35),
                    threshold_dbp=self.dbpedia_config.get("threshold_dbp", 0.3),
                    category_weight=self.dbpedia_config.get("category_weight", 0.7),
                    type_weight=self.dbpedia_config.get("type_weight", 0.3),
                    max_expansion=self._get_max_expansion(),
                )
            except Exception as exc:
                expansions = []

            expanded.extend(expansions)

        self.interests.extend(expanded)
        self.interests = list(set(self.interests))
        self.pl.profile["interests"] = self.interests
