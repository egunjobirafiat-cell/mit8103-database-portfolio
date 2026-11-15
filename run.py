"""
MIT 8103: Advanced Database Systems
Student: Rafiat Egunjobi (egunjobirafiat-cell)
Case Study: Riverside University Student Result Portal

Practical demonstration suite covering:
  - Activity 1: Relational Schema & Integrity Constraints
  - Activity 2: Query Optimisation, Covering Index & GPA Calculation
  - Activity 3: Transactions, Concurrency & SQLite WAL Isolation
  - Activity 4: NoSQL Document Model (Transcript JSON Extraction)
"""

import os
import json
import time
import sqlite3
import statistics

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "riverside_test.db")


def read_sql_file(relative_path):
    """Helper to read SQL file contents."""
    full_path = os.path.join(BASE_DIR, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def verify_constraint(db, sql_statement):
    """Verifies that an invalid operation is blocked by database constraints."""
    try:
        db.execute(sql_statement)
    except sqlite3.IntegrityError as err:
        print(f"Rejected: {err}")
    else:
        raise AssertionError(f"Expected constraint violation for: {sql_statement}")


def benchmark_query(db, query, offering_id=1, runs=11):
    """Explains query plan and benchmarks median execution time across multiple runs."""
    plan = db.execute("EXPLAIN QUERY PLAN " + query, (offering_id,)).fetchall()
    results = db.execute(query, (offering_id,)).fetchall()

    durations = []
    for _ in range(runs):
        start = time.perf_counter()
        db.execute(query, (offering_id,)).fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000
        durations.append(elapsed_ms)

    median_duration = statistics.median(durations)
    print(f"Plan: {plan}\nRows: {len(results)}; median: {median_duration:.3f} ms")
    return results, median_duration


def run_gpa_calculation(db, student_id=100, term_id=1):
    """Computes semester GPA for a student across all enrolled courses in a term."""
    gpa_sql = read_sql_file("portfolio-2-query-optimisation/gpa_calculation.sql")
    row = db.execute(gpa_sql, (student_id, term_id)).fetchone()
    if row:
        sid, sname, term, count, credits, quality_pts, gpa = row
        print(f"Student: {sname} (ID: {sid}) | Term: {term}")
        print(f"Courses Taken: {count} | Total Credits: {credits} | Quality Points: {quality_pts:.2f} | Semester GPA: {gpa:.2f} / 5.00")
        return gpa
    return None


def run_concurrency_test(db_path):
    """Demonstrates snapshot isolation, repeatable read across concurrent commit, lock contention, and rollback in SQLite WAL mode."""
    # Open two independent database connections
    writer = sqlite3.connect(db_path, isolation_level=None)
    reader = sqlite3.connect(db_path, timeout=0, isolation_level=None)

    query = "SELECT score FROM registration WHERE student_id = 100 AND offering_id = 1"
    initial_score = reader.execute(query).fetchone()[0]

    # Step 1: Reader opens an explicit read transaction (taking a point-in-time snapshot)
    reader.execute("BEGIN")
    score_in_snapshot = reader.execute(query).fetchone()[0]
    assert score_in_snapshot == initial_score
    print(f"Reader open transaction initial: {score_in_snapshot}")

    # Step 2: Writer starts an immediate transaction and updates student 100's score
    writer.execute("BEGIN IMMEDIATE")
    writer.execute("UPDATE registration SET score = 85 WHERE student_id = 100 AND offering_id = 1")

    # Step 3: Competing writer attempts write lock acquisition while writer holds write lock
    competing_conn = sqlite3.connect(db_path, timeout=0, isolation_level=None)
    try:
        competing_conn.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as err:
        assert err.sqlite_errorcode == sqlite3.SQLITE_BUSY
        print(f"Competing writer: {err}")
    else:
        competing_conn.rollback()
        raise AssertionError("Expected writer contention error")
    finally:
        competing_conn.close()

    # Step 4: Writer commits the grade update (85) to the WAL file
    writer.commit()

    # Step 5: Reader queries AGAIN inside its STILL OPEN transaction
    # True snapshot isolation: reader continues to observe the pre-commit snapshot (52)!
    score_after_writer_commit = reader.execute(query).fetchone()[0]
    assert score_after_writer_commit == initial_score
    print(f"Reader open transaction after writer commit (snapshot preserved): {score_after_writer_commit}")

    # Step 6: Reader closes transaction; fresh read now observes committed grade (85)
    reader.commit()
    committed_score = reader.execute(query).fetchone()[0]
    assert committed_score == 85
    print(f"Reader fresh read after commit: {committed_score}")

    # Step 7: Writer performs an update that gets rolled back
    writer.execute("BEGIN IMMEDIATE")
    writer.execute("UPDATE registration SET score = 10 WHERE student_id = 100 AND offering_id = 1")
    writer.rollback()

    rolled_back_score = reader.execute(query).fetchone()[0]
    assert rolled_back_score == committed_score
    print(f"Reader after rollback: {rolled_back_score}")

    writer.close()
    reader.close()


def run_document_model_test(relational_db):
    """Transforms relational course results into a JSON document and performs embedded extraction."""
    rows = relational_db.execute("""
        SELECT t.label, c.code, c.title, o.section, r.score
        FROM registration AS r
        JOIN offering AS o ON o.id = r.offering_id
        JOIN course AS c ON c.id = o.course_id
        JOIN term AS t ON t.id = o.term_id
        WHERE r.student_id = ? AND t.id = ?
        ORDER BY c.code, o.section
    """, (100, 1)).fetchall()

    transcript_doc = {
        "student_id": 100,
        "term": rows[0][0],
        "results": [
            {"course": code, "title": title, "section": section, "score": score}
            for _, code, title, section, score in rows
        ]
    }

    # Store document in a dedicated table with JSON validation
    doc_db = sqlite3.connect(":memory:")
    doc_db.execute("""
        CREATE TABLE transcript (
            id TEXT PRIMARY KEY,
            body TEXT NOT NULL CHECK(json_valid(body))
        );
    """)

    doc_key = "student:100:term:1"
    doc_db.execute("INSERT INTO transcript VALUES (?, ?)", (doc_key, json.dumps(transcript_doc)))

    # Retrieve full document
    body = doc_db.execute("SELECT body FROM transcript WHERE id = ?", (doc_key,)).fetchone()[0]
    print(json.dumps(json.loads(body), indent=2))

    # Query embedded array directly using SQLite JSON functions
    extracted = doc_db.execute("""
        SELECT json_extract(result.value, '$.score')
        FROM transcript, json_each(transcript.body, '$.results') AS result
        WHERE transcript.id = ? AND json_extract(result.value, '$.course') = ?
    """, (doc_key, "MIT8103")).fetchall()

    assert extracted == [(85,)]
    print(f"Embedded course scores: {extracted}")
    doc_db.close()


def main():
    # Clean up previous test database if it exists
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except OSError:
            pass

    # Connect to local SQLite database
    db = sqlite3.connect(DB_PATH, isolation_level=None)

    try:
        # Enable Write-Ahead Logging
        wal_mode = db.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        assert wal_mode.lower() == "wal"

        print(f"SQLite {sqlite3.sqlite_version}\n")

        # -------------------------------------------------------------
        # Portfolio 1: Schema Setup & Constraint Verification
        # -------------------------------------------------------------
        print("1. Design and constraints")
        db.executescript(read_sql_file("portfolio-1-database-design/schema.sql"))

        # Populate synthetic test dataset: 50,000 students and registrations
        db.executescript("""
            BEGIN;
            WITH RECURSIVE ids(n) AS (
                VALUES(1) UNION ALL SELECT n + 1 FROM ids WHERE n < 50000
            )
            INSERT INTO student SELECT n, 1, 'Student ' || n FROM ids;
            INSERT INTO registration
            SELECT id, CASE WHEN id % 100 = 0 THEN 1 ELSE 2 END, (id + 53) % 101
            FROM student;

            -- Additional course registrations for Student 100 to support multi-course GPA calculation
            INSERT OR REPLACE INTO registration VALUES (100, 3, 78); -- MIT8101 (3 credits): Score 78 -> A (5 pts)
            INSERT OR REPLACE INTO registration VALUES (100, 4, 68); -- MIT8105 (2 credits): Score 68 -> B (4 pts)
            COMMIT;
        """)

        # Verify integrity constraints
        verify_constraint(db, "INSERT INTO registration VALUES (100, 1, 50)")                 # Duplicate PK
        verify_constraint(db, "UPDATE registration SET score = 101 WHERE student_id = 100")    # Score > 100 check
        verify_constraint(db, "INSERT INTO registration VALUES (50001, 1, 50)")               # Invalid foreign key
        verify_constraint(db, "INSERT INTO course VALUES (99, 1, 'TEST99', 'Fractional Credits', 3.5)") # Fractional credits rejected
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []

        # -------------------------------------------------------------
        # Portfolio 2: Query Optimisation & Covering Index
        # -------------------------------------------------------------
        print("\n2. Grade roster before indexing")
        roster_sql = read_sql_file("portfolio-2-query-optimisation/roster.sql")
        before_rows, before_time = benchmark_query(db, roster_sql)
        print(f"First five rows: {before_rows[:5]}")

        # Add covering index
        db.execute("CREATE INDEX registration_roster ON registration(offering_id, student_id, score)")

        print("\nGrade roster after indexing")
        after_rows, after_time = benchmark_query(db, roster_sql)
        assert before_rows == after_rows and len(after_rows) == 500

        # Semester GPA Calculation
        print("\n2b. Semester GPA Calculation (Student 100)")
        run_gpa_calculation(db, student_id=100, term_id=1)

        # -------------------------------------------------------------
        # Portfolio 3: Transactions & Concurrency
        # -------------------------------------------------------------
        print("\n3. Transactions and concurrency")
        run_concurrency_test(DB_PATH)

        # -------------------------------------------------------------
        # Portfolio 4: NoSQL Document Model & Extraction
        # -------------------------------------------------------------
        print("\n4. Document storage and retrieval")
        run_document_model_test(db)

    finally:
        db.close()
        # Clean up database files
        for ext in ["", "-wal", "-shm"]:
            f = DB_PATH + ext
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass


if __name__ == "__main__":
    main()
