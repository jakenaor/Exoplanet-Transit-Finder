const fileInput = document.getElementById('fileInput');
const dropzone = document.getElementById('dropzone');
const analyzeButton = document.getElementById('analyzeButton');
const cancelAnalysisButton = document.getElementById('cancelAnalysisButton');
const statusEl = document.getElementById('status');
const analysisProgressEl = document.getElementById('analysisProgress');
const runStatusSection = document.getElementById('runStatusSection');
const assessmentEl = document.getElementById('assessment');
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
const searchModeInput = document.getElementById('searchModeInput');
const tlsOptionsEl = document.getElementById('tlsOptions');
const tlsTemplateInput = document.getElementById('tlsTemplateInput');
const stellarRadiusInput = document.getElementById('stellarRadiusInput');
const stellarMassInput = document.getElementById('stellarMassInput');
const limbDarkeningU1Input = document.getElementById('limbDarkeningU1Input');
const limbDarkeningU2Input = document.getElementById('limbDarkeningU2Input');
const tlsOversamplingInput = document.getElementById('tlsOversamplingInput');
const tlsMinTransitsInput = document.getElementById('tlsMinTransitsInput');
const tlsMinDepthPpmInput = document.getElementById('tlsMinDepthPpmInput');
const tlsThreadsInput = document.getElementById('tlsThreadsInput');
const tlsDurationGridStepInput = document.getElementById('tlsDurationGridStepInput');
const minDepthInput = document.getElementById('minDepthInput');
const minDurationInput = document.getElementById('minDurationInput');
const maxDurationInput = document.getElementById('maxDurationInput');
const minPeriodInput = document.getElementById('minPeriodInput');
const maxPeriodInput = document.getElementById('maxPeriodInput');
const resetDetectionButton = document.getElementById('resetDetectionButton');
const exportCsvButton = document.getElementById('exportCsvButton');
const exportPngButton = document.getElementById('exportPngButton');
const exportJsonButton = document.getElementById('exportJsonButton');
const exportAnalysisPdfButton = document.getElementById('exportAnalysisPdfButton');
const exportBatchPdfButton = document.getElementById('exportBatchPdfButton');
const resultSelect = document.getElementById('resultSelect');
const batchCount = document.getElementById('batchCount');
const batchPicker = document.getElementById('batchPicker');
const batchPickerButton = document.getElementById('batchPickerButton');
const batchPickerTitle = document.getElementById('batchPickerTitle');
const batchPickerMeta = document.getElementById('batchPickerMeta');
const batchPickerList = document.getElementById('batchPickerList');
const appShell = document.querySelector('main');
const MAX_BATCH_FILES = 100;
const JOB_POLL_INTERVAL_MS = 750;
const DEFAULT_SIDEBAR_WIDTH = 390;
const MIN_SIDEBAR_WIDTH = 320;
const MAX_SIDEBAR_WIDTH = 560;
let selectedFiles = [];
let selectedFile = null;
let batchResults = [];
let currentBatchIndex = -1;
let batchInProgress = false;
let activeAnalysisJobId = null;
let analysisCancelRequested = false;
let progressTimer = null;
let progressValues = [];
let progressElapsedStates = [];
let currentResult = null;
let currentView = 'zoom';
let currentViewport = null;
let dragState = null;
let boxDragState = null;
let lastPointer = null;
let selectedTransitIndex = null;
let editBoxesEnabled = false;
let transitBoxCache = [];
const chartPad = { left: 72, right: 48, top: 42, bottom: 66 };

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

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[character]));
}

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

function observationRangesForResult(result, fallbackDomain = null) {
  const segmentRanges = result?.normalization?.segment_time_ranges || [];
  const ranges = segmentRanges.map(segment => {
    const start = Number(segment.start_day ?? segment.start);
    const end = Number(segment.end_day ?? segment.end);
    if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
    return start <= end ? { start, end } : { start: end, end: start };
  }).filter(Boolean);
  if (ranges.length) return ranges;

  const domain = fallbackDomain || result?.domain;
  const start = Number(domain?.time_min);
  const end = Number(domain?.time_max);
  return Number.isFinite(start) && Number.isFinite(end)
    ? [{ start: Math.min(start, end), end: Math.max(start, end) }]
    : [];
}

function ephemerisCyclesInObservedRanges(period, epoch, tolerance, observedRanges) {
  const periodValue = Number(period);
  const epochValue = Number(epoch);
  const toleranceValue = Number(tolerance);
  if (
    !Number.isFinite(periodValue)
    || periodValue <= 0
    || !Number.isFinite(epochValue)
    || !Number.isFinite(toleranceValue)
  ) {
    return new Set();
  }

  const cycles = new Set();
  (observedRanges || []).forEach(range => {
    const start = Number(range.start);
    const end = Number(range.end);
    if (!Number.isFinite(start) || !Number.isFinite(end)) return;
    const firstCycle = Math.ceil((Math.min(start, end) - toleranceValue - epochValue) / periodValue);
    const lastCycle = Math.floor((Math.max(start, end) + toleranceValue - epochValue) / periodValue);
    if (lastCycle < firstCycle) return;
    for (let cycle = firstCycle; cycle <= lastCycle; cycle += 1) {
      cycles.add(cycle);
    }
  });
  return cycles;
}

function finishAccordionAnimation(section, body) {
  section.classList.remove('is-opening', 'is-closing');
  delete section.dataset.animating;
  body.style.height = '';
  body.style.opacity = '';
  body.style.transform = '';
  body.style.marginTop = '';
}

function animateAccordionOpen(section, body) {
  section.open = true;
  section.dataset.animating = 'true';
  section.classList.add('is-opening');
  section.classList.remove('is-closing');
  body.style.height = '0px';
  body.style.opacity = '0';
  body.style.transform = 'translateY(-4px)';
  body.style.marginTop = '0';
  body.offsetHeight;

  window.requestAnimationFrame(() => {
    body.style.height = `${body.scrollHeight}px`;
    body.style.opacity = '1';
    body.style.transform = 'translateY(0)';
    body.style.marginTop = '9px';
  });

  let complete = false;
  const finish = () => {
    if (complete) return;
    complete = true;
    body.removeEventListener('transitionend', onTransitionEnd);
    finishAccordionAnimation(section, body);
  };
  const onTransitionEnd = event => {
    if (event.target === body && event.propertyName === 'height') finish();
  };
  body.addEventListener('transitionend', onTransitionEnd);
  window.setTimeout(finish, 360);
}

function animateAccordionClose(section, body) {
  section.dataset.animating = 'true';
  section.classList.add('is-closing');
  section.classList.remove('is-opening');
  body.style.height = `${body.scrollHeight}px`;
  body.style.opacity = '1';
  body.style.transform = 'translateY(0)';
  body.style.marginTop = '9px';
  body.offsetHeight;

  window.requestAnimationFrame(() => {
    body.style.height = '0px';
    body.style.opacity = '0';
    body.style.transform = 'translateY(-4px)';
    body.style.marginTop = '0';
  });

  let complete = false;
  const finish = () => {
    if (complete) return;
    complete = true;
    body.removeEventListener('transitionend', onTransitionEnd);
    section.open = false;
    finishAccordionAnimation(section, body);
  };
  const onTransitionEnd = event => {
    if (event.target === body && event.propertyName === 'height') finish();
  };
  body.addEventListener('transitionend', onTransitionEnd);
  window.setTimeout(finish, 360);
}

function setupAccordions() {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  document.querySelectorAll('.accordion-section').forEach(section => {
    const summary = section.querySelector('summary');
    const body = section.querySelector('.accordion-body');
    if (!summary || !body) return;

    summary.addEventListener('click', event => {
      if (reducedMotion.matches) return;
      event.preventDefault();
      if (section.dataset.animating === 'true') return;
      if (section.open) {
        animateAccordionClose(section, body);
      } else {
        animateAccordionOpen(section, body);
      }
    });
  });
}

setupAccordions();

function openAccordionSection(section) {
  if (!section || section.open || section.dataset.animating === 'true') return;
  const body = section.querySelector('.accordion-body');
  if (!body || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    section.open = true;
    return;
  }
  animateAccordionOpen(section, body);
}

function showRunStatus() {
  openAccordionSection(runStatusSection);
}

function sidebarWidthForFiles(files) {
  const names = Array.from(files || [])
    .map(file => String(file.name || ''))
    .filter(Boolean);
  if (!names.length) return DEFAULT_SIDEBAR_WIDTH;

  const longestName = Math.max(...names.map(name => name.length));
  const longestSegment = Math.max(...names.flatMap(name => (
    name.split(/[\s._()-]+/).map(part => part.length)
  )));
  const widthForWrappedName = 255 + Math.min(longestName, 90) * 3.4;
  const widthForLongSegment = 250 + Math.min(longestSegment, 56) * 5.4;
  const preferredWidth = Math.max(DEFAULT_SIDEBAR_WIDTH, widthForWrappedName, widthForLongSegment);
  return Math.round(Math.max(MIN_SIDEBAR_WIDTH, Math.min(MAX_SIDEBAR_WIDTH, preferredWidth)));
}

function updateSidebarWidth(files = selectedFiles) {
  if (!appShell) return;
  if (!files || !files.length) {
    appShell.style.removeProperty('--sidebar-width');
    return;
  }
  appShell.style.setProperty('--sidebar-width', `${sidebarWidthForFiles(files)}px`);
}

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.className = isError ? 'status error' : 'status';
}

function clampProgress(value) {
  if (!Number.isFinite(Number(value))) return 0;
  return Math.max(0, Math.min(100, Number(value)));
}

function stopProgressTimer() {
  if (progressTimer !== null) {
    window.clearInterval(progressTimer);
    progressTimer = null;
  }
}

function renderProgressElapsed(index) {
  if (!analysisProgressEl) return;
  const row = analysisProgressEl.querySelector(`[data-progress-index="${index}"]`);
  const elapsedEl = row?.querySelector('[data-progress-elapsed]');
  const state = progressElapsedStates[index];
  if (!elapsedEl || !state) return;
  elapsedEl.hidden = !state.visible;
  if (!state.visible) return;
  const liveSeconds = state.seconds + (
    state.ticking ? Math.max(0, Date.now() - state.updatedAt) / 1000 : 0
  );
  elapsedEl.textContent = `Elapsed ${formatJobElapsed(liveSeconds)}`;
}

function startProgressTimer() {
  stopProgressTimer();
  progressTimer = window.setInterval(() => {
    progressElapsedStates.forEach((state, index) => {
      if (state?.visible) renderProgressElapsed(index);
    });
  }, 250);
}

function setProgressElapsed(index, seconds, ticking = true, visible = true) {
  progressElapsedStates[index] = {
    seconds: Math.max(0, Number(seconds) || 0),
    updatedAt: Date.now(),
    ticking,
    visible,
  };
  renderProgressElapsed(index);
}

function pauseProgressElapsed(index) {
  const state = progressElapsedStates[index];
  if (!state) return;
  const seconds = state.seconds + (
    state.ticking ? Math.max(0, Date.now() - state.updatedAt) / 1000 : 0
  );
  setProgressElapsed(index, seconds, false, state.visible);
}

function resetAnalysisProgress() {
  stopProgressTimer();
  progressValues = [];
  progressElapsedStates = [];
  if (analysisProgressEl) {
    analysisProgressEl.hidden = true;
    analysisProgressEl.innerHTML = '';
  }
}

function renderProgressRows(files) {
  stopProgressTimer();
  progressValues = files.map(() => 0);
  progressElapsedStates = files.map(() => ({
    seconds: 0,
    updatedAt: Date.now(),
    ticking: false,
    visible: false,
  }));
  if (!analysisProgressEl) return;
  updateSidebarWidth(files);
  analysisProgressEl.hidden = files.length === 0;
  analysisProgressEl.innerHTML = files.map((file, index) => `
    <div class="progress-item pending" data-progress-index="${index}">
      <div class="progress-header">
        <span title="${escapeHtml(file.name)}">${index + 1}. ${escapeHtml(file.name)}</span>
        <span data-progress-percent>Pending</span>
      </div>
      <div class="progress-elapsed" data-progress-elapsed hidden>Elapsed 0s</div>
      <div class="progress-track" role="progressbar" aria-label="Analysis progress for ${escapeHtml(file.name)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
        <div class="progress-fill"></div>
      </div>
    </div>
  `).join('');
  if (files.length) startProgressTimer();
  showRunStatus();
}

function setFileProgress(index, value, label, state = 'active') {
  if (!analysisProgressEl) return;
  showRunStatus();
  const row = analysisProgressEl.querySelector(`[data-progress-index="${index}"]`);
  if (!row) return;
  const progressValue = clampProgress(value);
  progressValues[index] = progressValue;
  row.className = `progress-item ${state}`;
  row.querySelector('[data-progress-percent]').textContent = label || `${Math.round(progressValue)}%`;
  row.querySelector('[role="progressbar"]').setAttribute('aria-valuenow', String(Math.round(progressValue)));
  row.querySelector('.progress-fill').style.width = `${progressValue}%`;
}

function beginFileProgress(index) {
  showRunStatus();
  setFileProgress(index, 8, 'Uploading', 'active');
  setProgressElapsed(index, 0, true, true);
}

function setIndeterminateFileProgress(index, label) {
  if (!analysisProgressEl) return;
  showRunStatus();
  const row = analysisProgressEl.querySelector(`[data-progress-index="${index}"]`);
  if (!row) return;
  row.className = 'progress-item active';
  row.querySelector('[data-progress-percent]').textContent = label;
  row.querySelector('[role="progressbar"]').removeAttribute('aria-valuenow');
  row.querySelector('.progress-fill').style.width = '100%';
}

function finishFileProgress(index, outcome = 'complete') {
  pauseProgressElapsed(index);
  const labels = { complete: 'Complete', failed: 'Failed', cancelled: 'Cancelled' };
  setFileProgress(index, outcome === 'cancelled' ? 0 : 100, labels[outcome] || 'Failed', outcome);
}

