"""File management helpers for Transmogrifier.

This module centralises file input/output used by the rest of the project.

Provided functions load and return data structures expected by the analysis
scripts (pandas DataFrames). Functions assume the repository layout under
``data/`` and ``output/`` and return already-parsed DataFrames or write files
to ``output/``.

Notes:
- Functions are thin wrappers around :mod:`pandas` IO and do not perform
    extensive validation of file contents; callers rely on expected column names
    and shapes.
"""

from datetime import datetime
from pathlib import Path
import pandas as pd


def readEffectCustomerPrices_2025(effectCustomerType, year):
    """Load network tariff data for a given customer type and year.

    The function reads the multi-index Excel file ``data/Effektkunder-1999-2025.xlsx``
    and extracts the columns for the requested ``year`` and customer
    ``effectCustomerType`` (NT9{1,2,3}). The returned DataFrame is indexed by
    a generated regional entity identifier ``RE``.

    Args:
        effectCustomerType (int): Customer type (1, 2, or 3).
        year (int): Year to extract (e.g. 2024).

    Returns:
        pd.DataFrame: Network pricing data indexed by regional entity (RE),
            containing tariff columns for the selected year and customer type.
    """
    df = pd.read_excel('data/Effektkunder-1999-2025.xlsx', header = [0,1,2])

    # Keep the columns to combine with result later on
    # Needed to do it this way since we always want these columns, and making them
    # a multiindex made me lose the name of the columns
    mask = df.columns.get_level_values(2).isin(['ReNamn', 'Företag', 'Gruppnamn'])

    df2 = df.loc[:, mask]
    df2 = df2.droplevel([0, 1], axis=1)
    
    # Find the columns that contain information about desired year
    year = str(year)
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
    df['RE'] = df['ReNamn'].fillna('') + df['Gruppnamn'].fillna('')
    # df.insert(5, 'RE', col)
    df = df.set_index('RE')
    df = df.drop(columns = ['index'])
    return df

def readElspotPrices(year: int, biddingArea: str) -> pd.DataFrame:
    """Return hourly electricity spot prices for a year and bidding area.

    For years 2019–2024 the function routes to the Vattenfall data reader.
    The returned DataFrame contains a datetime-like text column and a numeric
    column named ``Electricity price (<biddingArea>, SEK/MWh)``.

    Args:
        year: Year to load (2019-2024).
        biddingArea: Bidding area code (``'SE1'``, ``'SE2'``, ``'SE3'``, ``'SE4'``).

    Returns:
        DataFrame with hourly prices in SEK/MWh. The function ensures the output
        covers the full year (8760 hours) for non-leap years.

    Raises:
        ValueError: If ``year`` is outside the supported range (2019-2024).
    """
    if year in [2019, 2020, 2021, 2022, 2023, 2024]:
        return readElspotPrices_Vattenfall(year, biddingArea)
    else:
        raise ValueError(f"Year {year} is not supported. Valid years: 2019-2024")

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

def readLoadProfile(path: str, sheet: str) -> pd.DataFrame:
    """
    Read a 24-hour load profile template from an Excel file.
    
    Args:
        path (str): Path to the Excel file containing the load profile
        sheet (str): Sheet name to read from the Excel file
        
    Returns:
        pd.DataFrame: 24-hour load profile with hourly values
    """
    return pd.read_excel(path, sheet_name=sheet)

def readStudyAreas(sheet: str) -> pd.DataFrame:
    """
    Read study area configuration data from studyArea.xlsx.
    
    Args:
        sheet (str): Sheet name to read
        
    Returns:
        pd.DataFrame: Modeling area data
    """
    return pd.read_excel('input/studyArea.xlsx', sheet_name=sheet)