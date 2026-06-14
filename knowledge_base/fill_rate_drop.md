# Fill Rate Drop Troubleshooting Guide

## Overview

Fill rate represents the percentage of ad requests that result in a served ad. A sudden or gradual decline in fill rate directly impacts revenue and signals underlying issues in the programmatic supply chain. This guide covers systematic diagnosis of fill rate drops across all common root causes.

## Symptoms

- Fill rate drops from baseline (e.g., 85% to 40%) over hours or days
- Revenue decline without corresponding traffic reduction
- Bid request volume remains stable but bid responses decrease
- Specific ad units or geographies show disproportionate drops
- Fill rate recovers intermittently before dropping again
- Partner-level fill rates diverge significantly from historical norms

## Possible Causes

### 1. Ad Request Volume Changes

- **Traffic source shifts**: Migration from high-fill direct traffic to lower-fill programmatic sources
- **Bot traffic spikes**: Inflated requests from non-human traffic that demand partners reject
- **New inventory sources**: Adding low-quality supply that degrades overall fill
- **Page load timing changes**: JavaScript modifications delaying ad tag execution

### 2. Bid Shading and Price Floor Issues

- **Floor price increases**: Recent SSP/DSP floor adjustments pricing out bidders
- **Bid shading algorithms**: DSPs reducing bids to optimize for first-price auctions
- **Dynamic floor misconfiguration**: Automated floors set too aggressive for current demand
- **Currency fluctuations**: Cross-border bid degradation from exchange rate shifts

### 3. Advertiser Pullout

- **Campaign completions**: Major campaigns reaching flight end without renewal
- **Budget reallocation**: Advertisers shifting spend to competitors or channels
- **Brand safety blacklisting**: Advertisers blocking specific inventory categories
- **Seasonal pullback**: Industry-wide budget reductions (e.g., post-holiday)

### 4. Creative Issues

- **Creative audit failures**: New creatives failing platform review processes
- **File format incompatibility**:Creatives exceeding size or format specifications
- **Landing page policy violations**: Destination URLs flagged by trust & safety
- **Rich media errors**: Interactive creatives failing rendering checks

### 5. Demand Partner Failures

- **DSP connectivity issues**: API timeouts or authentication failures
- **Bid response errors**: Malformed responses from demand partners
- **QPS throttling**: Rate limiting from demand side platforms
- **Cookie sync failures**: Identity resolution breakdowns reducing bid rates

### 6. Supply Path Issues

- **SSP technical failures**: Server outages or degraded performance
- **Header bidding timeout**: Prebid.js or similar wrappers timing out
- **Ad server misconfiguration**: Incorrect line item priority or targeting
- **Passback tag failures**: Fallback ads not rendering when primary demand fails

## Diagnostic Queries

### Request-Level Analysis

```sql
-- Compare fill rates by day over last 30 days
SELECT
    DATE(timestamp) as request_date,
    COUNT(*) as total_requests,
    SUM(CASE WHEN status = 'filled' THEN 1 ELSE 0 END) as filled_requests,
    ROUND(SUM(CASE WHEN status = 'filled' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as fill_rate
FROM ad_requests
WHERE timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
GROUP BY DATE(timestamp)
ORDER BY request_date DESC;
```

### Partner-Level Fill Analysis

```sql
-- Fill rate by demand partner for last 7 days vs prior 7 days
SELECT
    partner_id,
    partner_name,
    SUM(CASE WHEN period = 'current' AND filled THEN 1 ELSE 0 END) * 100.0 /
        NULLIF(SUM(CASE WHEN period = 'current' THEN 1 ELSE 0 END), 0) as current_fill_rate,
    SUM(CASE WHEN period = 'previous' AND filled THEN 1 ELSE 0 END) * 100.0 /
        NULLIF(SUM(CASE WHEN period = 'previous' THEN 1 ELSE 0 END), 0) as previous_fill_rate
FROM (
    SELECT partner_id, partner_name, filled,
        CASE WHEN timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY) THEN 'current' ELSE 'previous' END as period
    FROM ad_requests
    WHERE timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 14 DAY)
) sub
GROUP BY partner_id, partner_name
ORDER BY current_fill_rate DESC;
```

### Bid Response Error Tracking

```sql
-- Top bid response errors in last 24 hours
SELECT
    error_code,
    error_message,
    partner_id,
    COUNT(*) as error_count
FROM bid_response_errors
WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
GROUP BY error_code, error_message, partner_id
ORDER BY error_count DESC
LIMIT 20;
```

### Geographic Fill Distribution

```sql
-- Fill rate by country for current vs baseline period
SELECT
    country_code,
    SUM(CASE WHEN filled THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as fill_rate,
    COUNT(*) as request_volume
FROM ad_requests
WHERE timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)
GROUP BY country_code
HAVING COUNT(*) > 1000
ORDER BY fill_rate ASC;
```

## Recommended Actions

### Immediate Triage (0-2 hours)

1. **Check partner health dashboards** for outages or degraded performance
2. **Review recent configuration changes** to floor prices, targeting, or line items
3. **Validate ad tag deployment** on key publisher pages
4. **Confirm bid response latency** is within acceptable thresholds (< 200ms)
5. **Check for creative rejection notifications** from ad review systems

### Short-Term Fixes (2-48 hours)

1. **Temporarily lower floor prices** by 10-15% to restore demand participation
2. **Activate backup demand partners** to compensate for underperforming sources
3. **Re-enable paused line items** that may have been accidentally deactivated
4. **Clear and regenerate cookie sync tables** if identity resolution is suspect
5. **Deploy A/B test** comparing current configuration against known-good baseline

### Long-Term Improvements

1. **Implement real-time fill rate alerting** with threshold-based notifications
2. **Establish partner SLA monitoring** with automated failover triggers
3. **Create demand partner scorecards** tracking fill rate, latency, and revenue trends
4. **Develop inventory quality filters** to reject low-probability-to-fill requests
5. **Build automated floor price optimization** based on real-time demand signals

## Escalation Paths

| Severity | Trigger | Escalation Level | Response Time |
|----------|---------|-----------------|---------------|
| P0 - Critical | Fill rate < 20% globally | VP Engineering + VP Sales | 15 minutes |
| P1 - High | Fill rate drops > 30% from baseline | Director of AdOps | 1 hour |
| P2 - Medium | Fill rate drops 15-30% from baseline | Senior AdOps Engineer | 4 hours |
| P3 - Low | Fill rate drops < 15% from baseline | AdOps Engineer | Next business day |

### Escalation Contacts

- **SSP/Exchange Issues**: Contact partner technical support with request IDs and timestamps
- **DSP Connectivity**: Reach out to partner account managers with error logs
- **Ad Server Issues**: Escalate to ad server vendor support with affected ad unit IDs
- **Creative Policy**: Contact publisher trust & safety teams with policy reference numbers

## Prevention Checklist

- [ ] Weekly fill rate trend review meetings
- [ ] Monthly partner performance audits
- [ ] Quarterly demand partner contract reviews
- [ ] Real-time monitoring dashboards for all critical metrics
- [ ] Automated alerts for fill rate deviations > 10%
- [ ] Documented runbooks for common fill rate scenarios
- [ ] Regular load testing of ad serving infrastructure
- [ ] Cookie sync health checks running every 6 hours
