"""Price component calculators for Transmogrifier.

This module contains the core pricing calculation functions for computing
electricity tariff components: taxes, fixed fees, power charges, energy charges,
and spot prices. All functions operate on provided inputs and return price DataFrames
indexed to hourly load profiles.
"""

import pandas as pd
import numpy as np
import TariffLogic as tl


def get_first_nonempty_value(df: pd.DataFrame, index_value, column_name):
    """Retrieve the first non-empty value for a column from rows matching an index value.

    When using df.loc[index_value], if multiple rows match that index value, pandas returns
    a DataFrame. This function iterates through those rows and returns the first non-empty
    (non-NaN, non-None, non-empty string) value found in the specified column.

    Args:
        df (pd.DataFrame): DataFrame to search in
        index_value: The index value to match (e.g., RE identifier)
        column_name (str): Column name to extract values from

    Returns:
        The first non-empty value found, or None if all matching rows are empty
        or if the column is missing.

    Raises:
        KeyError: If index_value is not present in the dataframe index.
    """
    result = df.loc[index_value]
    
    # If single row match, result is a Series
    if isinstance(result, pd.Series):
        value = result.get(column_name)
        if pd.notna(value) and value != '':
            return value
        return None
    
    # If multiple row matches, result is a DataFrame
    # Iterate through rows and return first non-empty value
    for idx, row in result.iterrows():
        value = row.get(column_name)
        if pd.notna(value) and value != '':
            return value
    
    return None


def taxAndfixedFee_ScaledByLoad_Yearly(networkPrices_df, RE, loadProfile_df, scenario, taxesAndFixedFees_prices_df):
    """Calculate the taxes and fixed fees distributed evenly across all 8760 hours.

    Stores (cost_per_hour / load) so that when multiplied by load later,
    each hour contributes the same absolute cost.

    Args:
        networkPrices_df (pd.DataFrame): DataFrame containing network pricing information
        RE (str): Regional entity identifier
        loadProfile_df (pd.DataFrame): DataFrame containing load profile data
        scenario (str): Name of the scenario being analyzed
        taxesAndFixedFees_prices_df (pd.DataFrame): DataFrame to store calculated prices

    Returns:
        pd.DataFrame: Updated DataFrame with taxes and fixed fees prices
    """
    taxes = get_first_nonempty_value(networkPrices_df, RE, 'Myndighetsavgifter Kr, exkl. moms')
    fixedFee = get_first_nonempty_value(networkPrices_df, RE, 'Fast avgift Kr, exkl. moms')

    # Distribute evenly: each hour gets (total / 8760) SEK
    # Store as SEK/kWh = (SEK_per_hour / kWh_per_hour) so multiplication by load gives SEK_per_hour
    hourly_cost = (taxes + fixedFee) / 8760
    taxesAndFixedFees_prices_df[RE] = hourly_cost / loadProfile_df[scenario]

    return taxesAndFixedFees_prices_df


