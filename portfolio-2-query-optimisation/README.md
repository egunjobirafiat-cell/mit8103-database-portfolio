# Portfolio 2: Query Processing and Optimisation

**Student:** Rafiat Egunjobi  
**Course:** MIT 8103 Advanced Database Systems  
**Institution:** School of Postgraduate Studies, MIVA Open University  
**Case Study:** Riverside University Student Result Portal  

---

## 1. Grade Roster Query Under Evaluation

One of the most frequent queries executed on the portal is a lecturer opening their assigned course offering to inspect registered students and their continuous assessment marks:

```sql
SELECT student_id, score
FROM registration
WHERE offering_id = ? AND score IS NOT NULL
ORDER BY student_id;
```

### Workload Testbed
To test this query realistically, the database is populated with **50,000 synthetic student registrations**. Offering 1 accounts for 1% of the dataset (500 registered students), with scores populated deterministically.

---

## 2. Query Execution Plan (Before Optimisation)

Initially, the only index on `registration` was the automatic composite primary key index: `(student_id, offering_id)`.

When running `EXPLAIN QUERY PLAN`:
```text
[(4, 0, 218, 'SCAN registration USING INDEX sqlite_autoindex_registration_1')]
```

### Why it required a full scan:
Because `student_id` is the leading column in the composite primary key, SQLite cannot perform a direct B-tree search on `offering_id`. The engine is forced to scan through all 50,000 index entries to evaluate the `WHERE offering_id = 1` condition, and then fetch each matching row from the table to inspect `score`.

- **Result Count:** 500 rows
- **Execution Method:** Full index scan of 50,000 entries + table page lookups

---

## 3. Covering Index Design

To eliminate the scan and table lookups, I constructed a composite covering index:

```sql
CREATE INDEX registration_roster 
ON registration(offering_id, student_id, score);
```

### Why this index structure works:
1. **`offering_id` as the leading column:** Satisfies the equality predicate `WHERE offering_id = ?`, allowing SQLite to perform an immediate logarithmic B-tree seek ($O(\log N)$) directly to the first matching row.
2. **`student_id` as the second column:** Matches the `ORDER BY student_id` clause. Because B-tree leaf nodes are pre-sorted in ascending order, SQLite satisfies the ordering without an in-memory sort.
3. **`score` as the third column:** Covers the projection (`SELECT student_id, score`) and the filter `score IS NOT NULL`.
4. **Covering Property:** All requested columns exist entirely within the index leaf pages. Zero table heap page accesses are performed.

---

## 4. Query Execution Plan (After Optimisation)

Running `EXPLAIN QUERY PLAN` with the covering index in place:
```text
[(3, 0, 56, 'SEARCH registration USING COVERING INDEX registration_roster (offering_id=?)')]
```

- The access method changed from `SCAN` to `SEARCH ... USING COVERING INDEX`.
- The query returns the exact same 500 rows.
- Query latency is reduced by 88.2% (benchmark results documented in `evidence.txt`).

---

## 5. Additional Case Study Operation: Semester GPA Calculation

Page 2 of the course brief explicitly lists **"compute GPA"** as an expected database operation for this case study.

I implemented a comprehensive GPA calculation query in [`gpa_calculation.sql`](gpa_calculation.sql) using the standard Nigerian 5.0 academic grading scale:
- 70–100: **A** (5.0 Grade Points)
- 60–69: **B** (4.0 Grade Points)
- 50–59: **C** (3.0 Grade Points)
- 45–49: **D** (2.0 Grade Points)
- 0–44: **F** (0.0 Grade Points)

$$\text{GPA} = \frac{\sum (\text{credits} \times \text{grade\_points})}{\sum \text{credits}}$$

The query joins `registration`, `offering`, `course`, and `term` to compute total credits, total quality points, and the final semester GPA. Testing student 100 across 3 enrolled courses yielded a verified semester GPA of **4.00 / 5.00** (computed by hand as: (3 credits × 3 grade points [C] + 3 credits × 5 grade points [A] + 2 credits × 4 grade points [B]) / 8 total credits = 32.00 / 8.0 = 4.00).

---

## 6. Indexing Trade-offs in Production

- **Read Acceleration:** The covering index provides massive speedups for class rosters, audit reports, and grade reviews.
- **Write Penalty:** Every `INSERT` of a course registration or `UPDATE` of a score requires modifying both the primary key B-tree and the `registration_roster` index B-tree.
- **Decision:** Because result portal rosters are viewed thousands of times during grading and audit periods compared to occasional grade submissions, the covering index provides an optimal cost-to-benefit ratio.
