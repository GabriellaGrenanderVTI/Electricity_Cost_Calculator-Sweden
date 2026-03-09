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
            ``län``, and f"RE + subgroup ({year})").
        municipalityList: Iterable of municipality names to keep.
        year: Year used to select the sub-accounting unit column.

    Returns:
        A DataFrame with columns: ``län``, ``kommunnamn``, ``RE + subgroup``
        for the year, ``FöretagNa`` and ``elomrade``.
    """
    df = df.loc[df['kommunnamn'].isin(municipalityList)]
    
    return df[['län', 'kommunnamn', f'RE + subgroup ({year})', 'FöretagNa', 'elomrade']]

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
    
    return df[['län', 'kommunnamn', f'RE + subgroup ({year})', 'FöretagNa', 'elomrade']]

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
    
    return df[['län', 'kommunnamn', f'RE + subgroup ({year})', 'FöretagNa', 'elomrade']]
    
def generateRElist(df, year):
    """Return a list of unique regional entities (RE) for the ``year``.

    The returned list is used to avoid duplicated RE computations during
    analysis.

    Args:
        df: DataFrame containing the column ``f'RE + subgroup ({year})'``.
        year: Year used to select the column holding the RE identifier.

    Returns:
        List of unique RE identifiers.
    """
    # We only want the unique REs of the area, to avoid computation of the same RE area over again
    return list(set(df[f'RE + subgroup ({year})'].tolist()))


def get_bidding_area_column(studyArea, year: int) -> str:
    """Return the bidding-area column name for the study area.

    Required column name:
    - ``Bidding Area``

    Args:
        studyArea: DataFrame with study area configuration.
        year (int): Year (included for API consistency, not currently used).

    Returns:
        str: The bidding area column name ('Bidding Area').

    Raises:
        KeyError: If the required 'Bidding Area' column is not found.
    """
    candidate = 'Bidding Area'
    if candidate in studyArea.columns:
        return candidate

    raise KeyError(
        "Missing required bidding area column in studyArea: 'Bidding Area'"
    )


def build_re_bidding_area_map(studyArea, year: int) -> dict:
    """Build mapping from RE to bidding area for the selected year.

    Args:
        studyArea: DataFrame with study area configuration including
            ``RE + subgroup (<year>)`` and ``Bidding Area`` columns.
        year (int): Year to select the regional entity column.

    Returns:
        dict: Mapping from RE identifier to bidding area code (uppercase).

    Raises:
        KeyError: If required columns are missing.
        ValueError: If bidding area values are empty or inconsistent.
    """
    re_col = f'RE + subgroup ({year})'
    if re_col not in studyArea.columns:
        raise KeyError(
            f"Missing required column '{re_col}' in studyArea"
        )

    bidding_col = get_bidding_area_column(studyArea, year)

    mapping_df = studyArea[[re_col, bidding_col]].dropna(subset=[re_col]).copy()
    mapping_df = mapping_df.rename(columns={re_col: 'RE', bidding_col: 'Bidding area'})
    mapping_df['RE'] = mapping_df['RE'].astype(str).str.strip()
    mapping_df['Bidding area'] = mapping_df['Bidding area'].astype(str).str.strip().str.upper()

    if mapping_df['Bidding area'].eq('').any():
        missing_re = mapping_df.loc[mapping_df['Bidding area'].eq(''), 'RE'].unique().tolist()
        raise ValueError(
            "Empty bidding area values found in studyArea for RE: "
            + ", ".join(sorted(missing_re))
        )

    inconsistent_re = (
        mapping_df.groupby('RE')['Bidding area']
        .nunique()
        .loc[lambda s: s > 1]
        .index
        .tolist()
    )
    if inconsistent_re:
        raise ValueError(
            "Inconsistent bidding area assignments for RE: "
            + ", ".join(sorted(inconsistent_re))
        )

    return mapping_df.drop_duplicates(subset=['RE']).set_index('RE')['Bidding area'].to_dict()
    