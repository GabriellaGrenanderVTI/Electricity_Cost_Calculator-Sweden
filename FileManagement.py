"""
File Management Module for Transmogrifier

This module handles all file I/O operations for the Transmogrifier project, including:
- Reading and writing data in CSV and Excel formats
- Loading electricity pricing data (elspot prices, network tariffs)
- Loading high-load time definitions
- Reading load profiles and modeling area data
- Handling network concession data

Data Sources:
- Vattenfall elspot prices (2019, 2023, 2024)
- ElspotNu data (2020, 2021, 2022)
- Network pricing and concession data
- High-load time definitions
- Load profile templates
- Regional/municipality modeling data
"""

from datetime import datetime
from pathlib import Path
import pandas as pd

def writeDfToCsv(df: pd.DataFrame, fileName: str) -> None:
    """
    Write a DataFrame to a CSV file in the output folder.
    
    Args:
        df (pd.DataFrame): DataFrame to write
        fileName (str): Name of the output file (e.g., 'results.csv')
        
    Returns:
        None
    """
    output_folder = Path('output')
    output_folder.mkdir(exist_ok=True)
    df.to_csv(output_folder / fileName, index=False)

def readDfFromCsv(filePath: str) -> pd.DataFrame:
    """
    Read a DataFrame from a CSV file.
    
    Args:
        filePath (str): Path to the CSV file
        
    Returns:
        pd.DataFrame: The loaded DataFrame
    """
    return pd.read_csv(filePath)

def writeLoadAndCostToExcel(loadProfile: pd.DataFrame, gridCost: pd.DataFrame, fileName: str) -> None:
    """
    Write load profile and grid cost data to separate Excel sheets with timestamped filename.
    
    Args:
        loadProfile (pd.DataFrame): Load profile data
        gridCost (pd.DataFrame): Grid cost data
        fileName (str): Base name for the output file (date will be appended)
        
    Returns:
        None
    """
    output_folder = Path('output')
    output_folder.mkdir(exist_ok=True)
    file_name = 'export_loadAndCost_' + fileName + '_' + datetime.today().strftime('%Y%m%d') + '.xlsx'
    
    with pd.ExcelWriter(output_folder / file_name) as writer:  
        loadProfile.to_excel(writer, sheet_name='loadProfile', index=False)
        gridCost.to_excel(writer, sheet_name='gridCost', index=False)

def readEffectCustomerPrices(effectCustomerType: int, year: int) -> pd.DataFrame:
    """
    Read effect customer (power customer) pricing data from network operators.
    
    Extracts network tariffs for a specific customer type and year from multi-level
    indexed Excel file. Customer types 1-3 represent different consumption levels.
    
    Args:
        effectCustomerType (int): Customer type (1, 2, or 3)
        year (int): Year to extract data for (2011-2023)
        
    Returns:
        pd.DataFrame: Network pricing data indexed by regional entity (RE), with columns
                     for different tariff components
    """
    df = pd.read_excel('data/energimarknadsinspektionen/effektkunder_2011-2023.xlsx', header=[0, 1, 2])
    
    # Keep the columns to combine with result later on
    df2 = df[['REnummer', 'Län', 'Org.nr', 'Nätföretag', 'REnamn']]
    df2 = df2.droplevel([1,2], axis=1)
    
    # Find the columns that contain information about desired year
    df = df.iloc[:, df.columns.get_level_values(2) == year]
    df = df.droplevel([2], axis=1)
    
    # Find the columnd that contain information about desired customer type (3 kinds)
    df = df.iloc[:, df.columns.get_level_values(0).str.contains('NT9' + str(effectCustomerType))]
    df = df.droplevel([0], axis=1)
    colNames = list(df.columns.values)
    
    # Join the "index columns" and the desired data columns
    df = pd.concat([df2, df], axis = 1, join = 'inner')

    # Remove rows that do not contain any data and reindex
    df.dropna(axis = 0, subset = colNames , how = 'all', inplace = True)
    df = df.reset_index()
    
    # Create unique identifier for the networkconcession
    col = df['REnummer'].fillna('') + df['REnamn'].fillna('')
    df.insert(5, 'RE', col)
    df = df.set_index('RE')    
    df = df.drop(columns = ['Län', 'index'])
    return df

