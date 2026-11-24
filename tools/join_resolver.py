from __future__ import annotations

from collections import deque

from semantic.query_registry import (
    RELATIONSHIPS,
    TABLES,
)


def quote_table(
    table_name: str,
) -> str:
    if " " in table_name:
        return f'"{table_name}"'

    return table_name


def find_join_path(
    start_table: str,
    target_table: str,
) -> list[dict[str, str]]:
    if start_table == target_table:
        return []

    adjacency = {
        table_name: []
        for table_name in TABLES
    }

    for relationship in RELATIONSHIPS:
        left = relationship["left_table"]
        right = relationship["right_table"]

        adjacency[left].append(
            (right, relationship)
        )

        adjacency[right].append(
            (left, relationship)
        )

    queue = deque(
        [(start_table, [])]
    )

    visited = {start_table}

    while queue:
        current, path = queue.popleft()

        for next_table, relationship in (
            adjacency[current]
        ):
            if next_table in visited:
                continue

            new_path = [
                *path,
                relationship,
            ]

            if next_table == target_table:
                return new_path

            visited.add(next_table)

            queue.append(
                (next_table, new_path)
            )

    raise ValueError(
        "No valid join path exists between "
        f"{start_table} and {target_table}."
    )


def collect_relationships(
    base_table: str,
    target_tables: set[str],
) -> list[dict[str, str]]:
    collected: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for target_table in sorted(target_tables):
        path = find_join_path(
            base_table,
            target_table,
        )

        for relationship in path:
            edge = tuple(
                sorted(
                    [
                        relationship["left_table"],
                        relationship["right_table"],
                    ]
                )
            )

            if edge not in seen:
                seen.add(edge)
                collected.append(relationship)

    return collected


def compile_from_clause(
    base_table: str,
    relationships: list[dict[str, str]],
) -> str:
    base_alias = TABLES[
        base_table
    ]["alias"]

    lines = [
        (
            f"FROM {quote_table(base_table)} "
            f"AS {base_alias}"
        )
    ]

    joined = {base_table}
    remaining = list(relationships)

    while remaining:
        progress = False

        for relationship in list(remaining):
            left = relationship["left_table"]
            right = relationship["right_table"]

            if left in joined and right not in joined:
                next_table = right

            elif right in joined and left not in joined:
                next_table = left

            elif left in joined and right in joined:
                remaining.remove(relationship)
                progress = True
                continue

            else:
                continue

            alias = TABLES[next_table]["alias"]

            lines.append(
                (
                    f"JOIN {quote_table(next_table)} "
                    f"AS {alias}\n"
                    f"    ON "
                    f"{relationship['condition']}"
                )
            )

            joined.add(next_table)
            remaining.remove(relationship)
            progress = True

        if not progress:
            raise ValueError(
                "Unable to order the required joins."
            )

    return "\n".join(lines)