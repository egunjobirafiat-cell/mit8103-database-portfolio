-- Semester GPA Calculation Query
-- Computes Grade Points, Quality Points, and Semester GPA for a student
-- Based on the Nigerian 5.0 tertiary grading scale:
-- 70 - 100: A (5 points), 60 - 69: B (4 points), 50 - 59: C (3 points), 45 - 49: D (2 points), < 45: F (0 points)

SELECT 
    r.student_id,
    s.name AS student_name,
    t.label AS term_label,
    COUNT(c.id) AS courses_taken,
    SUM(c.credits) AS total_credits,
    ROUND(SUM(c.credits * (
        CASE 
            WHEN r.score >= 70 THEN 5.0
            WHEN r.score >= 60 THEN 4.0
            WHEN r.score >= 50 THEN 3.0
            WHEN r.score >= 45 THEN 2.0
            ELSE 0.0
        END
    )), 2) AS total_quality_points,
    ROUND(SUM(c.credits * (
        CASE 
            WHEN r.score >= 70 THEN 5.0
            WHEN r.score >= 60 THEN 4.0
            WHEN r.score >= 50 THEN 3.0
            WHEN r.score >= 45 THEN 2.0
            ELSE 0.0
        END
    )) / CAST(SUM(c.credits) AS REAL), 2) AS semester_gpa
FROM registration AS r
JOIN student AS s ON s.id = r.student_id
JOIN offering AS o ON o.id = r.offering_id
JOIN course AS c ON c.id = o.course_id
JOIN term AS t ON t.id = o.term_id
WHERE r.student_id = ? AND t.id = ? AND r.score IS NOT NULL
GROUP BY r.student_id, s.name, t.label;
