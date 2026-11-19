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
        min_value=1.0,
        value=8929.0,
        step=1.0,
        format="%.2f",
    )
    c_outer = st.number_input(
        "Outer Edge Circumference (mm)",
        min_value=c_inner + 1.0,
        value=11060.0,
        step=1.0,
        format="%.2f",
    )
    n_turns = st.number_input(
        "Number of Turns",
        min_value=1,
        max_value=500,
        value=25,
        step=1,
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
        min_value=0.0001,
        value=0.1250 if unit == "V" else 125.0,
        step=0.0001 if unit == "V" else 0.1,
        format="%.4f",
    )

    default_v_target = 0.0124 if unit == "V" else 12.4
    v_target = st.number_input(
        f"Voltage Drop at Interested Location ({unit})",
        min_value=0.0,
        max_value=float(v_total),
        value=min(default_v_target, float(v_total)),
        step=0.0001 if unit == "V" else 0.1,
        format="%.4f",
    )

    winding_dir = st.radio(
        "Visual Winding Direction (from Start / Inner Tail)",
        ["Counter-Clockwise (CCW)", "Clockwise (CW)"],
        index=1,
        horizontal=True,
    )

# --- Core Calculations ---
delta_c = c_outer - c_inner
step_per_turn = delta_c / n_turns
r_inner = c_inner / (2 * math.pi)
r_outer = c_outer / (2 * math.pi)
radial_pitch = step_per_turn / (2 * math.pi)

rows = []
cum_len = 0.0
for k in range(1, int(n_turns) + 1):
    length_k = c_inner + (k - 0.5) * step_per_turn
    start_len = cum_len
    cum_len += length_k
    rows.append(
        {
            "Turn": k,
            "Turn Length (mm)": length_k,
            "Start Len Inner (mm)": start_len,
            "End Len Inner (mm)": cum_len,
        }
    )

df = pd.DataFrame(rows)
total_length_mm = df["End Len Inner (mm)"].iloc[-1]
v_per_mm = v_total / total_length_mm

df[f"Turn Drop ({unit})"] = df["Turn Length (mm)"] * v_per_mm

is_inner_ref = measured_from == "Start / Inner Tail"
ref_short = "Inner Tail" if is_inner_ref else "Outer Tail"

if is_inner_ref:
    df[f"Cum. Voltage Start ({unit})"] = df["Start Len Inner (mm)"] * v_per_mm
    df[f"Cum. Voltage End ({unit})"] = df["End Len Inner (mm)"] * v_per_mm
    dist_from_ref_mm = (v_target / v_total) * total_length_mm
    dist_from_inner_mm = dist_from_ref_mm
else:
    df[f"Cum. Voltage Start ({unit})"] = (
        total_length_mm - df["End Len Inner (mm)"]
    ) * v_per_mm
    df[f"Cum. Voltage End ({unit})"] = (
        total_length_mm - df["Start Len Inner (mm)"]
    ) * v_per_mm
    dist_from_ref_mm = (v_target / v_total) * total_length_mm
    dist_from_inner_mm = total_length_mm - dist_from_ref_mm

# Clamp floating point edge cases
dist_from_inner_mm = max(0.0, min(total_length_mm, dist_from_inner_mm))

# Locate exact turn and fractional position along that turn
match_rows = df[
    (df["Start Len Inner (mm)"] <= dist_from_inner_mm)
    & (df["End Len Inner (mm)"] >= dist_from_inner_mm)
]
target_row = match_rows.iloc[0] if not match_rows.empty else df.iloc[-1]

target_turn = int(target_row["Turn"])
turn_length_mm = float(target_row["Turn Length (mm)"])
dist_into_turn_inner_mm = dist_from_inner_mm - float(target_row["Start Len Inner (mm)"])
frac_from_inner = dist_into_turn_inner_mm / turn_length_mm
continuous_turn = (target_turn - 1) + frac_from_inner

# Length from the last complete turn (relative to chosen tail)
if is_inner_ref:
    dist_from_last_turn_mm = dist_into_turn_inner_mm
    completed_turns = target_turn - 1
    if abs(dist_from_last_turn_mm - turn_length_mm) < 1e-6:
        completed_turns = target_turn
        dist_from_last_turn_mm = 0.0
else:
    dist_from_last_turn_mm = float(target_row["End Len Inner (mm)"]) - dist_from_inner_mm
    completed_turns = int(n_turns) - target_turn
    if abs(dist_from_last_turn_mm - turn_length_mm) < 1e-6:
        completed_turns = int(n_turns) - target_turn + 1
        dist_from_last_turn_mm = 0.0

