const $ = (id) => document.getElementById(id);
const state = { script: "", output: "", engine: "luraph_14.9" };

function setStatus(msg, type) {
    const el = $("status");
    el.style.display = "block";
    el.className = "status " + (type || "");
    el.textContent = msg;
}

async function post(url, body) {
    const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    return { ok: r.ok, data: await r.json() };
}

function renderAnalysis(r) {
    const grid = $("infoGrid");
    grid.innerHTML = "";
    const row = (label, value, cls) => {
        const l = document.createElement("div");
        l.className = "info-label"; l.textContent = label;
        const v = document.createElement("div");
        v.className = "info-value " + (cls || ""); v.textContent = value;
        grid.appendChild(l); grid.appendChild(v);
    };
    row("Size", (r.size || 0).toLocaleString() + " bytes");
    row("Lines", (r.lines || 0).toLocaleString());
    row("Obfuscator", r.obfuscator, r.obfuscator !== "unknown" ? "ok" : "err");
    row("Version", r.version, r.version !== "unknown" ? "ok" : "warn");
    row("Opcode Handlers", r.opcode_handlers, r.opcode_handlers > 100 ? "ok" : "warn");
    row("Constants", r.constants, r.constants > 100 ? "ok" : "warn");
    row("Magic Bytes",
        r.magic_bytes ? "[" + r.magic_bytes.join(", ") + "]" : "none",
        r.magic_bytes ? "ok" : "warn");
    row("Encrypted Bytecode",
        r.encrypted_bytecode ? "Present" : "None",
        r.encrypted_bytecode ? "ok" : "warn");
    if (r.suggested_engine)
        row("Suggested Engine", r.suggested_engine, "ok");
    if (r.warnings && r.warnings.length)
        row("Warnings", r.warnings.join(" | "), "warn");
    if (r.command)
        row("CLI Command", r.command);
    $("analysisPanel").style.display = "block";
}

async function doFetch() {
    const url = $("scriptUrl").value.trim();
    if (!url) return setStatus("ใส่ URL ก่อน", "error");
    setStatus("Fetching + analyzing...", "working");
    const { ok, data } = await post("/api/analyze", { url });
    if (!ok) return setStatus("Error: " + (data.error || "unknown"), "error");

    if (data.script) {
        state.script = data.script;
        $("scriptBody").value = data.script;
    }

    renderAnalysis(data);

    // auto-select suggested engine
    if (data.suggested_engine && $("engineSelect")) {
        $("engineSelect").value = data.suggested_engine;
        state.engine = data.suggested_engine;
    }

    setStatus("Fetch + analyze OK (" + (data.size || 0).toLocaleString() + " bytes)", "success");
}

async function doAnalyze() {
    let script = $("scriptBody").value.trim();
    const url = $("scriptUrl").value.trim();

    if ((!script || script.length < 100) && url) {
        return doFetch();
    }

    if (script.length < 100) return setStatus("Code too short", "error");

    setStatus("Analyzing...", "working");
    const { ok, data } = await post("/api/analyze", { script });
    if (!ok) return setStatus("Error: " + (data.error || "unknown"), "error");
    state.script = script;
    renderAnalysis(data);

    if (data.suggested_engine && $("engineSelect")) {
        $("engineSelect").value = data.suggested_engine;
        state.engine = data.suggested_engine;
    }

    setStatus("Analysis complete", "success");
}

async function doDeobf() {
    let script = $("scriptBody").value.trim();
    const url = $("scriptUrl").value.trim();
    const engine = $("engineSelect") ? $("engineSelect").value : "luraph_14.9";
    state.engine = engine;

    if ((!script || script.length < 100) && url) {
        setStatus("Fetching script first...", "working");
        const { ok, data } = await post("/api/analyze", { url });
        if (!ok) return setStatus("Fetch failed: " + (data.error || "unknown"), "error");
        if (data.script) {
            state.script = data.script;
            $("scriptBody").value = data.script;
            script = data.script;
        }
    }

    if (!script || script.length < 100) {
        return setStatus("No script to deobfuscate", "error");
    }

    setStatus(`Deobfuscating with ${engine}... (อาจใช้เวลา 1-15 นาที)`, "working");

    const { ok, data } = await post("/api/deobf", { script, engine });

    if (!ok) {
        setStatus("Deobf failed: " + (data.error || "unknown"), "error");
        if (data.stdout || data.stderr) {
            $("outputPre").textContent =
                "ENGINE: " + (data.engine || engine) + "\n" +
                "RETURN CODE: " + (data.returncode != null ? data.returncode : "n/a") + "\n\n" +
                "STDOUT:\n" + (data.stdout || "") +
                "\n\nSTDERR:\n" + (data.stderr || "");
            $("outputPanel").style.display = "block";
        }
        return;
    }

    state.output = data.output;
    $("outputPre").textContent = data.output;
    $("outputPanel").style.display = "block";
    setStatus("Deobfuscation OK (" + data.size.toLocaleString() + " bytes) via " + data.engine, "success");
}

async function doDownload() {
    if (!state.output) return setStatus("No output", "error");
    const r = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ output: state.output }),
    });
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "deobfuscated_" + state.engine + ".lua";
    a.click();
}

function doCopy() {
    if (state.output) {
        navigator.clipboard.writeText(state.output);
        setStatus("Copied!", "success");
    }
}

function doClear() {
    $("scriptUrl").value = "";
    $("scriptBody").value = "";
    $("analysisPanel").style.display = "none";
    $("outputPanel").style.display = "none";
    $("status").style.display = "none";
    state.script = ""; state.output = "";
}

// ============================================================
// WIRE UP
// ============================================================
$("btnFetch").onclick = doFetch;
$("btnAnalyze").onclick = doAnalyze;
$("btnDeobf").onclick = doDeobf;
$("btnDownload").onclick = doDownload;
$("btnCopy").onclick = doCopy;
$("btnClear").onclick = doClear;

if ($("engineSelect")) {
    $("engineSelect").onchange = (e) => {
        state.engine = e.target.value;
        setStatus("Engine: " + state.engine, "working");
    };
}
