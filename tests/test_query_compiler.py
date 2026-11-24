from schemas.query_spec_schemas import (
    QueryFilter,
    QueryOperation,
    QuerySpec,
)
from tools.query_compiler import (
    compile_query_spec,
)
from tools.query_executor import (
    execute_read_only_query,
)
from tools.sql_validator import (
    validate_sql,
)


def test_monthly_category_comparison() -> None:
    specification = QuerySpec(
        metric="net_revenue",
        dimensions=[
            "order_month",
            "category",
        ],
        filters=[
            QueryFilter(
                field="category",
                operator="in",
                value=[
                    "Beverages",
                    "Dairy Products",
                ],
            )
        ],
        operations=[
            QueryOperation.AGGREGATE,
            QueryOperation.COMPARE,
            QueryOperation.TREND,
        ],
    )

    query = compile_query_spec(
        specification
    )

    assert (
        "STRFTIME('%Y-%m', o.OrderDate)"
        in query.sql
    )

    assert (
        'FROM "Order Details" AS od'
        in query.sql
    )

    assert "JOIN Orders AS o" in query.sql
    assert "JOIN Products AS p" in query.sql
    assert "JOIN Categories AS c" in query.sql

    assert query.parameters == {
        "filter_0_0": "Beverages",
        "filter_0_1": "Dairy Products",
    }

    validation = validate_sql(
        query.sql
    )

    assert validation.is_valid is True

    execution = execute_read_only_query(
        sql=query.sql,
        parameters=query.parameters,
    )

    assert execution.success is True
    assert execution.rows

def test_filtered_aggregate_can_return_zero_rows() -> None:
    specification = QuerySpec(
        metric="net_revenue",
        dimensions=[],
        filters=[
            QueryFilter(
                field="ship_country",
                operator="equals",
                value=(
                    "XYZ_NONEXISTENT"
                ),
            )
        ],
        operations=[
            QueryOperation.AGGREGATE
        ],
    )

    query = compile_query_spec(
        specification
    )

    assert (
        "HAVING COUNT(*) > 0"
        in query.sql
    )

    assert query.parameters == {
        "filter_0": (
            "XYZ_NONEXISTENT"
        )
    }

    execution = execute_read_only_query(
        sql=query.sql,
        parameters=query.parameters,
    )

    assert execution.success is True
    assert execution.rows == []