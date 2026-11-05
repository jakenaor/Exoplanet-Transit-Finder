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
    """Adapter for TLS 1.32's actual per-period tqdm updates, without terminal I/O."""

    def __init__(self, callback, total=0, **kwargs):
        self.callback = callback
        self.total = int(total)
        self.completed = 0
        self.started = monotonic_time.monotonic()
        self.last_sent = -math.inf
        self.first_completion_time = None
        self.first_completion_count = 0
        self.samples = deque(maxlen=32)
        self.emit(force=True)

    def emit(self, force=False, finished=False):
        now = monotonic_time.monotonic()
        if not force and now - self.last_sent < 0.75:
            return
        elapsed = now - self.started
        active_elapsed = now - self.first_completion_time if self.first_completion_time is not None else 0.0
        remaining = low = high = None
        # First completion excludes interpreter/JIT/worker startup. Several
        # subsequent observations are needed before throughput is representative.
        enough = (self.completed >= max(12, int(self.total * 0.05))
                  and active_elapsed >= 4.0 and len(self.samples) >= 5)
        if enough and self.completed < self.total and not finished:
            overall_rate = (self.completed - self.first_completion_count) / max(active_elapsed, 1e-9)
            first_time, first_count = list(self.samples)[-6:][0]
            recent_rate = (self.completed - first_count) / max(now - first_time, 1e-9)
            if recent_rate > 0 and overall_rate > 0:
                work_left = self.total - self.completed
                estimates = [work_left / overall_rate, work_left / recent_rate]
                rate_ratio = max(overall_rate, recent_rate) / min(overall_rate, recent_rate)
                if rate_ratio <= 2.5:
                    remaining = estimates[0] * 0.3 + estimates[1] * 0.7
                    low = max(1.0, min(estimates) * 0.5)
                    high = max(estimates) * (3.0 if rate_ratio > 1.8 else 2.0)
        details = {
            "completed_trials": self.completed, "total_trials": self.total,
            "work_completed": self.completed, "work_total": self.total,
            "estimated_remaining_seconds": remaining,
            "eta_lower_seconds": low, "eta_upper_seconds": high,
            "remaining_seconds_range": [low, high] if low is not None else None,
            "eta_scope": "search", "search_elapsed_seconds": elapsed,
            "throughput_elapsed_seconds": active_elapsed,
            "search_complete": bool(finished),
        }
        self.callback(details)
        self.last_sent = now
        if self.completed > 0:
            self.samples.append((now, self.completed))

    def update(self, count=1):
        self.completed = min(self.total, self.completed + int(count))
        if self.first_completion_time is None and self.completed > 0:
            self.first_completion_time = monotonic_time.monotonic()
            self.first_completion_count = self.completed
            self.emit(force=True)
            return
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
    transit_indices = np.flatnonzero(in_transit)
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


def fit_observed_model_duration(time, flux, period, epoch, seed_duration, phase, model_flux):
    """Refit the physical template's width/depth on matched search observations.

    Unlike threshold-based widening, this can shorten or lengthen a duration.
    Exposure integration and binned uncertainties limit cadence/noise bias.
    This is a conditional template fit, not a new period search or a posterior.
    """
    try:
        from scipy.optimize import least_squares
    except ImportError:
        return None
    time = np.asarray(time, dtype=float)
    flux = np.asarray(flux, dtype=float)
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
    x, y, errors, widths = [], [], [], []
    for index in range(len(edges) - 1):
        values = flux[bins == index]
        if len(values) < 3:
            continue
        center = float(np.median(values))
        sigma = max(1.4826 * np.median(np.abs(values - center)), global_sigma * 0.25)
        x.append(float(np.median(folded[bins == index])))
        y.append(center)
        errors.append(max(1.253 * sigma / math.sqrt(len(values)), 1e-8))
        widths.append(float(edges[index + 1] - edges[index]))
    if len(x) < 20:
        return None
    x, y, errors = np.asarray(x), np.asarray(y), np.asarray(errors)
    widths = np.asarray(widths)
    shoulders = np.abs(x) > seed_duration
    core = np.abs(x) < seed_duration * 0.35
    if np.count_nonzero(shoulders) < 6 or np.count_nonzero(core) < 4:
        return None
    baseline = float(np.median(y[shoulders]))
    measured_depth = baseline - float(np.percentile(y[core], 20))
    if measured_depth <= max(float(np.median(errors[core])) * 5.0, 1e-8):
        return None
    exposure_offsets = np.linspace(-0.5, 0.5, 7)

    def evaluate(parameters):
        scale, shift, depth, level = parameters
        # Integrate both finite exposures and the finite phase bins.
        exposure = np.sqrt(cadence ** 2 + widths ** 2)
        sample_phase = (x[:, None] - shift + exposure[:, None] * exposure_offsets) / scale
        shape = np.interp(sample_phase.ravel(), phase, unit_depth, left=0, right=0).reshape(sample_phase.shape).mean(axis=1)
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
    return {"duration": fitted_duration, "duration_uncertainty": max(duration_error, cadence / math.sqrt(max(np.count_nonzero(core), 1))),
            "epoch_shift": float(shift), "depth": float(depth), "baseline": float(level),
            "bin_count": len(x), "reduced_chi_squared": variance,
            "method": "robust exposure-integrated conditional template fit",
            "uncertainty_basis": "local Jacobian and cadence floor; conditional on period and template"}


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
    if unfolded_model_duration is not None:
        payload_phase = unfolded_phase_days
        payload_flux = unfolded_model
    else:
        payload_phase = folded_phase_days
        payload_flux = folded_model

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
                                    duration, payload_phase, payload_flux)
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
        duration_source = "observed exposure-integrated physical template fit"
    model_folded_phase, model_folded_flux = compact_model(payload_phase, payload_flux)

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
        },
        "engine": tls_engine_version(),
        "parameters": kwargs,
        "effective_stellar_priors": {
            "radius": {"value": kwargs.get("R_star", 1.0), "min": kwargs.get("R_star_min", 0.13), "max": kwargs.get("R_star_max", 3.5), "source": "explicit" if stellar_radius is not None else "TLS default"},
            "mass": {"value": kwargs.get("M_star", 1.0), "min": kwargs.get("M_star_min", 0.1), "max": kwargs.get("M_star_max", 1.0), "source": "explicit" if stellar_mass is not None else "TLS default"},
            "limb_darkening": {"coefficients": [0.0] if kwargs["transit_template"] == "box" else kwargs.get("u", [0.4804, 0.1867]),
                               "law": "linear" if kwargs["transit_template"] == "box" else "quadratic",
                               "source": "box template override" if kwargs["transit_template"] == "box" else ("explicit" if limb_u1 is not None else "TLS default")},
        },
    }
