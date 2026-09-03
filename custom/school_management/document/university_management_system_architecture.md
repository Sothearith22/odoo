# 🎓 University Management System --- Full Architecture

The key idea is: **Student is not the whole system. Academic structure,
enrollment, subjects, semesters, exams, results, fees, and users all
interact.**

## 1. 🏛️ University Structure

``` text
University
│
├── Faculty
│      │
│      └── Department
│              │
│              └── Program
│                      │
│                      └── Subject
```

Example:

``` text
Royal University
│
├── Faculty of IT
│   │
│   ├── Department of Computer Science
│   │   └── Bachelor of Computer Science
│   │
│   └── Department of Information Technology
│       └── Bachelor of IT
│
└── Faculty of Business
    │
    ├── Department of Accounting
    └── Department of Management
```

### Odoo models

``` text
university.faculty
university.department
university.program
university.subject
```

## 2. 👨‍🎓 Student Architecture

Student should contain **identity**, not everything.

``` text
university.student
│
├── Student ID
├── Name
├── Photo
├── Gender
├── Date of Birth
│
├── Contact Information
│   ├── Phone
│   ├── Email
│   └── Address
│
├── Emergency Contact
│
├── Academic Information
│   ├── Program
│   ├── Department
│   ├── Academic Year
│   └── Current Semester
│
└── Status
    ├── Active
    ├── Suspended
    ├── Graduated
    └── Dropped
```

**Important:** Don't put semester, subject, exam, fee, and result
directly as simple fields on Student. Those are separate business
records.

## 3. 📚 Academic Structure

``` text
Faculty
   ↓
Department
   ↓
Program
   ↓
Subject
```

Example:

``` text
Faculty of IT
     ↓
Computer Science Department
     ↓
Bachelor of Computer Science
     ↓
Year 3
     ↓
Semester 1
     ↓
Database Management
```

## 4. 📅 Academic Year & Semester

Create:

``` text
university.academic.year
university.semester
```

Example:

``` text
Academic Year
2026 - 2027
│
├── Semester 1
│
└── Semester 2
```

This is important because a student's academic data changes over time.

## 5. 📝 Enrollment

Don't connect Student directly to Subject with a simple Many2many.

Instead create an **Enrollment** model.

``` text
university.enrollment
```

Relationship:

``` text
Student
   │
   └── Enrollment
          │
          ├── Academic Year
          ├── Semester
          ├── Program
          └── Subjects
```

Example:

``` text
Sothearith
│
└── Enrollment 2026 / Semester 1
      │
      ├── Database
      ├── Java
      ├── Web Development
      └── Software Engineering
```

This gives you historical records.

## 6. 👨‍🏫 Teacher Architecture

``` text
university.teacher
│
├── Employee Information
├── Teacher ID
├── Name
├── Email
├── Phone
│
├── Department
│
└── Subjects
```

A teacher can teach multiple subjects.

## 7. 🏫 Class / Section

A **subject** and a **class section** should be different concepts.

``` text
Subject:
Database Management
```

Could have:

``` text
Database Management
│
├── Section A
│   └── Teacher: Mr. Dara
│
├── Section B
│   └── Teacher: Mr. Kim
│
└── Section C
    └── Teacher: Ms. Lina
```

Model:

``` text
university.class.section
```

## 8. 🕐 Class Schedule

``` text
university.schedule
```

Example:

``` text
Monday
│
├── 8:00 - 10:00
│   Database
│   Room: A101
│
├── 10:00 - 12:00
│   Java
│   Room: B201
│
└── 1:00 - 3:00
    Web Development
    Room: Lab 1
```

Relationships:

``` text
Schedule
├── Subject
├── Teacher
├── Classroom
├── Day
├── Start Time
└── End Time
```

## 9. 📅 Attendance

Attendance should be its own transaction.

``` text
university.attendance
```

Example:

