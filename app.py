import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Single-Layer Pancake Coil — Fault Locator",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ Single-Layer Pancake Coil — Fault Locator")
st.caption(
    "Locate the exact turn and conductor length along a spiral coil from a measured voltage drop."
)

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("1. Coil Geometry")
    c_inner = st.number_input(
        "Inner Edge Circumference (mm)",
        min_value=1,
        value=8929,
        step=1,
        format="%d",
    )
    c_outer = st.number_input(
        "Outer Edge Circumference (mm)",
        min_value=int(c_inner) + 1,
        value=11060,
        step=1,
        format="%d",
    )
    n_turns = st.number_input(
        "Number of Turns",
        min_value=1,
        max_value=500,
        value=25,
        step=1,
    )
    inner_lead_mm = st.number_input(
        "Start / Inner Tail Lead Length (mm)",
        min_value=0,
        value=0,
        step=1,
        format="%d",
        help="Extra conductor length from the Start / Inner probe point to the start of Turn 1.",
    )
    outer_lead_mm = st.number_input(
        "Finish / Outer Tail Lead Length (mm)",
        min_value=0,
        value=0,
        step=1,
        format="%d",
        help="Extra conductor length from the end of Turn N to the Finish / Outer probe point.",
    )

    st.divider()
    st.header("2. Voltage Drop Measurements")
    unit = st.radio("Voltage Unit", ["V", "mV"], horizontal=True)

    measured_from = st.radio(
        "Voltage Drop Measured From",
        ["Start / Inner Tail", "Finish / Outer Tail"],
        index=1,
        help="Select which tail of the coil your 0 V reference probe is connected to.",
    )

    v_total = st.number_input(
        f"Total Layer Voltage Drop ({unit})",
        min_value=0.000001,
        value=0.125000 if unit == "V" else 125.000000,
        step=0.000001 if unit == "V" else 0.001000,
        format="%.6f",
    )

    default_v_target = 0.012450 if unit == "V" else 12.450000
    v_target = st.number_input(
        f"Voltage Drop at Interested Location ({unit})",
        min_value=0.0,
        max_value=float(v_total),
        value=min(default_v_target, float(v_total)),
        step=0.000001 if unit == "V" else 0.001000,
        format="%.6f",
    )

    winding_dir = st.radio(
        "Visual Winding Direction (from Start / Inner Tail)",
        ["Counter-Clockwise (CCW)", "Clockwise (CW)"],
        index=1,
        horizontal=True,
    )

# --- Core Calculations ---
delta_c = float(c_outer - c_inner)
step_per_turn = delta_c / n_turns
r_inner = float(c_inner) / (2 * math.pi)
r_outer = float(c_outer) / (2 * math.pi)
radial_pitch = step_per_turn / (2 * math.pi)

rows = []
cum_len = 0.0
for k in range(1, int(n_turns) + 1):
    length_k = float(c_inner) + (k - 0.5) * step_per_turn
    start_len = cum_len
    cum_len += length_k
    rows.append(
        {
            "Turn": k,
            "Turn Length (mm)": length_k,
            "Start Len Winding (mm)": start_len,
            "End Len Winding (mm)": cum_len,
        }
    )

df = pd.DataFrame(rows)
winding_length_mm = df["End Len Winding (mm)"].iloc[-1]
total_length_mm = float(inner_lead_mm) + winding_length_mm + float(outer_lead_mm)
v_per_mm = v_total / total_length_mm

df[f"Turn Drop ({unit})"] = df["Turn Length (mm)"] * v_per_mm

is_inner_ref = measured_from == "Start / Inner Tail"
ref_short = "Inner Tail" if is_inner_ref else "Outer Tail"

if is_inner_ref:
    df[f"Cum. Voltage Start ({unit})"] = (
        float(inner_lead_mm) + df["Start Len Winding (mm)"]
    ) * v_per_mm
    df[f"Cum. Voltage End ({unit})"] = (
        float(inner_lead_mm) + df["End Len Winding (mm)"]
    ) * v_per_mm
    dist_from_ref_mm = (v_target / v_total) * total_length_mm
    dist_from_inner_probe_mm = dist_from_ref_mm
