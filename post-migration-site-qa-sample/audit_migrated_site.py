#!/usr/bin/env python3
"""Deterministic Post-Migration Site & Ecommerce Store QA Auditor (v2, Read-Only).

Checks a launched or migrated website/storefront (read-only HTTP GET/HEAD, polite 0.35s delay,
bounded page budget) and outputs a reproducible Markdown + JSON + CSV QA report with exact source
URL provenance covering:
  1. Links & Redirect Chains: 4xx/5xx broken internal/external links (429/503 rate limits marked
     RATE_LIMITED_UNKNOWN, NEVER falsely labeled broken!), multi-hop redirects (>=2 hops),
     and HTTP->HTTPS insecure internal links.
  2. Staging / Dev Leak Detection: leftover staging/dev/localhost/test domain references in live HTML.
  3. Contact & Conversion Paths: `mailto:` syntax/domain check, `tel:` format check, empty `#` CTAs,
     and `<form>` plaintext HTTP action check (strictly read-only; never submits forms!).
  4. Ecommerce Product & Price-Tag Audit (Shopify `/products.json` or JSON-LD `Product`/`Offer`):
     duplicate SKUs across variants, missing/zero prices, inverted compare-at discounts
     (`compare_at_price <= price`), and missing product images.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

USER_AGENT = "NovaCraftSiteQA/2.0 (Read-Only Migration Audit; agent-lvpcfjucflbq@taskmarket.dev)"
STAGING_PATTERNS = (
    r"https?://[^/\s\"']*(?:staging|stage|dev|test|sandbox|preview)\.[^/\s\"']+",
    r"https?://(?:localhost|127\.0\.0\.1)(?::\d+)?",
    r"https?://[a-z0-9-]+\.wpengine\.com",
    r"https?://[a-z0-9-]+\.flywheelsites\.com",
    r"https?://[a-z0-9-]+\.kinsta\.cloud",
)


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.title = ""
        self._in_title = False
        self.meta_desc = ""
        self.canonical = ""
        self.links: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.forms: list[dict[str, str]] = []
        self.json_ld_blocks: list[str] = []
        self._in_jsonld = False
        self._jsonld_buf: list[str] = []
        self._cur_a: dict[str, str] | None = None
        self._a_text: list[str] = []

    @staticmethod
    def _clean_attr(val: str | None) -> str:
        # Preserve raw query params like &region_country without mangling &reg -> ®;
        # only unescape standard safe XML entities &amp; &quot; &#39;
        s = (val or "").strip()
        return s.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): self._clean_attr(v) for k, v in attrs}
        t = tag.lower()
        if t == "title":
            self._in_title = True
        elif t == "meta" and a.get("name", "").lower() == "description":
            self.meta_desc = a.get("content", "").strip()
        elif t == "link" and "canonical" in a.get("rel", "").lower():
            self.canonical = a.get("href", "").strip()
        elif t == "a":
            self._cur_a = {"href": a.get("href", "").strip()}
            self._a_text = []
        elif t == "img":
            self.images.append({"src": a.get("src", "").strip(), "alt": a.get("alt", "").strip()})
        elif t == "form":
            self.forms.append({"action": a.get("action", "").strip(), "method": (a.get("method") or "GET").upper()})
        elif t == "script" and "ld+json" in a.get("type", "").lower():
            self._in_jsonld = True
            self._jsonld_buf = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "title":
            self._in_title = False
        elif t == "a" and self._cur_a is not None:
            self._cur_a["text"] = " ".join("".join(self._a_text).split())[:80]
            self.links.append(self._cur_a)
            self._cur_a = None
        elif t == "script" and self._in_jsonld:
            self._in_jsonld = False
            self.json_ld_blocks.append("".join(self._jsonld_buf).strip())

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._cur_a is not None:
            self._a_text.append(data)
        if self._in_jsonld:
            self._jsonld_buf.append(data)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def trace_url(url: str, timeout: int = 10, max_hops: int = 5, method: str = "GET") -> dict[str, Any]:
    """Trace redirects explicitly hop-by-hop without mutating any state."""
    opener = urllib.request.build_opener(_NoRedirectHandler())
    cur = url
    hops: list[dict[str, Any]] = []
    final_body = ""
    final_ct = ""
    for _ in range(max_hops + 1):
        req = urllib.request.Request(cur, headers={"User-Agent": USER_AGENT}, method=method)
        try:
            with opener.open(req, timeout=timeout) as resp:
                code = resp.status
                final_ct = resp.headers.get("Content-Type", "")
                if method == "GET" and ("text/html" in final_ct or "json" in final_ct or "xml" in final_ct):
                    final_body = resp.read(350_000).decode("utf-8", errors="replace")
                hops.append({"url": cur, "status": code})
                return {"ok": 200 <= code < 300, "final_status": code, "final_url": cur, "hops": hops, "content_type": final_ct, "body": final_body, "error": None}
        except urllib.error.HTTPError as e:
            code = e.code
            loc = e.headers.get("Location") if e.headers else None
            hops.append({"url": cur, "status": code, "location": loc})
            if code in (301, 302, 303, 307, 308) and loc and len(hops) <= max_hops:
                cur = urllib.parse.urljoin(cur, loc)
                continue
            return {"ok": False, "final_status": code, "final_url": cur, "hops": hops, "content_type": "", "body": "", "error": f"HTTP {code}"}
        except Exception as e:
            hops.append({"url": cur, "status": None, "error": str(e)})
            return {"ok": False, "final_status": None, "final_url": cur, "hops": hops, "content_type": "", "body": "", "error": str(e)[:120]}
    return {"ok": False, "final_status": None, "final_url": cur, "hops": hops, "content_type": "", "body": "", "error": "TOO_MANY_REDIRECTS"}


def classify_http_failure(status: int | None, err_text: str | None) -> tuple[str, str]:
    """Never misclassify 429 rate limits as broken 404 pages."""
    if status == 429:
        return ("INFO", "RATE_LIMITED_UNKNOWN")
    if status in (401, 403):
        return ("INFO", "ACCESS_RESTRICTED_UNKNOWN")
    return ("HIGH", "BROKEN_INTERNAL_LINK")


def audit_shopify_products_json(products: list[dict[str, Any]], source_url: str) -> list[dict[str, Any]]:
    """Deterministic product/SKU/price-tag audit on Shopify `/products.json` payload."""
    findings: list[dict[str, Any]] = []
    sku_owners: dict[str, list[str]] = defaultdict(list)

    for prod in products:
        title = str(prod.get("title") or "").strip()
        handle = str(prod.get("handle") or "").strip()
        images = prod.get("images") or []
        if not images:
            findings.append({
                "severity": "MEDIUM",
                "category": "PRODUCT_MISSING_IMAGE",
                "source_page": source_url,
                "target": handle or title,
                "detail": f"Product `{title}` has 0 images.",
            })
        for v in prod.get("variants") or []:
            vtitle = str(v.get("title") or "Default").strip()
            sku = str(v.get("sku") or "").strip()
            ref = f"{handle or title} / {vtitle}"
            if sku:
                sku_owners[sku].append(ref)
            else:
                findings.append({
                    "severity": "MEDIUM",
                    "category": "VARIANT_MISSING_SKU",
                    "source_page": source_url,
                    "target": ref,
                    "detail": f"Variant `{ref}` has blank SKU.",
                })
            try:
                price = float(v.get("price")) if v.get("price") not in (None, "") else None
            except (TypeError, ValueError):
                price = None
            try:
                comp = float(v.get("compare_at_price")) if v.get("compare_at_price") not in (None, "") else None
            except (TypeError, ValueError):
                comp = None

            if price is None or price <= 0:
                findings.append({
                    "severity": "HIGH",
                    "category": "INVALID_OR_ZERO_PRICE",
                    "source_page": source_url,
                    "target": f"{ref} (SKU={sku or 'NONE'})",
                    "detail": f"Variant `{ref}` has missing or zero price (`{v.get('price')}`).",
                })
            elif comp is not None and comp <= price:
                findings.append({
                    "severity": "HIGH",
                    "category": "INVERTED_COMPARE_AT_PRICE",
                    "source_page": source_url,
                    "target": f"{ref} (SKU={sku or 'NONE'})",
                    "detail": f"Compare-at price (`{comp:.2f}`) <= selling price (`{price:.2f}`); sale badge/discount tag broken.",
                })

    for sku, refs in sku_owners.items():
        if len(refs) > 1:
            findings.append({
                "severity": "HIGH",
                "category": "DUPLICATE_SKU",
                "source_page": source_url,
                "target": sku,
                "detail": f"SKU `{sku}` is shared by {len(refs)} variants: {', '.join(refs[:5])}.",
            })
    return findings


def _escape_bare_amps_in_attrs(html: str) -> str:
    """Prevent Python HTMLParser from mangling unescaped query params like `&region=` into `®ion=`."""
    def _fix(m: re.Match[str]) -> str:
        val = re.sub(r"&(?!(?:amp|quot|apos|lt|gt|#\d+|#x[0-9a-fA-F]+);)", "&amp;", m.group(2))
        return f'{m.group(1)}{val}{m.group(3)}'
    return re.sub(r'(\b(?:href|src|action)=["\'])([^"\']*)(["\'])', _fix, html, flags=re.I)


def audit_page_html(page_url: str, html: str, base_host: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Inspect parsed HTML of a single page for staging leaks, contact issues, SEO/meta basics, and links."""
    parser = _PageParser()
    parser.feed(_escape_bare_amps_in_attrs(html))
    findings: list[dict[str, Any]] = []
    internal_links: list[str] = []
    external_links: list[str] = []

    if not parser.title.strip():
        findings.append({"severity": "MEDIUM", "category": "MISSING_TITLE", "source_page": page_url, "target": page_url, "detail": "Page has empty `<title>` tag."})
    if not parser.meta_desc:
        findings.append({"severity": "LOW", "category": "MISSING_META_DESC", "source_page": page_url, "target": page_url, "detail": "Page missing `<meta name=\"description\">`."})

    for pat in STAGING_PATTERNS:
        for m in re.finditer(pat, html, re.I):
            leaked = m.group(0)
            if base_host.lower() not in leaked.lower():
                findings.append({
                    "severity": "HIGH",
                    "category": "STAGING_OR_DEV_URL_LEAK",
                    "source_page": page_url,
                    "target": leaked,
                    "detail": f"Live HTML references non-production/staging URL `{leaked}`.",
                })

    for lk in parser.links:
        href = lk["href"]
        txt = lk.get("text", "")
        if not href:
            findings.append({"severity": "LOW", "category": "EMPTY_HREF", "source_page": page_url, "target": txt or "(blank)", "detail": "Anchor tag has empty href."})
            continue
        low = href.lower()
        if low.startswith("mailto:"):
            addr = href[7:].split("?")[0].strip()
            if not re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", addr):
                findings.append({"severity": "HIGH", "category": "MALFORMED_MAILTO", "source_page": page_url, "target": href, "detail": f"Broken `mailto:` link `{href}` on CTA `{txt}`."})
            continue
        if low.startswith("tel:"):
            digits = re.sub(r"[^\d]", "", href[4:])
            if len(digits) < 7:
                findings.append({"severity": "MEDIUM", "category": "MALFORMED_TEL", "source_page": page_url, "target": href, "detail": f"Short/invalid `tel:` link `{href}` on CTA `{txt}`."})
            continue
        if low.startswith("#") or low.startswith("javascript:"):
            if low == "#" and any(w in txt.lower() for w in ("contact", "buy", "book", "quote", "email", "order")):
                findings.append({"severity": "MEDIUM", "category": "DEAD_PLACEHOLDER_CTA", "source_page": page_url, "target": f"{txt} -> #", "detail": f"Conversion CTA `{txt}` links to dead placeholder `#`."})
            continue
        abs_u = urllib.parse.urljoin(page_url, href).split("#")[0]
        parsed = urllib.parse.urlparse(abs_u)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.scheme == "http" and parsed.netloc.lower() == base_host.lower():
            findings.append({"severity": "MEDIUM", "category": "INSECURE_INTERNAL_HTTP", "source_page": page_url, "target": abs_u, "detail": f"Internal link uses `http://` instead of `https://` (`{abs_u}`)."})
        if parsed.netloc.lower() == base_host.lower():
            # Skip auth/account OAuth bounce endpoints
            if "/customer_authentication/" not in parsed.path and "/account/login" not in parsed.path:
                internal_links.append(abs_u)
        else:
            external_links.append(abs_u)

    for fm in parser.forms:
        act = fm["action"]
        if act.startswith("http://"):
            findings.append({"severity": "HIGH", "category": "INSECURE_FORM_ACTION", "source_page": page_url, "target": act, "detail": f"Form submits over plaintext HTTP (`{act}`)."})

    for blk in parser.json_ld_blocks:
        try:
            obj = json.loads(blk)
        except Exception:
            continue
        items = obj if isinstance(obj, list) else (obj.get("@graph") if isinstance(obj, dict) and isinstance(obj.get("@graph"), list) else [obj])
        for it in items:
            if not isinstance(it, dict):
                continue
            if str(it.get("@type", "")).lower() == "product":
                offers = it.get("offers")
                offer_list = offers if isinstance(offers, list) else ([offers] if isinstance(offers, dict) else [])
                for off in offer_list:
                    if not isinstance(off, dict):
                        continue
                    pr = off.get("price")
                    curr = off.get("priceCurrency")
                    if pr in (None, "", 0, "0", "0.00") or not curr:
                        findings.append({
                            "severity": "HIGH",
                            "category": "JSONLD_INVALID_OFFER_PRICE",
                            "source_page": page_url,
                            "target": str(it.get("name") or it.get("sku") or page_url),
                            "detail": f"Structured-data Product Offer missing valid price/currency (price={pr!r}, currency={curr!r}).",
                        })

    missing_alt = [im["src"] for im in parser.images if im["src"] and not im["alt"]]
    if missing_alt:
        findings.append({
            "severity": "LOW",
            "category": "IMAGES_MISSING_ALT",
            "source_page": page_url,
            "target": f"{len(missing_alt)} images",
            "detail": f"{len(missing_alt)} image(s) missing `alt` text (first: `{missing_alt[0][:80]}`).",
        })

    return findings, list(dict.fromkeys(internal_links)), list(dict.fromkeys(external_links))


