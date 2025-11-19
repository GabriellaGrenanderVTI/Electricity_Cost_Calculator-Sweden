# Electricity Grid Price Calculator

## Overview
This project calculates electricity grid prices scaled by load profiles for different scenarios and regional entities in Sweden. It handles various components of electricity pricing including taxes, fixed fees, power charges, and energy charges. The system is designed to analyze electricity costs for different municipalities and load patterns over multiple years.

## Key Features
- **Dynamic Load Profile Expansion:** Convert 24-hour profiles to full year (8760 hours) with automatic timestamp generation
- **Multiple Scenarios:** Base, flat, and peak-shaved load profile scenarios
- **Seasonal Pricing:** Winter, Spring, Summer, Fall pricing differentiation
- **Weekday/Weekend Differentiation:** Different tariffs for workdays vs weekends
- **Leap Year Handling:** Automatically skips Feb 29 for leap years
- **Price Components:** Taxes, fixed fees, power charges, energy charges, and spot prices
- **Multi-Year Support:** Process 2019-2024 with different data sources per year
- **DST Handling:** Automatic daylight saving time transition management

## Project Structure
```
Transmogrifier/
│
├── GridPriceScaledByLoad.py      # Core calculation functions
├── Transmogrifier.py             # 
├── GeneralizedTranslator.py      # Weighted spatial/entity transformations
├── FileManagement.py             # File I/O and data loading
├── FilterSpace.py                # Spatial data filtering
├── FilterTime.py                 # Temporal data filtering
├── ProcessData.py                # Data processing utilities
├── TranslateAttributes.py        # Data translation and mapping
├── README.md                     # This file
│
├── data/                         # Input data directory
│   ├── elspot_prices/
│   │   └── Vattenfall-data/YYYY/SE1-4/         (2019-2024)
│   ├── energimarknadsinspektionen/
│   │   ├── effektkunder-2011-2023.xlsx
│   │   └── effektkunder-1999-2025.xlsx
│   ├── koncessioner/
│   │   └── KommunKoncession_med_kontaktuppgifter_2024.csv
│   ├── Highloadtime.xlsx
│   ├── ModelingAreas.xlsx
│   └── Koncessioner/
│
└── output/                        # Generated results
    ├── loadProfileAllYears.csv
    └── totalCostAllYears.csv
```

## Prerequisites
- Python 3.8+
- Required packages:
  - calendar
  - datetime
  - logging
  - numpy >= 1.21.0
  - openpyxl
  - pandas >= 1.3.0
  - pathlib
  - typing

## Data Requirements

### Input Data Structure
All input data files must be placed in the `data/` directory.

#### <ins>Required Data Files</ins>

**1. Electricity Spot Prices** 
- **Vattenfall (2019-2024):**
  - Location: `data/elspot_prices/Vattenfall-data/{YEAR}/{BIDDING_AREA}/`
  - Files: `data.xlsx` + `data(1).xlsx` through `data(52).xlsx`
  - Format: Tidsperiod (timestamp) and Pris (öre/kWh)
  - Processing: Automatically converted to SEK/MWh (multiply by 10)

**2. Network Tariff Data**
- **File:** `data/effektkunder_2011-2023.xlsx`
- **Structure:** Multi-level indexed (REnummer × Year × CustomerType)
- **Customer Types:** 1, 2, 3 (different consumption levels)
<!--- TODO: Include 2025 --->
- **Years:** 2011-2023
- **Includes:** Authority fees, fixed fees, subscribed capacity costs
- **Selection:** Use config parameter `EFFECT_CUSTOMER_TYPE` to choose customer type, `YEAR` to choose year 

**3. High-Load Time Definitions**
- **File:** `data/Highloadtime.xlsx` (sheet: 'filteredHighloadTime')
- **Index:** RE (Regional Entity identifier)
- **Columns:** StartHour, EndHour (or '-' if not defined)
- **Purpose:** Define peak hours for seasonal tariff application
<!--- TODO: Describe somewhere else how to populate over REs --->
- **Fallback:** 
  - Uses "one-fits-all" month-based rule (Nov-Mar = high load)
  - Not populated for all REs, will need user maintenance for accuracy

**4. Regional Configuration**
- **File:** `data/ModelingAreas.xlsx`
- **Sheets:** 'Data' (raw data), 'ModelingAreas' (processed config)
- **Content:** Municipality-to-region mapping, modeling area definitions