def readElspotPrices(year: int, biddingArea: str) -> pd.DataFrame:
    """
    Read electricity spot prices for a given year and bidding area.
    
    Routes to appropriate data source based on year:
    - 2019-2024: Vattenfall source
    
    Args:
        year (int): Year to load (2019-2024)
        biddingArea (str): Bidding area code (e.g., 'SE1', 'SE2', 'SE3', 'SE4')
        
    Returns:
        pd.DataFrame: Hourly spot prices in SEK/MWh with 8760 rows (full year)
        
    Raises:
        ValueError: If year is not in supported range (2019-2024)
    """
    if year in [2019, 2020, 2021, 2022, 2023, 2024]:
        return readElspotPrices_Vattenfall(year, biddingArea)
    # elif year in [2020, 2021, 2022]:
    #     return readElspotPrices_ElspotNu(year, biddingArea)
    else:
        raise ValueError(f"Year {year} is not supported. Valid years: 2019-2024")

def readElspotPrices_ElspotNu(year: int, biddingArea: str) -> pd.DataFrame:
    """
    Read ElspotNu electricity spot prices (2020-2022).
    
    Args:
        year (int): Year (2020, 2021, or 2022)
        biddingArea (str): Bidding area code (SE1, SE2, SE3, SE4)
        
    Returns:
        pd.DataFrame: DataFrame with electricity prices already in SEK/MWh
    """
    df = pd.read_excel(f'data/elspot_prices/elspot-prices_{year}_hourly_sek_8760.xlsx')
    df.rename(columns={biddingArea: f'Electricity price ({biddingArea}, SEK/MWh)'}, inplace=True)
    df = df[[f'Electricity price ({biddingArea}, SEK/MWh)']]
    return df

