"""Thin, JSON-friendly integration around the reference TLS implementation."""

import math
import importlib
import threading
import time as monotonic_time
from collections import deque
from contextlib import contextmanager

import numpy as np

try:
    from transitleastsquares import transitleastsquares
    from transitleastsquares import tls_constants
except Exception as exc:  # pragma: no cover - exercised only in incomplete environments
    transitleastsquares = None
    tls_constants = None
    TLS_IMPORT_ERROR = exc
else:
    TLS_IMPORT_ERROR = None


MAX_MODEL_POINTS = 12000
MAX_SPECTRUM_POINTS = 1600
_PROGRESS_LOCK = threading.RLock()


class SearchProgress:
    """Count real TLS trials; forecast only from stable observed throughput.

    TLS 1.32 shuffles its trial grid and reports unordered worker completions.
    These counts do not expose the cost of the remaining trials. The displayed
    range is the spread of observed throughput, not a confidence interval.
    """

    def __init__(self, callback, total=0, **kwargs):
        self.callback = callback
        self.total = int(total)
        self.completed = 0
        self.started = monotonic_time.monotonic()
        self.last_sent = -math.inf
        self.first_completion_time = None
        self.first_completion_count = 0
        self.windows = deque(maxlen=12)
        self.window_started = None
        self.window_completed = 0
        self.emit(force=True)

    def emit(self, force=False, finished=False):
        now = monotonic_time.monotonic()
        if not force and now - self.last_sent < 0.75:
            return
        elapsed = now - self.started
        active_elapsed = now - self.first_completion_time if self.first_completion_time is not None else 0.0
        remaining = low = high = variation = None
        sample_seconds = sum(duration for _, duration in self.windows)
        # Exclude JIT/worker startup. Use independent windows rather than heavily
        # overlapping instantaneous rates, which created unhelpfully wide ranges.
        enough = (self.completed >= max(12, int(self.total * 0.05))
                  and len(self.windows) >= 4)
        if enough and self.completed < self.total and not finished:
            overall_rate = (self.completed - self.first_completion_count) / max(active_elapsed, 1e-9)
            recent_rate = sum(count for count, _ in self.windows) / max(sample_seconds, 1e-9)
            if recent_rate > 0 and overall_rate > 0:
                work_left = self.total - self.completed
                rates = [count / duration for count, duration in self.windows] + [overall_rate]
                if min(rates) > 0:
                    variation = max(rates) / min(rates)
                    trend = max(overall_rate, recent_rate) / min(overall_rate, recent_rate)
                    if variation <= 1.75 and trend <= 1.5:
                        remaining = work_left / recent_rate
                        low = work_left / max(rates)
                        high = work_left / min(rates)
        details = {
            "completed_trials": self.completed, "total_trials": self.total,
            "work_completed": self.completed, "work_total": self.total,
            "estimated_remaining_seconds": remaining,
            "eta_lower_seconds": low, "eta_upper_seconds": high,
            "remaining_seconds_range": [low, high] if low is not None else None,
            "eta_scope": "search", "search_elapsed_seconds": elapsed,
            "throughput_elapsed_seconds": active_elapsed,
            "search_complete": bool(finished),
            "eta_state": "available" if remaining is not None else "estimating",
            "eta_method": "observed_trial_throughput",
            "eta_sample_seconds": sample_seconds,
            "eta_variation": variation,
        }
        self.callback(details)
        self.last_sent = now

    def update(self, count=1):
        self.completed = min(self.total, self.completed + int(count))
        if self.first_completion_time is None and self.completed > 0:
            self.first_completion_time = monotonic_time.monotonic()
            self.first_completion_count = self.completed
            self.window_started = self.first_completion_time
            self.window_completed = self.completed
            self.emit(force=True)
            return
        now = monotonic_time.monotonic()
        if self.window_started is not None and now - self.window_started >= 5.0:
            self.windows.append((self.completed - self.window_completed, now - self.window_started))
            self.window_started = now
            self.window_completed = self.completed
        self.emit()

    def close(self):
        self.emit(force=True, finished=True)


@contextmanager
def measured_tls_progress(callback):
    # power() calls a module-local tqdm after constructing its real trial grid.
    # Jobs run in isolated processes; serialize direct threaded callers too.
    with _PROGRESS_LOCK:
        if not callable(callback):
            yield False
            return
        module = importlib.import_module("transitleastsquares.main")
        stats = importlib.import_module("transitleastsquares.stats")
        original = module.tqdm
        original_stats = stats.tqdm
        module.tqdm = lambda *args, **kwargs: SearchProgress(callback, *args, **kwargs)
        class QuietFinalization:
            def __init__(self, *args, **kwargs):
                pass
            def update(self, *args, **kwargs):
                pass
            def close(self):
                pass
        stats.tqdm = QuietFinalization
        try:
            yield True
        finally:
            module.tqdm = original
            stats.tqdm = original_stats


