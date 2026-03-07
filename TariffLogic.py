"""Tariff and peak-calculation helpers for Transmogrifier.

This module contains pure helper functions used by pricing calculations.
Functions are deterministic and operate on provided inputs only.
"""

import numpy as np


def daysInMonth(month: int) -> int:
    """Return the number of days in a given month.

    Args:
        month (int): Month number (1-12)

    Returns:
        int: Number of days in the month

    Raises:
        ValueError: If month number is not between 1 and 12
    """
    days31 = [1, 3, 5, 7, 8, 10, 12]
    days30 = [4, 6, 9, 11]
    days28 = [2]

    if month in days31:
        return 31
    elif month in days30:
        return 30
    elif month in days28:
        return 28
    else:
        raise ValueError("This is not a valid month number")


def getAnnualPeak(loadProfile_df, scenario):
    """Return the annual peak (maximum) value for a scenario.

    Args:
        loadProfile_df (pd.DataFrame): Yearly load profile with a column named by ``scenario``.
        scenario (str): Column name containing the load series.

    Returns:
        float: Maximum hourly load observed over the year for the scenario.
    """
    return loadProfile_df[scenario].max()


def getMonthlyPeak(loadProfile_df, scenario, month):
    """Return the peak (maximum) hourly load for a given month.

    Note: historically this used the mean of the three largest peaks. The current
    implementation returns the single maximum value for the month.

    Args:
        loadProfile_df (pd.DataFrame): Yearly load profile with ``Month`` and
            scenario columns.
        scenario (str): Column name containing the load series.
        month (int): Month number (1-12) to filter on.

    Returns:
        float: Maximum hourly load for the specified month.
    """
    monthlyLoad = loadProfile_df.loc[(loadProfile_df['Month'] == month), :]
    return monthlyLoad.loc[:, scenario].max()


def compute_window_peak(loadProfile_df, scenario, start_hour, end_hour, months=None):
    """Compute the peak load within a specific time window and optional month restriction.

    Args:
        loadProfile_df (pd.DataFrame): Yearly load profile with ``Month``, ``Hour`` and scenario columns.
        scenario (str): Column name containing the load series.
        start_hour (int): Starting hour of the window (inclusive).
        end_hour (int): Ending hour of the window (inclusive).
        months (list[int], optional): List of month numbers (1-12) to restrict  to.
            If None, all months are included.

    Returns:
        float: Maximum hourly load within the specified time window and months, or 0 if no data matches.
    """
    # Filter by time window
    hour_mask = loadProfile_df['Hour'].between(start_hour, end_hour)
    
    # Filter by months if specified
    if months is not None:
        month_mask = loadProfile_df['Month'].isin(months)
        combined_mask = hour_mask & month_mask
    else:
        combined_mask = hour_mask
    
    if combined_mask.any():
        return loadProfile_df.loc[combined_mask, scenario].max()
    else:
        return 0.0


def get_highload_months(tariff_rules, RE):
    """Return configured high-load months for an RE from tariff rules.

    Args:
        tariff_rules (dict): Parsed tariff rules from JSON where each RE key may
            contain a ``highload_power`` object.
        RE (str): Regional entity identifier to query.

    Returns:
        list[int]: Month numbers when high-load applies for the RE, or an empty
            list if not configured or not applicable.
    """
    if not (tariff_rules and RE in tariff_rules):
        return []
    hl_config = tariff_rules[RE].get('highload_power', {})
    if not hl_config.get('applies', False):
        return []
    return hl_config.get('months', [])


def compute_highload_peak_window(loadProfile_df, scenario, tariff_rules, RE, month):
    """Compute the high-load peak inside a configured time window for a month.

    This implements the ``window_peak`` method: restrict the hourly series to
    the tariff's time window for the RE and return the maximum value in that
    window for the given month.

    Args:
        loadProfile_df (pd.DataFrame): Yearly load profile with ``Month``,
            ``Hour`` and scenario columns.
        scenario (str): Column name with hourly load values.
        tariff_rules (dict): Tariff rules holding the time window under
            ``highload_power.time_window``.
        RE (str): Regional entity identifier.
        month (int): Month number to evaluate.

    Returns:
        float: Maximum load within the configured window for the month, or 0
        if no hours match.
    """
    hl_config = tariff_rules[RE].get('highload_power', {})
    time_window = hl_config.get('time_window', {})
    start_hour = time_window.get('start_hour', 0)
    end_hour = time_window.get('end_hour', 23)

    mask = (loadProfile_df['Month'] == month) & (loadProfile_df['Hour'].between(start_hour, end_hour))
    if mask.any():
        return loadProfile_df.loc[mask, scenario].max()
    return 0


def compute_highload_peak_monthly_avg(loadProfile_df, scenario, tariff_rules, RE):
    """Compute the average of monthly peaks across configured high-load months.

    Implements the ``monthly_peak`` calculation: for each high-load month the
    function takes the maximum value inside the configured time window and
    returns the arithmetic mean across months.

    Args:
        loadProfile_df (pd.DataFrame): Yearly load profile with ``Month``,
            ``Hour`` and scenario columns.
        scenario (str): Column name with hourly load values.
        tariff_rules (dict): Tariff rules containing ``highload_power.months``
            and ``time_window``.
        RE (str): Regional entity identifier.

    Returns:
        float: Mean of the monthly peaks for configured months, or 0 if none.
    """
    hl_config = tariff_rules[RE].get('highload_power', {})
    months = hl_config.get('months', [])
    time_window = hl_config.get('time_window', {})
    start_hour = time_window.get('start_hour', 0)
    end_hour = time_window.get('end_hour', 23)

    peaks = []
    for month in months:
        mask = (loadProfile_df['Month'] == month) & (loadProfile_df['Hour'].between(start_hour, end_hour))
        if mask.any():
            peaks.append(loadProfile_df.loc[mask, scenario].max())
    return np.mean(peaks) if peaks else 0


