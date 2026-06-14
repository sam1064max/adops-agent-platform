# Creative Rejection

## Symptoms

- New creative upload fails ad review with rejection reason codes
- Campaign cannot launch or resume because required creatives are disapproved
- Partial creative approval: some sizes/formats approved, others rejected
- Previously approved creative suddenly rejected after policy update
- Dynamic creative assembly fails due to individual asset rejection
- Publisher-specific rejection not covered by platform-wide approval
- Video creatives rejected for exceeding length, file size, or bitrate limits
- Rich media creatives failing safe area or expansion behavior requirements
- Native creative templates rejected for misleading formatting or unclear ad labeling
- Landing page flagged for brand safety, malware, or policy violations independent of creative content
- Animation creatives rejected for exceeding frame rate or duration limits
- Creative rejections causing campaign delivery gaps with no automatic retry mechanism

## Possible Causes

- Creative violates platform content policies (prohibited content, misleading claims, restricted categories)
- File specifications outside accepted ranges (dimensions, file size, format, codec)
- Landing page URL returns 404, timeout, or contains prohibited content (malware, adult, illegal)
- Animation exceeds platform limits (e.g., GIF > 15 seconds, HTML5 > 100KB initial load)
- Text-to-image ratio exceeds platform threshold (e.g., >20% text overlay on Facebook)
- Missing required ad disclosures (sponsored labeling, "Ad" identifier, Terms & Conditions link)
- Brand safety flags triggered by keyword or image recognition on creative content
- Creative contains copyright-infringing music, images, or trademarks
- Video creatives contain black frames, static images, or insufficient motion at start
- Dynamic creative variables contain URLs with tracking parameters that trigger spam filters
- Sub-accounts or publisher-specific ad review rules more restrictive than platform defaults
- Creative content changed post-approval through dynamic rendering or conditional logic

## Diagnostic Queries

```sql
-- Creative rejection history and reasons
SELECT
  creative_id,
  creative_name,
  format,
  rejection_reason_code,
  rejection_reason_text,
  reviewer_id,
  review_timestamp,
  resubmission_count,
  current_status
FROM creative_review_log
WHERE campaign_id = '{campaign_id}'
ORDER BY review_timestamp DESC;

-- Rejection rate by creative type
SELECT
  creative_format,
  COUNT(*) AS total_submissions,
  SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected,
  ROUND(SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS rejection_rate
FROM creative_submissions
WHERE campaign_id = '{campaign_id}'
GROUP BY creative_format
ORDER BY rejection_rate DESC;

-- Landing page compliance status
SELECT
  creative_id,
  landing_url,
  http_status_code,
  ssl_valid,
  malware_flag,
  adult_content_flag,
  page_load_time_ms,
  last_checked
FROM creative_landing_page_audit
WHERE campaign_id = '{campaign_id}'
  AND (http_status_code != 200 OR ssl_valid = 0 OR malware_flag = 1 OR adult_content_flag = 1);

-- Creative size and spec validation
SELECT
  creative_id,
  file_size_bytes,
  width_px,
  height_px,
  duration_seconds,
  frame_rate_fps,
  CASE WHEN file_size_bytes > 150000 THEN 'OVER_SIZE_LIMIT' ELSE 'OK' END AS size_check,
  CASE WHEN duration_seconds > 15 THEN 'OVER_DURATION' ELSE 'OK' END AS duration_check,
  CASE WHEN frame_rate_fps > 30 THEN 'OVER_FPS' ELSE 'OK' END AS fps_check
FROM creative_specs
WHERE campaign_id = '{campaign_id}';
```

## Recommended Actions

1. **Review rejection reason codes**: Map each rejection code to specific policy violation. Common codes: 001 (prohibited content), 002 (misleading claims), 003 (landing page violation), 004 (file spec violation), 005 (brand safety). Address each code individually.

2. **Fix file specification issues**: Ensure all creatives meet platform-specific requirements. Common limits: JPG/PNG < 500KB, GIF < 5MB and 15 seconds, HTML5 < 100KB initial load, video < 10MB and 30 seconds. Re-export at correct specs rather than compressing existing files.

3. **Remediate landing page issues**: If rejection is landing page related, verify URL returns 200 status, SSL certificate is valid, page loads in under 3 seconds, and content matches creative claims. Remove any pop-ups, redirects, or auto-play audio that violate ad experience policies.

4. **Add required disclosures**: Include "Ad" or "Sponsored" label in visible area. Add privacy policy link. Include Terms & Conditions for sweepstakes or promotional offers. Ensure age-gating for restricted products (alcohol, gambling).

5. **Address text overlay violations**: Reduce text-to-image ratio below platform threshold. For Facebook, keep text overlay under 20% of image area. Use clean background images with text in separate HTML5 layer rather than burned-in text.

6. **Request manual review**: If creative is policy-compliant but auto-rejected, submit for manual review with detailed appeal. Include screenshots, landing page documentation, and policy reference showing compliance. Manual review typically takes 24-48 hours.

7. **Update creative library**: For creative sets with mixed approval status, remove rejected variants and continue serving approved ones. Create replacement creatives for rejected formats. Maintain backup creative inventory to prevent delivery gaps.

8. **Implement pre-submission validation**: Before uploading to ad server, run creatives through platform's spec validator. Check file size, dimensions, format, duration, and text ratio. Catch 90% of rejections before submission.

9. **Create creative approval checklist**: Standardize pre-upload checklist: file format correct, dimensions match placement, file size under limit, landing page live and accessible, disclosures present, no prohibited content, brand safety review complete.

10. **Monitor policy updates**: Subscribe to platform policy change notifications. When policies update, audit existing approved creatives for new violations. Proactively update creatives before grace period expires to avoid post-approval rejections.

## Escalation Paths

- **Level 1 (Creative Ops)**: Handle routine spec violations and format issues. Re-export creatives to correct specifications. Resubmit for review. Target 24-hour turnaround on standard rejections.

- **Level 2 (Policy Specialist)**: Escalate policy interpretation disputes. Appeal auto-rejections with policy documentation. Coordinate with platform policy teams for clarification on ambiguous guidelines.

- **Level 3 (AdOps Lead)**: If creative rejections are blocking campaign delivery SLAs, escalate to platform contacts for expedited review. Request emergency approval for time-sensitive campaigns with documentation of compliance.

- **Level 4 (Legal/Compliance)**: If rejections involve potential legal issues (copyright claims, regulatory compliance, restricted product advertising), involve legal team for content review before resubmission. Ensure all creatives meet jurisdiction-specific advertising regulations.
