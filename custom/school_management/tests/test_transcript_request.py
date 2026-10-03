from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestTranscriptRequest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Security groups
        cls.group_student = cls.env.ref("school_management.group_school_student")
        cls.group_registrar = cls.env.ref("school_management.group_school_registrar")

        # Create users
        cls.student_user = cls.env["res.users"].create({
            "name": "Test Student User",
            "login": "test_student_req@example.com",
            "email": "test_student_req@example.com",
            "group_ids": [Command.set([cls.group_student.id])],
        })
        cls.registrar_user = cls.env["res.users"].create({
            "name": "Test Registrar User",
            "login": "test_registrar_req@example.com",
            "email": "test_registrar_req@example.com",
            "group_ids": [Command.set([cls.group_registrar.id])],
        })

        # Academic infrastructure
        cls.faculty = cls.env["university.faculty"].create({
            "name": "Faculty of Testing",
            "code": "FTEST-TR",
        })
        cls.department = cls.env["university.department"].create({
            "name": "Testing Dept",
            "code": "DTEST-TR",
            "faculty_id": cls.faculty.id,
        })
        cls.program = cls.env["university.program"].create({
            "name": "BS Testing Science",
            "code": "PTEST-TR",
            "faculty_id": cls.faculty.id,
            "department_id": cls.department.id,
            "degree_type": "bachelor",
        })
        cls.academic_year = cls.env["university.academic.year"].create({
            "name": "2026-2027 Test",
            "date_start": "2026-09-01",
            "date_end": "2027-06-30",
        })
        cls.semester = cls.env["university.semester"].create({
            "name": "Fall 2026 Test",
            "academic_year_id": cls.academic_year.id,
            "date_start": "2026-09-01",
            "date_end": "2026-12-31",
        })

        # Student record
        cls.student = cls.env["university.student"].create({
            "name": "Alice Requestor",
            "student_id": "STD-REQ-999",
            "email": "test_student_req@example.com",
            "user_id": cls.student_user.id,
            "faculty_id": cls.faculty.id,
            "department_id": cls.department.id,
            "program_id": cls.program.id,
            "academic_year_id": cls.academic_year.id,
            "current_semester_id": cls.semester.id,
            "status": "active",
        })

        # Create an approved transcript so holds pass
        cls.transcript = cls.env["university.transcript"].create({
            "student_id": cls.student.id,
            "state": "approved",
            "cumulative_gpa": 3.75,
            "total_credits": 15,
        })

    def test_01_full_workflow(self):
        """Test happy path from draft to delivered."""
        # 1. Student creates request
        req = self.env["university.transcript.request"].with_user(self.student_user).create({
            "student_id": self.student.id,
            "request_type": "official",
            "copies": 2,
            "purpose": "employment",
            "delivery_method": "download",
            "recipient": "Tech Corp HR",
        })
        self.assertEqual(req.state, "draft")
        self.assertTrue(req.name.startswith("TR-"))
        self.assertEqual(req.program_id, self.program)

        # 2. Student submits
        req.with_user(self.student_user).action_submit()
        self.assertEqual(req.state, "submitted")

        # 3. Registrar approves
        req.with_user(self.registrar_user).action_approve()
        self.assertEqual(req.state, "approved")
        self.assertEqual(req.approved_by, self.registrar_user)
        self.assertTrue(req.approved_date)

        # 4. Registrar issues
        req.with_user(self.registrar_user).action_issue()
        self.assertEqual(req.state, "issued")
        self.assertTrue(req.transcript_id)
        self.assertTrue(req.verification_code)

        # 5. Registrar delivers
        req.with_user(self.registrar_user).action_deliver()
        self.assertEqual(req.state, "delivered")

    def test_02_student_cannot_approve_or_issue(self):
        """A student must never be allowed to approve or issue a transcript."""
        req = self.env["university.transcript.request"].with_user(self.student_user).create({
            "student_id": self.student.id,
            "request_type": "unofficial",
            "copies": 1,
            "purpose": "scholarship",
            "delivery_method": "download",
        })
        req.with_user(self.student_user).action_submit()

        # Student attempting approve
        with self.assertRaises(UserError):
            req.with_user(self.student_user).action_approve()

        # Student attempting write to administrative fields
        with self.assertRaises(AccessError):
            req.with_user(self.student_user).write({"state": "approved"})

    def test_03_rejection_requires_reason(self):
        """Rejection must mandate an explanation."""
        req = self.env["university.transcript.request"].with_user(self.student_user).create({
            "student_id": self.student.id,
            "request_type": "official",
            "copies": 1,
            "purpose": "visa",
            "delivery_method": "download",
        })
        req.action_submit()

        # Rejecting without reason raises error
        with self.assertRaises(UserError):
            req.with_user(self.registrar_user).action_reject(reason="")

        # Rejecting with reason succeeds
        req.with_user(self.registrar_user).action_reject(reason="Missing identity verification")
        self.assertEqual(req.state, "rejected")
        self.assertEqual(req.reject_reason, "Missing identity verification")

    def test_04_holds_block_approval(self):
        """Active student holds must block approval."""
        # Make student suspended
        self.student.status = "suspended"

        req = self.env["university.transcript.request"].create({
            "student_id": self.student.id,
            "request_type": "official",
            "copies": 1,
            "purpose": "transfer",
            "delivery_method": "download",
        })
        req.action_submit()

        # Approval must fail due to student status hold
        holds = req._get_holds()
        self.assertTrue(len(holds) > 0)
        with self.assertRaises(UserError):
            req.with_user(self.registrar_user).action_approve()

        # Restore status
        self.student.status = "active"

    def test_05_cancellation_constraints(self):
        """Students can only cancel draft or submitted requests."""
        req = self.env["university.transcript.request"].with_user(self.student_user).create({
            "student_id": self.student.id,
            "request_type": "unofficial",
            "copies": 1,
            "purpose": "other",
            "purpose_other": "Personal records",
            "delivery_method": "download",
        })
        req.action_submit()
        req.action_cancel()
        self.assertEqual(req.state, "cancelled")

    def test_06_duplicate_open_request_blocked(self):
        """A student cannot have two open requests of the same request_type."""
        self.env["university.transcript.request"].create({
            "student_id": self.student.id,
            "request_type": "official",
            "copies": 1,
            "purpose": "employment",
            "delivery_method": "download",
            "state": "submitted",
        })

        with self.assertRaises(ValidationError):
            self.env["university.transcript.request"].create({
                "student_id": self.student.id,
                "request_type": "official",
                "copies": 1,
                "purpose": "visa",
                "delivery_method": "download",
                "state": "draft",
            })
