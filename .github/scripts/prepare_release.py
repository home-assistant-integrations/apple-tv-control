"""Prepare a release: move the changelog entries and set the version.

Usage: python3 .github/scripts/prepare_release.py <version> <yyyy-mm-dd>

- CHANGELOG.md: the entries under "## [Unreleased]" become the section
  "## [<version>] - <date>"; an empty "## [Unreleased]" stays on top.
- manifest.json and const.py: the version is set to <version>.

Prints the moved entries (the release notes). Nothing is written when the
changelog has no entries for the release.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
CHANGELOG = ROOT / "CHANGELOG.md"
MANIFEST = ROOT / "custom_components/apple_tv_control/manifest.json"

# Files with the integration version: path -> pattern, group 2 is the version
VERSION_FILES = {
    MANIFEST: re.compile(r'^(\s*"version":\s*")([^"]*)(")', re.MULTILINE),
    ROOT / "custom_components/apple_tv_control/const.py": re.compile(
        r'^(VERSION\s*=\s*")([^"]*)(")', re.MULTILINE
    ),
}

UNRELEASED = re.compile(r"^## \[Unreleased\][^\n]*\n", re.MULTILINE)
# A section ends at the next version heading or at the link references at the end
SECTION_END = re.compile(r"^(## \[|\[[^\]]+\]: )", re.MULTILINE)


class ReleaseError(Exception):
    """The repository is not ready for the release."""


def promote_changelog(text: str, version: str, date: str) -> tuple[str, str]:
    """Return the new changelog and the entries moved into the version section."""
    if re.search(rf"^## \[{re.escape(version)}\]", text, re.MULTILINE):
        raise ReleaseError(f"CHANGELOG.md already has a section for {version}")
    if (unreleased := UNRELEASED.search(text)) is None:
        raise ReleaseError("CHANGELOG.md has no '## [Unreleased]' section")

    rest = text[unreleased.end() :]
    end = SECTION_END.search(rest)
    entries = (rest[: end.start()] if end else rest).strip("\n")
    if not entries.strip():
        raise ReleaseError(
            "There are no entries under '## [Unreleased]' in CHANGELOG.md, "
            "describe the changes of this release there first"
        )

    new = f"{text[: unreleased.start()]}## [Unreleased]\n\n## [{version}] - {date}\n\n{entries}\n"
    if end:
        new += f"\n{rest[end.start():]}"
    return new, entries


def set_version(path: Path, text: str, version: str) -> str:
    """Return the file content with the version replaced."""
    new, count = VERSION_FILES[path].subn(
        lambda match: f"{match[1]}{version}{match[3]}", text, count=1
    )
    if count != 1:
        raise ReleaseError(f"No version found in {path.relative_to(ROOT)}")
    return new


def main() -> None:
    """Prepare the release given on the command line."""
    version, date = sys.argv[1], sys.argv[2]
    try:
        if not re.fullmatch(r"\d{4}\.\d{1,2}\.\d+", version):
            raise ReleaseError(f"Invalid version {version!r}, expected yyyy.mm.rm")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ReleaseError(f"Invalid date {date!r}, expected yyyy-mm-dd")

        # Work out all changes first, so nothing is written when one fails
        changelog, entries = promote_changelog(CHANGELOG.read_text(), version, date)
        updates = {CHANGELOG: changelog}
        for path in VERSION_FILES:
            updates[path] = set_version(path, path.read_text(), version)
        if json.loads(updates[MANIFEST])["version"] != version:
            raise ReleaseError("manifest.json does not contain the new version")
    except ReleaseError as err:
        print(f"::error::{err}")
        sys.exit(1)

    for path, content in updates.items():
        path.write_text(content)
    print(entries)


if __name__ == "__main__":
    main()
