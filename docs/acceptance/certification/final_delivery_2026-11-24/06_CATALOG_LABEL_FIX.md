# Catalog UI label fix — 2026-11-22

## Change
- Dropdown: `All Analyzer products (181)` (was All products)
- KPI: `Other governed inventory` / `Eligible · Human-approved`
- Hint under dropdown: product families = 181 Analyzer subset, not 911
- Family counts cached from Analyzer-matchable load (Windows 153 … JSON 0)
- API totals: `by_analyzer_source_family` sums to 181

## Verification
- pytest `tests/test_unified_catalog.py`: 4 passed
- `node scripts/check-catalog-ui-labels.mjs`: OK
- Browser Portal :3001: screenshot `evidence/knowledge-catalog-analyzer-product-labels.png`
- No commit/push
