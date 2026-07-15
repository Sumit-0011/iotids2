/* IoT IDS Dashboard - Real-Time Client (Polling with since-index) */

const MAX_POINTS = 60;

const chartConfigs = {
    temperature: { label: 'Temperature', color: '#ff6b35', elementId: 'tempChart', valueId: 'tempValue', unit: 'C' },
    pressure:    { label: 'Pressure',    color: '#00ff88', elementId: 'pressureChart', valueId: 'pressureValue', unit: 'hPa' },
    humidity:    { label: 'Humidity',    color: '#7ec8e3', elementId: 'humidityChart', valueId: 'humidityValue', unit: '%' }
};

const charts = {};
let lastTotal = 0;       // tracks how many rows we've seen (absolute index)
let totalPackets = 0;
let anomaliesDetected = 0;

// ── Create a Chart.js chart ──────────────────────────────────
function createChart(key, config) {
    const ctx = document.getElementById(config.elementId).getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, config.color + '30');
    gradient.addColorStop(1, config.color + '00');

    return new Chart(ctx, {
        type: 'line',
        data: { labels: [], datasets: [{ label: config.label, data: [], borderColor: config.color, backgroundColor: gradient, borderWidth: 2, fill: true, tension: 0.4, pointRadius: 0 }] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            plugins: { legend: { display: false } },
            scales: {
                x: { display: true, grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: 'rgba(255,255,255,0.25)', font: { size: 9 }, maxTicksLimit: 8, maxRotation: 0 } },
                y: { display: true, grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: 'rgba(255,255,255,0.3)', font: { size: 10 }, padding: 8 } }
            }
        }
    });
}

function initCharts() {
    for (const [key, config] of Object.entries(chartConfigs)) {
        charts[key] = createChart(key, config);
    }
}

// ── Push one point to all charts ────────────────────────────
function pushPoint(point, animate) {
    const label = point.timestamp || (totalPackets + '');
    for (const [key, config] of Object.entries(chartConfigs)) {
        const chart = charts[key];
        const val = parseFloat(point[key]) || 0;
        chart.data.labels.push(label);
        chart.data.datasets[0].data.push(val);
        if (chart.data.labels.length > MAX_POINTS) { chart.data.labels.shift(); chart.data.datasets[0].data.shift(); }
        chart.update(animate ? undefined : 'none');
        const el = document.getElementById(config.valueId);
        if (el) el.textContent = val.toFixed(1) + ' ' + config.unit;
    }
}

// ── Full sensor names for the attribution display ────────────
const FEATURE_FULLNAME = {
    temp: 'Temperature', hum: 'Humidity', press: 'Pressure'
};

// Parse the server's "temp:78|sound:15|..." attribution string into pairs.
function parseAttribution(str) {
    if (!str) return [];
    return String(str).split('|').map(seg => {
        const [label, pct] = seg.split(':');
        return { label, pct: parseFloat(pct) || 0 };
    }).filter(p => p.label);
}

// ── Update the Detection Intelligence panel (ensemble + XAI) ──
function updateIntel(point) {
    const det = parseInt(point.detected) || 0;
    // iforest/ocsvm/detector columns may be absent on old rows -> fall back to `detected`.
    const ifv  = point.iforest   !== undefined ? parseInt(point.iforest)   : det;
    const svmv = point.ocsvm    !== undefined ? parseInt(point.ocsvm)    : det;
    const detv = point.detector  !== undefined ? parseInt(point.detector)  : 0;

    setChip('chipIforest',  'verdictIforest',  ifv);
    setChip('chipOcsvm',    'verdictOcsvm',    svmv);
    setChip('chipDetector', 'verdictDetector', detv);

    // Ensemble summary line explains WHY the final verdict is what it is.
    const verdictEl = document.getElementById('ensembleVerdict');
    if (det === 1) {
        // Build a list of which specific detectors fired.
        const who = [];
        if (ifv)  who.push('Isolation Forest');
        if (svmv) who.push('One-Class SVM');
        if (detv) who.push('Adversarial RF');
        const whoStr = who.length > 0 ? who.join(' + ') + ' flagged it' : 'ensemble flagged it';
        verdictEl.textContent = '⚠ ATTACK — ' + whoStr;
        verdictEl.className = 'ensemble-verdict verdict-attack';
    } else {
        verdictEl.textContent = '✓ SAFE — all detectors clear';
        verdictEl.className = 'ensemble-verdict verdict-safe';
    }

    // Attribution bars: which sensor drove this reading (always show latest).
    const bars = parseAttribution(point.attribution);
    const container = document.getElementById('attributionBars');
    if (bars.length === 0) return;
    container.innerHTML = bars.map((b, i) => {
        const name = FEATURE_FULLNAME[b.label] || b.label;
        const cls = (i === 0 && det === 1) ? 'attr-bar-fill attr-top' : 'attr-bar-fill';
        return '<div class="attr-row">'
            + '<span class="attr-name">' + name + '</span>'
            + '<div class="attr-track"><div class="' + cls + '" style="width:' + b.pct + '%"></div></div>'
            + '<span class="attr-pct">' + b.pct + '%</span>'
            + '</div>';
    }).join('');
}

function setChip(chipId, verdictId, flagged) {
    const chip = document.getElementById(chipId);
    const verdict = document.getElementById(verdictId);
    if (!chip || !verdict) return;
    if (flagged === 1) {
        chip.classList.add('chip-flagged');
        verdict.textContent = 'ANOMALY';
    } else {
        chip.classList.remove('chip-flagged');
        verdict.textContent = 'normal';
    }
}

