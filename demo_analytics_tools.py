from pprint import pprint

from schemas.planning_schemas import (
    AnalyticalTask,
    TaskType,
)
from schemas.sql_schemas import (
    QueryExecutionResult,
)
from tools.analytics_tools import (
    analyze_ranking,
    calculate_contributions,
    calculate_summary_statistics,
    rows_to_dataframe,
)
from tools.result_validator import (
    validate_query_result,
)


def main() -> None:
    task = AnalyticalTask(
        task_id="T1",
        description=(
            "Rank categories by net revenue."
        ),
        task_type=TaskType.DATA_RETRIEVAL,
        metrics=["net_revenue"],
        dimensions=["category"],
        expected_columns=[
            "CategoryName",
            "NetRevenue",
        ],
    )

    execution = QueryExecutionResult(
        success=True,
        status="completed",
        columns=[
            "CategoryName",
            "NetRevenue",
        ],
        rows=[
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
        ],
        returned_row_count=3,
    )

    print("\nRESULT VALIDATION")
    print("=" * 70)

    validation = validate_query_result(
        task=task,
        execution=execution,
    )

    pprint(
        validation.model_dump(
            mode="json"
        ),
        sort_dicts=False,
    )

    if not validation.is_valid:
        print(
            "\nResult is not valid for analysis."
        )
        return

    dataframe = rows_to_dataframe(
        validation.validated_rows
    )

    print("\nSUMMARY STATISTICS")
    print("=" * 70)

    statistics = (
        calculate_summary_statistics(
            dataframe=dataframe,
            numeric_column="NetRevenue",
        )
    )

    pprint(
        statistics.model_dump(
            mode="json"
        ),
        sort_dicts=False,
    )

    print("\nRANKING")
    print("=" * 70)

    ranking = analyze_ranking(
        rows=validation.validated_rows,
        label_column="CategoryName",
        value_column="NetRevenue",
        descending=True,
        limit=3,
    )

    pprint(
        ranking.model_dump(
            mode="json"
        ),
        sort_dicts=False,
    )

    print("\nCONTRIBUTION TO TOTAL")
    print("=" * 70)

    contributions = calculate_contributions(
        dataframe=dataframe,
        label_column="CategoryName",
        value_column="NetRevenue",
    )

    for record in contributions:
        print(
            f"{record.rank}. "
            f"{record.label}: "
            f"{record.value:.2f} "
            f"({record.contribution_percentage:.2f}%)"
        )


if __name__ == "__main__":
    main()