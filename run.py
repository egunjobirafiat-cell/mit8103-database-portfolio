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
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from tempfile import TemporaryDirectory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))



def read_sql_file(relative_path):
    """Helper to read SQL file contents."""
    full_path = os.path.join(BASE_DIR, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def verify_constraint(db, sql_statement, expected=None):
    """Verifies that an invalid operation is blocked by database constraints."""
    try:
        db.execute(sql_statement)
    except sqlite3.IntegrityError as err:
        if expected is not None:
            assert expected in str(err), str(err)
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


def benchmark_grade_updates(db, runs=11):
    """Measure 500 grade updates per trial, excluding commit and rollback."""
    durations = []
    for _ in range(runs):
        db.execute("BEGIN IMMEDIATE")
        try:
            start = time.perf_counter()
            updated = db.execute("""
                UPDATE registration SET score = (score + 1) % 101
                WHERE student_id BETWEEN 1 AND 500 AND offering_id IN (1, 2)
            """).rowcount
            durations.append((time.perf_counter() - start) * 1000)
            assert updated == 500
        finally:
            db.rollback()
    print(f"500 grade updates; median: {statistics.median(durations):.3f} ms")


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

    # Run independent roster reads while the writer keeps its transaction open.
    roster_sql = read_sql_file("portfolio-2-query-optimisation/roster.sql")

    def read_roster(_):
        with closing(sqlite3.connect(db_path, timeout=0)) as connection:
            return connection.execute(roster_sql, (1,)).fetchall()

    with ThreadPoolExecutor(max_workers=4) as pool:
        rosters = list(pool.map(read_roster, range(4)))
    assert all(len(roster) == 500 and roster[0] == (100, initial_score) for roster in rosters)
    print("Four roster reads under an open write transaction returned the committed grades")

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

    batch_query = """
        SELECT student_id, score FROM registration
        WHERE offering_id = 1 AND student_id IN (100, 200, 300)
        ORDER BY student_id
    """
    original = reader.execute(batch_query).fetchall()
    writer.execute("BEGIN IMMEDIATE")
    try:
        writer.executemany(
            "UPDATE registration SET score = 10 WHERE offering_id = 1 AND student_id = ?",
            [(100,), (200,)],
        )
        assert writer.execute(batch_query).fetchall()[:2] == [(100, 10), (200, 10)]
        verify_constraint(
            writer,
            "UPDATE registration SET score = 101 WHERE student_id = 300 AND offering_id = 1",
            "CHECK constraint failed",
        )
    finally:
        writer.rollback()
    assert reader.execute(batch_query).fetchall() == original
    print(f"Failed batch rolled back all grade changes: {original}")

    writer.close()
    reader.close()


def refresh_transcript(relational_db, doc_db, student_id, term_id):
    """Rebuild the document from the current authoritative course results."""
    rows = relational_db.execute("""
        SELECT t.label, c.code, c.title, o.section, r.score
        FROM registration AS r
        JOIN offering AS o ON o.id = r.offering_id
        JOIN course AS c ON c.id = o.course_id
        JOIN term AS t ON t.id = o.term_id
        WHERE r.student_id = ? AND t.id = ?
        ORDER BY c.code, o.section
    """, (student_id, term_id)).fetchall()

    doc_key = f"student:{student_id}:term:{term_id}"
    if not rows:
        doc_db.execute("DELETE FROM transcript WHERE id = ?", (doc_key,))
        return

    transcript_doc = {
        "student_id": student_id,
        "term": rows[0][0],
        "results": [
            {"course": code, "title": title, "section": section, "score": score}
            for _, code, title, section, score in rows
        ]
    }

    store_transcript(doc_db, doc_key, transcript_doc)


def store_transcript(doc_db, doc_key, document):
    """Validate required fields and grade domains before publishing a document."""
    if not isinstance(document, dict):
        raise ValueError("Transcript must be a JSON object")
    student_id = document.get("student_id")
    term = document.get("term")
    results = document.get("results")
    if type(student_id) is not int or student_id < 1 or not isinstance(term, str) or not term.strip():
        raise ValueError("Transcript requires a positive student ID and a term label")
    if not isinstance(results, list) or not results:
        raise ValueError("Transcript requires a nonempty results array")

    courses = set()
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("Each transcript result must be an object")
        course, title, section, score = (
            result.get("course"), result.get("title"), result.get("section"), result.get("score")
        )
        if not isinstance(course, str) or not course.strip() or course in courses:
            raise ValueError("Transcript course codes must be present and unique")
        if not isinstance(title, str) or not title.strip() or type(section) is not int or section < 1:
            raise ValueError("Transcript results require a title and a positive section number")
        if "score" not in result or (score is not None and (type(score) is not int or not 0 <= score <= 100)):
            raise ValueError("Transcript score must be null or an integer from 0 to 100")
        courses.add(course)

    doc_db.execute("""
        INSERT INTO transcript (id, body) VALUES (?, ?)
        ON CONFLICT(id) DO UPDATE SET body = excluded.body
    """, (doc_key, json.dumps(document)))


def run_document_model_test(relational_db):
    """Publish, validate, and refresh a transcript after a grade correction."""
    doc_db = sqlite3.connect(":memory:")
    doc_db.execute("""
        CREATE TABLE transcript (
            id TEXT PRIMARY KEY,
            body TEXT NOT NULL CHECK(json_valid(body))
        );
    """)

    doc_key = "student:100:term:1"
    refresh_transcript(relational_db, doc_db, 100, 1)

    # Retrieve full document
    body = doc_db.execute("SELECT body FROM transcript WHERE id = ?", (doc_key,)).fetchone()[0]
    print(json.dumps(json.loads(body), indent=2))

    score_query = """
        SELECT json_extract(result.value, '$.score')
        FROM transcript, json_each(transcript.body, '$.results') AS result
        WHERE transcript.id = ? AND json_extract(result.value, '$.course') = ?
    """
    params = (doc_key, "MIT8103")
    assert doc_db.execute(score_query, params).fetchall() == [(85,)]
    print("Embedded course score: 85")

    incomplete = {"student_id": 100, "term": "2026/2027 Semester 1"}
    invalid_score = json.loads(body)
    invalid_score["results"][0]["score"] = 101
    for invalid in (incomplete, invalid_score):
        try:
            store_transcript(doc_db, doc_key, invalid)
        except ValueError as error:
            print(f"Rejected valid JSON with invalid transcript fields: {error}")
        else:
            raise AssertionError("Invalid transcript accepted")
    assert doc_db.execute("SELECT body FROM transcript WHERE id = ?", (doc_key,)).fetchone() == (body,)

    relational_db.execute("""
        UPDATE registration SET score = 90 WHERE student_id = 100 AND offering_id = 1
    """)
    refresh_transcript(relational_db, doc_db, 100, 1)
    assert doc_db.execute(score_query, params).fetchall() == [(90,)]
    refresh_transcript(relational_db, doc_db, 100, 1)
    assert doc_db.execute("SELECT count(*) FROM transcript").fetchone() == (1,)
    assert doc_db.execute(score_query, params).fetchall() == [(90,)]
    print("Grade correction refreshed the existing transcript from 85 to 90; retry kept one document")
    doc_db.close()


def run_portfolio(db_path):
    db = sqlite3.connect(db_path, isolation_level=None)

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
        verify_constraint(db, "INSERT INTO registration VALUES (100, 2, 50)", "already registered")
        verify_constraint(db, "UPDATE registration SET offering_id = 2 WHERE student_id = 100 AND offering_id = 3", "already registered")
        verify_constraint(db, "UPDATE offering SET course_id = 3 WHERE id = 3", "enrolled offering")
        db.execute("BEGIN")
        db.execute("UPDATE registration SET offering_id = 2 WHERE student_id = 100 AND offering_id = 1")
        assert run_gpa_calculation(db) == 4.0
        db.rollback()
        print("Moving the existing enrolment between sections preserves the GPA")
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []

        # -------------------------------------------------------------
        # Portfolio 2: Query Optimisation & Covering Index
        # -------------------------------------------------------------
        roster_sql = read_sql_file("portfolio-2-query-optimisation/roster.sql")
        print("\n2. Baseline roster workloads")
        selective_before, _ = benchmark_query(db, roster_sql, offering_id=1)
        dense_before, _ = benchmark_query(db, roster_sql, offering_id=2)
        benchmark_grade_updates(db)

        db.execute("CREATE INDEX registration_roster ON registration(offering_id, student_id, score)")

        print("\n2. Indexed roster workloads")
        selective_after, _ = benchmark_query(db, roster_sql, offering_id=1)
        dense_after, _ = benchmark_query(db, roster_sql, offering_id=2)
        benchmark_grade_updates(db)
        assert selective_before == selective_after and len(selective_after) == 500
        assert dense_before == dense_after and len(dense_after) == 49500

        print("\n2b. Semester GPA Calculation (Student 100)")
        assert run_gpa_calculation(db, student_id=100, term_id=1) == 4.0

        # -------------------------------------------------------------
        # Portfolio 3: Transactions & Concurrency
        # -------------------------------------------------------------
        print("\n3. Transactions and concurrency")
        run_concurrency_test(db_path)

        # -------------------------------------------------------------
        # Portfolio 4: NoSQL Document Model & Extraction
        # -------------------------------------------------------------
        print("\n4. Document storage and retrieval")
        run_document_model_test(db)

    finally:
        db.close()


def main():
    with TemporaryDirectory(prefix="riverside-") as directory:
        run_portfolio(os.path.join(directory, "riverside.db"))


if __name__ == "__main__":
    main()
