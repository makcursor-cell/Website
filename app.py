from flask import Flask, request, redirect, send_from_directory, abort, render_template
import os
import logging

from backend import run_chip

app = Flask(__name__)

# --------------------------------------------------
# Configuration
# --------------------------------------------------
CWD_BASE = "/asic_work/ewang/esf/old_work_areas"
OUTDIR   = "/asic_work/mkhan/website/tempo"
LOGFILE  = "/asic_work/mkhan/website/logs/timing.log"

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
    return sorted([
        d for d in os.listdir(cwd)
        if os.path.isdir(os.path.join(cwd, d))
    ])

# --------------------------------------------------
# Index page (multi-select form)
# --------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    try:
        designs = list_designs(CWD_BASE)
    except Exception:
        designs = []

    if request.method == "POST":
        selected_designs = request.form.getlist("designs")
        die = request.form.get("die", "").strip()

        if not selected_designs or not die:
            abort(400, "Design(s) and Die are required")

        logging.info(f"Running timing dashboard: designs={selected_designs}, die={die}")

        # Run the backend logic
        generated = run_chip(
            cwd=CWD_BASE,
            die=die,
            outdir=OUTDIR,
            designs=selected_designs
        )

        if not generated:
            abort(500, "No dashboard generated")

        # RENDER the template with results instead of just redirecting
        # This matches the {% if done %} logic in your index.html
        return render_template(
            "index.html", 
            designs=designs, 
            generated=generated, 
            comparison=(len(generated) > 1),
            done=True
        )

    # For GET requests, just show the form
    return render_template("index.html", designs=designs, done=False)
# --------------------------------------------------
# Serve generated dashboards (safe)
# --------------------------------------------------
@app.route("/files/<path:filename>")
def files(filename):
    if not filename.endswith(".html"):
        abort(404)
    return send_from_directory(OUTDIR, filename)

# --------------------------------------------------
# Main (localhost only)
# --------------------------------------------------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
