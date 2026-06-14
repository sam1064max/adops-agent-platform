# Inventory Not Serving Troubleshooting Guide

## Overview

When inventory fails to serve ads, publishers lose revenue and advertisers miss delivery goals. This issue can range from complete ad serving failure to intermittent delivery gaps. Systematic diagnosis requires examining ad server configurations, technical implementations, and supply chain connectivity.

## Symptoms

- Zero impressions served despite active campaigns and available inventory
- Specific ad units showing no delivery while others function normally
- Intermittent ad serving with periods of blank ad slots
- Error messages in browser console related to ad loading
- Ad server UI showing campaigns as "active" but impression logs empty
- Publisher reporting revenue drops to zero for affected inventory

## Possible Causes

### 1. Ad Server Misconfiguration

- **Line item priority conflicts**: Competing line items with incorrect priority ordering
- **Targeting rule errors**: Overlapping or contradictory targeting criteria
- **Flight date misconfiguration**: Campaign dates set in wrong timezone or format
- **Rate limiting**: Frequency caps or pacing settings preventing delivery
- **Creative rotation settings**: Incorrect weight distribution or rotation logic

### 2. Ad Tag Errors

- **Malformed ad tags**: Incorrect HTML/JavaScript syntax in tag implementation
- **Missing required parameters**: Essential query parameters omitted from tag URL
- **Incorrect ad unit IDs**: Wrong placement IDs pointing to non-existent inventory
- **Encoding issues**: Special characters not properly URL-encoded
- **Async loading failures**: Script loading order causing initialization failures

### 3. Passback Issues

- **Passback tag not implemented**: Fallback ad tag missing from ad unit setup
- **Passback timeout settings**: Timeout too aggressive causing premature fallback
- **Recursive passbacks**: Passback triggering another ad request creating infinite loop
- **Passback creative errors**: Fallback creative also failing to serve
- **Header bidding passback conflicts**: Passback interfering with wrapper logic

### 4. Timeout Errors

- **Header bidding timeout**: Prebid.js wrapper timing out before demand responds
- **Ad server response timeout**: Primary ad server exceeding response deadline
- **Demand partner latency**: DSP or SSP responding too slowly
- **Network latency**: Slow connections causing request/response delays
- **Page load race conditions**: Ad tags executing before DOM is ready

### 5. Ad Block Impact

- **Increased ad blocker usage**: Growing percentage of users blocking ads
- **Selective blocking**: Specific ad formats or networks being targeted
- **Anti-adblock bypass failures**: Detection scripts not functioning properly
- **Publisher domain changes**: New domains not whitelisted in adblock filter lists

### 6. SSL Issues

- **Mixed content warnings**: HTTP ad tags on HTTPS pages being blocked
- **Certificate errors**: Expired or invalid SSL certificates on ad serving domains
- **Content Security Policy**: CSP headers blocking ad content execution
- **Upgrade-insecure-requests**: Automatic HTTP to HTTPS upgrades breaking ad paths

### 7. Header Bidding Failures

- **Prebid.js configuration errors**: Incorrect adapter or parameter setup
- **Bid adapter failures**: Specific demand partner adapters throwing errors
- **Timeout threshold too low**: Wrapper not waiting long enough for bids
- **Missing consent management**: GDPR consent not being passed to bidders
- **Container div missing**: Ad unit div elements not present in DOM

### 8. Supply Source Deactivation

- **SSP account deactivation**: Demand partner account suspended or terminated
- **Deal deactivation**: Private marketplace deals expired or paused
- **Inventory exclusion**: Specific ad units removed from programmatic availability
- **Publisher domain changes**: New domains not registered with supply partners

## Diagnostic Queries

### Ad Request Volume Check

```sql
-- Ad request volume by ad unit over last 24 hours
SELECT
    ad_unit_id,
    ad_unit_name,
    COUNT(*) as request_count,
    MIN(timestamp) as first_request,
    MAX(timestamp) as last_request
FROM ad_requests
WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
GROUP BY ad_unit_id, ad_unit_name
ORDER BY request_count DESC;
```

### Line Item Delivery Status

```sql
-- Active line items with delivery status
SELECT
    li.line_item_id,
    li.line_item_name,
    li.status,
    li.priority,
    li.start_date,
    li.end_date,
    li.daily_budget,
    COALESCE(SUM(r.impressions), 0) as impressions_today,
    CASE
        WHEN li.status != 'active' THEN 'Status Issue'
        WHEN CURRENT_DATE < li.start_date THEN 'Not Started'
        WHEN CURRENT_DATE > li.end_date THEN 'Expired'
        WHEN COALESCE(SUM(r.impressions), 0) = 0 THEN 'No Delivery'
        ELSE 'Delivering'
    END as delivery_status
FROM line_items li
LEFT JOIN line_item_impressions r ON li.line_item_id = r.line_item_id
    AND r.impression_date = CURRENT_DATE
WHERE li.campaign_id = '{{campaign_id}}'
GROUP BY li.line_item_id, li.line_item_name, li.status, li.priority,
    li.start_date, li.end_date, li.daily_budget;
```

