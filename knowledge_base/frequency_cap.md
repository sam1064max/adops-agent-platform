# Frequency Cap

## Symptoms

- Same users seeing ad 10+ times within 24-hour period despite frequency cap set to 3-4
- Reach reports show significantly lower unique users than expected impression volume implies
- Frequency distribution histogram heavily skewed toward high-frequency buckets
- Ad fatigue signals: declining CTR, increasing skip rates, negative brand lift surveys
- Cross-device reports show different frequency counts per device for same user
- Campaign reaches ceiling on unique audience while impression quota remains unfulfilled
- Retargeting pools served disproportionately high frequency vs. prospecting pools
- Brand safety complaints from users about ad repetition on same publisher
- Programmatic deals delivering 100% of impressions to same user segments
- Deduplication logic not triggering across connected TV and mobile app placements
- Frequency cap counter resets unexpectedly at midnight UTC instead of user-local time

## Possible Causes

- Frequency cap applied at campaign level but not enforced at line item or placement level, allowing uncapped delivery through lower hierarchy
- Cross-device identity graph fragmented, treating same user's phone, tablet, and desktop as separate entities
- Cookie deletion or ITP/ETP restrictions causing cap counters to reset when new cookies are generated
- Server-side frequency tracking database experiencing write lag, allowing over-service before cap check completes
- Frequency cap window misconfigured (e.g., "per hour" instead of "per day" or "per lifetime")
- Third-party audience segments with stale data, allowing same user to re-enter targeting pool
- Deduplication window shorter than campaign flight, allowing user to be re-counted after window expires
- Multiple DSPs buying same inventory without shared frequency management
- Cap enforcement applied post-impression rather than pre-bid, allowing over-serving on high-latency connections
- Private marketplace deals with no frequency cap enforcement at deal level
- Frequency counter incremented on impression request but not on actual served impression, creating under-count

## Diagnostic Queries

```sql
-- Frequency distribution analysis
SELECT
  user_id,
  COUNT(*) AS impression_count,
  CASE
    WHEN COUNT(*) = 1 THEN '1'
    WHEN COUNT(*) BETWEEN 2 AND 3 THEN '2-3'
    WHEN COUNT(*) BETWEEN 4 AND 5 THEN '4-5'
    WHEN COUNT(*) BETWEEN 6 AND 10 THEN '6-10'
    ELSE '11+'
  END AS frequency_bucket
FROM impression_log
WHERE campaign_id = '{campaign_id}'
  AND impression_timestamp BETWEEN '{start_date}' AND '{end_date}'
GROUP BY user_id
ORDER BY impression_count DESC;

-- Top 20 most-served users
SELECT
  user_id,
  device_id,
  COUNT(*) AS impressions,
  MIN(impression_timestamp) AS first_seen,
  MAX(impression_timestamp) AS last_seen,
  DATEDIFF(hour, MIN(impression_timestamp), MAX(impression_timestamp)) AS hours_span
FROM impression_log
WHERE campaign_id = '{campaign_id}'
GROUP BY user_id, device_id
ORDER BY impressions DESC
LIMIT 20;

-- Frequency by device type to identify cross-device gaps
SELECT
  device_type,
  device_id_source,
  COUNT(DISTINCT user_id) AS unique_users,
  COUNT(*) AS total_impressions,
  ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT user_id), 2) AS avg_frequency
FROM impression_log
WHERE campaign_id = '{campaign_id}'
GROUP BY device_type, device_id_source
ORDER BY avg_frequency DESC;

-- Check for cap reset anomalies (same user serving in consecutive days with count restarting)
WITH daily_freq AS (
  SELECT
    user_id,
    DATE(impression_timestamp) AS serve_date,
    ROW_NUMBER() OVER (PARTITION BY user_id, DATE(impression_timestamp) ORDER BY impression_timestamp) AS daily_rank
  FROM impression_log
  WHERE campaign_id = '{campaign_id}'
)
SELECT user_id, serve_date, daily_rank
FROM daily_freq
WHERE daily_rank > 1
ORDER BY user_id, serve_date;
```

## Recommended Actions

1. **Audit frequency cap hierarchy**: Verify frequency caps are set at line item level, not just campaign level. Campaign-level caps in most ad servers are advisory; line item-level caps are enforced. Apply caps at every level of the hierarchy for redundancy.

2. **Implement cross-device frequency management**: Deploy a unified device graph (e.g., LiveRamp, Drawbridge, or internal identity resolution) to consolidate user identity across devices. Set frequency caps at the person level, not device level, using the identity graph to link sessions.

3. **Migrate to server-side frequency tracking**: Client-side cookie-based tracking is unreliable due to ITP/ETP. Implement server-side frequency counters stored in first-party database. Update counter on each impression serve event and check before rendering ad.

4. **Extend deduplication window**: If campaign runs 30 days, set deduplication window to match or exceed flight length. For always-on campaigns, use rolling 30-day window. Ensure deduplication logic applies before bid decision, not after.

5. **Add pre-bid frequency checks**: Integrate frequency data into pre-bid segment calls. Before submitting bid request, check user's current frequency count. If at or above cap, exclude from bid opportunity. This prevents over-serving on high-latency connections where post-impression enforcement fails.

6. **Share frequency data across DSPs**: If buying through multiple DSPs, implement a centralized frequency management layer. Use a shared frequency counter via DMP or custom middleware. Each DSP queries the shared counter before bidding to prevent compounding over-serving.

7. **Tune frequency caps by funnel stage**: Set different caps for prospecting (3-4 per 24h), retargeting (5-7 per 24h), and conversion-optimized (7-10 per 24h) campaigns. Retargeting audiences tolerate higher frequency; prospecting audiences fatigue faster.

8. **Monitor frequency distribution daily**: Build dashboard showing frequency distribution histogram. Alert if more than 5% of users exceed cap threshold. Review distribution weekly and adjust caps if fatigue signals (CTR decline, negative sentiment) appear.

9. **Implement frequency decay**: Rather than hard cap, implement exponential decay model where each subsequent impression has lower bid priority. This naturally reduces over-serving without abrupt cutoff that could impact delivery pacing.

10. **A/B test frequency impact**: Run holdout test with 10% of audience at zero frequency to measure incrementality. Compare brand lift and conversion rates across frequency buckets. Use data to set optimal frequency that balances reach and frequency efficiency.

## Escalation Paths

- **Level 1 (Trader)**: If frequency distribution shows >10% of users above cap, pause campaign and audit cap settings. Check line item hierarchy for missing caps. Adjust cap configuration and resume with monitoring.

- **Level 2 (Campaign Manager)**: If cross-device fragmentation is root cause, escalate to data engineering for identity graph deployment. Coordinate with DMP team to implement unified user profiles.

- **Level 3 (AdOps Lead)**: If frequency over-serving spans multiple campaigns or platforms, escalate to engineering for centralized frequency management system. This is a platform-level architectural issue requiring dedicated development.

- **Level 4 (Client Services)**: If frequency fatigue has already impacted brand perception (measured via surveys or social listening), notify client immediately. Propose frequency reduction and makegood impressions for affected audience segment.