else:
    df[f"Cum. Voltage Start ({unit})"] = (
        float(outer_lead_mm) + winding_length_mm - df["End Len Winding (mm)"]
    ) * v_per_mm
    df[f"Cum. Voltage End ({unit})"] = (
        float(outer_lead_mm) + winding_length_mm - df["Start Len Winding (mm)"]
    ) * v_per_mm
    dist_from_ref_mm = (v_target / v_total) * total_length_mm
    dist_from_inner_probe_mm = total_length_mm - dist_from_ref_mm

# Clamp floating point edge cases
dist_from_inner_probe_mm = max(0.0, min(total_length_mm, dist_from_inner_probe_mm))
dist_in_winding_from_inner_mm = dist_from_inner_probe_mm - float(inner_lead_mm)

# Determine whether fault is on Inner Lead, Outer Lead, or inside Winding
if dist_in_winding_from_inner_mm < -1e-6:
    fault_zone = "inner_lead"
    target_turn = None
    continuous_turn = 0.0
    lead_dist_from_winding_mm = -dist_in_winding_from_inner_mm
    turn_length_mm = 0.0
    dist_from_last_turn_mm = 0.0
    dist_to_complete_turn_mm = 0.0
    frac_from_last_turn = 0.0
    rem_frac_in_turn = 0.0
    angle_from_last_turn_deg = 0.0
    completed_turns = 0 if is_inner_ref else int(n_turns)
elif dist_in_winding_from_inner_mm > winding_length_mm + 1e-6:
    fault_zone = "outer_lead"
    target_turn = None
    continuous_turn = float(n_turns)
    lead_dist_from_winding_mm = dist_in_winding_from_inner_mm - winding_length_mm
    turn_length_mm = 0.0
    dist_from_last_turn_mm = 0.0
    dist_to_complete_turn_mm = 0.0
    frac_from_last_turn = 0.0
    rem_frac_in_turn = 0.0
    angle_from_last_turn_deg = 0.0
    completed_turns = int(n_turns) if is_inner_ref else 0
else:
    fault_zone = "winding"
    clamped_winding_mm = max(0.0, min(winding_length_mm, dist_in_winding_from_inner_mm))
    match_rows = df[
        (df["Start Len Winding (mm)"] <= clamped_winding_mm)
        & (df["End Len Winding (mm)"] >= clamped_winding_mm)
    ]
    target_row = match_rows.iloc[0] if not match_rows.empty else df.iloc[-1]

    target_turn = int(target_row["Turn"])
    turn_length_mm = float(target_row["Turn Length (mm)"])
    dist_into_turn_inner_mm = clamped_winding_mm - float(target_row["Start Len Winding (mm)"])
    frac_from_inner = dist_into_turn_inner_mm / turn_length_mm
    continuous_turn = (target_turn - 1) + frac_from_inner

    if is_inner_ref:
        dist_from_last_turn_mm = dist_into_turn_inner_mm
        completed_turns = target_turn - 1
        if abs(dist_from_last_turn_mm - turn_length_mm) < 1e-6:
            completed_turns = target_turn
            dist_from_last_turn_mm = 0.0
    else:
        dist_from_last_turn_mm = float(target_row["End Len Winding (mm)"]) - clamped_winding_mm
        completed_turns = int(n_turns) - target_turn
        if abs(dist_from_last_turn_mm - turn_length_mm) < 1e-6:
            completed_turns = int(n_turns) - target_turn + 1
            dist_from_last_turn_mm = 0.0

    frac_from_last_turn = dist_from_last_turn_mm / turn_length_mm
    angle_from_last_turn_deg = frac_from_last_turn * 360.0

    if dist_from_last_turn_mm == 0.0:
        dist_to_complete_turn_mm = 0.0
        rem_frac_in_turn = 0.0
    else:
        dist_to_complete_turn_mm = turn_length_mm - dist_from_last_turn_mm
        rem_frac_in_turn = 1.0 - frac_from_last_turn

