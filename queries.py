from dataclasses import dataclass

from config import CONTENT_POS, SUBSAMPLE_COUNT, TEXT_SOURCES

CONTENT_LIST = ", ".join(f"'{name}'" for name in CONTENT_POS)
PART_COLUMNS = ", ".join(f"part_{part}" for part in range(1, SUBSAMPLE_COUNT + 1))
TOP_LIMIT = 15
TEXT_COLUMNS = ",\n            ".join(
    f'SUM(k.text_id = {source.number}) AS "{source.title}"' for source in TEXT_SOURCES
)


@dataclass(frozen=True)
class Report:
    key: str
    title: str
    sql: str
    preview_rows: int | None = None


REPORTS = (
    Report(
        "01_text_overview",
        "Загальні показники текстів",
        """
        WITH base AS (
            SELECT
                text_id,
                COUNT(*) AS tokens,
                COUNT(DISTINCT word) AS wordforms,
                COUNT(DISTINCT lemma) AS lemmas,
                COUNT(DISTINCT sentence_id) AS sentences,
                AVG(LENGTH(word)) AS avg_word_length
            FROM tokens
            GROUP BY text_id
        ),
        hapax AS (
            SELECT text_id, SUM(abs_freq = 1) AS hapax_forms
            FROM freq_wordforms
            GROUP BY text_id
        )
        SELECT
            t.title AS "Текст",
            t.author AS "Автор",
            b.tokens AS "Слововживань",
            b.wordforms AS "Словоформ",
            b.lemmas AS "Лем",
            b.sentences AS "Речень",
            ROUND(1.0 * b.tokens / b.sentences, 2) AS "Сер. довжина речення",
            ROUND(b.avg_word_length, 2) AS "Сер. довжина слова",
            ROUND(1.0 * b.wordforms / b.tokens, 4) AS "Лекс. багатство",
            ROUND(1.0 * b.tokens / b.wordforms, 2) AS "Індекс повторюваності",
            h.hapax_forms AS "Гапакси",
            ROUND(100.0 * h.hapax_forms / b.wordforms, 2) AS "Гапакси, %"
        FROM base AS b
        JOIN texts AS t ON t.id = b.text_id
        JOIN hapax AS h ON h.text_id = b.text_id
        ORDER BY t.number
        """,
    ),
    Report(
        "02_pos_counts",
        "Кількість частин мови (SELECT ... COUNT ... GROUP BY)",
        """
        SELECT
            x.title AS "Текст",
            k.pos AS "Частина мови",
            COUNT(*) AS "Кількість",
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY k.text_id), 2) AS "Частка, %"
        FROM tokens AS k
        JOIN texts AS x ON x.id = k.text_id
        GROUP BY k.text_id, k.pos
        ORDER BY x.number, COUNT(*) DESC
        """,
    ),
    Report(
        "03_pos_comparison",
        "Порівняння частин мови між текстами",
        f"""
        SELECT
            k.pos AS "Частина мови",
            {TEXT_COLUMNS},
            COUNT(*) AS "Разом"
        FROM tokens AS k
        GROUP BY k.pos
        ORDER BY COUNT(*) DESC
        """,
    ),
    Report(
        "04_top_lemmas",
        "Найчастотніші повнозначні леми (повтори враховано)",
        f"""
        WITH ranked AS (
            SELECT
                text_id, lemma, pos, abs_freq,
                ROW_NUMBER() OVER (PARTITION BY text_id ORDER BY abs_freq DESC, lemma) AS place
            FROM freq_lemmas
            WHERE pos IN ({CONTENT_LIST})
        )
        SELECT t.title AS "Текст", r.place AS "Ранг", r.lemma AS "Лема",
               r.pos AS "Частина мови", r.abs_freq AS "Частота"
        FROM ranked AS r
        JOIN texts AS t ON t.id = r.text_id
        WHERE r.place <= {TOP_LIMIT}
        ORDER BY t.number, r.place
        """,
    ),
    Report(
        "05_top_wordforms",
        "Найчастотніші словоформи (усі частини мови)",
        f"""
        WITH ranked AS (
            SELECT
                text_id, word, COUNT(*) AS frequency,
                ROW_NUMBER() OVER (PARTITION BY text_id ORDER BY COUNT(*) DESC, word) AS place
            FROM tokens
            GROUP BY text_id, word
        )
        SELECT t.title AS "Текст", r.place AS "Ранг", r.word AS "Словоформа", r.frequency AS "Частота"
        FROM ranked AS r
        JOIN texts AS t ON t.id = r.text_id
        WHERE r.place <= {TOP_LIMIT}
        ORDER BY t.number, r.place
        """,
    ),
    Report(
        "06_tfidf_top",
        "TF-IDF: ключові леми текстів",
        f"""
        WITH content AS (
            SELECT text_id, lemma, MIN(pos) AS pos
            FROM freq_lemmas
            WHERE pos IN ({CONTENT_LIST})
            GROUP BY text_id, lemma
        ),
        ranked AS (
            SELECT
                f.text_id, f.lemma, c.pos, f.term_count, f.tf, f.df, f.idf, f.tfidf, f.sklearn_tfidf,
                ROW_NUMBER() OVER (PARTITION BY f.text_id ORDER BY f.tfidf DESC, f.lemma) AS place
            FROM tfidf AS f
            JOIN content AS c ON c.text_id = f.text_id AND c.lemma = f.lemma
        )
        SELECT t.title AS "Текст", r.place AS "Ранг", r.lemma AS "Лема", r.pos AS "Частина мови",
               r.term_count AS "Частота", ROUND(r.tf, 5) AS "TF", r.df AS "DF",
               ROUND(r.idf, 4) AS "IDF", ROUND(r.tfidf, 6) AS "TF-IDF",
               ROUND(r.sklearn_tfidf, 5) AS "TF-IDF sklearn"
        FROM ranked AS r
        JOIN texts AS t ON t.id = r.text_id
        WHERE r.place <= {TOP_LIMIT}
        ORDER BY t.number, r.place
        """,
    ),
    Report(
        "07_word_length",
        "Розподіл слів за довжиною",
        """
        SELECT t.title AS "Текст", LENGTH(k.word) AS "Довжина слова", COUNT(*) AS "Кількість"
        FROM tokens AS k
        JOIN texts AS t ON t.id = k.text_id
        GROUP BY k.text_id, LENGTH(k.word)
        ORDER BY t.number, LENGTH(k.word)
        """,
        12,
    ),
    Report(
        "08_sentence_length",
        "Розподіл речень за довжиною",
        """
        WITH lengths AS (
            SELECT text_id, sentence_id, COUNT(*) AS size
            FROM tokens
            GROUP BY text_id, sentence_id
        ),
        grouped AS (
            SELECT
                text_id,
                CASE
                    WHEN size <= 5 THEN '01-05'
                    WHEN size <= 10 THEN '06-10'
                    WHEN size <= 20 THEN '11-20'
                    WHEN size <= 30 THEN '21-30'
                    ELSE '31+'
                END AS band
            FROM lengths
        )
        SELECT t.title AS "Текст", g.band AS "Слів у реченні", COUNT(*) AS "Речень"
        FROM grouped AS g
        JOIN texts AS t ON t.id = g.text_id
        GROUP BY g.text_id, g.band
        ORDER BY t.number, g.band
        """,
    ),
    Report(
        "09_frequency_spectrum",
        "Частотний спектр словоформ",
        """
        SELECT
            t.title AS "Текст",
            CASE
                WHEN f.abs_freq = 1 THEN '1'
                WHEN f.abs_freq = 2 THEN '2'
                WHEN f.abs_freq <= 5 THEN '3-5'
                WHEN f.abs_freq <= 20 THEN '6-20'
                WHEN f.abs_freq <= 100 THEN '21-100'
                ELSE '101+'
            END AS "Абс. частота",
            COUNT(*) AS "Словоформ",
            SUM(f.abs_freq) AS "Слововживань"
        FROM freq_wordforms AS f
        JOIN texts AS t ON t.id = f.text_id
        GROUP BY f.text_id, 2
        ORDER BY t.number, MIN(f.abs_freq)
        """,
    ),
    Report(
        "10_vocabulary_overlap",
        "Спільна лексика текстів (леми, коефіцієнт Жаккара)",
        """
        WITH vocabulary AS (
            SELECT DISTINCT text_id, lemma FROM tokens
        ),
        sizes AS (
            SELECT text_id, COUNT(*) AS size FROM vocabulary GROUP BY text_id
        ),
        shared AS (
            SELECT a.text_id AS left_id, b.text_id AS right_id, COUNT(*) AS common
            FROM vocabulary AS a
            JOIN vocabulary AS b ON a.lemma = b.lemma AND a.text_id < b.text_id
            GROUP BY a.text_id, b.text_id
        )
        SELECT
            l.title AS "Текст 1",
            r.title AS "Текст 2",
            s.common AS "Спільних лем",
            ROUND(1.0 * s.common / (a.size + b.size - s.common), 4) AS "Жаккар"
        FROM shared AS s
        JOIN texts AS l ON l.id = s.left_id
        JOIN texts AS r ON r.id = s.right_id
        JOIN sizes AS a ON a.text_id = s.left_id
        JOIN sizes AS b ON b.text_id = s.right_id
        ORDER BY s.left_id, s.right_id
        """,
    ),
    Report(
        "11_pos_statistics",
        "Статистичні характеристики частин мови у 20 підвибірках",
        """
        SELECT
            t.title AS "Текст",
            s.pos AS "Частина мови",
            s.abs_freq AS "Частота",
            ROUND(s.mean_per_subsample, 2) AS "Середнє",
            ROUND(s.std_per_subsample, 2) AS "Сигма",
            ROUND(s.variation, 4) AS "Варіація",
            ROUND(100 * s.relative_error_sample, 2) AS "Похибка вибірки, %",
            ROUND(100 * s.relative_error_subsamples, 2) AS "Похибка за підвибірками, %",
            s.sufficiency AS "Оцінка обсягу"
        FROM pos_statistics AS s
        JOIN texts AS t ON t.id = s.text_id
        ORDER BY t.number, s.abs_freq DESC
        """,
    ),
    Report(
        "12_cluster_composition",
        "Кластеризація 60 підвибірок KMeans за TF-IDF",
        """
        SELECT
            c.cluster AS "Кластер",
            t.title AS "Текст",
            COUNT(*) AS "Підвибірок"
        FROM subsample_clusters AS c
        JOIN texts AS t ON t.id = c.text_id
        GROUP BY c.cluster, c.text_id
        ORDER BY c.cluster, COUNT(*) DESC
        """,
    ),
)

FULL_TABLE_EXPORTS = {
    "freq_forms": f"""
        SELECT id, text_id, wordform, abs_freq, {PART_COLUMNS}
        FROM freq_forms ORDER BY id
    """,
    "freq_wordforms": f"""
        SELECT id, text_id, pos, lemma, wordform, abs_freq, {PART_COLUMNS}
        FROM freq_wordforms ORDER BY id
    """,
    "freq_lemmas": f"""
        SELECT id, text_id, pos, lemma, abs_freq, {PART_COLUMNS}
        FROM freq_lemmas ORDER BY id
    """,
    "freq_pos": f"""
        SELECT id, text_id, pos, abs_freq, {PART_COLUMNS}
        FROM freq_pos ORDER BY id
    """,
    "tfidf": """
        SELECT id, text_id, lemma, term_count, tf, df, idf, tfidf, sklearn_tfidf
        FROM tfidf ORDER BY text_id, tfidf DESC, lemma
    """,
}
