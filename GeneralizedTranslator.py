import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Literal


def transmogrify(
        source_df: pd.DataFrame,
        source_id: str,
        target_id: str,
        weights: pd.DataFrame,
        val_cols: List[str],
        val_operators: Optional[Dict[str, Literal["sum", "mean", "rate"]]] = None,
        denom_cols: Optional[Dict[str, str]] = None
    ):
    """
        Transforms and aggregates values from a source DataFrame to a target ID using weighted contributions.

        Parameters:
        ----------
        source_df : pd.DataFrame
            The source data containing values to be transformed.
        source_id : str
            Column name in both `source_df` and `weights` representing the source entity.
        target_id : str
            Column name in `weights` representing the target entity to which values are mapped.
        weights : pd.DataFrame
            A DataFrame containing mapping weights between source and target IDs. Must include columns:
            [source_id, target_id, "weight"].
        val_cols : List[str]
            List of column names in `source_df` to be transformed.
        val_operators : Optional[Dict[str, Literal["sum", "mean", "rate"]]], default=None
            Dictionary specifying the aggregation method for each value column. If not provided, defaults to "sum".
            - "sum": weighted sum
            - "mean": weighted average
            - "rate": weighted rate (requires `denom_cols`)
        denom_cols : Optional[Dict[str, str]], default=None
            Dictionary mapping value columns to their denominator columns (used for "rate" or "mean" operations).

        Returns:
        -------
        pd.DataFrame
            A DataFrame indexed by `target_id` containing the aggregated/transformed values.
    """
    # Extract relevant columns from weights and source data
    w = weights[[source_id, target_id, "weight"]].copy()
    src = source_df[[source_id] + val_cols + ([] if denom_cols is None else list(denom_cols.values()))].copy()

    # Merge weights with source data on source_id
    df = w.merge(src, on=source_id, how="left") # TODO: is this correct? check so that concat behaves as it should

    # Default to 'sum' if no operators are provided
    if val_operators is None:
        val_operators = {c: "sum" for c in val_cols}

    out_parts = []# List to collect transformed columns

    for col in val_cols:
        val_op = val_operators.get(col, "sum")
        if val_op in ("sum"):
            # Weighted sum: multiply value by weight and group by target_id
            contrib = df[[target_id]].copy()
            contrib[col] = df[col] * df["weight"]
            part = contrib.groupby(target_id, dropna=False)[col].sum(min_count=1)
        elif val_op in ("mean", "rate"):
            # Weighted average or rate
            if denom_cols and col in denom_cols:
                # Weighted numerator and denominator
                denom_col = denom_cols[col]
                num = (df[col] * df[denom_col] * df["weight"]).groupby(df[target_id], dropna=False).sum(min_count=1)
                den = (df[denom_col] * df["weight"]).groupby(df[target_id], dropna=False).sum(min_count=1)
                part = num / den
            else:
                # Simple weighted average
                num = (df[col] * df["weight"]).groupby(df[target_id], dropna=False).sum(min_count=1)
                den = (df["weight"]).groupby(df[target_id], dropna=False).sum(min_count=1)
                part = num / den
            part.name = col # Name the resulting Series
        else:
            raise ValueError(f"Unknown value type for column '{col}': {val_operators}")
        out_parts.append(part)

    # Combine all transformed columns into a single DataFrame
    result = pd.concat(out_parts, axis=1)
    result.index.name = target_id
    return result.reset_index() # Return with target_id as a column


def create_source_df():
    return pd.DataFrame({
        "SPACE_SRC": ["S1", "S2", "S3"],
        "population": [100, 50, 75],
        "households": [40, 20, 25],
        "median_income": [30000, 40000, 35000],
        "denominator": [10, 5, 7]
    })


def create_space_weights_df():
    return pd.DataFrame({
        "SPACE_SRC": ["S1", "S1", "S2", "S3"],
        "SPACE_TGT": ["SIGMA1", "SIGMA2", "SIGMA2", "SIGMA3"],
        "weight": [0.4, 0.6, 1.0, 1.0]
    })


def create_time_weights_df():
    """
    Creates a sample time weights DataFrame for mapping source time slices to target time slices.
    Useful for testing non-uniform time transformations (e.g., month → day).
    """
    return pd.DataFrame({
        "TIME_SRC": ["M1", "M1", "M2", "M2"],
        "TIME_TGT": ["D1", "D2", "D2", "D3"],
        "weight": [0.6, 0.4, 0.7, 0.3]
    })


