import requests
import time
import re
from collections import deque
from urllib.parse import urlparse
import numpy as np
from wikipedia2vec import Wikipedia2Vec
import fasttext

class W2vDbpediaExpander:
    def __init__(
        self,
        wiki2vec_path,
        fasttext_path,
        dbpedia_sparql_url,
        graph_width: int = 3,
        request_timeout: int = 30,
        request_delay: float = 0.1,
        verbose: bool = False,
    ):
        self.endpoint = dbpedia_sparql_url
        self.wiki2vec = None
        self.fasttext = None
        self.fasttext_path = fasttext_path
        self.graph_width = graph_width
        self.request_timeout = request_timeout
        self.request_delay = request_delay
        self.verbose = verbose
        self._default_graph_uris = None

        if wiki2vec_path:
            self.wiki2vec = Wikipedia2Vec.load(wiki2vec_path)

        elif fasttext_path:
            self._ensure_fasttext_loaded()

        self.cache = {}
        self.cache = {}

        self.headers = {
            "User-Agent": "DBpediaExpander/1.0"
        }

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message)

    def _is_local_endpoint(self) -> bool:
        parsed = urlparse(self.endpoint)
        return parsed.hostname in {"localhost", "127.0.0.1", "::1"}

    def _discover_default_graph_uris(self) -> list[str]:
        if self._default_graph_uris is not None:
            return self._default_graph_uris

        if not self._is_local_endpoint():
            self._default_graph_uris = []
            return self._default_graph_uris

        discovery_query = """
        SELECT DISTINCT ?g WHERE {
            GRAPH ?g { ?s ?p ?o }
            FILTER(
                STRSTARTS(STR(?g), "http://") ||
                STRSTARTS(STR(?g), "https://")
            )
        }
        """

        try:
            response = requests.get(
                self.endpoint,
                params={"query": discovery_query, "format": "json"},
                headers=self.headers,
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            bindings = response.json()["results"]["bindings"]
            graph_uris = []
            for row in bindings:
                graph_uri = row.get("g", {}).get("value")
                if not graph_uri:
                    continue
                graph_key = graph_uri.lower()
                if "dbpedia" not in graph_key:
                    continue
                if "property_rules" in graph_key:
                    continue
                graph_uris.append(graph_uri)
            self._default_graph_uris = graph_uris
        except Exception:
            self._default_graph_uris = []

        return self._default_graph_uris

    def _ensure_fasttext_loaded(self) -> bool:
        if self.fasttext:
            return True
        if not self.fasttext_path:
            return False

        self.fasttext = fasttext.load_model(self.fasttext_path)
        return True

    def _run_query(self, query: str) -> list[dict]:
        """Run a SPARQL query against the DBpedia endpoint with caching and rate limiting."""

        # Check cache first to avoid redundant queries
        if query in self.cache:
            return self.cache[query]

        time.sleep(self.request_delay)

        # Make the HTTP request to the DBpedia SPARQL endpoint
        params: list[tuple[str, str]] = [("query", query), ("format", "json")]
        for graph_uri in self._discover_default_graph_uris():
            params.append(("default-graph-uri", graph_uri))

        response = requests.get(
            self.endpoint,
            params=params,
            headers=self.headers,
            timeout=self.request_timeout
        )

        # Raise an exception for HTTP errors
        response.raise_for_status()
        data = response.json()["results"]["bindings"]

        # Cache the results to minimize future requests
        self.cache[query] = data
        return data
    
    def _clean_entity(self, uri: str) -> str | None:
        """Clean the DBpedia URI to extract a readable entity name, applying filters to remove unwanted entries."""

        name = uri.split("/")[-1]

        # Remove unwanted patterns
        if name.startswith(("Category:", "List_of")):
            return None

        # Remove brackets
        name = re.sub(r"\(.*?\)", "", name)
        # Replace underscores with spaces
        name = name.replace("_", " ").strip()

        # Filter out numeric-heavy entries
        if any(char.isdigit() for char in name):
            return None

        # Filter out too short names
        if len(name) < 3:
            return None

        return name

    def _get_categories(self, entity_url: str) -> set:
        """Get DBpedia categories for a given entity URL."""

        query = f"""
        PREFIX dct: <http://purl.org/dc/terms/>
        SELECT DISTINCT ?cat WHERE {{
            <{entity_url}> dct:subject ?cat .
        }}
        """
        results = self._run_query(query)
        return {r["cat"]["value"] for r in results}

    def _get_types(self, entity_url: str) -> set:
        """Get DBpedia types for a given entity URL."""
        query = f"""
        SELECT DISTINCT ?type WHERE {{
            <{entity_url}> a ?type .
        }}
        """
        results = self._run_query(query)
        return {r["type"]["value"] for r in results}


    def _get_linked_entities(self, entity_url: str, query_limit) -> list[tuple[str, str]]:
        """Get linked DBpedia entities together with the relation used to reach them."""

        query = f"""
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX dct: <http://purl.org/dc/terms/>

        SELECT DISTINCT ?relation ?link WHERE {{
            {{
                BIND("dbo:wikiPageWikiLink" AS ?relation)
                <{entity_url}> dbo:wikiPageWikiLink ?link .
            }}
            UNION
            {{
                BIND("dct:subject" AS ?relation)
                <{entity_url}> dct:subject ?link .
            }}
            FILTER(STRSTARTS(STR(?link), "http://dbpedia.org/resource/"))
        }}
        LIMIT {query_limit}
        """
        
        try:
            results = self._run_query(query)
            return [
                (r["relation"]["value"], r["link"]["value"])
                for r in results
            ]
        except:
            return []

    def _traverse_dbpedia(
        self,
        seed_url: str,
        max_depth: int,
    ) -> set[str]:
        """Traverse the DBpedia graph starting from the seed URL, up to a specified depth, and collect linked entities."""
        
        visited = set()
        queue = deque([(seed_url, 0)])
        collected = set()

        self._log(f"[DBpedia BFS] Seed: {seed_url}")
        self._log(f"[DBpedia BFS] Max depth: {max_depth}")

        while queue:
            current, depth = queue.popleft()

            if current in visited or depth > max_depth:
                continue

            visited.add(current)
            collected.add(current)
            self._log(f"[DBpedia BFS] Visiting depth={depth}: {current}")
            links = self._get_linked_entities(current, self.graph_width)
            self._log(f"[DBpedia BFS] Outgoing edges found: {len(links)}")

            for relation, link in links:
                self._log(f"[DBpedia BFS]   {current} --{relation}--> {link}")
                if link not in visited:
                    queue.append((link, depth + 1))
        return collected


    def _cos_sim(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
    
    def _compute_wiki2vec_score(
        self,
        seed: str,
        word: str,
    ) -> float | None:
        """Compute the cosine similarity between the seed and the word using Wiki2Vec embeddings."""
        try:
            seed_vec = self.wiki2vec.get_entity_vector(seed)
            word_vec = self.wiki2vec.get_entity_vector(word)
            return self._cos_sim(seed_vec, word_vec)
        except KeyError:
            return None
            
    def _compute_fasttext_score(self, seed: str, word: str) -> float | None:
        """Compute the cosine similarity between the seed and the word using FastText embeddings."""
        try:
            if not self._ensure_fasttext_loaded():
                return None
            seed_vec = self.fasttext.get_word_vector(seed)
            word_vec = self.fasttext.get_word_vector(word)
            return self._cos_sim(seed_vec, word_vec)
        except Exception:
            return None

    def expand_fasttext(
        self,
        seed: str,
        threshold: float,
        max_expansion: int
    ) -> list[str]:
        """Expand a seed directly through FastText nearest neighbors."""
        if not self._ensure_fasttext_loaded():
            return []

        seed_key = seed.lower().strip()
        if not seed_key:
            return []

        try:
            neighbors = self.fasttext.get_nearest_neighbors(seed_key, k=max_expansion * 3)
        except Exception:
            return []

        expanded = []
        seen = {seed_key}
        for score, word in neighbors:
            word = word.strip().replace("_", " ")
            word_key = word.lower()

            if score < threshold or word_key in seen:
                continue
            if len(word) < 3 or any(char.isdigit() for char in word):
                continue

            seen.add(word_key)
            expanded.append(word)

            if len(expanded) >= max_expansion:
                break

        return expanded
        
    def _compute_dbpedia_score(
        self,
        entity_url : str,
        seed_cats : set,
        seed_types : set,
        category_weight: float,
        type_weight: float,
    ) -> float:
        """Compute a similarity score based on the overlap of DBpedia categories and types between the seed entity and the candidate entity."""
        entity_cats = self._get_categories(entity_url)
        entity_types = self._get_types(entity_url)

        cat_score = len(seed_cats & entity_cats) / len(seed_cats) if seed_cats else 0
        type_score = len(seed_types & entity_types) / len(seed_types) if seed_types else 0

        return category_weight * cat_score + type_weight * type_score

    def expand(
        self,
        seed: str,
        dbpedia_traversal_depth : int,
        threshold_w2v: float,
        threshold_fasttext: float,
        threshold_dbp: float,
        category_weight: float,
        type_weight: float,
        max_expansion: int
    ) -> list[str]:
        """Expand a seed entity using Wiki2Vec similarity and DBpedia graph traversal."""
        seed = seed.title()
        seed_url = f"http://dbpedia.org/resource/{seed.replace(' ', '_')}"

        # Get dbpedia entities via graph traversal
        entities = self._traverse_dbpedia(seed_url, dbpedia_traversal_depth)

        # Get seed dbpedia categories and types for fallback scoring
        seed_cats = self._get_categories(seed_url)
        seed_types = self._get_types(seed_url)

        scored = []
        for uri in entities:
            expaded_seed = self._clean_entity(uri)
            if not expaded_seed:
                continue
            if expaded_seed.lower() == seed.lower():
                continue

            score = None
            score_threshold = None

            # 1. Try Wiki2Vec
            if self.wiki2vec:
                score = self._compute_wiki2vec_score(seed, expaded_seed)
                score_threshold = threshold_w2v
            # 2. Fallback to FastText
            if score is None and (self.fasttext or self.fasttext_path):
                score = self._compute_fasttext_score(seed, expaded_seed)
                score_threshold = threshold_fasttext

            # 3. Use embedding score if available
            if score is not None:
                if score >= score_threshold:
                    scored.append((expaded_seed, score))
            else:
                # 4. Final fallback = DBpedia
                try:
                    dbp_score = self._compute_dbpedia_score(
                        uri,
                        seed_cats,
                        seed_types,
                        category_weight,
                        type_weight,
                    )
                    if dbp_score >= threshold_dbp:
                        scored.append((expaded_seed, dbp_score))
                except:
                    continue

        return [x[0] for x in sorted(scored, key=lambda x: x[1], reverse=True)[:max_expansion]]
