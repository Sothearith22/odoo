from odoo import fields, models


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
    active = fields.Boolean(string="Active", default=True)

    program_count = fields.Integer(compute="_compute_counts", string="Programs")
    teacher_count = fields.Integer(compute="_compute_counts", string="Teachers")
    subject_count = fields.Integer(compute="_compute_counts", string="Subjects")

    # sql constraints for unique head id and code of department 
    _sql_constraints = [
        ("unique_head_id", "unique(head_id,active)", "A teacher can only be the head of one department!"),
        ("unique_code", "unique(code,active)", "The department code must be unique!"),
    ]

    def _compute_counts(self):
        for rec in self:
            rec.program_count = len(rec.with_context(active_test=False).program_ids)
            rec.teacher_count = len(rec.with_context(active_test=False).teacher_ids)
            rec.subject_count = len(rec.with_context(active_test=False).subject_ids)
    