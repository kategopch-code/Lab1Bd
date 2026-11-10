import json
import re
from dataclasses import dataclass

import pymorphy3
import tokenize_uk

from config import OVERRIDES_PATH, POS_LABELS, SAMPLE_SIZE, SUBSAMPLE_SIZE, TextSource

APOSTROPHES = str.maketrans({"’": "'", "ʼ": "'", "`": "'", "′": "'", "ʹ": "'"})
REMOVED_CHARACTERS = dict.fromkeys(map(ord, "̀́­​﻿"))
CYRILLIC = re.compile(r"[а-яіїєґ]", re.IGNORECASE)


class CorpusError(Exception):
    pass


@dataclass(frozen=True)
class Token:
    position: int
    subsample: int
    word: str
    lemma: str
    pos_code: str


@dataclass(frozen=True)
class Sentence:
    number: int
    text: str
    tokens: tuple[Token, ...]


def normalize_text(text: str) -> str:
    cleaned = text.translate(REMOVED_CHARACTERS).translate(APOSTROPHES)
    return cleaned.replace(" ", " ")


def to_word(token: str) -> str | None:
    if not token or not token[0].isalpha():
        return None
    word = token.lower().rstrip(".-'")
    return word or None


class MorphologyTagger:
    def __init__(self) -> None:
        self._analyzer = pymorphy3.MorphAnalyzer(lang="uk")
        overrides = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
        self._cache = {word: tuple(value) for word, value in overrides.items()}

    def analyze(self, word: str) -> tuple[str, str]:
        if word not in self._cache:
            self._cache[word] = self._parse(word)
        return self._cache[word]

    def _parse(self, word: str) -> tuple[str, str]:
        if not CYRILLIC.search(word):
            return word, "LATN"
        parsed = self._analyzer.parse(word)[0]
        code = parsed.tag.POS if parsed.tag.POS in POS_LABELS else "UNKN"
        if code == "ADJF" and {"actv", "pssv"} & set(parsed.tag.grammemes):
            code = "PRTF"
        return normalize_text(parsed.normal_form), code


def read_text(source: TextSource) -> str:
    if not source.path.is_file():
        raise CorpusError(f"Не знайдено файл тексту: {source.path}")
    text = normalize_text(source.path.read_text(encoding="utf-8")).strip()
    if not text:
        raise CorpusError(f"Файл тексту порожній: {source.path}")
    return text


def build_sample(source: TextSource, text: str, tagger: MorphologyTagger) -> list[Sentence]:
    sentences: list[Sentence] = []
    position = 0
    for paragraph in filter(None, map(str.strip, text.splitlines())):
        for sentence_text in tokenize_uk.tokenize_sents(paragraph):
            tokens = []
            for raw_token in tokenize_uk.tokenize_words(sentence_text):
                word = to_word(raw_token)
                if word is None or position == SAMPLE_SIZE:
                    continue
                lemma, pos_code = tagger.analyze(word)
                subsample = position // SUBSAMPLE_SIZE + 1
                position += 1
                tokens.append(Token(position, subsample, word, lemma, pos_code))
            if tokens:
                sentences.append(Sentence(len(sentences) + 1, sentence_text, tuple(tokens)))
            if position == SAMPLE_SIZE:
                return sentences
    raise CorpusError(
        f"У тексті «{source.title}» лише {position} слововживань, потрібно {SAMPLE_SIZE}."
    )