def kWCharge_ScaledByLoad_Monthly(networkPrices_df, RE, month, loadProfile_df, scenario, kWCharge_prices_df, tariff_rules=None, annual_peaks=None, highload_peaks=None):
    """Calculate and allocate subscribed capacity (power) charges for a month.

    Supports multiple capacity definitions:
    - "sub_cap_annual_peak": Peak across the entire year, billed monthly as (annual_peak * price / 12)
    - "sub_cap_monthly_peak": Peak each month, billed monthly as (monthly_peak * price / 12)
    - "sub_cap_annual_avg_of_two_peaks": Average of two highest monthly peaks across the year
    - "sub_cap_avg_of_three_peaks": Average of three highest hourly peaks in the month
    - "sub_cap_avg_of_three_peaks_off_peak": Average of three highest peaks during off-peak hours
    - "sub_cap_window_peak": Peak within specified time window (from power_tariff.time_window or highload_power.time_window),
      optionally restricted to specific months (power_tariff.months). Charges are allocated proportionally only to
      hours within the applicable time window.
    - other values fall back to monthly peak

    Optional field `power_tariff.months` (list) can restrict which months the
    subscribed capacity charge applies; by default all months are included.
    
    Optional field `power_tariff.time_window` ({start_hour, end_hour}) can restrict
    which hours receive the charge allocation (currently only for sub_cap_window_peak).

    Note:
    This function handles subscribed capacity only. High-load power charges are
    computed separately.

    Parameters:
    -----------
    tariff_rules : dict
        Tariff structure from JSON with RE-specific capacity and high-load definitions.
    annual_peaks : dict
        Precomputed annual peaks keyed by RE.
    highload_peaks : dict
        Legacy argument kept for call compatibility; not used in this function.

    Returns:
        pd.DataFrame: ``kWCharge_prices_df`` with values populated for rows
        where ``Month`` equals the supplied ``month``. Values are the allocated
        monthly subscribed capacity cost distributed evenly in absolute SEK/hour
        across the month's hours (stored as SEK/kWh by dividing by hourly load).
    """
    monthlyLoad = loadProfile_df.loc[(loadProfile_df['Month'] == month), :]

    # --- Subscribed Capacity (Power) Charge ---
    # if the tariff explicitly does not apply, return zeros early
    if tariff_rules and RE in tariff_rules:
        if not tariff_rules[RE].get('power_tariff', {}).get('applies', True):
            kWCharge_prices_df.loc[(loadProfile_df['Month'] == month), RE] = 0
            return kWCharge_prices_df

    # Determine which capacity definition to use
    capacity_def = None
    if tariff_rules and RE in tariff_rules:
        capacity_def = tariff_rules[RE].get('power_tariff', {}).get('capacity_definition', 'sub_cap_monthly_peak')
    else:
        capacity_def = 'sub_cap_monthly_peak'  # Default fallback

    # Determine if the subscribed capacity applies this month
    power_months = None
    if tariff_rules and RE in tariff_rules:
        power_months = tariff_rules[RE].get('power_tariff', {}).get('months', None)
    if power_months is not None and month not in power_months:
        # no subscribed capacity charge in this month
        subCap = 0
    else:
        # Calculate subscribed capacity based on definition
        if capacity_def == 'sub_cap_annual_peak':
            # Use annual peak (pre-calculated and passed in)
            if annual_peaks and RE in annual_peaks:
                subCap = annual_peaks[RE]
            else:
                # Fallback: compute it from full year data
                subCap = loadProfile_df[scenario].max()
        elif capacity_def == 'sub_cap_annual_avg_of_two_peaks':
            # Average of two highest monthly peaks across the year
            all_months = loadProfile_df['Month'].unique()
            monthly_peaks = [loadProfile_df[loadProfile_df['Month'] == m][scenario].max() for m in all_months]
            top_two = sorted(monthly_peaks, reverse=True)[:2]
            subCap = np.mean(top_two) if len(top_two) >= 2 else np.mean(monthly_peaks)
        elif capacity_def == 'sub_cap_avg_of_three_peaks':
            # Average of three highest hourly peaks in this month
            subCap = tl.compute_avg_of_n_peaks_monthly(loadProfile_df, scenario, month, n=3)
        elif capacity_def == 'sub_cap_avg_of_three_peaks_off_peak':
            # Average of three highest peaks during off-peak hours (outside high-load time window)
            if tariff_rules and RE in tariff_rules:
                hl_config = tariff_rules[RE].get('highload_power', {})
                time_window = hl_config.get('time_window', {})
                start_hour = time_window.get('start_hour', 0)
                end_hour = time_window.get('end_hour', 23)
                # Off-peak is outside the high-load window
                mask = (loadProfile_df['Month'] == month) & ~(loadProfile_df['Hour'].between(start_hour, end_hour))
                if mask.any():
                    off_peak_values = loadProfile_df.loc[mask, scenario].values
                    top_three = sorted(off_peak_values, reverse=True)[:3]
                    subCap = np.mean(top_three) if len(top_three) >= 3 else np.mean(off_peak_values)
                else:
                    subCap = 0
            else:
                subCap = tl.compute_avg_of_n_peaks_monthly(loadProfile_df, scenario, month, n=3)
        elif capacity_def == 'sub_cap_window_peak':
            # Peak within specified time window, optionally restricted to specific months
            # Determine time window (check power_tariff first, then highload_power)
            time_window = None
            applicable_months = None
            if tariff_rules and RE in tariff_rules:
                pt_config = tariff_rules[RE].get('power_tariff', {})
                time_window = pt_config.get('time_window')
                # If power_tariff.months is specified, use only those months for capacity calculation
                applicable_months = pt_config.get('months')
                
                # If no time_window in power_tariff, check highload_power
                if not time_window:
                    hl_config = tariff_rules[RE].get('highload_power', {})
                    time_window = hl_config.get('time_window')
            
            if time_window:
                start_hour = time_window.get('start_hour', 0)
                end_hour = time_window.get('end_hour', 23)
                subCap = tl.compute_window_peak(loadProfile_df, scenario, start_hour, end_hour, months=applicable_months)
            else:
                # No window specified, fall back to monthly peak
                subCap = tl.getMonthlyPeak(loadProfile_df, scenario, month)
        else:
            # Default: monthly peak
            subCap = tl.getMonthlyPeak(loadProfile_df, scenario, month)

    # The price in the dataset is an annual charge (kr/kW per year).
    # Convert to a monthly charge per kW before allocating to the month's hours.
    annual_subscribed_price = get_first_nonempty_value(networkPrices_df, RE, 'Abonnerad effekt kr/kW')
    monthly_subscribed_price_per_kW = annual_subscribed_price / 12.0

    costOfMonthlySubcap = subCap * monthly_subscribed_price_per_kW
    
    # Determine which hours in this month should receive the charge
    # For sub_cap_window_peak, allocate only to hours within the applicable time window
    applicable_hour_mask = None
    if capacity_def == 'sub_cap_window_peak' and tariff_rules and RE in tariff_rules:
        # Check for time window definition
        pt_config = tariff_rules[RE].get('power_tariff', {})
        time_window = pt_config.get('time_window')
        if not time_window:
            hl_config = tariff_rules[RE].get('highload_power', {})
            time_window = hl_config.get('time_window')
        
        if time_window:
            start_hour = time_window.get('start_hour', 0)
            end_hour = time_window.get('end_hour', 23)
            # Create mask for hours within the window in this month
            applicable_hour_mask = (
                (loadProfile_df['Month'] == month) & 
                (loadProfile_df['Hour'].between(start_hour, end_hour))
            )
    
    if applicable_hour_mask is not None and applicable_hour_mask.any():
        # Allocate proportionally only to hours within the applicable window
        # Cost per hour = total_cost / sum_of_loads_in_window
        # Each hour gets: cost * (hour_load / sum_of_loads)
        total_load_in_window = loadProfile_df.loc[applicable_hour_mask, scenario].sum()
        if total_load_in_window > 0:
            # Allocate: for each hour, charge = (monthly_cost * hour_load / total_load_in_window)
            # Stored as SEK/kWh = (SEK / load) so multiplication by load gives SEK
            kWCharge_prices_df.loc[applicable_hour_mask, RE] = costOfMonthlySubcap / total_load_in_window
        # Hours outside the window remain 0 (default)
    else:
        # Default: distribute evenly across all hours in the month
        num_hours_in_month = tl.daysInMonth(month) * 24
        hourly_cost = costOfMonthlySubcap / num_hours_in_month
        kWCharge_prices_df.loc[(loadProfile_df['Month'] == month), RE] = hourly_cost / monthlyLoad.loc[:, scenario]

    return kWCharge_prices_df


