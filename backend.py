# ----------------------------
# Imports
# ----------------------------
import os
import re
import html
import time
import warnings
import numpy as np
import pandas as pd
import itables

warnings.filterwarnings("ignore")

# itables config
itables.options.style = "table-layout:auto;width:auto"
itables.options.showIndex = False

# ----------------------------
# Helpers
# ----------------------------
def make_clickable(target, view):
    """Generates an HTML link string."""
    if not target:
        return ""
    href = f"{target}.html"
    return f'<a target="_blank" href="{href}">{html.escape(str(view))}</a>'

def get_design_name(common_setup_path):
    if not os.path.exists(common_setup_path):
        return None
    with open(common_setup_path) as f:
        for line in f:
            m = re.search(r'set\s+DESIGN_NAME\s+(?:"|\{)?([^"\}\s]+)', line)
            if m:
                return m.group(1)
    return None

def write_comparison_html(df, outdir):
    os.makedirs(outdir, exist_ok=True)
    # The comparison dashboard uses its own styling for clickable Design links
    styled = df.style.format({
        "Design": lambda x: make_clickable(x, x)
    })
    with open(os.path.join(outdir, "comparison_dashboard.html"), "w") as f:
        f.write("""
        <html>
        <head><title>Timing Comparison Dashboard</title></head>
        <body>
            <div style="margin-bottom: 15px;">
                <a href="/" style="text-decoration: none; padding: 6px 12px; background-color: #2c7be5; color: white; border-radius: 4px; font-weight: bold;">
                    ⬅ Back to Home
                </a>
            </div>
            <h1><center>Timing Comparison Dashboard</center></h1>
        """)
        # allow_html=True is the key for clickable links
        f.write(itables.to_html_datatable(styled, allow_html=True))
        f.write("</body></html>")

# ----------------------------
# Report discovery
# ----------------------------
def find_reports(cwd, design, design_name):
    reports = {"timing": {}, "max_trans": {}, "max_cap": {}, "hist": {}}
    def add(scen, key, fname):
        path = os.path.join(cwd, design, scen, "reports", fname)
        if os.path.exists(path):
            reports[key][scen] = path

    design_dir = os.path.join(cwd, design)
    if not os.path.isdir(design_dir): return reports

    for scen in sorted(os.listdir(design_dir)):
        if not scen.startswith("scen"): continue
        if not os.path.isdir(os.path.join(design_dir, scen)): continue
        add(scen, "timing", f"{design_name}_report_global_timing.report")
        add(scen, "max_trans", f"{design_name}_max_trans.report")
        add(scen, "max_cap", f"{design_name}_max_cap.report")
        add(scen, "hist", f"{design_name}_report_timing.report")

    base = os.path.join(cwd, design, "reports")
    for key, fname in [("timing", f"{design_name}_report_global_timing.report"),
                       ("max_trans", f"{design_name}_max_trans.report"),
                       ("max_cap", f"{design_name}_max_cap.report"),
                       ("hist", f"{design_name}_report_timing.report")]:
        path = os.path.join(base, fname)
        if os.path.exists(path): reports[key]["global"] = path
    return reports

# ----------------------------
# Parsers
# ----------------------------
def parse_timing(report_path):
    setup = {"WNS": "0", "TNS": "0", "NUM": "0"}
    hold  = {"WNS": "0", "TNS": "0", "NUM": "0"}
    mode, header_seen = None, False
    try:
        with open(report_path) as f:
            for line in f:
                l = line.strip()
                if l == "Setup violations": mode, header_seen = "setup", False; continue
                if l == "Hold violations": mode, header_seen = "hold", False; continue
                if "No setup violations found" in l or "No hold violations found" in l: mode = None; continue
                if not mode: continue
                if l.startswith("Total"): header_seen = True; continue
                if header_seen:
                    parts = l.split()
                    if len(parts) >= 2:
                        key, val = parts[0], parts[1]
                        target = setup if mode == "setup" else hold
                        if key in target: target[key] = val
    except: pass
    return ([setup["WNS"], setup["TNS"], setup["NUM"]], [hold["WNS"], hold["TNS"], hold["NUM"]])

def extract_report_date(report_path):
    if not report_path or not os.path.exists(report_path): return ""
    try:
        with open(report_path) as f:
            for _ in range(50):
                line = f.readline()
                if not line: break
                if re.search(r"^\s*Date\s*[:=]", line, re.IGNORECASE):
                    return line.split(":", 1)[-1].strip()
    except: pass
    return ""

def extract_simple_count(path, keyword):
    if not path or not os.path.exists(path): return ""
    with open(path) as f:
        return sum(1 for line in f if keyword.lower() in line.lower())

def extract_freq(report_path):
    try:
        with open(report_path) as f:
            for line in f:
                m = re.search(r"([\d.]+)\s*GHz", line)
                if m: return m.group(1)
    except: pass
    return ""
#----------------------------
# Back button
#----------------------------
def add_back_button(html_content):
    """Injects a 'Back to Search' button at the top of the generated HTML."""
    back_button_html = """
    <div style="background: #f8f9fa; padding: 10px; border-bottom: 2px solid #2c7be5; margin-bottom: 20px; font-family: sans-serif;">
        <a href="/" style="text-decoration: none; background: #2c7be5; color: white; padding: 8px 15px; border-radius: 4px; font-weight: bold;">
            ⬅ Back to Design Selection
        </a>
        <span style="margin-left: 20px; color: #666; font-style: italic;">Timing Dashboard Report</span>
    </div>
    """
    # Insert the button right after the <body> tag
    if "<body>" in html_content:
        return html_content.replace("<body>", f"<body>{back_button_html}")
    return back_button_html + html_content
