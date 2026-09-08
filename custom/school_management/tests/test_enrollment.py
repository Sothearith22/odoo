from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestEnrollment(TransactionCase):
    def setUp(self):
        super().setUp()
        Faculty = self.env["university.faculty"]
        Department = self.env["university.department"]
        Program = self.env["university.program"]
        Year = self.env["university.academic.year"]
        Semester = self.env["university.semester"]
        self.Student = self.env["university.student"]
        self.Enrollment = self.env["university.enrollment"]
        self.StudentWizard = self.env["university.student.enrollment.wizard"]
        self.Wizard = self.env["university.bulk.enrollment.wizard"]
        Section = self.env["university.class.section"]

        self.faculty = Faculty.create({"name": "Test Science", "code": "TESTSCI"})
        self.department = Department.create(
            {
                "name": "Test Physics",
                "code": "TESTPHY",
                "faculty_id": self.faculty.id,
            }
        )
        self.program = Program.create(
            {
                "name": "Test BSc Physics",
                "code": "TEST-BSC-PHY",
                "department_id": self.department.id,
            }
        )
        self.year = Year.create(
            {
                "name": "2025-2026",
                "date_start": "2025-09-01",
                "date_end": "2026-06-30",
            }
        )
        self.semester = Semester.create(
            {
                "name": "Semester 1",
                "academic_year_id": self.year.id,
                "semester_type": "semester_1",
            }
        )
        self.section = Section.create(
            {
                "name": "GM-Y1-A",
                "program_id": self.program.id,
                "semester_id": self.semester.id,
                "capacity": 2,
            }
        )

    def _make_student(self, **kw):
        vals = {"name": "Student", "status": "active"}
        vals.update(kw)
        return self.Student.create(vals)

    def test_single_major_enrollment(self):
        student = self._make_student(program_id=self.program.id)
        enrollment = self.Enrollment.create(
            {
                "student_id": student.id,
                "program_id": self.program.id,
                "section_id": self.section.id,
                "academic_year_id": self.year.id,
                "semester_id": self.semester.id,
            }
        )
        self.assertEqual(enrollment.department_id, self.department)
        self.assertEqual(enrollment.faculty_id, self.faculty)
        self.assertEqual(enrollment.status, "enrolled")

    def test_student_wizard_enrolls_without_class_section(self):
        student = self._make_student(
            program_id=self.program.id,
            academic_year_id=self.year.id,
            current_semester_id=self.semester.id,
        )
        wizard = self.StudentWizard.create({
            "student_id": student.id,
            "program_id": self.program.id,
            "academic_year_id": self.year.id,
            "semester_id": self.semester.id,
        })

        wizard.action_register_enrollments()

        enrollment = self.Enrollment.search([
            ("student_id", "=", student.id),
            ("program_id", "=", self.program.id),
            ("academic_year_id", "=", self.year.id),
            ("semester_id", "=", self.semester.id),
            ("section_id", "=", False),
        ])
        self.assertEqual(len(enrollment), 1)
        self.assertEqual(enrollment.status, "enrolled")

    def test_student_wizard_defaults_academic_data_from_student(self):
        student = self._make_student(
            program_id=self.program.id,
            academic_year_id=self.year.id,
            current_semester_id=self.semester.id,
        )
        defaults = self.StudentWizard.with_context(
            default_student_id=student.id
        ).default_get([
            "student_id",
            "program_id",
            "academic_year_id",
            "semester_id",
        ])

        self.assertEqual(defaults["student_id"], student.id)
        self.assertEqual(defaults["program_id"], self.program.id)
        self.assertEqual(defaults["academic_year_id"], self.year.id)
        self.assertEqual(defaults["semester_id"], self.semester.id)

    def test_student_wizard_can_still_assign_selected_class(self):
        student = self._make_student(
            program_id=self.program.id,
            academic_year_id=self.year.id,
            current_semester_id=self.semester.id,
        )
        wizard = self.StudentWizard.create({
            "student_id": student.id,
            "program_id": self.program.id,
            "academic_year_id": self.year.id,
            "semester_id": self.semester.id,
            "section_ids": [(6, 0, [self.section.id])],
        })

        wizard.action_register_enrollments()

        enrollment = self.Enrollment.search([
            ("student_id", "=", student.id),
            ("section_id", "=", self.section.id),
        ])
        self.assertEqual(len(enrollment), 1)
        self.assertEqual(enrollment.program_id, self.program)

    def test_student_wizard_rejects_duplicate_sectionless_enrollment(self):
        student = self._make_student(
            program_id=self.program.id,
            academic_year_id=self.year.id,
            current_semester_id=self.semester.id,
        )
        values = {
            "student_id": student.id,
            "program_id": self.program.id,
            "academic_year_id": self.year.id,
            "semester_id": self.semester.id,
        }
        self.StudentWizard.create(values).action_register_enrollments()

        with self.assertRaises(ValidationError):
            self.StudentWizard.create(values).action_register_enrollments()

    def test_program_section_mismatch_rejected(self):
        other_dept = self.env["university.department"].create(
            {"name": "Test Chemistry", "code": "TESTCHM", "faculty_id": self.faculty.id}
        )
        other_program = self.env["university.program"].create(
            {
                "name": "Test BSc Chemistry",
                "code": "TEST-BSC-CHM",
                "department_id": other_dept.id,
            }
        )
        other_section = self.env["university.class.section"].create(
            {
                "name": "GM-C1-A",
                "program_id": other_program.id,
                "semester_id": self.semester.id,
            }
        )
        student = self._make_student(program_id=self.program.id)
        with self.assertRaises(ValidationError):
            self.Enrollment.create(
                {
                    "student_id": student.id,
                    "program_id": self.program.id,
                    "section_id": other_section.id,
                    "academic_year_id": self.year.id,
                    "semester_id": self.semester.id,
                }
            )

    def test_duplicate_active_major_prevented(self):
        student = self._make_student(program_id=self.program.id)
        self.Enrollment.create(
            {
                "student_id": student.id,
                "program_id": self.program.id,
                "academic_year_id": self.year.id,
                "semester_id": self.semester.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.Enrollment.create(
                {
                    "student_id": student.id,
                    "program_id": self.program.id,
                    "academic_year_id": self.year.id,
                    "semester_id": self.semester.id,
                }
            )

    def test_bulk_enroll_students(self):
        s1 = self._make_student(program_id=self.program.id)
        s2 = self._make_student(program_id=self.program.id)
        wizard = self.Wizard.create(
            {
                "faculty_id": self.faculty.id,
                "department_id": self.department.id,
                "program_id": self.program.id,
                "academic_year_id": self.year.id,
                "semester_id": self.semester.id,
                "section_id": self.section.id,
                "student_ids": [(6, 0, [s1.id, s2.id])],
            }
        )
        wizard.action_enroll_students()
        self.assertEqual(
            self.Enrollment.search_count(
                [
                    ("student_id", "in", [s1.id, s2.id]),
                    ("program_id", "=", self.program.id),
                ]
            ),
            2,
        )

    def test_bulk_enroll_skips_already_enrolled(self):
        s1 = self._make_student(program_id=self.program.id)
        s2 = self._make_student(program_id=self.program.id)
        self.Enrollment.create(
            {
                "student_id": s1.id,
                "program_id": self.program.id,
                "section_id": self.section.id,
                "academic_year_id": self.year.id,
                "semester_id": self.semester.id,
            }
        )
        no_section = self.env["university.class.section"].create(
            {
                "name": "GM-Y2-A",
                "program_id": self.program.id,
                "semester_id": self.semester.id,
                "capacity": 10,
            }
        )
        wizard = self.Wizard.create(
            {
                "program_id": self.program.id,
                "academic_year_id": self.year.id,
                "semester_id": self.semester.id,
                "section_id": no_section.id,
                "student_ids": [(6, 0, [s1.id, s2.id])],
            }
        )
        wizard.action_enroll_students()
        self.assertEqual(
            self.Enrollment.search_count(
                [
                    ("student_id", "=", s1.id),
                    ("program_id", "=", self.program.id),
                ]
            ),
            1,
        )
        self.assertEqual(
            self.Enrollment.search_count(
                [
                    ("student_id", "=", s2.id),
                    ("program_id", "=", self.program.id),
                ]
            ),
            1,
        )

    def test_bulk_enroll_all_already_enrolled_raises(self):
        s1 = self._make_student(program_id=self.program.id)
        self.Enrollment.create(
            {
                "student_id": s1.id,
                "program_id": self.program.id,
                "academic_year_id": self.year.id,
                "semester_id": self.semester.id,
            }
        )
        wizard = self.Wizard.create(
            {
                "program_id": self.program.id,
                "academic_year_id": self.year.id,
                "semester_id": self.semester.id,
                "student_ids": [(6, 0, [s1.id])],
            }
        )
        with self.assertRaises(UserError):
            wizard.action_enroll_students()

    def test_bulk_enroll_empty_selection(self):
        wizard = self.Wizard.create(
            {
                "program_id": self.program.id,
                "academic_year_id": self.year.id,
                "semester_id": self.semester.id,
            }
        )
        with self.assertRaises(UserError):
            wizard.action_enroll_students()

    def test_capacity_enforced(self):
        s1 = self._make_student(program_id=self.program.id)
        s2 = self._make_student(program_id=self.program.id)
        s3 = self._make_student(program_id=self.program.id)
        wizard = self.Wizard.create(
            {
                "program_id": self.program.id,
                "academic_year_id": self.year.id,
                "semester_id": self.semester.id,
                "section_id": self.section.id,
                "student_ids": [(6, 0, [s1.id, s2.id, s3.id])],
            }
        )
        with self.assertRaises(UserError):
            wizard.action_enroll_students()


class TestBulkWizardEligibility(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Faculty = self.env["university.faculty"]
        self.Department = self.env["university.department"]
        self.Program = self.env["university.program"]
        self.Wizard = self.env["university.bulk.enrollment.wizard"]

    def test_student_domain_program(self):
        faculty = self.Faculty.create({"name": "Test Eng", "code": "TESTENG"})
        department = self.Department.create(
            {"name": "Test CS", "code": "TESTCS", "faculty_id": faculty.id}
        )
        program = self.Program.create(
            {"name": "Test BSc CS", "code": "TEST-BSC-CS", "department_id": department.id}
        )
        wizard = self.Wizard.new(
            {
                "faculty_id": faculty.id,
                "department_id": department.id,
                "program_id": program.id,
            }
        )
        wizard._onchange_program_id()
        domain = wizard._student_domain()["domain"]["student_ids"]
        self.assertIn(("program_id", "=", program.id), domain)
