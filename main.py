import sqlite3
import sys


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        from pipeline import run
        from text_processing import CorpusError
    except ModuleNotFoundError as error:
        print(f"Не встановлено бібліотеку {error.name}. Виконайте: pip install -r requirements.txt")
        return 1
    try:
        run()
    except CorpusError as error:
        print(f"Помилка корпусу: {error}")
        return 1
    except (sqlite3.Error, OSError) as error:
        print(f"Помилка роботи з файлами або базою даних: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
