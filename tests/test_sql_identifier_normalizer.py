from tools.sql_identifier_normalizer import (
    normalize_sql_identifiers,
    normalize_table_names,
)


def test_unquoted_orderdetails_is_normalized() -> None:
    sql = (
        "SELECT * "
        "FROM OrderDetails AS od"
    )

    normalized, corrections = (
        normalize_sql_identifiers(sql)
    )

    assert (
        'FROM "Order Details" AS od'
        in normalized
    )

    assert corrections


def test_quoted_orderdetails_is_normalized() -> None:
    sql = (
        'SELECT * '
        'FROM "OrderDetails" AS od'
    )

    normalized, _ = (
        normalize_sql_identifiers(sql)
    )

    assert (
        'FROM "Order Details" AS od'
        in normalized
    )


def test_underscore_variant_is_normalized() -> None:
    sql = (
        "SELECT * "
        "FROM order_details AS od"
    )

    normalized, _ = (
        normalize_sql_identifiers(sql)
    )

    assert (
        'FROM "Order Details" AS od'
        in normalized
    )


def test_correct_table_name_remains_unchanged() -> None:
    sql = (
        'SELECT * '
        'FROM "Order Details" AS od'
    )

    normalized, corrections = (
        normalize_sql_identifiers(sql)
    )

    assert normalized == sql
    assert corrections == []


def test_unrelated_unknown_table_is_not_changed() -> None:
    sql = "SELECT * FROM Sales"

    normalized, corrections = (
        normalize_sql_identifiers(sql)
    )

    assert normalized == sql
    assert corrections == []


def test_table_metadata_is_normalized() -> None:
    result = normalize_table_names(
        [
            "Orders",
            "OrderDetails",
            "Products",
        ]
    )

    assert result == [
        "Orders",
        "Order Details",
        "Products",
    ]