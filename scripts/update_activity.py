#!/usr/bin/env python3
"""Render a self-hosted profile graphic from GitHub contribution data.

The existing SVG is never touched when the API request fails.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape


QUERY = """query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""


def fetch_counts(login: str, token: str) -> dict[str, int]:
    payload = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    request = Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "CopyPasteUser-profile-activity",
        },
    )
    with urlopen(request, timeout=25) as response:
        document = json.load(response)
    if document.get("errors"):
        raise RuntimeError("GitHub GraphQL returned errors; existing graphic preserved")
    user = document.get("data", {}).get("user")
    if not user:
        raise ValueError(f"User not found: {login}")
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {
        day["date"]: int(day["contributionCount"])
        for week in weeks
        for day in week["contributionDays"]
    }


def label(day: date) -> str:
    return f"{day:%b} {day.day}"


def render_svg(counts: dict[str, int], through: date) -> str:
    days = [(through - timedelta(days=30 - i)) for i in range(31)]
    values = [max(0, counts.get(day.isoformat(), 0)) for day in days]
    total, highest = sum(values), max(max(values), 1)
    metric_label_x = 50 + 28 * len(str(total))
    bars = []
    for index, (day, count) in enumerate(zip(days, values, strict=True)):
        height = max(4, round(70 * count / highest)) if count else 2
        color = (
            "#8af0ca" if count >= 100 else
            "#54cda6" if count >= 20 else
            "#318f7b" if count else "#253648"
        )
        bars.append(
            f'<g><title>{day.isoformat()}: {count} public contributions</title>'
            f'<rect x="{28 + 15 * index}" y="{151 - height}" width="9" '
            f'height="{height}" rx="3" fill="{color}"/></g>'
        )
    updated = datetime.now(timezone.utc).strftime("%d %b %Y")
    start, middle, end = (escape(label(day)) for day in
                          (days[0], days[len(days) // 2], days[-1]))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="520" height="216" viewBox="0 0 520 216" role="img" aria-labelledby="title desc">
  <title id="title">GitHub contribution activity</title>
  <desc id="desc">{total} public contributions in the 31 days through {through.isoformat()}.</desc>
  <rect x="1" y="1" width="518" height="214" rx="18" fill="#101b28" stroke="#304256" stroke-width="2"/>
  <g font-family="DejaVu Sans,Arial,sans-serif">
    <text x="28" y="35" fill="#9ab5c4" font-size="15" font-weight="700" letter-spacing="1.5">GITHUB / ACTIVITY</text>
    <text x="28" y="80" fill="#eaf5f6" font-size="43" font-weight="700">{total}</text>
    <text x="{metric_label_x}" y="77" fill="#b5ced6" font-size="15">public contributions</text>
    <text x="492" y="34" fill="#70ddba" text-anchor="end" font-size="12">LAST 31 DAYS</text>
    <path d="M28 151H492" stroke="#3a5367" stroke-width="1"/>
    {''.join(bars)}
    <text x="28" y="178" fill="#a2b9c8" font-size="13">{start}</text>
    <text x="260" y="178" fill="#a2b9c8" font-size="13" text-anchor="middle">{middle}</text>
    <text x="492" y="178" fill="#a2b9c8" font-size="13" text-anchor="end">{end}</text>
    <circle cx="30" cy="198" r="4" fill="#70ddba"/>
    <text x="42" y="202" fill="#a2b9c8" font-size="12">Source: GitHub public contributions</text>
    <text x="492" y="202" fill="#a2b9c8" font-size="12" text-anchor="end">Updated {updated}</text>
  </g>
</svg>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--login", default="CopyPasteUser")
    parser.add_argument("--output", type=Path, default=Path("assets/github-activity.svg"))
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        parser.error("GITHUB_TOKEN is required")
    counts = fetch_counts(args.login, token)
    today = datetime.now(timezone.utc).date()
    if len(counts) < 31 or today.isoformat() not in counts:
        raise RuntimeError("Incomplete contribution calendar; existing graphic preserved")
    result = render_svg(counts, today)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".svg.tmp")
    temporary.write_text(result, encoding="utf-8")
    temporary.replace(args.output)


if __name__ == "__main__":
    main()