def finite_number(value):
    if value is None or isinstance(value, (bool, np.bool_)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def finite_int(value):
    number = finite_number(value)
    return None if number is None else int(number)


def finite_list(values):
    if values is None:
        return []
    array = np.asarray(values).reshape(-1)
    return [
        float(value)
        for value in array
        if finite_number(value) is not None
    ]


def nullable_list(values):
    return [
        finite_number(value)
        for value in np.asarray(values).reshape(-1)
    ]


def compact_indices(values, max_points=MAX_SPECTRUM_POINTS, selected_index=None):
    values = np.asarray(values, dtype=float)
    count = int(values.size)
    if count <= max_points:
        return np.arange(count, dtype=int)

    keep = set(np.linspace(0, count - 1, max_points, dtype=int).tolist())
    top_count = min(80, count)
    if top_count:
        top_indices = np.argpartition(values, count - top_count)[-top_count:]
        keep.update(int(index) for index in top_indices)
    if selected_index is not None:
        keep.add(int(selected_index))
    return np.asarray(sorted(keep), dtype=int)


def distinct_period_candidates(periods, power, power_raw, limit=8):
    periods = np.asarray(periods, dtype=float)
    power = np.asarray(power, dtype=float)
    power_raw = np.asarray(power_raw, dtype=float)
    valid = np.isfinite(periods) & np.isfinite(power) & (periods > 0)
    if not np.any(valid):
        return []

    valid_indices = np.flatnonzero(valid)
    local_indices = []
    for index in valid_indices:
        left = power[index - 1] if index > 0 else -math.inf
        right = power[index + 1] if index + 1 < power.size else -math.inf
        if power[index] >= left and power[index] >= right:
            local_indices.append(int(index))
    if not local_indices:
        local_indices = valid_indices.tolist()

    ordered = sorted(local_indices, key=lambda index: power[index], reverse=True)
    candidates = []
    for index in ordered:
        period = float(periods[index])
        if any(abs(period - item["period"]) / period < 0.01 for item in candidates):
            continue
        raw_value = finite_number(power_raw[index]) if index < power_raw.size else None
        candidates.append({
            "period": period,
            "power": raw_value,
            "sde": float(power[index]),
            "method": "TLS",
        })
        if len(candidates) >= limit:
            break
    return candidates


def compact_model(time_values, flux_values, max_points=MAX_MODEL_POINTS):
    time_values = np.asarray(time_values, dtype=float).reshape(-1)
    flux_values = np.asarray(flux_values, dtype=float).reshape(-1)
    size = min(time_values.size, flux_values.size)
    if size == 0:
        return [], []
    time_values = time_values[:size]
    flux_values = flux_values[:size]
    valid = np.isfinite(time_values) & np.isfinite(flux_values)
    time_values = time_values[valid]
    flux_values = flux_values[valid]
    if time_values.size > max_points:
        # Uniform subsampling can skip every sample in a narrow transit. Retain
        # the local minimum and maximum from each time-ordered bucket so ingress,
        # the transit bottom, egress, and baseline survive compaction.
        bucket_count = max(1, (max_points - 2) // 2)
        edges = np.linspace(0, time_values.size, bucket_count + 1, dtype=int)
        keep = {0, int(time_values.size - 1)}
        for start, end in zip(edges[:-1], edges[1:]):
            if end <= start:
                continue
            bucket = flux_values[start:end]
            keep.add(start + int(np.argmin(bucket)))
            keep.add(start + int(np.argmax(bucket)))
        keep = np.asarray(sorted(keep), dtype=int)
        time_values = time_values[keep]
        flux_values = flux_values[keep]
    return time_values.tolist(), flux_values.tolist()


def duration_from_folded_model(phase_days, model_flux, period=None):
    phase_days = np.asarray(phase_days, dtype=float).reshape(-1)
    model_flux = np.asarray(model_flux, dtype=float).reshape(-1)
    size = min(phase_days.size, model_flux.size)
    if size < 3:
        return None
    phase_days = phase_days[:size]
    model_flux = model_flux[:size]
    valid = np.isfinite(phase_days) & np.isfinite(model_flux)
    phase_days = phase_days[valid]
    model_flux = model_flux[valid]
    if phase_days.size < 3:
        return None

    baseline = float(np.max(model_flux))
    bottom = float(np.min(model_flux))
    depth = baseline - bottom
    if not math.isfinite(depth) or depth <= 0:
        return None

    # The reference result duration can be compressed by its global gap
    # fill-factor correction. The fitted folded model still contains the true
    # T14-like support, so measure where it differs materially from baseline.
    in_transit = model_flux < baseline - depth * 0.001
    if np.count_nonzero(in_transit) < 2:
        return None
    transit_phase = phase_days[in_transit]
    duration = float(np.max(transit_phase) - np.min(transit_phase))
    if duration <= 0:
        return None
    if period is not None and duration >= float(period) * 0.5:
        return None
    return duration


def model_contact_sample_count(model_flux):
    values = np.asarray(model_flux, dtype=float).reshape(-1)
    values = values[np.isfinite(values)]
    if values.size < 3:
        return 0
    baseline, bottom = float(np.max(values)), float(np.min(values))
    depth = baseline - bottom
    return int(np.count_nonzero(values < baseline - depth * .001)) if depth > 0 else 0


def compact_folded_transit_model(phase_days, model_flux, max_points=MAX_MODEL_POINTS):
    """Spend the transport point budget on real template contact detail."""
    phase, values = np.asarray(phase_days, dtype=float), np.asarray(model_flux, dtype=float)
    size = min(phase.size, values.size)
    if size <= max_points:
        return compact_model(phase, values, max_points=max_points)
    phase, values = phase[:size], values[:size]
    valid = np.isfinite(phase) & np.isfinite(values)
    phase, values = phase[valid], values[valid]
    if len(phase) < 3:
        return phase.tolist(), values.tolist()
    baseline = float(np.max(values))
    depth = baseline - float(np.min(values))
    contact = np.flatnonzero(values < baseline - depth * 1e-10)
    if not contact.size:
        return compact_model(phase, values, max_points=max_points)
    left, right = max(0, int(contact[0]) - 1), min(len(phase), int(contact[-1]) + 2)
    contact_phase, contact_flux = compact_model(phase[left:right], values[left:right], max_points=max_points - 2)
    phases = np.r_[phase[0], contact_phase, phase[-1]]
    fluxes = np.r_[values[0], contact_flux, values[-1]]
    order = np.argsort(phases)
    phases, fluxes = phases[order], fluxes[order]
    phases, unique = np.unique(phases, return_index=True)
    return phases.tolist(), fluxes[unique].tolist()


def representative_unfolded_transit(model_time, model_flux, transit_times, period):
    model_time = np.asarray(model_time, dtype=float).reshape(-1)
    model_flux = np.asarray(model_flux, dtype=float).reshape(-1)
    transit_times = np.asarray(transit_times, dtype=float).reshape(-1)
    size = min(model_time.size, model_flux.size)
    period = finite_number(period)
    if size < 3 or period is None or period <= 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)

    model_time = model_time[:size]
    model_flux = model_flux[:size]
    valid = np.isfinite(model_time) & np.isfinite(model_flux)
    model_time = model_time[valid]
    model_flux = model_flux[valid]
    transit_times = transit_times[np.isfinite(transit_times)]
    if model_time.size < 3 or transit_times.size == 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)

    model_min = float(np.min(model_time))
    model_max = float(np.max(model_time))
    complete_centers = transit_times[
        (transit_times - period / 2.0 >= model_min)
        & (transit_times + period / 2.0 <= model_max)
    ]
    centers = complete_centers if complete_centers.size else transit_times
    center = float(centers[len(centers) // 2])
    in_cycle = (
        (model_time >= center - period / 2.0)
        & (model_time <= center + period / 2.0)
    )
    if np.count_nonzero(in_cycle) < 3:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)

    phase_days = model_time[in_cycle] - center
    cycle_flux = model_flux[in_cycle]
    order = np.argsort(phase_days)
    phase_days = phase_days[order]
    cycle_flux = cycle_flux[order]
    phase_days, unique_indices = np.unique(phase_days, return_index=True)
    cycle_flux = cycle_flux[unique_indices]
    return phase_days, cycle_flux


def sampling_fill_factor(time):
    time = np.asarray(time, dtype=float).reshape(-1)
    time = np.sort(np.unique(time[np.isfinite(time)]))
    if time.size < 2:
        return None
    span = float(time[-1] - time[0])
    positive_steps = np.diff(time)
    positive_steps = positive_steps[positive_steps > 0]
    if span <= 0 or positive_steps.size == 0:
        return None
    cadence = float(np.median(positive_steps))
    if not math.isfinite(cadence) or cadence <= 0:
        return None
    theoretical_cadences = span / cadence
    if theoretical_cadences <= 0:
        return None
    return float(min(1.0, max((time.size - 1) / theoretical_cadences, 1e-9)))


def rescale_folded_model_duration(phase_days, model_flux, target_duration, period=None):
    phase_days = np.asarray(phase_days, dtype=float).reshape(-1)
    model_flux = np.asarray(model_flux, dtype=float).reshape(-1)
    size = min(phase_days.size, model_flux.size)
    target_duration = finite_number(target_duration)
    period = finite_number(period)
    if size < 3 or target_duration is None or target_duration <= 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    if period is not None and target_duration >= period * 0.5:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)

    phase_days = phase_days[:size]
    model_flux = model_flux[:size]
    valid = np.isfinite(phase_days) & np.isfinite(model_flux)
    phase_days = phase_days[valid]
    model_flux = model_flux[valid]
    if phase_days.size < 3:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)

    order = np.argsort(phase_days)
    phase_days = phase_days[order]
    model_flux = model_flux[order]
    baseline = float(np.max(model_flux))
    bottom = float(np.min(model_flux))
    depth = baseline - bottom
    if not math.isfinite(depth) or depth <= 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)

    in_transit = model_flux < baseline - depth * 0.001
    if np.count_nonzero(in_transit) < 2:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    # The material-depth threshold measures a diagnostic width. Rescaling
    # contacts instead needs the full nonbaseline support so that its nearest
    # outside anchors really have zero deficit, including fine limb tails.
    transit_indices = np.flatnonzero(model_flux < baseline - depth * 1e-10)
    left_index = max(0, int(transit_indices[0]) - 1)
    right_index = min(len(phase_days) - 1, int(transit_indices[-1]) + 1)
    source_left = float(phase_days[left_index])
    source_right = float(phase_days[right_index])
    source_duration = source_right - source_left
    if source_duration <= 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)

    source_center = (source_left + source_right) / 2.0
    target_center = 0.0
    scale = target_duration / source_duration
    contact_window = np.arange(len(phase_days))
    contact_window = (contact_window >= left_index) & (contact_window <= right_index)
    scaled_contact_phase = target_center + (
        phase_days[contact_window] - source_center
    ) * scale
    outside_target = np.abs(phase_days - target_center) > target_duration / 2.0
    keep_baseline = (~contact_window) & (~in_transit) & outside_target
    scaled_phase = np.r_[phase_days[keep_baseline], scaled_contact_phase]
    scaled_flux = np.r_[model_flux[keep_baseline], model_flux[contact_window]]
    scaled_order = np.argsort(scaled_phase)
    scaled_phase = scaled_phase[scaled_order]
    scaled_flux = scaled_flux[scaled_order]
    scaled_phase, unique_indices = np.unique(scaled_phase, return_index=True)
    scaled_flux = scaled_flux[unique_indices]
    return scaled_phase, scaled_flux