function batchResultDetail(item) {
  if (!item) {
    return {
      label: 'No file selected',
      meta: 'Run analysis to populate this list.',
      status: 'pending',
      score: null,
      transits: null,
    };
  }
  if (item.error) {
    const cancelled = item.error === 'Cancelled';
    return {
      label: cancelled ? 'Cancelled' : 'Failed',
      meta: item.error,
      status: cancelled ? 'cancelled' : 'failed',
      score: null,
      transits: null,
    };
  }
  const assessment = assessmentForResult(item.result);
  const transitCount = item.result.transits.length;
  return {
    label: assessment.shortLabel,
    meta: `${transitCount} transit${transitCount === 1 ? '' : 's'}`,
    status: assessment.status,
    score: assessment.candidateScore,
    transits: transitCount,
  };
}

function closeBatchPicker() {
  if (!batchPickerList || !batchPickerButton) return;
  batchPickerList.hidden = true;
  batchPickerButton.setAttribute('aria-expanded', 'false');
}

function toggleBatchPicker() {
  if (!batchPickerList || !batchPickerButton || batchPickerButton.disabled) return;
  const willOpen = batchPickerList.hidden;
  batchPickerList.hidden = !willOpen;
  batchPickerButton.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
}

function renderBatchPicker() {
  if (!batchPicker || !batchPickerButton || !batchPickerTitle || !batchPickerMeta || !batchPickerList) return;
  const successCount = batchResults.filter(item => item.result).length;
  const activeItem = currentBatchIndex >= 0 ? batchResults[currentBatchIndex] : null;
  const activeDetail = batchResultDetail(activeItem);
  const disabled = !batchResults.length || batchInProgress;

  batchPicker.hidden = false;
  batchPickerButton.disabled = disabled;
  batchPickerButton.className = `batch-picker-button ${activeDetail.status}`;
  batchPickerTitle.textContent = activeItem ? activeItem.file.name : (batchResults.length ? 'No successful file selected' : 'No processed files');
  batchPickerMeta.textContent = activeItem
    ? `${activeDetail.score === null ? 'No score' : `${activeDetail.score}/100 confidence`} · ${activeDetail.label} · ${activeDetail.meta}`
    : (batchResults.length && successCount === 0 ? 'All processed files failed.' : 'Run analysis to populate this list.');
  batchPickerList.hidden = batchPickerList.hidden || disabled;
  batchPickerButton.setAttribute('aria-expanded', batchPickerList.hidden ? 'false' : 'true');
  batchPickerList.innerHTML = batchResults.map((item, index) => {
    const selected = index === currentBatchIndex;
    const detail = batchResultDetail(item);
    const disabledAttribute = item.error ? ' disabled aria-disabled="true"' : '';
    const scoreHtml = detail.score === null
      ? ''
      : `<span class="batch-score ${detail.status}" aria-label="Planet confidence ${detail.score} out of 100">${detail.score}/100</span>`;
    return `
      <button
        class="batch-option ${detail.status}${selected ? ' selected' : ''}"
        type="button"
        role="option"
        aria-selected="${selected ? 'true' : 'false'}"
        data-batch-index="${index}"
        title="${escapeHtml(item.file.name)}"
        ${disabledAttribute}
      >
        <span class="batch-option-index">${index + 1}</span>
        <span class="batch-option-body">
          <span class="batch-option-name">${escapeHtml(item.file.name)}</span>
          <span class="batch-option-meta">
            ${scoreHtml}
            <span class="batch-badge ${detail.status}">${escapeHtml(detail.label)}</span>
            <span>${escapeHtml(detail.meta)}</span>
          </span>
        </span>
      </button>
    `;
  }).join('');
}

function renderBatchSelect() {
  const successCount = batchResults.filter(item => item.result).length;
  batchCount.value = `${successCount}/${batchResults.length || selectedFiles.length || 0}`;
  if (!batchResults.length) {
    resultSelect.disabled = true;
    resultSelect.innerHTML = '<option>No processed files</option>';
    renderBatchPicker();
    syncExportButtons();
    return;
  }

  resultSelect.disabled = batchInProgress || successCount === 0;
  resultSelect.innerHTML = batchResults.map((item, index) => {
    const selected = index === currentBatchIndex ? ' selected' : '';
    const disabled = item.error ? ' disabled' : '';
    const detail = item.error
      ? (item.error === 'Cancelled' ? 'cancelled' : 'failed')
      : `${assessmentForResult(item.result).shortLabel}; ${item.result.transits.length} transits`;
    return `<option value="${index}"${selected}${disabled}>${index + 1}. ${escapeHtml(item.file.name)} (${detail})</option>`;
  }).join('');
  renderBatchPicker();
  syncExportButtons();
}

function setFiles(fileList) {
  const files = Array.from(fileList || []);
  selectedFiles = files.slice(0, MAX_BATCH_FILES);
  updateSidebarWidth(selectedFiles);
  selectedFile = selectedFiles[0] || null;
  batchResults = [];
  currentBatchIndex = -1;
  resetAnalysisProgress();
  renderBatchSelect();
  clearResultView();
  analyzeButton.disabled = !selectedFiles.length;
  if (!selectedFiles.length) {
    setStatus('No file selected.');
  } else if (files.length > MAX_BATCH_FILES) {
    setStatus(`Selected first ${MAX_BATCH_FILES} of ${files.length} files.`);
  } else {
    setStatus(selectedFiles.length === 1
      ? selectedFiles[0].name
      : `${selectedFiles.length} files selected.`);
  }
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
    searchMode: searchModeInput.value,
    tlsTemplate: tlsTemplateInput.value,
    stellarRadius: optionalNumber(stellarRadiusInput),
    stellarMass: optionalNumber(stellarMassInput),
    limbDarkeningU1: optionalNumber(limbDarkeningU1Input),
    limbDarkeningU2: optionalNumber(limbDarkeningU2Input),
    tlsOversampling: optionalNumber(tlsOversamplingInput),
    tlsMinTransits: optionalNumber(tlsMinTransitsInput),
    tlsMinDepthPpm: optionalNumber(tlsMinDepthPpmInput),
    tlsThreads: optionalNumber(tlsThreadsInput),
    tlsDurationGridStep: optionalNumber(tlsDurationGridStepInput),
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
  const tlsMode = searchModeInput.value === 'tls';
  tlsOptionsEl.hidden = !tlsMode;
  [strictnessInput, minDepthInput, minDurationInput, maxDurationInput].forEach(input => {
    input.disabled = tlsMode;
  });
}

function resetDetectionControls() {
  strictnessInput.value = '1';
  smoothingInput.value = '1';
  searchModeInput.value = 'tls';
  tlsTemplateInput.value = 'default';
  stellarRadiusInput.value = '';
  stellarMassInput.value = '';
  limbDarkeningU1Input.value = '';
  limbDarkeningU2Input.value = '';
  tlsOversamplingInput.value = '3';
  tlsMinTransitsInput.value = '3';
  tlsMinDepthPpmInput.value = '10';
  tlsThreadsInput.value = '4';
  tlsDurationGridStepInput.value = '1.1';
  minDepthInput.value = '';
  minDurationInput.value = '';
  maxDurationInput.value = '';
  minPeriodInput.value = '';
  maxPeriodInput.value = '';
  updateDetectionReadouts();
}

function markDetectionControlsChanged() {
  if (currentResult && selectedFiles.length) {
    setStatus('Detection controls changed. Run Analyze files to apply.');
  }
}

function canEditBoxes() {
  return Boolean(currentResult && editBoxesEnabled && currentView !== 'phase' && currentView !== 'periodogram');
}

function syncEditButton() {
  editBoxesButton.disabled = !currentResult || currentView === 'phase' || currentView === 'periodogram';
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
  exportAnalysisPdfButton.disabled = disabled;
  exportBatchPdfButton.disabled = !batchResults.some(item => item.result);
}

function clearResultView() {
  currentResult = null;
  currentViewport = null;
  selectedTransitIndex = null;
  boxDragState = null;
  transitBoxCache = [];
  editBoxesEnabled = false;
  emptyEl.style.display = 'grid';
  assessmentEl.innerHTML = `
    <div class="assessment-card pending">
      <div class="assessment-head">
        <strong>No dataset analyzed</strong>
        <span>-</span>
      </div>
      <p>Candidate verdict appears after analysis.</p>
    </div>
  `;
  metricsEl.innerHTML = `
    <div class="metric"><span>Data points</span><span>-</span></div>
    <div class="metric"><span>Transits</span><span>-</span></div>
    <div class="metric"><span>Orbital period</span><span>-</span></div>
    <div class="metric"><span>Period uncertainty</span><span>-</span></div>
    <div class="metric"><span>Median depth</span><span>-</span></div>
    <div class="metric"><span>Radius ratio</span><span>-</span></div>
    <div class="metric"><span>Depth SNR</span><span>-</span></div>
    <div class="metric"><span>Period SDE</span><span>-</span></div>
    <div class="metric"><span>TLS false-alarm probability</span><span>-</span></div>
    <div class="metric"><span>Ephemeris fit</span><span>-</span></div>
    <div class="metric"><span>Chi-sq p-value</span><span>-</span></div>
    <div class="metric"><span>Reduced chi-sq</span><span>-</span></div>
    <div class="metric"><span>JD start</span><span>-</span></div>
    <div class="metric"><span>Median flux</span><span>-</span></div>
    <div class="metric"><span>Noise</span><span>-</span></div>
  `;
  periodCandidatesEl.innerHTML = `
    <div class="warning-item info">
      <strong>No candidates yet</strong>
      <span>Period search results appear after analysis.</span>
    </div>
  `;
  warningsEl.innerHTML = `
    <div class="warning-item info">
      <strong>No analysis yet</strong>
      <span>Candidate checks appear after upload.</span>
    </div>
  `;
  rowsEl.innerHTML = '<tr><td colspan="10" style="text-align:left;color:#60656f;">No transit candidates yet.</td></tr>';
  updateChartHeading();
  syncEditButton();
  syncExportButtons();
  drawChart();
}

function appendDetectionOptions(formData, options) {
  formData.append('strictness', options.strictness);
  formData.append('smoothing', options.smoothing);
  formData.append('searchMode', options.searchMode);
  formData.append('tlsTemplate', options.tlsTemplate);
  if (options.stellarRadius !== null) formData.append('stellarRadius', options.stellarRadius);
  if (options.stellarMass !== null) formData.append('stellarMass', options.stellarMass);
  if (options.limbDarkeningU1 !== null) formData.append('limbDarkeningU1', options.limbDarkeningU1);
  if (options.limbDarkeningU2 !== null) formData.append('limbDarkeningU2', options.limbDarkeningU2);
  if (options.tlsOversampling !== null) formData.append('tlsOversampling', options.tlsOversampling);
  if (options.tlsMinTransits !== null) formData.append('tlsMinTransits', options.tlsMinTransits);
  if (options.tlsMinDepthPpm !== null) formData.append('tlsMinDepthPpm', options.tlsMinDepthPpm);
  if (options.tlsThreads !== null) formData.append('tlsThreads', options.tlsThreads);
  if (options.tlsDurationGridStep !== null) formData.append('tlsDurationGridStep', options.tlsDurationGridStep);
  if (options.minDepth !== null) formData.append('minDepth', options.minDepth);
  if (options.minDuration !== null) formData.append('minDuration', options.minDuration);
  if (options.maxDuration !== null) formData.append('maxDuration', options.maxDuration);
  if (options.minPeriod !== null) formData.append('minPeriod', options.minPeriod);
  if (options.maxPeriod !== null) formData.append('maxPeriod', options.maxPeriod);
}

class AnalysisCancelledError extends Error {
  constructor(message = 'Analysis cancelled.') {
    super(message);
    this.name = 'AnalysisCancelledError';
  }
}

function wait(milliseconds) {
  return new Promise(resolve => window.setTimeout(resolve, milliseconds));
}

function formatJobElapsed(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  return minutes ? `${minutes}m ${remainder}s` : `${remainder}s`;
}

function updateProgressFromJob(index, job, searchMode) {
  const active = ['queued', 'running', 'cancelling'].includes(job.status);
  setProgressElapsed(index, job.elapsed_seconds, active, true);
  if (job.status === 'queued') {
    const position = Number(job.queue_position);
    const label = Number.isFinite(position) ? `Queued #${position}` : 'Queued';
    setFileProgress(index, 12, label, 'active');
    return;
  }
  const engine = searchMode === 'tls' ? 'TLS' : 'Analysis';
  if (job.status === 'cancelling') {
    setIndeterminateFileProgress(index, job.stage_label || 'Cancelling…');
  } else if (job.status === 'running') {
    setIndeterminateFileProgress(index, job.stage_label || `${engine} running`);
  }
}

async function readJsonResponse(response) {
  try {
    return await response.json();
  } catch (error) {
    throw new Error(`Server returned an unreadable response (${response.status}).`);
  }
}

