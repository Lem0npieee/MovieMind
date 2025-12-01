"""Sync Douban short comments with the movies listed in douban_movies_enriched.csv."""

from __future__ import annotations

import csv
import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import requests
from requests import Session


DATA_DIR = Path(__file__).resolve().parent
BASE_INFO_PATH = DATA_DIR / "base_info.json"
CSV_PATH = DATA_DIR / "douban_movies_enriched.csv"
COMMENTS_PATH = DATA_DIR / "comments.json"

COMMENTS_API = "https://m.douban.com/rexxar/api/v2/movie/{subject_id}/interests"

PAGE_SIZE = 20
MAX_COMMENTS_PER_MOVIE = 200
REQUEST_TIMEOUT = 12
MAX_RETRIES = 3
SLEEP_RANGE = (0.8, 1.6)

HEADERS = {
	"User-Agent": (
		"Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
		"(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
	),
	"Referer": "https://m.douban.com/movie/subject",
	"Accept": "application/json",
}


def _load_base_info() -> List[Dict]:
	if not BASE_INFO_PATH.exists():
		return []
	content = BASE_INFO_PATH.read_text(encoding="utf-8").strip()
	return json.loads(content) if content else []


def _normalize_title(title: str | None) -> str:
	if not title:
		return ""
	text = title.replace("\xa0", " ").strip()
	text = re.split(r"[（(]", text, maxsplit=1)[0].strip()
	text = re.sub(r"\s+", "", text)
	return text.lower()


def _build_title_index(records: List[Dict]) -> Dict[str, Dict]:
	index: Dict[str, Dict] = {}
	for record in records:
		for key in (record.get("title"), record.get("original_title")):
			normalized = _normalize_title(key)
			if normalized and normalized not in index:
				index[normalized] = record
	return index


def _lookup_movie_id(title: str, title_index: Dict[str, Dict]) -> str | None:
	key = _normalize_title(title)
	if not key:
		return None
	if key in title_index:
		return title_index[key].get("id")
	for stored_key, record in title_index.items():
		if key in stored_key or stored_key in key:
			return record.get("id")
	return None


def _load_csv_targets(base_records: List[Dict]) -> List[Dict[str, str]]:
	if not CSV_PATH.exists():
		raise FileNotFoundError("douban_movies_enriched.csv not found. Run merge_movie_data.py first.")
	title_index = _build_title_index(base_records)
	targets: List[Dict[str, str]] = []
	missing_id_titles: List[str] = []
	seen_ids: set[str] = set()
	with CSV_PATH.open("r", encoding="utf-8", newline="") as csv_file:
		reader = csv.DictReader(csv_file)
		for row in reader:
			title = (row.get("title") or "").strip()
			movie_id = (row.get("id") or "").strip()
			if not movie_id:
				movie_id = _lookup_movie_id(title, title_index) or ""
			if not movie_id:
				missing_id_titles.append(title)
				continue
			if movie_id in seen_ids:
				continue
			seen_ids.add(movie_id)
			targets.append({"movie_id": movie_id, "title": title})
	for title in missing_id_titles:
		print(f"[WARN] CSV title '{title}' missing id; skipping comment sync.")
	return targets


def _load_existing_comments() -> Tuple[List[Dict], Dict[str, Dict]]:
	if not COMMENTS_PATH.exists():
		return [], {}
	content = COMMENTS_PATH.read_text(encoding="utf-8").strip()
	if not content:
		return [], {}
	records = json.loads(content)
	index = {item.get("movie_id"): item for item in records if item.get("movie_id")}
	return records, index


def _save_comments(records: List[Dict]) -> None:
	COMMENTS_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def _request_with_retry(session: Session, url: str, params: Dict) -> Dict:
	for attempt in range(1, MAX_RETRIES + 1):
		try:
			response = session.get(
				url,
				params=params,
				headers=HEADERS,
				timeout=REQUEST_TIMEOUT,
			)
			response.raise_for_status()
			return response.json()
		except requests.RequestException as exc:  # pragma: no cover - network code
			if attempt == MAX_RETRIES:
				raise
			wait_time = (2 ** (attempt - 1)) + random.random()
			print(f"Request error ({exc}); retrying in {wait_time:.1f}s...")
			time.sleep(wait_time)
	raise RuntimeError(f"Failed to fetch {url}")


def _normalize_comment(item: Dict) -> Dict:
	rating = item.get("rating") or {}
	user = item.get("user") or {}
	return {
		"comment_id": item.get("id"),
		"author": user.get("name"),
		"author_id": user.get("id") or user.get("uid"),
		"rating": rating.get("value"),
		"votes": item.get("vote_count"),
		"content": item.get("comment"),
		"created_at": item.get("created_at"),
		"spoiler": item.get("spoiler"),
		"status": item.get("status"),
	}


def _fetch_comments_for_movie(session: Session, movie_id: str, max_comments: int) -> List[Dict]:
	collected: List[Dict] = []
	start = 0
	while len(collected) < max_comments:
		params = {
			"count": PAGE_SIZE,
			"start": start,
			"order_by": "hot",
			"status": "P",
		}
		payload = _request_with_retry(session, COMMENTS_API.format(subject_id=movie_id), params)
		batch = payload.get("interests") or payload.get("comments") or []
		if not batch:
			break
		for item in batch:
			collected.append(_normalize_comment(item))
			if len(collected) >= max_comments:
				break
		start += len(batch)
		total = payload.get("total")
		if total is not None and start >= total:
			break
		time.sleep(random.uniform(*SLEEP_RANGE))
	return collected


def main() -> None:
	base_records = _load_base_info()
	if not base_records:
		print("base_info.json is empty. Run movie_base_info.py first.")
		return

	csv_targets = _load_csv_targets(base_records)
	if not csv_targets:
		print("No valid movies found in CSV to sync.")
		_save_comments([])
		return

	_, existing_index = _load_existing_comments()
	existing_map = dict(existing_index)
	target_ids = [item["movie_id"] for item in csv_targets]
	removed_ids = [movie_id for movie_id in existing_map.keys() if movie_id not in target_ids]
	if removed_ids:
		print(f"Removing {len(removed_ids)} movies from comments.json not present in CSV list.")
	for movie_id in removed_ids:
		existing_map.pop(movie_id, None)

	session = requests.Session()
	updated_records: List[Dict] = []
	for position, target in enumerate(csv_targets, start=1):
		movie_id = target["movie_id"]
		title = target.get("title")
		record = existing_map.get(movie_id)
		if record:
			record["title"] = title or record.get("title")
			updated_records.append(record)
			print(f"[{position}/{len(csv_targets)}] Keep existing comments for {movie_id}.")
			continue
		comments = _fetch_comments_for_movie(session, movie_id, MAX_COMMENTS_PER_MOVIE)
		record = {
			"movie_id": movie_id,
			"title": title,
			"comments": comments,
			"fetched_at": datetime.utcnow().isoformat() + "Z",
		}
		updated_records.append(record)
		_save_comments(updated_records)
		print(
			f"[{position}/{len(csv_targets)}] Collected {len(comments)} comments for movie {movie_id}. "
			f"Running total: {len(updated_records)}"
		)
		time.sleep(random.uniform(*SLEEP_RANGE))

	_save_comments(updated_records)
	print(f"Finished sync. Comments stored for {len(updated_records)} CSV movies in {COMMENTS_PATH.name}.")


if __name__ == "__main__":
	main()
