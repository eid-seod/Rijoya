# Rijoya visual QA

## Verified routes

The following routes were captured against the live preview at desktop width: `/`, `/catalog`, `/cart`, `/vendor/register`, `/vendor/dashboard`, and `/admin`.

## Findings

The warm editorial design system renders consistently across the public storefront and the two operations dashboards. Navigation, typography, filters, empty cart state, vendor application form, maker workspace, and admin KPI panels are visible and responsive at the captured desktop viewport. The catalog correctly falls back to six curated MVP products when the managed database is provisioned but has no product rows yet.

The initial hero image URL returned an alt-text-only state in the screenshot and was replaced with a known-working Unsplash asset reference before final verification.