# --- KPI Summary Rows ---
if fault_zone == "winding":
    row1_c1, row1_c2, row1_c3, row1_c4 = st.columns(4)
    row1_c1.metric(
        "Target Turn",
        f"Turn {target_turn} / {n_turns}",
        f"{completed_turns} complete turns from {ref_short}",
    )
    row1_c2.metric(
        "From Last Complete Turn",
        f"{dist_from_last_turn_mm:,.1f} mm",
        f"{dist_from_last_turn_mm / 1000:.3f} m ({frac_from_last_turn * 100:.1f}%)",
    )
    row1_c3.metric(
        "To Complete This Turn",
        f"{dist_to_complete_turn_mm:,.1f} mm",
        f"{dist_to_complete_turn_mm / 1000:.3f} m ({rem_frac_in_turn * 100:.1f}% left)",
    )
    row1_c4.metric(
        "Angular Position in Turn",
        f"{angle_from_last_turn_deg:.1f}°",
        f"Turn length: {turn_length_mm:,.1f} mm",
    )
else:
    lead_name = (
        "Start / Inner Tail Lead"
        if fault_zone == "inner_lead"
        else "Finish / Outer Tail Lead"
    )
    st.warning(
        f"**Location falls outside the winding — on the {lead_name}** "
        f"({lead_dist_from_winding_mm:,.1f} mm outside the coil edge)."
    )
    row1_c1, row1_c2, row1_c3 = st.columns(3)
    row1_c1.metric("Target Location", lead_name)
    row1_c2.metric(
        "Distance Outside Winding",
        f"{lead_dist_from_winding_mm:,.1f} mm",
        f"{lead_dist_from_winding_mm / 1000:.3f} m from coil edge",
    )
    row1_c3.metric(
        "Lead Length Configured",
        f"{inner_lead_mm if fault_zone == 'inner_lead' else outer_lead_mm:,d} mm",
        "Outside spiral turns",
    )

row2_c1, row2_c2, row2_c3 = st.columns(3)
row2_c1.metric(
    f"Total Distance from {ref_short} Probe",
    f"{dist_from_ref_mm / 1000:.3f} m",
    f"{dist_from_ref_mm:,.1f} mm (incl. lead)",
)
row2_c2.metric(
    "Voltage Gradient",
    f"{v_per_mm * 1000:.6f} {unit}/m",
    f"{v_per_mm:.6f} {unit}/mm",
)
row2_c3.metric(
    "Total Conductor Length",
    f"{total_length_mm / 1000:.3f} m",
    f"Winding: {winding_length_mm / 1000:.3f} m · Leads: {(inner_lead_mm + outer_lead_mm) / 1000:.3f} m",
)

st.divider()

# --- Visualizations ---
viz_col1, viz_col2 = st.columns([1.15, 1])

