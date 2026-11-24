#!/usr/bin/env python3
"""Unit tests for the deterministic Post-Migration Site & Store QA Auditor (v2)."""
import tempfile
import unittest
from pathlib import Path
from audit_migrated_site import (
    audit_page_html,
    audit_shopify_products_json,
    build_synthetic_store_demo,
    classify_http_failure,
)


class PostMigrationSiteQATests(unittest.TestCase):
    def test_01_catches_staging_leak_broken_contact_and_insecure_internal_link(self):
        html = """<!doctype html>
        <html>
          <head><title>Demo Migrated Shop</title></head>
          <body>
            <a href="http://demo-store.test/about">About</a>
            <a href="https://staging.demo-store.wpengine.com/legacy-page">Old Staging</a>
            <a href="mailto:broken-email">Email Us</a>
            <a href="tel:123">Call</a>
            <a href="#">Contact Us</a>
            <form action="http://demo-store.test/contact" method="post"></form>
            <img src="/hero.jpg" alt="">
          </body>
        </html>"""
        findings, int_lks, ext_lks = audit_page_html("https://demo-store.test/", html, "demo-store.test")
        cats = {f["category"] for f in findings}
        self.assertIn("MISSING_META_DESC", cats)
        self.assertIn("STAGING_OR_DEV_URL_LEAK", cats)
        self.assertIn("MALFORMED_MAILTO", cats)
        self.assertIn("MALFORMED_TEL", cats)
        self.assertIn("DEAD_PLACEHOLDER_CTA", cats)
        self.assertIn("INSECURE_INTERNAL_HTTP", cats)
        self.assertIn("INSECURE_FORM_ACTION", cats)
        self.assertIn("IMAGES_MISSING_ALT", cats)
        self.assertIn("http://demo-store.test/about", int_lks)
        self.assertIn("https://staging.demo-store.wpengine.com/legacy-page", ext_lks)

    def test_02_shopify_products_json_catches_duplicate_sku_zero_price_inverted_sale_and_no_image(self):
        products = [
            {
                "title": "Travel Mug",
                "handle": "travel-mug",
                "images": [{"src": "https://cdn.example.test/mug.jpg"}],
                "variants": [
                    {"title": "Black", "sku": "MUG-01", "price": "24.00", "compare_at_price": "19.00"},
                    {"title": "White", "sku": "MUG-01", "price": "0.00", "compare_at_price": None},
                ],
            },
            {
                "title": "Mystery Filter",
                "handle": "mystery-filter",
                "images": [],
                "variants": [
                    {"title": "Default", "sku": "", "price": "12.50", "compare_at_price": "15.00"},
                ],
            },
        ]
        findings = audit_shopify_products_json(products, "https://demo-store.test/products.json")
        cats = {f["category"] for f in findings}
        self.assertIn("INVERTED_COMPARE_AT_PRICE", cats)
        self.assertIn("INVALID_OR_ZERO_PRICE", cats)
        self.assertIn("DUPLICATE_SKU", cats)
        self.assertIn("PRODUCT_MISSING_IMAGE", cats)
        self.assertIn("VARIANT_MISSING_SKU", cats)

    def test_03_jsonld_product_invalid_price_and_clean_page_zero_high_findings(self):
        bad_html = """<html><head><title>Prod</title><meta name="description" content="ok">
        <script type="application/ld+json">
        {"@type": "Product", "name": "Mug", "offers": {"@type": "Offer", "price": "0.00", "priceCurrency": ""}}
        </script></head><body><a href="mailto:sales@demo-store.test">Sales</a></body></html>"""
        findings, _, _ = audit_page_html("https://demo-store.test/p/mug", bad_html, "demo-store.test")
        self.assertTrue(any(f["category"] == "JSONLD_INVALID_OFFER_PRICE" for f in findings))

        clean_html = """<html><head><title>Clean Store</title><meta name="description" content="Good page">
        <script type="application/ld+json">
        {"@type": "Product", "name": "Mug", "offers": {"@type": "Offer", "price": "24.99", "priceCurrency": "USD"}}
        </script></head><body>
        <a href="https://demo-store.test/shop">Shop</a>
        <a href="mailto:hello@demo-store.test">Email</a>
        <a href="tel:+18005551234">Call</a>
        <img src="/ok.jpg" alt="Mug photo">
        </body></html>"""
        clean_f, _, _ = audit_page_html("https://demo-store.test/", clean_html, "demo-store.test")
        self.assertEqual(clean_f, [])

    def test_04_rate_limit_429_and_403_never_falsely_labeled_broken_link(self):
        self.assertEqual(classify_http_failure(429, "HTTP 429"), ("INFO", "RATE_LIMITED_UNKNOWN"))
        self.assertEqual(classify_http_failure(403, "HTTP 403"), ("INFO", "ACCESS_RESTRICTED_UNKNOWN"))
        self.assertEqual(classify_http_failure(404, "HTTP 404"), ("HIGH", "BROKEN_INTERNAL_LINK"))

    def test_05_preserves_query_param_region_without_html_reg_entity_corruption_and_skips_oauth(self):
        html = """<html><head><title>Shop</title><meta name="description" content="ok"></head><body>
        <a href="https://demo-store.test/shop?locale=en&region_country=US">Region</a>
        <a href="https://demo-store.test/customer_authentication/redirect?locale=en">Login</a>
        </body></html>"""
        _, int_lks, _ = audit_page_html("https://demo-store.test/", html, "demo-store.test")
        self.assertIn("https://demo-store.test/shop?locale=en&region_country=US", int_lks)
        self.assertFalse(any("customer_authentication" in u for u in int_lks))

    def test_06_synthetic_demo_generates_complete_reproducible_report(self):
        with tempfile.TemporaryDirectory() as td:
            rep = build_synthetic_store_demo(Path(td))
            self.assertGreaterEqual(rep["total_findings"], 12)
            self.assertGreaterEqual(rep["severity_counts"].get("HIGH", 0), 6)
            self.assertTrue((Path(td) / "synthetic_store_migration_qa_report.md").exists())
            self.assertTrue((Path(td) / "synthetic_store_migration_qa_findings.csv").exists())


if __name__ == "__main__":
    unittest.main()
