"""数据导入脚本 - 从 CSV/JSON 初始化 openGauss 数据."""

import sys
import os
import json
import csv
import re
import ast
from collections import defaultdict

import psycopg2
from psycopg2.extras import execute_values

sys.path.append('..')
from backend.config import Config


def parse_list_field(value):
    """将 CSV 中的 list 字符串解析为字符串列表."""
    if value is None:
        return []
    value = value.strip()
    if not value:
        return []
    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except (ValueError, SyntaxError):
        pass
    if '/' in value:
        return [item.strip() for item in value.split('/') if item.strip()]
    return [value]


def parse_int(value):
    """从字符串中提取整数."""
    if value is None:
        return None
    digits = re.findall(r'\d+', str(value))
    return int(''.join(digits)) if digits else None


def extract_year(date_str):
    """从日期字符串中提取年份."""
    if not date_str:
        return None
    match = re.search(r'(\d{4})', date_str)
    return int(match.group(1)) if match else None


def load_comments_data(json_file):
    """加载评论 JSON."""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, dict):
        # 兼容旧格式 {movie_id: [...]}
        normalized = []
        for movie_id, comments in data.items():
            normalized.append({'movie_id': movie_id, 'comments': comments})
        return normalized
    return data


def sync_genres_from_json(cursor, type_file):
    """根据 type.json 初始化/同步类型表."""
    if not os.path.exists(type_file):
        print(f"⚠ 未找到类型文件: {type_file}")
        return {}
    with open(type_file, 'r', encoding='utf-8') as f:
        genres = json.load(f)
    cleaned = [g.strip() for g in genres if isinstance(g, str) and g.strip()]
    if cleaned:
        for name in cleaned:
            cursor.execute("""
                INSERT INTO genre (name)
                SELECT %s WHERE NOT EXISTS (SELECT 1 FROM genre WHERE name = %s)
            """, (name, name))
        print(f"✓ 同步 {len(cleaned)} 个类型")
    cursor.execute("SELECT genre_id, name FROM genre")
    return {row[1]: row[0] for row in cursor.fetchall()}


