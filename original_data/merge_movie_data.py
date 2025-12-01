"""Merge Douban CSV data with base_info.json to add id and cover columns."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

DATA_DIR = Path(__file__).resolve().parent
CSV_INPUT_PATH = DATA_DIR / "douban_movies.csv"
JSON_BASE_INFO_PATH = DATA_DIR / "base_info.json"
CSV_OUTPUT_PATH = DATA_DIR / "douban_movies_enriched.csv"


def _load_base_info() -> List[Dict]:
    if not JSON_BASE_INFO_PATH.exists():
        raise FileNotFoundError("base_info.json not found. Run movie_base_info.py first.")
    content = JSON_BASE_INFO_PATH.read_text(encoding="utf-8").strip()
    return json.loads(content) if content else []


def _sanitize(raw: str) -> str:
    if not raw:
        return ""
    cleaned = raw.replace("\xa0", " ").replace("\u200e", "").strip()
    return cleaned


def _strip_parentheses(text: str) -> str:
    return re.split(r"[（(]", text, maxsplit=1)[0].strip()


def _normalize_key(text: str) -> str:
    text = _sanitize(text)
    if not text:
        return ""
    text = _strip_parentheses(text)
    text = text.replace("·", "").replace("・", "").replace("·", "")
    text = text.replace(":", "：")
    text = re.sub(r"\s+", "", text)
    return text.lower()


def _title_variants(title: str) -> Iterable[str]:
    cleaned = _sanitize(title)
    if not cleaned:
        return []
    variants = {cleaned}
    variants.add(_strip_parentheses(cleaned))
    if " " in cleaned:
        variants.add(cleaned.split(" ", 1)[0])
    compact = re.sub(r"\s+", "", cleaned)
    variants.add(compact)
    return {_normalize_key(item) for item in variants if item}


def _build_title_index(records: List[Dict]) -> Dict[str, Dict]:
    index: Dict[str, Dict] = {}
    for record in records:
        for title in (record.get("title"), record.get("original_title")):
            for variant in _title_variants(title or ""):
                if variant and variant not in index:
                    index[variant] = record
    return index


def _find_record(title: str, index: Dict[str, Dict]) -> Optional[Dict]:
    key = _normalize_key(title)
    if key in index:
        return index[key]
    # fuzzy containment fallback for cases like "指环王2双塔奇兵" vs "指环王2：双塔奇兵"
    for variant_key, record in index.items():
        if key and (key in variant_key or variant_key in key):
            return record
    return None


def _enrich_rows(base_records: List[Dict]) -> None:
    if not CSV_INPUT_PATH.exists():
        raise FileNotFoundError("douban_movies.csv not found.")

    title_index = _build_title_index(base_records)
    enriched_rows: List[Dict[str, str]] = []
    missing_titles: List[str] = []

    with CSV_INPUT_PATH.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = list(reader.fieldnames or [])
        if "id" not in fieldnames:
            fieldnames.append("id")
        if "cover" not in fieldnames:
            fieldnames.append("cover")

        for row in reader:
            row_id = ""
            row_cover = ""
            record = _find_record(row.get("title", ""), title_index)
            if record:
                row_id = record.get("id", "") or ""
                row_cover = record.get("cover", "") or ""
            else:
                missing_titles.append(row.get("title", ""))
            row["id"] = row_id
            row["cover"] = row_cover
            enriched_rows.append(row)

    with CSV_OUTPUT_PATH.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(enriched_rows)

    for title in missing_titles:
        print(f"[WARN] CSV title '{title}' not found in base_info.json")
    print(
        f"Enriched CSV written to {CSV_OUTPUT_PATH.name} with {len(enriched_rows)} rows."
    )


def main() -> None:
    base_records = _load_base_info()
    if not base_records:
        print("base_info.json is empty; nothing to merge.")
        return
    _enrich_rows(base_records)


if __name__ == "__main__":
    main()
