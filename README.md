# Electricity Grid Price Calculator

## Overview
This project calculates electricity wholesale and grid costs given a load profile for different distribution system operators (DSOs) in Sweden. It handles various components of electricity pricing including taxes, fixed fees, power charges, and energy charges. The system is designed to analyze electricity costs for different DSOs and load patterns over multiple years.

## Key Features
- **Price Components:** Taxes, fixed fees, power charges, energy charges, and spot prices
- **Multi-Year Support:** Process 2019-2024 with different data sources per year
- **Flexible Load Profile Input:** Accept either 24-hour templates (auto-expanded to 8760) or full 8760-hour profiles
- **Seasonal Pricing:** Winter, Spring, Summer, Fall pricing differentiation
- **Weekday/Weekend Differentiation:** Different tariffs for workdays vs weekends
- **Leap Year Handling:** Automatically skips Feb 29 for leap years
- **DST Handling:** Automatic daylight saving time transition management

## Project Structure
```
Transmogrifier/
│
├── Main.py                           # Main orchestration pipeline
├── FileManagement.py                 # File I/O and data loading helpers
├── FilterSpace.py                    # Regional spatial filtering
├── PriceComponents.py                # Pricing component calculators
├── ProcessData.py                    # Data processing utilities
├── TariffLogic.py                    # Pure tariff calculation functions
├── README.md                         # This file
│
├── data/                             # Input data directory
│   ├── dsoTariffStructures.json      # Tariff rules configuration
│   ├── concession areas/             # Concession areas shapefile sets
│   │   ├── 2023/                     
│   │   ├── 2024/                     
│   │   └── 2025/                     
│   ├── elspot_prices/
│   │   └── Vattenfall-data/          
│   │       ├── 2019/SE1-4/*.xlsx     
│   │       ├── 2020/SE1-4/*.xlsx
│   │       ├── 2021/SE1-4/*.xlsx
│   │       ├── 2022/SE1-4/*.xlsx
│   │       ├── 2023/SE1-4/*.xlsx
│   │       └── 2024/SE1-4/*.xlsx
│   └── effektkunder-1999-2025.xlsx   # (network tariffs)
│
├── input/
│   └── studyarea.xlsx                (study area configuration)
│
└── output/                           # Generated results
```

## Prerequisites
- Python 3.8+
- Required packages:
  - numpy >= 1.21.0
  - pandas >= 1.3.0
  - openpyxl

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
- **Required Columns:**
  - `DSO (short)`
  - `DSO (long)`
  - `RE + subgroup (YYYY)`
  - `BiddingArea`
- **Note:** Every RE in each processed year must map to exactly one bidding area.
- **How to choose REs:** Use the concession maps in `data/concession areas/{YEAR}/` to decide which network concession areas (and corresponding REs) should be included in your study area file before running the analysis.

#### <ins>Provided Data Files</ins>
**1. Electricity Spot Prices** 
- **Includes:** Electricity spot pricing data for all four Swedish bidding areas (SE1-SE4), 2019-2024
- **Source:** Vattenfall
- **Location:** `data/elspot_prices/Vattenfall-data/{YEAR}/{BIDDING_AREA}/`
- **Files:** `data.xlsx`, `data(1).xlsx` through `data(52).xlsx`
- **Structure:** Tidsperiod (timestamp) and Pris (öre/kWh)
- **Processing:** Automatically converted to SEK/MWh (multiply by 10)

**2. Network Tariff Data**
- **Includes:** Authority fees, fixed fees, subscribed capacity costs, energy charges
- **Source:** Swedish Energy Market Inspectorate (EI)
- **File:** `data/effektkunder-1999-2025.xlsx`
- **Structure:** Multi-level indexed (RE number × Year × CustomerType)
  - RE number: Reporting entity (Swedish: Redovisningsenhet) under which a DSO reports to EI. Together with groupname serves as a unique identifier
  - Customer Types: 1 (100 kW, 350 MWh/year), 2 (1 MW, 5 GWh/year), 3 (20 MW, 140 GWh/year)
  - Years: 1999-2025
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

**4. Network Concession Area Maps (Reference Data)**
- **Includes:** GIS shapefiles for Swedish network concession areas for 2023-2025
- **Location:** `data/concession areas/{YEAR}/`
- **Files:** Standard shapefile components (`.shp`, `.dbf`, `.shx`, `.prj`, etc.)
- **Use in this project:** Reference input for selecting relevant REs/DSOs in your study area setup. These maps are not read by the calculation code directly.

### Data Format Notes
- **Price Units:** Expects both öre/kWh and SEK/MWh; automatic conversion
  - öre/kWh → SEK/MWh: multiply by 10
  - öre/kWh → SEK/kWh: divide by 100
- **Bidding Areas:** SE1, SE2, SE3, SE4
- **Years Supported:** 2019-2024 (with different data sources)
- **Regional Entities:** Defined by RE + subgroup in tariff data
- **Time Handling:** All times treated as local time; DST handled automatically

