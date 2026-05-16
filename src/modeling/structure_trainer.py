import json
import re

from collections import Counter
from src.modeling.token_categorizer import TokenCategorizer

class StructureTrainer:
    def __init__(
        self,
        categorizer: TokenCategorizer,
        profiles,
        max_password_length: int = 25,
    ):
        self.categorizer = categorizer
        self.profiles = profiles
        self.max_password_length = max_password_length
        self.leet_map = str.maketrans({
            "0": "o",
            "1": "i",
            "2": "z",
            "3": "e",
            "4": "a",
            "5": "s",
            "6": "g",
            "7": "t",
            "8": "b",
            "9": "g",
            "@": "a",
            "$": "s"
        })

        self.structure_counts = Counter()

        self.terminal_counts = {
            "<year>": Counter(),
            "<symbol>": Counter(),
            "<number>": Counter(),
            "<other>": Counter()
        }

    def _profile_dict(self, profile) -> dict:
        """Helper method to ensure we have a dictionary representation of the profile."""
        return profile.profile if hasattr(profile, "profile") else profile

    def _terminal_probs(self) -> dict:
        """Convert terminal counts to probabilities."""

        terminal_distributions = {}

        for token_type, counter in self.terminal_counts.items():
            total = sum(counter.values())
            if total == 0:
                terminal_distributions[token_type] = {}
            else:
                terminal_distributions[token_type] = {
                    terminal: count / total
                    for terminal, count in counter.items()
                }

        return terminal_distributions
    
    def _structure_probs(self) -> dict:
        """Convert structure counts to probabilities."""

        total = sum(self.structure_counts.values())
        return {s: c / total for s, c in self.structure_counts.items()}

    def _normalize_leet_password(self, password: str) -> str:
        """Normalize leet-like substitutions while preserving pure numeric chunks."""

        parts = re.findall(r'[A-Za-zÁ-Žá-ž0-9@\$]+|[^A-Za-zÁ-Žá-ž0-9@\$\s]', password)
        normalized_parts = []

        for part in parts:
            if part.isdigit():
                normalized_parts.append(part)
                continue

            trailing_number_match = re.match(r'^(.*?)(\d{2,4})$', part)
            if trailing_number_match:
                prefix, suffix = trailing_number_match.groups()
                normalized_parts.append(prefix.translate(self.leet_map) + suffix)
                continue

            normalized_parts.append(part.translate(self.leet_map))

        return "".join(normalized_parts)

    def _get_password_structure(
        self,
        password : str,
        profile : dict
    ) -> str:
        """Categorize each part of the password and return the structure string."""

        parts = re.findall(
            r'[A-ZÁ-Ž]?[a-zá-ž]+|[A-ZÁ-Ž]+(?![a-zá-ž])|\d+|[^A-Za-zÁ-Žá-ž0-9\s]',
            password
        )

        categories = []
        for part in parts:
            category = self.categorizer.categorize_token_with_fallback(part, profile)
            categories.append(category)

            if category in ["<year>", "<symbol>", "<number>", "<other>"]:
                terminal = part if category == "<year>" else part.lower()
                self.terminal_counts[category][terminal] += 1

        return "".join(categories)
    
    def train(self) -> None:
        """Train the structure model by analyzing password structures across all profiles."""

        for profile in self.profiles:
            passwords = profile.get_previous_passwords() or []
            for pwd in passwords:
                pwd = pwd.strip()
                if len(pwd) >= self.max_password_length:
                    continue  # Skip excessively long passwords

                pwd = self._normalize_leet_password(pwd)
                structure = self._get_password_structure(pwd, profile)
                if structure:
                    self.structure_counts[structure] += 1

    def save_model(self, path: str) -> None:
        """Save the learned structure model to a JSON file."""

        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "structures": self._structure_probs(),
                "terminals": self._terminal_probs()
            }, f, indent=2, ensure_ascii=False)