def observed_phase_folded_duration(time, flux, period, epoch, seed_duration):
    time = np.asarray(time, dtype=float).reshape(-1)
    flux = np.asarray(flux, dtype=float).reshape(-1)
    size = min(time.size, flux.size)
    period = finite_number(period)
    epoch = finite_number(epoch)
    seed_duration = finite_number(seed_duration)
    if (
        size < 20
        or period is None
        or epoch is None
        or seed_duration is None
        or period <= 0
        or seed_duration <= 0
    ):
        return None

    time = time[:size]
    flux = flux[:size]
    valid = np.isfinite(time) & np.isfinite(flux)
    time = time[valid]
    flux = flux[valid]
    if time.size < 20:
        return None

    unique_time = np.sort(np.unique(time))
    steps = np.diff(unique_time)
    steps = steps[steps > 0]
    if steps.size == 0:
        return None
    cadence = float(np.median(steps))
    focus = min(period * 0.22, max(seed_duration * 3.0, cadence * 40.0))
    if focus <= seed_duration / 2.0:
        return None

    bin_width = max(cadence, seed_duration / 60.0)
    bin_count = max(25, int(math.ceil(2.0 * focus / bin_width)))
    edges = np.linspace(-focus, focus, bin_count + 1)
    centers = (edges[:-1] + edges[1:]) / 2.0
    phase = ((time - epoch + period / 2.0) % period) - period / 2.0
    bin_ids = np.digitize(phase, edges) - 1
    binned_flux = np.asarray([
        np.median(flux[bin_ids == index])
        if np.any(bin_ids == index)
        else np.nan
        for index in range(bin_count)
    ])
    smooth_flux = np.full(bin_count, np.nan, dtype=float)
    for index in range(bin_count):
        window = binned_flux[max(0, index - 1):min(bin_count, index + 2)]
        finite_window = window[np.isfinite(window)]
        if finite_window.size:
            smooth_flux[index] = float(np.mean(finite_window))
    finite_bins = np.isfinite(smooth_flux)

    shoulder_min = max(seed_duration * 0.9, cadence * 8.0)
    shoulder_max = min(
        focus * 0.95,
        max(seed_duration * 2.2, shoulder_min + cadence * 12.0),
    )
    shoulder_mask = (
        finite_bins
        & (np.abs(centers) >= shoulder_min)
        & (np.abs(centers) <= shoulder_max)
    )
    shoulder_flux = smooth_flux[shoulder_mask]
    core_mask = finite_bins & (np.abs(centers) <= max(seed_duration * 0.3, cadence * 3.0))
    core_flux = smooth_flux[core_mask]
    if shoulder_flux.size < 8 or core_flux.size < 3:
        return None

    baseline = float(np.median(shoulder_flux))
    baseline_noise = 1.4826 * float(np.median(np.abs(shoulder_flux - baseline)))
    bottom = float(np.percentile(core_flux, 15.0))
    depth = baseline - bottom
    if not math.isfinite(depth) or depth <= max(baseline_noise * 5.0, 1e-9):
        return None

    threshold_drop = max(depth * 0.05, baseline_noise * 3.0)
    in_signal = finite_bins & (smooth_flux < baseline - threshold_drop)
    for index in range(1, len(in_signal) - 1):
        if not in_signal[index] and in_signal[index - 1] and in_signal[index + 1]:
            in_signal[index] = True

    core_indices = np.flatnonzero(core_mask)
    if core_indices.size == 0:
        return None
    center_index = int(core_indices[np.argmin(smooth_flux[core_indices])])
    if not in_signal[center_index]:
        return None
    left = center_index
    while left > 0 and in_signal[left - 1]:
        left -= 1
    right = center_index
    while right + 1 < len(in_signal) and in_signal[right + 1]:
        right += 1
    if left == 0 or right == len(in_signal) - 1:
        return None

    measured_start = float(edges[left])
    measured_end = float(edges[right + 1])
    padding = float(edges[1] - edges[0])
    symmetric_duration = 2.0 * max(
        abs(measured_start - padding),
        abs(measured_end + padding),
    )
    maximum_duration = min(period * 0.25, seed_duration * 2.5)
    if symmetric_duration <= seed_duration or symmetric_duration > maximum_duration:
        return None
    return {
        "duration": float(symmetric_duration),
        "measured_start": measured_start,
        "measured_end": measured_end,
        "bin_width": padding,
        "baseline": baseline,
        "depth": depth,
        "baseline_noise": baseline_noise,
        "threshold_drop": threshold_drop,
    }


