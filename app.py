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

DEOBF_REPO = "https://github.com/KryptIT/luraph-v15-v14.x-deobfuscator.git"
DEOBF_DIR = "/tmp/luraph-deobf"
BIN_DIR = os.path.join(DEOBF_DIR, "Deobfuscator", "deobf", "bin")
LUAU_URL = "https://github.com/luau-lang/luau/releases/download/0.653/luau-ubuntu.zip"
LOGO_URL = "https://raw.githubusercontent.com/juixcx/jui-99/879075e95a7d841e1859fefbb9291b5c3dbe9163/file_00000000b19c82119a08c4a5ef92d489.png"
LOGO_PATH = os.path.join(os.path.dirname(__file__), "static", "logo.png")

SETUP_DONE = False
SETUP_MSG = "not started"


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


def setup_all():
    global SETUP_DONE, SETUP_MSG
    if SETUP_DONE:
        return True, SETUP_MSG

    # 1) clone repo
    if not os.path.exists(DEOBF_DIR):
        try:
            subprocess.run(
                ["git", "clone", "--depth=1", DEOBF_REPO, DEOBF_DIR],
                check=True, capture_output=True, timeout=300
            )
        except Exception as e:
            SETUP_MSG = f"git clone failed: {e}"
            return False, SETUP_MSG

    os.makedirs(BIN_DIR, exist_ok=True)

    # 2) download luau binary
    luau_ast = os.path.join(BIN_DIR, "luau-ast")
    if not os.path.exists(luau_ast):
        try:
            zip_path = os.path.join(BIN_DIR, "luau.zip")
            urllib.request.urlretrieve(LUAU_URL, zip_path)

            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(BIN_DIR)
            os.remove(zip_path)

            for f in os.listdir(BIN_DIR):
                fp = os.path.join(BIN_DIR, f)
                if os.path.isfile(fp):
                    try:
                        os.chmod(fp, 0o755)
                    except Exception:
                        pass
        except Exception as e:
            SETUP_MSG = f"luau download failed: {e}"
            return False, SETUP_MSG

    if not os.path.exists(luau_ast):
        SETUP_MSG = f"luau-ast not found at {luau_ast}"
        return False, SETUP_MSG

    SETUP_DONE = True
    SETUP_MSG = "setup complete"
    return True, SETUP_MSG


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

    m = re.search(r"Luraph Obfuscator v([\d.]+)", script, re.I)
    if m:
        result["obfuscator"] = "Luraph"
        result["version"] = m.group(1)

    result["opcode_handlers"] = len(re.findall(
        r"(?:\[\d+\]|[A-Za-z_]\w*)\s*=\s*function\s*\(", script))

    result["constants"] = len(re.findall(
        r"\[\d+\]\s*=\s*(?:\d+|0x[0-9a-f]+|\"[^\"]*\"|'[^']*'|true|false|nil)",
        script, re.I))

    magic = re.search(
        r"[A-Za-z_]\w*\s*=\s*\{\s*(\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+)", script)
    if magic:
        result["magic_bytes"] = [int(x) for x in magic.group(1).split(",")][:8]

    if len(script) > 5000:
        if re.search(r"[A-Za-z0-9+/=]{5000,}", script):
            result["encrypted_bytecode"] = True

    if result["opcode_handlers"] < 5:
        result["warnings"].append("Few opcode handlers — script may be truncated")
    if not result["encrypted_bytecode"]:
        result["warnings"].append("No encrypted bytecode blob detected")
    if result["version"] == "unknown":
        result["warnings"].append("Luraph header missing")

    return result


# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def index():
    ensure_logo()
    return render_template("index.html")


@app.route("/api/setup", methods=["POST"])
def api_setup():
    ok, msg = setup_all()
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
    cmd = (f"python cli.py input.lua -o output.lua "
           f"--engine {result['version'] if result['version'] != 'unknown' else '14.9'}")
    result["command"] = cmd
    return jsonify(result)


@app.route("/api/deobf", methods=["POST"])
def api_deobf():
    ok, msg = setup_all()
    if not ok:
        return jsonify({"error": f"setup failed: {msg}"}), 500

    data = request.get_json(silent=True) or {}
    script = data.get("script", "")
    engine = data.get("engine", "14.9")
    executor = data.get("executor", "delta")

    if not script and data.get("url"):
        script, err = fetch_script_from_url(data["url"])
        if err:
            return jsonify({"error": f"fetch failed: {err}"}), 400

    if not script:
        return jsonify({"error": "empty script"}), 400

    workdir = f"/tmp/deobf_{int(time.time())}"
    os.makedirs(workdir, exist_ok=True)

    in_path = os.path.join(workdir, "input.lua")
    out_path = os.path.join(workdir, "output.lua")

    with open(in_path, "w", encoding="utf-8") as f:
        f.write(script)

    cli_dir = os.path.join(DEOBF_DIR, "Deobfuscator", "deobf")
    if not os.path.isdir(cli_dir):
        return jsonify({"error": "deobf cli folder not found"}), 500

    # ============================================================
    # ANTI-TAMPER BYPASS FLAGS
    # ============================================================
    args = [
        "python", "cli.py", in_path,
        "-o", out_path,
        "--engine", engine,
        "--executor", executor,       # บอก executor (Luraph optimizer)
        "--strings",                  # dump strings
        "--max-runs", "500",          # 500 รอบ (default 20)
        "--devirt-rounds", "50",      # 50 devirt rounds (default 5)
        "--timeout", "300",           # 300s timeout (default 20s)
        "--budget", "10000000",       # 10M budget
        "--trace-fallback",           # fallback tracing
        "--no-hooks",                 # ปิด hook patch (Luraph anti-tamper)
        "--keep-harness",             # เก็บ harness
        "--keep-work",                # เก็บ work dir
        "--debug",
    ]

    try:
        proc = subprocess.run(
            args, cwd=cli_dir, capture_output=True,
            text=True, timeout=900
        )
    except subprocess.TimeoutExpired:
        return jsonify({
            "error": "deobfuscation timed out (900s)",
            "stdout": "", "stderr": "timeout"
        }), 504
    except Exception as e:
        return jsonify({
            "error": f"subprocess error: {e}",
            "stdout": "", "stderr": str(e)
        }), 500

    if not os.path.exists(out_path):
        return jsonify({
            "error": "deobfuscation failed (no output file)",
            "stdout": proc.stdout[-8000:],
            "stderr": proc.stderr[-8000:],
            "returncode": proc.returncode,
        }), 500

    with open(out_path, "r", encoding="utf-8", errors="replace") as f:
        output = f.read()

    return jsonify({
        "success": True,
        "output": output,
        "size": len(output),
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-8000:],
        "returncode": proc.returncode,
    })


@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.get_json(silent=True) or {}
    output = data.get("output", "")
    if not output:
        return jsonify({"error": "no output"}), 400

    buf = io.BytesIO(output.encode("utf-8"))
    buf.seek(0)
    return send_file(
        buf, mimetype="text/plain",
        as_attachment=True, download_name="deobfuscated.lua"
    )


@app.route("/api/health")
def api_health():
    return jsonify({
        "status": "ok",
        "repo": os.path.exists(DEOBF_DIR),
        "bin": os.path.exists(os.path.join(BIN_DIR, "luau-ast")),
        "logo": os.path.exists(LOGO_PATH),
        "setup_done": SETUP_DONE,
        "setup_msg": SETUP_MSG,
    })


# ============================================================
# BOOT
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