with viz_col1:
    st.subheader("Top-Down Coil Spiral Map")

    dir_sign = 1.0 if "CCW" in winding_dir else -1.0
    pts_per_turn = 72
    u_all = np.linspace(0, n_turns, int(n_turns * pts_per_turn) + 1)
    theta_all = dir_sign * 2 * math.pi * u_all
    r_all = r_inner + (r_outer - r_inner) * (u_all / n_turns)
    x_all = r_all * np.cos(theta_all)
    y_all = r_all * np.sin(theta_all)

    # Highlighted winding span from chosen tail to target
    if is_inner_ref:
        u_active = np.linspace(
            0, continuous_turn, max(2, int(continuous_turn * pts_per_turn) + 1)
        )
    else:
        u_active = np.linspace(
            continuous_turn,
            n_turns,
            max(2, int((n_turns - continuous_turn) * pts_per_turn) + 1),
        )
    theta_act = dir_sign * 2 * math.pi * u_active
    r_act = r_inner + (r_outer - r_inner) * (u_active / n_turns)
    x_act = r_act * np.cos(theta_act)
    y_act = r_act * np.sin(theta_act)

    # Exact target point on spiral (or clamped to lead exit)
    theta_t = dir_sign * 2 * math.pi * continuous_turn
    r_t = r_inner + (r_outer - r_inner) * (continuous_turn / n_turns)
    x_t = r_t * np.cos(theta_t)
    y_t = r_t * np.sin(theta_t)

    fig_spiral = go.Figure()

    # Full coil outline
    fig_spiral.add_trace(
        go.Scatter(
            x=x_all,
            y=y_all,
            mode="lines",
            line=dict(color="rgba(160, 175, 190, 0.55)", width=2),
            name="Remaining Coil",
            hoverinfo="skip",
        )
    )

    # Active voltage-drop path
    fig_spiral.add_trace(
        go.Scatter(
            x=x_act,
            y=y_act,
            mode="lines",
            line=dict(color="#1f77b4", width=3.2),
            name=f"Measured Span from {ref_short} (0 → {v_target:.6f} {unit})",
            hoverinfo="skip",
        )
    )

    # Start / Inner & Finish / Outer tail markers
    fig_spiral.add_trace(
        go.Scatter(
            x=[r_inner, r_outer],
            y=[0, 0],
            mode="markers+text",
            marker=dict(size=9, color=["#2ca02c", "#9467bd"], symbol="circle"),
            text=["Start / Inner Tail (T1)", f"Finish / Outer Tail (T{n_turns})"],
            textposition=["middle left", "middle right"],
            name="Coil Tails",
        )
    )

    if fault_zone == "winding":
        hover_text = (
            f"<b>Target Location</b><br>"
            f"Measured From: {measured_from}<br>"
            f"Turn: {target_turn} ({frac_from_last_turn * 100:.1f}%)<br>"
            f"Past Last Turn: {dist_from_last_turn_mm:,.1f} mm ({dist_from_last_turn_mm / 1000:.3f} m)<br>"
            f"To Complete Turn: {dist_to_complete_turn_mm:,.1f} mm ({dist_to_complete_turn_mm / 1000:.3f} m)<br>"
            f"Angle: {angle_from_last_turn_deg:.1f}°<br>"
            f"Voltage Drop: {v_target:.6f} {unit}<br>"
            f"Total Dist from {ref_short}: {dist_from_ref_mm:,.1f} mm<extra></extra>"
        )
        annot_text = (
            f"<b>Turn {target_turn}</b> (+{dist_from_last_turn_mm:,.0f} mm / -{dist_to_complete_turn_mm:,.0f} mm left)<br>"
            f"{v_target:.6f} {unit} · {angle_from_last_turn_deg:.0f}°"
        )
    else:
        lead_label = "Inner Tail Lead" if fault_zone == "inner_lead" else "Outer Tail Lead"
        hover_text = (
            f"<b>Target Location: {lead_label}</b><br>"
            f"Distance Outside Winding: {lead_dist_from_winding_mm:,.1f} mm<br>"
            f"Voltage Drop: {v_target:.6f} {unit}<br>"
            f"Total Dist from {ref_short}: {dist_from_ref_mm:,.1f} mm<extra></extra>"
        )
        annot_text = (
            f"<b>On {lead_label}</b><br>"
            f"{lead_dist_from_winding_mm:,.0f} mm outside winding · {v_target:.6f} {unit}"
        )

    # Target location pin
    fig_spiral.add_trace(
        go.Scatter(
            x=[x_t],
            y=[y_t],
            mode="markers",
            marker=dict(
                size=16,
                color="#d62728",
                symbol="x-thin-open",
                line=dict(width=3.5, color="#d62728"),
            ),
            name="Target Location",
            hovertemplate=hover_text,
        )
    )

    fig_spiral.add_annotation(
        x=x_t,
        y=y_t,
        text=annot_text,
        showarrow=True,
        arrowhead=2,
        arrowcolor="#d62728",
        bgcolor="rgba(255,255,255,0.90)",
        bordercolor="#d62728",
        borderwidth=1,
        font=dict(color="#111111", size=12),
    )

    fig_spiral.update_layout(
        xaxis=dict(
            title="X (mm)",
            scaleanchor="y",
            scaleratio=1,
            showgrid=True,
            zeroline=False,
        ),
        yaxis=dict(title="Y (mm)", showgrid=True, zeroline=False),
        height=560,
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig_spiral, use_container_width=True)

