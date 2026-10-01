"""Lab 2 reference solution: three vector databases, the ef sweep, the filter test, compression."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
import vector_dbs as vdb
from labkit import table


def main():
    bench = vdb.make_benchmark_set(n=100_000, n_questions=200)
    print(f"{len(bench.X):,} vectors of {bench.X.shape[1]} numbers, {len(bench.Q)} questions, "
          f"exact search {bench.exact_ms} ms per question")
    print("versions:", vdb.versions(), "\n")

    dbs = []
    for name in vdb.DATABASES:
        db = vdb.open_db(name); db.build(bench.X, bench.labels); dbs.append(db)
    print(table([vdb.measure(db, bench) for db in dbs]))

    print("\nef sweep (the recall/latency curve):")
    curve = []
    for db in dbs:
        curve += vdb.sweep(db, bench)
    print(table(curve, ["database", "ef", "recall@10", "p50_ms", "p95_ms"]))

    print("\nselective filter test, label 3 only (1 row in 10):")
    print(table([vdb.filter_test(db, bench, label=3) for db in dbs]))

    print("\ncompression, Qdrant at ef 80:")
    print(table(vdb.compression_test(bench, ef=80)))
    for db in dbs:
        db.remove()


if __name__ == "__main__":
    main()