def import_movies_from_csv(cursor, csv_file):
    """导入电影基础数据，并返回导演/演员/类型映射."""
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"找不到 CSV 文件: {csv_file}")

    print(f"正在导入电影数据: {csv_file}")
    movies_payload = []
    movie_directors = defaultdict(list)
    movie_actors = defaultdict(list)
    movie_genres = defaultdict(list)
    directors_pool = set()
    actors_pool = set()

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            douban_id = parse_int(row.get('id'))
            rank = parse_int(row.get('rank'))
            if not douban_id or not rank:
                continue

            title = (row.get('title') or '').strip() or f"电影{rank}"
            original_title = title
            rating = float(row.get('score')) if row.get('score') else None
            comment_count = parse_int(row.get('comment_num'))
            poster_url = (row.get('cover') or '').strip()
            countries = (row.get('area') or '').strip()
            languages = (row.get('language') or '').strip()
            durations = (row.get('run_time') or '').strip()
            release_date = (row.get('start_time') or '').strip()
            year = extract_year(release_date)

            directors = parse_list_field(row.get('director'))
            actors = parse_list_field(row.get('actor'))
            genres = parse_list_field(row.get('type'))

            movie_directors[douban_id] = directors
            movie_actors[douban_id] = actors
            movie_genres[douban_id] = genres
            directors_pool.update(directors)
            actors_pool.update(actors)

            movies_payload.append((
                douban_id,
                rank,
                title,
                original_title,
                year,
                rating,
                comment_count,
                poster_url,
                '',  # description
                countries,
                languages,
                durations,
                release_date,
                None  # imdb_id
            ))

    if not movies_payload:
        print("⚠ CSV 中没有可导入的电影数据")
        return {
            'douban_ids': [],
            'movie_directors': movie_directors,
            'movie_actors': movie_actors,
            'movie_genres': movie_genres,
            'directors': set(),
            'actors': set()
        }

    # 使用循环插入，先检查是否存在再插入或更新
    for movie_data in movies_payload:
        douban_id = movie_data[0]
        # 先检查是否存在
        cursor.execute("SELECT 1 FROM movie WHERE douban_id = %s", (douban_id,))
        exists = cursor.fetchone()

        if exists:
            # 如果存在，更新
            cursor.execute("""
                UPDATE movie SET
                    rank = %s,
                    cn_title = %s,
                    original_title = %s,
                    year = %s,
                    rating = %s,
                    comment_count = %s,
                    poster_url = %s,
                    description = %s,
                    countries = %s,
                    languages = %s,
                    durations = %s,
                    release_date = %s,
                    imdb_id = %s
                WHERE douban_id = %s
            """, movie_data[1:] + (movie_data[0],))
        else:
            # 如果不存在，插入
            cursor.execute("""
                INSERT INTO movie (douban_id, rank, cn_title, original_title, year, rating,
                                   comment_count, poster_url, description, countries, languages,
                                   durations, release_date, imdb_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, movie_data)

    print(f"✓ 成功导入/更新 {len(movies_payload)} 部电影")

    return {
        'douban_ids': [item[0] for item in movies_payload],
        'movie_directors': movie_directors,
        'movie_actors': movie_actors,
        'movie_genres': movie_genres,
        'directors': directors_pool,
        'actors': actors_pool
    }


def build_movie_id_map(cursor, douban_ids):
    """构建 douban_id -> movie_id 的映射."""
    if not douban_ids:
        return {}
    cursor.execute("""
        SELECT movie_id, douban_id
        FROM movie
        WHERE douban_id = ANY(%s)
    """, (douban_ids,))
    return {row[1]: row[0] for row in cursor.fetchall()}


def upsert_people(cursor, table_name, id_column, names):
    """插入导演/演员并返回 name->id."""
    cleaned = sorted({name.strip() for name in names if isinstance(name, str) and name.strip()})
    if not cleaned:
        return {}
    # 使用循环插入，检查是否存在再插入
    for name in cleaned:
        cursor.execute(f"""
            INSERT INTO {table_name} (name)
            SELECT %s WHERE NOT EXISTS (SELECT 1 FROM {table_name} WHERE name = %s)
        """, (name, name))
    cursor.execute(f"SELECT {id_column}, name FROM {table_name} WHERE name = ANY(%s)", (cleaned,))
    mapping = {row[1]: row[0] for row in cursor.fetchall()}
    print(f"✓ {table_name} 同步 {len(mapping)} 条记录")
    return mapping


def link_movie_people(cursor, relation_table, person_column, movie_people_map, name_id_map, movie_id_map):
    """建立电影与导演/演员的关联."""
    relations = []
    for douban_id, names in movie_people_map.items():
        movie_id = movie_id_map.get(douban_id)
        if not movie_id:
            continue
        for name in names:
            person_id = name_id_map.get(name.strip()) if name else None
            if person_id:
                relations.append((movie_id, person_id))
    if not relations:
        return
    # 使用循环插入，检查是否存在再插入
    for movie_id, person_id in relations:
        cursor.execute(f"""
            INSERT INTO {relation_table} (movie_id, {person_column})
            SELECT %s, %s WHERE NOT EXISTS (
                SELECT 1 FROM {relation_table}
                WHERE movie_id = %s AND {person_column} = %s
            )
        """, (movie_id, person_id, movie_id, person_id))
    print(f"✓ {relation_table} 建立 {len(relations)} 条关联")


def link_movie_genres(cursor, movie_genres_map, genre_name_id_map, movie_id_map):
    """建立电影与类型关联."""
    relations = []
    missing = set()
    for douban_id, genres in movie_genres_map.items():
        movie_id = movie_id_map.get(douban_id)
        if not movie_id:
            continue
        for genre_name in genres:
            name = genre_name.strip()
            genre_id = genre_name_id_map.get(name)
            if not genre_id:
                if name:
                    missing.add(name)
                continue
            relations.append((movie_id, genre_id))
    if relations:
        # 使用循环插入，检查是否存在再插入
        for movie_id, genre_id in relations:
            cursor.execute("""
                INSERT INTO movie_genre (movie_id, genre_id)
                SELECT %s, %s WHERE NOT EXISTS (
                    SELECT 1 FROM movie_genre
                    WHERE movie_id = %s AND genre_id = %s
                )
            """, (movie_id, genre_id, movie_id, genre_id))
        print(f"✓ movie_genre 建立 {len(relations)} 条关联")
    if missing:
        print(f"⚠ 存在 {len(missing)} 个类型在 type.json 中未定义: {', '.join(sorted(list(missing))[:8])} ...")


def import_users_from_comments(cursor, comments_data):
    """根据评论创建用户."""
    users = {}
    for item in comments_data:
        for comment in item.get('comments', []):
            author_id = str(comment.get('author_id') or '').strip()
            if not author_id:
                continue
            username = (comment.get('author') or '').strip()[:100] or f"用户{author_id}"
            if author_id not in users:
                users[author_id] = username
    if not users:
        print("⚠ 评论数据中未找到用户信息")
        return {}

    # 使用循环插入，检查是否存在再插入
    for ext_id, name in users.items():
        cursor.execute("""
            INSERT INTO "user" (external_id, username, password, email, avatar_url)
            SELECT %s, %s, %s, %s, %s WHERE NOT EXISTS (
                SELECT 1 FROM "user" WHERE external_id = %s
            )
        """, (ext_id, name, '123456', '12345678@email.com', None, ext_id))
    cursor.execute('SELECT user_id, external_id FROM "user" WHERE external_id IS NOT NULL')
    mapping = {row[1]: row[0] for row in cursor.fetchall()}
    print(f"✓ 同步 {len(mapping)} 名用户")
    return mapping


def import_reviews_from_json(cursor, comments_data, movie_id_map, user_map):
    """导入评论数据，建立用户与电影的关联."""
    reviews = []
    skipped = 0
    for item in comments_data:
        douban_id = parse_int(item.get('movie_id'))
        movie_id = movie_id_map.get(douban_id)
        if not movie_id:
            continue
        for comment in item.get('comments', []):
            external_user_id = str(comment.get('author_id') or '').strip()
            user_id = user_map.get(external_user_id)
            if not user_id:
                skipped += 1
                continue
            review_ext_id = str(comment.get('comment_id') or '').strip()
            if not review_ext_id:
                skipped += 1
                continue
            rating = comment.get('rating')
            rating_value = float(rating) if rating not in (None, '') else None
            reviews.append((
                review_ext_id,
                movie_id,
                user_id,
                rating_value,
                comment.get('content', ''),
                parse_int(comment.get('votes')) or 0,
                comment.get('created_at'),
                comment.get('spoiler'),
                comment.get('status')
            ))

    if not reviews:
        print("⚠ 没有可写入的评论数据")
        return

    # 使用循环插入，先检查是否存在再插入或更新
    for review_data in reviews:
        douban_review_id = review_data[0]
        # 先检查是否存在
        cursor.execute("SELECT 1 FROM review WHERE douban_review_id = %s", (douban_review_id,))
        exists = cursor.fetchone()

        if exists:
            # 如果存在，更新
            cursor.execute("""
                UPDATE review SET
                    movie_id = %s,
                    user_id = %s,
                    user_rating = %s,
                    comment = %s,
                    useful_count = %s,
                    created_at = %s,
                    spoiler = %s,
                    status = %s
                WHERE douban_review_id = %s
            """, review_data[1:] + (review_data[0],))
        else:
            # 如果不存在，插入
            cursor.execute("""
                INSERT INTO review (douban_review_id, movie_id, user_id, user_rating,
                                    comment, useful_count, created_at, spoiler, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, review_data)

    print(f"✓ 导入/更新 {len(reviews)} 条评论，跳过 {skipped} 条")


def main():
    conn = None
    try:
        conn = psycopg2.connect(**Config.DB_CONFIG)
        cursor = conn.cursor()

        print("=" * 60)
        print("MovieMind 数据导入工具")
        print("=" * 60)

        base_dir = os.path.dirname(os.path.dirname(__file__))
        csv_file = os.path.join(base_dir, 'original_data', 'douban_movies.csv')
        comments_file = os.path.join(base_dir, 'original_data', 'comments.json')
        type_file = os.path.join(base_dir, 'original_data', 'type.json')

        genre_map = sync_genres_from_json(cursor, type_file)
        conn.commit()

        movie_context = import_movies_from_csv(cursor, csv_file)
        conn.commit()

        movie_id_map = build_movie_id_map(cursor, movie_context['douban_ids'])
        director_map = upsert_people(cursor, 'director', 'director_id', movie_context['directors'])
        actor_map = upsert_people(cursor, 'actor', 'actor_id', movie_context['actors'])
        link_movie_people(cursor, 'movie_director', 'director_id', movie_context['movie_directors'], director_map, movie_id_map)
        link_movie_people(cursor, 'movie_actor', 'actor_id', movie_context['movie_actors'], actor_map, movie_id_map)
        link_movie_genres(cursor, movie_context['movie_genres'], genre_map, movie_id_map)
        conn.commit()

        if os.path.exists(comments_file):
            comments_data = load_comments_data(comments_file)
            user_map = import_users_from_comments(cursor, comments_data)
            conn.commit()
            import_reviews_from_json(cursor, comments_data, movie_id_map, user_map)
            conn.commit()
        else:
            print(f"⚠ 未找到评论文件: {comments_file}")

        print("\n" + "=" * 60)
        print("数据导入完成！统计信息:")
        print("=" * 60)
        cursor.execute("SELECT COUNT(*) FROM movie")
        print(f"电影总数: {cursor.fetchone()[0]}")
        cursor.execute("SELECT COUNT(*) FROM director")
        print(f"导演总数: {cursor.fetchone()[0]}")
        cursor.execute("SELECT COUNT(*) FROM actor")
        print(f"演员总数: {cursor.fetchone()[0]}")
        cursor.execute('SELECT COUNT(*) FROM "user"')
        print(f"用户总数: {cursor.fetchone()[0]}")
        cursor.execute("SELECT COUNT(*) FROM genre")
        print(f"类型总数: {cursor.fetchone()[0]}")
        cursor.execute("SELECT COUNT(*) FROM review")
        print(f"评论总数: {cursor.fetchone()[0]}")

        cursor.close()
        conn.close()

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"✗ 数据导入失败: {str(e)}")
        raise


if __name__ == '__main__':
    main()
