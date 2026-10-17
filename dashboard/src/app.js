// dashboard/src/app.js
const API_BASE = "http://127.0.0.1:8000/api";
let allFindings = [];
let refreshInterval = null;

async function loadData() {
    try {
        const [findingsRes, runsRes, rulesRes] = await Promise.all([
            fetch(`${API_BASE}/findings?limit=100`),
            fetch(`${API_BASE}/runs?limit=100`),
            fetch(`${API_BASE}/rules`)
        ]);

        allFindings = await findingsRes.json();
        const runs = await runsRes.json();
        const rules = await rulesRes.json();

        updateStats(allFindings, runs);
        renderFindings(allFindings);
        renderRules(rules.rules);
        renderRuns(runs);
    } catch (err) {
        console.error("Failed to load data:", err);
    }
}

function startAutoRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
    refreshInterval = setInterval(() => {
        console.log("Auto-refreshing data...");
        loadData();
    }, 30000); 
}

function updateStats(findings, runs) {
    document.getElementById("stat-total").textContent = findings.length;
    document.getElementById("stat-high").textContent = findings.filter(f => f.confidence === "high").length;
    
    const today = new Date().toISOString().split("T")[0];
    const todayScans = runs.filter(r => r.ts.startsWith(today)).length;
    document.getElementById("stat-scans").textContent = todayScans;
}

function renderFindings(findings) {
    const tbody = document.getElementById("findings-body");
    tbody.innerHTML = "";
    
    const filter = document.getElementById("confidence-filter").value;
    const filtered = filter === "all" ? findings : findings.filter(f => f.confidence === filter);

    filtered.forEach(f => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td><span class="conf-${f.confidence}">[${f.confidence.toUpperCase()}]</span></td>
            <td>${f.repo.split('\\').pop().split('/').pop()}</td>
            <td>${f.file}:${f.line_number}</td>
            <td>${f.rule_id}</td>
            <td><code>${f.masked}</code></td>
            <td style="color: var(--text-secondary)">${f.ts.split('T')[0]}</td>
        `;
        tbody.appendChild(row);
    });
}

function renderRules(rules) {
    const tbody = document.getElementById("rules-body");
    tbody.innerHTML = "";
    
    rules.forEach(r => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${r.id}</td>
            <td><code>${r.pattern}</code></td>
            <td><span class="conf-${r.severity === 'high' ? 'high' : 'medium'}">${r.severity.toUpperCase()}</span></td>
            <td>${r.active ? '✅ Active' : '❌ Disabled'}</td>
        `;
        tbody.appendChild(row);
    });
}

function setupTabs() {
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
            
            btn.classList.add("active");
            document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
        });
    });
}

function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
}

document.addEventListener("DOMContentLoaded", () => {
    const savedTheme = localStorage.getItem("theme") || "dark";
    document.documentElement.setAttribute("data-theme", savedTheme);
    
    document.getElementById("theme-toggle").addEventListener("click", toggleTheme);
    document.getElementById("confidence-filter").addEventListener("change", () => renderFindings(allFindings));
    
    setupTabs();
    loadData();
    startAutoRefresh(); 
});