// ── Update detection log table ───────────────────────────────
function addLogEntry(point) {
    const tbody = document.getElementById('logBody');
    const empty = document.getElementById('logEmpty');
    if (empty) empty.remove();

    const row = document.createElement('tr');
    const det = parseInt(point.detected) || 0;
    row.className = det === 1 ? 'attack-row' : 'new-row';
    const badge = det === 1
        ? '<span class="badge badge-attack"><span class="badge-dot"></span>Attack</span>'
        : '<span class="badge badge-safe"><span class="badge-dot"></span>Safe</span>';

    // "Cause" = top contributing sensor (XAI), only meaningful for attacks.
    const bars = parseAttribution(point.attribution);
    let cause = '—';
    if (det === 1 && bars.length > 0) {
        const name = FEATURE_FULLNAME[bars[0].label] || bars[0].label;
        cause = '<span class="cause-tag">' + name + ' ' + bars[0].pct + '%</span>';
    }

    row.innerHTML = '<td>' + (point.timestamp || '--') + '</td>'
        + '<td>' + (parseFloat(point.temperature)||0).toFixed(1) + '</td>'
        + '<td>' + (parseFloat(point.pressure)||0).toFixed(1) + '</td>'
        + '<td>' + (parseFloat(point.humidity)||0).toFixed(1) + '</td>'
        + '<td>' + (point.fuzz || 0) + '</td>'
        + '<td>' + (parseFloat(point.score)||0).toFixed(4) + '</td>'
        + '<td>' + cause + '</td>'
        + '<td>' + badge + '</td>';

    tbody.insertBefore(row, tbody.firstChild);
    while (tbody.children.length > 20) tbody.removeChild(tbody.lastChild);
}

// ── Update stats + status indicator ─────────────────────────
function updateStats(det) {
    totalPackets++;
    if (det === 1) anomaliesDetected++;
    document.getElementById('statTotal').textContent = totalPackets;
    document.getElementById('statAnomalies').textContent = anomaliesDetected;
    document.getElementById('statStealth').textContent =
        (totalPackets > 0 ? (anomaliesDetected / totalPackets * 100).toFixed(1) : '0.0') + '%';

    const statusEl = document.getElementById('statStatus');
    const indicator = document.getElementById('statusIndicator');
    const statusText = document.getElementById('statusText');

    if (det === 1) {
        statusEl.textContent = 'ATTACK'; statusEl.className = 'stat-value status-attack';
        indicator.classList.add('attack'); statusText.textContent = 'ATTACK DETECTED';
    } else {
        statusEl.textContent = 'SAFE'; statusEl.className = 'stat-value status-safe';
        indicator.classList.remove('attack'); statusText.textContent = 'SYSTEM SECURE';
    }
}

// ── Poll the server for new rows ─────────────────────────────
// Uses ?since=N so the server only returns rows we haven't seen yet.
async function poll() {
    let payload;
    try {
        const res = await fetch('/api/history?since=' + lastTotal);
        if (!res.ok) return;
        payload = await res.json();
    } catch (e) {
        return;  // network/server not ready — try again next tick
    }

    const newRows = payload.rows || [];
    const serverTotal = payload.total || lastTotal;

    // CRITICAL: advance the cursor FIRST. If a single row's render throws, we
    // must not re-fetch and re-process the same batch forever (that is what
    // froze the dashboard during high-rate attack bursts). We consume the batch
    // exactly once regardless of any per-row rendering error.
    if (newRows.length > 0) {
        lastTotal = serverTotal;
    }

    // During attack bursts the simulator sends ~5 packets/sec. Animating every
    // Chart.js update (300ms each) at that rate saturates the main thread and
    // looks like a freeze. Animate only when a single new row arrived.
    const animate = newRows.length === 1;

    for (const point of newRows) {
        try {
            pushPoint(point, animate);
            addLogEntry(point);
            updateStats(parseInt(point.detected) || 0);
        } catch (e) {
            /* one bad row must never stall the live feed */
        }
    }

    if (newRows.length > 0) {
        try { updateIntel(newRows[newRows.length - 1]); } catch (e) { /* keep polling */ }
        document.getElementById('logCount').textContent = totalPackets;
    }
}

// ── Initial page load ────────────────────────────────────────
async function loadInitial() {
    try {
        const res = await fetch('/api/history');
        if (!res.ok) return;
        const payload = await res.json();
        const rows = payload.rows || [];

        for (const point of rows) {
            try {
                pushPoint(point, false);
                updateStats(parseInt(point.detected) || 0);
            } catch (e) { /* skip a bad historical row */ }
        }
        lastTotal = payload.total || rows.length;

        // Show last 20 in log (newest first)
        const logEntries = [...rows].reverse().slice(0, 20);
        for (const entry of logEntries) {
            try { addLogEntry(entry); } catch (e) { /* skip */ }
        }
        if (rows.length > 0) {
            try { updateIntel(rows[rows.length - 1]); } catch (e) { /* ignore */ }
        }
        document.getElementById('logCount').textContent = totalPackets;
    } catch (e) { /* ignore */ }
}

// ── Reset ────────────────────────────────────────────────────
async function handleReset() {
    if (!confirm('Clear all data?')) return;
    await fetch('/api/reset', { method: 'POST' });
    location.reload();
}

// ── Boot ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    loadInitial();
    setInterval(poll, 1000);
    document.getElementById('btnReset').addEventListener('click', handleReset);
});
