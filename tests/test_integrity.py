import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import DATABASE_PATH, SAMPLE_SIZE, SUBSAMPLE_COUNT, SUBSAMPLE_SIZE, TEXT_SOURCES
from pipeline import build_database
from text_processing import MorphologyTagger, normalize_text, to_word

PART_SUM = " + ".join(f"part_{part}" for part in range(1, SUBSAMPLE_COUNT + 1))


def setUpModule() -> None:
    if not DATABASE_PATH.exists():
        build_database()


class DatabaseIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = sqlite3.connect(DATABASE_PATH)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.connection.close()

    def scalar(self, sql: str) -> object:
        return self.connection.execute(sql).fetchone()[0]

    def test_every_text_has_exact_sample_size(self) -> None:
        rows = self.connection.execute("SELECT COUNT(*) FROM tokens GROUP BY text_id").fetchall()
        self.assertEqual(rows, [(SAMPLE_SIZE,)] * len(TEXT_SOURCES))

    def test_every_subsample_has_exact_size(self) -> None:
        rows = self.connection.execute(
            "SELECT COUNT(*) FROM tokens GROUP BY text_id, subsample"
        ).fetchall()
        self.assertEqual(rows, [(SUBSAMPLE_SIZE,)] * (len(TEXT_SOURCES) * SUBSAMPLE_COUNT))

    def test_frequency_tables_keep_all_repeats(self) -> None:
        expected = SAMPLE_SIZE * len(TEXT_SOURCES)
        for table in ("freq_forms", "freq_wordforms", "freq_lemmas", "freq_pos"):
            with self.subTest(table=table):
                self.assertEqual(self.scalar(f"SELECT SUM(abs_freq) FROM {table}"), expected)

    def test_parts_sum_to_absolute_frequency(self) -> None:
        for table in ("freq_forms", "freq_wordforms", "freq_lemmas", "freq_pos"):
            with self.subTest(table=table):
                mismatches = self.scalar(f"SELECT COUNT(*) FROM {table} WHERE abs_freq <> {PART_SUM}")
                self.assertEqual(mismatches, 0)

    def test_foreign_keys_are_valid(self) -> None:
        self.assertEqual(self.connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_tfidf_formula(self) -> None:
        mismatches = self.scalar("SELECT COUNT(*) FROM tfidf WHERE ABS(tfidf - tf * idf) > 1e-12")
        self.assertEqual(mismatches, 0)

    def test_words_common_to_all_texts_have_zero_tfidf(self) -> None:
        text_count = len(TEXT_SOURCES)
        self.assertEqual(self.scalar(f"SELECT MAX(tfidf) FROM tfidf WHERE df = {text_count}"), 0)

    def test_sklearn_scores_are_filled(self) -> None:
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM tfidf WHERE sklearn_tfidf IS NULL"), 0)


class TextProcessingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tagger = MorphologyTagger()

    def test_apostrophes_and_stress_are_normalized(self) -> None:
        self.assertEqual(normalize_text("сім’я́"), "сім'я")

    def test_non_words_are_rejected(self) -> None:
        self.assertIsNone(to_word("12"))
        self.assertIsNone(to_word("—"))

    def test_abbreviation_dot_is_removed(self) -> None:
        self.assertEqual(to_word("Др."), "др")

    def test_function_words_are_disambiguated(self) -> None:
        expected = {"його": ("він", "NPRO"), "до": ("до", "PREP"), "ще": ("ще", "ADVB")}
        for word, analysis in expected.items():
            with self.subTest(word=word):
                self.assertEqual(self.tagger.analyze(word), analysis)

    def test_foreign_words_are_marked(self) -> None:
        self.assertEqual(self.tagger.analyze("pardon"), ("pardon", "LATN"))


if __name__ == "__main__":
    unittest.main()
