from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from schemas.analytics_schemas import (
    AnalyticsOperation,
    AnalyticsResult,
    AnomalyRecord,
    ContributionRecord,
    GrowthResult,
    RankingRecord,
    SummaryStatistics,
)


def rows_to_dataframe(
    rows: list[dict[str, Any]],
) -> pd.DataFrame:
    """
    Convert validated query rows into a DataFrame.
    """

    return pd.DataFrame(rows)


def calculate_summary_statistics(
    dataframe: pd.DataFrame,
    numeric_column: str,
) -> SummaryStatistics:
    """
    Calculate deterministic descriptive statistics for
    one numeric column.
    """

    if numeric_column not in dataframe.columns:
        raise ValueError(
            f"Column {numeric_column} does not exist."
        )

    numeric_series = pd.to_numeric(
        dataframe[numeric_column],
        errors="coerce",
    )

    valid_series = numeric_series.dropna()

    if valid_series.empty:
        return SummaryStatistics(
            column=numeric_column,
            count=0,
            null_count=len(dataframe),
        )

    standard_deviation = (
        float(valid_series.std(ddof=1))
        if len(valid_series) > 1
        else 0.0
    )

    return SummaryStatistics(
        column=numeric_column,
        count=int(valid_series.count()),
        null_count=int(
            numeric_series.isna().sum()
        ),
        minimum=float(valid_series.min()),
        maximum=float(valid_series.max()),
        mean=float(valid_series.mean()),
        median=float(valid_series.median()),
        standard_deviation=(
            standard_deviation
        ),
        total=float(valid_series.sum()),
    )


def calculate_growth(
    previous_value: float,
    current_value: float,
) -> GrowthResult:
    """
    Calculate absolute and percentage growth.

    Percentage change is undefined when the previous
    value is zero.
    """

    previous = float(previous_value)
    current = float(current_value)

    absolute_change = (
        current - previous
    )

    if previous == 0:
        percentage_change = None
        warning = (
            "Percentage change is undefined because "
            "the previous value is zero."
        )
    else:
        percentage_change = (
            absolute_change
            / abs(previous)
            * 100
        )

        warning = None

    if absolute_change > 0:
        direction = "increase"
    elif absolute_change < 0:
        direction = "decrease"
    else:
        direction = "no_change"

    return GrowthResult(
        previous_value=previous,
        current_value=current,
        absolute_change=(
            round(absolute_change, 4)
        ),
        percentage_change=(
            round(percentage_change, 4)
            if percentage_change
            is not None
            else None
        ),
        direction=direction,
        warning=warning,
    )