def transmogrify_by_group(
        source_df: pd.DataFrame,
        group_col: str,
        source_id: str,
        target_id: str,
        weights: pd.DataFrame,
        val_cols: List[str],
        val_operators: Optional[Dict[str, Literal["sum", "mean", "rate"]]] = None,
        denom_cols: Optional[Dict[str, str]] = None
    ) -> pd.DataFrame:
    """Applies transmogrify within each group (e.g., time slice)."""
    results = []
    for group_val, group_df in source_df.groupby(group_col):
        transformed = transmogrify(
            source_df=group_df,
            source_id=source_id,
            target_id=target_id,
            weights=weights,
            val_cols=val_cols,
            val_operators=val_operators,
            denom_cols=denom_cols
        )
        transformed[group_col] = group_val  # Add back the group info
        results.append(transformed)
    return pd.concat(results, ignore_index=True)

############## TESTS ##############
def test_sum_operator():
    source_df = create_source_df()
    weights = create_space_weights_df()
    val_cols = ["population"]
    val_operators = {"population": "sum"}
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, val_cols, val_operators)
    assert "population" in result.columns
    assert np.isclose(result[result["SPACE_TGT"] == "SIGMA1"]["population"].values[0], 100 * 0.4)


def test_mean_operator():
    source_df = create_source_df()
    weights = create_space_weights_df()
    val_cols = ["median_income"]
    val_operators = {"median_income": "mean"}
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, val_cols, val_operators)
    assert "median_income" in result.columns
    assert np.isclose(result[result["SPACE_TGT"] == "SIGMA1"]["median_income"].values[0], 30000)


def test_rate_operator_with_denominator():
    source_df = create_source_df()
    weights = create_space_weights_df()
    val_cols = ["population"]
    val_operators = {"population": "rate"}
    denom_cols = {"population": "denominator"}
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, val_cols, val_operators, denom_cols)
    assert "population" in result.columns
    assert not result["population"].isnull().any()

def test_single_value_sum():
    source_df = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "population": [100, 200]
    })
    weights = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "SPACE_TGT": ["SIGMA1", "SIGMA1"],
        "weight": [0.5, 0.5]
    })
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, ["population"], val_operators={"population": "sum"})
    assert result["population"].iloc[0] == 150.0


def test_multiple_columns_mixed_operators():
    source_df = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "population": [100, 200],
        "income": [30000, 50000]
    })
    weights = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "SPACE_TGT": ["SIGMA1", "SIGMA1"],
        "weight": [0.5, 0.5]
    })
    val_ops = {"population": "sum", "income": "mean"}
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, ["population", "income"], val_operators=val_ops)
    assert result["population"].iloc[0] == 150.0
    assert result["income"].iloc[0] == 40000.0


def test_missing_val_operators_defaults_to_sum():
    source_df = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "population": [100, 200]
    })
    weights = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "SPACE_TGT": ["SIGMA1", "SIGMA1"],
        "weight": [0.5, 0.5]
    })
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, ["population"])
    assert result["population"].iloc[0] == 150.0
    

def test_missing_denom_cols_fallback_to_weighted_average():
    source_df = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "income": [30000, 50000]
    })
    weights = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "SPACE_TGT": ["SIGMA1", "SIGMA1"],
        "weight": [0.25, 0.75]
    })
    val_ops = {"income": "mean"}
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, ["income"], val_operators=val_ops)
    expected_income = (30000 * 0.25 + 50000 * 0.75) / (0.25 + 0.75)
    assert np.isclose(result["income"].iloc[0], expected_income)


def test_missing_values():
    source_df = create_source_df()
    source_df.loc[0, "population"] = np.nan
    weights = create_space_weights_df()
    val_cols = ["population"]
    val_operators = {"population": "sum"}
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, val_cols, val_operators)
    assert "population" in result.columns


def test_zero_weights():
    source_df = create_source_df()
    weights = create_space_weights_df()
    weights["weight"] = 0.0
    val_cols = ["population"]
    val_operators = {"population": "sum"}
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, val_cols, val_operators)
    assert result["population"].sum() == 0.0


def test_empty_inputs():
    source_df = pd.DataFrame(columns=["SPACE_SRC", "population"])
    weights = pd.DataFrame(columns=["SPACE_SRC", "SPACE_TGT", "weight"])
    val_cols = ["population"]
    val_operators = {"population": "sum"}
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, val_cols, val_operators)
    assert result.empty


def test_unmatched_source_ids():
    source_df = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "population": [100, 200]
    })
    weights = pd.DataFrame({
        "SPACE_SRC": ["S1", "S3"],  # S3 not in source_df
        "SPACE_TGT": ["SIGMA1", "SIGMA2"],
        "weight": [0.5, 0.5]
    })
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, ["population"])
    assert "population" in result.columns
    assert result["population"].isnull().any()

    
