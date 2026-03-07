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

import calendar
import json
import numpy as np
import pandas as pd

import FileManagement as fm
import FilterSpace as fs
import PriceComponents as pc
import ProcessData as prd
import TariffLogic as tl


def reshapeLoadProfile(loadProfile_df: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Normalize load profile to full-year hourly shape (8760 rows) with timestamps.
    Handles both 24-hour template profiles and already-hourly 8760 profiles.
    
    Args:
        loadProfile_df (pd.DataFrame): DataFrame containing either:
            - 24 rows (hour template), or
            - 8760 rows (full-year hourly profile)
            Must have 'Load (kWh)' column
        year (int): Year to generate timestamps for
        
    Returns:
        pd.DataFrame: DataFrame with 8760 rows containing:
            - Timestamp: datetime index for each hour
            - Year: year number
            - Month: 1-12
            - Day: 1-31
            - Hour: 0-23
            - Season: 'Winter', 'Spring', 'Summer', 'Fall'
            - DayType: 'Weekday' or 'Weekend'
            - Load (kWh): Hourly load values
            
    Raises:
        ValueError: If loadProfile_df doesn't have exactly 24 or 8760 rows
        KeyError: If 'Load (kWh)' column is not found in loadProfile_df
    """
    profile_length = len(loadProfile_df)
    if profile_length not in (24, 8760):
        raise ValueError(
            f"Load profile must have exactly 24 or 8760 rows, got {profile_length}"
        )
    
    # Validate Load (kWh) column exists
    if 'Load (kWh)' not in loadProfile_df.columns:
        raise KeyError("Column 'Load (kWh)' not found in load profile")
    
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
        """Return season name for a month number.

        Args:
            month (int): Month number (1-12).

        Returns:
            str: One of 'Winter', 'Spring', 'Summer', 'Fall'.
        """
        if month in [12, 1, 2]:
            return 'Winter'
        elif month in [3, 4, 5]:
            return 'Spring'
        elif month in [6, 7, 8]:
            return 'Summer'
        else:  # 9, 10, 11
            return 'Fall'
    
    df['Season'] = df['Month'].map(get_season)
    
    # Fill load column depending on input granularity
    load_values = loadProfile_df['Load (kWh)'].to_numpy()
    
    if profile_length == 24:
        df['Load (kWh)'] = np.tile(load_values, 365)
    else:  # profile_length == 8760
        df['Load (kWh)'] = load_values
    
    return df


def calculatorInput(networkPrices_df: pd.DataFrame,
                       RElist: list,
                       loadProfile_df: pd.DataFrame,
                       scenario: str,
                       elspot_df: pd.DataFrame,
                       biddingArea: str,
                       tariff_rules=None) -> tuple:
    """
    Calculate all price components for the electricity price analysis.

    Args:
        networkPrices_df: Network pricing information
        RElist: List of regional entities
        loadProfile_df: Load profile data
        scenario: Scenario name
        elspot_df: Electricity spot prices
        biddingArea: Bidding area code
        tariff_rules: Tariff structure from JSON with RE-specific definitions (optional)

    Returns:
        tuple: (taxes_df, kw_charges_df, kwh_charges_df, highload_power_df, spot_prices_df)
            - All price component DataFrames in SEK/kWh aligned to the hourly
              index of ``loadProfile_df``. The fourth element contains any
              high-load power allocations when applicable.
    """
    taxesAndFixedFees_prices_df, kWCharge_prices_df, kWhCharge_prices_df, highLoadPower_prices_df = pc.calculateNetworkPrice_RElist(
        networkPrices_df, RElist, loadProfile_df, scenario, tariff_rules=tariff_rules
    )
    spot_prices_df = pc.calculateElectricityPrice_8760(elspot_df, RElist, biddingArea, loadProfile_df)
    return taxesAndFixedFees_prices_df, kWCharge_prices_df, kWhCharge_prices_df, highLoadPower_prices_df, spot_prices_df


def runCalculations(effectCustomerType, biddingArea, studyArea, loadProfile, yearList):
    """Run full yearly calculations and write output CSV files.

    Args:
        effectCustomerType (int): Effect customer tariff type used when reading
            network prices.
        biddingArea (str): Electricity bidding area code (for example 'SE3').
        studyArea (pd.DataFrame): Study area table with at least
            ``DSO (short)``, ``DSO (long)``, and year-specific
            ``Subredovisningsenhet (<year>)`` columns.
        loadProfile (pd.DataFrame): Load profile input with 'Load (kWh)' column.
            Can be either 24 rows (hourly template) or 8760 rows (full-year hourly).
        yearList (list[int]): Years to evaluate.

    Side effects:
        Writes:
        - ``output/loadProfileAllYears.csv``
        - ``output/totalCost_AllYears.csv``
    """
    
    studyDSOs = studyArea['DSO (short)'].unique().tolist()

    # Create dataframes to be populated in for-loop below for visualisation
    taxesAndFixedFees_prices_allYears_df = pd.DataFrame(columns = ['Year', 'Season', 'Month', 'Hour', 'DSO (short)', 'Tax and Fixed Fee (SEK/kWh)'])
    kWCharge_prices_allYears_df = pd.DataFrame(columns = ['Year', 'Season', 'Month', 'Hour', 'DSO (short)', 'kW Fee (SEK/kWh)'])
    kWhCharge_prices_allYears_df = pd.DataFrame(columns = ['Year', 'Season', 'Month', 'Hour', 'DSO (short)', 'kWh Fee (SEK/kWh)'])
    highLoadPower_prices_allYears_df = pd.DataFrame(columns = ['Year', 'Season', 'Month', 'Hour', 'DSO (short)', 'Highload power (SEK/kWh)'])
    spot_prices_allYears_df = pd.DataFrame(columns = ['Year', 'Season', 'Month', 'Hour', 'DSO (short)', 'Spot Price (SEK/kWh)'])
    loadProfile_allYears_df = pd.DataFrame(columns = ['Year', 'Season', 'Month', 'Hour', 'Load profile (kWh)'])
    totalCost_allYears_df = pd.DataFrame(columns = ['Year', 'Season', 	'Month' ,	'DSO (short)', 'RE', 'Företagsnamn', 'Total Cost (DSO)', 'Fixed fees (DSO)', 'Power (DSO)', 'Highload power (DSO)',	'Energy (DSO)',	'Energy (Spot)'])

    with open('data/dsoTariffStructures.json') as f:
        TARIFF_RULES = json.load(f)

    for year in yearList:
        print(year)

        # List of REs in the modeling area
        RElist = fs.generateRElist(studyArea, year)

        # Read in datafames with pricing data
        networkPrices_df = fm.readEffectCustomerPrices_2025(effectCustomerType, year)
        elspot_df = fm.readElspotPrices(year, biddingArea) #SEK/kWh

        # Shape the load profile to be on 8760 hours
        loadProfile_reshape_df = reshapeLoadProfile(loadProfile, year)
        loadProfile_df = loadProfile_reshape_df[['Day', 'Month', 'Year', 'Hour', 'Season', 'Load (kWh)']].copy()

        taxesAndFixedFees_prices_df, kWCharge_prices_df, kWhCharge_prices_df, highLoadPower_prices_df, spot_prices_df = calculatorInput(
            networkPrices_df, RElist, loadProfile_df, 'Load (kWh)', elspot_df, biddingArea, 
            tariff_rules=TARIFF_RULES
        )

        # Clean up
        taxesAndFixedFees_prices_df = prd.processData(taxesAndFixedFees_prices_df)
        kWCharge_prices_df = prd.processData(kWCharge_prices_df)
        kWhCharge_prices_df = prd.processData(kWhCharge_prices_df)
        highLoadPower_prices_df = prd.processData(highLoadPower_prices_df)
        spot_prices_df  = prd.processData(spot_prices_df)
        loadProfile_df = prd.processData(loadProfile_df)

        #Transfer back into DSOs
        for DSO in studyDSOs:
            RE = studyArea.loc[studyArea['DSO (short)'] == DSO, f'Subredovisningsenhet ({year})'].item()

            taxesAndFixedFees_prices_df[DSO] = taxesAndFixedFees_prices_df[RE]
            kWCharge_prices_df[DSO] = kWCharge_prices_df[RE]
            kWhCharge_prices_df[DSO] = kWhCharge_prices_df[RE]
            highLoadPower_prices_df[DSO] = highLoadPower_prices_df[RE]
            spot_prices_df[DSO] = spot_prices_df[RE]

        def postProcessing(df, year, valueName):
            """Melt hourly RE-indexed DataFrame into long format for DSOs.

            Args:
                df (pd.DataFrame): DataFrame indexed by RE with hourly columns.
                year (int): Year to insert.
                valueName (str): Column name for the melted values.

            Returns:
                pd.DataFrame: Melted DataFrame with columns
                    ['Year','Season','Month','Hour','DSO (short)', valueName].
            """
            df = df.drop(RElist, axis = 1)
            df['Year'] = year

            return pd.melt(df,
                        ['Year', 'Season', 'Month', 'Hour'],
                        studyDSOs,
                        var_name = 'DSO (short)',
                        value_name= valueName)

        taxesAndFixedFees_prices_df = postProcessing(taxesAndFixedFees_prices_df, year, 'Tax and Fixed Fee (SEK/kWh)')
        kWCharge_prices_df = postProcessing(kWCharge_prices_df, year, 'kW Fee (SEK/kWh)')
        kWhCharge_prices_df = postProcessing(kWhCharge_prices_df, year, 'kWh Fee (SEK/kWh)')
        highLoadPower_prices_df = postProcessing(highLoadPower_prices_df, year, 'Highload power (SEK/kWh)')
        spot_prices_df = postProcessing(spot_prices_df, year, 'Spot Price (SEK/kWh)')

        # Concat the prices to one dataframe 
        taxesAndFixedFees_prices_allYears_df = pd.concat([taxesAndFixedFees_prices_allYears_df, taxesAndFixedFees_prices_df], axis = 0, ignore_index = True)
        kWCharge_prices_allYears_df = pd.concat([kWCharge_prices_allYears_df, kWCharge_prices_df], axis = 0, ignore_index = True)
        kWhCharge_prices_allYears_df = pd.concat([kWhCharge_prices_allYears_df, kWhCharge_prices_df], axis = 0, ignore_index = True)
        highLoadPower_prices_allYears_df = pd.concat([highLoadPower_prices_allYears_df, highLoadPower_prices_df], axis = 0, ignore_index = True)
        spot_prices_allYears_df = pd.concat([spot_prices_allYears_df, spot_prices_df], axis = 0, ignore_index = True)

        # Calculate and save total cost
        totalCost = taxesAndFixedFees_prices_df[['DSO (short)', 'Year', 'Season', 'Month', 'Hour']].copy()
        hourly_load_values = loadProfile_df['Load (kWh)'].to_numpy()
        totalCost['Load profile (kWh)'] = np.repeat(hourly_load_values, len(studyDSOs))

        if len(totalCost) != len(totalCost['Load profile (kWh)']):
            raise ValueError(
                f"Load profile alignment mismatch in year {year}: "
                f"{len(totalCost)} price rows vs {len(totalCost['Load profile (kWh)'])} load rows"
            )
        
        # Add RE and company name columns by mapping from DSO short name
        dso_to_re_company = {}
        for dso in studyDSOs:
            re = studyArea.loc[studyArea['DSO (short)'] == dso, f'Subredovisningsenhet ({year})'].item()
            # Company name is taken from the long DSO name column
            company_name = studyArea.loc[studyArea['DSO (short)'] == dso, 'DSO (long)'].item()
            dso_to_re_company[dso] = (re, company_name)
        
        totalCost['RE'] = totalCost['DSO (short)'].map(lambda dso: dso_to_re_company[dso][0])
        totalCost['Företagsnamn'] = totalCost['DSO (short)'].map(lambda dso: dso_to_re_company[dso][1])
        
        # Directly assign price columns - all dataframes are aligned after postProcessing()
        totalCost['Tax and Fixed Fee (SEK/kWh)'] = taxesAndFixedFees_prices_df['Tax and Fixed Fee (SEK/kWh)'].values
        totalCost['kW Fee (SEK/kWh)'] = kWCharge_prices_df['kW Fee (SEK/kWh)'].values
        totalCost['kWh Fee (SEK/kWh)'] = kWhCharge_prices_df['kWh Fee (SEK/kWh)'].values
        totalCost['Highload power (SEK/kWh)'] = highLoadPower_prices_df['Highload power (SEK/kWh)'].values
        totalCost['Spot Price (SEK/kWh)'] = spot_prices_df['Spot Price (SEK/kWh)'].values

        totalCost['Total Price (DSO)'] = (
            totalCost['Tax and Fixed Fee (SEK/kWh)']
            + totalCost['kW Fee (SEK/kWh)']
            + totalCost['kWh Fee (SEK/kWh)']
            + totalCost['Highload power (SEK/kWh)']
        )
        totalCost['Total Cost (DSO)'] = totalCost['Total Price (DSO)'] * totalCost['Load profile (kWh)']
        totalCost['Fixed fees (DSO)'] = totalCost['Tax and Fixed Fee (SEK/kWh)'] * totalCost['Load profile (kWh)']
        totalCost['Power (DSO)'] = totalCost['kW Fee (SEK/kWh)'] * totalCost['Load profile (kWh)']
        totalCost['Highload power (DSO)'] = totalCost['Highload power (SEK/kWh)'] * totalCost['Load profile (kWh)']
        totalCost['Energy (DSO)'] = totalCost['kWh Fee (SEK/kWh)'] * totalCost['Load profile (kWh)']
        totalCost['Energy (Spot)'] = totalCost['Spot Price (SEK/kWh)'] * totalCost['Load profile (kWh)']
        totalCost_allYears_df = pd.concat([totalCost_allYears_df, totalCost], axis = 0, ignore_index = True)
            
    print(totalCost_allYears_df)

    # Reorder columns in totalCost output
    column_order = [
        'Year', 'Season', 'Month', 'Hour', 'DSO (short)', 'RE',
        'Företagsnamn', 'Load profile (kWh)', 'Total Cost (DSO)', 'Fixed fees (DSO)', 'Power (DSO)',
        'Highload power (DSO)', 'Energy (DSO)', 'Energy (Spot)', 
        'Tax and Fixed Fee (SEK/kWh)', 'kW Fee (SEK/kWh)',
        'kWh Fee (SEK/kWh)', 'Highload power (SEK/kWh)', 'Spot Price (SEK/kWh)',
        'Total Price (DSO)'
    ]
    totalCost_allYears_df = totalCost_allYears_df[column_order]

    totalCost_allYears_df.to_csv('output/totalCost_AllYears.csv')

def main():
    effectCustomerType = 2 # Possible 1, 2, 3
    biddingArea = 'SE3'
    studyArea = fm.readStudyAreas('Sheet1')
    loadProfile = fm.readLoadProfile('input/test-load.xlsx', 'Sheet1')
    yearList = [2024]

    runCalculations(effectCustomerType = effectCustomerType, 
                    biddingArea = biddingArea, 
                    studyArea = studyArea, 
                    loadProfile=loadProfile,
                    yearList = yearList)
      
if __name__ == "__main__":
    main()