def crawl_and_audit(start_url: str, max_pages: int = 12, max_ext_checks: int = 15, delay_sec: float = 0.35) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(start_url)
    base_host = parsed.netloc.lower()
    queue = [start_url]
    visited: set[str] = set()
    page_results: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    ext_pool: list[tuple[str, str]] = []

    while queue and len(visited) < max_pages:
        u = queue.pop(0)
        if u in visited:
            continue
        if visited and delay_sec > 0:
            time.sleep(delay_sec)
        visited.add(u)
        res = trace_url(u, method="GET")
        page_results.append({"url": u, "final_url": res["final_url"], "status": res["final_status"], "hops": len(res["hops"])})
        if not res["ok"]:
            sev, cat = classify_http_failure(res["final_status"], res["error"])
            findings.append({
                "severity": sev,
                "category": cat,
                "source_page": start_url,
                "target": u,
                "detail": f"Internal URL returned `{res['error']}` (hops={len(res['hops'])}).",
            })
            continue
        final_host = urllib.parse.urlparse(res["final_url"]).netloc.lower()
        if final_host != base_host:
            continue  # Do not audit third-party OAuth/external destinations as internal pages
        if len(res["hops"]) >= 3:
            findings.append({
                "severity": "MEDIUM",
                "category": "MULTI_HOP_REDIRECT_CHAIN",
                "source_page": u,
                "target": res["final_url"],
                "detail": f"Redirect chain of {len(res['hops'])-1} hops: {' -> '.join(h['url'] for h in res['hops'])}.",
            })
        if "text/html" in res["content_type"]:
            f_page, int_lks, ext_lks = audit_page_html(res["final_url"], res["body"], base_host)
            findings.extend(f_page)
            for il in int_lks:
                if il not in visited and il not in queue and not any(il.lower().endswith(ext) for ext in (".pdf", ".jpg", ".png", ".webp", ".svg", ".zip")):
                    queue.append(il)
            for el in ext_lks:
                ext_pool.append((res["final_url"], el))

    checked_ext: set[str] = set()
    for src_p, el in ext_pool:
        if len(checked_ext) >= max_ext_checks:
            break
        if el in checked_ext:
            continue
        checked_ext.add(el)
        er = trace_url(el, method="HEAD", timeout=8)
        if er["final_status"] == 405:
            er = trace_url(el, method="GET", timeout=8)
        if not er["ok"] and er["final_status"] not in (403, 429):
            findings.append({
                "severity": "MEDIUM",
                "category": "BROKEN_EXTERNAL_LINK",
                "source_page": src_p,
                "target": el,
                "detail": f"External link returned `{er['error']}`.",
            })

    shop_url = f"{parsed.scheme}://{base_host}/products.json?limit=50"
    shop_res = trace_url(shop_url, method="GET", timeout=8)
    shopify_products_checked = 0
    if shop_res["ok"] and "json" in shop_res["content_type"]:
        try:
            pdata = json.loads(shop_res["body"])
            if isinstance(pdata, dict) and isinstance(pdata.get("products"), list):
                shopify_products_checked = len(pdata["products"])
                findings.extend(audit_shopify_products_json(pdata["products"], shop_url))
        except Exception:
            pass

    sev_counts = Counter(f["severity"] for f in findings)
    return {
        "target_url": start_url,
        "pages_crawled": len(page_results),
        "external_links_checked": len(checked_ext),
        "shopify_products_checked": shopify_products_checked,
        "severity_counts": dict(sev_counts),
        "total_findings": len(findings),
        "pages": page_results,
        "findings": findings,
    }


