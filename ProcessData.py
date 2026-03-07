"""
Process Data Module for Transmogrifier

This module provides utility functions for enriching and restructuring time-series data
used in electricity pricing and load profile analysis. It focuses on adding temporal
metadata to datasets for downstream cost modeling and visualization.

Key Functions:
- createDatetime(df): Generates a 'Date' column from Year, Month, Day, and Hour fields.
- createSeasonColumn(df): Adds a 'Season' column based on month (Winter, Spring, Summer, Autumn).
- createWeekdayColumn(df): Adds a 'Day of week' column (0 = Monday, 6 = Sunday).
- processData(df): Combines all steps to produce a cleaned DataFrame with temporal attributes.

Features:
- Converts discrete time components into a unified datetime format.
- Classifies records by season and weekday for tariff application and scenario analysis.
- Reorders columns for readability and drops redundant fields.

Typical Use Case:
Used after generating hourly load profiles to append temporal context before cost calculation.
"""

import pandas as pd

def createDatetime(df):
    """Add a ``Date`` column created from integer time components.

    Expects columns ``Year``, ``Month``, ``Day`` and ``Hour`` to be present in
    ``df``. The new column is a pandas datetime (``datetime64[ns]``).

    Args:
        df: DataFrame with time component columns.

    Returns:
        The same DataFrame with an added ``Date`` column.
    """
    df['Date'] = pd.to_datetime(df[['Year', 'Month', 'Day', 'Hour']])
    
    return df

def createSeasonColumn(df):
    """Add a numeric ``Season`` column derived from ``Date``.

    Seasons are encoded as integers 1–4 (1=Winter, 2=Spring, 3=Summer, 4=Autumn)
    and are calculated from ``df['Date']``. Caller must ensure ``Date`` exists
    (e.g. created by :func:`createDatetime`).

    Args:
        df: DataFrame with a datetime-like ``Date`` column.

    Returns:
        The DataFrame with a new ``Season`` column (integers 1–4).
    """
    # 1: Winter
    # 2: Spring
    # 3: Summer
    # 4: Autumn
    df['Season'] = df['Date'].dt.month%12 // 3 + 1
    
    return df

def createWeekdayColumn(df):
    """Add ``Day of week`` column (0=Monday .. 6=Sunday) from ``Date``.

    Args:
        df: DataFrame with a ``Date`` column.

    Returns:
        The DataFrame with a ``Day of week`` integer column.
    """
    df['Day of week'] = df['Date'].dt.weekday
    
    return df

def processData(df):
    """Run the standard time enrichment pipeline on the DataFrame.

    This convenience function sequentially calls :func:`createDatetime`,
    :func:`createSeasonColumn` and :func:`createWeekdayColumn`, then reorders
    and drops intermediate columns to produce a consistent output shape used by
    the analysis scripts.

    Args:
        df: DataFrame with ``Year``, ``Month``, ``Day`` and ``Hour`` columns.

    Returns:
        The processed DataFrame with columns ``Date``, ``Season``, ``Day of week``
        inserted at the front and the original ``Day`` column dropped.
    """
    df = createDatetime(df)
    df = createSeasonColumn(df)
    df = createWeekdayColumn(df)

    df.insert(0, 'Day of week', df.pop('Day of week'))
    df.insert(0, 'Season', df.pop('Season'))
    df.insert(0, 'Date', df.pop('Date'))

    df = df.drop(['Day'], axis = 1)

    return df