from odoo import fields, models


class UniversityFaculty(models.Model):
    _name = "university.faculty"
    _description = "University Faculty"

    name = fields.Char(string="Faculty Name", required=True)
    code = fields.Char(string="Faculty Code", required=True)
    dean_id = fields.Many2one("university.teacher", string="Dean")
    department_ids = fields.One2many(
        "university.department", "faculty_id", string="Departments"
    )
    description = fields.Text(string="Description")
    active = fields.Boolean(string="Active", default=True)

    department_count = fields.Integer(compute="_compute_counts", string="Departments")

    def _compute_counts(self):
        for rec in self:
            rec.department_count = len(rec.department_ids)
