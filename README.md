# Electricity Grid Price Calculator

## Overview
This project calculates electricity wholesale and grid costs given a load profile for different distribution system operators (DSOs) in Sweden. It handles various components of electricity pricing including taxes, fixed fees, power charges, and energy charges. The system is designed to analyze electricity costs for different DSOs and load patterns over multiple years.

## Key Features
- **Flexible Load Profile Input:** Accept either 24-hour templates (auto-expanded to 8760) or full 8760-hour profiles
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
├── GridPriceScaledByLoad.py      # Main orchestration pipeline
├── FileManagement.py             # File I/O and data loading helpers
├── FilterSpace.py                # Regional spatial filtering
├── PriceComponents.py            # Pricing component calculators
├── ProcessData.py                # Data processing utilities
├── TariffLogic.py                # Pure tariff calculation functions
├── README.md                     # This file
│
├── data/                         # Input data directory
│   ├── dsoTariffStructures.json  # Tariff rules configuration
│   ├── elspot_prices/
│   │   └── Vattenfall-data/
│   │       ├── 2019/SE1-4/*.xlsx   (weekly spot prices)s
│   │       ├── 2020/SE1-4/*.xlsx
│   │       ├── 2021/SE1-4/*.xlsx
│   │       ├── 2022/SE1-4/*.xlsx
│   │       ├── 2023/SE1-4/*.xlsx
│   │       └── 2024/SE1-4/*.xlsx
│   └── effektkunder-1999-2025.xlsx           (network tariffs)
│
├── input/
│   └── studyarea.xlsx                        (study area configuration)
│
└── output/                        # Generated results
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
All input data files must be placed in the `input/` directory.

#### <ins>User Input Files</ins>

**1. Load Profile** 
- Any Excel file with hourly load data
- Supported structures:
  - 24 rows (hours 0-23): treated as a daily template and expanded to 8760 hours
  - 8760 rows: treated as a full-year hourly profile (used directly)
- Required column: `Load (kWh)` containing hourly load values
- `reshapeLoadProfile()` normalizes both formats to a consistent 8760-hour structure

**2. Regional Configuration**
- **File:** `data/studyArea.xlsx` or similar study area definition file
- **Content:** DSO (Distribution System Operator) identifiers
- **Required Columns:** 'DSO (short)', 'Subredovisningsenhet (YYYY)' QQQ this needs to be checked

#### <ins>Provided Data Files</ins>
**1. Electricity Spot Prices** 
- **Source:** Vattenfall
- **Location:** `data/elspot_prices/Vattenfall-data/{YEAR}/{BIDDING_AREA}/`
- **Files:** `data.xlsx`, `data(1).xlsx` through `data(52).xlsx`
- **Structure** Tidsperiod (timestamp) and Pris (öre/kWh)
- **Includes:** Electricity pricing data for 
- **Processing:** Automatically converted to SEK/MWh (multiply by 10)

**2. Network Tariff Data**
- **Source:** Swedish Energy Market Inspectorate (EI)
- **File:** `data/effektkunder-1999-2025.xlsx`
- **Structure:** Multi-level indexed (RE number × Year × CustomerType)
  - RE number: Reporting entity (Swedish: Redovisningsenhet) under which a DSO reports to EI. Together with groupname serves as a unique identifier
  - Customer Types: 1 (100 kW, 350 MWh/year), 2 (1 MW, 5 GWh/year), 3 (20 MW, 140 GWh/year)
  - Years: 1999-2025
- **Includes:** Authority fees, fixed fees, subscribed capacity costs, energy charges
- **Selection:** Use `effectCustomerType` parameter to choose customer type (1, 2, or 3)

**3. Tariff Rules Configuration (JSON)** 
- **File:** `data/DsoTariffStructures.json`
- **Structure:** DSO-specific tariff rules with capacity definitions and high-load configurations
- **Example:**
  ```json
  {
    "REL00011": {
      "DSO": "Bjärke Energi ek. för.",
      "power_tariff": {
        "applies": true,
        "capacity_definition": "sub_cap_window_peak",
        "months": [4, 5, 6, 7, 8, 9, 10],
        "time_window": {
          "start_hour": 6,
          "end_hour": 22
        }
      },
      "highload_power": {
        "applies": true,
        "months": [11, 12, 1, 2, 3],
        "calculation": "high_load_window_peak_avg_of_three",
        "time_window": {
          "start_hour": 6,
          "end_hour": 22
        }
      }
    }
  }
  ```
- **Purpose:** Defines how subscribed capacity charges and high-load power charges are calculated per DSO

### Data Format Notes
- **Price Units:** Expects both öre/kWh and SEK/MWh; automatic conversion
  - öre/kWh → SEK/MWh: multiply by 10
  - öre/kWh → SEK/kWh: divide by 100
- **Bidding Areas:** SE1, SE2, SE3, SE4
- **Years Supported:** 2019-2024 (with different data sources)
- **Regional Entities:** Defined by REnummer + REnamn in tariff data
- **Time Handling:** All times treated as local time; DST handled automatically

## Usage

### Main Script Execution

**As a standalone script:**
```bash
python GridPriceScaledByLoad.py
```
Runs with default parameters: `effectCustomerType=2`, `biddingArea='SE3'`, `yearList=[2024]`, and generates output CSVs.

**Programmatic usage with `main()` function:**
```python
from GridPriceScaledByLoad import main
import FileManagement as fm

# Prepare inputs
effectCustomerType = 2
biddingArea = 'SE3'
studyArea = fm.readStudyAreas('Sheet1')
loadProfile_raw_df = fm.readLoadProfile('data/EV-bus-charging-needs-Arsalan.xlsx')
yearList = [2023, 2024]

# Run analysis and capture results
totalCost_df, totalCost_24h_df, loadProfile_df = main(
    effectCustomerType,
    biddingArea,
    studyArea,
    loadProfile_raw_df,
    yearList
)

# Use results programmatically
print(f"Processed {len(totalCost_df)} rows")
print(totalCost_df.groupby('Year')['Total Cost (DSO)'].sum())
```

### Programmatic Usage - Helper Function Examples

**Expand 24-hour profile to full year:**
```python
import pandas as pd
from GridPriceScaledByLoad import reshapeLoadProfile

# Load 24-hour profile (must have 'Load (kWh)' column)
profile_24h = pd.DataFrame({
    'Hour': range(24),
    'Load (kWh)': [1.0] * 24
})

# Expand to 8760 hours with metadata
profile_8760 = reshapeLoadProfile(profile_24h, year=2024)

# Result includes: Timestamp, Year, Month, Day, Hour, Season, DayType, Load (kWh)
print(profile_8760.head())
print(f"Total hours: {len(profile_8760)}")  # 8760
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
from FileManagement import readEffectCustomerPrices_2025

tariffs = readEffectCustomerPrices_2025(effectCustomerType=2, year=2023)
print(tariffs.head())
```

## Output Files

### loadProfileAllYears.csv
Expanded load profiles with metadata for all processed years:
- **Year:** Processing year
- **Season:** Winter/Spring/Summer/Fall
- **Hour:** 0-23 (repeating for each day)
- **Load profile (kWh):** Hourly load values

### totalCost_AllYears.csv
Full hourly cost breakdown by municipality (8760 rows per year × DSO):
- **Year:** Processing year
- **Season:** Seasonal aggregation
- **Month:** Month number
- **Hour:** Hour of day (0-23)
- **DSO (short):** Distribution system operator short code
- **Total Cost (DSO):** Sum of all DSO costs for that hour (kr)
- **Fixed fees (DSO):** Fixed annual costs distributed hourly (kr)
- **Power (DSO):** Subscribed capacity charges (kr)
- **Highload power (DSO):** High-load power charges (kr)
- **Energy (DSO):** Network energy charges (kr)
- **Energy (Spot):** Spot market electricity costs (kr)

### totalCost_24hour_AllYears.csv
24-hour aggregate cost profile (redistributed for visualization):
- **Hour:** 0-23
- **DSO (short):** Distribution system operator short code
- **Year:** Processing year
- **Fixed fees (DSO):** Average fixed fees per hour across year (kr)
- **Energy (DSO):** Average network energy charges per hour (kr)
- **Energy (Spot):** Average spot costs per hour (kr)
- **Power (DSO):** Annual subscribed capacity cost accumulated at hour 23 (kr)
- **Highload power (DSO):** Annual high-load power cost accumulated at hour 12 (kr)

## Key Configuration Parameters

Configuration is now handled via function parameters in the `main()` function. Edit these values in `GridPriceScaledByLoad.py` (in the `if __name__ == '__main__':` block) or pass them directly when calling `main()`:

```python
# In the if __name__ == '__main__': block:

effectCustomerType = 2  # Customer type: 1 (small), 2 (medium), 3 (large)
biddingArea = 'SE3'     # Electricity bidding area: SE1-SE4
studyArea = fm.readStudyAreas('Sheet1')  # Regional configuration
loadProfile_raw_df = fm.readLoadProfile('data/EV-bus-charging-needs-Arsalan.xlsx')  # Load profile data
yearList = [2024]       # Years to process
```

**Parameter Details:**
- **effectCustomerType:** Integer (1, 2, or 3) indicating customer consumption level for tariff selection
- **biddingArea:** String code for electricity bidding area ('SE1', 'SE2', 'SE3', 'SE4')
- **studyArea:** DataFrame with study area configuration including DSO codes and region mappings
- **loadProfile_raw_df:** DataFrame with 24-hour load profile (24 rows, hourly values)
- **yearList:** List of years to process (e.g., `[2023, 2024]`)

## Tariff Configuration Guide

### JSON Structure Overview

The `DsoTariffStructures.json` file defines how tariffs are calculated for each DSO. Each entry consists of:

1. **`power_tariff`** - Regular power (capacity) charges
2. **`highload_power`** - High-load period power charges

### Power Tariff Configuration

**Required Fields:**
- `applies` (boolean) - Whether power tariff is active
- `capacity_definition` (string) - How to calculate capacity charge

**Optional Fields:**
- `months` (array) - Restrict tariff to specific months (1-12)
- `time_window` (object) - Restrict tariff to specific hours
  - `start_hour` (int) - Starting hour (0-23)
  - `end_hour` (int) - Ending hour (0-23)

**Example - Seasonal Power Tariff:**
```json
"power_tariff": {
  "applies": true,
  "capacity_definition": "sub_cap_monthly_peak",
  "months": [4, 5, 6, 7, 8, 9, 10]
}
```

**Example - Time-Windowed Power Tariff:**
```json
"power_tariff": {
  "applies": true,
  "capacity_definition": "sub_cap_window_peak",
  "months": [4, 5, 6, 7, 8, 9, 10],
  "time_window": {
    "start_hour": 6,
    "end_hour": 22
  }
}
```

### High-Load Power Configuration

**Required Fields:**
- `applies` (boolean) - Whether high-load tariff is active

**Optional Fields:**
- `months` (array) - High-load months (typically November-March)
- `calculation` (string) - Calculation method (see supported calculations above)
- `n_months` (int) - Number of months to average (for `_avg_of_n` methods)
- `time_window` (object) - Time window for peak detection
  - `start_hour` (int) - Starting hour (0-23)
  - `end_hour` (int) - Ending hour (0-23)
- `kWh_period_applies` (boolean) - Whether to use this as energy pricing period (independent of power charge)
- `kWh_period_window` (object) - Separate time window for energy pricing classification

**Example - Basic High-Load Tariff:**
```json
"highload_power": {
  "applies": true,
  "months": [11, 12, 1, 2, 3],
  "calculation": "window_peak",
  "time_window": {
    "start_hour": 6,
    "end_hour": 22
  }
}
```

**Example - Average of Monthly Peaks:**
```json
"highload_power": {
  "applies": true,
  "months": [11, 12, 1, 2, 3],
  "calculation": "high_load_annual_peak_avg_of_n",
  "n_months": 5,
  "time_window": {
    "start_hour": 6,
    "end_hour": 22
  }
}
```

**Example - Separate Energy/Power Windows:**
```json
"highload_power": {
  "applies": true,
  "months": [11, 12, 1, 2, 3],
  "calculation": "high_load_annual_peak_avg_of_n",
  "n_months": 2,
  "time_window": {
    "start_hour": 0,
    "end_hour": 23
  },
  "kWh_period_applies": true,
  "kWh_period_window": {
    "start_hour": 6,
    "end_hour": 22
  }
}
```

In this example:
- Power charge calculated using all hours (0-23)
- Energy pricing uses high/low classification based on 6-22 window

## Main Functions Reference

### Core Modules

#### TariffLogic.py
Pure tariff calculation functions with no side effects. All functions are deterministic and operate only on provided inputs.

**Key Functions:**
- `getAnnualPeak(loadProfile_df, scenario)` - Returns maximum hourly load for the year
- `getMonthlyPeak(loadProfile_df, scenario, month)` - Returns maximum hourly load for a specific month
- `compute_window_peak(loadProfile_df, scenario, start_hour, end_hour, months)` - Computes peak within time window and optional month restriction
- `get_highload_months(tariff_rules, RE)` - Returns configured high-load months for a DSO
- `compute_highload_peak_window(loadProfile_df, scenario, tariff_rules, RE, month)` - Computes high-load peak within configured time window
- `compute_highload_peak_monthly_avg(loadProfile_df, scenario, tariff_rules, RE)` - Average of monthly peaks across high-load months
- `compute_avg_of_n_peaks_monthly(loadProfile_df, scenario, month, n)` - Average of n highest peaks in a month
- `compute_avg_of_n_peaks_in_window(loadProfile_df, scenario, tariff_rules, RE, month, n)` - Average of n highest peaks within time window
- `compute_avg_of_n_highload_monthly_peaks_in_window(loadProfile_df, scenario, tariff_rules, RE, n)` - Average of n highest monthly peaks within high-load window
- `is_highload_hour_from_tariff(tariff_rules, RE, month, hour)` - Checks if hour is high-load for energy pricing

#### PriceComponents.py
Pricing component calculators that use TariffLogic functions to compute costs.

**Key Functions:**
- `taxAndfixedFee_ScaledByLoad_Yearly(networkPrices_df, RE, loadProfile_df, scenario, totalPrice_df)` - Computes annual taxes and fixed fees distributed across hours
- `kWCharge_ScaledByLoad_Monthly(networkPrices_df, RE, month, loadProfile_df, scenario, totalPrice_df, tariff_rules, annual_peaks, highload_peaks)` - Computes monthly power charges based on capacity definition
- `kWhCharge_ScaledByLoad_Hourly(networkPrices_df, RE, loadProfile_df, scenario, totalPrice_df, tariff_rules)` - Computes hourly energy charges with high/low load differentiation
- `spotCharge_Monthly(elspot_df, RE, loadProfile_df, scenario, totalPrice_df, biddingArea)` - Computes spot market electricity costs

**Supported Capacity Definitions:**
- `sub_cap_monthly_peak` - Monthly peak load
- `sub_cap_annual_peak` - Annual peak load  
- `sub_cap_avg_of_three_peaks` - Average of 3 highest peaks in month (all hours)
- `sub_cap_avg_of_three_peaks_off_peak` - Average of 3 highest peaks outside high-load period
- `sub_cap_window_peak` - Peak within configured time window and optional month restriction
- `sub_cap_annual_avg_of_two_peaks` - Annual average of 2 highest monthly peaks

**Supported High-Load Calculations:**
- `window_peak` - Peak within configured time window for the month
- `high_load_annual_peak` - Average of monthly peaks across high-load months
- `high_load_monthly_peak_avg_of_two` - Average of 2 highest monthly peaks within high-load window
- `high_load_monthly_peak_avg_of_n` - Average of n highest monthly peaks within high-load window
- `high_load_annual_peak_avg_of_two` - Average of 2 highest monthly peaks (annual billing)
- `high_load_annual_peak_avg_of_n` - Average of n highest monthly peaks (annual billing)
- `high_load_window_peak_avg_of_three` - Average of 3 highest peaks within time window
- `high_load_window_peak_avg_of_two` - Average of 2 highest peaks within time window

### GridPriceScaledByLoad.py

**`main(effectCustomerType, biddingArea, studyArea, loadProfile_raw_df, yearList)`**
- Primary execution function that orchestrates the full analysis pipeline
- Loads tariff rules, pricing data, and processes all specified years and scenarios
- Writes results to `loadProfileAllYears.csv`, `totalCost_AllYears.csv`, and `totalCost_24hour_AllYears.csv`
- **Parameters:**
  - `effectCustomerType` (int): Customer type (1, 2, 3)
  - `biddingArea` (str): Bidding area code (SE1-SE4)
  - `studyArea` (DataFrame): Regional configuration with DSO mappings
  - `loadProfile_raw_df` (DataFrame): 24-hour load profile
  - `yearList` (list): Years to process
- **Returns:** Tuple of 3 DataFrames (totalCost_allYears_df, totalCost_24hour_df, loadProfile_allYears_df)

**`reshapeLoadProfile(loadProfile_df, year)`**
- Accepts either 24-hour or 8760-hour load profile and normalizes to 8760 hours with timestamps and metadata
- Adds Year, Month, Day, Hour, Season (Winter/Spring/Summer/Fall), DayType (Weekday/Weekend)
- Handles leap years (skips Feb 29)
- **Parameters:**
  - `loadProfile_df` (DataFrame): Load profile with 'Load (kWh)' column (24 or 8760 rows)
  - `year` (int): Year for timestamp generation
- **Returns:** DataFrame with 8760 rows and `Load (kWh)` column

**`isHighLoadMonth(month)`**
- Determines if month is high-load period (Nov-Mar)
- **Parameters:** `month` (int): Month number (1-12)
- **Returns:** Boolean (True = Nov-Mar)

**`isHighLoadTime(df, RE, month, day, hour)`**
- Checks if specific hour is high-load for regional entity (legacy method)
- **Parameters:** RE (str), month/day/hour (int)
- **Returns:** Boolean

**`calculatorInput(networkPrices_df, highload_df, RElist, loadProfile_df, scenario, elspot_df, biddingArea, tariff_rules=None)`**
- Computes all price components (taxes, kW charges, kWh charges, spot prices, high-load power)
- **Returns:** Tuple of 5 DataFrames (taxes_df, kW_df, kWh_df, highload_df, spot_df)

### FileManagement.py

**`readElspotPrices(year, biddingArea)`**
- Loads hourly spot prices from Vattenfall source
- Routes automatically to correct data location
- **Returns:** DataFrame with 8760 rows in SEK/MWh

**`readEffectCustomerPrices_2025(effectCustomerType, year)`**
- Loads network tariffs for specified customer type and year
- **Returns:** DataFrame indexed by RE with tariff columns

**`readHighloadtime()`**
- Loads high-load hour definitions
- **Returns:** DataFrame indexed by RE

**`readStudyAreas(sheet_name)`**
- Loads study area (municipality/DSO) configuration
- **Returns:** DataFrame with regional mappings

**`readLoadProfile(filepath)`**
- Loads 24-hour load profile from Excel
- **Returns:** 24-row DataFrame with load values

## Testing

Test the main function and load profile expansion:
```python
from GridPriceScaledByLoad import reshapeLoadProfile, main
from FileManagement import readStudyAreas, readLoadProfile
import pandas as pd

# Test 1: Load profile expansion
test_profile = pd.DataFrame({
    'Hour': range(24),
    'Load (kWh)': [1.0] * 24
})

expanded = reshapeLoadProfile(test_profile, year=2024)

assert len(expanded) == 8760, "Should have 8760 hours"
assert expanded['Season'].nunique() == 4, "Should have 4 seasons"
assert set(expanded['Season']) == {'Winter', 'Spring', 'Summer', 'Fall'}
assert set(expanded['DayType']) == {'Weekday', 'Weekend'}

# Verify no Feb 29 in leap year
feb_dates = expanded[expanded['Month'] == 2]['Day'].unique()
assert 29 not in feb_dates, "Should skip Feb 29"

print("✓ Load profile expansion tests passed")

# Test 2: Main function execution (with minimal parameters)
try:
    studyArea = readStudyAreas('Sheet1')
    loadProfile_raw_df = readLoadProfile('data/EV-bus-charging-needs-Arsalan.xlsx')
    
    totalCost, totalCost_24h, loadProfile = main(
        effectCustomerType=2,
        biddingArea='SE3',
        studyArea=studyArea,
        loadProfile_raw_df=loadProfile_raw_df,
        yearList=[2024]
    )
    
    assert len(totalCost) > 0, "Should have results"
    assert 'Total Cost (DSO)' in totalCost.columns, "Should have cost column"
    assert len(loadProfile) > 0, "Should have load profile results"
    
    print("✓ Main function execution test passed")
except Exception as e:
    print(f"✗ Main function test failed: {e}")
```

## Tips & Best Practices

1. **Modular Architecture**
   - TariffLogic.py contains pure functions - safe to use independently
   - PriceComponents.py delegates to TariffLogic - use for integrated pricing
   - Import specific functions when you need fine-grained control
   - Use `main()` in GridPriceScaledByLoad.py for full pipeline execution

2. **Tariff Configuration**
   - Start with simple `applies: true/false` before adding complexity
   - Use `months` array to restrict tariffs to specific periods
   - `time_window` restricts when peaks are measured
   - `kWh_period_applies` separates energy classification from power charging
   - Test each DSO individually before processing full dataset
   - Validate JSON with a linter to catch syntax errors early

3. **Programmatic Usage**
   - Use `main()` function for programmatic access to results
   - Function returns tuples of DataFrames for further analysis
   - Avoids file I/O overhead if chaining multiple analyses
   - Import individual functions from TariffLogic for custom calculations

4. **Validate Input Data First**
   - Check for missing values in key columns
   - Verify units (öre/kWh vs SEK/MWh)
   - Ensure years in data match `yearList`
   - Validate tariff rules JSON for syntax and DSO consistency

5. **Use Dry-Run Mode**
   - Test with single year before processing multi-year range
   - Process small subset of DSOs first to verify pipeline
   - Check output files for expected columns and data ranges

6. **Monitor Data Sources**
   - Electricity wholesale prices
      - Vattenfall data no longer available for public download
      - ElspotNu data no longer available for public download
      - Adding years further in the future requires alternative data sources
   - Concession tariff data updated annually—check for new versions
   - High-load rules may vary by DSO—validate with tariff provider

7. **Unit Consistency**
   - All spot prices normalized to SEK/MWh for calculations
   - Network tariffs expected in öre/kWh (converted in code)
   - Output prices in SEK/kWh unless otherwise noted
   - Verify conversions in source code if extending

8. **Regional Entity (RE) Mapping**
   - RE created as combination of REnummer + REnamn in tariff data
   - Must match consistently across all data sources
   - Verify municipality codes match Swedish standard (CommCode)
   - Check for stale RE mappings when processing historical data

9. **Performance Optimization**
   - Vectorized kWh price assignment (FastPath) reduces per-hour overhead
   - Pre-computed annual and high-load peaks cache expensive calculations
   - For large regional sets, consider processing in batches by year

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

### Version 3.0 (March 2026)
**Major Refactoring - Modular Architecture:**
- Extracted TariffLogic.py with pure tariff calculation functions
- Extracted PriceComponents.py with pricing component calculators
- GridPriceScaledByLoad.py now orchestrates via delegation to specialized modules
- All tariff logic functions now side-effect-free and deterministic

**Enhanced Tariff Configuration:**
- Implemented `sub_cap_window_peak` capacity definition with time window and month restrictions
- Added month-based tariff restrictions (`power_tariff.months`)
- Added time window support for power tariffs (`power_tariff.time_window`)
- Implemented `kWh_period_applies` flag for independent energy period classification
- Added `kWh_period_window` for separate energy pricing time windows
- Support for dual-season power structures (ordinary + high-load)

**New Calculation Methods:**
- `high_load_annual_peak_avg_of_n` - Average of n highest monthly peaks (annual billing)
- `high_load_window_peak_avg_of_three` - Average of 3 highest peaks within window
- `high_load_window_peak_avg_of_two` - Average of 2 highest peaks within window
- `compute_window_peak()` - Peak detection with time/month restrictions
- `compute_avg_of_n_highload_monthly_peaks_in_window()` - Advanced peak averaging

**JSON Configuration Simplification:**
- Removed documentation-only fields: `note`, `type`, `billing_frequency`, `price_unit`
- Standardized field ordering: `applies` first, `capacity_definition` second
- File size reduced by ~15% while maintaining full functionality

**Documentation:**
- Comprehensive tariff configuration guide
- Detailed module reference for TariffLogic and PriceComponents
- Examples for all capacity definitions and high-load calculations
- Updated API documentation with new function signatures

### Version 2.1 (Feb 2026)
- Refactored main execution into `main()` function with explicit parameters
- Added `if __name__ == '__main__':` guard for standalone CLI execution
- Implemented vectorized kWh price assignment for improved performance
- Added comprehensive docstrings to peak calculation and tariff functions
- Added support for RE-specific tariff rules via `DsoTariffStructures.json`
- Introduced high-load power charge calculations with "window_peak" and "monthly_peak" methods
- Added 24-hour cost redistribution output (`totalCost_24hour_AllYears.csv`)
- Updated all module docstrings for clarity and maintainability
- Returns DataFrames from `main()` for programmatic use

### Version 2.0 (Nov 2025)
- Refactored `reshapeLoadProfile()` to generate timestamps dynamically
- Implemented proper leap year handling (skip Feb 29)
- Added weekday/weekend differentiation
- Removed dependency on static 8760hours.xlsx file
