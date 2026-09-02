from odoo import fields, models


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