def compute_avg_of_n_peaks_monthly(loadProfile_df, scenario, month, n=3):
    """Compute the average of the n highest hourly peaks in a month.

    This function finds the three (or n) highest hourly load values in a
    specific month and returns their arithmetic mean.

    Args:
        loadProfile_df (pd.DataFrame): Yearly load profile with ``Month``
            and scenario columns.
        scenario (str): Column name with hourly load values.
        month (int): Month number to evaluate.
        n (int): Number of peaks to average (default=3).

    Returns:
        float: Average of the n highest hourly peaks for the month, or 0 if
        insufficient data.
    """
    mask = loadProfile_df['Month'] == month
    if not mask.any():
        return 0
    monthly_values = loadProfile_df.loc[mask, scenario].values
    if len(monthly_values) < n:
        return np.mean(monthly_values) if len(monthly_values) > 0 else 0
    top_n = sorted(monthly_values, reverse=True)[:n]
    return np.mean(top_n)


def compute_avg_of_n_peaks_in_window(loadProfile_df, scenario, tariff_rules, RE, month, n=3):
    """Compute the average of the n highest peaks within a time window for a month.

    This function finds the n highest hourly load values within a configured
    time window for a given month and returns their arithmetic mean.

    Args:
        loadProfile_df (pd.DataFrame): Yearly load profile with ``Month``,
            ``Hour`` and scenario columns.
        scenario (str): Column name with hourly load values.
        tariff_rules (dict): Tariff rules holding the time window.
        RE (str): Regional entity identifier.
        month (int): Month number to evaluate.
        n (int): Number of peaks to average (default=3).

    Returns:
        float: Average of the n highest hourly peaks within the window for
        the month, or 0 if insufficient data.
    """
    hl_config = tariff_rules[RE].get('highload_power', {})
    time_window = hl_config.get('time_window', {})
    start_hour = time_window.get('start_hour', 0)
    end_hour = time_window.get('end_hour', 23)

    mask = (loadProfile_df['Month'] == month) & (loadProfile_df['Hour'].between(start_hour, end_hour))
    if not mask.any():
        return 0
    window_values = loadProfile_df.loc[mask, scenario].values
    if len(window_values) < n:
        return np.mean(window_values) if len(window_values) > 0 else 0
    top_n = sorted(window_values, reverse=True)[:n]
    return np.mean(top_n)


def is_highload_hour_from_tariff(tariff_rules, RE, month, hour):
    """Return True if the specified month/hour is configured as high-load.

    Args:
        tariff_rules (dict): Tariff configuration parsed from JSON.
        RE (str): Regional entity identifier.
        month (int): Month number.
        hour (int): Hour of day (0-23).

    Returns:
        bool: True when the hour falls inside the configured high-load months
            and time window for the RE; False otherwise.

    Notes:
        - ``highload_power.kWh_period_applies`` (if provided) controls whether the
          high-load *period definition* is active for classification.
        - If ``kWh_period_applies`` is omitted, the function falls back to
          ``highload_power.applies`` for backward compatibility.
        - ``highload_power.kWh_period_window`` (if provided) defines the time window
          for energy pricing classification, separate from the power tariff window.
          Falls back to ``time_window`` if not provided.
    """
    if not (tariff_rules and RE in tariff_rules):
        return False
    hl_config = tariff_rules[RE].get('highload_power', {})
    kWh_period_applies = hl_config.get('kWh_period_applies', hl_config.get('applies', False))
    if not kWh_period_applies:
        return False
    months = hl_config.get('months', [])
    # Use kWh_period_window if provided, otherwise fall back to time_window
    time_window = hl_config.get('kWh_period_window', hl_config.get('time_window', {}))
    start_hour = time_window.get('start_hour', 0)
    end_hour = time_window.get('end_hour', 23)
    return month in months and start_hour <= hour <= end_hour


def compute_avg_of_n_highload_monthly_peaks_in_window(loadProfile_df, scenario, tariff_rules, RE, n=2):
    """Compute the average of the n highest monthly peaks within high-load time window.

    This function calculates the peak within the high-load time window for each
    high-load month, then returns the average of the n highest of these monthly peaks.

    Args:
        loadProfile_df (pd.DataFrame): Yearly load profile with ``Month``,
            ``Hour`` and scenario columns.
        scenario (str): Column name with hourly load values.
        tariff_rules (dict): Tariff rules containing ``highload_power.months``
            and ``time_window``.
        RE (str): Regional entity identifier.
        n (int): Number of monthly peaks to average (default=2).

    Returns:
        float: Average of the n highest monthly peaks within the high-load
        window across all high-load months, or 0 if insufficient data.
    """
    hl_config = tariff_rules[RE].get('highload_power', {})
    months = hl_config.get('months', [])
    time_window = hl_config.get('time_window', {})
    start_hour = time_window.get('start_hour', 0)
    end_hour = time_window.get('end_hour', 23)

    monthly_peaks = []
    for month in months:
        mask = (loadProfile_df['Month'] == month) & (loadProfile_df['Hour'].between(start_hour, end_hour))
        if mask.any():
            peak = loadProfile_df.loc[mask, scenario].max()
            monthly_peaks.append(peak)

    if len(monthly_peaks) < n:
        return np.mean(monthly_peaks) if monthly_peaks else 0

    top_n = sorted(monthly_peaks, reverse=True)[:n]
    return np.mean(top_n)
