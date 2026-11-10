from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TEXTS_DIR = BASE_DIR / "texts"
DATA_DIR = BASE_DIR / "data"
SQL_DIR = BASE_DIR / "sql"
OUTPUT_DIR = BASE_DIR / "output"
CSV_DIR = OUTPUT_DIR / "csv"
DATABASE_PATH = OUTPUT_DIR / "freq_dict.db"
SCHEMA_PATH = SQL_DIR / "schema.sql"
OVERRIDES_PATH = DATA_DIR / "morphology_overrides.json"
REPORT_PATH = OUTPUT_DIR / "report.md"

SAMPLE_SIZE = 20_000
SUBSAMPLE_SIZE = 1_000
SUBSAMPLE_COUNT = SAMPLE_SIZE // SUBSAMPLE_SIZE
CONFIDENCE_T = 1.96
HIGH_ACCURACY_ERROR = 0.10
ACCEPTABLE_ERROR = 0.33
RANDOM_STATE = 42

POS_LABELS = {
    "NOUN": "Іменник",
    "ADJF": "Прикметник",
    "ADJS": "Прикметник",
    "COMP": "Прикметник",
    "PRTF": "Дієприкметник",
    "PRTS": "Дієприкметник",
    "VERB": "Дієслово",
    "INFN": "Дієслово",
    "GRND": "Дієприслівник",
    "NUMR": "Числівник",
    "ADVB": "Прислівник",
    "NPRO": "Займенник",
    "PRED": "Присудкове слово",
    "PREP": "Прийменник",
    "CONJ": "Сполучник",
    "PRCL": "Частка",
    "INTJ": "Вигук",
    "LATN": "Іншомовне",
    "UNKN": "Невизначено",
}

CONTENT_POS = ("Іменник", "Прикметник", "Дієслово", "Прислівник")


@dataclass(frozen=True)
class TextSource:
    number: int
    slug: str
    author: str
    title: str
    genre: str
    edition: str
    source_url: str

    @property
    def path(self) -> Path:
        return TEXTS_DIR / f"{self.slug}.txt"


TEXT_SOURCES = (
    TextSource(
        1,
        "zakhar_berkut",
        "Іван Франко",
        "Захар Беркут",
        "історична повість",
        "Франко І. Твори, 1956–1962, т. 13",
        "https://uk.wikisource.org/wiki/Твори_(Франко,_1956–1962)/13/Захар_Беркут",
    ),
    TextSource(
        2,
        "perekhresni_stezhky",
        "Іван Франко",
        "Перехресні стежки",
        "соціально-психологічна повість",
        "Франко І. Твори, 1956–1962, т. 12",
        "https://uk.wikisource.org/wiki/Твори_(Франко,_1956–1962)/12",
    ),
    TextSource(
        3,
        "fata_morgana",
        "Михайло Коцюбинський",
        "Fata Morgana",
        "соціально-психологічна повість",
        "Коцюбинський М. Твори, 1955, т. 2",
        "https://uk.wikisource.org/wiki/Твори_(Коцюбинський,_1955)/2/Fata_Morgana",
    ),
)
