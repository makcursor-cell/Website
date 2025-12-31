# ----------------------------
# backend_power.py (regex-parsing, formatted output)
# ----------------------------

import os
import re
import pandas as pd
import warnings
import time

warnings.filterwarnings("ignore")

# ----------------------------
# Helpers / Parsers
# ----------------------------
def find_voltus_reports(cwd, design):
    """
    Locate all Voltus reports for a given design.
    Returns a dict: {scenario_name: [list of .report.avgpwr full paths]}
    """
    reports_dict = {}
    voltus_dir = os.path.join(cwd, design, "voltus_work")
    if not os.path.isdir(voltus_dir):
        return reports_dict

    for folder in sorted(os.listdir(voltus_dir)):
        if folder.startswith("voltus_reports"):
            folder_path = os.path.join(voltus_dir, folder)
            if not os.path.isdir(folder_path):
                continue
            avgpwr_files = [
                os.path.join(folder_path, f)
                for f in os.listdir(folder_path)
                if f.endswith(".report.avgpwr")  # tolerate extensions
            ]
            if avgpwr_files:
                reports_dict[folder] = avgpwr_files

    return reports_dict

def _to_float(s):
    if s is None:
        return float("nan")
    s = str(s).strip()
    if s == "":
        return float("nan")
    s = s.replace(",", "")
    s = s.replace("%", "")
    try:
        return float(s)
    except Exception:
        m = re.search(r"-?\d+(\.\d+)?", s)
        if m:
            try:
                return float(m.group(0))
            except:
                pass
    return float("nan")

