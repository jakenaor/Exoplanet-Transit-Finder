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
const sessionIndicatorEl = document.getElementById('sessionIndicator');
const saveLocationFormEl = document.getElementById('saveLocationForm');
const saveLocationInputEl = document.getElementById('saveLocationInput');
const saveLocationButtonEl = document.getElementById('saveLocationButton');
const saveLocationFileEl = document.getElementById('saveLocationFile');
const cacheSelectEl = document.getElementById('cacheSelect');
const loadCacheButtonEl = document.getElementById('loadCacheButton');
const refreshCachesButtonEl = document.getElementById('refreshCachesButton');
const loadCacheStatusEl = document.getElementById('loadCacheStatus');
const emptyEl = document.getElementById('empty');
const rowsEl = document.getElementById('transitRows');
const canvas = document.getElementById('chart');
const ctx = canvas.getContext('2d');
const viewButtons = [...document.querySelectorAll('.view-button[data-view]')];
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
const tlsMaxSignalsInput = document.getElementById('tlsMaxSignalsInput');
const perFileSettingsInput = document.getElementById('perFileSettings');
const batchSortInput = document.getElementById('batchSort');
const reconnectJobButton = document.getElementById('reconnectJobButton');
const metadataEl = document.getElementById('analysisMetadata');
const signalSelect = document.getElementById('signalSelect');
const showModelInput = document.getElementById('showModel');
const showLocalDipsInput = document.getElementById('showLocalDips');
const phaseScopeInput = document.getElementById('phaseScope');
const stackEventInput = document.getElementById('stackEvent');
const stackGroupInput = document.getElementById('stackGroup');
const stackIsolateInput = document.getElementById('stackIsolate');
const stackMedianInput = document.getElementById('stackMedian');
const stackRecenterInput = document.getElementById('stackRecenter');
const csvTimeFormatInput = document.getElementById('csvTimeFormat');
const csvTimeScaleInput = document.getElementById('csvTimeScale');
const csvTimeUnitInput = document.getElementById('csvTimeUnit');
const appShell = document.querySelector('main');
const MAX_BATCH_FILES = 100;
const JOB_POLL_INTERVAL_MS = 750;
const DEFAULT_SIDEBAR_WIDTH = 390;
const MIN_SIDEBAR_WIDTH = 320;
const MAX_SIDEBAR_WIDTH = 560;
const SESSION_QUERY_KEY = 'session';
const SESSION_ID_PATTERN = /^[a-zA-Z0-9_-]{8,80}$/;
const SESSION_SAVE_DELAY_MS = 350;
const SESSION_VIEWS = new Set(['zoom', 'clean', 'raw', 'phase', 'stack', 'periodogram', 'audit', 'comparison']);
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
let primaryResult = null;
let activeFileIndex = null;
let activeBatchId = null;
let pendingBatchFiles = [];
let jobConnectionLost = false;
let activeRequestId = null;
let resultViewports = new Map();
let currentView = 'zoom';
let currentViewport = null;
let dragState = null;
let lastPointer = null;
let sessionId = null;
let sessionInitialized = false;
let restoringSession = false;
let sessionSaveTimer = null;
let sessionSaveChain = Promise.resolve();
let sessionReadyPromise = null;
let knownSessionCaches = [];
const chartPad = { left: 72, right: 48, top: 42, bottom: 66 };

function nullableNumber(value) {
  if (value === null || value === undefined || typeof value === 'boolean' || (typeof value === 'string' && !value.trim())) return null;
  if (typeof value !== 'number' && typeof value !== 'string') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function isFiniteNumber(value) { return nullableNumber(value) !== null; }

function durationLabel(days) {
  const value = nullableNumber(days);
  if (value === null) return '-';
  return Math.abs(value) < 1 / 24 ? `${fmt(value * 1440, 2)} min` : `${fmt(value * 24, 3)} h`;
}

function fmtReference(value) {
  const number=nullableNumber(value);
  return number===null?'-':number.toFixed(8).replace(/\.?0+$/,'');
}

const fmt = (value, digits = 6) => {
  if (value === null || value === undefined || !isFiniteNumber(value)) return '-';
  const n = Number(value);
  if (Math.abs(n) >= 1000000 || (Math.abs(n) > 0 && Math.abs(n) < 0.001)) return n.toExponential(3);
  return Number.parseFloat(n.toFixed(digits)).toString();
};

const fmtPercent = value => {
  if (value === null || value === undefined || !isFiniteNumber(value)) return '-';
  const percent = Number(value) * 100;
  if (percent === 0) return '< 1e-12%';
  if (percent > 0 && percent < 0.000001) return '< 0.000001%';
  return `${fmt(percent, 6)}%`;
};

const fmtDepthPercent = value => {
  if (value === null || value === undefined || !isFiniteNumber(value)) return '-';
  return `${fmt(Number(value) * 100, 6)}%`;
};

const fmtPpm = value => {
  if (value === null || value === undefined || !isFiniteNumber(value)) return '-';
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

function generateSessionId() {
  if (window.crypto && typeof window.crypto.randomUUID === 'function') {
    return window.crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  const random = Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');
  return `session_${Date.now().toString(36)}_${random}`;
}

function ensureSessionId() {
  const url = new URL(window.location.href);
  const requested = url.searchParams.get(SESSION_QUERY_KEY);
  sessionId = requested && SESSION_ID_PATTERN.test(requested) ? requested : generateSessionId();
  if (requested !== sessionId) {
    url.searchParams.set(SESSION_QUERY_KEY, sessionId);
    window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`);
  }
  return sessionId;
}

function shortSessionId() {
  return sessionId ? sessionId.slice(0, 8) : '--------';
}

function setSessionIndicator(message, state = '', title = '') {
  if (!sessionIndicatorEl) return;
  sessionIndicatorEl.textContent = message;
  sessionIndicatorEl.className = `session-indicator${state ? ` ${state}` : ''}`;
  sessionIndicatorEl.title = title;
}

function setSaveFileLocation(directory, cacheFile = '') {
  if (!saveLocationInputEl || !saveLocationFileEl || !directory) return;
  const normalizedDirectory = String(directory).replace(/\/$/, '');
  const fullCacheFile = cacheFile || `${normalizedDirectory}/session-${sessionId}.json`;
  const filename = fullCacheFile.split('/').pop() || `session-${sessionId}.json`;
  saveLocationInputEl.value = normalizedDirectory;
  saveLocationInputEl.title = normalizedDirectory;
  saveLocationFileEl.textContent = `Current file: ${filename}`;
  saveLocationFileEl.className = 'save-location-file';
  saveLocationFileEl.title = fullCacheFile;
}

function setSaveLocationFeedback(message, isError = false) {
  if (!saveLocationFileEl) return;
  saveLocationFileEl.textContent = message;
  saveLocationFileEl.className = `save-location-file${isError ? ' error' : ''}`;
}

function formatCacheBytes(value) {
  const bytes = Math.max(0, Number(value) || 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatCacheDate(value) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return 'unknown date';
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function updateLoadCacheButton() {
  if (!cacheSelectEl || !loadCacheButtonEl) return;
  const selected = knownSessionCaches.find(item => item.session_id === cacheSelectEl.value);
  loadCacheButtonEl.disabled = !selected || !selected.loadable || selected.session_id === sessionId;
}

function renderSessionCacheList() {
  if (!cacheSelectEl || !loadCacheStatusEl) return;
  cacheSelectEl.replaceChildren();
  if (!knownSessionCaches.length) {
    const option = document.createElement('option');
    option.textContent = 'No saved sessions found';
    option.value = '';
    cacheSelectEl.append(option);
    cacheSelectEl.disabled = true;
    loadCacheStatusEl.textContent = 'Run an analysis to create a cache you can reopen here.';
    updateLoadCacheButton();
    return;
  }

  knownSessionCaches.forEach(item => {
    const option = document.createElement('option');
    const current = item.session_id === sessionId ? ' · current' : '';
    const unavailable = item.loadable ? '' : ' · too large';
    option.value = item.session_id;
    option.textContent = `${item.session_id.slice(0, 12)} · ${formatCacheDate(item.modified_at)} · ${formatCacheBytes(item.size_bytes)}${current}${unavailable}`;
    option.title = item.cache_file || item.cache_directory || '';
    option.disabled = !item.loadable;
    option.selected = item.session_id === sessionId;
    cacheSelectEl.append(option);
  });
  cacheSelectEl.disabled = false;
  if (!cacheSelectEl.value) {
    const firstLoadable = knownSessionCaches.find(item => item.loadable);
    if (firstLoadable) cacheSelectEl.value = firstLoadable.session_id;
  }
  loadCacheStatusEl.textContent = `${knownSessionCaches.length} saved session${knownSessionCaches.length === 1 ? '' : 's'} found, newest first.`;
  loadCacheStatusEl.className = 'load-cache-status';
  updateLoadCacheButton();
}

async function refreshSessionCacheList() {
  if (!cacheSelectEl || !loadCacheStatusEl) return;
  refreshCachesButtonEl.disabled = true;
  cacheSelectEl.disabled = true;
  loadCacheStatusEl.textContent = 'Refreshing saved sessions…';
  loadCacheStatusEl.className = 'load-cache-status';
  try {
    const response = await fetch('/analysis-sessions', { cache: 'no-store' });
    const payload = await readJsonResponse(response);
    if (!response.ok) throw new Error(payload.error || 'Could not find saved sessions.');
    knownSessionCaches = Array.isArray(payload.sessions) ? payload.sessions : [];
    renderSessionCacheList();
  } catch (error) {
    console.error('[session cache] list failed', error);
    knownSessionCaches = [];
    cacheSelectEl.replaceChildren();
    const option = document.createElement('option');
    option.textContent = 'Saved sessions unavailable';
    cacheSelectEl.append(option);
    loadCacheStatusEl.textContent = error.message;
    loadCacheStatusEl.className = 'load-cache-status error';
    updateLoadCacheButton();
  } finally {
    refreshCachesButtonEl.disabled = false;
  }
}

function sessionStateSnapshot() {
  return {
    ui_schema_version: 2,
    current_batch_index: currentBatchIndex,
    current_view: currentView,
    current_viewport: currentViewport,
    phase_scope: phaseScopeInput.value,
    current_signal_index: primaryResult?.signals?.indexOf(currentResult) ?? -1,
    current_signal_selection: signalSelect.value,
    active_job_id: activeAnalysisJobId,
    active_request_id: activeRequestId,
    active_file_index: activeFileIndex,
    batch_id: activeBatchId,
    pending_files: pendingBatchFiles,
    per_file_settings: perFileSettingsInput.value,
    detection_options: detectionOptions(),
    results: batchResults.map(item => ({
      file_name: String(item.file?.name || item.result?.source_file || 'unknown'),
      file_size: Number(item.file?.size) || 0,
      file_last_modified: Number(item.file?.lastModified) || null,
      result: item.result || null,
      error: item.error || null,
      status: item.status || (item.result ? 'completed' : item.error ? 'failed' : 'pending'),
    })),
  };
}

function persistSessionNow() {
  if (!sessionInitialized || restoringSession || !sessionId) return Promise.resolve(false);
  if (sessionSaveTimer !== null) {
    window.clearTimeout(sessionSaveTimer);
    sessionSaveTimer = null;
  }
  const snapshot = sessionStateSnapshot();
  setSessionIndicator(`Session ${shortSessionId()} · saving cache…`, 'saving');
  sessionSaveChain = sessionSaveChain.catch(() => false).then(async () => {
    try {
      const response = await fetch(`/analysis-sessions/${encodeURIComponent(sessionId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(snapshot),
      });
      const payload = await readJsonResponse(response);
      if (!response.ok) throw new Error(payload.error || 'Could not save this analysis session.');
      setSaveFileLocation(payload.cache_directory, payload.cache_file);
      setSessionIndicator(
        `Session ${shortSessionId()} · cache saved`,
        '',
        payload.cache_file || payload.cache_directory || ''
      );
      return true;
    } catch (error) {
      console.error('[session cache] save failed', error);
      setSessionIndicator(`Session ${shortSessionId()} · cache save failed`, 'error', error.message);
      return false;
    }
  });
  return sessionSaveChain;
}

function queueSessionSave() {
  if (!sessionInitialized || restoringSession) return;
  if (sessionSaveTimer !== null) window.clearTimeout(sessionSaveTimer);
  sessionSaveTimer = window.setTimeout(() => {
    sessionSaveTimer = null;
    persistSessionNow();
  }, SESSION_SAVE_DELAY_MS);
}

function applySavedDetectionOptions(options) {
  if (!options || typeof options !== 'object') return;
  const setValue = (input, value, fallback = '') => {
    input.value = value === null || value === undefined ? fallback : String(value);
  };
  setValue(strictnessInput, options.strictness, '1');
  setValue(smoothingInput, options.smoothing, '1');
  setValue(searchModeInput, options.searchMode, 'tls');
  setValue(tlsTemplateInput, options.tlsTemplate, 'default');
  setValue(stellarRadiusInput, options.stellarRadius);
  setValue(stellarMassInput, options.stellarMass);
  setValue(limbDarkeningU1Input, options.limbDarkeningU1);
  setValue(limbDarkeningU2Input, options.limbDarkeningU2);
  setValue(tlsOversamplingInput, options.tlsOversampling, '3');
  setValue(tlsMinTransitsInput, options.tlsMinTransits, '3');
  setValue(tlsMinDepthPpmInput, options.tlsMinDepthPpm, '10');
  setValue(tlsThreadsInput, options.tlsThreads, '4');
  setValue(tlsDurationGridStepInput, options.tlsDurationGridStep, '1.1');
  setValue(tlsMaxSignalsInput, options.tlsMaxSignals, '1');
  setValue(csvTimeFormatInput, options.csvTimeFormat, 'unknown');
  setValue(csvTimeScaleInput, options.csvTimeScale, 'unknown');
  setValue(csvTimeUnitInput, options.csvTimeUnit, 'days');
  setValue(minDepthInput, options.minDepth);
  setValue(minDurationInput, options.minDuration);
  setValue(maxDurationInput, options.maxDuration);
  setValue(minPeriodInput, options.minPeriod);
  setValue(maxPeriodInput, options.maxPeriod);
  updateDetectionReadouts();
}

function restoreSessionState(state) {
  if (!state || typeof state !== 'object' || !Array.isArray(state.results)) return 0;
  restoringSession = true;
  try {
    selectedFiles = [];
    selectedFile = null;
    batchResults = state.results.slice(0, MAX_BATCH_FILES).map(item => ({
      file: {
        name: String(item.file_name || item.result?.source_file || 'restored-analysis'),
        size: Number(item.file_size) || 0,
        lastModified: Number(item.file_last_modified) || 0,
        restored: true,
      },
      result: item.result && typeof item.result === 'object' ? item.result : null,
      error: item.error ? String(item.error) : null,
      status: item.status || (item.result ? 'completed' : item.error ? 'failed' : 'pending'),
    }));
    applySavedDetectionOptions(state.detection_options);
    perFileSettingsInput.value = typeof state.per_file_settings === 'string' ? state.per_file_settings : '';
    activeAnalysisJobId = typeof state.active_job_id === 'string' ? state.active_job_id : null;
    activeRequestId = typeof state.active_request_id === 'string' ? state.active_request_id : null;
    activeFileIndex = Number.isInteger(state.active_file_index) ? state.active_file_index : null;
    activeBatchId = state.batch_id || null;
    pendingBatchFiles = Array.isArray(state.pending_files) ? state.pending_files : [];
    jobConnectionLost = Boolean(activeAnalysisJobId || activeRequestId);
    reconnectJobButton.hidden = !jobConnectionLost;
    phaseScopeInput.value = state.phase_scope === 'orbit' ? 'orbit' : 'focus';
    currentView = SESSION_VIEWS.has(state.current_view) ? state.current_view : 'zoom';
    viewButtons.forEach(button => button.classList.toggle('active', button.dataset.view === currentView));
    currentBatchIndex = Number.isInteger(state.current_batch_index) ? state.current_batch_index : -1;
    if (!batchResults[currentBatchIndex]?.result) {
      currentBatchIndex = batchResults.findIndex(item => item.result);
    }
    updateSidebarWidth(batchResults.map(item => item.file));
    resetAnalysisProgress();
    renderBatchSelect();
    if (currentBatchIndex >= 0) {
      const item = batchResults[currentBatchIndex];
      selectedFile = item.file;
      primaryResult = item.result;
      currentResult = item.result.signals?.[state.current_signal_index] || item.result;
      currentViewport = validViewport(state.current_viewport) ? state.current_viewport : null;
      renderResult(currentResult);
      if(state.current_signal_selection==='combined'&&primaryResult.joint_model_comparison){signalSelect.value='combined';currentViewport=null;updateChartHeading();drawChart();}
    } else {
      clearResultView();
    }
    analyzeButton.disabled = true;
    fileInput.disabled = jobConnectionLost;
    dropzone.setAttribute('aria-disabled', String(jobConnectionLost));
    return batchResults.length;
  } finally {
    restoringSession = false;
  }
}

async function initializeSession() {
  ensureSessionId();
  setSessionIndicator(`Session ${shortSessionId()} · checking saved cache…`, 'saving');
  try {
    const response = await fetch(`/analysis-sessions/${encodeURIComponent(sessionId)}`, { cache: 'no-store' });
    const payload = await readJsonResponse(response);
    if (!response.ok) throw new Error(payload.error || 'Could not load this analysis session.');
    setSaveFileLocation(payload.cache_directory, payload.cache_file);
    sessionInitialized = true;
    if (payload.exists) {
      const restoredCount = restoreSessionState(payload.state);
      setSessionIndicator(
        `Session ${shortSessionId()} · restored from cache`,
        '',
        payload.cache_directory || ''
      );
      setStatus(
        restoredCount
          ? `Restored ${restoredCount} processed file${restoredCount === 1 ? '' : 's'} from this session.`
          : 'This session is ready. No files have been processed yet.'
      );
      return;
    }
    await persistSessionNow();
  } catch (error) {
    sessionInitialized = true;
    console.error('[session cache] load failed', error);
    setSessionIndicator(`Session ${shortSessionId()} · cache unavailable`, 'error', error.message);
  } finally {
    await refreshSessionCacheList();
  }
}

if (saveLocationFormEl) {
  saveLocationFormEl.addEventListener('submit', async event => {
    event.preventDefault();
    await sessionReadyPromise;
    const directory = saveLocationInputEl.value.trim();
    if (!directory) {
      setSaveLocationFeedback('Enter a save folder.', true);
      saveLocationInputEl.focus();
      return;
    }

    saveLocationButtonEl.disabled = true;
    setSaveLocationFeedback('Updating this session’s save folder…');
    try {
      const response = await fetch(
        `/analysis-sessions/${encodeURIComponent(sessionId)}/location`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ directory }),
        }
      );
      const payload = await readJsonResponse(response);
      if (!response.ok) throw new Error(payload.error || 'Could not update the save location.');
      setSaveFileLocation(payload.cache_directory, payload.cache_file);
      const saved = await persistSessionNow();
      if (saved) {
        setSessionIndicator(
          `Session ${shortSessionId()} · ${payload.moved ? 'cache moved' : 'save location updated'}`,
          '',
          payload.cache_file || payload.cache_directory || ''
        );
        await refreshSessionCacheList();
      }
    } catch (error) {
      console.error('[session cache] location update failed', error);
      setSaveLocationFeedback(error.message, true);
    } finally {
      saveLocationButtonEl.disabled = false;
    }
  });
}

