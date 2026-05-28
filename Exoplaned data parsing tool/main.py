from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import cgi
import csv
import io
import json
import math
import os
from urllib.parse import urlparse

import numpy as np

try:
    from scipy.signal import find_peaks, peak_widths
except Exception:
    find_peaks = None
    peak_widths = None

try:
    from scipy.stats import chi2
except Exception:
    chi2 = None

try:
    from astropy.timeseries import BoxLeastSquares
except Exception:
    BoxLeastSquares = None


HOST = "127.0.0.1"
DEFAULT_PORT = 8000
MAX_UPLOAD_BYTES = 80 * 1024 * 1024
MAX_PLOT_POINTS = 12000
DEFAULT_DETECTION_OPTIONS = {
    "strictness": 1.0,
    "smoothing": 1.0,
    "min_depth": None,
    "min_duration": None,
    "max_duration": None,
    "min_period": None,
    "max_period": None,
}


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Exoplanet Transit Finder</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #202124;
      --muted: #60656f;
      --line: #d7dce3;
      --surface: #ffffff;
      --panel: #f5f7fa;
      --accent: #0f766e;
      --accent-2: #b45309;
      --danger: #b42318;
      --shadow: 0 16px 40px rgba(30, 41, 59, .12);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font: 15px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #eef2f6;
    }

    main {
      width: min(1220px, calc(100vw - 32px));
      margin: 24px auto;
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 18px;
      align-items: start;
    }

    h1 {
      margin: 0 0 4px;
      font-size: 26px;
      letter-spacing: 0;
    }

    h2 {
      margin: 0 0 10px;
      font-size: 16px;
    }

    p { margin: 0; color: var(--muted); }

    .sidebar, .workspace {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }

    .sidebar {
      padding: 18px;
      display: grid;
      gap: 16px;
    }

    .workspace {
      min-width: 0;
      overflow: hidden;
    }

    .topbar {
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: center;
    }

    .dropzone {
      min-height: 190px;
      border: 2px dashed #9aa6b2;
      background: var(--panel);
      border-radius: 8px;
      display: grid;
      place-items: center;
      padding: 20px;
      text-align: center;
      cursor: pointer;
      transition: border-color .15s ease, background .15s ease;
    }

    .dropzone:hover, .dropzone.dragging {
      border-color: var(--accent);
      background: #eefaf8;
    }

    .dropzone strong {
      display: block;
      margin-bottom: 6px;
      font-size: 17px;
    }

    input[type="file"] { display: none; }

    button {
      appearance: none;
      border: 1px solid var(--accent);
      background: var(--accent);
      color: #fff;
      border-radius: 6px;
      padding: 10px 13px;
      font-weight: 700;
      cursor: pointer;
    }

    button:disabled {
      cursor: not-allowed;
      opacity: .55;
    }

    .view-controls {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .view-button {
      border-color: #b8c2cc;
      background: #fff;
      color: #2f3742;
      padding: 8px 10px;
      font-size: 13px;
    }

    .view-button.active {
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
    }

    .meta {
      display: grid;
      gap: 8px;
    }

    .metric {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 9px 0;
      border-bottom: 1px solid #edf0f3;
    }

    .metric:last-child { border-bottom: 0; }
    .metric span:first-child { color: var(--muted); }
    .metric span:last-child { font-weight: 750; text-align: right; }

    .warning-list {
      display: grid;
      gap: 8px;
    }

    .warning-item {
      border: 1px solid #d7dce3;
      border-left-width: 4px;
      border-radius: 6px;
      padding: 9px 10px;
      background: #fbfcfd;
      color: #3f4650;
    }

    .warning-item strong {
      display: block;
      color: var(--ink);
      font-size: 13px;
    }

    .warning-item span {
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
    }

    .warning-item.info { border-left-color: var(--accent); }
    .warning-item.caution { border-left-color: var(--accent-2); }
    .warning-item.danger { border-left-color: var(--danger); }

    .controls {
      display: grid;
      gap: 12px;
    }

    .control-row {
      display: grid;
      gap: 5px;
    }

    .control-label {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }

    .control-label output {
      color: var(--ink);
      font-weight: 750;
    }

    input[type="range"] {
      width: 100%;
      accent-color: var(--accent);
    }

    input[type="number"] {
      width: 100%;
      border: 1px solid #c8d0da;
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
      color: var(--ink);
      background: #fff;
    }

    .chart-wrap {
      position: relative;
      height: min(66vh, 680px);
      min-height: 430px;
      background: #fbfcfd;
    }

    canvas {
      width: 100%;
      height: 100%;
      display: block;
      cursor: grab;
      touch-action: none;
      user-select: none;
    }

    canvas.dragging {
      cursor: grabbing;
    }

    canvas.editing {
      cursor: ew-resize;
    }

    tbody tr {
      cursor: pointer;
    }

    tbody tr.selected {
      background: rgba(15, 118, 110, 0.08);
    }

    .empty {
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      text-align: center;
      padding: 30px;
      color: var(--muted);
      pointer-events: none;
    }

    .table-wrap {
      border-top: 1px solid var(--line);
      max-height: 300px;
      overflow: auto;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }

    th, td {
      padding: 9px 12px;
      border-bottom: 1px solid #edf0f3;
      text-align: right;
      white-space: nowrap;
    }

    th:first-child, td:first-child { text-align: left; }
    th {
      position: sticky;
      top: 0;
      background: #f8fafc;
      color: #3f4650;
      z-index: 1;
    }

    .status {
      min-height: 22px;
      color: var(--muted);
    }

    .error { color: var(--danger); font-weight: 700; }

    @media (max-width: 860px) {
      main { grid-template-columns: 1fr; }
      .topbar { align-items: flex-start; flex-direction: column; }
      .chart-wrap { height: 58vh; min-height: 360px; }
    }
  </style>
</head>
<body>
  <main>
    <aside class="sidebar">
      <div>
        <h1>Transit Finder</h1>
        <p>Upload a CSV with <b>Time</b> and <b>Flux</b> columns.</p>
      </div>

      <label id="dropzone" class="dropzone" for="fileInput">
        <span>
          <strong>Drop CSV here</strong>
          or click to choose a file
        </span>
      </label>
      <input id="fileInput" type="file" accept=".csv,text/csv">
      <button id="analyzeButton" disabled>Analyze CSV</button>
      <div id="status" class="status">No file selected.</div>

      <section>
        <h2>Detection</h2>
        <div class="controls">
          <div class="control-row">
            <label class="control-label" for="strictnessInput">
              <span>Strictness</span>
              <output id="strictnessValue">1.00x</output>
            </label>
            <input id="strictnessInput" type="range" min="0.5" max="2" step="0.05" value="1">
          </div>
          <div class="control-row">
            <label class="control-label" for="smoothingInput">
              <span>Smoothing</span>
              <output id="smoothingValue">1.00x</output>
            </label>
            <input id="smoothingInput" type="range" min="0.5" max="2.5" step="0.05" value="1">
          </div>
          <div class="control-row">
            <label class="control-label" for="minDepthInput">
              <span>Min depth</span>
              <output>auto</output>
            </label>
            <input id="minDepthInput" type="number" min="0" step="0.001" placeholder="auto">
          </div>
          <div class="control-row">
            <label class="control-label" for="minDurationInput">
              <span>Min duration days</span>
              <output>auto</output>
            </label>
            <input id="minDurationInput" type="number" min="0" step="0.01" placeholder="auto">
          </div>
          <div class="control-row">
            <label class="control-label" for="maxDurationInput">
              <span>Max duration days</span>
              <output>auto</output>
            </label>
            <input id="maxDurationInput" type="number" min="0" step="0.01" placeholder="auto">
          </div>
          <div class="control-row">
            <label class="control-label" for="minPeriodInput">
              <span>Min period days</span>
              <output>auto</output>
            </label>
            <input id="minPeriodInput" type="number" min="0" step="0.01" placeholder="auto">
          </div>
          <div class="control-row">
            <label class="control-label" for="maxPeriodInput">
              <span>Max period days</span>
              <output>auto</output>
            </label>
            <input id="maxPeriodInput" type="number" min="0" step="0.01" placeholder="auto">
          </div>
          <button id="resetDetectionButton" class="view-button" type="button">Reset detection</button>
        </div>
      </section>

      <section>
        <h2>Analysis</h2>
        <div class="meta" id="metrics">
          <div class="metric"><span>Data points</span><span>-</span></div>
          <div class="metric"><span>Transits</span><span>-</span></div>
          <div class="metric"><span>Orbital period</span><span>-</span></div>
          <div class="metric"><span>Median depth</span><span>-</span></div>
          <div class="metric"><span>Radius ratio</span><span>-</span></div>
          <div class="metric"><span>Depth SNR</span><span>-</span></div>
          <div class="metric"><span>Period SDE</span><span>-</span></div>
          <div class="metric"><span>Chi-sq p-value</span><span>-</span></div>
          <div class="metric"><span>Reduced chi-sq</span><span>-</span></div>
          <div class="metric"><span>JD start</span><span>-</span></div>
          <div class="metric"><span>Median flux</span><span>-</span></div>
          <div class="metric"><span>Noise</span><span>-</span></div>
        </div>
      </section>

      <section>
        <h2>Period Candidates</h2>
        <div class="warning-list" id="periodCandidates">
          <div class="warning-item info">
            <strong>No candidates yet</strong>
            <span>Period search results appear after analysis.</span>
          </div>
        </div>
      </section>

      <section>
        <h2>Warnings</h2>
        <div class="warning-list" id="warnings">
          <div class="warning-item info">
            <strong>No analysis yet</strong>
            <span>Candidate checks appear after upload.</span>
          </div>
        </div>
      </section>

      <section>
        <h2>Export</h2>
        <div class="controls">
          <button id="exportCsvButton" class="view-button" type="button" disabled>Transit CSV</button>
          <button id="exportPngButton" class="view-button" type="button" disabled>Graph PNG</button>
          <button id="exportJsonButton" class="view-button" type="button" disabled>Summary JSON</button>
        </div>
      </section>
    </aside>

    <section class="workspace">
      <div class="topbar">
        <div>
          <h2 id="chartTitle">Flux Over Time</h2>
          <p id="subtitle">Transit boxes appear after analysis.</p>
        </div>
        <div class="view-controls" aria-label="Chart view">
          <button class="view-button active" type="button" data-view="zoom">Transit zoom</button>
          <button class="view-button" type="button" data-view="clean">Full cleaned</button>
          <button class="view-button" type="button" data-view="raw">Raw clipped</button>
          <button class="view-button" type="button" data-view="phase">Phase folded</button>
          <button id="editBoxesButton" class="view-button" type="button" disabled>Edit boxes</button>
        </div>
      </div>
      <div class="chart-wrap">
        <canvas id="chart"></canvas>
        <div id="empty" class="empty">Waiting for a light curve.</div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Transit</th>
              <th>Start day</th>
              <th>Center day</th>
              <th>End day</th>
              <th>Duration</th>
              <th>Depth</th>
              <th>Depth %</th>
              <th>Depth ppm</th>
              <th>Rp/Rs</th>
              <th>Points</th>
            </tr>
          </thead>
          <tbody id="transitRows">
            <tr><td colspan="10" style="text-align:left;color:#60656f;">No transit candidates yet.</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>

  <script>
    const fileInput = document.getElementById('fileInput');
    const dropzone = document.getElementById('dropzone');
    const analyzeButton = document.getElementById('analyzeButton');
    const statusEl = document.getElementById('status');
    const metricsEl = document.getElementById('metrics');
    const warningsEl = document.getElementById('warnings');
    const periodCandidatesEl = document.getElementById('periodCandidates');
    const chartTitleEl = document.getElementById('chartTitle');
    const subtitleEl = document.getElementById('subtitle');
    const emptyEl = document.getElementById('empty');
    const rowsEl = document.getElementById('transitRows');
    const canvas = document.getElementById('chart');
    const ctx = canvas.getContext('2d');
    const viewButtons = [...document.querySelectorAll('.view-button[data-view]')];
    const editBoxesButton = document.getElementById('editBoxesButton');
    const strictnessInput = document.getElementById('strictnessInput');
    const strictnessValue = document.getElementById('strictnessValue');
    const smoothingInput = document.getElementById('smoothingInput');
    const smoothingValue = document.getElementById('smoothingValue');
    const minDepthInput = document.getElementById('minDepthInput');
    const minDurationInput = document.getElementById('minDurationInput');
    const maxDurationInput = document.getElementById('maxDurationInput');
    const minPeriodInput = document.getElementById('minPeriodInput');
    const maxPeriodInput = document.getElementById('maxPeriodInput');
    const resetDetectionButton = document.getElementById('resetDetectionButton');
    const exportCsvButton = document.getElementById('exportCsvButton');
    const exportPngButton = document.getElementById('exportPngButton');
    const exportJsonButton = document.getElementById('exportJsonButton');
    let selectedFile = null;
    let currentResult = null;
    let currentView = 'zoom';
    let currentViewport = null;
    let dragState = null;
    let boxDragState = null;
    let lastPointer = null;
    let selectedTransitIndex = null;
    let editBoxesEnabled = false;
    let transitBoxCache = [];
    const chartPad = { left: 62, right: 22, top: 24, bottom: 48 };

    const fmt = (value, digits = 6) => {
      if (value === null || value === undefined || !Number.isFinite(Number(value))) return '-';
      const n = Number(value);
      if (Math.abs(n) >= 1000000 || (Math.abs(n) > 0 && Math.abs(n) < 0.001)) return n.toExponential(3);
      return Number.parseFloat(n.toFixed(digits)).toString();
    };

    const fmtPercent = value => {
      if (value === null || value === undefined || !Number.isFinite(Number(value))) return '-';
      const percent = Number(value) * 100;
      if (percent === 0) return '< 1e-12%';
      if (percent > 0 && percent < 0.000001) return '< 0.000001%';
      return `${fmt(percent, 6)}%`;
    };

    const fmtDepthPercent = value => {
      if (value === null || value === undefined || !Number.isFinite(Number(value))) return '-';
      return `${fmt(Number(value) * 100, 6)}%`;
    };

    const fmtPpm = value => {
      if (value === null || value === undefined || !Number.isFinite(Number(value))) return '-';
      return fmt(Number(value), 1);
    };

    function average(values) {
      if (!values.length) return null;
      return values.reduce((sum, value) => sum + value, 0) / values.length;
    }

    function standardDeviation(values, center = average(values)) {
      if (!values.length || center === null) return null;
      const variance = values.reduce((sum, value) => sum + (value - center) ** 2, 0) / values.length;
      return Math.sqrt(variance);
    }

    function median(values) {
      const clean = values.filter(value => Number.isFinite(value)).sort((a, b) => a - b);
      if (!clean.length) return null;
      const middle = Math.floor(clean.length / 2);
      return clean.length % 2 ? clean[middle] : (clean[middle - 1] + clean[middle]) / 2;
    }

    function coefficientOfVariation(values) {
      const clean = values.filter(value => Number.isFinite(value) && value >= 0);
      const center = median(clean);
      if (center === null || center <= 0 || clean.length < 2) return null;
      return standardDeviation(clean, average(clean)) / center;
    }

    function erfcApprox(x) {
      const z = Math.abs(x);
      const t = 1 / (1 + z / 2);
      const r = t * Math.exp(
        -z * z - 1.26551223 + t * (
          1.00002368 + t * (
            0.37409196 + t * (
              0.09678418 + t * (
                -0.18628806 + t * (
                  0.27886807 + t * (
                    -1.13520398 + t * (
                      1.48851587 + t * (
                        -0.82215223 + t * 0.17087277
                      )
                    )
                  )
                )
              )
            )
          )
        )
      );
      return x >= 0 ? r : 2 - r;
    }

    function chiSquareOneDegreePValue(deltaChiSquared) {
      if (!Number.isFinite(deltaChiSquared) || deltaChiSquared < 0) return null;
      return Math.max(0, Math.min(1, erfcApprox(Math.sqrt(deltaChiSquared / 2))));
    }

    function setStatus(message, isError = false) {
      statusEl.textContent = message;
      statusEl.className = isError ? 'status error' : 'status';
    }

    function setFile(file) {
      selectedFile = file;
      analyzeButton.disabled = !file;
      setStatus(file ? file.name : 'No file selected.');
    }

    function optionalNumber(input) {
      if (!input.value.trim()) return null;
      const value = Number(input.value);
      return Number.isFinite(value) ? value : null;
    }

    function detectionOptions() {
      return {
        strictness: Number(strictnessInput.value),
        smoothing: Number(smoothingInput.value),
        minDepth: optionalNumber(minDepthInput),
        minDuration: optionalNumber(minDurationInput),
        maxDuration: optionalNumber(maxDurationInput),
        minPeriod: optionalNumber(minPeriodInput),
        maxPeriod: optionalNumber(maxPeriodInput),
      };
    }

    function updateDetectionReadouts() {
      strictnessValue.value = `${Number(strictnessInput.value).toFixed(2)}x`;
      smoothingValue.value = `${Number(smoothingInput.value).toFixed(2)}x`;
    }

    function resetDetectionControls() {
      strictnessInput.value = '1';
      smoothingInput.value = '1';
      minDepthInput.value = '';
      minDurationInput.value = '';
      maxDurationInput.value = '';
      minPeriodInput.value = '';
      maxPeriodInput.value = '';
      updateDetectionReadouts();
    }

    function markDetectionControlsChanged() {
      if (currentResult && selectedFile) {
        setStatus('Detection controls changed. Run Analyze CSV to apply.');
      }
    }

    function canEditBoxes() {
      return Boolean(currentResult && editBoxesEnabled && currentView !== 'phase');
    }

    function syncEditButton() {
      editBoxesButton.disabled = !currentResult || currentView === 'phase';
      editBoxesButton.classList.toggle('active', editBoxesEnabled && !editBoxesButton.disabled);
      if (editBoxesButton.disabled) {
        canvas.classList.remove('editing');
      }
    }

    function syncExportButtons() {
      const disabled = !currentResult;
      exportCsvButton.disabled = disabled;
      exportPngButton.disabled = disabled;
      exportJsonButton.disabled = disabled;
    }

    fileInput.addEventListener('change', () => setFile(fileInput.files[0]));
    [strictnessInput, smoothingInput].forEach(input => {
      input.addEventListener('input', () => {
        updateDetectionReadouts();
        markDetectionControlsChanged();
      });
    });
    [minDepthInput, minDurationInput, maxDurationInput, minPeriodInput, maxPeriodInput].forEach(input => {
      input.addEventListener('change', markDetectionControlsChanged);
    });
    resetDetectionButton.addEventListener('click', () => {
      resetDetectionControls();
      markDetectionControlsChanged();
    });
    updateDetectionReadouts();

    ['dragenter', 'dragover'].forEach(name => {
      dropzone.addEventListener(name, event => {
        event.preventDefault();
        dropzone.classList.add('dragging');
      });
    });

    ['dragleave', 'drop'].forEach(name => {
      dropzone.addEventListener(name, event => {
        event.preventDefault();
        dropzone.classList.remove('dragging');
      });
    });

    dropzone.addEventListener('drop', event => {
      const file = event.dataTransfer.files[0];
      if (file) {
        fileInput.files = event.dataTransfer.files;
        setFile(file);
      }
    });

    analyzeButton.addEventListener('click', async () => {
      if (!selectedFile) return;
      setStatus('Analyzing light curve...');
      analyzeButton.disabled = true;
      try {
        const formData = new FormData();
        formData.append('csv', selectedFile);
        const options = detectionOptions();
        formData.append('strictness', options.strictness);
        formData.append('smoothing', options.smoothing);
        if (options.minDepth !== null) formData.append('minDepth', options.minDepth);
        if (options.minDuration !== null) formData.append('minDuration', options.minDuration);
        if (options.maxDuration !== null) formData.append('maxDuration', options.maxDuration);
        if (options.minPeriod !== null) formData.append('minPeriod', options.minPeriod);
        if (options.maxPeriod !== null) formData.append('maxPeriod', options.maxPeriod);
        const response = await fetch('/analyze', { method: 'POST', body: formData });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'Analysis failed.');
        currentResult = payload;
        currentViewport = null;
        selectedTransitIndex = null;
        boxDragState = null;
        transitBoxCache = [];
        renderResult(payload);
        setStatus('Analysis complete.');
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        analyzeButton.disabled = false;
      }
    });

    viewButtons.forEach(button => {
      button.addEventListener('click', () => {
        currentView = button.dataset.view;
        currentViewport = null;
        viewButtons.forEach(item => item.classList.toggle('active', item === button));
        updateChartHeading();
        syncEditButton();
        drawChart();
      });
    });

    editBoxesButton.addEventListener('click', () => {
      editBoxesEnabled = !editBoxesEnabled;
      if (!editBoxesEnabled) selectedTransitIndex = null;
      syncEditButton();
      renderTransitRows();
      drawChart();
    });

    function hasPhaseFold() {
      return Boolean(currentResult && currentResult.phase_folded && currentResult.phase_folded.phase.length);
    }

    function updateChartHeading() {
      if (!currentResult) {
        chartTitleEl.textContent = 'Flux Over Time';
        subtitleEl.textContent = 'Transit boxes appear after analysis.';
        return;
      }

      if (currentView === 'phase') {
        chartTitleEl.textContent = 'Phase-Folded Light Curve';
        if (hasPhaseFold()) {
          subtitleEl.textContent = `${currentResult.phase_folded.phase.length.toLocaleString()} folded points centered on phase 0 using a ${fmt(currentResult.phase_folded.period)} day period.`;
        } else {
          subtitleEl.textContent = 'Phase folding needs a detected orbital period.';
        }
        return;
      }

      chartTitleEl.textContent = 'Flux Over Time';
      subtitleEl.textContent = `${currentResult.plot.time.length.toLocaleString()} plotted points shown from ${currentResult.total_points.toLocaleString()} total samples. Time is shown as Julian days since JD ${fmt(currentResult.time_reference, 5)}.`;
    }

    function estimatePeriodFromTransitBoxes() {
      const centers = currentResult.transits
        .map(transit => Number(transit.center))
        .filter(value => Number.isFinite(value))
        .sort((a, b) => a - b);
      if (centers.length < 2) return { period: null, scatter: null, count: 0 };

      const originalPeriod = Number(currentResult.original_period ?? currentResult.period);
      let periodSamples = [];
      if (Number.isFinite(originalPeriod) && originalPeriod > 0) {
        for (let left = 0; left < centers.length; left++) {
          for (let right = left + 1; right < centers.length; right++) {
            const gap = centers[right] - centers[left];
            const cycles = Math.round(gap / originalPeriod);
            if (cycles < 1) continue;
            const normalizedGap = gap / cycles;
            if (Math.abs(normalizedGap - originalPeriod) / originalPeriod <= 0.3) {
              periodSamples.push(normalizedGap);
            }
          }
        }
      }

      if (!periodSamples.length) {
        periodSamples = centers.slice(1).map((center, index) => center - centers[index]);
      }

      const period = average(periodSamples);
      return {
        period,
        scatter: standardDeviation(periodSamples, period),
        count: periodSamples.length,
      };
    }

    function estimatePValueFromTransitBoxes() {
      if (!currentResult || !currentResult.transits.length) return null;
      const times = currentResult.plot.time;
      const flux = currentResult.plot.smooth_flux;
      const usableFlux = [];
      const inTransit = [];

      for (let i = 0; i < times.length; i++) {
        const value = Number(flux[i]);
        if (!Number.isFinite(value)) continue;
        usableFlux.push(value);
        inTransit.push(currentResult.transits.some(transit => times[i] >= transit.start && times[i] <= transit.end));
      }

      const inValues = usableFlux.filter((value, index) => inTransit[index]);
      const outValues = usableFlux.filter((value, index) => !inTransit[index]);
      if (inValues.length < 3 || outValues.length < 3) return null;

      const baseline = average(usableFlux);
      const flatResiduals = usableFlux.map(value => value - baseline);
      const residualMedian = median(flatResiduals) ?? 0;
      const mad = median(flatResiduals.map(value => Math.abs(value - residualMedian))) ?? 0;
      const sigma = Math.max(1.4826 * mad, standardDeviation(flatResiduals, 0) ?? 0, 1e-9);
      const inLevel = average(inValues);
      const outLevel = average(outValues);
      if (inLevel === null || outLevel === null || inLevel >= outLevel) return null;

      const chiFlat = usableFlux.reduce((sum, value) => sum + ((value - baseline) / sigma) ** 2, 0);
      const chiBox = usableFlux.reduce((sum, value, index) => {
        const model = inTransit[index] ? inLevel : outLevel;
        return sum + ((value - model) / sigma) ** 2;
      }, 0);
      const delta = Math.max(0, chiFlat - chiBox);
      return {
        pValue: chiSquareOneDegreePValue(delta),
        deltaChiSquared: delta,
      };
    }

    function currentAnalysisMetrics() {
      const depthFractions = currentResult.transits
        .map(transit => Number(transit.depth_fraction))
        .filter(value => Number.isFinite(value) && value >= 0);
      const radiusRatios = currentResult.transits
        .map(transit => Number(transit.radius_ratio))
        .filter(value => Number.isFinite(value) && value >= 0);
      const metrics = {
        period: currentResult.period,
        periodMethod: currentResult.period_method,
        periodScatter: currentResult.period_scatter,
        periodMatchCount: currentResult.period_match_count,
        pValue: currentResult.p_value,
        deltaChiSquared: currentResult.delta_chi_squared,
        reducedChiSquared: currentResult.reduced_chi_squared_box,
        periodSde: currentResult.period_sde,
        medianDepthFraction: median(depthFractions),
        medianRadiusRatio: median(radiusRatios),
        detectionSnr: currentResult.detection_snr,
        oddEvenDepthMismatch: currentResult.odd_even_depth_mismatch,
        depthScatterRatio: currentResult.depth_scatter_ratio,
      };

      if (currentResult.boxesEdited) {
        const periodStats = estimatePeriodFromTransitBoxes();
        if (periodStats.period !== null) {
          metrics.period = periodStats.period;
          metrics.periodMethod = 'edited boxes';
          metrics.periodScatter = periodStats.scatter;
          metrics.periodMatchCount = periodStats.count;
        }

        const pValueStats = estimatePValueFromTransitBoxes();
        if (pValueStats && pValueStats.pValue !== null) {
          metrics.pValue = pValueStats.pValue;
          metrics.deltaChiSquared = pValueStats.deltaChiSquared;
        }
      }

      return metrics;
    }

    function currentWarnings(metrics = currentAnalysisMetrics()) {
      if (!currentResult) return [];
      const transits = currentResult.transits || [];
      const warnings = [];
      const depths = transits
        .map(transit => Number(transit.depth_ppm ?? transit.depth))
        .filter(value => Number.isFinite(value) && value >= 0);
      const rawDepths = transits
        .map(transit => Number(transit.depth))
        .filter(value => Number.isFinite(value) && value >= 0);
      const radii = transits
        .map(transit => Number(transit.radius_ratio))
        .filter(value => Number.isFinite(value) && value >= 0);
      const points = transits
        .map(transit => Number(transit.points))
        .filter(value => Number.isFinite(value) && value >= 0);
      const oddDepths = depths.filter((_, index) => index % 2 === 0);
      const evenDepths = depths.filter((_, index) => index % 2 === 1);
      const oddMedian = median(oddDepths);
      const evenMedian = median(evenDepths);
      const depthCenter = median(depths);
      const depthScatterRatio = coefficientOfVariation(depths);
      const oddEvenMismatch = (
        oddMedian !== null && evenMedian !== null && Math.max(oddMedian, evenMedian) > 0
      ) ? Math.abs(oddMedian - evenMedian) / Math.max(oddMedian, evenMedian) : null;
      const rawDepthCenter = median(rawDepths);
      const snr = currentResult.boxesEdited || !Number.isFinite(Number(metrics.detectionSnr)) ? (
        rawDepthCenter !== null && Number.isFinite(Number(currentResult.robust_noise)) && currentResult.robust_noise > 0
          ? rawDepthCenter / currentResult.robust_noise
          : null
      ) : Number(metrics.detectionSnr);
      const medianPoints = median(points);
      const maxRadius = radii.length ? Math.max(...radii) : null;

      if (!transits.length) {
        warnings.push({
          severity: 'caution',
          title: 'No transit candidates',
          detail: 'Try lowering strictness or checking the input columns and flux units.',
        });
      }
      if (transits.length > 0 && transits.length < 3) {
        warnings.push({
          severity: 'caution',
          title: 'Few observed transits',
          detail: 'A single event or pair of events is harder to separate from systematics.',
        });
      }
      if (metrics.period === null || metrics.period === undefined) {
        warnings.push({
          severity: 'caution',
          title: 'No stable period',
          detail: 'The app could not estimate a repeating orbital period.',
        });
      }
      if (metrics.periodMethod && metrics.periodMethod !== 'BLS') {
        warnings.push({
          severity: 'info',
          title: 'Period is provisional',
          detail: `Period came from ${metrics.periodMethod}, not a BLS peak.`,
        });
      }
      if (metrics.pValue !== null && metrics.pValue !== undefined && metrics.pValue > 0.01) {
        warnings.push({
          severity: 'caution',
          title: 'Weak model significance',
          detail: 'The box model is not much better than a flat light curve by the current chi-squared estimate.',
        });
      }
      if (snr !== null && snr < 7) {
        warnings.push({
          severity: 'caution',
          title: 'Low depth SNR',
          detail: `Median transit depth is about ${fmt(snr, 2)}x the robust noise.`,
        });
      }
      if (oddEvenMismatch !== null && oddEvenMismatch > 0.5 && oddDepths.length >= 2 && evenDepths.length >= 2) {
        warnings.push({
          severity: 'danger',
          title: 'Odd/even depth mismatch',
          detail: 'Alternating transit depths can indicate an eclipsing binary or blended source.',
        });
      }
      if (depthScatterRatio !== null && depthScatterRatio > 0.8 && depths.length >= 4) {
        warnings.push({
          severity: 'caution',
          title: 'Inconsistent transit depths',
          detail: 'Detected depths vary substantially across events.',
        });
      }
      if (maxRadius !== null && maxRadius > 0.2) {
        warnings.push({
          severity: 'caution',
          title: 'Large radius ratio',
          detail: 'Rp/Rs above 0.2 is large for many planet candidates and deserves closer inspection.',
        });
      }
      if (medianPoints !== null && medianPoints < 4) {
        warnings.push({
          severity: 'info',
          title: 'Sparse transit sampling',
          detail: 'Some events have very few points inside the detected box.',
        });
      }
      return warnings;
    }

    function renderWarnings() {
      if (!currentResult) return;
      const warnings = currentWarnings();
      if (!warnings.length) {
        warningsEl.innerHTML = `
          <div class="warning-item info">
            <strong>No major warnings</strong>
            <span>These checks are heuristic and do not prove the candidate is planetary.</span>
          </div>
        `;
        return;
      }
      warningsEl.innerHTML = warnings.map(warning => `
        <div class="warning-item ${warning.severity}">
          <strong>${warning.title}</strong>
          <span>${warning.detail}</span>
        </div>
      `).join('');
    }

    function renderPeriodCandidates() {
      if (!currentResult) return;
      const candidates = (currentResult.period_candidates || []).slice(0, 5);
      if (!candidates.length) {
        periodCandidatesEl.innerHTML = `
          <div class="warning-item info">
            <strong>No period grid</strong>
            <span>Only candidate-box spacing is available for this run.</span>
          </div>
        `;
        return;
      }
      periodCandidatesEl.innerHTML = candidates.map((candidate, index) => `
        <div class="warning-item ${index === 0 ? 'info' : 'caution'}">
          <strong>${fmt(candidate.period, 4)} days</strong>
          <span>Power ${fmt(candidate.power, 2)}${candidate.sde === null || candidate.sde === undefined ? '' : `, SDE ${fmt(candidate.sde, 2)}`}</span>
        </div>
      `).join('');
    }

    function renderMetrics() {
      if (!currentResult) return;
      const metrics = currentAnalysisMetrics();
      const period = metrics.period === null || metrics.period === undefined
        ? 'Not enough transits'
        : `${fmt(metrics.period)} days${metrics.periodMethod ? ` (${metrics.periodMethod})` : ''}`;

      metricsEl.innerHTML = `
        <div class="metric"><span>Data points</span><span>${currentResult.total_points.toLocaleString()}</span></div>
        <div class="metric"><span>Transits</span><span>${currentResult.transits.length}</span></div>
        <div class="metric"><span>Orbital period</span><span>${period}</span></div>
        <div class="metric"><span>Median depth</span><span>${fmtDepthPercent(metrics.medianDepthFraction)} / ${fmtPpm(metrics.medianDepthFraction === null ? null : metrics.medianDepthFraction * 1000000)} ppm</span></div>
        <div class="metric"><span>Radius ratio</span><span>${fmt(metrics.medianRadiusRatio)}</span></div>
        <div class="metric"><span>Depth SNR</span><span>${fmt(metrics.detectionSnr, 2)}</span></div>
        <div class="metric"><span>Period SDE</span><span>${fmt(metrics.periodSde, 2)}</span></div>
        <div class="metric"><span>Chi-sq p-value</span><span>${fmtPercent(metrics.pValue)}</span></div>
        <div class="metric"><span>Reduced chi-sq</span><span>${fmt(metrics.reducedChiSquared, 3)}</span></div>
        <div class="metric"><span>JD start</span><span>${fmt(currentResult.time_reference, 5)}</span></div>
        <div class="metric"><span>Median flux</span><span>${fmt(currentResult.median_flux)}</span></div>
        <div class="metric"><span>Noise</span><span>${fmt(currentResult.robust_noise)}</span></div>
      `;
      renderPeriodCandidates();
      renderWarnings();
    }

    function renderResult(result) {
      emptyEl.style.display = 'none';
      result.original_period = result.period;
      result.original_period_method = result.period_method;
      result.boxesEdited = false;
      renderMetrics();
      updateChartHeading();
      syncEditButton();
      syncExportButtons();
      renderTransitRows();
      drawChart();
    }

    function renderTransitRows() {
      if (!currentResult) return;
      rowsEl.innerHTML = currentResult.transits.length ? currentResult.transits.map((t, index) => `
        <tr data-transit-index="${index}" class="${index === selectedTransitIndex ? 'selected' : ''}">
          <td>Transit ${index + 1}</td>
          <td>${fmt(t.start)}</td>
          <td>${fmt(t.center)}</td>
          <td>${fmt(t.end)}</td>
          <td>${fmt(t.duration)}</td>
          <td>${fmt(t.depth)}</td>
          <td>${fmtDepthPercent(t.depth_fraction)}</td>
          <td>${fmtPpm(t.depth_ppm)}</td>
          <td>${fmt(t.radius_ratio)}</td>
          <td>${t.points}</td>
        </tr>
      `).join('') : '<tr><td colspan="10" style="text-align:left;color:#60656f;">No statistically strong transit candidates found.</td></tr>';
    }

    rowsEl.addEventListener('click', event => {
      const row = event.target.closest('tr[data-transit-index]');
      if (!row || !currentResult) return;
      selectedTransitIndex = Number(row.dataset.transitIndex);
      renderTransitRows();
      drawChart();
    });

    function exportBaseName() {
      const fileStem = selectedFile
        ? selectedFile.name.replace(/\.[^/.]+$/, '')
        : 'transit-analysis';
      const safeStem = fileStem.replace(/[^a-z0-9_-]+/gi, '-').replace(/^-+|-+$/g, '');
      return safeStem || 'transit-analysis';
    }

    function downloadBlob(content, filename, type) {
      const blob = content instanceof Blob ? content : new Blob([content], { type });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }

    function csvCell(value) {
      if (value === null || value === undefined) return '';
      const text = String(value);
      return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    }

    function transitRowsForExport() {
      return currentResult.transits.map((transit, index) => ({
        transit: index + 1,
        start_day: transit.start,
        center_day: transit.center,
        end_day: transit.end,
        start_jd: currentResult.time_reference + transit.start,
        center_jd: currentResult.time_reference + transit.center,
        end_jd: currentResult.time_reference + transit.end,
        duration_days: transit.duration,
        depth: transit.depth,
        depth_fraction: transit.depth_fraction,
        depth_percent: transit.depth_percent,
        depth_ppm: transit.depth_ppm,
        radius_ratio: transit.radius_ratio,
        depth_basis: transit.depth_basis,
        points: transit.points,
        manually_edited: Boolean(transit.manually_edited),
      }));
    }

    function exportTransitCsv() {
      if (!currentResult) return;
      const rows = transitRowsForExport();
      const headers = [
        'transit',
        'start_day',
        'center_day',
        'end_day',
        'start_jd',
        'center_jd',
        'end_jd',
        'duration_days',
        'depth',
        'depth_fraction',
        'depth_percent',
        'depth_ppm',
        'radius_ratio',
        'depth_basis',
        'points',
        'manually_edited',
      ];
      const csv = [
        headers.join(','),
        ...rows.map(row => headers.map(header => csvCell(row[header])).join(',')),
      ].join('\n');
      downloadBlob(csv, `${exportBaseName()}-transits.csv`, 'text/csv;charset=utf-8');
      setStatus('Transit CSV exported.');
    }

    function summaryForExport() {
      const metrics = currentAnalysisMetrics();
      const warnings = currentWarnings(metrics);
      return {
        exported_at: new Date().toISOString(),
        source_file: selectedFile ? selectedFile.name : null,
        chart_view: currentView,
        total_points: currentResult.total_points,
        time_reference_jd: currentResult.time_reference,
        time_unit: currentResult.time_unit,
        detection_options: currentResult.detection_options,
        boxes_edited: Boolean(currentResult.boxesEdited),
        warnings,
        diagnostics: {
          detection_snr: metrics.detectionSnr,
          odd_even_depth_mismatch: metrics.oddEvenDepthMismatch,
          depth_scatter_ratio: metrics.depthScatterRatio,
        },
        metrics: {
          transit_count: currentResult.transits.length,
          orbital_period_days: metrics.period,
          orbital_period_method: metrics.periodMethod,
          orbital_period_scatter: metrics.periodScatter,
          period_sample_count: metrics.periodMatchCount,
          median_depth_fraction: metrics.medianDepthFraction,
          median_depth_percent: metrics.medianDepthFraction === null ? null : metrics.medianDepthFraction * 100,
          median_depth_ppm: metrics.medianDepthFraction === null ? null : metrics.medianDepthFraction * 1000000,
          median_radius_ratio: metrics.medianRadiusRatio,
          chi_square_p_value: metrics.pValue,
          chi_square_p_value_percent: metrics.pValue === null || metrics.pValue === undefined ? null : metrics.pValue * 100,
          delta_chi_squared: metrics.deltaChiSquared,
          reduced_chi_squared: metrics.reducedChiSquared,
          detection_snr: metrics.detectionSnr,
          period_sde: metrics.periodSde,
          median_flux: currentResult.median_flux,
          robust_noise: currentResult.robust_noise,
        },
        period_candidates: currentResult.period_candidates || [],
        period_search: currentResult.period_search || null,
        transits: transitRowsForExport(),
      };
    }

    function exportSummaryJson() {
      if (!currentResult) return;
      downloadBlob(
        JSON.stringify(summaryForExport(), null, 2),
        `${exportBaseName()}-summary.json`,
        'application/json;charset=utf-8'
      );
      setStatus('Summary JSON exported.');
    }

    function exportGraphPng() {
      if (!currentResult) return;
      drawChart();
      canvas.toBlob(blob => {
        if (!blob) {
          setStatus('Graph PNG export failed.', true);
          return;
        }
        downloadBlob(blob, `${exportBaseName()}-${currentView}-graph.png`, 'image/png');
        setStatus('Graph PNG exported.');
      }, 'image/png');
    }

    exportCsvButton.addEventListener('click', exportTransitCsv);
    exportPngButton.addEventListener('click', exportGraphPng);
    exportJsonButton.addEventListener('click', exportSummaryJson);

    function resizeCanvas() {
      const rect = canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.floor(rect.width * ratio));
      canvas.height = Math.max(1, Math.floor(rect.height * ratio));
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    }

    function getChartGeometry() {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      return {
        width,
        height,
        pad: chartPad,
        innerW: Math.max(1, width - chartPad.left - chartPad.right),
        innerH: Math.max(1, height - chartPad.top - chartPad.bottom),
      };
    }

    function getInitialDomain() {
      if (!currentResult) return null;
      if (currentView === 'phase') {
        if (!hasPhaseFold()) return null;
        const phaseDomain = currentResult.phase_folded.focus_domain || currentResult.phase_folded.domain;
        return {
          xMin: phaseDomain.time_min,
          xMax: phaseDomain.time_max,
          yMin: phaseDomain.flux_min,
          yMax: phaseDomain.flux_max,
        };
      }
      const zoomReady = currentView === 'zoom' && currentResult.zoom_domain;
      const yDomain = zoomReady ? currentResult.zoom_domain : (currentView === 'raw' ? currentResult.raw_domain : currentResult.clean_domain);
      return {
        xMin: zoomReady ? currentResult.zoom_domain.time_min : currentResult.domain.time_min,
        xMax: zoomReady ? currentResult.zoom_domain.time_max : currentResult.domain.time_max,
        yMin: yDomain.flux_min,
        yMax: yDomain.flux_max,
      };
    }

    function getLimitDomain() {
      if (!currentResult) return null;
      if (currentView === 'phase') {
        if (!hasPhaseFold()) return null;
        const phaseDomain = currentResult.phase_folded.domain;
        return {
          xMin: phaseDomain.time_min,
          xMax: phaseDomain.time_max,
          yMin: phaseDomain.flux_min,
          yMax: phaseDomain.flux_max,
        };
      }
      const yDomain = currentView === 'raw' ? currentResult.raw_domain : currentResult.clean_domain;
      return {
        xMin: currentResult.domain.time_min,
        xMax: currentResult.domain.time_max,
        yMin: yDomain.flux_min,
        yMax: yDomain.flux_max,
      };
    }

    function cloneDomain(domain) {
      return { xMin: domain.xMin, xMax: domain.xMax, yMin: domain.yMin, yMax: domain.yMax };
    }

    function clampRange(min, max, limitMin, limitMax) {
      const limitSpan = Math.max(1e-12, limitMax - limitMin);
      let span = Math.max(1e-12, max - min);
      const minSpan = limitSpan * 0.0005;
      if (span < minSpan) {
        const center = (min + max) / 2;
        span = minSpan;
        min = center - span / 2;
        max = center + span / 2;
      }
      if (span >= limitSpan) return [limitMin, limitMax];
      if (min < limitMin) {
        max += limitMin - min;
        min = limitMin;
      }
      if (max > limitMax) {
        min -= max - limitMax;
        max = limitMax;
      }
      return [min, max];
    }

    function clampViewport(viewport) {
      const limit = getLimitDomain();
      if (!limit) return viewport;
      const [xMin, xMax] = clampRange(viewport.xMin, viewport.xMax, limit.xMin, limit.xMax);
      const [yMin, yMax] = clampRange(viewport.yMin, viewport.yMax, limit.yMin, limit.yMax);
      return { xMin, xMax, yMin, yMax };
    }

    function getViewport() {
      if (!currentViewport) {
        const initial = getInitialDomain();
        if (!initial) return null;
        currentViewport = clampViewport(cloneDomain(initial));
      }
      return currentViewport;
    }

    function pointerPosition(event) {
      const rect = canvas.getBoundingClientRect();
      return {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      };
    }

    function clampPointerToPlot(point) {
      const geo = getChartGeometry();
      return {
        x: Math.min(geo.width - geo.pad.right, Math.max(geo.pad.left, point.x)),
        y: Math.min(geo.height - geo.pad.bottom, Math.max(geo.pad.top, point.y)),
      };
    }

    function dataAtCanvasPoint(point, viewport) {
      const geo = getChartGeometry();
      const clamped = clampPointerToPlot(point);
      const xRatio = (clamped.x - geo.pad.left) / geo.innerW;
      const yRatio = (clamped.y - geo.pad.top) / geo.innerH;
      return {
        x: viewport.xMin + xRatio * (viewport.xMax - viewport.xMin),
        y: viewport.yMax - yRatio * (viewport.yMax - viewport.yMin),
      };
    }

    function zoomAtPointer(scale, axis = 'both') {
      const viewport = getViewport();
      if (!viewport) return;
      const geo = getChartGeometry();
      const point = lastPointer || {
        x: geo.pad.left + geo.innerW / 2,
        y: geo.pad.top + geo.innerH / 2,
      };
      const anchor = dataAtCanvasPoint(point, viewport);
      currentViewport = clampViewport({
        xMin: axis === 'y' ? viewport.xMin : anchor.x - (anchor.x - viewport.xMin) * scale,
        xMax: axis === 'y' ? viewport.xMax : anchor.x + (viewport.xMax - anchor.x) * scale,
        yMin: axis === 'x' ? viewport.yMin : anchor.y - (anchor.y - viewport.yMin) * scale,
        yMax: axis === 'x' ? viewport.yMax : anchor.y + (viewport.yMax - anchor.y) * scale,
      });
      drawChart();
    }

    function transitFluxRange(transit, flux) {
      if (Number.isFinite(transit.flux_min) && Number.isFinite(transit.flux_max)) {
        const padding = Math.max((transit.flux_max - transit.flux_min) * 0.14, Math.abs(transit.depth || 0) * 0.04, 1e-9);
        return { low: transit.flux_min - padding, high: transit.flux_max + padding };
      }
      let low = Infinity;
      let high = -Infinity;
      let count = 0;
      for (let i = 0; i < currentResult.plot.time.length; i++) {
        const time = currentResult.plot.time[i];
        if (time < transit.start || time > transit.end) continue;
        const value = flux[i];
        if (!Number.isFinite(value)) continue;
        low = Math.min(low, value);
        high = Math.max(high, value);
        count += 1;
      }
      if (!count) return null;
      const padding = Math.max((high - low) * 0.22, Math.abs(transit.depth || 0) * 0.08, 1e-9);
      return { low: low - padding, high: high + padding };
    }

    function minimumTransitDuration() {
      if (!currentResult) return 1e-6;
      const span = Math.max(1e-9, currentResult.domain.time_max - currentResult.domain.time_min);
      return Math.max(span * 0.00025, 1e-6);
    }

    function applyDepthMetrics(transit, baseline) {
      if (!transit || !Number.isFinite(Number(transit.depth)) || Number(transit.depth) < 0) {
        transit.depth_fraction = null;
        transit.depth_percent = null;
        transit.depth_ppm = null;
        transit.radius_ratio = null;
        transit.depth_basis = null;
        return;
      }
      const depth = Number(transit.depth);
      const normalizedFraction = Number.isFinite(Number(baseline)) && baseline > 0
        ? depth / Number(baseline)
        : null;
      const useNormalizedFlux = normalizedFraction !== null && normalizedFraction <= 0.5;
      const depthFraction = useNormalizedFlux ? normalizedFraction : depth / 1000000;
      transit.depth_fraction = depthFraction;
      transit.depth_percent = depthFraction * 100;
      transit.depth_ppm = depthFraction * 1000000;
      transit.radius_ratio = Math.sqrt(depthFraction);
      transit.depth_basis = useNormalizedFlux ? 'fractional flux' : 'ppm flux';
    }

    function clampTransitBounds(start, end) {
      const minDuration = minimumTransitDuration();
      const domain = currentResult.domain;
      start = Math.max(domain.time_min, Math.min(domain.time_max - minDuration, start));
      end = Math.max(start + minDuration, Math.min(domain.time_max, end));
      return { start, end };
    }

    function refreshTransitStats(transit) {
      const times = currentResult.plot.time;
      const flux = currentResult.plot.smooth_flux;
      let low = Infinity;
      let high = -Infinity;
      let count = 0;
      for (let i = 0; i < times.length; i++) {
        if (times[i] < transit.start || times[i] > transit.end) continue;
        const value = flux[i];
        if (!Number.isFinite(value)) continue;
        low = Math.min(low, value);
        high = Math.max(high, value);
        count += 1;
      }
      if (count > 0) {
        transit.flux_min = low;
        transit.flux_max = high;
        transit.points = count;
        const baseline = Number.isFinite(currentResult.median_flux) ? currentResult.median_flux : high;
        transit.depth = Math.max(0, baseline - low);
        applyDepthMetrics(transit, baseline);
      }
    }

    function setTransitBounds(index, start, end) {
      const transit = currentResult.transits[index];
      if (!transit) return;
      const bounds = clampTransitBounds(start, end);
      transit.start = bounds.start;
      transit.end = bounds.end;
      transit.center = (bounds.start + bounds.end) / 2;
      transit.duration = bounds.end - bounds.start;
      transit.manually_edited = true;
      currentResult.boxesEdited = true;
      refreshTransitStats(transit);
      renderMetrics();
    }

    function hitTestTransitBox(point) {
      if (!canEditBoxes()) return null;
      for (let i = transitBoxCache.length - 1; i >= 0; i--) {
        const box = transitBoxCache[i];
        const xMin = Math.min(box.x1, box.x2);
        const xMax = Math.max(box.x1, box.x2);
        const yMin = Math.min(box.y1, box.y2);
        const yMax = Math.max(box.y1, box.y2);
        if (point.x < xMin - 6 || point.x > xMax + 6 || point.y < yMin - 6 || point.y > yMax + 6) {
          continue;
        }
        const leftDistance = Math.abs(point.x - xMin);
        const rightDistance = Math.abs(point.x - xMax);
        if (leftDistance <= 8) return { index: box.index, mode: 'left' };
        if (rightDistance <= 8) return { index: box.index, mode: 'right' };
        return { index: box.index, mode: 'move' };
      }
      return null;
    }

    function updateCanvasCursor(point = lastPointer) {
      if (dragState) {
        canvas.style.cursor = 'grabbing';
        return;
      }
      if (boxDragState) {
        canvas.style.cursor = boxDragState.mode === 'move' ? 'move' : 'ew-resize';
        return;
      }
      if (point && canEditBoxes()) {
        const hit = hitTestTransitBox(point);
        if (hit) {
          canvas.style.cursor = hit.mode === 'move' ? 'move' : 'ew-resize';
          return;
        }
      }
      canvas.style.cursor = 'grab';
    }

    function drawNotice(message, width, height) {
      ctx.fillStyle = '#fbfcfd';
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = '#60656f';
      ctx.font = '700 14px system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(message, width / 2, height / 2);
    }

    canvas.addEventListener('pointermove', event => {
      lastPointer = pointerPosition(event);
      if (boxDragState && currentResult) {
        const pointData = dataAtCanvasPoint(lastPointer, boxDragState.viewport);
        const original = boxDragState.original;
        const minDuration = minimumTransitDuration();
        if (boxDragState.mode === 'left') {
          setTransitBounds(boxDragState.index, Math.min(pointData.x, original.end - minDuration), original.end);
        } else if (boxDragState.mode === 'right') {
          setTransitBounds(boxDragState.index, original.start, Math.max(pointData.x, original.start + minDuration));
        } else {
          const shift = pointData.x - boxDragState.anchorData.x;
          let start = original.start + shift;
          let end = original.end + shift;
          if (start < currentResult.domain.time_min) {
            end += currentResult.domain.time_min - start;
            start = currentResult.domain.time_min;
          }
          if (end > currentResult.domain.time_max) {
            start -= end - currentResult.domain.time_max;
            end = currentResult.domain.time_max;
          }
          setTransitBounds(boxDragState.index, start, end);
        }
        renderTransitRows();
        drawChart();
        updateCanvasCursor(lastPointer);
        return;
      }
      if (!dragState || !currentResult) {
        updateCanvasCursor(lastPointer);
        return;
      }
      const geo = getChartGeometry();
      const dx = lastPointer.x - dragState.x;
      const dy = lastPointer.y - dragState.y;
      const xSpan = dragState.viewport.xMax - dragState.viewport.xMin;
      const ySpan = dragState.viewport.yMax - dragState.viewport.yMin;
      const xShift = -dx / geo.innerW * xSpan;
      const yShift = dy / geo.innerH * ySpan;
      currentViewport = clampViewport({
        xMin: dragState.viewport.xMin + xShift,
        xMax: dragState.viewport.xMax + xShift,
        yMin: dragState.viewport.yMin + yShift,
        yMax: dragState.viewport.yMax + yShift,
      });
      drawChart();
      updateCanvasCursor(lastPointer);
    });

    canvas.addEventListener('pointerdown', event => {
      if (!currentResult || event.button !== 0) return;
      event.preventDefault();
      const point = pointerPosition(event);
      lastPointer = point;
      const viewport = getViewport();
      if (!viewport) return;
      const hit = hitTestTransitBox(point);
      if (hit) {
        const transit = currentResult.transits[hit.index];
        selectedTransitIndex = hit.index;
        boxDragState = {
          index: hit.index,
          mode: hit.mode,
          anchorData: dataAtCanvasPoint(point, viewport),
          viewport: cloneDomain(viewport),
          original: {
            start: transit.start,
            end: transit.end,
          },
        };
        canvas.classList.add('editing');
        renderTransitRows();
        drawChart();
        updateCanvasCursor(point);
        canvas.setPointerCapture(event.pointerId);
        return;
      }
      if (canEditBoxes()) {
        selectedTransitIndex = null;
        renderTransitRows();
        drawChart();
      }
      dragState = {
        x: point.x,
        y: point.y,
        viewport: cloneDomain(viewport),
      };
      canvas.classList.add('dragging');
      canvas.setPointerCapture(event.pointerId);
    });

    function finishDrag(event) {
      if (boxDragState) {
        boxDragState = null;
        canvas.classList.remove('editing');
        updateCanvasCursor(lastPointer);
        if (event && canvas.hasPointerCapture(event.pointerId)) {
          canvas.releasePointerCapture(event.pointerId);
        }
        return;
      }
      if (!dragState) return;
      dragState = null;
      canvas.classList.remove('dragging');
      updateCanvasCursor(lastPointer);
      if (event && canvas.hasPointerCapture(event.pointerId)) {
        canvas.releasePointerCapture(event.pointerId);
      }
    }

    canvas.addEventListener('pointerup', finishDrag);
    canvas.addEventListener('pointercancel', finishDrag);
    canvas.addEventListener('pointerleave', event => {
      if (!dragState) lastPointer = null;
      updateCanvasCursor(lastPointer);
    });

    document.addEventListener('keydown', event => {
      if (!currentResult) return;
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        zoomAtPointer(0.72);
      } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        zoomAtPointer(1.28);
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
        zoomAtPointer(1.28, 'x');
      } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        zoomAtPointer(0.72, 'x');
      }
    });

    function drawPhaseChart(geo) {
      transitBoxCache = [];
      const width = geo.width;
      const height = geo.height;
      const pad = geo.pad;
      const innerW = geo.innerW;
      const innerH = geo.innerH;
      if (!hasPhaseFold()) {
        drawNotice('Phase folding needs a detected orbital period.', width, height);
        return;
      }

      const folded = currentResult.phase_folded;
      const viewport = getViewport();
      if (!viewport) {
        drawNotice('Phase folding needs a detected orbital period.', width, height);
        return;
      }

      const xMin = viewport.xMin;
      const xMax = viewport.xMax;
      const yMin = viewport.yMin;
      const yMax = viewport.yMax;
      const xScale = value => pad.left + ((value - xMin) / (xMax - xMin || 1)) * innerW;
      const yScale = value => pad.top + (1 - ((value - yMin) / (yMax - yMin || 1))) * innerH;

      ctx.fillStyle = '#fbfcfd';
      ctx.fillRect(0, 0, width, height);

      if (Number.isFinite(folded.duration) && folded.duration > 0) {
        const start = Math.max(xMin, -folded.duration / 2);
        const end = Math.min(xMax, folded.duration / 2);
        if (end > start) {
          ctx.fillStyle = 'rgba(180, 83, 9, 0.12)';
          ctx.fillRect(xScale(start), pad.top, Math.max(1, xScale(end) - xScale(start)), innerH);
        }
      }

      ctx.strokeStyle = '#d6dde5';
      ctx.lineWidth = 1;
      ctx.fillStyle = '#5f6874';
      ctx.font = '12px system-ui, sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';

      for (let i = 0; i <= 5; i++) {
        const y = pad.top + (innerH * i / 5);
        const value = yMax - ((yMax - yMin) * i / 5);
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(width - pad.right, y);
        ctx.stroke();
        ctx.fillText(fmt(value, 4), pad.left - 8, y);
      }

      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      for (let i = 0; i <= 6; i++) {
        const x = pad.left + (innerW * i / 6);
        const value = xMin + ((xMax - xMin) * i / 6);
        ctx.beginPath();
        ctx.moveTo(x, pad.top + innerH);
        ctx.lineTo(x, pad.top + innerH + 5);
        ctx.stroke();
        ctx.fillText(fmt(value, 4), x, pad.top + innerH + 10);
      }

      const zeroX = xScale(0);
      if (zeroX >= pad.left && zeroX <= width - pad.right) {
        ctx.strokeStyle = 'rgba(180, 83, 9, 0.75)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(zeroX, pad.top);
        ctx.lineTo(zeroX, pad.top + innerH);
        ctx.stroke();
      }

      ctx.save();
      ctx.beginPath();
      ctx.rect(pad.left, pad.top, innerW, innerH);
      ctx.clip();

      ctx.fillStyle = 'rgba(15, 118, 110, 0.18)';
      const pointSize = folded.phase.length > 8000 ? 1.2 : 1.8;
      for (let i = 0; i < folded.phase.length; i++) {
        const phase = folded.phase[i];
        const value = folded.raw_flux[i];
        if (phase < xMin || phase > xMax || value < yMin || value > yMax) continue;
        const x = xScale(phase);
        const y = yScale(value);
        ctx.fillRect(x - pointSize / 2, y - pointSize / 2, pointSize, pointSize);
      }

      ctx.strokeStyle = '#063f3b';
      ctx.lineWidth = 2.6;
      ctx.beginPath();
      let hasBinPoint = false;
      for (let i = 0; i < folded.binned_phase.length; i++) {
        const phase = folded.binned_phase[i];
        const value = folded.binned_flux[i];
        if (phase < xMin || phase > xMax) continue;
        const x = xScale(phase);
        const y = yScale(value);
        if (!hasBinPoint) {
          ctx.moveTo(x, y);
          hasBinPoint = true;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
      ctx.restore();

      ctx.fillStyle = '#202124';
      ctx.font = '700 12px system-ui, sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText('Folded flux', 14, 16);
      ctx.textAlign = 'right';
      ctx.fillText('Phase days from transit center', width - 22, height - 22);
      updateCanvasCursor(lastPointer);
    }

    function drawChart() {
      resizeCanvas();
      const geo = getChartGeometry();
      const width = geo.width;
      const height = geo.height;
      ctx.clearRect(0, 0, width, height);
      if (!currentResult) return;

      if (currentView === 'phase') {
        drawPhaseChart(geo);
        return;
      }

      const times = currentResult.plot.time;
      const rawFlux = currentResult.plot.raw_flux;
      const smoothFlux = currentResult.plot.smooth_flux;
      const flux = currentView === 'raw' ? rawFlux : smoothFlux;
      if (!times.length) return;

      const pad = geo.pad;
      const innerW = geo.innerW;
      const innerH = geo.innerH;
      const viewport = getViewport();
      const xMin = viewport.xMin;
      const xMax = viewport.xMax;
      const yMin = viewport.yMin;
      const yMax = viewport.yMax;
      const xScale = value => pad.left + ((value - xMin) / (xMax - xMin || 1)) * innerW;
      const yScale = value => pad.top + (1 - ((value - yMin) / (yMax - yMin || 1))) * innerH;

      ctx.fillStyle = '#fbfcfd';
      ctx.fillRect(0, 0, width, height);
      transitBoxCache = [];

      currentResult.transits.forEach((t, index) => {
        if (t.end < xMin || t.start > xMax) return;
        const range = transitFluxRange(t, flux);
        if (!range) return;
        const x1 = Math.max(pad.left, xScale(t.start));
        const x2 = Math.min(width - pad.right, xScale(t.end));
        const y1 = Math.max(pad.top, Math.min(pad.top + innerH, yScale(range.high)));
        const y2 = Math.max(pad.top, Math.min(pad.top + innerH, yScale(range.low)));
        const boxWidth = Math.max(8, x2 - x1);
        const boxTop = Math.min(y1, y2);
        const boxHeight = Math.max(8, Math.abs(y2 - y1));
        transitBoxCache.push({
          index,
          x1,
          x2: x1 + boxWidth,
          y1: boxTop,
          y2: boxTop + boxHeight,
        });
        ctx.fillStyle = 'rgba(180, 83, 9, 0.22)';
        ctx.fillRect(x1, boxTop, boxWidth, boxHeight);
        const selected = index === selectedTransitIndex;
        ctx.strokeStyle = selected ? 'rgba(15, 118, 110, 1)' : 'rgba(180, 83, 9, 1)';
        ctx.lineWidth = selected ? 3.2 : 2.5;
        ctx.strokeRect(x1, boxTop, boxWidth, boxHeight);
        if (selected && canEditBoxes()) {
          ctx.fillStyle = 'rgba(15, 118, 110, 0.95)';
          ctx.fillRect(x1 - 3, boxTop, 6, boxHeight);
          ctx.fillRect(x1 + boxWidth - 3, boxTop, 6, boxHeight);
        }
        ctx.fillStyle = '#8a3f06';
        ctx.font = '700 12px system-ui, sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        if (boxWidth > 18 || currentView === 'zoom') {
          ctx.fillText(`T${index + 1}`, Math.max(pad.left + 4, x1 + 5), Math.max(pad.top + 4, boxTop + 5));
        }
      });

      ctx.strokeStyle = '#d6dde5';
      ctx.lineWidth = 1;
      ctx.fillStyle = '#5f6874';
      ctx.font = '12px system-ui, sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';

      for (let i = 0; i <= 5; i++) {
        const y = pad.top + (innerH * i / 5);
        const value = yMax - ((yMax - yMin) * i / 5);
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(width - pad.right, y);
        ctx.stroke();
        ctx.fillText(fmt(value, 4), pad.left - 8, y);
      }

      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      for (let i = 0; i <= 6; i++) {
        const x = pad.left + (innerW * i / 6);
        const value = xMin + ((xMax - xMin) * i / 6);
        ctx.beginPath();
        ctx.moveTo(x, pad.top + innerH);
        ctx.lineTo(x, pad.top + innerH + 5);
        ctx.stroke();
        ctx.fillText(fmt(value, 4), x, pad.top + innerH + 10);
      }

      if (currentView !== 'raw') {
        ctx.strokeStyle = 'rgba(15, 118, 110, 0.16)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        let hasRawPoint = false;
        for (let i = 0; i < times.length; i++) {
          if (times[i] < xMin || times[i] > xMax) continue;
          const x = xScale(times[i]);
          const y = yScale(rawFlux[i]);
          if (!hasRawPoint) {
            ctx.moveTo(x, y);
            hasRawPoint = true;
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();
      }

      ctx.strokeStyle = currentView === 'raw' ? '#0f766e' : '#063f3b';
      ctx.lineWidth = currentView === 'raw' ? 1.2 : 2.4;
      ctx.beginPath();
      let hasPoint = false;
      for (let i = 0; i < times.length; i++) {
        if (times[i] < xMin || times[i] > xMax) continue;
        const x = xScale(times[i]);
        const y = yScale(flux[i]);
        if (!hasPoint) {
          ctx.moveTo(x, y);
          hasPoint = true;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();

      ctx.fillStyle = '#202124';
      ctx.font = '700 12px system-ui, sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText(currentView === 'raw' ? 'Flux' : 'Smoothed flux', 14, 16);
      ctx.textAlign = 'right';
      ctx.fillText('Julian days', width - 22, height - 22);
      updateCanvasCursor(lastPointer);
    }

    window.addEventListener('resize', drawChart);
  </script>
</body>
</html>
"""


def parse_csv_upload(file_item):
    raw = file_item.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("CSV is too large for this local tool.")

    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("The CSV does not have a header row.")

    column_map = {name.strip().lower(): name for name in reader.fieldnames if name}
    if "time" not in column_map or "flux" not in column_map:
        raise ValueError('The CSV must contain columns named "Time" and "Flux".')

    times = []
    fluxes = []
    for row in reader:
        try:
            t = float(row[column_map["time"]])
            f = float(row[column_map["flux"]])
        except (TypeError, ValueError):
            continue
        if math.isfinite(t) and math.isfinite(f):
            times.append(t)
            fluxes.append(f)

    if len(times) < 20:
        raise ValueError("Need at least 20 numeric rows to analyze a light curve.")

    time = np.asarray(times, dtype=float)
    flux = np.asarray(fluxes, dtype=float)
    order = np.argsort(time)
    return time[order], flux[order]


def clamp(value, low, high):
    return max(low, min(high, value))


def field_value(form, name):
    if name not in form:
        return None
    item = form[name]
    if isinstance(item, list):
        item = item[0]
    return getattr(item, "value", None)


def parse_optional_float(form, name, low=None, high=None):
    raw_value = field_value(form, name)
    if raw_value is None or str(raw_value).strip() == "":
        return None
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number.")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    if low is not None and value < low:
        raise ValueError(f"{name} must be at least {low}.")
    if high is not None and value > high:
        raise ValueError(f"{name} must be at most {high}.")
    return value


def parse_detection_options(form):
    options = dict(DEFAULT_DETECTION_OPTIONS)
    strictness = parse_optional_float(form, "strictness", 0.2, 5.0)
    smoothing = parse_optional_float(form, "smoothing", 0.25, 4.0)
    if strictness is not None:
        options["strictness"] = clamp(strictness, 0.2, 5.0)
    if smoothing is not None:
        options["smoothing"] = clamp(smoothing, 0.25, 4.0)

    options["min_depth"] = parse_optional_float(form, "minDepth", 0.0, None)
    options["min_duration"] = parse_optional_float(form, "minDuration", 0.0, None)
    options["max_duration"] = parse_optional_float(form, "maxDuration", 0.0, None)
    options["min_period"] = parse_optional_float(form, "minPeriod", 0.0, None)
    options["max_period"] = parse_optional_float(form, "maxPeriod", 0.0, None)
    if (
        options["min_duration"] is not None
        and options["max_duration"] is not None
        and options["max_duration"] <= options["min_duration"]
    ):
        raise ValueError("maxDuration must be greater than minDuration.")
    if (
        options["min_period"] is not None
        and options["max_period"] is not None
        and options["max_period"] <= options["min_period"]
    ):
        raise ValueError("maxPeriod must be greater than minPeriod.")
    return options


def odd_window_width(base_width, scale, minimum, maximum):
    width = int(round(base_width * scale))
    width = int(clamp(width, minimum, maximum))
    if width % 2 == 0:
        width += 1
    return int(min(width, maximum if maximum % 2 == 1 else maximum - 1))


def moving_average(values, width):
    if width <= 1:
        return values.copy()
    kernel = np.ones(width, dtype=float) / width
    padded = np.pad(values, (width // 2, width - 1 - width // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def contiguous_regions(mask):
    if not np.any(mask):
        return []
    edges = np.diff(mask.astype(np.int8))
    starts = np.where(edges == 1)[0] + 1
    ends = np.where(edges == -1)[0] + 1
    if mask[0]:
        starts = np.r_[0, starts]
    if mask[-1]:
        ends = np.r_[ends, mask.size]
    return list(zip(starts.tolist(), ends.tolist()))


def merge_regions(regions, max_gap):
    if not regions:
        return []
    merged = [regions[0]]
    for start, end in regions[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= max_gap:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return merged


def estimate_period(centers):
    if len(centers) < 2:
        return None, None, 0
    centers = np.asarray(sorted(centers), dtype=float)
    gaps = np.diff(centers)
    if gaps.size == 0:
        return None, None, 0

    period = float(np.mean(gaps))
    scatter = float(np.std(gaps)) if gaps.size > 1 else 0.0
    return period, scatter, int(len(centers))


def estimate_period_from_candidates(transits, time_span):
    centers = np.asarray([item["center"] for item in transits], dtype=float)
    return estimate_period(centers)


def chi_squared_transit_probability(time, flattened_flux, period, duration, transit_time):
    if chi2 is None or period <= 0 or duration <= 0:
        return None

    phase = ((time - transit_time + period / 2.0) % period) - period / 2.0
    in_transit = np.abs(phase) <= duration / 2.0
    if np.count_nonzero(in_transit) < 3 or np.count_nonzero(~in_transit) < 3:
        return None

    y = np.asarray(flattened_flux, dtype=float)
    baseline = float(np.mean(y))
    flat_residuals = y - baseline
    flat_mad = float(np.median(np.abs(flat_residuals - np.median(flat_residuals))))
    sigma = max(1.4826 * flat_mad, float(np.std(flat_residuals)), 1e-9)

    in_level = float(np.mean(y[in_transit]))
    out_level = float(np.mean(y[~in_transit]))
    if in_level >= out_level:
        return None

    box_model = np.where(in_transit, in_level, out_level)
    chi2_flat = float(np.sum(((y - baseline) / sigma) ** 2))
    chi2_box = float(np.sum(((y - box_model) / sigma) ** 2))
    delta_chi2 = max(0.0, chi2_flat - chi2_box)
    p_value = float(chi2.sf(delta_chi2, 1))
    if not math.isfinite(p_value):
        p_value = 0.0

    return {
        "chi_squared_flat": chi2_flat,
        "chi_squared_box": chi2_box,
        "reduced_chi_squared_box": chi2_box / max(len(y) - 2, 1),
        "delta_chi_squared": delta_chi2,
        "p_value": p_value,
    }


def period_search_bounds(cadence, full_span, options=None):
    auto_min_period = max(cadence * 20.0, 2.0, full_span / 30.0)
    auto_max_period = max(auto_min_period * 1.5, full_span / 3.0)
    min_period = auto_min_period
    max_period = auto_max_period
    if options:
        if options.get("min_period") is not None:
            min_period = max(cadence * 2.0, float(options["min_period"]))
        if options.get("max_period") is not None:
            max_period = min(full_span * 0.95, float(options["max_period"]))
    return min_period, max_period


def duration_search_bounds(cadence, full_span, options=None):
    auto_min_duration = max(cadence * 4.0, 0.3)
    auto_max_duration = min(30.0, max(auto_min_duration * 2.0, full_span / 8.0))
    min_duration = auto_min_duration
    max_duration = auto_max_duration
    if options:
        if options.get("min_duration") is not None:
            min_duration = max(cadence * 2.0, float(options["min_duration"]))
        if options.get("max_duration") is not None:
            max_duration = min(full_span * 0.25, float(options["max_duration"]))
    return min_duration, max_duration


def estimate_period_with_binned_bls(time, flux, options=None):
    if len(time) < 50:
        return None

    cadence = float(np.median(np.diff(time))) if len(time) > 1 else 1.0
    full_span = float(time[-1] - time[0]) if len(time) > 1 else 0.0
    if full_span <= 0:
        return None

    clipped_low, clipped_high = robust_flux_limits(flux, sigma=3.0)
    clipped_flux = np.clip(flux, clipped_low, clipped_high)
    trend_days = min(10.0, max(2.0, full_span / 6.0))
    trend_width = max(5, int(trend_days / max(cadence, 1e-9)))
    if trend_width % 2 == 0:
        trend_width += 1
    trend = moving_average(clipped_flux, trend_width)
    flattened_flux = clipped_flux - trend
    flattened_flux = flattened_flux - np.median(flattened_flux)
    residual_median = float(np.median(flattened_flux))
    residual_mad = float(np.median(np.abs(flattened_flux - residual_median)))
    sigma = max(1.4826 * residual_mad, float(np.std(flattened_flux)), 1e-9)

    min_period, max_period = period_search_bounds(cadence, full_span, options)
    min_duration, max_duration = duration_search_bounds(cadence, full_span, options)
    if min_period >= max_period or min_duration >= max_duration:
        return None

    periods = np.linspace(min_period, max_period, 900)
    durations = np.linspace(min_duration, max_duration, 10)
    bin_count = 360
    best = None
    powers = []
    reference_time = float(time[0])

    for period in periods:
        phase = ((time - reference_time) % period) / period
        bin_ids = np.minimum((phase * bin_count).astype(int), bin_count - 1)
        sums = np.bincount(bin_ids, weights=flattened_flux, minlength=bin_count)
        counts = np.bincount(bin_ids, minlength=bin_count)
        doubled_sums = np.r_[sums, sums]
        doubled_counts = np.r_[counts, counts]
        sum_prefix = np.r_[0.0, np.cumsum(doubled_sums)]
        count_prefix = np.r_[0.0, np.cumsum(doubled_counts)]
        period_best_power = -math.inf

        for duration in durations:
            window = max(1, int(round((duration / period) * bin_count)))
            if window >= bin_count // 2:
                continue

            window_sums = sum_prefix[window:window + bin_count] - sum_prefix[:bin_count]
            window_counts = count_prefix[window:window + bin_count] - count_prefix[:bin_count]
            valid = window_counts > 2
            if not np.any(valid):
                continue

            means = np.where(valid, window_sums / np.maximum(window_counts, 1), np.inf)
            bin_index = int(np.argmin(means))
            depth = -float(means[bin_index])
            if depth <= 0:
                continue

            power = depth / sigma * math.sqrt(max(float(window_counts[bin_index]), 1.0))
            period_best_power = max(period_best_power, power)
            if best is None or power > best["power"]:
                transit_time = reference_time + ((bin_index + window / 2.0) / bin_count) * period
                best = {
                    "period": float(period),
                    "duration": float(duration),
                    "transit_time": float(transit_time),
                    "power": float(power),
                }

        powers.append(period_best_power if math.isfinite(period_best_power) else 0.0)

    if best is None:
        return None

    powers = np.asarray(powers, dtype=float)
    finite_powers = powers[np.isfinite(powers)]
    if finite_powers.size >= 5:
        power_median = float(np.median(finite_powers))
        power_std = max(float(np.std(finite_powers)), 1e-9)
        sde = (best["power"] - power_median) / power_std
    else:
        sde = None

    candidate_indices = np.argsort(powers)[-8:][::-1]
    candidates = []
    for index in candidate_indices:
        power = float(powers[index])
        if not math.isfinite(power) or power <= 0:
            continue
        candidates.append({
            "period": float(periods[index]),
            "power": power,
            "sde": None if sde is None else float((power - power_median) / power_std),
        })

    first_epoch = math.ceil((time[0] - best["transit_time"]) / best["period"])
    last_epoch = math.floor((time[-1] - best["transit_time"]) / best["period"])
    expected_count = max(1, int(last_epoch - first_epoch + 1))
    chi_squared = chi_squared_transit_probability(
        time,
        flattened_flux,
        best["period"],
        best["duration"],
        best["transit_time"],
    )
    return {
        "period": best["period"],
        "scatter": 0.0,
        "count": expected_count,
        "duration": best["duration"],
        "transit_time": best["transit_time"],
        "power": best["power"],
        "sde": sde,
        "candidates": candidates,
        "search_min_period": float(min_period),
        "search_max_period": float(max_period),
        "search_min_duration": float(min_duration),
        "search_max_duration": float(max_duration),
        "method": "binned BLS fallback",
        **(chi_squared or {}),
    }


def estimate_period_with_bls(time, flux, options=None):
    if BoxLeastSquares is None or len(time) < 50:
        return estimate_period_with_binned_bls(time, flux, options)

    cadence = float(np.median(np.diff(time))) if len(time) > 1 else 1.0
    full_span = float(time[-1] - time[0]) if len(time) > 1 else 0.0
    if full_span <= 0:
        return None

    clipped_low, clipped_high = robust_flux_limits(flux, sigma=3.0)
    clipped_flux = np.clip(flux, clipped_low, clipped_high)

    trend_days = min(10.0, max(2.0, full_span / 6.0))
    trend_width = max(5, int(trend_days / max(cadence, 1e-9)))
    if trend_width % 2 == 0:
        trend_width += 1
    trend = moving_average(clipped_flux, trend_width)
    flattened_flux = clipped_flux - trend
    flattened_flux = flattened_flux - np.median(flattened_flux)

    min_period, max_period = period_search_bounds(cadence, full_span, options)
    min_duration, max_duration = duration_search_bounds(cadence, full_span, options)
    if min_period >= max_period or min_duration >= max_duration:
        return None

    periods = np.linspace(min_period, max_period, 1800)
    durations = np.linspace(min_duration, max_duration, 12)
    try:
        model = BoxLeastSquares(time, flattened_flux)
        result = model.power(periods, durations)
    except Exception:
        return None

    if len(result.power) == 0 or not np.any(np.isfinite(result.power)):
        return None

    best_index = int(np.nanargmax(result.power))
    period = float(result.period[best_index])
    duration = float(result.duration[best_index])
    transit_time = float(result.transit_time[best_index])
    power = float(result.power[best_index])
    if not math.isfinite(period) or period <= 0:
        return None

    first_epoch = math.ceil((time[0] - transit_time) / period)
    last_epoch = math.floor((time[-1] - transit_time) / period)
    expected_count = max(1, int(last_epoch - first_epoch + 1))
    chi_squared = chi_squared_transit_probability(time, flattened_flux, period, duration, transit_time)
    order = np.argsort(result.power)[-8:][::-1]
    candidates = []
    power_median = float(np.nanmedian(result.power))
    power_std = max(float(np.nanstd(result.power)), 1e-9)
    for index in order:
        if not math.isfinite(float(result.power[index])):
            continue
        power_value = float(result.power[index])
        candidates.append({
            "period": float(result.period[index]),
            "power": power_value,
            "sde": (power_value - power_median) / power_std,
        })

    return {
        "period": period,
        "scatter": 0.0,
        "count": expected_count,
        "duration": duration,
        "transit_time": transit_time,
        "power": power,
        "sde": (power - power_median) / power_std,
        "candidates": candidates,
        "search_min_period": float(min_period),
        "search_max_period": float(max_period),
        "search_min_duration": float(min_duration),
        "search_max_duration": float(max_duration),
        "method": "BLS",
        **(chi_squared or {}),
    }


def time_at_fractional_index(time, index_position):
    if index_position <= 0:
        return float(time[0])
    if index_position >= len(time) - 1:
        return float(time[-1])
    left = int(math.floor(index_position))
    right = int(math.ceil(index_position))
    if left == right:
        return float(time[left])
    fraction = index_position - left
    return float(time[left] + (time[right] - time[left]) * fraction)


def prune_overlapping_transits(transits):
    if not transits:
        return []

    kept = []
    for candidate in sorted(transits, key=lambda item: item["center"]):
        if not kept:
            kept.append(candidate)
            continue

        previous = kept[-1]
        overlap = min(previous["end"], candidate["end"]) - max(previous["start"], candidate["start"])
        shorter = max(min(previous["duration"], candidate["duration"]), 1e-9)
        if overlap > 0 and overlap / shorter > 0.78:
            if candidate["depth"] > previous["depth"]:
                kept[-1] = candidate
            continue
        kept.append(candidate)
    return kept


def detect_transits_by_prominence(time, flux, median_flux, options):
    if find_peaks is None:
        return None

    clipped_low, clipped_high = robust_flux_limits(flux, sigma=3.0)
    clipped_flux = np.clip(flux, clipped_low, clipped_high)

    strictness = float(options["strictness"])
    smoothing = float(options["smoothing"])
    base_smooth_width = int(max(31, min(201, len(clipped_flux) // 360)))
    smooth_width = odd_window_width(base_smooth_width, smoothing, 7, 501)
    smoothed = moving_average(clipped_flux, smooth_width)

    baseline = float(np.median(smoothed))
    mad = float(np.median(np.abs(smoothed - baseline)))
    robust_noise = max(1.4826 * mad, 1e-9)
    cadence = float(np.median(np.diff(time))) if len(time) > 1 else 1.0
    full_span = float(time[-1] - time[0]) if len(time) > 1 else 0.0

    auto_min_width_time = max(cadence * 4.0, min(0.5, full_span / 1000.0))
    auto_max_curve_time = max(auto_min_width_time * 4.0, min(36.0, max(1.0, full_span * 0.12)))
    min_width_time = (
        max(cadence * 2.0, float(options["min_duration"]))
        if options["min_duration"] is not None
        else auto_min_width_time
    )
    max_curve_time = (
        max(min_width_time * 1.2, float(options["max_duration"]))
        if options["max_duration"] is not None
        else auto_max_curve_time
    )
    max_curve_points = max(4, int(max_curve_time / cadence))
    min_distance_time = max(min_width_time * 2.5, min(4.0, full_span / 350.0))
    min_distance_points = max(smooth_width // 2, int(min_distance_time / cadence))
    auto_min_prominence = max(2.2 * robust_noise, abs(median_flux) * 0.002) * strictness
    min_prominence = (
        float(options["min_depth"])
        if options["min_depth"] is not None
        else auto_min_prominence
    )

    peaks, properties = find_peaks(
        -smoothed,
        prominence=min_prominence,
        distance=min_distance_points,
        wlen=max_curve_points * 2,
    )

    if len(peaks) == 0:
        return {
            "transits": [],
            "robust_noise": robust_noise,
            "smooth_points": smooth_width,
        }

    transits = []
    peak_indexes = np.asarray(sorted(peaks.tolist()), dtype=int)
    prominence_by_index = {
        int(peak_index): float(properties["prominences"][offset])
        for offset, peak_index in enumerate(peaks)
    }

    for offset, center_index in enumerate(peak_indexes):
        previous_center = peak_indexes[offset - 1] if offset > 0 else None
        next_center = peak_indexes[offset + 1] if offset + 1 < len(peak_indexes) else None

        left_cap = max(0, center_index - max_curve_points)
        right_cap = min(len(smoothed) - 1, center_index + max_curve_points)
        if previous_center is not None:
            left_cap = max(left_cap, int((previous_center + center_index) // 2))
        if next_center is not None:
            right_cap = min(right_cap, int((center_index + next_center) // 2))
        if left_cap >= center_index or right_cap <= center_index:
            continue

        left_index = left_cap + int(np.argmax(smoothed[left_cap:center_index + 1]))
        right_index = center_index + int(np.argmax(smoothed[center_index:right_cap + 1]))
        if left_index >= center_index or right_index <= center_index:
            continue

        duration = float(time[right_index] - time[left_index])
        if duration < min_width_time or duration > max_curve_time:
            continue

        left_shoulder = float(smoothed[left_index])
        right_shoulder = float(smoothed[right_index])
        trough = float(smoothed[center_index])
        depth = min(left_shoulder, right_shoulder) - trough
        if depth < min_prominence:
            continue

        box_level = trough + depth * 0.85
        box_left = center_index
        while box_left > left_index and smoothed[box_left] < box_level:
            box_left -= 1
        box_right = center_index
        while box_right < right_index and smoothed[box_right] < box_level:
            box_right += 1

        left_index = box_left
        right_index = box_right
        duration = float(time[right_index] - time[left_index])
        if duration < min_width_time or duration > max_curve_time:
            continue

        segment = smoothed[left_index:right_index + 1]
        if segment.size < 3:
            continue

        shape_prominence = max(robust_noise * 0.8 * strictness, depth * 0.28)
        inner_distance = max(3, smooth_width // 3)
        inner_peaks, _ = find_peaks(segment, prominence=shape_prominence, distance=inner_distance)
        inner_troughs, _ = find_peaks(-segment, prominence=shape_prominence, distance=inner_distance)
        center_relative = center_index - left_index
        extra_troughs = [
            trough_index
            for trough_index in inner_troughs
            if abs(int(trough_index) - center_relative) > inner_distance
        ]
        if len(inner_peaks) > 1 or len(extra_troughs) > 1:
            continue

        flux_min = float(np.min(segment))
        flux_max = float(np.max(segment))
        transits.append({
            "start": float(time[left_index]),
            "end": float(time[right_index]),
            "center": float(time[center_index]),
            "duration": float(duration),
            "depth": max(float(depth), prominence_by_index.get(int(center_index), float(depth))),
            "points": int(right_index - left_index + 1),
            "flux_min": flux_min,
            "flux_max": flux_max,
        })

    return {
        "transits": prune_overlapping_transits(transits),
        "robust_noise": robust_noise,
        "smooth_points": smooth_width,
    }


def detect_transits_by_threshold(time, flux, median_flux, options):
    clipped_low, clipped_high = robust_flux_limits(flux, sigma=3.0)
    clipped_flux = np.clip(flux, clipped_low, clipped_high)

    strictness = float(options["strictness"])
    smoothing = float(options["smoothing"])
    base_smooth_width = int(max(31, min(101, len(clipped_flux) // 700)))
    smooth_width = odd_window_width(base_smooth_width, smoothing, 7, 501)
    smoothed = moving_average(clipped_flux, smooth_width)

    baseline = float(np.median(smoothed))
    mad = float(np.median(np.abs(smoothed - baseline)))
    robust_noise = max(1.4826 * mad, 1e-9)

    dip_sigma = 2.4 * strictness
    auto_min_depth = max(dip_sigma * robust_noise, abs(median_flux) * 0.002 * strictness)
    min_depth = (
        float(options["min_depth"])
        if options["min_depth"] is not None
        else auto_min_depth
    )
    dip_threshold = min_depth if options["min_depth"] is not None else dip_sigma * robust_noise
    candidate_mask = smoothed < (baseline - dip_threshold)
    regions = merge_regions(contiguous_regions(candidate_mask), max_gap=max(2, smooth_width // 2))

    transits = []
    cadence = float(np.median(np.diff(time))) if len(time) > 1 else 1.0
    full_span = float(time[-1] - time[0]) if len(time) > 1 else 0.0
    auto_min_points = max(5, smooth_width // 4)
    auto_max_points = max(smooth_width * 5, min(len(time), int(len(time) * 0.05)))
    min_points = (
        max(3, int(float(options["min_duration"]) / max(cadence, 1e-9)))
        if options["min_duration"] is not None
        else auto_min_points
    )
    max_points = (
        max(min_points + 1, int(float(options["max_duration"]) / max(cadence, 1e-9)))
        if options["max_duration"] is not None
        else auto_max_points
    )
    for start_index, end_index in regions:
        if end_index - start_index < min_points:
            continue
        if end_index - start_index > max_points:
            continue
        segment = smoothed[start_index:end_index]
        local_min = float(np.min(segment))
        depth = baseline - local_min
        if depth < min_depth:
            continue

        edge_level = baseline - max(robust_noise * 0.55, depth * 0.28)
        left = start_index
        while left > 0 and smoothed[left - 1] < edge_level:
            left -= 1
        right = end_index
        while right < len(smoothed) and smoothed[right] < edge_level:
            right += 1

        duration = float(time[right - 1] - time[left]) if right > left else 0.0
        if duration <= 0:
            continue
        if options["min_duration"] is not None and duration < float(options["min_duration"]):
            continue
        if options["max_duration"] is not None and duration > float(options["max_duration"]):
            continue
        if full_span > 0 and duration > 0.15 * full_span:
            continue

        center_index = left + int(np.argmin(smoothed[left:right]))
        box_segment = smoothed[left:right]
        transits.append({
            "start": float(time[left]),
            "end": float(time[right - 1]),
            "center": float(time[center_index]),
            "duration": duration,
            "depth": float(depth),
            "points": int(right - left),
            "flux_min": float(np.min(box_segment)),
            "flux_max": float(np.max(box_segment)),
        })

    return {
        "transits": prune_overlapping_transits(transits),
        "robust_noise": robust_noise,
        "smooth_points": smooth_width,
    }


def detect_transits(time, flux, options=None):
    if options is None:
        options = dict(DEFAULT_DETECTION_OPTIONS)
    median_flux = float(np.median(flux))
    detection = detect_transits_by_prominence(time, flux, median_flux, options)
    if detection is None:
        detection = detect_transits_by_threshold(time, flux, median_flux, options)

    transits = sorted(detection["transits"], key=lambda item: item["center"])
    full_span = float(time[-1] - time[0]) if len(time) > 1 else 0.0
    bls_period = estimate_period_with_bls(time, flux, options)
    p_value = None
    chi_squared_flat = None
    chi_squared_box = None
    reduced_chi_squared_box = None
    delta_chi_squared = None
    period_epoch = None
    period_duration = None
    period_sde = None
    period_candidates = []
    period_search = None
    if bls_period is not None:
        period = bls_period["period"]
        period_scatter = bls_period["scatter"]
        period_match_count = bls_period["count"]
        period_method = bls_period["method"]
        p_value = bls_period.get("p_value")
        chi_squared_flat = bls_period.get("chi_squared_flat")
        chi_squared_box = bls_period.get("chi_squared_box")
        reduced_chi_squared_box = bls_period.get("reduced_chi_squared_box")
        delta_chi_squared = bls_period.get("delta_chi_squared")
        period_epoch = bls_period.get("transit_time")
        period_duration = bls_period.get("duration")
        period_sde = bls_period.get("sde")
        period_candidates = bls_period.get("candidates", [])
        period_search = {
            "min_period": bls_period.get("search_min_period"),
            "max_period": bls_period.get("search_max_period"),
            "min_duration": bls_period.get("search_min_duration"),
            "max_duration": bls_period.get("search_max_duration"),
        }
    else:
        period, period_scatter, period_match_count = estimate_period_from_candidates(transits, full_span)
        period_method = "average gaps" if period is not None else None
        if period is not None and transits:
            period_epoch = float(transits[0]["center"])
            period_duration = float(np.median([item["duration"] for item in transits]))
    return {
        "transits": transits,
        "period": period,
        "period_scatter": period_scatter,
        "period_match_count": period_match_count,
        "period_method": period_method,
        "period_epoch": period_epoch,
        "period_duration": period_duration,
        "period_sde": period_sde,
        "period_candidates": period_candidates,
        "period_search": period_search,
        "p_value": p_value,
        "p_value_percent": None if p_value is None else p_value * 100.0,
        "chi_squared_flat": chi_squared_flat,
        "chi_squared_box": chi_squared_box,
        "reduced_chi_squared_box": reduced_chi_squared_box,
        "delta_chi_squared": delta_chi_squared,
        "median_flux": median_flux,
        "robust_noise": float(detection["robust_noise"]),
        "smooth_points": int(detection["smooth_points"]),
        "detection_options": options,
    }


def add_depth_metrics(transit, baseline_flux):
    depth = transit.get("depth")
    if (
        depth is None
        or not math.isfinite(float(depth))
        or float(depth) < 0
    ):
        transit["depth_fraction"] = None
        transit["depth_percent"] = None
        transit["depth_ppm"] = None
        transit["radius_ratio"] = None
        transit["depth_basis"] = None
        return transit

    normalized_fraction = None
    if (
        baseline_flux is not None
        and math.isfinite(float(baseline_flux))
        and float(baseline_flux) > 0
    ):
        normalized_fraction = float(depth) / float(baseline_flux)

    use_normalized_flux = normalized_fraction is not None and normalized_fraction <= 0.5
    depth_fraction = normalized_fraction if use_normalized_flux else float(depth) / 1000000.0
    transit["depth_fraction"] = depth_fraction
    transit["depth_percent"] = depth_fraction * 100.0
    transit["depth_ppm"] = depth_fraction * 1000000.0
    transit["radius_ratio"] = math.sqrt(depth_fraction)
    transit["depth_basis"] = "fractional flux" if use_normalized_flux else "ppm flux"
    return transit


def finite_values(values):
    return [float(value) for value in values if value is not None and math.isfinite(float(value))]


def median_or_none(values):
    clean = sorted(finite_values(values))
    if not clean:
        return None
    middle = len(clean) // 2
    if len(clean) % 2:
        return clean[middle]
    return (clean[middle - 1] + clean[middle]) / 2.0


def coefficient_of_variation(values):
    clean = finite_values(values)
    center = median_or_none(clean)
    if center is None or center <= 0 or len(clean) < 2:
        return None
    return float(np.std(np.asarray(clean, dtype=float)) / center)


def build_candidate_diagnostics(transits, detection):
    depths = finite_values([item.get("depth") for item in transits])
    radius_ratios = finite_values([item.get("radius_ratio") for item in transits])
    point_counts = finite_values([item.get("points") for item in transits])
    odd_depths = depths[0::2]
    even_depths = depths[1::2]
    odd_depth = median_or_none(odd_depths)
    even_depth = median_or_none(even_depths)
    depth_center = median_or_none(depths)
    robust_noise = detection.get("robust_noise")
    detection_snr = None
    if depth_center is not None and robust_noise is not None and math.isfinite(float(robust_noise)) and float(robust_noise) > 0:
        detection_snr = depth_center / float(robust_noise)

    odd_even_depth_mismatch = None
    if odd_depth is not None and even_depth is not None and max(odd_depth, even_depth) > 0:
        odd_even_depth_mismatch = abs(odd_depth - even_depth) / max(odd_depth, even_depth)

    diagnostics = {
        "detection_snr": detection_snr,
        "median_transit_points": median_or_none(point_counts),
        "depth_scatter_ratio": coefficient_of_variation(depths),
        "odd_depth": odd_depth,
        "even_depth": even_depth,
        "odd_even_depth_mismatch": odd_even_depth_mismatch,
        "max_radius_ratio": max(radius_ratios) if radius_ratios else None,
    }

    warnings = []
    if not transits:
        warnings.append({
            "severity": "caution",
            "title": "No transit candidates",
            "detail": "Try lowering strictness or checking the input columns and flux units.",
        })
    if 0 < len(transits) < 3:
        warnings.append({
            "severity": "caution",
            "title": "Few observed transits",
            "detail": "A single event or pair of events is harder to separate from systematics.",
        })
    if detection.get("period") is None:
        warnings.append({
            "severity": "caution",
            "title": "No stable period",
            "detail": "The app could not estimate a repeating orbital period.",
        })
    if detection.get("period_method") and detection.get("period_method") != "BLS":
        warnings.append({
            "severity": "info",
            "title": "Period is provisional",
            "detail": f"Period came from {detection.get('period_method')}, not a BLS peak.",
        })
    p_value = detection.get("p_value")
    if p_value is not None and math.isfinite(float(p_value)) and float(p_value) > 0.01:
        warnings.append({
            "severity": "caution",
            "title": "Weak model significance",
            "detail": "The box model is not much better than a flat light curve by the current chi-squared estimate.",
        })
    if detection_snr is not None and detection_snr < 7:
        warnings.append({
            "severity": "caution",
            "title": "Low depth SNR",
            "detail": f"Median transit depth is about {detection_snr:.2f}x the robust noise.",
        })
    if odd_even_depth_mismatch is not None and odd_even_depth_mismatch > 0.5 and len(odd_depths) >= 2 and len(even_depths) >= 2:
        warnings.append({
            "severity": "danger",
            "title": "Odd/even depth mismatch",
            "detail": "Alternating transit depths can indicate an eclipsing binary or blended source.",
        })
    if diagnostics["depth_scatter_ratio"] is not None and diagnostics["depth_scatter_ratio"] > 0.8 and len(depths) >= 4:
        warnings.append({
            "severity": "caution",
            "title": "Inconsistent transit depths",
            "detail": "Detected depths vary substantially across events.",
        })
    if diagnostics["max_radius_ratio"] is not None and diagnostics["max_radius_ratio"] > 0.2:
        warnings.append({
            "severity": "caution",
            "title": "Large radius ratio",
            "detail": "Rp/Rs above 0.2 is large for many planet candidates and deserves closer inspection.",
        })
    if diagnostics["median_transit_points"] is not None and diagnostics["median_transit_points"] < 4:
        warnings.append({
            "severity": "info",
            "title": "Sparse transit sampling",
            "detail": "Some events have very few points inside the detected box.",
        })

    return diagnostics, warnings


def robust_flux_limits(values, sigma=4.0):
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    noise = max(1.4826 * mad, 1e-9)
    low = median - sigma * noise
    high = median + sigma * noise
    pct_low, pct_high = np.percentile(values, [0.2, 99.8])
    return float(min(low, pct_low)), float(max(high, pct_high))


def domain_for(values, lower_percentile=0.5, upper_percentile=99.5):
    low, high = np.percentile(values, [lower_percentile, upper_percentile])
    padding = max((high - low) * 0.14, np.std(values) * 0.08, 1e-9)
    return float(low - padding), float(high + padding)


def downsample_indices(flux, max_points=MAX_PLOT_POINTS):
    n = len(flux)
    if n <= max_points:
        return np.arange(n, dtype=int)

    bucket_count = max_points // 2
    edges = np.linspace(0, n, bucket_count + 1, dtype=int)
    keep = []
    for start, end in zip(edges[:-1], edges[1:]):
        if end <= start:
            continue
        segment = flux[start:end]
        min_i = start + int(np.argmin(segment))
        max_i = start + int(np.argmax(segment))
        keep.extend([min_i, max_i])
    return np.asarray(sorted(set(keep)), dtype=int)


def downsample_for_plot(time, flux, smooth_flux, max_points=MAX_PLOT_POINTS):
    n = len(time)
    keep = downsample_indices(smooth_flux if n > max_points else flux, max_points)
    return time[keep], flux[keep], smooth_flux[keep]


def build_phase_folded_plot(time, raw_flux, smooth_flux, period, epoch, duration, max_points=MAX_PLOT_POINTS):
    if period is None or epoch is None:
        return None
    if not math.isfinite(period) or period <= 0 or not math.isfinite(epoch):
        return None

    phase = ((time - epoch + period / 2.0) % period) - period / 2.0
    order = np.argsort(phase)
    phase = phase[order]
    raw_flux = raw_flux[order]
    smooth_flux = smooth_flux[order]

    keep = downsample_indices(smooth_flux if len(phase) > max_points else raw_flux, max_points)
    point_phase = phase[keep]
    point_raw = raw_flux[keep]
    point_smooth = smooth_flux[keep]

    bin_count = int(max(60, min(280, len(phase) // 180)))
    edges = np.linspace(-period / 2.0, period / 2.0, bin_count + 1)
    bin_ids = np.digitize(phase, edges) - 1
    binned_phase = []
    binned_flux = []
    for bin_index in range(bin_count):
        mask = bin_ids == bin_index
        if not np.any(mask):
            continue
        binned_phase.append(float((edges[bin_index] + edges[bin_index + 1]) / 2.0))
        binned_flux.append(float(np.median(raw_flux[mask])))

    binned_phase = np.asarray(binned_phase, dtype=float)
    binned_flux = np.asarray(binned_flux, dtype=float)
    if binned_flux.size >= 7:
        binned_flux = moving_average(binned_flux, 5)

    if binned_flux.size >= 5:
        flux_min, flux_max = domain_for(binned_flux, 0.0, 100.0)
    else:
        flux_min, flux_max = domain_for(raw_flux, 0.5, 99.5)

    cadence = float(np.median(np.diff(time))) if len(time) > 1 else 1.0
    duration_value = float(duration) if duration is not None and math.isfinite(duration) and duration > 0 else None
    focus_half_width = max(period * 0.04, cadence * 30.0, 1.0)
    if duration_value is not None:
        focus_half_width = max(focus_half_width, duration_value * 4.0)
    focus_half_width = min(period / 2.0, focus_half_width)

    focus_mask = (binned_phase >= -focus_half_width) & (binned_phase <= focus_half_width)
    if np.count_nonzero(focus_mask) >= 5:
        focus_flux_min, focus_flux_max = domain_for(binned_flux[focus_mask], 0.0, 100.0)
    else:
        raw_focus_mask = (phase >= -focus_half_width) & (phase <= focus_half_width)
        focus_values = raw_flux[raw_focus_mask] if np.count_nonzero(raw_focus_mask) >= 2 else raw_flux
        focus_flux_min, focus_flux_max = domain_for(focus_values, 0.5, 99.5)

    return {
        "phase": point_phase.tolist(),
        "raw_flux": point_raw.tolist(),
        "smooth_flux": point_smooth.tolist(),
        "binned_phase": binned_phase.tolist(),
        "binned_flux": binned_flux.tolist(),
        "period": float(period),
        "epoch": float(epoch),
        "duration": duration_value,
        "domain": {
            "time_min": float(-period / 2.0),
            "time_max": float(period / 2.0),
            "flux_min": flux_min,
            "flux_max": flux_max,
        },
        "focus_domain": {
            "time_min": float(-focus_half_width),
            "time_max": float(focus_half_width),
            "flux_min": focus_flux_min,
            "flux_max": focus_flux_max,
        },
    }


def analyze(time, flux, options=None):
    if options is None:
        options = dict(DEFAULT_DETECTION_OPTIONS)
    detection = detect_transits(time, flux, options)
    time_reference = float(time[0])
    display_time = time - time_reference
    raw_low, raw_high = robust_flux_limits(flux, sigma=4.0)
    raw_clipped = np.clip(flux, raw_low, raw_high)

    base_smooth_width = int(max(25, min(251, len(flux) // 300)))
    smooth_width = odd_window_width(base_smooth_width, float(options["smoothing"]), 5, 601)
    smooth_flux = moving_average(raw_clipped, smooth_width)
    plot_time, plot_raw, plot_smooth = downsample_for_plot(display_time, raw_clipped, smooth_flux)
    raw_flux_min, raw_flux_max = domain_for(raw_clipped, 0.5, 99.5)
    clean_flux_min, clean_flux_max = domain_for(smooth_flux, 0.2, 99.8)
    phase_folded = build_phase_folded_plot(
        time,
        raw_clipped,
        smooth_flux,
        detection["period"],
        detection["period_epoch"],
        detection["period_duration"],
    )

    display_transits = []
    for transit in detection["transits"]:
        display_transit = dict(transit)
        add_depth_metrics(display_transit, detection["median_flux"])
        display_transit["start"] = float(transit["start"] - time_reference)
        display_transit["center"] = float(transit["center"] - time_reference)
        display_transit["end"] = float(transit["end"] - time_reference)
        display_transits.append(display_transit)
    diagnostics, warnings = build_candidate_diagnostics(display_transits, detection)

    zoom_domain = None
    if display_transits:
        first = display_transits[0]
        last = display_transits[-1]
        median_duration = float(np.median([item["duration"] for item in display_transits]))
        if len(display_transits) == 1:
            pad = max(first["duration"] * 2.8, (time[-1] - time[0]) * 0.015, 1.0)
        else:
            pad = max(median_duration * 3.0, (time[-1] - time[0]) * 0.02, 1.0)
        zoom_time_min = float(max(0.0, first["start"] - pad))
        zoom_time_max = float(min(display_time[-1], last["end"] + pad))
        zoom_mask = (display_time >= zoom_time_min) & (display_time <= zoom_time_max)
        zoom_flux_min, zoom_flux_max = domain_for(smooth_flux[zoom_mask], 0.0, 100.0)
        zoom_domain = {
            "time_min": zoom_time_min,
            "time_max": zoom_time_max,
            "flux_min": zoom_flux_min,
            "flux_max": zoom_flux_max,
        }

    return {
        "total_points": int(len(time)),
        "time_reference": time_reference,
        "time_unit": "Julian days since first observation",
        "plot": {
            "time": plot_time.tolist(),
            "raw_flux": plot_raw.tolist(),
            "smooth_flux": plot_smooth.tolist(),
        },
        "domain": {
            "time_min": 0.0,
            "time_max": float(display_time[-1]),
        },
        "raw_domain": {"flux_min": raw_flux_min, "flux_max": raw_flux_max},
        "clean_domain": {"flux_min": clean_flux_min, "flux_max": clean_flux_max},
        "zoom_domain": zoom_domain,
        "phase_folded": phase_folded,
        "plot_smooth_points": smooth_width,
        "diagnostics": diagnostics,
        "warnings": warnings,
        "detection_snr": diagnostics["detection_snr"],
        "odd_even_depth_mismatch": diagnostics["odd_even_depth_mismatch"],
        "depth_scatter_ratio": diagnostics["depth_scatter_ratio"],
        **{**detection, "transits": display_transits},
    }


class TransitRequestHandler(BaseHTTPRequestHandler):
    server_version = "TransitFinder/1.0"

    def do_GET(self):
        path = urlparse(self.path).path
        if path != "/":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(INDEX_HTML.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(INDEX_HTML.encode("utf-8"))

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/analyze":
            self.send_error(404)
            return

        try:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                    "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
                },
            )
            file_item = form["csv"] if "csv" in form else None
            if file_item is None or not getattr(file_item, "file", None):
                raise ValueError("No CSV file was uploaded.")
            time, flux = parse_csv_upload(file_item)
            options = parse_detection_options(form)
            payload = analyze(time, flux, options)
            self.write_json(payload, status=200)
        except Exception as exc:
            self.write_json({"error": str(exc)}, status=400)

    def write_json(self, payload, status=200):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


def main():
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(os.getcwd(), ".matplotlib-cache"))
    server = None
    for port in range(DEFAULT_PORT, DEFAULT_PORT + 11):
        try:
            server = ThreadingHTTPServer((HOST, port), TransitRequestHandler)
            break
        except OSError:
            continue
    if server is None:
        raise OSError(f"Could not bind to any port from {DEFAULT_PORT} to {DEFAULT_PORT + 10}.")

    print(f"Transit Finder running at http://{HOST}:{server.server_port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
