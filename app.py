"""
Project Budget Assumption — Budget & Cost Tracker
RelleT Consulting Inc. | Version: 1.1.0
"""
import json

import pandas as pd
import streamlit as st
from supabase import Client, create_client

st.set_page_config(
    page_title="Project Budget Assumption — RelleT",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Brand palette
NAVY = "#1F2933"
TEAL = "#00A6A6"
SLATE = "#4B5563"
GREEN = "#047857"
RED = "#B91C1C"
YELLOW = "#D97706"

LOGO = (
    '<svg width="42" height="42" viewBox="0 0 42 42" xmlns="http://www.w3.org/2000/svg">'
    '<defs><linearGradient id="rG" x1="0%" y1="0%" x2="100%" y2="100%">'
    '<stop offset="0%" style="stop-color:#00A6A6"/>'
    '<stop offset="100%" style="stop-color:#007a7a"/>'
    '</linearGradient></defs>'
    '<rect width="42" height="42" rx="10" fill="url(#rG)"/>'
    '<path d="M11 9h12c4 0 7 2.5 7 6.5 0 3-2 5.5-5 6.2l6 10.3h-5.5l-5.5-9.5h-4v9.5h-5V9zm5 4v6h6c2.2 0 3.5-1.2 3.5-3s-1.3-3-3.5-3h-6z" fill="white"/>'
    '<circle cx="34" cy="32" r="5" fill="#D4AF37"/>'
    '<text x="34" y="35" text-anchor="middle" font-size="6" fill="#1A2B3C" font-weight="bold">$</text>'
    '</svg>'
)
LOGO_LG = LOGO.replace('width="42"', 'width="80"').replace('height="42"', 'height="80"')

st.markdown(
    f"""<style>
.main-title{{color:{NAVY};font-size:2rem;font-weight:700;margin-bottom:0.25rem}}
.sub-title{{color:{SLATE};font-size:1rem;margin-bottom:1.5rem}}
.kpi-card{{background:#f8fafc;border-radius:12px;padding:1.25rem;text-align:center;border-left:4px solid {TEAL}}}
.kpi-value{{font-size:1.75rem;font-weight:700;color:{NAVY}}}
.kpi-label{{font-size:0.85rem;color:{SLATE};margin-top:0.25rem}}
.section-header{{color:{NAVY};font-size:1.25rem;font-weight:600;border-bottom:2px solid {TEAL};padding-bottom:0.5rem;margin:1.5rem 0 1rem}}
div[data-testid="stSidebar"]{{background-color:#f1f5f9}}
</style>""",
    unsafe_allow_html=True,
)


# ---------- Supabase clients (lazy, import-safe) ----------
@st.cache_resource
def get_client() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])


@st.cache_resource
def get_admin() -> Client:
    return create_client(
        st.secrets["supabase"]["url"], st.secrets["supabase"]["service_role_key"]
    )


def sb() -> Client:
    return get_client()


def sb_admin() -> Client:
    return get_admin()


# ---------- Session ----------
_SESSION_DEFAULTS = {
    "authenticated": False,
    "user": None,
    "user_id": None,
    "organization_id": None,
    "organization_name": None,
    "user_role": None,
    "access_token": None,
    "refresh_token": None,
}


def init_session():
    for k, v in _SESSION_DEFAULTS.items():
        st.session_state.setdefault(k, v)


def authenticate(email, password):
    try:
        r = sb().auth.sign_in_with_password({"email": email, "password": password})
        if not r.user or not r.session:
            return False
        st.session_state.user = r.user
        st.session_state.user_id = r.user.id
        st.session_state.access_token = r.session.access_token
        st.session_state.refresh_token = r.session.refresh_token
        mem = (
            sb_admin()
            .table("organization_members")
            .select("organization_id, role, organizations(name)")
            .eq("user_id", r.user.id)
            .limit(1)
            .execute()
        )
        if mem.data and mem.data[0].get("organization_id"):
            row = mem.data[0]
            st.session_state.organization_id = row["organization_id"]
            st.session_state.user_role = row["role"]
            st.session_state.organization_name = (row.get("organizations") or {}).get(
                "name", "Organization"
            )
            st.session_state.authenticated = True
            return True
        st.error("No organization membership found.")
        return False
    except Exception as e:
        st.error(f"Auth failed: {e}")
        return False