if (cacheSelectEl) {
  cacheSelectEl.addEventListener('change', updateLoadCacheButton);
}

if (refreshCachesButtonEl) {
  refreshCachesButtonEl.addEventListener('click', refreshSessionCacheList);
}

if (loadCacheButtonEl) {
  loadCacheButtonEl.addEventListener('click', async () => {
    await sessionReadyPromise;
    const selectedSessionId = cacheSelectEl.value;
    const selected = knownSessionCaches.find(item => item.session_id === selectedSessionId);
    if (!selected || !selected.loadable || selectedSessionId === sessionId) return;
    if (batchInProgress) {
      loadCacheStatusEl.textContent = 'Wait for the active analysis to finish, or cancel it before loading another cache.';
      loadCacheStatusEl.className = 'load-cache-status error';
      return;
    }

    loadCacheButtonEl.disabled = true;
    loadCacheStatusEl.textContent = `Saving this session before loading ${selectedSessionId.slice(0, 12)}…`;
    const saved = await persistSessionNow();
    if (!saved) {
      loadCacheStatusEl.textContent = 'This session could not be saved, so the other cache was not loaded.';
      loadCacheStatusEl.className = 'load-cache-status error';
      updateLoadCacheButton();
      return;
    }

    const url = new URL(window.location.href);
    url.searchParams.set(SESSION_QUERY_KEY, selectedSessionId);
    window.location.assign(`${url.pathname}${url.search}${url.hash}`);
  });
}

