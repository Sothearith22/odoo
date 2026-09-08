from odoo import api, fields, models
from odoo.exceptions import ValidationError


class UniversityAcademicYear(models.Model):
    _name = "university.academic.year"
    _description = "Academic Year"

    name = fields.Char(string="Academic Year", required=True)
    date_start = fields.Date(string="Start Date", required=True)
    date_end = fields.Date(string="End Date", required=True)
    semester_ids = fields.One2many(
        "university.semester", "academic_year_id", string="Semesters"
    )
    current = fields.Boolean(string="Current Academic Year", default=False)
    active = fields.Boolean(string="Active", default=True)

    @api.constrains("date_start", "date_end")
    def _check_date_range(self):
        for year in self:
            if year.date_start and year.date_end and year.date_start > year.date_end:
                raise ValidationError("The academic year start date must be before the end date.")

    @api.constrains("current", "active")
    def _check_single_current_year(self):
        for year in self.filtered(lambda rec: rec.current and rec.active):
            duplicate = self.search([
                ("id", "!=", year.id),
                ("current", "=", True),
                ("active", "=", True),
            ], limit=1)
            if duplicate:
                raise ValidationError("Only one active academic year can be marked as current.")


class UniversitySemester(models.Model):
    _name = "university.semester"
    _description = "Semester"

    name = fields.Char(string="Semester Name", required=True)
    academic_year_id = fields.Many2one(
        "university.academic.year", string="Academic Year", required=True
    )
    semester_type = fields.Selection(
        [
            ("semester_1", "Semester 1"),
            ("semester_2", "Semester 2"),
            ("summer", "Summer Semester"),
        ],
        string="Semester Type",
        default="semester_1",
        required=True,
    )
    date_start = fields.Date(string="Start Date")
    date_end = fields.Date(string="End Date")
    semester_subject_ids = fields.One2many(
        "university.semester.subject", "semester_id", string="Offered Subjects"
    )
    active = fields.Boolean(string="Active", default=True)

    @api.constrains("date_start", "date_end", "academic_year_id")
    def _check_date_range(self):
        for semester in self:
            if semester.date_start and semester.date_end and semester.date_start > semester.date_end:
                raise ValidationError("The semester start date must be before the end date.")

            academic_year = semester.academic_year_id
            if not academic_year:
                continue
            if semester.date_start and semester.date_start < academic_year.date_start:
                raise ValidationError("The semester start date cannot be before its academic year.")
            if semester.date_end and semester.date_end > academic_year.date_end:
                raise ValidationError("The semester end date cannot be after its academic year.")
