from odoo import api, fields, models
from odoo.exceptions import ValidationError


class UniversityEnrollment(models.Model):
    _name = "university.enrollment"
    _description = "University Course Enrollment"
    _sql_constraints = [
        (
            "student_section_unique",
            "unique(student_id, section_id)",
            "This student is already enrolled in this class section.",
        ),
    ]

    student_id = fields.Many2one(
        "university.student",
        string="Student",
        required=True,
    )
    section_id = fields.Many2one(
        "university.class.section",
        string="Class Section",
        required=True,
    )
    subject_id = fields.Many2one(
        related="section_id.subject_id",
        string="Subject",
        store=True,
        readonly=True,
    )
    teacher_id = fields.Many2one(
        related="section_id.teacher_id",
        string="Instructor",
        store=True,
        readonly=True,
    )
    academic_year_id = fields.Many2one(
        related="section_id.semester_id.academic_year_id",
        string="Academic Year",
        store=True,
        readonly=True,
    )
    semester_id = fields.Many2one(
        related="section_id.semester_id",
        string="Semester",
        store=True,
        readonly=True,
    )
    faculty_id = fields.Many2one(
        related="student_id.faculty_id",
        string="Faculty",
        store=True,
        readonly=True,
    )
    enrollment_date = fields.Date(
        string="Enrollment Date",
        default=fields.Date.context_today,
    )
    status = fields.Selection(
        [
            ("enrolled", "Enrolled"),
            ("completed", "Completed"),
            ("dropped", "Dropped"),
        ],
        string="Status",
        default="enrolled",
    )