function clampProgress(value) {
  if (!isFiniteNumber(value)) return 0;
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
  elapsedEl.textContent = `${state.label || 'Elapsed'} ${formatJobElapsed(liveSeconds)}`;
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
      <div class="progress-eta" data-progress-eta></div>
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
  setIndeterminateFileProgress(index, 'Uploading');
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
  setProgressEta(index,'');
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
  if (!item.result) return { label: item.status || 'Pending', meta: 'No completed result', status: 'pending', score: null, transits: null };
  const assessment = assessmentForResult(item.result);
  const transitCount = item.result.transits.length;
  return {
    label: assessment.shortLabel,
    meta: `${item.result.observed_events?.length ?? '-'} supported / ${transitCount} windows · P ${fmt(item.result.period, 5)} d · SDE ${fmt(item.result.period_sde, 1)} · SNR ${fmt(item.result.tls_snr ?? item.result.detection_snr, 1)} · ${durationLabel(item.result.period_duration)}${item.result.warnings?.some(w => w.severity === 'danger') ? ' · review warnings' : ''}`,
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
  const disabled = successCount === 0;

  batchPicker.hidden = false;
  batchPickerButton.disabled = disabled;
  batchPickerButton.className = `batch-picker-button ${activeDetail.status}`;
  batchPickerTitle.textContent = activeItem ? activeItem.file.name : (batchResults.length ? 'No successful file selected' : 'No processed files');
  batchPickerMeta.textContent = activeItem
    ? `${activeDetail.score === null ? 'No score' : `${activeDetail.score}/100 candidate score`} · ${activeDetail.label} · ${activeDetail.meta}`
    : (batchResults.length && successCount === 0 ? 'All processed files failed.' : 'Run analysis to populate this list.');
  batchPickerList.hidden = batchPickerList.hidden || disabled;
  batchPickerButton.setAttribute('aria-expanded', batchPickerList.hidden ? 'false' : 'true');
  const focusIndex = document.activeElement?.dataset?.batchIndex;
  const scrollTop = batchPickerList.scrollTop;
  batchPickerList.innerHTML = sortedBatchEntries().map(({item, index}) => {
    const selected = index === currentBatchIndex;
    const detail = batchResultDetail(item);
    const disabledAttribute = !item.result ? ' disabled aria-disabled="true"' : '';
    const scoreHtml = detail.score === null
      ? ''
      : `<span class="batch-score ${detail.status}" aria-label="Candidate score ${detail.score} out of 100">${detail.score}/100</span>`;
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
  batchPickerList.scrollTop = scrollTop;
  if (focusIndex !== undefined && !batchPickerList.hidden) batchPickerList.querySelector(`[data-batch-index="${focusIndex}"]`)?.focus({preventScroll:true});
}

function sortedBatchEntries() {
  const entries = batchResults.map((item,index) => ({item,index}));
  const sort = batchSortInput?.value || 'index';
  return entries.sort((a,b) => {
    if (sort === 'name') return a.item.file.name.localeCompare(b.item.file.name);
    if (sort === 'score') return (assessmentForResult(b.item.result)?.candidateScore ?? -1) - (assessmentForResult(a.item.result)?.candidateScore ?? -1);
    if (sort === 'period') return (nullableNumber(a.item.result?.period) ?? Infinity) - (nullableNumber(b.item.result?.period) ?? Infinity);
    return a.index-b.index;
  });
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

  resultSelect.disabled = successCount === 0;
  resultSelect.innerHTML = batchResults.map((item, index) => {
    const selected = index === currentBatchIndex ? ' selected' : '';
    const disabled = !item.result ? ' disabled' : '';
    const detail = !item.result
      ? (item.error ? (item.error === 'Cancelled' ? 'cancelled' : 'failed') : (item.status || 'pending').replaceAll('_',' '))
      : `${assessmentForResult(item.result).shortLabel}; ${item.result.transits.length} covered windows`;
    return `<option value="${index}"${selected}${disabled}>${index + 1}. ${escapeHtml(item.file.name)} (${detail})</option>`;
  }).join('');
  renderBatchPicker();
  syncExportButtons();
}

function setFiles(fileList) {
  if (batchInProgress || activeAnalysisJobId || jobConnectionLost) { setStatus('Reconnect to or cancel the current job before replacing files. Completed results remain available below.'); return; }
  const files = Array.from(fileList || []);
  selectedFiles = files.slice(0, MAX_BATCH_FILES);
  renderPerFileTarget();
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
  queueSessionSave();
}

function optionalNumber(input) {
  return nullableNumber(input?.value);
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
    tlsMaxSignals: optionalNumber(tlsMaxSignalsInput) ?? 1,
    csvTimeFormat: csvTimeFormatInput.value,
    csvTimeScale: csvTimeScaleInput.value,
    csvTimeUnit: csvTimeUnitInput.value,
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
  [strictnessInput, minDepthInput, minDurationInput, maxDurationInput].forEach(input => { input.disabled = false; });
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
  tlsMaxSignalsInput.value = '1';
  csvTimeFormatInput.value = 'unknown';
  csvTimeScaleInput.value = 'unknown';
  csvTimeUnitInput.value = 'days';
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
  queueSessionSave();
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
  primaryResult = null;
  updateInspectorControls();
  currentViewport = null;
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
    <div class="metric"><span>Local median depth</span><span>-</span></div>
    <div class="metric"><span>Radius ratio</span><span>-</span></div>
    <div class="metric"><span>Depth SNR</span><span>-</span></div>
    <div class="metric"><span>Period SDE</span><span>-</span></div>
    <div class="metric"><span>TLS false-alarm probability</span><span>-</span></div>
    <div class="metric"><span>Measured timing agreement</span><span>-</span></div>
    <div class="metric"><span>Approx. model-vs-flat p-value</span><span>-</span></div>
    <div class="metric"><span>Reduced chi-sq</span><span>-</span></div>
    <div class="metric"><span>Time reference</span><span>-</span></div>
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
  formData.append('tlsMaxSignals', options.tlsMaxSignals ?? 1);
  formData.append('csvTimeFormat', options.csvTimeFormat || 'unknown');
  formData.append('csvTimeScale', options.csvTimeScale || 'unknown');
  formData.append('csvTimeUnit', options.csvTimeUnit || 'days');
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

class AnalysisDisconnectedError extends Error {}

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
    if (progressElapsedStates[index]) progressElapsedStates[index].label='Queue wait';
    const position = nullableNumber(job.queue_position);
    const label = position !== null ? `Queued #${position}` : 'Queued';
    setIndeterminateFileProgress(index, label);
    setProgressEta(index, 'Queue wait is separate from search time.');
    return;
  }
  if (progressElapsedStates[index]) progressElapsedStates[index].label='Elapsed';
  const engine = searchMode === 'tls' ? 'TLS' : 'Analysis';
  if (job.status === 'cancelling') {
    setIndeterminateFileProgress(index, job.stage_label || 'Cancelling…');
  } else if (job.status === 'running') {
    setIndeterminateFileProgress(index, job.stage_label || `${engine} running`);
  }
  const progress = { ...job, ...(job.progress_details || job.progress || {}) };
  const completed = nullableNumber(progress.completed_trials ?? progress.work_completed);
  const total = nullableNumber(progress.total_trials ?? progress.work_total);
  const range = progress.remaining_seconds_range || [progress.eta_lower_seconds, progress.eta_upper_seconds];
  const low = nullableNumber(range?.[0]); const high = nullableNumber(range?.[1]);
  const counts = completed !== null && total > 0 ? `${completed.toLocaleString()} / ${total.toLocaleString()} period trials. ` : '';
  if (!active || job.status === 'cancelling') setProgressEta(index, '');
  else if(job.stage==='tls_finalizing' || progress.search_complete) setProgressEta(index,'Finalizing the model and diagnostics; completion ETA unavailable.');
  else if (low !== null && high !== null && high > 0 && job.status === 'running') {
    const lower = Math.max(1, Math.floor(low / 60)); const upper = Math.max(lower + 1, Math.ceil(high / 60));
    setProgressEta(index, `${counts}Search time remaining: about ${lower}–${upper} min.`);
  } else if (job.status === 'running') setProgressEta(index, `${counts}${/search|TLS|period/i.test(job.stage_label || '') ? 'Search ETA: estimating…' : 'Finalization in progress; completion ETA unavailable.'}`);
}

function setProgressEta(index, label) {
  const row = analysisProgressEl?.querySelector(`[data-progress-index="${index}"]`);
  const element = row?.querySelector('[data-progress-eta]');
  if (element) element.textContent = label;
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

async function analyzeFile(file, options, onJobUpdate = () => {}, existingJobId = null) {
  activeRequestId = existingJobId ? (activeRequestId || `${activeBatchId}:${activeFileIndex}`) : `${activeBatchId}:${activeFileIndex}`;
  await persistSessionNow();
  const formData = new FormData();
  if (!existingJobId) formData.append('datafile', file);
  formData.append('batchId', activeBatchId || '');
  formData.append('analysisRequestId', activeRequestId);
  appendDetectionOptions(formData, options);
  let submittedJob = {job_id: existingJobId, status:'running'};
  if (!existingJobId) {
    let response;
    for (let attempt=0; attempt<3; attempt++) {
      try {
        response = await fetch('/analysis-jobs', { method: 'POST', body: formData });
        submittedJob = await readJsonResponse(response);
        break;
      } catch (error) {
        if (attempt === 2) {
          const lookup=await lookupRequest(activeRequestId).catch(()=>null);
          if (lookup) {submittedJob=lookup;response={ok:true};break;}
          jobConnectionLost=true;
          throw new AnalysisDisconnectedError('Submission response was lost. Reconnect to resolve this request before starting another search.');
        }
        await wait(JOB_POLL_INTERVAL_MS);
      }
    }
    if (!response.ok) throw new Error(submittedJob.error || 'Analysis could not be started.');
  }
  if (!submittedJob.job_id) throw new Error('Server did not return an analysis job ID.');

  const jobId = submittedJob.job_id;
  activeAnalysisJobId = jobId;
  jobConnectionLost = false;
  reconnectJobButton.hidden = true;
  await persistSessionNow();
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
        if (failedPolls >= 5) { jobConnectionLost = true; throw new AnalysisDisconnectedError(`Connection lost. Reconnect to the existing job; it may still be running. ${error.message}`); }
        await wait(JOB_POLL_INTERVAL_MS);
        continue;
      }

      onJobUpdate(job);
      if (job.status === 'completed') {
        const payload = job.result;
        if (!payload) throw new Error('Completed analysis did not include a result.');
        payload.source_file = file.name;
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
    if (activeAnalysisJobId === jobId && !jobConnectionLost) {activeAnalysisJobId = null;activeRequestId=null;}
  }
}

function validViewport(value) {
  return value && ['xMin','xMax','yMin','yMax'].every(k => isFiniteNumber(value[k])) && value.xMax > value.xMin && value.yMax > value.yMin;
}

function selectBatchResult(index) {
  const item = batchResults[index];
  if (!item || !item.result) return;
  if (currentBatchIndex >= 0) resultViewports.set(`${currentBatchIndex}:${currentView}`,currentViewport);
  currentBatchIndex = index;
  selectedFile = item.file;
  primaryResult = item.result;
  currentResult = item.result;
  currentViewport = resultViewports.get(`${index}:${currentView}`) || null;
  stackEventInput.value = 'all';
  renderBatchSelect();
  renderResult(currentResult);
  if (!batchInProgress) setStatus(`Showing ${item.file.name}.`);
  queueSessionSave();
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
  tlsMaxSignalsInput,
  csvTimeFormatInput,csvTimeScaleInput,csvTimeUnitInput,
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
  if (batchInProgress || activeAnalysisJobId || jobConnectionLost) return;
  if (event.dataTransfer.files.length) {
    fileInput.files = event.dataTransfer.files;
    setFiles(event.dataTransfer.files);
  }
});

cancelAnalysisButton.addEventListener('click', async () => {
  if ((!batchInProgress && !activeAnalysisJobId && !activeRequestId) || analysisCancelRequested) return;
  analysisCancelRequested = true;
  cancelAnalysisButton.disabled = true;
  setStatus('Cancelling the active analysis…');
  try {
    if(!activeAnalysisJobId && activeRequestId && !batchInProgress) {
      const job=await lookupRequest(activeRequestId);
      if(job)activeAnalysisJobId=job.job_id;
      else {
        activeRequestId=null;activeFileIndex=null;jobConnectionLost=false;
        reconnectJobButton.hidden=true;cancelAnalysisButton.hidden=true;lockBatchInputs(false);
        setStatus('No active server job was found. Completed results remain available.');await persistSessionNow();return;
      }
    }
    if (!activeAnalysisJobId) return;
    await requestJobCancellation(activeAnalysisJobId);
    if (!batchInProgress) {
      const item=batchResults[activeFileIndex];
      if(item){item.error='Cancelled';item.status='cancelled';}
      activeAnalysisJobId=null;activeFileIndex=null;activeRequestId=null;jobConnectionLost=false;
      reconnectJobButton.hidden=true;cancelAnalysisButton.hidden=true;
      lockBatchInputs(false);renderBatchSelect();await persistSessionNow();
      setStatus('Cancellation requested. Completed results remain available.');
    }
  } catch (error) {
    analysisCancelRequested=false;cancelAnalysisButton.disabled=false;
    setStatus(error.message, true);
  }
});

function readPerFileSettings() {
  const text = perFileSettingsInput.value.trim();
  if (!text) return {};
  const parsed = JSON.parse(text);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error('Per-file settings must be a JSON object keyed by filename.');
  const allowed = new Set(Object.keys(detectionOptions()));
  for (const [filename, values] of Object.entries(parsed)) {
    if (!values || Array.isArray(values) || typeof values !== 'object') throw new Error(`Settings for ${filename} must be an object.`);
    for (const key of Object.keys(values)) if (!allowed.has(key)) throw new Error(`Unknown per-file setting: ${key}`);
  }
  return parsed;
}

function renderPerFileTarget() {
  const select=document.getElementById('perFileTarget');
  select.innerHTML=selectedFiles.length
    ? selectedFiles.map(file=>`<option value="${escapeHtml(file.name)}">${escapeHtml(file.name)}</option>`).join('')
    : '<option value="">Choose source files first</option>';
}

function updatePerFileSettings(remove=false) {
  if(batchInProgress || activeAnalysisJobId || jobConnectionLost)return;
  const filename=document.getElementById('perFileTarget').value;
  if(!filename){setStatus('Choose source files before assigning per-file settings.');return;}
  try {
    const overrides=readPerFileSettings();
    if(remove)delete overrides[filename];else overrides[filename]=detectionOptions();
    perFileSettingsInput.value=Object.keys(overrides).length?JSON.stringify(overrides,null,2):'';
    document.getElementById('perFileSettingsStatus').textContent=remove?`${filename} will use the batch defaults.`:`Current settings saved for ${filename}. Changes above now affect the remaining batch defaults.`;
    queueSessionSave();
  } catch(error){setStatus(error.message,true);}
}

function lockBatchInputs(locked) {
  fileInput.disabled = locked;
  dropzone.setAttribute('aria-disabled', String(locked));
  analyzeButton.disabled = locked || !selectedFiles.length;
  perFileSettingsInput.disabled = locked;
}

async function executeBatch(startIndex = 0, resumeJobId = null) {
  if (batchInProgress) return;
  batchInProgress = true;
  jobConnectionLost = false;
  analysisCancelRequested = false;
  lockBatchInputs(true);
  cancelAnalysisButton.hidden = false;
  cancelAnalysisButton.disabled = false;
  reconnectJobButton.hidden = true;
  renderBatchSelect();
  try {
    for (let index=startIndex; index<batchResults.length; index++) {
      const item=batchResults[index];
      if (item.result || item.error) continue;
      const existing = index === startIndex ? resumeJobId : null;
      if (!existing && !(item.file instanceof Blob)) {
        item.status='needs_reselection';
        setFileProgress(index,0,'Reselect source file','pending');
        continue;
      }
      activeFileIndex=index;
      item.status='running';
      if (pendingBatchFiles[index]) pendingBatchFiles[index].status='running';
      setStatus(`Analyzing ${index+1}/${batchResults.length}: ${item.file.name}`);
      beginFileProgress(index);
      try {
        item.result=await analyzeFile(item.file, item.options || pendingBatchFiles[index]?.options || detectionOptions(),
          job=>updateProgressFromJob(index,job,(item.options || detectionOptions()).searchMode),existing);
        item.status='completed'; item.error=null;
        finishFileProgress(index,'complete');
        if (currentBatchIndex === -1) selectBatchResult(index);
      } catch (error) {
        if (error instanceof AnalysisDisconnectedError) {
          item.status='disconnected';
          setStatus(error.message,true);
          reconnectJobButton.hidden=false;
          pauseProgressElapsed(index);
          setProgressEta(index,'Connection lost. Reconnect to update the existing job.');
          break;
        }
        item.error=error instanceof AnalysisCancelledError ? 'Cancelled' : error.message;
        item.status=error instanceof AnalysisCancelledError ? 'cancelled' : 'failed';
        finishFileProgress(index,item.status === 'cancelled' ? 'cancelled' : 'failed');
        if (error instanceof AnalysisCancelledError) {
          for (let j=index+1;j<batchResults.length;j++) {
            if (!batchResults[j].result) { batchResults[j].status='cancelled'; batchResults[j].error='Cancelled'; setFileProgress(j,0,'Not started','cancelled'); }
          }
          break;
        }
      }
      if (pendingBatchFiles[index]) pendingBatchFiles[index].status=item.status;
      renderBatchSelect();
      await persistSessionNow();
    }
    if (!jobConnectionLost) {
      const completed=batchResults.filter(item=>item.result);
      const failed=batchResults.filter(item=>item.error);
      const remaining=batchResults.filter(item=>!item.result&&!item.error);
      const candidates=completed.filter(item=>['strong_candidate','possible_candidate'].includes(assessmentForResult(item.result).status)).length;
      setStatus(remaining.length
        ? `${completed.length} results available. Reselect ${remaining.length} unsubmitted source file(s) to continue; their bytes were not cached.`
        : `Batch ${analysisCancelRequested ? 'cancelled' : 'complete'}: ${completed.length}/${batchResults.length} processed, ${candidates} candidate-like${failed.length ? `, ${failed.length} failed or cancelled` : ''}.`);
    }
  } finally {
    stopProgressTimer();
    batchInProgress=false;
    if (!jobConnectionLost) { activeAnalysisJobId=null; activeFileIndex=null;activeRequestId=null; }
    lockBatchInputs(jobConnectionLost);
    cancelAnalysisButton.hidden=!jobConnectionLost;
    cancelAnalysisButton.disabled=false;
    renderBatchSelect();
    await persistSessionNow();
  }
}

analyzeButton.addEventListener('click', async () => {
  if (batchInProgress || activeAnalysisJobId || activeRequestId || !selectedFiles.length) return;
  let overrides;
  try { overrides=readPerFileSettings(); } catch(error) { setStatus(error.message,true); return; }
  await sessionReadyPromise;
  if (batchInProgress || activeAnalysisJobId || activeRequestId) return;
  const options=detectionOptions();
  activeBatchId=generateSessionId();
  batchResults=selectedFiles.slice(0,MAX_BATCH_FILES).map(file=>({file,result:null,error:null,status:'pending',options:{...options,...(overrides[file.name]||{})}}));
  pendingBatchFiles=batchResults.map(item=>({file_name:item.file.name,file_size:item.file.size,file_last_modified:item.file.lastModified,options:item.options,status:'pending'}));
  currentBatchIndex=-1;
  resultViewports.clear();
  renderProgressRows(batchResults.map(item=>item.file));
  clearResultView();
  await executeBatch();
});

reconnectJobButton.addEventListener('click', async () => {
  if (batchInProgress || activeFileIndex === null) return;
  try {
    if(!activeAnalysisJobId && activeRequestId) {
      const job=await lookupRequest(activeRequestId);
      if(job)activeAnalysisJobId=job.job_id;
      else if(!(batchResults[activeFileIndex]?.file instanceof Blob)) {
        activeRequestId=null;jobConnectionLost=false;reconnectJobButton.hidden=true;lockBatchInputs(false);
        setStatus('No server job was found for the saved request. Reselect the unsubmitted source file to run it.');await persistSessionNow();return;
      }
    }
    renderProgressRows(batchResults.map(item=>item.file));
    await executeBatch(activeFileIndex,activeAnalysisJobId);
  } catch(error) {setStatus(`Could not reconnect: ${error.message}`,true);}
});

async function lookupRequest(requestId) {
  const response=await fetch(`/analysis-jobs?request_id=${encodeURIComponent(requestId)}`,{cache:'no-store'});
  if(response.status===404)return null;
  const job=await readJsonResponse(response);
  if(!response.ok)throw new Error(job.error||'Could not resolve the analysis request.');
  return job;
}

batchSortInput.addEventListener('change',renderBatchPicker);

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
    resultViewports.set(`${currentBatchIndex}:${currentView}`,currentViewport);
    currentView = button.dataset.view;
    if(signalSelect.value==='combined'&&currentView!=='comparison'){
      currentResult=primaryResult?.signals?.[0]||primaryResult;signalSelect.value='0';renderMetrics();renderSignalPicker();
    }
    currentViewport = resultViewports.get(`${currentBatchIndex}:${currentView}`) || null;
    viewButtons.forEach(item => item.classList.toggle('active', item === button));
    updateChartHeading();
    drawChart();
    queueSessionSave();
  });
});