def test_duplicate_mappings():
    source_df = pd.DataFrame({
        "SPACE_SRC": ["S1"],
        "population": [100]
    })
    weights = pd.DataFrame({
        "SPACE_SRC": ["S1", "S1"],
        "SPACE_TGT": ["SIGMA1", "SIGMA1"],
        "weight": [0.3, 0.7]
    })
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, ["population"])
    assert np.isclose(result["population"].iloc[0], 100.0)


def test_all_weights_nan():
    source_df = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "population": [100, 200]
    })
    weights = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "SPACE_TGT": ["SIGMA1", "SIGMA1"],
        "weight": [np.nan, np.nan]
    })
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, ["population"])
    assert result["population"].isnull().all()


def test_non_uniform_time_weights():
    source_df = pd.DataFrame({
        "TIME_SRC": ["M1", "M1", "M2", "M2"],
        "population": [100, 150, 200, 250]
    })
    weights = pd.DataFrame({
        "TIME_SRC": ["M1", "M1", "M2", "M2"],
        "TIME_TGT": ["D1", "D2", "D2", "D3"],
        "weight": [0.6, 0.4, 0.7, 0.3]
    })
    val_cols = ["population"]
    val_operators = {"population": "sum"}
    result = transmogrify(source_df, "TIME_SRC", "TIME_TGT", weights, val_cols, val_operators)
    assert "population" in result.columns
    assert not result["population"].isnull().any()
    assert set(result["TIME_TGT"]) == {"D1", "D2", "D3"}


def test_space_then_time_chaining():
    source_df = pd.DataFrame({
        "SPACE_SRC": ["S1", "S1", "S2", "S2", "S3", "S3"],
        "TIME_SRC": ["T1", "T2", "T1", "T2", "T1", "T2"],
        "population": [100, 110, 50, 55, 75, 80],
        "households": [40, 42, 20, 22, 25, 27],
        "median_income": [30000, 31000, 40000, 40500, 35000, 35500],
    })

    space_weights = pd.DataFrame({
        "SPACE_SRC": ["S1", "S1", "S2", "S3"],
        "SPACE_TGT": ["SIGMA1", "SIGMA2", "SIGMA2", "SIGMA3"],
        "weight": [0.4, 0.6, 1.0, 1.0]
    })

    time_weights = pd.DataFrame({
        "TIME_SRC": ["T1", "T1", "T2", "T2"],
        "TIME_TGT": ["T_combined", "T_combined", "T_combined", "T_combined"],
        "weight": [0.5, 0.5, 0.5, 0.5]
    })

    val_ops = {
        "population": "sum",
        "households": "sum",
        "median_income": "mean"
    }

    # Step 1: Space transformation grouped by TIME
    space_results = []
    for time_val, group_df in source_df.groupby("TIME_SRC"):
        transformed = transmogrify(
            source_df=group_df,
            source_id="SPACE_SRC",
            target_id="SPACE_TGT",
            weights=space_weights,
            val_cols=["population", "households", "median_income"],
            val_operators=val_ops
        )
        transformed["TIME_SRC"] = time_val
        space_results.append(transformed)
    space_transformed = pd.concat(space_results, ignore_index=True)

    # Step 2: Time transformation grouped by TGT
    time_results = []
    for tgt_val, group_df in space_transformed.groupby("SPACE_TGT"):
        transformed = transmogrify(
            source_df=group_df,
            source_id="TIME_SRC",
            target_id="TIME_TGT",
            weights=time_weights,
            val_cols=["population", "households", "median_income"],
            val_operators=val_ops
        )
        transformed["SPACE_TGT"] = tgt_val
        time_results.append(transformed)
    final_result = pd.concat(time_results, ignore_index=True)

    assert set(final_result["TIME_TGT"]) == {"T_combined"}
    assert set(final_result["SPACE_TGT"]) == {"SIGMA1", "SIGMA2", "SIGMA3"}
    assert not final_result.isnull().any().any()


