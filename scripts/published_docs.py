"""Validate English published documents against Japanese canonical documents.

No automatic translation is attempted. `record` is an explicit review checkpoint:
run it *only after* reviewing an English update against the Japanese source.

Usage:
    python scripts/published_docs.py status
    python scripts/published_docs.py release-check
    python scripts/published_docs.py check
    python scripts/published_docs.py record
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "devdocs" / "canonical_documents"
MANIFEST = ROOT / "devdocs" / "config" / "published_en.json"

# Explicit source -> destination mapping: generated Japanese documents remain canon.
FILES: dict[str, str] = {
    "README.md": "README.md",
    "STATUS.md": "STATUS.md",
    "CHANGELOG.md": "CHANGELOG.md",
    "GLOSSARY.md": "docs/GLOSSARY.md",
    "specification/INDEX.md": "docs/specification/INDEX.md",
    "specification/construct.md": "docs/specification/construct.md",
    "specification/frontend.md": "docs/specification/frontend.md",
    "specification/composition.md": "docs/specification/composition.md",
    "specification/conversion.md": "docs/specification/conversion.md",
    "realizer/INDEX.md": "docs/realizer/INDEX.md",
    "realizer/implementation-guide.md": "docs/realizer/implementation-guide.md",
    "realizer/declaration-reference.md": "docs/realizer/declaration-reference.md",
    "realizer/construct-reference.md": "docs/realizer/construct-reference.md",
    "realizer/admission-reference.md": "docs/realizer/admission-reference.md",
    "realizer/verification-guide.md": "docs/realizer/verification-guide.md",
}

# Translation completeness is a tracked editorial assertion, not a guessed feature.
STATUSES: dict[str, str] = {source: "translated" for source in FILES}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records() -> dict[str, dict[str, str]]:
    return {
        source: {
            "published": target,
            "canonical_sha256": digest(SOURCE / source),
            "english_sha256": digest(ROOT / target),
            "coverage": STATUSES[source],
        }
        for source, target in FILES.items()
    }


def record() -> int:
    missing = [
        p
        for source, target in FILES.items()
        for p in (SOURCE / source, ROOT / target)
        if not p.is_file()
    ]
    if missing:
        print("Cannot record missing documents: " + ", ".join(map(str, missing)))
        return 1
    MANIFEST.write_text(
        json.dumps({"schema": 1, "entries": records()}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(
        "Recorded source/published hashes; this does not certify translation quality."
    )
    return 0


def anchors(markdown: str) -> set[str]:
    results: set[str] = set()
    for title in re.findall(r"^#{1,6} +(.+)$", markdown, re.MULTILINE):
        # GitHub-ish simplified anchors (all our linked IDs use ASCII underscores).
        slug = re.sub(r"[^\w\- ]", "", title.strip().lower())
        slug = re.sub(r" +", "-", slug)
        results.add(slug)
    return results


def internal_link_errors(path: Path) -> list[str]:
    content = path.read_text(encoding="utf-8")
    failures = []
    # Remove fenced code, where snippets may contain Markdown-looking links.
    plain = re.sub(r"(?ms)^```[^\n]*\n.*?^```\s*$", "", content)
    # Inline code such as `t[0](args)` is not a Markdown link.
    plain = re.sub(r"`[^`\n]*`", "", plain)
    for href in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", plain):
        if href.startswith(("https:", "http:", "mailto:", "#")):
            if href.startswith("#") and href[1:].lower() not in anchors(content):
                failures.append(
                    f"{path.relative_to(ROOT)}: missing local anchor {href}"
                )
            continue
        clean, _, anchor = href.partition("#")
        target = (path.parent / clean).resolve()
        if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
            failures.append(f"{path.relative_to(ROOT)}: broken link {href}")
            continue
        if anchor and anchor.lower() not in anchors(target.read_text(encoding="utf-8")):
            failures.append(f"{path.relative_to(ROOT)}: missing anchor {href}")
    return failures


def translated_contract_errors(
    original: str, english: str, *, prefix: str, label: str
) -> list[str]:
    """Validate fields and ordered IDs for an unabridged contract translation.

    Checks structural completeness, not linguistic equivalence. Translations
    still require semantic review against the Japanese canonical documents.
    """
    clause_heading = rf"^## ({re.escape(prefix)}_\d+)\s*$"
    source_ids = re.findall(clause_heading, original, re.MULTILINE)
    published_ids = re.findall(clause_heading, english, re.MULTILINE)
    if source_ids != published_ids:
        return [f"{label}: clause IDs/order differ from Japanese canonical"]

    def sections(document: str) -> list[str]:
        return re.split(clause_heading, document, flags=re.MULTILINE)[2::2]

    failures: list[str] = []
    for cid, jp, en in zip(
        source_ids, sections(original), sections(english), strict=True
    ):
        for field in ("title", "level", "related"):
            japanese = re.findall(rf"^{field}: (.+)$", jp, re.MULTILINE)
            translated = re.findall(rf"^{field}: (.+)$", en, re.MULTILINE)
            if len(japanese) != len(translated):
                failures.append(f"{label} {cid}: {field} field count differs")
            if field == "level" and japanese != translated:
                failures.append(f"{label} {cid}: normative level changed")
            if field == "related":
                anchors = r"\]\(([^)]+)\)"
                if re.findall(anchors, " ".join(japanese)) != re.findall(
                    anchors, " ".join(translated)
                ):
                    failures.append(f"{label} {cid}: related clause links differ")
        body = re.split(r"^title: ", en, maxsplit=1, flags=re.MULTILINE)[0]
        if not body.strip():
            failures.append(f"{label} {cid}: empty translated body")
    return failures


def translated_composition_errors(original: str, english: str) -> list[str]:
    """Backward-compatible name for the Composition parity checker."""
    return translated_contract_errors(
        original, english, prefix="CMP", label="Composition"
    )


def translated_status_errors(original: str, english: str) -> list[str]:
    """Check full STATUS section coverage and item order/count.

    This is a structural guard, not a semantic translation validator.
    """
    headings = (
        ("開発段階", "Development stage"),
        (
            "現在の公開・開発構成（0.3.0）",
            "Current distribution and development structure (0.3.0)",
        ),
        ("実装済み", "Implemented"),
        ("未実装・制限", "Unimplemented features and limitations"),
        ("次の検証", "Next verification"),
    )

    def sections(document: str) -> dict[str, str]:
        split = re.split(r"(?m)^## ([^\n]+)\s*$", document)
        return {split[index]: split[index + 1] for index in range(1, len(split), 2)}

    original_sections = sections(original)
    translated_sections = sections(english)
    errors: list[str] = []
    if len(original_sections) != len(headings) or len(translated_sections) != len(
        headings
    ):
        errors.append("STATUS: top-level section count changed")
    for japanese, translated in headings:
        original_body = original_sections.get(japanese)
        english_body = translated_sections.get(translated)
        if original_body is None or english_body is None:
            errors.append(f"STATUS: missing section {japanese}/{translated}")
            continue
        original_bullets = re.findall(
            r"(?m)^\- .+(?:\n(?!\- |## )[^\n]*)*", original_body
        )
        english_bullets = re.findall(
            r"(?m)^\- .+(?:\n(?!\- |## )[^\n]*)*", english_body
        )
        if len(original_bullets) != len(english_bullets):
            errors.append(f"STATUS: bullet count differs in {translated}")
        if not english_body.strip():
            errors.append(f"STATUS: empty section {translated}")
    if "not yet a full translation" in english.lower():
        errors.append("STATUS: synopsis disclaimer remains")
    return errors


def translated_changelog_errors(original: str, english: str) -> list[str]:
    """Check entry coverage and identifiers across *all* release sections."""
    errors: list[str] = []
    version_heading = r"(?m)^## (\d+\.\d+\.\d+)"

    def versions(text: str) -> list[tuple[str, str]]:
        matches = list(re.finditer(version_heading, text))
        return [
            (
                match.group(1),
                text[match.end() : matches[index + 1].start()]
                if index + 1 < len(matches)
                else text[match.end() :],
            )
            for index, match in enumerate(matches)
        ]

    source_versions, english_versions = versions(original), versions(english)
    if not source_versions or [v for v, _ in source_versions] != [
        v for v, _ in english_versions
    ]:
        errors.append("CHANGELOG: missing or mismatched version section")

    for (version, source), (_, translated) in zip(
        source_versions, english_versions, strict=False
    ):
        for section in ("Added", "Changed", "Removed"):
            pattern = rf"(?ms)^{section}:\s*\n(.*?)(?=^\w+:\s*$|\Z)"
            jp = re.search(pattern, source)
            en = re.search(pattern, translated)
            if (jp is None) != (en is None):
                errors.append(f"CHANGELOG: {version} missing {section} section")
                continue
            if jp is None or en is None:
                continue
            source_items = re.findall(r"(?m)^\- .+$", jp.group(1))
            english_items = re.findall(r"(?m)^\- .+$", en.group(1))
            if len(source_items) != len(english_items):
                errors.append(f"CHANGELOG: {version} {section} entry count differs")
            for index, (japanese, translated_item) in enumerate(
                zip(source_items, english_items, strict=False), start=1
            ):
                pattern_ids = r"(?:CST|FRT|CMP|CVT)_\d+"
                if re.findall(pattern_ids, japanese) != re.findall(
                    pattern_ids, translated_item
                ):
                    errors.append(
                        f"CHANGELOG: {version} {section} entry {index} contract IDs differ"
                    )
    if "not yet a complete translation" in english.lower():
        errors.append("CHANGELOG: synopsis disclaimer remains")
    return errors


def check() -> int:
    if not MANIFEST.is_file():
        print("Missing published English document manifest; run record after review.")
        return 1
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures: list[str] = []
    if data.get("schema") != 1 or set(data.get("entries", {})) != set(FILES):
        failures.append("Unexpected manifest schema or entry list")
    for source, target in FILES.items():
        src, out = SOURCE / source, ROOT / target
        if not src.is_file() or not out.is_file():
            failures.append(f"Missing {source} or {target}")
            continue
        entry = data.get("entries", {}).get(source, {})
        if entry != {
            "published": target,
            "canonical_sha256": digest(src),
            "english_sha256": digest(out),
            "coverage": STATUSES[source],
        }:
            failures.append(f"Out-of-sync English document: {target}")
        content = out.read_text(encoding="utf-8")
        if len(re.findall(r"^```", content, re.MULTILINE)) % 2:
            failures.append(f"Unclosed code fence: {target}")
        if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", content):
            failures.append(f"Japanese text left in English document: {target}")
        failures.extend(internal_link_errors(out))
    for spec in ("construct", "frontend", "composition", "conversion"):
        orig = (SOURCE / "specification" / f"{spec}.md").read_text(encoding="utf-8")
        en = (ROOT / "docs" / "specification" / f"{spec}.md").read_text(
            encoding="utf-8"
        )
        rule_ids = r"^## ([A-Z]{3}_\d+)\s*$"
        if re.findall(rule_ids, orig, re.MULTILINE) != re.findall(
            rule_ids, en, re.MULTILINE
        ):
            failures.append(f"Specification contract ID mismatch: {spec}")
    for spec, prefix, label in (
        ("composition", "CMP", "Composition"),
        ("construct", "CST", "Construct Model"),
        ("frontend", "FRT", "Python Frontend"),
    ):
        original = (SOURCE / "specification" / f"{spec}.md").read_text(encoding="utf-8")
        english = (ROOT / "docs" / "specification" / f"{spec}.md").read_text(
            encoding="utf-8"
        )
        failures.extend(
            translated_contract_errors(original, english, prefix=prefix, label=label)
        )
    failures.extend(
        translated_status_errors(
            (SOURCE / "STATUS.md").read_text(encoding="utf-8"),
            (ROOT / "STATUS.md").read_text(encoding="utf-8"),
        )
    )
    failures.extend(
        translated_changelog_errors(
            (SOURCE / "CHANGELOG.md").read_text(encoding="utf-8"),
            (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
        )
    )
    orig_ref = (SOURCE / "realizer" / "construct-reference.md").read_text()
    en_ref = (ROOT / "docs" / "realizer" / "construct-reference.md").read_text()
    construct_pattern = (
        r"^\| (\w+) \| `?(?:default|false|true|integer|open domain|開いた定義域)"
    )
    if re.findall(construct_pattern, orig_ref, re.MULTILINE) != re.findall(
        construct_pattern, en_ref, re.MULTILINE
    ):
        failures.append("Construct variant table entries differ")
    if failures:
        for item in failures:
            print("ERROR:", item)
        return 1
    synopsis = [FILES[s] for s, value in STATUSES.items() if value == "synopsis"]
    print(f"Published English files in sync: {len(FILES)}")
    if synopsis:
        print("Editorial translation work remains for English synopses:")
        for name in synopsis:
            print(" -", name)
    return 0


def release_check() -> int:
    result = check()
    if result:
        return result
    pending = [
        source for source, coverage in STATUSES.items() if coverage != "translated"
    ]
    if pending:
        print(
            "Cannot approve full English publication: unabridged translation pending:"
        )
        for name in pending:
            print(" -", name)
        return 1
    print(
        "All English translations are marked complete; editorial review is still required."
    )
    return 0


def status() -> int:
    for source, target in FILES.items():
        print(f"{STATUSES[source]:10} {source:50} -> {target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("check", "record", "status", "release-check")
    )
    cmd = parser.parse_args().command
    return {
        "check": check,
        "record": record,
        "status": status,
        "release-check": release_check,
    }[cmd]()


if __name__ == "__main__":
    raise SystemExit(main())
