from odoo import api, fields, models
from odoo.exceptions import ValidationError


class UniversityClassSection(models.Model):
    _name = "university.class.section"
    _description = "Class Section"

    name = fields.Char(string="Section Name", required=True)
    subject_id = fields.Many2one(
        "university.subject", string="Subject", required=True
    )
    teacher_id = fields.Many2one(
        "university.teacher", string="Instructor", required=True
    )
    semester_id = fields.Many2one(
        "university.semester", string="Semester", required=True
    )
    classroom_id = fields.Many2one(
        "university.classroom", string="Classroom"
    )
    capacity = fields.Integer(string="Max Capacity", default=30)
    enrollment_ids = fields.One2many(
        "university.enrollment", "section_id", string="Enrolled Students"
    )
    active = fields.Boolean(string="Active", default=True)
    enrolled_student_count = fields.Integer(
        string="Enrolled Count",
        compute="_compute_enrolled_student_count",
    )

    def _compute_enrolled_student_count(self):
        for section in self:
            section.enrolled_student_count = len(
                section.enrollment_ids.filtered(lambda e: e.status == "enrolled")
            )

    @api.constrains("teacher_id", "subject_id")
    def _check_teacher_subject(self):
        for section in self:
            if not section.subject_id or not section.teacher_id:
                continue
            if (
                section.subject_id.teacher_ids
                and section.teacher_id not in section.subject_id.teacher_ids
            ):
                raise ValidationError(
                    "The selected instructor is not assigned to teach this subject."
                )

    def action_open_bulk_enroll_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Bulk Enroll Students",
            "res_model": "university.enrollment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_section_id": self.id,
                "default_program_id": self.subject_id.program_ids[:1].id
                if
                    self.subject_id.program_ids
                else
                    False,
            },
        }
