// dashboard/src/app.js
const API_BASE = "http://127.0.0.1:8000/api";
const REFRESH_INTERVAL_MS = 15000;

let allFindings = [];
let refreshTimer = null;

async function loadData() {
    try {
        const [findingsRes, runsRes, rulesRes] = await Promise.all([
            fetch(`${API_BASE}/findings?limit=100`),
            fetch(`${API_BASE}/runs?limit=100`),
            fetch(`${API_BASE}/rules`),
        ]);
        allFindings = await findingsRes.json();
        const runs = await runsRes.json();
        const rules = await rulesRes.json();

        updateStats(allFindings, runs);
        renderFindings(allFindings);
        renderRules(rules.rules || []);
    } catch (err) {
        console.error("Failed to load data:", err);
    }
}

function updateStats(findings, runs) {
    document.getElementById("stat-total").textContent = findings.length;
    document.getElementById("stat-high").textContent =
        findings.filter((f) => f.confidence === "high").length;

    const today = new Date().toISOString().slice(0, 10);
    document.getElementById("stat-scans").textContent =
        runs.filter((r) => r.ts && r.ts.startsWith(today)).length;
}

function renderFindings(findings) {
    const tbody = document.getElementById("findings-body");
    const filter = document.getElementById("confidence-filter").value;
    const rows = filter === "all" ? findings : findings.filter((f) => f.confidence === filter);

    tbody.innerHTML = rows.length
        ? rows
            .map(
                (f) => `
        <tr>
            <td><span class="conf-${f.confidence}">[${(f.confidence || "low").toUpperCase()}]</span></td>
            <td>${escapeHtml(shortRepo(f.repo))}</td>
            <td>${escapeHtml(f.file)}:${f.line_number}</td>
            <td>${escapeHtml(f.rule_id)}</td>
            <td><code>${escapeHtml(f.masked)}</code></td>
            <td class="muted">${escapeHtml(f.ts || "")}</td>
            <td class="muted">${f.commit_sha ? escapeHtml(f.commit_sha.slice(0, 8)) : "&mdash;"}</td>
        </tr>`
            )
            .join("")
        : `<tr><td colspan="7" class="muted">No findings yet.</td></tr>`;
}

function renderRules(rules) {
    const tbody = document.getElementById("rules-body");
    if (!rules.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="muted">No custom rules yet.</td></tr>`;
        return;
    }
    tbody.innerHTML = rules
        .map(
            (r) => `
        <tr>
            <td>${escapeHtml(r.id)}</td>
            <td><code>${escapeHtml(r.pattern)}</code></td>
            <td><span class="conf-${r.severity}">${(r.severity || "medium").toUpperCase()}</span></td>
            <td>${r.active ? "Active" : "Disabled"}</td>
            <td><button class="btn-icon" data-delete="${escapeHtml(r.id)}" title="Delete rule">&#128465;</button></td>
        </tr>`
        )
        .join("");
}

function shortRepo(repo) {
    return repo.split(/[\\/]/).pop();
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

/* --- Modal lifecycle: belongs to Rules tab only --- */
const modal = () => document.getElementById("add-rule-modal");

function openModal() {
    modal().hidden = false;
    document.getElementById("rule-id").focus();
}

function closeModal() {
    modal().hidden = true;
    document.getElementById("add-rule-form").reset();
}

function setupTabs() {
    document.querySelectorAll(".tab-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            closeModal(); // Switching tabs always dismisses the modal
            document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
        });
    });
}

async function submitRule(event) {
    event.preventDefault();
    const payload = {
        id: document.getElementById("rule-id").value.trim(),
        pattern: document.getElementById("rule-pattern").value.trim(),
        severity: document.getElementById("rule-severity").value,
        description: document.getElementById("rule-description").value.trim(),
    };
    try {
        const res = await fetch(`${API_BASE}/rules`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
            const err = await res.json();
            alert(`Rule rejected: ${err.detail}`);
            return;
        }
        closeModal();
        loadData();
    } catch (e) {
        console.error("Failed to add rule:", e);
    }
}

async function deleteRule(ruleId) {
    if (!confirm(`Delete rule ${ruleId}?`)) return;
    try {
        const res = await fetch(`${API_BASE}/rules/${encodeURIComponent(ruleId)}`, { method: "DELETE" });
        if (res.ok) loadData();
    } catch (e) {
        console.error("Failed to delete rule:", e);
    }
}

/* --- Playground: test arbitrary text against active rules + one-off regex --- */
async function runPlayground() {
    const payload = {
        text: document.getElementById("pg-text").value,
        pattern: document.getElementById("pg-pattern").value.trim() || null,
    };
    if (!payload.text.trim()) {
        document.getElementById("pg-body").innerHTML =
            `<tr><td colspan="5" class="muted">Enter a test string first.</td></tr>`;
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/playground`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
            const err = await res.json();
            alert(`Playground error: ${err.detail}`);
            return;
        }
        const data = await res.json();
        document.getElementById("pg-body").innerHTML = data.results.length
            ? data.results
                .map(
                    (r) => `
                <tr>
                    <td>${escapeHtml(r.rule_id)}</td>
                    <td><code>${escapeHtml(r.masked)}</code></td>
                    <td>${r.entropy}</td>
                    <td><span class="conf-${r.confidence}">${r.confidence.toUpperCase()}</span></td>
                    <td>${r.severity.toUpperCase()}</td>
                </tr>`
                )
                .join("")
            : `<tr><td colspan="5" class="muted">No rule matched this input.</td></tr>`;
    } catch (e) {
        console.error("Playground request failed:", e);
    }
}

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(loadData, REFRESH_INTERVAL_MS);
}

/// Probe /api/status with a hard timeout so a hung connection cannot stall the loop.
async function probeStatus(timeoutMs = 1500) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const res = await fetch(`${API_BASE}/status`, { signal: controller.signal });
        return res.ok;
    } catch (_) {
        return false;
    } finally {
        clearTimeout(timer);
    }
}

/// Poll the status endpoint until reachable (spawn race mitigation).
async function waitForApi(maxAttempts = 10, delayMs = 2000) {
    for (let i = 0; i < maxAttempts; i++) {
        if (await probeStatus()) return true;
        await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
    return false;
}

/// Load data in background; UI interactivity must never depend on API readiness.
async function bootstrap() {
    const ready = await waitForApi();
    if (!ready) {
        console.warn("Murmur API unreachable; dashboard keeps polling in background");
    }
    loadData();
    startAutoRefresh();
}

document.addEventListener("DOMContentLoaded", () => {
    document.documentElement.setAttribute("data-theme", localStorage.getItem("theme") || "dark");
    document.getElementById("theme-toggle").addEventListener("click", () => {
        const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("theme", next);
    });
    document.getElementById("confidence-filter").addEventListener("change", () => renderFindings(allFindings));
    document.getElementById("open-add-rule").addEventListener("click", openModal);
    document.getElementById("cancel-add-rule").addEventListener("click", closeModal);
    document.getElementById("add-rule-form").addEventListener("submit", submitRule);
    document.getElementById("pg-run").addEventListener("click", runPlayground);
    document.getElementById("rules-body").addEventListener("click", (e) => {
        const id = e.target?.dataset?.delete;
        if (id) deleteRule(id);
    });
    // Click on overlay backdrop or Escape closes the modal
    modal().addEventListener("click", (e) => {
        if (e.target === modal()) closeModal();
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !modal().hidden) closeModal();
    });

    // UI wiring is synchronous and completes immediately, so tabs/buttons work
    // even while the API is still booting in background.
    setupTabs();
    bootstrap();
});