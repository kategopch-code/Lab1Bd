from analytics import build_clusters, build_pos_statistics, build_tfidf
from config import DATABASE_PATH, TEXT_SOURCES
from database import DatabaseBuilder, connect
from reporting import console_table, export_reports
from text_processing import MorphologyTagger, build_sample, read_text


def build_database() -> None:
    tagger = MorphologyTagger()
    with DatabaseBuilder(DATABASE_PATH) as builder:
        for source in TEXT_SOURCES:
            print(f"Обробка: {source.author}, «{source.title}»")
            text = read_text(source)
            builder.insert_text(source, text, build_sample(source, text, tagger))
        builder.build_frequency_tables()
        build_tfidf(builder.connection)
        build_pos_statistics(builder.connection)
        build_clusters(builder.connection)


def run() -> None:
    build_database()
    connection = connect(DATABASE_PATH)
    try:
        tables = export_reports(connection)
    finally:
        connection.close()
    for title, (headers, rows) in tables:
        print(f"\n=== {title} ===")
        print(console_table(headers, rows))
    print(f"\nБазу даних збережено: {DATABASE_PATH}")
