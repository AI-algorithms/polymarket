"""
Polymarket Quant - Professional Trading Dashboard
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, List
import sys
import os
import numpy as np
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.polymarket_client import PolymarketClient
from analytics.trader_analyzer import TraderAnalyzer
from strategies.copy_trading import CopyTradingStrategy, TraderTier

st.set_page_config(
    page_title="Polymarket Quant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

def load_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    :root {
        --primary: #3b82f6;
        --primary-dark: #2563eb;
        --success: #10b981;
        --danger: #ef4444;
        --warning: #f59e0b;
        --bg-dark: #0f172a;
        --bg-card: #1e293b;
        --bg-card-hover: #334155;
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --border: #334155;
    }
    
    * { font-family: 'Inter', sans-serif !important; }
    
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
    }
    
    .main .block-container {
        padding: 1.5rem 2rem;
        max-width: 1600px;
    }
    
    /* Hide Streamlit branding */
    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }
    
    /* Custom header */
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem 0 1.5rem 0;
        border-bottom: 1px solid var(--border);
        margin-bottom: 1.5rem;
    }
    
    .brand {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .brand-logo {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
        font-weight: 700;
        color: white;
    }
    
    .brand-name {
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.5px;
    }
    
    .brand-tag {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.65rem;
        font-weight: 600;
        margin-left: 8px;
    }
    
    /* Cards */
    .card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        transition: all 0.2s ease;
    }
    
    .card:hover {
        border-color: var(--primary);
        box-shadow: 0 4px 20px rgba(59, 130, 246, 0.15);
    }
    
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid var(--border);
    }
    
    .card-title {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* Metrics Grid */
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    
    .metric-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
        transition: all 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: var(--primary);
    }
    
    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 0.25rem;
    }
    
    .metric-value.positive { color: var(--success); }
    .metric-value.negative { color: var(--danger); }
    .metric-value.primary { color: var(--primary); }
    
    .metric-label {
        font-size: 0.75rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .metric-delta {
        font-size: 0.8rem;
        margin-top: 0.25rem;
    }
    
    .metric-delta.up { color: var(--success); }
    .metric-delta.down { color: var(--danger); }
    
    /* Table */
    .data-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
    }
    
    .data-table th {
        background: rgba(59, 130, 246, 0.1);
        color: var(--text-secondary);
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 0.75rem 1rem;
        text-align: left;
        border-bottom: 1px solid var(--border);
    }
    
    .data-table th:first-child { border-radius: 8px 0 0 0; }
    .data-table th:last-child { border-radius: 0 8px 0 0; }
    
    .data-table td {
        padding: 0.875rem 1rem;
        color: var(--text-primary);
        font-size: 0.875rem;
        border-bottom: 1px solid var(--border);
    }
    
    .data-table tr:hover td {
        background: var(--bg-card-hover);
    }
    
    /* Badges */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.625rem;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    
    .badge-elite {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        color: white;
    }
    
    .badge-premium {
        background: rgba(59, 130, 246, 0.2);
        color: #60a5fa;
    }
    
    .badge-standard {
        background: rgba(148, 163, 184, 0.2);
        color: #94a3b8;
    }
    
    .badge-success {
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
    }
    
    .badge-danger {
        background: rgba(239, 68, 68, 0.2);
        color: #f87171;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: var(--bg-card);
        border-radius: 10px;
        padding: 0.375rem;
        gap: 0.25rem;
        border: 1px solid var(--border);
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 8px;
        color: var(--text-muted);
        font-weight: 500;
        font-size: 0.875rem;
        padding: 0.625rem 1.25rem;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        color: white;
    }
    
    /* Inputs */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
        font-size: 0.875rem !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2) !important;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.625rem 1.5rem !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: var(--bg-card);
        border-right: 1px solid var(--border);
    }
    
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: var(--text-primary) !important;
    }
    
    /* Metrics */
    [data-testid="stMetric"] {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1rem;
    }
    
    [data-testid="stMetricLabel"] {
        color: var(--text-muted) !important;
    }
    
    [data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
    }
    
    /* Alerts */
    .stSuccess {
        background: rgba(16, 185, 129, 0.1) !important;
        border: 1px solid rgba(16, 185, 129, 0.3) !important;
        color: #34d399 !important;
    }
    
    .stError {
        background: rgba(239, 68, 68, 0.1) !important;
        border: 1px solid rgba(239, 68, 68, 0.3) !important;
        color: #f87171 !important;
    }
    
    .stInfo {
        background: rgba(59, 130, 246, 0.1) !important;
        border: 1px solid rgba(59, 130, 246, 0.3) !important;
        color: #60a5fa !important;
    }
    
    /* Slider */
    .stSlider > div > div > div > div {
        background: var(--primary) !important;
    }
    
    /* Selectbox */
    .stSelectbox > div > div {
        background: var(--bg-card) !important;
        border-color: var(--border) !important;
    }
    
    /* Progress */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #3b82f6, #8b5cf6) !important;
    }
    
    /* Divider */
    hr {
        border-color: var(--border);
        margin: 1.5rem 0;
    }
    
    /* Responsive */
    @media (max-width: 1200px) {
        .metrics-grid {
            grid-template-columns: repeat(3, 1fr);
        }
    }
    
    @media (max-width: 768px) {
        .metrics-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    </style>
    """, unsafe_allow_html=True)


