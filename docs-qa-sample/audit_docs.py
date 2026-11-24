#!/usr/bin/env python3
"""Read-only technical documentation QA checker (links, anchors, prose hygiene, OpenAPI spec drift)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
DUP_WORD_RE = re.compile(r"\b([A-Za-z]+)\s+\1\b", re.IGNORECASE)
PARAM_RE = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_.-]*)`")


def slugify_heading(text: str) -> str:
    cleaned = re.sub(r"[`*_~]", "", text.strip().lower())
    cleaned = re.sub(r"[^\w\s-]", "", cleaned)
    return re.sub(r"\s+", "-", cleaned).strip("-")


def collect_headings(md_text: str) -> set[str]:
    return {slugify_heading(m.group(2)) for m in HEADING_RE.finditer(md_text)}


def audit_markdown_doc(
    doc_path: Path,
    *,
    docs_root: Path | None = None,
    glossary_terms: dict[str, str] | None = None,
    openapi_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text = doc_path.read_text(encoding="utf-8")
    root = docs_root or doc_path.parent
    local_anchors = collect_headings(text)
    findings: list[dict[str, Any]] = []

    # 1. Internal links and anchors
    for idx, line in enumerate(text.splitlines(), start=1):
        for m in LINK_RE.finditer(line):
            target = m.group(2).strip()
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if target.startswith("#"):
                anchor = target[1:]
                if anchor not in local_anchors:
                    findings.append({
                        "severity": "error",
                        "category": "broken_anchor",
                        "line": idx,
                        "detail": f"Missing heading anchor #{anchor}",
                    })
                continue
            path_part, _, frag = target.partition("#")
            resolved = (doc_path.parent / path_part).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                findings.append({
                    "severity": "error",
                    "category": "link_outside_docs_root",
                    "line": idx,
                    "detail": f"Relative link escapes docs root: {target}",
                })
                continue
            if not resolved.exists():
                findings.append({
                    "severity": "error",
                    "category": "broken_file_link",
                    "line": idx,
                    "detail": f"Referenced file does not exist: {path_part}",
                })
            elif frag and resolved.suffix.lower() in (".md", ".mdx"):
                target_anchors = collect_headings(resolved.read_text(encoding="utf-8"))
                if frag not in target_anchors:
                    findings.append({
                        "severity": "error",
                        "category": "broken_cross_file_anchor",
                        "line": idx,
                        "detail": f"Missing anchor #{frag} in {path_part}",
                    })

        # 2. Duplicated adjacent words
        for dm in DUP_WORD_RE.finditer(line):
            findings.append({
                "severity": "warning",
                "category": "duplicated_word",
                "line": idx,
                "detail": f"Duplicated word '{dm.group(0)}'",
            })

        # 3. Glossary casing / terminology consistency
        if glossary_terms:
            for wrong, canonical in glossary_terms.items():
                if re.search(rf"\b{re.escape(wrong)}\b", line) and wrong != canonical:
                    findings.append({
                        "severity": "warning",
                        "category": "terminology_drift",
                        "line": idx,
                        "detail": f"Use canonical term '{canonical}' instead of '{wrong}'",
                    })

    # 4. OpenAPI required parameter coverage check (optional)
    if openapi_spec:
        documented_tokens = set(PARAM_RE.findall(text))
        for path_key, methods in (openapi_spec.get("paths") or {}).items():
            if path_key not in text:
                findings.append({
                    "severity": "warning",
                    "category": "undocumented_endpoint",
                    "line": 1,
                    "detail": f"Spec path '{path_key}' not mentioned in doc",
                })
                continue
            for method, op in (methods or {}).items():
                for param in (op.get("parameters") or []):
                    pname = param.get("name")
                    if param.get("required") and pname and pname not in documented_tokens:
                        findings.append({
                            "severity": "error",
                            "category": "missing_required_param",
                            "line": 1,
                            "detail": f"Required parameter `{pname}` for {method.upper()} {path_key} missing from docs",
                        })

    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    return {
        "file": str(doc_path.name),
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
        "status": "FAIL" if errors else ("WARN" if warnings else "PASS"),
    }


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Audit Markdown documentation against links, glossary, and OpenAPI spec.")
    p.add_argument("doc", type=Path)
    p.add_argument("--spec", type=Path, default=None)
    args = p.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8")) if args.spec else None
    print(json.dumps(audit_markdown_doc(args.doc, openapi_spec=spec), indent=2))


if __name__ == "__main__":
    main()
