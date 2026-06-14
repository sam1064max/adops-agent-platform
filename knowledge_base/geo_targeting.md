# Geo Targeting

## Symptoms

- Impressions serving outside designated geographic target area
- DMA (Designated Market Area) delivery reports show mismatches between targeted and actual DMAs
- Country-level targeting correct but state/province or city-level targeting inaccurate
- VPN users bypassing geo restrictions, serving ads to blocked regions
- Campaign targeting US-only but impressions appearing in Canada, Mexico, or overseas territories
- City-level targeting showing delivery to neighboring metros or suburban areas
- State-level targeting missing border cities or cross-state metro areas
- GDPR/CCPA consent violations: ads serving to users in regulated regions without proper consent flags
- Geo-fenced campaigns not triggering on mobile devices within defined radius
- International campaigns delivering to wrong language regions despite correct country targeting
- Rural areas showing zero delivery despite targeting entire state or country
- IP database lag causing new cell towers or ISP routing changes to map incorrectly

## Possible Causes

- IP geolocation database outdated, mapping IPs to incorrect physical locations
- Mobile carrier CGNAT (Carrier-Grade NAT) routing thousands of users through single IP gateway located in different region
- VPN and proxy usage allowing users to appear in locations outside their physical geography
- Geo-targeting radius too small for mobile users whose GPS accuracy is limited to 100-500m
- DMA boundaries defined by Nielsen may not align with actual metro area definitions used by advertisers
- ISP routing anomalies causing IP addresses to geolocate to unexpected regions
- Geo-fence trigger zones misconfigured with incorrect latitude/longitude coordinates or radius
- Cross-border metro areas (e.g., Kansas City MO/KS, Texarkana TX/AR) not properly segmented
- Consent management platform not passing geo-consent flags to ad server correctly
- Daylight saving time or timezone handling errors causing time-based geo rules to miscalculate
- Rural areas with limited ISP infrastructure routing through distant data centers
- Programmatic deal targeting not inheriting geo restrictions from parent campaign

## Diagnostic Queries

```sql
-- Geographic distribution of served impressions
SELECT
  targeted_country,
  targeted_region,
  actual_country,
  actual_region,
  actual_city,
  COUNT(*) AS impressions,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS pct_of_total
FROM impression_log
WHERE campaign_id = '{campaign_id}'
  AND impression_timestamp BETWEEN '{start_date}' AND '{end_date}'
GROUP BY targeted_country, targeted_region, actual_country, actual_region, actual_city
ORDER BY impressions DESC;

-- Out-of-target impressions detail
SELECT
  impression_id,
  user_ip,
  geo_ip_country,
  geo_ip_region,
  geo_ip_city,
  targeted_country,
  targeted_region,
  device_type,
  impression_timestamp
FROM impression_log
WHERE campaign_id = '{campaign_id}'
  AND (
    geo_ip_country != targeted_country
    OR (geo_ip_region != targeted_region AND targeted_region IS NOT NULL)
  )
ORDER BY impression_timestamp DESC
LIMIT 100;

-- VPN/proxy detection correlation
SELECT
  CASE WHEN is_vpn = 1 THEN 'VPN' ELSE 'Non-VPN' END AS user_type,
  COUNT(*) AS impressions,
  COUNT(DISTINCT user_ip) AS unique_ips,
  ROUND(AVG(CAST(geo_accuracy_km AS FLOAT)), 1) AS avg_accuracy_km
FROM impression_log il
JOIN ip_intelligence ipi ON il.user_ip = ipi.ip_address
WHERE campaign_id = '{campaign_id}'
GROUP BY is_vpn;

-- City-level accuracy: compare targeted city vs actual city
SELECT
  targeted_city,
  actual_city,
  COUNT(*) AS impressions,
  ROUND(AVG(geo_accuracy_km), 1) AS avg_accuracy_km
FROM impression_log
WHERE campaign_id = '{campaign_id}'
  AND targeted_city IS NOT NULL
GROUP BY targeted_city, actual_city
HAVING COUNT(*) > 10
ORDER BY targeted_city, impressions DESC;
```

## Recommended Actions

1. **Upgrade IP geolocation database**: Ensure IP-to-geo mapping uses latest database (MaxMind GeoIP2, IP2Location, or similar) updated monthly. Older databases can be off by 50-200km in rural areas and 10-50km in urban areas. Implement automated database refresh schedule.

2. **Add mobile-specific geo validation**: For mobile campaigns, use GPS coordinates when available (with user consent) rather than IP-based geolocation. GPS accuracy is typically 10-50m vs. 1-10km for IP-based. Fall back to IP geolocation only when GPS is unavailable.

3. **Implement VPN/proxy detection**: Deploy real-time VPN detection service (e.g., IPQualityScore, MaxMind minFraud). Either exclude VPN users entirely or apply secondary validation. For premium campaigns, require device-level location services rather than accepting IP-only targeting.

4. **Expand border metro targeting**: For cross-border metro areas, define targeting as union of both states/provinces (e.g., "New York City" = Manhattan + Brooklyn + Jersey City + Newark). Use Nielsen DMA definitions as baseline but add manual overrides for known edge cases.

5. **Increase geo-fence radius**: For location-based campaigns, set minimum radius of 500m for urban areas and 2km for rural areas to account for mobile GPS accuracy limitations. Use poi-based targeting rather than raw lat/long when targeting specific venues or business districts.

6. **Validate consent flag propagation**: For GDPR/CCPA compliance, verify geo-consent flags flow correctly from consent management platform through to ad server. Implement automated compliance checks that block serving to regulated regions when consent is not confirmed.

7. **Create geo-exclusion zones**: Build exclusion zones around military bases, prisons, and other facilities where IP geolocation is unreliable. Add exclusions for known VPN exit node IP ranges. Maintain updated exclusion list based on quarterly accuracy audits.

8. **Test with residential proxies**: Conduct QA testing using residential proxies in target geo to verify actual ad delivery. Test across different ISPs, mobile carriers, and device types. Document any systematic geo-mapping errors and submit corrections to geo database provider.

9. **Implement geo-validation post-impression**: Add post-impression geo validation that logs both targeted and actual served location. Generate weekly accuracy reports. If accuracy drops below 90%, investigate root cause (database lag, carrier routing changes, etc.).

10. **Set up geo-based bid modifiers**: Apply bid adjustments based on geo-accuracy confidence. Reduce bids by 10-20% in areas where geo-database accuracy is known to be lower (rural, cross-border). Increase bids in high-confidence urban areas with accurate GPS data.

## Escalation Paths

- **Level 1 (Trader)**: If out-of-target impressions exceed 5%, pause affected line items. Review geo-targeting configuration for obvious errors (wrong country code, inverted coordinates). Test with manual geo-override.

- **Level 2 (Campaign Manager)**: If geo-accuracy issues persist across multiple campaigns, escalate to data engineering for IP database audit. Coordinate with geo-database provider for manual corrections to known problem areas.

- **Level 3 (Compliance/Privacy)**: If GDPR/CCPA consent violations are identified through geo-targeting failures, immediately pause all delivery to affected regions. Notify legal and privacy teams. Implement emergency geo-block until consent flow is validated.

- **Level 4 (VP AdOps)**: If geo-targeting failures result in contractual SLA violations (e.g., brand safety commitments, regional exclusivity deals), escalate to account leadership for client notification and remediation planning.
