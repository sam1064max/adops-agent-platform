# CTR Decline Troubleshooting Guide

## Overview

Click-through rate (CTR) measures the percentage of served impressions that result in a user click. CTR declines reduce campaign effectiveness, increase effective CPA, and can trigger advertiser dissatisfaction. Diagnosing CTR drops requires analyzing creative performance, audience quality, placement health, and external market factors.

## Symptoms

- CTR drops below historical baseline (e.g., from 0.35% to 0.15%)
- Click volume declines while impressions remain stable or increase
- Specific ad units or placements showing disproportionate CTR decline
- CTR varies significantly by device, browser, or geography
- Advertiser reporting shows CTR divergence from platform metrics
- Post-click metrics (bounce rate, time on site) also declining

## Possible Causes

### 1. Creative Fatigue

- **Audience saturation**: Same users seeing same creative repeatedly
- **Creative staleness**: Ad unchanged for extended period (> 2-3 weeks)
- **Diminishing novelty**: Initial engagement spike wearing off
- **Frequency-induced annoyance**: Users actively avoiding familiar ads

### 2. Ad Blindness

- **Banner blindness**: Users subconsciously ignoring display ad placements
- **Position degradation**: Ads moved to less visible page locations
- **Layout changes**: Publisher site redesign pushing ads below fold
- **Ad density increase**: Too many ads competing for user attention

### 3. Audience Mismatch

- **Targeting drift**: Audience segment no longer aligns with product-market fit
- **Data decay**: Third-party audience data becoming stale
- **Broad targeting**: Casting too wide a net reducing relevance
- **Lookalike degradation**: Model trained on outdated seed audience

### 4. Placement Changes

- **Publisher site changes**: Page layout modifications affecting ad visibility
- **Ad unit resizing**: Dimensions changed reducing visual impact
- **New placements added**: Low-quality inventory diluting overall CTR
- **Below-fold migration**: Ads no longer in viewport on page load

### 5. Seasonality

- **Holiday periods**: User behavior shifts during seasonal events
- **Industry cycles**: B2B audiences less active during certain periods
- **Weekend vs weekday**: Different engagement patterns by day type
- **Time-of-day effects**: Peak and off-peak engagement variations

### 6. Competitor Campaigns

- **New competitor entrants**: Additional advertisers competing for same audience
- **Competitor creative innovation**: Better-performing ads setting higher bar
- **Competitor bid increases**: Pushing your ads to less desirable positions
- **Category expansion**: Related brands targeting overlapping audiences

### 7. Landing Page Issues

- **Slow load times**: Post-click experience degrading user patience
- **Mobile responsiveness**: Landing pages not optimized for device
- **Content mismatch**: Landing page not matching ad creative promise
- **Broken links**: Destination URLs returning errors

### 8. Ad Viewability

- **Low viewability scores**: Ads rendered but never visible to users
- **Fraudulent impressions**: Bot traffic inflating impression count
- **Measurement discrepancies**: Viewability vendor reporting issues
- **Ad rendering delays**: Heavy creative assets loading slowly

## Diagnostic Queries

### CTR Trend Analysis

```sql
-- Daily CTR trend over last 30 days
SELECT
    DATE(timestamp) as report_date,
    impressions,
    clicks,
    ROUND(clicks * 100.0 / NULLIF(impressions, 0), 4) as ctr,
    ROUND(AVG(clicks * 100.0 / NULLIF(impressions, 0)) OVER(
        ORDER BY DATE(timestamp) ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 4) as rolling_7d_avg
FROM campaign_daily_metrics
WHERE campaign_id = '{{campaign_id}}'
    AND timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
ORDER BY report_date;
```

### Creative-Level Performance

```sql
-- CTR by creative asset over last 14 days
SELECT
    creative_id,
    creative_name,
    impressions,
    clicks,
    ROUND(clicks * 100.0 / NULLIF(impressions, 0), 4) as ctr,
    DATEDIFF(CURRENT_DATE, MAX(timestamp)) as days_since_last_impression
FROM creative_impressions
WHERE campaign_id = '{{campaign_id}}'
    AND timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 14 DAY)
GROUP BY creative_id, creative_name
ORDER BY ctr DESC;
```

### Placement-Level Analysis

