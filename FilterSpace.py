def filterMunicipalitySubset(df, municipalityList, year):
    """
    Filter the DataFrame to include only the specified municipalities.

    Args:
        df (pd.DataFrame): DataFrame containing regional data
        municipalityList (list): List of municipalities to filter by
        year (int): Year for which the data is relevant
    Returns:
        pd.DataFrame: Filtered DataFrame containing only the specified municipalities
    """
    df = df.loc[df['kommunnamn'].isin(municipalityList)]
    
    return df[['län', 'kommunnamn', f'Subredovisningsenhet ({year})', 'FöretagNa', 'elomrade']]

def filterRegion(df, region, year):
    """
    Filter the DataFrame to include only the specified region.
    
    Args:
        df (pd.DataFrame): DataFrame containing regional data
        region (str): Region to filter by
        year (int): Year for which the data is relevant

    Returns:
        pd.DataFrame: Filtered DataFrame containing only the specified region
    """
    df = df.loc[df['län'] == region]
    
    return df[['län', 'kommunnamn', f'Subredovisningsenhet ({year})', 'FöretagNa', 'elomrade']]

def filterBiddingArea(df, biddingArea, year):
    """
    Filter the DataFrame to include only the specified bidding area.
    
    Args:
        df (pd.DataFrame): DataFrame containing regional data
        biddingArea (str): Bidding area to filter by
        year (int): Year for which the data is relevant
    
    Returns:
        pd.DataFrame: Filtered DataFrame containing only the specified bidding area
    """
    df = df.loc[df['elomrade'] == biddingArea]
    
    return df[['län', 'kommunnamn', f'Subredovisningsenhet ({year})', 'FöretagNa', 'elomrade']]
    
def generateRElist(df, year):
    """
    Generate a list of unique regional entities for the specified year.
    
    Args:
        df (pd.DataFrame): DataFrame containing regional data
        year (int): Year for which the data is relevant
    
    Returns:
        list: List of unique regional entities
    """
    # We only want the unique REs of the area, to avoid computation of the same RE area over again
    return list(set(df[f'Subredovisningsenhet ({year})'].tolist()))
    