## Usage

### Running the Analysis

Open [Main.py](Main.py) in your IDE and modify the parameters in the `main()` function:

```python
def main():
    effectCustomerType = 2  # Possible 1, 2, 3
    studyArea = fm.readStudyAreas('Sheet1')
    loadProfile = fm.readLoadProfile('input/test-load.xlsx', 'Sheet1')
    yearList = [2024]

    runCalculations(effectCustomerType = effectCustomerType, 
                    studyArea = studyArea, 
                    loadProfile=loadProfile,
                    yearList = yearList)
```

Then run [Main.py](Main.py) from your IDE. Results will be written to the `output/` directory.

### Helper Functions

**Load electricity prices:**
```python
from FileManagement import readElspotPrices_Vattenfall

# Loads Vattenfall spot price data for the selected year and bidding area
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

### totalCost_AllYears.csv
Full hourly cost breakdown by municipality (8760 rows per year × DSO):
- **Year:** Processing year
- **Season:** Seasonal aggregation (Winter/Spring/Summer/Fall)
- **Month:** Month number (1-12)
- **Hour:** Hour of day (0-23)
- **DSO (short):** Distribution system operator short code
- **RE:** Regional entity identifier
- **DSO (long):** Company name (DSO long name)
- **Load profile (kWh):** Hourly load values
- **Total Cost (DSO):** Sum of all DSO costs for that hour (kr)
- **Fixed fees (DSO):** Fixed annual costs distributed hourly (kr)
- **Power (DSO):** Subscribed capacity charges (kr)
- **Highload power (DSO):** High-load power charges (kr)
- **Energy (DSO):** Network energy charges (kr)
- **Energy (Spot):** Spot market electricity costs (kr)
- **Tax and Fixed Fee (SEK/kWh):** Tax and fixed fee component per kWh
- **kW Fee (SEK/kWh):** Power charge component per kWh
- **kWh Fee (SEK/kWh):** Energy charge component per kWh
- **Highload power (SEK/kWh):** High-load power component per kWh
- **Spot Price (SEK/kWh):** Spot price per kWh
- **Total Price (DSO):** Total DSO price per kWh

## Key Configuration Parameters

Configuration is handled via function parameters in the `main()` function. Edit these values in [Main.py](Main.py) (in the `main()` function):

```python
def main():
    effectCustomerType = 2  # Possible 1, 2, 3
    studyArea = fm.readStudyAreas('Sheet1')
    loadProfile = fm.readLoadProfile('input/test-load.xlsx', 'Sheet1')
    yearList = [2024]

    runCalculations(effectCustomerType = effectCustomerType, 
                    studyArea = studyArea, 
                    loadProfile=loadProfile,
                    yearList = yearList)