def parse_avgpwr_file(file_path):
    """
    Parse a .report.avgpwr file into:
      - total_summary: dict {Internal, Switching, Leakage, Total}
      - group_df: DataFrame(columns=[Group, Internal, Switching, Leakage, Total, Percentage])
      - clock_df: DataFrame(columns=[Clock, Internal, Switching, Leakage, Total, Percentage])
      - rail_df: DataFrame(columns=[Rail, Voltage, Internal, Switching, Leakage, Total, Percentage])
    The parser is tolerant of spacing/format variations by using regex and multi-space splitting.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            lines = [ln.rstrip() for ln in fh]
    except Exception:
        lines = []

    # State machine for sections
    section = None
    total_summary = {}
    group_rows = []
    clock_rows = []
    rail_rows = []

    # Regex patterns for total summary lines
    patterns_total = {
        "Internal": re.compile(r"Total\s+Internal\s+Power\s*[:\-]?\s*([0-9,\.Ee+-]+)"),
        "Switching": re.compile(r"Total\s+Switching\s+Power\s*[:\-]?\s*([0-9,\.Ee+-]+)"),
        "Leakage": re.compile(r"Total\s+Leakage\s+Power\s*[:\-]?\s*([0-9,\.Ee+-]+)"),
        "Total": re.compile(r"^Total\s+Power\s*[:\-]?\s*([0-9,\.Ee+-]+)")
    }

    # Table row splitter: split on 2 or more spaces to keep names with single spaces
    def split_row(s):
        parts = re.split(r"\s{2,}", s.strip())
        parts = [p.strip() for p in parts if p.strip() != ""]
        return parts

    # Identify when group/clock/rail tables start by header lines
    for ln in lines:
        ln_stripped = ln.strip()
        # detect section headers
        if re.match(r"^Total Power\b", ln_stripped, re.I):
            section = "total"
            continue
        if re.match(r"^Group\b", ln_stripped) and "Internal" in ln_stripped:
            section = "group"
            continue
        if re.match(r"^Clock\b", ln_stripped) and "Internal" in ln_stripped:
            section = "clock"
            continue
        if re.match(r"^Rail\b", ln_stripped):
            section = "rail"
            continue
        # skip separator lines
        if re.match(r"^[-*]{3,}$", ln_stripped) or re.match(r"^\*[-]{3,}", ln_stripped):
            continue

        # parse based on section
        if section == "total":
            # try all total patterns on this line
            for key, pat in patterns_total.items():
                m = pat.search(ln)
                if m:
                    total_summary[key] = _to_float(m.group(1))
                    break
            # also handle lines like "Total Internal Power:   62.015345      59.71%"
            # fallback: look for known labels in line
            if "Total Internal Power" in ln and "Internal" not in total_summary:
                m = re.search(r"Total\s+Internal\s+Power.*?([0-9,\.Ee+-]+)", ln)
                if m:
                    total_summary["Internal"] = _to_float(m.group(1))
            if "Total Switching Power" in ln and "Switching" not in total_summary:
                m = re.search(r"Total\s+Switching\s+Power.*?([0-9,\.Ee+-]+)", ln)
                if m:
                    total_summary["Switching"] = _to_float(m.group(1))
            if "Total Leakage Power" in ln and "Leakage" not in total_summary:
                m = re.search(r"Total\s+Leakage\s+Power.*?([0-9,\.Ee+-]+)", ln)
                if m:
                    total_summary["Leakage"] = _to_float(m.group(1))
            if ln.strip().startswith("Total Power") and "Total" not in total_summary:
                m = re.search(r"Total\s+Power.*?([0-9,\.Ee+-]+)", ln)
                if m:
                    total_summary["Total"] = _to_float(m.group(1))
        elif section == "group":
            # ignore header line variants
            if re.search(r"^Group\s+.*Internal", ln, re.I):
                continue
            parts = split_row(ln)
            if not parts:
                continue
            # Expect: [Group Name, Internal, Switching, Leakage, Total, Percentage]
            # But group name may include spaces -> split_row already handles that.
            if len(parts) >= 6:
                name = parts[0]
                internal = _to_float(parts[1])
                switching = _to_float(parts[2])
                leakage = _to_float(parts[3])
                total = _to_float(parts[4])
                pct = _to_float(parts[5])
                group_rows.append([name, internal, switching, leakage, total, pct])
            else:
                # try to pull numbers from the end of the line
                nums = re.findall(r"([0-9,\.Ee+-]+)", ln)
                if len(nums) >= 4:
                    pct = _to_float(nums[-1])
                    total = _to_float(nums[-2])
                    leakage = _to_float(nums[-3])
                    switching = _to_float(nums[-4])
                    # name is the remaining prefix
                    name = ln[:ln.rfind(nums[-4])].strip()
                    group_rows.append([name, _to_float(switching if False else nums[-4]), switching, leakage, total, pct])
        elif section == "clock":
            if re.search(r"^Clock\s+.*Internal", ln, re.I):
                continue
            parts = split_row(ln)
            if not parts:
                continue
            # Expect: [Clock Name, Internal, Switching, Leakage, Total, Percentage]
            if len(parts) >= 6:
                name = parts[0]
                internal = _to_float(parts[1])
                switching = _to_float(parts[2])
                leakage = _to_float(parts[3])
                total = _to_float(parts[4])
                pct = _to_float(parts[5])
                clock_rows.append([name, internal, switching, leakage, total, pct])
            else:
                nums = re.findall(r"([0-9,\.Ee+-]+)", ln)
                if len(nums) >= 4:
                    pct = _to_float(nums[-1])
                    total = _to_float(nums[-2])
                    leakage = _to_float(nums[-3])
                    switching = _to_float(nums[-4])
                    name = ln[:ln.rfind(nums[-4])].strip()
                    clock_rows.append([name, _to_float(nums[-4]), switching, leakage, total, pct])
        elif section == "rail":
            if re.search(r"^Rail\s+.*Voltage", ln, re.I):
                continue
            parts = split_row(ln)
            if not parts:
                continue
            # Expect: [Rail Name, Voltage, Internal, Switching, Leakage, Total, Percentage]
            if len(parts) >= 7:
                name = parts[0]
                voltage = parts[1]
                internal = _to_float(parts[2])
                switching = _to_float(parts[3])
                leakage = _to_float(parts[4])
                total = _to_float(parts[5])
                pct = _to_float(parts[6])
                rail_rows.append([name, voltage, internal, switching, leakage, total, pct])
            else:
                # fallback: extract numbers; assume first token is name, second is voltage if present
                nums = re.findall(r"([0-9,\.Ee+-]+)", ln)
                if len(nums) >= 4:
                    # attempt to find voltage (a short token like 0.8) near name
                    tokens = ln.split()
                    if len(tokens) >= 2 and re.match(r"^[0-9\.]+$", tokens[1]):
                        name = tokens[0]
                        voltage = tokens[1]
                        internal = _to_float(nums[0])
                        switching = _to_float(nums[1])
                        leakage = _to_float(nums[2])
                        total = _to_float(nums[3])
                        pct = _to_float(nums[4]) if len(nums) > 4 else float("nan")
                        rail_rows.append([name, voltage, internal, switching, leakage, total, pct])

    # Build DataFrames
    group_df = pd.DataFrame(group_rows, columns=["Group", "Internal", "Switching", "Leakage", "Total", "Percentage"]) if group_rows else pd.DataFrame(columns=["Group","Internal","Switching","Leakage","Total","Percentage"])
    clock_df = pd.DataFrame(clock_rows, columns=["Clock", "Internal", "Switching", "Leakage", "Total", "Percentage"]) if clock_rows else pd.DataFrame(columns=["Clock","Internal","Switching","Leakage","Total","Percentage"])
    rail_df = pd.DataFrame(rail_rows, columns=["Rail", "Voltage", "Internal", "Switching", "Leakage", "Total", "Percentage"]) if rail_rows else pd.DataFrame(columns=["Rail","Voltage","Internal","Switching","Leakage","Total","Percentage"])

    # Ensure numeric types
    for df, cols in [(group_df, ["Internal","Switching","Leakage","Total","Percentage"]),
                     (clock_df, ["Internal","Switching","Leakage","Total","Percentage"]),
                     (rail_df, ["Internal","Switching","Leakage","Total","Percentage"])]:
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

    # Fill total_summary from parsed objects if some keys missing
    def safe_sum(series):
        try:
            return float(pd.to_numeric(series, errors="coerce").sum())
        except:
            return float("nan")

    if not group_df.empty:
        # many reports provide group totals; use those if present
        if "Internal" not in total_summary or pd.isna(total_summary.get("Internal")):
            total_summary["Internal"] = safe_sum(group_df["Internal"])
        if "Switching" not in total_summary or pd.isna(total_summary.get("Switching")):
            total_summary["Switching"] = safe_sum(group_df["Switching"])
        if "Leakage" not in total_summary or pd.isna(total_summary.get("Leakage")):
            total_summary["Leakage"] = safe_sum(group_df["Leakage"])
        if "Total" not in total_summary or pd.isna(total_summary.get("Total")):
            total_summary["Total"] = safe_sum(group_df["Total"])

    # final numeric coercion for summary
    for k in ["Internal","Switching","Leakage","Total"]:
        if k not in total_summary:
            total_summary[k] = float("nan")
        else:
            total_summary[k] = _to_float(total_summary[k])

    return {
        "Total Summary": total_summary,
        "Group Power": group_df,
        "Clock Power": clock_df,
        "Rail Power": rail_df
    }

# ----------------------------
# HTML writer (formatted text output)
# ----------------------------
def _fmt(v, precision=6, trim=False):
    try:
        if pd.isna(v):
            return ""
    except:
        pass
    try:
        v_f = float(v)
    except:
        return str(v)
    if precision == 0:
        s = f"{v_f:,.0f}"
    else:
        s = f"{v_f:,.{precision}f}"
    if trim:
        # remove trailing zeros and dot
        s = s.rstrip("0").rstrip(".")
    return s

def write_html(obj, name, outdir, report_date=""):
    """
    Write a text-formatted HTML page matching the requested layout.
    obj: dict of parsed sections returned from parse_avgpwr_file
    """
    os.makedirs(outdir, exist_ok=True)
    html_path = os.path.join(outdir, f"{name}.html")

    total = obj.get("Total Summary", {})
    t_internal = total.get("Internal", float("nan"))
    t_switch = total.get("Switching", float("nan"))
    t_leak = total.get("Leakage", float("nan"))
    t_total = total.get("Total", float("nan"))

    def pct_str(v):
        try:
            if pd.isna(v) or pd.isna(t_total) or t_total == 0:
                return ""
            return f"{(float(v) / float(t_total) * 100):.2f}%"
        except:
            return ""

    lines = []
    lines.append("Total Power")
    lines.append("-" * 58)
    lines.append(f"Total Internal Power:         {_fmt(t_internal,6):>12}       {pct_str(t_internal)}")
    lines.append(f"Total Switching Power:        {_fmt(t_switch,6):>12}       {pct_str(t_switch)}")
    lines.append(f"Total Leakage Power:          {_fmt(t_leak,6):>12}       {pct_str(t_leak)}")
    lines.append("-" * 58)
    lines.append(f"Total Power:                  {_fmt(t_total,6):>12}      100.00%")
    lines.append("-" * 58)
    lines.append("")

    # Group table
    group_df = obj.get("Group Power", pd.DataFrame())
    lines.append("Group                           Internal   Switching     Leakage     Total    Percentage")
    lines.append("-" * 89)
    if not group_df.empty:
        for _, r in group_df.iterrows():
            name_col = str(r.get("Group", "")).ljust(30)[:30]
            internal = _fmt(r.get("Internal", 0), 2, trim=True)
            switching = _fmt(r.get("Switching", 4), 4, trim=True)
            leakage = _fmt(r.get("Leakage", 4), 4, trim=True)
            total_g = _fmt(r.get("Total", 0), 2, trim=True)
            pct = _fmt(r.get("Percentage", (r.get("Total", 0)/t_total*100) if t_total not in (None,0) and not pd.isna(t_total) else 0), 2, trim=True)
            lines.append(f"{name_col} {internal:>8}   {switching:>8}     {leakage:>8}     {total_g:>8}    {pct:>8}")
    else:
        lines.append("(No Group Power data found)")
    # Group totals row
    if not group_df.empty:
        tot_internal = group_df["Internal"].sum(skipna=True)
        tot_switch = group_df["Switching"].sum(skipna=True)
        tot_leak = group_df["Leakage"].sum(skipna=True)
        tot_total = group_df["Total"].sum(skipna=True)
    else:
        tot_internal = t_internal
        tot_switch = t_switch
        tot_leak = t_leak
        tot_total = t_total
    lines.append("-" * 89)
    lines.append(f"{'Total':30} { _fmt(tot_internal,2):>8}    { _fmt(tot_switch,2):>8}        { _fmt(tot_leak,3):>8}       { _fmt(tot_total,1):>8}    {(_fmt(100,0))}")
    lines.append("-" * 89)
    lines.append("")

    # Clock table
    clock_df = obj.get("Clock Power", pd.DataFrame())
    lines.append("Clock")
    lines.append("-" * 89)
    if not clock_df.empty:
        for _, r in clock_df.iterrows():
            name_col = str(r.get("Clock", "")).ljust(30)[:30]
            internal = _fmt(r.get("Internal", 0), 2)
            switching = _fmt(r.get("Switching", 2), 2)
            leakage = _fmt(r.get("Leakage", 3), 3)
            total_c = _fmt(r.get("Total", 0), 2)
            pct = _fmt(r.get("Percentage", 0), 2)
            lines.append(f"{name_col} {internal:>8}       {switching:>8}       {leakage:>8}       {total_c:>8}     {pct:>6}")
    else:
        lines.append("(No Clock Power data found)")
    lines.append("-" * 89)
    # Clock totals (excluding duplicates) - sum of clock_df or fallback to totals
    if not clock_df.empty:
        c_tot_internal = clock_df["Internal"].sum(skipna=True)
        c_tot_switch = clock_df["Switching"].sum(skipna=True)
        c_tot_leak = clock_df["Leakage"].sum(skipna=True)
        c_tot_total = clock_df["Total"].sum(skipna=True)
    else:
        c_tot_internal = t_internal
        c_tot_switch = t_switch
        c_tot_leak = t_leak
        c_tot_total = t_total
    lines.append(f"{'Total (excluding duplicates)':30} {_fmt(c_tot_internal,2):>8}      {_fmt(c_tot_switch,2):>8}       {_fmt(c_tot_leak,3):>8}       {_fmt(c_tot_total,1):>8}     100")
    lines.append("-" * 89)
    lines.append("")

    # Rail table
    rail_df = obj.get("Rail Power", pd.DataFrame())
    lines.append("Rail")
    lines.append("-" * 89)
    if not rail_df.empty:
        for _, r in rail_df.iterrows():
            name_col = str(r.get("Rail", "")).ljust(30)[:30]
            voltage = str(r.get("Voltage", "")).ljust(6)[:6]
            internal = _fmt(r.get("Internal", 0), 2)
            switching = _fmt(r.get("Switching", 2), 2)
            leakage = _fmt(r.get("Leakage", 3), 3)
            total_r = _fmt(r.get("Total", 0), 1)
            pct = _fmt(r.get("Percentage", 0), 2)
            lines.append(f"{name_col} {voltage:>6}  {internal:>8}    {switching:>8}    {leakage:>8}    {total_r:>8}    {pct:>6}")
    else:
        lines.append("(No Rail Power data found)")
    lines.append("-" * 89)
    # final totals row (repeat totals)
    lines.append(f"{'':30} {_fmt(t_internal,2):>8}    {_fmt(t_switch,2):>8}      {_fmt(t_leak,3):>8}     {_fmt(t_total,1):>8}     100")
    lines.append("-" * 89)

    pre_text = "\n".join(lines)
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write("<html><head><meta charset='utf-8'><title>Power Dashboard - ")
        fh.write(str(name))
        fh.write("</title><style>body{font-family: monospace; white-space: pre; padding:20px; background:#fff;}</style></head><body>\n")
        fh.write(f"<div style='margin-bottom:8px;'><a href='/' style='text-decoration:none;padding:6px 12px;background:#2c7be5;color:white;border-radius:4px;'>⬅ Back</a></div>\n")
        if report_date:
            fh.write(f"<div style='margin-bottom:6px;font-family:monospace;'>Date: {report_date}</div>\n")
        fh.write("<pre>\n")
        fh.write(pre_text)
        fh.write("\n</pre>\n</body></html>")

    return html_path

# ----------------------------
# DataFrame generation
# ----------------------------
def generate_power_df(design, reports_dict):
    """
    Convert all avgpwr reports into dict of parsed report data:
    {scenario_name: {file_name: parsed_obj}}
    """
    output = {}
    for scenario, files in reports_dict.items():
        scenario_tables = {}
        for fpath in files:
            parsed = parse_avgpwr_file(fpath)
            scenario_tables[os.path.basename(fpath)] = parsed
        output[scenario] = scenario_tables
    return output

# ----------------------------
# Main entry
# ----------------------------
def run_power(cwd, outdir, designs):
    """
    Generate formatted HTML dashboards for a list of designs.
    Returns a list of generated HTML file basenames (without .html).
    """
    os.makedirs(outdir, exist_ok=True)
    generated = []

    for design in designs:
        reports_dict = find_voltus_reports(cwd, design)
        if not reports_dict:
            continue

        dfs_dict = generate_power_df(design, reports_dict)
        for scenario, tables_dict in dfs_dict.items():
            base = f"{design}_{scenario}"
            for file_name, parsed_obj in tables_dict.items():
                safe_file = re.sub(r"[^\w\-_\.]", "_", file_name)
                page_name = f"{base}_{safe_file}"
                write_html(parsed_obj, page_name, outdir, report_date=time.ctime())
                generated.append(page_name)

    return list(dict.fromkeys(generated))
