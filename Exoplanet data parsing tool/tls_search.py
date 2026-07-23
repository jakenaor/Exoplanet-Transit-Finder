"""Thin, JSON-friendly integration around the reference TLS implementation."""

import math

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


def finite_number(value):
    if value is None:
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
    transit_phase = phase_days[in_transit]
    source_duration = float(np.max(transit_phase) - np.min(transit_phase))
    if source_duration <= 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)

    center = float((np.min(transit_phase) + np.max(transit_phase)) / 2.0)
    scale = target_duration / source_duration
    scaled_transit_phase = center + (transit_phase - center) * scale
    outside_target = np.abs(phase_days - center) > target_duration / 2.0
    keep_baseline = (~in_transit) & outside_target
    scaled_phase = np.r_[phase_days[keep_baseline], scaled_transit_phase]
    scaled_flux = np.r_[model_flux[keep_baseline], model_flux[in_transit]]
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


def run_tls_search(time, flux, options):
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
        duration = corrected_model_duration
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
    if observed_refinement is not None:
        observed_phase, observed_flux = rescale_folded_model_duration(
            payload_phase,
            payload_flux,
            observed_refinement["duration"],
            period,
        )
        observed_model_duration = duration_from_folded_model(
            observed_phase,
            observed_flux,
            period,
        )
        if observed_model_duration is not None and observed_model_duration > duration:
            duration = observed_model_duration
            payload_phase = observed_phase
            payload_flux = observed_flux
            duration_source = "TLS model widened to observed phase-folded ingress/egress"
    else:
        observed_model_duration = None
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
        "depth_fraction": None if bottom_flux is None else max(0.0, 1.0 - bottom_flux),
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
    }