**Network Concessions**
- **2023:** `data/Koncessioner/Natkoncessioner_per_kommun_med_kontaktuppgifter_fixad_2023.xlsx`
- **2024:** `data/Koncessioner/KommunKoncession_med_kontaktuppgifter_2024.csv`
- Maps municipalities to network operators (DSOs)

#### <ins>Optional Data Files</ins>

**Load Profiles**
- Any Excel file with 24-hour profile data
- Structure: 24 rows (hours 0-23) with load values
- Columns: 'hours', 'Base load profile', 'Peak load profile', 'Shaved load profile', etc.
- Can be extended to 8760 hours using `reshapeLoadProfile()`

### Data Format Notes
- **Price Units:** Handle both öre/kWh and SEK/MWh; automatic conversion
  - öre/kWh → SEK/MWh: multiply by 10
  - öre/kWh → SEK/kWh: divide by 100
- **Bidding Areas:** SE1 (North), SE2 (Central), SE3 (East), SE4 (South)
- **Years Supported:** 2019-2024 (with different data sources)
- **Regional Entities:** Defined by REnummer + REnamn in tariff data
- **Time Handling:** All times treated as local time; DST handled automatically

## Usage

### Programmatic Usage - Examples

**Expand 24-hour profile to full year:**
```python
import pandas as pd
from GridPriceScaledByLoad import reshapeLoadProfile

# Load 24-hour profile
profile_24h = pd.DataFrame({
    'Hour': range(24),
    'Power (kW)': [1.0] * 24,
    'Energy (kWh)': [1.0] * 24
})

# Expand to 8760 hours with metadata
profile_8760 = reshapeLoadProfile(
    profile_24h, 
    year=2024,
    scenario_cols=['Power (kW)', 'Energy (kWh)']
)

# Result includes: Timestamp, Year, Month, Day, Hour, Season, DayType
print(profile_8760.head())
print(f"Total hours: {len(profile_8760)}")  # 8760
```

**Generate example scenarios:**
```python
from GridPriceScaledByLoad import createScenarioLoadProfiles

scenarios_df, scenario_names = createScenarioLoadProfiles()
# Returns: Base, Flat, and Shaved load profiles (24 hours each)
print(scenario_names)
```

**Load electricity prices:**
```python
from FileManagement import readElspotPrices

# Automatically routes to correct source (Vattenfall or ElspotNu)
prices = readElspotPrices(year=2023, biddingArea='SE3')
print(f"Loaded {len(prices)} hourly prices")  # 8760
```

**Load network tariffs:**
```python
from FileManagement import readEffectCustomerPrices

tariffs = readEffectCustomerPrices(effectCustomerType=2, year=2023)
print(tariffs.head())
```

## Output Files

### loadProfileAllYears.csv
Expanded load profiles with metadata for all processed years/scenarios:
- **Year:** Processing year
- **Scenario:** Load scenario name
- **Season:** Winter/Spring/Summer/Fall
- **Hour:** 0-23 (repeating for each day)
- **DayType:** Weekday or Weekend
- **Load profile (kWh):** Hourly load values

### totalCostAllYears.csv
Cost breakdown by municipality and scenario:
- **Scenario:** Load profile scenario
- **Year:** Processing year
- **Season:** Seasonal aggregation
- **Municipality:** Target municipality
- **Total Cost (DSO):** Sum of all DSO costs
- **Fixed fees (DSO):** Annual fixed costs
- **Power (DSO):** Capacity/demand charges
- **Energy (DSO):** Energy charges
- **Energy (Spot):** Spot market costs

## Key Configuration Parameters

Edit these parameters in `GridPriceScaledByLoad.py` to suit your needs:

```python
# Customer type: 1 (small), 2 (medium), 3 (large)
EFFECT_CUSTOMER_TYPE = 2

# Electricity bidding area
BIDDING_AREA = 'SE3'

# Municipalities to include in analysis
MODELING_MUNICIPALITIES = [
    'Skövde', 'Götene', 'Skara', 'Falköping',
    'Tidaholm', 'Hjo', 'Tibro', 'Töreboda', 'Mariestad'
]

# Years to process
YEAR_LIST = [2019, 2020, 2021, 2022, 2023, 2024]
```

## Main Functions Reference

### GridPriceScaledByLoad.py

**`reshapeLoadProfile(loadProfile_df, year, scenario_cols=None)`**
- Expands 24-hour profile to 8760 hours
- Adds timestamps, seasons, and day types
- Handles leap years (skips Feb 29)
- Returns: DataFrame with 8760 rows

