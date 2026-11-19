from tools.schema_loader import (
    load_business_glossary,
    load_metric_definitions,
    load_schema_catalog,
)


def test_schema_catalog_loads() -> None:
    """
    Verify that the schema catalog loads successfully
    and contains the main Northwind tables.
    """

    schema = load_schema_catalog()

    assert isinstance(schema, dict)

    assert "database_name" in schema
    assert "database_dialect" in schema
    assert "tables" in schema
    assert "relationships" in schema

    assert schema["database_name"] == "Northwind"
    assert schema["database_dialect"] == "sqlite"

    expected_tables = {
        "Categories",
        "Customers",
        "Orders",
        "Order Details",
        "Products",
        "Suppliers",
    }

    actual_tables = set(schema["tables"].keys())

    assert expected_tables.issubset(actual_tables)


def test_schema_table_definitions() -> None:
    """
    Verify that important tables contain the expected
    descriptions, primary keys, and columns.
    """

    schema = load_schema_catalog()
    tables = schema["tables"]

    orders = tables["Orders"]

    assert "description" in orders
    assert "primary_key" in orders
    assert "columns" in orders

    assert orders["primary_key"] == ["OrderID"]

    assert "OrderID" in orders["columns"]
    assert "CustomerID" in orders["columns"]
    assert "EmployeeID" in orders["columns"]
    assert "OrderDate" in orders["columns"]
    assert "ShipCountry" in orders["columns"]

    order_details = tables["Order Details"]

    assert order_details["primary_key"] == [
        "OrderID",
        "ProductID",
    ]

    assert "UnitPrice" in order_details["columns"]
    assert "Quantity" in order_details["columns"]
    assert "Discount" in order_details["columns"]

    products = tables["Products"]

    assert "ProductID" in products["columns"]
    assert "ProductName" in products["columns"]
    assert "CategoryID" in products["columns"]
    assert "SupplierID" in products["columns"]


def test_schema_column_definitions() -> None:
    """
    Verify that important columns contain data types
    and business descriptions.
    """

    schema = load_schema_catalog()
    tables = schema["tables"]

    order_id = tables["Orders"]["columns"]["OrderID"]

    assert order_id["type"] == "INTEGER"
    assert "description" in order_id
    assert order_id["description"]

    order_date = tables["Orders"]["columns"]["OrderDate"]

    assert order_date["type"] == "DATETIME"
    assert "description" in order_date

    unit_price = tables["Order Details"]["columns"]["UnitPrice"]

    assert unit_price["type"] == "NUMERIC"
    assert "description" in unit_price

    discount = tables["Order Details"]["columns"]["Discount"]

    assert discount["type"] == "REAL"
    assert "description" in discount


def test_schema_relationships_exist() -> None:
    """
    Verify that the schema catalog contains the important
    table relationships required for analytical queries.
    """

    schema = load_schema_catalog()
    relationships = schema["relationships"]

    assert isinstance(relationships, list)
    assert len(relationships) > 0

    customer_order_relationship = any(
        relationship["from_table"] == "Customers"
        and relationship["from_column"] == "CustomerID"
        and relationship["to_table"] == "Orders"
        and relationship["to_column"] == "CustomerID"
        for relationship in relationships
    )

    order_details_relationship = any(
        relationship["from_table"] == "Orders"
        and relationship["from_column"] == "OrderID"
        and relationship["to_table"] == "Order Details"
        and relationship["to_column"] == "OrderID"
        for relationship in relationships
    )

    product_order_details_relationship = any(
        relationship["from_table"] == "Products"
        and relationship["from_column"] == "ProductID"
        and relationship["to_table"] == "Order Details"
        and relationship["to_column"] == "ProductID"
        for relationship in relationships
    )

    category_product_relationship = any(
        relationship["from_table"] == "Categories"
        and relationship["from_column"] == "CategoryID"
        and relationship["to_table"] == "Products"
        and relationship["to_column"] == "CategoryID"
        for relationship in relationships
    )

    supplier_product_relationship = any(
        relationship["from_table"] == "Suppliers"
        and relationship["from_column"] == "SupplierID"
        and relationship["to_table"] == "Products"
        and relationship["to_column"] == "SupplierID"
        for relationship in relationships
    )

    assert customer_order_relationship
    assert order_details_relationship
    assert product_order_details_relationship
    assert category_product_relationship
    assert supplier_product_relationship