def rank_records(
    dataframe: pd.DataFrame,
    label_column: str,
    value_column: str,
    descending: bool = True,
    limit: int | None = None,
    ) -> list[RankingRecord]:
    """
    Rank grouped business records by a numeric value.
    """

    required_columns = {
        label_column,
        value_column,
    }

    missing_columns = (
        required_columns
        - set(dataframe.columns)
    )

    if missing_columns:
        raise ValueError(
            "Missing ranking column(s): "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    ranking_data = dataframe[
        [
            label_column,
            value_column,
        ]
    ].copy()

    ranking_data[value_column] = pd.to_numeric(
        ranking_data[value_column],
        errors="coerce",
    )

    ranking_data = ranking_data.dropna(
        subset=[value_column]
    )

    ranking_data = ranking_data.sort_values(
        by=value_column,
        ascending=not descending,
        kind="stable",
    )

    if limit is not None:
        safe_limit = max(
            1,
            min(int(limit), 100)
        )

        ranking_data = ranking_data.head(
            safe_limit
        )

    total = float(
        ranking_data[value_column].sum()
    )

    records: list[RankingRecord] = []

    for rank, (_, row) in enumerate(
        ranking_data.iterrows(),
        start=1,
    ):
        value = float(
            row[value_column]
        )

        percentage = (
            value / total * 100
            if total != 0
            else None
        )

        records.append(
            RankingRecord(
                rank=rank,
                label=str(
                    row[label_column]
                ),
                value=value,
                percentage_of_total=(
                    round(percentage, 4)
                    if percentage
                    is not None
                    else None
                ),
            )
        )

    return records


def calculate_contributions(
    dataframe: pd.DataFrame,
    label_column: str,
    value_column: str,
    descending: bool = True,
) -> list[ContributionRecord]:
    """
    Calculate each row's share of the total value.

    This is appropriate for positive totals such as
    revenue by category.

    Decline-contribution analysis should use period
    changes rather than raw revenue values.
    """

    if label_column not in dataframe.columns:
        raise ValueError(
            f"Column {label_column} does not exist."
        )

    if value_column not in dataframe.columns:
        raise ValueError(
            f"Column {value_column} does not exist."
        )

    contribution_data = dataframe[
        [
            label_column,
            value_column,
        ]
    ].copy()

    contribution_data[value_column] = (
        pd.to_numeric(
            contribution_data[value_column],
            errors="coerce",
        )
    )

    contribution_data = (
        contribution_data.dropna(
            subset=[value_column]
        )
    )

    contribution_data = (
        contribution_data.sort_values(
            by=value_column,
            ascending=not descending,
            kind="stable",
        )
    )

    total = float(
        contribution_data[
            value_column
        ].sum()
    )

    records: list[
        ContributionRecord
    ] = []

    for rank, (_, row) in enumerate(
        contribution_data.iterrows(),
        start=1,
    ):
        value = float(
            row[value_column]
        )

        contribution = (
            value / total * 100
            if total != 0
            else None
        )

        records.append(
            ContributionRecord(
                label=str(
                    row[label_column]
                ),
                value=value,
                contribution_percentage=(
                    round(
                        contribution,
                        4,
                    )
                    if contribution
                    is not None
                    else None
                ),
                rank=rank,
            )
        )

    return records


def detect_zscore_anomalies(
    dataframe: pd.DataFrame,
    value_column: str,
    label_column: str | None = None,
    threshold: float = 3.0,
) -> list[AnomalyRecord]:
    """
    Detect potential anomalies using absolute Z-scores.

    A threshold of 3.0 is a conventional starting point.
    Small samples should be interpreted cautiously.
    """

    if value_column not in dataframe.columns:
        raise ValueError(
            f"Column {value_column} does not exist."
        )

    safe_threshold = float(
        max(0.1, threshold)
    )

    numeric_series = pd.to_numeric(
        dataframe[value_column],
        errors="coerce",
    )

    valid_mask = numeric_series.notna()

    valid_values = numeric_series[
        valid_mask
    ]

    if len(valid_values) < 3:
        return []

    if math.isclose(
        float(valid_values.std(ddof=0)),
        0.0,
    ):
        z_scores = np.zeros(
            len(valid_values)
        )
    else:
        z_scores = np.abs(
            stats.zscore(
                valid_values,
                nan_policy="omit",
            )
        )

    records: list[
        AnomalyRecord
    ] = []

    valid_indices = list(
        valid_values.index
    )

    for position, index in enumerate(
        valid_indices
    ):
        label = None

        if (
            label_column
            and label_column
            in dataframe.columns
        ):
            label = str(
                dataframe.loc[
                    index,
                    label_column,
                ]
            )

        score = float(
            z_scores[position]
        )

        records.append(
            AnomalyRecord(
                index=int(index),
                label=label,
                value=float(
                    valid_values.loc[index]
                ),
                score=round(score, 4),
                method="zscore",
                is_anomaly=(
                    score >= safe_threshold
                ),
            )
        )

    return records


def analyze_ranking(
    rows: list[dict[str, Any]],
    label_column: str,
    value_column: str,
    descending: bool = True,
    limit: int | None = None,
) -> AnalyticsResult:
    """
    High-level ranking operation suitable for later use
    by the Analysis Agent.
    """

    dataframe = rows_to_dataframe(rows)

    try:
        ranking = rank_records(
            dataframe=dataframe,
            label_column=label_column,
            value_column=value_column,
            descending=descending,
            limit=limit,
        )

        return AnalyticsResult(
            success=True,
            operation=(
                AnalyticsOperation.RANKING
            ),
            summary=(
                f"Ranked {len(ranking)} record or "
                f"records by {value_column}."
            ),
            records=[
                record.model_dump(
                    mode="json"
                )
                for record in ranking
            ],
            metadata={
                "label_column": label_column,
                "value_column": value_column,
                "descending": descending,
                "limit": limit,
            },
        )

    except ValueError as error:
        return AnalyticsResult(
            success=False,
            operation=(
                AnalyticsOperation.RANKING
            ),
            summary=(
                "Ranking could not be completed."
            ),
            errors=[str(error)],
        )