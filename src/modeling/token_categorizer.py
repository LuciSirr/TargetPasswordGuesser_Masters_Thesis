import re
import unicodedata

from datetime import datetime

import fasttext
import numpy as np

from src.loaders.resource_loader import ResourceLoader

class TokenCategorizer:
    def __init__(self, language="en", embedding_fallback_threshold: float = 0.2):
        loader = ResourceLoader("configs/resources.yaml")
        resources = loader.get_language_resources(language)
    
        self.model = fasttext.load_model(resources["fasttext_model"])
        self.embedding_fallback_threshold = embedding_fallback_threshold
        print("loaded model")

    def _normalize_for_match(self, text: str) -> str:
        """Normalize text for diacritic-insensitive, case-insensitive matching."""
        normalized = unicodedata.normalize("NFD", str(text).lower())
        return "".join(c for c in normalized if unicodedata.category(c) != "Mn")

    def _is_symbol(self, token: str) -> bool:
        """Check if the token is a symbol (non-alphanumeric character)."""

        return re.fullmatch(r'[^A-Za-zÁ-Žá-ž0-9\s]', token)
    
    def _match_numbers(self, token: str) -> str | None:
        """Check if the token is a number and categorize it as <year> or <number>."""

        if re.fullmatch(r"\d{4}", token):
            year = int(token)
            current_year = datetime.now().year
            return "<year>" if 1900 <= year <= current_year else "<number>"
        elif re.fullmatch(r"\d+", token):
            return "<number>"
        return None

    def _birth_components(self, profile) -> dict | None:
        """Extract birth date components from the profile and return them in a structured format for matching."""
        birth_date = profile.get_birth_date()
        if not birth_date:
            return None
        try:
            parsed = datetime.strptime(str(birth_date), "%Y-%m-%d")
        except ValueError:
            return None

        return {
            "year": parsed.strftime("%Y"),
            "month": parsed.strftime("%m"),
            "month_no_pad": str(parsed.month),
            "month_name": parsed.strftime("%B").lower(),
            "month_abbr": parsed.strftime("%b").lower(),
            "day": parsed.strftime("%d"),
            "day_no_pad": str(parsed.day),
            "full_variants": {
                parsed.strftime("%Y%m%d"),
                parsed.strftime("%d%m%Y"),
                parsed.strftime("%m%d%Y"),
                parsed.strftime("%Y%d%m"),
                parsed.strftime("%d%Y%m"),
                parsed.strftime("%m%Y%d"),
            },
        }

    def _match_birth_date(self, token: str, profile) -> str | None:
        """Check if the token matches any birth date component in the profile and categorize accordingly."""
        birth = self._birth_components(profile)
        if not birth:
            return None

        token_lower = token.lower()
        if token_lower in birth["full_variants"]:
            return "<birthdate>"
        if token == birth["year"]:
            return "<birth_year>"
        if token in {birth["day"], birth["day_no_pad"]}:
            return "<birth_day>"
        if token_lower in {
            birth["month"],
            birth["month_no_pad"],
            birth["month_name"],
            birth["month_abbr"],
        }:
            return "<birth_month>"
        return None

    def _match_first_last_names(self, token: str, profile) -> str | None:
        """Check if the token matches any first or last name in the profile and categorize accordingly."""
        token_normalized = self._normalize_for_match(token)
        mapping = [
            ("<self_first_name>", profile.get_self_first()),
            ("<self_last_name>", profile.get_self_last()),
            ("<partner_first_name>", profile.get_partner_first()),
            ("<partner_last_name>", profile.get_partner_last()),
        ]

        for label, value in mapping:
            if value and self._normalize_for_match(value) in token_normalized:
                return label

        for child in profile.get_children():
            if child.get("first_name") and self._normalize_for_match(child["first_name"]) in token_normalized:
                return "<child_first_name>"
            if child.get("last_name") and self._normalize_for_match(child["last_name"]) in token_normalized:
                return "<child_last_name>"
        return None

    def _match_pets(self, token: str, profile) -> str | None:
        """Check if the token matches any pet name or type in the profile and categorize accordingly."""
        token_normalized = self._normalize_for_match(token)
        for pet in profile.get_pets():
            if pet.get("pet_name") and self._normalize_for_match(pet["pet_name"]) in token_normalized:
                return "<pet_name>"
            if pet.get("pet_type") and self._normalize_for_match(pet["pet_type"]) in token_normalized:
                return "<pet_type>"
        return None

    def _match_interests(self, token: str, profile) -> str | None:
        """Check if the token matches any interest in the profile and categorize accordingly."""
        token_normalized = self._normalize_for_match(token)
        for interest in profile.get_interests():
            if self._normalize_for_match(interest) in token_normalized:
                return "<interest>"
        return None

    def _match_profile_attributes(self, token: str, profile) -> str | None:
        """Match flat profile attributes that should become explicit PCFG placeholders."""
        token_lower = token.lower()
        token_normalized = self._normalize_for_match(token)
        mapping = [
            ("<region>", profile.get_region()),
            ("<company>", profile.get_company()),
            ("<nationality>", profile.get_nationality()),
            ("<car_brand>", profile.get_car_brand()),
        ]

        for label, value in mapping:
            if value and self._normalize_for_match(value) in token_normalized:
                return label

        birth = self._birth_components(profile)
        if birth:
            if token_lower in birth["full_variants"]:
                return "<birthdate>"
            if token == birth["year"]:
                return "<birth_year>"
            if token in {birth["day"], birth["day_no_pad"]}:
                return "<birth_day>"
            if token_lower in {
                birth["month"],
                birth["month_no_pad"],
                birth["month_name"],
                birth["month_abbr"],
            }:
                return "<birth_month>"
        age = profile.get_age()
        if age is not None and str(age) == token:
            return "<age>"
        return None

    def _cos_sim(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)
        if a_norm == 0 or b_norm == 0:
            return 0.0
        return np.dot(a, b) / (a_norm * b_norm)

    def _compute_cos_sim(self, token_emb: np.ndarray, text: str) -> float:
        """Compute cosine similarity between the token embedding and the embedding of a profile attribute value."""
        val_emb = self.model.get_word_vector(text)
        return self._cos_sim(token_emb, val_emb)

    def _embedding_candidates(
        self,
        token_emb: np.ndarray,
        profile
    ) -> list[tuple[str, float]]:
        """Compute embedding-based category candidates for the token based on profile attributes."""
        candidates = []

        mapping = [
            ("<self_first_name>", profile.get_self_first()),
            ("<self_last_name>", profile.get_self_last()),
            ("<partner_first_name>", profile.get_partner_first()),
            ("<partner_last_name>", profile.get_partner_last()),
            ("<region>", profile.get_region()),
            ("<company>", profile.get_company()),
            ("<nationality>", profile.get_nationality()),
            ("<car_brand>", profile.get_car_brand()),
        ]

        for label, value in mapping:
            if value:
                score = self._compute_cos_sim(token_emb, value)
                candidates.append((label, score))

        birth = self._birth_components(profile)
        if birth:
            candidates.extend([
                ("<birthdate>", self._compute_cos_sim(token_emb, birth["year"] + birth["month"] + birth["day"])),
                ("<birth_year>", self._compute_cos_sim(token_emb, birth["year"])),
                ("<birth_month>", self._compute_cos_sim(token_emb, birth["month_name"])),
                ("<birth_day>", self._compute_cos_sim(token_emb, birth["day"])),
            ])

        age = profile.get_age()
        if age is not None:
            candidates.append(("<age>", self._compute_cos_sim(token_emb, str(age))))

        # Children
        for child in profile.get_children():
            if child.get("first_name"):
                score = self._compute_cos_sim(token_emb, child["first_name"])
                candidates.append(("<child_first_name>", score))

            if child.get("last_name"):
                score = self._compute_cos_sim(token_emb, child["last_name"])
                candidates.append(("<child_last_name>", score))

        # Interests
        for interest in profile.get_interests():
            score = self._compute_cos_sim(token_emb, interest)
            candidates.append(("<interest>", score))

        # Pets
        for pet in profile.get_pets():
            for k in ["pet_name", "pet_type"]:
                if pet.get(k):
                    score = self._compute_cos_sim(token_emb, pet[k])
                    candidates.append((f"<{k}>", score))

        return candidates

    def _embed_based_category(
        self,
        token: str,
        profile,
    ) -> str:
        """Categorize the token based on embedding similarity to profile attributes, with a confidence threshold."""
        token_vec = self.model.get_word_vector(token)
        candidates = self._embedding_candidates(token_vec, profile)

        if not candidates:
            return "<other>"

        best_label, best_score = max(candidates, key=lambda x: x[1])
        return best_label if best_score > self.embedding_fallback_threshold else "<other>"
    

    def _categorize_token(
        self,
        token: str,
        profile
    ) -> str:
        """Categorize the token using rule-based methods."""

        if self._is_symbol(token):
            return "<symbol>"
        for func in [
            self._match_birth_date,
            self._match_first_last_names,
            self._match_pets,
            self._match_interests,
            self._match_profile_attributes,
        ]:
            category = func(token, profile)
            if category:
                return category
        category = self._match_numbers(token)
        return category if category else "<other>"

    def categorize_token_with_fallback(
        self,
        token: str,
        profile
    ) -> str:
        """Categorize the token using rule-based methods first, 
        then fall back to embedding-based categorization if needed."""

        category = self._categorize_token(token, profile)
        return category if category != "<other>" else self._embed_based_category(token, profile)
