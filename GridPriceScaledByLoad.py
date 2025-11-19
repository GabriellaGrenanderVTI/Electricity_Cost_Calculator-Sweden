#%%
"""
Grid Price Scaled By Load Calculator

This module calculates electricity grid prices scaled by load profiles for different scenarios
and regional entities. It handles various components of electricity pricing including:
- Taxes and fixed fees
- Power (kW) charges
- Energy (kWh) charges
- Spot prices

The calculations are performed for different load profiles and scenarios across multiple years
and municipalities in Sweden.
"""

from pathlib import Path
from typing import Tuple, List

import argparse
import calendar
import logging
import numpy as np
import pandas as pd

import FileManagement as fm
import FilterSpace as fs
import ProcessData as prd
import TranslateAttributes as trAtt
import Transmogrifier as tm

# Attempt to import file management helper used in original notebook
try:
    import FileManagement as fm  # original alias used: fm
except Exception:
    fm = None
    logging.getLogger(__name__).warning("FileManagement module not found; fm functions will be unavailable.")


def daysInMonth(month: int) -> int:
    """
    Return the number of days in a given month.

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


def reshapeLoadProfile(loadProfile_df: pd.DataFrame, year: int, scenario_cols: list = None) -> pd.DataFrame:
    """
    Expand a 24-hour load profile to cover a full year (8760 hours) with timestamps.
    Handles multiple scenario columns simultaneously.
    
    Args:
        loadProfile_df (pd.DataFrame): DataFrame containing 24-hour load profiles
        year (int): Year to generate timestamps for
        scenario_cols (list): List of column names containing load values. 
                            If None, uses all columns except 'hours'
        
    Returns:
        pd.DataFrame: DataFrame with 8760 rows containing:
            - Timestamp: datetime index for each hour
            - Year: year number
            - Month: 1-12
            - Day: 1-31
            - Hour: 0-23
            - Season: 'Winter', 'Spring', 'Summer', 'Fall'
            - DayType: 'Weekday' or 'Weekend'
            - Load values for each scenario column
            
    Raises:
        ValueError: If loadProfile_df doesn't have exactly 24 rows
        KeyError: If any scenario_col is not found in loadProfile_df
    """
    # Validate input
    if len(loadProfile_df) != 24:
        raise ValueError(f"Load profile must have exactly 24 rows, got {len(loadProfile_df)}")
    
    # If no scenario columns specified, use all except 'hours'
    if scenario_cols is None:
        scenario_cols = [col for col in loadProfile_df.columns if col != 'hours']
    
    # Validate all scenario columns exist
    missing_cols = [col for col in scenario_cols if col not in loadProfile_df.columns]
    if missing_cols:
        raise KeyError(f"Columns not found in load profile: {missing_cols}")
    
    # Create timestamp range for the full year
    timestamps = pd.date_range(
        start=f'{year}-01-01',
        end=f'{year}-12-31 23:00:00',
        freq='H'
    )

    # Remove February 29th if it's a leap year
    if calendar.isleap(year):
        leap_day_mask = ~((timestamps.month == 2) & (timestamps.day == 29))
        timestamps = timestamps[leap_day_mask]
        
    # Verify we have exactly 8760 hours
    if len(timestamps) != 8760:
        raise ValueError(f"Expected 8760 hours, got {len(timestamps)} hours after timestamp generation")
    
    # Create base dataframe with timestamps
    df = pd.DataFrame({
        'Timestamp': timestamps,
        'Year': timestamps.year,
        'Month': timestamps.month,
        'Day': timestamps.day,
        'Hour': timestamps.hour,
        'DayOfWeek': timestamps.dayofweek  # Monday=0, Sunday=6
    })
    
    # Add weekday/weekend information
    df['DayType'] = df['DayOfWeek'].map(lambda x: 'Weekend' if x >= 5 else 'Weekday')
    
    # Add season based on month
    def get_season(month):
        if month in [12, 1, 2]:
            return 'Winter'
        elif month in [3, 4, 5]:
            return 'Spring'
        elif month in [6, 7, 8]:
            return 'Summer'
        else:  # 9, 10, 11
            return 'Fall'
    
    df['Season'] = df['Month'].map(get_season)
    
    # Tile each scenario column to fill the year
    for col in scenario_cols:
        load_values = loadProfile_df[col].to_numpy()
        tiled_values = np.tile(load_values, 365)
        df[col] = tiled_values
    
    return df


def isHighLoadMonth(month: int) -> bool:
    """
    Check if a given month is considered a high load month.

    High load months are typically November through March (11, 12, 1, 2, 3).

    Args:
        month (int): Month number (1-12)

    Returns:
        bool: True if high load month, False otherwise
    """
    highLoadMonths = [11, 12, 1, 2, 3] #TODO inte säker att dessa stämmer för alla elnätsföretag, men antar detta för nu
    if month in highLoadMonths:
        return True
    else:
        return False


def isHighLoadTime(df: pd.DataFrame, RE: str, month: int, day: int, hour: int) -> bool:
    """
    Determine if a specific hour is considered high load time for a given regional entity.

    Args:
        df (pd.DataFrame): DataFrame containing high load time definitions
        RE (str): Regional entity identifier
        month (int): Month number (1-12)
        day (int): Day of month
        hour (int): Hour of day (0-23)

    Returns:
        bool: True if the specified time is high load time, False otherwise
    """
    REdata = df.iloc[df.index.get_loc(RE),:]
    
    if (((REdata['StartHour'] == 0) & (REdata['EndHour'] == 0)) | (REdata['StartHour'] == '-')):
        return False
    elif (REdata['StartHour'] <= hour <= REdata['EndHour']) & (isHighLoadMonth(month)):
        return True
    else:
        return False


# 
def taxAndfixedFee_ScaledByLoad_Yearly(networkPrices_df, RE, loadProfile_df, scenario, taxesAndFixedFees_prices_df):
    """
    Calculate the taxes and fixed fees scaled by load for a specific regional entity.

    Args:
        networkPrices_df (pd.DataFrame): DataFrame containing network pricing information
        RE (str): Regional entity identifier
        loadProfile_df (pd.DataFrame): DataFrame containing load profile data
        scenario (str): Name of the scenario being analyzed
        taxesAndFixedFees_prices_df (pd.DataFrame): DataFrame to store calculated prices
    Returns:
        pd.DataFrame: Updated DataFrame with taxes and fixed fees prices
    """
    taxes = networkPrices_df.loc[RE]['Myndighetsavgifter Kr, exkl. moms']
    fixedFee = networkPrices_df.loc[RE]['Fast avgift Kr, exkl. moms']

    totalKWh = loadProfile_df[scenario].sum()

    taxesAndFixedFees_prices_df[RE] = (taxes + fixedFee) /totalKWh

    return taxesAndFixedFees_prices_df


# 
def kWCharge_ScaledByLoad_Monthly(networkPrices_df, RE, month, loadProfile_df, scenario, kWCharge_prices_df):
    """
    Calculate the kW charge scaled by load for a specific month and regional entity.

    Args:
        networkPrices_df (pd.DataFrame): DataFrame containing network pricing information
        RE (str): Regional entity identifier
        month (int): Month number (1-12)
        loadProfile_df (pd.DataFrame): DataFrame containing load profile data
        scenario (str): Name of the scenario being analyzed
        kWCharge_prices_df (pd.DataFrame): DataFrame to store calculated kW charge prices
        
    Returns:
        pd.DataFrame: Updated DataFrame with kW charge prices
    """
    # Find the monthly subscribed capacity
    monthlyLoad = loadProfile_df.loc[(loadProfile_df['Month'] == month), :]
    monthlyPeaks = monthlyLoad.nlargest(3, scenario) # the three largest load hours in month (not entirely correct, also depends on the company, this is modeled after https://www.seom.se/el/elnat/effektavgiften/)
    monthlySubCap = monthlyPeaks.loc[:,scenario].mean()

    costOfMonthlySubcap = monthlySubCap * networkPrices_df.loc[RE,'Abonnerad effekt kr/kW']
    kWCharge_prices_df.loc[(loadProfile_df['Month'] == month), RE] = costOfMonthlySubcap * monthlyLoad.loc[:,scenario] / (monthlyLoad.loc[:,scenario].dot(monthlyLoad.loc[:,scenario]))

    return kWCharge_prices_df


def kWhCharge_ScaledByLoad_Hourly(networkPrices_df, highload_df, RE, month, day, hour, loadProfile_df, kWhCharge_prices_df):
    """
    Calculate the kWh charge scaled by load for a specific hour and regional entity.

    Args:
        networkPrices_df (pd.DataFrame): DataFrame containing network pricing information
        highload_df (pd.DataFrame): DataFrame containing high load time definitions
        RE (str): Regional entity identifier
        month (int): Month number (1-12)
        day (int): Day of month
        hour (int): Hour of day (0-23)
        loadProfile_df (pd.DataFrame): DataFrame containing load profile data
        kWhCharge_prices_df (pd.DataFrame): DataFrame to store calculated kWh charge prices
        
    Returns:
        pd.DataFrame: Updated DataFrame with kWh charge prices
    """
    if (3 <= month <= 5) |( 9 <= month <= 11):
        season = "Vår/höst"
    elif 6 <= month <= 8:
        season = "Sommar"
    elif (month == 12) | (1 <= month <= 2):
        season = "Vinter"
    else:
        raise ValueError("This is not a valid month number")
    
    # TODO: Is this actually correct? Only highload at specific months?
    if isHighLoadTime(highload_df, RE, month, day, hour): #Höglasttid (true)
        last = 'hög'
    else: #Låglasttid (false)
        last = 'låg'
        
    kWhCharge_colName = season + ' ' + last + ' öre/kWh'
    kWhCharge = networkPrices_df.loc[RE][kWhCharge_colName] / 100 #return in kr/kWh and not öre/kWh

    hourlyLoad = loadProfile_df.loc[(loadProfile_df['Day'] == day) & (loadProfile_df['Month'] == month) & (loadProfile_df['Hour'] == hour), :]

    kWhCharge_prices_df.loc[hourlyLoad.index[0], RE] = kWhCharge
    return kWhCharge_prices_df


def calculateNetworkPrice_RElist(
    networkPrices_df: pd.DataFrame,
    highload_df: pd.DataFrame,
    RElist: list,
    loadProfile_df: pd.DataFrame,
    scenario: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Calculate network prices scaled by load for a list of regional entities.

    This function calculates three components of network pricing:
    1. Taxes and fixed fees (yearly basis)
    2. Power charges (monthly basis)
    3. Energy charges (hourly basis)

    Args:
        networkPrices_df: DataFrame containing network pricing information
        highload_df: DataFrame containing high load time periods
        RElist: List of regional entity identifiers
        loadProfile_df: DataFrame containing load profile data
        scenario: Name of the scenario being analyzed

    Returns:
        tuple: (taxes_df, power_charges_df, energy_charges_df)
            - taxes_df: DataFrame with taxes and fixed fees
            - power_charges_df: DataFrame with power charges
            - energy_charges_df: DataFrame with energy charges
    """    
    taxesAndFixedFees_prices_df = pd.DataFrame(data=loadProfile_df[['Day', 'Month', 'Year', 'Hour', 'Season']])
    kWCharge_prices_df = pd.DataFrame(data=loadProfile_df[['Day', 'Month', 'Year', 'Hour', 'Season']])
    kWhCharge_prices_df = pd.DataFrame(data=loadProfile_df[['Day', 'Month', 'Year', 'Hour', 'Season']])

    for RE in RElist:
        taxesAndFixedFees_prices_df = taxAndfixedFee_ScaledByLoad_Yearly(networkPrices_df, RE, loadProfile_df, scenario, taxesAndFixedFees_prices_df)
        for month in range(1, 13):
            kWCharge_prices_df = kWCharge_ScaledByLoad_Monthly(networkPrices_df, RE, month, loadProfile_df, scenario, kWCharge_prices_df)

            numDays = daysInMonth(month)
            for day in range(1, numDays + 1):
                for hour in range(0, 24):
                    kWhCharge_prices_df = kWhCharge_ScaledByLoad_Hourly(networkPrices_df, highload_df, RE, month, day, hour, loadProfile_df, kWhCharge_prices_df)

    return taxesAndFixedFees_prices_df, kWCharge_prices_df, kWhCharge_prices_df


