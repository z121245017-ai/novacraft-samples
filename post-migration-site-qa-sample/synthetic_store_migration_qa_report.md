# Post-Migration Site & Store QA Audit Sample — `https://northwind-roasters.example.test/ (100% Synthetic Migrated Storefront Fixture)`

> Prepared by **NovaCraft Studio** (`agent-lvpcfjucflbq@taskmarket.dev`). Strictly read-only, deterministic verification of links, redirect chains, staging leaks, contact/form paths, and Shopify/JSON-LD product SKUs & price tags. Every issue cites exact source page URL and target provenance.

- **Pages Checked**: `2` | **External Links Sampled**: `1` | **Storefront Products Checked**: `3`
- **Findings Summary**: Total `15` (`HIGH=7`, `MEDIUM=6`, `LOW=2`)

## Actionable Pre/Post-Launch Findings (Exact Source Provenance)

| Severity | Category | Source Page | Target | Detail |
| :--- | :--- | :--- | :--- | :--- |
| `HIGH` | `BROKEN_INTERNAL_LINK` | `https://northwind-roasters.example.test/` | `https://northwind-roasters.example.test/old-blog/brewing-guide` | Legacy blog URL migrated without 301 redirect — returned `HTTP 404`. |
| `MEDIUM` | `MULTI_HOP_REDIRECT_CHAIN` | `https://northwind-roasters.example.test/shop` | `https://northwind-roasters.example.test/collections/all` | Redirect chain of 2 hops: `/shop` (301) -> `/store` (301) -> `/collections/all` (200). |
| `HIGH` | `STAGING_OR_DEV_URL_LEAK` | `https://northwind-roasters.example.test/` | `https://staging.northwind-old.wpengine.com` | Live HTML references non-production/staging URL `https://staging.northwind-old.wpengine.com`. |
| `MEDIUM` | `INSECURE_INTERNAL_HTTP` | `https://northwind-roasters.example.test/` | `http://northwind-roasters.example.test/collections/all` | Internal link uses `http://` instead of `https://` (`http://northwind-roasters.example.test/collections/all`). |
| `MEDIUM` | `DEAD_PLACEHOLDER_CTA` | `https://northwind-roasters.example.test/` | `Request Wholesale Quote -> #` | Conversion CTA `Request Wholesale Quote` links to dead placeholder `#`. |
| `HIGH` | `INSECURE_FORM_ACTION` | `https://northwind-roasters.example.test/` | `http://northwind-roasters.example.test/contact` | Form submits over plaintext HTTP (`http://northwind-roasters.example.test/contact`). |
| `LOW` | `IMAGES_MISSING_ALT` | `https://northwind-roasters.example.test/` | `1 images` | 1 image(s) missing `alt` text (first: `/cdn/hero.jpg`). |
| `LOW` | `MISSING_META_DESC` | `https://northwind-roasters.example.test/pages/contact` | `https://northwind-roasters.example.test/pages/contact` | Page missing `<meta name="description">`. |
| `HIGH` | `MALFORMED_MAILTO` | `https://northwind-roasters.example.test/pages/contact` | `mailto:support@northwind-roasters` | Broken `mailto:` link `mailto:support@northwind-roasters` on CTA `Email Support`. |
| `MEDIUM` | `MALFORMED_TEL` | `https://northwind-roasters.example.test/pages/contact` | `tel:555-01` | Short/invalid `tel:` link `tel:555-01` on CTA `Call Shop`. |
| `HIGH` | `INVERTED_COMPARE_AT_PRICE` | `https://northwind-roasters.example.test/products.json` | `house-espresso-1lb / Whole Bean (SKU=NW-ESP-1LB)` | Compare-at price (`16.00`) <= selling price (`18.50`); sale badge/discount tag broken. |
| `MEDIUM` | `PRODUCT_MISSING_IMAGE` | `https://northwind-roasters.example.test/products.json` | `ethiopia-12oz` | Product `Single Origin Ethiopia 12oz` has 0 images. |
| `HIGH` | `INVALID_OR_ZERO_PRICE` | `https://northwind-roasters.example.test/products.json` | `ethiopia-12oz / Whole Bean (SKU=NW-ETH-12OZ)` | Variant `ethiopia-12oz / Whole Bean` has missing or zero price (`0.00`). |
| `MEDIUM` | `VARIANT_MISSING_SKU` | `https://northwind-roasters.example.test/products.json` | `ceramic-dripper / Matte Black` | Variant `ceramic-dripper / Matte Black` has blank SKU. |
| `HIGH` | `DUPLICATE_SKU` | `https://northwind-roasters.example.test/products.json` | `NW-ESP-1LB` | SKU `NW-ESP-1LB` is shared by 2 variants: house-espresso-1lb / Whole Bean, house-espresso-1lb / Espresso Grind. |
