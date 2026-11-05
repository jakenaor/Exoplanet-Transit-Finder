import math

import numpy as np

from tls_search import run_tls_search

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


MAX_PLOT_POINTS = 12000
MAX_PERIODOGRAM_POINTS = 1600
DEFAULT_DETECTION_OPTIONS = {
    "strictness": 1.0,
    "smoothing": 1.0,
    "search_mode": "tls",
    "min_depth": None,
    "min_duration": None,
    "max_duration": None,
    "min_period": None,
    "max_period": None,
    "tls_template": "default",
    "stellar_radius": None,
    "stellar_mass": None,
    "limb_darkening_u1": None,
    "limb_darkening_u2": None,
    "tls_oversampling": 3,
    "tls_min_transits": 3,
    "tls_threads": 4,
    "tls_min_depth_ppm": 10.0,
    "tls_duration_grid_step": 1.1,
    "tls_max_signals": 1,
}


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


def parse_optional_int(form, name, low=None, high=None):
    value = parse_optional_float(form, name, low, high)
    if value is None:
        return None
    if not float(value).is_integer():
        raise ValueError(f"{name} must be a whole number.")
    return int(value)


def parse_choice(form, name, choices, default):
    raw_value = field_value(form, name)
    if raw_value is None or str(raw_value).strip() == "":
        return default
    value = str(raw_value).strip().lower().replace("_", "-")
    if value not in choices:
        allowed = ", ".join(sorted(choices))
        raise ValueError(f"{name} must be one of: {allowed}.")
    return choices[value]


def parse_detection_options(form):
    options = dict(DEFAULT_DETECTION_OPTIONS)
    strictness = parse_optional_float(form, "strictness", 0.2, 5.0)
    smoothing = parse_optional_float(form, "smoothing", 0.25, 4.0)
    if strictness is not None:
        options["strictness"] = clamp(strictness, 0.2, 5.0)
    if smoothing is not None:
        options["smoothing"] = clamp(smoothing, 0.25, 4.0)
    options["search_mode"] = parse_choice(
        form,
        "searchMode",
        {
            "bls": "bls",
            "bls-regularity": "bls",
            "bls+regularity": "bls",
            "tls": "tls",
            "tls-style": "tls",
        },
        DEFAULT_DETECTION_OPTIONS["search_mode"],
    )

    options["min_depth"] = parse_optional_float(form, "minDepth", 0.0, None)
    options["min_duration"] = parse_optional_float(form, "minDuration", 0.0, None)
    options["max_duration"] = parse_optional_float(form, "maxDuration", 0.0, None)
    options["min_period"] = parse_optional_float(form, "minPeriod", 0.0, None)
    options["max_period"] = parse_optional_float(form, "maxPeriod", 0.0, None)
    options["tls_template"] = parse_choice(
        form,
        "tlsTemplate",
        {"default": "default", "grazing": "grazing", "box": "box"},
        "default",
    )
    options["stellar_radius"] = parse_optional_float(form, "stellarRadius", 0.1, 100.0)
    options["stellar_mass"] = parse_optional_float(form, "stellarMass", 0.01, 100.0)
    options["limb_darkening_u1"] = parse_optional_float(form, "limbDarkeningU1", -1.0, 2.0)
    options["limb_darkening_u2"] = parse_optional_float(form, "limbDarkeningU2", -1.0, 2.0)
    options["tls_oversampling"] = parse_optional_int(form, "tlsOversampling", 1, 9) or 3
    options["tls_min_transits"] = parse_optional_int(form, "tlsMinTransits", 2, 10) or 3
    options["tls_max_signals"] = parse_optional_int(form, "tlsMaxSignals", 1, 5) or 1
    options["tls_threads"] = (
        parse_optional_int(form, "tlsThreads", 1, 8)
        or DEFAULT_DETECTION_OPTIONS["tls_threads"]
    )
    options["tls_min_depth_ppm"] = parse_optional_float(form, "tlsMinDepthPpm", 0.1, 500000.0) or 10.0
    options["tls_duration_grid_step"] = parse_optional_float(form, "tlsDurationGridStep", 1.01, 2.0) or 1.1
    limb_u1 = options["limb_darkening_u1"]
    limb_u2 = options["limb_darkening_u2"]
    if (limb_u1 is None) != (limb_u2 is None):
        raise ValueError("Both limbDarkeningU1 and limbDarkeningU2 are required when either is set.")
    if limb_u1 is not None and (limb_u1 + limb_u2 < 0 or limb_u1 + limb_u2 > 1.5):
        raise ValueError("Quadratic limb-darkening coefficients must have a sum between 0 and 1.5.")
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


def transit_preserving_smoothing_width(requested_width, cadence, duration):
    if (
        duration is None
        or not math.isfinite(float(duration))
        or float(duration) <= 0
        or not math.isfinite(float(cadence))
        or float(cadence) <= 0
    ):
        return int(requested_width)

    transit_samples = float(duration) / float(cadence)
    max_width = max(1, int(math.floor(transit_samples / 3.0)))
    if max_width % 2 == 0:
        max_width = max(1, max_width - 1)
    return int(min(int(requested_width), max_width))


