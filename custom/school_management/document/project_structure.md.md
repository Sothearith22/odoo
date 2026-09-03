# University Management System
#
# Models (_name) grouped by module area.
# "*"  = implemented in the current codebase
# "+"  = planned (to be implemented after role management)


# └── Dashboard
#     └── school.dashboard                  *


# ├── Structure
# │   ├── university.faculty                *
# │   ├── university.department             *
# │   ├── university.program                *
# │   ├── university.subject                *
# │   ├── university.class.section          *
# │   └── university.classroom              *


# ├── Students
# │   ├── university.student                *
# │   └── university.enrollment             *


# ├── Teachers
# │   └── university.teacher                *


# ├── Academic
# │   ├── university.academic.year          *
# │   ├── university.semester               *
# │   └── university.semester.subject       *


# ├── Attendance
# │   └── university.attendance             +


# ├── Exams
# │   ├── university.exam                   +
# │   ├── university.assessment             +
# │   ├── university.result                 +
# │   └── university.grade                  +


# └── Finance
#     ├── university.fee   (+ fee.line)     *
#     └── university.payment                *


1. # Other planned models
2. # ├── university.schedule                   +
3. # ├── university.scholarship                +
4. # ├── university.graduation                 +
5. # └── university.certificate                +

# Wizards (transient models)
# ├── university.enrollment.wizard          *
# └── university.student.enrollment.wizard  *
