from odoo import api, fields, models
from odoo.exceptions import ValidationError


class UniversityEnrollmentWizard(models.TransientModel):
    _name = "university.enrollment.wizard"
    _description = "Bulk Student Enrollment Wizard"

    # ── Cascading location fields ─────────────────────────────────────────────
    faculty_id = fields.Many2one(
        "university.faculty",
        string="Faculty",
    )
    department_id = fields.Many2one(
        "university.department",
        string="Department",
    )
    program_id = fields.Many2one(
        "university.program",
        string="Major",
        required=True,
    )
    subject_ids = fields.Many2many(
        "university.subject",
        string="Loaded Subjects",
        readonly=True,
    )

    # ── Subject / Section ─────────────────────────────────────────────────────
    subject_id = fields.Many2one(
        "university.subject",
        string="Subject",
        required=True,
    )
    section_id = fields.Many2one(
        "university.class.section",
        string="Class Section",
        required=True,
    )

    # ── Auto-filled from Section ──────────────────────────────────────────────
    teacher_id = fields.Many2one(
        related="section_id.teacher_id",
        string="Instructor",
        readonly=True,
    )
    semester_id = fields.Many2one(
        related="section_id.semester_id",
        string="Semester",
        readonly=True,
    )
    academic_year_id = fields.Many2one(
        related="section_id.semester_id.academic_year_id",
        string="Academic Year",
        readonly=True,
    )

    # ── Students ──────────────────────────────────────────────────────────────
    student_ids = fields.Many2many(
        "university.student",
        string="Students",
        required=True,
    )

    # ── Enrollment Details ────────────────────────────────────────────────────
    enrollment_date = fields.Date(
        string="Enrollment Date",
        default=fields.Date.context_today,
        required=True,
    )
    status = fields.Selection(
        [
            ("enrolled", "Enrolled"),
            ("completed", "Completed"),
            ("dropped", "Dropped"),
        ],
        string="Status",
        default="enrolled",
        required=True,
    )
    enrolled_count = fields.Integer(
        string="Current Enrolled",
        compute="_compute_enrollment_stats",
    )
    available_seats = fields.Integer(
        string="Available Seats",
        compute="_compute_enrollment_stats",
    )
    selected_student_count = fields.Integer(
        string="Selected Students",
        compute="_compute_selected_students",
    )
    capacity_warning = fields.Boolean(
        string="Capacity Warning",
        compute="_compute_capacity_warning",
    )

    # ── Onchange cascade ──────────────────────────────────────────────────────

    @api.onchange("faculty_id")
    def _onchange_faculty_id(self):
        self.department_id = False
        self.program_id = False
        self.subject_id = False
        self.section_id = False
        self.subject_ids = False
        self.student_ids = False
        if self.faculty_id:
            return {"domain": {"department_id": [("faculty_id", "=", self.faculty_id.id)]}}
        return {"domain": {"department_id": []}}

    @api.onchange("department_id")
    def _onchange_department_id(self):
        self.program_id = False
        self.subject_id = False
        self.section_id = False
        self.subject_ids = False
        self.student_ids = False
        if self.department_id:
            if not self.faculty_id and self.department_id.faculty_id:
                self.faculty_id = self.department_id.faculty_id
            return {"domain": {"program_id": [("department_id", "=", self.department_id.id)]}}
        return {"domain": {"program_id": []}}

    @api.onchange("program_id")
    def _onchange_program_id(self):
        self.subject_id = False
        self.section_id = False
        self.student_ids = False
        self.subject_ids = False
        if self.program_id:
            if not self.department_id and self.program_id.department_id:
                self.department_id = self.program_id.department_id
                if self.department_id.faculty_id:
                    self.faculty_id = self.department_id.faculty_id
            
            subjects = self.env["university.subject"].search(self._get_subject_domain())
            self.subject_ids = subjects

            students = self.env["university.student"].search([
                ("program_id", "=", self.program_id.id),
                ("status", "=", "active")
            ])
            self.student_ids = students
            return {"domain": {"subject_id": [("id", "in", subjects.ids)]}}

    def _get_subject_domain(self):
        self.ensure_one()
        if not self.program_id:
            return [("id", "=", 0)]
        return [
            ("active", "=", True),
            "|",
            ("program_ids", "in", [self.program_id.id]),
            "&",
            ("department_id", "=", self.program_id.department_id.id),
            ("program_ids", "=", False),
        ]

    @api.onchange("subject_id")
    def _onchange_subject_id(self):
        self.section_id = False

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends("section_id", "section_id.enrollment_ids", "section_id.capacity")
    def _compute_enrollment_stats(self):
        for wizard in self:
            if not wizard.section_id:
                wizard.enrolled_count = 0
                wizard.available_seats = 0
                continue
            active = wizard.section_id.enrollment_ids.filtered(
                lambda e: e.status == "enrolled"
            )
            wizard.enrolled_count = len(active)
            capacity = wizard.section_id.capacity or 0
            wizard.available_seats = max(capacity - wizard.enrolled_count, 0)

    @api.depends("student_ids")
    def _compute_selected_students(self):
        for wizard in self:
            wizard.selected_student_count = len(wizard.student_ids)

    @api.depends("selected_student_count", "available_seats", "section_id", "section_id.capacity")
    def _compute_capacity_warning(self):
        for wizard in self:
            if wizard.section_id and wizard.section_id.capacity and wizard.selected_student_count > wizard.available_seats:
                wizard.capacity_warning = True
            else:
                wizard.capacity_warning = False

    # ── Validation ────────────────────────────────────────────────────────────

    def _check_subject_program(self):
        self.ensure_one()
        if not self.subject_id or not self.program_id:
            return
        if self.subject_id.program_ids and self.program_id not in self.subject_id.program_ids:
            raise ValidationError(
                "The selected subject does not belong to the chosen major."
            )
        if (
            not self.subject_id.program_ids
            and self.subject_id.department_id != self.program_id.department_id
        ):
            raise ValidationError(
                "The selected subject does not belong to the chosen major."
            )

    # ── Main action ───────────────────────────────────────────────────────────

    def action_enroll_students(self):
        self.ensure_one()
        if not self.student_ids:
            raise ValidationError("Please select at least one student.")

        self._check_subject_program()

        # Find students already enrolled in this section
        existing_enrollments = self.env["university.enrollment"].search([
            ("section_id", "=", self.section_id.id),
            ("student_id", "in", self.student_ids.ids),
            ("status", "=", "enrolled"),
        ])
        existing_students = existing_enrollments.mapped("student_id")
        students_to_enroll = self.student_ids - existing_students

        if not students_to_enroll:
            raise ValidationError(
                "All selected students are already enrolled in this class section."
            )

        if self.section_id.capacity:
            seats_needed = len(students_to_enroll)
            if self.enrolled_count + seats_needed > self.section_id.capacity:
                raise ValidationError(
                    "Not enough seats in this class section. "
                    f"Available: {self.available_seats}, requested: {seats_needed}."
                )

        enrollments = self.env["university.enrollment"].create([
            {
                "student_id": student.id,
                "section_id": self.section_id.id,
                "enrollment_date": self.enrollment_date,
                "status": self.status,
            }
            for student in students_to_enroll
        ])

        message = f"{len(enrollments)} student(s) enrolled successfully."
        if existing_students:
            message += (
                f" {len(existing_students)} student(s) were already enrolled and skipped."
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Enrollment Complete",
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
