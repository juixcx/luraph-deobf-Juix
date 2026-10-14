import os
import re
import io
import time
import shutil
import zipfile
import subprocess
import urllib.request
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)

LOGO_URL = "https://raw.githubusercontent.com/juixcx/jui-99/879075e95a7d841e1859fefbb9291b5c3dbe9163/file_00000000b19c82119a08c4a5ef92d489.png"
LOGO_PATH = os.path.join(os.path.dirname(__file__), "static", "logo.png")

# ============================================================
# ENGINE MAP
# ============================================================
ENGINES = {
    "luraph_14.9": {
        "name": "Luraph v14.9",
        "repo": "https://github.com/KryptIT/luraph-v15-v14.x-deobfuscator.git",
        "clone_dir": "/tmp/luraph-deobf",
        "cli_dir": "Deobfuscator/deobf",
        "cli_file": "cli.py",
        "args": ["--engine", "14.9"],
        "bin_url": "https://github.com/luau-lang/luau/releases/download/0.653/luau-ubuntu.zip",
        "bin_dir": "bin",
        "bin_name": "luau-ast",
    },
    "prometheus": {
        "name": "Prometheus",
        "repo": "https://github.com/levno-710/Prometheus.git",
        "clone_dir": "/tmp/prometheus",
        "cli_dir": ".",
        "cli_file": "main.py",
        "args": [],
        "bin_url": None, "bin_dir": None, "bin_name": None,
    },
    "moonsec_v3": {
        "name": "MoonSec V3",
        "repo": "https://github.com/PandaGamingTV/MoonSecV3-Deobfuscator.git",
        "clone_dir": "/tmp/moonsecv3",
        "cli_dir": ".",
        "cli_file": "deobf.py",
        "args": [],
        "bin_url": None, "bin_dir": None, "bin_name": None,
    },
    "moonsec_v2": {
        "name": "MoonSec V2",
        "repo": "https://github.com/Byte-cc/MoonSec-Deobf.git",
        "clone_dir": "/tmp/moonsecv2",
        "cli_dir": ".",
        "cli_file": "main.py",
        "args": [],
        "bin_url": None, "bin_dir": None, "bin_name": None,
    },
    "moonveil": {
        "name": "Moonveil",
        "repo": "https://github.com/LulzTeam/Moonveil-Deobf.git",
        "clone_dir": "/tmp/moonveil",
        "cli_dir": ".",
        "cli_file": "deobf.py",
        "args": [],
        "bin_url": None, "bin_dir": None, "bin_name": None,
    },
}

SETUP_STATUS = {}


