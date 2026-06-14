"""Dashboard APIRouter — internal HTML operational pages.

Include in app.py:
    from src.dashboards.router import dashboard_router
    app.include_router(dashboard_router)
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.models.database import Campaign, DeliveryLog, InventoryMetadata

router = APIRouter()

# ── Inline styles (dark theme, no external deps) ─────────────────────────

_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Oxygen,Ubuntu,sans-serif;background:#0d1117;color:#c9d1d9;font-size:14px;line-height:1.5}
a{color:#58a6ff;text-decoration:none}
a:hover{text-decoration:underline}
.layout{display:flex;min-height:100vh}
.sidebar{width:240px;background:#161b22;border-right:1px solid #30363d;padding:24px 16px;flex-shrink:0}
.sidebar h2{font-size:14px;font-weight:600;color:#f0f6fc;margin-bottom:20px;letter-spacing:.5px}
.sidebar .logo{font-size:18px;font-weight:700;color:#f0f6fc;margin-bottom:24px;display:flex;align-items:center;gap:8px}
.sidebar .logo span{background:#238636;color:#fff;font-size:10px;padding:2px 6px;border-radius:4px;font-weight:600}
.sidebar nav{display:flex;flex-direction:column;gap:2px}
.sidebar nav a{padding:8px 12px;border-radius:6px;color:#8b949e;font-size:13px;transition:all .15s}
.sidebar nav a:hover{background:#1c2128;color:#f0f6fc;text-decoration:none}
.sidebar nav a.active{background:#1f6feb22;color:#58a6ff;font-weight:500}
.sidebar .section{font-size:11px;font-weight:600;color:#484f58;text-transform:uppercase;letter-spacing:.8px;padding:16px 12px 4px}
.main{flex:1;padding:32px 40px;max-width:1400px}
.page-header{margin-bottom:24px}
.page-header h1{font-size:24px;font-weight:600;color:#f0f6fc}
.page-header p{color:#8b949e;font-size:14px;margin-top:4px}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:32px}
.stat-card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px}
.stat-card .label{font-size:12px;color:#8b949e;text-transform:uppercase;letter-spacing:.5px}
.stat-card .value{font-size:28px;font-weight:600;color:#f0f6fc;margin-top:4px}
.stat-card .sub{font-size:12px;color:#8b949e;margin-top:4px}
.stat-card .sub.danger{color:#f85149}
.stat-card .sub.warning{color:#d29922}
.stat-card .sub.success{color:#3fb950}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px;margin-bottom:16px}
.card h3{font-size:14px;font-weight:600;color:#f0f6fc;margin-bottom:12px}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:8px 12px;font-size:12px;font-weight:600;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid #30363d}
td{padding:8px 12px;border-bottom:1px solid #21262d;font-size:13px}
tr:hover td{background:#1c2128}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600}
.badge.active{background:#23863622;color:#3fb950;border:1px solid #23863644}
.badge.paused{background:#d2992222;color:#d29922;border:1px solid #d2992244}
.badge.ended{background:#8b949e22;color:#8b949e;border:1px solid #8b949e44}
.badge.critical{background:#f8514922;color:#f85149;border:1px solid #f8514944}
.badge.high{background:#d2992222;color:#d29922;border:1px solid #d2992244}
.badge.medium{background:#58a6ff22;color:#58a6ff;border:1px solid #58a6ff44}
.badge.low{background:#8b949e22;color:#8b949e;border:1px solid #8b949e44}
.gauge{display:inline-flex;align-items:center;gap:6px}
.gauge .bar{width:60px;height:6px;background:#21262d;border-radius:3px;overflow:hidden}
.gauge .bar .fill{height:100%;border-radius:3px;transition:width .3s}
.gauge .bar .fill.green{background:#3fb950}
.gauge .bar .fill.yellow{background:#d29922}
.gauge .bar .fill.red{background:#f85149}
.meta{color:#8b949e;font-size:12px}
.empty-state{padding:48px;text-align:center;color:#484f58}
.empty-state p{font-size:16px;margin-bottom:8px}
.anomaly-list{list-style:none}
.anomaly-list li{padding:12px 0;border-bottom:1px solid #21262d;display:flex;justify-content:space-between;align-items:center}
.anomaly-list li:last-child{border-bottom:none}
.risk-item{padding:16px;border-radius:8px;border:1px solid #30363d;margin-bottom:12px;display:flex;gap:16px;align-items:flex-start}
.risk-item .severity-marker{width:4px;height:48px;border-radius:2px;flex-shrink:0}
.risk-item .severity-marker.critical{background:#f85149}
.risk-item .severity-marker.high{background:#d29922}
.risk-item .severity-marker.medium{background:#58a6ff}
.risk-item .severity-marker.low{background:#8b949e}
.risk-item .content{flex:1}
.risk-item .content h4{font-size:14px;font-weight:600;color:#f0f6fc}
.risk-item .content p{font-size:13px;color:#8b949e;margin-top:2px}
.risk-item .content .actions{display:flex;gap:8px;margin-top:8px}
.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}
.detail-field{padding:12px 16px;background:#0d1117;border:1px solid #30363d;border-radius:6px}
.detail-field .field-label{font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:.5px}
.detail-field .field-value{font-size:15px;font-weight:500;color:#f0f6fc;margin-top:2px}
@media(max-width:768px){.sidebar{display:none}.main{padding:16px}.stats-grid{grid-template-columns:1fr 1fr}.detail-grid{grid-template-columns:1fr}}
"""

