"""
Pump Sizing & Irrigation Design Tool  (single file, no other files needed)

Run:      pip install -r requirements.txt
          streamlit run app.py
Tools:    1) Pump Sizing  2) Water Demand
"""
from math import ceil, floor, log10, pi

import pandas as pd
import streamlit as st

# ============================================================ display switches
# Everything below still exists in the app. Set a switch to True to show it again.
SHOW_UNIT_SELECTORS = False    # flow-unit and head-unit dropdowns
SHOW_PIPE_SUMMARY = False      # "Selected pipe: ..." line
SHOW_MOTOR = False             # motor estimate
SHOW_WALL_AND_ID = False       # wall / ID columns in the pipe comparison table
SHOW_WATER_TEMP = False        # water temperature input (Darcy-Weisbach only)
FITTINGS_ALLOWANCE_PCT = 0.0   # extra % on friction loss for fittings (0 = pure pipe friction)
WATER_TEMP_C = 25.0

# ============================================================ data
OD_INCH = {20: '1/2"', 25: '3/4"', 32: '1"', 40: '1 1/4"', 50: '1 1/2"',
           63: '2"', 75: '2 1/2"', 90: '3"', 110: '4"'}

# PE100 pressure classes -> SDR (used inside the app to get the wall thickness)
CLASSES = {"PN4": 41, "PN5": 33, "PN6": 26, "PN8": 21, "PN10": 17,
           "PN12.5": 13.6, "PN16": 11, "PN20": 9, "PN25": 7.4}

# material: (Hazen-Williams C, roughness k in mm)
MATERIALS = {
    "HDPE": (150, 0.0015), "LDPE": (150, 0.0015), "uPVC": (150, 0.0015),
    "Rubber lined": (140, 0.01), "New steel": (140, 0.045),
    "Medium steel": (120, 0.15), "Corroded steel": (100, 0.6),
    "Galvanized iron": (120, 0.15), "Glass": (140, 0.0015), "Lead": (130, 0.0015),
}

VOL_TO_L = {"litres/day": 1, "m³/day": 1000, "US gallons/day": 3.78541, "Imp. gallons/day": 4.54609}
LEN_TO_M = {"m": 1, "ft": 0.3048, "yd": 0.9144, "km": 1000}
FLOW_FROM_M3H = {"m³/h": 1, "L/min": 1000 / 60, "L/s": 1000 / 3600, "m³/min": 1 / 60,
                 "L/h": 1000, "m³/day": 24, "US GPM": 4.40287}
HEAD_FROM_M = {"m": 1, "ft": 3.28084, "bar": 0.0980665, "kPa": 9.80665, "psi": 1.42233}
PRESSURE_FROM_KPA = {"bar": 0.01, "kPa": 1.0, "psi": 0.145038, "MPa": 0.001,
                     "atm": 0.00986923, "kgf/cm²": 0.0101972}
G = 9.81

# crop: (peak Kc, root depth m, allowable depletion p)
CROPS = {"Tomato": (1.15, 1.0, 0.5), "Cabbage": (1.05, 0.5, 0.45), "Carrot": (1.05, 0.6, 0.5),
         "Cauliflower": (1.05, 0.6, 0.5), "Onion": (1.05, 0.6, 0.5), "Garlic": (1.0, 0.6, 0.5),
         "Egg plant": (1.05, 0.6, 0.5), "Peppers": (1.05, 0.8, 0.5), "Cucumber": (1.0, 0.6, 0.5),
         "Water melons": (1.0, 0.4, 0.5), "Beans": (1.15, 0.4, 0.6), "Cotton": (1.2, 1.0, 0.9),
         "Coffee": (1.1, 0.9, 0.5), "Maize": (1.2, 0.9, 0.8), "Millet": (1.0, 1.0, 0.7),
         "Rice": (1.2, 0.5, 0.5), "Banana": (1.2, 0.5, 0.55), "Pumpkin": (1.0, 0.6, 0.5)}
LTU = {"Cattle": 0.7, "Goats": 0.15, "Sheep": 0.15, "Pigs": 0.4, "Poultry": 0.1}

