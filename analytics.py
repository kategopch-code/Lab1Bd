import math
import sqlite3
import statistics

from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from config import (
    ACCEPTABLE_ERROR,
    CONFIDENCE_T,
    CONTENT_POS,
    HIGH_ACCURACY_ERROR,
    RANDOM_STATE,
    SAMPLE_SIZE,
    SUBSAMPLE_COUNT,
)

CONTENT_PLACEHOLDERS = ", ".join("?" for _ in CONTENT_POS)


def keep_tokens(tokens: list[str]) -> list[str]:
    return tokens


def build_tfidf(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO tfidf (text_id, lemma, term_count, tf, df, idf, tfidf)
        WITH counts AS (
            SELECT text_id, lemma, COUNT(*) AS term_count
            FROM tokens
            GROUP BY text_id, lemma
        ),
        lengths AS (
            SELECT text_id, SUM(term_count) AS text_length
            FROM counts
            GROUP BY text_id
        ),
        frequencies AS (
            SELECT lemma, COUNT(*) AS df
            FROM counts
            GROUP BY lemma
        ),
        corpus AS (
            SELECT COUNT(*) AS text_count FROM texts
        )
        SELECT
            c.text_id,
            c.lemma,
            c.term_count,
            1.0 * c.term_count / l.text_length,
            f.df,
            LN(1.0 * corpus.text_count / f.df),
            1.0 * c.term_count / l.text_length * LN(1.0 * corpus.text_count / f.df)
        FROM counts AS c
        JOIN lengths AS l ON l.text_id = c.text_id
        JOIN frequencies AS f ON f.lemma = c.lemma
        CROSS JOIN corpus
        """
    )
    documents: dict[int, list[str]] = {}
    for text_id, lemma in connection.execute(
        "SELECT text_id, lemma FROM tokens ORDER BY text_id, position"
    ):
        documents.setdefault(text_id, []).append(lemma)
    text_ids = sorted(documents)
    vectorizer = TfidfVectorizer(analyzer=keep_tokens)
    matrix = vectorizer.fit_transform(documents[text_id] for text_id in text_ids).tocoo()
    terms = vectorizer.get_feature_names_out()
    connection.executemany(
        "UPDATE tfidf SET sklearn_tfidf = ? WHERE text_id = ? AND lemma = ?",
        [
            (float(score), text_ids[row], str(terms[column]))
            for row, column, score in zip(matrix.row, matrix.col, matrix.data)
        ],
    )


def classify_error(error: float) -> str:
    if error <= HIGH_ACCURACY_ERROR:
        return "висока точність"
    if error <= ACCEPTABLE_ERROR:
        return "достатній обсяг"
    return "обсягу недостатньо"


def build_pos_statistics(connection: sqlite3.Connection) -> None:
    part_columns = ", ".join(f"part_{part}" for part in range(1, SUBSAMPLE_COUNT + 1))
    rows = connection.execute(f"SELECT text_id, pos, abs_freq, {part_columns} FROM freq_pos")
    records = []
    for text_id, pos, abs_freq, *parts in rows:
        probability = abs_freq / SAMPLE_SIZE
        mean = statistics.fmean(parts)
        deviation = statistics.stdev(parts)
        variation = deviation / mean
        sample_error = CONFIDENCE_T * math.sqrt((1 - probability) / (SAMPLE_SIZE * probability))
        subsample_error = CONFIDENCE_T * variation / math.sqrt(SUBSAMPLE_COUNT)
        records.append(
            (
                text_id,
                pos,
                abs_freq,
                probability,
                mean,
                deviation,
                variation,
                sample_error,
                subsample_error,
                classify_error(sample_error),
            )
        )
    connection.executemany(
        """
        INSERT INTO pos_statistics (
            text_id, pos, abs_freq, probability, mean_per_subsample, std_per_subsample,
            variation, relative_error_sample, relative_error_subsamples, sufficiency
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )


def build_clusters(connection: sqlite3.Connection) -> None:
    documents: dict[tuple[int, int], list[str]] = {}
    query = f"""
        SELECT text_id, subsample, lemma
        FROM tokens
        WHERE pos IN ({CONTENT_PLACEHOLDERS})
        ORDER BY text_id, position
    """
    for text_id, subsample, lemma in connection.execute(query, CONTENT_POS):
        documents.setdefault((text_id, subsample), []).append(lemma)
    keys = sorted(documents)
    matrix = TfidfVectorizer(analyzer=keep_tokens).fit_transform(documents[key] for key in keys)
    text_count = connection.execute("SELECT COUNT(*) FROM texts").fetchone()[0]
    labels = KMeans(n_clusters=text_count, random_state=RANDOM_STATE, n_init=20).fit_predict(matrix)
    connection.executemany(
        "INSERT INTO subsample_clusters (text_id, subsample, cluster) VALUES (?, ?, ?)",
        [(text_id, subsample, int(label) + 1) for (text_id, subsample), label in zip(keys, labels)],
    )
