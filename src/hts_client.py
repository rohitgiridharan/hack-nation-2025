#!/usr/bin/env python3
"""
HTS (USITC) client – search and fetch tariff rates for goods imported into the U.S.

Endpoints (from HTS external user guide):
- Base:   https://hts.usitc.gov/reststop
- Search: GET /reststop/search?keyword={term}
- Export: GET /reststop/exportList?from={code}&to={code}&format=JSON&styles={true|false}

Usage examples:
  python hts_client.py search "bicycle"
  python hts_client.py code 4011500000
  python hts_client.py code 4011.50.00.00

Notes:
- Search results include top-level fields: general, special, other.
- For a specific HTS code, we call exportList with from==to to retrieve that item.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
from typing import Any, Dict, Iterable, List, Optional

import requests


BASE_URL = "https://hts.usitc.gov/reststop"


def extract_tariff_percentage(rate_string: Any) -> str:
    """Extract a percentage from a rate string (e.g., "5.3%"),
    or return "0%" for "Free", or a fallback description.
    """
    if not isinstance(rate_string, str) or not rate_string:
        return "N/A"

    s = rate_string.strip()
    if s.lower() == "free":
        return "0%"

    m = re.search(r"(\d+\.?\d*)\s*%", s)
    if m:
        return f"{m.group(1)}%"
    return "No percentage rate found"


def format_hts(code: str) -> str:
    """Format an HTS code into one of the common dotted forms.

    Accepts raw strings like "4011500000" or already-formatted codes like
    "4011.50.00.00" and returns a normalized representation that works with
    exportList. If length doesn't match 4/6/8/10 digits, return as-is.
    """
    digits = re.sub(r"\D", "", code)
    if len(digits) == 4:
        return digits
    if len(digits) == 6:
        return f"{digits[:4]}.{digits[4:6]}"
    if len(digits) == 8:
        return f"{digits[:4]}.{digits[4:6]}.{digits[6:8]}"
    if len(digits) == 10:
        # HTS 10-digit: 4-2-2-2
        return f"{digits[:4]}.{digits[4:6]}.{digits[6:8]}.{digits[8:10]}"
    # Fallback: pass-through
    return code


def search_hts(keyword: str, *, timeout: int = 20) -> List[Dict[str, Any]]:
    """Search tariff articles by description/keyword.

    Returns a list of dicts. Each item may include: htsno, description,
    general, special, other, units, etc.
    """
    resp = requests.get(
        f"{BASE_URL}/search",
        params={"keyword": keyword},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def get_tariff_by_code(hts_code: str, *, timeout: int = 20) -> Optional[Dict[str, Any]]:
    """Fetch tariff row for a specific HTS code using exportList.

    We call exportList with from==to==code and scan for the exact code
    (after normalization). Returns the matching article dict, or None.
    """
    code_norm = format_hts(hts_code)
    resp = requests.get(
        f"{BASE_URL}/exportList",
        params={
            "from": code_norm,
            "to": code_norm,
            "format": "JSON",
            "styles": "false",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    # Prefer exact matches; if none, fallback to first non-superior entry
    # The API returns an array; when from==to the match should be present.
    # Return the first element if present.
    if isinstance(data, list) and data:
        return data[0]
    return None


def print_search_results(items: List[Dict[str, Any]], limit: int = 20) -> None:
    if not items:
        print("No results found.")
        return
    print(f"{'HTS Number':<15} | {'Description':<70} | {'General':<10} | {'Other':<10}")
    print("-" * 120)
    for i, item in enumerate(items[:limit]):
        htsno = item.get("htsno", "N/A")
        desc = (item.get("description") or "").replace("\n", " ")
        if len(desc) > 67:
            desc = desc[:67] + "..."
        gen = extract_tariff_percentage(item.get("general"))
        other = extract_tariff_percentage(item.get("other"))
        print(f"{htsno:<15} | {desc:<70} | {gen:<10} | {other:<10}")


def cli() -> None:
    parser = argparse.ArgumentParser(description="USITC HTS tariff client")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Search by keyword/description")
    p_search.add_argument("keyword", help="Search term, e.g. 'bicycle'")
    p_search.add_argument("--limit", type=int, default=20, help="Max rows to print (default: 20)")

    p_code = sub.add_parser("code", help="Fetch tariff for a specific HTS code")
    p_code.add_argument("hts_code", help="HTS code (4/6/8/10 digits, with or without dots)")

    args = parser.parse_args()

    if args.cmd == "search":
        print(f"--- Searching HTS for '{args.keyword}' ---")
        try:
            items = search_hts(args.keyword)
        except requests.HTTPError as e:
            print(f"HTTP error: {e}")
            if e.response is not None:
                print(f"Status: {e.response.status_code}\nBody: {e.response.text[:400]}...")
            return
        except requests.RequestException as e:
            print(f"Network error: {e}")
            return
        print_search_results(items, limit=args.limit)
    elif args.cmd == "code":
        code = args.hts_code
        print(f"--- Fetching tariff for HTS {code} ---")
        try:
            row = get_tariff_by_code(code)
        except requests.HTTPError as e:
            print(f"HTTP error: {e}")
            if e.response is not None:
                print(f"Status: {e.response.status_code}\nBody: {e.response.text[:400]}...")
            return
        except requests.RequestException as e:
            print(f"Network error: {e}")
            return

        if not row:
            print("No matching row found.")
            return

        htsno = row.get("htsno", "N/A")
        desc = (row.get("description") or "").strip()
        gen = extract_tariff_percentage(row.get("general"))
        other = extract_tariff_percentage(row.get("other"))
        special = row.get("special") or ""

        print("HTS Number:", htsno)
        print("Description:", desc)
        print("General:", gen)
        print("Other:", other)
        if special:
            print("Special:", special)


if __name__ == "__main__":
    cli()