def tls_engine_version():
    if tls_constants is None:
        return None
    version = str(getattr(tls_constants, "TLS_VERSION", "TLS 1.32"))
    return version.replace("Transit Least Squares ", "").strip()


def exposure_array_seconds(exposure_seconds, size):
    """Return aligned durations; NaN means unknown, zero means instantaneous."""
    if exposure_seconds is None:
        return np.full(size, np.nan)
    values = np.asarray(exposure_seconds, dtype=float)
    if values.ndim == 0:
        values = np.full(size, float(values))
    if values.ndim != 1 or len(values) != size:
        raise ValueError("Exposure durations must align with observations.")
    if np.any(np.isinf(values)) or np.any(values[np.isfinite(values)] < 0):
        raise ValueError("Exposure durations must be nonnegative finite seconds or null when unknown.")
    return values


def exposure_integrated_template(phase_days, template_phase, template_flux, period,
                                 exposure_seconds=None, baseline=1.0):
    """Evaluate a periodic template at the actual exposure midpoints.

    Unknown durations use an explicitly reported instantaneous approximation.
    The periodic piecewise-linear model is integrated exactly, including whole
    orbital cycles. Cadence and plotting-bin widths are never exposures. The
    caller supplies midpoint timestamps.
    """
    phases = np.asarray(phase_days, dtype=float)
    exposures = exposure_array_seconds(exposure_seconds, len(phases))
    period = float(period)
    if not math.isfinite(period) or period <= 0:
        raise ValueError("Exposure integration requires a positive finite period.")
    template_phase, template_flux = np.asarray(template_phase, dtype=float), np.asarray(template_flux, dtype=float)
    wrapped = (phases + period / 2.0) % period - period / 2.0
    result = np.interp(wrapped, template_phase, template_flux, left=baseline, right=baseline)
    finite = np.flatnonzero(np.isfinite(exposures) & (exposures > 0))
    if not finite.size:
        return result
    # Integrate deviations to avoid subtracting nearly equal baseline areas.
    # Outside the supplied template the deviation is zero, matching np.interp.
    deviation = template_flux - baseline
    intervals = np.diff(template_phase)
    if len(template_phase) < 2 or np.any(intervals <= 0):
        raise ValueError("Exposure integration requires a sorted unique template with at least two points.")
    slopes = np.diff(deviation) / intervals
    cumulative = np.r_[0.0, np.cumsum(intervals * (deviation[:-1] + deviation[1:]) / 2.0)]

    def primitive(position):
        position = np.asarray(position, dtype=float)
        indices = np.searchsorted(template_phase, position, side="right") - 1
        clipped = np.clip(indices, 0, len(template_phase) - 2)
        offset = position - template_phase[clipped]
        area = cumulative[clipped] + deviation[clipped] * offset + slopes[clipped] * offset ** 2 / 2.0
        return np.where(position <= template_phase[0], 0.0,
                        np.where(position >= template_phase[-1], cumulative[-1], area))

    left = -period / 2.0
    origin_area = float(primitive(left))
    cycle_area = float(primitive(period / 2.0)) - origin_area

    def periodic_primitive(position):
        cycles = np.floor((position - left) / period)
        local = (position - left) % period + left
        return cycles * cycle_area + primitive(local) - origin_area

    width = exposures[finite] / 86400.0
    centers = wrapped[finite]
    result[finite] = baseline + (periodic_primitive(centers + width / 2.0)
                                - periodic_primitive(centers - width / 2.0)) / width
    return result


