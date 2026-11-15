# Portfolio 3: Transactions and Concurrency

**Student:** Rafiat Egunjobi  
**Course:** MIT 8103 Advanced Database Systems  
**Institution:** School of Postgraduate Studies, MIVA Open University  
**Case Study:** Riverside University Student Result Portal  

---

## 1. Concurrency Requirements in the Result Portal

During examination grading and course registration periods, hundreds of students and faculty access the portal concurrently. The database engine must guarantee strict **ACID** properties:
- **Atomicity:** When an instructor uploads continuous assessment grades for a class, all scores in the batch must be saved, or none if an error occurs.
- **Consistency:** Marks must always satisfy integrity constraints (`0 <= score <= 100`) regardless of concurrent access.
- **Isolation:** A student viewing their result slip must never observe partially entered, uncommitted grades while an instructor is actively submitting marks.
- **Durability:** Once committed, grades must survive power failures or process crashes.

---

## 2. SQLite Write-Ahead Logging (WAL) Architecture

By default, SQLite uses rollback journal mode, where write operations place an exclusive lock on the database file, blocking concurrent readers.

To improve concurrency, the database operates in **WAL mode**:
```sql
PRAGMA journal_mode = WAL;
```

In WAL mode:
- Changes are appended to a separate `-wal` file rather than modifying the main database file directly.
- Readers read from a point-in-time snapshot of the database and never block writers.
- Writers append changes to the WAL file and never block readers.
- However, SQLite enforces a **single active writer at a time**. Concurrent write attempts must either wait or fail with a lock contention error (`SQLITE_BUSY`).

---

## 3. Three-Connection Concurrency Demonstration

The demonstration uses three connections. The reader opens a transaction and reads 52, establishing its snapshot. The active writer starts `BEGIN IMMEDIATE` and updates the grade to 85. A separate competing writer with a zero-second timeout receives `SQLITE_BUSY`.

After the active writer commits, the reader still sees 52 within its open transaction. Once that transaction ends, a fresh read sees 85. Four worker connections also read the roster while the writer held its transaction open. All saw the committed grades. In a later batch, two valid updates were staged before a third failed its score check. An explicit rollback restored all three original grades.

```mermaid
sequenceDiagram
    participant Reader
    participant Writer
    participant Competitor as Competing writer
    Reader->>Reader: BEGIN and read 52
    Writer->>Writer: BEGIN IMMEDIATE and update to 85
    Competitor->>Competitor: BEGIN IMMEDIATE returns SQLITE_BUSY
    Writer->>Writer: COMMIT
    Reader->>Reader: Read 52 in the open transaction
    Reader->>Reader: End transaction and read 85
    Writer->>Writer: Stage two valid grades and attempt an invalid grade
    Writer->>Writer: ROLLBACK failed batch
    Reader->>Reader: Verify all three original grades
```

This demonstrates repeatable reads across a concurrent commit, single-writer contention, commit visibility, and rollback of the whole failed batch. See [execution output](../evidence.txt).

---

## 4. Scaling Beyond SQLite in Enterprise Production

While SQLite WAL mode works well for local testing and lightweight applications, a full-scale university portal with thousands of concurrent lecturers and students requires an enterprise database engine such as **PostgreSQL**:
- **Row-Level Locking:** In PostgreSQL, multiple lecturers can submit grades for different courses simultaneously (`SELECT ... FOR UPDATE`) without blocking one another.
- **Connection Pooling & Busy Timeout:** Production servers configure connection pools (e.g., PgBouncer) and exponential backoff retry loops rather than letting queries fail immediately on contention.
- **Optimistic Concurrency Control (OCC):** Storing a `version` or `updated_at` column on grade records allows client applications to detect conflicting edits to the same grade without long-held locks.
