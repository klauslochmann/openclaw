#!/usr/bin/env python3
"""Fetch stock market news from themarketear.com and print to stdout."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Iterable, List, Optional, Set, Tuple


BASE_URL = "https://themarketear.com"
NEWSFEED_PATH = "/newsfeed"
RENDER_POSTS_PATH = "/render/posts"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)


def build_cookie(token: str) -> str:
    tags_payload = json.dumps({"tags": ["newsfeed"]}, separators=(",", ":"))
    tags_cookie = urllib.parse.quote(tags_payload, safe="")
    return f"U={token}; P={tags_cookie}"


def make_request(url: str, *, cookie: str, headers: Dict[str, str], data: Optional[bytes] = None) -> bytes:
    request_headers = {
        "User-Agent": USER_AGENT,
        "Cookie": cookie,
        **headers,
    }
    req = urllib.request.Request(url, headers=request_headers, data=data)
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def fetch_newsfeed_html(cookie: str) -> str:
    url = f"{BASE_URL}{NEWSFEED_PATH}"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    raw = make_request(url, cookie=cookie, headers=headers)
    return raw.decode("utf-8", "replace")


def fetch_render_posts_html(cookie: str, post_id: Optional[str]) -> str:
    url = f"{BASE_URL}{RENDER_POSTS_PATH}"
    payload = json.dumps({"tags": ["newsfeed"], "query": None, "postId": post_id})
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}{NEWSFEED_PATH}",
        "X-Requested-With": "XMLHttpRequest",
    }
    raw = make_request(url, cookie=cookie, headers=headers, data=payload.encode("utf-8"))
    return raw.decode("utf-8", "replace").strip()


def unescape_text(value: str) -> str:
    return html.unescape(value).strip()


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value).strip()


def extract_records_from_html(html_text: str) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    for article in re.findall(r"<article[^>]*>.*?</article>", html_text, re.S | re.I):
        json_ld_match = re.search(
            r"<script[^>]*type=\"application/ld\+json\"[^>]*>(.*?)</script>",
            article,
            re.S | re.I,
        )
        if json_ld_match:
            data = json_ld_match.group(1).strip()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                title = payload.get("headline") or payload.get("name") or ""
                description = payload.get("description") or ""
                if isinstance(title, str) or isinstance(description, str):
                    title_text = unescape_text(str(title)) if title else ""
                    desc_text = unescape_text(str(description)) if description else ""
                    if title_text or desc_text:
                        records.append({
                            "title": title_text,
                            "description": desc_text,
                        })
                        continue

        title_match = re.search(r"<h1[^>]*>(.*?)</h1>", article, re.S | re.I)
        if not title_match:
            title_match = re.search(r"<h2[^>]*>(.*?)</h2>", article, re.S | re.I)
        if not title_match:
            title_match = re.search(r"<h3[^>]*>(.*?)</h3>", article, re.S | re.I)
        desc_match = re.search(r"<p[^>]*>(.*?)</p>", article, re.S | re.I)
        title = strip_tags(title_match.group(1)) if title_match else ""
        description = strip_tags(desc_match.group(1)) if desc_match else ""
        if title or description:
            records.append({
                "title": unescape_text(title),
                "description": unescape_text(description),
            })
    return records


def extract_post_id_from_html(html_text: str) -> Optional[str]:
    ids = re.findall(r"<article[^>]*\sid=\"([^\"]+)\"", html_text, re.I)
    if ids:
        return ids[-1]
    match = re.search(r"data-post-id=\"([^\"]+)\"", html_text)
    if match:
        return match.group(1)
    match = re.search(r'"postId"\s*:\s*"([^"]+)"', html_text)
    if match:
        return match.group(1)
    return None


def find_article_records(html_text: str) -> List[Dict[str, str]]:
    return extract_records_from_html(html_text)


def dedupe_records(records: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: Set[Tuple[str, str]] = set()
    unique: List[Dict[str, str]] = []
    for record in records:
        key = (record.get("title", ""), record.get("description", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def print_records(records: Iterable[Dict[str, str]]) -> None:
    for record in records:
        title = record.get("title", "").strip()
        description = record.get("description", "").strip()
        if not title and not description:
            continue
        print(title)
        if description:
            print(description)
        print()


def run(pages: int) -> int:
    token = os.environ.get("TME_TOKEN")
    if not token:
        print("TME_TOKEN is not set.", file=sys.stderr)
        return 2

    cookie = build_cookie(token)

    try:
        html_text = fetch_newsfeed_html(cookie)
    except urllib.error.URLError as exc:
        print(f"Failed to load newsfeed: {exc}", file=sys.stderr)
        return 1

    records = dedupe_records(find_article_records(html_text))

    if not records:
        try:
            fallback_post_id = extract_post_id_from_html(html_text)
            html_text = fetch_render_posts_html(cookie, fallback_post_id)
        except urllib.error.URLError as exc:
            print(f"Failed to load fallback page: {exc}", file=sys.stderr)
            return 1
        records = dedupe_records(find_article_records(html_text))

    if records:
        print_records(records)

    if pages <= 1:
        return 0

    last_post_id = extract_post_id_from_html(html_text)
    if not last_post_id:
        print("Warning: could not find a post id for pagination.", file=sys.stderr)
        return 0

    page = 2
    while page <= pages and last_post_id:
        try:
            html_text = fetch_render_posts_html(cookie, last_post_id)
        except urllib.error.URLError as exc:
            print(f"Failed to load page {page}: {exc}", file=sys.stderr)
            return 1

        page_records = dedupe_records(find_article_records(html_text))
        if not page_records:
            break

        print_records(page_records)
        last_post_id = extract_post_id_from_html(html_text)
        page += 1

    return 0


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch The Market Ear newsfeed posts.")
    parser.add_argument(
        "--pages",
        type=int,
        default=5,
        help="Total pages to fetch, including the first page.",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    pages = max(1, args.pages)
    return run(pages)


if __name__ == "__main__":
    raise SystemExit(main())
