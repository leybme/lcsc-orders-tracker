"""Lightweight crawler for LCSC product detail pages.

Reads `combined.csv`, takes the `LCSC Part Number` column, fetches each
product page, extracts a few public fields (title/name, brand, price if
exposed, description, image URL), and optionally downloads the product
image.

By default this only processes the first 3 parts and prints debug output so
you can validate parsing without hammering the site. Increase `--limit` when
you're happy with the results.
"""

from __future__ import annotations

import argparse
import html
import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
DEFAULT_COMBINED = ROOT / "combined.csv"
DEFAULT_OUTPUT = ROOT / "crawled_products.csv"
DEFAULT_IMAGE_DIR = ROOT / "images"
DEFAULT_HTML = ROOT / "crawled_products.html"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)


def _load_parts(csv_path: Path) -> List[str]:
    df = pd.read_csv(csv_path)
    if "LCSC Part Number" not in df.columns:
        raise KeyError("`LCSC Part Number` column missing in combined.csv")
    # Drop NA and strip whitespace
    parts = [str(p).strip() for p in df["LCSC Part Number"].dropna().tolist() if str(p).strip()]
    return parts


def _get_meta(soup: BeautifulSoup, key: str) -> Optional[str]:
    tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
    return tag.get("content") if tag and tag.get("content") else None


def _parse_json_ld(soup: BeautifulSoup) -> Optional[Dict]:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        text = tag.string or tag.get_text("", strip=True)
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            return data
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") == "Product":
                    return item
    return None


def _first_image_url(raw: Optional[object]) -> Optional[str]:
    if isinstance(raw, list) and raw:
        return str(raw[0])
    if isinstance(raw, str):
        return raw
    return None


def fetch_product(part: str, session: requests.Session, timeout: int = 20) -> Dict[str, Optional[str]]:
    url = f"https://www.lcsc.com/product-detail/{part}.html"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    print(f"[DEBUG] Fetching {url}")
    resp = session.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    json_ld = _parse_json_ld(soup)

    data: Dict[str, Optional[str]] = {
        "LCSC Part Number": part,
        "product_url": url,
    }

    if json_ld:
        data["name"] = json_ld.get("name") or json_ld.get("title")
        brand = json_ld.get("brand")
        if isinstance(brand, dict):
            data["brand"] = brand.get("name")
        elif isinstance(brand, str):
            data["brand"] = brand
        data["sku"] = json_ld.get("sku")
        data["description"] = json_ld.get("description")
        offers = json_ld.get("offers")
        if isinstance(offers, dict):
            data["price"] = offers.get("price")
            data["currency"] = offers.get("priceCurrency")
        data["image_url"] = _first_image_url(json_ld.get("image"))

    # Fallbacks from meta tags
    data.setdefault("name", _get_meta(soup, "og:title"))
    data.setdefault("description", _get_meta(soup, "description"))
    data.setdefault("image_url", _get_meta(soup, "og:image"))

    return data


def download_image(url: str, dest_dir: Path, part: str, session: requests.Session, timeout: int = 20) -> Optional[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    resp = session.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=timeout)
    resp.raise_for_status()

    # Guess extension from Content-Type
    content_type = resp.headers.get("Content-Type", "image/jpeg")
    ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".jpg"
    file_path = dest_dir / f"{part}{ext}"

    with open(file_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return file_path


def build_html(records: List[Dict[str, Any]], html_path: Path) -> None:
    html_path = html_path.resolve()
    html_path.parent.mkdir(parents=True, exist_ok=True)

    def esc(val: Optional[str]) -> str:
        return html.escape(str(val)) if val is not None else ""

    rows = []
    for rec in records:
        part = rec.get("LCSC Part Number", "")
        product_url = rec.get("product_url") or (f"https://www.lcsc.com/product-detail/{part}.html" if part else "")
        name = esc(rec.get("name")) or esc(part)
        brand = esc(rec.get("brand"))
        price = esc(rec.get("price"))
        currency = esc(rec.get("currency"))
        desc = esc(rec.get("description"))
        image_src = rec.get("image_path") or rec.get("image_url")
        image_tag = f'<img src="{esc(image_src)}" alt="{esc(part)}" width="160" loading="lazy">' if image_src else ""
        part_link = f'<a href="{esc(product_url)}" target="_blank" rel="noreferrer">{esc(part)}</a>' if product_url else esc(part)

        rows.append(
            f"<tr>"
            f"<td>{image_tag}</td>"
            f"<td>{part_link}</td>"
            f"<td>{name}</td>"
            f"<td>{brand}</td>"
            f"<td>{price} {currency}</td>"
            f"<td>{desc}</td>"
            f"</tr>"
        )

    table_body = "\n".join(rows)
    html_doc = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>LCSC Crawl Results</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 24px; background: #f8f9fb; }}
        h1 {{ margin-bottom: 12px; }}
        table {{ width: 100%; border-collapse: collapse; background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
        th, td {{ border: 1px solid #e2e6eb; padding: 8px 10px; vertical-align: top; }}
        th {{ background: #eef2f7; text-align: left; }}
        img {{ display: block; max-width: 160px; height: auto; }}
    </style>
</head>
<body>
    <h1>LCSC Crawl Results</h1>
    <table>
        <thead>
            <tr>
                <th>Image</th>
                <th>LCSC Part Number</th>
                <th>Name</th>
                <th>Brand</th>
                <th>Price</th>
                <th>Description</th>
            </tr>
        </thead>
        <tbody>
            {table_body}
        </tbody>
    </table>
</body>
</html>
"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_doc)

    print(f"[INFO] Wrote HTML summary to {html_path}")


def run_crawl(
    combined_path: Path,
    output_path: Path,
    limit: int,
    sleep_s: float,
    download_images: bool,
    image_dir: Path,
    html_output: Path,
) -> None:
    parts = _load_parts(combined_path)
    if limit > 0:
        parts = parts[:limit]

    print(f"[INFO] Crawling {len(parts)} parts (limit={limit})")

    session = requests.Session()
    records = []

    for idx, part in enumerate(parts, start=1):
        try:
            record = fetch_product(part, session)
            if download_images and record.get("image_url"):
                saved = download_image(record["image_url"], image_dir, part, session)
                record["image_path"] = str(saved) if saved else None
            records.append(record)
            print(f"[DEBUG] Parsed {part}: {json.dumps(record, ensure_ascii=False)}")
        except Exception as exc:  # noqa: BLE001 broad but keeps run going
            print(f"[WARN] Failed {part}: {exc}")
        if sleep_s:
            time.sleep(sleep_s)

    if records:
        pd.DataFrame(records).to_csv(output_path, index=False)
        print(f"[INFO] Saved {len(records)} records to {output_path}")
        if html_output:
            build_html(records, html_output)
    else:
        print("[INFO] No records saved")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl LCSC product pages from combined.csv")
    parser.add_argument("--combined", type=Path, default=DEFAULT_COMBINED, help="Path to combined.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Where to write crawled data CSV")
    parser.add_argument("--limit", type=int, default=3, help="Number of parts to crawl (default: 3 for safe debug)")
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds to sleep between requests")
    parser.add_argument("--download-images", action="store_true", help="Download product images to the images folder")
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR, help="Directory to save images when enabled")
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML, help="Write HTML summary to this file")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_crawl(
        combined_path=args.combined,
        output_path=args.output,
        limit=args.limit,
        sleep_s=args.sleep,
        download_images=args.download_images,
        image_dir=args.image_dir,
        html_output=args.html_output,
    )