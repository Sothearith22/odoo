from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class UniversitySemesterSubject(models.Model):
    _name = "university.semester.subject"
    _description = "Semester Subject Offering"
    _rec_name = "display_name"

    semester_id = fields.Many2one(
        "university.semester",
        string="Semester",
        required=True,
        ondelete="cascade",
    )
    subject_id = fields.Many2one(
        "university.subject",
        string="Subject",
        required=True,
        ondelete="cascade",
    )
    academic_year_id = fields.Many2one(
        "university.academic.year",
        related="semester_id.academic_year_id",
        string="Academic Year",
        store=True,
        readonly=True,
    )
    department_id = fields.Many2one(
        "university.department",
        related="subject_id.department_id",
        string="Department",
        store=True,
        readonly=True,
    )
    credits = fields.Integer(
        related="subject_id.credits",
        string="Credits",
        readonly=True,
    )
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
    )
    active = fields.Boolean(string="Active", default=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("allow_closed_year_write"):
            semester_ids = [vals.get("semester_id") for vals in vals_list if vals.get("semester_id")]
            if semester_ids:
                semesters = self.env["university.semester"].browse(semester_ids).exists()
                if any(s.academic_year_id.state in ("closed", "archived") for s in semesters):
                    raise UserError("Cannot create semester subjects in a closed or archived academic year.")
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("allow_closed_year_write"):
            if any(subj.academic_year_id.state in ("closed", "archived") for subj in self):
                raise UserError("Semester subjects of a closed or archived academic year are read-only and cannot be modified.")
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("allow_closed_year_write"):
            if any(subj.academic_year_id.state in ("closed", "archived") for subj in self):
                raise UserError("Cannot delete semester subjects of a closed or archived academic year.")
        return super().unlink()

    @api.constrains("semester_id", "subject_id")
    def _check_unique_semester_subject(self):
        for rec in self:
            if rec.semester_id and rec.subject_id:
                domain = [
                    ("id", "!=", rec.id),
                    ("semester_id", "=", rec.semester_id.id),
                    ("subject_id", "=", rec.subject_id.id),
                ]
                if self.search_count(domain):
                    raise ValidationError(
                        "This subject is already offered in the selected semester."
                    )

    @api.depends("semester_id.name", "subject_id.name")
    def _compute_display_name(self):
        for rec in self:
            if rec.semester_id and rec.subject_id:
                rec.display_name = f"{rec.semester_id.name} - {rec.subject_id.name}"
            elif rec.subject_id:
                rec.display_name = rec.subject_id.name
            else:
                rec.display_name = "Semester Subject"