def test_time_then_space_chaining():
    source_df = pd.DataFrame({
        "SPACE_SRC": ["S1", "S1", "S2", "S2", "S3", "S3"],
        "TIME_SRC": ["T1", "T2", "T1", "T2", "T1", "T2"],
        "population": [100, 110, 50, 55, 75, 80],
        "households": [40, 42, 20, 22, 25, 27],
        "median_income": [30000, 31000, 40000, 40500, 35000, 35500],
    })

    time_weights = pd.DataFrame({
        "TIME_SRC": ["T1", "T1", "T2", "T2"],
        "TIME_TGT": ["T_combined", "T_combined", "T_combined", "T_combined"],
        "weight": [0.5, 0.5, 0.5, 0.5]
    })

    space_weights = pd.DataFrame({
        "SPACE_SRC": ["S1", "S1", "S2", "S3"],
        "SPACE_TGT": ["SIGMA1", "SIGMA2", "SIGMA2", "SIGMA3"],
        "weight": [0.4, 0.6, 1.0, 1.0]
    })

    val_ops = {
        "population": "sum",
        "households": "sum",
        "median_income": "mean"
    }

    # Step 1: Time transformation grouped by SRC
    time_results = []
    for src_val, group_df in source_df.groupby("SPACE_SRC"):
        transformed = transmogrify(
            source_df=group_df,
            source_id="TIME_SRC",
            target_id="TIME_TGT",
            weights=time_weights,
            val_cols=["population", "households", "median_income"],
            val_operators=val_ops
        )
        transformed["SPACE_SRC"] = src_val
        time_results.append(transformed)
    time_transformed = pd.concat(time_results, ignore_index=True)

    # Step 2: Space transformation
    final_result = transmogrify(
        source_df=time_transformed,
        source_id="SPACE_SRC",
        target_id="SPACE_TGT",
        weights=space_weights,
        val_cols=["population", "households", "median_income"],
        val_operators=val_ops
    )

    assert set(final_result["SPACE_TGT"]) == {"SIGMA1", "SIGMA2", "SIGMA3"}
    assert not final_result.isnull().any().any()



def test_multiindex_input():
    index = pd.MultiIndex.from_tuples([("S1", "T1"), ("S2", "T1")], names=["SPACE_SRC", "TIME_SRC"])
    source_df = pd.DataFrame({
        "population": [100, 200]
    }, index=index).reset_index()
    weights = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "SPACE_TGT": ["SIGMA1", "SIGMA1"],
        "weight": [0.5, 0.5]
    })
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, ["population"])
    assert "population" in result.columns



def test_rate_known_result():
    source_df = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "cases": [10, 20],
        "population": [100, 200]
    })
    weights = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "SPACE_TGT": ["SIGMA1", "SIGMA1"],
        "weight": [1.0, 1.0]
    })
    val_ops = {"cases": "rate"}
    denom_cols = {"cases": "population"}
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, ["cases"], val_operators=val_ops, denom_cols=denom_cols)
    expected_rate = (10 * 100 + 20 * 200) / (100 + 200)
    assert np.isclose(result["cases"].iloc[0], expected_rate)


def test_weighted_average_bias():
    source_df = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "income": [30000, 100000]
    })
    weights = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "SPACE_TGT": ["SIGMA1", "SIGMA1"],
        "weight": [0.9, 0.1]
    })
    val_ops = {"income": "mean"}
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, ["income"], val_operators=val_ops)
    expected_income = (30000 * 0.9 + 100000 * 0.1) / (0.9 + 0.1)
    assert np.isclose(result["income"].iloc[0], expected_income)


def test_column_name_collision():
    source_df = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "weight": [100, 200],  # same name as weight column in weights
        "population": [1000, 2000]
    })
    weights = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "SPACE_TGT": ["SIGMA1", "SIGMA1"],
        "weight": [0.5, 0.5]
    })
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, ["population"])
    assert "population" in result.columns


def test_return_format_consistency():
    source_df = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "population": [100, 200]
    })
    weights = pd.DataFrame({
        "SPACE_SRC": ["S1", "S2"],
        "SPACE_TGT": ["SIGMA1", "SIGMA2"],
        "weight": [1.0, 1.0]
    })
    result = transmogrify(source_df, "SPACE_SRC", "SPACE_TGT", weights, ["population"])
    assert isinstance(result, pd.DataFrame)
    assert "SPACE_TGT" in result.columns


def main():
    test_sum_operator()
    test_mean_operator()
    test_rate_operator_with_denominator()
    test_single_value_sum()
    test_multiple_columns_mixed_operators()
    test_missing_val_operators_defaults_to_sum()
    test_missing_denom_cols_fallback_to_weighted_average()
    test_missing_values()
    test_zero_weights()
    test_empty_inputs()
    test_unmatched_source_ids()
    test_duplicate_mappings()
    test_all_weights_nan()
    test_non_uniform_time_weights()
    test_space_then_time_chaining()
    test_time_then_space_chaining()
    test_multiindex_input()
    test_rate_known_result()
    test_weighted_average_bias()
    test_column_name_collision()
    test_return_format_consistency()    

    print("All tests passed.")


if __name__ == "__main__":
    main() 