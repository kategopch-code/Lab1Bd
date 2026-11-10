import math
import os
import sqlite3
from pathlib import Path

from config import POS_LABELS, SCHEMA_PATH, SUBSAMPLE_COUNT, TextSource
from text_processing import Sentence

PARTS = range(1, SUBSAMPLE_COUNT + 1)
PART_COLUMNS = ", ".join(f"part_{part}" for part in PARTS)
PART_DEFINITIONS = ",\n    ".join(f"part_{part} INTEGER NOT NULL" for part in PARTS)
PART_COUNTS = ", ".join(f"SUM(subsample = {part})" for part in PARTS)
PART_SUMS = ", ".join(f"SUM(part_{part})" for part in PARTS)


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.create_function("LN", 1, math.log, deterministic=True)
    return connection


class DatabaseBuilder:
    def __init__(self, target: Path) -> None:
        self._target = target
        self._temporary = target.with_suffix(".tmp")
        target.parent.mkdir(parents=True, exist_ok=True)
        self._temporary.unlink(missing_ok=True)
        self.connection = connect(self._temporary)

    def __enter__(self) -> "DatabaseBuilder":
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self._insert_pos()
        return self

    def __exit__(self, exception_type, exception, traceback) -> None:
        if exception_type is None:
            self.connection.commit()
        self.connection.close()
        if exception_type is None:
            os.replace(self._temporary, self._target)
        else:
            self._temporary.unlink(missing_ok=True)

    def _insert_pos(self) -> None:
        first_codes: dict[str, str] = {}
        for code, name in POS_LABELS.items():
            first_codes.setdefault(name, code)
        self.connection.executemany(
            "INSERT INTO pos (code, name) VALUES (?, ?)",
            [(code, name) for name, code in first_codes.items()],
        )

    def insert_text(self, source: TextSource, text: str, sentences: list[Sentence]) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO texts (number, slug, author, title, genre, edition, source_url, text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source.number,
                source.slug,
                source.author,
                source.title,
                source.genre,
                source.edition,
                source.source_url,
                text,
            ),
        )
        text_id = cursor.lastrowid
        pos_ids = dict(cursor.execute("SELECT name, id FROM pos").fetchall())
        for sentence in sentences:
            cursor.execute(
                "INSERT INTO sentences (text_id, number, sentence) VALUES (?, ?, ?)",
                (text_id, sentence.number, sentence.text),
            )
            sentence_id = cursor.lastrowid
            cursor.executemany(
                """
                INSERT INTO words (sentence_id, number, position, subsample, word, lemma, pos_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        sentence_id,
                        number,
                        token.position,
                        token.subsample,
                        token.word,
                        token.lemma,
                        pos_ids[POS_LABELS[token.pos_code]],
                    )
                    for number, token in enumerate(sentence.tokens, start=1)
                ],
            )

    def build_frequency_tables(self) -> None:
        self.connection.executescript(
            f"""
            CREATE TABLE freq_wordforms (
                id INTEGER PRIMARY KEY,
                text_id INTEGER NOT NULL REFERENCES texts (id),
                pos TEXT NOT NULL,
                lemma TEXT NOT NULL,
                wordform TEXT NOT NULL,
                abs_freq INTEGER NOT NULL,
                {PART_DEFINITIONS},
                UNIQUE (text_id, pos, lemma, wordform)
            );

            INSERT INTO freq_wordforms (text_id, pos, lemma, wordform, abs_freq, {PART_COLUMNS})
            SELECT text_id, pos, lemma, word, COUNT(*), {PART_COUNTS}
            FROM tokens
            GROUP BY text_id, pos, lemma, word
            ORDER BY text_id, COUNT(*) DESC, word;

            CREATE TABLE freq_forms (
                id INTEGER PRIMARY KEY,
                text_id INTEGER NOT NULL REFERENCES texts (id),
                wordform TEXT NOT NULL,
                abs_freq INTEGER NOT NULL,
                {PART_DEFINITIONS},
                UNIQUE (text_id, wordform)
            );

            INSERT INTO freq_forms (text_id, wordform, abs_freq, {PART_COLUMNS})
            SELECT text_id, wordform, SUM(abs_freq), {PART_SUMS}
            FROM freq_wordforms
            GROUP BY text_id, wordform
            ORDER BY text_id, SUM(abs_freq) DESC, wordform;

            CREATE TABLE freq_lemmas (
                id INTEGER PRIMARY KEY,
                text_id INTEGER NOT NULL REFERENCES texts (id),
                pos TEXT NOT NULL,
                lemma TEXT NOT NULL,
                abs_freq INTEGER NOT NULL,
                {PART_DEFINITIONS},
                UNIQUE (text_id, pos, lemma)
            );

            INSERT INTO freq_lemmas (text_id, pos, lemma, abs_freq, {PART_COLUMNS})
            SELECT text_id, pos, lemma, SUM(abs_freq), {PART_SUMS}
            FROM freq_wordforms
            GROUP BY text_id, pos, lemma
            ORDER BY text_id, SUM(abs_freq) DESC, lemma;

            CREATE TABLE freq_pos (
                id INTEGER PRIMARY KEY,
                text_id INTEGER NOT NULL REFERENCES texts (id),
                pos TEXT NOT NULL,
                abs_freq INTEGER NOT NULL,
                {PART_DEFINITIONS},
                UNIQUE (text_id, pos)
            );

            INSERT INTO freq_pos (text_id, pos, abs_freq, {PART_COLUMNS})
            SELECT text_id, pos, SUM(abs_freq), {PART_SUMS}
            FROM freq_wordforms
            GROUP BY text_id, pos
            ORDER BY text_id, SUM(abs_freq) DESC;
            """
        )
