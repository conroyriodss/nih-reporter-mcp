# Independent Whole-Award Total

**Cohort:** "CRISPR sickle cell" FY2024
**Retrieval date:** 2026-10-15T20:31:43.117032+00:00
**Methodology:** docs/ground_truth_methodology.md (whole_award rules)

## Input

* Raw records: 38 (from `raw_records.json`)
* SHA-256 of raw_records.json: `ff178702ec35720c88b7f85900db60d6fc9380e000fbf9aaacda20617a7f789d`

## Whole-Award Rules Applied (independently of server code)

1. **Exclude subprojects**: remove any record whose `subproject_id` is non-null → 1 excluded
2. **Deduplicate by appl_id**: remove duplicates keeping first occurrence → 0 removed
3. **Exclude null amounts**: remove records with `award_amount = null` → 0 excluded
4. **Sum remaining**: 37 records contribute to the total

## Arithmetic

| appl_id | core_project_num | award_amount | running_total |
|---:|---|---:|---:|
| 10747883 | R01HL147028 | $  402,500.00 | $     402,500.00 |
| 10756130 | R21HL166178 | $  191,250.00 | $     593,750.00 |
| 10760297 | R01HL136135 | $  728,713.00 | $   1,322,463.00 |
| 10771309 | R01HL119479 | $  669,586.00 | $   1,992,049.00 |
| 10796848 | R01HL167513 | $  658,954.00 | $   2,651,003.00 |
| 10808443 | R21EB034346 | $  217,890.00 | $   2,868,893.00 |
| 10813016 | R01DK134936 | $  415,031.00 | $   3,283,924.00 |
| 10815708 | K08DK129716 | $  166,860.00 | $   3,450,784.00 |
| 10817959 | R21NS130250 | $  196,250.00 | $   3,647,034.00 |
| 10821108 | R41GM153041 | $  293,319.00 | $   3,940,353.00 |
| 10827103 | R01HL172489 | $  889,998.00 | $   4,830,351.00 |
| 10837898 | K08DK128571 | $  158,328.00 | $   4,988,679.00 |
| 10843188 | U01AI176471 | $  479,100.00 | $   5,467,779.00 |
| 10843746 | F30HL164007 | $   33,892.00 | $   5,501,671.00 |
| 10849327 | R01AR082858 | $  395,537.00 | $   5,897,208.00 |
| 10867474 | R01HL165247 | $  662,949.00 | $   6,560,157.00 |
| 10876342 | R01HL169761 | $  632,319.00 | $   7,192,476.00 |
| 10877295 | R01HL166271 | $  684,002.00 | $   7,876,478.00 |
| 10900650 | R01DK134516 | $  373,824.00 | $   8,250,302.00 |
| 10905723 | R01HG013618 | $  802,221.00 | $   9,052,523.00 |
| 10908700 | R01HL170629 | $  760,457.00 | $   9,812,980.00 |
| 10911966 | R01HL130040 | $  644,784.00 | $  10,457,764.00 |
| 10913609 | R01HL170115 | $  446,729.00 | $  10,904,493.00 |
| 10914937 | K01OD032455 | $  125,280.00 | $  11,029,773.00 |
| 10916761 | R01HL169761 | $   42,336.00 | $  11,072,109.00 |
| 10917350 | U01HL163983 | $1,159,340.00 | $  12,231,449.00 |
| 10917383 | R25GM146240 | $  270,444.00 | $  12,501,893.00 |
| 10922546 | R44GM146471 | $1,036,415.00 | $  13,538,308.00 |
| 10929941 | R01HL098032 | $  750,647.00 | $  14,288,955.00 |
| 10947873 | R21AI185498 | $  220,488.00 | $  14,509,443.00 |
| 10999595 | R01AR084841 | $  531,109.00 | $  15,040,552.00 |
| 11004909 | R43HL174204 | $  300,000.00 | $  15,340,552.00 |
| 11013163 | R01HL161361 | $  422,713.00 | $  15,763,265.00 |
| 11139766 | R01HL169761 | $   78,410.00 | $  15,841,675.00 |
| 11179930 | ZIAHG200403 | $  320,508.00 | $  16,162,183.00 |
| 11189414 | ZIAAI001150 | $2,194,965.00 | $  18,357,148.00 |
| 11189427 | ZIAAI001185 | $1,432,986.00 | $  19,790,134.00 |

## Result

**Independent hand-computed whole_award total: $19,790,134.00**

This matches:
* `decision_ledger.csv` sum(amount_counted): $19,790,134.00
* `tool_output.json` total_award_amount_usd: $19,790,134.00

All three figures agree to the dollar.

## Re-verification at v0.13.0

* **Re-run date:** 2026-10-19T23:21:16Z
* **Tag:** v0.13.0 @ `6ad354deac8710f4f4a92b2d53701baf1f796804`
* **Live API returns identical data:** 38 raw records, 0 field-level diffs vs stored `raw_records.json`
* **Dollar total:** $19,790,134.00 (exact match)
* **raw_records.json SHA-256:** `ff178702ec35720c88b7f85900db60d6fc9380e000fbf9aaacda20617a7f789d` (verified on disk)
* **Schema validation:** `tool_output.json` passes `FundingSummary.model_validate()` at v0.13.0 (16/16 fields, 0 missing)
* **Verdict:** VERIFIED AT HEAD — not frozen, not drifted.
