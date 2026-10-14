const $ = (id) => document.getElementById(id);
const state = { script: "", output: "" };

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
    row("Obfuscator", r.obfuscator, r.obfuscator === "Luraph" ? "ok" : "err");
    row("Version", r.version, r.version !== "unknown" ? "ok" : "err");
    row("Opcode Handlers", r.opcode_handlers, r.opcode_handlers > 100 ? "ok" : "warn");
    row("Constants", r.constants, r.constants > 100 ? "ok" : "warn");
    row("Magic Bytes",
        r.magic_bytes ? "[" + r.magic_bytes.join(", ") + "]" : "none",
        r.magic_bytes ? "ok" : "warn");
    row("Encrypted Bytecode",
        r.encrypted_bytecode ? "Present" : "None",
        r.encrypted_bytecode ? "ok" : "warn");
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

    // เก็บ script ที่ server ส่งกลับมา → ไม่ต้อง clear
    if (data.script) {
        state.script = data.script;
        $("scriptBody").value = data.script;
    }

    renderAnalysis(data);
    setStatus("Fetch + analyze OK (" + (data.size || 0).toLocaleString() + " bytes)", "success");
}

async function doAnalyze() {
    let script = $("scriptBody").value.trim();
    const url = $("scriptUrl").value.trim();

    // ถ้า script สั้นแต่มี URL → fetch ก่อน
    if ((!script || script.length < 100) && url) {
        return doFetch();
    }

    if (script.length < 100) return setStatus("Code too short", "error");

    setStatus("Analyzing...", "working");
    const { ok, data } = await post("/api/analyze", { script });
    if (!ok) return setStatus("Error: " + (data.error || "unknown"), "error");
    state.script = script;
    renderAnalysis(data);
    setStatus("Analysis complete", "success");
}

async function doDeobf() {
    let script = $("scriptBody").value.trim();
    const url = $("scriptUrl").value.trim();

    // ถ้าไม่มี script แต่มี URL → fetch ก่อน
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

    setStatus("Deobfuscating... (อาจใช้เวลา 5-15 นาที)", "working");

    const engine = "14.9";
    const executor = "delta";   // ← ส่ง executor ให้ backend

    const { ok, data } = await post("/api/deobf", {
        script,
        engine,
        executor
    });

    if (!ok) {
        setStatus("Deobf failed: " + (data.error || "unknown"), "error");
        if (data.stdout || data.stderr) {
            $("outputPre").textContent =
                "STDOUT:\n" + (data.stdout || "") +
                "\n\nSTDERR:\n" + (data.stderr || "");
            $("outputPanel").style.display = "block";
        }
        return;
    }

    state.output = data.output;
    $("outputPre").textContent = data.output;
    $("outputPanel").style.display = "block";
    setStatus("Deobfuscation OK (" + data.size.toLocaleString() + " bytes)", "success");
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
    a.download = "deobfuscated.lua";
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

$("btnFetch").onclick = doFetch;
$("btnAnalyze").onclick = doAnalyze;
$("btnDeobf").onclick = doDeobf;
$("btnDownload").onclick = doDownload;
$("btnCopy").onclick = doCopy;
$("btnClear").onclick = doClear;