async function requestJobCancellation(jobId) {
  if (!jobId) return;
  const response = await fetch(`/analysis-jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
  const payload = await readJsonResponse(response);
  if (!response.ok) throw new Error(payload.error || 'Could not cancel the analysis.');
}

async function analyzeFile(file, options, onJobUpdate = () => {}) {
  const formData = new FormData();
  formData.append('datafile', file);
  appendDetectionOptions(formData, options);
  const response = await fetch('/analysis-jobs', { method: 'POST', body: formData });
  const submittedJob = await readJsonResponse(response);
  if (!response.ok) throw new Error(submittedJob.error || 'Analysis could not be started.');
  if (!submittedJob.job_id) throw new Error('Server did not return an analysis job ID.');

  const jobId = submittedJob.job_id;
  activeAnalysisJobId = jobId;
  cancelAnalysisButton.disabled = false;
  onJobUpdate(submittedJob);

  try {
    if (analysisCancelRequested) {
      await requestJobCancellation(jobId);
      throw new AnalysisCancelledError();
    }

    let failedPolls = 0;
    while (true) {
      let jobResponse;
      let job;
      try {
        jobResponse = await fetch(`/analysis-jobs/${encodeURIComponent(jobId)}`, { cache: 'no-store' });
        job = await readJsonResponse(jobResponse);
        if (!jobResponse.ok) throw new Error(job.error || 'Could not read analysis status.');
        failedPolls = 0;
      } catch (error) {
        failedPolls += 1;
        if (failedPolls >= 5) throw error;
        await wait(JOB_POLL_INTERVAL_MS);
        continue;
      }

      onJobUpdate(job);
      if (job.status === 'completed') {
        const payload = job.result;
        if (!payload) throw new Error('Completed analysis did not include a result.');
        payload.source_file = file.name;
        payload.original_period = payload.period;
        payload.original_period_method = payload.period_method;
        payload.boxesEdited = false;
        return payload;
      }
      if (job.status === 'failed') throw new Error(job.error || 'Analysis failed.');
      if (job.status === 'cancelled') throw new AnalysisCancelledError();
      if (analysisCancelRequested && job.status !== 'cancelling') {
        await requestJobCancellation(jobId);
        throw new AnalysisCancelledError();
      }
      await wait(JOB_POLL_INTERVAL_MS);
    }
  } finally {
    if (activeAnalysisJobId === jobId) activeAnalysisJobId = null;
  }
}

function selectBatchResult(index) {
  const item = batchResults[index];
  if (!item || !item.result) return;
  currentBatchIndex = index;
  selectedFile = item.file;
  currentResult = item.result;
  currentViewport = null;
  selectedTransitIndex = null;
  boxDragState = null;
  transitBoxCache = [];
  editBoxesEnabled = false;
  renderBatchSelect();
  renderResult(currentResult);
  setStatus(`Showing ${item.file.name}.`);
}

fileInput.addEventListener('change', () => setFiles(fileInput.files));
[strictnessInput, smoothingInput].forEach(input => {
  input.addEventListener('input', () => {
    updateDetectionReadouts();
    markDetectionControlsChanged();
  });
});
[minDepthInput, minDurationInput, maxDurationInput, minPeriodInput, maxPeriodInput].forEach(input => {
  input.addEventListener('change', markDetectionControlsChanged);
});
[
  tlsTemplateInput,
  stellarRadiusInput,
  stellarMassInput,
  limbDarkeningU1Input,
  limbDarkeningU2Input,
  tlsOversamplingInput,
  tlsMinTransitsInput,
  tlsMinDepthPpmInput,
  tlsThreadsInput,
  tlsDurationGridStepInput,
].forEach(input => input.addEventListener('change', markDetectionControlsChanged));
searchModeInput.addEventListener('change', () => {
  updateDetectionReadouts();
  markDetectionControlsChanged();
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
  if (event.dataTransfer.files.length) {
    fileInput.files = event.dataTransfer.files;
    setFiles(event.dataTransfer.files);
  }
});

cancelAnalysisButton.addEventListener('click', async () => {
  if (!batchInProgress || analysisCancelRequested) return;
  analysisCancelRequested = true;
  cancelAnalysisButton.disabled = true;
  setStatus('Cancelling the active analysis…');
  if (!activeAnalysisJobId) return;
  try {
    await requestJobCancellation(activeAnalysisJobId);
  } catch (error) {
    setStatus(error.message, true);
  }
});

analyzeButton.addEventListener('click', async () => {
  if (!selectedFiles.length) return;
  const filesToAnalyze = selectedFiles.slice(0, MAX_BATCH_FILES);
  const options = detectionOptions();
  setStatus(`Analyzing 1/${filesToAnalyze.length}: ${filesToAnalyze[0].name}`);
  renderProgressRows(filesToAnalyze);
  analyzeButton.disabled = true;
  batchInProgress = true;
  analysisCancelRequested = false;
  activeAnalysisJobId = null;
  cancelAnalysisButton.hidden = false;
  cancelAnalysisButton.disabled = false;
  batchResults = [];
  currentBatchIndex = -1;
  renderBatchSelect();
  clearResultView();
  try {
    let batchWasCancelled = false;
    for (let index = 0; index < filesToAnalyze.length; index++) {
      const file = filesToAnalyze[index];
      let fileSucceeded = false;
      setStatus(`Analyzing ${index + 1}/${filesToAnalyze.length}: ${file.name}`);
      beginFileProgress(index);
      try {
        const result = await analyzeFile(
          file,
          options,
          job => updateProgressFromJob(index, job, options.searchMode),
        );
        batchResults.push({ file, result, error: null });
        fileSucceeded = true;
        if (currentBatchIndex === -1) {
          selectBatchResult(batchResults.length - 1);
        } else {
          renderBatchSelect();
        }
      } catch (error) {
        if (error instanceof AnalysisCancelledError) {
          batchResults.push({ file, result: null, error: 'Cancelled' });
          finishFileProgress(index, 'cancelled');
          for (let pendingIndex = index + 1; pendingIndex < filesToAnalyze.length; pendingIndex++) {
            setFileProgress(pendingIndex, 0, 'Not started', 'cancelled');
          }
          batchWasCancelled = true;
          break;
        }
        batchResults.push({ file, result: null, error: error.message });
        renderBatchSelect();
      }
      finishFileProgress(index, fileSucceeded ? 'complete' : 'failed');
    }

    if (batchWasCancelled) {
      renderBatchSelect();
      setStatus('Analysis cancelled. The server is ready for another run.');
      return;
    }

    const successCount = batchResults.filter(item => item.result).length;
    const failureCount = batchResults.length - successCount;
    const assessments = batchResults
      .filter(item => item.result)
      .map(item => assessmentForResult(item.result));
    const signalCount = assessments.filter(assessment => (
      assessment.status === 'strong_candidate' || assessment.status === 'possible_candidate'
    )).length;
    const noSignalCount = assessments.filter(assessment => assessment.status === 'no_planet_like_signal').length;
    const verdictSummary = successCount
      ? ` ${signalCount} candidate-like, ${noSignalCount} no credible signal.`
      : '';
    if (successCount && currentBatchIndex === -1) {
      const firstSuccessIndex = batchResults.findIndex(item => item.result);
      selectBatchResult(firstSuccessIndex);
    }
    setStatus(
      failureCount
        ? `Batch complete: ${successCount}/${batchResults.length} processed, ${failureCount} failed.${verdictSummary}`
        : `Batch complete: ${successCount}/${batchResults.length} processed.${verdictSummary}`
    , failureCount > 0 && successCount === 0);
  } finally {
    stopProgressTimer();
    batchInProgress = false;
    activeAnalysisJobId = null;
    analysisCancelRequested = false;
    cancelAnalysisButton.hidden = true;
    cancelAnalysisButton.disabled = false;
    analyzeButton.disabled = !selectedFiles.length;
    renderBatchSelect();
  }
});

resultSelect.addEventListener('change', () => {
  selectBatchResult(Number(resultSelect.value));
});

if (batchPickerButton) {
  batchPickerButton.addEventListener('click', toggleBatchPicker);
}

if (batchPickerList) {
  batchPickerList.addEventListener('click', event => {
    const option = event.target.closest('[data-batch-index]');
    if (!option || option.disabled) return;
    closeBatchPicker();
    selectBatchResult(Number(option.dataset.batchIndex));
  });
}

document.addEventListener('click', event => {
  if (!batchPicker || batchPicker.hidden || batchPicker.contains(event.target)) return;
  closeBatchPicker();
});

document.addEventListener('keydown', event => {
  if (event.key === 'Escape') closeBatchPicker();
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

function hasTransitModel() {
  return Boolean(
    currentResult
    && currentResult.transit_model
    && Array.isArray(currentResult.transit_model.time)
    && currentResult.transit_model.time.length
  );
}

function periodogramSeries() {
  if (!currentResult || !currentResult.periodogram) return null;
  const payload = currentResult.periodogram;
  const periods = Array.isArray(payload.periods) ? payload.periods : [];
  const powers = Array.isArray(payload.power) ? payload.power : [];
  const sdes = Array.isArray(payload.sde) ? payload.sde : [];
  const hasSde = sdes.some(value => value !== null && value !== undefined && Number.isFinite(Number(value)));
  const points = periods.map((period, index) => {
    const x = Number(period);
    const power = Number(powers[index]);
    const sde = sdes[index] === null || sdes[index] === undefined ? NaN : Number(sdes[index]);
    const value = hasSde ? sde : power;
    return {
      period: x,
      value,
      power,
      sde,
    };
  }).filter(point => Number.isFinite(point.period) && point.period > 0 && Number.isFinite(point.value))
    .sort((a, b) => a.period - b.period);
  if (!points.length) return null;
  return {
    points,
    yLabel: hasSde ? 'SDE' : 'BLS power',
    valueKey: hasSde ? 'sde' : 'power',
    method: payload.method || currentResult.period_method || 'period search',
    fullCount: Number.isFinite(Number(payload.point_count)) ? Number(payload.point_count) : points.length,
    shownCount: Number.isFinite(Number(payload.shown_count)) ? Number(payload.shown_count) : points.length,
  };
}

function hasPeriodogram() {
  const series = periodogramSeries();
  return Boolean(series && series.points.length);
}

function domainForPeriodogram() {
  const series = periodogramSeries();
  if (!series) return null;
  const xValues = series.points.map(point => point.period);
  const yValues = series.points.map(point => point.value);
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMinRaw = Math.min(...yValues, 0);
  const yMaxRaw = Math.max(...yValues, 0);
  const xPad = Math.max((xMax - xMin) * 0.015, xMax * 0.001, 1e-6);
  const yPad = Math.max((yMaxRaw - yMinRaw) * 0.12, 0.5);
  return {
    xMin: Math.max(0, xMin - xPad),
    xMax: xMax + xPad,
    yMin: yMinRaw - yPad,
    yMax: yMaxRaw + yPad,
  };
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

  if (currentView === 'periodogram') {
    chartTitleEl.textContent = 'Periodogram';
    const series = periodogramSeries();
    if (series) {
      subtitleEl.textContent = `${series.shownCount.toLocaleString()} plotted periods from ${series.fullCount.toLocaleString()} searched. Higher ${series.yLabel} means a stronger repeating transit candidate.`;
    } else {
      subtitleEl.textContent = 'Periodogram data is not available for this run.';
    }
    return;
  }

  if (currentView === 'audit') {
    chartTitleEl.textContent = 'Ephemeris Audit';
    const metrics = currentAnalysisMetrics();
    if (!Number.isFinite(Number(metrics.period)) || !Number.isFinite(Number(metrics.periodEpoch))) {
      subtitleEl.textContent = 'Audit view needs a recovered period and epoch.';
    } else if (
      Number.isFinite(Number(metrics.ephemerisMatchCount))
      && Number.isFinite(Number(metrics.ephemerisMatchFraction))
    ) {
      const matchCount = Number(metrics.ephemerisMatchCount);
      const total = currentResult.transits.length;
      subtitleEl.textContent = `${matchCount}/${total} detected dips align with the ${fmt(metrics.period, 5)} day ephemeris. Green boxes match; red boxes are off-period.`;
    } else {
      subtitleEl.textContent = `Predicted windows are shown for the ${fmt(metrics.period, 5)} day ephemeris.`;
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

function ephemerisDiagnosticsForTransits(transits, period, epoch, duration, expectedCount, observedRanges = null) {
  const centers = transits
    .map(transit => Number(transit.center))
    .filter(value => Number.isFinite(value));
  const durations = transits
    .map(transit => Number(transit.duration))
    .filter(value => Number.isFinite(value) && value > 0);
  const periodValue = Number(period);
  const epochValue = Number(epoch);
  const durationValue = Number(duration);
  const expectedValue = Number(expectedCount);
  const empty = {
    ephemerisMatchCount: null,
    ephemerisMatchFraction: null,
    ephemerisEventMatchCount: null,
    ephemerisEventMatchFraction: null,
    offEphemerisTransitCount: null,
    offEphemerisFraction: null,
    expectedTransitCount: Number.isFinite(expectedValue) ? expectedValue : null,
    expectedTransitCoverage: null,
    timingResidualMedian: null,
    timingResidualMax: null,
    timingResidualTolerance: null,
    timingResidualRatio: null,
  };

  if (!centers.length || !Number.isFinite(periodValue) || periodValue <= 0 || !Number.isFinite(epochValue)) {
    return empty;
  }

  const medianDuration = median(durations);
  const durationScale = Math.max(
    Number.isFinite(durationValue) ? durationValue : 0,
    medianDuration || 0,
    periodValue * 0.035
  );
  const tolerance = Math.min(
    Math.max(durationScale * 1.5, periodValue * 0.025),
    periodValue * 0.18
  );
  if (!Number.isFinite(tolerance) || tolerance <= 0) return empty;

  const residuals = centers.map(center => {
    const cycles = Math.round((center - epochValue) / periodValue);
    return Math.abs(center - (epochValue + cycles * periodValue));
  });
  const matchedCycles = new Set();
  const matchedResiduals = [];
  residuals.forEach((residual, index) => {
    if (residual <= tolerance) {
      matchedResiduals.push(residual);
      matchedCycles.add(Math.round((centers[index] - epochValue) / periodValue));
    }
  });
  const matchCount = matchedResiduals.length;
  const eventMatchCount = matchedCycles.size;
  const offCount = centers.length - matchCount;
  const residualMedian = median(residuals);
  const observedCycles = ephemerisCyclesInObservedRanges(periodValue, epochValue, tolerance, observedRanges);
  const expectedObservedCount = observedCycles.size || (Number.isFinite(expectedValue) && expectedValue > 0 ? expectedValue : null);
  const expectedCoverage = expectedObservedCount
    ? Math.min(1, eventMatchCount / expectedObservedCount)
    : null;

  return {
    ephemerisMatchCount: matchCount,
    ephemerisMatchFraction: matchCount / centers.length,
    ephemerisEventMatchCount: eventMatchCount,
    ephemerisEventMatchFraction: expectedObservedCount ? eventMatchCount / expectedObservedCount : null,
    offEphemerisTransitCount: offCount,
    offEphemerisFraction: offCount / centers.length,
    expectedTransitCount: expectedObservedCount || (Number.isFinite(expectedValue) ? expectedValue : null),
    expectedTransitCoverage: expectedCoverage,
    timingResidualMedian: residualMedian,
    timingResidualMax: residuals.length ? Math.max(...residuals) : null,
    timingResidualTolerance: tolerance,
    timingResidualRatio: residualMedian === null ? null : residualMedian / tolerance,
  };
}

function ephemerisTolerance(period, duration, transits) {
  const periodValue = Number(period);
  if (!Number.isFinite(periodValue) || periodValue <= 0) return null;
  const durationValue = Number(duration);
  const transitDurations = (transits || [])
    .map(transit => Number(transit.duration))
    .filter(value => Number.isFinite(value) && value > 0);
  const medianDuration = median(transitDurations);
  const durationScale = Math.max(
    Number.isFinite(durationValue) ? durationValue : 0,
    medianDuration || 0,
    periodValue * 0.035
  );
  const tolerance = Math.min(
    Math.max(durationScale * 1.5, periodValue * 0.025),
    periodValue * 0.18
  );
  return Number.isFinite(tolerance) && tolerance > 0 ? tolerance : null;
}

function isDenseRegularityMatch(matchCount, eventCount, expectedCoverage, transitCount) {
  if (
    !Number.isFinite(Number(matchCount))
    || !Number.isFinite(Number(eventCount))
    || !Number.isFinite(Number(expectedCoverage))
    || !Number.isFinite(Number(transitCount))
    || Number(transitCount) < 12
  ) {
    return false;
  }
  const total = Number(transitCount);
  const denseBoxFloor = Math.max(6, Math.ceil(total * 0.35));
  return (
    Number(matchCount) >= denseBoxFloor
    && Number(eventCount) >= 3
    && Number(matchCount) / total >= 0.35
    && Number(expectedCoverage) >= 0.3
  );
}

function ephemerisResidual(center, period, epoch) {
  const centerValue = Number(center);
  const periodValue = Number(period);
  const epochValue = Number(epoch);
  if (!Number.isFinite(centerValue) || !Number.isFinite(periodValue) || periodValue <= 0 || !Number.isFinite(epochValue)) {
    return null;
  }
  const cycles = Math.round((centerValue - epochValue) / periodValue);
  const predictedCenter = epochValue + cycles * periodValue;
  return {
    cycles,
    predictedCenter,
    residual: Math.abs(centerValue - predictedCenter),
  };
}

function classifyTransitForEphemeris(transit, metrics = currentAnalysisMetrics()) {
  const tolerance = ephemerisTolerance(metrics.period, metrics.periodDuration, currentResult ? currentResult.transits : []);
  const residual = ephemerisResidual(transit.center, metrics.period, metrics.periodEpoch);
  if (!residual || tolerance === null) {
    return { status: 'unknown', residual: null, tolerance: null, predictedCenter: null };
  }
  return {
    status: residual.residual <= tolerance ? 'matched' : 'off',
    residual: residual.residual,
    tolerance,
    predictedCenter: residual.predictedCenter,
  };
}

function predictedEphemerisEvents(metrics, domain = currentResult ? currentResult.domain : null) {
  if (!domain) return [];
  const period = Number(metrics.period);
  const epoch = Number(metrics.periodEpoch);
  if (!Number.isFinite(period) || period <= 0 || !Number.isFinite(epoch)) return [];
  const tolerance = ephemerisTolerance(metrics.period, metrics.periodDuration, currentResult ? currentResult.transits : []);
  const observedRanges = observationRangesForResult(currentResult, domain);
  const firstCycle = Math.ceil((domain.time_min - epoch) / period) - 1;
  const lastCycle = Math.floor((domain.time_max - epoch) / period) + 1;
  const events = [];
  for (let cycle = firstCycle; cycle <= lastCycle; cycle++) {
    const center = epoch + cycle * period;
    if (center < domain.time_min - period || center > domain.time_max + period) continue;
    const eventStart = tolerance === null ? center : center - tolerance;
    const eventEnd = tolerance === null ? center : center + tolerance;
    const overlapsObservedData = !observedRanges.length || observedRanges.some(range => (
      eventEnd >= range.start && eventStart <= range.end
    ));
    if (!overlapsObservedData) continue;
    events.push({
      cycle,
      center,
      start: eventStart,
      end: eventEnd,
    });
  }
  return events;
}

function currentAnalysisMetrics() {
  const depthFractions = currentResult.transits
    .map(transit => Number(transit.depth_fraction))
    .filter(value => Number.isFinite(value) && value >= 0);
  const radiusRatios = currentResult.transits
    .map(transit => Number(transit.radius_ratio))
    .filter(value => Number.isFinite(value) && value >= 0);
  const rawDepths = currentResult.transits
    .map(transit => Number(transit.depth))
    .filter(value => Number.isFinite(value) && value >= 0);
  const transitPoints = currentResult.transits
    .map(transit => Number(transit.points))
    .filter(value => Number.isFinite(value) && value >= 0);
  const oddDepths = rawDepths.filter((_, index) => index % 2 === 0);
  const evenDepths = rawDepths.filter((_, index) => index % 2 === 1);
  const oddMedian = median(oddDepths);
  const evenMedian = median(evenDepths);
  const editedOddEvenMismatch = (
    oddMedian !== null && evenMedian !== null && Math.max(oddMedian, evenMedian) > 0
  ) ? Math.abs(oddMedian - evenMedian) / Math.max(oddMedian, evenMedian) : null;
  const editedDepthScatterRatio = coefficientOfVariation(rawDepths);
  const metrics = {
    period: currentResult.period,
    periodMethod: currentResult.period_method,
    periodScatter: currentResult.period_scatter,
    periodUncertainty: currentResult.period_uncertainty,
    periodMatchCount: currentResult.period_match_count,
    pValue: currentResult.p_value,
    deltaChiSquared: currentResult.delta_chi_squared,
    reducedChiSquared: currentResult.reduced_chi_squared_box,
    periodEpoch: Number.isFinite(Number(currentResult.period_epoch))
      ? Number(currentResult.period_epoch) - Number(currentResult.time_reference || 0)
      : null,
    periodDuration: currentResult.period_duration,
    periodSde: currentResult.period_sde,
    tlsSdeRaw: currentResult.tls_sde_raw,
    tlsFap: currentResult.tls_fap,
    tlsSnr: currentResult.tls_snr,
    tlsOddEvenMismatchSigma: currentResult.tls?.odd_even_mismatch_sigma ?? null,
    medianDepthFraction: median(depthFractions),
    medianRadiusRatio: median(radiusRatios),
    detectionSnr: currentResult.detection_snr,
    oddEvenDepthMismatch: currentResult.boxesEdited ? editedOddEvenMismatch : currentResult.odd_even_depth_mismatch,
    depthScatterRatio: currentResult.boxesEdited ? editedDepthScatterRatio : currentResult.depth_scatter_ratio,
    medianTransitPoints: median(transitPoints),
    maxRadiusRatio: radiusRatios.length ? Math.max(...radiusRatios) : null,
  };

  if (currentResult.boxesEdited) {
    const editedDepthCenter = median(rawDepths);
    metrics.detectionSnr = (
      editedDepthCenter !== null
      && Number.isFinite(Number(currentResult.robust_noise))
      && Number(currentResult.robust_noise) > 0
    ) ? editedDepthCenter / Number(currentResult.robust_noise) : null;
    metrics.periodSde = null;
    const periodStats = estimatePeriodFromTransitBoxes();
    if (periodStats.period !== null) {
      const centers = currentResult.transits
        .map(transit => Number(transit.center))
        .filter(value => Number.isFinite(value))
        .sort((a, b) => a - b);
      const durations = currentResult.transits
        .map(transit => Number(transit.duration))
        .filter(value => Number.isFinite(value) && value > 0);
      metrics.period = periodStats.period;
      metrics.periodMethod = 'edited boxes';
      metrics.periodScatter = periodStats.scatter;
      metrics.periodMatchCount = periodStats.count;
      metrics.periodEpoch = centers.length ? centers[0] : metrics.periodEpoch;
      metrics.periodDuration = median(durations);
      metrics.periodUncertainty = null;
      metrics.tlsFap = null;
      metrics.tlsSnr = null;
      metrics.tlsSdeRaw = null;
    }

    const pValueStats = estimatePValueFromTransitBoxes();
    if (pValueStats && pValueStats.pValue !== null) {
      metrics.pValue = pValueStats.pValue;
      metrics.deltaChiSquared = pValueStats.deltaChiSquared;
    }
  }

  Object.assign(
    metrics,
    ephemerisDiagnosticsForTransits(
      currentResult.transits,
      metrics.period,
      metrics.periodEpoch,
      metrics.periodDuration,
      metrics.periodMatchCount,
      observationRangesForResult(currentResult)
    )
  );

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
    if (metrics.periodMethod === 'transit regularity') {
      warnings.push({
        severity: 'info',
        title: 'Period selected by regularity',
        detail: 'A shorter repeating transit-box cadence explained more detected events than the strongest BLS alias.',
      });
    } else if (metrics.periodMethod === 'TLS') {
      warnings.push({
        severity: 'info',
        title: 'Physical TLS search',
        detail: 'The period was fitted with a limb-darkened transit template including ingress and egress.',
      });
    } else {
      warnings.push({
        severity: 'info',
        title: 'Period is provisional',
        detail: `Period came from ${metrics.periodMethod}, not a BLS peak.`,
      });
    }
  }
  if (metrics.pValue !== null && metrics.pValue !== undefined && metrics.pValue > 0.01) {
    warnings.push({
      severity: 'caution',
      title: 'Weak model significance',
      detail: 'The box model is not much better than a flat light curve by the current chi-squared estimate.',
    });
  }
  if (metrics.periodMethod === 'TLS' && Number.isFinite(Number(metrics.periodSde)) && Number(metrics.periodSde) < 5) {
    warnings.push({
      severity: 'caution',
      title: 'TLS peak below candidate threshold',
      detail: `TLS SDE is ${fmt(metrics.periodSde, 2)}; candidate review normally starts around SDE 5 and strong evidence around SDE 7.`,
    });
  }
  if (metrics.periodMethod === 'TLS' && Number.isFinite(Number(metrics.tlsFap)) && Number(metrics.tlsFap) > 0.01) {
    warnings.push({
      severity: 'caution',
      title: 'Weak TLS false-alarm estimate',
      detail: `TLS reports a white-noise false-alarm probability of about ${fmt(Number(metrics.tlsFap) * 100, 2)}%; red noise can make this optimistic.`,
    });
  }
  if (snr !== null && snr < 7) {
    warnings.push({
      severity: 'caution',
      title: metrics.periodMethod === 'TLS' ? 'Low search SNR' : 'Low depth SNR',
      detail: metrics.periodMethod === 'TLS'
        ? `TLS reports a combined transit SNR of ${fmt(snr, 2)}.`
        : `Median transit depth is about ${fmt(snr, 2)}x the robust noise.`,
    });
  }
  if (Number.isFinite(Number(metrics.tlsOddEvenMismatchSigma)) && Number(metrics.tlsOddEvenMismatchSigma) >= 5) {
    warnings.push({
      severity: 'danger',
      title: 'TLS odd/even mismatch',
      detail: `TLS measures an odd/even depth difference of ${fmt(metrics.tlsOddEvenMismatchSigma, 2)} sigma.`,
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
  if (
    transits.length >= 3
    && ['BLS', 'binned BLS fallback', 'transit regularity', 'TLS'].includes(metrics.periodMethod)
    && Number.isFinite(Number(metrics.ephemerisMatchFraction))
  ) {
    const matchFraction = Number(metrics.ephemerisMatchFraction);
    const matchCount = Number(metrics.ephemerisMatchCount);
    const eventCount = Number(metrics.ephemerisEventMatchCount);
    const expectedCount = Number(metrics.expectedTransitCount);
    const expectedCoverage = Number(metrics.expectedTransitCoverage);
    const wellCoveredEvents = (
      ['transit regularity', 'TLS'].includes(metrics.periodMethod)
      && Number.isFinite(eventCount)
      && eventCount >= 3
      && (
        (Number.isFinite(expectedCoverage) && expectedCoverage >= 0.65)
        || isDenseRegularityMatch(matchCount, eventCount, expectedCoverage, transits.length)
      )
    );
    const periodLabel = metrics.periodMethod === 'BLS' ? 'BLS period' : 'selected period';
    if (matchFraction < 0.55 && !wellCoveredEvents) {
      warnings.push({
        severity: 'danger',
        title: 'Irregular transit timing',
        detail: `Only ${matchCount} of ${transits.length} detected dips align with the ${periodLabel}.`,
      });
    } else if (matchFraction < 0.75 && !wellCoveredEvents) {
      warnings.push({
        severity: 'caution',
        title: 'Weak ephemeris agreement',
        detail: `${matchCount} of ${transits.length} detected dips align with the ${periodLabel}.`,
      });
    }
    if (wellCoveredEvents && matchFraction < 0.65) {
      warnings.push({
        severity: 'caution',
        title: 'Noisy extra dips',
        detail: `${eventCount} of ${expectedCount} predicted events are covered, but extra off-period dips were also boxed.`,
      });
    }

    if (
      Number.isFinite(Number(metrics.offEphemerisTransitCount))
      && Number.isFinite(Number(metrics.offEphemerisFraction))
      && Number(metrics.offEphemerisTransitCount) >= 3
      && Number(metrics.offEphemerisFraction) >= 0.35
      && !wellCoveredEvents
    ) {
      warnings.push({
        severity: 'caution',
        title: 'Many off-period dips',
        detail: 'Several detected dips do not land near the recovered period and may be systematics.',
      });
    }
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

function scoreBand(value, bands) {
  if (!Number.isFinite(Number(value))) return null;
  const numeric = Number(value);
  for (const [threshold, points, title, detail] of bands) {
    if (numeric >= threshold) return { points, title, detail };
  }
  return null;
}

function buildPlanetAssessment(metrics, warnings) {
  const transits = currentResult ? currentResult.transits || [] : [];
  const transitCount = transits.length;
  const period = Number.isFinite(Number(metrics.period)) ? Number(metrics.period) : null;
  const periodMethod = metrics.periodMethod || null;
  const periodSde = Number.isFinite(Number(metrics.periodSde)) ? Number(metrics.periodSde) : null;
  const detectionSnr = Number.isFinite(Number(metrics.detectionSnr)) ? Number(metrics.detectionSnr) : null;
  const tlsFap = Number.isFinite(Number(metrics.tlsFap)) ? Number(metrics.tlsFap) : null;
  const pValue = Number.isFinite(Number(metrics.pValue)) ? Number(metrics.pValue) : null;
  const depthScatterRatio = Number.isFinite(Number(metrics.depthScatterRatio)) ? Number(metrics.depthScatterRatio) : null;
  const oddEvenMismatch = Number.isFinite(Number(metrics.oddEvenDepthMismatch)) ? Number(metrics.oddEvenDepthMismatch) : null;
  const maxRadiusRatio = Number.isFinite(Number(metrics.maxRadiusRatio)) ? Number(metrics.maxRadiusRatio) : null;
  const medianTransitPoints = Number.isFinite(Number(metrics.medianTransitPoints)) ? Number(metrics.medianTransitPoints) : null;
  const ephemerisMatchFraction = Number.isFinite(Number(metrics.ephemerisMatchFraction)) ? Number(metrics.ephemerisMatchFraction) : null;
  const ephemerisMatchCount = Number.isFinite(Number(metrics.ephemerisMatchCount)) ? Number(metrics.ephemerisMatchCount) : null;
  const ephemerisEventMatchCount = Number.isFinite(Number(metrics.ephemerisEventMatchCount)) ? Number(metrics.ephemerisEventMatchCount) : null;
  const offEphemerisCount = Number.isFinite(Number(metrics.offEphemerisTransitCount)) ? Number(metrics.offEphemerisTransitCount) : null;
  const offEphemerisFraction = Number.isFinite(Number(metrics.offEphemerisFraction)) ? Number(metrics.offEphemerisFraction) : null;
  const expectedTransitCount = Number.isFinite(Number(metrics.expectedTransitCount)) ? Number(metrics.expectedTransitCount) : null;
  const expectedTransitCoverage = Number.isFinite(Number(metrics.expectedTransitCoverage)) ? Number(metrics.expectedTransitCoverage) : null;
  const timingResidualRatio = Number.isFinite(Number(metrics.timingResidualRatio)) ? Number(metrics.timingResidualRatio) : null;
  const ephemerisPeriodMethods = ['BLS', 'binned BLS fallback', 'transit regularity', 'TLS'];
  const periodLabel = periodMethod === 'BLS' ? 'BLS period' : 'selected period';
  const wellCoveredEphemeris = (
    ['transit regularity', 'TLS'].includes(periodMethod)
    && ephemerisEventMatchCount !== null
    && ephemerisEventMatchCount >= 3
    && (
      (expectedTransitCoverage !== null && expectedTransitCoverage >= 0.65)
      || isDenseRegularityMatch(
        ephemerisMatchCount,
        ephemerisEventMatchCount,
        expectedTransitCoverage,
        transitCount
      )
    )
  );
  const supportingEvidence = [];
  const limitingEvidence = [];
  let score = 0;

  const support = (title, detail, points) => {
    score += points;
    supportingEvidence.push({ title, detail, points });
  };
  const limit = (title, detail, points) => {
    score += points;
    limitingEvidence.push({ title, detail, points });
  };

  if (transitCount >= 3) {
    support('Repeated transit-like events', `${transitCount} candidate dips were boxed.`, 20);
  } else if (transitCount > 0) {
    support('Transit-like dip found', `${transitCount} candidate dip${transitCount === 1 ? ' was' : 's were'} boxed.`, 6);
    limit('Too few events', 'Fewer than three events is weak evidence for an orbital period.', -8);
  } else {
    limit('No boxed transit events', 'The detector did not find statistically strong local dips.', -28);
  }

  if (period !== null && period > 0 && periodMethod === 'BLS') {
    support('Stable BLS period', `Best period is ${fmt(period, 6)} days from the BLS search.`, 22);
  } else if (period !== null && period > 0 && periodMethod === 'TLS') {
    support('Physical TLS period', `Best period is ${fmt(period, 6)} days from the limb-darkened TLS search.`, 22);
  } else if (period !== null && period > 0 && periodMethod === 'transit regularity') {
    support('Frequent transit regularity', `Best repeating interval is ${fmt(period, 6)} days from the boxed transit cadence.`, 20);
  } else if (period !== null && period > 0) {
    support('Provisional period', `Estimated period is ${fmt(period, 6)} days from ${periodMethod || 'candidate spacing'}.`, 10);
    limit('Period is not a BLS peak', 'The repeating period needs manual confirmation.', -4);
  } else {
    limit('No stable period', 'A repeating orbital period was not recovered.', -18);
  }

  const sdeBand = scoreBand(periodSde, [
    [10, 22, 'Very strong period peak', `Period SDE is ${fmt(periodSde, 2)}.`],
    [7, 17, 'Strong period peak', `Period SDE is ${fmt(periodSde, 2)}.`],
    [5, 8, 'Moderate period peak', `Period SDE is ${fmt(periodSde, 2)}.`],
  ]);
  if (sdeBand) {
    support(sdeBand.title, sdeBand.detail, sdeBand.points);
  } else if (periodSde !== null) {
    limit('Weak period peak', `Period SDE is only ${fmt(periodSde, 2)}.`, -10);
  }

  const snrTitle = periodMethod === 'TLS' ? 'TLS signal SNR' : 'transit depth SNR';
  const snrBand = scoreBand(detectionSnr, [
    [10, 22, `High ${snrTitle}`, `Search SNR is ${fmt(detectionSnr, 2)}.`],
    [7, 16, `Good ${snrTitle}`, `Search SNR is ${fmt(detectionSnr, 2)}.`],
    [5, 8, `Marginal ${snrTitle}`, `Search SNR is ${fmt(detectionSnr, 2)}.`],
  ]);
  if (snrBand) {
    support(snrBand.title, snrBand.detail, snrBand.points);
  } else if (detectionSnr !== null) {
    limit(`Low ${snrTitle}`, `Search SNR is only ${fmt(detectionSnr, 2)}.`, -14);
  }

  if (periodMethod === 'TLS' && tlsFap !== null) {
    if (tlsFap <= 0.001) {
      support('Low TLS false-alarm probability', `White-noise FAP is ${fmt(tlsFap * 100, 3)}%.`, 10);
    } else if (tlsFap <= 0.01) {
      support('Useful TLS false-alarm estimate', `White-noise FAP is ${fmt(tlsFap * 100, 2)}%.`, 6);
    } else {
      limit('Weak TLS false-alarm estimate', `White-noise FAP is ${fmt(tlsFap * 100, 2)}%.`, -10);
    }
  }

  if (pValue !== null) {
    if (pValue <= 1e-6) {
      support('Very significant box model', 'The transit model strongly beats a flat light curve.', 16);
    } else if (pValue <= 1e-4) {
      support('Significant box model', 'The transit model clearly beats a flat light curve.', 12);
    } else if (pValue <= 0.01) {
      support('Useful box-model improvement', 'The transit model improves over a flat light curve.', 8);
    } else {
      limit('Weak box-model significance', 'The transit model is not much better than a flat light curve.', -12);
    }
  }

  if (ephemerisPeriodMethods.includes(periodMethod) && transitCount >= 3 && ephemerisMatchFraction !== null) {
    if (ephemerisMatchFraction >= 0.8) {
      support('Detected dips follow the ephemeris', `${ephemerisMatchCount} of ${transitCount} dips align with the ${periodLabel}.`, 16);
    } else if (wellCoveredEphemeris) {
      support('Predicted events are covered', `${ephemerisEventMatchCount} of ${expectedTransitCount} predicted events have matching dips.`, 12);
    } else if (ephemerisMatchFraction >= 0.65) {
      support('Partial ephemeris agreement', `${ephemerisMatchCount} of ${transitCount} dips align with the ${periodLabel}.`, 5);
      limit('Some off-period dips', 'Several detected dips do not belong to the recovered period.', -6);
    } else if (ephemerisMatchFraction < 0.55) {
      limit('Irregular transit timing', `Only ${ephemerisMatchCount} of ${transitCount} dips align with the ${periodLabel}.`, -34);
    } else {
      limit('Weak timing agreement', `Only ${ephemerisMatchCount} of ${transitCount} dips align with the ${periodLabel}.`, -18);
    }
  }

  if (offEphemerisCount !== null && offEphemerisFraction !== null && offEphemerisCount >= 3 && offEphemerisFraction >= 0.35) {
    if (wellCoveredEphemeris) {
      limit('Extra off-period dips', 'The selected ephemeris repeats, but extra boxed dips may be noise or systematics.', -6);
    } else {
      limit('Many off-period dips', 'The detector found too many transit-like dips away from the recovered ephemeris.', -24);
    }
  }

  if (expectedTransitCoverage !== null && transitCount >= 3 && expectedTransitCoverage < 0.5) {
    limit('Weak predicted-transit coverage', `Only ${fmt(expectedTransitCoverage * 100, 0)}% of expected ${periodLabel} events were matched.`, -10);
  }

  if (timingResidualRatio !== null && timingResidualRatio > 1.0 && transitCount >= 3 && !wellCoveredEphemeris) {
    limit('Large timing residuals', 'Detected dip centers are not tightly clustered around the recovered ephemeris.', -10);
  }

  if (depthScatterRatio !== null && transitCount >= 4) {
    if (depthScatterRatio <= 0.35) {
      support('Consistent transit depths', `Depth scatter ratio is ${fmt(depthScatterRatio, 2)}.`, 7);
    } else if (depthScatterRatio > 0.8) {
      limit('Inconsistent transit depths', `Depth scatter ratio is ${fmt(depthScatterRatio, 2)}.`, -12);
    } else if (depthScatterRatio > 0.5) {
      limit('Moderately inconsistent depths', `Depth scatter ratio is ${fmt(depthScatterRatio, 2)}.`, -6);
    }
  }

  if (oddEvenMismatch !== null && transitCount >= 4) {
    if (oddEvenMismatch <= 0.25) {
      support('Odd/even depths agree', `Odd/even mismatch is ${fmt(oddEvenMismatch, 2)}.`, 6);
    } else if (oddEvenMismatch > 0.5) {
      limit('Odd/even depth mismatch', 'Alternating depths can indicate an eclipsing binary or blend.', -18);
    } else if (oddEvenMismatch > 0.35) {
      limit('Possible odd/even mismatch', `Odd/even mismatch is ${fmt(oddEvenMismatch, 2)}.`, -8);
    }
  }

  if (maxRadiusRatio !== null) {
    if (maxRadiusRatio <= 0.2) {
      support('Planet-sized radius ratio', `Maximum Rp/Rs estimate is ${fmt(maxRadiusRatio, 3)}.`, 4);
    } else if (maxRadiusRatio > 0.3) {
      limit('Very large radius ratio', `Maximum Rp/Rs estimate is ${fmt(maxRadiusRatio, 3)}.`, -16);
    } else {
      limit('Large radius ratio', `Maximum Rp/Rs estimate is ${fmt(maxRadiusRatio, 3)}.`, -8);
    }
  }

  if (medianTransitPoints !== null) {
    if (medianTransitPoints >= 8) {
      support('Well-sampled events', `Median transit has ${fmt(medianTransitPoints, 0)} plotted points.`, 4);
    } else if (medianTransitPoints < 4) {
      limit('Sparse transit sampling', `Median transit has only ${fmt(medianTransitPoints, 0)} plotted points.`, -6);
    }
  }

  const dangerCount = warnings.filter(warning => warning.severity === 'danger').length;
  const cautionCount = warnings.filter(warning => warning.severity === 'caution').length;
  if (dangerCount) score -= dangerCount * 10;
  if (cautionCount >= 3) score -= 6;

  const rawCandidateScore = Math.round(Math.max(0, Math.min(100, score)));
  const highRepeatConfidence = (
    transitCount >= 5
    && detectionSnr !== null
    && detectionSnr >= 5
    && periodSde !== null
    && periodSde >= (periodMethod === 'TLS' ? 7 : 8)
    && (ephemerisMatchFraction === null || ephemerisMatchFraction >= 0.85)
    && (expectedTransitCoverage === null || expectedTransitCoverage >= 0.65)
    && (offEphemerisFraction === null || offEphemerisFraction <= 0.2)
  );
  const strongRequirementsMet = (
    transitCount >= 3
    && period !== null
    && ['BLS', 'TLS'].includes(periodMethod)
    && detectionSnr !== null
    && (detectionSnr >= 7 || highRepeatConfidence)
    && (periodSde === null || periodSde >= (periodMethod === 'TLS' ? 7 : 5))
    && (periodMethod !== 'TLS' || tlsFap === null || tlsFap <= 0.01)
    && (ephemerisMatchFraction === null || ephemerisMatchFraction >= 0.75)
    && (offEphemerisFraction === null || offEphemerisFraction <= 0.3)
    && dangerCount === 0
  );
  const severeTimingMismatch = (
    transitCount >= 3
    && ephemerisPeriodMethods.includes(periodMethod)
    && ephemerisMatchFraction !== null
    && ephemerisMatchFraction < 0.55
    && !wellCoveredEphemeris
    && offEphemerisCount !== null
    && offEphemerisCount >= 2
  );
  const credibleTlsSignal = (
    periodMethod !== 'TLS'
    || (
      periodSde !== null
      && periodSde >= 5
      && detectionSnr !== null
      && detectionSnr >= 5
    )
  );

  let status;
  let title;
  let shortLabel;
  let summary;
  let recommendation;

  if (transitCount === 0) {
    const hasUnboxedPeriodSignal = (
      rawCandidateScore >= 35
      && periodSde !== null
      && periodSde >= 7
      && (pValue === null || pValue <= 0.01)
    );
    if (hasUnboxedPeriodSignal) {
      status = 'inconclusive';
      title = 'Period signal needs review';
      shortLabel = 'Inconclusive';
      summary = 'The period search found some signal, but the local detector did not box credible transit events. This needs manual review before calling it an exoplanet candidate.';
      recommendation = 'Inspect the phase-folded view and try adjusted duration/strictness bounds.';
    } else {
      status = 'no_planet_like_signal';
      title = 'No planet-like transit detected';
      shortLabel = 'No credible signal';
      summary = 'No statistically credible repeating transit signal was found. This dataset may not contain a detectable transiting exoplanet at the current settings.';
      recommendation = 'Check the input columns, try lower strictness, or analyze a longer/higher-SNR light curve.';
    }
  } else if (severeTimingMismatch) {
    status = 'no_planet_like_signal';
    title = 'Transit-like dips are not periodic';
    shortLabel = 'No credible signal';
    summary = 'The detector found dip-shaped events, but most do not align with one repeating orbital schedule. That pattern is more consistent with irregular variability or systematics than a single transiting exoplanet.';
    recommendation = 'Inspect the off-period dips and try stricter duration/depth bounds before treating this as a candidate.';
  } else if (rawCandidateScore >= 75 && strongRequirementsMet) {
    status = 'strong_candidate';
    title = 'Strong planet-like transit candidate';
    shortLabel = 'Strong candidate';
    summary = 'Repeated dips align with a stable period and pass the current signal-strength checks. This is a strong candidate, not a confirmed planet.';
    recommendation = 'Use the phase-folded view, exports, and follow-up vetting before treating this as confirmed.';
  } else if (rawCandidateScore >= 45 && transitCount >= 2 && credibleTlsSignal) {
    status = 'possible_candidate';
    title = 'Possible transit candidate';
    shortLabel = 'Possible candidate';
    summary = 'The dataset contains some planet-like transit evidence, but one or more checks are not strong enough for a confident candidate call.';
    recommendation = 'Review warnings, period aliases, and the phase-folded view.';
  } else {
    status = 'no_planet_like_signal';
    title = 'No credible planet-like signal';
    shortLabel = 'No credible signal';
    summary = 'Detected dips do not currently pass enough planet-likeness checks. This dataset may not contain a detectable transiting exoplanet.';
    recommendation = 'Inspect warnings and rerun with adjusted detection bounds if the light curve looks suspicious.';
  }

  let candidateScore = rawCandidateScore;
  if (status === 'possible_candidate') {
    candidateScore = Math.min(candidateScore, 74);
  } else if (status === 'inconclusive') {
    candidateScore = Math.min(candidateScore, 59);
  } else if (status === 'no_planet_like_signal') {
    candidateScore = Math.min(candidateScore, 44);
  }

  return {
    status,
    title,
    shortLabel,
    short_label: shortLabel,
    candidateScore,
    candidate_score: candidateScore,
    summary,
    recommendation,
    supportingEvidence,
    supporting_evidence: supportingEvidence,
    limitingEvidence,
    limiting_evidence: limitingEvidence,
    inputs: {
      transit_count: transitCount,
      period,
      period_method: periodMethod,
      period_sde: periodSde,
      detection_snr: detectionSnr,
      tls_fap: tlsFap,
      p_value: pValue,
      depth_scatter_ratio: depthScatterRatio,
      odd_even_depth_mismatch: oddEvenMismatch,
      max_radius_ratio: maxRadiusRatio,
      median_transit_points: medianTransitPoints,
      ephemeris_match_fraction: ephemerisMatchFraction,
      ephemeris_match_count: ephemerisMatchCount,
      ephemeris_event_match_count: ephemerisEventMatchCount,
      off_ephemeris_transit_count: offEphemerisCount,
      off_ephemeris_fraction: offEphemerisFraction,
      expected_transit_count: expectedTransitCount,
      expected_transit_coverage: expectedTransitCoverage,
      timing_residual_ratio: timingResidualRatio,
      warning_count: warnings.length,
      danger_warning_count: dangerCount,
      caution_warning_count: cautionCount,
    },
  };
}

function currentPlanetAssessment(metrics = null, warnings = null) {
  if (!currentResult) return null;
  const resolvedMetrics = metrics || currentAnalysisMetrics();
  const resolvedWarnings = warnings || currentWarnings(resolvedMetrics);
  return buildPlanetAssessment(resolvedMetrics, resolvedWarnings);
}

function assessmentForResult(result) {
  const previousResult = currentResult;
  currentResult = result;
  try {
    const metrics = currentAnalysisMetrics();
    return currentPlanetAssessment(metrics, currentWarnings(metrics));
  } finally {
    currentResult = previousResult;
  }
}

function evidenceListHtml(items) {
  return items.slice(0, 3).map(item => `
    <div>
      <strong>${escapeHtml(item.title)}</strong>
      <span>${escapeHtml(item.detail)}</span>
    </div>
  `).join('');
}

function renderAssessment(metrics = null, warnings = null) {
  if (!currentResult) return;
  const resolvedMetrics = metrics || currentAnalysisMetrics();
  const resolvedWarnings = warnings || currentWarnings(resolvedMetrics);
  const assessment = currentPlanetAssessment(resolvedMetrics, resolvedWarnings);
  const evidenceHtml = evidenceListHtml(
    assessment.status === 'strong_candidate'
      ? assessment.supportingEvidence
      : [...assessment.limitingEvidence, ...assessment.supportingEvidence]
  );
  assessmentEl.innerHTML = `
    <div class="assessment-card ${assessment.status}">
      <div class="assessment-head">
        <strong>${escapeHtml(assessment.title)}</strong>
        <span>${assessment.candidateScore}/100</span>
      </div>
      <p>${escapeHtml(assessment.summary)}</p>
      <div class="score-track" aria-label="Candidate score">
        <div class="score-fill" style="width: ${assessment.candidateScore}%;"></div>
      </div>
      <p>${escapeHtml(assessment.recommendation)}</p>
      ${evidenceHtml ? `<div class="assessment-evidence">${evidenceHtml}</div>` : ''}
    </div>
  `;
}

function renderWarnings(warnings = null) {
  if (!currentResult) return;
  const resolvedWarnings = warnings || currentWarnings();
  if (!resolvedWarnings.length) {
    warningsEl.innerHTML = `
      <div class="warning-item info">
        <strong>No major warnings</strong>
        <span>These checks are heuristic and do not prove the candidate is planetary.</span>
      </div>
    `;
    return;
  }
  warningsEl.innerHTML = resolvedWarnings.map(warning => `
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
      <span>${candidate.method ? `${escapeHtml(candidate.method)}; ` : ''}Power ${fmt(candidate.power, 2)}${candidate.sde === null || candidate.sde === undefined ? '' : `, SDE ${fmt(candidate.sde, 2)}`}</span>
    </div>
  `).join('');
}

function renderMetrics() {
  if (!currentResult) return;
  const metrics = currentAnalysisMetrics();
  const warnings = currentWarnings(metrics);
  const period = metrics.period === null || metrics.period === undefined
    ? 'Not enough transits'
    : `${fmt(metrics.period)} days${metrics.periodMethod ? ` (${metrics.periodMethod})` : ''}`;
  const ephemerisFit = (
    metrics.ephemerisMatchCount === null
    || metrics.ephemerisMatchCount === undefined
    || metrics.ephemerisMatchFraction === null
    || metrics.ephemerisMatchFraction === undefined
  )
    ? '-'
    : `${metrics.ephemerisMatchCount}/${currentResult.transits.length} (${fmt(metrics.ephemerisMatchFraction * 100, 0)}%)`;

  renderAssessment(metrics, warnings);
  metricsEl.innerHTML = `
    <div class="metric"><span>Data points</span><span>${currentResult.total_points.toLocaleString()}</span></div>
    <div class="metric"><span>Transits</span><span>${currentResult.transits.length}</span></div>
    <div class="metric"><span>Orbital period</span><span>${period}</span></div>
    <div class="metric"><span>Period uncertainty</span><span>${metrics.periodUncertainty === null || metrics.periodUncertainty === undefined ? '-' : `± ${fmt(metrics.periodUncertainty, 6)} days`}</span></div>
    <div class="metric"><span>Median depth</span><span>${fmtDepthPercent(metrics.medianDepthFraction)} / ${fmtPpm(metrics.medianDepthFraction === null ? null : metrics.medianDepthFraction * 1000000)} ppm</span></div>
    <div class="metric"><span>Radius ratio</span><span>${fmt(metrics.medianRadiusRatio)}</span></div>
    <div class="metric"><span>${metrics.periodMethod === 'TLS' ? 'TLS SNR' : 'Depth SNR'}</span><span>${fmt(metrics.detectionSnr, 2)}</span></div>
    <div class="metric"><span>Period SDE</span><span>${fmt(metrics.periodSde, 2)}</span></div>
    <div class="metric"><span>TLS false-alarm probability</span><span>${metrics.periodMethod === 'TLS' ? fmtPercent(metrics.tlsFap) : '-'}</span></div>
    <div class="metric"><span>Ephemeris fit</span><span>${ephemerisFit}</span></div>
    <div class="metric"><span>Chi-sq p-value</span><span>${fmtPercent(metrics.pValue)}</span></div>
    <div class="metric"><span>Reduced chi-sq</span><span>${fmt(metrics.reducedChiSquared, 3)}</span></div>
    <div class="metric"><span>JD start</span><span>${fmt(currentResult.time_reference, 5)}</span></div>
    <div class="metric"><span>Median flux</span><span>${fmt(currentResult.median_flux)}</span></div>
    <div class="metric"><span>Noise</span><span>${fmt(currentResult.robust_noise)}</span></div>
  `;
  renderPeriodCandidates();
  renderWarnings(warnings);
}

function renderResult(result) {
  emptyEl.style.display = 'none';
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
  const planetAssessment = currentPlanetAssessment(metrics, warnings);
  return {
    exported_at: new Date().toISOString(),
    source_file: selectedFile ? selectedFile.name : null,
    chart_view: currentView,
    total_points: currentResult.total_points,
    time_reference_jd: currentResult.time_reference,
    time_unit: currentResult.time_unit,
    flux_unit: currentResult.flux_unit,
    normalization: currentResult.normalization,
    detection_options: currentResult.detection_options,
    boxes_edited: Boolean(currentResult.boxesEdited),
    planet_assessment: planetAssessment,
    warnings,
    diagnostics: {
      detection_snr: metrics.detectionSnr,
      tls_snr: metrics.tlsSnr,
      tls_fap: metrics.tlsFap,
      tls_odd_even_mismatch_sigma: metrics.tlsOddEvenMismatchSigma,
      odd_even_depth_mismatch: metrics.oddEvenDepthMismatch,
      depth_scatter_ratio: metrics.depthScatterRatio,
      ephemeris_match_count: metrics.ephemerisMatchCount,
      ephemeris_match_fraction: metrics.ephemerisMatchFraction,
      ephemeris_event_match_count: metrics.ephemerisEventMatchCount,
      ephemeris_event_match_fraction: metrics.ephemerisEventMatchFraction,
      off_ephemeris_transit_count: metrics.offEphemerisTransitCount,
      off_ephemeris_fraction: metrics.offEphemerisFraction,
      expected_transit_count: metrics.expectedTransitCount,
      expected_transit_coverage: metrics.expectedTransitCoverage,
      timing_residual_median: metrics.timingResidualMedian,
      timing_residual_tolerance: metrics.timingResidualTolerance,
      timing_residual_ratio: metrics.timingResidualRatio,
    },
    metrics: {
      transit_count: currentResult.transits.length,
      orbital_period_days: metrics.period,
      orbital_period_method: metrics.periodMethod,
      orbital_period_scatter: metrics.periodScatter,
      orbital_period_uncertainty: metrics.periodUncertainty,
      harmonic_alias_corrected: Boolean(currentResult.harmonic_alias_corrected),
      harmonic_alias_period: currentResult.harmonic_alias_period ?? null,
      harmonic_alias_factor: currentResult.harmonic_alias_factor ?? null,
      harmonic_alias_power_ratio: currentResult.harmonic_alias_power_ratio ?? null,
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
      tls_sde_raw: metrics.tlsSdeRaw,
      tls_fap: metrics.tlsFap,
      tls_snr: metrics.tlsSnr,
      ephemeris_match_count: metrics.ephemerisMatchCount,
      ephemeris_match_fraction: metrics.ephemerisMatchFraction,
      ephemeris_event_match_count: metrics.ephemerisEventMatchCount,
      ephemeris_event_match_fraction: metrics.ephemerisEventMatchFraction,
      off_ephemeris_transit_count: metrics.offEphemerisTransitCount,
      off_ephemeris_fraction: metrics.offEphemerisFraction,
      median_flux: currentResult.median_flux,
      robust_noise: currentResult.robust_noise,
    },
    period_candidates: currentResult.period_candidates || [],
    period_search: currentResult.period_search || null,
    periodogram: currentResult.periodogram || null,
    tls: currentResult.tls || null,
    transits: transitRowsForExport(),
  };
}

function metricsForResult(result) {
  const previousResult = currentResult;
  currentResult = result;
  try {
    return currentAnalysisMetrics();
  } finally {
    currentResult = previousResult;
  }
}

const analysisPdfColumns = [
  { key: 'file', label: 'File', width: 135, align: 'left' },
  { key: 'assessment', label: 'Assessment', width: 110, align: 'left' },
  { key: 'score', label: 'Score', width: 42, align: 'right' },
  { key: 'points', label: 'Data points', width: 55, align: 'right' },
  { key: 'transits', label: 'Transits', width: 45, align: 'right' },
  { key: 'ephemerisFit', label: 'Ephem fit', width: 52, align: 'right' },
  { key: 'period', label: 'Period d', width: 62, align: 'right' },
  { key: 'method', label: 'Method', width: 48, align: 'left' },
  { key: 'depthPercent', label: 'Depth %', width: 54, align: 'right' },
  { key: 'depthPpm', label: 'Depth ppm', width: 58, align: 'right' },
  { key: 'radiusRatio', label: 'Rp/Rs', width: 46, align: 'right' },
  { key: 'snr', label: 'Depth SNR', width: 50, align: 'right' },
  { key: 'sde', label: 'Period SDE', width: 50, align: 'right' },
  { key: 'pValue', label: 'Chi-sq p %', width: 58, align: 'right' },
  { key: 'reducedChi', label: 'Red chi-sq', width: 54, align: 'right' },
  { key: 'jdStart', label: 'JD start', width: 66, align: 'right' },
  { key: 'medianFlux', label: 'Med flux', width: 52, align: 'right' },
  { key: 'noise', label: 'Noise', width: 50, align: 'right' },
];

function analysisPdfRow(fileName, result) {
  const metrics = metricsForResult(result);
  const assessment = assessmentForResult(result);
  const depthPpm = metrics.medianDepthFraction === null || metrics.medianDepthFraction === undefined
    ? null
    : metrics.medianDepthFraction * 1000000;
  const pValuePercent = metrics.pValue === null || metrics.pValue === undefined
    ? null
    : metrics.pValue * 100;
  return {
    file: fileName || result.source_file || 'analysis',
    assessment: assessment.shortLabel,
    score: assessment.candidateScore.toString(),
    points: result.total_points.toLocaleString(),
    transits: result.transits.length.toString(),
    ephemerisFit: (
      metrics.ephemerisMatchCount === null
      || metrics.ephemerisMatchCount === undefined
      || metrics.ephemerisMatchFraction === null
      || metrics.ephemerisMatchFraction === undefined
    )
      ? '-'
      : `${metrics.ephemerisMatchCount}/${result.transits.length}`,
    period: fmt(metrics.period, 6),
    method: metrics.periodMethod || '-',
    depthPercent: fmtDepthPercent(metrics.medianDepthFraction),
    depthPpm: fmtPpm(depthPpm),
    radiusRatio: fmt(metrics.medianRadiusRatio, 6),
    snr: fmt(metrics.detectionSnr, 2),
    sde: fmt(metrics.periodSde, 2),
    pValue: pValuePercent === null ? '-' : `${fmt(pValuePercent, 6)}%`,
    reducedChi: fmt(metrics.reducedChiSquared, 3),
    jdStart: fmt(result.time_reference, 5),
    medianFlux: fmt(result.median_flux, 6),
    noise: fmt(result.robust_noise, 6),
  };
}

function pdfSafeText(value) {
  return String(value ?? '-')
    .replace(/[^\x20-\x7E]/g, '?')
    .replace(/\\/g, '\\\\')
    .replace(/\(/g, '\\(')
    .replace(/\)/g, '\\)');
}

function fitPdfText(value, maxChars) {
  const text = String(value ?? '-').replace(/\s+/g, ' ').trim();
  return text.length > maxChars ? `${text.slice(0, Math.max(0, maxChars - 1))}...` : text;
}

function pdfText(x, y, text, size = 7, font = 'F1') {
  return `BT /${font} ${size} Tf ${x.toFixed(2)} ${y.toFixed(2)} Td (${pdfSafeText(text)}) Tj ET\n`;
}

function pdfLine(x1, y1, x2, y2) {
  return `${x1.toFixed(2)} ${y1.toFixed(2)} m ${x2.toFixed(2)} ${y2.toFixed(2)} l S\n`;
}

function pdfRect(x, y, width, height) {
  return `${x.toFixed(2)} ${y.toFixed(2)} ${width.toFixed(2)} ${height.toFixed(2)} re S\n`;
}

function buildPdfBlob(pageContents, pageWidth, pageHeight) {
  const objects = [null];
  objects[1] = '<< /Type /Catalog /Pages 2 0 R >>';
  objects[2] = '';
  objects[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>';
  objects[4] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>';
  const pageIds = [];

  pageContents.forEach(content => {
    const contentId = objects.length;
    objects.push(`<< /Length ${content.length} >>\nstream\n${content}endstream`);
    const pageId = objects.length;
    pageIds.push(pageId);
    objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents ${contentId} 0 R >>`);
  });

  objects[2] = `<< /Type /Pages /Kids [${pageIds.map(id => `${id} 0 R`).join(' ')}] /Count ${pageIds.length} >>`;

  let pdf = '%PDF-1.4\n';
  const offsets = [0];
  for (let index = 1; index < objects.length; index++) {
    offsets[index] = pdf.length;
    pdf += `${index} 0 obj\n${objects[index]}\nendobj\n`;
  }
  const xrefStart = pdf.length;
  pdf += `xref\n0 ${objects.length}\n0000000000 65535 f \n`;
  for (let index = 1; index < objects.length; index++) {
    pdf += `${String(offsets[index]).padStart(10, '0')} 00000 n \n`;
  }
  pdf += `trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF`;
  return new Blob([pdf], { type: 'application/pdf' });
}

