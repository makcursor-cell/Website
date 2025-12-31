# ----------------------------
# backend_power.py
# ----------------------------

import os
import pandas as pd
import warnings
import time
import itables

warnings.filterwarnings("ignore")

# itables config
itables.options.style = "table-layout:auto;width:auto"
itables.options.showIndex = False

# ----------------------------
# Helpers
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
                if f.endswith(".report.avgpwr")
            ]
            if avgpwr_files:
                reports_dict[folder] = avgpwr_files

    return reports_dict

# ----------------------------
# Parsing
# ----------------------------
def parse_avgpwr_file(file_path):
    """
    Parse a .report.avgpwr file and extract four tables:
    Total Power, Group Power, Clock Power, Rail Power.
    Returns pandas DataFrames in a dict.
    """
    total_data, group_data, clock_data, rail_data = [], [], [], []

    with open(file_path) as f:
        lines = f.readlines()

    mode = None
    for line in lines:
        line = line.strip()
        if line.startswith("Total Power"):
            mode = "total"
            continue
        elif line.startswith("Group") and "Internal" in line:
            mode = "group"
            continue
        elif line.startswith("Clock") and "Internal" in line:
            mode = "clock"
            continue
        elif line.startswith("Rail"):
            mode = "rail"
            continue
        elif not line or line.startswith("-"):
            continue

        parts = line.split()
        # Total Power: Internal, Switching, Leakage, Total
        if mode == "total" and len(parts) >= 4:
            total_data.append(parts[:4])
        # Group Power: Group, Internal, Switching, Leakage, Total, Percentage
        elif mode == "group" and len(parts) >= 6:
            group_data.append(parts[:6])
        # Clock Power: Clock, Internal, Switching, Leakage, Total, Percentage
        elif mode == "clock" and len(parts) >= 6:
            clock_data.append(parts[:6])
        # Rail Power: Rail, Voltage, Internal, Switching, Leakage, Total, Percentage
        elif mode == "rail" and len(parts) >= 7:
            rail_data.append(parts[:7])

    return {
        "Total Power": pd.DataFrame(total_data, columns=["Internal","Switching","Leakage","Total"]),
        "Group Power": pd.DataFrame(group_data, columns=["Group","Internal","Switching","Leakage","Total","Percentage"]),
        "Clock Power": pd.DataFrame(clock_data, columns=["Clock","Internal","Switching","Leakage","Total","Percentage"]),
        "Rail Power": pd.DataFrame(rail_data, columns=["Rail","Voltage","Internal","Switching","Leakage","Total","Percentage"])
    }

# ----------------------------
# DataFrame generation
# ----------------------------
def generate_power_df(design, reports_dict):
    """
    Convert all avgpwr reports into dict of DataFrames:
    {scenario_name: {file_name: {table_name: DataFrame}}}
    """
    output = {}
    for scenario, files in reports_dict.items():
        scenario_tables = {}
        for fpath in files:
            scenario_tables[os.path.basename(fpath)] = parse_avgpwr_file(fpath)
        output[scenario] = scenario_tables
    return output

# ----------------------------
# HTML writer
# ----------------------------
def write_html(obj, name, outdir, report_date=""):
    """
    Write an interactive HTML page with itables.
    obj: dict of DataFrames {table_name: df}
    """
    os.makedirs(outdir, exist_ok=True)
    date_to_show = report_date or ""
    html_path = os.path.join(outdir, f"{name}.html")

    with open(html_path, "w") as f:
        f.write(f"<html><head><title>Power Dashboard - {name}</title></head><body>")
        f.write(f"<h2>Design: {name}</h2><pre>Date: {date_to_show}</pre>")

        for file_name, tables in obj.items():
            f.write(f"<h3>Report File: {file_name}</h3>")
            for table_name, df in tables.items():
                f.write(f"<h4>{table_name}</h4>")
                f.write(itables.to_html_datatable(df, allow_html=True))

        f.write("</body></html>")

    return html_path

# ----------------------------
# Main entry
# ----------------------------
def run_power(cwd, outdir, designs):
    """
    Generate HTML dashboards for a list of designs.
    Returns a list of generated HTML file names.
    """
    os.makedirs(outdir, exist_ok=True)
    generated = []

    for design in designs:
        reports_dict = find_voltus_reports(cwd, design)
        if not reports_dict:
            continue

        dfs_dict = generate_power_df(design, reports_dict)
        for scenario, tables_dict in dfs_dict.items():
            html_name = f"{design}_{scenario}"
            report_date = time.ctime()
            write_html(tables_dict, html_name, outdir, report_date)
            generated.append(html_name)

    return list(dict.fromkeys(generated))