```

**Parameter Details:**
- **effectCustomerType:** Integer (1, 2, or 3) indicating customer consumption level for tariff selection
- **studyArea:** DataFrame with DSO/RE mappings and per-RE bidding area assignments
- **loadProfile:** DataFrame with load profile (24 or 8760 rows with 'Load (kWh)' column)
- **yearList:** List of years to process (e.g., `[2023, 2024]`)

## Tariff Configuration Guide

### JSON Structure Overview

The `DsoTariffStructures.json` file defines how tariffs are calculated for each DSO. Each entry consists of:

1. **`power_tariff`** - Regular power (capacity) charges
2. **`highload_power`** - High-load period power charges

### Power Tariff Configuration

**Required Fields:**
- `applies` (boolean) - Whether power tariff is active

**Required Fields (when `applies: true`):**
- `capacity_definition` (string) - How to calculate capacity charge

**Optional Fields:**
- `months` (array) - Restrict tariff to specific months (1-12)
- `time_window` (object) - Restrict tariff to specific hours (required for `sub_cap_window_peak`)
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

**Required Fields (when `applies: true`):**
- `months` (array) - High-load months (typically November-March: [11, 12, 1, 2, 3])
- `time_window` (object) - Time window for peak detection
  - `start_hour` (int) - Starting hour (0-23)
  - `end_hour` (int) - Ending hour (0-23)

**Optional Fields:**
- `calculation` (string) - Calculation method (default: `window_peak`). See supported calculations below.
- `n_months` (int) - Number of months to average (required for `high_load_annual_peak_avg_of_n` and `high_load_monthly_peak_avg_of_n`)
- `kWh_period_applies` (boolean) - Whether to use this as energy pricing period (independent of power charge)
- `kWh_period_window` (object) - Separate time window for energy pricing classification
  - `start_hour` (int) - Starting hour (0-23)
  - `end_hour` (int) - Ending hour (0-23)

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

#### Main.py

**`main()`**
- Entry point that orchestrates the full analysis pipeline
- Loads tariff rules, pricing data, and processes all specified years
- Uses bidding area assignments from `studyArea` per RE (not one global bidding area)
- Writes results to `totalCost_AllYears.csv`
- **Parameters:** None (configured in the function body)
- **Returns:** None

**`runCalculations(effectCustomerType, studyArea, loadProfile, yearList)`**
- Internal orchestration function called by `main()`
- Loads tariff rules, pricing data, and processes all specified years
- Uses bidding area assignments from `studyArea` per RE
- **Parameters:**
  - `effectCustomerType` (int): Customer type (1, 2, 3)
  - `studyArea` (DataFrame): Regional configuration with DSO/RE and bidding area mappings
  - `loadProfile` (DataFrame): Load profile with `Load (kWh)` column (24 or 8760 rows)
  - `yearList` (list): Years to process
- **Returns:** None (writes output files)

**`calculatorInput(networkPrices_df, highload_df, RElist, loadProfile_df, scenario, elspot_prices_by_area, re_bidding_areas, tariff_rules=None)`**
- Computes all price components (taxes, kW charges, kWh charges, spot prices, high-load power)
- **Returns:** Tuple of 5 DataFrames (taxes_df, kW_df, kWh_df, highload_df, spot_df)


#### TariffLogic.py
Pure tariff calculation functions with no side effects. All functions are deterministic and operate only on provided inputs.

**Key Functions:**
- `daysInMonth(year, month)` - Returns number of days in a given month/year (handles leap years)
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
- `calculateNetworkPrice_RElist(networkPrices_df, RElist, loadProfile_df, scenario, tariff_rules=None)` - Computes all network price components for a list of REs. Returns tuple of (taxes_df, kW_df, kWh_df, highload_df)
- `taxAndfixedFee_ScaledByLoad_Yearly(networkPrices_df, RE, loadProfile_df, scenario, taxesAndFixedFees_prices_df)` - Computes annual taxes and fixed fees distributed across hours
- `kWCharge_ScaledByLoad_Monthly(networkPrices_df, RE, month, loadProfile_df, scenario, kWCharge_prices_df, tariff_rules, annual_peaks, highload_peaks)` - Computes monthly power charges based on capacity definition
- `kWhCharge_ScaledByLoad_Hourly(networkPrices_df, tariff_rules, RE, month, day, hour, loadProfile_df, kWhCharge_prices_df)` - Computes hourly energy charges with high/low load differentiation
- `calculateElectricityPrice_8760(elspot_prices_by_area, RElist, re_bidding_areas, loadProfile_df)` - Computes hourly spot market electricity costs for all REs based on their bidding areas

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

#### ProcessData.py

**`reshapeLoadProfile(loadProfile_df, year)`**
- Accepts either 24-hour or 8760-hour load profile and normalizes to 8760 hours with timestamps and metadata
- Adds Year, Month, Day, Hour, Season (Winter/Spring/Summer/Fall), DayType (Weekday/Weekend)
- Handles leap years (skips Feb 29)
- **Parameters:**
  - `loadProfile_df` (DataFrame): Load profile with 'Load (kWh)' column (24 or 8760 rows)
  - `year` (int): Year for timestamp generation
- **Returns:** DataFrame with 8760 rows and `Load (kWh)` column

#### FileManagement.py

**`readElspotPrices(year, biddingArea)`**
- Loads hourly spot prices from primary source
- Removes Feb 29 for leap years (returns 8760 rows)
- **Returns:** DataFrame with 8760 rows in SEK/MWh

**`readElspotPrices_Vattenfall(year, biddingArea)`**
- Loads hourly spot prices from Vattenfall source
- Routes automatically to correct data location
- Removes Feb 29 for leap years (returns 8760 rows)
- **Returns:** DataFrame with 8760 rows in SEK/MWh

**`readEffectCustomerPrices_2025(effectCustomerType, year)`**
- Loads network tariffs for specified customer type and year
- **Returns:** DataFrame indexed by RE with tariff columns

**`readStudyAreas(sheet_name)`**
- Loads study area (municipality/DSO) configuration
- **Returns:** DataFrame with regional mappings

**`readLoadProfile(filepath, sheet_name)`**
- Loads load profile from Excel file
- **Returns:** DataFrame with load values


## Tips & Best Practices

1. **Modular Architecture**
   - TariffLogic.py contains pure functions - safe to use independently
   - PriceComponents.py delegates to TariffLogic - use for integrated pricing
   - ProcessData.py contains data transformation utilities
   - FilterSpace.py handles regional configuration and filtering
   - Run [Main.py](Main.py) for full pipeline execution

2. **Tariff Configuration**
   - Start with simple `applies: true/false` before adding complexity
   - Use `months` array to restrict tariffs to specific periods
   - `time_window` restricts when peaks are measured
   - `kWh_period_applies` separates energy classification from power charging
   - Test each DSO individually before processing full dataset
   - Validate JSON with a linter to catch syntax errors early

3. **IDE-Based Workflow**
   - Edit parameters directly in [Main.py](Main.py) `if __name__ == '__main__':` block
   - Run [Main.py](Main.py) from your IDE to execute the analysis
   - Results are written to `output/` directory
   - Import individual functions from TariffLogic or ProcessData for custom analyses

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