frac_from_last_turn = dist_from_last_turn_mm / turn_length_mm
angle_from_last_turn_deg = frac_from_last_turn * 360.0

# Remaining length from interested point to complete that turn
if dist_from_last_turn_mm == 0.0:
    dist_to_complete_turn_mm = 0.0
    rem_frac_in_turn = 0.0
else:
    dist_to_complete_turn_mm = turn_length_mm - dist_from_last_turn_mm
    rem_frac_in_turn = 1.0 - frac_from_last_turn

# --- KPI Summary Rows ---
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

row2_c1, row2_c2, row2_c3 = st.columns(3)
row2_c1.metric(
    f"Total Distance from {ref_short}",
    f"{dist_from_ref_mm / 1000:.3f} m",
    f"{dist_from_ref_mm:,.1f} mm",
)
row2_c2.metric(
    "Voltage Gradient",
    f"{v_per_mm * 1000:.4f} {unit}/m",
    f"{v_per_mm:.6f} {unit}/mm",
)
row2_c3.metric(
    "Total Conductor Length",
    f"{total_length_mm / 1000:.3f} m",
    f"Pitch ≈ {radial_pitch:.2f} mm/turn",
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

    # Highlighted path from chosen tail to target
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

    # Exact target point
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
            name=f"Measured Span from {ref_short} (0 → {v_target:.4f} {unit})",
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
            hovertemplate=(
                f"<b>Target Location</b><br>"
                f"Measured From: {measured_from}<br>"
                f"Turn: {target_turn} ({frac_from_last_turn * 100:.1f}%)<br>"
                f"Past Last Turn: {dist_from_last_turn_mm:,.1f} mm ({dist_from_last_turn_mm / 1000:.3f} m)<br>"
                f"To Complete Turn: {dist_to_complete_turn_mm:,.1f} mm ({dist_to_complete_turn_mm / 1000:.3f} m)<br>"
                f"Angle: {angle_from_last_turn_deg:.1f}°<br>"
                f"Voltage Drop: {v_target:.4f} {unit}<br>"
                f"Total Dist from {ref_short}: {dist_from_ref_mm:,.1f} mm<extra></extra>"
            ),
        )
    )

    fig_spiral.add_annotation(
        x=x_t,
        y=y_t,
        text=(
            f"<b>Turn {target_turn}</b> (+{dist_from_last_turn_mm:,.0f} mm / -{dist_to_complete_turn_mm:,.0f} mm left)<br>"
            f"{v_target:.4f} {unit} · {angle_from_last_turn_deg:.0f}°"
        ),
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
        y_volts = [0.0] + df[f"Cum. Voltage End ({unit})"].tolist()
    else:
        x_turns = [0] + df["Turn"].tolist()
        y_volts = [v_total] + df[f"Cum. Voltage Start ({unit})"].tolist()

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
        annotation_text=f"{v_target:.4f} {unit}",
    )
    fig_profile.add_vline(
        x=continuous_turn,
        line_dash="dash",
        line_color="#d62728",
        annotation_text=f"Turn {target_turn} (+{dist_from_last_turn_mm:,.0f} mm)",
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
        yaxis_title=f"Voltage Drop from {ref_short} ({unit})",
        height=310,
        margin=dict(l=20, r=20, t=25, b=20),
        showlegend=False,
    )
    st.plotly_chart(fig_profile, use_container_width=True)

    st.subheader("Voltage Drop per Individual Turn")
    bar_colors = [
        "#d62728" if t == target_turn else "#6baed6" for t in df["Turn"]
    ]
    fig_bar = go.Figure(
        go.Bar(
            x=df["Turn"],
            y=df[f"Turn Drop ({unit})"],
            marker_color=bar_colors,
            hovertemplate=(
                "Turn %{x}<br>"
                f"Turn Drop: %{{y:.4f}} {unit}<extra></extra>"
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
        "End Len Inner (mm)",
        f"Turn Drop ({unit})",
        f"Cum. Voltage Start ({unit})",
        f"Cum. Voltage End ({unit})",
    ]
].rename(columns={"End Len Inner (mm)": "Cum. Length from Inner Tail (mm)"})

st.dataframe(
    display_df.style.format(
        {
            "Turn Length (mm)": "{:,.2f}",
            "Cum. Length from Inner Tail (mm)": "{:,.2f}",
            f"Turn Drop ({unit})": "{:.4f}",
            f"Cum. Voltage Start ({unit})": "{:.4f}",
            f"Cum. Voltage End ({unit})": "{:.4f}",
        }
    ).apply(
        lambda row: [
            "background-color: rgba(214, 39, 40, 0.18); font-weight: bold;"
            if row["Turn"] == target_turn
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