# ============================================================ look and feel (navy, blue and orange)
CSS = """
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 1.4rem; max-width: 1180px;}
[data-testid="stSidebar"] {background: linear-gradient(180deg, #031B45 0%, #000E28 100%);
    border-right: 2px solid #015FBF;}
[data-testid="stSidebar"] label, [data-testid="stSidebar"] label p, [data-testid="stSidebar"] label span,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {color: #FFFFFF !important;}
[data-testid="stSidebar"] h2 {color: #FE7C00 !important; font-size: 1.05rem; letter-spacing: .04em;
    text-transform: uppercase; border-bottom: 1px solid #015FBF; padding-bottom: .3rem;}
h1, h2, h3, h4, p, label, li {color: #FFFFFF;}
h3 {border-left: 5px solid #FE7C00; padding-left: 12px !important; margin-top: .8rem;}
[data-testid="stMetric"] {background: linear-gradient(135deg, #04204D 0%, #021433 100%);
    border: 1px solid #0B3A80; border-left: 5px solid #FE7C00; border-radius: 12px;
    padding: 14px 16px; box-shadow: 0 3px 12px rgba(0, 0, 0, .3);}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {color: #8FB8FF !important; font-size: .85rem;}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] div {color: #FFFFFF !important; font-weight: 700;}
[data-testid="stAlert"] {border-radius: 12px;}
</style>
"""


def setup_page():
    st.set_page_config(page_title="Pump & Irrigation Calculator", page_icon="💧", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title):
    st.title(title)


