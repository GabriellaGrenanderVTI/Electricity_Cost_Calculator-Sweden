def filterYear(df, year):
    """
    Filter the DataFrame to include only the specified year.
    
    Args:
        df (pd.DataFrame): DataFrame containing time series data
        year (int): Year to filter by
    
    Returns:
        pd.DataFrame: Filtered DataFrame containing only the specified year
    """
    return df[df['Date'].dt.year == year]

def filterSeason(df, season):
    """
    Filter the DataFrame to include only the specified season.
    
    Args:
        df (pd.DataFrame): DataFrame containing time series data
        season (str or int): Season to filter by ('Winter', 'Spring', 'Summer', 'Autumn' or 1, 2, 3, 4)
    
    Returns:
        pd.DataFrame: Filtered DataFrame containing only the specified season
    """
    if (season == 'Winter') | (season == 1):
        return df[df['Season'] == 1]
    elif (season == 'Spring') | (season == 2):
        return df[df['Season'] == 2]
    if (season == 'Summer') | (season == 3):
        return df[df['Season'] == 3]
    if (season == 'Autumn') | (season == 4):
        return df[df['Season'] == 4]

def filterMonth(df, month):
    """
    Filter the DataFrame to include only the specified month.
    
    Args:
        df (pd.DataFrame): DataFrame containing time series data
        month (int): Month to filter by (1-12)
        
    Returns:
        pd.DataFrame: Filtered DataFrame containing only the specified month"""
    return df[df['Date'].dt.month == month]

def filterWeekdayWeekend(df, typeOfDay):
    """
    Filter the DataFrame to include only weekdays or weekends.

    Args:
        df (pd.DataFrame): DataFrame containing time series data
        typeOfDay (str): 'Weekday' or 'Weekend'
    Returns:
        pd.DataFrame: Filtered DataFrame containing only weekdays or weekends
    """
    if typeOfDay == 'Weekend': #[5, 6]
        df = df[(df['Day of week'].isin([5, 6]))]
    else:
        df = df[(df['Day of week'].isin([0, 1, 2, 3, 4]))]
    
    return df

def filterDay(df, day):
    """
    Filter the DataFrame to include only the specified day of the month.
    
    Args:
        df (pd.DataFrame): DataFrame containing time series data
        day (int): Day of the month to filter by (1-31)
    
    Returns:
        pd.DataFrame: Filtered DataFrame containing only the specified day of the month
    """
    return df[df['Date'].dt.day == day]

def filterHour(df, hour):
    """
    Filter the DataFrame to include only the specified hour of the day.
    
    Args:
        df (pd.DataFrame): DataFrame containing time series data
        hour (int): Hour of the day to filter by (0-23)
        
    Returns:
        pd.DataFrame: Filtered DataFrame containing only the specified hour of the day
    """
    return df[df['Date'].dt.hour == hour]

def months2seasons(month):
    """
    Convert month number to season name.
    Args:
        month (int): Month number (1-12)
        
    Returns:
        str: Season name ('Winter', 'Spring', 'Summer', 'Autumn')
    """
    if 3 <= month <= 5:
        return "Spring"
    elif 6 <= month <= 8:
        return "Summer"
    elif 9 <= month <= 11:
        return "Autumn"
    elif (month == 12) | (1 <= month <= 2):
        return "Winter"
    else:
        raise ValueError("This is not a valid month number")