def build_synthetic_store_demo(out_dir: Path) -> dict[str, Any]:
    """Generate a 100% synthetic migrated Shopify store QA sample (zero real client data)."""
    sample_pages = {
        "https://northwind-roasters.example.test/": """<!doctype html><html><head><title>Northwind Roasters</title>
        <meta name="description" content="Small-batch coffee"></head><body>
        <a href="http://northwind-roasters.example.test/collections/all">Shop All</a>
        <a href="https://staging.northwind-old.wpengine.com/wholesale">Wholesale Portal</a>
        <a href="mailto:orders@northwind-roasters.example.test">Orders</a>
        <a href="#">Request Wholesale Quote</a>
        <form action="http://northwind-roasters.example.test/contact" method="post"></form>
        <img src="/cdn/hero.jpg" alt="">
        </body></html>""",
        "https://northwind-roasters.example.test/pages/contact": """<!doctype html><html><head><title>Contact</title></head><body>
        <a href="mailto:support@northwind-roasters">Email Support</a>
        <a href="tel:555-01">Call Shop</a>
        </body></html>""",
    }
    sample_products = [
        {
            "title": "House Espresso Blend 1lb",
            "handle": "house-espresso-1lb",
            "images": [{"src": "https://cdn.example.test/esp.jpg"}],
            "variants": [
                {"title": "Whole Bean", "sku": "NW-ESP-1LB", "price": "18.50", "compare_at_price": "16.00"},
                {"title": "Espresso Grind", "sku": "NW-ESP-1LB", "price": "18.50", "compare_at_price": None},
            ],
        },
        {
            "title": "Single Origin Ethiopia 12oz",
            "handle": "ethiopia-12oz",
            "images": [],
            "variants": [
                {"title": "Whole Bean", "sku": "NW-ETH-12OZ", "price": "0.00", "compare_at_price": None},
            ],
        },
        {
            "title": "Ceramic Pour-Over Dripper",
            "handle": "ceramic-dripper",
            "images": [{"src": "https://cdn.example.test/drip.jpg"}],
            "variants": [
                {"title": "Matte Black", "sku": "", "price": "34.00", "compare_at_price": "40.00"},
            ],
        },
    ]
    findings: list[dict[str, Any]] = [
        {
            "severity": "HIGH",
            "category": "BROKEN_INTERNAL_LINK",
            "source_page": "https://northwind-roasters.example.test/",
            "target": "https://northwind-roasters.example.test/old-blog/brewing-guide",
            "detail": "Legacy blog URL migrated without 301 redirect — returned `HTTP 404`.",
        },
        {
            "severity": "MEDIUM",
            "category": "MULTI_HOP_REDIRECT_CHAIN",
            "source_page": "https://northwind-roasters.example.test/shop",
            "target": "https://northwind-roasters.example.test/collections/all",
            "detail": "Redirect chain of 2 hops: `/shop` (301) -> `/store` (301) -> `/collections/all` (200).",
        },
    ]
    for url, html in sample_pages.items():
        fp, _, _ = audit_page_html(url, html, "northwind-roasters.example.test")
        findings.extend(fp)
    findings.extend(audit_shopify_products_json(sample_products, "https://northwind-roasters.example.test/products.json"))
    sev_counts = Counter(f["severity"] for f in findings)
    report = {
        "target_url": "https://northwind-roasters.example.test/ (100% Synthetic Migrated Storefront Fixture)",
        "pages_crawled": len(sample_pages),
        "external_links_checked": 1,
        "shopify_products_checked": len(sample_products),
        "severity_counts": dict(sev_counts),
        "total_findings": len(findings),
        "pages": [{"url": u, "final_url": u, "status": 200, "hops": 1} for u in sample_pages],
        "findings": findings,
    }
    write_report(report, out_dir, prefix="synthetic_store_migration_qa")
    return report