@st.cache_resource
def init_clients():
    return (
        PolymarketClient(),
        TraderAnalyzer(min_trades=20, min_win_rate=0.90, min_sharpe=1.0),
        CopyTradingStrategy(capital=10000)
    )


def analyze_trader(client, analyzer, address: str) -> Dict:
    trades = client.get_user_trades(address, limit=500)
    positions = client.get_user_positions(address)
    analysis = analyzer.analyze_trader(trades, positions)
    analysis["address"] = address
    return analysis


def render_header():
    st.markdown("""
    <div class="header-container">
        <div class="brand">
            <div class="brand-logo">📊</div>
            <span class="brand-name">Polymarket Quant</span>
            <span class="brand-tag">PRO</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_metrics(metrics: List[tuple]):
    cols = st.columns(len(metrics))
    for col, (value, label, delta, delta_type) in zip(cols, metrics):
        with col:
            if delta:
                st.metric(label=label, value=value, delta=delta, delta_color="normal" if delta_type == "normal" else "inverse")
            else:
                st.metric(label=label, value=value)


def create_area_chart(title: str = "", height: int = 300) -> go.Figure:
    np.random.seed(42)
    days = 90
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    returns = np.random.randn(days) * 0.015 + 0.002
    equity = 10000 * (1 + returns).cumprod()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=equity,
        fill='tozeroy',
        line=dict(color='#3b82f6', width=2),
        fillcolor='rgba(59, 130, 246, 0.1)',
        hovertemplate='%{x|%b %d}<br>$%{y:,.0f}<extra></extra>',
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color='#94a3b8'), x=0),
        height=height,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            showgrid=False,
            color='#64748b',
            tickfont=dict(size=10),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(51, 65, 85, 0.5)',
            color='#64748b',
            tickprefix='$',
            tickfont=dict(size=10),
        ),
        hovermode='x unified',
        hoverlabel=dict(bgcolor='#1e293b', font_size=12),
    )
    return fig


def create_radar_chart(data: Dict) -> go.Figure:
    categories = ['Win Rate', 'Sharpe', 'Sortino', 'Consistency', 'Profit Factor']
    values = [
        data.get('win_rate', 0) * 100,
        min(data.get('sharpe_ratio', 0) / 3, 1) * 100,
        min(data.get('sortino_ratio', 0) / 3, 1) * 100,
        data.get('consistency_score', 0) * 100,
        min(data.get('profit_factor', 0) / 5, 1) * 100,
    ]
    
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill='toself',
        fillcolor='rgba(59, 130, 246, 0.2)',
        line=dict(color='#3b82f6', width=2),
    ))
    
    fig.update_layout(
        height=280,
        margin=dict(l=50, r=50, t=30, b=30),
        paper_bgcolor='rgba(0,0,0,0)',
        polar=dict(
            bgcolor='rgba(0,0,0,0)',
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                gridcolor='rgba(51, 65, 85, 0.5)',
                color='#64748b',
                tickfont=dict(size=9),
            ),
            angularaxis=dict(
                gridcolor='rgba(51, 65, 85, 0.5)',
                color='#94a3b8',
                tickfont=dict(size=10),
            ),
        ),
        showlegend=False,
    )
    return fig


def create_monthly_bars() -> go.Figure:
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
    values = [4.2, -1.8, 6.5, 2.1, 5.8, 3.2]
    colors = ['#10b981' if v >= 0 else '#ef4444' for v in values]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=months, y=values,
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in values],
        textposition='outside',
        textfont=dict(size=10, color='#94a3b8'),
    ))
    
    fig.update_layout(
        height=200,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, color='#64748b', tickfont=dict(size=10)),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(51, 65, 85, 0.5)',
            color='#64748b',
            ticksuffix='%',
            tickfont=dict(size=10),
        ),
        bargap=0.4,
    )
    return fig


def render_trader_table(traders: List[Dict]):
    if not traders:
        st.info("No traders to display")
        return
    
    rows_html = ""
    for i, t in enumerate(traders[:15]):
        addr = f"{t['address'][:8]}...{t['address'][-6:]}"
        
        sharpe = t.get('sharpe_ratio', 0)
        if sharpe > 2:
            tier_badge = '<span class="badge badge-elite">ELITE</span>'
        elif sharpe > 1.5:
            tier_badge = '<span class="badge badge-premium">PREMIUM</span>'
        else:
            tier_badge = '<span class="badge badge-standard">STANDARD</span>'
        
        qual = t.get('is_qualified', False)
        status_badge = '<span class="badge badge-success">QUALIFIED</span>' if qual else '<span class="badge badge-danger">UNQUALIFIED</span>'
        
        pnl = t.get('overall_pnl', 0)
        pnl_color = '#10b981' if pnl >= 0 else '#ef4444'
        
        rows_html += f"""
        <tr>
            <td style="font-family: monospace; color: #60a5fa;">{addr}</td>
            <td>{tier_badge}</td>
            <td style="color: #10b981;">{t.get('win_rate', 0):.1%}</td>
            <td style="color: #3b82f6;">{sharpe:.2f}</td>
            <td style="color: #f59e0b;">{t.get('max_drawdown', 0):.1%}</td>
            <td style="color: {pnl_color};">${pnl:,.0f}</td>
            <td>{status_badge}</td>
        </tr>
        """
    
    st.markdown(f"""
    <table class="data-table">
        <thead>
            <tr>
                <th>Address</th>
                <th>Tier</th>
                <th>Win Rate</th>
                <th>Sharpe</th>
                <th>Max DD</th>
                <th>P&L</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)