def logout():
    try:
        sb().auth.sign_out()
    except Exception:
        pass
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    init_session()
    st.rerun()


def get_org_id():
    v = st.session_state.get("organization_id")
    return str(v) if v else ""


def require_org_id():
    oid = get_org_id()
    if not oid:
        st.error("Organization context not loaded. Sign out and sign in again.")
        st.stop()
    return oid


# ---------- Formatting ----------
def fmt_currency(v):
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def fmt_pct(v):
    """Format a value as a percentage. Values in [0, 1] are treated as fractions;
    values > 1 are treated as already being in percent units."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "0.0%"
    pct = x * 100 if x <= 1 else x
    return f"{pct:.1f}%"


def as_pct(v):
    """Return numeric percent value (0-100) from a fraction or percent input."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return x * 100 if x <= 1 else x


def kpi_card(label, value, color=TEAL):
    st.markdown(
        f'<div class="kpi-card" style="border-left-color:{color}">'
        f'<div class="kpi-value" style="color:{color}">{value}</div>'
        f'<div class="kpi-label">{label}</div></div>',
        unsafe_allow_html=True,
    )


# ---------- Data fetchers (cached) ----------
def _attach_project_name(df: pd.DataFrame) -> pd.DataFrame:
    if "pba_budget_reports" in df.columns:
        df["project_name"] = df["pba_budget_reports"].apply(
            lambda x: x.get("project_name", "") if x else ""
        )
    return df


@st.cache_data(ttl=120)
def fetch_reports(_oid):
    r = (
        sb_admin()
        .table("pba_budget_reports")
        .select("*")
        .eq("organization_id", _oid)
        .eq("is_archived", False)
        .order("project_name")
        .execute()
    )
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()


@st.cache_data(ttl=60)
def fetch_invoices(_oid):
    r = (
        sb_admin()
        .table("pba_invoices")
        .select("*, pba_budget_reports(project_name)")
        .eq("organization_id", _oid)
        .eq("is_archived", False)
        .order("invoice_date", desc=True)
        .execute()
    )
    return _attach_project_name(pd.DataFrame(r.data)) if r.data else pd.DataFrame()


@st.cache_data(ttl=60)
def fetch_time_cost(_oid):
    r = (
        sb_admin()
        .table("pba_time_cost")
        .select("*, pba_budget_reports(project_name)")
        .eq("organization_id", _oid)
        .eq("is_archived", False)
        .order("month", desc=True)
        .execute()
    )
    return _attach_project_name(pd.DataFrame(r.data)) if r.data else pd.DataFrame()


@st.cache_data(ttl=60)
def fetch_scenarios(_oid):
    r = (
        sb_admin()
        .table("pba_scenarios")
        .select("*, pba_budget_reports(project_name)")
        .eq("organization_id", _oid)
        .eq("is_archived", False)
        .execute()
    )
    return _attach_project_name(pd.DataFrame(r.data)) if r.data else pd.DataFrame()


def clear_cache():
    fetch_reports.clear()
    fetch_invoices.clear()
    fetch_time_cost.clear()
    fetch_scenarios.clear()


def _num_sum(df: pd.DataFrame, col: str) -> float:
    if df.empty or col not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[col], errors="coerce").sum())


def _num_mean(df: pd.DataFrame, col: str) -> float:
    if df.empty or col not in df.columns:
        return 0.0
    val = pd.to_numeric(df[col], errors="coerce").mean()
    return 0.0 if pd.isna(val) else float(val)


