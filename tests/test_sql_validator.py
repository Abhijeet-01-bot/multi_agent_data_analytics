from tools.sql_validator import validate_sql


def test_valid_select_query_is_approved() -> None:
    sql = """
        SELECT
            OrderID,
            OrderDate
        FROM Orders
        LIMIT 10
    """

    result = validate_sql(sql)

    assert result.is_valid is True
    assert result.status == "approved"
    assert result.statement_type == "SELECT"
    assert "Orders" in result.referenced_tables
    assert result.errors == []


def test_valid_join_query_is_approved() -> None:
    sql = """
        SELECT
            c.CategoryName,
            SUM(
                od.UnitPrice
                * od.Quantity
                * (1 - od.Discount)
            ) AS NetRevenue
        FROM "Order Details" AS od
        JOIN Products AS p
            ON od.ProductID = p.ProductID
        JOIN Categories AS c
            ON p.CategoryID = c.CategoryID
        GROUP BY
            c.CategoryID,
            c.CategoryName
    """

    result = validate_sql(sql)

    assert result.is_valid is True
    assert result.status == "approved"

    assert "Order Details" in result.referenced_tables
    assert "Products" in result.referenced_tables
    assert "Categories" in result.referenced_tables


def test_delete_query_is_rejected() -> None:
    result = validate_sql(
        "DELETE FROM Orders"
    )

    assert result.is_valid is False
    assert result.status == "rejected"

    assert any(
        "DELETE" in error
        for error in result.errors
    )


def test_drop_query_is_rejected() -> None:
    result = validate_sql(
        "DROP TABLE Customers"
    )

    assert result.is_valid is False
    assert result.status == "rejected"


def test_update_query_is_rejected() -> None:
    result = validate_sql(
        """
        UPDATE Products
        SET UnitPrice = 0
        """
    )

    assert result.is_valid is False
    assert result.status == "rejected"


def test_unknown_table_is_rejected() -> None:
    result = validate_sql(
        "SELECT * FROM Sales"
    )

    assert result.is_valid is False

    assert any(
        "Unknown table" in error
        for error in result.errors
    )


def test_multiple_statements_are_rejected() -> None:
    result = validate_sql(
        """
        SELECT * FROM Orders;
        SELECT * FROM Customers;
        """
    )

    assert result.is_valid is False

    assert any(
        "Exactly one SQL statement" in error
        for error in result.errors
    )


def test_empty_query_is_rejected() -> None:
    result = validate_sql("")

    assert result.is_valid is False
    assert result.status == "rejected"
    assert "SQL query is empty." in result.errors


def test_sql_comment_is_rejected() -> None:
    result = validate_sql(
        """
        SELECT *
        FROM Orders
        -- Retrieve all orders
        """
    )

    assert result.is_valid is False

    assert any(
        "comments are not allowed" in error
        for error in result.errors
    )


def test_parameterized_select_is_approved() -> None:
    result = validate_sql(
        """
        SELECT
            CustomerID,
            CompanyName,
            Country
        FROM Customers
        WHERE Country = :country
        """
    )

    assert result.is_valid is True
    assert result.status == "approved"