# ============================================================
# HELPERS
# ============================================================
def fetch_script_from_url(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace"), None
    except Exception as e:
        return None, str(e)


def setup_engine(key):
    if SETUP_STATUS.get(key) == "complete":
        return True, "ok"

    cfg = ENGINES[key]
    clone_dir = cfg["clone_dir"]

    # 1) clone repo
    if not os.path.exists(clone_dir):
        try:
            subprocess.run(
                ["git", "clone", "--depth=1", cfg["repo"], clone_dir],
                check=True, capture_output=True, timeout=300
            )
        except Exception as e:
            SETUP_STATUS[key] = f"clone failed: {e}"
            return False, SETUP_STATUS[key]

    # 2) bin (เฉพาะ luraph)
    if cfg["bin_url"] and cfg["bin_dir"]:
        bin_dir = os.path.join(clone_dir, cfg["cli_dir"], cfg["bin_dir"])
        os.makedirs(bin_dir, exist_ok=True)
        bin_path = os.path.join(bin_dir, cfg["bin_name"])

        if not os.path.exists(bin_path):
            try:
                zip_path = os.path.join(bin_dir, "bin.zip")
                urllib.request.urlretrieve(cfg["bin_url"], zip_path)
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(bin_dir)
                os.remove(zip_path)
                for f in os.listdir(bin_dir):
                    fp = os.path.join(bin_dir, f)
                    if os.path.isfile(fp):
                        try: os.chmod(fp, 0o755)
                        except: pass
            except Exception as e:
                SETUP_STATUS[key] = f"bin failed: {e}"
                return False, SETUP_STATUS[key]

    SETUP_STATUS[key] = "complete"
    return True, "ok"


def ensure_logo():
    os.makedirs(os.path.dirname(LOGO_PATH), exist_ok=True)
    if not os.path.exists(LOGO_PATH):
        try:
            urllib.request.urlretrieve(LOGO_URL, LOGO_PATH)
        except Exception as e:
            print("logo fetch failed:", e)


# ============================================================
# ANALYZER
# ============================================================
def analyze(script: str) -> dict:
    result = {
        "size": len(script),
        "lines": script.count("\n") + 1,
        "obfuscator": "unknown",
        "version": "unknown",
        "opcode_handlers": 0,
        "constants": 0,
        "magic_bytes": None,
        "encrypted_bytecode": False,
        "warnings": [],
    }

    # detect obfuscator
    if re.search(r"Luraph Obfuscator v([\d.]+)", script, re.I):
        m = re.search(r"Luraph Obfuscator v([\d.]+)", script, re.I)
        result["obfuscator"] = "Luraph"
        result["version"] = m.group(1)
    elif re.search(r"prometheus", script, re.I) or "Prometheus" in script[:2000]:
        result["obfuscator"] = "Prometheus"
    elif re.search(r"moonsec.{0,5}v?3", script, re.I):
        result["obfuscator"] = "MoonSec"
        result["version"] = "3"
    elif re.search(r"moonsec.{0,5}v?2", script, re.I):
        result["obfuscator"] = "MoonSec"
        result["version"] = "2"
    elif re.search(r"moonveil", script, re.I):
        result["obfuscator"] = "Moonveil"

    result["opcode_handlers"] = len(re.findall(
        r"(?:\[\d+\]|[A-Za-z_]\w*)\s*=\s*function\s*\(", script))
    result["constants"] = len(re.findall(
        r"\[\d+\]\s*=\s*(?:\d+|0x[0-9a-f]+|\"[^\"]*\"|'[^']*'|true|false|nil)",
        script, re.I))

    magic = re.search(
        r"[A-Za-z_]\w*\s*=\s*\{\s*(\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+)", script)
    if magic:
        result["magic_bytes"] = [int(x) for x in magic.group(1).split(",")][:8]

    if len(script) > 5000 and re.search(r"[A-Za-z0-9+/=]{5000,}", script):
        result["encrypted_bytecode"] = True

    if result["opcode_handlers"] < 5:
        result["warnings"].append("Few opcode handlers")
    if not result["encrypted_bytecode"]:
        result["warnings"].append("No encrypted bytecode blob")
    if result["version"] == "unknown" and result["obfuscator"] == "unknown":
        result["warnings"].append("Cannot detect obfuscator")

    # auto-pick engine
    if result["obfuscator"] == "Luraph":
        result["suggested_engine"] = "luraph_14.9"
    elif result["obfuscator"] == "Prometheus":
        result["suggested_engine"] = "prometheus"
    elif result["obfuscator"] == "MoonSec" and result["version"] == "3":
        result["suggested_engine"] = "moonsec_v3"
    elif result["obfuscator"] == "MoonSec" and result["version"] == "2":
        result["suggested_engine"] = "moonsec_v2"
    elif result["obfuscator"] == "Moonveil":
        result["suggested_engine"] = "moonveil"
    else:
        result["suggested_engine"] = "luraph_14.9"

    return result


# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def index():
    ensure_logo()
    return render_template("index.html")


@app.route("/api/engines")
def api_engines():
    return jsonify({
        "engines": [
            {"key": k, "name": v["name"]}
            for k, v in ENGINES.items()
        ]
    })


@app.route("/api/setup", methods=["POST"])
def api_setup():
    data = request.get_json(silent=True) or {}
    engine_key = data.get("engine", "luraph_14.9")
    if engine_key not in ENGINES:
        return jsonify({"error": "unknown engine"}), 400
    ok, msg = setup_engine(engine_key)
    return jsonify({"ok": ok, "message": msg})


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json(silent=True) or {}
    script = data.get("script", "")

    if not script and data.get("url"):
        script, err = fetch_script_from_url(data["url"])
        if err:
            return jsonify({"error": f"fetch failed: {err}"}), 400

    if not script or len(script) < 100:
        return jsonify({"error": "script too short"}), 400

    result = analyze(script)
    result["script"] = script
    return jsonify(result)


@app.route("/api/deobf", methods=["POST"])
def api_deobf():
    data = request.get_json(silent=True) or {}
    script = data.get("script", "")
    engine_key = data.get("engine", "luraph_14.9")

    if engine_key not in ENGINES:
        return jsonify({"error": f"unknown engine: {engine_key}"}), 400

    if not script and data.get("url"):
        script, err = fetch_script_from_url(data["url"])
        if err:
            return jsonify({"error": f"fetch failed: {err}"}), 400

    if not script:
        return jsonify({"error": "empty script"}), 400

    ok, msg = setup_engine(engine_key)
    if not ok:
        return jsonify({"error": f"setup failed: {msg}"}), 500

    cfg = ENGINES[engine_key]
    workdir = f"/tmp/deobf_{int(time.time())}"
    os.makedirs(workdir, exist_ok=True)

    in_path = os.path.join(workdir, "input.lua")
    out_path = os.path.join(workdir, "output.lua")

    with open(in_path, "w", encoding="utf-8") as f:
        f.write(script)

    cli_dir = os.path.join(cfg["clone_dir"], cfg["cli_dir"])
    if not os.path.isdir(cli_dir):
        return jsonify({"error": f"cli dir not found: {cli_dir}"}), 500

    args = ["python", cfg["cli_file"], in_path, "-o", out_path] + cfg["args"]

    try:
        proc = subprocess.run(
            args, cwd=cli_dir, capture_output=True,
            text=True, timeout=900
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "timeout (900s)", "stdout": "", "stderr": "timeout"}), 504
    except Exception as e:
        return jsonify({"error": f"subprocess: {e}", "stdout": "", "stderr": str(e)}), 500

    if not os.path.exists(out_path):
        return jsonify({
            "error": "deobfuscation failed",
            "stdout": proc.stdout[-8000:],
            "stderr": proc.stderr[-8000:],
            "returncode": proc.returncode,
            "engine": engine_key,
        }), 500

    with open(out_path, "r", encoding="utf-8", errors="replace") as f:
        output = f.read()

    return jsonify({
        "success": True,
        "engine": engine_key,
        "output": output,
        "size": len(output),
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-8000:],
    })


@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.get_json(silent=True) or {}
    output = data.get("output", "")
    if not output:
        return jsonify({"error": "no output"}), 400

    buf = io.BytesIO(output.encode("utf-8"))
    buf.seek(0)
    return send_file(buf, mimetype="text/plain",
                     as_attachment=True, download_name="deobfuscated.lua")


@app.route("/api/health")
def api_health():
    return jsonify({
        "status": "ok",
        "engines": list(ENGINES.keys()),
        "setup": SETUP_STATUS,
    })


# ============================================================
# BOOT
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