def kWhCharge_ScaledByLoad_Hourly(networkPrices_df, tariff_rules, RE, month, day, hour, loadProfile_df, kWhCharge_prices_df):
    """Calculate the kWh charge scaled by load for a specific hour and regional entity.

    Args:
        networkPrices_df (pd.DataFrame): DataFrame containing network pricing information
        tariff_rules (dict): Tariff configuration parsed from JSON.
        RE (str): Regional entity identifier
        month (int): Month number (1-12)
        day (int): Day of month
        hour (int): Hour of day (0-23)
        loadProfile_df (pd.DataFrame): DataFrame containing load profile data
        kWhCharge_prices_df (pd.DataFrame): DataFrame to store calculated kWh charge prices

    Returns:
        pd.DataFrame: Updated DataFrame with kWh charge prices
    """
    if (3 <= month <= 5) | (9 <= month <= 11):
        season = "Vår/höst"
    elif 6 <= month <= 8:
        season = "Sommar"
    elif (month == 12) | (1 <= month <= 2):
        season = "Vinter"
    else:
        raise ValueError("This is not a valid month number")

    # Determine high/low-load period from tariff-configured months and hour window
    if tl.is_highload_hour_from_tariff(tariff_rules, RE, month, hour):  # Höglasttid (true)
        last = 'hög'
    else:  # Låglasttid (false)
        last = 'låg'

    kWhCharge_colName = season + ' ' + last + ' öre/kWh'
    kWhCharge = get_first_nonempty_value(networkPrices_df, RE, kWhCharge_colName) / 100  # return in kr/kWh and not öre/kWh

    hourlyLoad = loadProfile_df.loc[(loadProfile_df['Day'] == day) & (loadProfile_df['Month'] == month) & (loadProfile_df['Hour'] == hour), :]

    kWhCharge_prices_df.loc[hourlyLoad.index[0], RE] = kWhCharge
    return kWhCharge_prices_df


