from tools.query_executor import (
    execute_read_only_query,
)


def test_execute_valid_query() -> None:
    result = execute_read_only_query(
        """
        SELECT
            CustomerID,
            CompanyName,
            Country
        FROM Customers
        ORDER BY CompanyName
        LIMIT 5
        """
    )

    assert result.success is True
    assert result.status == "completed"
    assert result.returned_row_count == 5

    assert "CustomerID" in result.columns
    assert "CompanyName" in result.columns
    assert "Country" in result.columns

    assert len(result.rows) == 5
    assert result.errors == []


def test_execute_revenue_query() -> None:
    result = execute_read_only_query(
        """
        SELECT
            ROUND(
                SUM(
                    UnitPrice
                    * Quantity
                    * (1 - Discount)
                ),
                2
            ) AS NetRevenue
        FROM "Order Details"
        """
    )

    assert result.success is True
    assert result.status == "completed"
    assert result.returned_row_count == 1

    assert "NetRevenue" in result.columns
    assert result.rows[0]["NetRevenue"] is not None


def test_unsafe_query_is_not_executed() -> None:
    result = execute_read_only_query(
        "DELETE FROM Orders"
    )

    assert result.success is False
    assert result.status == "validation_failed"
    assert len(result.errors) > 0


def test_unknown_table_is_not_executed() -> None:
    result = execute_read_only_query(
        "SELECT * FROM Sales"
    )

    assert result.success is False
    assert result.status == "validation_failed"


def test_row_limit_truncation() -> None:
    result = execute_read_only_query(
        "SELECT * FROM Orders",
        max_rows=5,
    )

    assert result.success is True
    assert result.returned_row_count == 5
    assert result.truncated is True

    assert any(
        "truncated" in warning.lower()
        for warning in result.warnings
    )


def test_parameterized_query() -> None:
    result = execute_read_only_query(
        """
        SELECT
            CustomerID,
            CompanyName,
            Country
        FROM Customers
        WHERE Country = :country
        ORDER BY CompanyName
        """,
        parameters={
            "country": "Germany",
        },
    )

    assert result.success is True
    assert result.status == "completed"
    assert result.returned_row_count > 0

    assert all(
        row["Country"] == "Germany"
        for row in result.rows
    )


def test_invalid_column_returns_execution_failure() -> None:
    result = execute_read_only_query(
        """
        SELECT
            FakeColumn
        FROM Orders
        """
    )

    assert result.success is False
    assert result.status == "execution_failed"

    assert any(
        "Database execution failed" in error
        for error in result.errors
    )