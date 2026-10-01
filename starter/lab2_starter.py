"""
LAB 2 STARTER: benchmark three vector databases and choose one.

    python starter/lab2_starter.py

Chroma, Qdrant and Milvus all run inside Python, with no server and no account.
They come from requirements-frameworks.txt (setup_windows.cmd installs it).
Reference: solutions/lab2_solution.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
import vector_dbs as vdb
from labkit import table


def main():
    # TODO 1: build the benchmark set: 100,000 vectors, 200 questions, and the answer
    #         key from exact search. Why is exact search a valid answer key, and what
    #         does it NOT tell you?
    bench = vdb.make_benchmark_set(n=100_000, n_questions=200)
    print(f"{len(bench.X):,} vectors, exact search {bench.exact_ms} ms per question\n")

    # TODO 2: load the three databases and measure them at ef 40, one question at a
    #         time and all 200 in one call. Predict the fastest before you run it.
    dbs = []
    for name in vdb.DATABASES:
        db = vdb.open_db(name); db.build(bench.X, bench.labels); dbs.append(db)
    print(table([vdb.measure(db, bench) for db in dbs]))

    # TODO 3: sweep ef over 10, 20, 40, 80, 160 on each database with vdb.sweep().
    #         Where is the elbow? Predict the shape before you run it.

    # TODO 4: the filter test, vdb.filter_test(db, bench, label=3). How many results does
    #         each database return with its own filter, and how many when you filter
    #         after the search? Which would you ship, and why?

    # TODO 5: compression, vdb.compression_test(bench). What does 16 times smaller cost,
    #         and how much does re-checking win back?

    # TODO 6: write your memo in the Your write-up cell of the Lab 2 notebook.
    for db in dbs:
        db.remove()


if __name__ == "__main__":
    main()