def calculateNetworkPrice_RElist(networkPrices_df, RElist, loadProfile_df, scenario, tariff_rules=None):
    """Compute network price components for a list of REs.

    The function returns four DataFrames aligned with ``loadProfile_df``'s
    hourly index:
      - taxesAndFixedFees_prices_df: taxes and fixed fees allocated per hour
      - kWCharge_prices_df: allocated subscribed-capacity (kW) charges
      - kWhCharge_prices_df: energy (kWh) charges per hour
      - highLoadPower_prices_df: high-load power charges allocated to hours

    Args:
        networkPrices_df (pd.DataFrame): Network pricing table indexed by RE.
        RElist (list): RE identifiers to compute for.
        loadProfile_df (pd.DataFrame): Hourly load profile used for allocation.
        scenario (str): Scenario/column name in ``loadProfile_df`` with load.
        tariff_rules (dict, optional): RE-specific tariff rules from JSON.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
            (taxes_df, kW_df, kWh_df, highload_df)
    """
    taxesAndFixedFees_prices_df = pd.DataFrame(data=loadProfile_df[['Day', 'Month', 'Year', 'Hour', 'Season']])
    kWCharge_prices_df = pd.DataFrame(data=loadProfile_df[['Day', 'Month', 'Year', 'Hour', 'Season']])
    kWhCharge_prices_df = pd.DataFrame(data=loadProfile_df[['Day', 'Month', 'Year', 'Hour', 'Season']])
    highLoadPower_prices_df = pd.DataFrame(data=loadProfile_df[['Day', 'Month', 'Year', 'Hour', 'Season']])
    # Initialize high-load columns for all REs with zeros so DSOs without high-load get 0s
    for _RE in RElist:
        highLoadPower_prices_df[_RE] = 0.0

    # Pre-compute annual peaks for each RE (needed if any use sub_cap_annual_peak definition)
    annual_peaks = {}
    highload_peaks = {}
    if tariff_rules:
        for RE in RElist:
            annual_peaks[RE] = tl.getAnnualPeak(loadProfile_df, scenario)
            # Pre-compute high-load peaks for annual calculation methods
            if RE in tariff_rules:
                hl_config = tariff_rules[RE].get('highload_power', {})
                if hl_config.get('applies', False):
                    calculation = hl_config.get('calculation', 'window_peak')
                    if calculation == 'high_load_annual_peak':
                        highload_peaks[RE] = tl.compute_highload_peak_monthly_avg(loadProfile_df, scenario, tariff_rules, RE)
                    elif calculation == 'high_load_monthly_peak_avg_of_two':
                        highload_peaks[RE] = tl.compute_avg_of_n_highload_monthly_peaks_in_window(loadProfile_df, scenario, tariff_rules, RE, n=2)
                    elif calculation == 'high_load_monthly_peak_avg_of_n':
                        n = hl_config.get('n_months', 2)
                        highload_peaks[RE] = tl.compute_avg_of_n_highload_monthly_peaks_in_window(loadProfile_df, scenario, tariff_rules, RE, n=n)
                    elif calculation == 'high_load_annual_peak_avg_of_two':
                        highload_peaks[RE] = tl.compute_avg_of_n_highload_monthly_peaks_in_window(loadProfile_df, scenario, tariff_rules, RE, n=2)
                    elif calculation == 'high_load_annual_peak_avg_of_n':
                        n = hl_config.get('n_months', 2)
                        highload_peaks[RE] = tl.compute_avg_of_n_highload_monthly_peaks_in_window(loadProfile_df, scenario, tariff_rules, RE, n=n)

    for RE in RElist:
        taxesAndFixedFees_prices_df = taxAndfixedFee_ScaledByLoad_Yearly(networkPrices_df, RE, loadProfile_df, scenario, taxesAndFixedFees_prices_df)
        for month in range(1, 13):
            kWCharge_prices_df = kWCharge_ScaledByLoad_Monthly(
                networkPrices_df, RE, month, loadProfile_df, scenario, kWCharge_prices_df, 
                tariff_rules=tariff_rules, 
                annual_peaks=annual_peaks,
                highload_peaks=highload_peaks
            )

            # --- Compute high-load power charge separately and populate highLoadPower_prices_df ---
            if tariff_rules and RE in tariff_rules and month in tl.get_highload_months(tariff_rules, RE):
                hl_config = tariff_rules[RE].get('highload_power', {})
                calculation = hl_config.get('calculation', 'window_peak')

                if calculation == 'high_load_annual_peak':
                    highload_peak = highload_peaks.get(RE, 0) if highload_peaks else 0
                elif calculation == 'high_load_annual_peak_avg_of_n':
                    # Average of n highest monthly peaks within high-load time window across all high-load months
                    highload_peak = highload_peaks.get(RE, 0) if highload_peaks else 0
                elif calculation == 'high_load_window_peak_avg_of_three':
                    # Average of three highest peaks within the high-load time window
                    highload_peak = tl.compute_avg_of_n_peaks_in_window(loadProfile_df, scenario, tariff_rules, RE, month, n=3)
                elif calculation == 'high_load_window_peak_avg_of_two':
                    # Average of two highest peaks within the high-load time window
                    highload_peak = tl.compute_avg_of_n_peaks_in_window(loadProfile_df, scenario, tariff_rules, RE, month, n=2)
                else:
                    # Default: window_peak
                    highload_peak = tl.compute_highload_peak_window(loadProfile_df, scenario, tariff_rules, RE, month)

                if highload_peak > 0 and 'Högbelasteffekt kr/kW, exkl. moms' in networkPrices_df.columns:
                    annual_highload_price = get_first_nonempty_value(networkPrices_df, RE, 'Högbelasteffekt kr/kW, exkl. moms')
                    if annual_highload_price is not None:
                        monthly_highload_price_per_kW = annual_highload_price / 12.0
                        costOfMonthlyHighload = highload_peak * monthly_highload_price_per_kW

                    is_hl = pd.Series(
                        [tl.is_highload_hour_from_tariff(tariff_rules, RE, row['Month'], row['Hour'])
                         for i, row in loadProfile_df.iterrows()],
                        index=loadProfile_df.index
                    )
                    month_mask = (loadProfile_df['Month'] == month)
                    hl_mask = is_hl & month_mask

                    if hl_mask.any():
                        denom = loadProfile_df.loc[hl_mask, scenario].dot(loadProfile_df.loc[hl_mask, scenario])
                        if denom > 0:
                            allocation = costOfMonthlyHighload * loadProfile_df.loc[hl_mask, scenario] / denom
                            highLoadPower_prices_df.loc[hl_mask, RE] = allocation

            numDays = tl.daysInMonth(month)
            for day in range(1, numDays + 1):
                for hour in range(0, 24):
                    kWhCharge_prices_df = kWhCharge_ScaledByLoad_Hourly(networkPrices_df, tariff_rules, RE, month, day, hour, loadProfile_df, kWhCharge_prices_df)

    return taxesAndFixedFees_prices_df, kWCharge_prices_df, kWhCharge_prices_df, highLoadPower_prices_df