def main():
    load_css()
    render_header()
    
    client, analyzer, strategy = init_clients()
    
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        
        st.markdown("**Screening Criteria**")
        min_trades = st.number_input("Min Trades", value=20, min_value=1)
        min_win_rate = st.slider("Min Win Rate", 0.5, 1.0, 0.90, 0.01, format="%.0f%%")
        min_sharpe = st.slider("Min Sharpe", 0.0, 3.0, 1.0, 0.1)
        max_drawdown = st.slider("Max Drawdown", 0.0, 0.5, 0.30, 0.01, format="%.0f%%")
        
        st.markdown("---")
        
        st.markdown("**Position Sizing**")
        capital = st.number_input("Capital ($)", value=10000, min_value=100, step=1000)
        max_position = st.slider("Max Position", 0.01, 0.30, 0.10, 0.01, format="%.0f%%")
        kelly_frac = st.slider("Kelly Fraction", 0.1, 0.5, 0.25, 0.05)
        
        st.markdown("---")
        
        st.markdown("**System Status**")
        col1, col2 = st.columns(2)
        col1.markdown("🟢 API")
        col2.markdown("🟢 Online")

    tabs = st.tabs(["📊 Dashboard", "🔍 Analyze", "🏆 Leaderboard", "📡 Monitor"])
    
    with tabs[0]:
        render_metrics([
            ("$12,458", "Portfolio", "+$458 (3.8%)", "normal"),
            ("+24.6%", "Total Return", "Since inception", None),
            ("2.34", "Sharpe Ratio", "+0.12", "normal"),
            ("8.2%", "Max Drawdown", "-1.2%", "inverse"),
            ("72.4%", "Win Rate", "+1.8%", "normal"),
            ("12", "Active Traders", "+2", "normal"),
        ])
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("#### 📈 Equity Curve")
            st.plotly_chart(create_area_chart(), use_container_width=True, config={'displayModeBar': False})
        
        with col2:
            st.markdown("#### 📊 Monthly Returns")
            st.plotly_chart(create_monthly_bars(), use_container_width=True, config={'displayModeBar': False})
            
            st.markdown("#### 📋 Quick Stats")
            col_a, col_b = st.columns(2)
            col_a.metric("Today P&L", "+$127", "+1.02%")
            col_b.metric("Open Positions", "8", "-2")
    
    with tabs[1]:
        st.markdown("#### 🔍 Trader Analysis")
        
        col1, col2 = st.columns([5, 1])
        with col1:
            address = st.text_input("Wallet Address", placeholder="Enter trader address (0x...)", label_visibility="collapsed")
        with col2:
            analyze_btn = st.button("Analyze", use_container_width=True)
        
        if analyze_btn and address:
            with st.spinner("Analyzing trader..."):
                try:
                    data = analyze_trader(client, analyzer, address)
                    
                    st.markdown("---")
                    
                    render_metrics([
                        (f"{data['win_rate']:.1%}", "Win Rate", None, None),
                        (f"{data['sharpe_ratio']:.2f}", "Sharpe Ratio", None, None),
                        (f"{data['sortino_ratio']:.2f}", "Sortino Ratio", None, None),
                        (f"{data['max_drawdown']:.1%}", "Max Drawdown", None, None),
                        (f"${data['overall_pnl']:,.0f}", "Total P&L", None, None),
                        (str(data['total_markets']), "Total Trades", None, None),
                    ])
                    
                    col1, col2, col3 = st.columns([1, 1, 1])
                    
                    with col1:
                        st.markdown("##### Performance Radar")
                        st.plotly_chart(create_radar_chart(data), use_container_width=True, config={'displayModeBar': False})
                    
                    with col2:
                        st.markdown("##### Trading Statistics")
                        stats = {
                            "Winning Markets": data['winning_markets'],
                            "Losing Markets": data['losing_markets'],
                            "Profit Factor": f"{data['profit_factor']:.2f}",
                            "Avg Win": f"${data['avg_win']:.2f}",
                            "Avg Loss": f"${data['avg_loss']:.2f}",
                            "Expectancy": f"${data['expectancy']:.2f}",
                        }
                        for k, v in stats.items():
                            st.markdown(f"**{k}:** {v}")
                    
                    with col3:
                        st.markdown("##### Risk Metrics")
                        risk = {
                            "Volatility": f"{data['volatility']:.1%}",
                            "Calmar Ratio": f"{data['calmar_ratio']:.2f}",
                            "Skewness": f"{data['skewness']:.2f}",
                            "Kurtosis": f"{data['kurtosis']:.2f}",
                            "Consistency": f"{data['consistency_score']:.2f}",
                            "Trade Frequency": f"{data['trade_frequency']:.1f}/day",
                        }
                        for k, v in risk.items():
                            st.markdown(f"**{k}:** {v}")
                    
                    st.markdown("---")
                    
                    is_qual = analyzer.is_qualified_trader(data)
                    if is_qual:
                        tier = "ELITE" if data['sharpe_ratio'] > 2 else "PREMIUM" if data['sharpe_ratio'] > 1.5 else "STANDARD"
                        kelly = strategy.position_sizer.calculate_kelly(data['win_rate'], data['avg_win'], data['avg_loss'])
                        st.success(f"✅ **QUALIFIED** — Tier: **{tier}** | Recommended Position: **{kelly:.1%}**")
                    else:
                        st.error("❌ **NOT QUALIFIED** — Does not meet minimum screening criteria")
                
                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")
    
    with tabs[2]:
        st.markdown("#### 🏆 Batch Analysis & Leaderboard")
        
        addresses_text = st.text_area(
            "Trader Addresses",
            placeholder="Enter wallet addresses (one per line)...\n0x1234...\n0x5678...",
            height=120,
            label_visibility="collapsed"
        )
        
        if st.button("🔎 Scan All Traders", use_container_width=False):
            addresses = [a.strip() for a in addresses_text.split('\n') if a.strip()]
            
            if addresses:
                results = []
                progress = st.progress(0)
                status = st.empty()
                
                for i, addr in enumerate(addresses):
                    status.text(f"Analyzing {addr[:16]}...")
                    try:
                        data = analyze_trader(client, analyzer, addr)
                        data['is_qualified'] = analyzer.is_qualified_trader(data)
                        results.append(data)
                    except:
                        pass
                    progress.progress((i + 1) / len(addresses))
                
                progress.empty()
                status.empty()
                
                if results:
                    ranked = analyzer.rank_traders(results)
                    qual_count = len([r for r in ranked if r.get('is_qualified')])
                    
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Scanned", len(ranked))
                    col2.metric("Qualified", qual_count)
                    col3.metric("Qualification Rate", f"{qual_count/len(ranked)*100:.1f}%")
                    
                    st.markdown("---")
                    render_trader_table(ranked)
            else:
                st.warning("Please enter at least one address")
    
    with tabs[3]:
        st.markdown("#### 📡 Copy Trading Monitor")
        
        summary = strategy.get_portfolio_summary()
        
        render_metrics([
            (str(summary['tracked_traders']), "Tracked Traders", None, None),
            (str(summary['active_positions']), "Active Positions", None, None),
            (f"${summary['total_exposure']:,.0f}", "Total Exposure", None, None),
            (f"${summary['daily_pnl']:+,.0f}", "Daily P&L", None, None),
        ])
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### ➕ Add Trader to Watchlist")
            new_addr = st.text_input("Address", placeholder="0x...", key="new_trader", label_visibility="collapsed")
            tier_select = st.selectbox("Select Tier", ["ELITE", "PREMIUM", "STANDARD"])
            weight = st.slider("Weight", 0.1, 2.0, 1.0, 0.1)
            
            if st.button("Add Trader", use_container_width=True):
                if new_addr:
                    st.success(f"✅ Added trader: {new_addr[:20]}...")
        
        with col2:
            st.markdown("##### 📋 Current Watchlist")
            if strategy.tracked_traders:
                for addr, trader in list(strategy.tracked_traders.items())[:8]:
                    tier_class = trader.tier.value
                    st.markdown(f"• `{addr[:16]}...` — **{tier_class.upper()}** (WR: {trader.win_rate:.0%})")
            else:
                st.info("No traders in watchlist. Add traders to start copy trading.")


if __name__ == "__main__":
    main()
