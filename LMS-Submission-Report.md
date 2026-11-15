# Continuous Assessment Report: MIT 8103 Advanced Database Systems

**Student Name:** Rafiat Egunjobi  
**GitHub Username:** `egunjobirafiat-cell`  
**Course Code:** MIT 8103 — Advanced Database Systems  
**Programme:** Master of Information Technology (MIT)  
**Session / Semester:** 2026/2027 Academic Session — First Semester  
**Institution:** School of Postgraduate Studies, MIVA Open University  
**GitHub Repository:** `https://github.com/egunjobirafiat-cell/mit8103-database-portfolio`

*The public repository provides access to the SQL, runner, and execution evidence.*

---

## 1. Selected Organisation & Case Study Overview

### 1.1 Organisation & Business Scenario
The selected case study is the **Riverside University Student Result Portal (Simulated)**. The system is designed to handle core academic operations for a tertiary institution, including departmental course scheduling, student admissions, enrollment registrations, continuous assessment and examination grade submissions, semester GPA computation, and academic transcript queries.

### 1.2 User Roles & Operational Workload
1. **Students:** Query semester course offerings, register for designated course sections, inspect published continuous assessment/exam scores, calculate semester GPAs, and generate term transcripts.
2. **Lecturers:** Access enrollment rosters for assigned course offerings, record course marks (0–100), and submit final grades.
3. **Registry Staff:** Manage departments, define courses and credit unit allocations (1–6), configure academic terms, and assign instructors to course offerings.

---

## 2. Technical Deliverables across Portfolio Activities

### Activity 1: Database Design and Modelling
- **Relational Schema:** Implemented in standard SQL (`schema.sql`) across seven normalized entities: `department`, `student`, `lecturer`, `course`, `term`, `offering`, and `registration`.
- **Primary & Composite Keys:** `registration` utilizes a composite primary key `(student_id, offering_id)` for individual sections. Triggers enforce the case-study rule of one section per student, course and term. Moving the existing registration preserves the GPA.
- **Data Integrity Constraints:**
  - Foreign key constraints (`PRAGMA foreign_keys = ON`) enforce referential integrity across all relationships.
  - `CHECK (score IS NULL OR (typeof(score) = 'integer' AND score BETWEEN 0 AND 100))` enforces valid score bounds.
  - `CHECK (typeof(credits) = 'integer' AND credits BETWEEN 1 AND 6)` and `CHECK (typeof(section) = 'integer' AND section > 0)` enforce academic course validity.
  - Natural composite uniqueness `UNIQUE (course_id, term_id, section)` prevents duplicate section assignments within a term.
- **Normalisation (1NF to 3NF):** All attributes are atomic (1NF); the non-key attribute `score` depends fully on the composite key `{student_id, offering_id}` with no partial dependencies (2NF); departmental, course, and instructor metadata are isolated into reference entities to eliminate transitive dependencies (3NF).
- **Practical Evidence:** Executing invalid insertions in `run.py` triggered explicit integrity rejections:
  ```text
  Rejected: UNIQUE constraint failed: registration.student_id, registration.offering_id
  Rejected: CHECK constraint failed: score IS NULL OR (typeof(score) = 'integer' AND score BETWEEN 0 AND 100)
  Rejected: FOREIGN KEY constraint failed
  ```

---

### Activity 2: Query Processing, Optimisation and GPA Calculation
- **Target Query:** High-frequency roster extraction retrieving all graded students for an offering:
  ```sql
  SELECT student_id, score FROM registration WHERE offering_id = ? AND score IS NOT NULL ORDER BY student_id;
  ```
- **Workload Testbed:** 50,000 synthetic student registrations evaluated over 11 benchmark runs.
- **Pre-Optimisation:** The query planner defaulted to scanning the primary key index:
  `SCAN registration USING INDEX sqlite_autoindex_registration_1`  
  Because `student_id` is the leading key column, SQLite had to inspect all 50,000 index rows, producing a median execution latency of **9.285 ms**.
- **Covering Index Implementation:** A composite covering index was constructed:
  `CREATE INDEX registration_roster ON registration(offering_id, student_id, score);`  
  `offering_id` satisfies the equality filter via a logarithmic B-tree search (O(log N)); `student_id` provides pre-sorted order; `score` covers the projection and NOT NULL predicate.
- **Post-Optimisation:** The query planner switched to a direct B-tree search:
  `SEARCH registration USING COVERING INDEX registration_roster (offering_id=?)`  
  The 49,500-row roster went from 122.020 to 108.449 ms in the recorded run and from 48.566 to 52.300 ms in a separate rerun. Both runs showed faster selective roster reads and slower batches of 500 grade updates (excluding commit). The index helps selective reads, adds update overhead, and gives variable results when the query returns almost the entire table.
  For the 500-row roster, median latency dropped from **9.285 ms to 0.767 ms (~12.1x speedup / 91.7% reduction)** with zero table heap lookups.
- **Semester GPA Calculation:** Addressing the key case study operation on Page 2 of the brief, a GPA calculation query was implemented in `gpa_calculation.sql` based on the Nigerian 5.0 scale (A=5, B=4, C=3, D=2, F=0). For Student 100 across 3 courses (8 credit units), the system computed **32.00 quality points**, yielding a verified semester GPA of **4.00 / 5.00**.

---