def calculateElectricityPrice_8760(elspot_prices_by_area, RElist, re_bidding_areas, loadProfile_df):
    """Calculate electricity spot prices for all hours in a year.

    Args:
        elspot_prices_by_area (dict[str, pd.DataFrame]): Mapping from bidding
            area code to DataFrame containing electricity spot prices.
        RElist (list): RE identifiers to compute for.
        re_bidding_areas (dict[str, str]): Mapping from RE identifier to
            bidding area code.
        loadProfile_df (pd.DataFrame): Load profile data with timestamp information

    Returns:
        pd.DataFrame: Hourly spot prices in SEK/kWh for each regional entity
    """
    spot_prices_df = pd.DataFrame(data=loadProfile_df[['Day', 'Month', 'Year', 'Hour', 'Season']])

    for RE in RElist:
        if RE not in re_bidding_areas:
            raise KeyError(f"Missing bidding area mapping for RE '{RE}'")

        bidding_area = re_bidding_areas[RE]
        if bidding_area not in elspot_prices_by_area:
            raise KeyError(
                f"Missing elspot data for bidding area '{bidding_area}' (RE '{RE}')"
            )

        elspot_df = elspot_prices_by_area[bidding_area]
        price_column = f'Electricity price ({bidding_area}, SEK/MWh)'
        if price_column not in elspot_df.columns:
            raise KeyError(
                f"Column '{price_column}' not found in elspot data for area '{bidding_area}'"
            )

        price_values = (elspot_df[price_column].to_numpy() / 1000)
        if len(price_values) != len(loadProfile_df):
            raise ValueError(
                f"Spot price length mismatch for area '{bidding_area}': "
                f"{len(price_values)} prices vs {len(loadProfile_df)} load rows"
            )

        spot_prices_df[RE] = price_values

    return spot_prices_df
