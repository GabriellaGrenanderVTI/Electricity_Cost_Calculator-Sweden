"""
Process Data Module for Transmogrifier

This module provides utility functions for enriching and restructuring time-series data
used in electricity pricing and load profile analysis. It focuses on adding temporal
metadata to datasets for downstream cost modeling and visualization.

Key Functions:
- reshapeLoadProfile(loadProfile_df, year): Expands 24-hour or 8760-hour profile to full-year hourly with timestamps and metadata.
- createDatetime(df): Generates a 'Date' column from Year, Month, Day, and Hour fields.
- createSeasonColumn(df): Adds a 'Season' column based on month (Winter, Spring, Summer, Autumn).
- createWeekdayColumn(df): Adds a 'Day of week' column (0 = Monday, 6 = Sunday).
- processData(df): Combines all steps to produce a cleaned DataFrame with temporal attributes.

Features:
- Normalizes load profiles to consistent 8760-hour format with temporal metadata.
- Converts discrete time components into a unified datetime format.
- Classifies records by season and weekday for tariff application and scenario analysis.
- Reorders columns for readability and drops redundant fields.

Typical Use Case:
Used after generating hourly load profiles to append temporal context before cost calculation.
"""

import calendar

import numpy as np
import pandas as pd


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