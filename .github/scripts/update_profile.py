#!/usr/bin/env python3
"""
Self-update the GitHub profile README:
  - <!--STATS:START-->     public repos / total stars (followers badge is live via shields.io)
  - <!--GUESTBOOK:START--> latest guestbook comments from the "📖 Guestbook" issue

Run from the repo root. Requires GITHUB_TOKEN to create the guestbook issue;
statistics updates work anonymously.
"""
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request

OWNER = "MjxUpUp"
REPO = "MjxUpUp"
API = "https://api.github.com"
README_PATH = "README.md"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ISSUE_TITLE = "📖 Guestbook"
MAX_MESSAGES = 5

STATS_START = "<!--STATS:START-->"
STATS_END = "<!--STATS:END-->"
GUEST_START = "<!--GUESTBOOK:START-->"
GUEST_END = "<!--GUESTBOOK:END-->"

GUEST_PLACEHOLDER = (
    "**Sign it here:** [📖 Guestbook]"
    "(https://github.com/MjxUpUp/MjxUpUp/issues/new) — leave a message and it shows up below!\n\n"
    "| Guest | Message | When |\n|---|---|---|\n"
    "| — | Be the first to sign! ✨ | — |\n\n"
    "<sub>latest 0 messages · auto-updated</sub>"
)


def api(path: str, method: str = "GET", body: dict | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{OWNER}-profile-updater",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API {method} {path} -> {e.code}: {e.read()[:300]!r}") from e


def fetch_all(path: str) -> list:
    """Fetch every page of a paginated GitHub API list endpoint."""
    items, page = [], 1
    while True:
        sep = "&" if "?" in path else "?"
        batch = api(f"{path}{sep}per_page=100&page={page}")
        if not batch:
            return items
        items.extend(batch)
        page += 1


def find_guestbook_issue():
    issues = fetch_all(f"/repos/{OWNER}/{REPO}/issues?state=open")
    for it in issues:
        if "pull_request" not in it and "guestbook" in (it.get("title") or "").strip().lower():
            return it
    return None


def create_guestbook_issue() -> dict:
    body = (
        "**Welcome!** 👋 Leave a message below and it will show up on my GitHub profile.\n\n"
        "Keep it kind and on-topic. Spam will be removed."
    )
    return api(
        f"/repos/{OWNER}/{REPO}/issues",
        method="POST",
        body={"title": ISSUE_TITLE, "body": body},
    )


def render_guestbook(issue) -> str:
    url = issue["html_url"]
    comments = fetch_all(f"/repos/{OWNER}/{REPO}/issues/{issue['number']}/comments")
    latest = [
        c
        for c in comments
        if c.get("user")
        and c["user"]["login"] not in ("github-actions[bot]", "dependabot[bot]")
    ][-MAX_MESSAGES:][::-1]

    if not latest:
        rows = "| — | Be the first to sign! ✨ | — |"
    else:
        lines = []
        for c in latest:
            login = c["user"]["login"]
            avatar = c["user"]["avatar_url"]
            message = html.escape(re.sub(r"\s+", " ", (c.get("body") or "").strip()))
            if not message:
                message = "—"
            if len(message) > 120:
                message = message[:117] + "…"
            message = message.replace("|", "\\|")
            when = c["created_at"][:10]
            lines.append(
                f'| <img width="24" src="{avatar}"/> **{login}** | {message} | {when} |'
            )
        rows = "\n".join(lines)

    return (
        f"**Sign it here:** [{ISSUE_TITLE}]({url})\n\n"
        f"| Guest | Message | When |\n|---|---|---|\n{rows}\n\n"
        f"<sub>latest {len(latest)} messages · auto-updated</sub>"
    )


def render_stats(user, stars: int) -> str:
    return (
        f'<img src="https://img.shields.io/github/followers/{OWNER}?style=flat-square&label=followers&color=7AA2F7"/>\n'
        f'<img src="https://img.shields.io/badge/public%20repos-{user["public_repos"]}-9ECE6A?style=flat-square"/>\n'
        f'<img src="https://img.shields.io/badge/total%20stars-{stars}-F7768E?style=flat-square"/>'
    )


def replace_block(text: str, start: str, end: str, content: str) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        raise RuntimeError(f"marker {start!r} not found in {README_PATH}")
    return pattern.sub(lambda _: f"{start}\n{content}\n{end}", text)


def main() -> int:
    user = api(f"/users/{OWNER}")
    repos = fetch_all(f"/users/{OWNER}/repos")
    stars = sum(r.get("stargazers_count", 0) for r in repos)

    with open(README_PATH, encoding="utf-8") as f:
        text = f.read()

    text = replace_block(text, STATS_START, STATS_END, render_stats(user, stars))

    issue = find_guestbook_issue()
    if issue is None:
        if TOKEN:
            issue = create_guestbook_issue()
            print(f"created guestbook issue #{issue['number']}")
        else:
            print("no GITHUB_TOKEN: keeping guestbook placeholder", file=sys.stderr)
    guest = render_guestbook(issue) if issue is not None else GUEST_PLACEHOLDER
    text = replace_block(text, GUEST_START, GUEST_END, guest)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(text)

    print(
        f"README updated: {user['public_repos']} repos, {stars} stars, "
        f"guestbook={'#' + str(issue['number']) if issue else 'placeholder'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
