from odoo import api, fields, models


class UniversitySubject(models.Model):
    _name = "university.subject"
    _description = "University Subject"

    name = fields.Char(string="Subject Name", required=True)
    code = fields.Char(string="Subject Code", copy=False, index=True)
    department_id = fields.Many2one(
        "university.department",
        string="Department",
    )
    program_ids = fields.Many2many(
        "university.program",
        "university_program_subject_rel",
        "subject_id",
        "program_id",
        string="Majors / Programs",
    )
    credits = fields.Integer(string="Credits", default=3)
    semester_number = fields.Integer(
        string="Semester",
        default=1,
        help="Which semester this subject is taught (e.g. 1, 2, 3 …). "
             "Used to order subjects in the curriculum report.",
    )
    description = fields.Text(string="Description")
    teacher_ids = fields.Many2many(
        "university.teacher",
        "university_teacher_subject_rel",
        "subject_id",
        "teacher_id",
        string="Teachers",
    )
    section_ids = fields.One2many(
        "university.class.section",
        "subject_id",
        string="Class Sections",
    )
    semester_subject_ids = fields.One2many(
        "university.semester.subject",
        "subject_id",
        string="Semester Offerings",
    )
    active = fields.Boolean(string="Active", default=True)

    @api.onchange("program_ids")
    def _onchange_program_ids(self):
        if self.program_ids and not self.department_id:
            self.department_id = self.program_ids[0].department_id