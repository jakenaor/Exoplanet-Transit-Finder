import math

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


def normalize_flux_by_segments(time, flux):
    normalized = np.asarray(flux, dtype=float).copy()
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
    min_duration, max_duration = constrain_duration_bounds(cadence, min_period, min_duration, max_duration, options)
    if min_period >= max_period or min_duration >= max_duration:
        return None

    periods = period_grid(min_period, max_period, 1200)
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


def finite_number(value):
    if value is None:
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


def build_ephemeris_diagnostics(transits, detection, time_reference=0.0):
    period = finite_number(detection.get("period"))
    epoch = finite_number(detection.get("period_epoch"))
    period_duration = finite_number(detection.get("period_duration"))
    expected_count = finite_number(detection.get("period_match_count"))
    centers = finite_values([item.get("center") for item in transits])
    durations = finite_values([item.get("duration") for item in transits])

    empty = {
        "ephemeris_match_count": None,
        "ephemeris_match_fraction": None,
        "off_ephemeris_transit_count": None,
        "off_ephemeris_fraction": None,
        "expected_transit_count": expected_count,
        "expected_transit_coverage": None,
        "timing_residual_median": None,
        "timing_residual_max": None,
        "timing_residual_tolerance": None,
        "timing_residual_ratio": None,
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
    for center in centers:
        cycles = round((center - epoch_relative) / period)
        nearest_epoch = epoch_relative + cycles * period
        residual = abs(center - nearest_epoch)
        residuals.append(residual)
        if residual <= tolerance:
            matched_residuals.append(residual)

    match_count = len(matched_residuals)
    transit_count = len(centers)
    off_count = transit_count - match_count
    median_residual = median_or_none(residuals)
    expected_coverage = None
    if expected_count is not None and expected_count > 0:
        expected_coverage = min(1.0, match_count / expected_count)

    return {
        "ephemeris_match_count": int(match_count),
        "ephemeris_match_fraction": match_count / transit_count,
        "off_ephemeris_transit_count": int(off_count),
        "off_ephemeris_fraction": off_count / transit_count,
        "expected_transit_count": expected_count,
        "expected_transit_coverage": expected_coverage,
        "timing_residual_median": median_residual,
        "timing_residual_max": max(residuals) if residuals else None,
        "timing_residual_tolerance": tolerance,
        "timing_residual_ratio": None if median_residual is None else median_residual / tolerance,
    }


def build_candidate_diagnostics(transits, detection, time_reference=0.0):
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

    ephemeris = build_ephemeris_diagnostics(transits, detection, time_reference)
    diagnostics = {
        "detection_snr": detection_snr,
        "median_transit_points": median_or_none(point_counts),
        "depth_scatter_ratio": coefficient_of_variation(depths),
        "odd_depth": odd_depth,
        "even_depth": even_depth,
        "odd_even_depth_mismatch": odd_even_depth_mismatch,
        "max_radius_ratio": max(radius_ratios) if radius_ratios else None,
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
    if (
        len(transits) >= 3
        and detection.get("period_method") == "BLS"
        and diagnostics["ephemeris_match_fraction"] is not None
    ):
        match_fraction = diagnostics["ephemeris_match_fraction"]
        match_count = diagnostics["ephemeris_match_count"]
        transit_count = len(transits)
        if match_fraction < 0.55:
            warnings.append({
                "severity": "danger",
                "title": "Irregular transit timing",
                "detail": f"Only {match_count} of {transit_count} detected dips align with the BLS period.",
            })
        elif match_fraction < 0.75:
            warnings.append({
                "severity": "caution",
                "title": "Weak ephemeris agreement",
                "detail": f"{match_count} of {transit_count} detected dips align with the BLS period.",
            })

        off_count = diagnostics["off_ephemeris_transit_count"]
        off_fraction = diagnostics["off_ephemeris_fraction"]
        if off_count is not None and off_fraction is not None and off_count >= 3 and off_fraction >= 0.35:
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
    transit_count = len(transits)
    period = finite_number(detection.get("period"))
    period_method = detection.get("period_method")
    period_sde = finite_number(detection.get("period_sde"))
    detection_snr = finite_number(diagnostics.get("detection_snr"))
    p_value = finite_number(detection.get("p_value"))
    depth_scatter_ratio = finite_number(diagnostics.get("depth_scatter_ratio"))
    odd_even_mismatch = finite_number(diagnostics.get("odd_even_depth_mismatch"))
    max_radius_ratio = finite_number(diagnostics.get("max_radius_ratio"))
    median_transit_points = finite_number(diagnostics.get("median_transit_points"))
    ephemeris_match_fraction = finite_number(diagnostics.get("ephemeris_match_fraction"))
    ephemeris_match_count = finite_number(diagnostics.get("ephemeris_match_count"))
    off_ephemeris_count = finite_number(diagnostics.get("off_ephemeris_transit_count"))
    off_ephemeris_fraction = finite_number(diagnostics.get("off_ephemeris_fraction"))
    expected_transit_coverage = finite_number(diagnostics.get("expected_transit_coverage"))
    timing_residual_ratio = finite_number(diagnostics.get("timing_residual_ratio"))

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

    if transit_count >= 3:
        support("Repeated transit-like events", f"{transit_count} candidate dips were boxed.", 20)
    elif transit_count > 0:
        support("Transit-like dip found", f"{transit_count} candidate dip{'s were' if transit_count != 1 else ' was'} boxed.", 6)
        limit("Too few events", "Fewer than three events is weak evidence for an orbital period.", -8)
    else:
        limit("No boxed transit events", "The detector did not find statistically strong local dips.", -28)

    if period is not None and period > 0 and period_method == "BLS":
        support("Stable BLS period", f"Best period is {period:.6g} days from the BLS search.", 22)
    elif period is not None and period > 0:
        support("Provisional period", f"Estimated period is {period:.6g} days from {period_method or 'candidate spacing'}.", 10)
        limit("Period is not a BLS peak", "The repeating period needs manual confirmation.", -4)
    else:
        limit("No stable period", "A repeating orbital period was not recovered.", -18)

    sde_result = score_band(period_sde, (
        (10.0, 22, "Very strong period peak", f"Period SDE is {format_metric(period_sde)}."),
        (7.0, 17, "Strong period peak", f"Period SDE is {format_metric(period_sde)}."),
        (5.0, 8, "Moderate period peak", f"Period SDE is {format_metric(period_sde)}."),
    ))
    if sde_result is not None:
        points, title, detail = sde_result
        support(title, detail, points)
    elif period_sde is not None:
        limit("Weak period peak", f"Period SDE is only {period_sde:.2f}.", -10)

    snr_result = score_band(detection_snr, (
        (10.0, 22, "High transit depth SNR", f"Median depth is {format_metric(detection_snr)}x the robust noise."),
        (7.0, 16, "Good transit depth SNR", f"Median depth is {format_metric(detection_snr)}x the robust noise."),
        (5.0, 8, "Marginal transit depth SNR", f"Median depth is {format_metric(detection_snr)}x the robust noise."),
    ))
    if snr_result is not None:
        points, title, detail = snr_result
        support(title, detail, points)
    elif detection_snr is not None:
        limit("Low transit depth SNR", f"Median depth is only {detection_snr:.2f}x the robust noise.", -14)

    if p_value is not None:
        if p_value <= 1e-6:
            support("Very significant box model", "The transit model strongly beats a flat light curve.", 16)
        elif p_value <= 1e-4:
            support("Significant box model", "The transit model clearly beats a flat light curve.", 12)
        elif p_value <= 0.01:
            support("Useful box-model improvement", "The transit model improves over a flat light curve.", 8)
        else:
            limit("Weak box-model significance", "The transit model is not much better than a flat light curve.", -12)

    if period_method == "BLS" and transit_count >= 3 and ephemeris_match_fraction is not None:
        if ephemeris_match_fraction >= 0.8:
            support("Detected dips follow the ephemeris", f"{int(ephemeris_match_count)} of {transit_count} dips align with the BLS period.", 16)
        elif ephemeris_match_fraction >= 0.65:
            support("Partial ephemeris agreement", f"{int(ephemeris_match_count)} of {transit_count} dips align with the BLS period.", 5)
            limit("Some off-period dips", "Several detected dips do not belong to the recovered period.", -6)
        elif ephemeris_match_fraction < 0.55:
            limit("Irregular transit timing", f"Only {int(ephemeris_match_count)} of {transit_count} dips align with the BLS period.", -34)
        else:
            limit("Weak timing agreement", f"Only {int(ephemeris_match_count)} of {transit_count} dips align with the BLS period.", -18)

    if (
        off_ephemeris_count is not None
        and off_ephemeris_fraction is not None
        and off_ephemeris_count >= 3
        and off_ephemeris_fraction >= 0.35
    ):
        limit("Many off-period dips", "The detector found too many transit-like dips away from the recovered ephemeris.", -24)

    if expected_transit_coverage is not None and transit_count >= 3 and expected_transit_coverage < 0.5:
        limit("Weak predicted-transit coverage", f"Only {expected_transit_coverage:.0%} of expected BLS events were matched.", -10)

    if timing_residual_ratio is not None and timing_residual_ratio > 1.0 and transit_count >= 3:
        limit("Large timing residuals", "Detected dip centers are not tightly clustered around the recovered ephemeris.", -10)

    if depth_scatter_ratio is not None and transit_count >= 4:
        if depth_scatter_ratio <= 0.35:
            support("Consistent transit depths", f"Depth scatter ratio is {depth_scatter_ratio:.2f}.", 7)
        elif depth_scatter_ratio > 0.8:
            limit("Inconsistent transit depths", f"Depth scatter ratio is {depth_scatter_ratio:.2f}.", -12)
        elif depth_scatter_ratio > 0.5:
            limit("Moderately inconsistent depths", f"Depth scatter ratio is {depth_scatter_ratio:.2f}.", -6)

    if odd_even_mismatch is not None and transit_count >= 4:
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
            support("Well-sampled events", f"Median transit has {median_transit_points:.0f} plotted points.", 4)
        elif median_transit_points < 4:
            limit("Sparse transit sampling", f"Median transit has only {median_transit_points:.0f} plotted points.", -6)

    danger_count = sum(1 for warning in warnings if warning.get("severity") == "danger")
    caution_count = sum(1 for warning in warnings if warning.get("severity") == "caution")
    if danger_count:
        score -= danger_count * 10
    if caution_count >= 3:
        score -= 6

    candidate_score = int(round(clamp(score, 0, 100)))
    strong_requirements_met = (
        transit_count >= 3
        and period is not None
        and period_method == "BLS"
        and detection_snr is not None
        and detection_snr >= 7
        and (period_sde is None or period_sde >= 5)
        and (ephemeris_match_fraction is None or ephemeris_match_fraction >= 0.75)
        and (off_ephemeris_fraction is None or off_ephemeris_fraction <= 0.3)
        and danger_count == 0
    )
    severe_timing_mismatch = (
        transit_count >= 3
        and period_method == "BLS"
        and ephemeris_match_fraction is not None
        and ephemeris_match_fraction < 0.55
        and off_ephemeris_count is not None
        and off_ephemeris_count >= 2
    )

    if transit_count == 0:
        has_unboxed_period_signal = (
            candidate_score >= 35
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
    elif candidate_score >= 75 and strong_requirements_met:
        status = "strong_candidate"
        title = "Strong planet-like transit candidate"
        short_label = "Strong candidate"
        summary = (
            "Repeated dips align with a stable period and pass the current signal-strength checks. "
            "This is a strong candidate, not a confirmed planet."
        )
        recommendation = "Use the phase-folded view, exports, and follow-up vetting before treating this as confirmed."
    elif candidate_score >= 45 and transit_count >= 2:
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

    return {
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
            "period": period,
            "period_method": period_method,
            "period_sde": period_sde,
            "detection_snr": detection_snr,
            "p_value": p_value,
            "depth_scatter_ratio": depth_scatter_ratio,
            "odd_even_depth_mismatch": odd_even_mismatch,
            "max_radius_ratio": max_radius_ratio,
            "median_transit_points": median_transit_points,
            "ephemeris_match_fraction": ephemeris_match_fraction,
            "ephemeris_match_count": ephemeris_match_count,
            "off_ephemeris_transit_count": off_ephemeris_count,
            "off_ephemeris_fraction": off_ephemeris_fraction,
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
    analysis_flux, segments = normalize_flux_by_segments(time, flux)
    detection = detect_transits(time, analysis_flux, options)
    time_reference = float(time[0])
    display_time = time - time_reference
    raw_low, raw_high = robust_flux_limits(analysis_flux, sigma=4.0)
    raw_clipped = np.clip(analysis_flux, raw_low, raw_high)

    base_smooth_width = int(max(25, min(251, len(analysis_flux) // 300)))
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
    diagnostics, warnings = build_candidate_diagnostics(display_transits, detection, time_reference)
    planet_assessment = build_planet_assessment(display_transits, detection, diagnostics, warnings)

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
        "flux_unit": "relative flux",
        "normalization": {
            "method": "per-observing-segment median",
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
        "planet_assessment": planet_assessment,
        "detection_snr": diagnostics["detection_snr"],
        "odd_even_depth_mismatch": diagnostics["odd_even_depth_mismatch"],
        "depth_scatter_ratio": diagnostics["depth_scatter_ratio"],
        **{**detection, "transits": display_transits},
    }
