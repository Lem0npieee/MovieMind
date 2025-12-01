import ast
import csv
import json
import re
from collections import OrderedDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "douban_movies.csv"
TYPE_JSON_PATH = BASE_DIR / "type.json"

_paren_pattern = re.compile(r"\([^)]*\)")

def collect_types(cell_value: str, accumulator: OrderedDict) -> None:
    if cell_value is None:
        return
    raw = cell_value.strip()
    if not raw:
        return

    parsed = None
    try:
        parsed = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        parsed = None

    values = []
    if isinstance(parsed, (list, tuple)):
        values = [str(item).strip() for item in parsed]
    elif isinstance(parsed, str):
        values = [segment.strip() for segment in parsed.split('/') if segment.strip()]
    else:
        fallback = raw.strip("[]")
        values = [segment.strip().strip("'\"") for segment in fallback.split(',') if segment.strip()]

    for value in values:
        cleaned = value.strip().strip("'\"")
        if cleaned and cleaned not in accumulator:
            accumulator[cleaned] = None

def sanitize_start_time(start_time: str) -> str:
    if not start_time:
        return start_time
    cleaned = _paren_pattern.sub('', start_time)
    return cleaned.strip()


if __name__ == "__main__":
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV file not found: {CSV_PATH}")

    type_accumulator: OrderedDict[str, None] = OrderedDict()
    rows = []

    with CSV_PATH.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise ValueError("CSV file is missing headers")

        for row in reader:
            row['start_time'] = sanitize_start_time(row.get('start_time', ''))
            collect_types(row.get('type', ''), type_accumulator)
            rows.append(row)

    with CSV_PATH.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with TYPE_JSON_PATH.open("w", encoding="utf-8") as json_file:
        json.dump(list(type_accumulator.keys()), json_file, ensure_ascii=False, indent=2)
        json_file.write("\n")
