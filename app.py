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

BASE_URL = "https://raw.githubusercontent.com/juixcx/jui-99/bf3fd42d3988f5db2a4ec8249227c81313137592"


# ============================================================
# ENGINE MAP
# ============================================================
ENGINES = {
    "luraph_14.9": {
        "name": "Luraph v14.9",
        "type": "git",
        "repo": "https://github.com/KryptIT/luraph-v15-v14.x-deobfuscator.git",
        "clone_dir": "/tmp/engines/luraph_14.9",
        "cli_dir": "Deobfuscator/deobf",
        "cli_file": "cli.py",
        "cli_args": ["--engine", "14.9"],
        "bin_url": "https://github.com/luau-lang/luau/releases/download/0.653/luau-ubuntu.zip",
        "bin_dir": "bin",
        "bin_name": "luau-ast",
    },
    "clyde": {
        "name": "Clyde", "type": "zip",
        "zip_url": f"{BASE_URL}/ClydeDeobfuscator-main.zip",
        "extract_dir": "/tmp/engines/clyde",
        "cli_args": [],
    },
    "77fuscator": {
        "name": "77fuscator", "type": "zip",
        "zip_url": f"{BASE_URL}/77fuscatorDeobfuscator-main.zip",
        "extract_dir": "/tmp/engines/77fuscator",
        "cli_args": [],
    },
    "ironveil": {
        "name": "Ironveil V1", "type": "zip",
        "zip_url": f"{BASE_URL}/Ironveil-Deobfuscator-V1-main.zip",
        "extract_dir": "/tmp/engines/ironveil",
        "cli_args": [],
    },
    "luaobfuscator": {
        "name": "LuaObfuscator", "type": "zip",
        "zip_url": f"{BASE_URL}/LuaObfuscator-Deobfuscator-main.zip",
        "extract_dir": "/tmp/engines/luaobfuscator",
        "cli_args": [],
    },
    "moonsec": {
        "name": "MoonSec", "type": "zip",
        "zip_url": f"{BASE_URL}/MoonsecDeobfuscator-master.zip",
        "extract_dir": "/tmp/engines/moonsec",
        "cli_args": [],
    },
    "prometheus": {
        "name": "Prometheus", "type": "zip",
        "zip_url": f"{BASE_URL}/Prometheus-Deobfuscator-main.zip",
        "extract_dir": "/tmp/engines/prometheus",
        "cli_args": [],
    },
    "moonveil": {
        "name": "Moonveil", "type": "zip",
        "zip_url": f"{BASE_URL}/moonveilvro-main.zip",
        "extract_dir": "/tmp/engines/moonveil",
        "cli_args": [],
    },
    "promdeobf": {
        "name": "Prometheus (alt)", "type": "zip",
        "zip_url": f"{BASE_URL}/promdeobf.rar.zip",
        "extract_dir": "/tmp/engines/promdeobf",
        "cli_args": [],
    },
    "ib2": {
        "name": "IronBrew 2", "type": "zip",
        "zip_url": f"{BASE_URL}/ib2-deobf.zip",
        "extract_dir": "/tmp/engines/ib2",
        "cli_args": [],
    },
    "hercules": {
        "name": "Hercules", "type": "zip",
        "zip_url": f"{BASE_URL}/hercules-deobfuscator-main.zip",
        "extract_dir": "/tmp/engines/hercules",
        "cli_args": [],
    },
}

SETUP_STATUS = {}


# ============================================================
# SETUP
# ============================================================
def setup_git_engine(cfg):
    cd = cfg["clone_dir"]
    if not os.path.exists(cd):
        subprocess.run(["git", "clone", "--depth=1", cfg["repo"], cd],
                       check=True, capture_output=True, timeout=300)
    if cfg.get("bin_url"):
        bd = os.path.join(cd, cfg["cli_dir"], cfg["bin_dir"])
        os.makedirs(bd, exist_ok=True)
        bp = os.path.join(bd, cfg["bin_name"])
        if not os.path.exists(bp):
            z = os.path.join(bd, "bin.zip")
            urllib.request.urlretrieve(cfg["bin_url"], z)
            with zipfile.ZipFile(z) as zf: zf.extractall(bd)
            os.remove(z)
            for f in os.listdir(bd):
                fp = os.path.join(bd, f)
                if os.path.isfile(fp):
                    try: os.chmod(fp, 0o755)
                    except: pass


