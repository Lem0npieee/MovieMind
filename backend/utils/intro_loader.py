import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
INTRO_FILE_PATH = os.path.join(PROJECT_ROOT, 'original_data', 'Intro.json')
_intro_cache: Optional[Dict[str, str]] = None


def _build_intro_cache() -> Dict[str, str]:
    try:
        with open(INTRO_FILE_PATH, 'r', encoding='utf-8') as intro_file:
            data = json.load(intro_file)
    except FileNotFoundError:
        logger.warning("Intro.json 未找到: %s", INTRO_FILE_PATH)
        return {}
    except json.JSONDecodeError as exc:
        logger.error("Intro.json 解析失败: %s", exc)
        return {}

    cache: Dict[str, str] = {}
    items = data if isinstance(data, list) else []
    for item in items:
        douban_id = str(item.get('id') or '').strip()
        introduction = (item.get('introduction') or '').strip()
        if douban_id:
            cache[douban_id] = introduction
    return cache


def load_intro_cache(force_refresh: bool = False) -> Dict[str, str]:
    global _intro_cache
    if force_refresh or _intro_cache is None:
        _intro_cache = _build_intro_cache()
    return _intro_cache


def get_movie_introduction(douban_id: Optional[str]) -> str:
    if not douban_id:
        return ''
    cache = load_intro_cache()
    return cache.get(str(douban_id), '')