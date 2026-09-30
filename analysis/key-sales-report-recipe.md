# Key multi-variation sales report recipe

Run on demand. Capture the report date, source timestamps, marketplace
`EBAY_GB`, and timezone `Europe/London`. If run on 30 September 2026, use
31 August–29 September and 1–30 August as the two complete 30-day windows;
use 2 July–29 September for 90-day context. Recalculate these dates on later
runs. Do not substitute a Seller Hub rolling 30-day figure whose exact bounds
are unknown for either window.

## 1. Listing census and identity

Enumerate all active key multi-variation parent ItemIDs in Seller Hub or
Trading, and ended/relisted key masters in the 90-day window. Join Listing
Studio SKUs and exact key selectors to the ItemID valid at the time. Record
status, listing start/end dates, title, lead photo, price, postage, available
quantity, variation count, and capture time. A missing Listing Studio SKU or
an ended parent is **unknown** until checked, not zero stock or zero demand.
Never derive dated sales by differencing Listing Studio's deduplicated
reconciliation snapshots.

## 2. Parent-listing funnel

Call `seller_get_traffic_report` with `dimension=LISTING` and all relevant
ItemIDs for each window. Retain eBay's metric names and `applicable` flags:

| Metric | Meaning |
| --- | --- |
| `LISTING_IMPRESSION_SEARCH_RESULTS_PAGE` | Search-result appearances, including positions buyers may not see |
| `LISTING_VIEWS_SOURCE_SEARCH_RESULTS_PAGE` | Listing-page views reached from search results |
| `LISTING_VIEWS_TOTAL` | All listing-page views |
| `TRANSACTION` | eBay's traffic-report transaction count |
| `CLICK_THROUGH_RATE` | eBay-reported search click-through rate |
| `SALES_CONVERSION_RATE` | eBay-reported sales conversion rate |
| `TOTAL_IMPRESSION_TOTAL` | All-page impression metric closest to Seller Hub's total |

Keep rate units as eBay returns them and check against Seller Hub before
formatting percentages. Compare absolute counts and rates at the same grain;
report unavailable metrics as **unknown**. A parent listing gives no evidence
of which variation an unsold visitor wanted. Mark one low stage at a time as
a hypothesis: impressions (discoverability), search views per search
impression (offer/title/photo/placement), and transactions per listing view
(price/postage/trust/selector/stock). Do not call a stage causal solely from
one period's rate.

## 3. Promotion and orders

Call `seller_get_promotion_performance` first with `stage=inventory`. Keep
campaign coverage, current ad bid/rate, dates, and discount membership
separate. For each paid funding model, request a listing-performance ad report
with `stage=start_ad_report`, then fetch its task when ready with
`stage=fetch_ad_report`. Retain ad impressions, clicks, attributed sales,
fees, reporting period, and update time separately from organic/total traffic.
Recent ad attribution is provisional. If inventory or discount scan is
truncated or denied, mark coverage **unknown**; an empty partial scan is not
proof there is no promotion. A paid ad rate is a seller fee, not a buyer
markdown.

Call `seller_get_key_order_lines` for both windows and the 90-day context,
including ended/relisted ItemIDs. This tool projects only dates, ItemID,
variation SKU/selectors, units, realised item price, cancellation/refund state.
Before interpreting variation demand, reconcile its order-line units and
cancellations with `TRANSACTION`; the metrics can differ by definition and
timing. Join current and historical availability to distinguish absent demand
from a key that was unavailable.

## 4. Matched competitors

Use `research_snapshot_key_cohort` for each series with a bounded list of
exact key codes, maker, and the seller's ItemIDs to exclude. Review the
candidate physical key form and selector before calling it an exact match.
Compare live asking price plus postage, listing age, and parent cumulative
sold signal within exact-code, same-series, cut-to-code, and broad multi-series
cohorts separately. Use authenticated Product Research for realised 90-day and
12-month demand where available. Deduplicate by parent ItemID and retain each
query, date, result cap, and exclusion. Repeating a Browse snapshot and
calling `research_compare_key_cohort_snapshots` gives a change in live
cumulative sold counter, labelled **proxy**; relisted or absent parents need
manual identity review. Never assign a broad parent's historical hundreds of
sales to a single key code or recent window.

## Output and acceptance

Produce one parent-listing funnel table for both 30-day windows plus 90-day
context, one variation order/availability table, and one matched competitor
table. Record the promotion type and actual rates. For each series, state the
best-supported finding, alternative explanations still open, and a testable
next decision. Include explicit source coverage, capture dates, relist joins,
and **unknown** fields. Compare a small sample of traffic, promotion, and
orders results with Seller Hub before treating a live MCP result as accepted.
No listing or campaign mutation is part of this recipe.