def full_width(fn, *args, **kwargs):
    """st.dataframe / st.data_editor that works on old AND new Streamlit versions."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except (TypeError, st.errors.StreamlitAPIException):
        return fn(*args, use_container_width=True, **kwargs)


# ============================================================ hydraulics
def wall_mm(od, sdr):
    return max(ceil(od / sdr * 10) / 10, 1.8)


def hazen_williams(q_m3h, length, d_m, c):
    q = q_m3h / 3600
    return 10.67 * length * q ** 1.852 / (c ** 1.852 * d_m ** 4.87)


def water_props(temp_c):
    mu = 2.414e-5 * 10 ** (247.8 / (temp_c + 133.15))
    rho = 1000 * (1 - (temp_c - 4) ** 2 / 119000)
    return rho, mu


def darcy_weisbach(q_m3h, length, d_m, k_mm, temp_c):
    rho, mu = water_props(temp_c)
    v = q_m3h / 3600 / (pi * d_m ** 2 / 4)
    re = rho * v * d_m / mu
    if re < 2300:
        f = 64 / max(re, 1e-9)
    else:
        f = 0.25 / log10(k_mm / 1000 / (3.7 * d_m) + 5.74 / re ** 0.9) ** 2
    return f * length / d_m * v ** 2 / (2 * G), f, re


def friction(q, length, d_m, method, c, k_mm, temp):
    if method.startswith("Hazen"):
        return hazen_williams(q, length, d_m, c), None, None
    return darcy_weisbach(q, length, d_m, k_mm, temp)


def length_input(label, default, key, min_value=0.0):
    col1, col2 = st.columns([2, 1])
    val = col1.number_input(label, min_value=min_value, value=default, step=0.5, key=key)
    unit = col2.selectbox("Unit", list(LEN_TO_M), key=key + "_u")
    return val * LEN_TO_M[unit]


# ============================================================ tool 1: pump sizing
def pump_sizing():
    with st.sidebar:
        st.header("Water requirement")
        c1, c2 = st.columns([2, 1])
        vol = c1.number_input("Daily water requirement", 0.0, value=10000.0, step=500.0)
        vol_u = c2.selectbox("Unit", list(VOL_TO_L), key="vol_u")
        hours = st.number_input("Pumping hours per day", 0.5, 24.0, 5.0, 0.5)

        st.header("Heights and distances")
        depth = length_input("Depth of water source", 30.0, "depth")
        elev = length_input("Elevation, source to tank", 5.0, "elev", min_value=-1000.0)
        dist = length_input("Horizontal distance, source to tank", 100.0, "dist")
        tank_h = length_input("Height of tank", 2.0, "tank")
        stand = length_input("Tank stand height", 3.0, "stand")

        st.header("Pipe")
        material = st.selectbox("Pipe material", list(MATERIALS), index=0)
        cls = st.selectbox("Pressure class (PN)", list(CLASSES), index=list(CLASSES).index("PN10"))
        pipe_choice = st.selectbox("Pipe size (outer diameter)",
                                   ["Auto (smallest within velocity limit)"] +
                                   [f"{mm} mm ({OD_INCH[mm]})" for mm in OD_INCH] +
                                   ["Custom inside diameter"])
        custom_id = None
        if pipe_choice.startswith("Custom"):
            custom_id = st.number_input("Inside diameter (mm)", 5.0, 500.0, 25.0, 0.1)

        st.header("Friction method")
        method = st.selectbox("Method", ["Hazen-Williams", "Darcy-Weisbach (Moody / Swamee-Jain)"])
        c_default, k_default = MATERIALS[material]
        c_val = st.number_input("Hazen-Williams C", 50.0, 160.0, float(c_default), 1.0)
        k_val = st.number_input("Roughness k (mm), for Darcy-Weisbach", 0.0, 5.0, float(k_default),
                                0.0005, format="%.4f")
        temp = (st.number_input("Water temperature (°C)", 0.0, 90.0, WATER_TEMP_C, 1.0)
                if SHOW_WATER_TEMP else WATER_TEMP_C)
        minor = FITTINGS_ALLOWANCE_PCT
        vmax = st.number_input("Max velocity (m/s)", 0.5, 4.0, 1.5, 0.1)
        eff = st.number_input("Pump efficiency (%)", 10.0, 90.0, 50.0)

        if SHOW_UNIT_SELECTORS:
            st.header("Display units")
            flow_u = st.selectbox("Flow unit", list(FLOW_FROM_M3H), index=0)
            head_u = st.selectbox("Head / pressure unit", list(HEAD_FROM_M), index=0)
        else:
            flow_u, head_u = "m³/h", "m"

    if vol <= 0:
        st.warning("Enter a daily water requirement greater than zero to see results.")
        return
    if depth + dist + tank_h + stand <= 0:
        st.warning("Pipe length is zero. Enter the depth, distance, tank height and stand height.")
        return

    daily_l = vol * VOL_TO_L[vol_u]
    q = daily_l / 1000 / hours
    static = depth + elev + tank_h + stand
    length = depth + dist + tank_h + stand
    sdr = CLASSES[cls]

    rows = []
    for od in OD_INCH:
        w = wall_mm(od, sdr)
        d_m = (od - 2 * w) / 1000                      # true bore, used for the velocity check
        hf, f, re = friction(q, length, od / 1000, method, c_val, k_val, temp)   # friction uses the OUTER diameter
        hf *= 1 + minor / 100
        v = q / 3600 / (pi * d_m ** 2 / 4)
        rows.append({"ext": od, "Dfric": od, "Pipe": f"{od} mm ({OD_INCH[od]})", "Wall (mm)": w,
                     "ID (mm)": round(d_m * 1000, 1), "Velocity (m/s)": round(v, 2),
                     "Friction (m)": round(hf, 2), "TDH (m)": round(static + hf, 2),
                     "OK": v <= vmax, "f": f, "Re": re, "hf": hf})
    df = pd.DataFrame(rows)

    if custom_id:
        d_m = custom_id / 1000
        hf, f, re = friction(q, length, d_m, method, c_val, k_val, temp)
        hf *= 1 + minor / 100
        v = q / 3600 / (pi * d_m ** 2 / 4)
        sel = {"Pipe": f"Custom ID {custom_id} mm", "Dfric": custom_id, "ID (mm)": custom_id, "Velocity (m/s)": round(v, 2),
               "Friction (m)": round(hf, 2), "TDH (m)": round(static + hf, 2), "OK": v <= vmax,
               "f": f, "Re": re, "hf": hf}
    elif pipe_choice.startswith("Auto"):
        ok = df[df["OK"]]
        sel = (ok.iloc[0] if not ok.empty else df.iloc[-1]).to_dict()
    else:
        sel = df[df["ext"] == int(pipe_choice.split()[0])].iloc[0].to_dict()

    tdh = sel["TDH (m)"]
    hf_exact = sel["hf"]
    loss_kpa = hf_exact * 1000 * G / 1000          # pressure loss = rho * g * h
    loss_bar = loss_kpa / 100
    hyd_kw = 1000 * G * (q / 3600) * tdh / 1000
    motor_kw = hyd_kw / (eff / 100) * 1.2

    def head_fmt(m, dp=2):
        return f"{m * HEAD_FROM_M[head_u]:.{dp}f} {head_u}"

    st.subheader("Flow rate (Q)")
    cols = st.columns(4)
    cols[0].metric(f"Q ({flow_u})", f"{q * FLOW_FROM_M3H[flow_u]:.3f}")
    cols[1].metric("L/min", f"{q * FLOW_FROM_M3H['L/min']:.3f}")
    cols[2].metric("L/s", f"{q * FLOW_FROM_M3H['L/s']:.3f}")
    cols[3].metric("L/day", f"{daily_l:,.0f}")

    st.subheader("Total Dynamic Head")
    cols = st.columns(4)
    cols[0].metric("TDH", head_fmt(tdh))
    cols[1].metric("Static head", head_fmt(static))
    cols[2].metric("Friction head loss", head_fmt(hf_exact, 4))
    cols[3].metric("Pipe length L", f"{length:.1f} m")

    pc = st.columns([1, 2])
    p_unit = pc[0].selectbox("Pressure unit", list(PRESSURE_FROM_KPA), index=0)
    pc[1].metric("Pressure loss", f"{loss_kpa * PRESSURE_FROM_KPA[p_unit]:.4f} {p_unit}")

    if SHOW_PIPE_SUMMARY:
        tag = "Recommended" if pipe_choice.startswith("Auto") else "Selected"
        st.info(f"{tag} pipe: **{sel['Pipe']}** ({material}, {cls}) · inside diameter {sel['ID (mm)']} mm · "
                f"velocity {sel['Velocity (m/s)']} m/s")
    if not sel["OK"]:
        st.warning("Velocity is above your limit for this pipe. Try a larger size.")

    if SHOW_MOTOR:
        st.subheader("Motor estimate")
        a, b = st.columns(2)
        a.metric("Hydraulic power", f"{hyd_kw:.2f} kW")
        b.metric("Suggested motor (+20% margin)", f"{motor_kw:.2f} kW", f"≈ {motor_kw * 1.341:.2f} HP",
                 delta_color="off")

    st.subheader("All pipe sizes compared")
    hide = ["ext", "Dfric", "f", "Re", "hf"] + ([] if SHOW_WALL_AND_ID else ["Wall (mm)", "ID (mm)"])
    show = df.drop(columns=hide).copy()
    show["OK"] = show["OK"].map({True: "✔", False: "✖"})
    full_width(st.dataframe, show, hide_index=True)

    with st.expander("Show the calculation"):
        st.write(f"**Q** = {daily_l:,.0f} L/day ÷ 1000 ÷ {hours} h = **{q:.3f} m³/h**")
        st.write(f"**Static head** = depth + elevation + tank height + stand = **{static:.2f} m**")
        st.write(f"**L** = depth + distance + tank height + stand = **{length:.2f} m**")
        if method.startswith("Hazen"):
            st.latex(r"h_f = \frac{10.67\,L\,Q^{1.852}}{C^{1.852}\,D^{4.87}}")
            st.write(f"C = {c_val:g}, D = {sel['Dfric']:g} mm "
                     f"({'inside diameter as entered' if custom_id else 'outer diameter'}; "
                     f"Q in m³/s, D and L in metres)")
        else:
            st.latex(r"h_f = f\,\frac{L}{D}\,\frac{v^2}{2g}")
            if sel["f"]:
                st.write(f"Reynolds number = {sel['Re']:,.0f}, friction factor f = {sel['f']:.4f}, k = {k_val} mm")
        if minor:
            st.write(f"Friction loss includes a {minor:g}% allowance for fittings.")
        st.write(f"**Friction head loss** = {hf_exact:.4f} m of water")
        st.write(f"**Pressure loss** = ρ·g·h = 1000 × 9.81 × {hf_exact:.4f} = "
                 f"{loss_kpa * 1000:,.0f} Pa = **{loss_bar:.4f} bar**")
        st.write(f"**TDH = {static:.2f} + {hf_exact:.2f} = {tdh:.2f} m**")


# ============================================================ tool 2: water demand
def water_demand():
    st.caption("Crop water requirement → net and gross depth → daily volume → pumping flow.")
    left, right = st.columns(2)
    with left:
        st.subheader("Crop and climate")
        crop = st.selectbox("Design crop", list(CROPS))
        kc0, zr0, p0 = CROPS[crop]
        kc = st.number_input("Kc (mid season)", 0.1, 2.0, kc0, 0.05, key=f"kc{crop}")
        eto = st.number_input("Peak ETo (mm/day)", 0.0, 12.0, 4.84, 0.01)
        rain = st.number_input("Effective rain in that month (mm/day)", 0.0, 20.0, 0.23, 0.01)
        etc = max(eto * kc - rain, 0.01)
        st.metric("Crop water requirement (ETc − rain)", f"{etc:.2f} mm/day")

        st.subheader("Soil")
        fc = st.number_input("Field capacity (m³/m³)", 0.05, 0.6, 0.285, 0.005, format="%.3f")
        pwp = st.number_input("Permanent wilting point (m³/m³)", 0.01, 0.5, 0.19, 0.005, format="%.3f")
        p = st.number_input("Allowable depletion, p", 0.1, 1.0, p0, 0.05, key=f"p{crop}")
        zr = st.number_input("Effective root depth Zr (m)", 0.1, 3.0, 0.6, 0.1, key=f"zr{crop}",
                             help=f"Table value for {crop}: {zr0} m.")
    with right:
        st.subheader("System")
        area = st.number_input("Command area (ha)", 0.1, 1000.0, 5.0, 0.5)
        eff = st.number_input("Application efficiency", 0.3, 1.0, 0.85, 0.05)
        pr = st.number_input("Sprinkler / rainspray precipitation rate (mm/hr)", 1.0, 100.0, 15.0, 1.0)
        infil = st.number_input("Soil infiltration rate (mm/hr)", 1.0, 100.0, 25.0, 1.0)
        st.subheader("Livestock")
        counts = {a: st.number_input(f"{a} (number)", 0, 100000, v, key=f"n_{a}")
                  for a, v in zip(LTU, [200, 100, 50, 50, 0])}
        deficit = st.number_input("Irrigation supplied under deficit irrigation (%)", 10, 100, 50)
        hours = st.number_input("Pumping hours per day", 1.0, 24.0, 7.0, 0.5, key="wd_hours")

    aw = (fc - pwp) * 1000
    dnet = aw * p * zr
    freq = dnet / etc
    fa = st.number_input("Adopted irrigation frequency (days)", 1, 30, 4,
                         help="Keep it at or below the maximum frequency shown below.")
    dnet_c = fa * etc
    dgross = dnet_c / eff
    shift = dgross / pr
    irr_m3 = dgross * 10 * (area / fa)                  # 1 mm on 1 ha = 10 m3
    live_m3 = sum(n * LTU[a] * 50 for a, n in counts.items()) / 1000
    full = irr_m3 + live_m3
    deficit_m3 = irr_m3 * deficit / 100 + live_m3
    flow = deficit_m3 / hours

    st.divider()
    a, b, c, d = st.columns(4)
    a.metric("Net depth dnet", f"{dnet:.1f} mm")
    b.metric("Max frequency", f"{freq:.2f} days")
    c.metric("Gross depth", f"{dgross:.1f} mm")
    d.metric("Time per set", f"{shift:.2f} h")
    a, b, c, d = st.columns(4)
    a.metric("Irrigation", f"{irr_m3:.1f} m³/day")
    b.metric("Livestock", f"{live_m3:.2f} m³/day")
    c.metric("Total (full irrigation)", f"{full:.1f} m³/day")
    d.metric(f"Total ({deficit}% irrigation)", f"{deficit_m3:.1f} m³/day")
    st.success(f"Design pumping flow = {deficit_m3:.1f} m³/day ÷ {hours:g} h = **{flow:.2f} m³/h** "
               f"({flow * 1000 / 60:.0f} L/min, {flow / 3.6:.2f} L/s)")
    if fa > freq:
        st.warning("The adopted frequency is longer than the maximum frequency: the crop may be stressed.")
    if pr > infil:
        st.warning("Precipitation rate exceeds the soil infiltration rate: expect runoff.")


# ============================================================ main
TOOLS = {"Pump Sizing": ("Pump Sizing Calculator", pump_sizing),
         "Water Demand": ("Water Demand", water_demand)}


def main():
    setup_page()
    with st.sidebar:
        st.header("Menu")
        tool = st.radio("Tool", list(TOOLS), label_visibility="collapsed")
    title, fn = TOOLS[tool]
    hero(title)
    fn()

main()