def readElspotPrices_Vattenfall(year: int, biddingArea: str) -> pd.DataFrame:
    """
    Read Vattenfall electricity spot prices (2019-2024).
    
    Reads base file and 52 weekly data files, handles DST transitions and missing hours.
    Prices are converted from öre/kWh to SEK/MWh (multiply by 10).
    
    Args:
        year (int): Year (2019-2024)
        biddingArea (str): Bidding area code (SE1, SE2, SE3, SE4)
        
    Returns:
        pd.DataFrame: DataFrame with 8760 hourly prices in SEK/MWh
    """
    columnNames = ['Tidsperiod', 'Pris (öre/kWh)']
    dataFolder = Path(f'data/elspot_prices/Vattenfall-data/{year}/{biddingArea}')

    parts = []

    # Read the base file
    base = pd.read_excel(dataFolder / 'data.xlsx', header=0, usecols=[0,1])
    base.columns = columnNames
    base['Tidsperiod'] = pd.to_datetime(base['Tidsperiod'], format='%Y-%m-%d %H:%M')
    parts.append(base)

    # Read weekly files
    for i in range(1, 53):
        df_i = pd.read_excel(dataFolder / f'data ({i}).xlsx', header=0, usecols=[0,1])
        df_i.columns = columnNames
        df_i['Tidsperiod'] = pd.to_datetime(df_i['Tidsperiod'], format='%Y-%m-%d %H:%M')

        # Keep only the current year
        df_i = df_i[df_i['Tidsperiod'].dt.year == year]

        parts.append(df_i)

    # Concatenate all parts
    df = pd.concat(parts, ignore_index=True)
    df = df.drop_duplicates(subset=['Tidsperiod'])
    df['Tidsperiod'] = df['Tidsperiod'].dt.strftime('%Y-%m-%d %H:%M')

    # Adjust for lost hour due to summertime (wintertime hour is already included in data)
    if year == 2019:
        val = df.loc[df['Tidsperiod'] == '2019-03-31 01:00', 'Pris (öre/kWh)'].iloc[0]
        summertimeRow = pd.DataFrame(columns = df.columns, data = [['2019-03-31 02:00', val]]) #take same price as 01:00
    elif year == 2020:
        val = df.loc[df['Tidsperiod'] == '2020-03-29 01:00', 'Pris (öre/kWh)'].iloc[0]
        summertimeRow = pd.DataFrame(columns = df.columns, data = [['2020-03-29 02:00', val]]) #take same price as 01:00
    elif year == 2021:
        val = df.loc[df['Tidsperiod'] == '2021-03-28 01:00', 'Pris (öre/kWh)'].iloc[0]
        summertimeRow = pd.DataFrame(columns = df.columns, data = [['2021-03-28 02:00', val]]) #take same price as 01:00
    elif year == 2022:
        val = df.loc[df['Tidsperiod'] == '2022-03-27 01:00', 'Pris (öre/kWh)'].iloc[0]
        summertimeRow = pd.DataFrame(columns = df.columns, data = [['2022-03-27 02:00', val]]) #take same price as 01:00
    elif year == 2023:
        val = df.loc[df['Tidsperiod'] == '2023-03-26 01:00', 'Pris (öre/kWh)'].iloc[0]
        summertimeRow = pd.DataFrame(columns = df.columns, data = [['2023-03-26 02:00', val]]) #take same price as 01:00
    elif year == 2024:
        val = df.loc[df['Tidsperiod'] == '2024-03-31 01:00', 'Pris (öre/kWh)'].iloc[0]
        summertimeRow = pd.DataFrame(columns = df.columns, data = [['2024-03-31 02:00', val]]) #take same price as 01:00
    df = pd.concat([df, summertimeRow], axis=0)
    df = df.sort_values(by='Tidsperiod').reset_index(drop = True)

    df[f'Electricity price ({biddingArea}, SEK/MWh)'] = df['Pris (öre/kWh)']*10 # multiply by 10 to get SEK/MWh
    df = df.drop(columns=['Pris (öre/kWh)'])
    return df

def readElspotPrices_Vattenfall_test(year: int, biddingArea: str) -> pd.DataFrame:
    """
    Alternative implementation for reading Vattenfall prices with DST handling.
    
    Uses timezone-aware operations to properly handle daylight saving time transitions.
    This version is more robust for DST edge cases but slower than the main version.
    
    Args:
        year (int): Year (2019, 2023, or 2024)
        biddingArea (str): Bidding area code (SE1, SE2, SE3, SE4)
        
    Returns:
        pd.DataFrame: DataFrame with 8760 hourly prices in SEK/MWh
    """
    columnNames = ['Tidsperiod', 'Pris (öre/kWh)']
    dataFolder = Path(f'data/elspot_prices/Vattenfall-data/{year}/{biddingArea}')
    
    parts = []

    # Read the base file
    base = pd.read_excel(dataFolder / 'data.xlsx', header=0, usecols=[0,1])
    base.columns = columnNames
    base['Tidsperiod'] = pd.to_datetime(base['Tidsperiod'], format='%Y-%m-%d %H:%M')
    parts.append(base)

    # Read weekly files
    for i in range(1, 53):
        df_i = pd.read_excel(dataFolder / f'data ({i}).xlsx', header=0, usecols=[0,1])
        df_i.columns = columnNames
        df_i['Tidsperiod'] = pd.to_datetime(df_i['Tidsperiod'], format='%Y-%m-%d %H:%M')

        # Keep only the current year
        df_i = df_i[df_i['Tidsperiod'].dt.year == year]

        parts.append(df_i)

    # Concatenate all parts
    df = pd.concat(parts, ignore_index=True)
    df = df.drop_duplicates(subset=['Tidsperiod'])
    df = df.sort_values('Tidsperiod')

    # Use datetime index
    df = df.set_index('Tidsperiod')

    # Localize to Oslo to resolve DST issues
    df = df.tz_localize("Europe/Oslo",
                        nonexistent="shift_forward",    # handle spring forward
                        ambiguous="NaT")                # handle autumn back

    # Convert to UTC (no DST)
    df = df.tz_convert("UTC")

    # --- Force exactly 8760 hours ---
    full_index = pd.date_range(f"{year}-01-01 00:00",
                               f"{year}-12-31 23:00",
                               freq="H",
                               tz="UTC")
    df = df.reindex(full_index)

    # For the spring DST hour, fill with the values from next hour
    df = df.fillna(method="bfill")

    # Convert prices to SEK/MWh
    df[f"Electricity price ({biddingArea}, SEK/MWh)"] = df["Pris (öre/kWh)"] * 10
    df = df.drop(columns=["Pris (öre/kWh)"])

    # Convert back to local time for Excel (timezone-unaware)
    df = df.tz_localize(None) #.tz_convert("Europe/Oslo")

    # # Drop leap day rows
    # df = df[~((df.index.month == 2) & (df.index.day == 29))]

    return df

