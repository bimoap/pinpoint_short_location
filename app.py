import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Coil Voltage Drop Locator",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ Single-Layer Pancake Coil — Voltage Drop Locator")
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

    v_total = st.number_input(
        f"Total Layer Voltage Drop ({unit})",
        min_value=0.0001,
        value=10.0 if unit == "V" else 1000.0,
        step=0.1 if unit == "V" else 10.0,
        format="%.4f",
    )

    ref_lead = st.radio(
        "0 V Reference Probe Location",
        ["Inner Lead (Turn 1)", "Outer Lead (Turn N)"],
        help="Select which end of the coil your negative/reference probe is connected to.",
    )

    v_target = st.number_input(
        f"Voltage Drop at Interested Location ({unit})",
        min_value=0.0,
        max_value=float(v_total),
        value=min(float(v_total) * 0.42, float(v_total)),
        step=0.05 if unit == "V" else 5.0,
        format="%.4f",
    )

    winding_dir = st.radio(
        "Visual Winding Direction (from Inner Lead)",
        ["Counter-Clockwise (CCW)", "Clockwise (CW)"],
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

if ref_lead == "Inner Lead (Turn 1)":
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
dist_into_turn_inner_mm = dist_from_inner_mm - float(target_
