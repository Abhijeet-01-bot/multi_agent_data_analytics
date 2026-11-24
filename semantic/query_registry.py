from __future__ import annotations

from typing import Any


TABLES: dict[str, dict[str, str]] = {
    "Orders": {"alias": "o"},
    "Order Details": {"alias": "od"},
    "Products": {"alias": "p"},
    "Categories": {"alias": "c"},
    "Customers": {"alias": "cu"},
    "Suppliers": {"alias": "s"},
    "Employees": {"alias": "e"},
    "Shippers": {"alias": "sh"},
}


METRICS: dict[str, dict[str, Any]] = {
    "net_revenue": {
        "expression": (
            "od.UnitPrice * od.Quantity "
            "* (1 - od.Discount)"
        ),
        "aggregation": "SUM",
        "alias": "NetRevenue",
        "base_table": "Order Details",
    },
    "gross_revenue": {
        "expression": (
            "od.UnitPrice * od.Quantity"
        ),
        "aggregation": "SUM",
        "alias": "GrossRevenue",
        "base_table": "Order Details",
    },
    "order_count": {
        "expression": "o.OrderID",
        "aggregation": "COUNT_DISTINCT",
        "alias": "OrderCount",
        "base_table": "Orders",
    },
    "product_quantity": {
        "expression": "od.Quantity",
        "aggregation": "SUM",
        "alias": "ProductQuantity",
        "base_table": "Order Details",
    },
    "average_order_value": {
        "expression": (
            "od.UnitPrice * od.Quantity "
            "* (1 - od.Discount)"
        ),
        "aggregation": "AVERAGE_ORDER_VALUE",
        "alias": "AverageOrderValue",
        "base_table": "Order Details",
    },
}


DIMENSIONS: dict[str, dict[str, str]] = {
    "category": {
        "expression": "c.CategoryName",
        "alias": "CategoryName",
        "table": "Categories",
    },
    "product": {
        "expression": "p.ProductName",
        "alias": "ProductName",
        "table": "Products",
    },
    "customer": {
        "expression": "cu.CompanyName",
        "alias": "CustomerName",
        "table": "Customers",
    },
    "customer_country": {
        "expression": "cu.Country",
        "alias": "CustomerCountry",
        "table": "Customers",
    },
    "ship_country": {
        "expression": "o.ShipCountry",
        "alias": "ShipCountry",
        "table": "Orders",
    },
    "supplier": {
        "expression": "s.CompanyName",
        "alias": "SupplierName",
        "table": "Suppliers",
    },
    "employee": {
        "expression": (
            "e.FirstName || ' ' || e.LastName"
        ),
        "alias": "EmployeeName",
        "table": "Employees",
    },
    "order_month": {
        "expression": (
            "STRFTIME('%Y-%m', o.OrderDate)"
        ),
        "alias": "OrderMonth",
        "table": "Orders",
    },
    "order_quarter": {
        "expression": (
            "STRFTIME('%Y', o.OrderDate) "
            "|| '-Q' || CAST("
            "((CAST(STRFTIME('%m', o.OrderDate) "
            "AS INTEGER) - 1) / 3) + 1 "
            "AS INTEGER)"
        ),
        "alias": "OrderQuarter",
        "table": "Orders",
    },
    "order_year": {
        "expression": (
            "STRFTIME('%Y', o.OrderDate)"
        ),
        "alias": "OrderYear",
        "table": "Orders",
    },
}


FILTER_FIELDS: dict[str, dict[str, str]] = {
    name: {
        "expression": definition["expression"],
        "table": definition["table"],
    }
    for name, definition in DIMENSIONS.items()
}

FILTER_FIELDS["order_date"] = {
    "expression": "o.OrderDate",
    "table": "Orders",
}


RELATIONSHIPS: list[dict[str, str]] = [
    {
        "left_table": "Orders",
        "right_table": "Order Details",
        "condition": "o.OrderID = od.OrderID",
    },
    {
        "left_table": "Orders",
        "right_table": "Customers",
        "condition": "o.CustomerID = cu.CustomerID",
    },
    {
        "left_table": "Orders",
        "right_table": "Employees",
        "condition": "o.EmployeeID = e.EmployeeID",
    },
    {
        "left_table": "Orders",
        "right_table": "Shippers",
        "condition": "o.ShipVia = sh.ShipperID",
    },
    {
        "left_table": "Order Details",
        "right_table": "Products",
        "condition": "od.ProductID = p.ProductID",
    },
    {
        "left_table": "Products",
        "right_table": "Categories",
        "condition": "p.CategoryID = c.CategoryID",
    },
    {
        "left_table": "Products",
        "right_table": "Suppliers",
        "condition": "p.SupplierID = s.SupplierID",
    },
]