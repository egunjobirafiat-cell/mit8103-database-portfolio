# Continuous Assessment Report: MIT 8103 Advanced Database Systems

**Student Name:** Rafiat Egunjobi  
**GitHub Username:** `egunjobirafiat-cell`  
**Course Code:** MIT 8103 — Advanced Database Systems  
**Programme:** Master of Information Technology (MIT)  
**Session / Semester:** 2026/2027 Academic Session — First Semester  
**Institution:** School of Postgraduate Studies, MIVA Open University  
**Private GitHub Repository:** `https://github.com/egunjobirafiat-cell/mit8103-database-portfolio`  
*(Assessor access granted via private repository collaborator invitation)*

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
- **Primary & Composite Keys:** `registration` utilizes a composite primary key `(student_id, offering_id)` guaranteeing that a student can only register once per course section per term.
- **Data Integrity Constraints:**
  - Foreign key constraints (`PRAGMA foreign_keys = ON`) enforce referential integrity across all relationships.
  - `CHECK (score IS NULL OR (typeof(score) = 'integer' AND score BETWEEN 0 AND 100))` enforces valid score bounds.
  - `CHECK (credits BETWEEN 1 AND 6)` and `CHECK (section > 0)` enforce academic course validity.
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
  Because `student_id` is the leading key column, SQLite had to inspect all 50,000 index rows, producing a median execution latency of **3.876 ms**.
- **Covering Index Implementation:** A composite covering index was constructed:
  `CREATE INDEX registration_roster ON registration(offering_id, student_id, score);`  
  `offering_id` satisfies the equality filter via a logarithmic B-tree search (O(log N)); `student_id` provides pre-sorted order; `score` covers the projection and NOT NULL predicate.
- **Post-Optimisation:** The query planner switched to a direct B-tree search:
  `SEARCH registration USING COVERING INDEX registration_roster (offering_id=?)`  
  Median latency dropped from **3.876 ms to 0.459 ms (~8.4x speedup / 88.2% reduction)** with zero table heap lookups.
- **Semester GPA Calculation:** Addressing the key case study operation on Page 2 of the brief, a GPA calculation query was implemented in `gpa_calculation.sql` based on the Nigerian 5.0 scale (A=5, B=4, C=3, D=2, F=0). For Student 100 across 3 courses (8 credit units), the system computed **32.00 quality points**, yielding a verified semester GPA of **4.00 / 5.00**.

---

### Activity 3: Transactions and Concurrency
- **Concurrency Architecture:** Configured Write-Ahead Logging (`PRAGMA journal_mode = WAL`) allowing simultaneous reading and writing without blocking readers.
- **Multi-Connection Experimentation:** Two concurrent database connections (`writer` and `reader`) were evaluated under zero-timeout conditions:
  1. **Snapshot Isolation:** While the writer initiated `BEGIN IMMEDIATE` and staged an uncommitted score change (from 52 to 85), the concurrent reader queried the record and consistently observed the original value (52), proving dirty reads are blocked.
  2. **Lock Contention:** A simultaneous write attempt by the reader was rejected with `OperationalError: database is locked (SQLITE_BUSY)`, demonstrating engine-level write serialization.
  3. **Durability & Visibility:** Following `writer.commit()`, the reader immediately observed the updated score (85).
  4. **Atomicity & Rollback:** A subsequent uncommitted score change to 10 was terminated via `ROLLBACK`; the reader verified the score remained unchanged at 85.

---

### Activity 4: NoSQL and Document Data Model
- **Access Pattern Problem:** Rendering student transcripts in 3NF requires a four-table relational join (`registration` JOIN `offering` JOIN `course` JOIN `term`), which becomes a severe bottleneck during semester grade publication.
- **Document Model Solution:** Implemented a document collection (`transcript`) storing pre-materialized semester result documents in JSON format, identified by `student:{student_id}:term:{term_id}`.
- **Schema Validation & Querying:** Validated via `CHECK (json_valid(body))`. Embedded array items were queried using SQLite's JSON functions:
  ```sql
  SELECT json_extract(result.value, '$.score')
  FROM transcript, json_each(transcript.body, '$.results') AS result
  WHERE transcript.id = 'student:100:term:1' AND json_extract(result.value, '$.course') = 'MIT8103';
  ```
  *(Returned: `[(85,)]` without table joins).*
- **Trade-off Evaluation:** Full transcript retrieval is an **O(1) primary key point lookup**, bypassing relational joins entirely. The trade-off is data duplication of course titles, requiring an asynchronous cache refresh or event-driven materialization upon master course title modifications.

---

### Activity 5: Distributed and Cloud Database Architecture
- **Multi-AZ High Availability:** Designed a cloud deployment using managed Multi-AZ database clustering (such as AWS Aurora / RDS) with a Primary instance in AZ-1 and a Synchronous Standby in AZ-2. Synchronous storage replication achieves zero data loss (Recovery Point Objective, RPO = 0), with automated failover in under 60 seconds (Recovery Time Objective, RTO < 60s).
- **Read Scaling & Replication Lag:** Asynchronous read replicas offload transcript queries. To prevent the "read-your-own-writes" inconsistency where lecturers view stale grades immediately after submission, session-level routing directs immediate post-submission requests from lecturers to the Primary node for 5–10 seconds.
- **Partitioning & Disaster Recovery:** Evaluated campus-level vs hash-based student sharding; recommended keeping active academic terms centralized on an Aurora cluster while archiving graduated terms into cold object storage. Continuous WAL streaming to Amazon S3 enables Point-in-Time Recovery (PITR).

---

## 3. Individual Technical Reflection

### Design Decisions & Index Alignment
During implementation, the primary challenge involved balancing relational strictness with read performance. In Portfolio 2, the composite primary key `(student_id, offering_id)` was optimal for verifying student uniqueness, but penalised queries filtering by `offering_id`. Analyzing SQLite query plans highlighted how column order in B-trees dictates index usability. Designing the covering index `(offering_id, student_id, score)` resolved this by aligning index order with filter and sort predicates, cutting query latency from 3.876 ms to 0.459 ms.

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