**`createScenarioLoadProfiles()`**
- Generates base, flat, and peak-shaved scenarios
- Returns: (24-hour DataFrame, list of scenario names)

**`isHighLoadMonth(month)`**
- Determines if month is high-load period
- Returns: Boolean (True = Nov-Mar)

**`isHighLoadTime(df, RE, month, day, hour)`**
- Checks if specific hour is high-load for regional entity
- Returns: Boolean

### GeneralizedTranslator.py

**`transmogrify(source_df, source_id, target_id, weights, val_cols, ...)`**
- Weighted aggregation from source to target entities
- Supports sum, mean, and rate operations

**`expand_24h_to_8760(loadProfile_df, hour_col='Hour', scenario_cols=None, year=2024)`**
- Alternative load profile expansion function
- Same output as `reshapeLoadProfile()`

### FileManagement.py

**`readElspotPrices(year, biddingArea)`**
- Loads hourly spot prices
- Routes to correct data source automatically
- Returns: DataFrame with 8760 rows in SEK/MWh

**`readEffectCustomerPrices(effectCustomerType, year)`**
- Loads network tariffs for customer type and year
- Returns: DataFrame indexed by RE

**`readHighloadtime()`**
- Loads high-load hour definitions
- Returns: DataFrame indexed by RE

**`readNetworkConcessionData(year)`**
- Loads municipality-to-DSO mapping
- Returns: DataFrame with municipality and operator info

**`writeDfToCsv(df, fileName)`**
- Writes DataFrame to output folder
- Auto-creates output folder if needed

## Testing

Test the load profile expansion:
```python
from GridPriceScaledByLoad import reshapeLoadProfile
import pandas as pd

# Create test profile
test = pd.DataFrame({
    'Hour': range(24),
    'Load': [1.0] * 24
})

# Expand to full year
expanded = reshapeLoadProfile(test, year=2024, scenario_cols=['Load'])

# Verify
assert len(expanded) == 8760, "Should have 8760 hours"
assert expanded['Season'].nunique() == 4, "Should have 4 seasons"
assert set(expanded['Season']) == {'Winter', 'Spring', 'Summer', 'Fall'}
assert set(expanded['DayType']) == {'Weekday', 'Weekend'}

# Verify no Feb 29 in leap year
feb_dates = expanded[expanded['Month'] == 2]['Day'].unique()
assert 29 not in feb_dates, "Should skip Feb 29"

print("✓ All tests passed")
```

## Tips & Best Practices

1. **Validate Input Data First**
   - Check for missing values in key columns
   - Verify units (öre/kWh vs SEK/MWh)
   - Ensure years in data match YEAR_LIST

2. **Use Dry-Run Mode**
   - Test full pipeline without writing files
   - Verify data loads correctly
   - Check for any errors before production run

3. **Monitor Data Sources**
   - Electricity wholesale prices
      - Vattenfall data no longer available for public download
      - Elspot.nu data no longer available for public download
      - Adding years further in the future will mean accessing these data somewhere else.
   - Concession tariff data 
      - Updated annually
      - New 

4. **Unit Consistency**
   - All prices normalized to SEK/MWh for elspot
   - Network tariffs converted from öre/kWh to SEK/kWh
   - Verify conversions in output data

5. **Regional Entity Mapping**
   - RE (regional entity) created as REnummer + REnamn
   - Must match across all data sources
   - Verify municipality codes match Swedish standard

## Error Handling
Common errors and solutions:

**"Expected 8760 hours, got X hours"**
- Check if Feb 29 is included when it shouldn't be (leap year handling)
- Verify source data has exactly 24 rows per scenario

**"Year X is not supported"**
- Valid range: 2019-2024
- Check available data files for the year

**"Column 'X' not found"**
- Verify file format matches expected structure
- Check sheet names in Excel files

**FileNotFoundError**
- Ensure data files in `data/` directory
- Use absolute paths if running from different directory

## License
[Add your license here]

## Contributors
- Gabriella Grenander (VTI)

## Contact
gabriella.grenander@vti.se

## Changelog

### Version 2.0 (Nov 2025)
- Refactored `reshapeLoadProfile()` to generate timestamps dynamically
- Implemented proper leap year handling (skip Feb 29)
- Added weekday/weekend differentiation
- Removed dependency on static 8760hours.xlsx file
