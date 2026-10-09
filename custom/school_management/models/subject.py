from odoo import api, fields, models
from odoo.exceptions import UserError
from .academic_lock import can_maintain_closed_year_records


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
    auto_quiz_per_session = fields.Boolean(
        string="Auto-Quiz per Session",
        default=False,
        help="If enabled, timetable sessions for this subject automatically generate a quiz when class begins.",
    )

    @api.onchange("program_ids")
    def _onchange_program_ids(self):
        if self.program_ids and not self.department_id:
            self.department_id = self.program_ids[0].department_id

    def unlink(self):
        if not can_maintain_closed_year_records(self.env):
            locked_offering = self.with_context(active_test=False).mapped(
                "semester_subject_ids"
            ).filtered(
                lambda offering: offering.academic_year_id.state in ("closed", "archived")
            )[:1]
            if locked_offering:
                raise UserError(
                    "Cannot delete a subject with semester offerings in a closed or archived academic year."
                )
        return super().unlink()
