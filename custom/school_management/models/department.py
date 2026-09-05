from odoo import api, fields, models


class UniversityDepartment(models.Model):
    _name = "university.department"
    _description = "University Department"

    name = fields.Char(string="Department Name", required=True)
    code = fields.Char(string="Department Code", required=True)
    faculty_id = fields.Many2one(
        "university.faculty", string="Faculty", required=True
    )
    head_id = fields.Many2one("university.teacher", string="Head of Department")
    program_ids = fields.One2many(
        "university.program", "department_id", string="Programs"
    )
    teacher_ids = fields.One2many(
        "university.teacher", "department_id", string="Teachers"
    )
    subject_ids = fields.One2many(
        "university.subject", "department_id", string="Subjects"
    )
    student_ids = fields.One2many(
        "university.student", "department_id", string="Students"
    )
    class_section_ids = fields.Many2many(
        "university.class.section",
        compute="_compute_class_sections",
        string="Class Sections",
    )
    active = fields.Boolean(string="Active", default=True)

    assignment_ids = fields.One2many(
        "university.academic.assignment",
        "department_id",
        string="Head Appointments",
    )

    program_count = fields.Integer(compute="_compute_counts", string="Program Count")
    teacher_count = fields.Integer(compute="_compute_counts", string="Teacher Count")
    subject_count = fields.Integer(compute="_compute_counts", string="Subject Count")
    student_count = fields.Integer(compute="_compute_counts", string="Student Count")
    class_section_count = fields.Integer(
        compute="_compute_counts", string="Class Section Count"
    )

    # sql constraints for unique head id and code of department
    _sql_constraints = [
        ("unique_head_id", "unique(head_id,active)", "A teacher can only be the head of one department!"),
        ("unique_code", "unique(code,active)", "The department code must be unique!"),
    ]

    @api.depends("subject_ids.section_ids")
    def _compute_class_sections(self):
        for rec in self:
            rec.class_section_ids = rec.subject_ids.mapped("section_ids")

    @api.depends(
        "program_ids",
        "teacher_ids",
        "subject_ids",
        "student_ids",
        "class_section_ids",
    )
    def _compute_counts(self):
        for rec in self:
            rec.program_count = len(rec.with_context(active_test=False).program_ids)
            rec.teacher_count = len(rec.with_context(active_test=False).teacher_ids)
            rec.subject_count = len(rec.with_context(active_test=False).subject_ids)
            rec.student_count = len(rec.with_context(active_test=False).student_ids)
            rec.class_section_count = len(
                rec.with_context(active_test=False).class_section_ids
            )
