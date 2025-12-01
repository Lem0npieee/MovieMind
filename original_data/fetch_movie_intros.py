import csv
import json
import logging
import random
import time
from pathlib import Path
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "douban_movies.csv"
OUTPUT_JSON_PATH = BASE_DIR / "Intro.json"
BASE_URL = "https://movie.douban.com/subject/{}/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36"
)
MAX_RETRIES = 3
TIMEOUT = 15

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def normalize_text(text: str) -> str:
    lines = [line.strip(" \t\r\n\u3000") for line in text.splitlines()]
    filtered = [line for line in lines if line]
    return "\n".join(filtered)


def extract_intro(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    summary = soup.find("span", attrs={"property": "v:summary"})
    if not summary:
        summary = soup.find("div", id="link-report-intra")
    if not summary:
        return ""
    text = summary.get_text("\n")
    return normalize_text(text)


def fetch_intro(session: requests.Session, douban_id: str) -> str:
    url = BASE_URL.format(douban_id)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, timeout=TIMEOUT)
            if response.status_code == 200:
                intro = extract_intro(response.text)
                if intro:
                    return intro
                logging.warning("Intro missing for %s (attempt %d)", douban_id, attempt)
            else:
                logging.warning(
                    "Unexpected status %s for %s (attempt %d)",
                    response.status_code,
                    douban_id,
                    attempt,
                )
        except requests.RequestException as exc:
            logging.warning("Request error for %s (attempt %d): %s", douban_id, attempt, exc)
        time.sleep(1.5 * attempt)
    return ""


def load_movies() -> List[Dict[str, str]]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing CSV file: {CSV_PATH}")
    with CSV_PATH.open(encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("CSV file lacks headers")
        return [row for row in reader if row.get("id") and row.get("title")]


def main() -> None:
    movies = load_movies()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    results = []
    for idx, movie in enumerate(movies, 1):
        douban_id = movie["id"].strip()
        title = movie["title"].strip()
        logging.info("[%d/%d] Fetching %s (%s)", idx, len(movies), title, douban_id)
        intro = fetch_intro(session, douban_id)
        if not intro:
            logging.warning("Falling back to empty intro for %s (%s)", title, douban_id)
        results.append(
            {
                "id": douban_id,
                "name": title,
                "introduction": intro,
            }
        )
        sleep_time = random.uniform(1.0, 2.5)
        time.sleep(sleep_time)

    with OUTPUT_JSON_PATH.open("w", encoding="utf-8") as json_file:
        json.dump(results, json_file, ensure_ascii=False, indent=2)
        json_file.write("\n")
    logging.info("Saved %d introductions to %s", len(results), OUTPUT_JSON_PATH)


if __name__ == "__main__":
    main()