def fit_observed_model_duration(time, flux, period, epoch, seed_duration, phase, model_flux,
                                exposure_seconds=None, flux_uncertainty=None):
    """Refit the physical template's width/depth on matched search observations.

    Unlike threshold-based widening, this can shorten or lengthen a duration.
    Known exposure durations are integrated at actual observation midpoints.
    Unknown exposure is explicitly instantaneous; cadence is not exposure.
    This is a conditional template fit, not a new period search or a posterior.
    """
    try:
        from scipy.optimize import least_squares
    except ImportError:
        return None
    time = np.asarray(time, dtype=float)
    flux = np.asarray(flux, dtype=float)
    exposures = exposure_array_seconds(exposure_seconds, len(time))
    supplied_errors = np.asarray(flux_uncertainty, dtype=float) if flux_uncertainty is not None else None
    if supplied_errors is not None and (supplied_errors.ndim != 1 or len(supplied_errors) != len(time)):
        raise ValueError("Flux uncertainties must align with observations.")
    phase = np.asarray(phase, dtype=float)
    model_flux = np.asarray(model_flux, dtype=float)
    if len(time) < 50 or len(phase) < 5 or seed_duration <= 0:
        return None
    order = np.argsort(phase)
    phase, model_flux = phase[order], model_flux[order]
    phase, unique = np.unique(phase, return_index=True)
    model_flux = model_flux[unique]
    template_depth = float(np.max(model_flux) - np.min(model_flux))
    if template_depth <= 1e-9:
        return None
    unit_depth = (np.max(model_flux) - model_flux) / template_depth
    cadence_steps = np.diff(np.unique(time))
    cadence_steps = cadence_steps[cadence_steps > 0]
    cadence = float(np.median(cadence_steps)) if cadence_steps.size else seed_duration / 20
    focus = min(period * 0.35, seed_duration * 2.5)
    folded = ((time - epoch + period / 2) % period) - period / 2
    # A median bin estimates location robustly; its standard error includes n.
    width = max(seed_duration / 45.0, cadence / 3.0)
    edges = np.linspace(-focus, focus, max(31, min(501, int(2 * focus / width))) + 1)
    bins = np.digitize(folded, edges) - 1
    global_sigma = max(1.4826 * np.median(np.abs(flux - np.median(flux))), 1e-8)
    x, y, errors, sample_groups = [], [], [], []
    for index in range(len(edges) - 1):
        members = np.flatnonzero(bins == index)
        values = flux[members]
        if len(values) < 3:
            continue
        center = float(np.median(values))
        sigma = max(1.4826 * np.median(np.abs(values - center)), global_sigma * 0.25)
        x.append(float(np.median(folded[members])))
        y.append(center)
        empirical_error = 1.253 * sigma / math.sqrt(len(values))
        measurement_error = 0.0
        if supplied_errors is not None:
            local_errors = supplied_errors[members]
            if np.all(np.isfinite(local_errors)) and np.all(local_errors > 0):
                measurement_error = 1.253 * float(np.sqrt(np.sum(local_errors ** 2))) / len(values)
        errors.append(max(empirical_error, measurement_error, 1e-8))
        # Bound fit cost while sampling actual phases and exposures across the
        # observing baseline. No artificial boxcar is assigned to phase bins.
        if len(members) > 32:
            members = members[np.linspace(0, len(members) - 1, 32, dtype=int)]
        sample_groups.append(members)
    if len(x) < 20:
        return None
    x, y, errors = np.asarray(x), np.asarray(y), np.asarray(errors)
    shoulders = np.abs(x) > seed_duration
    core = np.abs(x) < seed_duration * 0.35
    if np.count_nonzero(shoulders) < 6 or np.count_nonzero(core) < 4:
        return None
    baseline = float(np.median(y[shoulders]))
    measured_depth = baseline - float(np.percentile(y[core], 20))
    if measured_depth <= max(float(np.median(errors[core])) * 5.0, 1e-8):
        return None
    sample_indices = np.concatenate(sample_groups)
    sample_starts = np.r_[0, np.cumsum([len(group) for group in sample_groups])]
    sample_phase = folded[sample_indices]
    sample_exposure = exposures[sample_indices]

    def evaluate(parameters):
        scale, shift, depth, level = parameters
        shape_at_samples = exposure_integrated_template(
            (sample_phase - shift) / scale, phase, unit_depth, period / scale,
            sample_exposure / scale, baseline=0.0)
        shape = np.asarray([np.median(shape_at_samples[left:right])
                            for left, right in zip(sample_starts[:-1], sample_starts[1:])])
        return level - depth * shape

    initial = [1.0, 0.0, measured_depth, baseline]
    fit = least_squares(lambda pars: (evaluate(pars) - y) / errors, initial,
                        bounds=([0.55, -seed_duration * 0.2, 0, baseline - measured_depth],
                                [1.8, seed_duration * 0.2, measured_depth * 3, baseline + measured_depth]),
                        loss="soft_l1", max_nfev=120)
    if not fit.success or not np.all(np.isfinite(fit.x)):
        return None
    scale, shift, depth, level = fit.x
    if scale <= 0.56 or scale >= 1.79 or depth <= 0:
        return None
    variance = float(np.sum(fit.fun ** 2) / max(len(x) - 4, 1))
    try:
        covariance = np.linalg.pinv(fit.jac.T @ fit.jac) * max(1.0, variance)
        duration_error = float(math.sqrt(max(0.0, covariance[0, 0])) * seed_duration)
    except np.linalg.LinAlgError:
        duration_error = None
    fitted_duration = float(seed_duration * scale)
    if duration_error is None or duration_error > fitted_duration * 0.3:
        return None
    known_count = int(np.count_nonzero(np.isfinite(exposures)))
    return {"duration": fitted_duration, "duration_uncertainty": max(duration_error, cadence / math.sqrt(max(np.count_nonzero(core), 1))),
            "epoch_shift": float(shift), "depth": float(depth), "baseline": float(level),
            "bin_count": len(x), "representative_sample_count": len(sample_indices), "reduced_chi_squared": variance,
            "method": "robust conditional template fit at observed exposure midpoints",
            "exposure": {"known_rows": known_count, "unknown_rows": len(time) - known_count,
                "unit": "seconds", "cadence_is_exposure": False,
                "integration": "exact periodic piecewise-linear template integral for declared finite durations; instantaneous for zero or unknown",
                "unknown_policy": "instantaneous approximation; exposure smearing uncertainty is not included"},
            "uncertainty_basis": "local Jacobian, empirical/input-error bin uncertainties and cadence floor; conditional on period, template, and declared exposure; excludes unknown exposure systematics"}