``` text
Student       Subject       Date        Status
------------------------------------------------
Sothearith    Database      28/08       Present
Dara          Database      28/08       Absent
Kim           Database      28/08       Late
```

Possible status:

``` text
Present
Absent
Late
Excused
```

## 10. 📝 Examination Architecture

Don't make one `exam` record contain everything.

Use:

``` text
Exam
  ↓
Exam Schedule
  ↓
Exam Result
```

Example:

``` text
Midterm Examination
│
├── Database
│   └── 20 Aug
│
├── Java
│   └── 22 Aug
│
└── Web Development
    └── 25 Aug
```

## 11. 📊 Result Architecture

``` text
Student
   │
   ↓
Enrollment
   │
   ↓
Subject
   │
   ↓
Assessment
   │
   ├── Assignment
   ├── Midterm
   ├── Final
   └── Project
   │
   ↓
Result
```

Example:

``` text
Sothearith
│
└── Database
     │
     ├── Assignment    18/20
     ├── Midterm       25/30
     ├── Final         42/50
     │
     └── Total         85/100
                         ↓
                       Grade A
                         ↓
                       GPA 4.0
```

## 12. 🎯 Grade System

Create:

``` text
university.grade
```

Example:

  Score    Grade     GPA
  -------- ------- -----
  90-100   A         4.0
  85-89    B+        3.5
  80-84    B         3.0
  75-79    C+        2.5
  70-74    C         2.0
  60-69    D         1.0
  \<60     F         0.0

Then calculate:

``` text
Semester GPA
       ↓
Cumulative GPA
       ↓
Academic Standing
```

## 13. 💰 Fee Architecture

Fees should also be transactions.

``` text
Student
   │
   ↓
Fee Invoice
   │
   ├── Tuition
   ├── Registration
   ├── Library
   ├── Laboratory
   └── Other
          │
          ↓
       Payment
```

Example:

``` text
Invoice #INV-001

Tuition             $500
Registration         $50
Library               $20
-------------------------
Total                $570

Paid                 $570
Balance                $0
```

Later you can integrate Odoo's accounting functionality rather than
rebuilding an accounting system yourself.

## 14. 🎓 Scholarship

``` text
university.scholarship
```

Relationship:

``` text
Student
   ↓
Scholarship
   ├── Type
   ├── Percentage
   ├── Amount
   ├── Start Date
   └── End Date
```

Example:

``` text
Tuition:       $500
Scholarship:    50%
------------------
Pay:           $250
```

## 15. 🎓 Graduation

A university system should eventually have:

``` text
university.graduation
```

Flow:

``` text
Student
   ↓
Complete Required Subjects
   ↓
Earn Required Credits
   ↓
Meet GPA Requirement
   ↓
Graduation
   ↓
Certificate
```

Example:

``` text
Student: Sothearith Kim

Program: Bachelor of IT

Required Credits: 120
Completed Credits: 120

GPA: 3.42

Status: Eligible for Graduation
```

## 16. 🏠 Classroom

``` text
university.building
       ↓
university.classroom
```

Example:

``` text
Building A
│
├── A101
├── A102
└── A103

Building B
│
├── B201
└── B202
```

Classrooms can contain:

``` text
Room Number
Capacity
Building
Type
Equipment
```

## 17. 👥 User & Security Architecture

Because this is Odoo, think about **users and access rights**.

``` text
                    ODOO USERS
                        │
       ┌────────────────┼────────────────┐
       ↓                ↓                ↓
    Student          Teacher            Admin
       │                │                │
       ↓                ↓                ↓
 View own          Manage classes     Full access
 results           Attendance
 fees              Results
 schedule
```

Roles could be:

``` text
University Admin
Faculty Admin
Department Manager
Teacher
Student
Accountant
Registrar
```

## 18. 📊 Dashboard

Your main dashboard can show:

``` text
┌─────────────────────────────────────────────────────┐
│              UNIVERSITY DASHBOARD                   │
├────────────┬────────────┬────────────┬──────────────┤
│ Students   │ Teachers   │ Programs   │ Departments  │
│   5,240    │    320     │    25      │      12      │
├────────────┴────────────┴────────────┴──────────────┤
│                                                     │
│ 📊 Student Statistics                               │
│                                                     │
│ Active        4,850                                 │
│ Graduated       320                                 │
│ Suspended        40                                 │
│                                                     │
├────────────────────────┬────────────────────────────┤
│ 📅 Today's Classes     │ 💰 Fee Status              │
│                        │                            │
│ 45 Classes             │ Paid       $125K           │
│ 12 Exams               │ Unpaid      $18K           │
│ 86% Attendance         │ Scholarship $32K           │
└────────────────────────┴────────────────────────────┘
```

## 🧩 Complete Model Architecture

``` text
UNIVERSITY
│
├── 🏛️ ORGANIZATION
│   ├── Faculty
│   ├── Department
│   ├── Program
│   └── Academic Year
│
├── 👨‍🎓 PEOPLE
│   ├── Student
│   ├── Teacher
│   ├── Staff
│   └── Guardian
│
├── 📚 ACADEMIC
│   ├── Subject
│   ├── Semester
│   ├── Enrollment
│   ├── Class Section
│   └── Academic Credit
│
├── 🕐 SCHEDULE
│   ├── Building
│   ├── Classroom
│   └── Schedule
│
├── 📅 ATTENDANCE
│   └── Attendance
│
├── 📝 EXAMINATION
│   ├── Exam
│   ├── Exam Schedule
│   ├── Assessment
│   ├── Result
│   └── Grade
│
├── 💰 FINANCE
│   ├── Fee
│   ├── Invoice
│   ├── Payment
│   └── Scholarship
│
├── 🎓 GRADUATION
│   ├── Graduation
│   ├── Certificate
│   └── Transcript
│
└── 🔐 SECURITY
    ├── Admin
    ├── Teacher
    ├── Student
    ├── Accountant
    └── Registrar
```

## 🔗 Core ERD

``` text
Faculty
   │
   ↓
Department
   │
   ↓
Program
   │
   ├───────────────┐
   ↓               ↓
Subject         Student
   │               │
   │               ↓
   │          Enrollment
   │               │
   │               ↓
   │          Class Section
   │               │
   ├───────────────┤
   ↓               ↓
Schedule       Attendance
   │
   ↓
Exam
   │
   ↓
Result
   │
   ↓
Grade
   │
   ↓
GPA

Student ─────── Fee ─────── Payment
   │
   └────────── Scholarship

Student ─────── Graduation ─────── Certificate
```

## ⭐ Core Mental Model

Think of the system as **five layers**:

``` text
1. STRUCTURE
   Faculty → Department → Program → Subject

2. PEOPLE
   Student → Teacher → Staff

3. ACADEMIC ACTIVITY
   Enrollment → Class → Schedule → Attendance

4. ASSESSMENT
   Exam → Assessment → Result → Grade → GPA

5. MONEY
   Fee → Invoice → Payment → Scholarship
```

## 🚀 Recommended Implementation Order

Don't implement everything at once.

### Phase 1 --- Foundation

``` text
Student
Faculty
Department
Program
Subject
```

### Phase 2 --- Academic

``` text
Academic Year
Semester
Enrollment
Class Section
Teacher
```

### Phase 3 --- Academic Operations

``` text
Classroom
Schedule
Attendance
```

### Phase 4 --- Examination

``` text
Exam
Assessment
Result
Grade
GPA
```

### Phase 5 --- Finance

``` text
Fee
Invoice
Payment
Scholarship
```

### Phase 6 --- Graduation

``` text
Graduation
Certificate
Transcript
```

### Phase 7 --- Dashboard & Security

``` text
Dashboard
KPI Cards
Charts
Reports
Access Rights
User Roles
```

The goal is to build this progressively so each Odoo concept is
understandable rather than copying a huge project all at once.
