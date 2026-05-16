import heapq
import math
import random
import re
from datetime import datetime
    
class PasswordGenerator:
    def __init__(self, grammar, profile_loader, seed: int | None = None):
        # Load the trained structural model and the target profile.
        self.structures = grammar["structures"]
        self.terminals = grammar.get("terminals", {})
        self.pl = profile_loader
        self.rng = random.Random(seed)

        # Prepare shared helpers used by both generation modes.
        self.current_year = datetime.now().year
        self.years = [str(self.current_year), str(self.current_year - 1), "2020", "1990"]
        self._placeholder_pattern = re.compile(r"(<[^>]+>)")
        self._terminal_distributions = self._build_terminal_distributions()

        # Determine which placeholders and structures are valid for the current profile.
        self.available_placeholders = self._build_available_placeholders()
        self.valid_structures = self._filter_structures()

        # Cache structure collections reused by random sampling and deterministic search.
        self.random_mode_structure_population = list(self.valid_structures.keys())
        self.random_mode_structure_weights = list(self.valid_structures.values())
        self.tokenized_valid_structures = {
            structure: self._tokenize_structure(structure)
            for structure in self.random_mode_structure_population
        }

        # Prepare random mode placeholder resolution functions.
        self.random_mode_replacements = self._build_placeholder_map()

        # Prepare deterministic mode ranked candidate lists for each placeholder.
        self.deterministic_placeholder_candidates = self._build_placeholder_candidates()

    def _build_terminal_distributions(self) -> dict[str, tuple[list[str], list[float]]]:
        """Builds a lookup for learned terminal token distributions"""
        distributions = {}
        for token_type, dist in self.terminals.items():
            if not dist:
                continue
            distributions[token_type] = (list(dist.keys()), list(dist.values()))
        return distributions

    def _rank_weighted_values(
        self,
        values: list[str],
        probs: list[float],
    ) -> list[tuple[str, float]]:
        pairs = [
            (str(value), float(prob))
            for value, prob in zip(values, probs)
            if str(value) and float(prob) > 0
        ]
        pairs.sort(key=lambda item: item[1], reverse=True)
        return pairs

    def _rank_uniform_values(self, values) -> list[tuple[str, float]]:
        normalized = []
        for value in values:
            text = str(value)
            if text:
                normalized.append(text)
        if not normalized:
            return []
        prob = 1.0 / len(normalized)
        return [(value, prob) for value in normalized]

    def _sample_from_distribution(self, token_type: str) -> str:
        """Sample a terminal value based on the learned distribution for the given token type."""
        distribution = self._terminal_distributions.get(token_type)
        if not distribution:
            raise ValueError(f"No distribution available for terminal {token_type}")
        values, probs = distribution
        return self.rng.choices(values, weights=probs, k=1)[0]
    
    def _sample_profile_value(self, values, placeholder: str) -> str:
        """Sample a value for a profile-backed placeholder in the strict generation mode."""
        if not values:
            raise ValueError(f"No values available for placeholder {placeholder}")
        return str(self.rng.choice(values))
    
    def _birth_components(self) -> dict[str, list[str]] | None:
        """Parse the birth date from the profile and return various formatted components for password generation."""
        birth_date = self.pl.get_birth_date()
        if not birth_date:
            return None
        try:
            parsed = datetime.strptime(birth_date, "%Y-%m-%d")
        except ValueError:
            return None
        return {
            "birthdate": [
                parsed.strftime("%Y%m%d"),
                parsed.strftime("%d%m%Y"),
                parsed.strftime("%m%d%Y"),
                parsed.strftime("%Y%d%m"),
                parsed.strftime("%d%Y%m"),
                parsed.strftime("%m%Y%d"),
            ],
            "birth_year": [parsed.strftime("%Y")],
            "birth_month": [
                parsed.strftime("%m"),
                str(parsed.month),
                parsed.strftime("%B").lower(),
                parsed.strftime("%b").lower(),
            ],
            "birth_day": [
                parsed.strftime("%d"),
                str(parsed.day),
            ],
        }

    def _build_placeholder_map(self) -> dict:
        """Create a mapping of placeholders to functions that generate appropriate replacements based on the profile and learned distributions."""
        self_first = self._ensure_list(self.pl.get_self_first())
        self_last = self._ensure_list(self.pl.get_self_last())
        partner_first = self._ensure_list(self.pl.get_partner_first())
        partner_last = self._ensure_list(self.pl.get_partner_last())
        children_first = self._ensure_list(self.pl.get_children_first())
        children_last = self._ensure_list(self.pl.get_children_last())
        pets = self.pl.get_pets() or []
        region = self._ensure_list(self.pl.get_region())
        interests = self.pl.get_interests() or []
        company = self._ensure_list(self.pl.get_company())
        nationality = self._ensure_list(self.pl.get_nationality())
        car_brand = self._ensure_list(self.pl.get_car_brand())
        age = self._ensure_list(self.pl.profile.get("age"))
        birth = self._birth_components() or {
            "birthdate": [],
            "birth_year": [],
            "birth_month": [],
            "birth_day": [],
        }

        return {
            "<interest>": lambda: self._sample_profile_value(interests, "<interest>"),
            "<pet_type>": lambda: self._sample_profile_value(
                [p["pet_type"] for p in pets if p.get("pet_type")],
                "<pet_type>",
            ),
            "<pet_name>": lambda: self._sample_profile_value(
                [p["pet_name"] for p in pets if p.get("pet_name")],
                "<pet_name>",
            ),
            "<partner_first_name>": lambda: self._sample_profile_value(
                partner_first,
                "<partner_first_name>",
            ),
            "<partner_last_name>": lambda: self._sample_profile_value(
                partner_last,
                "<partner_last_name>",
            ),
            "<self_first_name>": lambda: self._sample_profile_value(
                self_first,
                "<self_first_name>",
            ),
            "<self_last_name>": lambda: self._sample_profile_value(
                self_last,
                "<self_last_name>",
            ),
            "<child_first_name>": lambda: self._sample_profile_value(
                children_first,
                "<child_first_name>",
            ),
            "<child_last_name>": lambda: self._sample_profile_value(
                children_last,
                "<child_last_name>",
            ),

            "<year>": lambda: self._sample_from_distribution("<year>")
            if "<year>" in self._terminal_distributions
            else self.rng.choice(self.years),

            "<number>": lambda: self._sample_from_distribution("<number>"),
            "<symbol>": lambda: self._sample_from_distribution("<symbol>"),

            "<region>": lambda: self._sample_profile_value(region, "<region>"),
            "<company>": lambda: self._sample_profile_value(company, "<company>"),
            "<nationality>": lambda: self._sample_profile_value(nationality, "<nationality>"),
            "<car_brand>": lambda: self._sample_profile_value(car_brand, "<car_brand>"),
            "<age>": lambda: self._sample_profile_value(age, "<age>"),
            "<birthdate>": lambda: self._sample_profile_value(birth["birthdate"], "<birthdate>"),
            "<birth_year>": lambda: self._sample_profile_value(birth["birth_year"], "<birth_year>"),
            "<birth_month>": lambda: self._sample_profile_value(birth["birth_month"], "<birth_month>"),
            "<birth_day>": lambda: self._sample_profile_value(birth["birth_day"], "<birth_day>"),

            "<other>": lambda: self._sample_from_distribution("<other>")
        }

    def _ensure_list(self, x):
        if not x:
            return []
        return x if isinstance(x, list) else [x]
    
    def _build_placeholder_candidates(self) -> dict[str, list[tuple[str, float]]]:
        """Precompute ranked candidate lists for each placeholder based on the profile and learned distributions."""
    
        self_first = self._ensure_list(self.pl.get_self_first())
        self_last = self._ensure_list(self.pl.get_self_last())
        partner_first = self._ensure_list(self.pl.get_partner_first())
        partner_last = self._ensure_list(self.pl.get_partner_last())
        children_first = self._ensure_list(self.pl.get_children_first())
        children_last = self._ensure_list(self.pl.get_children_last())
        pets = self.pl.get_pets() or []
        region = self._ensure_list(self.pl.get_region())
        interests = self.pl.get_interests() or []
        company = self._ensure_list(self.pl.get_company())
        nationality = self._ensure_list(self.pl.get_nationality())
        car_brand = self._ensure_list(self.pl.get_car_brand())
        age = self._ensure_list(self.pl.profile.get("age"))
        birth = self._birth_components() or {
            "birthdate": [],
            "birth_year": [],
            "birth_month": [],
            "birth_day": [],
        }

        number_candidates = self._rank_weighted_values(
            *self._terminal_distributions.get("<number>", ([], []))
        ) or [("1", 1.0)]
        year_candidates = self._rank_weighted_values(
            *self._terminal_distributions.get("<year>", ([], []))
        )
        symbol_candidates = self._rank_weighted_values(
            *self._terminal_distributions.get("<symbol>", ([], []))
        ) or [("!", 1.0)]
        other_candidates = self._rank_weighted_values(
            *self._terminal_distributions.get("<other>", ([], []))
        ) or [("x", 1.0)]

        year_weights = [len(self.years) - index for index in range(len(self.years))]
        fallback_year_candidates = self._rank_weighted_values(self.years, year_weights)

        return {
            "<interest>": self._rank_uniform_values(interests),
            "<pet_type>": self._rank_uniform_values(
                [pet.get("pet_type") for pet in pets if pet.get("pet_type")]
            ),
            "<pet_name>": self._rank_uniform_values(
                [pet.get("pet_name") for pet in pets if pet.get("pet_name")]
            ),
            "<partner_first_name>": self._rank_uniform_values(partner_first),
            "<partner_last_name>": self._rank_uniform_values(partner_last),
            "<self_first_name>": self._rank_uniform_values(self_first),
            "<self_last_name>": self._rank_uniform_values(self_last),
            "<child_first_name>": self._rank_uniform_values(children_first),
            "<child_last_name>": self._rank_uniform_values(children_last),
            "<year>": year_candidates or fallback_year_candidates,
            "<number>": number_candidates,
            "<symbol>": symbol_candidates,
            "<region>": self._rank_uniform_values(region),
            "<company>": self._rank_uniform_values(company),
            "<nationality>": self._rank_uniform_values(nationality),
            "<car_brand>": self._rank_uniform_values(car_brand),
            "<age>": self._rank_uniform_values(age),
            "<birthdate>": self._rank_uniform_values(birth["birthdate"]),
            "<birth_year>": self._rank_uniform_values(birth["birth_year"]),
            "<birth_month>": self._rank_uniform_values(birth["birth_month"]),
            "<birth_day>": self._rank_uniform_values(birth["birth_day"]),
            "<other>": other_candidates,
        }

    def _build_available_placeholders(self) -> set[str]:
        """Determine which placeholders can be used based on the profile data and learned distributions."""
        available = {"<year>", "<number>", "<symbol>", "<other>"}

        if self.pl.get_self_first():
            available.add("<self_first_name>")
        if self.pl.get_self_last():
            available.add("<self_last_name>")
        if self.pl.get_partner_first():
            available.add("<partner_first_name>")
        if self.pl.get_partner_last():
            available.add("<partner_last_name>")
        if self.pl.get_children_first():
            available.add("<child_first_name>")
        if self.pl.get_children_last():
            available.add("<child_last_name>")
        if self.pl.get_pets():
            available.update({"<pet_name>", "<pet_type>"})
        if self.pl.get_interests():
            available.add("<interest>")
        if self.pl.get_region():
            available.add("<region>")
        if self.pl.get_company():
            available.add("<company>")
        if self.pl.get_nationality():
            available.add("<nationality>")
        if self.pl.get_car_brand():
            available.add("<car_brand>")
        if self.pl.profile.get("age") is not None:
            available.add("<age>")
        if self.pl.get_birth_date():
            available.update({"<birthdate>", "<birth_year>", "<birth_month>", "<birth_day>"})

        return available

    def _filter_structures(self) -> dict:
        """Filter the grammar structures to only include those that can be fully resolved with the available placeholders."""
        filtered = {}
        for structure, weight in self.structures.items():
            tokenized = self._tokenize_structure(structure)
            placeholders = set(tokenized)
            if placeholders.issubset(self.available_placeholders):
                filtered[structure] = weight
        return filtered if filtered else self.structures

    def _tokenize_structure(self, structure: str) -> list[str]:
        return [token for token in self._placeholder_pattern.split(structure) if token]

    def _resolve_tokenized_structure(
        self,
        tokenized_structure: list[str],
        candidate_indices: tuple[int, ...],
    ) -> tuple[str, float]:
        """Construct a password and its log-score for a valid tokenized structure state."""
        parts = []
        score = 0.0

        for placeholder_pos, token in enumerate(tokenized_structure):
            candidates = self.deterministic_placeholder_candidates[token]
            if not candidates:
                raise ValueError(f"No candidates available for placeholder {token}")

            index = candidate_indices[placeholder_pos]

            value, prob = candidates[index]
            parts.append(value)
            score += math.log(max(prob, 1e-12))

        return "".join(parts), score

    def _generate_passwords_deterministic(
        self,
        num_passwords: int,
    ):
        # Stores candidate passwords ordered by score
        # because heapq is a min-heap and we want highest-score items first
        heap = []
        # Collects unique passwords in emission order
        emitted = []
        # Prevents returning the same concrete password string more than once
        seen_passwords = set()
        # Tracks which placeholder and index combinations were already explored
        # for each structure so we do not recompute identical states
        visited_states = {}

        # Seed the heap with the best initial candidate for every valid structure
        for structure, weight in self.valid_structures.items():
            # Look up the tokenized placeholders for this structure.
            tokenized_structure = self.tokenized_valid_structures[structure]
            # Count how many placeholders need candidate selections.
            placeholder_count = len(tokenized_structure)
            # Start with the top-ranked candidate (index 0) for every placeholder
            initial_indices = tuple(0 for _ in range(placeholder_count))

            # Resolve the structure using those initial candidate choices
            password, candidate_log_score = self._resolve_tokenized_structure(
                tokenized_structure,
                initial_indices,
            )

            # Convert the structure weight to log to avoid small probabilities
            structure_log_score = math.log(max(float(weight), 1e-12))
            total_log_score = structure_log_score + candidate_log_score
            visited_states[structure] = {initial_indices}

            heapq.heappush(
                heap,
                (-total_log_score, structure, initial_indices, password),
            )

        # Keep taking the best remaining candidate until we have enough passwords
        # or there are no more states to explore
        while heap and len(emitted) < num_passwords:
            # Pop the currently highest-scoring password candidate.
            _, structure, indices, password = heapq.heappop(heap)
            # Emit it only if this exact password string has not been returned yet.
            if password not in seen_passwords:
                emitted.append(password)
                seen_passwords.add(password)

            # Reuse the parsed tokens for the structure we just expanded.
            placeholder_tokens = self.tokenized_valid_structures[structure]

            # Create neighboring states by advancing one placeholder choice at a time.
            for pos, token in enumerate(placeholder_tokens):
                next_indices = list(indices)
                # Move this placeholder to its next-ranked candidate.
                next_indices[pos] += 1
                next_indices_tuple = tuple(next_indices)

                # Consider the full candidate list for this placeholder.
                candidates = self.deterministic_placeholder_candidates[token]
                if next_indices[pos] >= len(candidates):
                    continue

                structure_states = visited_states.setdefault(structure, set())
                if next_indices_tuple in structure_states:
                    continue
                structure_states.add(next_indices_tuple)

                # Build the next concrete password and score for this neighbor state
                next_password, candidate_log_score = self._resolve_tokenized_structure(
                    placeholder_tokens,
                    next_indices_tuple,
                )

                total_log_score = math.log(max(float(self.valid_structures[structure]), 1e-12)) + candidate_log_score
                heapq.heappush(
                    heap,
                    (-total_log_score, structure, next_indices_tuple, next_password),
                )

        return emitted

    def _generate_password_random(self) -> str:
        """Generate a single password by replacing placeholders in a randomly chosen structure."""
        structure = self.rng.choices(
            population=self.random_mode_structure_population,
            weights=self.random_mode_structure_weights,
            k=1
        )[0]

        parts = []
        for token in self.tokenized_valid_structures[structure]:
            parts.append(self.random_mode_replacements[token]())
        return "".join(parts)

    def _generate_passwords_random(
        self,
        num_passwords: int,
        unique: bool,
    ):
        """Entry point for generating random passwords."""
        if not unique:
            for _ in range(num_passwords):
                yield self._generate_password_random()
            return

        passwords = set()
        while len(passwords) < num_passwords:
            password = self._generate_password_random()
            if password in passwords:
                continue
            passwords.add(password)
            yield password

    def generate_passwords_iter(
        self,
        num_passwords: int,
        mode: str,
        unique: bool,
    ):
        """Yield passwords in random or deterministic mode."""
        if mode == "deterministic":
            yield from self._generate_passwords_deterministic(num_passwords)
            return

        yield from self._generate_passwords_random(num_passwords, unique)

    def generate_passwords(
        self,
        num_passwords: int,
        mode: str,
        unique: bool,
    ) -> list[str]:
        """Generate passwords in random or deterministic mode."""
        return list(self.generate_passwords_iter(num_passwords, mode=mode, unique=unique))
