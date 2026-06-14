# Auction Competitiveness

## Symptoms

- Win rate declining month-over-month despite maintaining or increasing bid levels
- CPM costs rising 20-40% without corresponding audience growth or quality improvement
- Same campaigns winning fewer auctions on premium publishers while losing on mid-tier
- New competitor entries coinciding with sudden drop in auction performance
- Deal IDs that previously guaranteed delivery now under-serving significantly
- Bid landscape reports show cluster of bids just above our max bid, suggesting bid shadowing
- Programmatic guaranteed deals losing to open exchange when makegood rules trigger
- Brand campaigns with fixed CPM deals seeing frequent budget overrides due to CPM spikes
- Auction timeout errors increasing, suggesting demand-side latency issues
- First-price auction migration causing effective CPM inflation without bid adjustment
- Private marketplace floor prices rising faster than open exchange clearing prices
- Header bidding stack favoring new demand partners with faster response times

## Possible Causes

- New high-budget advertiser entered auction with aggressive bidding strategy
- Market-wide CPM inflation due to seasonal demand (Q4 holidays, back-to-school, political advertising)
- Transition from second-price to first-price auction mechanics inflating effective CPMs
- Bid shading algorithms not calibrated for current auction dynamics, overpaying or underbidding
- Competitor using real-time bid optimization tools that react faster to auction opportunities
- Publisher shifting premium inventory to programmatic guaranteed, reducing open exchange supply
- SSP taking larger margin through hidden fees or supply path markup
- Data management platform segments becoming more competitive as more bidders access same audiences
- Device ID deprecation reducing ability to target effectively, forcing broader (less efficient) bids
- Supply path optimization removing intermediaries but reducing auction access breadth
- Frequency capping competition where multiple advertisers bid on same user simultaneously
- Deal ID floor prices set based on outdated CPM benchmarks, no longer reflecting true market value

## Diagnostic Queries

```sql
-- Win rate and CPM trend analysis
SELECT
  DATE(log_date) AS day,
  SUM(bids) AS total_bids,
  SUM(wins) AS total_wins,
  ROUND(SUM(wins) * 100.0 / NULLIF(SUM(bids), 0), 2) AS win_rate,
  ROUND(AVG(cpm_bid), 2) AS avg_bid_cpm,
  ROUND(AVG(cpm_won), 2) AS avg_won_cpm,
  ROUND(AVG(cpm_won - cpm_bid), 2) AS avg_bid_vs_win_delta
FROM auction_logs
WHERE campaign_id = '{campaign_id}'
  AND log_date BETWEEN DATE_SUB('{end_date}', INTERVAL 30 DAY) AND '{end_date}'
GROUP BY DATE(log_date)
ORDER BY day;

-- Competitor density analysis by publisher
SELECT
  publisher,
  deal_id,
  COUNT(DISTINCT advertiser_id) AS competing_advertisers,
  ROUND(AVG(rival_max_bid), 2) AS avg_competitor_bid,
  ROUND(MAX(rival_max_bid), 2) AS highest_competitor_bid,
  ROUND(AVG(our_bid), 2) AS our_avg_bid,
  ROUND((AVG(rival_max_bid) - AVG(our_bid)) / AVG(our_bid) * 100, 2) AS bid_gap_pct
FROM auction_competition_log
WHERE campaign_id = '{campaign_id}'
  AND log_date BETWEEN '{start_date}' AND '{end_date}'
GROUP BY publisher, deal_id
HAVING COUNT(DISTINCT advertiser_id) > 1
ORDER BY bid_gap_pct DESC;

-- First-price vs second-price auction impact
SELECT
  auction_type,
  COUNT(*) AS total_auctions,
  ROUND(AVG(cpm_bid), 2) AS avg_bid,
  ROUND(AVG(cpm_won), 2) AS avg_won,
  ROUND(AVG(cpm_won) / AVG(cpm_bid) * 100, 2) AS effective_cpm_pct,
  SUM(wins) AS wins,
  ROUND(SUM(wins) * 100.0 / COUNT(*), 2) AS win_rate
FROM auction_logs
WHERE campaign_id = '{campaign_id}'
  AND log_date BETWEEN '{start_date}' AND '{end_date}'
GROUP BY auction_type;

-- Bid-to-win analysis: identify auctions lost by narrow margins
SELECT
  publisher,
  deal_id,
  our_bid,
  winning_bid,
  ROUND((winning_bid - our_bid) / our_bid * 100, 2) AS lost_by_pct,
  COUNT(*) AS auctions_lost_by_this_margin
FROM auction_loss_log
WHERE campaign_id = '{campaign_id}'
  AND log_date BETWEEN '{start_date}' AND '{end_date}'
  AND winning_bid - our_bid < our_bid * 0.15
GROUP BY publisher, deal_id, our_bid, winning_bid
ORDER BY auctions_lost_by_this_margin DESC;
```

