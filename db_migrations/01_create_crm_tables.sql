-- EduVision CRM Database Schema
-- Migration: Create core tables for courses, groups, lessons, attendance, and payments

-- Курси
CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    duration_months INT,
    age_min INT,
    age_max INT,
    price DECIMAL(10,2),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Групи
CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    course_id INT REFERENCES courses(id) ON DELETE SET NULL,
    teacher_id INT,
    max_students INT DEFAULT 10,
    schedule JSONB,
    room VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Учні в групах
CREATE TABLE IF NOT EXISTS group_students (
    id SERIAL PRIMARY KEY,
    group_id INT REFERENCES groups(id) ON DELETE CASCADE,
    student_id INT,
    enrolled_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'active',
    UNIQUE(group_id, student_id)
);

-- Заняття
CREATE TABLE IF NOT EXISTS lessons (
    id SERIAL PRIMARY KEY,
    group_id INT REFERENCES groups(id) ON DELETE CASCADE,
    scheduled_at TIMESTAMP NOT NULL,
    topic VARCHAR(255),
    homework TEXT,
    status VARCHAR(20) DEFAULT 'scheduled',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Відвідуваність
CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    lesson_id INT REFERENCES lessons(id) ON DELETE CASCADE,
    student_id INT,
    status VARCHAR(20),
    note TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(lesson_id, student_id)
);

-- Оплати
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    student_id INT,
    parent_id INT,
    amount DECIMAL(10,2) NOT NULL,
    paid_at TIMESTAMP DEFAULT NOW(),
    period_start DATE,
    period_end DATE,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Індекси для покращення продуктивності
CREATE INDEX IF NOT EXISTS idx_groups_course ON groups(course_id);
CREATE INDEX IF NOT EXISTS idx_groups_teacher ON groups(teacher_id);
CREATE INDEX IF NOT EXISTS idx_group_students_group ON group_students(group_id);
CREATE INDEX IF NOT EXISTS idx_group_students_student ON group_students(student_id);
CREATE INDEX IF NOT EXISTS idx_lessons_group ON lessons(group_id);
CREATE INDEX IF NOT EXISTS idx_attendance_lesson ON attendance(lesson_id);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);
CREATE INDEX IF NOT EXISTS idx_payments_student ON payments(student_id);
CREATE INDEX IF NOT EXISTS idx_payments_parent ON payments(parent_id);