# ----------------------------
# Histogram
# ----------------------------
def gen_histogram(report_path, die, design_id):
    arr = []
    try:
        with open(report_path) as f:
            for line in f:
                if "(VIOLATED)" in line and "slack" in line.lower():
                    nums = re.findall(r"-?\d+\.\d+", line)
                    if nums: arr.append(abs(float(nums[-1])))
    except: return None
    if not arr: return None
    bins = [0, 0.01, 0.02, 0.03, np.inf]
    counts, edges = np.histogram(arr, bins=bins)
    df = pd.DataFrame([counts], columns=[str(e) for e in edges[:-1]])
    df.insert(0, "Design", design_id)
    df.insert(0, "Die", die)
    return df

# ----------------------------
# DataFrame generation
# ----------------------------
def generate_df(design_id, reports, die):
    rows = []
    hist_outputs = {}
    for scen, rpt in reports["timing"].items():
        setup, hold = parse_timing(rpt)
        row = {
            "Die": die, "Design": design_id, "Scenario": scen,
            "SETUP[WNS]": setup[0], "SETUP[TNS]": setup[1], "SETUP[NUM]": setup[2],
            "HOLD[WNS]": hold[0], "HOLD[TNS]": hold[1], "HOLD[NUM]": hold[2],
            "Annotated nets": extract_simple_count(rpt, "Annotated"),
            "Freq. GHz": extract_freq(rpt), "Histogram": "",
        }
        if scen in reports["max_trans"]: row["Max Trans Data"] = extract_simple_count(reports["max_trans"][scen], "")
        if scen in reports["max_cap"]: row["Max Cap"] = extract_simple_count(reports["max_cap"][scen], "")
        
        if scen in reports["hist"]:
            h_df = gen_histogram(reports["hist"][scen], die, design_id)
            if h_df is not None:
                h_name = f"{design_id}_{scen}_histogram"
                row["Histogram"] = h_name
                hist_outputs[h_name] = h_df
        rows.append(row)

    df = pd.DataFrame(rows)
    # This styling is what creates the <a> tags
    styled = df.style.format({
        "Design": lambda x: make_clickable(x, x),
        "Die": lambda x: make_clickable(x, x),
        "Histogram": lambda x: make_clickable(x, x) if x else ""
    })
    return styled, df, hist_outputs

# ----------------------------
# HTML writer
# ----------------------------
def write_html(obj, name, outdir, report_date=""):
    os.makedirs(outdir, exist_ok=True)
    date_to_show = report_date or time.ctime()
    
    # We pass 'obj' which can be Styled or DataFrame. 
    # itables will handle Styled objects if allow_html is True.
    with open(os.path.join(outdir, f"{name}.html"), "w") as f:
        f.write(f"""
        <html>
        <head>
            <title>Timing Dashboard - {name}</title>
            <style>
                body {{ font-family: sans-serif; margin: 20px; }}
                a {{ color: #2c7be5; text-decoration: none; font-weight: bold; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <div style="margin-bottom:15px;"><a href="/" style="text-decoration:none;padding:6px 12px;background:#2c7be5;color:white;border-radius:4px;font-weight:bold;">⬅ Back to Home</a></div>
            <pre style="background:#f8f9fa;padding:10px;border:1px solid #ddd;">Design : {name}\nDate   : {date_to_show}</pre>
        """)
        # allow_html=True ensures the <a> tags are rendered as links
        f.write(itables.to_html_datatable(obj, allow_html=True))
        f.write("</body></html>")

def compute_baseline_deltas(df, baseline_design, metrics):
    df = df.copy()
    for col in metrics: df[col] = pd.to_numeric(df[col], errors="coerce")
    baseline = df[df["Design"] == baseline_design].groupby("Scenario")[metrics].first()
    for col in metrics:
        delta_col = f"Δ{col}"
        df[delta_col] = df.apply(lambda r: (r[col] - baseline.loc[r["Scenario"], col]) if r["Scenario"] in baseline.index and r["Design"] != baseline_design else (0.0 if r["Design"] == baseline_design else None), axis=1)
    return df

# ----------------------------
# Main entry
# ----------------------------
def run_chip(cwd, die, outdir, designs):
    os.makedirs(outdir, exist_ok=True)
    all_raw = []
    generated = []

    for design_folder in designs:
        setup_path = os.path.join(cwd, design_folder, "common_setup.tcl")
        design_name_tcl = get_design_name(setup_path) or design_folder
        
        reports = find_reports(cwd, design_folder, design_name_tcl)
        report_date = extract_report_date(next(iter(reports["timing"].values()))) if reports["timing"] else ""

        styled, raw, hists = generate_df(design_folder, reports, die)

        # FIX: Pass 'styled' instead of 'raw' to write_html to keep the links!
        write_html(styled, design_folder, outdir, report_date)

        # Write histograms
        for h_name, h_df in hists.items():
            # For histograms, convert to styled if you want them clickable too
            h_styled = h_df.style.format({"Design": lambda x: make_clickable(x, x), "Die": lambda x: make_clickable(x, x)})
            write_html(h_styled, h_name, outdir, report_date)

        raw_copy = raw.copy()
        raw_copy["Design"] = design_folder
        all_raw.append(raw_copy)
        generated.append(design_folder)

    if len(all_raw) > 1:
        compare_df = pd.concat(all_raw, ignore_index=True)
        metrics = ["SETUP[WNS]", "SETUP[TNS]", "SETUP[NUM]", "HOLD[WNS]", "HOLD[TNS]", "HOLD[NUM]", "Freq. GHz"]
        compare_df = compute_baseline_deltas(compare_df[["Design", "Scenario"] + metrics], generated[0], metrics)
        write_comparison_html(compare_df, outdir)

    return list(dict.fromkeys(generated))
