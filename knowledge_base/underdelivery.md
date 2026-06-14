# Campaign Underdelivery Troubleshooting Guide

## Overview

Campaign underdelivery occurs when an advertiser's campaign fails to serve its intended impression volume within the specified flight dates. This directly impacts advertiser satisfaction, revenue realization, and can trigger makegood obligations. Systematic diagnosis requires examining delivery constraints, competitive dynamics, and technical configurations.

## Symptoms

- Campaign delivering below pacing targets (e.g., 60% of expected daily volume)
- Daily impression delivery fluctuating significantly day-over-day
- Campaign projected to miss flight end delivery guarantee
- Specific targeting segments showing zero or minimal delivery
- Delivery spikes on some days but gaps on others
- Campaign status shows "limited" or "constrained" in ad server UI

## Possible Causes

### 1. Budget Pacing Issues

- **Daily budget caps too restrictive**: Daily limit set below required daily impressions
- **Lifetime budget miscalculation**: Total budget insufficient for targeting scope
- **Pacing algorithm over-conservative**: Front-loading protection preventing full daily delivery
- **Shared budget contention**: Multiple campaigns drawing from same budget pool
- **Currency mismatch**: Budget entered in wrong currency denomination

### 2. Frequency Cap Constraints

- **Overly aggressive frequency caps**: Limiting impressions per user too strictly
- **Narrow audience pool**: Frequency caps exhausting unique users quickly
- **Cross-platform caps**: Global caps across devices reducing available inventory
- **Lookback window too short**: Insufficient historical data for frequency management

### 3. Targeting Too Narrow

- **Layered targeting overlap**: Multiple targeting criteria reducing addressable audience
- **Geographic restrictions**: DMA or ZIP-level targeting limiting scale
- **Demographic filters**: Age, gender, income combinations creating micro-audiences
- **Interest/behavioral segments**: Third-party data segments with low match rates
- **Dayparting restrictions**: Limited delivery windows reducing daily opportunity

### 4. Bid Competition

- **CPM bid below market rate**: Losing auctions to higher bidders
- **Bid shading impact**: Algorithm reducing bids to optimize efficiency
- **Competitor campaigns**: New entrants bidding on same inventory
- **Seasonal CPM inflation**: Holiday or event-driven demand spikes
- **Private marketplace competition**: Deal-specific auctions excluding open exchange bids

### 5. Creative Approval Delays

- **Pending ad review**: Creatives stuck in moderation queue
- **Policy violations**: Rejected creatives awaiting revision and resubmission
- **Landing page review**: Destination URL verification delays
- **Rich media certification**: Interactive creative approval requirements

### 6. Flight Date and Scheduling Issues

- **Incorrect flight dates**: Campaign start/end dates misconfigured
- **Timezone mismatches**: Flight dates interpreted in wrong timezone
- **Activation delays**: Campaign approved but not yet activated
- **Flight extension needed**: Original dates insufficient for delivery goals

### 7. Dayparting and Device Restrictions

- **Limited delivery hours**: Dayparting restricting to off-peak hours only
- **Device exclusions**: Mobile or desktop inventory excluded
- **OS/browser restrictions**: Narrow technology targeting reducing scale
- **App vs web limitations**: Restricted to specific inventory types

## Diagnostic Queries

### Campaign Delivery Summary

```sql
-- Campaign delivery performance vs. goal
SELECT
    c.campaign_id,
    c.campaign_name,
    c.budget,
    c.daily_budget,
    c.start_date,
    c.end_date,
    COALESCE(SUM(r.impressions), 0) as delivered_impressions,
    c.impression_goal,
    ROUND(COALESCE(SUM(r.impressions), 0) * 100.0 / NULLIF(c.impression_goal, 0), 2) as delivery_pct,
    DATEDIFF(c.end_date, CURRENT_DATE) as days_remaining,
    ROUND((c.impression_goal - COALESCE(SUM(r.impressions), 0)) / NULLIF(DATEDIFF(c.end_date, CURRENT_DATE), 0), 0) as required_daily_avg
FROM campaigns c
LEFT JOIN campaign_impressions r ON c.campaign_id = r.campaign_id
    AND r.impression_date BETWEEN c.start_date AND CURRENT_DATE
WHERE c.campaign_id = '{{campaign_id}}'
GROUP BY c.campaign_id, c.campaign_name, c.budget, c.daily_budget,
    c.start_date, c.end_date, c.impression_goal;
```

### Daily Pacing Analysis

