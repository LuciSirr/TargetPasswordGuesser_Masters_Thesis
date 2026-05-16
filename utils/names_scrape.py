import requests
from bs4 import BeautifulSoup
import json
import re

URLS = [
    "https://www.myczechrepublic.com/culture/czech-name-days/czech-name-diminutives-and-shortened-forms-2/",
    "https://www.myczechrepublic.com/culture/czech-name-days/czech-name-diminutives-and-shortened-forms/"
]
OUTPUT_FILE = "czech_name_diminutives.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0 Safari/537.36"
    )
}

name_map = {}

for url in URLS:
    print(f"Scraping {url}...")
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    for p in soup.find_all("p"):
        lines = [line.strip() for line in p.stripped_strings if "–" in line or "—" in line]
        for line in lines:
            line = line.replace("—", "–")
            parts = line.split("–", 1)
            if len(parts) != 2:
                continue

            base = parts[0].strip()
            variants = parts[1].strip()

            base = re.sub(r'^[^A-Za-zÁ-Žá-ž]+|[^A-Za-zÁ-Žá-ž]+$', '', base)
            variants = [v.strip() for v in re.split(r"[;,/]", variants) if v.strip()]

            if base and variants:
                # Merge if base already exists
                if base in name_map:
                    name_map[base] = list(set(name_map[base] + variants))
                else:
                    name_map[base] = variants

# Save to JSON
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(name_map, f, ensure_ascii=False, indent=2)

print(f"Saved {len(name_map)} Czech names with diminutives to {OUTPUT_FILE}")