def test_relationship_types() -> None:
    """
    Verify that every relationship includes a valid
    relationship type.
    """

    schema = load_schema_catalog()
    relationships = schema["relationships"]

    allowed_relationship_types = {
        "one_to_one",
        "one_to_many",
        "many_to_one",
        "many_to_many",
    }

    for relationship in relationships:
        assert "relationship" in relationship

        assert (
            relationship["relationship"]
            in allowed_relationship_types
        )


def test_metric_definitions_load() -> None:
    """
    Verify that the metric-definition file loads
    and contains the required business metrics.
    """

    metrics_data = load_metric_definitions()

    assert isinstance(metrics_data, dict)
    assert "metrics" in metrics_data

    metrics = metrics_data["metrics"]

    expected_metrics = {
        "net_revenue",
        "gross_revenue",
        "order_count",
        "product_quantity",
        "average_order_value",
    }

    actual_metrics = set(metrics.keys())

    assert expected_metrics.issubset(actual_metrics)


def test_net_revenue_metric() -> None:
    """
    Verify that net revenue uses UnitPrice, Quantity,
    and Discount.
    """

    metrics_data = load_metric_definitions()
    metrics = metrics_data["metrics"]

    net_revenue = metrics["net_revenue"]

    assert net_revenue["display_name"] == "Net Revenue"
    assert "description" in net_revenue
    assert "formula" in net_revenue

    formula = net_revenue["formula"]

    assert "UnitPrice" in formula
    assert "Quantity" in formula
    assert "Discount" in formula


def test_gross_revenue_metric() -> None:
    """
    Verify that gross revenue uses price and quantity
    without applying a discount.
    """

    metrics_data = load_metric_definitions()
    metrics = metrics_data["metrics"]

    gross_revenue = metrics["gross_revenue"]

    assert gross_revenue["display_name"] == "Gross Revenue"

    formula = gross_revenue["formula"]

    assert "UnitPrice" in formula
    assert "Quantity" in formula
    assert "Discount" not in formula


def test_order_count_metric() -> None:
    """
    Verify that the order-count metric counts unique orders.
    """

    metrics_data = load_metric_definitions()
    metrics = metrics_data["metrics"]

    order_count = metrics["order_count"]

    assert order_count["display_name"] == "Order Count"
    assert "OrderID" in order_count["formula"]

    normalized_formula = (
        order_count["formula"]
        .replace(" ", "")
        .upper()
    )

    assert "COUNT(DISTINCTORDERID)" in normalized_formula


def test_business_glossary_loads() -> None:
    """
    Verify that the business glossary loads and contains
    important natural-language terms.
    """

    glossary_data = load_business_glossary()

    assert isinstance(glossary_data, dict)
    assert "terms" in glossary_data

    terms = glossary_data["terms"]

    expected_terms = {
        "sales",
        "revenue",
        "income",
        "orders",
        "products",
        "customers",
        "suppliers",
        "categories",
        "countries",
        "discount",
    }

    actual_terms = set(terms.keys())

    assert expected_terms.issubset(actual_terms)


def test_revenue_synonyms_map_to_net_revenue() -> None:
    """
    Verify that different revenue-related business terms
    map to the same approved metric.
    """

    glossary_data = load_business_glossary()
    terms = glossary_data["terms"]

    assert terms["sales"]["metric"] == "net_revenue"
    assert terms["revenue"]["metric"] == "net_revenue"
    assert terms["income"]["metric"] == "net_revenue"


def test_business_entities_map_to_tables() -> None:
    """
    Verify that business entities map to the appropriate
    Northwind tables.
    """

    glossary_data = load_business_glossary()
    terms = glossary_data["terms"]

    assert terms["products"]["table"] == "Products"
    assert terms["customers"]["table"] == "Customers"
    assert terms["suppliers"]["table"] == "Suppliers"
    assert terms["categories"]["table"] == "Categories"


def test_business_fields_map_correctly() -> None:
    """
    Verify that business field names map to existing
    database field names.
    """

    glossary_data = load_business_glossary()
    terms = glossary_data["terms"]

    assert terms["countries"]["field"] == "Country"
    assert terms["discount"]["field"] == "Discount"