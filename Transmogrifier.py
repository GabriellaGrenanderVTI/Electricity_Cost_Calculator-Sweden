import pandas as pd

from FilterTime import filterSeason, filterMonth, filterWeekdayWeekend, filterHour

# The transmogrifier assumes that you get data on a 8760 time resolution level, and will compress it into the timeslice level of your choosing

##################### POSSIBLE TRANSFORMATIONS #####################

### AGGREGATE ON A SEASONAL AND HOURLY BASIS (4*24 = 96 SLICES) ###
def seasonHourTrans(df, dataColumns, operator):
    """
    Aggregate the DataFrame on a seasonal and hourly basis.
    
    Args:
        df (pd.DataFrame): DataFrame containing time series data
        dataColumns (list): List of columns to aggregate
        operator (str): Aggregation operator ('average' or 'sum')
    
    Returns:
        pd.DataFrame: Aggregated DataFrame on a seasonal and hourly basis
    """
    seasonHourList = []
    
    for season in range(1,5):
        season_df = filterSeason(df, season)
        for hour in range(0,24):
            seasonHour_df = filterHour(season_df, hour)
            
            if operator == 'average':
                seasonHourData = seasonHour_df.loc[:,dataColumns].mean().tolist()
            elif operator == 'sum':                
                seasonHourData = seasonHour_df.loc[:,dataColumns].sum().tolist()

            seasonHourList.append([season, hour] + seasonHourData)
    
    return pd.DataFrame(seasonHourList, columns=['Season', 'Hour'] + dataColumns)

### AGGREGATE ON A MONTHLY BASIS (12 SLICES) ###
def monthTrans(df, dataColumns, operator):
    """
    Aggregate the DataFrame on a monthly basis.
    
    Args:
        df (pd.DataFrame): DataFrame containing time series data
        dataColumns (list): List of columns to aggregate
        operator (str): Aggregation operator ('average' or 'sum')
        
    Returns:
        pd.DataFrame: Aggregated DataFrame on a monthly basis
    """
    monthList = []
    
    for month in range(1,13):
        month_df = filterMonth(df, month)
        
        if operator == 'average':
            monthData = month_df.loc[:,dataColumns].mean().tolist()
        elif operator == 'sum':
            monthData = month_df.loc[:,dataColumns].sum().tolist()
        monthList.append([month] + monthData)
    
    return pd.DataFrame(monthList, columns=['Month'] + dataColumns)

### AGGREGATE ON A WEEKDAY/WEEKEND BASIS (2 SLICES) ###
def weekdayWeekendTrans(df, dataColumns, typeOfDay, operator):
    """
    Aggregate the DataFrame on a weekday/weekend basis.

    Args:
        df (pd.DataFrame): DataFrame containing time series data
        dataColumns (list): List of columns to aggregate
        typeOfDay (str): 'Weekday' or 'Weekend'
        operator (str): Aggregation operator ('average' or 'sum')
    
    Returns:
        pd.DataFrame: Aggregated DataFrame on a weekday/weekend basis
    """
    typeOfDayList = []
    
    typeOfDay_df = filterWeekdayWeekend(df, typeOfDay)

    if operator == 'average':
        typeOfDayData = typeOfDay_df.loc[:,dataColumns].mean().tolist()
    elif operator == 'sum':
        typeOfDayData = typeOfDay_df.loc[:,dataColumns].sum().tolist() 

    typeOfDayList.append([typeOfDay] + typeOfDayData)
    
    return pd.DataFrame(typeOfDayList, columns = ['Type of day'] + dataColumns)

### AGGREGATE ON A MONTHLY AND WEEKDAY/WEEKEND BASIS (12*2 = 24 SLICES) ###
def monthWeekdayWeekendTrans(df, dataColumns, operator):
    """
    Aggregate the DataFrame on a monthly and weekday/weekend basis.
    
    Args:
        df (pd.DataFrame): DataFrame containing time series data
        dataColumns (list): List of columns to aggregate
        operator (str): Aggregation operator ('average' or 'sum')
        
    Returns:
        pd.DataFrame: Aggregated DataFrame on a monthly and weekday/weekend basis
    """
    monthTypeOfDayList = []
    
    for month in range(1,13):
        month_df = filterMonth(df, month)
        for typeOfDay in ['Weekday', 'Weekend']:
            monthTypeOfDay_df = filterWeekdayWeekend(month_df, typeOfDay)
            
            if operator == 'average':
                monthTypeOfDayData = monthTypeOfDay_df.loc[:,dataColumns].mean().tolist()
            elif operator == 'sum':
                monthTypeOfDayData = monthTypeOfDay_df.loc[:,dataColumns].sum().tolist() 
            
            monthTypeOfDayList.append([month, typeOfDay] + monthTypeOfDayData)
    
    return pd.DataFrame(monthTypeOfDayList, columns=['Month', 'Type of day'] + dataColumns)

### AGGREGATE ON A MONTHLY AND HOURLY BASIS (12*24 = 288 SLICES) ###
def monthHourTrans(df, dataColumns, operator):
    """
    Aggregate the DataFrame on a monthly and hourly basis.
    
    Args:
        df (pd.DataFrame): DataFrame containing time series data
        dataColumns (list): List of columns to aggregate
        operator (str): Aggregation operator ('average' or 'sum')
        
    Returns:
        pd.DataFrame: Aggregated DataFrame on a monthly and hourly basis
    """
    monthHourList = []
    
    for month in range(1,13):
        month_df = filterMonth(df, month)
        for hour in range(0,24):
            monthHour_df = filterHour(month_df, hour)
            
            if operator == 'average':
                monthHourData = monthHour_df.loc[:,dataColumns].mean().tolist()
            elif operator == 'sum':
                monthHourData = monthHour_df.loc[:,dataColumns].sum().tolist() 
            
            monthHourList.append([month, hour] + monthHourData)
    
    return pd.DataFrame(monthHourList, columns=['Month', 'Hour'] + dataColumns)

### AGGREGATE ON A MONTHLY, WEEKDAY/WEEKEND, AND HOURLY BASIS (12*2*24 = 576 SLICES) ###
def monthWeekdayWeekendHourTrans(df, dataColumns, operator):
    """
    Aggregate the DataFrame on a monthly, weekday/weekend, and hourly basis.

    Args:
        df (pd.DataFrame): DataFrame containing time series data
        dataColumns (list): List of columns to aggregate
        operator (str): Aggregation operator ('average' or 'sum')

    Returns:
        pd.DataFrame: Aggregated DataFrame on a monthly, weekday/weekend, and hourly basis
    """
    monthTypeOfDayHourList = []
    
    for month in range(1,13):
        month_df = filterMonth(df, month)
        for typeOfDay in ['Weekday', 'Weekend']:
            monthTypeOfDay_df = filterWeekdayWeekend(month_df, typeOfDay)
            for hour in range(0,24):
                monthHour_df = filterHour(monthTypeOfDay_df, hour)
            
                if operator == 'average':
                    monthTypeOfDayHourData = monthHour_df.loc[:,dataColumns].mean().tolist()
                elif operator == 'sum':
                    monthTypeOfDayHourData = monthHour_df.loc[:,dataColumns].sum().tolist() 
            
                monthTypeOfDayHourList.append([month, typeOfDay, hour] + monthTypeOfDayHourData)
    
    return pd.DataFrame(monthTypeOfDayHourList, columns=['Month', 'Type of day', 'Hour'] + dataColumns)