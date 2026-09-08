from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestStudentAcademicPlacement(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Faculty = self.env["university.faculty"]
        self.Department = self.env["university.department"]
        self.Program = self.env["university.program"]
        self.Student = self.env["university.student"]

        self.faculty = self.Faculty.create({"name": "F", "code": "F1"})
        self.department = self.Department.create(
            {"name": "D", "code": "D1", "faculty_id": self.faculty.id}
        )
        self.program = self.Program.create(
            {"name": "P", "code": "P1", "department_id": self.department.id}
        )

    def test_department_faculty_derived_from_program(self):
        student = self.Student.create(
            {"name": "S", "program_id": self.program.id}
        )
        self.assertEqual(student.department_id, self.department)
        self.assertEqual(student.faculty_id, self.faculty)

    def test_changing_program_updates_department_and_faculty(self):
        other_faculty = self.Faculty.create({"name": "G", "code": "F2"})
        other_dept = self.Department.create(
            {"name": "E", "code": "D2", "faculty_id": other_faculty.id}
        )
        other_program = self.Program.create(
            {"name": "Q", "code": "P2", "department_id": other_dept.id}
        )
        student = self.Student.create(
            {"name": "S", "program_id": self.program.id}
        )
        student.program_id = other_program
        self.assertEqual(student.department_id, other_dept)
        self.assertEqual(student.faculty_id, other_faculty)

    def test_student_id_unique(self):
        self.Student.create({"name": "A", "student_id": "STU-X"})
        with self.assertRaises(IntegrityError):
            self.Student.create({"name": "B", "student_id": "STU-X"})


class TestEnrollmentSectionPeriod(TransactionCase):
    def setUp(self):
        super().setUp()
        Year = self.env["university.academic.year"]
        Semester = self.env["university.semester"]
        self.Faculty = self.env["university.faculty"]
        self.Department = self.env["university.department"]
        self.Program = self.env["university.program"]
        self.Student = self.env["university.student"]
        self.Enrollment = self.env["university.enrollment"]
        self.Section = self.env["university.class.section"]

        self.year1 = Year.create(
            {"name": "2025-2026", "date_start": "2025-09-01", "date_end": "2026-06-30"}
        )
        self.year2 = Year.create(
            {"name": "2026-2027", "date_start": "2026-09-01", "date_end": "2027-06-30"}
        )
        self.sem1 = Semester.create(
            {"name": "S1", "academic_year_id": self.year1.id, "semester_type": "semester_1"}
        )
        self.sem_other = Semester.create(
            {"name": "S1-Other", "academic_year_id": self.year2.id, "semester_type": "semester_1"}
        )
        self.faculty = self.Faculty.create({"name": "F", "code": "F1"})
        self.department = self.Department.create(
            {"name": "D", "code": "D1", "faculty_id": self.faculty.id}
        )
        self.program = self.Program.create(
            {"name": "P", "code": "P1", "department_id": self.department.id}
        )
        self.section = self.Section.create(
            {"name": "SEC-A", "program_id": self.program.id, "semester_id": self.sem1.id}
        )
        self.student = self.Student.create({"name": "S", "program_id": self.program.id})

    def test_section_period_mismatch_rejected(self):
        with self.assertRaises(ValidationError):
            self.Enrollment.create(
                {
                    "student_id": self.student.id,
                    "program_id": self.program.id,
                    "section_id": self.section.id,
                    "academic_year_id": self.year1.id,
                    "semester_id": self.sem_other.id,
                }
            )

    def test_section_onchange_autofills_period(self):
        enrollment = self.Enrollment.new(
            {
                "student_id": self.student.id,
                "program_id": self.program.id,
                "section_id": self.section.id,
            }
        )
        enrollment._onchange_section_id()
        self.assertEqual(enrollment.semester_id, self.sem1)
        self.assertEqual(enrollment.academic_year_id, self.year1)


class TestLeadershipSourceOfTruth(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Faculty = self.env["university.faculty"]
        self.Department = self.env["university.department"]
        self.Teacher = self.env["university.teacher"]
        self.Assignment = self.env["university.academic.assignment"]

        self.faculty = self.Faculty.create({"name": "F", "code": "F1"})
        self.department = self.Department.create(
            {"name": "D", "code": "D1", "faculty_id": self.faculty.id}
        )
        self.dean = self.Teacher.create(
            {"name": "Dean", "faculty_id": self.faculty.id, "department_id": self.department.id}
        )
        self.hod = self.Teacher.create(
            {"name": "HOD", "department_id": self.department.id}
        )

    def test_dean_derived_from_active_assignment(self):
        self.assertFalse(self.faculty.dean_id)
        assignment = self.Assignment.create(
            {
                "name": "Dean Appointment",
                "staff_id": self.dean.id,
                "role": "dean",
                "faculty_id": self.faculty.id,
                "start_date": "2025-01-01",
            }
        )
        self.assertEqual(self.faculty.dean_id, self.dean)
        self.assertTrue(self.dean.is_dean)

        assignment.active = False
        self.assertFalse(self.faculty.dean_id)
        self.assertFalse(self.dean.is_dean)

    def test_hod_derived_from_active_assignment(self):
        self.assertFalse(self.department.head_id)
        assignment = self.Assignment.create(
            {
                "name": "HOD Appointment",
                "staff_id": self.hod.id,
                "role": "department_head",
                "department_id": self.department.id,
                "start_date": "2025-01-01",
            }
        )
        self.assertEqual(self.department.head_id, self.hod)
        self.assertTrue(self.hod.is_hod)

        assignment.active = False
        self.assertFalse(self.department.head_id)
        self.assertFalse(self.hod.is_hod)

    def test_dean_field_is_not_directly_editable(self):
        self.assertTrue(self.faculty._fields["dean_id"].readonly)
        self.assertTrue(self.department._fields["head_id"].readonly)


class TestClassSectionDataRules(TransactionCase):
    def setUp(self):
        super().setUp()
        Year = self.env["university.academic.year"]
        Semester = self.env["university.semester"]
        self.Faculty = self.env["university.faculty"]
        self.Department = self.env["university.department"]
        self.Program = self.env["university.program"]
        self.Section = self.env["university.class.section"]

        self.year = Year.create(
            {"name": "2025-2026", "date_start": "2025-09-01", "date_end": "2026-06-30"}
        )
        self.semester = Semester.create(
            {"name": "S1", "academic_year_id": self.year.id, "semester_type": "semester_1"}
        )
        self.faculty = self.Faculty.create({"name": "F", "code": "F1"})
        self.department = self.Department.create(
            {"name": "D", "code": "D1", "faculty_id": self.faculty.id}
        )
        self.program = self.Program.create(
            {"name": "P", "code": "P1", "department_id": self.department.id}
        )

    def test_capacity_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self.Section.create(
                {
                    "name": "SEC-A",
                    "program_id": self.program.id,
                    "semester_id": self.semester.id,
                    "capacity": 0,
                }
            )

    def test_section_requires_program_or_subject(self):
        with self.assertRaises(ValidationError):
            self.Section.create(
                {"name": "SEC-X", "semester_id": self.semester.id}
            )


class TestHodRecordRules(TransactionCase):
    def setUp(self):
        super().setUp()
        Year = self.env["university.academic.year"]
        Semester = self.env["university.semester"]
        self.Faculty = self.env["university.faculty"]
        self.Department = self.env["university.department"]
        self.Program = self.env["university.program"]
        self.Teacher = self.env["university.teacher"]
        self.Assignment = self.env["university.academic.assignment"]
        self.Section = self.env["university.class.section"]
        self.Users = self.env["res.users"].sudo()

        self.faculty = self.Faculty.create({"name": "F", "code": "F1"})
        self.department = self.Department.create(
            {"name": "D", "code": "D1", "faculty_id": self.faculty.id}
        )
        self.program = self.Program.create(
            {"name": "P", "code": "P1", "department_id": self.department.id}
        )
        self.year = Year.create(
            {"name": "2025-2026", "date_start": "2025-09-01", "date_end": "2026-06-30"}
        )
        self.semester = Semester.create(
            {"name": "S1", "academic_year_id": self.year.id, "semester_type": "semester_1"}
        )
        self.hod = self.Teacher.create({"name": "HOD", "department_id": self.department.id})
        self.hod_group = self.env.ref("school_management.group_school_hod")
        self.hod_user = self.Users.create(
            {
                "name": "HOD User",
                "login": "hod@example.com",
                "email": "hod@example.com",
                "group_ids": [(6, 0, [self.hod_group.id])],
            }
        )
        self.hod.user_id = self.hod_user
        self.Assignment.create(
            {
                "name": "HOD Appointment",
                "staff_id": self.hod.id,
                "role": "department_head",
                "department_id": self.department.id,
                "start_date": "2025-01-01",
            }
        )

    def test_hod_sees_program_level_sections_of_own_department(self):
        section = self.Section.create(
            {"name": "COHORT-A", "program_id": self.program.id, "semester_id": self.semester.id}
        )
        visible = self.Section.with_user(self.hod_user).search(
            [("id", "=", section.id)], limit=1
        )
        self.assertEqual(visible.id, section.id)

    def test_hod_does_not_see_other_department_program_sections(self):
        other_faculty = self.Faculty.create({"name": "G", "code": "F2"})
        other_dept = self.Department.create(
            {"name": "E", "code": "D2", "faculty_id": other_faculty.id}
        )
        other_program = self.Program.create(
            {"name": "Q", "code": "P2", "department_id": other_dept.id}
        )
        section = self.Section.create(
            {"name": "COHORT-B", "program_id": other_program.id, "semester_id": self.semester.id}
        )
        visible = self.Section.with_user(self.hod_user).search(
            [("id", "=", section.id)], limit=1
        )
        self.assertFalse(visible)
