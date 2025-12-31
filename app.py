import os
import logging
from flask import Flask, request, send_from_directory, abort, render_template

# Updated imports to match your folder structure
from backend.backend_timing import run_chip  # Timing dashboard
from backend.backend_power import run_power  # Power dashboard

app = Flask(__name__)

# --------------------------------------------------
# Configuration
# --------------------------------------------------
CWD_BASE_TIMING = "/asic_work/ewang/esf/old_work_areas"
CWD_BASE_POWER  = "/asic_work/jchang/esf/power_released/"
OUTDIR          = "/asic_work/mkhan/website/tempo"
LOGFILE         = "/asic_work/mkhan/website/logs/timing.log"

# --------------------------------------------------
# Logging
# --------------------------------------------------
logging.basicConfig(
    filename=LOGFILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def list_designs(cwd):
    """List all directories in cwd"""
    try:
        return sorted([d for d in os.listdir(cwd) if os.path.isdir(os.path.join(cwd, d))])
    except Exception:
        return []

# --------------------------------------------------
# Index page (multi-select form)
# --------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    designs_timing = list_designs(CWD_BASE_TIMING)
    designs_power  = list_designs(CWD_BASE_POWER)

    if request.method == "POST":
        selected_designs = request.form.getlist("designs")
        die = request.form.get("die", "").strip()
        report_type = request.form.get("mode", "timing")

        if not selected_designs or not die:
            abort(400, "Design(s) and Die are required")

        logging.info(f"Running {report_type} dashboard: designs={selected_designs}, die={die}")

        if report_type == "timing":
            generated = run_chip(
                cwd=CWD_BASE_TIMING,
                die=die,
                outdir=OUTDIR,
                designs=selected_designs
            )
        else:  # Power dashboard
            generated = run_power(
                cwd=CWD_BASE_POWER,
                outdir=OUTDIR,
                designs=selected_designs
            )

        if not generated:
            abort(500, "No dashboard generated")

        return render_template(
            "index.html",
            designs_timing=designs_timing,
            designs_power=designs_power,
            generated=generated,
            comparison=(len(generated) > 1),
            done=True,
            report_type=report_type
        )

    return render_template(
        "index.html",
        designs_timing=designs_timing,
        designs_power=designs_power,
        done=False
    )

# --------------------------------------------------
# Serve generated dashboards
# --------------------------------------------------
@app.route("/files/<path:filename>")
def files(filename):
    if not filename.endswith(".html"):
        abort(404)
    return send_from_directory(OUTDIR, filename)

# --------------------------------------------------
# Main
# --------------------------------------------------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
