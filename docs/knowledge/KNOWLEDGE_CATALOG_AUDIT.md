# Knowledge Catalog Audit (2026-11-19)

## What the number 163 actually is

The catalog is **two different data sets**, not one:

| Source file | Entries | What they are |
|---|---|---|
| `operational_event_catalog.json` | **141** | Windows event context: `event_id, provider, title, category, severity, description, operator_context, related_events, keywords, source` |
| `diagnostic_knowledge_catalog.json` | **22** | Full diagnostic entries: `diagnostic_code, product, vendor, compatibility_scope, observed_signatures, relevant_log_fields, investigation_steps, limitations, official_references, support_level, verification_status` |
| **Total** | **163** | matches the UI counter |

**Only the 22 diagnostic entries carry investigation steps, limitations and
official references.** The 141 operational entries are event context, not
engineer-grade diagnostic knowledge. Presenting them as one "catalog" number
overstates the product.

## Distribution

| Product / family | Entries | Share |
|---|---|---|
| Microsoft Windows (operational event context) | 141 | 86.5% |
| Cisco | 6 | 3.7% |
| Fortinet | 5 | 3.1% |
| Veeam | 4 | 2.5% |
| Palo Alto Networks | 4 | 2.5% |
| VMware / Broadcom | 2 | 1.2% |
| OpenSSH | 1 | 0.6% |

Windows accounts for 86.5% of the displayed total. Linux/OpenSSH has 1
diagnostic entry; several vendors have none.

## Field coverage

| Field | Operational (141) | Diagnostic (22) |
|---|---|---|
| title / description | yes | yes |
| category, severity | yes | yes |
| event id / diagnostic code | yes (`event_id`) | yes (`diagnostic_code`) |
| operator context / meaning | yes (`operator_context`) | yes (`description`) |
| investigation steps | **no** | **yes** |
| limitations / false positives | **no** | **yes** |
| official references | **no** (only a `source` label) | **yes (20 of 22 contain a URL)** |
| remediation guidance | **no** | **no** (not modelled) |
| verification criteria | **no** | **no** (not modelled) |
| version / compatibility scope | **no** | **yes** (`compatibility_scope`) |

## Findings

1. **Quality tiers are mixed in one counter.** Fix the UI: show
   "Validated diagnostic entries: 22" and
   "Operational event context: 141" separately.
2. **No remediation or verification field exists anywhere.** The domain model
   supports investigation and limitations only. Adding remediation/verification
   is a schema change, not a data-entry task — it must be designed once and
   applied to both tiers.
3. **Two duplicate titles** were detected inside the diagnostic set; they need a
   manual merge decision (IDs preserved). No duplicate IDs exist.
4. **Parser-only row in the UI is correct as a taxonomy note** ("Structured JSON
   (parser only): 0") — it is not, and should not be, a knowledge entry.
5. `event_knowledge.json` is a third knowledge source with a different shape and
   was **not** counted here; it must not be silently added to the same total.

## What was not done in this round

- No entry-by-entry verification of all 141 operational records
  against vendor documentation.
- No new entries were added: adding them without per-entry source verification
  would violate the quality standard below.
