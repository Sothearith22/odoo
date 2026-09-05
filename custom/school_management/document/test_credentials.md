# Testing & Demo Credentials

Working login accounts for testing the **University Management System** locally.
These accounts were created directly in the database and all logins were verified.

## Base URL

Open your browser and go to: **http://localhost:8070/web/login**

---

## 1. Active login accounts (verified working)

| Role | Username | Password | Groups | Linked teacher |
|------|----------|----------|--------|----------------|
| Administrator | `admin` | `Admin@123` | Administrator | — |
| Dean | `dean` | `Dean@123` | School User, Teacher, HOD, Dean | Dr. John Doe (TCH-001) |
| Head of Department | `hod` | `Hod@123` | School User, Teacher, HOD | Prof. Charles Xavier (TCH-005) |
| Teacher / Lecturer | `teacher` | `Teacher@123` | School User, Teacher | Dr. Gregory Hous (TCH-003) |
| Student | `student` | `Student@123` | School User, Student | — |

All accounts are **active** and the passwords were hashed correctly (verified via the
`/web/session/authenticate` endpoint).

> Tip: The `dean` user `teacher_id=3`, `hod` → `teacher_id=4`, `teacher` → `teacher_id=8`.
> These links are what make the role-based record rules effective when the role groups
> are used without the full `base.group_user`.

---

## 2. Notes

- The module does **not** create logins automatically — these were created for you.
- To change a password, log in as `admin`, go to **Settings → Users**, open the user, and set a new password.
- The role-level record scoping (Teacher sees own data, HOD their department, Dean their faculty)
  only fully takes effect for users who are **not** also in the default `base.group_user`
  broad group.