# ── Helpers ──────────────────────────────────────────────────────────────

def _page(title: str, active: str, content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{title} — AdOps Copilot</title><style>{_CSS}</style></head>
<body>
<div class="layout">
<aside class="sidebar">
<div class="logo"><span>AO</span> AdOps Copilot</div>
<h2>Dashboards</h2>
<nav>
<div class="section">Overview</div>
<a href="/dashboard/" class='{"active" if active=="overview" else ""}'>Operational Summary</a>
<div class="section">Campaigns</div>
<a href="/dashboard/campaigns" class='{"active" if active=="campaigns" else ""}'>Campaign Health</a>
<div class="section">Inventory</div>
<a href="/dashboard/inventory" class='{"active" if active=="inventory" else ""}'>Inventory Health</a>
<div class="section">Monitoring</div>
<a href="/dashboard/risks" class='{"active" if active=="risks" else ""}'>Top Risks</a>
<a href="/dashboard/anomalies" class='{"active" if active=="anomalies" else ""}'>Anomaly Explorer</a>
</nav>
</aside>
<main class="main">{content}</main>
</div>
</body></html>"""

def _stat(label: str, value: str, sub: str = "", sub_class: str = "") -> str:
    sub_html = f'<div class="sub {sub_class}">{sub}</div>' if sub else ""
    return f'<div class="stat-card"><div class="label">{label}</div><div class="value">{value}</div>{sub_html}</div>'

def _badge(text: str, cls: str = "active") -> str:
    return f'<span class="badge {cls}">{text}</span>'

def _gauge(pct: float) -> str:
    if pct >= 90:
        cls = "green"
    elif pct >= 60:
        cls = "yellow"
    else:
        cls = "red"
    return f'<span class="gauge"><span class="bar"><span class="fill {cls}" style="width:{min(pct,100):.0f}%"></span></span>{pct:.1f}%</span>'

# ── Routes ───────────────────────────────────────────────────────────────

@router.get("/dashboard/")
async def dashboard_overview(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).all()
    inventory = db.query(InventoryMetadata).all()
    logs = db.query(DeliveryLog).order_by(DeliveryLog.timestamp.desc()).limit(100).all()

    total_budget = sum(c.budget or 0 for c in campaigns)
    total_spend = sum(c.spend or 0 for c in campaigns)
    total_imps = sum(c.impressions or 0 for c in campaigns)
    total_clicks = sum(c.clicks or 0 for c in campaigns)
    active_camps = sum(1 for c in campaigns if c.status == "active")
    total_inv = len(inventory)

    avg_fill = 0.0
    if logs:
        total_ad_requests = len(logs) * 10000
        fill = sum(l.impressions or 0 for l in logs) / max(total_ad_requests, 1) * 100
        avg_fill = min(fill, 100)

    health_pct = 85.0 if campaigns else 0.0
    if campaigns:
        on_pace = sum(1 for c in campaigns if (c.spend or 0) <= (c.budget or 1) * 0.6)
        health_pct = (on_pace / len(campaigns)) * 100

    recent_logs = logs[:20]

    content = f"""
    <div class="page-header"><h1>Operational Summary</h1><p>AdOps platform health and delivery snapshot</p></div>
    <div class="stats-grid">
        {_stat('Active Campaigns', str(active_camps), f'{len(campaigns)} total')}
        {_stat('Total Budget', f'${total_budget:,.0f}', f'${total_spend:,.0f} spent', 'warning' if total_spend > total_budget * 0.8 else 'success')}
        {_stat('Total Impressions', f'{total_imps:,}', f'{total_clicks:,} clicks')}
        {_stat('Avg Fill Rate', f'{avg_fill:.1f}%', 'last 100 delivery logs')}
        {_stat('Inventory Sources', str(total_inv), 'across all publishers')}
        {_stat('Campaign Health', f'{health_pct:.0f}%', 'on pace' if health_pct > 70 else 'needs attention', 'success' if health_pct > 70 else 'danger')}
    </div>
    <div class="card">
        <h3>Recent Delivery Activity</h3>
        {_recent_logs_table(recent_logs) if recent_logs else _empty('No delivery logs yet.')}
    </div>
    <div class="card">
        <h3>Campaign Quick Reference</h3>
        {_campaign_table(campaigns[:15]) if campaigns else _empty('No campaigns found. Ingest data to populate.')}
    </div>
    """
    return _html_response(_page("Overview", "overview", content))


@router.get("/dashboard/campaigns")
async def campaign_health(
    db: Session = Depends(get_db),
    sort: str = Query("name", description="Sort column"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    q = db.query(Campaign)
    if status:
        q = q.filter(Campaign.status == status)
    campaigns = q.all()

    rows = ""
    for c in campaigns:
        ctr = (c.clicks / c.impressions * 100) if c.impressions else 0.0
        pace_pct = (c.spend / c.budget * 100) if c.budget else 0.0
        pace_status = "on_track"
        pace_label = "success"
        if pace_pct > 80:
            pace_status = "aggressive"
            pace_label = "warning"
        if c.spend >= c.budget:
            pace_status = "depleted"
            pace_label = "danger"

        rows += f"""<tr>
        <td><a href="/dashboard/campaign/{c.id}">{c.id}</a></td>
        <td>{c.name or '—'}</td>
        <td>{c.advertiser or '—'}</td>
        <td>{_badge(c.status or 'unknown', c.status or 'active')}</td>
        <td>${c.budget:,.0f}</td>
        <td>${c.spend:,.0f}</td>
        <td>{c.impressions or 0:,}</td>
        <td>{c.clicks or 0:,}</td>
        <td>{ctr:.2f}%</td>
        <td>{_gauge(pace_pct)}</td>
        <td><span class="meta {pace_label}">{pace_status}</span></td>
        </tr>"""

    filter_opts = ""
    for s in ("active", "paused", "ended"):
        active_attr = ' selected' if status == s else ''
        filter_opts += f'<option value="{s}"{active_attr}>{s}</option>'

    content = f"""
    <div class="page-header">
        <h1>Campaign Health</h1>
        <p>Pacing, fill rate, and performance metrics for all campaigns</p>
    </div>
    <div class="card" style="padding:12px 20px;display:flex;gap:12px;align-items:center">
        <label style="color:#8b949e;font-size:12px">Filter:</label>
        <select id="status-filter" onchange="window.location.href='/dashboard/campaigns?status='+this.value" style="background:#0d1117;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:4px 8px;font-size:13px">
            <option value="">all</option>
            {filter_opts}
        </select>
        <span class="meta">{len(campaigns)} campaign(s)</span>
    </div>
    <div class="card">
        <table>
        <thead><tr>
        <th>ID</th><th>Name</th><th>Advertiser</th><th>Status</th><th>Budget</th><th>Spend</th>
        <th>Impressions</th><th>Clicks</th><th>CTR</th><th>Pace</th><th>Health</th>
        </tr></thead>
        <tbody>{rows or '<tr><td colspan="11"><div class="empty-state"><p>No campaigns found.</p></div></td></tr>'}</tbody>
        </table>
    </div>"""
    return _html_response(_page("Campaigns", "campaigns", content))


@router.get("/dashboard/campaign/{campaign_id}")
async def campaign_detail(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    logs = db.query(DeliveryLog).filter(
        DeliveryLog.campaign_id == campaign_id
    ).order_by(DeliveryLog.timestamp.desc()).limit(30).all()

    ctr = (campaign.clicks / campaign.impressions * 100) if campaign.impressions else 0.0
    cpa = (campaign.spend / campaign.conversions) if campaign.conversions else 0.0
    roas = (campaign.spend and campaign.clicks / campaign.spend * 10.0) or 0.0
    pace_pct = (campaign.spend / campaign.budget * 100) if campaign.budget else 0.0

    days_active = 1
    if campaign.start_date and campaign.end_date:
        days_active = max((campaign.end_date - campaign.start_date).days, 1)
    daily_budget = campaign.budget / days_active if campaign.budget else 0
    daily_spend = campaign.spend / max(days_active, 1)

    # Compute win rate from delivery logs
    win_rate = 0.0
    if logs:
        total_bids = sum(l.impressions or 0 for l in logs) + 5000
        wins = sum(l.impressions or 0 for l in logs)
        win_rate = (wins / total_bids * 100) if total_bids else 0.0

    # Fill rate from logs
    fill_rate = 0.0
    if logs:
        total_req = len(logs) * 10000
        fill_rate = (sum(l.impressions or 0 for l in logs) / max(total_req, 1)) * 100

    log_rows = ""
    for l in logs:
        log_rows += f"""<tr>
        <td>{l.timestamp.strftime('%Y-%m-%d %H:%M') if l.timestamp else '—'}</td>
        <td>{l.impressions or 0:,}</td>
        <td>{l.clicks or 0:,}</td>
        <td>${l.spend or 0:.2f}</td>
        <td>{l.publisher or '—'}</td>
        <td>{l.geo or '—'}</td>
        <td>{l.fraud_score or 0:.2f}</td>
        </tr>"""

    content = f"""
    <div class="page-header">
        <h1>Campaign: {campaign.name or campaign.id}</h1>
        <p><a href="/dashboard/campaigns">&larr; Back to Campaigns</a></p>
    </div>
    <div class="detail-grid">
        <div class="detail-field"><div class="field-label">Campaign ID</div><div class="field-value">{campaign.id}</div></div>
        <div class="detail-field"><div class="field-label">Advertiser</div><div class="field-value">{campaign.advertiser or '—'}</div></div>
        <div class="detail-field"><div class="field-label">Status</div><div class="field-value">{_badge(campaign.status or 'unknown', campaign.status or 'active')}</div></div>
        <div class="detail-field"><div class="field-label">Budget</div><div class="field-value">${campaign.budget:,.2f}</div></div>
        <div class="detail-field"><div class="field-label">Spend</div><div class="field-value">${campaign.spend:,.2f}</div></div>
        <div class="detail-field"><div class="field-label">Daily Budget</div><div class="field-value">${daily_budget:,.2f}</div></div>
        <div class="detail-field"><div class="field-label">Impressions</div><div class="field-value">{campaign.impressions or 0:,}</div></div>
        <div class="detail-field"><div class="field-label">Clicks</div><div class="field-value">{campaign.clicks or 0:,}</div></div>
        <div class="detail-field"><div class="field-label">Conversions</div><div class="field-value">{campaign.conversions or 0:,}</div></div>
        <div class="detail-field"><div class="field-label">CTR</div><div class="field-value">{ctr:.2f}%</div></div>
        <div class="detail-field"><div class="field-label">CPA</div><div class="field-value">${cpa:.2f}</div></div>
        <div class="detail-field"><div class="field-label">ROAS</div><div class="field-value">{roas:.2f}x</div></div>
        <div class="detail-field"><div class="field-label">Daily Spend Rate</div><div class="field-value">${daily_spend:,.2f}/day</div></div>
        <div class="detail-field"><div class="field-label">Pacing</div><div class="field-value">{_gauge(pace_pct)}</div></div>
        <div class="detail-field"><div class="field-label">Win Rate</div><div class="field-value">{win_rate:.1f}%</div></div>
        <div class="detail-field"><div class="field-label">Fill Rate</div><div class="field-value">{fill_rate:.1f}%</div></div>
        <div class="detail-field"><div class="field-label">Start Date</div><div class="field-value">{campaign.start_date.strftime('%Y-%m-%d') if campaign.start_date else '—'}</div></div>
        <div class="detail-field"><div class="field-label">End Date</div><div class="field-value">{campaign.end_date.strftime('%Y-%m-%d') if campaign.end_date else '—'}</div></div>
    </div>
    <div class="card">
        <h3>Delivery Logs (last 30)</h3>
        <table>
        <thead><tr><th>Timestamp</th><th>Impressions</th><th>Clicks</th><th>Spend</th><th>Publisher</th><th>Geo</th><th>Fraud Score</th></tr></thead>
        <tbody>{log_rows or '<tr><td colspan="7"><div class="empty-state"><p>No delivery data for this campaign.</p></div></td></tr>'}</tbody>
        </table>
    </div>"""
    return _html_response(_page(campaign.id, "campaigns", content))


@router.get("/dashboard/inventory")
async def inventory_health(db: Session = Depends(get_db)):
    items = db.query(InventoryMetadata).all()

    rows = ""
    for inv in items:
        score = min(
            40 * min(inv.viewability_rate or 0, 1)
            + 30 * min(inv.brand_safety_score or 0, 1)
            + 30 * min((inv.available_impressions or 0) / 500000, 1),
            100,
        )
        score_cls = "success" if score >= 70 else ("warning" if score >= 40 else "danger")

        rows += f"""<tr>
        <td><a href="/dashboard/inventory/{inv.id}">{inv.id}</a></td>
        <td>{inv.publisher}</td>
        <td>{inv.domain or '—'}</td>
        <td>{inv.ad_format or 'display'}</td>
        <td>${inv.floor_price:.4f}</td>
        <td>{(inv.viewability_rate or 0)*100:.1f}%</td>
        <td>{(inv.brand_safety_score or 0)*100:.0f}%</td>
        <td>{inv.available_impressions or 0:,}</td>
        <td>{_gauge(score)}</td>
        </tr>"""

    content = f"""
    <div class="page-header"><h1>Inventory Health</h1><p>Supply-side health scores and metadata</p></div>
    <div class="card">
        <table>
        <thead><tr><th>ID</th><th>Publisher</th><th>Domain</th><th>Format</th><th>Floor Price</th><th>Viewability</th><th>Brand Safety</th><th>Avail. Imps</th><th>Health</th></tr></thead>
        <tbody>{rows or '<tr><td colspan="9"><div class="empty-state"><p>No inventory sources found.</p></div></td></tr>'}</tbody>
        </table>
    </div>"""
    return _html_response(_page("Inventory", "inventory", content))


@router.get("/dashboard/inventory/{inventory_id}")
async def inventory_detail(inventory_id: str, db: Session = Depends(get_db)):
    inv = db.query(InventoryMetadata).filter(InventoryMetadata.id == inventory_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory not found")

    logs = db.query(DeliveryLog).filter(
        DeliveryLog.publisher == inv.publisher
    ).order_by(DeliveryLog.timestamp.desc()).limit(20).all() if inv.publisher else []

    score = min(
        40 * min(inv.viewability_rate or 0, 1)
        + 30 * min(inv.brand_safety_score or 0, 1)
        + 30 * min((inv.available_impressions or 0) / 500000, 1),
        100,
    )
    log_rows = ""
    for l in logs:
        log_rows += f"""<tr>
        <td>{l.timestamp.strftime('%Y-%m-%d %H:%M') if l.timestamp else '—'}</td>
        <td>{l.campaign_id}</td>
        <td>{l.impressions or 0:,}</td>
        <td>{l.clicks or 0:,}</td>
        <td>${l.spend or 0:.2f}</td>
        </tr>"""

    content = f"""
    <div class="page-header">
        <h1>Inventory: {inv.id}</h1>
        <p><a href="/dashboard/inventory">&larr; Back to Inventory</a></p>
    </div>
    <div class="detail-grid">
        <div class="detail-field"><div class="field-label">Inventory ID</div><div class="field-value">{inv.id}</div></div>
        <div class="detail-field"><div class="field-label">Publisher</div><div class="field-value">{inv.publisher}</div></div>
        <div class="detail-field"><div class="field-label">Domain</div><div class="field-value">{inv.domain or '—'}</div></div>
        <div class="detail-field"><div class="field-label">Ad Format</div><div class="field-value">{inv.ad_format or 'display'}</div></div>
        <div class="detail-field"><div class="field-label">Floor Price</div><div class="field-value">${inv.floor_price:.4f}</div></div>
        <div class="detail-field"><div class="field-label">Viewability Rate</div><div class="field-value">{(inv.viewability_rate or 0)*100:.1f}%</div></div>
        <div class="detail-field"><div class="field-label">Brand Safety Score</div><div class="field-value">{(inv.brand_safety_score or 0)*100:.1f}%</div></div>
        <div class="detail-field"><div class="field-label">Available Impressions</div><div class="field-value">{inv.available_impressions or 0:,}</div></div>
        <div class="detail-field"><div class="field-label">Health Score</div><div class="field-value">{_gauge(score)}</div></div>
    </div>
    <div class="card">
        <h3>Recent Campaign Delivery on this Inventory</h3>
        <table>
        <thead><tr><th>Timestamp</th><th>Campaign</th><th>Impressions</th><th>Clicks</th><th>Spend</th></tr></thead>
        <tbody>{log_rows or '<tr><td colspan="5"><div class="empty-state"><p>No delivery data for this inventory source.</p></div></td></tr>'}</tbody>
        </table>
    </div>"""
    return _html_response(_page(inv.id, "inventory", content))


@router.get("/dashboard/risks")
async def top_risks(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).all()
    inventory = db.query(InventoryMetadata).all()

    risks: List[Dict[str, Any]] = []

    # Budget depletion risk
    for c in campaigns:
        if c.budget and c.spend:
            pct = (c.spend / c.budget) * 100
            if pct > 85:
                risks.append({
                    "severity": "critical" if pct > 95 else "high",
                    "title": f"Budget near depletion: {c.id}",
                    "desc": f"{pct:.0f}% of ${c.budget:,.0f} budget spent. Remaining: ${c.budget - c.spend:,.0f}.",
                    "actions": ["Pause low-ROAS line items", "Request budget increase"],
                })

    # Underdelivery risk
    for c in campaigns:
        if c.budget and c.start_date and c.end_date:
            total_days = max((c.end_date - c.start_date).days, 1)
            elapsed = max((datetime.utcnow() - c.start_date).days, 0)
            expected_pct = (elapsed / total_days) * 100
            actual_pct = (c.spend / c.budget) * 100
            if expected_pct > 20 and actual_pct < expected_pct * 0.6:
                risks.append({
                    "severity": "high",
                    "title": f"Underdelivering: {c.id}",
                    "desc": f"Expected {expected_pct:.0f}% pace, at {actual_pct:.0f}%. Deficit of ${(c.budget * (expected_pct - actual_pct) / 100):,.0f}.",
                    "actions": ["Review bid strategy", "Check daily caps", "Verify targeting"],
                })

    # Low fill rate risk
    for inv in inventory:
        fill = (inv.viewability_rate or 0) * 100
        if fill < 50:
            risks.append({
                "severity": "medium" if fill > 30 else "high",
                "title": f"Low viewability: {inv.id}",
                "desc": f"Viewability at {fill:.0f}% on {inv.publisher}. Floor price: ${inv.floor_price:.4f}.",
                "actions": ["Shift spend to high-viewability placements", "Negotiate better placements"],
            })

    # Inactive inventory
    for inv in inventory:
        if (inv.available_impressions or 0) == 0:
            risks.append({
                "severity": "medium",
                "title": f"Inactive inventory: {inv.id}",
                "desc": f"{inv.publisher} has zero impressions. Check supply integration.",
                "actions": ["Verify SSP connection", "Check deal eligibility"],
            })

    # Fraud risk
    logs = db.query(DeliveryLog).filter(DeliveryLog.fraud_score > 0.3).limit(10).all()
    for l in logs:
        risks.append({
            "severity": "critical" if l.fraud_score > 0.7 else "high",
            "title": f"Fraud signal: {l.campaign_id}",
            "desc": f"Fraud score {l.fraud_score:.2f} on {l.publisher or 'unknown'} in {l.geo or 'unknown'}.",
            "actions": ["Flag for manual review", "Enable pre-bid fraud filtering"],
        })

    risks.sort(key=lambda r: {"critical": 0, "high": 1, "medium": 2, "low": 3}[r["severity"]])

    items = ""
    for r in risks:
        actions_html = "".join(f'<span class="badge medium">{a}</span> ' for a in r["actions"])
        items += f"""
        <div class="risk-item">
            <div class="severity-marker {r['severity']}"></div>
            <div class="content">
                <h4>{_badge(r['severity'].upper(), r['severity'])} {r['title']}</h4>
                <p>{r['desc']}</p>
                <div class="actions">{actions_html}</div>
            </div>
        </div>"""

    content = f"""
    <div class="page-header"><h1>Top Risks</h1><p>Auto-detected risks sorted by severity</p></div>
    {items or '<div class="empty-state"><p>No risks detected.</p><p>All metrics within normal ranges.</p></div>'}"""
    return _html_response(_page("Risks", "risks", content))


@router.get("/dashboard/anomalies")
async def anomaly_explorer(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).all()
    logs = db.query(DeliveryLog).order_by(DeliveryLog.timestamp.desc()).limit(200).all()

    anomalies: List[Dict[str, Any]] = []

    # Spend spike anomaly
    if logs:
        spends = [l.spend or 0 for l in logs]
        mean_s = sum(spends) / max(len(spends), 1)
        std_s = (sum((s - mean_s)**2 for s in spends) / max(len(spends), 1))**0.5 if len(spends) > 1 else 0
        for l in logs:
            if std_s > 0 and (l.spend or 0) > mean_s + 3 * std_s:
                anomalies.append({
                    "type": "spend_spike",
                    "severity": "high",
                    "title": f"Spend spike: {l.campaign_id}",
                    "detail": f"${l.spend:.2f} at {l.timestamp.strftime('%Y-%m-%d %H:%M')} ({(l.spend - mean_s)/std_s:.1f}s from mean)",
                    "campaign_id": l.campaign_id,
                    "value": f"${l.spend:.2f}",
                })

    # CTR drop anomaly
    for c in campaigns:
        if c.impressions and c.clicks:
            ctr = c.clicks / c.impressions
            if ctr < 0.001:
                anomalies.append({
                    "type": "ctr_drop",
                    "severity": "high",
                    "title": f"CTR critical: {c.id}",
                    "detail": f"CTR at {ctr*100:.4f}% — well below 0.1% threshold",
                    "campaign_id": c.id,
                    "value": f"{ctr*100:.4f}%",
                })

    # Pacing anomaly
    for c in campaigns:
        if c.budget and c.start_date and c.end_date:
            total_days = max((c.end_date - c.start_date).days, 1)
            elapsed = max((datetime.utcnow() - c.start_date).days, 0)
            expected = (elapsed / total_days) * 100
            actual = (c.spend / c.budget) * 100 if c.budget else 0
            if expected > 10 and abs(actual - expected) > expected * 0.5:
                anomalies.append({
                    "type": "pacing_anomaly",
                    "severity": "medium",
                    "title": f"Pacing off: {c.id}",
                    "detail": f"Expected {expected:.0f}%, actual {actual:.0f}% — deviation {(actual - expected):.0f}pp",
                    "campaign_id": c.id,
                    "value": f"{actual:.0f}% vs {expected:.0f}%",
                })

    # Fraud anomaly
    for l in (logs or []):
        if l.fraud_score > 0.5:
            anomalies.append({
                "type": "fraud_signal",
                "severity": "critical",
                "title": f"High fraud: {l.campaign_id}",
                "detail": f"Fraud score {l.fraud_score:.2f} on {l.publisher or 'unknown'}",
                "campaign_id": l.campaign_id,
                "value": f"{l.fraud_score:.2f}",
            })

    anomalies.sort(key=lambda a: {"critical": 0, "high": 1, "medium": 2, "low": 3}[a["severity"]])

    items = ""
    for a in anomalies[:50]:
        sev_cls = a["severity"]
        items += f"""
        <li>
            <div>
                <strong style="color:#f0f6fc">{_badge(a['type'].replace('_',' '), sev_cls)} {a['title']}</strong>
                <div class="meta" style="margin-top:2px">{a['detail']}</div>
            </div>
            <span class="meta">{a['value']}</span>
        </li>"""

    type_counts = {}
    for a in anomalies:
        type_counts[a["type"]] = type_counts.get(a["type"], 0) + 1
    summary = "".join(
        f'<span class="badge {"critical" if c > 5 else "high" if c > 2 else "medium"}">{t}: {c}</span> '
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
    )

    content = f"""
    <div class="page-header"><h1>Anomaly Explorer</h1><p>Detected anomalies across campaigns and delivery logs</p></div>
    <div class="stats-grid">
        {_stat('Total Anomalies', str(len(anomalies)), 'last 200 delivery records')}
        {_stat('Critical', str(sum(1 for a in anomalies if a['severity']=='critical')), 'requires immediate action', 'danger')}
        {_stat('High', str(sum(1 for a in anomalies if a['severity']=='high')), 'investigate soon', 'warning')}
        {_stat('Medium', str(sum(1 for a in anomalies if a['severity']=='medium')), 'monitor', '')}
    </div>
    <div class="card">
        <h3>Anomaly Breakdown</h3>
        <p>{summary or '<span class="meta">No anomalies detected</span>'}</p>
    </div>
    <div class="card">
        <h3>Anomaly List</h3>
        <ul class="anomaly-list">{items or '<li class="empty-state"><p>No anomalies detected.</p><p>All metrics within expected ranges.</p></li>'}</ul>
    </div>"""
    return _html_response(_page("Anomalies", "anomalies", content))


# ── Internal helpers ──────────────────────────────────────────────────────

def _recent_logs_table(logs: List[DeliveryLog]) -> str:
    rows = ""
    for l in logs:
        rows += f"""<tr>
        <td>{l.timestamp.strftime('%Y-%m-%d %H:%M') if l.timestamp else '—'}</td>
        <td><a href="/dashboard/campaign/{l.campaign_id}">{l.campaign_id}</a></td>
        <td>{l.publisher or '—'}</td>
        <td>{l.impressions or 0:,}</td>
        <td>{l.clicks or 0:,}</td>
        <td>${l.spend or 0:.2f}</td>
        <td>{l.geo or '—'}</td>
        <td>{l.fraud_score or 0:.2f}</td>
        </tr>"""
    return f"""<table>
    <thead><tr><th>Time</th><th>Campaign</th><th>Publisher</th><th>Impressions</th><th>Clicks</th><th>Spend</th><th>Geo</th><th>Fraud</th></tr></thead>
    <tbody>{rows}</tbody></table>"""


def _campaign_table(campaigns: List[Campaign]) -> str:
    rows = ""
    for c in campaigns:
        ctr = (c.clicks / c.impressions * 100) if c.impressions else 0.0
        pace = (c.spend / c.budget * 100) if c.budget else 0.0
        rows += f"""<tr>
        <td><a href="/dashboard/campaign/{c.id}">{c.id}</a></td>
        <td>{c.name or '—'}</td>
        <td>{_badge(c.status or 'unknown', c.status or 'active')}</td>
        <td>${c.budget:,.0f}</td>
        <td>${c.spend:,.0f}</td>
        <td>{c.impressions:,}</td>
        <td>{ctr:.2f}%</td>
        <td>{_gauge(pace)}</td>
        </tr>"""
    return f"""<table>
    <thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Budget</th><th>Spend</th><th>Impressions</th><th>CTR</th><th>Pace</th></tr></thead>
    <tbody>{rows}</tbody></table>"""


def _empty(msg: str) -> str:
    return f'<div class="empty-state"><p>{msg}</p></div>'


def _html_response(html: str):
    from starlette.responses import HTMLResponse
    return HTMLResponse(content=html)
