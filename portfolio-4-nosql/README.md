# Portfolio 4: NoSQL and Advanced Data Models

**Student:** Rafiat Egunjobi  
**Course:** MIT 8103 Advanced Database Systems  
**Institution:** School of Postgraduate Studies, MIVA Open University  
**Case Study:** Riverside University Student Result Portal  

---

## 1. Business Motivation for a Document Model

In a 3NF relational database, generating a student's semester transcript or result slip requires joining four separate tables:
- `registration` JOIN `offering` JOIN `course` JOIN `term`.

During semester results publication week, tens of thousands of students repeatedly query the portal to view their result slips. Executing thousands of 4-table relational joins concurrently creates severe server CPU, memory, and disk I/O bottlenecks.

To eliminate join overhead on high-frequency read paths, I implemented a **Document Data Model** (JSON format) for student semester transcripts.

---

## 2. Document Data Model Design

Rather than distributing student marks across separate tables, all course results for a student's term are embedded in a single hierarchical JSON document:

- **Document Key:** `student:100:term:1`
- **Document Body:**
```json
{
  "student_id": 100,
  "term": "2026/2027 Semester 1",
  "results": [
    {
      "course": "MIT8103",
      "title": "Advanced Database Systems",
      "section": 1,
      "score": 85
    },
    {
      "course": "MIT8101",
      "title": "Advanced Software Engineering",
      "section": 1,
      "score": 78
    }
  ]
}
```

---

## 3. Implementation in SQLite

Using SQLite's built-in JSON1 extension, a dedicated `transcript` document store was created with structural JSON validation:

```sql
CREATE TABLE transcript (
    id TEXT PRIMARY KEY,
    body TEXT NOT NULL CHECK (json_valid(body))
);
```

### Querying Inside the Document
To retrieve an individual course score from the embedded JSON array:

```sql
SELECT json_extract(result.value, '$.score') AS course_score
FROM transcript, json_each(transcript.body, '$.results') AS result
WHERE transcript.id = 'student:100:term:1' 
  AND json_extract(result.value, '$.course') = 'MIT8103';
```

**Output from `run.py`:**
```text
4. Document storage and retrieval
{
  "student_id": 100,
  "term": "2026/2027 Semester 1",
  "results": [
    {
      "course": "MIT8103",
      "title": "Advanced Database Systems",
      "section": 1,
      "score": 85
    }
  ]
}
Embedded course scores: [(85,)]
```

---

## 4. Query Complexity and Performance Analysis

- **Full Transcript Retrieval:** Fetching an entire student transcript (`SELECT body FROM transcript WHERE id = ?`) is an **O(1) primary key point lookup**. It retrieves the complete pre-rendered result slip in a single read operation, completely bypassing relational joins.
- **Embedded Array Filtering:** Querying a specific course mark inside the document via `json_extract()` and `json_each()` performs an in-memory scan of that individual student's courses (typically 4–6 courses per term), which is computationally trivial compared to joining 50,000-row relational tables.

---

## 5. Architectural Trade-offs & Polyglot Persistence

| Comparison Dimension | Relational Model (3NF) | Document Model (JSON / NoSQL) |
| :--- | :--- | :--- |
| **Primary Use Case** | Transactional grade recording and continuous assessment updates. | High-traffic transcript lookups and mobile app result rendering. |
| **Read Complexity** | High: 4-table join (`registration`, `offering`, `course`, `term`). | Low: Direct single-document primary key point lookup. |
| **Write Performance** | High: Updates only the single modified score integer in place. | Moderate: Requires rewriting or patching the JSON document. |
| **Data Duplication** | Zero redundancy (3NF). | Course titles and term labels are duplicated across student documents. |
| **Consistency Model** | Immediate Consistency (ACID). | Eventual Consistency (Materialized view / cache). |

### Recommended Production Architecture:
In production, a **Polyglot Persistence** architecture is ideal:
1. **Relational Database (e.g. PostgreSQL):** Serves as the authoritative **System of Record (SoR)** where lecturers enter grades and registry staff manage courses with strict ACID guarantees.
2. **Document Cache (e.g. MongoDB, AWS DocumentDB, or PostgreSQL JSONB):** Once semester grades are locked and approved by the academic senate, an asynchronous worker pre-computes and materializes student transcripts into the document store. This gives students sub-millisecond transcript loading without impacting transactional grading systems.