### Error Log Analysis

```sql
-- Top ad serving errors in last 6 hours
SELECT
    error_type,
    error_code,
    error_message,
    ad_unit_id,
    COUNT(*) as error_count,
    MIN(timestamp) as first_occurrence,
    MAX(timestamp) as last_occurrence
FROM ad_serving_errors
WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 6 HOUR)
GROUP BY error_type, error_code, error_message, ad_unit_id
ORDER BY error_count DESC
LIMIT 25;
```

### Header Bidding Performance

```sql
-- Header bidding bid rate and timeout analysis
SELECT
    ad_unit_id,
    wrapper_name,
    COUNT(*) as total_requests,
    SUM(CASE WHEN bid_received THEN 1 ELSE 0 END) as bids_received,
    ROUND(SUM(CASE WHEN bid_received THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as bid_rate,
    ROUND(AVG(CASE WHEN bid_received THEN response_time_ms END), 0) as avg_response_ms,
    SUM(CASE WHEN timed_out THEN 1 ELSE 0 END) as timeouts,
    ROUND(SUM(CASE WHEN timed_out THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as timeout_rate
FROM header_bidding_logs
WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 6 HOUR)
GROUP BY ad_unit_id, wrapper_name
ORDER BY timeout_rate DESC;
```

### Passback Tag Verification

```sql
-- Passback tag execution and errors
SELECT
    ad_unit_id,
    passback_tag_id,
    COUNT(*) as passback_executions,
    SUM(CASE WHEN error_occurred THEN 1 ELSE 0 END) as errors,
    ROUND(SUM(CASE WHEN error_occurred THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as error_rate,
    AVG(render_time_ms) as avg_render_time
FROM passback_logs
WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
GROUP BY ad_unit_id, passback_tag_id
HAVING COUNT(*) > 0
ORDER BY error_rate DESC;
```

## Recommended Actions

### Immediate Fixes (0-2 hours)

1. **Validate ad tag syntax**: Check for HTML/JavaScript errors in tag implementation
2. **Confirm line item status**: Ensure campaigns are active with correct dates
3. **Check ad server connectivity**: Verify API access and authentication
4. **Review targeting settings**: Remove conflicting or overly restrictive criteria
5. **Test ad tags in browser console**: Execute tags manually to capture error messages

### Short-Term Resolutions (2-48 hours)

1. **Increase header bidding timeout**: Adjust from 1000ms to 2000ms if timeouts are frequent
2. **Implement passback tags**: Add fallback ad tags for failed primary demand
3. **Fix SSL certificate issues**: Renew expired certificates or update ad serving URLs
4. **Update CSP headers**: Whitelist ad serving domains in Content-Security-Policy
5. **Activate backup demand partners**: Enable additional SSPs to compensate for failures

### Long-Term Improvements

1. **Implement ad rendering monitoring**: Real-time alerts when ad units fail to render
2. **Deploy ad quality scoring**: Rate inventory quality based on viewability and engagement
3. **Build automated tag validation**: Pre-deployment checks for ad tag correctness
4. **Create redundancy in demand paths**: Multiple demand sources for each ad unit
5. **Establish SLA monitoring**: Track partner response times and uptime

## Escalation Paths

| Severity | Trigger | Escalation Level | Response Time |
|----------|---------|-----------------|---------------|
| P0 - Critical | Complete ad serving failure across all inventory | VP Engineering + VP Publisher Services | 15 minutes |
| P1 - High | > 50% of inventory not serving for > 1 hour | Director of Ad Operations | 30 minutes |
| P2 - Medium | 10-50% of inventory not serving for > 4 hours | Senior Ad Operations Engineer | 2 hours |
| P3 - Low | < 10% of inventory affected or intermittent issues | Ad Operations Engineer | 8 hours |

### Escalation Contacts

- **Ad Server Issues**: Contact ad server vendor support with ad unit IDs and error logs
- **SSP/DSP Failures**: Reach out to partner technical support with request IDs
- **SSL/Certificate Issues**: Coordinate with IT security team for certificate management
- **Header Bidding Failures**: Engage wrapper vendor support with bidder diagnostic data

## Prevention Checklist

- [ ] Pre-deployment ad tag validation automated in CI/CD pipeline
- [ ] Real-time monitoring dashboards for all ad units with rendering alerts
- [ ] Weekly ad server configuration audits
- [ ] Monthly header bidding wrapper performance reviews
- [ ] Quarterly SSL certificate expiration tracking
- [ ] Automated passback tag testing
- [ ] Ad blocker impact monitoring with revenue loss estimation
- [ ] Content Security Policy whitelist maintenance