# ============ PAGES ============
def page_dashboard():
    cl, cr = st.columns([1, 10])
    with cl:
        st.markdown(LOGO, unsafe_allow_html=True)
    with cr:
        st.markdown(
            '<div class="main-title">Project Budget Assumption Dashboard</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="sub-title">{st.session_state.organization_name} — Budget & Cost Intelligence</div>',
            unsafe_allow_html=True,
        )

    oid = require_org_id()
    df_r = fetch_reports(oid)
    df_i = fetch_invoices(oid)
    df_t = fetch_time_cost(oid)

    total_budget = _num_sum(df_r, "total_budget")
    cost_to_date = _num_sum(df_r, "cost_to_date")
    remaining = total_budget - cost_to_date
    total_invoiced = _num_sum(df_i, "invoice_amount")
    avg_util = _num_mean(df_t, "utilization")
    total_leakage = _num_sum(df_t, "revenue_leakage")
    burn_pct = (cost_to_date / total_budget * 100) if total_budget > 0 else 0
    util_pct = as_pct(avg_util)

    def burn_color(p):
        return GREEN if p < 70 else (YELLOW if p < 90 else RED)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        kpi_card("Total Budget", fmt_currency(total_budget))
    with c2:
        kpi_card("Cost to Date", fmt_currency(cost_to_date), burn_color(burn_pct))
    with c3:
        kpi_card(
            "Remaining Budget",
            fmt_currency(remaining),
            GREEN if remaining > 0 else RED,
        )
    with c4:
        kpi_card("Total Invoiced", fmt_currency(total_invoiced))
    with c5:
        kpi_card(
            "Avg Utilization", fmt_pct(avg_util), GREEN if util_pct >= 80 else RED
        )
    with c6:
        kpi_card(
            "Revenue Leakage",
            fmt_currency(abs(total_leakage)),
            RED if abs(total_leakage) > 8000 else TEAL,
        )

    st.markdown("---")
    if df_r.empty:
        st.info("No budget reports. Create one via Budget Reports page.")
        return

    st.markdown(
        '<div class="section-header">Budget Summary by Project</div>',
        unsafe_allow_html=True,
    )
    cols = [
        "project_name",
        "total_budget",
        "cost_to_date",
        "total_invoiced",
        "avg_utilization",
        "revenue_leakage",
    ]
    avail = [c for c in cols if c in df_r.columns]
    st.dataframe(
        df_r[avail].rename(
            columns={
                "project_name": "Project",
                "total_budget": "Budget",
                "cost_to_date": "Cost to Date",
                "total_invoiced": "Invoiced",
                "avg_utilization": "Avg Util",
                "revenue_leakage": "Leakage",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )


def page_budget_reports():
    st.markdown('<div class="main-title">📊 Budget Reports</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Project-level budget and cost summary</div>',
        unsafe_allow_html=True,
    )
    oid = require_org_id()
    df = fetch_reports(oid)

    with st.expander("➕ Add Budget Report", expanded=df.empty):
        with st.form("add_report"):
            c1, c2 = st.columns(2)
            with c1:
                pname = st.text_input("Project Name")
                budget = st.number_input(
                    "Total Budget ($)", min_value=0.0, step=100.0, format="%.2f"
                )
            with c2:
                cost = st.number_input(
                    "Cost to Date ($)", min_value=0.0, step=100.0, format="%.2f"
                )
                notes = st.text_area("Notes", height=80)
            submitted = st.form_submit_button("Save Report", use_container_width=True)
            if submitted:
                if not pname.strip():
                    st.warning("Project name is required.")
                else:
                    try:
                        sb_admin().table("pba_budget_reports").insert(
                            {
                                "organization_id": oid,
                                "project_name": pname.strip(),
                                "total_budget": budget,
                                "cost_to_date": cost,
                                "notes": notes or None,
                            }
                        ).execute()
                        st.success(f"Budget report '{pname}' created.")
                        clear_cache()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

    if df.empty:
        return

    st.markdown(
        '<div class="section-header">All Budget Reports</div>', unsafe_allow_html=True
    )
    cols = [
        "project_name",
        "total_budget",
        "cost_to_date",
        "total_invoiced",
        "avg_utilization",
        "revenue_leakage",
        "notes",
    ]
    avail = [c for c in cols if c in df.columns]
    st.dataframe(
        df[avail].rename(
            columns={
                "project_name": "Project",
                "total_budget": "Budget",
                "cost_to_date": "Cost",
                "total_invoiced": "Invoiced",
                "avg_utilization": "Util",
                "revenue_leakage": "Leakage",
                "notes": "Notes",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )


def page_invoices():
    st.markdown('<div class="main-title">🧾 Invoice Data</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Track invoices per project</div>', unsafe_allow_html=True
    )
    oid = require_org_id()
    df_r = fetch_reports(oid)
    df_i = fetch_invoices(oid)
    if df_r.empty:
        st.warning("Create a Budget Report first.")
        return

    report_map = dict(zip(df_r["project_name"], df_r["id"]))
    with st.expander("➕ Add Invoice", expanded=False):
        with st.form("add_inv"):
            c1, c2, c3 = st.columns(3)
            with c1:
                proj = st.selectbox("Project", list(report_map.keys()))
                inv_num = st.text_input("Invoice Number")
            with c2:
                inv_date = st.date_input("Invoice Date")
                amount = st.number_input(
                    "Amount ($)", min_value=0.0, step=100.0, format="%.2f"
                )
            with c3:
                svc_month = st.text_input("Service Month (e.g., March 2025)")
                notes = st.text_input("Notes")
            submitted = st.form_submit_button("Save Invoice", use_container_width=True)
            if submitted:
                if not inv_num.strip():
                    st.warning("Invoice number is required.")
                else:
                    try:
                        sb_admin().table("pba_invoices").insert(
                            {
                                "organization_id": oid,
                                "budget_report_id": report_map[proj],
                                "invoice_number": inv_num.strip(),
                                "invoice_date": inv_date.isoformat(),
                                "invoice_amount": amount,
                                "service_month": svc_month or None,
                                "notes": notes or None,
                            }
                        ).execute()
                        st.success("Invoice saved.")
                        clear_cache()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

    if df_i.empty:
        st.info("No invoices recorded.")
        return

    st.markdown(
        '<div class="section-header">Invoice Records</div>', unsafe_allow_html=True
    )
    cols = [
        "project_name",
        "invoice_number",
        "invoice_date",
        "invoice_amount",
        "service_month",
        "notes",
    ]
    avail = [c for c in cols if c in df_i.columns]
    st.dataframe(
        df_i[avail].rename(
            columns={
                "project_name": "Project",
                "invoice_number": "Invoice #",
                "invoice_date": "Date",
                "invoice_amount": "Amount",
                "service_month": "Service Month",
                "notes": "Notes",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )


def page_time_cost():
    st.markdown(
        '<div class="main-title">⏱️ Time & Cost Tracking</div>', unsafe_allow_html=True
    )
    st.markdown(
        '<div class="sub-title">Weekly hours by role with cost calculation</div>',
        unsafe_allow_html=True,
    )
    oid = require_org_id()
    df_r = fetch_reports(oid)
    df_t = fetch_time_cost(oid)
    if df_r.empty:
        st.warning("Create a Budget Report first.")
        return

    report_map = dict(zip(df_r["project_name"], df_r["id"]))
    with st.expander("➕ Add Time Entry", expanded=False):
        with st.form("add_time"):
            c1, c2, c3 = st.columns(3)
            with c1:
                proj = st.selectbox("Project", list(report_map.keys()), key="tc_proj")
                role = st.text_input("Role")
                month = st.text_input("Month (e.g., March 2025)")
            with c2:
                w1 = st.number_input("Week 1 Hrs", 0.0, step=0.25, format="%.2f")
                w2 = st.number_input("Week 2 Hrs", 0.0, step=0.25, format="%.2f")
                w3 = st.number_input("Week 3 Hrs", 0.0, step=0.25, format="%.2f")
            with c3:
                w4 = st.number_input("Week 4 Hrs", 0.0, step=0.25, format="%.2f")
                w5 = st.number_input("Week 5 Hrs", 0.0, step=0.25, format="%.2f")
                rate = st.number_input(
                    "Hourly Rate ($)", 0.0, step=1.0, format="%.2f"
                )
            target_hrs = st.number_input(
                "Target Hours (for util calc)", 0.0, step=1.0, format="%.2f", value=40.0
            )
            submitted = st.form_submit_button("Save Entry", use_container_width=True)
            if submitted:
                if not role.strip():
                    st.warning("Role is required.")
                else:
                    total = w1 + w2 + w3 + w4 + w5
                    cost = total * rate
                    util = total / target_hrs if target_hrs > 0 else 0
                    diff = util - 0.8
                    leak = diff * rate * target_hrs if diff < 0 else 0
                    try:
                        sb_admin().table("pba_time_cost").insert(
                            {
                                "organization_id": oid,
                                "budget_report_id": report_map[proj],
                                "role": role.strip(),
                                "month": month or None,
                                "week_1_hrs": w1,
                                "week_2_hrs": w2,
                                "week_3_hrs": w3,
                                "week_4_hrs": w4,
                                "week_5_hrs": w5,
                                "total_hours": total,
                                "hourly_rate": rate,
                                "invoice_cost": cost,
                                "utilization": util,
                                "difference_pct": diff,
                                "revenue_leakage": leak,
                            }
                        ).execute()
                        st.success("Time entry saved.")
                        clear_cache()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

    if df_t.empty:
        st.info("No time entries.")
        return

    st.markdown(
        '<div class="section-header">Time & Cost Records</div>', unsafe_allow_html=True
    )
    cols = [
        "project_name",
        "role",
        "month",
        "total_hours",
        "hourly_rate",
        "invoice_cost",
        "utilization",
        "revenue_leakage",
    ]
    avail = [c for c in cols if c in df_t.columns]
    st.dataframe(
        df_t[avail].rename(
            columns={
                "project_name": "Project",
                "role": "Role",
                "month": "Month",
                "total_hours": "Total Hrs",
                "hourly_rate": "Rate",
                "invoice_cost": "Cost",
                "utilization": "Util",
                "revenue_leakage": "Leakage",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )


def page_scenarios():
    st.markdown(
        '<div class="main-title">🔮 Scenario Forecasting</div>', unsafe_allow_html=True
    )
    st.markdown(
        '<div class="sub-title">Model different utilization scenarios</div>',
        unsafe_allow_html=True,
    )
    oid = require_org_id()
    df_r = fetch_reports(oid)
    df_s = fetch_scenarios(oid)
    if df_r.empty:
        st.warning("Create a Budget Report first.")
        return

    report_map = dict(zip(df_r["project_name"], df_r["id"]))
    with st.expander("➕ Add Scenario", expanded=False):
        with st.form("add_scen"):
            c1, c2, c3 = st.columns(3)
            with c1:
                proj = st.selectbox("Project", list(report_map.keys()), key="sc_proj")
                name = st.selectbox(
                    "Scenario",
                    [
                        "100% Utilization",
                        "80% Utilization",
                        "60% Utilization",
                        "Within 6-Month Budget",
                        "Custom",
                    ],
                )
            with c2:
                role = st.text_input("Role")
                util_pct = st.number_input(
                    "Utilization %", 0.0, 100.0, 80.0, step=5.0
                )
            with c3:
                hrs = st.number_input("Hours", 0.0, step=1.0, format="%.2f")
                cost = st.number_input("Cost ($)", 0.0, step=100.0, format="%.2f")
            submitted = st.form_submit_button("Save Scenario", use_container_width=True)
            if submitted:
                if not role.strip():
                    st.warning("Role is required.")
                else:
                    try:
                        sb_admin().table("pba_scenarios").insert(
                            {
                                "organization_id": oid,
                                "budget_report_id": report_map[proj],
                                "scenario_name": name,
                                "utilization_pct": util_pct,
                                "role": role.strip(),
                                "hours": hrs,
                                "cost": cost,
                            }
                        ).execute()
                        st.success("Scenario saved.")
                        clear_cache()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

    if df_s.empty:
        st.info("No scenarios modeled yet.")
        return

    st.markdown(
        '<div class="section-header">Scenario Models</div>', unsafe_allow_html=True
    )
    for sname in df_s["scenario_name"].unique():
        st.markdown(f"**{sname}**")
        subset = df_s[df_s["scenario_name"] == sname]
        cols = ["project_name", "role", "utilization_pct", "hours", "cost"]
        avail = [c for c in cols if c in subset.columns]
        st.dataframe(
            subset[avail].rename(
                columns={
                    "project_name": "Project",
                    "role": "Role",
                    "utilization_pct": "Util %",
                    "hours": "Hours",
                    "cost": "Cost",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )
        total_cost = pd.to_numeric(subset["cost"], errors="coerce").sum()
        st.caption(f"Total Monthly Cost: {fmt_currency(total_cost)}")


def page_settings():
    st.markdown('<div class="main-title">⚙️ Settings</div>', unsafe_allow_html=True)
    oid = require_org_id()
    res = (
        sb_admin()
        .table("pba_settings")
        .select("*")
        .eq("organization_id", oid)
        .limit(1)
        .execute()
    )
    default_settings = {
        "thresholds": {
            "budget_burn": {"green_max": 70, "yellow_max": 90},
            "utilization": {"green_min": 80, "yellow_min": 60},
            "leakage": {"green_max": 2000, "yellow_max": 8000},
        },
        "target_utilization": 80,
    }
    settings = res.data[0] if res.data else default_settings
    raw_th = settings.get("thresholds", {})
    if isinstance(raw_th, dict):
        th = raw_th
    else:
        try:
            th = json.loads(raw_th or "{}")
        except (TypeError, ValueError):
            th = {}

    with st.form("pba_settings"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Budget Burn Thresholds**")
            bg = st.number_input(
                "Green Max %",
                value=float(th.get("budget_burn", {}).get("green_max", 70)),
            )
            by = st.number_input(
                "Yellow Max %",
                value=float(th.get("budget_burn", {}).get("yellow_max", 90)),
            )
        with c2:
            st.markdown("**Utilization Thresholds**")
            ug = st.number_input(
                "Green Min %",
                value=float(th.get("utilization", {}).get("green_min", 80)),
            )
            uy = st.number_input(
                "Yellow Min %",
                value=float(th.get("utilization", {}).get("yellow_min", 60)),
            )
        target = st.number_input(
            "Default Target Utilization %",
            value=float(settings.get("target_utilization", 80)),
        )
        if st.form_submit_button("Save Settings", use_container_width=True):
            new_th = json.dumps(
                {
                    "budget_burn": {"green_max": bg, "yellow_max": by},
                    "utilization": {"green_min": ug, "yellow_min": uy},
                    "leakage": th.get(
                        "leakage", {"green_max": 2000, "yellow_max": 8000}
                    ),
                }
            )
            rec = {
                "organization_id": oid,
                "thresholds": new_th,
                "target_utilization": target,
            }
            try:
                if res.data:
                    sb_admin().table("pba_settings").update(rec).eq(
                        "organization_id", oid
                    ).execute()
                else:
                    sb_admin().table("pba_settings").insert(rec).execute()
                st.success("Settings saved.")
            except Exception as e:
                st.error(f"Failed: {e}")


# ---------- Auth + Navigation ----------
def show_login():
    cl, cr = st.columns([1, 5])
    with cl:
        st.markdown(LOGO_LG, unsafe_allow_html=True)
    with cr:
        st.markdown(
            '<div class="main-title">📈 Project Budget Assumption</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="sub-title">Budget & Cost Tracker — RelleT Consulting</div>',
            unsafe_allow_html=True,
        )
    _, c2, _ = st.columns([1, 2, 1])
    with c2:
        with st.form("login"):
            st.markdown("### Sign In")
            email = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In", use_container_width=True):
                if email and pw:
                    if authenticate(email, pw):
                        st.rerun()
                else:
                    st.warning("Enter email and password.")


def render_sidebar():
    with st.sidebar:
        st.markdown(
            f'<div style="text-align:center;padding:1rem 0">'
            f'<div style="display:flex;justify-content:center;margin-bottom:8px">{LOGO}</div>'
            f'<div style="font-size:1.5rem;font-weight:700;color:{NAVY}">Budget Assumption</div>'
            f'<div style="font-size:0.8rem;color:{SLATE}">RelleT Consulting Inc.</div>'
            f'<div style="font-size:0.7rem;color:{TEAL};margin-top:4px">v1.1.0</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown(f"**{st.session_state.organization_name}**")
        user = st.session_state.get("user")
        email = getattr(user, "email", None) if user is not None else None
        st.caption(email or "")
        st.markdown("---")
        pages = {
            "📈 Dashboard": "dashboard",
            "📊 Budget Reports": "reports",
            "🧾 Invoice Data": "invoices",
            "⏱️ Time & Cost": "time_cost",
            "🔮 Scenarios": "scenarios",
            "⚙️ Settings": "settings",
        }
        sel = st.radio(
            "Navigation",
            list(pages.keys()),
            label_visibility="collapsed",
            key="nav_selection",
        )
        st.markdown("---")
        if st.button("🚪 Sign Out", use_container_width=True):
            logout()
        return pages[sel]


_PAGE_ROUTES = {
    "dashboard": page_dashboard,
    "reports": page_budget_reports,
    "invoices": page_invoices,
    "time_cost": page_time_cost,
    "scenarios": page_scenarios,
    "settings": page_settings,
}


def main():
    init_session()
    if not st.session_state.authenticated:
        show_login()
        return
    page = render_sidebar()
    _PAGE_ROUTES[page]()


if __name__ == "__main__":
    main()
