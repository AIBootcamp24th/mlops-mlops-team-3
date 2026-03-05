#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

README_PATH = Path(__file__).resolve().parents[1] / "README.md"
TEAM_SECTION_HEADER = "## 2. Team Members"
CONTRIB_SECTION_HEADER = "### 기여도 (main 브랜치 커밋 기준)"
START_MARKER = "<!-- contribution-table:start -->"
END_MARKER = "<!-- contribution-table:end -->"
BOT_KEYWORDS = ("[bot]", "github-classroom")


def run_git_shortlog_main() -> list[str]:
    # GitHub Actions에서는 detached HEAD 상태라 local `main` 브랜치가 없을 수 있어 fallback을 사용한다.
    fallback_refs = ("main", "origin/main", "refs/remotes/origin/main", "HEAD")
    last_stderr = ""

    for ref in fallback_refs:
        result = subprocess.run(
            ["git", "shortlog", "-sne", ref],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return [line.rstrip() for line in result.stdout.splitlines() if line.strip()]
        last_stderr = (result.stderr or "").strip()

    raise RuntimeError(
        "git shortlog 실행에 실패했습니다. "
        f"시도한 ref: {', '.join(fallback_refs)} / 오류: {last_stderr}"
    )


def normalize(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def parse_team_members(readme: str) -> list[tuple[str, str]]:
    start = readme.find(TEAM_SECTION_HEADER)
    if start == -1:
        raise RuntimeError(f"'{TEAM_SECTION_HEADER}' 섹션을 찾을 수 없습니다.")

    remaining = readme[start:]
    next_h2 = remaining.find("\n## ", len(TEAM_SECTION_HEADER))
    section = remaining if next_h2 == -1 else remaining[:next_h2]
    member_matches = re.findall(
        r"-\s+\[([^\]]+)\]\(https://github\.com/([A-Za-z0-9-]+)\)",
        section,
    )
    if not member_matches:
        raise RuntimeError("Team Members 섹션에서 이름/ GitHub 사용자명을 찾지 못했습니다.")
    return member_matches


def extract_shortlog_entry(line: str) -> tuple[int, str, str] | None:
    match = re.match(r"^\s*(\d+)\s+(.+?)\s+<([^>]+)>\s*$", line)
    if not match:
        return None
    count = int(match.group(1))
    name = match.group(2).strip()
    email = match.group(3).strip().lower()
    return count, name, email


def detect_member(username_set: set[str], author_name: str, author_email: str) -> str | None:
    author_name_lower = author_name.lower()
    email_local = author_email.split("@", 1)[0].lower()
    candidates = list(username_set)

    for username in candidates:
        if username.lower() == author_name_lower:
            return username
        if username.lower() == email_local:
            return username
        if normalize(username) == normalize(author_name):
            return username
        if normalize(username) == normalize(email_local):
            return username
    return None


def calculate_member_contributions(
    member_pairs: list[tuple[str, str]], shortlog_lines: list[str]
) -> dict[str, int]:
    usernames = [username for _, username in member_pairs]
    username_set = set(usernames)
    contributions = {username: 0 for username in usernames}
    email_totals: dict[str, int] = defaultdict(int)
    email_names: dict[str, set[str]] = defaultdict(set)

    for line in shortlog_lines:
        parsed = extract_shortlog_entry(line)
        if parsed is None:
            continue
        count, name, email = parsed
        lower_name = name.lower()
        if any(keyword in lower_name for keyword in BOT_KEYWORDS) or any(
            keyword in email for keyword in BOT_KEYWORDS
        ):
            continue
        email_totals[email] += count
        email_names[email].add(name)

    for email, total in email_totals.items():
        mapped = None
        for name in sorted(email_names[email]):
            mapped = detect_member(username_set, name, email)
            if mapped is not None:
                break
        if mapped is not None:
            contributions[mapped] += total

    return contributions


def badge_url(label: str, message: str, color: str, logo: str | None = None) -> str:
    label_q = quote(label, safe="")
    message_q = quote(message, safe="")
    url = f"https://img.shields.io/badge/{label_q}-{message_q}-{color}?style=for-the-badge"
    if logo:
        url += f"&logo={quote(logo, safe='')}"
    return url


def percent_color(percent: float) -> str:
    if percent >= 50:
        return "2ea043"
    if percent >= 30:
        return "1f6feb"
    if percent >= 10:
        return "fb8c00"
    return "9e9e9e"


def build_contribution_table_block(
    member_pairs: list[tuple[str, str]], contributions: dict[str, int]
) -> str:
    total_commits = sum(contributions.values())
    name_by_username = {username: name for name, username in member_pairs}

    rows = []
    for username, commits in sorted(
        contributions.items(),
        key=lambda item: (-item[1], item[0].lower()),
    ):
        percent = (commits / total_commits * 100) if total_commits > 0 else 0.0
        percent_badge = (
            f"![contribution]"
            f"({badge_url('contribution', f'{percent:.2f}%', percent_color(percent), logo='github')})"
        )
        member_name = name_by_username.get(username, username)
        rows.append(
            f"| [{member_name} (@{username})](https://github.com/{username}) | {percent_badge} |"
        )

    table_lines = [
        START_MARKER,
        "| 팀원 (이름 + GitHub) | 기여도 |",
        "| --- | ---: |",
        *rows,
        END_MARKER,
    ]
    return "\n".join(table_lines)


def build_full_contribution_section(table_block: str) -> str:
    section_lines = [
        CONTRIB_SECTION_HEADER,
        "",
        "`main` 브랜치의 `git shortlog -sne main` 결과를 기준으로, `shields.io` 배지로 자동 렌더링합니다.",
        table_block,
    ]
    return "\n".join(section_lines)


def upsert_contribution_section(readme: str, table_block: str) -> str:
    if START_MARKER in readme and END_MARKER in readme:
        start = readme.index(START_MARKER)
        end = readme.index(END_MARKER) + len(END_MARKER)
        return f"{readme[:start]}{table_block}{readme[end:]}"

    team_header_index = readme.find(TEAM_SECTION_HEADER)
    if team_header_index == -1:
        raise RuntimeError(f"'{TEAM_SECTION_HEADER}' 섹션을 찾을 수 없습니다.")

    remaining = readme[team_header_index:]
    next_h2 = remaining.find("\n## ", len(TEAM_SECTION_HEADER))
    if next_h2 == -1:
        insert_pos = len(readme)
    else:
        insert_pos = team_header_index + next_h2

    section = build_full_contribution_section(table_block)
    insertion = f"\n\n{section}\n"
    return f"{readme[:insert_pos]}{insertion}{readme[insert_pos:]}"


def main() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    member_pairs = parse_team_members(readme)
    shortlog_lines = run_git_shortlog_main()
    contributions = calculate_member_contributions(member_pairs, shortlog_lines)
    table_block = build_contribution_table_block(member_pairs, contributions)
    updated = upsert_contribution_section(readme, table_block)
    README_PATH.write_text(updated, encoding="utf-8")
    print("README 기여도 표를 main 브랜치 기준으로 갱신했습니다.")


if __name__ == "__main__":
    main()
