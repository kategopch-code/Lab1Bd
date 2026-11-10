import csv
import sqlite3
from pathlib import Path

from config import (
    ACCEPTABLE_ERROR,
    CSV_DIR,
    HIGH_ACCURACY_ERROR,
    REPORT_PATH,
    SAMPLE_SIZE,
    SUBSAMPLE_COUNT,
    SUBSAMPLE_SIZE,
    TEXT_SOURCES,
)
from queries import FULL_TABLE_EXPORTS, REPORTS

Table = tuple[list[str], list[tuple]]


def fetch_table(connection: sqlite3.Connection, sql: str) -> Table:
    cursor = connection.execute(sql)
    return [column[0] for column in cursor.description], cursor.fetchall()


def write_csv(path: Path, headers: list[str], rows: list[tuple]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)


def format_cell(value: object) -> str:
    return "" if value is None else str(value)


def console_table(headers: list[str], rows: list[tuple]) -> str:
    cells = [headers] + [[format_cell(value) for value in row] for row in rows]
    widths = [max(len(row[index]) for row in cells) for index in range(len(headers))]
    lines = [" | ".join(value.ljust(width) for value, width in zip(row, widths)) for row in cells]
    lines.insert(1, "-+-".join("-" * width for width in widths))
    return "\n".join(lines)


def markdown_table(headers: list[str], rows: list[tuple]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + " --- |" * len(headers)]
    for row in rows:
        lines.append("| " + " | ".join(format_cell(value) for value in row) + " |")
    return "\n".join(lines)


def describe_corpus() -> str:
    sample_rows = [
        (source.number, source.author, source.title, source.genre, source.edition, source.source_url)
        for source in TEXT_SOURCES
    ]
    return "\n\n".join(
        [
            "# Автоматичне укладання частотних словників",
            "## 1. Опис вибірок",
            "### Лінгвістична однорідність",
            "Усі вибірки належать до художнього стилю, жанру прози (повість), української "
            "літератури кінця XIX — початку XX ст.",
            markdown_table(
                ["№", "Автор", "Твір", "Жанр", "Видання", "Джерело"], sample_rows
            ),
            "### Статистична однорідність",
            f"Метод організації вибірки — механічний: суцільний фрагмент від початку твору. "
            f"Обсяг кожної вибірки — {SAMPLE_SIZE} слововживань після токенізації `tokenize_uk`, "
            f"кількість підвибірок — {SUBSAMPLE_COUNT} по {SUBSAMPLE_SIZE} слововживань.",
            "Достатність обсягу оцінено за відносною похибкою "
            "`δ = t · √((1 − p) / (p · N))`, де `t = 1,96` (надійність 95 %). "
            f"Межі оцінки: δ ≤ {HIGH_ACCURACY_ERROR:.0%} — висока точність, "
            f"δ ≤ {ACCEPTABLE_ERROR:.0%} — достатній обсяг.",
        ]
    )


def export_reports(connection: sqlite3.Connection) -> list[tuple[str, Table]]:
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    tables = []
    sections = [describe_corpus(), "## 2. Результати"]
    for report in REPORTS:
        headers, rows = fetch_table(connection, report.sql)
        write_csv(CSV_DIR / f"{report.key}.csv", headers, rows)
        preview = rows[: report.preview_rows] if report.preview_rows else rows
        sections.append(f"### {report.title}\n\n{markdown_table(headers, preview)}")
        tables.append((report.title, (headers, preview)))
    for name, sql in FULL_TABLE_EXPORTS.items():
        headers, rows = fetch_table(connection, sql)
        write_csv(CSV_DIR / f"{name}.csv", headers, rows)
    REPORT_PATH.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    return tables
