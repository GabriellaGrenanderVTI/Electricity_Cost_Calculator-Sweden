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

import json
import numpy as np
import pandas as pd

import FileManagement as fm
import FilterSpace as fs
import PriceComponents as pc
import ProcessData as prd
import TariffLogic as tl



def calculatorInput(networkPrices_df: pd.DataFrame,
                       RElist: list,
                       loadProfile_df: pd.DataFrame,
                       scenario: str,
                       elspot_prices_by_area: dict,
                       re_bidding_areas: dict,
                       tariff_rules=None) -> tuple:
    """
    Calculate all price components for the electricity price analysis.

    Args:
        networkPrices_df: Network pricing information
        RElist: List of regional entities
        loadProfile_df: Load profile data
        scenario: Scenario name
        elspot_prices_by_area: Mapping from bidding area code to hourly
            electricity spot price DataFrame.
        re_bidding_areas: Mapping from RE identifier to bidding area code.
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
    spot_prices_df = pc.calculateElectricityPrice_8760(
        elspot_prices_by_area,
        RElist,
        re_bidding_areas,
        loadProfile_df
    )
    return taxesAndFixedFees_prices_df, kWCharge_prices_df, kWhCharge_prices_df, highLoadPower_prices_df, spot_prices_df



def runCalculations(effectCustomerType, studyArea, loadProfile, yearList):
    """Run full yearly calculations and write output CSV files.

    Args:
        effectCustomerType (int): Effect customer tariff type used when reading
            network prices.
        studyArea (pd.DataFrame): Study area table with at least
            ``DSO (short)``, ``DSO (long)``, and year-specific
            ``RE + subgroup (<year>)`` and bidding area columns.
        loadProfile (pd.DataFrame): Load profile input with 'Load (kWh)' column.
            Can be either 24 rows (hourly template) or 8760 rows (full-year hourly).
        yearList (list[int]): Years to evaluate.

    Side effects:
        Writes:
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
    totalCost_allYears_df = pd.DataFrame(columns = ['Year', 'Season', 	'Month' ,	'DSO (short)', 'RE', 'DSO (long)', 'Total Cost (DSO)', 'Fixed fees (DSO)', 'Power (DSO)', 'Highload power (DSO)',	'Energy (DSO)',	'Energy (Spot)'])

    with open('data/dsoTariffStructures.json') as f:
        TARIFF_RULES = json.load(f)

    for year in yearList:
        print(year)

        # List of REs in the modeling area
        RElist = fs.generateRElist(studyArea, year)
        re_bidding_areas = fs.build_re_bidding_area_map(studyArea, year)

        missing_res = sorted(set(RElist) - set(re_bidding_areas.keys()))
        if missing_res:
            raise ValueError(
                "Missing bidding area assignment in studyArea for RE: "
                + ", ".join(missing_res)
            )

        bidding_areas = sorted({re_bidding_areas[re] for re in RElist})

        # Read in datafames with pricing data
        networkPrices_df = fm.readEffectCustomerPrices_2025(effectCustomerType, year)
        elspot_prices_by_area = {
            area: fm.readElspotPrices(year, area)
            for area in bidding_areas
        }

        # Shape the load profile to be on 8760 hours
        loadProfile_reshape_df = prd.reshapeLoadProfile(loadProfile, year)
        loadProfile_df = loadProfile_reshape_df[['Day', 'Month', 'Year', 'Hour', 'Season', 'Load (kWh)']].copy()

        taxesAndFixedFees_prices_df, kWCharge_prices_df, kWhCharge_prices_df, highLoadPower_prices_df, spot_prices_df = calculatorInput(
            networkPrices_df, RElist, loadProfile_df, 'Load (kWh)', elspot_prices_by_area, re_bidding_areas,
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
            RE = studyArea.loc[studyArea['DSO (short)'] == DSO, f'RE + subgroup ({year})'].item()

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
            re = studyArea.loc[studyArea['DSO (short)'] == dso, f'RE + subgroup ({year})'].item()
            # Company name is taken from the long DSO name column
            company_name = studyArea.loc[studyArea['DSO (short)'] == dso, 'DSO (long)'].item()
            dso_to_re_company[dso] = (re, company_name)
        
        totalCost['RE'] = totalCost['DSO (short)'].map(lambda dso: dso_to_re_company[dso][0])
        totalCost['DSO (long)'] = totalCost['DSO (short)'].map(lambda dso: dso_to_re_company[dso][1])
        
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
        'DSO (long)', 'Load profile (kWh)', 'Total Cost (DSO)', 'Fixed fees (DSO)', 'Power (DSO)',
        'Highload power (DSO)', 'Energy (DSO)', 'Energy (Spot)', 
        'Tax and Fixed Fee (SEK/kWh)', 'kW Fee (SEK/kWh)',
        'kWh Fee (SEK/kWh)', 'Highload power (SEK/kWh)', 'Spot Price (SEK/kWh)',
        'Total Price (DSO)'
    ]
    totalCost_allYears_df = totalCost_allYears_df[column_order]

    totalCost_allYears_df.to_csv('output/totalCost_AllYears.csv')

def main():
    effectCustomerType = 2 # Possible 1, 2, 3
    studyArea = fm.readStudyAreas('Sheet1')
    loadProfile = fm.readLoadProfile('input/test-load.xlsx', 'Sheet1')
    yearList = [2024]

    runCalculations(effectCustomerType = effectCustomerType, 
                    studyArea = studyArea, 
                    loadProfile=loadProfile,
                    yearList = yearList)
      
if __name__ == "__main__":
    main()