def calculateElectricityPrice_8760(elspot_df: pd.DataFrame,
                                   RElist: list,
                                   bidding_area: str, 
                                   loadProfile_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate electricity spot prices for all hours in a year.

    Args:
        elspot_df (pd.DataFrame): DataFrame containing electricity spot prices
        bidding_area (str): Electricity bidding area code (e.g. 'SE3')
        loadProfile_df (pd.DataFrame): Load profile data with timestamp information

    Returns:
        pd.DataFrame: Hourly spot prices in SEK/kWh for each regional entity
    """
    spot_prices_df = pd.DataFrame(data=loadProfile_df[['Day', 'Month', 'Year', 'Hour', 'Season']])
    for RE in RElist:
        spot_prices_df[RE] = elspot_df[[f'Electricity price ({bidding_area}, SEK/MWh)']]/1000
    
    return spot_prices_df


def calculatorInput(networkPrices_df: pd.DataFrame,
                       highload_df: pd.DataFrame,
                       RElist: list,
                       loadProfile_df: pd.DataFrame,
                       scenario: str,
                       elspot_df: pd.DataFrame,
                       bidding_area: str) -> tuple:
    """
    Calculate all price components for the electricity price analysis.

    Args:
        networkPrices_df: Network pricing information
        highload_df: High load time definitions
        RElist: List of regional entities
        loadProfile_df: Load profile data
        scenario: Scenario name
        elspot_df: Electricity spot prices
        bidding_area: Bidding area code

    Returns:
        tuple: (taxes_df, kw_charges_df, kwh_charges_df, spot_prices_df)
            - All price components in SEK/kWh
    """
    taxesAndFixedFees_prices_df, kWCharge_prices_df, kWhCharge_prices_df = calculateNetworkPrice_RElist(networkPrices_df, highload_df, RElist, loadProfile_df, scenario)
    spot_prices_df = calculateElectricityPrice_8760(elspot_df, RElist, bidding_area, loadProfile_df)
    return taxesAndFixedFees_prices_df, kWCharge_prices_df, kWhCharge_prices_df, spot_prices_df

## TODO: Insert input argument information in docstring
def createScenarioLoadProfiles(loadProfile_raw_df, useExampleScenario) -> tuple[pd.DataFrame, list]:
    """
    Create different load profile scenarios for analysis.

    Generates three scenarios:
    1. Base load profile: Original profile from input data
    2. Flat load profile: Evenly distributed load across 24 hours
    3. Shaved load profile: Peak load reduced by 10% and redistributed

    Returns:
        tuple: (scenarios_df, scenario_list)
            - scenarios_df: DataFrame containing all load profile scenarios
            - scenario_list: List of scenario names
    """
    scenarioList = []

    ### Scenario 0: Base case
    loadProfile_scenarios_df = loadProfile_raw_df.copy()
    loadProfile_scenarios_df = loadProfile_scenarios_df.rename(columns={'Energy (kWh)': 'Base load profile'})
    
    scenarioList.append('Base load profile')

    if useExampleScenario:
        ### Scenario 1: Flat load profile
        loadProfile_scenarios_df['Flat load profile'] = loadProfile_scenarios_df['Base load profile'].sum()/24 #~221 kWh per hour
        
        scenarioList.append('Flat load profile')

        ### Scenario 2: Peak shaving 10%
        peak_hour = loadProfile_scenarios_df['Base load profile'].idxmax()
        peak_value = loadProfile_scenarios_df.loc[peak_hour, 'Base load profile']

        redistribute_amount = peak_value * 0.10
        loadProfile_scenarios_df['Shaved load profile'] = loadProfile_scenarios_df['Base load profile']
        loadProfile_scenarios_df.loc[peak_hour, 'Shaved load profile'] = peak_value * 0.90

        # Determine adjacent hours
        before_hour = (peak_hour - 1) % 24
        after_hour = (peak_hour + 1) % 24

        # Distribute the 10% amount to adjacent hours (split equally)
        loadProfile_scenarios_df.loc[before_hour, 'Shaved load profile'] += redistribute_amount / 2
        loadProfile_scenarios_df.loc[after_hour, 'Shaved load profile'] += redistribute_amount / 2

        scenarioList.append('Shaved load profile')

    return loadProfile_scenarios_df, scenarioList


def main(loadProfile_path: Path = None, effectCustomerType: int = 2, biddingArea: str = 'SE3', modelingMunicipalities: list = None, yearList: list = None, useExampleScenario: bool = False):
    """Main entry point for running the transmogrifier calculations (was previously top-level notebook code)."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Read modeling areas using FileManagement if available
    modelingData = fm.readModelingAreas('Data') if fm else None
    modelingArea = fm.readModelingAreas('ModelingAreas') if fm else None

    # Prepare result containers
    taxesAndFixedFees_prices_seasonHourly_allYears_df = pd.DataFrame(columns=['Scenario', 'Year', 'Season', 'Hour', 'Municipality', 'Tax and Fixed Fee (SEK/kWh)'])
    kWCharge_prices_seasonHourly_allYears_df = pd.DataFrame(columns=['Scenario', 'Year', 'Season', 'Hour', 'Municipality', 'kW Fee (SEK/kWh)'])
    kWhCharge_prices_seasonHourly_allYears_df = pd.DataFrame(columns=['Scenario', 'Year', 'Season', 'Hour', 'Municipality', 'kWh Fee (SEK/kWh)'])
    spot_prices_seasonHourly_allYears_df = pd.DataFrame(columns=['Scenario', 'Year', 'Season', 'Hour', 'Municipality', 'Spot Price (SEK/kWh)'])
    loadProfile_seasonHourly_allYears_df = pd.DataFrame(columns=['Scenario', 'Year', 'Season', 'Hour', 'Load profile (kWh)'])
    totalCost_allYears_df = pd.DataFrame(columns=['Scenario', 'Year', 'Season', 'Municipality', 'Total Cost (DSO)', 'Fixed fees (DSO)', 'Power (DSO)', 'Energy (DSO)', 'Energy (Spot)'])

    # Load load profile data
    loadProfile_raw_df = fm.readLoadProfile(loadProfile_path) if loadProfile_path else pd.DataFrame()

    # Create scenario specific load profiles
    loadProfile_scenarios_df, scenarioList = createScenarioLoadProfiles(loadProfile_raw_df, useExampleScenario)

    for year in yearList:
        logger.info("Processing year %s", year)

        municipalityData = fs.filterMunicipalitySubset(modelingData, modelingMunicipalities, year)

        # List of REs in the modeling area
        RElist = fs.generateRElist(municipalityData, year)

        # Read in datafames with pricing data
        highload_df = fm.readHighloadtime()
        networkPrices_df = fm.readEffectCustomerPrices(effectCustomerType, year) #These are in kW
        elspot_df = fm.readElspotPrices(year, biddingArea) #SEK/kWh

        # Shape the load profile to be on 8760 hours
        loadProfile_reshape_df = reshapeLoadProfile(loadProfile_scenarios_df, year)
        for scenario in scenarioList:
            print(scenario)
            # Use scenario specific load profile
            loadProfile_df = loadProfile_reshape_df[['Day', 'Month', 'Year', 'Hour', 'Season', scenario]].copy()

            taxesAndFixedFees_prices_df, kWCharge_prices_df, kWhCharge_prices_df, spot_prices_df = calculatorInput(networkPrices_df, highload_df, RElist, loadProfile_df, scenario, elspot_df, biddingArea)

            # Clean up
            data_taxesAndFixedFees_prices_df = prd.processData(taxesAndFixedFees_prices_df)
            data_kWCharge_prices_df = prd.processData(kWCharge_prices_df)
            data_kWhCharge_prices_df = prd.processData(kWhCharge_prices_df)
            data_spot_prices_df  = prd.processData(spot_prices_df)

            # SEASON HOURLY (MEAN OVER ALL HOURS IN THE SEASON)
            taxesAndFixedFees_prices_seasonHourly_df = tm.seasonHourTrans(data_taxesAndFixedFees_prices_df, RElist, 'average')
            kWCharge_prices_seasonHourly_df = tm.seasonHourTrans(data_kWCharge_prices_df, RElist, 'average')
            kWhCharge_prices_seasonHourly_df = tm.seasonHourTrans(data_kWhCharge_prices_df, RElist, 'average')
            spot_prices_seasonHourly_df = tm.seasonHourTrans(data_spot_prices_df, RElist, 'average')

            #Transfer back into municipalities
            for municipality in modelingMunicipalities:
                RE = municipalityData.loc[modelingData['kommunnamn'] == municipality, f'Subredovisningsenhet ({year})'].item()

                taxesAndFixedFees_prices_seasonHourly_df[municipality] = taxesAndFixedFees_prices_seasonHourly_df[RE]
                kWCharge_prices_seasonHourly_df[municipality] = kWCharge_prices_seasonHourly_df[RE]
                kWhCharge_prices_seasonHourly_df[municipality] = kWhCharge_prices_seasonHourly_df[RE]
                spot_prices_seasonHourly_df[municipality] = spot_prices_seasonHourly_df[RE]

            def postProcessing(df, scenario, year, valueName):
                df = df.drop(RElist, axis = 1)
                df['Scenario'] = scenario
                df['Year'] = year
                df = trAtt.translateSeason(df)

                return pd.melt(df,
                            ['Scenario', 'Year', 'Season', 'Hour'],
                            modelingMunicipalities,
                            var_name = 'Municipality',
                            value_name= valueName)

            taxesAndFixedFees_prices_seasonHourly_df = postProcessing(taxesAndFixedFees_prices_seasonHourly_df, scenario, year, 'Tax and Fixed Fee (SEK/kWh)')
            kWCharge_prices_seasonHourly_df = postProcessing(kWCharge_prices_seasonHourly_df, scenario, year, 'kW Fee (SEK/kWh)')
            kWhCharge_prices_seasonHourly_df = postProcessing(kWhCharge_prices_seasonHourly_df, scenario, year, 'kWh Fee (SEK/kWh)')
            spot_prices_seasonHourly_df = postProcessing(spot_prices_seasonHourly_df, scenario, year, 'Spot Price (SEK/kWh)')
            
            # Concat the prices to one dataframe for visualization
            taxesAndFixedFees_prices_seasonHourly_allYears_df = pd.concat([taxesAndFixedFees_prices_seasonHourly_allYears_df, taxesAndFixedFees_prices_seasonHourly_df], axis = 0, ignore_index = True)
            kWCharge_prices_seasonHourly_allYears_df = pd.concat([kWCharge_prices_seasonHourly_allYears_df, kWCharge_prices_seasonHourly_df], axis = 0, ignore_index = True)
            kWhCharge_prices_seasonHourly_allYears_df = pd.concat([kWhCharge_prices_seasonHourly_allYears_df, kWhCharge_prices_seasonHourly_df], axis = 0, ignore_index = True)
            spot_prices_seasonHourly_allYears_df = pd.concat([spot_prices_seasonHourly_allYears_df, spot_prices_seasonHourly_df], axis = 0, ignore_index = True)

            # Save load profile for visualisation later
            loadProfile_vis_df = loadProfile_df.head(24).copy()
            loadProfile_vis_df['Scenario'] = scenario
            loadProfile_vis_df = loadProfile_vis_df[['Scenario', 'Year', 'Season', 'Hour', scenario]].rename(columns={scenario: 'Load profile (kWh)'})
            loadProfile_seasonHourly_allYears_df = pd.concat([loadProfile_seasonHourly_allYears_df, loadProfile_vis_df], axis = 0, ignore_index = True)

            loadProfile_864_df = np.tile(loadProfile_vis_df, [36,1])
            loadProfile_864_df = pd.DataFrame(data = loadProfile_864_df, columns = ['Scenario', 'Year', 'Season', 'Hour', 'Load profile (kWh)'])
            loadProfile_864_df['Season'] = taxesAndFixedFees_prices_seasonHourly_df['Season']
            loadProfile_864_df['Municipality'] = taxesAndFixedFees_prices_seasonHourly_df['Municipality']
        
            # Calculate and save total cost for visualisation later
            totalCost = pd.DataFrame(data=loadProfile_864_df[['Scenario', 'Municipality', 'Year', 'Season', 'Hour']])
            totalCost['Total Price (DSO)'] = taxesAndFixedFees_prices_seasonHourly_df['Tax and Fixed Fee (SEK/kWh)'] + kWCharge_prices_seasonHourly_df['kW Fee (SEK/kWh)'] + kWhCharge_prices_seasonHourly_df['kWh Fee (SEK/kWh)']
            totalCost['Total Cost (DSO)'] = totalCost['Total Price (DSO)'] * loadProfile_864_df['Load profile (kWh)']
            totalCost['Fixed fees (DSO)'] = taxesAndFixedFees_prices_seasonHourly_df['Tax and Fixed Fee (SEK/kWh)'] * loadProfile_864_df['Load profile (kWh)']
            totalCost['Power (DSO)'] = kWCharge_prices_seasonHourly_df['kW Fee (SEK/kWh)'] * loadProfile_864_df['Load profile (kWh)']
            totalCost['Energy (DSO)'] = kWhCharge_prices_seasonHourly_df['kWh Fee (SEK/kWh)'] * loadProfile_864_df['Load profile (kWh)']
            totalCost['Energy (Spot)'] = spot_prices_seasonHourly_df['Spot Price (SEK/kWh)'] * loadProfile_864_df['Load profile (kWh)']

            totalCost = totalCost.groupby(['Scenario', 'Year', 'Season', 'Municipality'])[['Total Cost (DSO)', 'Fixed fees (DSO)', 'Power (DSO)', 'Energy (DSO)', 'Energy (Spot)']].sum().reset_index()
            totalCost_allYears_df = pd.concat([totalCost_allYears_df, totalCost], axis = 0, ignore_index = True)

    out_dir = Path.cwd()
    loadProfile_seasonHourly_allYears_df.to_csv(out_dir / 'loadProfileAllYears.csv', index=False)
    totalCost_allYears_df.to_csv(out_dir / 'totalCostAllYears.csv', index=False)
    logger.info("Wrote loadProfileAllYears.csv and totalCostAllYears.csv to %s", out_dir)


if __name__ == "__main__":
    EFFECT_CUSTOMER_TYPE = 2    # Possible 1, 2, 3
    BIDDING_AREA = 'SE3'        # Possible: SE1, SE2, SE3, SE4

    MODELING_MUNICIPALITIES = [
        'Skövde', 'Götene', 'Skara', 'Falköping',
        'Tidaholm', 'Hjo', 'Tibro', 'Töreboda', 'Mariestad'
    ]
    YEAR_LIST = [2019]#, 2020, 2021, 2022, 2023]

    LOADPROFILE_PATH = 'data\EV-bus-charging-needs-Arsalan.xlsx'

    main(loadProfile_path=LOADPROFILE_PATH, 
         effectCustomerType=EFFECT_CUSTOMER_TYPE, 
         biddingArea=BIDDING_AREA,
         modelingMunicipalities=MODELING_MUNICIPALITIES,
         yearList=YEAR_LIST
         )
    
            
