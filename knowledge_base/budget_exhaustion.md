# Budget Exhaustion

## Symptoms

- Campaign pacing drops to near-zero impressions after first few hours or days of flight
- Budget utilization reaches 100% well before campaign end date
- Daily spend spikes dramatically on launch day then flatlines
- Advertiser receives "budget exhausted" alerts from DSP or ad server
- Linked line items or insertion orders stop delivering prematurely
- Share-of-voice drops to zero while campaign is still technically active
- Publisher reports show front-loaded impressions with no tail delivery
- Reallocate requests from sales team citing under-delivery on secondary campaigns
- Client dashboards show 100% budget consumed with 60%+ flight time remaining
- Automated bidding algorithms consume entire daily cap in first hour of availability
- Cross-platform campaigns show budget depletion on one channel while others remain underfunded

## Possible Causes

- Daily or lifetime budget cap set too low relative to target audience size and bid levels
- Pacing set to "ASAP" or "even" with no ramp period, causing spend acceleration beyond sustainable rate
- Shared budget across multiple line items where one high-CPM line item cannibalizes allocation
- Frequency cap misconfiguration allowing same user to serve repeatedly, exhausting budget on minimal unique reach
- Dayparting windows concentrated into narrow time slots, forcing all daily budget into compressed delivery
- Bid multipliers or floor prices set too high for auction competitiveness, inflating effective CPM
- Audience targeting too narrow for available inventory, concentrating spend on limited supply
- Budget synchronization lag between DSP and ad server causing double-counting or race conditions
- Flight dates misconfigured as start-of-day to start-of-day instead of full-day coverage
- Currency conversion rounding errors in international campaigns causing micro-overages
- Lack of pacing controls on programmatic guaranteed deals with fixed delivery commitments
- Auto-budget rules triggered by performance thresholds that inadvertently increase spend limits

## Diagnostic Queries

```sql
-- Budget consumption rate over campaign lifetime
SELECT
  campaign_id,
  date,
  impressions_served,
  spend,
  SUM(spend) OVER (PARTITION BY campaign_id ORDER BY date) AS cumulative_spend,
  lifetime_budget,
  ROUND(SUM(spend) OVER (PARTITION BY campaign_id ORDER BY date) / lifetime_budget * 100, 2) AS pct_consumed
FROM campaign_daily_stats
WHERE campaign_id = '{campaign_id}'
ORDER BY date;

-- Compare daily spend vs daily budget cap
SELECT
  line_item_id,
  date,
  daily_spend,
  daily_budget_cap,
  CASE WHEN daily_spend > daily_budget_cap * 1.1 THEN 'OVERPACE'
       WHEN daily_spend < daily_budget_cap * 0.3 THEN 'UNDERPACE'
       ELSE 'NORMAL' END AS pacing_status
FROM line_item_daily_stats
WHERE line_item_id IN (SELECT id FROM line_items WHERE campaign_id = '{campaign_id}')
ORDER BY date DESC;

-- Budget allocation across shared line items
SELECT
  li.id AS line_item_id,
  li.name,
  li.budget_allocation_pct,
  li.budget_cap,
  COALESCE(SUM(s.spend), 0) AS total_spend,
  li.budget_cap - COALESCE(SUM(s.spend), 0) AS remaining
FROM line_items li
LEFT JOIN spend_data s ON li.id = s.line_item_id
WHERE li.campaign_id = '{campaign_id}'
GROUP BY li.id, li.name, li.budget_allocation_pct, li.budget_cap
ORDER BY total_spend DESC;

-- Hourly spend distribution to identify front-loading
SELECT
  EXTRACT(HOUR FROM impression_timestamp) AS hour_of_day,
  COUNT(*) AS impressions,
  SUM(cost) AS spend,
  ROUND(SUM(cost) / SUM(SUM(cost)) OVER () * 100, 2) AS pct_of_total
FROM impression_log
WHERE campaign_id = '{campaign_id}'
  AND impression_timestamp >= '{start_date}'
GROUP BY EXTRACT(HOUR FROM impression_timestamp)
ORDER BY hour_of_day;
```

## Recommended Actions

1. **Immediate spend throttle**: Reduce bid multipliers by 30-50% to slow consumption rate while preserving delivery continuity. If campaign is already exhausted, request emergency budget increase from finance or reduce daily cap to allow gradual pacing over remaining flight days.

2. **Switch pacing to "even" with ramp**: If set to ASAP, change to even pacing. Add 3-day ramp period at 50% of target daily spend, scaling to 100% by day 4. This prevents front-loading while maintaining delivery trajectory.

3. **Implement budget guards**: Set hard budget alerts at 70%, 85%, and 95% of lifetime budget. Configure auto-pause rules at 95% to allow manual review before complete exhaustion. Use line-item-level caps as secondary safety net.

4. **Audit shared budget allocation**: If multiple line items share a budget pool, verify allocation percentages sum to 100%. Check that no single line item is consuming disproportionate share. Consider splitting into independent budgets if contention persists.

5. **Review frequency caps**: Ensure frequency cap of 3-5 impressions per user per 24-hour period. Uncapped frequency allows same users to consume budget repeatedly without incremental reach, which is the most common cause of premature exhaustion in remarketing campaigns.

6. **Expand targeting or reduce floor prices**: If audience pool is too narrow for budget, broaden targeting parameters (age, interest, contextual). Alternatively, remove or lower bid floors to access more inventory at lower CPMs, stretching budget further.

7. **Check for budget sync issues**: Verify DSP and ad server budgets are synchronized. Implement reconciliation checks between platforms. If using multiple demand sources, ensure each has independent budget caps rather than relying on a single shared pool.

8. **Adjust dayparting windows**: If budget is concentrated into narrow delivery windows, expand dayparting to full-day or near-full-day delivery. Narrow windows create artificial scarcity that accelerates spend within constrained hours.

9. **Set up automated pacing rules**: Configure ML-based pacing in DSP that adjusts bids dynamically based on remaining budget and remaining flight time. This automatically decelerates spend as budget depletes.

10. **Post-flight analysis**: Document actual CPM, reach, and frequency achieved vs. plan. Feed data into next campaign's forecasting model to improve budget allocation accuracy. Update pacing templates with lessons learned.

## Escalation Paths

- **Level 1 (AM/Trader)**: Monitor pacing dashboard hourly for first 48 hours. If spend exceeds 120% of daily target, pause line items and adjust bids. Contact campaign manager for budget reallocation approval.

- **Level 2 (Campaign Manager)**: If budget exhaustion occurs before 50% flight completion, escalate to sales for additional budget approval or revised KPI targets. Coordinate with finance for emergency budget transfer between campaigns.

- **Level 3 (AdOps Lead)**: If systemic budget sync issues are identified across multiple campaigns, escalate to engineering for platform-level fix. Review DSP integration for budget reconciliation bugs.

- **Level 4 (Account Director)**: Client-facing escalation when budget exhaustion impacts contractual delivery guarantees. Negotiate makegoods, credit memo, or extended flight dates with advertiser.
