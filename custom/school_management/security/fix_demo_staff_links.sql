-- Standalone equivalent of the module migration at
-- custom/school_management/data/fix_user_teacher_links.xml
-- (runs res.users._fix_demo_staff_links() on `-u school_management`).
--
-- Realigns the seeded demo staff logins so res.users.teacher_id and
-- university.teacher.user_id are reciprocal, pointing each login at the
-- teacher that ACTUALLY holds the matching active role assignment:
--     dean (9)     <-> teacher 4  Prof. Charles Xavier
--     hod  (10)    <-> teacher 6  Dr. Sarah Jenkins
--     teacher (11) <-> teacher 8  Dr. Gregory Hous
--
-- Statement order matters to respect the partial unique indexes:
--   res_users._unique_teacher_id     (teacher_id)
--   university_teacher._unique_user_id (user_id)
-- Run from psql or any SQL console, or `psql ... -f this file`.
-- Safe to re-run (idempotent) once all users/teachers are present.

BEGIN;

-- 1. Release the reverse (user_id) links currently held on the demo logins.
UPDATE university_teacher SET user_id = NULL WHERE user_id IN (9, 10, 11);

-- 2. Re-point forward (res_users.teacher_id): move 'hod' first so teacher 4
--    is freed before 'dean' takes it (teacher_id unique per user).
UPDATE res_users SET teacher_id = 6 WHERE id = 10;  -- hod  -> Dr. Sarah Jenkins
UPDATE res_users SET teacher_id = 4 WHERE id = 9;   -- dean -> Prof. Charles Xavier
-- (teacher 11 already points at teacher 8 / Dr. Gregory Hous)

-- 3. Re-point reverse (university.teacher.user_id): 4/6/8 targets are free.
UPDATE university_teacher SET user_id = 10 WHERE id = 6;  -- Dr. Sarah Jenkins said to 10
UPDATE university_teacher SET user_id = 9  WHERE id = 4;  -- Prof. Charles Xavier to 9
UPDATE university_teacher SET user_id = 11 WHERE id = 8;  -- Dr. Gregory Hous to 11

COMMIT;

-- Sanity check (expected)
SELECT u.id, u.login, u.teacher_id, t.name
FROM res_users u
JOIN university_teacher t ON t.id = u.teacher_id
WHERE u.login IN ('dean', 'hod', 'teacher')
ORDER BY u.id;