"""Fetch cast and crew information for previously discovered Douban movies."""

from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import requests
from bs4 import BeautifulSoup
from requests import Session


DATA_DIR = Path(__file__).resolve().parent
MOVIE_IDS_PATH = DATA_DIR / "movie_ids.json"
CAST_INFO_PATH = DATA_DIR / "cast_info.json"

CREDITS_API = "https://m.douban.com/rexxar/api/v2/movie/{subject_id}/credits"
CELEBRITIES_PAGE = "https://movie.douban.com/subject/{subject_id}/celebrities"

REQUEST_TIMEOUT = 12
MAX_RETRIES = 3
SLEEP_RANGE = (0.8, 1.6)

MOBILE_HEADERS = {
	"User-Agent": (
		"Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
		"(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
	),
	"Referer": "https://m.douban.com/movie/subject",
	"Accept": "application/json",
}

PC_HEADERS = {
	"User-Agent": (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
		"(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
	),
	"Referer": "https://movie.douban.com/top250",
	"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _load_movie_ids() -> List[str]:
	if not MOVIE_IDS_PATH.exists():
		raise FileNotFoundError(
			"movie_ids.json not found. Run movie_base_info.py first to generate ids."
		)
	data = MOVIE_IDS_PATH.read_text(encoding="utf-8").strip()
	if not data:
		return []
	return json.loads(data)


def _load_existing_cast() -> Tuple[List[Dict], Dict[str, int]]:
	if not CAST_INFO_PATH.exists():
		return [], {}
	content = CAST_INFO_PATH.read_text(encoding="utf-8").strip()
	if not content:
		return [], {}
	records = json.loads(content)
	index = {item.get("movie_id"): idx for idx, item in enumerate(records) if item.get("movie_id")}
	return records, index


def _save_cast(records: List[Dict]) -> None:
	CAST_INFO_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def _request_json_with_retry(session: Session, url: str) -> Dict:
	for attempt in range(1, MAX_RETRIES + 1):
		try:
			response = session.get(url, headers=MOBILE_HEADERS, timeout=REQUEST_TIMEOUT)
			response.raise_for_status()
			return response.json()
		except requests.RequestException as exc:  # pragma: no cover - network code
			if attempt == MAX_RETRIES:
				raise
			wait_time = (2 ** (attempt - 1)) + random.random()
			print(f"JSON credits error ({exc}); retrying in {wait_time:.1f}s...")
			time.sleep(wait_time)
	raise RuntimeError(f"Failed to fetch {url}")


def _normalize_person(person: Dict) -> Dict:
	photos = person.get("avatars") or person.get("avatar") or {}
	return {
		"id": person.get("id"),
		"name": person.get("name"),
		"name_en": person.get("name_en") or person.get("latin_name"),
		"roles": person.get("roles") or [],
		"character": person.get("character") or person.get("role"),
		"cover": photos.get("large") or photos.get("normal") or person.get("cover_url"),
	}


def _build_cast_record(movie_id: str, payload: Dict | None) -> Dict:
	payload = payload or {}
	return {
		"movie_id": movie_id,
		"title": payload.get("title"),
		"directors": [_normalize_person(p) for p in payload.get("directors") or []],
		"writers": [_normalize_person(p) for p in payload.get("writers") or []],
		"actors": [_normalize_person(p) for p in payload.get("actors") or []],
		"producers": [_normalize_person(p) for p in payload.get("producers") or []],
		"fetched_at": datetime.utcnow().isoformat() + "Z",
	}


def _record_has_people(record: Dict) -> bool:
	return any((record.get("directors"), record.get("writers"), record.get("actors"), record.get("producers")))


def _fetch_celebrity_page(session: Session, subject_id: str) -> str:
	url = CELEBRITIES_PAGE.format(subject_id=subject_id)
	for attempt in range(1, MAX_RETRIES + 1):
		try:
			response = session.get(url, headers=PC_HEADERS, timeout=REQUEST_TIMEOUT)
			response.raise_for_status()
			response.encoding = response.apparent_encoding or "utf-8"
			return response.text
		except requests.RequestException as exc:  # pragma: no cover - network code
			if attempt == MAX_RETRIES:
				raise
			wait_time = (2 ** (attempt - 1)) + random.random()
			print(f"Celebrities page error ({exc}); retrying in {wait_time:.1f}s...")
			time.sleep(wait_time)
	raise RuntimeError(f"Failed to fetch celebrities page for {subject_id}")


def _extract_celebrity_id(url: str | None) -> str | None:
	if not url:
		return None
	match = re.search(r"/celebrity/(\d+)/", url)
	return match.group(1) if match else None


def _categorize_role(role_text: str | None) -> str:
	if not role_text:
		return "actors"
	role_lower = role_text.lower()
	if "导演" in role_text or "director" in role_lower:
		return "directors"
	if "编剧" in role_text or "writer" in role_lower:
		return "writers"
	if "制片" in role_text or "producer" in role_lower:
		return "producers"
	return "actors"


def _parse_celebrity_page(html: str, movie_id: str) -> Dict:
	soup = BeautifulSoup(html, "html.parser")
	result = {
		"movie_id": movie_id,
		"title": None,
		"directors": [],
		"writers": [],
		"actors": [],
		"producers": [],
	}
	title_tag = soup.select_one('#content h1')
	if title_tag:
		result["title"] = title_tag.get_text(strip=True)
	celebrity_nodes = soup.select('#celebrities li.celebrity, ul.celebrities-list li, ul.celebrity-list li')
	for node in celebrity_nodes:
		name_tag = node.select_one("span.name") or node.select_one("span.title")
		if not name_tag:
			continue
		name = name_tag.get_text(strip=True)
		role_tag = node.select_one("span.role") or node.select_one("span.profession")
		role_text = role_tag.get_text(strip=True) if role_tag else ""
		link_tag = node.select_one("a")
		cover_tag = node.select_one("img")
		person = {
			"id": _extract_celebrity_id(link_tag.get("href") if link_tag else None),
			"name": name,
			"name_en": None,
			"roles": [role_text] if role_text else [],
			"character": role_text or None,
			"cover": None,
		}
		if cover_tag:
			person["cover"] = cover_tag.get("data-src") or cover_tag.get("src")
		bucket = _categorize_role(role_text)
		result[bucket].append(person)
	return result


def _build_final_record(base_record: Dict, page_html: str | None, movie_id: str) -> Dict:
	record = base_record
	if _record_has_people(record) or not page_html:
		return record
	parsed = _parse_celebrity_page(page_html, movie_id)
	for key in ("directors", "writers", "actors", "producers"):
		parsed_list = parsed.get(key)
		if parsed_list:
			record[key] = parsed_list
	if not record.get("title"):
		record["title"] = parsed.get("title")
	return record


def main() -> None:
	movie_ids = _load_movie_ids()
	if not movie_ids:
		print("movie_ids.json is empty. Run movie_base_info.py first.")
		return

	records, index = _load_existing_cast()
	completed = set(index.keys())
	session = requests.Session()
	total = len(movie_ids)
	for position, movie_id in enumerate(movie_ids, start=1):
		if movie_id in completed:
			print(f"[{position}/{total}] Skip {movie_id}: already saved.")
			continue
		payload = None
		try:
			payload = _request_json_with_retry(session, CREDITS_API.format(subject_id=movie_id))
		except Exception as exc:  # pragma: no cover - network code
			print(f"Failed to fetch JSON cast for {movie_id}: {exc}")
		record = _build_cast_record(movie_id, payload)
		need_html = not _record_has_people(record)
		page_html = None
		if need_html:
			try:
				page_html = _fetch_celebrity_page(session, movie_id)
			except Exception as exc:  # pragma: no cover - network code
				print(f"Failed to fetch HTML celebrities for {movie_id}: {exc}")
		record = _build_final_record(record, page_html, movie_id)
		if not _record_has_people(record):
			print(f"[{position}/{total}] Warning: no cast parsed for {movie_id}.")
		index[movie_id] = len(records)
		records.append(record)
		completed.add(movie_id)
		_save_cast(records)
		print(f"[{position}/{total}] Stored cast info for movie {movie_id}. Running total: {len(records)}")
		time.sleep(random.uniform(*SLEEP_RANGE))

	print(f"Finished run. Cast info stored for {len(records)} movies in {CAST_INFO_PATH.name}.")


if __name__ == "__main__":
	main()