### Activity 3: Transactions and Concurrency
- **Concurrency Architecture:** Configured Write-Ahead Logging (`PRAGMA journal_mode = WAL`) allowing simultaneous reading and writing without blocking readers.
- **Snapshot and Commit Visibility:** The reader opens a transaction and reads 52. The active writer commits a change to 85. The reader still sees 52 in the same transaction and sees 85 in a fresh query after ending it.
- **Lock Contention:** While the active writer holds the write lock, a third connection with zero lock timeout receives `SQLITE_BUSY` on `BEGIN IMMEDIATE`.
- **Concurrent reads and batch rollback:** Four concurrent roster readers saw committed grades. Two valid edits followed by an invalid score were rolled back as a batch. All original grades were preserved.

---

### Activity 4: NoSQL and Document Data Model
- **Access Pattern Problem:** Rendering student transcripts in 3NF requires a four-table relational join (`registration` JOIN `offering` JOIN `course` JOIN `term`), which can increase load during semester grade publication.
- **Document Model Solution:** Implemented a document collection (`transcript`) storing pre-materialized semester result documents in JSON format, identified by `student:{student_id}:term:{term_id}`.
- **JSON Syntax Validation & Querying:** Validated via `CHECK (json_valid(body))`. Embedded array items were queried using SQLite's JSON functions:
  ```sql
  SELECT json_extract(result.value, '$.score')
  FROM transcript, json_each(transcript.body, '$.results') AS result
  WHERE transcript.id = 'student:100:term:1' AND json_extract(result.value, '$.course') = 'MIT8103';
  ```
  *(Returned: `[(85,)]` without table joins).*
- **Refresh and field checks:** The publication function rejects missing required fields and out-of-range scores. A committed grade correction refreshed the same document from 85 to 90. Retrying kept one document.
- **Trade-off Evaluation:** Full transcript retrieval is an **O(log N) B-tree lookup**, bypassing relational joins entirely. The trade-off is data duplication of course titles, requiring an asynchronous cache refresh or event-driven materialization upon master course title modifications.

---

### Activity 5: Distributed and Cloud Database Architecture
- **Multi-AZ High Availability:** Proposed Aurora PostgreSQL with an AZ-separated writer and promotable reader sharing storage replicated synchronously across three AZs. Target RPO = 0 for a single-AZ failure and RTO under 60 seconds with a promotable reader, subject to testing and application reconnection.
- **Read Scaling & Replication Lag:** Readers serve transcript requests. After a grade commit, keep the instructor’s reads on the writer until a candidate reader can confirm it has applied the relevant change. Use the writer whenever catch-up cannot be confirmed.
- **Partitioning & Disaster Recovery:** Evaluated campus-level vs hash-based student sharding; recommended keeping active academic terms centralized on an Aurora cluster while archiving graduated terms into cold object storage. Aurora automated backups support point-in-time recovery within the configured retention window.

---

## 3. Individual Technical Reflection

### Design Decisions & Index Alignment
During implementation, the primary challenge involved balancing relational strictness with read performance. In Portfolio 2, the composite primary key `(student_id, offering_id)` was optimal for verifying student uniqueness, but penalised queries filtering by `offering_id`. Analyzing SQLite query plans highlighted how column order in B-trees dictates index usability. Designing the covering index `(offering_id, student_id, score)` resolved this by aligning index order with filter and sort predicates, cutting query latency from 9.285 ms to 0.767 ms.

### Concurrency Observations
In Portfolio 3, testing concurrent connections under SQLite WAL demonstrated the real-world trade-off between concurrency and isolation. While WAL provides non-blocking reads, SQLite's single-writer architecture surfaces `database is locked` when multiple transactions attempt concurrent write locks. In an enterprise system like PostgreSQL, row-level locks (`SELECT ... FOR UPDATE`) or optimistic concurrency control (`version` columns) would be preferred to handle high-volume simultaneous grading sessions.

### Key Lessons Learned
The exercise emphasized polyglot persistence: relational engines excel as transactional systems of record (ACID, normalisation, constraints), whereas document stores shine as read-optimized materialized views (denormalisation, single-key fetches).

---

## 4. Academic Integrity & AI-Use Declaration

In compliance with Section 11 of the MIT 8103 Course Assessment requirements, the following declaration discloses external tools and assistance:

1. **AI Tool Used:** Antigravity (Google DeepMind).
2. **Scope of AI Assistance:**
   - Antigravity was used as an interactive AI pair-programming assistant to help draft relational schema boilerplate (`schema.sql`), construct the synthetic test data generator loop, and format Markdown and Mermaid architectural diagrams.
3. **Student Verification & Ownership:**
   - I defined the specific business rules, integrity constraints, and grading logic for the Riverside University case study.
   - I formulated the SQL queries and designed the covering index structure.
   - I executed all test suites locally on Windows using Python 3.14 and SQLite, benchmarked the execution times, validated constraint rejections, and confirmed WAL concurrency behaviors.
   - I authored the technical reflections, structured the repository, and conducted the final submission review.

---

## 5. References & Resources

1. Date, C. J. (2019). *Database Design and Relational Theory: Normal Forms and All That Jazz*. O'Reilly Media.
2. Silberschatz, A., Korth, H. F., & Sudarshan, S. (2020). *Database System Concepts* (7th ed.). McGraw-Hill.
3. SQLite Documentation (2026). *Write-Ahead Logging (WAL) and Query Planner Analysis*. Available at: https://www.sqlite.org/wal.html
4. Kleppmann, M. (2017). *Designing Data-Intensive Applications: The Big Ideas Behind Reliable, Scalable, and Maintainable Systems*. O'Reilly Media.