function buildAnalysisPdf(rows, title) {
  const pageWidth = 1224;
  const pageHeight = 792;
  const margin = 24;
  const tableWidth = analysisPdfColumns.reduce((sum, column) => sum + column.width, 0);
  const rowHeight = 22;
  const headerHeight = 24;
  const rowsPerPage = Math.max(1, Math.floor((pageHeight - 96 - headerHeight) / rowHeight));
  const pages = [];
  const pageCount = Math.max(1, Math.ceil(rows.length / rowsPerPage));

  for (let pageIndex = 0; pageIndex < pageCount; pageIndex++) {
    const pageRows = rows.slice(pageIndex * rowsPerPage, (pageIndex + 1) * rowsPerPage);
    let content = '0.8 w\n';
    const titleY = pageHeight - margin - 12;
    content += pdfText(margin, titleY, title, 13, 'F2');
    content += pdfText(pageWidth - margin - 88, titleY, `Page ${pageIndex + 1}/${pageCount}`, 8, 'F1');
    content += pdfText(margin, titleY - 16, `Generated ${new Date().toLocaleString()}`, 8, 'F1');

    let y = pageHeight - margin - 54;
    let x = margin;
    content += pdfRect(margin, y - headerHeight + 4, tableWidth, headerHeight);
    analysisPdfColumns.forEach(column => {
      content += pdfLine(x, y + 4, x, y - headerHeight + 4);
      content += pdfText(x + 3, y - 11, column.label, 7, 'F2');
      x += column.width;
    });
    content += pdfLine(margin + tableWidth, y + 4, margin + tableWidth, y - headerHeight + 4);
    y -= headerHeight;

    pageRows.forEach(row => {
      x = margin;
      content += pdfRect(margin, y - rowHeight + 4, tableWidth, rowHeight);
      analysisPdfColumns.forEach(column => {
        const rawValue = row[column.key] ?? '-';
        const maxChars = Math.max(4, Math.floor(column.width / 4.2));
        const value = fitPdfText(rawValue, maxChars);
        const textWidth = value.length * 3.7;
        const textX = column.align === 'right'
          ? Math.max(x + 3, x + column.width - textWidth - 4)
          : x + 3;
        content += pdfLine(x, y + 4, x, y - rowHeight + 4);
        content += pdfText(textX, y - 10, value, 7, 'F1');
        x += column.width;
      });
      content += pdfLine(margin + tableWidth, y + 4, margin + tableWidth, y - rowHeight + 4);
      y -= rowHeight;
    });

    pages.push(content);
  }

  return buildPdfBlob(pages, pageWidth, pageHeight);
}