## Recommended Actions

1. **Implement bid shading**: Deploy machine learning bid shading algorithm that analyzes historical auction outcomes and competitor behavior. Bid shading typically reduces CPM by 10-20% while maintaining win rates. Calibrate for first-price auction dominance.

2. **Adjust bid strategy by auction type**: For first-price auctions, bid at expected clearing price (not maximum willingness to pay). For second-price auctions, bid true value. Implement dynamic bid adjustments that automatically calibrate based on auction type detection.

3. **Diversify supply sources**: Reduce reliance on concentrated publishers where competition is highest. Expand to long-tail publishers with lower competition and comparable audience quality. Target 30% of impressions from publishers where competition index is below market average.

4. **Optimize deal ID portfolio**: Audit all active deal IDs for performance. Remove deals with win rates below 30% after 30 days. Negotiate floor price reductions on underperforming deals. Prioritize deals with exclusive or first-look access.

5. **Enhance audience differentiation**: Use first-party data segments that competitors cannot access. Build lookalike models on proprietary data to create unique audience pools. Deploy contextual targeting layers that reduce overlap with competitor audience segments.

6. **Improve response latency**: Ensure bid response time is under 100ms for all SSP connections. Slow response times cause auction losses even with competitive bids. Optimize ad creative rendering, reduce tracking pixel chains, and implement bid caching where SSP allows.

7. **Implement competitive intelligence monitoring**: Track competitor bid patterns, timing, and publisher preferences. Use auction log analysis to identify when specific competitors increase activity. Adjust bidding strategy in real-time based on competitive landscape changes.

8. **Negotiate auction access terms**: Work with SSPs to secure preferred auction access (first-look, priority tier, private marketplace exclusivity). Negotiate reduced SSP fees or transparent supply path pricing. Request auction data exports for post-campaign competitive analysis.

9. **Calibrate max bid caps**: Review and adjust maximum bid caps based on current market conditions. If CPMs have inflated 30% over past quarter, increase max bids proportionally or accept reduced win rates on premium inventory. Set hard budget ceilings to prevent runaway CPMs.

10. **Leverage contextual signals**: Layer contextual targeting on top of audience targeting to improve bid relevance. Ads placed in contextually relevant content receive higher engagement, allowing lower bids while maintaining performance. Use AI-powered contextual analysis for real-time content classification.

## Escalation Paths

- **Level 1 (Trader)**: If win rate drops below 15% on critical campaigns, increase bid multipliers by 10-15%. Monitor for 48 hours. If CPMs increase without win rate improvement, revert and investigate competitive landscape.

- **Level 2 (Campaign Manager)**: If auction competitiveness decline is sustained (>2 weeks), escalate to inventory team for alternative supply sourcing. Request publisher negotiations for improved deal terms. Review and optimize deal ID portfolio.

- **Level 3 (AdOps Lead)**: If CPM inflation exceeds 30% without market justification, escalate to engineering for bid algorithm optimization. Review SSP integration for hidden fees or supply path inefficiencies. Coordinate competitive intelligence analysis across account portfolio.

- **Level 4 (VP AdOps/Revenue)**: If auction competitiveness issues threaten client retention or contractual commitments, escalate to executive level. Engage publisher C-suite relationships for strategic inventory access. Consider platform-wide bidding strategy overhaul for major accounts.
