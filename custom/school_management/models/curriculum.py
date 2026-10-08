from odoo import api, fields, models


class UniversityCurriculum(models.Model):
    _name = "university.curriculum"
    _description = "University Curriculum"
    _order = "name"

    name = fields.Char(string="Curriculum Name", compute="_compute_name", store=True, readonly=False, required=True)
    program_id = fields.Many2one("university.program", string="Program", required=True)
    session_id = fields.Many2one("university.academic.year", string="Session", required=True)
    active = fields.Boolean(string="Active", default=True)
    line_ids = fields.One2many("university.curriculum.line", "curriculum_id", string="Curriculum Lines")

    @api.depends("program_id", "session_id")
    def _compute_name(self):
        for rec in self:
            if rec.program_id and rec.session_id and not rec.name:
                rec.name = f"{rec.program_id.name} - {rec.session_id.name}"


class UniversityCurriculumLine(models.Model):
    _name = "university.curriculum.line"
    _description = "Curriculum Line"
    _order = "program_id, year_level, semester_number, sequence, id"

    program_id = fields.Many2one(
        "university.program",
        string="Program",
        required=True,
        ondelete="cascade",
        index=True,
    )
    subject_id = fields.Many2one(
        "university.subject",
        string="Subject",
        required=True,
        index=True,
    )
    year_level = fields.Selection([
        ("1", "Year 1"),
        ("2", "Year 2"),
        ("3", "Year 3"),
        ("4", "Year 4"),
    ], string="Year Level", required=True, default="1")

    semester_number = fields.Selection([
        ("1", "Semester 1"),
        ("2", "Semester 2"),
    ], string="Semester", required=True, default="1")

    sequence = fields.Integer(string="Sequence", default=10)
    credits = fields.Integer(string="Credits", related="subject_id.credits", store=True, readonly=False)

    # Legacy compatibility fields
    curriculum_id = fields.Many2one(
        "university.curriculum",
        string="Curriculum",
        ondelete="cascade",
    )
    semester = fields.Selection([
        ("1", "Semester 1"),
        ("2", "Semester 2"),
    ], string="Semester (Legacy)", compute="_compute_legacy_semester", inverse="_inverse_legacy_semester", store=True)
    required = fields.Boolean(string="Required", default=True)

    # Student-facing view helpers
    is_current_student_year = fields.Boolean(
        string="Current Student Year",
        compute="_compute_student_view_flags",
    )
    is_student_enrolled = fields.Boolean(
        string="Enrolled",
        compute="_compute_student_view_flags",
    )
    enrollment_status = fields.Char(
        string="Enrollment Status",
        compute="_compute_student_view_flags",
    )

    _unique_program_subject = models.Constraint(
        "UNIQUE(program_id, subject_id)",
        "This subject already exists in the curriculum for this program.",
    )

    @api.depends("semester_number")
    def _compute_legacy_semester(self):
        for rec in self:
            rec.semester = rec.semester_number

    def _inverse_legacy_semester(self):
        for rec in self:
            if rec.semester:
                rec.semester_number = rec.semester

    def _compute_student_view_flags(self):
        user = self.env.user
        student = self.env["university.student"].search([("user_id", "=", user.id)], limit=1)
        active_student_id = self.env.context.get("active_student_id")
        if not student and active_student_id:
            student = self.env["university.student"].browse(active_student_id).exists()

        for line in self:
            if not student:
                line.is_current_student_year = False
                line.is_student_enrolled = False
                line.enrollment_status = "Planned"
                continue

            line.is_current_student_year = (line.year_level == student.year_level)
            enrollment = self.env["university.enrollment"].search([
                ("student_id", "=", student.id),
                ("subject_id", "=", line.subject_id.id),
                ("status", "in", ["enrolled", "completed"]),
            ], limit=1)
            if enrollment:
                line.is_student_enrolled = True
                line.enrollment_status = "Enrolled" if enrollment.status == "enrolled" else "Completed"
            else:
                line.is_student_enrolled = False
                line.enrollment_status = "Planned"
