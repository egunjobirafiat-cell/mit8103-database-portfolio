-- =============================================================
-- MIT 8103: Advanced Database Systems
-- Student: Rafiat Egunjobi (egunjobirafiat-cell)
-- Portfolio 1: Relational Database Schema & Integrity Rules
-- Case Study: Riverside University Student Result Portal
-- =============================================================

PRAGMA foreign_keys = ON;

-- 1. Academic departments
CREATE TABLE department (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- 2. Students admitted into departments
CREATE TABLE student (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (department_id) REFERENCES department(id)
);

-- 3. Academic lecturers / instructors
CREATE TABLE lecturer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (department_id) REFERENCES department(id)
);

-- 4. Course catalogue
CREATE TABLE course (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL CHECK (typeof(credits) = 'integer' AND credits BETWEEN 1 AND 6),
    FOREIGN KEY (department_id) REFERENCES department(id)
);

-- 5. Academic calendar terms / semesters
CREATE TABLE term (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL UNIQUE
);

-- 6. Course offerings (sections scheduled in a term)
CREATE TABLE offering (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    term_id INTEGER NOT NULL,
    lecturer_id INTEGER NOT NULL,
    section INTEGER NOT NULL CHECK (typeof(section) = 'integer' AND section > 0),
    FOREIGN KEY (course_id) REFERENCES course(id),
    FOREIGN KEY (term_id) REFERENCES term(id),
    FOREIGN KEY (lecturer_id) REFERENCES lecturer(id),
    UNIQUE (course_id, term_id, section)
);

-- 7. Student registrations and recorded grades
CREATE TABLE registration (
    student_id INTEGER NOT NULL,
    offering_id INTEGER NOT NULL,
    score INTEGER CHECK (score IS NULL OR (typeof(score) = 'integer' AND score BETWEEN 0 AND 100)),
    PRIMARY KEY (student_id, offering_id),
    FOREIGN KEY (student_id) REFERENCES student(id),
    FOREIGN KEY (offering_id) REFERENCES offering(id)
);

CREATE TRIGGER registration_one_section_insert
BEFORE INSERT ON registration
WHEN EXISTS (
    SELECT 1
    FROM registration AS r
    JOIN offering AS current ON current.id = r.offering_id
    JOIN offering AS target ON target.id = NEW.offering_id
    WHERE r.student_id = NEW.student_id
      AND current.course_id = target.course_id
      AND current.term_id = target.term_id
      AND r.offering_id <> NEW.offering_id
)
BEGIN
    SELECT RAISE(ABORT, 'Student already registered for this course and term');
END;

CREATE TRIGGER registration_one_section_update
BEFORE UPDATE OF student_id, offering_id ON registration
WHEN EXISTS (
    SELECT 1
    FROM registration AS r
    JOIN offering AS current ON current.id = r.offering_id
    JOIN offering AS target ON target.id = NEW.offering_id
    WHERE r.student_id = NEW.student_id
      AND current.course_id = target.course_id
      AND current.term_id = target.term_id
      AND r.offering_id <> NEW.offering_id
      AND (r.student_id <> OLD.student_id OR r.offering_id <> OLD.offering_id)
)
BEGIN
    SELECT RAISE(ABORT, 'Student already registered for this course and term');
END;

-- Preserve the enrolment rule when scheduling details change.
CREATE TRIGGER offering_preserve_enrolled_course_term
BEFORE UPDATE OF course_id, term_id ON offering
WHEN (NEW.course_id <> OLD.course_id OR NEW.term_id <> OLD.term_id)
 AND EXISTS (SELECT 1 FROM registration WHERE offering_id = OLD.id)
BEGIN
    SELECT RAISE(ABORT, 'Cannot change the course or term of an enrolled offering');
END;

-- -------------------------------------------------------------
-- Baseline Seed Data
-- -------------------------------------------------------------
INSERT INTO department (id, name) VALUES (1, 'Computing');
INSERT INTO lecturer (id, department_id, name) VALUES (1, 1, 'Dr. Arinze Okoli');
INSERT INTO course (id, department_id, code, title, credits) VALUES 
    (1, 1, 'MIT8103', 'Advanced Database Systems', 3),
    (2, 1, 'MIT8101', 'Advanced Software Engineering', 3),
    (3, 1, 'MIT8105', 'Research Methods in IT', 2);

INSERT INTO term (id, label) VALUES (1, '2026/2027 Semester 1');

INSERT INTO offering (id, course_id, term_id, lecturer_id, section) VALUES 
    (1, 1, 1, 1, 1),
    (2, 1, 1, 1, 2),
    (3, 2, 1, 1, 1),
    (4, 3, 1, 1, 1);