```sql
-- CTR by ad placement
SELECT
    placement_id,
    placement_name,
    ad_position,
    viewability_rate,
    impressions,
    clicks,
    ROUND(clicks * 100.0 / NULLIF(impressions, 0), 4) as ctr
FROM placement_performance
WHERE campaign_id = '{{campaign_id}}'
    AND timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)
ORDER BY impressions DESC;
```

### Device and Browser Segmentation

```sql
-- CTR by device type and browser
SELECT
    device_type,
    browser,
    os,
    impressions,
    clicks,
    ROUND(clicks * 100.0 / NULLIF(impressions, 0), 4) as ctr
FROM device_performance
WHERE campaign_id = '{{campaign_id}}'
    AND timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)
GROUP BY device_type, browser, os
HAVING impressions > 1000
ORDER BY ctr DESC;
```

### Audience Segment Performance

```sql
-- CTR by audience segment
SELECT
    audience_segment,
    segment_provider,
    impressions,
    clicks,
    ROUND(clicks * 100.0 / NULLIF(impressions, 0), 4) as ctr
FROM audience_performance
WHERE campaign_id = '{{campaign_id}}'
    AND timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)
GROUP BY audience_segment, segment_provider
HAVING impressions > 500
ORDER BY ctr DESC;
```

### Frequency vs CTR Correlation

```sql
-- CTR by impression frequency
SELECT
    impression_frequency,
    COUNT(DISTINCT user_id) as unique_users,
    SUM(impressions) as total_impressions,
    SUM(clicks) as total_clicks,
    ROUND(SUM(clicks) * 100.0 / NULLIF(SUM(impressions), 0), 4) as ctr
FROM user_frequency_analysis
WHERE campaign_id = '{{campaign_id}}'
    AND timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)
GROUP BY impression_frequency
ORDER BY impression_frequency;
```

## Recommended Actions

### Immediate Interventions (0-24 hours)

1. **Rotate creative assets**: Deploy fresh creative variations to combat fatigue
2. **Adjust ad positioning**: Move ads to higher-visibility page locations
3. **Exclude low-performing placements**: Pause placements with CTR < 0.05%
4. **Refresh audience segments**: Test alternative targeting parameters
5. **Verify landing page functionality**: Confirm destination URLs load correctly

### Short-Term Optimizations (1-7 days)

1. **A/B test creative concepts**: Test different messaging, imagery, CTAs
2. **Implement sequential messaging**: Show different ads to users based on exposure count
3. **Optimize ad sizes**: Test larger, IAB standard ad units
4. **Refine audience targeting**: Narrow focus to highest-engaging segments
5. **Implement dayparting**: Focus delivery during peak engagement hours

### Long-Term Strategy

1. **Establish creative refresh cadence**: Replace creatives every 2-3 weeks
2. **Build creative performance scoring**: Automated ranking of creative effectiveness
3. **Develop audience quality metrics**: Track post-click engagement by segment
4. **Implement viewability targeting**: Focus on placements with > 70% viewability
5. **Create competitive intelligence reports**: Monitor competitor creative strategies

## Escalation Paths

| Severity | Trigger | Escalation Level | Response Time |
|----------|---------|-----------------|---------------|
| P0 - Critical | CTR drops > 60% from baseline across all campaigns | VP Marketing + VP AdOps | 30 minutes |
| P1 - High | CTR drops 40-60% from baseline for top-spending campaigns | Director of Performance | 2 hours |
| P2 - Medium | CTR drops 20-40% from baseline | Senior Campaign Manager | 8 hours |
| P3 - Low | CTR drops < 20% from baseline | Campaign Analyst | Next business day |

### Escalation Contacts

- **Creative Issues**: Creative operations team for asset refresh and new concept development
- **Viewability Concerns**: Ad quality team for placement auditing and verification
- **Audience Performance**: Data science team for segment analysis and model retraining
- **Competitive Intelligence**: Strategy team for market analysis and positioning recommendations

## Prevention Checklist

- [ ] Creative refresh calendar maintained with 2-week rotation schedule
- [ ] Weekly CTR trend reports reviewed by campaign management team
- [ ] Monthly creative performance reviews with advertisers
- [ ] Real-time viewability monitoring on all active campaigns
- [ ] Audience segment freshness checks running weekly
- [ ] Placement quality audits conducted monthly
- [ ] Competitive landscape reports generated quarterly
- [ ] Landing page performance monitored continuously with alerts for degradation