with viz_col2:
    st.subheader("Cumulative Voltage Drop by Turn")

    fig_profile = go.Figure()

    if is_inner_ref:
        x_turns = [0] + df["Turn"].tolist()
        y_volts = [float(inner_lead_mm) * v_per_mm] + df[
            f"Cum. Voltage End ({unit})"
        ].tolist()
    else:
        x_turns = [0] + df["Turn"].tolist()
        y_volts = [
            (float(outer_lead_mm) + winding_length_mm) * v_per_mm
        ] + df[f"Cum. Voltage Start ({unit})"].tolist()

    fig_profile.add_trace(
        go.Scatter(
            x=x_turns,
            y=y_volts,
            mode="lines+markers",
            line=dict(color="#1f77b4", width=2.5),
            marker=dict(size=6),
            name=f"Cumulative Voltage ({unit})",
        )
    )

    fig_profile.add_hline(
        y=v_target,
        line_dash="dash",
        line_color="#d62728",
        annotation_text=f"{v_target:.6f} {unit}",
    )

    vline_label = (
        f"Turn {target_turn} (+{dist_from_last_turn_mm:,.0f} mm)"
        if fault_zone == "winding"
        else ("Inner Lead" if fault_zone == "inner_lead" else "Outer Lead")
    )
    fig_profile.add_vline(
        x=continuous_turn,
        line_dash="dash",
        line_color="#d62728",
        annotation_text=vline_label,
    )

    fig_profile.add_trace(
        go.Scatter(
            x=[continuous_turn],
            y=[v_target],
            mode="markers",
            marker=dict(size=12, color="#d62728"),
            name="Interested Location",
        )
    )

    fig_profile.update_layout(
        xaxis_title="Turn Number (Start / Inner = 0 → Finish / Outer = N)",
        yaxis_title=f"Voltage Drop from {ref_short} Probe ({unit})",
        height=310,
        margin=dict(l=20, r=20, t=25, b=20),
        showlegend=False,
    )
    st.plotly_chart(fig_profile, use_container_width=True)

    st.subheader("Voltage Drop per Individual Turn")
    bar_colors = [
        "#d62728" if (fault_zone == "winding" and t == target_turn) else "#6baed6"
        for t in df["Turn"]
    ]
    fig_bar = go.Figure(
        go.Bar(
            x=df["Turn"],
            y=df[f"Turn Drop ({unit})"],
            marker_color=bar_colors,
            hovertemplate=(
                "Turn %{x}<br>"
                f"Turn Drop: %{{y:.6f}} {unit}<extra></extra>"
            ),
        )
    )
    fig_bar.update_layout(
        xaxis_title="Turn Number",
        yaxis_title=f"Turn Drop ({unit})",
        height=230,
        margin=dict(l=20, r=20, t=10, b=20),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# --- Detailed Per-Turn Table ---
st.subheader("Per-Turn Breakdown Table")

display_df = df[
    [
        "Turn",
        "Turn Length (mm)",
        "End Len Winding (mm)",
        f"Turn Drop ({unit})",
        f"Cum. Voltage Start ({unit})",
        f"Cum. Voltage End ({unit})",
    ]
].rename(columns={"End Len Winding (mm)": "Cum. Winding Length from T1 (mm)"})

st.dataframe(
    display_df.style.format(
        {
            "Turn Length (mm)": "{:,.2f}",
            "Cum. Winding Length from T1 (mm)": "{:,.2f}",
            f"Turn Drop ({unit})": "{:.6f}",
            f"Cum. Voltage Start ({unit})": "{:.6f}",
            f"Cum. Voltage End ({unit})": "{:.6f}",
        }
    ).apply(
        lambda row: [
            "background-color: rgba(214, 39, 40, 0.18); font-weight: bold;"
            if (fault_zone == "winding" and row["Turn"] == target_turn)
            else ""
            for _ in row
        ],
        axis=1,
    ),
    use_container_width=True,
    hide_index=True,
)

csv_bytes = display_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download Table as CSV",
    data=csv_bytes,
    file_name="coil_fault_location_table.csv",
    mime="text/csv",
)
