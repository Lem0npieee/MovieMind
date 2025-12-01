"""Collect base information for every film in Douban's TOP250 ranking."""

from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import requests
from bs4 import BeautifulSoup
from requests import Response, Session


DATA_DIR = Path(__file__).resolve().parent
BASE_INFO_PATH = DATA_DIR / "base_info.json"
MOVIE_IDS_PATH = DATA_DIR / "movie_ids.json"

TOP250_URL = "https://movie.douban.com/top250"
DETAIL_PAGE_URL = "https://movie.douban.com/subject/{subject_id}/"
DETAIL_ABSTRACT_API = "https://movie.douban.com/j/subject_abstract"

REQUEST_TIMEOUT = 12
MAX_RETRIES = 3
SLEEP_RANGE = (0.8, 1.6)
TOP_PAGE_SIZE = 25
TOP_LIMIT = 250

PC_HEADERS = {
	"User-Agent": (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
		"(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
	),
	"Referer": "https://movie.douban.com/top250",
	"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _request_with_retry(session: Session, url: str, *, params: Dict | None = None,
						headers: Dict | None = None) -> Response:
	for attempt in range(1, MAX_RETRIES + 1):
		try:
			response = session.get(
				url,
				params=params,
				headers=headers,
				timeout=REQUEST_TIMEOUT,
			)
			response.raise_for_status()
			return response
		except requests.RequestException as exc:  # pragma: no cover - network code
			wait_time = (2 ** (attempt - 1)) + random.random()
			print(f"Request failed ({exc}); retrying in {wait_time:.1f}s...")
			time.sleep(wait_time)
	raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRIES} retries")


def _extract_subject_id(url: str) -> str | None:
	if not url:
		return None
	match = re.search(r"/subject/(\d+)/", url)
	return match.group(1) if match else None


def _parse_top250_page(html: str) -> List[Dict]:
	soup = BeautifulSoup(html, "html.parser")
	subjects: List[Dict] = []
	for item in soup.select("div.item"):
		link = item.select_one("div.pic a")
		if not link:
			continue
		href = (link.get("href") or "").strip()
		subject_id = _extract_subject_id(href)
		if not subject_id:
			continue
		img = link.select_one("img")
		title = (img.get("alt").strip() if img and img.get("alt") else link.get("title")) or None
		cover = None
		if img:
			cover = img.get("data-src") or img.get("src")
		rating_tag = item.select_one("span.rating_num")
		rank_tag = item.select_one("div.pic em")
		subjects.append(
			{
				"id": subject_id,
				"title": title,
				"url": href or f"https://movie.douban.com/subject/{subject_id}/",
				"cover": cover,
				"rank": rank_tag.text.strip() if rank_tag else None,
				"rating": rating_tag.text.strip() if rating_tag else None,
			}
		)
	return subjects


def _iterate_top250(session: Session) -> Iterable[Dict]:
	start = 0
	while start < TOP_LIMIT:
		params = {"start": start}
		response = _request_with_retry(session, TOP250_URL, params=params, headers=PC_HEADERS)
		page_subjects = _parse_top250_page(response.text)
		if not page_subjects:
			break
		print(f"Fetched {len(page_subjects)} TOP250 entries from start={start}.")
		yield from page_subjects
		if len(page_subjects) < TOP_PAGE_SIZE:
			break
		start += TOP_PAGE_SIZE
		time.sleep(random.uniform(*SLEEP_RANGE))


def _fetch_detail(session: Session, subject_id: str) -> Dict:
	abstract: Dict = {}
	try:
		resp = _request_with_retry(
			session,
			DETAIL_ABSTRACT_API,
			params={"subject_id": subject_id},
			headers=PC_HEADERS,
		)
		abstract = (resp.json() or {}).get("subject") or {}
	except Exception as exc:  # pragma: no cover - network code
		print(f"Subject abstract fetch failed for {subject_id}: {exc}")

	page_html = ""
	try:
		page_resp = _request_with_retry(
			session,
			DETAIL_PAGE_URL.format(subject_id=subject_id),
			headers=PC_HEADERS,
		)
		page_html = page_resp.text
	except Exception as exc:  # pragma: no cover - network code
		print(f"Subject page fetch failed for {subject_id}: {exc}")

	parsed = _parse_subject_page(page_html) if page_html else {}
	return _merge_detail_sources(abstract, parsed, subject_id)


def _ensure_list(value) -> List[str]:
	if value is None:
		return []
	if isinstance(value, list):
		return value
	if isinstance(value, str):
		return [item.strip() for item in value.split("/") if item.strip()]
	return [str(value)]


def _split_info_value(value: str | None) -> List[str]:
	if not value:
		return []
	return [item.strip() for item in value.split("/") if item.strip()]


def _parse_info_block(text: str) -> Dict[str, str]:
	info: Dict[str, str] = {}
	for line in text.splitlines():
		line = line.strip()
		if not line or ":" not in line:
			continue
		label, value = line.split(":", 1)
		info[label.strip()] = value.strip()
	return info


