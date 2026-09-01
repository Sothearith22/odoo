from odoo import fields, models


class Teacher(models.Model):
    _name = "university.teacher"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "University Teacher"

    # Personal Information
    name = fields.Char(string="Teacher Name", required=True)
    teacher_id = fields.Char(string="Teacher ID", copy=False, index=True)
    image_1920 = fields.Image(string="Photo")
    gender = fields.Selection(
        [
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ],
        string="Gender",
    )
    date_of_birth = fields.Date(string="Date of Birth")

    # Contact Information
    phone = fields.Char(string="Phone")
    email = fields.Char(string="Email")
    address = fields.Text(string="Address")

    # Academic Information
    department_id = fields.Many2one(
        "university.department",
        string="Department",
    )
    specialization = fields.Char(string="Specialization")
    qualification = fields.Char(string="Qualification")

    # Status
    active = fields.Boolean(string="Active", default=True)

    # Teaching
    subject_ids = fields.Many2many(
        "university.subject",
        "university_teacher_subject_rel",
        "teacher_id",
        "subject_id",
        string="Subjects",
    )
    section_ids = fields.One2many(
        "university.class.section",
        "teacher_id",
        string="Class Sections",
    )

