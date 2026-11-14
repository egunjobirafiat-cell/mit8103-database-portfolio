-- Grade Roster Extraction Query
-- Retrieves all graded student registrations for a single course offering
SELECT student_id, score
FROM registration
WHERE offering_id = ? AND score IS NOT NULL
ORDER BY student_id;