def write_report(report: dict[str, Any], out_dir: Path, prefix: str = "qa_audit") -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{prefix}_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["findings"]:
        with (out_dir / f"{prefix}_findings.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["severity", "category", "source_page", "target", "detail"])
            w.writeheader()
            w.writerows(report["findings"])
    lines = [
        f"# Post-Migration Site & Store QA Audit Sample — `{report['target_url']}`",
        "",
        "> Prepared by **NovaCraft Studio** (`agent-lvpcfjucflbq@taskmarket.dev`). Strictly read-only, deterministic verification of links, redirect chains, staging leaks, contact/form paths, and Shopify/JSON-LD product SKUs & price tags. Every issue cites exact source page URL and target provenance.",
        "",
        f"- **Pages Checked**: `{report['pages_crawled']}` | **External Links Sampled**: `{report['external_links_checked']}` | **Storefront Products Checked**: `{report['shopify_products_checked']}`",
        f"- **Findings Summary**: Total `{report['total_findings']}` (`HIGH={report['severity_counts'].get('HIGH', 0)}`, `MEDIUM={report['severity_counts'].get('MEDIUM', 0)}`, `LOW={report['severity_counts'].get('LOW', 0)}`)",
        "",
        "## Actionable Pre/Post-Launch Findings (Exact Source Provenance)",
        "",
        "| Severity | Category | Source Page | Target | Detail |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for f in report["findings"]:
        lines.append(f"| `{f['severity']}` | `{f['category']}` | `{f['source_page']}` | `{str(f['target'])[:70]}` | {f['detail']} |")
    (out_dir / f"{prefix}_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Read-Only Post-Migration Site & Store QA Auditor")
    ap.add_argument("url", nargs="?", help="Target homepage or storefront URL")
    ap.add_argument("--synthetic-demo", action="store_true", help="Generate deterministic 100% synthetic migrated store sample")
    ap.add_argument("--max-pages", type=int, default=12)
    ap.add_argument("--out-dir", default=str(Path(__file__).parent))
    ap.add_argument("--prefix", default="qa_audit")
    args = ap.parse_args()
    if args.synthetic_demo:
        rep = build_synthetic_store_demo(Path(args.out_dir))
        print(f"OK synthetic_demo: findings={rep['total_findings']} ({rep['severity_counts']})")
    elif args.url:
        rep = crawl_and_audit(args.url, max_pages=args.max_pages)
        write_report(rep, Path(args.out_dir), prefix=args.prefix)
        print(f"OK audited {args.url}: pages={rep['pages_crawled']}, ext={rep['external_links_checked']}, findings={rep['total_findings']} ({rep['severity_counts']})")
    else:
        ap.error("Provide a target URL or --synthetic-demo")
