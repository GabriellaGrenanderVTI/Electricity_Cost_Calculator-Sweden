"""
Filter Space Module for Transmogrifier

This module provides functions to filter spatial data related to electricity grid pricing
and network concessions. It enables selection of specific municipalities, regions, or bidding
areas for targeted analysis and scenario modeling.

Key Functions:
- filterMunicipalitySubset(df, municipalityList, year): Filters data for a given list of municipalities.
- filterRegion(df, region, year): Filters data for a specified region (county level).
- filterBiddingArea(df, biddingArea, year): Filters data for a specified electricity bidding area (SE1–SE4).
- generateRElist(df, year): Generates a unique list of regional entities (REs) for the specified year.

Features:
- Supports spatial filtering for cost analysis and visualization.
- Returns relevant columns including municipality name, region, sub-accounting unit, DSO name, and bidding area.
- Facilitates aggregation and mapping of tariff data to geographic entities.

Typical Use Case:
Used during preprocessing to isolate municipalities or regions of interest before applying
tariff structures and calculating electricity costs for different load scenarios.
"""

def filterMunicipalitySubset(df, municipalityList, year):
    """Return rows for the given municipalities and select useful columns.

    The function filters ``df`` for rows where ``kommunnamn`` is in
    ``municipalityList`` and returns a subset containing commonly used columns
    including the sub-accounting unit for the supplied ``year``.

    Args:
        df: DataFrame with regional metadata (expects columns ``kommunnamn``,
            ``län``, and f"Subredovisningsenhet ({year})").
        municipalityList: Iterable of municipality names to keep.
        year: Year used to select the sub-accounting unit column.

    Returns:
        A DataFrame with columns: ``län``, ``kommunnamn``, ``Subredovisningsenhet``
        for the year, ``FöretagNa`` and ``elomrade``.
    """
    df = df.loc[df['kommunnamn'].isin(municipalityList)]
    
    return df[['län', 'kommunnamn', f'Subredovisningsenhet ({year})', 'FöretagNa', 'elomrade']]

def filterRegion(df, region, year):
    """Return rows for the supplied region (county) and select key columns.

    Args:
        df: DataFrame with regional metadata (expects column ``län``).
        region: Region/county name to filter on.
        year: Year used to select the sub-accounting unit column.

    Returns:
        DataFrame with the same columns as :func:`filterMunicipalitySubset`.
    """
    df = df.loc[df['län'] == region]
    
    return df[['län', 'kommunnamn', f'Subredovisningsenhet ({year})', 'FöretagNa', 'elomrade']]

def filterBiddingArea(df, biddingArea, year):
    """Return rows where the bidding area column matches ``biddingArea``.

    Args:
        df: DataFrame with an ``elomrade`` column (bidding area).
        biddingArea: Bidding area id (e.g. ``'SE3'``).
        year: Year used to select the sub-accounting unit column.

    Returns:
        DataFrame with the same columns as :func:`filterMunicipalitySubset`.
    """
    df = df.loc[df['elomrade'] == biddingArea]
    
    return df[['län', 'kommunnamn', f'Subredovisningsenhet ({year})', 'FöretagNa', 'elomrade']]
    
def generateRElist(df, year):
    """Return a list of unique regional entities (RE) for the ``year``.

    The returned list is used to avoid duplicated RE computations during
    analysis.

    Args:
        df: DataFrame containing the column ``f'Subredovisningsenhet ({year})'``.
        year: Year used to select the column holding the RE identifier.

    Returns:
        List of unique RE identifiers.
    """
    # We only want the unique REs of the area, to avoid computation of the same RE area over again
    return list(set(df[f'Subredovisningsenhet ({year})'].tolist()))
    