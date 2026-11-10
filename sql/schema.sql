PRAGMA foreign_keys = ON;

CREATE TABLE texts (
    id INTEGER PRIMARY KEY,
    number INTEGER NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    author TEXT NOT NULL,
    title TEXT NOT NULL,
    genre TEXT NOT NULL,
    edition TEXT NOT NULL,
    source_url TEXT NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE pos (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE sentences (
    id INTEGER PRIMARY KEY,
    text_id INTEGER NOT NULL REFERENCES texts (id),
    number INTEGER NOT NULL,
    sentence TEXT NOT NULL,
    UNIQUE (text_id, number)
);

CREATE TABLE words (
    id INTEGER PRIMARY KEY,
    sentence_id INTEGER NOT NULL REFERENCES sentences (id),
    number INTEGER NOT NULL,
    position INTEGER NOT NULL,
    subsample INTEGER NOT NULL CHECK (subsample BETWEEN 1 AND 20),
    word TEXT NOT NULL,
    lemma TEXT NOT NULL,
    pos_id INTEGER NOT NULL REFERENCES pos (id),
    UNIQUE (sentence_id, number)
);

CREATE INDEX idx_sentences_text ON sentences (text_id);
CREATE INDEX idx_words_sentence ON words (sentence_id);
CREATE INDEX idx_words_lemma ON words (lemma);
CREATE INDEX idx_words_pos ON words (pos_id);

CREATE VIEW tokens AS
SELECT
    w.id,
    s.text_id,
    w.sentence_id,
    w.position,
    w.subsample,
    w.word,
    w.lemma,
    p.code AS pos_code,
    p.name AS pos
FROM words AS w
JOIN sentences AS s ON s.id = w.sentence_id
JOIN pos AS p ON p.id = w.pos_id;

CREATE TABLE tfidf (
    id INTEGER PRIMARY KEY,
    text_id INTEGER NOT NULL REFERENCES texts (id),
    lemma TEXT NOT NULL,
    term_count INTEGER NOT NULL,
    tf REAL NOT NULL,
    df INTEGER NOT NULL,
    idf REAL NOT NULL,
    tfidf REAL NOT NULL,
    sklearn_tfidf REAL,
    UNIQUE (text_id, lemma)
);

CREATE TABLE pos_statistics (
    id INTEGER PRIMARY KEY,
    text_id INTEGER NOT NULL REFERENCES texts (id),
    pos TEXT NOT NULL,
    abs_freq INTEGER NOT NULL,
    probability REAL NOT NULL,
    mean_per_subsample REAL NOT NULL,
    std_per_subsample REAL NOT NULL,
    variation REAL NOT NULL,
    relative_error_sample REAL NOT NULL,
    relative_error_subsamples REAL NOT NULL,
    sufficiency TEXT NOT NULL,
    UNIQUE (text_id, pos)
);

CREATE TABLE subsample_clusters (
    id INTEGER PRIMARY KEY,
    text_id INTEGER NOT NULL REFERENCES texts (id),
    subsample INTEGER NOT NULL,
    cluster INTEGER NOT NULL,
    UNIQUE (text_id, subsample)
);