```sql
-- Daily delivery vs. pacing target
SELECT
    impression_date,
    impressions_served,
    pacing_target,
    impressions_served - pacing_target as variance,
    ROUND(impressions_served * 100.0 / NULLIF(pacing_target, 0), 2) as pacing_pct
FROM campaign_daily_pacing
WHERE campaign_id = '{{campaign_id}}'
    AND impression_date >= DATE_SUB(CURRENT_DATE, INTERVAL 14 DAY)
ORDER BY impression_date;
```

### Targeting Constraint Analysis

```sql
-- Impression delivery by targeting dimension
SELECT
    targeting_type,
    targeting_value,
    impressions,
    ROUND(impressions * 100.0 / SUM(impressions) OVER(), 2) as pct_of_total
FROM campaign_targeting_delivery
WHERE campaign_id = '{{campaign_id}}'
    AND impression_date >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)
ORDER BY impressions DESC;
```

### Bid Landscape Review

```sql
-- Win rate and CPM analysis by targeting segment
SELECT
    targeting_segment,
    COUNT(*) as bid_count,
    SUM(CASE WHEN won THEN 1 ELSE 0 END) as wins,
    ROUND(SUM(CASE WHEN won THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as win_rate,
    ROUND(AVG(CASE WHEN won THEN bid_price END), 2) as avg_winning_cpm,
    ROUND(AVG(bid_price), 2) as avg_bid_cpm
FROM bid_events
WHERE campaign_id = '{{campaign_id}}'
    AND event_date >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)
GROUP BY targeting_segment
ORDER BY win_rate ASC;
```

### Frequency Cap Utilization

```sql
-- Frequency distribution of reached users
SELECT
    impression_frequency,
    COUNT(DISTINCT user_id) as user_count,
    SUM(impressions) as total_impressions
FROM user_impression_frequency
WHERE campaign_id = '{{campaign_id}}'
    AND impression_date >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)
GROUP BY impression_frequency
ORDER BY impression_frequency;
```

## Recommended Actions

### Immediate Fixes (0-4 hours)

1. **Verify campaign status**: Ensure campaign is "active" and not "paused" or "completed"
2. **Check budget utilization**: Confirm budget hasn't been exhausted
3. **Review targeting exclusions**: Remove overly restrictive targeting layers
4. **Increase bids by 15-20%**: Test if bid competition is the bottleneck
5. **Expand dayparting windows**: Add peak hours to delivery schedule

### Short-Term Optimizations (4-48 hours)

1. **Adjust frequency caps**: Increase caps from 3/day to 5-7/day if audience is small
2. **Broaden geographic targeting**: Expand from city-level to state or national
3. **Add supplemental inventory sources**: Activate additional SSPs or direct deals
4. **Request creative re-approval**: Fast-track policy-compliant creative revisions
5. **Reallocate budget from over-pacing campaigns**: Shift budget to underdelivering campaigns

### Long-Term Strategy

1. **Implement automated pacing alerts**: Notify when delivery deviates > 15% from target
2. **Build forecasting models**: Pre-validate campaign viability before launch
3. **Create targeting constraint reports**: Show advertisers estimated reach before activation
4. **Develop bid optimization algorithms**: Real-time bid adjustments based on delivery pace
5. **Establish client communication protocols**: Proactive updates when delivery is at risk

## Escalation Paths

| Severity | Trigger | Escalation Level | Response Time |
|----------|---------|-----------------|---------------|
| P0 - Critical | Campaign < 30% delivered with < 20% flight time remaining | VP Account Management | 30 minutes |
| P1 - High | Campaign delivery < 50% of daily target for 3+ consecutive days | Campaign Manager Lead | 2 hours |
| P2 - Medium | Campaign delivery 50-80% of daily target | Campaign Manager | 8 hours |
| P3 - Low | Campaign delivery 80-95% of daily target | Ad Operations Analyst | Next business day |

### Escalation Contacts

- **Creative Issues**: Contact creative operations team with ad ID and rejection reason
- **Bid Competition**: Engage yield management team for bid optimization review
- **Technical Failures**: Escalate to ad server engineering with campaign ID and error logs
- **Client Communication**: Account management team handles direct advertiser outreach

## Prevention Checklist

- [ ] Pre-launch delivery feasibility assessment for all campaigns
- [ ] Automated pacing reports generated every 4 hours
- [ ] Weekly delivery review meetings with account teams
- [ ] Bid landscape analysis before campaign activation
- [ ] Creative approval submitted minimum 72 hours before flight start
- [ ] Budget allocation reviewed against historical delivery patterns
- [ ] Targeting constraint impact analysis before layering multiple criteria
- [ ] Automated alerts for campaigns projected to miss delivery guarantees