function hasPhaseFold() {
  return Boolean(currentResult && currentResult.phase_folded && currentResult.phase_folded.phase.length);
}

function hasTransitStack() {
  return Boolean(
    currentResult
    && currentResult.transit_stack
    && Array.isArray(currentResult.transit_stack.traces)
    && currentResult.transit_stack.traces.length
  );
}

function hasTransitModel() {
  return Boolean(
    showModelInput.checked
    && currentResult
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
  const hasSde = sdes.some(value => value !== null && value !== undefined && isFiniteNumber(value));
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
    fullCount: isFiniteNumber(payload.point_count) ? Number(payload.point_count) : points.length,
    shownCount: isFiniteNumber(payload.shown_count) ? Number(payload.shown_count) : points.length,
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
  updateInspectorControls();
  if (!currentResult) {
    chartTitleEl.textContent = 'Flux Over Time';
    subtitleEl.textContent = 'Transit boxes appear after analysis.';
    return;
  }

  if (currentView === 'phase') {
    chartTitleEl.textContent = 'Phase-Folded Light Curve';
    if (hasPhaseFold()) {
      subtitleEl.textContent = `Global periodic-signal check: ${currentResult.phase_folded.phase.length.toLocaleString()} folded samples at P = ${fmt(currentResult.phase_folded.period)} days. Use Full orbit to inspect secondary dips and orbital trends.`;
    } else {
      subtitleEl.textContent = 'Phase folding needs a detected orbital period.';
    }
    return;
  }

  if (currentView === 'stack') {
    chartTitleEl.textContent = 'Transit Stack Inspector';
    if (hasTransitStack()) {
      const traceCount = currentResult.transit_stack.traces.length;
      subtitleEl.textContent = `Event-by-event consistency: ${traceCount.toLocaleString()} local windows aligned on the ephemeris. Select an event to inspect depth, coverage, and timing. This is not an independent periodic-signal confirmation.`;
    } else {
      subtitleEl.textContent = 'Transit stacking needs detected transits; reanalyze older saved results to generate it.';
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
    if (!isFiniteNumber(metrics.period) || !isFiniteNumber(metrics.periodEpoch)) {
      subtitleEl.textContent = 'Audit view needs a recovered period and epoch.';
    } else if (
      isFiniteNumber(metrics.ephemerisMatchCount)
      && isFiniteNumber(metrics.ephemerisMatchFraction)
    ) {
      const matchCount = Number(metrics.ephemerisMatchCount);
      const total = currentResult.transits.length;
      subtitleEl.textContent = `${matchCount} independently supported events align with the ${fmt(metrics.period, 5)} day ephemeris; ${total} predicted windows. Timing is available only where independently measured.`;
    } else {
      subtitleEl.textContent = `Predicted windows are shown for the ${fmt(metrics.period, 5)} day ephemeris.`;
    }
    return;
  }

  if (currentView === 'comparison') {
    chartTitleEl.textContent = 'Fit and Residuals';
    subtitleEl.textContent = comparisonPayload()?.representation || 'Matched search data and evaluated model; residuals are observations minus model. Reanalyze legacy caches to generate this view.';
    return;
  }
  chartTitleEl.textContent = 'Flux Over Time';
  subtitleEl.textContent = `${currentResult.plot.time.length.toLocaleString()} plotted points from ${currentResult.total_points.toLocaleString()} samples. Days since ${fmtReference(currentResult.time_reference)}; ${currentResult.input_metadata?.time_format || 'time convention unverified'}.`;
}

function ephemerisDiagnosticsForTransits(transits, period, epoch, duration, expectedCount, observedRanges = null) {
  const centers = transits
    .map(transit => nullableNumber(transit.center))
    .filter(value => Number.isFinite(value));
  const durations = transits
    .map(transit => nullableNumber(transit.duration))
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
    .map(transit => nullableNumber(transit.duration))
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
    !isFiniteNumber(matchCount)
    || !isFiniteNumber(eventCount)
    || !isFiniteNumber(expectedCoverage)
    || !isFiniteNumber(transitCount)
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
  const measuredCenter=nullableNumber(transit.measured_center);
  if (measuredCenter === null && (transit.source === 'TLS model' || transit.state)) {
    return {status:'unknown',residual:null,tolerance:null,predictedCenter:null};
  }
  const tolerance = ephemerisTolerance(metrics.period, metrics.periodDuration, currentResult ? currentResult.transits : []);
  const residual = ephemerisResidual(measuredCenter ?? transit.center, metrics.period, metrics.periodEpoch);
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
    .map(eventSignedDepthFraction)
    .filter(Number.isFinite);
  const radiusRatios = currentResult.transits
    .map(transit => nullableNumber(transit.radius_ratio))
    .filter(value => Number.isFinite(value) && value >= 0);
  const transitPoints = currentResult.transits
    .map(transit => nullableNumber(transit.points))
    .filter(value => Number.isFinite(value) && value >= 0);
  const metrics = {
    period: currentResult.period,
    periodMethod: currentResult.period_method,
    periodScatter: currentResult.period_scatter,
    periodUncertainty: currentResult.period_uncertainty,
    periodMatchCount: currentResult.period_match_count,
    pValue: currentResult.p_value,
    deltaChiSquared: currentResult.delta_chi_squared,
    reducedChiSquared: currentResult.reduced_chi_squared_box,
    periodEpoch: isFiniteNumber(currentResult.period_epoch)
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
    oddEvenDepthMismatch: currentResult.odd_even_depth_mismatch,
    depthScatterRatio: currentResult.depth_scatter_ratio,
    medianTransitPoints: median(transitPoints),
    maxRadiusRatio: radiusRatios.length ? Math.max(...radiusRatios) : null,
  };

  const diagnostics = currentResult.diagnostics || {};
  const keys = {
    ephemeris_match_count:'ephemerisMatchCount', ephemeris_match_fraction:'ephemerisMatchFraction',
    ephemeris_event_match_count:'ephemerisEventMatchCount', ephemeris_event_match_fraction:'ephemerisEventMatchFraction',
    off_ephemeris_transit_count:'offEphemerisTransitCount', off_ephemeris_fraction:'offEphemerisFraction',
    expected_transit_count:'expectedTransitCount', expected_transit_coverage:'expectedTransitCoverage',
    timing_residual_median:'timingResidualMedian',timing_residual_tolerance:'timingResidualTolerance',timing_residual_ratio:'timingResidualRatio',
  };
  for(const [source,destination] of Object.entries(keys)) metrics[destination]=nullableNumber(diagnostics[source]);
  metrics.observedEventCount=Array.isArray(currentResult.observed_events)?currentResult.observed_events.length:null;
  if (metrics.periodMethod === 'TLS' && !Array.isArray(currentResult.observed_events)) {
    metrics.ephemerisMatchCount=null;metrics.ephemerisMatchFraction=null;
  }

  return metrics;
}

function currentWarnings() {
  if (!currentResult) return [];
  return Array.isArray(currentResult.warnings) ? currentResult.warnings : [
    { severity: 'info', title: 'Legacy analysis', detail: 'Saved warnings are unavailable. Reanalyze to run current checks.' },
  ];
}

function currentPlanetAssessment(metrics = null, warnings = null) {
  if (!currentResult) return null;
  const saved = currentResult.planet_assessment;
  if (!saved || typeof saved !== 'object') return {
    status: 'legacy_unknown', title: 'Legacy analysis — assessment unavailable',
    shortLabel: 'Legacy / unassessed', candidateScore: null,
    summary: 'This cache has no saved backend assessment. Its measurements remain available.',
    recommendation: 'Reanalyze the source file to apply current checks.', supportingEvidence: [], limitingEvidence: [],
  };
  return {
    ...saved, shortLabel: saved.short_label || saved.shortLabel || saved.title || 'Unassessed',
    candidateScore: nullableNumber(saved.candidate_score ?? saved.candidateScore),
    supportingEvidence: saved.supporting_evidence || saved.supportingEvidence || [],
    limitingEvidence: saved.limiting_evidence || saved.limitingEvidence || [],
    summary: saved.summary || '', recommendation: saved.recommendation || '',
  };
}

function assessmentForResult(result) {
  if (!result) return {shortLabel:'Pending',candidateScore:null,status:'pending'};
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
  return items.slice(0, 6).map(item => `
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
    [...assessment.limitingEvidence, ...assessment.supportingEvidence]
  );
  assessmentEl.innerHTML = `
    <div class="assessment-card ${assessment.status}">
      <div class="assessment-head">
        <strong>${escapeHtml(assessment.title)}</strong>
        <span>${assessment.candidateScore === null ? 'Unscored' : `Candidate score ${assessment.candidateScore}/100`}</span>
      </div>
      <p>${escapeHtml(assessment.summary)}</p>
      <div class="score-track" aria-label="Candidate score">
        <div class="score-fill" style="width: ${assessment.candidateScore ?? 0}%;"></div>
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
      <strong>${escapeHtml(warning.title)}</strong>
      <span>${escapeHtml(warning.detail)}</span>
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
    <div class="metric"><span>Supported events / covered windows</span><span>${metrics.observedEventCount ?? 'unverified'} / ${currentResult.transits.length}</span></div>
    <div class="metric"><span>All predicted windows</span><span>${currentResult.predicted_windows?.length ?? 'not recorded'}</span></div>
    <div class="metric"><span>Orbital period</span><span>${period}</span></div>
    <div class="metric"><span>Period uncertainty</span><span>${metrics.periodUncertainty === null || metrics.periodUncertainty === undefined ? '-' : `± ${fmt(metrics.periodUncertainty, 6)} days`}</span></div>
    <div class="metric"><span>Local median depth</span><span>${fmtDepthPercent(metrics.medianDepthFraction)} / ${fmtPpm(metrics.medianDepthFraction === null ? null : metrics.medianDepthFraction * 1000000)} ppm</span></div>
    <div class="metric"><span>Radius ratio</span><span>${fmt(metrics.medianRadiusRatio)}</span></div>
    <div class="metric"><span>${metrics.periodMethod === 'TLS' ? 'TLS SNR' : 'Depth SNR'}</span><span>${fmt(metrics.detectionSnr, 2)}</span></div>
    <div class="metric"><span>Period SDE</span><span>${fmt(metrics.periodSde, 2)}</span></div>
    <div class="metric"><span>TLS false-alarm probability</span><span>${metrics.periodMethod === 'TLS' ? fmtPercent(metrics.tlsFap) : '-'}</span></div>
    <div class="metric"><span>Measured timing agreement</span><span>${ephemerisFit}</span></div>
    <div class="metric"><span>Approx. model-vs-flat p-value</span><span>${fmtPercent(metrics.pValue)}</span></div>
    <div class="metric"><span>Reduced chi-sq</span><span>${fmt(metrics.reducedChiSquared, 3)}</span></div>
    <div class="metric"><span>Time reference</span><span>${fmtReference(currentResult.time_reference)}</span></div>
    <div class="metric"><span>Median flux</span><span>${fmt(currentResult.median_flux)}</span></div>
    <div class="metric"><span>Noise</span><span>${fmt(currentResult.robust_noise)}</span></div>
  `;
  renderPeriodCandidates();
  renderWarnings(warnings);
}

function renderResult(result) {
  emptyEl.style.display = 'none';
  renderMetadata();
  renderSignalPicker();
  renderStackEvents();
  renderMetrics();
  updateChartHeading();
  syncExportButtons();
  renderTransitRows();
  drawChart();
}

function renderTransitRows() {
  if (!currentResult) return;
  rowsEl.innerHTML = currentResult.transits.length ? currentResult.transits.map((t, index) => `
    <tr>
      <td>Window ${index + 1}<br><small>${escapeHtml(t.state || 'Legacy: unverified support')}</small></td>
      <td>${fmt(t.start)}</td>
      <td>${fmt(t.center)}</td>
      <td>${fmt(t.end)}</td>
      <td>${durationLabel(t.duration)}</td>
      <td>${fmt(t.depth)}</td>
      <td>${fmtDepthPercent(eventSignedDepthFraction(t))}</td>
      <td>${fmtPpm(eventSignedDepthFraction(t) === null ? null : eventSignedDepthFraction(t)*1000000)}</td>
      <td>${fmt(t.radius_ratio)}</td>
      <td>${fmt(t.points,0)}</td>
    </tr>
  `).join('') : '<tr><td colspan="10" style="text-align:left;color:#60656f;">No statistically strong transit candidates found.</td></tr>';
}

function eventSignedDepthFraction(event) {
  const signed=nullableNumber(event.signed_depth);
  const baseline=nullableNumber(event.local_baseline) ?? nullableNumber(currentResult?.median_flux);
  if(signed!==null && baseline>0)return signed/baseline;
  return nullableNumber(event.depth_fraction);
}

function renderMetadata() {
  if (!currentResult || !metadataEl) return;
  const result = currentResult;
  const provenance = result.provenance || {};
  const settings = result.effective_settings || provenance.effective_settings || result.detection_options || {};
  const cleaning = result.cleaning || result.cleaning_report || {};
  const input = result.input_metadata || {};
  const pairs = [
    ['Analyzed at', result.analyzed_at || provenance.analyzed_at || 'Unknown (legacy analysis)'],
    ['Local dips (unvalidated)', `${primaryResult?.exploratory_dips?.length ?? result.exploratory_dips?.length ?? 'not recorded'}; these do not count as detected planets or supported events`],
    ['Analysis version', provenance.analysis_version || result.analysis_version || 'Unknown (legacy analysis)'],
    ['Result schema', result.result_schema_version ?? provenance.result_schema_version ?? 'Legacy'],
    ['Time format / scale', `${input.time_format || 'unknown'} / ${input.time_scale || 'unknown'}`],
    ['Normalization', result.normalization?.method || 'Unknown'],
    ['Local depth', 'Median measured event depth; signed depths and uncertainty are retained per event.'],
    ['Model depth', fmtDepthPercent(result.tls?.depth_fraction)],
    ['Duration / source', `${durationLabel(result.period_duration)} / ${result.tls?.duration_source || 'not recorded'}`],
  ];
  const objectRows = (label,object) => Object.keys(object).length ? `<details><summary>${escapeHtml(label)}</summary><pre>${escapeHtml(JSON.stringify(object,null,2))}</pre></details>` : '';
  metadataEl.innerHTML = pairs.map(([key,value]) => `<div class="metric"><span>${escapeHtml(key)}</span><span>${escapeHtml(value)}</span></div>`).join('')
    + '<p class="metadata-note">The approximate model-vs-flat p-value is not a search-wide false-alarm probability. Candidate scores are not probabilities.</p>'
    + objectRows('Cleaning report',cleaning) + objectRows('Effective search settings',settings)
    + objectRows('Input metadata',input) + objectRows('Search sample context',result.search_context || {}) + objectRows('Dependency versions',provenance.dependency_versions || {});
}

function renderSignalPicker() {
  const signals = primaryResult?.signals || [];
  document.getElementById('signalControl').hidden = signals.length < 2;
  const previous = signalSelect.value;
  signalSelect.innerHTML = signals.map((s,i) => `<option value="${i}">${escapeHtml(s.label || `Signal ${i+1}`)} · ${fmt(s.period,5)} d</option>`).join('');
  if(primaryResult?.joint_model_comparison)signalSelect.innerHTML+='<option value="combined">Combined fit and residuals</option>';
  if(previous==='combined'&&currentResult===primaryResult){signalSelect.value='combined';return;}
  signalSelect.value = signals.some((s,i) => String(i) === previous && s === currentResult) ? previous : String(Math.max(0,signals.indexOf(currentResult)));
}

function traceEventIndex(trace,fallback) {
  const value=nullableNumber(trace?.transit_index);
  return value === null ? fallback : Math.max(0,value-1);
}

function renderStackEvents() {
  const selected = stackEventInput.value;
  const traces = currentResult?.transit_stack?.traces || [];
  stackEventInput.innerHTML = '<option value="all">All events</option>' + traces.map((trace,index) => {
    const event = currentResult.transits?.[traceEventIndex(trace,index)];
    return `<option value="${index}">Window ${(traceEventIndex(trace,index))+1} · day ${fmt(event?.center,3)} · ${escapeHtml(event?.state || 'support unverified')}</option>`;
  }).join('');
  stackEventInput.value = selected !== 'all' && Number(selected)<traces.length ? selected : 'all';
}

function updateInspectorControls() {
  document.getElementById('phaseScopeControl').hidden = currentView !== 'phase';
  document.getElementById('stackControls').hidden = currentView !== 'stack';
  document.getElementById('localDipsControl').hidden = !['zoom','clean','raw','audit'].includes(currentView) || !(primaryResult?.exploratory_dips?.length || currentResult?.exploratory_dips?.length);
  const quality = currentResult?.fit_quality;
  document.getElementById('fitQualityLabel').textContent = !currentResult ? '' : (quality?.label || (isTentativeModel() ? 'Tentative fit — below candidate threshold' : 'Fitted model'));
  const element = document.getElementById('eventInspection');
  element.hidden = currentView !== 'stack';
  const trace = currentResult?.transit_stack?.traces?.[Number(stackEventInput.value)];
  const event = stackEventInput.value === 'all' ? null : currentResult?.transits?.[traceEventIndex(trace,Number(stackEventInput.value))];
  element.textContent = event
    ? `Window ${Number(stackEventInput.value)+1}: cycle ${event.cycle_number ?? 'unknown'}; ${event.state || 'support unverified'}; signed depth ${fmtDepthPercent(event.signed_depth ?? event.depth_fraction)} ± ${fmtDepthPercent(event.depth_uncertainty)}; local SNR ${fmt(event.local_snr,2)}; coverage ${isFiniteNumber(event.coverage_fraction) ? fmt(event.coverage_fraction*100,0)+'%' : 'unknown'}; measured center ${fmt(event.measured_center)} d ± ${durationLabel(event.timing_uncertainty)}. Recentring shifts only the display; fitted ephemeris is unchanged.`
    : 'Select an event to highlight its measurements. Odd/even groups use orbital cycle number. Legacy events without cycle metadata remain unclassified.';
}

function isTentativeModel() {
  if (currentResult?.fit_quality) return currentResult.fit_quality.state !== 'accepted';
  return !['strong_candidate','possible_candidate'].includes(currentResult?.planet_assessment?.status);
}

function applyModelStyle(width=2) {
  ctx.strokeStyle = isTentativeModel() ? '#9c8979' : '#b45309';
  ctx.lineWidth=width;
  ctx.setLineDash(isTentativeModel() ? [6,5] : []);
}

function drawSeriesPath(xs,ys,xScale,yScale,viewport,{breakIndices=[],timeSeries=false}={}) {
  const breaks=new Set(breakIndices);
  const positive=[];
  if(!timeSeries)for(let i=1;i<xs.length;i++) if(isFiniteNumber(xs[i])&&isFiniteNumber(xs[i-1])&&xs[i]>xs[i-1]) positive.push(xs[i]-xs[i-1]);
  const gap=median(positive)*8;
  const ranges=timeSeries ? observationRangesForResult(currentResult) : [];
  let open=false;let previous=null;
  ctx.beginPath();
  for(let i=0;i<Math.min(xs.length,ys.length);i++) {
    const x=nullableNumber(xs[i]),y=nullableNumber(ys[i]);
    if(x===null||y===null||x<viewport.xMin||x>viewport.xMax) {open=false;previous=null;continue;}
    const crossesGap=previous!==null && (timeSeries ? ranges.some(r=>previous<=r.end&&x>r.end&&previous>=r.start) : (gap>0&&x-previous>gap));
    if(!open||breaks.has(i)||crossesGap)ctx.moveTo(xScale(x),yScale(y));else ctx.lineTo(xScale(x),yScale(y));
    open=true;previous=x;
  }
  ctx.stroke();
}

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
    start_jd: ['jd','bjd','mjd','bkjd','btjd'].includes(currentResult.input_metadata?.time_format?.toLowerCase()) ? currentResult.time_reference + transit.start : null,
    center_jd: ['jd','bjd','mjd','bkjd','btjd'].includes(currentResult.input_metadata?.time_format?.toLowerCase()) ? currentResult.time_reference + transit.center : null,
    end_jd: ['jd','bjd','mjd','bkjd','btjd'].includes(currentResult.input_metadata?.time_format?.toLowerCase()) ? currentResult.time_reference + transit.end : null,
    duration_days: transit.duration,
    depth: transit.depth,
    depth_fraction: transit.depth_fraction,
    depth_percent: transit.depth_percent,
    depth_ppm: transit.depth_ppm,
    radius_ratio: transit.radius_ratio,
    depth_basis: transit.depth_basis,
    points: transit.points,
    state: transit.state || 'legacy_unverified',
    cycle_number: transit.cycle_number ?? null,
    signed_depth: transit.signed_depth ?? null,
    signed_depth_fraction: eventSignedDepthFraction(transit),
    depth_uncertainty: transit.depth_uncertainty ?? null,
    measured_center_day: transit.measured_center ?? null,
    timing_uncertainty_days: transit.timing_uncertainty ?? null,
    local_snr: transit.local_snr ?? null,
    coverage_fraction: transit.coverage_fraction ?? null,
    time_reference: currentResult.time_reference,
    time_format: currentResult.input_metadata?.time_format || 'unknown',
    time_scale: currentResult.input_metadata?.time_scale || 'unknown',
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
    'state','cycle_number','signed_depth','signed_depth_fraction','depth_uncertainty','measured_center_day','timing_uncertainty_days','local_snr','coverage_fraction',
    'time_reference','time_format','time_scale',
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
    time_reference: currentResult.time_reference,
    time_reference_jd: ['jd','bjd','mjd','bkjd','btjd'].includes(currentResult.input_metadata?.time_format?.toLowerCase()) ? currentResult.time_reference : null,
    time_unit: currentResult.time_unit,
    flux_unit: currentResult.flux_unit,
    normalization: currentResult.normalization,
    detection_options: currentResult.detection_options,
    planet_assessment: currentResult.planet_assessment || planetAssessment,
    result_schema_version: currentResult.result_schema_version ?? null,
    provenance: currentResult.provenance || {analysis_version:'unknown',analyzed_at:null,legacy:true},
    analyzed_at: currentResult.analyzed_at ?? currentResult.provenance?.analyzed_at ?? null,
    input_metadata: currentResult.input_metadata || {time_format:'unknown',time_scale:'unknown'},
    cleaning: currentResult.cleaning || currentResult.cleaning_report || null,
    effective_settings: currentResult.effective_settings || null,
    fit_quality: currentResult.fit_quality || null,
    model_comparison: currentResult.model_comparison || null,
    joint_model_comparison: primaryResult?.joint_model_comparison || null,
    predicted_windows: currentResult.predicted_windows || null,
    observed_events: currentResult.observed_events || null,
    exploratory_dips: primaryResult?.exploratory_dips || currentResult.exploratory_dips || [],
    signals: primaryResult?.signals || [],
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
      covered_window_count: currentResult.transits.length,
      predicted_window_count: currentResult.predicted_windows?.length ?? null,
      observed_event_count: currentResult.observed_events?.length ?? null,
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
  {key:'file',label:'File',width:200,align:'left'},
  {key:'assessment',label:'Assessment',width:160,align:'left'},
  {key:'score',label:'Cand. score',width:70,align:'right'},
  {key:'points',label:'Samples',width:75,align:'right'},
  {key:'supported',label:'Supported',width:75,align:'right'},
  {key:'transits',label:'Windows',width:75,align:'right'},
  {key:'period',label:'Period (d)',width:110,align:'right'},
  {key:'duration',label:'Duration',width:90,align:'right'},
  {key:'depthPercent',label:'Local depth',width:95,align:'right'},
  {key:'sde',label:'SDE',width:85,align:'right'},
  {key:'snr',label:'Search SNR',width:85,align:'right'},
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
    score: assessment.candidateScore === null ? '-' : assessment.candidateScore.toString(),
    points: result.total_points.toLocaleString(),
    transits: result.transits.length.toString(),
    supported: result.observed_events?.length?.toString() ?? 'unverified',
    duration: durationLabel(result.period_duration),
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
    jdStart: fmtReference(result.time_reference),
    medianFlux: fmt(result.median_flux, 6),
    noise: fmt(result.robust_noise, 6),
    detailResult: result,
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
  const rowHeight = 36;
  const headerHeight = 30;
  const rowsPerPage = Math.max(1, Math.floor((pageHeight - 96 - headerHeight) / rowHeight));
  const pages = [];
  const pageCount = Math.max(1, Math.ceil(rows.length / rowsPerPage));

  for (let pageIndex = 0; pageIndex < pageCount; pageIndex++) {
    const pageRows = rows.slice(pageIndex * rowsPerPage, (pageIndex + 1) * rowsPerPage);
    let content = '0.8 w\n';
    const titleY = pageHeight - margin - 12;
    content += pdfText(margin, titleY, title, 16, 'F2');
    content += pdfText(pageWidth - margin - 118, titleY, `Summary ${pageIndex + 1}/${pageCount}`, 8, 'F1');
    content += pdfText(margin, titleY - 16, `Generated ${new Date().toLocaleString()}`, 8, 'F1');

    let y = pageHeight - margin - 54;
    let x = margin;
    content += pdfRect(margin, y - headerHeight + 4, tableWidth, headerHeight);
    analysisPdfColumns.forEach(column => {
      content += pdfLine(x, y + 4, x, y - headerHeight + 4);
      content += pdfText(x + 3, y - 11, column.label, 9, 'F2');
      x += column.width;
    });
    content += pdfLine(margin + tableWidth, y + 4, margin + tableWidth, y - headerHeight + 4);
    y -= headerHeight;

    pageRows.forEach(row => {
      x = margin;
      content += pdfRect(margin, y - rowHeight + 4, tableWidth, rowHeight);
      analysisPdfColumns.forEach(column => {
        const rawValue = row[column.key] ?? '-';
        const maxChars = Math.max(4, Math.floor(column.width / 5.3));
        const value = fitPdfText(rawValue, maxChars);
        const textWidth = value.length * 4.8;
        const textX = column.align === 'right'
          ? Math.max(x + 3, x + column.width - textWidth - 4)
          : x + 3;
        content += pdfLine(x, y + 4, x, y - rowHeight + 4);
        content += pdfText(textX, y - 13, value, 10, 'F1');
        x += column.width;
      });
      content += pdfLine(margin + tableWidth, y + 4, margin + tableWidth, y - rowHeight + 4);
      y -= rowHeight;
    });

    pages.push(content);
  }

  for(const row of rows) {
    const lines=pdfAnalysisDetails(row);
    for(let offset=0;offset<lines.length;offset+=43) {
      let content=pdfText(margin,pageHeight-margin-12,'Transit Finder: '+row.file,16,'F2');
      content+=pdfLine(margin,pageHeight-margin-25,pageWidth-margin,pageHeight-margin-25);
      lines.slice(offset,offset+43).forEach((line,index)=>{
        content+=pdfText(margin,pageHeight-margin-48-index*15,line.text,line.heading?12:11,line.heading?'F2':'F1');
      });
      content+=pdfText(margin,20,`Analysis details ${Math.floor(offset/43)+1}/${Math.ceil(lines.length/43)}`,9,'F1');
      pages.push(content);
    }
  }

  return buildPdfBlob(pages, pageWidth, pageHeight);
}

function pdfPlainText(value) {
  return String(value??'-').replace(/±/g,'+/-').replace(/[–—]/g,'-').replace(/σ/g,'sigma').replace(/☉/g,'sun').replace(/[^\x20-\x7E]/g,' ');
}

function pdfWrap(value,maxLength=160) {
  const words=pdfPlainText(value).replace(/\s+/g,' ').trim().split(' '),lines=[];
  let line='';
  for(const word of words){
    if(line.length+word.length+1>maxLength){lines.push(line);line='';}
    if(word.length>maxLength){if(line){lines.push(line);line='';}for(let i=0;i<word.length;i+=maxLength)lines.push(word.slice(i,i+maxLength));}
    else line+=(line?' ':'')+word;
  }
  if(line)lines.push(line);
  return lines;
}

function pdfSettingPairs(object,prefix='') {
  const pairs=[];
  for(const [key,value] of Object.entries(object||{})) {
    const label=(prefix?prefix+' / ':'')+key.replaceAll('_',' ').replace(/([a-z])([A-Z])/g,'$1 $2').toLowerCase();
    if(value && typeof value==='object' && !Array.isArray(value))pairs.push(...pdfSettingPairs(value,label));
    else pairs.push(`${label}: ${value===null?'not specified':Array.isArray(value)?JSON.stringify(value):value}`);
  }
  return pairs;
}

function pdfAnalysisDetails(row) {
  const result=row.detailResult;if(!result)return [];
  const lines=[];
  const add=(text,heading=false)=>pdfWrap(text).forEach(text=>lines.push({text,heading}));
  const section=name=>{if(lines.length)lines.push({text:'',heading:false});add(name,true);};
  const packed=pairs=>{
    let text='';
    for(const pair of pairs){if(text.length+pair.length+3>150){add(text);text='';}text+=(text?';  ':'')+pair;}
    if(text)add(text);
  };
  section('RESULT AND EVIDENCE');
  add(`Assessment: ${row.assessment}. Candidate score: ${row.score}/100 (not a probability).`);
  add(`Supported events: ${row.supported}; covered windows: ${row.transits}; all predicted windows: ${result.predicted_windows?.length??'not recorded'}. Measured timing agreement: ${row.ephemerisFit}.`);
  add(`Period: ${fmt(result.period,9)} +/- ${fmt(result.period_uncertainty,9)} days (${result.period_method||'unknown method'}). SDE: ${row.sde}; search SNR: ${row.snr}.`);
  add(`Duration: ${row.duration}. Source: ${result.tls?.duration_source||'not recorded'}. Fit quality: ${result.fit_quality?.label||'legacy / unverified'}.`);
  add(`Local measured depth: ${row.depthPercent} (${row.depthPpm} ppm). Model depth: ${fmtDepthPercent(result.tls?.depth_fraction)}. These are different estimators.`);
  add(`Local Rp/Rstar: ${row.radiusRatio}; median flux: ${row.medianFlux}; robust noise: ${row.noise}.`);
  add(`Approximate model-vs-flat p-value: ${row.pValue}; reduced chi-square: ${row.reducedChi}. This p-value is not a search-wide false-alarm probability.`);
  const assessment=result.planet_assessment||{};
  if(assessment.summary)add(assessment.summary);
  if(assessment.recommendation)add(assessment.recommendation);
  if(result.multi_signal_search?.joint_fit)packed(pdfSettingPairs(result.multi_signal_search.joint_fit,'Joint fit'));
  section('ANALYSIS PROVENANCE');
  const provenance=result.provenance||{};
  add(`Analyzed: ${result.analyzed_at||provenance.analyzed_at||'unknown (legacy analysis)'}. Analysis version: ${provenance.analysis_version||'unknown'}; app: ${provenance.app_version||'unknown'}; result schema: ${result.result_schema_version??provenance.result_schema_version??'legacy'}.`);
  const dependencies=Object.entries(provenance.dependency_versions||{}).map(([key,value])=>`${key} ${value}`).join('; ');
  if(dependencies)add('Software: '+dependencies);
  section('INPUT AND CLEANING');
  add(`Time reference: ${fmtReference(result.time_reference)} days. Format: ${result.input_metadata?.time_format||'unknown'}; scale: ${result.input_metadata?.time_scale||'unknown'}; flux unit: ${result.flux_unit||'not specified'}.`);
  packed(pdfSettingPairs(result.input_metadata||{}));
  const cleaning=result.cleaning||result.cleaning_report;
  if(cleaning)packed(pdfSettingPairs(cleaning));else add('Cleaning counts were not recorded in this legacy result.');
  add(`Normalization: ${result.normalization?.method||'unknown'}. Segments: ${result.normalization?.segment_count??'not recorded'}.`);
  section('EFFECTIVE SEARCH SETTINGS');
  packed(pdfSettingPairs(result.effective_settings||provenance.effective_settings||result.detection_options||{}));
  if(!(result.effective_settings||provenance.effective_settings))add('Legacy controls are recorded above; exact engine defaults and dependency versions may be unknown.');
  section('WARNINGS');
  if(!result.warnings?.length)add('No saved major warnings. This does not establish that the signal is planetary.');
  for(const warning of result.warnings||[])add(`${warning.severity}: ${warning.title}. ${warning.detail}`);
  return lines;
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
  const pad = { ...chartPad, bottom: ['phase','stack'].includes(currentView) ? 112 : chartPad.bottom };
  return {
    width,
    height,
    pad,
    innerW: Math.max(1, width - pad.left - pad.right),
    innerH: Math.max(1, height - pad.top - pad.bottom),
  };
}

function getInitialDomain() {
  if (!currentResult) return null;
  if (currentView === 'comparison') return comparisonDomain();
  if (currentView === 'stack') {
    if (!hasTransitStack()) return null;
    const stackDomain = currentResult.transit_stack.domain;
    return {
      xMin: stackDomain.time_min,
      xMax: stackDomain.time_max,
      yMin: stackDomain.flux_min,
      yMax: stackDomain.flux_max,
    };
  }
  if (currentView === 'phase') {
    if (!hasPhaseFold()) return null;
    const phaseDomain = phaseDomainForScope();
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

function phaseDomainForScope() {
  const folded=currentResult.phase_folded;
  if(phaseScopeInput.value==='orbit')return folded.domain;
  const saved=folded.focus_domain || folded.domain;
  const duration=nullableNumber(folded.duration ?? currentResult.period_duration);
  if(duration===null||duration<=0)return saved;
  const halfWidth=Math.min((folded.domain.time_max-folded.domain.time_min)/2,duration*1.5);
  return {...saved,time_min:Math.max(saved.time_min,-halfWidth),time_max:Math.min(saved.time_max,halfWidth)};
}

function getLimitDomain() {
  if (!currentResult) return null;
  if (currentView === 'comparison') return comparisonDomain();
  if (currentView === 'stack') {
    if (!hasTransitStack()) return null;
    const stackDomain = currentResult.transit_stack.domain;
    return {
      xMin: stackDomain.time_min,
      xMax: stackDomain.time_max,
      yMin: stackDomain.flux_min,
      yMax: stackDomain.flux_max,
    };
  }
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
  const variant=currentView==='raw'?'raw':'clean';
  const extent=transit.display_extents?.[variant] || transit[`${variant}_extent`];
  if (extent && isFiniteNumber(extent.low ?? extent.flux_min) && isFiniteNumber(extent.high ?? extent.flux_max)) return {low:extent.low ?? extent.flux_min,high:extent.high ?? extent.flux_max};
  const values=[];
  for (let i = lowerBoundTime(currentResult.plot.time,transit.start); i < currentResult.plot.time.length; i++) {
    const time = currentResult.plot.time[i];
    if (time > transit.end) break;
    const value = flux[i];
    if (!Number.isFinite(value)) continue;
    values.push(value);
  }
  if (!values.length) return null;
  values.sort((a,b)=>a-b);
  const low=values[Math.floor((values.length-1)*.05)];
  const high=values[Math.ceil((values.length-1)*.95)];
  const padding = Math.max((high - low) * 0.22, Math.abs(transit.depth || 0) * 0.08, 1e-9);
  return { low: low - padding, high: high + padding };
}

function lowerBoundTime(times,target) {
  let left=0,right=times.length;
  while(left<right){const middle=(left+right)>>1;if(times[middle]<target)left=middle+1;else right=middle;}
  return left;
}

function updateCanvasCursor(point = lastPointer) {
  if (dragState) {
    canvas.style.cursor = 'grabbing';
    return;
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
  ctx.save();
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
    const available=Math.max(80,width-pad.left-pad.right);
    const labelWidth=ctx.measureText(xLabel).width;
    if(labelWidth>available)ctx.font='600 10px system-ui,sans-serif';
    ctx.fillText(xLabel, width - pad.right, height - 23, Math.max(available,100));
  }
  ctx.restore();
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
  canvas.focus({ preventScroll: true });
  event.preventDefault();
  const point = pointerPosition(event);
  lastPointer = point;
  const viewport = getViewport();
  if (!viewport) return;
  dragState = {
    x: point.x,
    y: point.y,
    viewport: cloneDomain(viewport),
  };
  canvas.classList.add('dragging');
  canvas.setPointerCapture(event.pointerId);
});

function finishDrag(event) {
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
  if (!currentResult || event.defaultPrevented || event.target?.isContentEditable
      || event.target?.closest?.('input,select,textarea,[contenteditable]:not([contenteditable="false"]),[role=slider],[role=spinbutton],[role=listbox],[role=combobox],[role=menu],[role=tree],[role=tablist],[aria-haspopup=listbox]')) return;
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
  if (!hasPhaseFold()) { drawNotice('Phase folding needs a recovered orbital period.',geo.width,geo.height); return; }
  const folded=currentResult.phase_folded, viewport=getViewport();
  if(!viewport)return;
  const x=value=>geo.pad.left+(value-viewport.xMin)/(viewport.xMax-viewport.xMin)*geo.innerW;
  const y=value=>geo.pad.top+(1-(value-viewport.yMin)/(viewport.yMax-viewport.yMin))*geo.innerH;
  ctx.fillStyle='#fbfcfd';ctx.fillRect(0,0,geo.width,geo.height);
  drawChartAxes(geo,viewport,{xLabel:'Days from fitted transit center',yLabel:'Global folded flux'});
  ctx.save();clipToChartPlot(geo);
  if(isFiniteNumber(folded.duration)) {ctx.fillStyle='rgba(180,83,9,.09)';ctx.fillRect(x(-folded.duration/2),geo.pad.top,x(folded.duration/2)-x(-folded.duration/2),geo.innerH);}
  ctx.fillStyle='rgba(15,118,110,.18)';
  for(let i=0;i<folded.phase.length;i++) {
    const phase=nullableNumber(folded.phase[i]),value=nullableNumber(folded.raw_flux[i]);
    if(phase===null||value===null||phase<viewport.xMin||phase>viewport.xMax)continue;
    ctx.fillRect(x(phase)-.8,y(value)-.8,1.6,1.6);
  }
  const model=currentResult.transit_model;
  if(showModelInput.checked && model?.folded_phase_days?.length) {
    applyModelStyle(2.1);drawSeriesPath(model.folded_phase_days,model.folded_flux,x,y,viewport);ctx.setLineDash([]);
  }
  ctx.strokeStyle='#063f3b';ctx.lineWidth=2.3;
  drawSeriesPath(folded.binned_phase||[],folded.binned_flux||[],x,y,viewport);
  if(Array.isArray(folded.binned_uncertainty)) {
    ctx.lineWidth=1;ctx.strokeStyle='rgba(6,63,59,.55)';
    folded.binned_phase.forEach((phase,index)=>{
      const uncertainty=nullableNumber(folded.binned_uncertainty[index]),value=nullableNumber(folded.binned_flux[index]);
      if(uncertainty===null||value===null||phase<viewport.xMin||phase>viewport.xMax)return;
      ctx.beginPath();ctx.moveTo(x(phase),y(value-uncertainty));ctx.lineTo(x(phase),y(value+uncertainty));ctx.stroke();
    });
  }
  ctx.restore();
  drawTransitStackLegend(geo,Boolean(showModelInput.checked&&model?.folded_phase_days?.length),true);
  updateCanvasCursor(lastPointer);
}

function drawTransitStackLegend(geo,hasModel,phase=false) {
  const items=[
    {color:'rgba(15,118,110,.6)',text:phase?'Folded observations':'Individual event windows',width:1.2},
    {color:'#063f3b',text:phase?'Median bins':'All-event median',width:3},
  ];
  if(hasModel)items.push({color:isTentativeModel()?'#9c8979':'#b45309',text:isTentativeModel()?'Tentative fitted model':'Fitted model',width:2,dash:isTentativeModel()});
  ctx.save();ctx.textAlign='left';ctx.textBaseline='middle';ctx.globalAlpha=1;ctx.font='600 10px system-ui,sans-serif';
  let x=geo.pad.left,y=geo.pad.top+geo.innerH+34;
  const limit=geo.width-geo.pad.right;
  for(const item of items) {
    const itemWidth=24+ctx.measureText(item.text).width+12;
    if(x+itemWidth>limit&&x>geo.pad.left){x=geo.pad.left;y+=17;}
    ctx.strokeStyle=item.color;ctx.lineWidth=item.width;ctx.setLineDash(item.dash?[5,4]:[]);
    ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+14,y);ctx.stroke();
    ctx.setLineDash([]);ctx.fillStyle='#3f4650';ctx.fillText(item.text,x+20,y);x+=itemWidth;
  }
  ctx.restore();
}

function drawTransitStackChart(geo) {
  if(!hasTransitStack()){drawNotice('Reanalyze this file to create event-level stack data.',geo.width,geo.height);return;}
  const stack=currentResult.transit_stack, viewport=getViewport();if(!viewport)return;
  const x=value=>geo.pad.left+(value-viewport.xMin)/(viewport.xMax-viewport.xMin)*geo.innerW;
  const y=value=>geo.pad.top+(1-(value-viewport.yMin)/(viewport.yMax-viewport.yMin))*geo.innerH;
  ctx.fillStyle='#fbfcfd';ctx.fillRect(0,0,geo.width,geo.height);
  drawChartAxes(geo,viewport,{xLabel:'Days from ephemeris center',yLabel:'Locally normalized flux'});
  const selected=stackEventInput.value==='all'?null:Number(stackEventInput.value);
  const colors=['#0f766e','#2563eb','#7c3aed','#0891b2','#047857','#4f46e5'];
  ctx.save();clipToChartPlot(geo);
  stack.traces.forEach((trace,index)=>{
    const event=currentResult.transits?.[traceEventIndex(trace,index)];
    const cycle=nullableNumber(event?.cycle_number);
    if(stackGroupInput.value!=='all'&&(cycle===null || Math.abs(cycle%2)!==(stackGroupInput.value==='odd'?1:0)))return;
    if(selected!==null&&stackIsolateInput.checked&&selected!==index)return;
    const shift=stackRecenterInput.checked&&isFiniteNumber(event?.measured_center)?event.measured_center-event.center:0;
    const phases=(trace.phase_days||[]).map(value=>value-shift);
    ctx.strokeStyle=colors[index%colors.length];ctx.globalAlpha=selected===index?.95:selected===null?.32:.1;ctx.lineWidth=selected===index?2.6:1.1;
    drawSeriesPath(phases,trace.flux||[],x,y,viewport);
  });
  ctx.globalAlpha=1;
  const model=currentResult.transit_model;
  const hasModel=Boolean(showModelInput.checked&&model?.folded_phase_days?.length);
  if(hasModel){applyModelStyle(2);drawSeriesPath(model.folded_phase_days,model.folded_flux,x,y,viewport);ctx.setLineDash([]);}
  if(stackMedianInput.checked){ctx.strokeStyle='#063f3b';ctx.lineWidth=2.7;drawSeriesPath(stack.median_phase_days||[],stack.median_flux||[],x,y,viewport);}
  ctx.restore();
  drawTransitStackLegend(geo,hasModel);updateInspectorControls();updateCanvasCursor(lastPointer);
}

function comparisonDomain() {
  const comparison=comparisonPayload();
  if(!comparison?.time?.length)return null;
  const values=[...(comparison.search_flux||[]),...(comparison.model_flux||[])].map(nullableNumber).filter(Number.isFinite);
  if(!values.length)return null;
  const minimum=values.reduce((a,b)=>Math.min(a,b),Infinity),maximum=values.reduce((a,b)=>Math.max(a,b),-Infinity),padding=Math.max((maximum-minimum)*.08,1e-6);
  return {xMin:comparison.time[0],xMax:comparison.time[comparison.time.length-1],yMin:minimum-padding,yMax:maximum+padding};
}

function drawComparisonChart(geo) {
  const comparison=comparisonPayload(),viewport=getViewport();
  if(!comparison?.time?.length||!viewport){drawNotice('Reanalyze this file to compare matched search flux and model residuals.',geo.width,geo.height);return;}
  ctx.fillStyle='#fbfcfd';ctx.fillRect(0,0,geo.width,geo.height);
  const top={...geo,innerH:geo.innerH*.57,height:geo.pad.top+geo.innerH*.57+geo.pad.bottom};
  const residuals=(comparison.residual_flux||[]).map(nullableNumber).filter(Number.isFinite).sort((a,b)=>a-b);
  const scale=Math.max(Math.abs(residuals[Math.floor(residuals.length*.01)]||0),Math.abs(residuals[Math.floor(residuals.length*.99)]||0),1e-6)*1.15;
  const bottom={...geo,pad:{...geo.pad,top:geo.pad.top+geo.innerH*.69},innerH:geo.innerH*.31};
  const residualDomain={...viewport,yMin:-scale,yMax:scale};
  const x=value=>geo.pad.left+(value-viewport.xMin)/(viewport.xMax-viewport.xMin)*geo.innerW;
  const topY=value=>top.pad.top+(1-(value-viewport.yMin)/(viewport.yMax-viewport.yMin))*top.innerH;
  const bottomY=value=>bottom.pad.top+(1-(value+scale)/(2*scale))*bottom.innerH;
  drawChartAxes(top,viewport,{yLabel:'Search flux and model'});
  drawChartAxes(bottom,residualDomain,{xLabel:timeAxisLabel(),yLabel:'Residual flux (data − model)'});
  ctx.save();clipToChartPlot(top);ctx.strokeStyle='#0f766e';ctx.lineWidth=1;
  drawSeriesPath(comparison.time,comparison.search_flux,x,topY,viewport,{timeSeries:true});
  if(showModelInput.checked){applyModelStyle(1.8);drawSeriesPath(comparison.time,comparison.model_flux,x,topY,viewport,{timeSeries:true});}
  ctx.restore();ctx.save();clipToChartPlot(bottom);ctx.setLineDash([]);ctx.strokeStyle='#526173';ctx.lineWidth=1;
  drawSeriesPath(comparison.time,comparison.residual_flux,x,bottomY,residualDomain,{timeSeries:true});ctx.restore();
}

function comparisonPayload() {
  return signalSelect.value==='combined' ? primaryResult?.joint_model_comparison : currentResult?.model_comparison;
}

function timeAxisLabel() {
  return `Days since ${fmtReference(currentResult?.time_reference)} (${currentResult?.input_metadata?.time_format||'convention unverified'})`;
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
    const transitX = xScale(transit.measured_center ?? transit.center);
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
    isFiniteNumber(metrics.ephemerisMatchCount)
    && isFiniteNumber(metrics.ephemerisMatchFraction)
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

  if (currentView === 'comparison') { drawComparisonChart(geo); return; }

  if (currentView === 'periodogram') {
    drawPeriodogramChart(geo);
    return;
  }

  if (currentView === 'phase') {
    drawPhaseChart(geo);
    return;
  }

  if (currentView === 'stack') {
    drawTransitStackChart(geo);
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
  const auditMetrics = currentView === 'audit' ? currentAnalysisMetrics() : null;
  if (currentView === 'audit' && (!isFiniteNumber(auditMetrics.period) || !isFiniteNumber(auditMetrics.periodEpoch))) {
    drawNotice('Ephemeris audit needs a recovered period and epoch.', width, height);
    return;
  }
  if (currentView === 'audit') {
    drawAuditPredictions(geo, viewport, auditMetrics, xScale);
  }

  ctx.save();
  clipToChartPlot(geo);
  currentResult.transits.forEach((t, index) => {
    const boxStart = t.start;
    const boxEnd = t.end;
    if (boxEnd < xMin || boxStart > xMax) return;
    const range = transitFluxRange(t, flux);
    if (!range) return;
    const x1 = Math.max(pad.left, xScale(boxStart));
    const x2 = Math.min(width - pad.right, xScale(boxEnd));
    const y1 = Math.max(pad.top, Math.min(pad.top + innerH, yScale(range.high)));
    const y2 = Math.max(pad.top, Math.min(pad.top + innerH, yScale(range.low)));
    const boxWidth = Math.max(0.7, x2 - x1);
    const boxTop = Math.min(y1, y2);
    const boxHeight = Math.max(8, Math.abs(y2 - y1));
    const auditClassification = auditMetrics ? classifyTransitForEphemeris(t, auditMetrics) : null;
    const auditMatched = auditClassification && auditClassification.status === 'matched';
    const auditOffPeriod = auditClassification && auditClassification.status === 'off';
    ctx.fillStyle = auditMatched
      ? 'rgba(21, 128, 61, 0.2)'
      : (auditOffPeriod ? 'rgba(180, 35, 24, 0.18)' : 'rgba(180, 83, 9, 0.22)');
    ctx.fillRect(x1, boxTop, boxWidth, boxHeight);
    ctx.strokeStyle = auditMatched
      ? 'rgba(21, 128, 61, 1)'
      : (auditOffPeriod ? 'rgba(180, 35, 24, 1)' : 'rgba(180, 83, 9, 1)');
    ctx.lineWidth = 1.5;
    ctx.setLineDash(isTentativeModel() ? [5,4] : []);
    ctx.strokeRect(x1, boxTop, boxWidth, boxHeight);
    ctx.setLineDash([]);
    ctx.fillStyle = auditMatched ? '#166534' : (auditOffPeriod ? '#991b1b' : '#8a3f06');
    ctx.font = '700 12px system-ui, sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    if (boxWidth > 18 || currentView === 'zoom') {
      ctx.fillText(`W${index + 1}`, Math.max(pad.left + 4, x1 + 5), Math.max(pad.top + 4, boxTop + 5));
    }
  });
  if(showLocalDipsInput.checked) {
    const dips=primaryResult?.exploratory_dips || currentResult.exploratory_dips || [];
    ctx.strokeStyle='rgba(124,58,237,.65)';ctx.lineWidth=1.1;ctx.setLineDash([3,4]);
    dips.forEach((dip,index)=>{
      if(dip.end<viewport.xMin||dip.start>viewport.xMax)return;
      const range=transitFluxRange(dip,flux);if(!range)return;
      const left=xScale(dip.start),right=xScale(dip.end),top=yScale(range.high),bottom=yScale(range.low);
      ctx.strokeRect(left,Math.min(top,bottom),Math.max(.7,right-left),Math.max(2,Math.abs(bottom-top)));
      if(currentView==='zoom'&&right-left>12){ctx.fillStyle='#7c3aed';ctx.textAlign='left';ctx.font='10px system-ui,sans-serif';ctx.fillText(`D${index+1}`,left+2,Math.min(top,bottom)-3);}
    });
    ctx.setLineDash([]);
  }
  ctx.restore();

  drawChartAxes(geo, viewport, {
    xDigits: 4,
    yDigits: 4,
    xLabel: timeAxisLabel(),
    yLabel: currentView === 'raw' ? 'Flux' : (currentView === 'audit' ? 'Ephemeris audit' : 'Smoothed flux'),
  });

  ctx.save();
  clipToChartPlot(geo);
  if (currentView !== 'raw') {
    ctx.strokeStyle='rgba(15,118,110,.16)';ctx.lineWidth=1;
    drawSeriesPath(times,rawFlux,xScale,yScale,viewport,{breakIndices:currentResult.plot.break_indices||[],timeSeries:true});
  }
  ctx.strokeStyle=currentView==='raw'?'#0f766e':'#063f3b';ctx.lineWidth=currentView==='raw'?1.2:2.4;
  drawSeriesPath(times,flux,xScale,yScale,viewport,{breakIndices:currentResult.plot.break_indices||[],timeSeries:true});
  if(hasTransitModel()&&currentView!=='raw') {
    applyModelStyle(1.8);
    drawSeriesPath(currentResult.transit_model.time,currentResult.transit_model.flux,xScale,yScale,viewport,{timeSeries:true});
  }
  ctx.restore();

  if (currentView === 'audit') {
    drawAuditResiduals(geo, viewport, auditMetrics, xScale);
    drawAuditLegend(geo, auditMetrics);
  }

  updateCanvasCursor(lastPointer);
}

document.getElementById('resetViewButton').addEventListener('click',()=>{
  currentViewport=null;drawChart();queueSessionSave();
});
showModelInput.addEventListener('change',()=>{drawChart();});
showLocalDipsInput.addEventListener('change',()=>{drawChart();});
phaseScopeInput.addEventListener('change',()=>{currentViewport=null;drawChart();queueSessionSave();});
[stackEventInput,stackGroupInput,stackIsolateInput,stackMedianInput,stackRecenterInput].forEach(input=>input.addEventListener('change',()=>{
  updateInspectorControls();drawChart();
}));
signalSelect.addEventListener('change',()=>{
  if(signalSelect.value==='combined') {
    currentResult=primaryResult;currentView='comparison';viewButtons.forEach(button=>button.classList.toggle('active',button.dataset.view===currentView));
  } else currentResult=primaryResult?.signals?.[Number(signalSelect.value)] || primaryResult;
  currentViewport=null;stackEventInput.value='all';renderResult(currentResult);queueSessionSave();
});
perFileSettingsInput.addEventListener('change',queueSessionSave);
document.getElementById('applyPerFileSettings').addEventListener('click',()=>updatePerFileSettings(false));
document.getElementById('clearPerFileSettings').addEventListener('click',()=>updatePerFileSettings(true));

window.addEventListener('resize', () => {
  updateSidebarWidth();
  drawChart();
});

sessionReadyPromise = initializeSession();