def setup_zip_engine(cfg):
    ed = cfg["extract_dir"]
    if os.path.exists(ed) and os.listdir(ed):
        return
    os.makedirs(ed, exist_ok=True)
    zp = f"/tmp/{os.path.basename(cfg['zip_url'])}"
    if not os.path.exists(zp):
        urllib.request.urlretrieve(cfg["zip_url"], zp)
    with zipfile.ZipFile(zp) as z: z.extractall(ed)
    items = os.listdir(ed)
    if len(items) == 1 and os.path.isdir(os.path.join(ed, items[0])):
        inner = os.path.join(ed, items[0])
        for f in os.listdir(inner):
            shutil.move(os.path.join(inner, f), os.path.join(ed, f))
        os.rmdir(inner)


def setup_engine(key):
    if SETUP_STATUS.get(key) == "complete":
        return True, "ok"
    cfg = ENGINES[key]
    try:
        if cfg["type"] == "git":
            setup_git_engine(cfg)
        else:
            setup_zip_engine(cfg)
        SETUP_STATUS[key] = "complete"
        return True, "ok"
    except Exception as e:
        SETUP_STATUS[key] = f"setup failed: {e}"
        return False, SETUP_STATUS[key]


def find_cli(extract_dir):
    candidates = ["main.py", "cli.py", "deobf.py", "deobfuscate.py",
                  "index.js", "app.js", "run.py", "__main__.py"]
    for c in candidates:
        for root, dirs, files in os.walk(extract_dir):
            if c in files:
                return root, c
    return None, None


def ensure_logo():
    os.makedirs(os.path.dirname(LOGO_PATH), exist_ok=True)
    if not os.path.exists(LOGO_PATH):
        try: urllib.request.urlretrieve(LOGO_URL, LOGO_PATH)
        except Exception as e: print("logo:", e)


# ============================================================
# AUTO-DETECT OBFUSCATOR
# ============================================================
def detect_obfuscator(script: str) -> tuple:
    """Returns (obfuscator_name, version, engine_key, confidence)"""
    head = script[:5000]  # อ่าน 5000 chars แรก
    full = script[:50000]  # สำหรับ pattern ที่อยู่ลึก

    # === Luraph ===
    m = re.search(r"Luraph Obfuscator v?([\d.]+)", head, re.I)
    if m:
        v = m.group(1)
        if v.startswith("14.9"):
            return ("Luraph", v, "luraph_14.9", "high")
        if v.startswith("14."):
            return ("Luraph", v, "luraph_14.9", "medium")
        return ("Luraph", v, "luraph_14.9", "low")

    if re.search(r"lura\.ph|luraph", head, re.I):
        return ("Luraph", "unknown", "luraph_14.9", "medium")

    # === Prometheus ===
    if re.search(r"prometheus", head, re.I):
        return ("Prometheus", "unknown", "prometheus", "high")
    if "Prometheus" in full or re.search(r"levno-710", full):
        return ("Prometheus", "unknown", "prometheus", "medium")

    # === MoonSec ===
    m = re.search(r"moonsec[\s\-_]*v?(\d)", head, re.I)
    if m:
        return ("MoonSec", m.group(1), "moonsec", "high")
    if re.search(r"moonsec", full, re.I):
        return ("MoonSec", "unknown", "moonsec", "medium")

    # === Moonveil ===
    if re.search(r"moonveil", head, re.I):
        return ("Moonveil", "unknown", "moonveil", "high")
    if re.search(r"moonveil", full, re.I):
        return ("Moonveil", "unknown", "moonveil", "medium")

    # === IronBrew 2 ===
    if re.search(r"ironbrew|iron\s*brew|ib2", head, re.I):
        return ("IronBrew", "2", "ib2", "high")
    if re.search(r"ironbrew", full, re.I):
        return ("IronBrew", "2", "ib2", "medium")

    # === Hercules ===
    if re.search(r"hercules", head, re.I):
        return ("Hercules", "unknown", "hercules", "high")

    # === 77fuscator ===
    if re.search(r"77fuscator", head, re.I):
        return ("77fuscator", "unknown", "77fuscator", "high")

    # === Ironveil ===
    if re.search(r"ironveil", head, re.I):
        return ("Ironveil", "V1", "ironveil", "high")

    # === Clyde ===
    if re.search(r"clyde", head, re.I):
        return ("Clyde", "unknown", "clyde", "medium")

    # === LuaObfuscator ===
    if re.search(r"luaobfuscator", head, re.I):
        return ("LuaObfuscator", "unknown", "luaobfuscator", "high")

    # === Heuristic: Luraph pattern ===
    # Luraph scripts มี pattern: return({...}) ที่มี opcode table + magic bytes
    if re.search(r"return\s*\(\s*\{\s*\w+\s*=\s*function", head) and \
       re.search(r"\[0[XxBb][0-9A-Fa-f_]*\]\s*=\s*function", full):
        return ("Luraph", "unknown", "luraph_14.9", "low")

    # === Unknown ===
    return ("Unknown", "unknown", "luraph_14.9", "none")