def smoothed_transit_display_bounds(start, end, cadence, smooth_width, domain_min, domain_max):
    start = float(start)
    end = float(end)
    cadence = float(cadence)
    smooth_width = int(smooth_width)
    if not math.isfinite(cadence) or cadence <= 0 or smooth_width <= 1:
        return start, end

    smoothing_radius = (smooth_width // 2) * cadence
    return (
        float(max(domain_min, start - smoothing_radius)),
        float(min(domain_max, end + smoothing_radius)),
    )


def moving_average(values, width):
    if width <= 1:
        return values.copy()
    kernel = np.ones(width, dtype=float) / width
    padded = np.pad(values, (width // 2, width - 1 - width // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def moving_average_by_segments(values, width, segments):
    values = np.asarray(values, dtype=float)
    if width <= 1 or not segments:
        return values.copy()

    smoothed = values.copy()
    for start, end in segments:
        length = int(end - start)
        if length <= 1:
            continue
        segment_width = min(int(width), length)
        if segment_width % 2 == 0:
            segment_width -= 1
        if segment_width <= 1:
            continue
        smoothed[start:end] = moving_average(values[start:end], segment_width)
    return smoothed


def observing_segments(time):
    if len(time) == 0:
        return []
    if len(time) == 1:
        return [(0, 1)]

    deltas = np.diff(time)
    positive_deltas = deltas[np.isfinite(deltas) & (deltas > 0)]
    if positive_deltas.size == 0:
        return [(0, len(time))]

    cadence = float(np.median(positive_deltas))
    full_span = float(time[-1] - time[0])
    gap_threshold = max(cadence * 25.0, 0.25)
    if full_span > 0:
        gap_threshold = min(gap_threshold, max(cadence * 25.0, full_span * 0.08))

    starts = np.r_[0, np.where(deltas > gap_threshold)[0] + 1]
    ends = np.r_[starts[1:], len(time)]
    return [
        (int(start), int(end))
        for start, end in zip(starts, ends)
        if end > start
    ]


def flux_normalization_plan(flux):
    values = np.asarray(flux, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {
            "input_representation": "absolute or relative flux",
            "residual_scale": None,
            "method": "per-observing-segment median",
        }

    baseline = float(np.median(finite))
    low, high = np.percentile(finite, [5.0, 95.0])
    mad = float(np.median(np.abs(finite - baseline)))
    robust_spread = max(1.4826 * mad, float((high - low) / 2.0), 1e-12)
    crosses_zero = low < 0 < high
    residual_like = (
        not math.isfinite(baseline)
        or baseline <= 1e-9
        or (crosses_zero and abs(baseline) <= robust_spread * 5.0)
    )
    if not residual_like:
        return {
            "input_representation": "absolute or relative flux",
            "residual_scale": None,
            "method": "per-observing-segment median",
        }

    amplitude = float(np.percentile(np.abs(finite), 95.0))
    residual_scale = 1000000.0 if amplitude > 1.0 else 1.0
    return {
        "input_representation": (
            "zero-centered residual flux (ppm)"
            if residual_scale == 1000000.0
            else "zero-centered residual relative flux"
        ),
        "residual_scale": residual_scale,
        "method": "residual-to-relative conversion, then per-observing-segment median",
    }


def normalize_flux_by_segments(time, flux):
    plan = flux_normalization_plan(flux)
    normalized = np.asarray(flux, dtype=float).copy()
    residual_scale = plan["residual_scale"]
    if residual_scale is not None:
        normalized = 1.0 + normalized / residual_scale
    segments = observing_segments(time)

    for start, end in segments:
        segment = normalized[start:end]
        baseline = float(np.median(segment))
        if math.isfinite(baseline) and baseline > 1e-9:
            normalized[start:end] = segment / baseline

    return normalized, segments


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


def flattened_flux_for_period_search(time, flux):
    cadence = float(np.median(np.diff(time))) if len(time) > 1 else 1.0
    full_span = float(time[-1] - time[0]) if len(time) > 1 else 0.0
    if full_span <= 0:
        return None

    flattened_flux = np.empty_like(flux, dtype=float)
    for start, end in observing_segments(time):
        values = np.asarray(flux[start:end], dtype=float)
        segment_steps = np.diff(time[start:end])
        positive = segment_steps[segment_steps > 0]
        local_cadence = float(np.median(positive)) if positive.size else cadence
        # Clip only upward transients for the search. Clipping the low tail at
        # a global MAD erased deep, short transits in otherwise quiet curves.
        low, high = robust_flux_limits(values, sigma=5.0)
        clipped = np.minimum(values, high)
        trend_days = min(10.0, max(2.0, float(time[end - 1] - time[start]) / 6.0))
        trend_width = min(len(values), max(5, int(trend_days / max(local_cadence, 1e-9))))
        if trend_width % 2 == 0:
            trend_width -= 1
        # A clipped trend prevents transits from pulling the local continuum
        # down while the un-clipped downward samples remain available to TLS.
        trend = moving_average(np.clip(values, low, high), max(trend_width, 1))
        segment_flat = clipped - trend
        flattened_flux[start:end] = segment_flat - np.median(segment_flat)
    return flattened_flux


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
    auto_min_period = max(cadence * 20.0, 0.5)
    minimum_transits = int((options or {}).get("tls_min_transits", 3))
    auto_max_period = max(auto_min_period * 1.5, full_span / max(minimum_transits, 2))
    min_period = auto_min_period
    max_period = auto_max_period
    if options:
        if options.get("min_period") is not None:
            min_period = max(cadence * 2.0, float(options["min_period"]))
        if options.get("max_period") is not None:
            max_period = min(full_span * 0.95, float(options["max_period"]))
    return min_period, max_period


def duration_search_bounds(cadence, full_span, options=None):
    auto_min_duration = max(cadence * 4.0, 0.05)
    auto_max_duration = min(30.0, max(auto_min_duration * 2.0, full_span / 8.0))
    min_duration = auto_min_duration
    max_duration = auto_max_duration
    if options:
        if options.get("min_duration") is not None:
            min_duration = max(cadence * 2.0, float(options["min_duration"]))
        if options.get("max_duration") is not None:
            max_duration = min(full_span * 0.25, float(options["max_duration"]))
    return min_duration, max_duration


def period_grid(min_period, max_period, count):
    if min_period >= max_period:
        return np.asarray([], dtype=float)

    linear_periods = np.linspace(min_period, max_period, count)
    frequency_periods = 1.0 / np.linspace(1.0 / max_period, 1.0 / min_period, count)
    periods = np.unique(np.r_[linear_periods, frequency_periods])
    periods = periods[(periods >= min_period) & (periods <= max_period)]
    return np.sort(periods.astype(float))


def build_periodogram_payload(periods, powers, power_median=None, power_std=None, method=None, selected_period=None):
    periods = np.asarray(periods, dtype=float)
    powers = np.asarray(powers, dtype=float)
    size = min(periods.size, powers.size)
    if size == 0:
        return None

    periods = periods[:size]
    powers = powers[:size]
    valid = np.isfinite(periods) & np.isfinite(powers) & (periods > 0)
    if not np.any(valid):
        return None

    periods = periods[valid]
    powers = powers[valid]
    order = np.argsort(periods)
    periods = periods[order]
    powers = powers[order]
    point_count = int(periods.size)

    finite_powers = powers[np.isfinite(powers)]
    if power_median is None or power_std is None:
        if finite_powers.size >= 5:
            power_median = float(np.median(finite_powers))
            power_std = max(float(np.std(finite_powers)), 1e-9)
    if power_median is not None and power_std is not None and power_std > 0:
        sdes = (powers - float(power_median)) / float(power_std)
    else:
        sdes = np.full(periods.shape, np.nan, dtype=float)

    keep = set(np.linspace(0, point_count - 1, min(point_count, MAX_PERIODOGRAM_POINTS), dtype=int).tolist())
    top_count = min(80, point_count)
    if top_count:
        top_indices = np.argpartition(powers, point_count - top_count)[-top_count:]
        keep.update(int(index) for index in top_indices)
    if selected_period is not None and math.isfinite(float(selected_period)) and selected_period > 0:
        keep.add(int(np.argmin(np.abs(periods - float(selected_period)))))

    keep_indices = np.asarray(sorted(keep), dtype=int)
    shown_periods = periods[keep_indices]
    shown_powers = powers[keep_indices]
    shown_sdes = sdes[keep_indices]

    return {
        "periods": [float(value) for value in shown_periods],
        "power": [float(value) for value in shown_powers],
        "sde": [float(value) if math.isfinite(float(value)) else None for value in shown_sdes],
        "method": method,
        "selected_period": float(selected_period) if selected_period is not None and math.isfinite(float(selected_period)) and selected_period > 0 else None,
        "power_median": float(power_median) if power_median is not None and math.isfinite(float(power_median)) else None,
        "power_std": float(power_std) if power_std is not None and math.isfinite(float(power_std)) else None,
        "point_count": point_count,
        "shown_count": int(shown_periods.size),
    }


def constrain_duration_bounds(cadence, min_period, min_duration, max_duration, options=None):
    max_duration = min(max_duration, min_period * 0.5)
    if min_duration >= max_duration:
        if options and options.get("min_duration") is not None:
            return min_duration, max_duration
        min_duration = max(cadence * 2.0, max_duration * 0.2)
    return min_duration, max_duration


def estimate_period_with_binned_bls(time, flux, options=None):
    if len(time) < 50:
        return None

    cadence = float(np.median(np.diff(time))) if len(time) > 1 else 1.0
    full_span = float(time[-1] - time[0]) if len(time) > 1 else 0.0
    if full_span <= 0:
        return None

    flattened_flux = flattened_flux_for_period_search(time, flux)
    if flattened_flux is None:
        return None
    residual_median = float(np.median(flattened_flux))
    residual_mad = float(np.median(np.abs(flattened_flux - residual_median)))
    sigma = max(1.4826 * residual_mad, float(np.std(flattened_flux)), 1e-9)

    min_period, max_period = period_search_bounds(cadence, full_span, options)
    min_duration, max_duration = duration_search_bounds(cadence, full_span, options)
    min_duration, max_duration = constrain_duration_bounds(cadence, min_period, min_duration, max_duration, options)
    if min_period >= max_period or min_duration >= max_duration:
        return None

    periods = period_grid(min_period, max_period, 900)
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
    power_median = None
    power_std = None
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
        "periodogram": build_periodogram_payload(
            periods,
            powers,
            power_median=power_median,
            power_std=power_std,
            method="binned BLS fallback",
            selected_period=best["period"],
        ),
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

    flattened_flux = flattened_flux_for_period_search(time, flux)
    if flattened_flux is None:
        return None

    min_period, max_period = period_search_bounds(cadence, full_span, options)
    min_duration, max_duration = duration_search_bounds(cadence, full_span, options)
    min_duration, max_duration = constrain_duration_bounds(cadence, min_period, min_duration, max_duration, options)
    if min_period >= max_period or min_duration >= max_duration:
        return None

    periods = period_grid(min_period, max_period, 1200)
    durations = np.linspace(min_duration, max_duration, 12)
    try:
        model = BoxLeastSquares(time, flattened_flux)
        result = model.power(periods, durations)
    except Exception:
        return estimate_period_with_binned_bls(time, flux, options)

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
        "periodogram": build_periodogram_payload(
            result.period,
            result.power,
            power_median=power_median,
            power_std=power_std,
            method="BLS",
            selected_period=period,
        ),
        "search_min_period": float(min_period),
        "search_max_period": float(max_period),
        "search_min_duration": float(min_duration),
        "search_max_duration": float(max_duration),
        "method": "BLS",
        **(chi_squared or {}),
    }


def normalized_flux_for_tls(time, flux):
    flux = np.asarray(flux, dtype=float)
    plan = flux_normalization_plan(flux)
    residual_scale = plan["residual_scale"]
    if residual_scale is not None:
        normalized = 1.0 + flux / residual_scale
    else:
        baseline = float(np.median(flux))
        normalized = flux / baseline

    flattened = flattened_flux_for_period_search(time, normalized)
    if flattened is None:
        return None, None
    tls_flux = 1.0 + flattened
    finite = tls_flux[np.isfinite(tls_flux)]
    if finite.size == 0:
        return None, None
    positive_floor = max(float(np.percentile(finite, 0.01)), 1e-6)
    tls_flux = np.maximum(tls_flux, positive_floor)
    residual = tls_flux - 1.0
    residual_median = float(np.median(residual))
    residual_mad = float(np.median(np.abs(residual - residual_median)))
    robust_noise = max(1.4826 * residual_mad, float(np.std(residual)), 1e-9)
    return tls_flux, robust_noise


def estimate_period_with_tls(time, flux, options=None, progress_callback=None):
    if len(time) < 50:
        raise ValueError("TLS needs at least 50 finite light-curve samples.")
    if options is None:
        options = dict(DEFAULT_DETECTION_OPTIONS)

    cadence = float(np.median(np.diff(time))) if len(time) > 1 else 1.0
    full_span = float(time[-1] - time[0]) if len(time) > 1 else 0.0
    if full_span <= 0:
        return None

    tls_flux, tls_noise = normalized_flux_for_tls(time, flux)
    if tls_flux is None:
        return None
    min_period, max_period = period_search_bounds(cadence, full_span, options)
    max_period = min(max_period, full_span / max(int(options.get("tls_min_transits", 3)), 1))
    if min_period >= max_period:
        raise ValueError(
            "TLS period bounds do not leave room for the requested minimum number of transits."
        )

    tls_options = {
        **options,
        "period_min": float(min_period),
        "period_max": float(max_period),
    }
    result = run_tls_search(time, tls_flux, tls_options, progress_callback=progress_callback)
    flattened_flux = tls_flux - 1.0
    chi_squared = chi_squared_transit_probability(
        time,
        flattened_flux,
        result["period"],
        result["duration"],
        result["transit_time"],
    )
    expected_count = result.get("transit_count")
    if expected_count is None:
        first_epoch = math.ceil((time[0] - result["transit_time"]) / result["period"])
        last_epoch = math.floor((time[-1] - result["transit_time"]) / result["period"])
        expected_count = max(1, int(last_epoch - first_epoch + 1))

    return {
        "period": result["period"],
        "period_uncertainty": result.get("period_uncertainty"),
        "scatter": result.get("period_uncertainty") or 0.0,
        "count": int(expected_count),
        "duration": result["duration"],
        "transit_time": result["transit_time"],
        "power": result.get("power"),
        "sde": result.get("sde"),
        "sde_raw": result.get("sde_raw"),
        "fap": result.get("fap"),
        "snr": result.get("snr"),
        "candidates": result.get("candidates", []),
        "periodogram": result.get("periodogram"),
        "search_min_period": float(min_period),
        "search_max_period": float(max_period),
        "search_min_duration": None,
        "search_max_duration": None,
        "method": "TLS",
        "tls_noise": tls_noise,
        "tls_result": result,
        "transit_model": result.get("model"),
        **(chi_squared or {}),
    }


def robust_standard_error(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size < 2:
        return None
    center = float(np.median(values))
    sigma = max(1.4826 * float(np.median(np.abs(values - center))), 1e-9)
    # Median standard error, with a short-block noise floor for correlations.
    error = 1.253 * sigma / math.sqrt(values.size)
    if values.size >= 12:
        blocks = [np.mean(block) for block in np.array_split(values - center, min(8, values.size // 3))]
        error = max(error, float(np.std(blocks, ddof=1)) / math.sqrt(len(blocks)))
    return float(error)


def transits_from_tls_result(time, flux, tls_period):
    if tls_period is None:
        return []
    result = tls_period.get("tls_result") or {}
    duration = finite_number(tls_period.get("duration"))
    period = finite_number(tls_period.get("period"))
    epoch = finite_number(tls_period.get("transit_time"))
    if duration is None or duration <= 0 or period is None or epoch is None:
        return []
    time, flux = np.asarray(time, dtype=float), np.asarray(flux, dtype=float)
    segments = observing_segments(time)
    steps = np.diff(time)
    positive = steps[steps > 0]
    cadence = float(np.median(positive)) if positive.size else duration
    transits = []
    for center in finite_values(result.get("transit_times", [])):
        start, end = center - duration / 2.0, center + duration / 2.0
        left = int(np.searchsorted(time, start, side="left"))
        right = int(np.searchsorted(time, end, side="right"))
        count = right - left
        segment = next(((a, b) for a, b in segments if time[a] <= center <= time[b - 1]), None)
        expected_points = max(1.0, duration / max(cadence, 1e-9))
        coverage = min(1.0, count / expected_points)
        shoulders = np.asarray([], dtype=float)
        if segment is not None:
            a, b = segment
            shoulder_start = max(a, int(np.searchsorted(time, center - duration * 2.5)))
            shoulder_left = max(a, min(b, int(np.searchsorted(time, center - duration * 0.75, side="right"))))
            shoulder_right = max(a, min(b, int(np.searchsorted(time, center + duration * 0.75))))
            shoulder_end = min(b, int(np.searchsorted(time, center + duration * 2.5, side="right")))
            shoulders = np.r_[flux[shoulder_start:shoulder_left], flux[shoulder_right:shoulder_end]]
        in_flux = np.asarray(flux[left:right], dtype=float)
        core_flux = in_flux[np.abs(time[left:right] - center) <= duration * 0.25]
        if core_flux.size < 3:
            core_flux = in_flux
        baseline = float(np.median(shoulders)) if shoulders.size >= 3 else None
        depth = baseline - float(np.median(core_flux)) if baseline is not None and core_flux.size else None
        in_error = robust_standard_error(core_flux)
        out_error = robust_standard_error(shoulders)
        error = math.hypot(in_error, out_error) if in_error is not None and out_error is not None else None
        local_snr = depth / error if depth is not None and error and error > 0 else None
        if count == 0:
            state = "outside_observations"
        elif segment is None or count < 3 or shoulders.size < 6 or coverage < 0.35:
            state = "insufficient_coverage"
        elif local_snr is not None and local_snr >= 3.0 and depth > 0:
            state = "supported_dip"
        else:
            state = "unsupported_window"
        measured_center = timing_error = None
        if state == "supported_dip" and count >= 5:
            # A flux-weighted local centroid is measured from observations,
            # not copied from T0+nP. It is conditional on the selected window.
            deficits = np.maximum(0.0, baseline - in_flux - (out_error or 0.0))
            if deficits.sum() > 0:
                measured_center = float(np.sum(time[left:right] * deficits) / deficits.sum())
                timing_error = max(cadence / math.sqrt(12.0), duration / (2.0 * local_snr))
        values = np.r_[in_flux, baseline] if baseline is not None else in_flux
        raw_min, raw_max = (np.percentile(values, [5, 95]).tolist() if values.size else [None, None])
        transits.append({
            "start": float(start), "end": float(end), "center": float(center),
            "predicted_center": float(center), "measured_center": measured_center,
            "timing_uncertainty": timing_error, "timing_method": "conditional local flux centroid" if measured_center is not None else None,
            "cycle_number": int(round((center - epoch) / period)),
            "duration": float(duration), "depth": depth, "signed_depth": depth,
            "depth_estimator": "median flux in central half of predicted window relative to local shoulders",
            "full_window_depth": baseline - float(np.median(in_flux)) if baseline is not None and count else None,
            "depth_uncertainty": error, "local_snr": local_snr,
            "local_baseline": baseline, "points": int(count), "coverage_fraction": float(coverage),
            "baseline_points": int(shoulders.size), "state": state,
            "flux_min": float(raw_min) if raw_min is not None else None,
            "flux_max": float(raw_max) if raw_max is not None else None,
            "source": "TLS model", "evidence_source": "local observations",
        })
    return transits


def transit_regularity_tolerance(period, durations):
    clean_durations = np.asarray(
        [value for value in durations if math.isfinite(float(value)) and float(value) > 0],
        dtype=float,
    )
    duration_scale = float(np.percentile(clean_durations, 40)) if clean_durations.size else 0.0
    tolerance = max(duration_scale * 1.25, period * 0.02)
    return float(min(tolerance, period * 0.12))


def is_dense_regularity_match(match_count, event_count, expected_coverage, transit_count):
    if (
        match_count is None
        or event_count is None
        or expected_coverage is None
        or transit_count < 12
    ):
        return False
    dense_box_floor = max(6, int(math.ceil(transit_count * 0.35)))
    return (
        int(match_count) >= dense_box_floor
        and int(event_count) >= 3
        and float(match_count) / transit_count >= 0.35
        and float(expected_coverage) >= 0.30
    )


def score_transit_regularity_period(
    centers,
    durations,
    depths,
    time_start,
    time_end,
    period,
    candidate_support=0,
    pair_support=0,
    fixed_epoch=None,
):
    if centers.size < 3 or not math.isfinite(float(period)) or period <= 0:
        return None

    period = float(period)
    tolerance = transit_regularity_tolerance(period, durations)
    if not math.isfinite(tolerance) or tolerance <= 0:
        return None

    epoch_values = [float(fixed_epoch)] if fixed_epoch is not None and math.isfinite(float(fixed_epoch)) else centers
    best = None
    for epoch in epoch_values:
        first_epoch = math.ceil((float(time_start) - epoch) / period)
        last_epoch = math.floor((float(time_end) - epoch) / period)
        expected_count = int(last_epoch - first_epoch + 1)
        if expected_count < 3:
            continue

        residuals = np.abs(((centers - epoch + period / 2.0) % period) - period / 2.0)
        matched_mask = residuals <= tolerance
        matched_indices = np.flatnonzero(matched_mask)
        if matched_indices.size == 0:
            continue

        matched_cycles = np.rint((centers[matched_indices] - epoch) / period).astype(int)
        unique_cycles = np.unique(matched_cycles)
        event_match_count = int(unique_cycles.size)
        if event_match_count == 0:
            continue

        representative_depths = []
        representative_durations = []
        representative_residuals = []
        for cycle in unique_cycles:
            cycle_indices = matched_indices[matched_cycles == cycle]
            best_index = int(cycle_indices[np.argmax(depths[cycle_indices])])
            representative_depths.append(float(depths[best_index]))
            representative_durations.append(float(durations[best_index]))
            representative_residuals.append(float(residuals[best_index]))

        box_match_count = int(matched_indices.size)
        expected_coverage = event_match_count / expected_count
        residual_rms = float(np.sqrt(np.mean(np.asarray(representative_residuals) ** 2)))
        depth_sum = float(np.sum(representative_depths))
        duration = median_or_none(representative_durations) or median_or_none(durations) or tolerance
        score_key = (
            box_match_count,
            event_match_count,
            expected_coverage,
            int(pair_support),
            int(candidate_support),
            depth_sum,
            -residual_rms,
            -period,
        )
        candidate = {
            "period": period,
            "scatter": residual_rms,
            "count": expected_count,
            "duration": float(duration),
            "transit_time": float(epoch),
            "event_match_count": event_match_count,
            "box_match_count": box_match_count,
            "expected_count": expected_count,
            "expected_coverage": expected_coverage,
            "match_fraction": box_match_count / centers.size,
            "pair_support": int(pair_support),
            "candidate_support": int(candidate_support),
            "tolerance": tolerance,
            "depth_sum": depth_sum,
            "residual_median": median_or_none(representative_residuals),
            "residual_rms": residual_rms,
            "method": "transit regularity",
            "_score_key": score_key,
        }
        if best is None or score_key > best["_score_key"]:
            best = candidate

    return best


def estimate_period_by_transit_regularity(transits, time, options=None, bls_period=None):
    if len(transits) < 3 or len(time) < 3:
        return None

    centers = np.asarray([item["center"] for item in transits], dtype=float)
    durations = np.asarray([max(float(item.get("duration", 0.0)), 0.0) for item in transits], dtype=float)
    depths = np.asarray([max(float(item.get("depth", 0.0)), 0.0) for item in transits], dtype=float)
    finite_mask = np.isfinite(centers) & np.isfinite(durations) & np.isfinite(depths)
    centers = centers[finite_mask]
    durations = durations[finite_mask]
    depths = depths[finite_mask]
    if centers.size < 3:
        return None

    order = np.argsort(centers)
    centers = centers[order]
    durations = durations[order]
    depths = depths[order]

    cadence = float(np.median(np.diff(time))) if len(time) > 1 else 1.0
    full_span = float(time[-1] - time[0]) if len(time) > 1 else 0.0
    if full_span <= 0:
        return None

    min_period, max_period = period_search_bounds(cadence, full_span, options)
    positive_durations = durations[durations > 0]
    if positive_durations.size:
        duration_floor = float(np.percentile(positive_durations, 40))
        min_period = max(min_period, duration_floor * 4.0)
    if min_period >= max_period:
        return None

    resolution = max(cadence * 5.0, full_span / 50000.0, 1e-4)
    candidates = {}

    def add_candidate(period, support=1, pair=False):
        if period is None:
            return
        try:
            period_value = float(period)
        except (TypeError, ValueError):
            return
        if not math.isfinite(period_value) or period_value < min_period or period_value > max_period:
            return
        key = int(round(period_value / resolution))
        record = candidates.setdefault(
            key,
            {"period_sum": 0.0, "weight": 0.0, "support": 0, "pair_support": 0},
        )
        weight = max(float(support), 1.0)
        record["period_sum"] += period_value * weight
        record["weight"] += weight
        record["support"] += int(max(round(weight), 1))
        if pair:
            record["pair_support"] += int(max(round(weight), 1))

    pair_count = min(80, centers.size)
    if centers.size > pair_count:
        strongest = np.argsort(depths)[-pair_count:]
        pair_centers = np.sort(centers[strongest])
    else:
        pair_centers = centers

    for left_index in range(pair_centers.size):
        for right_index in range(left_index + 1, pair_centers.size):
            gap = float(pair_centers[right_index] - pair_centers[left_index])
            if gap < min_period:
                continue
            max_cycles = min(30, int(gap / min_period))
            for cycle_count in range(1, max_cycles + 1):
                add_candidate(gap / cycle_count, pair=True)

    bls_sources = []
    if bls_period is not None:
        bls_sources.append(bls_period)
        bls_sources.extend(bls_period.get("candidates", []))
    for source in bls_sources:
        source_period = source.get("period") if isinstance(source, dict) else None
        add_candidate(source_period, support=30)
        if source_period is None:
            continue
        for divisor in range(2, 13):
            add_candidate(float(source_period) / divisor, support=12)
        for multiple in range(2, 5):
            add_candidate(float(source_period) * multiple, support=6)

    if not candidates:
        return None

    candidate_records = sorted(
        candidates.values(),
        key=lambda item: (item["pair_support"], item["support"]),
        reverse=True,
    )[:3000]

    pair_support_floor = max(3, min(12, int(math.ceil(centers.size * 0.25))))
    event_floor = max(3, min(6, int(math.ceil(centers.size * 0.25))))
    best = None
    for record in candidate_records:
        period = record["period_sum"] / max(record["weight"], 1.0)
        score = score_transit_regularity_period(
            centers,
            durations,
            depths,
            float(time[0]),
            float(time[-1]),
            period,
            candidate_support=record["support"],
            pair_support=record["pair_support"],
        )
        if score is None:
            continue
        if score["pair_support"] < pair_support_floor:
            continue
        if score["event_match_count"] < event_floor:
            continue
        if (
            score["expected_coverage"] < 0.55
            and not is_dense_regularity_match(
                score["box_match_count"],
                score["event_match_count"],
                score["expected_coverage"],
                centers.size,
            )
        ):
            continue
        if best is None or score["_score_key"] > best["_score_key"]:
            best = score

    if best is None:
        return None

    best.pop("_score_key", None)
    return best


def should_prefer_regularity_period(regularity_period, bls_period, transits, time):
    if regularity_period is None:
        return False
    if bls_period is None:
        return True

    bls_value = float(bls_period.get("period", 0.0) or 0.0)
    regular_value = float(regularity_period.get("period", 0.0) or 0.0)
    if bls_value <= 0 or regular_value <= 0:
        return True
    if abs(regular_value - bls_value) / bls_value <= 0.02:
        return False

    centers = np.asarray([item["center"] for item in transits], dtype=float)
    durations = np.asarray([max(float(item.get("duration", 0.0)), 0.0) for item in transits], dtype=float)
    depths = np.asarray([max(float(item.get("depth", 0.0)), 0.0) for item in transits], dtype=float)
    bls_score = score_transit_regularity_period(
        centers,
        durations,
        depths,
        float(time[0]),
        float(time[-1]),
        bls_value,
        fixed_epoch=bls_period.get("transit_time"),
    )
    bls_event_count = int(bls_score.get("event_match_count", 0)) if bls_score else 0
    bls_coverage = float(bls_score.get("expected_coverage", 0.0)) if bls_score else 0.0
    regular_event_count = int(regularity_period.get("event_match_count", 0))
    regular_box_count = int(regularity_period.get("box_match_count", 0))
    regular_coverage = float(regularity_period.get("expected_coverage", 0.0))
    transit_count = len(transits)

    if regular_event_count >= bls_event_count + 2 and regular_coverage >= 0.55:
        return True
    if (
        regular_event_count >= bls_event_count + 2
        and is_dense_regularity_match(
            regular_box_count,
            regular_event_count,
            regular_coverage,
            transit_count,
        )
    ):
        return True
    return (
        regular_value < bls_value
        and regular_event_count >= bls_event_count
        and regular_coverage >= max(0.65, bls_coverage)
    )


def dealiased_bls_period(bls_period, transits, time, flux):
    if bls_period is None or len(transits) < 3:
        return bls_period

    top_period = finite_number(bls_period.get("period"))
    top_power = finite_number(bls_period.get("power"))
    if top_period is None or top_period <= 0 or top_power is None or top_power <= 0:
        return bls_period

    candidates = [
        candidate
        for candidate in bls_period.get("candidates", [])
        if finite_number(candidate.get("period")) is not None
    ]
    if len(candidates) < 2:
        return bls_period

    centers = np.asarray([item["center"] for item in transits], dtype=float)
    durations = np.asarray([max(float(item.get("duration", 0.0)), 0.0) for item in transits], dtype=float)
    depths = np.asarray([max(float(item.get("depth", 0.0)), 0.0) for item in transits], dtype=float)
    top_score = score_transit_regularity_period(
        centers,
        durations,
        depths,
        float(time[0]),
        float(time[-1]),
        top_period,
    )
    if top_score is None:
        return bls_period

    best = None
    for candidate in candidates:
        candidate_period = finite_number(candidate.get("period"))
        candidate_power = finite_number(candidate.get("power"))
        candidate_sde = finite_number(candidate.get("sde"))
        if candidate_period is None or candidate_power is None:
            continue
        if candidate_period <= top_period * 1.5:
            continue

        ratio = candidate_period / top_period
        harmonic = int(round(ratio))
        if harmonic < 2 or harmonic > 4:
            continue
        if abs(ratio / harmonic - 1.0) > 0.035:
            continue
        if candidate_power / top_power < 0.75:
            continue
        if candidate_sde is not None and candidate_sde < 5.0:
            continue

        candidate_score = score_transit_regularity_period(
            centers,
            durations,
            depths,
            float(time[0]),
            float(time[-1]),
            candidate_period,
        )
        if candidate_score is None:
            continue

        top_box_count = int(top_score.get("box_match_count", 0))
        top_event_count = int(top_score.get("event_match_count", 0))
        candidate_box_count = int(candidate_score.get("box_match_count", 0))
        candidate_event_count = int(candidate_score.get("event_match_count", 0))
        if candidate_box_count < max(3, int(math.floor(top_box_count * 0.9))):
            continue
        if candidate_event_count < max(3, int(math.floor(top_event_count * 0.9))):
            continue
        if candidate_score["expected_count"] >= top_score["expected_count"] * 0.75:
            continue

        selection_key = (
            candidate_box_count,
            candidate_event_count,
            candidate_power / top_power,
            candidate_sde if candidate_sde is not None else 0.0,
            candidate_period,
        )
        if best is None or selection_key > best["selection_key"]:
            best = {
                "candidate": candidate,
                "score": candidate_score,
                "harmonic": harmonic,
                "selection_key": selection_key,
            }

    if best is None:
        return bls_period

    candidate = best["candidate"]
    score = best["score"]
    flattened_flux = flattened_flux_for_period_search(time, flux)
    chi_squared = None if flattened_flux is None else chi_squared_transit_probability(
        time,
        flattened_flux,
        score["period"],
        score["duration"],
        score["transit_time"],
    )

    selected_period = score["period"]
    selected_candidates = []
    selected_seen = set()
    for item in [candidate, *candidates]:
        item_period = finite_number(item.get("period"))
        if item_period is None:
            continue
        key = round(item_period, 10)
        if key in selected_seen:
            continue
        selected_seen.add(key)
        selected_candidates.append(item)

    return {
        **bls_period,
        "period": selected_period,
        "scatter": score["scatter"],
        "count": score["expected_count"],
        "duration": score["duration"],
        "transit_time": score["transit_time"],
        "power": finite_number(candidate.get("power")) or bls_period.get("power"),
        "sde": finite_number(candidate.get("sde")),
        "candidates": selected_candidates,
        "harmonic_alias_corrected": True,
        "harmonic_alias_period": top_period,
        "harmonic_alias_factor": best["harmonic"],
        "harmonic_alias_power_ratio": (finite_number(candidate.get("power")) or 0.0) / top_power,
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
    smoothed = moving_average_by_segments(clipped_flux, smooth_width, observing_segments(time))

    baseline = float(np.median(smoothed))
    mad = float(np.median(np.abs(smoothed - baseline)))
    robust_noise = max(1.4826 * mad, 1e-9)
    cadence = float(np.median(np.diff(time))) if len(time) > 1 else 1.0
    full_span = float(time[-1] - time[0]) if len(time) > 1 else 0.0

    auto_min_width_time = max(cadence * 4.0, min(0.08, full_span / 5000.0))
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
    smoothed = moving_average_by_segments(clipped_flux, smooth_width, observing_segments(time))

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


def detect_transits(time, flux, options=None, progress_callback=None):
    if options is None:
        options = dict(DEFAULT_DETECTION_OPTIONS)
    median_flux = float(np.median(flux))
    search_mode = options.get("search_mode", DEFAULT_DETECTION_OPTIONS["search_mode"])
    if search_mode == "tls":
        flux_mad = float(np.median(np.abs(flux - median_flux)))
        detection = {
            "transits": [],
            "robust_noise": max(1.4826 * flux_mad, 1e-9),
            "smooth_points": 1,
        }
    else:
        detection = detect_transits_by_prominence(time, flux, median_flux, options)
        threshold_detection = detect_transits_by_threshold(time, flux, median_flux, options)
        if detection is None:
            detection = threshold_detection
        elif threshold_detection is not None and len(threshold_detection["transits"]) > len(detection["transits"]):
            detection = {
                **detection,
                "transits": prune_overlapping_transits(detection["transits"] + threshold_detection["transits"]),
                "robust_noise": min(float(detection["robust_noise"]), float(threshold_detection["robust_noise"])),
                "smooth_points": min(int(detection["smooth_points"]), int(threshold_detection["smooth_points"])),
            }

    transits = sorted(detection["transits"], key=lambda item: item["center"])
    full_span = float(time[-1] - time[0]) if len(time) > 1 else 0.0
    tls_period = estimate_period_with_tls(time, flux, options, progress_callback=progress_callback) if search_mode == "tls" else None
    if tls_period is not None:
        tls_transits = transits_from_tls_result(time, flux, tls_period)
        if tls_transits:
            transits = tls_transits
        bls_period = None
        regularity_period = None
        use_regularity_period = False
    else:
        bls_period = estimate_period_with_bls(time, flux, options)
        bls_period = dealiased_bls_period(bls_period, transits, time, flux)
        regularity_period = estimate_period_by_transit_regularity(transits, time, options, bls_period)
        use_regularity_period = should_prefer_regularity_period(regularity_period, bls_period, transits, time)
    p_value = None
    chi_squared_flat = None
    chi_squared_box = None
    reduced_chi_squared_box = None
    delta_chi_squared = None
    period_epoch = None
    period_duration = None
    period_sde = None
    period_uncertainty = None
    period_candidates = []
    period_search = None
    periodogram = None
    tls_sde_raw = None
    tls_fap = None
    tls_snr = None
    tls_details = None
    transit_model = None
    if tls_period is not None:
        period = tls_period["period"]
        period_scatter = tls_period["scatter"]
        period_uncertainty = tls_period.get("period_uncertainty")
        period_match_count = tls_period["count"]
        period_method = tls_period["method"]
        p_value = tls_period.get("p_value")
        chi_squared_flat = tls_period.get("chi_squared_flat")
        chi_squared_box = tls_period.get("chi_squared_box")
        reduced_chi_squared_box = tls_period.get("reduced_chi_squared_box")
        delta_chi_squared = tls_period.get("delta_chi_squared")
        period_epoch = tls_period.get("transit_time")
        period_duration = tls_period.get("duration")
        period_sde = tls_period.get("sde")
        tls_sde_raw = tls_period.get("sde_raw")
        tls_fap = tls_period.get("fap")
        tls_snr = tls_period.get("snr")
        period_candidates = tls_period.get("candidates", [])
        periodogram = tls_period.get("periodogram")
        period_search = {
            "min_period": tls_period.get("search_min_period"),
            "max_period": tls_period.get("search_max_period"),
            "min_duration": tls_period.get("search_min_duration"),
            "max_duration": tls_period.get("search_max_duration"),
        }
        tls_result = tls_period.get("tls_result") or {}
        tls_details = {
            key: value
            for key, value in tls_result.items()
            if key not in ("candidates", "periodogram", "model")
        }
        transit_model = tls_period.get("transit_model")
    elif bls_period is not None and not use_regularity_period:
        periodogram = bls_period.get("periodogram")
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
        if regularity_period is not None:
            period_candidates = [
                {
                    "period": regularity_period["period"],
                    "power": regularity_period["event_match_count"],
                    "sde": None,
                    "method": regularity_period["method"],
                    "event_match_count": regularity_period["event_match_count"],
                    "expected_transit_count": regularity_period["expected_count"],
                    "expected_transit_coverage": regularity_period["expected_coverage"],
                },
                *period_candidates,
            ]
        period_search = {
            "min_period": bls_period.get("search_min_period"),
            "max_period": bls_period.get("search_max_period"),
            "min_duration": bls_period.get("search_min_duration"),
            "max_duration": bls_period.get("search_max_duration"),
        }
    elif regularity_period is not None:
        period = regularity_period["period"]
        period_scatter = regularity_period["scatter"]
        period_match_count = regularity_period["count"]
        period_method = regularity_period["method"]
        period_epoch = regularity_period["transit_time"]
        period_duration = regularity_period["duration"]
        period_candidates = [
            {
                "period": regularity_period["period"],
                "power": regularity_period["event_match_count"],
                "sde": None,
                "method": regularity_period["method"],
                "event_match_count": regularity_period["event_match_count"],
                "expected_transit_count": regularity_period["expected_count"],
                "expected_transit_coverage": regularity_period["expected_coverage"],
            },
            *(bls_period.get("candidates", []) if bls_period is not None else []),
        ]
        if bls_period is not None:
            periodogram = bls_period.get("periodogram")
            period_search = {
                "min_period": bls_period.get("search_min_period"),
                "max_period": bls_period.get("search_max_period"),
                "min_duration": bls_period.get("search_min_duration"),
                "max_duration": bls_period.get("search_max_duration"),
            }
        flattened_flux = flattened_flux_for_period_search(time, flux)
        chi_squared = None if flattened_flux is None else chi_squared_transit_probability(
            time,
            flattened_flux,
            period,
            period_duration,
            period_epoch,
        )
        if chi_squared:
            p_value = chi_squared.get("p_value")
            chi_squared_flat = chi_squared.get("chi_squared_flat")
            chi_squared_box = chi_squared.get("chi_squared_box")
            reduced_chi_squared_box = chi_squared.get("reduced_chi_squared_box")
            delta_chi_squared = chi_squared.get("delta_chi_squared")
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
        "period_uncertainty": period_uncertainty,
        "period_candidates": period_candidates,
        "period_search": period_search,
        "periodogram": periodogram,
        "tls_sde_raw": tls_sde_raw,
        "tls_fap": tls_fap,
        "tls_snr": tls_snr,
        "tls": tls_details,
        "transit_model": transit_model,
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


def finite_number(value):
    if value is None or isinstance(value, (bool, np.bool_)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def format_metric(value, digits=2):
    number = finite_number(value)
    return "-" if number is None else f"{number:.{digits}f}"


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


def normalize_observed_ranges(observed_ranges):
    ranges = []
    for item in observed_ranges or []:
        if isinstance(item, dict):
            start = finite_number(item.get("start_day", item.get("start")))
            end = finite_number(item.get("end_day", item.get("end")))
        else:
            try:
                start = finite_number(item[0])
                end = finite_number(item[1])
            except (TypeError, IndexError):
                start = None
                end = None
        if start is None or end is None:
            continue
        if end < start:
            start, end = end, start
        ranges.append((float(start), float(end)))
    return ranges


def ephemeris_cycles_in_observed_ranges(period, epoch, tolerance, observed_ranges):
    period = finite_number(period)
    epoch = finite_number(epoch)
    tolerance = finite_number(tolerance)
    if period is None or epoch is None or tolerance is None or period <= 0:
        return set()

    cycles = set()
    for start, end in normalize_observed_ranges(observed_ranges):
        first_cycle = math.ceil((start - tolerance - epoch) / period)
        last_cycle = math.floor((end + tolerance - epoch) / period)
        if last_cycle < first_cycle:
            continue
        cycles.update(range(int(first_cycle), int(last_cycle) + 1))
    return cycles


def build_ephemeris_diagnostics(transits, detection, time_reference=0.0, observed_ranges=None):
    period = finite_number(detection.get("period"))
    epoch = finite_number(detection.get("period_epoch"))
    period_duration = finite_number(detection.get("period_duration"))
    expected_count = finite_number(detection.get("period_match_count"))
    independent_timing = detection.get("period_method") == "TLS"
    centers = finite_values([
        item.get("measured_center") if independent_timing else item.get("center")
        for item in transits
        if not independent_timing or item.get("state") == "supported_dip"
    ])
    durations = finite_values([item.get("duration") for item in transits])

    empty = {
        "ephemeris_match_count": None,
        "ephemeris_match_fraction": None,
        "ephemeris_event_match_count": None,
        "ephemeris_event_match_fraction": None,
        "off_ephemeris_transit_count": None,
        "off_ephemeris_fraction": None,
        "expected_transit_count": expected_count,
        "expected_transit_coverage": None,
        "timing_residual_median": None,
        "timing_residual_max": None,
        "timing_residual_tolerance": None,
        "timing_residual_ratio": None,
        "timing_basis": "independently measured local centroids" if independent_timing else "detected event centers",
        "measured_timing_count": len(centers),
        "predicted_window_count": len(transits),
        "covered_window_count": sum(item.get("state") in ("supported_dip", "unsupported_window") for item in transits) if independent_timing else len(transits),
    }
    if not centers or period is None or epoch is None or period <= 0:
        return empty

    epoch_relative = epoch - float(time_reference)
    median_duration = median_or_none(durations)
    duration_scale = max(
        period_duration or 0.0,
        median_duration or 0.0,
        period * 0.035,
    )
    tolerance = max(duration_scale * 1.5, period * 0.025)
    tolerance = min(tolerance, period * 0.18)
    if tolerance <= 0:
        return empty

    residuals = []
    matched_residuals = []
    matched_cycles = set()
    for center in centers:
        cycles = round((center - epoch_relative) / period)
        nearest_epoch = epoch_relative + cycles * period
        residual = abs(center - nearest_epoch)
        residuals.append(residual)
        if residual <= tolerance:
            matched_residuals.append(residual)
            matched_cycles.add(int(cycles))

    match_count = len(matched_residuals)
    event_match_count = len(matched_cycles)
    transit_count = len(centers)
    off_count = transit_count - match_count
    median_residual = median_or_none(residuals)
    observed_cycles = ephemeris_cycles_in_observed_ranges(period, epoch_relative, tolerance, observed_ranges)
    if independent_timing:
        expected_count = sum(item.get("state") in ("supported_dip", "unsupported_window") for item in transits)
    elif observed_cycles:
        expected_count = len(observed_cycles)
    expected_coverage = None
    if expected_count is not None and expected_count > 0:
        expected_coverage = min(1.0, event_match_count / expected_count)

    return {
        **empty,
        "ephemeris_match_count": int(match_count),
        "ephemeris_match_fraction": match_count / transit_count,
        "ephemeris_event_match_count": int(event_match_count),
        "ephemeris_event_match_fraction": None if expected_count is None or expected_count <= 0 else event_match_count / expected_count,
        "off_ephemeris_transit_count": int(off_count),
        "off_ephemeris_fraction": off_count / transit_count,
        "expected_transit_count": int(expected_count) if expected_count is not None else None,
        "expected_transit_coverage": expected_coverage,
        "timing_residual_median": median_residual,
        "timing_residual_max": max(residuals) if residuals else None,
        "timing_residual_tolerance": tolerance,
        "timing_residual_ratio": None if median_residual is None else median_residual / tolerance,
    }


def build_candidate_diagnostics(transits, detection, time_reference=0.0, observed_ranges=None):
    has_window_states = any("state" in item for item in transits)
    evidence_events = [item for item in transits if not has_window_states or item.get("state") == "supported_dip"]
    depths = finite_values([item.get("depth") for item in evidence_events])
    radius_ratios = finite_values([item.get("radius_ratio") for item in evidence_events])
    point_counts = finite_values([item.get("points") for item in evidence_events])
    # Absolute orbital cycle parity survives missing observations.
    epoch = finite_number(detection.get("period_epoch"))
    period = finite_number(detection.get("period"))
    def parity(item, index):
        if item.get("cycle_number") is not None:
            return int(item["cycle_number"]) % 2
        if epoch is not None and period and period > 0:
            return int(round((item["center"] + time_reference - epoch) / period)) % 2
        return index % 2
    odd_depths = finite_values([item.get("depth") for i, item in enumerate(evidence_events) if parity(item, i) == 1])
    even_depths = finite_values([item.get("depth") for i, item in enumerate(evidence_events) if parity(item, i) == 0])
    odd_depth = median_or_none(odd_depths)
    even_depth = median_or_none(even_depths)
    depth_center = median_or_none(depths)
    robust_noise = detection.get("robust_noise")
    local_depth_snr = None
    if depth_center is not None and robust_noise is not None and math.isfinite(float(robust_noise)) and float(robust_noise) > 0:
        local_depth_snr = depth_center / float(robust_noise)
    tls_snr = finite_number(detection.get("tls_snr"))
    detection_snr = tls_snr if detection.get("period_method") == "TLS" and tls_snr is not None else local_depth_snr
    tls_details = detection.get("tls") or {}
    tls_odd_even_mismatch = finite_number(tls_details.get("odd_even_mismatch_sigma"))

    odd_even_depth_mismatch = None
    if odd_depth is not None and even_depth is not None and max(odd_depth, even_depth) > 0:
        odd_even_depth_mismatch = abs(odd_depth - even_depth) / max(odd_depth, even_depth)

    ephemeris = build_ephemeris_diagnostics(transits, detection, time_reference, observed_ranges)
    usable_windows = [item for item in transits
                      if item.get("state") in ("supported_dip", "unsupported_window")
                      and finite_number(item.get("depth")) is not None
                      and finite_number(item.get("depth_uncertainty")) is not None
                      and item["depth_uncertainty"] > 0]
    combined_depth = combined_error = combined_snr = None
    if usable_windows:
        signed = np.asarray([item["depth"] for item in usable_windows])
        errors = np.asarray([item["depth_uncertainty"] for item in usable_windows])
        weights = 1.0 / errors ** 2
        # Per-event errors estimated from very few samples can be spuriously
        # small. Cap their relative precision rather than allowing one shallow
        # window to dominate the collective signal.
        weights = np.minimum(weights, np.median(weights) * 2.0)
        combined_depth = float(np.average(signed, weights=weights))
        formal_error = float(1.0 / math.sqrt(np.sum(weights)))
        empirical_error = float(np.std(signed, ddof=1) / math.sqrt(len(signed))) if len(signed) > 1 else formal_error
        combined_error = max(formal_error, empirical_error)
        combined_snr = combined_depth / combined_error if combined_error > 0 else None
    positive_windows = sum(item["depth"] > 0 for item in usable_windows)
    combined_support = (len(usable_windows) >= 3 and positive_windows >= 3
                        and positive_windows / len(usable_windows) >= 0.6
                        and combined_snr is not None and combined_snr >= 3.0
                        and detection.get("period_method") == "TLS"
                        and (finite_number(detection.get("period_sde")) or 0) >= 7.0
                        and (tls_snr or 0) >= 5.0)
    diagnostics = {
        "detection_snr": detection_snr,
        "local_depth_snr": local_depth_snr,
        "tls_snr": tls_snr,
        "tls_fap": finite_number(detection.get("tls_fap")),
        "tls_odd_even_mismatch_sigma": tls_odd_even_mismatch,
        "median_transit_points": median_or_none(point_counts),
        "depth_scatter_ratio": coefficient_of_variation(depths),
        "odd_depth": odd_depth,
        "even_depth": even_depth,
        "odd_even_depth_mismatch": odd_even_depth_mismatch,
        "max_radius_ratio": max(radius_ratios) if radius_ratios else None,
        "supported_event_count": len(evidence_events),
        "combined_window_count": len(usable_windows),
        "positive_window_count": positive_windows,
        "combined_signed_depth": combined_depth,
        "combined_depth_uncertainty": combined_error,
        "combined_depth_snr": combined_snr,
        "combined_signal_supported": bool(combined_support),
        "predicted_window_count": len(transits),
        "unsupported_window_count": sum(item.get("state") == "unsupported_window" for item in transits),
        "insufficient_coverage_count": sum(item.get("state") == "insufficient_coverage" for item in transits),
        "outside_observations_count": sum(item.get("state") == "outside_observations" for item in transits),
        "odd_event_count": len(odd_depths), "even_event_count": len(even_depths),
        **ephemeris,
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
        if detection.get("period_method") == "TLS":
            warnings.append({
                "severity": "info",
                "title": "Physical TLS search",
                "detail": "The period was fitted with a limb-darkened transit template including ingress and egress.",
            })
        elif detection.get("period_method") == "transit regularity":
            warnings.append({
                "severity": "info",
                "title": "Period selected by regularity",
                "detail": "A shorter repeating transit-box cadence explained more detected events than the strongest BLS alias.",
            })
        else:
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
    tls_fap = finite_number(detection.get("tls_fap"))
    tls_sde = finite_number(detection.get("period_sde"))
    if detection.get("period_method") == "TLS" and tls_sde is not None and tls_sde < 5:
        warnings.append({
            "severity": "caution",
            "title": "TLS peak below candidate threshold",
            "detail": f"TLS SDE is {tls_sde:.2f}; candidate review normally starts around SDE 5 and strong evidence around SDE 7.",
        })
    if detection.get("period_method") == "TLS" and tls_fap is not None and tls_fap > 0.01:
        warnings.append({
            "severity": "caution",
            "title": "Weak TLS false-alarm estimate",
            "detail": f"TLS reports a white-noise false-alarm probability of about {tls_fap:.2%}; red noise can make this optimistic.",
        })
    if detection_snr is not None and detection_snr < 7:
        warnings.append({
            "severity": "caution",
            "title": "Low search SNR" if detection.get("period_method") == "TLS" else "Low depth SNR",
            "detail": (
                f"TLS reports a combined transit SNR of {detection_snr:.2f}."
                if detection.get("period_method") == "TLS"
                else f"Median transit depth is about {detection_snr:.2f}x the robust noise."
            ),
        })
    if tls_odd_even_mismatch is not None and tls_odd_even_mismatch >= 5:
        warnings.append({
            "severity": "danger",
            "title": "TLS odd/even mismatch",
            "detail": f"TLS measures an odd/even depth difference of {tls_odd_even_mismatch:.2f} sigma.",
        })
    if odd_even_depth_mismatch is not None and odd_even_depth_mismatch > 0.5 and len(odd_depths) >= 2 and len(even_depths) >= 2:
        warnings.append({
            "severity": "danger",
            "title": "Odd/even depth mismatch",
            "detail": "Alternating transit depths can indicate an eclipsing binary or blended source.",
        })
    depth_uncertainties = finite_values([item.get("depth_uncertainty") for item in evidence_events])
    inconsistent_three = (len(depths) >= 3 and len(depth_uncertainties) == len(depths)
                          and max(depths) - min(depths) > 3 * math.hypot(max(depth_uncertainties), min(depth_uncertainties)))
    if diagnostics["depth_scatter_ratio"] is not None and diagnostics["depth_scatter_ratio"] > 0.8 and (len(depths) >= 4 or inconsistent_three):
        warnings.append({
            "severity": "caution",
            "title": "Inconsistent transit depths",
            "detail": "Measured event depths disagree beyond their local uncertainty estimates. Review stellar variability, overlap, and systematics.",
        })
    if has_window_states and len(evidence_events) < min(3, len(transits)):
        warnings.append({"severity": "caution", "title": "Predicted windows lack local support",
                         "detail": f"Only {len(evidence_events)} of {len(transits)} predicted windows have a positive local dip above 3-sigma with usable coverage."})
    if len(odd_depths) < 2 or len(even_depths) < 2:
        diagnostics["odd_even_comparison_state"] = "insufficient_events"
    else:
        diagnostics["odd_even_comparison_state"] = "available"
    duration_disagreement = finite_number(tls_details.get("duration_disagreement_fraction"))
    if duration_disagreement is not None and duration_disagreement > 0.35:
        warnings.append({"severity": "caution", "title": "Duration estimates disagree",
                         "detail": "Threshold-based width and physical template contacts differ by more than 35%; inspect the conditional fit and cadence."})
    search_bounds = detection.get("period_search") or {}
    selected_period = finite_number(detection.get("period"))
    minimum = finite_number(search_bounds.get("min_period"))
    maximum = finite_number(search_bounds.get("max_period"))
    if selected_period is not None and minimum is not None and maximum is not None:
        edge_margin = max((maximum - minimum) * 0.01, selected_period * 0.002)
        if min(abs(selected_period - minimum), abs(maximum - selected_period)) < edge_margin:
            warnings.append({"severity": "caution", "title": "Period peak near search edge",
                             "detail": "The selected period is close to a search bound. Widen the bounds when baseline and minimum-transit constraints permit."})
    strong_alternatives = [candidate for candidate in detection.get("period_candidates", [])
                           if selected_period and finite_number(candidate.get("period"))
                           and abs(candidate["period"] - selected_period) / selected_period > 0.02
                           and finite_number(candidate.get("sde")) is not None
                           and candidate["sde"] >= max(7.0, (finite_number(detection.get("period_sde")) or 0) * 0.85)]
    if strong_alternatives:
        diagnostics["strong_alias_periods"] = [candidate["period"] for candidate in strong_alternatives[:4]]
        warnings.append({"severity": "caution", "title": "Strong alternative periods",
                         "detail": "Other distinct period peaks have comparable strength. Inspect harmonics, aliases, and additional planets before choosing an ephemeris."})
    if (
        len(transits) >= 3
        and detection.get("period_method") in ("BLS", "binned BLS fallback", "transit regularity", "TLS")
        and diagnostics["ephemeris_match_fraction"] is not None
    ):
        match_fraction = diagnostics["ephemeris_match_fraction"]
        match_count = diagnostics["ephemeris_match_count"]
        transit_count = len(transits)
        event_count = diagnostics["ephemeris_event_match_count"]
        expected_count = diagnostics["expected_transit_count"]
        expected_coverage = diagnostics["expected_transit_coverage"]
        well_covered_events = (
            detection.get("period_method") in ("transit regularity", "TLS")
            and event_count is not None
            and event_count >= 3
            and (
                (
                    expected_coverage is not None
                    and expected_coverage >= 0.65
                )
                or is_dense_regularity_match(
                    match_count,
                    event_count,
                    expected_coverage,
                    transit_count,
                )
            )
        )
        period_label = "BLS period" if detection.get("period_method") == "BLS" else "selected period"
        if match_fraction < 0.55 and not well_covered_events:
            warnings.append({
                "severity": "danger",
                "title": "Irregular transit timing",
                "detail": f"Only {match_count} of {transit_count} detected dips align with the {period_label}.",
            })
        elif match_fraction < 0.75 and not well_covered_events:
            warnings.append({
                "severity": "caution",
                "title": "Weak ephemeris agreement",
                "detail": f"{match_count} of {transit_count} detected dips align with the {period_label}.",
            })
        if well_covered_events and match_fraction < 0.65:
            warnings.append({
                "severity": "caution",
                "title": "Noisy extra dips",
                "detail": f"{int(event_count)} of {int(expected_count)} predicted events are covered, but extra off-period dips were also boxed.",
            })

        off_count = diagnostics["off_ephemeris_transit_count"]
        off_fraction = diagnostics["off_ephemeris_fraction"]
        if off_count is not None and off_fraction is not None and off_count >= 3 and off_fraction >= 0.35:
            if not well_covered_events:
                warnings.append({
                    "severity": "caution",
                    "title": "Many off-period dips",
                    "detail": "Several detected dips do not land near the recovered period and may be systematics.",
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


def score_band(value, bands):
    if value is None:
        return None
    for threshold, points, label, detail in bands:
        if value >= threshold:
            return points, label, detail
    return None


def build_planet_assessment(transits, detection, diagnostics, warnings):
    local_event_count = int(diagnostics.get("supported_event_count", len(transits)))
    combined_support = bool(diagnostics.get("combined_signal_supported"))
    transit_count = max(local_event_count, int(diagnostics.get("positive_window_count", 0)) if combined_support else 0)
    period = finite_number(detection.get("period"))
    period_method = detection.get("period_method")
    period_sde = finite_number(detection.get("period_sde"))
    detection_snr = finite_number(diagnostics.get("detection_snr"))
    tls_fap = finite_number(detection.get("tls_fap"))
    p_value = finite_number(detection.get("p_value"))
    depth_scatter_ratio = finite_number(diagnostics.get("depth_scatter_ratio"))
    odd_even_mismatch = finite_number(diagnostics.get("odd_even_depth_mismatch"))
    max_radius_ratio = finite_number(diagnostics.get("max_radius_ratio"))
    median_transit_points = finite_number(diagnostics.get("median_transit_points"))
    ephemeris_match_fraction = finite_number(diagnostics.get("ephemeris_match_fraction"))
    ephemeris_match_count = finite_number(diagnostics.get("ephemeris_match_count"))
    ephemeris_event_match_count = finite_number(diagnostics.get("ephemeris_event_match_count"))
    off_ephemeris_count = finite_number(diagnostics.get("off_ephemeris_transit_count"))
    off_ephemeris_fraction = finite_number(diagnostics.get("off_ephemeris_fraction"))
    expected_transit_count = finite_number(diagnostics.get("expected_transit_count"))
    expected_transit_coverage = finite_number(diagnostics.get("expected_transit_coverage"))
    timing_residual_ratio = finite_number(diagnostics.get("timing_residual_ratio"))
    ephemeris_period_methods = ("BLS", "binned BLS fallback", "transit regularity", "TLS")
    period_label = "BLS period" if period_method == "BLS" else "selected period"
    well_covered_ephemeris = (
        period_method in ("transit regularity", "TLS")
        and ephemeris_event_match_count is not None
        and ephemeris_event_match_count >= 3
        and (
            (
                expected_transit_coverage is not None
                and expected_transit_coverage >= 0.65
            )
            or is_dense_regularity_match(
                ephemeris_match_count,
                ephemeris_event_match_count,
                expected_transit_coverage,
                transit_count,
            )
        )
    )

    score = 0.0
    supporting_evidence = []
    limiting_evidence = []

    def support(title, detail, points):
        nonlocal score
        score += points
        supporting_evidence.append({
            "title": title,
            "detail": detail,
            "points": points,
        })

    def limit(title, detail, points):
        nonlocal score
        score += points
        limiting_evidence.append({
            "title": title,
            "detail": detail,
            "points": points,
        })

    if combined_support and local_event_count < 3:
        support("Coherent combined transit signal", f"{transit_count} windows have positive signed depth; combined local SNR is {diagnostics['combined_depth_snr']:.2f}. Individual windows remain tentative unless independently supported.", 20)
    elif transit_count >= 3:
        support("Repeated locally supported dips", f"{transit_count} windows contain positive measured dips with usable coverage.", 20)
    elif transit_count > 0:
        support("Locally supported dip", f"{transit_count} window{'s have' if transit_count != 1 else ' has'} local transit-like support.", 6)
        limit("Too few events", "Fewer than three events is weak evidence for an orbital period.", -8)
    else:
        limit("No boxed transit events", "The detector did not find statistically strong local dips.", -28)

    if period is not None and period > 0 and period_method == "BLS":
        support("Stable BLS period", f"Best period is {period:.6g} days from the BLS search.", 22)
    elif period is not None and period > 0 and period_method == "TLS":
        support("Physical TLS period", f"Best period is {period:.6g} days from the limb-darkened TLS search.", 22)
    elif period is not None and period > 0 and period_method == "transit regularity":
        support("Frequent transit regularity", f"Best repeating interval is {period:.6g} days from the boxed transit cadence.", 20)
    elif period is not None and period > 0:
        support("Provisional period", f"Estimated period is {period:.6g} days from {period_method or 'candidate spacing'}.", 10)
        limit("Period is not a BLS peak", "The repeating period needs manual confirmation.", -4)
    else:
        limit("No stable period", "A repeating orbital period was not recovered.", -18)

    sde_label = "TLS SDE" if period_method == "TLS" else "Period SDE"
    sde_result = score_band(period_sde, (
        (10.0, 22, "Very strong period peak", f"{sde_label} is {format_metric(period_sde)}."),
        (7.0, 17, "Strong period peak", f"{sde_label} is {format_metric(period_sde)}."),
        (5.0, 8, "Moderate period peak", f"{sde_label} is {format_metric(period_sde)}."),
    ))
    if sde_result is not None:
        points, title, detail = sde_result
        support(title, detail, points)
    elif period_sde is not None:
        limit("Weak period peak", f"{sde_label} is only {period_sde:.2f}.", -10)

    snr_title = "TLS signal SNR" if period_method == "TLS" else "transit depth SNR"
    snr_result = score_band(detection_snr, (
        (10.0, 22, f"High {snr_title}", f"Search SNR is {format_metric(detection_snr)}."),
        (7.0, 16, f"Good {snr_title}", f"Search SNR is {format_metric(detection_snr)}."),
        (5.0, 8, f"Marginal {snr_title}", f"Search SNR is {format_metric(detection_snr)}."),
    ))
    if snr_result is not None:
        points, title, detail = snr_result
        support(title, detail, points)
    elif detection_snr is not None:
        limit(f"Low {snr_title}", f"Search SNR is only {detection_snr:.2f}.", -14)

    if period_method == "TLS" and tls_fap is not None:
        if tls_fap <= 0.001:
            support("Low TLS false-alarm probability", f"White-noise FAP is {tls_fap:.3%}.", 10)
        elif tls_fap <= 0.01:
            support("Useful TLS false-alarm estimate", f"White-noise FAP is {tls_fap:.2%}.", 6)
        else:
            limit("Weak TLS false-alarm estimate", f"White-noise FAP is {tls_fap:.2%}.", -10)

    if p_value is not None:
        if p_value <= 1e-6:
            support("Very significant box model", "The transit model strongly beats a flat light curve.", 16)
        elif p_value <= 1e-4:
            support("Significant box model", "The transit model clearly beats a flat light curve.", 12)
        elif p_value <= 0.01:
            support("Useful box-model improvement", "The transit model improves over a flat light curve.", 8)
        else:
            limit("Weak box-model significance", "The transit model is not much better than a flat light curve.", -12)

    # TLS windows are selected with an ephemeris, so their local centroids are
    # conditional evidence. Report timing descriptively but award no circular
    # timing bonus. Non-TLS dip searches can retain independent timing credit.
    if period_method != "TLS" and period_method in ephemeris_period_methods and transit_count >= 3 and ephemeris_match_fraction is not None:
        if ephemeris_match_fraction >= 0.8:
            support("Detected dips follow the ephemeris", f"{int(ephemeris_match_count)} of {transit_count} dips align with the {period_label}.", 16)
        elif well_covered_ephemeris:
            support(
                "Predicted events are covered",
                f"{int(ephemeris_event_match_count)} of {int(expected_transit_count)} predicted events have matching dips.",
                12,
            )
        elif ephemeris_match_fraction >= 0.65:
            support("Partial ephemeris agreement", f"{int(ephemeris_match_count)} of {transit_count} dips align with the {period_label}.", 5)
            limit("Some off-period dips", "Several detected dips do not belong to the recovered period.", -6)
        elif ephemeris_match_fraction < 0.55:
            limit("Irregular transit timing", f"Only {int(ephemeris_match_count)} of {transit_count} dips align with the {period_label}.", -34)
        else:
            limit("Weak timing agreement", f"Only {int(ephemeris_match_count)} of {transit_count} dips align with the {period_label}.", -18)

    if (
        off_ephemeris_count is not None
        and off_ephemeris_fraction is not None
        and off_ephemeris_count >= 3
        and off_ephemeris_fraction >= 0.35
    ):
        if well_covered_ephemeris:
            limit("Extra off-period dips", "The selected ephemeris repeats, but extra boxed dips may be noise or systematics.", -6)
        else:
            limit("Many off-period dips", "The detector found too many transit-like dips away from the recovered ephemeris.", -24)

    if expected_transit_coverage is not None and transit_count >= 3 and expected_transit_coverage < 0.5:
        limit("Weak predicted-transit coverage", f"Only {expected_transit_coverage:.0%} of expected {period_label} events were matched.", -10)

    if timing_residual_ratio is not None and timing_residual_ratio > 1.0 and transit_count >= 3 and not well_covered_ephemeris:
        limit("Large timing residuals", "Detected dip centers are not tightly clustered around the recovered ephemeris.", -10)

    if depth_scatter_ratio is not None and transit_count >= 3:
        if depth_scatter_ratio <= 0.35:
            support("Consistent transit depths", f"Depth scatter ratio is {depth_scatter_ratio:.2f}.", 7)
        elif depth_scatter_ratio > 0.8:
            limit("Inconsistent transit depths", f"Depth scatter ratio is {depth_scatter_ratio:.2f}.", -12)
        elif depth_scatter_ratio > 0.5:
            limit("Moderately inconsistent depths", f"Depth scatter ratio is {depth_scatter_ratio:.2f}.", -6)

    if odd_even_mismatch is not None and diagnostics.get("odd_even_comparison_state", "available") == "available" and transit_count >= 4:
        if odd_even_mismatch <= 0.25:
            support("Odd/even depths agree", f"Odd/even mismatch is {odd_even_mismatch:.2f}.", 6)
        elif odd_even_mismatch > 0.5:
            limit("Odd/even depth mismatch", "Alternating depths can indicate an eclipsing binary or blend.", -18)
        elif odd_even_mismatch > 0.35:
            limit("Possible odd/even mismatch", f"Odd/even mismatch is {odd_even_mismatch:.2f}.", -8)

    if max_radius_ratio is not None:
        if max_radius_ratio <= 0.2:
            support("Planet-sized radius ratio", f"Maximum Rp/Rs estimate is {max_radius_ratio:.3f}.", 4)
        elif max_radius_ratio > 0.3:
            limit("Very large radius ratio", f"Maximum Rp/Rs estimate is {max_radius_ratio:.3f}.", -16)
        else:
            limit("Large radius ratio", f"Maximum Rp/Rs estimate is {max_radius_ratio:.3f}.", -8)

    if median_transit_points is not None:
        if median_transit_points >= 8:
            support("Well-sampled events", f"Median supported event has {median_transit_points:.0f} analysis samples.", 4)
        elif median_transit_points < 4:
            limit("Sparse transit sampling", f"Median supported event has only {median_transit_points:.0f} analysis samples.", -6)

    danger_count = sum(1 for warning in warnings if warning.get("severity") == "danger")
    caution_count = sum(1 for warning in warnings if warning.get("severity") == "caution")
    if danger_count:
        score -= danger_count * 10
    if caution_count >= 3:
        score -= 6

    raw_candidate_score = int(round(clamp(score, 0, 100)))
    required_period_sde = 7 if period_method == "TLS" else 5
    high_repeat_confidence = (
        transit_count >= 5
        and detection_snr is not None
        and detection_snr >= 5
        and period_sde is not None
        and period_sde >= (7 if period_method == "TLS" else 8)
        and (ephemeris_match_fraction is None or ephemeris_match_fraction >= 0.85)
        and (expected_transit_coverage is None or expected_transit_coverage >= 0.65)
        and (off_ephemeris_fraction is None or off_ephemeris_fraction <= 0.2)
    )
    strong_requirements_met = (
        transit_count >= 3
        and period is not None
        and period_method in ("BLS", "TLS")
        and detection_snr is not None
        and (detection_snr >= 7 or high_repeat_confidence)
        and (period_sde is None or period_sde >= required_period_sde)
        and (period_method != "TLS" or tls_fap is None or tls_fap <= 0.01)
        and (ephemeris_match_fraction is None or ephemeris_match_fraction >= 0.75)
        and (off_ephemeris_fraction is None or off_ephemeris_fraction <= 0.3)
        and danger_count == 0
    )
    severe_timing_mismatch = (
        transit_count >= 3
        and period_method in ephemeris_period_methods
        and ephemeris_match_fraction is not None
        and ephemeris_match_fraction < 0.55
        and not well_covered_ephemeris
        and off_ephemeris_count is not None
        and off_ephemeris_count >= 2
    )
    credible_tls_signal = (
        period_method != "TLS"
        or (
            period_sde is not None
            and period_sde >= 5
            and detection_snr is not None
            and detection_snr >= 5
        )
    )

    if transit_count == 0:
        has_unboxed_period_signal = (
            raw_candidate_score >= 35
            and period_sde is not None
            and period_sde >= 7
            and (p_value is None or p_value <= 0.01)
        )
        if has_unboxed_period_signal:
            status = "inconclusive"
            title = "Period signal needs review"
            short_label = "Inconclusive"
            summary = (
                "The period search found some signal, but the local detector did not box credible transit events. "
                "This needs manual review before calling it an exoplanet candidate."
            )
            recommendation = "Inspect the phase-folded view and try adjusted duration/strictness bounds."
        else:
            status = "no_planet_like_signal"
            title = "No planet-like transit detected"
            short_label = "No credible signal"
            summary = (
                "No statistically credible repeating transit signal was found. "
                "This dataset may not contain a detectable transiting exoplanet at the current settings."
            )
            recommendation = "Check the input columns, try lower strictness, or analyze a longer/higher-SNR light curve."
    elif severe_timing_mismatch:
        status = "no_planet_like_signal"
        title = "Transit-like dips are not periodic"
        short_label = "No credible signal"
        summary = (
            "The detector found dip-shaped events, but most do not align with one repeating orbital schedule. "
            "That pattern is more consistent with irregular variability or systematics than a single transiting exoplanet."
        )
        recommendation = "Inspect the off-period dips and try stricter duration/depth bounds before treating this as a candidate."
    elif raw_candidate_score >= 75 and strong_requirements_met:
        status = "strong_candidate"
        title = "Strong planet-like transit candidate"
        short_label = "Strong candidate"
        summary = (
            "Repeated dips align with a stable period and pass the current signal-strength checks. "
            "This is a strong candidate, not a confirmed planet."
        )
        recommendation = "Use the phase-folded view, exports, and follow-up vetting before treating this as confirmed."
    elif raw_candidate_score >= 45 and transit_count >= 2 and credible_tls_signal:
        status = "possible_candidate"
        title = "Possible transit candidate"
        short_label = "Possible candidate"
        summary = (
            "The dataset contains some planet-like transit evidence, but one or more checks are not strong enough "
            "for a confident candidate call."
        )
        recommendation = "Review warnings, period aliases, and the phase-folded view."
    else:
        status = "no_planet_like_signal"
        title = "No credible planet-like signal"
        short_label = "No credible signal"
        summary = (
            "Detected dips do not currently pass enough planet-likeness checks. "
            "This dataset may not contain a detectable transiting exoplanet."
        )
        recommendation = "Inspect warnings and rerun with adjusted detection bounds if the light curve looks suspicious."

    candidate_score = raw_candidate_score
    if status == "possible_candidate":
        candidate_score = min(candidate_score, 74)
    elif status == "inconclusive":
        candidate_score = min(candidate_score, 59)
    elif status == "no_planet_like_signal":
        candidate_score = min(candidate_score, 44)

    return {
        "assessment_version": 2,
        "score_label": "Candidate score",
        "score_is_probability": False,
        "status": status,
        "title": title,
        "short_label": short_label,
        "candidate_score": candidate_score,
        "summary": summary,
        "recommendation": recommendation,
        "supporting_evidence": supporting_evidence,
        "limiting_evidence": limiting_evidence,
        "inputs": {
            "transit_count": transit_count,
            "locally_supported_event_count": local_event_count,
            "evidence_basis": "combined periodic signal" if combined_support and local_event_count < 3 else "locally supported events",
            "predicted_window_count": len(transits),
            "period": period,
            "period_method": period_method,
            "period_sde": period_sde,
            "detection_snr": detection_snr,
            "tls_fap": tls_fap,
            "p_value": p_value,
            "depth_scatter_ratio": depth_scatter_ratio,
            "odd_even_depth_mismatch": odd_even_mismatch,
            "max_radius_ratio": max_radius_ratio,
            "median_transit_points": median_transit_points,
            "ephemeris_match_fraction": ephemeris_match_fraction,
            "ephemeris_match_count": ephemeris_match_count,
            "ephemeris_event_match_count": ephemeris_event_match_count,
            "off_ephemeris_transit_count": off_ephemeris_count,
            "off_ephemeris_fraction": off_ephemeris_fraction,
            "expected_transit_count": expected_transit_count,
            "expected_transit_coverage": expected_transit_coverage,
            "timing_residual_ratio": timing_residual_ratio,
            "warning_count": len(warnings),
            "danger_warning_count": danger_count,
            "caution_warning_count": caution_count,
        },
    }


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


def downsample_indices_for_series(series_values, max_points=MAX_PLOT_POINTS):
    series = [np.asarray(values, dtype=float) for values in series_values if values is not None]
    if not series:
        return np.asarray([], dtype=int)
    size = min(len(values) for values in series)
    if size <= max_points:
        return np.arange(size, dtype=int)

    points_per_bucket = max(2, 2 * len(series))
    bucket_count = max(1, (max_points - 2) // points_per_bucket)
    edges = np.linspace(0, size, bucket_count + 1, dtype=int)
    keep = {0, size - 1}
    for start, end in zip(edges[:-1], edges[1:]):
        if end <= start:
            continue
        for values in series:
            bucket = values[start:end]
            finite = np.isfinite(bucket)
            if not np.any(finite):
                continue
            finite_indices = np.flatnonzero(finite)
            finite_values = bucket[finite]
            keep.add(start + int(finite_indices[int(np.argmin(finite_values))]))
            keep.add(start + int(finite_indices[int(np.argmax(finite_values))]))
    return np.asarray(sorted(keep), dtype=int)


def downsample_for_plot(time, flux, smooth_flux, max_points=MAX_PLOT_POINTS):
    n = len(time)
    keep = downsample_indices(smooth_flux if n > max_points else flux, max_points)
    return time[keep], flux[keep], smooth_flux[keep]


def model_flux_at_observations(time, period, epoch, transit_model):
    if (
        transit_model is None
        or period is None
        or epoch is None
        or not math.isfinite(float(period))
        or float(period) <= 0
        or not math.isfinite(float(epoch))
    ):
        return None

    model_phase = np.asarray(transit_model.get("folded_phase_days", []), dtype=float)
    model_flux = np.asarray(transit_model.get("folded_flux", []), dtype=float)
    size = min(model_phase.size, model_flux.size)
    if size < 2:
        return None
    model_phase = model_phase[:size]
    model_flux = model_flux[:size]
    valid = np.isfinite(model_phase) & np.isfinite(model_flux)
    model_phase = model_phase[valid]
    model_flux = model_flux[valid]
    if model_phase.size < 2:
        return None

    order = np.argsort(model_phase)
    model_phase = model_phase[order]
    model_flux = model_flux[order]
    model_phase, unique_indices = np.unique(model_phase, return_index=True)
    model_flux = model_flux[unique_indices]
    if model_phase.size < 2:
        return None

    period = float(period)
    phase = ((np.asarray(time, dtype=float) - float(epoch) + period / 2.0) % period) - period / 2.0
    return np.interp(phase, model_phase, model_flux, left=1.0, right=1.0)


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

    cadence = float(np.median(np.diff(time))) if len(time) > 1 else 1.0
    duration_value = float(duration) if duration is not None and math.isfinite(duration) and duration > 0 else None
    focus_half_width = max(period * 0.04, cadence * 30.0, 1.0)
    if duration_value is not None:
        focus_half_width = max(focus_half_width, duration_value * 4.0)
    focus_half_width = min(period / 2.0, focus_half_width)

    global_bin_count = int(max(60, min(280, len(phase) // 180)))
    global_edges = np.linspace(-period / 2.0, period / 2.0, global_bin_count + 1)
    focus_point_count = int(np.count_nonzero(np.abs(phase) <= focus_half_width))
    if duration_value is not None:
        target_focus_width = max(cadence, duration_value / 24.0)
    else:
        target_focus_width = max(cadence, focus_half_width / 80.0)
    desired_focus_bins = int(math.ceil(2.0 * focus_half_width / target_focus_width))
    data_limited_focus_bins = max(40, focus_point_count // 8)
    focus_bin_count = int(max(
        40,
        min(600, desired_focus_bins, data_limited_focus_bins),
    ))
    focus_edges = np.linspace(-focus_half_width, focus_half_width, focus_bin_count + 1)
    edges = np.unique(np.r_[
        global_edges[global_edges < -focus_half_width],
        focus_edges,
        global_edges[global_edges > focus_half_width],
    ])
    bin_count = len(edges) - 1
    bin_ids = np.digitize(phase, edges) - 1
    binned_phase = []
    binned_flux = []
    binned_count = []
    binned_uncertainty = []
    binned_break_indices = []
    last_bin = None
    for bin_index in range(bin_count):
        mask = bin_ids == bin_index
        if not np.any(mask):
            continue
        if last_bin is not None and bin_index > last_bin + 1:
            binned_break_indices.append(len(binned_phase))
        binned_phase.append(float((edges[bin_index] + edges[bin_index + 1]) / 2.0))
        binned_flux.append(float(np.median(raw_flux[mask])))
        binned_count.append(int(np.count_nonzero(mask)))
        binned_uncertainty.append(robust_standard_error(raw_flux[mask]))
        last_bin = bin_index

    binned_phase = np.asarray(binned_phase, dtype=float)
    binned_flux = np.asarray(binned_flux, dtype=float)

    if binned_flux.size >= 5:
        flux_min, flux_max = domain_for(binned_flux, 0.0, 100.0)
    else:
        flux_min, flux_max = domain_for(raw_flux, 0.5, 99.5)

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
        "binned_count": binned_count,
        "binned_uncertainty": binned_uncertainty,
        "binned_break_indices": binned_break_indices,
        "representation": "normalized observations (global phase check)",
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


def build_transit_stack(time, smooth_flux, transits, period, duration, max_trace_points=320):
    """Align and locally normalize individual events for display-only inspection."""
    time = np.asarray(time, dtype=float)
    smooth_flux = np.asarray(smooth_flux, dtype=float)
    if time.size < 3 or time.size != smooth_flux.size or not transits:
        return None

    duration_value = finite_number(duration)
    if duration_value is None or duration_value <= 0:
        durations = finite_values([item.get("duration") for item in transits])
        duration_value = float(np.median(durations)) if durations else None
    if duration_value is None or duration_value <= 0:
        return None

    finite_time = time[np.isfinite(time)]
    if finite_time.size < 3:
        return None
    positive_steps = np.diff(np.sort(finite_time))
    positive_steps = positive_steps[positive_steps > 0]
    cadence = float(np.median(positive_steps)) if positive_steps.size else duration_value / 20.0
    half_window = max(duration_value * 3.0, cadence * 12.0)
    period_value = finite_number(period)
    if period_value is not None and period_value > 0:
        half_window = min(half_window, period_value * 0.35)
    half_window = max(half_window, duration_value * 1.5, cadence * 4.0)

    traces = []
    combined_phase = []
    combined_flux = []
    segments = observing_segments(time)
    for index, transit in enumerate(transits):
        center = finite_number(transit.get("center"))
        if center is None:
            continue
        mask = (
            np.isfinite(time)
            & np.isfinite(smooth_flux)
            & (time >= center - half_window)
            & (time <= center + half_window)
        )
        segment = next(((a, b) for a, b in segments if time[a] <= center <= time[b - 1]), None)
        if segment is None:
            continue
        segment_mask = np.zeros(len(time), dtype=bool)
        segment_mask[segment[0]:segment[1]] = True
        mask &= segment_mask
        if np.count_nonzero(mask) < 3:
            continue

        offsets = time[mask] - center
        values = smooth_flux[mask]
        order = np.argsort(offsets)
        offsets = offsets[order]
        values = values[order]

        baseline_mask = np.abs(offsets) >= duration_value * 0.75
        if np.count_nonzero(baseline_mask) >= 6:
            slope, intercept = np.polyfit(offsets[baseline_mask], values[baseline_mask], 1)
            baseline_curve = slope * offsets + intercept
            if not np.all(np.isfinite(baseline_curve)) or np.any(baseline_curve <= 0):
                baseline_curve = np.full_like(values, float(np.median(values[baseline_mask])))
        else:
            baseline_values = values[baseline_mask] if np.any(baseline_mask) else values
            baseline_curve = np.full_like(values, float(np.median(baseline_values)))
        valid_baseline = np.isfinite(baseline_curve) & (baseline_curve > 0)
        if np.count_nonzero(valid_baseline) < 3:
            continue
        offsets = offsets[valid_baseline]
        values = values[valid_baseline]
        baseline_curve = baseline_curve[valid_baseline]
        normalized = values / baseline_curve

        combined_phase.append(offsets)
        combined_flux.append(normalized)
        keep = downsample_indices_for_series([normalized], max_trace_points)
        traces.append({
            "transit_index": index + 1,
            "center": float(center),
            "phase_days": offsets[keep].tolist(),
            "flux": normalized[keep].tolist(),
            "point_count": int(offsets.size),
            "baseline": float(np.median(baseline_curve)),
            "cycle_number": transit.get("cycle_number", index),
            "state": transit.get("state", "legacy_event"),
            "depth": transit.get("signed_depth", transit.get("depth")),
            "depth_uncertainty": transit.get("depth_uncertainty"),
            "local_snr": transit.get("local_snr"),
            "coverage_fraction": transit.get("coverage_fraction"),
            "timing_residual": None if transit.get("measured_center") is None else transit["measured_center"] - center,
            "timing_uncertainty": transit.get("timing_uncertainty"),
        })

    if not traces:
        return None

    all_phase = np.concatenate(combined_phase)
    all_flux = np.concatenate(combined_flux)
    target_bin_width = max(cadence, duration_value / 36.0)
    bin_count = int(max(48, min(400, math.ceil(2.0 * half_window / target_bin_width))))
    edges = np.linspace(-half_window, half_window, bin_count + 1)
    bin_ids = np.digitize(all_phase, edges) - 1
    median_phase = []
    median_flux = []
    for bin_index in range(bin_count):
        mask = bin_ids == bin_index
        if not np.any(mask):
            continue
        median_phase.append(float(np.median(all_phase[mask])))
        median_flux.append(float(np.median(all_flux[mask])))

    domain_values = np.r_[all_flux, np.asarray(median_flux, dtype=float)]
    flux_min, flux_max = domain_for(domain_values, 0.2, 99.8)
    return {
        "traces": traces,
        "median_phase_days": median_phase,
        "median_flux": median_flux,
        "duration": float(duration_value),
        "window_half_width": float(half_window),
        "representation": "locally detrended normalized observations (event consistency)",
        "domain": {
            "time_min": float(-half_window),
            "time_max": float(half_window),
            "flux_min": flux_min,
            "flux_max": flux_max,
        },
    }


def exploratory_local_dips(time, flux, options, time_reference, max_items=500):
    """Reuse the local morphology detector as an explicitly unvalidated layer."""
    candidates = []
    for start, end in observing_segments(time):
        if end - start < 10:
            continue
        segment_baseline = float(np.median(flux[start:end]))
        prominence = detect_transits_by_prominence(time[start:end], flux[start:end], segment_baseline, options)
        threshold = detect_transits_by_threshold(time[start:end], flux[start:end], segment_baseline, options)
        local_events = prune_overlapping_transits((prominence or {}).get("transits", []) + (threshold or {}).get("transits", []))
        for transit in local_events:
            event = dict(transit)
            add_depth_metrics(event, float(np.median(flux[start:end])))
            for key in ("start", "end", "center"):
                event[key] -= time_reference
            event.update(role="exploratory", validated=False, source="local prominence/threshold detectors",
                         matched_signal_ids=[], assignment="unassigned")
            candidates.append(event)
    total = len(candidates)
    if total > max_items:
        candidates = sorted(candidates, key=lambda item: item.get("depth", 0) * math.sqrt(item.get("points", 1)), reverse=True)[:max_items]
    candidates.sort(key=lambda item: item["center"])
    for index, candidate in enumerate(candidates):
        candidate["dip_id"] = f"dip-{index + 1}"
    return candidates, {"method": "existing local prominence/threshold detectors, applied within observing segments",
                        "total_before_display_cap": total, "display_cap": max_items,
                        "interpretation": "Unvalidated local features; not planets, not independent confirmations, and never added to the candidate score."}


def tag_exploratory_assignments(result, signals):
    for dip in result.get("exploratory_dips", []):
        absolute_center = dip["center"] + result["time_reference"]
        matches = []
        for index, signal in enumerate(signals):
            relative_center = absolute_center - signal["time_reference"]
            if any(event["start"] <= relative_center <= event["end"] for event in signal.get("predicted_windows", signal.get("transits", []))):
                matches.append(signal.get("signal_id", f"signal-{index + 1}"))
        dip["matched_signal_ids"] = matches
        dip["assignment"] = "overlaps_predicted_window" if matches else "unassigned"


def joint_template_amplitudes(time, search_flux, signals, uncertainty=None):
    """Fit simultaneous depths and one baseline with orbital templates fixed.

    This handles additive small-planet flux deficits at overlapping timestamps.
    It does not infer orbital parameters or model overlapping silhouettes.
    """
    if len(signals) < 2:
        return None
    try:
        from scipy.optimize import least_squares
    except ImportError:
        return None
    time, values = np.asarray(time, dtype=float), np.asarray(search_flux, dtype=float)
    shapes, prior_depths = [], []
    for signal in signals:
        model = signal.get("transit_model") or {}
        folded_flux = np.asarray(model.get("folded_flux", []), dtype=float)
        if folded_flux.size < 3:
            return None
        baseline = float(np.max(folded_flux))
        depth = float(baseline - np.min(folded_flux))
        if depth <= 0:
            return None
        aligned = model_flux_at_observations(time, signal["period"], signal["period_epoch"], model)
        if aligned is None:
            return None
        shapes.append(np.maximum(0.0, (baseline - aligned) / depth))
        prior_depths.append(depth)
    design = np.column_stack([np.ones(len(time))] + [-shape for shape in shapes])
    sigma = max(1.4826 * float(np.median(np.abs(values - np.median(values)))), 1e-8)
    errors = np.full(len(time), sigma)
    if uncertainty is not None:
        supplied = np.asarray(uncertainty, dtype=float)
        if len(supplied) == len(time) and np.all(np.isfinite(supplied)) and np.all(supplied > 0):
            errors = supplied
    initial = [float(np.median(values)), *prior_depths]
    fit = least_squares(lambda pars: (design @ pars - values) / errors, initial,
                        jac=lambda pars: design / errors[:, None], loss="soft_l1",
                        bounds=([0.5] + [0.0] * len(signals), [1.5] + [0.5] * len(signals)), max_nfev=60)
    if not fit.success or not np.all(np.isfinite(fit.x)):
        return None
    degrees = max(len(values) - len(fit.x), 1)
    residual_variance = float(np.sum(fit.fun ** 2) / degrees)
    try:
        covariance = np.linalg.pinv(fit.jac.T @ fit.jac) * max(1.0, residual_variance)
        errors_on_parameters = np.sqrt(np.maximum(0.0, np.diag(covariance)))
    except np.linalg.LinAlgError:
        errors_on_parameters = np.full(len(fit.x), np.nan)
    fitted = design @ fit.x
    return {
        "baseline": float(fit.x[0]), "depths": fit.x[1:].tolist(),
        "depth_uncertainties": [float(value) if np.isfinite(value) else None for value in errors_on_parameters[1:]],
        "model_flux": fitted, "residual_flux": values - fitted,
        "components": [1.0 - depth * shape for depth, shape in zip(fit.x[1:], shapes)],
        "metadata": {"method": "robust simultaneous additive template amplitude and baseline fit",
                     "fixed_parameters": ["period", "epoch", "duration", "template shape"],
                     "fitted_parameters": ["per-signal flux deficit", "shared baseline"],
                     "overlap_model": "sum of flux deficits; overlapping planet silhouettes are not modeled geometrically",
                     "uncertainty_basis": "conditional local Jacobian with residual-variance inflation; not an orbital posterior",
                     "reduced_chi_squared": residual_variance,
                     "overlapping_sample_count": int(np.count_nonzero(np.sum(np.asarray(shapes) > .001, axis=0) > 1))},
    }


def update_signal_joint_depth(signal, depth, uncertainty):
    """Keep component model payloads consistent with a conditional joint depth."""
    model = signal.get("transit_model") or {}
    folded_flux = np.asarray(model.get("folded_flux", []), dtype=float)
    if folded_flux.size < 3:
        return
    baseline = float(np.max(folded_flux))
    previous_depth = float(baseline - np.min(folded_flux))
    if previous_depth <= 0:
        return
    signal["transit_model"] = {**model,
        "folded_flux": (1.0 - (baseline - folded_flux) * depth / previous_depth).tolist(),
        "flux": (1.0 - (baseline - np.asarray(model.get("flux", []))) * depth / previous_depth).tolist(),
        "depth_source": "conditional joint template amplitude", "component_baseline": 1.0,
    }
    if signal.get("tls"):
        signal["tls"] = {**signal["tls"], "engine_depth_fraction": signal["tls"].get("engine_depth_fraction", signal["tls"].get("depth_fraction")),
                         "depth_fraction": float(depth), "depth_uncertainty": uncertainty,
                         "depth_source": "conditional joint template amplitude"}
    comparison = signal.get("model_comparison")
    if comparison:
        old = np.asarray(comparison["model_flux"])
        updated = 1.0 - (baseline - old) * depth / previous_depth
        signal["model_comparison"] = {**comparison, "model_flux": updated.tolist(),
                                      "residual_flux": (np.asarray(comparison["search_flux"]) - updated).tolist()}
    signal["joint_depth_refinement"] = {"depth_fraction": float(depth), "uncertainty": uncertainty,
                                        "parameters_held_fixed": ["period", "epoch", "duration", "template shape"]}


def analyze(time, flux, options=None, progress_callback=None):
    def report_progress(stage, stage_label, details=None):
        if callable(progress_callback):
            if details is None:
                progress_callback(stage, stage_label)
            else:
                progress_callback(stage, stage_label, details)

    if options is None:
        options = dict(DEFAULT_DETECTION_OPTIONS)
    else:
        options = {**DEFAULT_DETECTION_OPTIONS, **options}
    time, flux = np.asarray(time, dtype=float), np.asarray(flux, dtype=float)
    if len(time) < 3 or len(time) != len(flux) or not np.isfinite(time).all() or not np.isfinite(flux).all():
        raise ValueError("Analysis requires matching finite time/flux samples.")
    if np.any(np.diff(time) <= 0):
        raise ValueError("Analysis timestamps must be sorted, unique, and span more than zero days.")
    report_progress("preparing", "Preparing light curve")
    normalization_plan = flux_normalization_plan(flux)
    analysis_flux, segments = normalize_flux_by_segments(time, flux)
    normalized_uncertainty = None
    uncertainty_complete = False
    if options.get("_flux_uncertainty") is not None:
        supplied_uncertainty = np.asarray(options["_flux_uncertainty"], dtype=float)
        if len(supplied_uncertainty) == len(time):
            normalized_uncertainty = supplied_uncertainty.copy()
            for start, end in segments:
                residual_scale = normalization_plan.get("residual_scale")
                scale = abs(float(np.median(flux[start:end])) + (residual_scale or 0.0))
                if scale > 0:
                    normalized_uncertainty[start:end] /= scale
            uncertainty_complete = bool(np.all(np.isfinite(normalized_uncertainty)) and np.all(normalized_uncertainty > 0))
            if uncertainty_complete:
                options = {**options, "_normalized_flux_uncertainty": normalized_uncertainty}
    search_mode = options.get("search_mode", DEFAULT_DETECTION_OPTIONS["search_mode"])
    if search_mode == "tls":
        report_progress("tls_search", "Searching periods with TLS")
    else:
        report_progress("bls_search", "Searching periods with BLS")
    detection = detect_transits(time, analysis_flux, options,
                                progress_callback=lambda details: report_progress(
                                    "tls_finalizing" if details.get("search_complete") else "tls_search",
                                    "Finalizing TLS model" if details.get("search_complete") else "Searching periods with TLS", details))
    report_progress("building", "Building transit model and plots")
    time_reference = float(time[0])
    display_time = time - time_reference
    raw_low, raw_high = robust_flux_limits(analysis_flux, sigma=4.0)
    raw_clipped = np.clip(analysis_flux, raw_low, raw_high)

    transit_model = detection.get("transit_model")
    base_smooth_width = int(max(25, min(251, len(analysis_flux) // 300)))
    smooth_width = odd_window_width(base_smooth_width, float(options["smoothing"]), 5, 601)
    cadence = float(np.median(np.diff(time))) if len(time) > 1 else 1.0
    period_sde = finite_number(detection.get("period_sde"))
    if transit_model is not None and period_sde is not None and period_sde >= 5.0:
        smooth_width = transit_preserving_smoothing_width(
            smooth_width,
            cadence,
            detection.get("period_duration"),
        )
    smooth_flux = moving_average_by_segments(raw_clipped, smooth_width, segments)

    observed_model_flux = model_flux_at_observations(
        time,
        detection.get("period"),
        detection.get("period_epoch"),
        transit_model,
    )
    display_model_flux = None
    if observed_model_flux is not None:
        display_model_flux = moving_average_by_segments(observed_model_flux, smooth_width, segments)

    plot_keep = downsample_indices_for_series(
        [analysis_flux, smooth_flux, display_model_flux] if display_model_flux is not None else [analysis_flux, smooth_flux],
        MAX_PLOT_POINTS,
    )
    plot_keep = np.unique(np.r_[plot_keep, [index for start, end in segments for index in (start, end - 1)]]).astype(int)
    plot_time = display_time[plot_keep]
    plot_raw = analysis_flux[plot_keep]
    plot_smooth = smooth_flux[plot_keep]
    raw_flux_min, raw_flux_max = domain_for(raw_clipped, 0.5, 99.5)
    clean_domain_values = (
        np.r_[smooth_flux, display_model_flux]
        if display_model_flux is not None
        else smooth_flux
    )
    clean_flux_min, clean_flux_max = domain_for(clean_domain_values, 0.2, 99.8)
    phase_folded = build_phase_folded_plot(
        time,
        raw_clipped,
        smooth_flux,
        detection["period"],
        detection["period_epoch"],
        detection["period_duration"],
    )
    transit_stack = build_transit_stack(
        time,
        analysis_flux,
        [event for event in detection["transits"] if event.get("points", 1) > 0],
        detection["period"],
        detection["period_duration"],
    )

    if transit_model is not None and display_model_flux is not None:
        transit_model = {
            **transit_model,
            "time": plot_time.tolist(),
            "flux": display_model_flux[plot_keep].tolist(),
            "time_series_representation": "observation-aligned and plot-smoothed",
            "plot_smooth_points": smooth_width,
        }
        detection = {**detection, "transit_model": transit_model}

    display_transits = []
    for transit in detection["transits"]:
        display_transit = dict(transit)
        add_depth_metrics(display_transit, transit.get("local_baseline", detection["median_flux"]))
        for key in ("predicted_center", "measured_center"):
            if transit.get(key) is not None:
                display_transit[key] = float(transit[key] - time_reference)
        display_transit["start"] = float(transit["start"] - time_reference)
        display_transit["center"] = float(transit["center"] - time_reference)
        display_transit["end"] = float(transit["end"] - time_reference)
        local = (time >= transit["start"]) & (time <= transit["end"])
        display_extents = {}
        for name, values in (("raw", analysis_flux), ("clean", smooth_flux)):
            local_values = values[local]
            if name == "clean" and display_model_flux is not None:
                local_values = np.r_[local_values, display_model_flux[local]]
            if local_values.size:
                low, high = np.percentile(local_values, [5, 95])
                baseline = transit.get("local_baseline")
                if baseline is not None:
                    high = max(high, baseline)
                padding = max((high - low) * 0.12, 1e-6)
                display_extents[name] = {"flux_min": float(low - padding), "flux_max": float(high + padding),
                                         "low": float(low - padding), "high": float(high + padding)}
        display_transit["display_extents"] = display_extents
        if transit_model is not None and display_model_flux is not None:
            display_start, display_end = smoothed_transit_display_bounds(
                display_transit["start"],
                display_transit["end"],
                cadence,
                smooth_width,
                float(display_time[0]),
                float(display_time[-1]),
            )
            display_transit["display_start"] = display_start
            display_transit["display_end"] = display_end
        display_transits.append(display_transit)
    observed_ranges = [
        (float(time[start] - time_reference), float(time[end - 1] - time_reference))
        for start, end in segments
    ]
    report_progress("vetting", "Calculating diagnostics")
    diagnostics, warnings = build_candidate_diagnostics(display_transits, detection, time_reference, observed_ranges)
    if normalized_uncertainty is not None and not uncertainty_complete:
        warnings.append({"severity": "info", "title": "Partial measurement uncertainties",
                         "detail": "Some flux errors are missing or invalid. They remain null in plots/exports; TLS uses its unweighted fallback for this file and local checks use empirical noise."})
    planet_assessment = build_planet_assessment(display_transits, detection, diagnostics, warnings)
    exploratory_dips, exploratory_metadata = ([], None)
    if not options.get("_skip_local_inspection"):
        exploratory_dips, exploratory_metadata = exploratory_local_dips(time, analysis_flux, options, time_reference)
    fit_accepted = planet_assessment["status"] in ("strong_candidate", "possible_candidate")
    fit_quality = {"state": "accepted" if fit_accepted else "tentative",
                   "label": "Candidate model" if fit_accepted else "Tentative fit - below candidate threshold",
                   "reason_codes": [warning["title"].lower().replace(" ", "_") for warning in warnings if warning.get("severity") in ("caution", "danger")]}
    search_flux = None
    if search_mode == "tls":
        search_flux, _ = normalized_flux_for_tls(time, analysis_flux)
    comparison = None
    if search_flux is not None and observed_model_flux is not None:
        comparison = {"time": plot_time.tolist(), "search_flux": search_flux[plot_keep].tolist(),
                      "model_flux": observed_model_flux[plot_keep].tolist(),
                      "residual_flux": (search_flux - observed_model_flux)[plot_keep].tolist(),
                      "representation": "search-detrended observations and physical template on identical timestamps",
                      "break_indices": [int(np.searchsorted(plot_keep, start)) for start, _ in segments[1:]]}

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
        zoom_values = smooth_flux[zoom_mask]
        if display_model_flux is not None:
            zoom_values = np.r_[zoom_values, display_model_flux[zoom_mask]]
        zoom_flux_min, zoom_flux_max = domain_for(zoom_values, 0.0, 100.0)
        zoom_domain = {
            "time_min": zoom_time_min,
            "time_max": zoom_time_max,
            "flux_min": zoom_flux_min,
            "flux_max": zoom_flux_max,
        }

    report_progress("finalizing", "Finalizing results")
    public_options = {key: value for key, value in options.items() if not key.startswith("_")}
    result = {
        "total_points": int(len(time)),
        "time_reference": time_reference,
        "time_unit": "Days since first observation",
        "flux_unit": "relative flux",
        "normalization": {
            "method": normalization_plan["method"],
            "input_representation": normalization_plan["input_representation"],
            "residual_scale": normalization_plan["residual_scale"],
            "segment_count": len(segments),
            "segment_time_ranges": [
                {
                    "start_day": float(time[start] - time_reference),
                    "end_day": float(time[end - 1] - time_reference),
                    "median_flux": float(np.median(flux[start:end])),
                }
                for start, end in segments
            ],
        },
        "plot": {
            "time": plot_time.tolist(),
            "raw_flux": plot_raw.tolist(),
            "smooth_flux": plot_smooth.tolist(),
            "break_indices": [int(np.searchsorted(plot_keep, start)) for start, _ in segments[1:]],
            "raw_representation": "unclipped segment-normalized flux at retained plot samples",
            "clean_representation": "display-clipped, segment-smoothed observations",
        },
        "domain": {
            "time_min": 0.0,
            "time_max": float(display_time[-1]),
        },
        "raw_domain": {"flux_min": raw_flux_min, "flux_max": raw_flux_max},
        "clean_domain": {"flux_min": clean_flux_min, "flux_max": clean_flux_max},
        "zoom_domain": zoom_domain,
        "phase_folded": phase_folded,
        "transit_stack": transit_stack,
        "plot_smooth_points": smooth_width,
        "diagnostics": diagnostics,
        "warnings": warnings,
        "planet_assessment": planet_assessment,
        "fit_quality": fit_quality,
        "model_comparison": comparison,
        "predicted_windows": display_transits,
        "observed_events": [event for event in display_transits if event.get("state", "supported_dip") == "supported_dip"],
        "exploratory_dips": exploratory_dips,
        "exploratory_dips_metadata": exploratory_metadata,
        "cleaning_report": options.get("_cleaning_report"),
        "input_metadata": options.get("_input_metadata", {"time_format": "unspecified", "time_standard": "unspecified"}),
        "preprocessing": {"normalized": "per-observing-segment median", "search": "segment-local trend removal; downward samples retained", "display": "segment-local moving average", "stack": "per-event linear baseline, no automatic recentering"},
        "significance_metadata": {"p_value": "Approximate fixed-model-versus-flat chi-squared comparison after selecting the period; not search-wide false alarm or planet probability.",
                                  "tls_fap": "Reference TLS white-noise lookup; correlated noise and selection effects can make it optimistic.",
                                  "candidate_score": "Heuristic review score, not a calibrated probability."},
        "effective_settings": {**public_options, "stellar_priors": (detection.get("tls") or {}).get("effective_stellar_priors"),
                               "local_dip_settings": {key: public_options.get(key) for key in ("strictness", "smoothing", "min_depth", "min_duration", "max_duration")},
                               "search_bounds": {**(detection.get("period_search") or {}), "min_transits": options.get("tls_min_transits"),
                                                 "duration_policy": "Physical TLS stellar-prior/template grid; explicit local dip duration bounds are not applied to TLS." if search_mode == "tls" else "Explicit or cadence-derived BLS duration bounds.",
                                                 "bounds_reason": ("Upper period limited by observed baseline / minimum transit count; explicit bounds also applied." if search_mode == "tls" else "Cadence, baseline and explicit period/duration bounds applied to BLS.")}},
        "detection_snr": diagnostics["detection_snr"],
        "odd_even_depth_mismatch": diagnostics["odd_even_depth_mismatch"],
        "depth_scatter_ratio": diagnostics["depth_scatter_ratio"],
        **{**detection, "transits": [event for event in display_transits if event.get("points", 1) > 0], "detection_options": public_options},
    }
    if normalized_uncertainty is not None:
        result["plot"]["flux_uncertainty"] = [float(value) if np.isfinite(value) and value > 0 else None for value in normalized_uncertainty[plot_keep]]
        result["uncertainty_usage"] = ("Normalized input uncertainties supplied to TLS; local event estimates additionally use empirical correlated-noise errors." if uncertainty_complete
                                       else "Incomplete errors retained as null; TLS uses unweighted fallback and local checks use empirical correlated-noise errors.")
    max_signals = int(options.get("tls_max_signals", options.get("max_signals", 1)))
    if search_mode == "tls" and max_signals > 1:
        signals = [{"signal_id": "signal-1", "label": "Signal 1", **result}]
        retained = np.ones(len(time), dtype=bool)
        stop_reason = "requested_signal_limit"
        for signal_index in range(1, min(max_signals, 5)):
            previous = signals[-1]
            if previous["planet_assessment"]["status"] != "strong_candidate":
                stop_reason = "Previous signal lacks strong support; no tentative model was masked."
                break
            supported = previous.get("observed_events", [])
            if len(supported) < 3:
                stop_reason = "Fewer than three locally supported events; residual search stopped."
                break
            for event in supported:
                center = event["center"] + previous["time_reference"]
                retained &= np.abs(time - center) > event["duration"] * 0.65
            if np.count_nonzero(retained) < 50:
                stop_reason = "Too few unmasked observations remain."
                break
            report_progress("tls_search", f"Searching residual observations for signal {signal_index + 1}")
            next_options = {**options, "tls_max_signals": 1, "max_signals": 1, "_skip_local_inspection": True}
            if options.get("_flux_uncertainty") is not None:
                next_options["_flux_uncertainty"] = np.asarray(options["_flux_uncertainty"])[retained]
                next_options.pop("_normalized_flux_uncertainty", None)
            candidate = analyze(time[retained], flux[retained], next_options, progress_callback)
            # Do not present another optimizer noise pattern as a recovered planet.
            if candidate["planet_assessment"]["status"] not in ("strong_candidate", "possible_candidate"):
                result["residual_search_attempt"] = {"period": candidate.get("period"), "sde": candidate.get("period_sde"), "fit_quality": candidate.get("fit_quality")}
                stop_reason = "No additional credible periodic signal in the residual observations."
                break
            candidate.update(signal_id=f"signal-{signal_index + 1}", label=f"Signal {signal_index + 1}",
                             search_context={"method": "iterative conservative transit masking", "masked_samples": int(np.count_nonzero(~retained)), "joint_refit": False})
            signals.append(candidate)
        result["signals"] = signals
        result["multi_signal_search"] = {"requested": max_signals, "recovered": sum(signal["planet_assessment"]["status"] in ("strong_candidate", "possible_candidate") for signal in signals),
                                         "attempted_signals": len(signals), "stop_reason": stop_reason,
                                         "method": "conservative supported-event masking; conditional residual searches", "joint_refit": False,
                                         "limitation": "Overlapping events and period aliases still require joint follow-up vetting."}
        if len(signals) >= 2 and search_flux is not None:
            report_progress("building", "Refining overlapping transit amplitudes together")
            joint = joint_template_amplitudes(time, search_flux, signals,
                                               normalized_uncertainty if uncertainty_complete else None)
            if joint is not None:
                for signal, depth, depth_error in zip(signals, joint["depths"], joint["depth_uncertainties"]):
                    update_signal_joint_depth(signal, depth, depth_error)
                    signal["search_context"] = {**signal.get("search_context", {}), "joint_refit": True,
                                                 "joint_scope": "amplitudes and shared baseline; orbital parameters held fixed"}
                for field in ("transit_model", "tls", "model_comparison", "joint_depth_refinement"):
                    result[field] = signals[0][field]
                result["joint_model_comparison"] = {
                    "time": plot_time.tolist(), "search_flux": search_flux[plot_keep].tolist(),
                    "model_flux": joint["model_flux"][plot_keep].tolist(), "residual_flux": joint["residual_flux"][plot_keep].tolist(),
                    "break_indices": [int(np.searchsorted(plot_keep, start)) for start, _ in segments[1:]],
                    "representation": "original search-detrended observations with simultaneous fixed-template signal amplitudes",
                    "components": [{"signal_id": signal["signal_id"], "label": signal["label"], "flux": component[plot_keep].tolist()}
                                   for signal, component in zip(signals, joint["components"])],
                }
                result["multi_signal_search"].update(joint_refit=True, joint_fit=joint["metadata"],
                                                      limitation="Joint amplitudes and baseline fitted; orbital parameters and transit shapes remain conditional and require follow-up vetting.")
    tag_exploratory_assignments(result, result.get("signals") or [result])
    return result
