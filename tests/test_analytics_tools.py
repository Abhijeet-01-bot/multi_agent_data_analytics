import pandas as pd
import pytest

from tools.analytics_tools import (
    analyze_ranking,
    calculate_contributions,
    calculate_growth,
    calculate_summary_statistics,
    detect_zscore_anomalies,
    rank_records,
    rows_to_dataframe,
)


def build_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "CategoryName": "Beverages",
                "NetRevenue": 1000.0,
            },
            {
                "CategoryName": "Confections",
                "NetRevenue": 800.0,
            },
            {
                "CategoryName": "Seafood",
                "NetRevenue": 200.0,
            },
        ]
    )


def test_rows_to_dataframe() -> None:
    dataframe = rows_to_dataframe(
        [
            {
                "CategoryName": "Beverages",
                "NetRevenue": 1000.0,
            }
        ]
    )

    assert len(dataframe) == 1
    assert "CategoryName" in dataframe.columns
    assert "NetRevenue" in dataframe.columns


def test_summary_statistics() -> None:
    result = calculate_summary_statistics(
        dataframe=build_dataframe(),
        numeric_column="NetRevenue",
    )

    assert result.count == 3
    assert result.minimum == 200.0
    assert result.maximum == 1000.0
    assert result.total == 2000.0

    assert result.mean == pytest.approx(
        666.666666,
        rel=1e-4,
    )


def test_growth_decrease() -> None:
    result = calculate_growth(
        previous_value=100000,
        current_value=88000,
    )

    assert result.absolute_change == -12000
    assert result.percentage_change == -12.0
    assert result.direction == "decrease"


def test_growth_from_zero() -> None:
    result = calculate_growth(
        previous_value=0,
        current_value=100,
    )

    assert result.percentage_change is None
    assert result.warning is not None
    assert result.direction == "increase"


def test_rank_records() -> None:
    result = rank_records(
        dataframe=build_dataframe(),
        label_column="CategoryName",
        value_column="NetRevenue",
        descending=True,
        limit=2,
    )

    assert len(result) == 2
    assert result[0].rank == 1
    assert result[0].label == "Beverages"
    assert result[0].value == 1000.0

    assert result[1].label == "Confections"


def test_rank_records_missing_column() -> None:
    with pytest.raises(
        ValueError,
        match="Missing ranking column",
    ):
        rank_records(
            dataframe=build_dataframe(),
            label_column="MissingColumn",
            value_column="NetRevenue",
        )


def test_calculate_contributions() -> None:
    result = calculate_contributions(
        dataframe=build_dataframe(),
        label_column="CategoryName",
        value_column="NetRevenue",
    )

    assert len(result) == 3

    beverages = result[0]

    assert beverages.label == "Beverages"

    assert (
        beverages.contribution_percentage
        == 50.0
    )


def test_zscore_anomalies() -> None:
    dataframe = pd.DataFrame(
        {
            "Month": [
                "M1",
                "M2",
                "M3",
                "M4",
                "M5",
                "M6",
            ],
            "Revenue": [
                100,
                102,
                98,
                101,
                99,
                1000,
            ],
        }
    )

    result = detect_zscore_anomalies(
        dataframe=dataframe,
        value_column="Revenue",
        label_column="Month",
        threshold=2.0,
    )

    assert len(result) == 6

    flagged = [
        record
        for record in result
        if record.is_anomaly
    ]

    assert len(flagged) >= 1
    assert flagged[-1].label == "M6"


def test_anomaly_detection_small_sample() -> None:
    dataframe = pd.DataFrame(
        {
            "Revenue": [
                100,
                200,
            ]
        }
    )

    result = detect_zscore_anomalies(
        dataframe=dataframe,
        value_column="Revenue",
    )

    assert result == []


def test_analyze_ranking_success() -> None:
    result = analyze_ranking(
        rows=build_dataframe().to_dict(
            orient="records"
        ),
        label_column="CategoryName",
        value_column="NetRevenue",
        descending=True,
        limit=2,
    )

    assert result.success is True
    assert len(result.records) == 2
    assert result.errors == []


def test_analyze_ranking_failure() -> None:
    result = analyze_ranking(
        rows=build_dataframe().to_dict(
            orient="records"
        ),
        label_column="MissingColumn",
        value_column="NetRevenue",
    )

    assert result.success is False
    assert result.errors