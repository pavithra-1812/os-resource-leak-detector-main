
import io
import html
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from simulator import (
    create_processes,
    tick_processes,
    inject_leak,
    stop_leak,
    get_process_snapshot,
)
from detector import detect_suspicious_growth
from recovery import recover_simulated_process
from real_monitor import get_system_metrics, get_real_processes


# ============================================================
# OPTIONAL PDF SUPPORT
# The app also generates a formatted HTML report if reportlab
# is not installed, so the dashboard remains usable.
# ============================================================
try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    )
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="OS Resource Leak Detector",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# DARK THEME ONLY
# ============================================================
BG = "#0B1120"
SIDEBAR = "#111827"
CARD = "#172033"
TEXT = "#F1F5F9"
MUTED = "#94A3B8"
BORDER = "#293548"
ACCENT = "#22D3EE"
GREEN = "#34D399"
RED = "#F87171"
AMBER = "#FBBF24"

st.markdown(
    f"""
    <style>
    .stApp {{ background: {BG}; color: {TEXT}; }}
    [data-testid="stSidebar"] {{
        background: {SIDEBAR};
        border-right: 1px solid {BORDER};
    }}
    [data-testid="stHeader"] {{ background: {BG}; }}
    h1, h2, h3, h4, p, label,
    [data-testid="stMarkdownContainer"] {{ color: {TEXT}; }}
    [data-testid="stCaptionContainer"],
    [data-testid="stWidgetLabel"] {{ color: {MUTED}; }}
    [data-testid="stMetric"] {{
        background: {CARD};
        border: 1px solid {BORDER};
        padding: 16px;
        border-radius: 12px;
    }}
    [data-testid="stMetricLabel"] {{ color: {MUTED}; }}
    [data-testid="stMetricValue"] {{ color: {TEXT}; }}
    div.stButton > button,
    div[data-testid="stDownloadButton"] > button {{
        background: {CARD};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 9px;
        font-weight: 600;
        min-height: 40px;
    }}
    div.stButton > button:hover,
    div[data-testid="stDownloadButton"] > button:hover {{
        border-color: {ACCENT};
        color: {ACCENT};
    }}
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div {{
        background: {CARD};
        color: {TEXT};
        border-color: {BORDER};
    }}
    [data-testid="stDataFrame"] {{
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}
    .hero {{
        background: linear-gradient(120deg, #111827, #172033);
        border: 1px solid {BORDER};
        padding: 24px;
        border-radius: 16px;
        margin-bottom: 18px;
    }}
    .hero-title {{
        font-size: 29px;
        font-weight: 750;
        color: {TEXT};
        margin-bottom: 6px;
    }}
    .hero-subtitle {{ color: {MUTED}; font-size: 14px; }}
    .eyebrow {{
        color: {ACCENT};
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 2px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================
defaults = {
    "sim_processes": None,
    "monitoring": True,
    "event_log": [],
    "recovery_log": [],
    "system_history": [],
    "real_process_history": {},
    "generated_report": None,
    "generated_report_name": None,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

if st.session_state.sim_processes is None:
    st.session_state.sim_processes = create_processes()


def now_text():
    return datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S %Z")


def number(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def add_event(kind, message, source):
    st.session_state.event_log.append({
        "time": now_text(),
        "event": kind,
        "message": message,
        "source": source,
    })
    st.session_state.event_log = st.session_state.event_log[-500:]


def make_chart(title, x_values, y_values, y_title):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_values,
        y=y_values,
        mode="lines+markers",
        line={"color": ACCENT, "width": 3},
        marker={"size": 5},
        fill="tozeroy",
        fillcolor="rgba(34,211,238,0.08)",
        name=y_title,
    ))
    fig.update_layout(
        title=title,
        height=310,
        margin={"l": 15, "r": 15, "t": 55, "b": 15},
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        font={"color": TEXT},
        xaxis={"title": "Measurement", "gridcolor": BORDER},
        yaxis={"title": y_title, "gridcolor": BORDER},
        showlegend=False,
        uirevision=title,
    )
    return fig


# ============================================================
# REPORT BUILDERS
# ============================================================
def build_html_report(mode, metrics, processes, detections, recoveries, events):
    """Build a standalone, formatted HTML report with no extra dependency."""
    generated = now_text()

    def esc(value):
        return html.escape(str(value if value is not None else "N/A"))

    def make_table(headers, rows):
        head = "".join(f"<th>{esc(item)}</th>" for item in headers)
        body = ""
        for row in rows:
            body += "<tr>" + "".join(
                f"<td>{esc(item)}</td>" for item in row
            ) + "</tr>"
        if not rows:
            body = (
                f'<tr><td colspan="{len(headers)}">No records available.</td></tr>'
            )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    metric_rows = []
    if metrics:
        for label, key, suffix in [
            ("CPU utilization", "cpu_percent", "%"),
            ("Memory utilization", "memory_percent", "%"),
            ("Memory used", "memory_used_mb", " MB"),
            ("Total memory", "memory_total_mb", " MB"),
            ("Visible process count", "process_count", ""),
        ]:
            if metrics.get(key) is not None:
                metric_rows.append(
                    [label, f"{number(metrics[key]):,.2f}{suffix}"]
                )

    process_rows = [
        [
            p.get("pid", "N/A"),
            p.get("name", "Unknown"),
            f"{number(p.get('memory_mb')):.2f}" if p.get("memory_mb") is not None else "N/A",
            f"{number(p.get('cpu_percent')):.1f}",
            p.get("source", mode),
        ]
        for p in processes
    ]

    detection_table_rows = [
        [
            d["process"],
            d["status"],
            f"{number(d['growth_mb']):.2f}",
            d["reason"],
        ]
        for d in detections
    ]

    recovery_table_rows = [
        [
            r.get("time", "N/A"),
            r.get("process", "N/A"),
            f"{number(r.get('before_mb')):.2f}",
            f"{number(r.get('after_mb')):.2f}",
            f"{number(r.get('reduced_mb')):.2f}",
            r.get("source", "SIMULATION"),
        ]
        for r in recoveries
    ]

    event_table_rows = [
        [
            e.get("time", "N/A"),
            e.get("event", "N/A"),
            e.get("source", "N/A"),
            e.get("message", ""),
        ]
        for e in events[-100:]
    ]

    limitations = (
        "Simulation mode: process values and recovery actions are simulated. "
        "They are not measurements or recovery actions on real OS processes."
        if mode == "Simulation Mode"
        else
        "Real monitoring mode: measurements are read-only and limited to "
        "processes visible inside this Codespace. A snapshot alone does not "
        "prove a memory leak. Real-process recovery is not performed."
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>OS Resource Leak Detection Report</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 38px auto; max-width: 1100px;
       padding: 0 24px; color: #172033; background: #f4f7fb; }}
header {{ background: #0b1120; color: #f1f5f9; padding: 30px;
          border-radius: 14px; }}
header h1 {{ margin: 0 0 10px; font-size: 27px; }}
header p {{ color: #cbd5e1; margin: 0; }}
.meta {{ margin: 20px 0; padding: 16px; background: white;
         border-radius: 10px; border: 1px solid #dce3ec; }}
h2 {{ color: #0e7490; margin-top: 30px; border-bottom: 2px solid #dce3ec;
      padding-bottom: 8px; }}
table {{ width: 100%; border-collapse: collapse; background: white;
         margin: 12px 0 22px; font-size: 13px; }}
th {{ background: #172033; color: white; text-align: left; }}
th, td {{ padding: 9px; border: 1px solid #dce3ec; overflow-wrap: anywhere; }}
tbody tr:nth-child(even) {{ background: #f8fafc; }}
.note {{ background: #fff7ed; border-left: 4px solid #f59e0b;
         padding: 14px; line-height: 1.6; }}
footer {{ margin-top: 35px; padding-top: 12px; border-top: 1px solid #dce3ec;
          color: #64748b; font-size: 12px; }}
@media print {{ body {{ background: white; }} }}
</style>
</head>
<body>
<header>
<h1>OS Resource Leak Detection &amp; Recovery</h1>
<p>System monitoring report · {esc(mode)}</p>
</header>
<div class="meta">
<strong>Generated:</strong> {esc(generated)}<br>
<strong>Monitoring mode:</strong> {esc(mode)}<br>
<strong>Process records:</strong> {len(processes)} &nbsp;|&nbsp;
<strong>Detection results:</strong> {len(detections)} &nbsp;|&nbsp;
<strong>Recovery records:</strong> {len(recoveries)}
</div>
<h2>1. System Resource Summary</h2>
{make_table(["Metric", "Recorded value"], metric_rows)}
<h2>2. Process Details</h2>
{make_table(["PID", "Process", "Memory (MB)", "CPU (%)", "Source"], process_rows)}
<h2>3. Leak Detection Results</h2>
{make_table(["Process", "Status", "Recent growth (MB)", "Reason"], detection_table_rows)}
<h2>4. Recovery History</h2>
{make_table(["Time", "Process", "Before (MB)", "After (MB)", "Reduced (MB)", "Source"], recovery_table_rows)}
<h2>5. Event History</h2>
{make_table(["Time", "Event", "Source", "Details"], event_table_rows)}
<h2>6. Interpretation and Limitations</h2>
<div class="note">{esc(limitations)}</div>
<h2>Conclusion</h2>
<p>This report summarizes the records available in the application when the report was generated.
Suspicious-growth results indicate that the configured detection criteria were met; they do not
independently establish a confirmed memory leak.</p>
<footer>OS Resource Leak Detection System · Generated {esc(generated)}</footer>
</body>
</html>"""


def build_pdf_report(mode, metrics, processes, detections, recoveries, events):
    """Build a formatted PDF. Called only when ReportLab is available."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=18 * mm,
        title="OS Resource Leak Detection Report",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="CoverTitle", parent=styles["Title"],
        alignment=TA_CENTER, textColor=colors.HexColor("#0E7490"),
        fontSize=19, leading=24, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle", parent=styles["Heading2"],
        textColor=colors.HexColor("#0E7490"), fontSize=12,
        leading=15, spaceBefore=12, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="SmallCell", parent=styles["BodyText"],
        fontSize=7, leading=9, wordWrap="CJK",
    ))

    story = [
        Paragraph("OS RESOURCE LEAK DETECTION<br/>AND RECOVERY REPORT", styles["CoverTitle"]),
        Paragraph(f"Generated: {html.escape(now_text())}", styles["Normal"]),
        Paragraph(f"Monitoring mode: {html.escape(mode)}", styles["Normal"]),
        Spacer(1, 12),
    ]

    def add_section(title, headers, rows, widths=None):
        story.append(Paragraph(title, styles["SectionTitle"]))
        data = [headers]
        for row in rows:
            data.append([
                Paragraph(html.escape(str(cell if cell is not None else "N/A")), styles["SmallCell"])
                for cell in row
            ])
        if len(data) == 1:
            data.append(["No records available."] + [""] * (len(headers) - 1))
        table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172033")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F1F5F9")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
        story.append(Spacer(1, 5))

    metric_rows = []
    if metrics:
        for label, key, suffix in [
            ("CPU utilization", "cpu_percent", "%"),
            ("Memory utilization", "memory_percent", "%"),
            ("Memory used", "memory_used_mb", " MB"),
            ("Total memory", "memory_total_mb", " MB"),
            ("Visible process count", "process_count", ""),
        ]:
            if metrics.get(key) is not None:
                metric_rows.append([label, f"{number(metrics[key]):,.2f}{suffix}"])

    add_section("1. System Resource Summary", ["Metric", "Value"], metric_rows,
                [75 * mm, 90 * mm])

    add_section("2. Process Details",
        ["PID", "Process", "Memory MB", "CPU %", "Source"],
        [[p.get("pid"), p.get("name"), p.get("memory_mb"), p.get("cpu_percent"),
          p.get("source", mode)] for p in processes],
        [19 * mm, 55 * mm, 28 * mm, 23 * mm, 34 * mm])

    add_section("3. Leak Detection Results",
        ["Process", "Status", "Growth MB", "Reason"],
        [[d["process"], d["status"], f"{number(d['growth_mb']):.2f}", d["reason"]]
         for d in detections],
        [31 * mm, 37 * mm, 28 * mm, 63 * mm])

    add_section("4. Recovery History",
        ["Time", "Process", "Before MB", "After MB", "Reduced MB", "Source"],
        [[r.get("time"), r.get("process"), r.get("before_mb"), r.get("after_mb"),
          r.get("reduced_mb"), r.get("source", "SIMULATION")] for r in recoveries],
        [34 * mm, 29 * mm, 24 * mm, 24 * mm, 26 * mm, 22 * mm])

    add_section("5. Event History",
        ["Time", "Event", "Source", "Details"],
        [[e.get("time"), e.get("event"), e.get("source"), e.get("message")]
         for e in events[-60:]],
        [34 * mm, 24 * mm, 27 * mm, 74 * mm])

    story.append(Paragraph("6. Interpretation and Limitations", styles["SectionTitle"]))
    note = (
        "Simulation mode: measurements and recovery actions are simulated. "
        "Real Monitoring Mode: system metrics and process rows are read-only "
        "measurements from this Codespace. A snapshot alone cannot prove a memory "
        "leak. This application does not recover real OS processes."
    )
    story.append(Paragraph(note, styles["BodyText"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Conclusion", styles["SectionTitle"]))
    story.append(Paragraph(
        f"The report contains {len(processes)} process records, "
        f"{len(detections)} detection results, {len(recoveries)} recovery records, "
        f"and {len(events)} events. Results should be interpreted in the context "
        "of the selected monitoring mode.", styles["BodyText"]
    ))

    def page_footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(16 * mm, 10 * mm, "OS Resource Leak Detection System")
        canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("## 🖥️ OS Leak Detector")
    st.caption("SYSTEM RESOURCE INTELLIGENCE")
    st.divider()

    mode = st.radio(
        "Monitoring mode",
        ["Simulation Mode", "Real Monitoring Mode"],
        key="monitor_mode",
    )

    if mode == "Simulation Mode":
        st.markdown("### Simulation Controls")
        st.caption("These processes are simulated.")

        a, b = st.columns(2)
        if a.button("▶ Start", use_container_width=True):
            st.session_state.monitoring = True
            add_event("MONITOR", "Simulation monitoring started.", "SIMULATION")
        if b.button("⏸ Pause", use_container_width=True):
            st.session_state.monitoring = False
            add_event("MONITOR", "Simulation monitoring paused.", "SIMULATION")

        process_names = list(st.session_state.sim_processes.keys())
        selected = st.selectbox("Process to control", process_names)

        if st.button("⚠ Inject simulated leak", use_container_width=True):
            inject_leak(st.session_state.sim_processes, selected)
            add_event("LEAK TEST", f"Simulated growth started for {selected}.", "SIMULATION")
            st.rerun()

        if st.button("Stop leak growth", use_container_width=True):
            stop_leak(st.session_state.sim_processes, selected)
            add_event("LEAK TEST", f"Simulated growth stopped for {selected}.", "SIMULATION")
            st.rerun()

        if st.button("↺ Reset simulation", use_container_width=True):
            st.session_state.sim_processes = create_processes()
            st.session_state.recovery_log = []
            st.session_state.event_log = []
            add_event("RESET", "Simulated process baselines restored.", "SIMULATION")
            st.rerun()
    else:
        st.markdown("### Real Monitoring")
        st.info(
            "Read-only monitoring of processes visible inside this Codespace. "
            "This is not your personal laptop's process list."
        )

    st.divider()
    st.caption("Dark mode enabled")


@st.fragment(run_every=2 if st.session_state.monitoring else None)
def live_dashboard():
    # ============================================================
    # READ CURRENT DATA
    # ============================================================
    system_metrics = None
    process_rows = []
    detection_rows = []

    if mode == "Simulation Mode":
        if st.session_state.monitoring:
            tick_processes(st.session_state.sim_processes)

        snapshots = get_process_snapshot(st.session_state.sim_processes)

        for name, process in st.session_state.sim_processes.items():
            history = process.get("history", [])
            samples = [number(sample.get("memory_mb")) for sample in history]
            result = detect_suspicious_growth(samples)

            detection_rows.append({
                "process": name,
                "status": (
                    "Suspicious growth detected"
                    if result.get("suspicious")
                    else "No suspicious growth"
                ),
                "growth_mb": number(result.get("total_growth_mb")),
                "reason": result.get("reason", ""),
            })

        for item in snapshots:
            process_rows.append({
                "pid": item.get("pid", "SIMULATED"),
                "name": item.get("name", "Unknown"),
                "memory_mb": item.get("memory_mb"),
                "cpu_percent": 0.0,
                "source": "SIMULATION",
                "mode": item.get("mode", "normal"),
            })

    else:
        try:
            system_metrics = get_system_metrics()
            real_processes = get_real_processes()

            for process in real_processes:
                process_rows.append({
                    "pid": process.get("pid"),
                    "name": process.get("name", "Unknown"),
                    "memory_mb": process.get("memory_mb"),
                    "cpu_percent": process.get("cpu_percent", 0.0),
                    "source": "REAL_OS",
                    "mode": "read-only",
                })

            st.session_state.system_history.append({
                "time": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S"),
                "cpu_percent": number(system_metrics.get("cpu_percent")),
                "memory_percent": number(system_metrics.get("memory_percent")),
            })
            st.session_state.system_history = st.session_state.system_history[-120:]

            for process in real_processes:
                pid = str(process.get("pid"))
                history = st.session_state.real_process_history.setdefault(pid, [])
                history.append({
                    "time": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S"),
                    "memory_mb": number(process.get("memory_mb")),
                })
                st.session_state.real_process_history[pid] = history[-120:]

        except Exception as error:
            st.error(f"Unable to read real system metrics: {error}")


    # ============================================================
    # HEADER AND METRICS
    # ============================================================
    st.markdown(
        """
        <div class="hero">
            <div class="eyebrow">SYSTEM RESOURCE INTELLIGENCE</div>
            <div class="hero-title">OS Resource Leak Detection</div>
            <div class="hero-subtitle">
                Monitor system resources, inspect process memory and review
                suspicious growth and recovery activity.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Monitoring mode", mode)
    c2.metric("Current time", datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S"))
    c3.metric(
        "Monitor status",
        ("Running" if st.session_state.monitoring else "Paused")
        if mode == "Simulation Mode" else "Read-only",
    )

    st.markdown("## Resource Overview")

    if mode == "Real Monitoring Mode" and system_metrics:
        metrics = st.columns(4)
        metrics[0].metric("CPU usage", f"{number(system_metrics.get('cpu_percent')):.1f}%")
        metrics[1].metric("RAM usage", f"{number(system_metrics.get('memory_percent')):.1f}%")
        metrics[2].metric("RAM used", f"{number(system_metrics.get('memory_used_mb')):,.0f} MB")
        metrics[3].metric("Visible processes", str(system_metrics.get("process_count", len(process_rows))))
    else:
        total_memory = sum(number(p.get("memory_mb")) for p in process_rows)
        alert_count = sum(d["status"] == "Suspicious growth detected" for d in detection_rows)
        metrics = st.columns(3)
        metrics[0].metric("Simulated processes", len(process_rows))
        metrics[1].metric("Simulated memory", f"{total_memory:.1f} MB")
        metrics[2].metric("Suspicious growth", alert_count)


    # ============================================================
    # TABS
    # ============================================================
    overview, processes_tab, detection_tab, recovery_tab, report_tab = st.tabs([
        "📊 Overview",
        "🧩 Processes",
        "🔎 Leak Detection",
        "🛠️ Recovery & Events",
        "📄 Generate Report",
    ])


    with overview:
        if mode == "Real Monitoring Mode":
            history = st.session_state.system_history
            if history:
                left, right = st.columns(2)
                left.plotly_chart(
                    make_chart(
                        "CPU utilization",
                        [x["time"] for x in history],
                        [x["cpu_percent"] for x in history],
                        "CPU (%)",
                    ),
                    use_container_width=True,
                    key="cpu_utilization_chart",
                )
                right.plotly_chart(
                    make_chart(
                        "Memory utilization",
                        [x["time"] for x in history],
                        [x["memory_percent"] for x in history],
                        "Memory (%)",
                    ),
                    use_container_width=True,
                    key="memory_utilization_chart",
                )
            st.info("Charts show readings captured while the dashboard is open.")
        else:
            left, right = st.columns(2)
            for i, (name, process) in enumerate(st.session_state.sim_processes.items()):
                history = process.get("history", [])
                values = [number(x.get("memory_mb")) for x in history]
                fig = make_chart(
                    f"{name} memory trend",
                    list(range(1, len(values) + 1)),
                    values,
                    "Memory (MB)",
                )
                (left if i % 2 == 0 else right).plotly_chart(
                    fig, use_container_width=True
                )
            st.warning("Simulated memory values are not real OS measurements.")


    with processes_tab:
        st.markdown("### Visible Processes")
        if process_rows:
            st.dataframe(pd.DataFrame(process_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No process data is currently available.")


    with detection_tab:
        st.markdown("### Detection Results")

        if mode == "Simulation Mode":
            for result in detection_rows:
                with st.container(border=True):
                    st.markdown(f"#### {result['process']}")
                    if result["status"] == "Suspicious growth detected":
                        st.error(result["status"])
                        st.write(f"Recent growth: **{result['growth_mb']:.2f} MB**")
                        st.caption(result["reason"])
                        st.warning("This is simulated growth, not proof of a real memory leak.")

                        if st.button("Recover " + result["process"], key="recover_" + result["process"]):
                            outcome = recover_simulated_process(
                                st.session_state.sim_processes,
                                result["process"],
                            )
                            st.session_state.recovery_log.append({
                                "time": now_text(),
                                "process": outcome.get("process", result["process"]),
                                "before_mb": outcome.get("before_mb", 0),
                                "after_mb": outcome.get("after_mb", 0),
                                "reduced_mb": outcome.get("reduced_mb", 0),
                                "status": outcome.get("status", "Completed"),
                                "source": "SIMULATION",
                            })
                            add_event(
                                "RECOVERY",
                                f"Simulated recovery for {result['process']}; "
                                f"{number(outcome.get('reduced_mb')):.2f} MB reduced.",
                                "SIMULATION",
                            )
                            st.success("Simulated recovery recorded.")
                            st.rerun()
                    else:
                        st.success(result["status"])
                        st.write(f"Recent growth: **{result['growth_mb']:.2f} MB**")
                        st.caption(result["reason"])
        else:
            st.info(
                "Real per-process leak detection is not implemented in this version. "
                "Real mode currently provides read-only process and system metrics."
            )


    with recovery_tab:
        st.markdown("### Recovery History")
        if st.session_state.recovery_log:
            st.dataframe(
                pd.DataFrame(st.session_state.recovery_log),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No recovery actions recorded in this session.")

        st.markdown("### Event History")
        if st.session_state.event_log:
            st.dataframe(
                pd.DataFrame(st.session_state.event_log[::-1]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No events recorded yet.")


    with report_tab:
        st.markdown("## Generate Report")
        st.write(
            "Create a formatted report containing the current system snapshot, "
            "process details, detection results, recovery history and event log."
        )

        st.info(
            "The report reflects data available at generation time. "
            "Real monitoring is read-only; simulated recovery is not real OS recovery."
        )

        if st.button("📄 Generate Report", type="primary", use_container_width=True):
            try:
                report_metrics = system_metrics if mode == "Real Monitoring Mode" else None

                html_report = build_html_report(
                    mode,
                    report_metrics,
                    process_rows,
                    detection_rows,
                    st.session_state.recovery_log,
                    st.session_state.event_log,
                )

                st.session_state.generated_report = html_report
                st.session_state.generated_report_name = (
                    "OS_Resource_Leak_Report_"
                    + datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y%m%d_%H%M%S")
                )

                if PDF_AVAILABLE:
                    st.session_state.generated_pdf = build_pdf_report(
                        mode,
                        report_metrics,
                        process_rows,
                        detection_rows,
                        st.session_state.recovery_log,
                        st.session_state.event_log,
                    )
                else:
                    st.session_state.generated_pdf = None

                add_event("REPORT", f"Report generated in {mode}.", mode.upper())
                st.success("Report generated successfully.")

            except Exception as error:
                st.error(f"Report generation failed: {error}")

        if st.session_state.generated_report:
            base_name = st.session_state.generated_report_name

            if st.session_state.generated_pdf:
                st.download_button(
                    "⬇ Download PDF Report",
                    data=st.session_state.generated_pdf,
                    file_name=base_name + ".pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

            st.download_button(
                "⬇ Download Formatted HTML Report",
                data=st.session_state.generated_report.encode("utf-8"),
                file_name=base_name + ".html",
                mime="text/html",
                use_container_width=True,
            )

            if not PDF_AVAILABLE:
                st.caption(
                    "PDF support is unavailable because ReportLab is not installed. "
                    "The formatted HTML report is ready to download."
                )


    # ============================================================
    # FOOTER
    # ============================================================
    st.divider()
    st.caption(
        "OS Resource Leak Detection and Recovery System · "
        "Real monitoring is read-only; recovery actions affect simulated data only."
    )


live_dashboard()