function successfulBatchItems() {
  return batchResults.filter(item => item.result);
}

function exportAnalysisPdf() {
  if (!currentResult) return;
  const fileName = selectedFile ? selectedFile.name : currentResult.source_file;
  const rows = [analysisPdfRow(fileName, currentResult)];
  const pdf = buildAnalysisPdf(rows, 'Transit Finder Analysis');
  downloadBlob(pdf, `${exportBaseName()}-analysis.pdf`, 'application/pdf');
  setStatus('Analysis PDF exported.');
}

function exportBatchAnalysisPdf() {
  const items = successfulBatchItems();
  if (!items.length) return;
  const rows = items.map(item => analysisPdfRow(item.file.name, item.result));
  const pdf = buildAnalysisPdf(rows, 'Transit Finder Batch Analysis');
  downloadBlob(pdf, `${exportBaseName()}-batch-analysis.pdf`, 'application/pdf');
  setStatus(`Batch analysis PDF exported for ${rows.length} file${rows.length === 1 ? '' : 's'}.`);
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
exportAnalysisPdfButton.addEventListener('click', exportAnalysisPdf);
exportBatchPdfButton.addEventListener('click', exportBatchAnalysisPdf);

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
  if (currentView === 'periodogram') {
    return domainForPeriodogram();
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
  if (currentView === 'periodogram') {
    return domainForPeriodogram();
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

function drawChartAxes(geo, viewport, options = {}) {
  const { width, height, pad, innerW, innerH } = geo;
  const {
    xDigits = 4,
    yDigits = 4,
    xLabel = '',
    yLabel = '',
  } = options;
  const xDivisions = Math.max(2, Math.min(6, Math.floor(innerW / 88)));
  const yDivisions = Math.max(2, Math.min(5, Math.floor(innerH / 52)));
  const plotBottom = pad.top + innerH;

  ctx.strokeStyle = '#d6dde5';
  ctx.lineWidth = 1;
  ctx.fillStyle = '#5f6874';
  ctx.font = '12px system-ui, sans-serif';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';

  for (let i = 0; i <= yDivisions; i++) {
    const y = pad.top + (innerH * i / yDivisions);
    const value = viewport.yMax - ((viewport.yMax - viewport.yMin) * i / yDivisions);
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
    ctx.fillText(fmt(value, yDigits), pad.left - 9, y);
  }

  ctx.textBaseline = 'top';
  for (let i = 0; i <= xDivisions; i++) {
    const x = pad.left + (innerW * i / xDivisions);
    const value = viewport.xMin + ((viewport.xMax - viewport.xMin) * i / xDivisions);
    ctx.beginPath();
    ctx.moveTo(x, plotBottom);
    ctx.lineTo(x, plotBottom + 5);
    ctx.stroke();
    ctx.textAlign = i === 0 ? 'left' : (i === xDivisions ? 'right' : 'center');
    ctx.fillText(fmt(value, xDigits), x, plotBottom + 10);
  }

  ctx.fillStyle = '#202124';
  ctx.font = '700 12px system-ui, sans-serif';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  if (yLabel) {
    ctx.fillText(yLabel, pad.left, Math.max(8, pad.top - 27));
  }
  ctx.textAlign = 'right';
  if (xLabel) {
    ctx.fillText(xLabel, width - pad.right, height - 23);
  }
}

function clipToChartPlot(geo) {
  ctx.beginPath();
  ctx.rect(geo.pad.left, geo.pad.top, geo.innerW, geo.innerH);
  ctx.clip();
}

function nearestPeriodogramPoint(points, period) {
  const target = Number(period);
  if (!Number.isFinite(target) || target <= 0) return null;
  let nearest = null;
  let nearestDistance = Infinity;
  points.forEach(point => {
    const distance = Math.abs(point.period - target);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearest = point;
    }
  });
  return nearest;
}

function drawPeriodogramLegend(geo, series) {
  const { width, pad } = geo;
  const selectedPeriod = Number(currentResult.period);
  const items = [
    { color: '#063f3b', text: series.yLabel },
    { color: '#202124', text: Number.isFinite(selectedPeriod) ? `Selected ${fmt(selectedPeriod, 4)} d` : 'Selected period' },
    { color: '#b45309', text: 'Top candidates' },
  ];
  ctx.save();
  ctx.font = '700 11px system-ui, sans-serif';
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'left';
  const itemWidths = items.map(item => 18 + ctx.measureText(item.text).width + 10);
  const legendWidth = Math.min(
    width - pad.left - pad.right,
    itemWidths.reduce((sum, value) => sum + value, 0) + 12
  );
  const xStart = Math.max(pad.left + 8, width - pad.right - legendWidth - 6);
  let x = xStart + 8;
  const y = pad.top + 15;
  ctx.fillStyle = 'rgba(251, 252, 253, 0.9)';
  ctx.strokeStyle = 'rgba(215, 220, 227, 0.95)';
  ctx.lineWidth = 1;
  ctx.fillRect(xStart, pad.top + 4, legendWidth, 22);
  ctx.strokeRect(xStart, pad.top + 4, legendWidth, 22);
  items.forEach(item => {
    const widthNeeded = 18 + ctx.measureText(item.text).width + 10;
    if (x + widthNeeded > xStart + legendWidth) return;
    ctx.fillStyle = item.color;
    ctx.fillRect(x, y - 4, 9, 8);
    ctx.fillStyle = '#3f4650';
    ctx.fillText(item.text, x + 14, y);
    x += widthNeeded;
  });
  ctx.restore();
}

function drawPeriodogramMarker(geo, viewport, xScale, period, color, label, offset = 0, dashed = false) {
  const periodValue = Number(period);
  if (!Number.isFinite(periodValue) || periodValue <= 0 || periodValue < viewport.xMin || periodValue > viewport.xMax) return;
  const { pad, innerH } = geo;
  const x = xScale(periodValue);
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  if (dashed) ctx.setLineDash([5, 5]);
  ctx.beginPath();
  ctx.moveTo(x, pad.top);
  ctx.lineTo(x, pad.top + innerH);
  ctx.stroke();
  ctx.setLineDash([]);
  if (label) {
    ctx.fillStyle = color;
    ctx.font = '700 11px system-ui, sans-serif';
    ctx.textBaseline = 'top';
    const labelWidth = ctx.measureText(label).width;
    const plotLeft = pad.left + 4;
    const plotRight = geo.width - pad.right - 4;
    const fitsRight = x + 6 + labelWidth <= plotRight;
    ctx.textAlign = fitsRight ? 'left' : 'right';
    const labelX = fitsRight
      ? Math.max(plotLeft, x + 6)
      : Math.min(plotRight, x - 6);
    const labelY = pad.top + 34 + offset;
    ctx.fillStyle = 'rgba(251, 252, 253, 0.9)';
    ctx.fillRect(
      fitsRight ? labelX - 2 : labelX - labelWidth - 2,
      labelY - 1,
      labelWidth + 4,
      14
    );
    ctx.fillStyle = color;
    ctx.fillText(label, labelX, labelY);
  }
  ctx.restore();
}

function drawPeriodogramChart(geo) {
  transitBoxCache = [];
  const width = geo.width;
  const height = geo.height;
  const pad = geo.pad;
  const innerW = geo.innerW;
  const innerH = geo.innerH;
  const series = periodogramSeries();
  if (!series) {
    drawNotice('Periodogram data is not available for this run.', width, height);
    return;
  }

  const viewport = getViewport();
  if (!viewport) {
    drawNotice('Periodogram data is not available for this run.', width, height);
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

  drawChartAxes(geo, viewport, {
    xDigits: 4,
    yDigits: 3,
    xLabel: 'Period days',
    yLabel: series.yLabel,
  });

  if (yMin < 0 && yMax > 0) {
    const zeroY = yScale(0);
    ctx.strokeStyle = 'rgba(95, 104, 116, 0.45)';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(pad.left, zeroY);
    ctx.lineTo(width - pad.right, zeroY);
    ctx.stroke();
  }

  ctx.save();
  ctx.beginPath();
  ctx.rect(pad.left, pad.top, innerW, innerH);
  ctx.clip();

  ctx.strokeStyle = '#063f3b';
  ctx.lineWidth = 2.2;
  ctx.beginPath();
  let hasLinePoint = false;
  series.points.forEach(point => {
    if (point.period < xMin || point.period > xMax) return;
    const x = xScale(point.period);
    const y = yScale(point.value);
    if (!hasLinePoint) {
      ctx.moveTo(x, y);
      hasLinePoint = true;
    } else {
      ctx.lineTo(x, y);
    }
  });
  if (hasLinePoint) ctx.stroke();

  ctx.fillStyle = 'rgba(15, 118, 110, 0.26)';
  const pointSize = series.points.length > 1800 ? 1.2 : 1.8;
  series.points.forEach(point => {
    if (point.period < xMin || point.period > xMax || point.value < yMin || point.value > yMax) return;
    ctx.fillRect(xScale(point.period) - pointSize / 2, yScale(point.value) - pointSize / 2, pointSize, pointSize);
  });

  const selectedPeriod = Number(currentResult.period);
  const candidates = (currentResult.period_candidates || [])
    .map(candidate => Number(candidate.period))
    .filter(period => Number.isFinite(period) && period > 0)
    .filter(period => (
      !Number.isFinite(selectedPeriod)
      || Math.abs(period - selectedPeriod) / Math.max(period, selectedPeriod, 1e-9) >= 0.001
    ))
    .filter((period, index, periods) => periods.findIndex(other => Math.abs(other - period) / Math.max(period, 1e-9) < 0.001) === index)
    .slice(0, 6);
  candidates.forEach((period, index) => {
    const nearest = nearestPeriodogramPoint(series.points, period);
    if (!nearest || nearest.period < xMin || nearest.period > xMax || nearest.value < yMin || nearest.value > yMax) return;
    const x = xScale(nearest.period);
    const y = yScale(nearest.value);
    ctx.fillStyle = index === 0 ? '#0f766e' : '#b45309';
    ctx.strokeStyle = '#fbfcfd';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(x, y, index === 0 ? 4.5 : 3.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  });
  ctx.restore();

  candidates.forEach((period, index) => {
    drawPeriodogramMarker(
      geo,
      viewport,
      xScale,
      period,
      index === 0 ? '#0f766e' : '#b45309',
      index < 3 ? `${fmt(period, 4)} d` : '',
      (index + 1) * 15,
      true
    );
  });
  drawPeriodogramMarker(
    geo,
    viewport,
    xScale,
    selectedPeriod,
    '#202124',
    Number.isFinite(selectedPeriod) ? `Selected ${fmt(selectedPeriod, 4)} d` : 'Selected',
    0,
    false
  );
  drawPeriodogramLegend(geo, series);

  updateCanvasCursor(lastPointer);
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

  drawChartAxes(geo, viewport, {
    xDigits: 4,
    yDigits: 4,
    xLabel: 'Phase days from transit center',
    yLabel: 'Folded flux',
  });

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

  const transitModel = currentResult.transit_model;
  if (
    transitModel
    && Array.isArray(transitModel.folded_phase_days)
    && Array.isArray(transitModel.folded_flux)
  ) {
    ctx.strokeStyle = '#b45309';
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    let hasModelPoint = false;
    const modelCount = Math.min(transitModel.folded_phase_days.length, transitModel.folded_flux.length);
    for (let i = 0; i < modelCount; i++) {
      const phase = Number(transitModel.folded_phase_days[i]);
      const value = Number(transitModel.folded_flux[i]);
      if (!Number.isFinite(phase) || !Number.isFinite(value) || phase < xMin || phase > xMax) continue;
      const x = xScale(phase);
      const y = yScale(value);
      if (!hasModelPoint) {
        ctx.moveTo(x, y);
        hasModelPoint = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
    if (hasModelPoint) ctx.stroke();
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

  updateCanvasCursor(lastPointer);
}

function drawAuditPredictions(geo, viewport, metrics, xScale) {
  const events = predictedEphemerisEvents(metrics);
  if (!events.length) return;
  const { width, pad, innerH } = geo;
  const xMin = viewport.xMin;
  const xMax = viewport.xMax;
  ctx.save();
  ctx.beginPath();
  ctx.rect(pad.left, pad.top, geo.innerW, innerH);
  ctx.clip();

  events.forEach(event => {
    if (event.end < xMin || event.start > xMax) return;
    const x1 = Math.max(pad.left, xScale(event.start));
    const x2 = Math.min(width - pad.right, xScale(event.end));
    const centerX = xScale(event.center);
    if (x2 > x1) {
      ctx.fillStyle = 'rgba(37, 99, 235, 0.08)';
      ctx.fillRect(x1, pad.top, Math.max(1, x2 - x1), innerH);
    }
    if (centerX >= pad.left && centerX <= width - pad.right) {
      ctx.strokeStyle = 'rgba(37, 99, 235, 0.46)';
      ctx.lineWidth = 1.2;
      ctx.setLineDash([5, 5]);
      ctx.beginPath();
      ctx.moveTo(centerX, pad.top);
      ctx.lineTo(centerX, pad.top + innerH);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  });
  ctx.restore();
}

function drawAuditResiduals(geo, viewport, metrics, xScale) {
  if (!currentResult || !currentResult.transits.length) return;
  const { width, pad, innerH } = geo;
  const railY = pad.top + innerH - 15;
  ctx.save();
  ctx.beginPath();
  ctx.rect(pad.left, pad.top, geo.innerW, innerH);
  ctx.clip();

  currentResult.transits.forEach(transit => {
    if (transit.center < viewport.xMin || transit.center > viewport.xMax) return;
    const classification = classifyTransitForEphemeris(transit, metrics);
    if (!Number.isFinite(classification.predictedCenter)) return;
    const transitX = xScale(transit.center);
    const predictedX = xScale(classification.predictedCenter);
    if (
      (transitX < pad.left && predictedX < pad.left)
      || (transitX > width - pad.right && predictedX > width - pad.right)
    ) {
      return;
    }
    ctx.strokeStyle = classification.status === 'matched'
      ? 'rgba(21, 128, 61, 0.7)'
      : 'rgba(180, 35, 24, 0.72)';
    ctx.lineWidth = classification.status === 'matched' ? 1.4 : 2.2;
    ctx.setLineDash(classification.status === 'matched' ? [] : [4, 4]);
    ctx.beginPath();
    ctx.moveTo(Math.max(pad.left, Math.min(width - pad.right, predictedX)), railY);
    ctx.lineTo(Math.max(pad.left, Math.min(width - pad.right, transitX)), railY);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = classification.status === 'matched' ? '#15803d' : '#b42318';
    ctx.beginPath();
    ctx.arc(Math.max(pad.left, Math.min(width - pad.right, transitX)), railY, 3.5, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();
}

function drawAuditLegend(geo, metrics) {
  const { width, pad } = geo;
  const matchText = (
    Number.isFinite(Number(metrics.ephemerisMatchCount))
    && Number.isFinite(Number(metrics.ephemerisMatchFraction))
  )
    ? `Ephemeris fit ${metrics.ephemerisMatchCount}/${currentResult.transits.length}`
    : 'Ephemeris fit -';
  const items = [
    { color: '#2563eb', text: 'Predicted' },
    { color: '#15803d', text: 'Aligned' },
    { color: '#b42318', text: 'Off-period' },
    { color: '#202124', text: matchText },
  ];
  ctx.save();
  ctx.font = '700 11px system-ui, sans-serif';
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'left';
  const itemWidths = items.map(item => 18 + ctx.measureText(item.text).width + 10);
  const legendWidth = Math.min(
    width - pad.left - pad.right,
    itemWidths.reduce((sum, value) => sum + value, 0) + 12
  );
  const xStart = Math.max(pad.left + 8, width - pad.right - legendWidth - 6);
  let x = xStart + 8;
  const y = pad.top + 15;
  ctx.fillStyle = 'rgba(251, 252, 253, 0.88)';
  ctx.strokeStyle = 'rgba(215, 220, 227, 0.95)';
  ctx.lineWidth = 1;
  ctx.fillRect(xStart, pad.top + 4, legendWidth, 22);
  ctx.strokeRect(xStart, pad.top + 4, legendWidth, 22);
  items.forEach(item => {
    const widthNeeded = 18 + ctx.measureText(item.text).width + 10;
    if (x + widthNeeded > xStart + legendWidth) return;
    ctx.fillStyle = item.color;
    ctx.fillRect(x, y - 4, 9, 8);
    ctx.fillStyle = '#3f4650';
    ctx.fillText(item.text, x + 14, y);
    x += widthNeeded;
  });
  ctx.restore();
}

function drawChart() {
  resizeCanvas();
  const geo = getChartGeometry();
  const width = geo.width;
  const height = geo.height;
  ctx.clearRect(0, 0, width, height);
  if (!currentResult) return;

  if (currentView === 'periodogram') {
    drawPeriodogramChart(geo);
    return;
  }

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
  const auditMetrics = currentView === 'audit' ? currentAnalysisMetrics() : null;
  if (currentView === 'audit' && (!Number.isFinite(Number(auditMetrics.period)) || !Number.isFinite(Number(auditMetrics.periodEpoch)))) {
    drawNotice('Ephemeris audit needs a recovered period and epoch.', width, height);
    return;
  }
  if (currentView === 'audit') {
    drawAuditPredictions(geo, viewport, auditMetrics, xScale);
  }

  ctx.save();
  clipToChartPlot(geo);
  currentResult.transits.forEach((t, index) => {
    const paddedStart = Number(t.display_start);
    const paddedEnd = Number(t.display_end);
    const useDisplayBounds = currentView !== 'raw'
      && !t.manually_edited
      && Number.isFinite(paddedStart)
      && Number.isFinite(paddedEnd);
    const boxStart = useDisplayBounds ? paddedStart : t.start;
    const boxEnd = useDisplayBounds ? paddedEnd : t.end;
    if (boxEnd < xMin || boxStart > xMax) return;
    const range = transitFluxRange(t, flux);
    if (!range) return;
    const x1 = Math.max(pad.left, xScale(boxStart));
    const x2 = Math.min(width - pad.right, xScale(boxEnd));
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
    const auditClassification = auditMetrics ? classifyTransitForEphemeris(t, auditMetrics) : null;
    const auditMatched = auditClassification && auditClassification.status === 'matched';
    const auditOffPeriod = auditClassification && auditClassification.status === 'off';
    ctx.fillStyle = auditMatched
      ? 'rgba(21, 128, 61, 0.2)'
      : (auditOffPeriod ? 'rgba(180, 35, 24, 0.18)' : 'rgba(180, 83, 9, 0.22)');
    ctx.fillRect(x1, boxTop, boxWidth, boxHeight);
    const selected = index === selectedTransitIndex;
    ctx.strokeStyle = selected
      ? 'rgba(15, 118, 110, 1)'
      : (auditMatched ? 'rgba(21, 128, 61, 1)' : (auditOffPeriod ? 'rgba(180, 35, 24, 1)' : 'rgba(180, 83, 9, 1)'));
    ctx.lineWidth = selected ? 3.2 : 2.5;
    ctx.strokeRect(x1, boxTop, boxWidth, boxHeight);
    if (selected && canEditBoxes()) {
      ctx.fillStyle = 'rgba(15, 118, 110, 0.95)';
      ctx.fillRect(x1 - 3, boxTop, 6, boxHeight);
      ctx.fillRect(x1 + boxWidth - 3, boxTop, 6, boxHeight);
    }
    ctx.fillStyle = auditMatched ? '#166534' : (auditOffPeriod ? '#991b1b' : '#8a3f06');
    ctx.font = '700 12px system-ui, sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    if (boxWidth > 18 || currentView === 'zoom') {
      ctx.fillText(`T${index + 1}`, Math.max(pad.left + 4, x1 + 5), Math.max(pad.top + 4, boxTop + 5));
    }
  });
  ctx.restore();

  drawChartAxes(geo, viewport, {
    xDigits: 4,
    yDigits: 4,
    xLabel: 'Julian days',
    yLabel: currentView === 'raw' ? 'Flux' : (currentView === 'audit' ? 'Ephemeris audit' : 'Smoothed flux'),
  });

  ctx.save();
  clipToChartPlot(geo);
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

  if (hasTransitModel() && currentView !== 'raw') {
    const modelTimes = currentResult.transit_model.time;
    const modelFlux = currentResult.transit_model.flux;
    ctx.strokeStyle = '#b45309';
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    let hasModelPoint = false;
    const modelCount = Math.min(modelTimes.length, modelFlux.length);
    for (let i = 0; i < modelCount; i++) {
      const modelTime = Number(modelTimes[i]);
      const modelValue = Number(modelFlux[i]);
      if (!Number.isFinite(modelTime) || !Number.isFinite(modelValue) || modelTime < xMin || modelTime > xMax) continue;
      const x = xScale(modelTime);
      const y = yScale(modelValue);
      if (!hasModelPoint) {
        ctx.moveTo(x, y);
        hasModelPoint = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
    if (hasModelPoint) ctx.stroke();
  }
  ctx.restore();

  if (currentView === 'audit') {
    drawAuditResiduals(geo, viewport, auditMetrics, xScale);
    drawAuditLegend(geo, auditMetrics);
  }

  updateCanvasCursor(lastPointer);
}

window.addEventListener('resize', () => {
  updateSidebarWidth();
  drawChart();
});