# ============================================================
# ANALYZER
# ============================================================
def analyze(script: str) -> dict:
    result = {
        "size": len(script), "lines": script.count("\n") + 1,
        "opcode_handlers": 0, "constants": 0,
        "magic_bytes": None, "encrypted_bytecode": False,
        "warnings": [],
    }

    # detect
    obf, ver, engine, conf = detect_obfuscator(script)
    result["obfuscator"] = obf
    result["version"] = ver
    result["suggested_engine"] = engine
    result["confidence"] = conf

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

    if obf == "Unknown":
        result["warnings"].append("Cannot auto-detect obfuscator — will try Luraph")
    if conf == "low":
        result["warnings"].append("Low detection confidence")

    return result


# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def index():
    ensure_logo()
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json(silent=True) or {}
    script = data.get("script", "")
    if not script and data.get("url"):
        try:
            req = urllib.request.Request(data["url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                script = r.read().decode("utf-8", errors="replace")
        except Exception as e:
            return jsonify({"error": f"fetch failed: {e}"}), 400
    if not script or len(script) < 100:
        return jsonify({"error": "script too short"}), 400
    result = analyze(script)
    result["script"] = script
    return jsonify(result)


@app.route("/api/deobf", methods=["POST"])
def api_deobf():
    data = request.get_json(silent=True) or {}
    script = data.get("script", "")

    if not script and data.get("url"):
        try:
            req = urllib.request.Request(data["url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                script = r.read().decode("utf-8", errors="replace")
        except Exception as e:
            return jsonify({"error": f"fetch failed: {e}"}), 400

    if not script:
        return jsonify({"error": "empty script"}), 400

    # === AUTO-DETECT ===
    obf, ver, engine_key, conf = detect_obfuscator(script)
    print(f"[AUTO-DETECT] {obf} {ver} → engine={engine_key} ({conf})")

    if engine_key not in ENGINES:
        return jsonify({"error": f"engine not found: {engine_key}"}), 500

    ok, msg = setup_engine(engine_key)
    if not ok:
        return jsonify({"error": f"setup failed: {msg}", "engine": engine_key}), 500

    cfg = ENGINES[engine_key]
    workdir = f"/tmp/deobf_{int(time.time())}"
    os.makedirs(workdir, exist_ok=True)
    in_path = os.path.join(workdir, "input.lua")
    out_path = os.path.join(workdir, "output.lua")
    with open(in_path, "w", encoding="utf-8") as f:
        f.write(script)

    if cfg["type"] == "git":
        cli_dir = os.path.join(cfg["clone_dir"], cfg["cli_dir"])
        cli_file = cfg["cli_file"]
    else:
        cli_dir, cli_file = find_cli(cfg["extract_dir"])
        if not cli_dir:
            return jsonify({
                "error": "CLI file not found in extracted zip",
                "engine": engine_key,
                "extract_dir": cfg["extract_dir"],
                "contents": os.listdir(cfg["extract_dir"])[:50],
            }), 500

    args = ["python", cli_file, in_path, "-o", out_path] + cfg.get("cli_args", [])

    try:
        proc = subprocess.run(args, cwd=cli_dir, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return jsonify({"error": "timeout (900s)", "engine": engine_key}), 504
    except Exception as e:
        return jsonify({"error": f"subprocess: {e}", "engine": engine_key}), 500

    if not os.path.exists(out_path):
        return jsonify({
            "error": "deobfuscation failed",
            "engine": engine_key,
            "detected_obfuscator": f"{obf} {ver}",
            "confidence": conf,
            "stdout": proc.stdout[-8000:],
            "stderr": proc.stderr[-8000:],
            "returncode": proc.returncode,
            "cli_dir": cli_dir,
            "cli_file": cli_file,
        }), 500

    with open(out_path, "r", encoding="utf-8", errors="replace") as f:
        output = f.read()

    return jsonify({
        "success": True,
        "engine": engine_key,
        "detected_obfuscator": f"{obf} {ver}",
        "confidence": conf,
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
