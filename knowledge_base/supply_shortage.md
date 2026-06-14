# Supply Shortage

## Symptoms

- Campaign delivery dropping below 50% of planned impressions despite adequate budget
- Bid request volume declining sharply on specific publishers or exchanges
- Win rates dropping below historical baseline by 20%+ without bid changes
- Inventory availability alerts triggering on multiple line items simultaneously
- Forecasted impressions no longer match actual delivery projections
- Private marketplace deals under-delivering due to limited inventory supply
- Seasonal demand spikes (Q4, Black Friday) causing inventory scarcity
- Publisher pulling inventory from programmatic pool to fulfill direct sales commitments
- Floor prices rising unexpectedly due to competing demand from new advertisers
- Header bidding wrappers timeout causing lost bid opportunities
- Supply-side platform throttling bid requests due to rate limiting
- Cookie deprecation reducing addressable inventory on Safari and Firefox

## Possible Causes

- Seasonal inventory contraction (summer months, holiday periods) reducing available impressions
- Publisher shifting inventory from open exchange to private deals or direct sales
- New advertiser entering market with aggressive bidding, consuming available supply
- Privacy regulations (GDPR, CCPA, cookie deprecation) reducing addressable user pool
- Header bidding timeout configurations too aggressive, reducing bid opportunity windows
- Ad blocker adoption increasing, removing impressions from measurable inventory
- SSP rate limiting or throttling based on bidder response time or quality score
- Inventory forecasting model using stale data, overestimating available supply
- Publisher ad server caps limiting programmatic fill to protect direct-sold campaigns
- Supply partner technical issues (API outages, bid stream interruptions) reducing bid volume
- Geo-specific supply shortage where target region has limited premium inventory
- Dayparting restrictions concentrating demand into narrow time windows

## Diagnostic Queries

```sql
-- Bid request volume trend analysis
SELECT
  date,
  publisher,
  exchange,
  bid_requests,
  bid_requests_last_week,
  ROUND((bid_requests - bid_requests_last_week) * 100.0 / bid_requests_last_week, 2) AS pct_change
FROM supply_metrics
WHERE campaign_id = '{campaign_id}'
  AND date BETWEEN DATE_SUB('{end_date}', INTERVAL 14 DAY) AND '{end_date}'
ORDER BY date, pct_change;

-- Win rate analysis by publisher
SELECT
  publisher,
  exchange,
  SUM(bids) AS total_bids,
  SUM(wins) AS total_wins,
  ROUND(SUM(wins) * 100.0 / NULLIF(SUM(bids), 0), 2) AS win_rate,
  ROUND(AVG(cpm_bid), 2) AS avg_bid_cpm,
  ROUND(AVG(cpm_won), 2) AS avg_won_cpm
FROM auction_logs
WHERE campaign_id = '{campaign_id}'
  AND log_date BETWEEN '{start_date}' AND '{end_date}'
GROUP BY publisher, exchange
ORDER BY total_wins DESC;

-- Inventory gap analysis
SELECT
  li.id AS line_item_id,
  li.name,
  li.planned_impressions,
  COALESCE(SUM(s.impressions_served), 0) AS impressions_served,
  li.planned_impressions - COALESCE(SUM(s.impressions_served), 0) AS impression_gap,
  li.end_date,
  DATEDIFF(day, MAX(s.serve_date), li.end_date) AS days_remaining,
  CASE
    WHEN DATEDIFF(day, MAX(s.serve_date), li.end_date) > 0
    THEN (li.planned_impressions - COALESCE(SUM(s.impressions_served), 0)) / DATEDIFF(day, MAX(s.serve_date), li.end_date)
    ELSE 0
  END AS daily_gap_rate
FROM line_items li
LEFT JOIN daily_serve_stats s ON li.id = s.line_item_id
WHERE li.campaign_id = '{campaign_id}'
GROUP BY li.id, li.name, li.planned_impressions, li.end_date;

-- Floor price competition analysis
SELECT
  publisher,
  deal_id,
  DATE(log_date) AS day,
  AVG(floor_price) AS avg_floor,
  AVG(our_bid) AS avg_our_bid,
  AVG(rival_bid) AS avg_competitor_bid,
  SUM(CASE WHEN our_bid >= floor_price THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS above_floor_pct
FROM auction_competition_log
WHERE campaign_id = '{campaign_id}'
  AND log_date BETWEEN '{start_date}' AND '{end_date}'
GROUP BY publisher, deal_id, DATE(log_date)
ORDER BY avg_floor DESC;
```

## Recommended Actions

1. **Expand supply sources**: Add new SSPs, exchanges, or publisher direct integrations to increase bid request volume. Prioritize exchanges with high-quality inventory in target geo and demo. Evaluate emerging supply sources (CTV, in-app, digital out-of-home).

2. **Optimize bid competitiveness**: If win rate dropped due to floor price increases, raise bid multipliers by 10-20% on high-performing publishers. Implement bid shading algorithms that balance win rate against CPM efficiency. Review and remove bid caps that may be too restrictive.

3. **Broaden targeting parameters**: Relax audience targeting criteria to increase addressable inventory. Expand age ranges, add interest categories, or include contextual targeting alongside audience targeting. This increases available impressions without reducing relevance significantly.

4. **Adjust pacing and dayparting**: If demand is concentrated into narrow windows, spread delivery across more hours. Shift delivery from peak hours (6-9 PM) to off-peak (10 AM-2 PM) when competition is lower and CPMs are 15-30% cheaper.

5. **Activate backup line items**: Create secondary line items with broader targeting as backup supply sources. These auto-activate when primary line items fall below delivery thresholds. Use conditional logic to shift budget to backup sources when primary delivery drops below 70% of target.

6. **Negotiate private marketplace priority**: Work with publishers to secure preferential deal terms (first-look, priority access, fixed allocation). Ensure PMP deals have minimum impression guarantees or priority tiers above open exchange.

7. **Implement supply forecasting refresh**: Update inventory forecasting models with most recent 30-day data. Account for seasonality, new competitor entry, and privacy-related inventory loss. Run forecast daily during periods of known supply volatility.

8. **Optimize header bidding setup**: Review header bidding wrapper timeout settings (default 1000ms). Reduce to 500ms for faster response. Ensure all demand partners are returning bids within timeout window. Remove underperforming demand partners that slow down auction.

9. **Diversify across supply channels**: Don't rely on single publisher or exchange for more than 30% of impressions. Maintain balanced supply mix across open exchange, PMP, programmatic guaranteed, and direct integrations. This reduces concentration risk.

10. **Pre-negotiate seasonal inventory**: For known high-demand periods (Q4, Black Friday, Super Bowl), pre-negotiate inventory commitments with publishers 60-90 days in advance. Lock in fixed CPMs and minimum impression guarantees before competition drives up prices.

## Escalation Paths

- **Level 1 (Trader)**: Monitor delivery dashboards daily. If delivery drops below 80% of target for 2+ consecutive days, expand targeting or increase bids. Activate backup line items if available.

- **Level 2 (Inventory Manager)**: If supply shortage affects multiple campaigns, escalate to publisher development team. Request priority access to reserved inventory. Negotiate emergency PMP deals with key publishers.

- **Level 3 (AdOps Lead)**: If supply shortage is systemic across platform, escalate to engineering for SSP integration optimization. Review rate limiting and timeout configurations. Coordinate with supply partners for emergency bid stream capacity increase.

- **Level 4 (VP Partnerships)**: For contractual delivery guarantees at risk, escalate to executive-level publisher relationships. Negotiate guaranteed inventory allocations or makegood commitments. Consider strategic partnerships with premium publishers for dedicated supply.