def run_tls_search(time, flux, options, progress_callback=None):
    if transitleastsquares is None:
        detail = f" ({TLS_IMPORT_ERROR})" if TLS_IMPORT_ERROR else ""
        raise ValueError(
            "TLS mode requires the transitleastsquares package. "
            "Install the project requirements and try again." + detail
        )

    time = np.asarray(time, dtype=float)
    flux = np.asarray(flux, dtype=float)
    if time.size < 20 or flux.size != time.size:
        raise ValueError("TLS needs at least 20 matching time/flux samples.")

    time_origin = float(time[0])
    relative_time = time - time_origin
    supplied_uncertainty = options.get("_normalized_flux_uncertainty")
    uncertainty = np.asarray(supplied_uncertainty, dtype=float) if supplied_uncertainty is not None else None
    if uncertainty is not None and uncertainty.size == time.size and np.all(np.isfinite(uncertainty)) and np.all(uncertainty > 0):
        model = transitleastsquares(relative_time, flux, dy=uncertainty, verbose=False)
    else:
        model = transitleastsquares(relative_time, flux, verbose=False)

    kwargs = {
        "period_min": float(options["period_min"]),
        "period_max": float(options["period_max"]),
        "n_transits_min": int(options.get("tls_min_transits", 3)),
        "transit_template": options.get("tls_template", "default"),
        "oversampling_factor": int(options.get("tls_oversampling", 3)),
        "duration_grid_step": float(options.get("tls_duration_grid_step", 1.1)),
        "transit_depth_min": float(options.get("tls_min_depth_ppm", 10.0)) / 1000000.0,
        "use_threads": int(options.get("tls_threads", 4)),
        "show_progress_bar": False,
        "verbose": False,
    }

    stellar_radius = finite_number(options.get("stellar_radius"))
    stellar_mass = finite_number(options.get("stellar_mass"))
    if stellar_radius is not None:
        kwargs.update({
            "R_star": stellar_radius,
            "R_star_min": max(0.1, stellar_radius * 0.7),
            "R_star_max": stellar_radius * 1.3,
        })
    if stellar_mass is not None:
        kwargs.update({
            "M_star": stellar_mass,
            "M_star_min": max(0.01, stellar_mass * 0.7),
            "M_star_max": stellar_mass * 1.3,
        })

    limb_u1 = finite_number(options.get("limb_darkening_u1"))
    limb_u2 = finite_number(options.get("limb_darkening_u2"))
    if limb_u1 is not None and limb_u2 is not None:
        kwargs["u"] = [limb_u1, limb_u2]
        kwargs["limb_dark"] = "quadratic"

    with measured_tls_progress(progress_callback) as reports_trials:
        kwargs["show_progress_bar"] = reports_trials
        results = model.power(**kwargs)
    period = finite_number(getattr(results, "period", None))
    duration = finite_number(getattr(results, "duration", None))
    transit_time_relative = finite_number(getattr(results, "T0", None))
    if period is None or duration is None or transit_time_relative is None or period <= 0 or duration <= 0:
        raise ValueError(
            "TLS did not fit a valid transit. Try a smaller TLS minimum depth, "
            "wider period bounds, or different stellar priors."
        )

    periods = np.asarray(getattr(results, "periods", []), dtype=float)
    lower, upper = float(options["period_min"]), float(options["period_max"])
    tolerance = max(1e-10, max(abs(lower), abs(upper)) * 1e-10)
    if (period < lower - tolerance or period > upper + tolerance
            or np.any(~np.isfinite(periods))
            or np.any(periods < lower - tolerance) or np.any(periods > upper + tolerance)):
        # Reference TLS 1.32 can fall back to its default grid when a requested
        # grid is too small, dropping the caller's bounds in the recursive call.
        raise ValueError("TLS generated periods outside requested bounds; widen the period bounds or increase TLS oversampling and try again.")
    actual_period_bounds = {"minimum": float(np.min(periods)) if periods.size else period,
                            "maximum": float(np.max(periods)) if periods.size else period,
                            "count": int(periods.size)}
    power = np.asarray(getattr(results, "power", []), dtype=float)
    power_raw = np.asarray(getattr(results, "power_raw", []), dtype=float)
    spectrum_size = min(periods.size, power.size)
    periods = periods[:spectrum_size]
    power = power[:spectrum_size]
    power_raw = power_raw[:spectrum_size]
    selected_index = int(np.nanargmin(np.abs(periods - period))) if periods.size else None
    keep = compact_indices(power, selected_index=selected_index) if periods.size else np.asarray([], dtype=int)

    raw_model_time = np.asarray(getattr(results, "model_lightcurve_time", []), dtype=float)
    raw_model_flux = np.asarray(getattr(results, "model_lightcurve_model", []), dtype=float)
    transit_times_relative = finite_list(getattr(results, "transit_times", []))
    model_time, model_flux = compact_model(raw_model_time, raw_model_flux)
    folded_phase = np.asarray(getattr(results, "model_folded_phase", []), dtype=float)
    folded_model = np.asarray(getattr(results, "model_folded_model", []), dtype=float)
    folded_phase_days = (folded_phase - 0.5) * period if folded_phase.size else folded_phase
    engine_duration = duration
    folded_engine_duration = duration_from_folded_model(folded_phase_days, folded_model, period)
    unfolded_phase_days, unfolded_model = representative_unfolded_transit(
        raw_model_time,
        raw_model_flux,
        transit_times_relative,
        period,
    )
    unfolded_model_duration = duration_from_folded_model(
        unfolded_phase_days,
        unfolded_model,
        period,
    )
    folded_contact_samples = model_contact_sample_count(folded_model)
    unfolded_contact_samples = model_contact_sample_count(unfolded_model)
    # TLS's unfolded single cycle uses N / all predicted epochs samples.
    # Long observing gaps can leave only a handful of contact points there,
    # while the independently generated folded physical template is dense.
    # Retain the representation with real contact detail before any rescaling;
    # interpolating a coarse cycle cannot reconstruct its missing shape.
    if folded_engine_duration is not None and (unfolded_model_duration is None
                                               or folded_contact_samples >= unfolded_contact_samples):
        payload_phase = folded_phase_days
        payload_flux = folded_model
        template_source = "engine folded template"
    elif unfolded_model_duration is not None:
        payload_phase = unfolded_phase_days
        payload_flux = unfolded_model
        template_source = "engine unfolded cycle"
    else:
        payload_phase = folded_phase_days
        payload_flux = folded_model
        template_source = "engine folded fallback"

    fill_factor = sampling_fill_factor(relative_time)
    uncompressed_duration = (
        engine_duration / fill_factor
        if fill_factor is not None and fill_factor > 0
        else None
    )
    if (
        uncompressed_duration is not None
        and math.isfinite(uncompressed_duration)
        and 0 < uncompressed_duration < period * 0.5
    ):
        corrected_phase, corrected_flux = rescale_folded_model_duration(
            payload_phase,
            payload_flux,
            uncompressed_duration,
            period,
        )
        corrected_model_duration = duration_from_folded_model(
            corrected_phase,
            corrected_flux,
            period,
        )
    else:
        corrected_phase = np.asarray([], dtype=float)
        corrected_flux = np.asarray([], dtype=float)
        corrected_model_duration = None

    if corrected_model_duration is not None:
        duration = uncompressed_duration
        payload_phase = corrected_phase
        payload_flux = corrected_flux
        duration_source = "TLS duration with sampling-gap compression removed"
    elif unfolded_model_duration is not None:
        duration = unfolded_model_duration
        # The unfolded model remains a duration diagnostic even when its
        # sparse shape is replaced by the independently dense folded template.
        if template_source == "engine folded template":
            payload_phase, payload_flux = rescale_folded_model_duration(
                payload_phase, payload_flux, duration, period)
        duration_source = "unfolded TLS model"
    else:
        if folded_engine_duration is not None:
            duration = folded_engine_duration
        duration_source = "folded TLS model fallback"

    search_sde = finite_number(getattr(results, "SDE", None))
    observed_refinement = (
        observed_phase_folded_duration(
            relative_time,
            flux,
            period,
            transit_time_relative,
            duration,
        )
        if search_sde is not None and search_sde >= 5.0
        else None
    )
    # Retain the threshold width as a diagnostic, not an automatic one-way
    # expansion. Its smoothed-bin padding systematically broadened contacts.
    observed_fit = (
        fit_observed_model_duration(relative_time, flux, period, transit_time_relative,
                                    duration, payload_phase, payload_flux,
                                    exposure_seconds=(options.get("exposure_seconds") if options.get("exposure_seconds") is not None
                                                      else options.get("_exposure_seconds")),
                                    flux_uncertainty=uncertainty)
        if search_sde is not None and search_sde >= 7.0 else None
    )
    observed_model_duration = None
    if observed_fit is not None:
        fitted_phase, fitted_flux = rescale_folded_model_duration(
            payload_phase, payload_flux, observed_fit["duration"], period)
        old_depth = float(np.max(fitted_flux) - np.min(fitted_flux))
        if old_depth > 0:
            fitted_flux = observed_fit["baseline"] - (np.max(fitted_flux) - fitted_flux) * observed_fit["depth"] / old_depth
        duration = observed_fit["duration"]
        payload_phase, payload_flux = fitted_phase, fitted_flux
        transit_time_relative += observed_fit["epoch_shift"]
        transit_times_relative = [value + observed_fit["epoch_shift"] for value in transit_times_relative]
        observed_model_duration = duration_from_folded_model(payload_phase, payload_flux, period)
        duration_source = ("observed exposure-integrated physical template fit"
                           if observed_fit["exposure"]["unknown_rows"] == 0
                           else "observed physical template fit; unknown exposures approximated as instantaneous")
    model_folded_phase, model_folded_flux = compact_folded_transit_model(payload_phase, payload_flux)

    transit_times = [time_origin + value for value in transit_times_relative]
    transit_flux_levels = finite_list(getattr(results, "transit_depths", []))
    transit_depth_fractions = [max(0.0, 1.0 - value) for value in transit_flux_levels]
    depth_mean = getattr(results, "depth_mean", None)
    depth_mean_flux = None
    depth_mean_uncertainty = None
    if isinstance(depth_mean, (tuple, list, np.ndarray)) and len(depth_mean) >= 2:
        depth_mean_flux = finite_number(depth_mean[0])
        depth_mean_uncertainty = finite_number(depth_mean[1])
    bottom_flux = finite_number(getattr(results, "depth", None))

    return {
        "period": period,
        "period_uncertainty": finite_number(getattr(results, "period_uncertainty", None)),
        "duration": duration,
        "engine_duration": engine_duration,
        "folded_engine_duration": folded_engine_duration,
        "unfolded_model_duration": unfolded_model_duration,
        "sampling_fill_factor": fill_factor,
        "uncompressed_duration": uncompressed_duration,
        "observed_duration_refinement": observed_refinement,
        "duration_fit": observed_fit,
        "duration_uncertainty": observed_fit.get("duration_uncertainty") if observed_fit else None,
        "duration_quality": "conditional_fit" if observed_fit else "template_estimate",
        "duration_disagreement_fraction": (
            abs(observed_refinement["duration"] - duration) / duration
            if observed_refinement is not None else None
        ),
        "observed_model_duration": observed_model_duration,
        "duration_source": duration_source,
        "template_source": template_source,
        "template_resolution": {"engine_folded_contact_samples": folded_contact_samples,
                                "engine_unfolded_contact_samples": unfolded_contact_samples,
                                "retained_contact_samples": model_contact_sample_count(payload_flux),
                                "transported_contact_samples": model_contact_sample_count(model_folded_flux),
                                "policy": "retain the independently generated engine template with more real in-transit samples before rescaling"},
        "transit_time": time_origin + transit_time_relative,
        "power": finite_number(getattr(results, "SDE_raw", None)),
        "sde": finite_number(getattr(results, "SDE", None)),
        "sde_raw": finite_number(getattr(results, "SDE_raw", None)),
        "fap": finite_number(getattr(results, "FAP", None)),
        "snr": finite_number(getattr(results, "snr", None)),
        "rp_rs": finite_number(getattr(results, "rp_rs", None)),
        "odd_even_mismatch_sigma": finite_number(getattr(results, "odd_even_mismatch", None)),
        "chi_squared": finite_number(getattr(results, "chi2_min", None)),
        "reduced_chi_squared": finite_number(getattr(results, "chi2red_min", None)),
        "transit_count": finite_int(getattr(results, "transit_count", None)),
        "distinct_transit_count": finite_int(getattr(results, "distinct_transit_count", None)),
        "empty_transit_count": finite_int(getattr(results, "empty_transit_count", None)),
        "transit_times": transit_times,
        "per_transit_count": finite_list(getattr(results, "per_transit_count", [])),
        "transit_depth_fractions": transit_depth_fractions,
        "transit_depth_uncertainties": finite_list(getattr(results, "transit_depths_uncertainties", [])),
        "snr_per_transit": finite_list(getattr(results, "snr_per_transit", [])),
        "snr_pink_per_transit": finite_list(getattr(results, "snr_pink_per_transit", [])),
        "depth_fraction": observed_fit["depth"] if observed_fit else (None if bottom_flux is None else max(0.0, 1.0 - bottom_flux)),
        "depth_mean_fraction": None if depth_mean_flux is None else max(0.0, 1.0 - depth_mean_flux),
        "depth_mean_uncertainty": depth_mean_uncertainty,
        "candidates": distinct_period_candidates(periods, power, power_raw),
        "periodogram": {
            "periods": nullable_list(periods[keep]),
            "power": nullable_list(power_raw[keep] if power_raw.size >= spectrum_size else power[keep]),
            "sde": nullable_list(power[keep]),
            "raw_sde": nullable_list(power_raw[keep]) if power_raw.size >= spectrum_size else [],
            "method": "TLS",
            "selected_period": period,
            "point_count": int(spectrum_size),
            "shown_count": int(keep.size),
        },
        "model": {
            "time": model_time,
            "flux": model_flux,
            "folded_phase_days": model_folded_phase,
            "folded_flux": model_folded_flux,
            "duration_source": duration_source,
            "template_source": template_source,
        },
        "engine": tls_engine_version(),
        "parameters": kwargs,
        "actual_period_grid": actual_period_bounds,
        "effective_stellar_priors": {
            "radius": {"value": kwargs.get("R_star", 1.0), "min": kwargs.get("R_star_min", 0.13), "max": kwargs.get("R_star_max", 3.5), "source": "explicit" if stellar_radius is not None else "TLS default"},
            "mass": {"value": kwargs.get("M_star", 1.0), "min": kwargs.get("M_star_min", 0.1), "max": kwargs.get("M_star_max", 1.0), "source": "explicit" if stellar_mass is not None else "TLS default"},
            "limb_darkening": {"coefficients": [0.0] if kwargs["transit_template"] == "box" else kwargs.get("u", [0.4804, 0.1867]),
                               "law": "linear" if kwargs["transit_template"] == "box" else "quadratic",
                               "source": "box template override" if kwargs["transit_template"] == "box" else ("explicit" if limb_u1 is not None else "TLS default")},
        },
    }
