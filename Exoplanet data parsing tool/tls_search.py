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
        keep = np.linspace(0, time_values.size - 1, max_points, dtype=int)
        time_values = time_values[keep]
        flux_values = flux_values[keep]
    return time_values.tolist(), flux_values.tolist()


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
        "use_threads": int(options.get("tls_threads", 1)),
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

    model_time, model_flux = compact_model(
        np.asarray(getattr(results, "model_lightcurve_time", []), dtype=float),
        np.asarray(getattr(results, "model_lightcurve_model", []), dtype=float),
    )
    folded_phase = np.asarray(getattr(results, "model_folded_phase", []), dtype=float)
    folded_model = np.asarray(getattr(results, "model_folded_model", []), dtype=float)
    folded_phase_days = (folded_phase - 0.5) * period if folded_phase.size else folded_phase
    model_folded_phase, model_folded_flux = compact_model(folded_phase_days, folded_model)

    transit_times = [time_origin + value for value in finite_list(getattr(results, "transit_times", []))]
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
        },
        "engine": tls_engine_version(),
        "parameters": kwargs,
    }