def readHighloadtime() -> pd.DataFrame:
    """
    Read high-load time definitions for network tariff calculations.
    
    High-load times typically correspond to winter months and peak hours,
    used to determine higher energy rates during these periods.
    
    Returns:
        pd.DataFrame: High-load time definitions indexed by regional entity (RE)
                     with columns for StartHour and EndHour (or '-' if not defined)
    """
    df = pd.read_excel('data/Highloadtime.xlsx', sheet_name='filteredHighloadTime')
    df = df.set_index('RE')    
    return df

def readLoadProfile(path: str) -> pd.DataFrame:
    """
    Read a 24-hour load profile template from an Excel file.
    
    Args:
        path (str): Path to the Excel file containing the load profile
        
    Returns:
        pd.DataFrame: 24-hour load profile with hourly values
    """
    return pd.read_excel(path)

def readModelingAreas(sheet: str) -> pd.DataFrame:
    """
    Read modeling area configuration data from ModelingAreas.xlsx.
    
    Args:
        sheet (str): Sheet name to read ('Data', 'ModelingAreas', etc.)
        
    Returns:
        pd.DataFrame: Modeling area data
    """
    return pd.read_excel('data/ModelingAreas.xlsx', sheet_name=sheet)
    
def readNetworkConcessionData(year: int) -> pd.DataFrame:
    """
    Read network concession data for a given year.
    
    Network concessions define which regional entities (DSOs) operate in each municipality.
    Data sources and formats differ between years (2023 Excel, 2024 CSV).
    
    Args:
        year (int): Year (2023 or 2024)
        
    Returns:
        pd.DataFrame: Network concession data with columns:
                     - kommunkod: Municipality code
                     - kommunnamn: Municipality name
                     - KONCESSION: Concession number
                     - Spanning: Voltage level
                     - Enhet: Regional entity/DSO name
                     - Företagsnamn: Company name
                     
    Raises:
        ValueError: If year is not 2023 or 2024
    """
    if year == 2023:
        df = pd.read_excel("data/Koncessioner/Natkoncessioner_per_kommun_med_kontaktuppgifter_fixad_2023.xlsx")
        return df[['Kommunkod', 'Kommunnamn', 'Koncession', 'Spänning', 'Red.enhet', 'Företagsn']]
    elif year == 2024:
        df = pd.read_csv("data/Koncessioner/KommunKoncession_med_kontaktuppgifter_2024.csv")
        return df[['kommunkod', 'kommunnamn', 'KONCESSION', 'Spanning', 'Enhet', 'Företagsnamn']]
    else:
        raise ValueError(f"Year {year} is not supported. Valid years: 2023, 2024")