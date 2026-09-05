# University Management System
#
# Codebase-aligned model map as of 2026-09-04.
# "*" = implemented in the current addon
# "+" = planned / not yet implemented
# "ext" = extension of an existing Odoo model
# "wiz" = transient model wizard

# Dashboard
#     school.dashboard                              *

# Structure
#     university.faculty                            *
#     university.department                         *
#     university.program                            *
#     university.subject                            *
#     university.classroom                          *

# Academic calendar
#     university.academic.year                      *
#     university.semester                           *
#     university.semester.subject                   *

# People
#     university.teacher                            *
#     university.student                            *
#     res.users                                     ext -> adds teacher_id

# Delivery and registration
#     university.class.section                      *
#     university.enrollment                         *
#     university.academic.assignment                *
#     university.enrollment.wizard                  wiz
#     university.student.enrollment.wizard          wiz

# Finance
#     university.fee                                *
#     university.fee.line                           *
#     university.payment                            *

# Planned models
#     university.schedule                           +
#     university.attendance                         +
#     university.exam                               +
#     university.assessment                         +
#     university.result                             +
#     university.grade                              +
#     university.scholarship                        +
#     university.graduation                         +
#     university.certificate                        +

# Security flow reference
#     res.users.teacher_id -> university.teacher
#     university.teacher -> department
#     department -> faculty
#     record rules scope data through that chain