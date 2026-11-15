# MIT 8103 Advanced Database Systems — Coursework Portfolio

**Student Name:** Rafiat Egunjobi  
**GitHub Account:** `egunjobirafiat-cell`  
**Degree Programme:** Master of Information Technology (MIT)  
**Session / Semester:** 2026/2027 Academic Session — First Semester  
**Institution:** School of Postgraduate Studies, MIVA Open University  
**Case Study:** Riverside University Student Result Portal (Simulated)  
**Repository:** `https://github.com/egunjobirafiat-cell/mit8103-database-portfolio`  

---

## 1. Project Overview

This repository contains my practical database portfolio for **MIT 8103: Advanced Database Systems**.

The selected case study is the **Riverside University Student Result Portal**, designed to manage course registrations, lecturer grading rosters, GPA computation, academic transcripts, and high-concurrency transaction handling for a tertiary institution.

### Portfolio Activities Implemented:
1. **Portfolio 1: Database Design and Modelling** — Relational schema across 7 entities, composite primary keys, check constraints, foreign keys, and 1NF to 3NF normalisation proof.
2. **Portfolio 2: Query Processing and Optimisation** — Execution plan diagnostic analysis, composite covering index design, benchmark comparison (9.285 ms down to 0.767 ms), and semester GPA computation.
3. **Portfolio 3: Transactions and Concurrency** — SQLite Write-Ahead Logging (WAL) mode demonstration verifying Snapshot Isolation, writer lock contention (`SQLITE_BUSY`), commit visibility, and rollback atomicity.
4. **Portfolio 4: NoSQL and Advanced Data Models** — Pre-computed JSON semester transcript document model, JSON syntax validation via `CHECK (json_valid(body))`, embedded query extraction, and polyglot persistence analysis.
5. **Portfolio 5: Distributed and Cloud Database Architecture** — Multi-AZ high availability (RPO = 0, RTO < 60s), asynchronous read replica scaling, replication lag mitigation ("read-your-own-writes"), sharding trade-offs, and continuous WAL disaster recovery.

---

## 2. Directory Structure

```text
mit8103-database-portfolio/
├── portfolio-1-database-design/
│   ├── README.md               # Case study, ER diagram, schema, constraints, normalisation
│   └── schema.sql              # Relational DDL definitions and initial seed fixtures
├── portfolio-2-query-optimisation/
│   ├── README.md               # Roster query, EXPLAIN plans, covering index, GPA calculation
│   ├── roster.sql              # Parameterised grade roster query
│   └── gpa_calculation.sql     # Semester GPA computation query (Nigerian 5.0 scale)
├── portfolio-3-transactions-concurrency/
│   └── README.md               # WAL concurrency model, isolation, contention, and rollback logs
├── portfolio-4-nosql/
│   └── README.md               # JSON document model, SQLite JSON extraction, polyglot persistence
├── portfolio-5-distributed-cloud/
│   └── README.md               # Multi-AZ architecture, replication lag, sharding, disaster recovery
├── evidence.txt                # Automated terminal execution benchmark log
├── LMS-Submission-Report.md    # 3-page continuous assessment report for LMS submission
├── LMS-Submission-Report.html  # Print-ready HTML document formatted for PDF export
└── run.py                      # Python demonstration test suite and benchmarking script
```

---

## 3. Running the Test Suite

### Requirements
- Python 3.11+ (tested on Python 3.14)
- SQLite 3 (included in Python standard library)

Navigate to the project root and run:

```bash
python run.py
```

The script automatically executes:
1. Integrity constraint violation tests (duplicate primary key, score > 100, invalid foreign key).
2. Query execution plan and benchmark timings before and after creating the covering index.
3. Semester GPA calculation for student 100.
4. WAL snapshot reads, concurrent roster reads, writer contention, and rollback of a failed grade batch.
5. Transcript JSON validation, extraction, and refresh after a grade correction.

To save output to `evidence.txt`:
```bash
python run.py > evidence.txt
```

---

## 4. Key Results Summary

| Portfolio Component | Technical Deliverable | Measured Outcome / Evidence |
| :--- | :--- | :--- |
| **Portfolio 1** | Schema Design & Normalisation | Active enforcement of composite PK `(student_id, offering_id)`, score check (`0 <= score <= 100`), and clean `PRAGMA foreign_key_check`. |
| **Portfolio 2** | Query Optimisation & GPA | Covering index `(offering_id, student_id, score)` converted a 50,000-row index scan into a direct B-tree seek, reducing median latency from **9.285 ms to 0.767 ms (~12.1x speedup)**. Verified semester GPA: **4.00 / 5.00**. |
| **Portfolio 3** | Concurrency & Transactions | Verified SQLite WAL Snapshot Isolation (uncommitted writes invisible to readers), single-writer lock serialization (`database is locked`), and rollback atomicity. |
| **Portfolio 4** | Document Store & NoSQL | Validated JSON transcripts with `CHECK(json_valid(body))`. Document retrieval is an O(log N) B-tree lookup, eliminating 4-table relational joins. |
| **Portfolio 5** | Distributed Cloud Architecture | Proposed Aurora PostgreSQL design targeting RPO = 0 for a single-AZ failure and RTO under 60 seconds, with primary routing for immediate post-write reads. |