def _parse_subject_page(html: str) -> Dict:
	soup = BeautifulSoup(html, "html.parser")
	data: Dict = {}
	title_tag = soup.select_one('h1 span[property="v:itemreviewed"]')
	if title_tag:
		data["title"] = title_tag.text.strip()
	year_tag = soup.select_one('h1 span.year')
	if year_tag:
		year_match = re.search(r"(\d{4})", year_tag.text)
		if year_match:
			data["year"] = year_match.group(1)
	rating_value_tag = soup.select_one('strong[property="v:average"]')
	if rating_value_tag:
		data["rating_value"] = rating_value_tag.text.strip() or None
	rating_count_tag = soup.select_one('span[property="v:votes"]')
	if rating_count_tag:
		data["rating_count"] = rating_count_tag.text.strip() or None
	summary_tag = soup.select_one('span[property="v:summary"]')
	if summary_tag:
		summary_text = summary_tag.get_text(separator=" ").strip()
		data["summary"] = re.sub(r"\s+", " ", summary_text)
	poster_tag = soup.select_one('#mainpic img')
	if poster_tag:
		data["poster"] = poster_tag.get("src") or poster_tag.get("data-src")
	info_tag = soup.select_one('#info')
	if info_tag:
		info_text = info_tag.get_text(separator="\n").replace('\xa0', ' ').strip()
		info_map = _parse_info_block(info_text)
		data["genres"] = _split_info_value(info_map.get("类型"))
		data["countries"] = _split_info_value(info_map.get("制片国家/地区"))
		data["pubdates"] = _split_info_value(info_map.get("上映日期"))
		data["durations"] = _split_info_value(info_map.get("片长"))
		data["card_subtitle"] = info_map.get("又名")
		data["original_title"] = info_map.get("又名")
		data["languages"] = _split_info_value(info_map.get("语言"))
	return data


def _merge_detail_sources(abstract: Dict, parsed: Dict, subject_id: str) -> Dict:
	rating_value = parsed.get("rating_value") or abstract.get("rating") or abstract.get("score")
	rating_count = parsed.get("rating_count") or abstract.get("vote_count")
	genres = parsed.get("genres") or abstract.get("types")
	countries = parsed.get("countries") or abstract.get("regions")
	pubdates = parsed.get("pubdates") or _split_info_value(abstract.get("release_date"))
	durations = parsed.get("durations")
	return {
		"title": abstract.get("title") or parsed.get("title"),
		"original_title": parsed.get("original_title"),
		"url": abstract.get("url") or DETAIL_PAGE_URL.format(subject_id=subject_id),
		"cover": abstract.get("cover") or parsed.get("poster"),
		"card_subtitle": parsed.get("card_subtitle"),
		"summary": parsed.get("summary") or abstract.get("intro"),
		"genres": genres,
		"countries": countries,
		"pubdates": pubdates,
		"durations": durations,
		"year": parsed.get("year") or abstract.get("year"),
		"rating": {
			"value": rating_value,
			"count": rating_count,
		},
		"pic": {"large": abstract.get("cover"), "normal": parsed.get("poster")},
	}


def _load_json_list(path: Path) -> List:
	if not path.exists():
		return []
	content = path.read_text(encoding="utf-8").strip()
	return json.loads(content) if content else []


def _dedupe_preserve_order(items: List[str]) -> List[str]:
	seen = set()
	result: List[str] = []
	for item in items:
		if not item or item in seen:
			continue
		seen.add(item)
		result.append(item)
	return result


def _build_record(summary: Dict, detail: Dict) -> Dict:
	rating_info = detail.get("rating") or {}
	poster = detail.get("pic") or {}
	record = {
		"id": summary.get("id"),
		"title": detail.get("title") or summary.get("title"),
		"original_title": detail.get("original_title"),
		"url": summary.get("url") or f"https://movie.douban.com/subject/{summary.get('id')}/",
		"cover": summary.get("cover") or poster.get("large") or poster.get("normal"),
		"top250_rank": summary.get("rank"),
		"top250_rating_snapshot": summary.get("rating"),
		"rating": rating_info.get("value"),
		"rating_count": rating_info.get("count"),
		"genres": _ensure_list(detail.get("genres")),
		"countries": _ensure_list(detail.get("countries")),
		"durations": _ensure_list(detail.get("durations")),
		"pubdates": _ensure_list(detail.get("pubdate")),
		"card_subtitle": detail.get("card_subtitle"),
		"summary": detail.get("intro"),
		"year": detail.get("year"),
		"fetched_at": datetime.utcnow().isoformat() + "Z",
	}
	return record


def _save_json(path: Path, payload) -> None:
	path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
	session = requests.Session()
	base_records = _load_json_list(BASE_INFO_PATH)
	movie_ids = _dedupe_preserve_order(_load_json_list(MOVIE_IDS_PATH))
	processed_ids = {record.get("id") for record in base_records if record.get("id")}
	processed_ids.update(movie_ids)

	for summary in _iterate_top250(session):
		subject_id = summary.get("id")
		if not subject_id or subject_id in processed_ids:
			print(f"Skipping subject {subject_id} (already stored).")
			continue
		try:
			detail = _fetch_detail(session, subject_id)
		except Exception as exc:  # pragma: no cover - network code
			print(f"Failed to fetch detail for {subject_id}: {exc}")
			continue

		record = _build_record(summary, detail)
		base_records.append(record)
		processed_ids.add(subject_id)
		movie_ids.append(subject_id)
		_save_json(BASE_INFO_PATH, base_records)
		_save_json(MOVIE_IDS_PATH, movie_ids)
		print(
			f"Stored base info for {record['title']} (rank {summary.get('rank')}). "
			f"Total stored: {len(base_records)}"
		)
		time.sleep(random.uniform(*SLEEP_RANGE))

	print(
		f"Finished run. {len(base_records)} base records and {len(movie_ids)} movie ids currently saved."
	)


if __name__ == "__main__":
	main()
