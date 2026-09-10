from odoo import api, fields, models

class UniversityAttendance(models.Model):
    _name = "university.attendance"
    _description = "Student Attendance"
    _order = "date desc, id desc"

    student_id = fields.Many2one("university.student", string="Student", required=True)
    section_id = fields.Many2one("university.class.section", string="Grade/Section", required=True)
    teacher_id = fields.Many2one(
        "university.teacher", 
        string="Teacher",
        related="section_id.teacher_id",
        store=True,
    )
    date = fields.Date(string="Date", default=fields.Date.context_today, required=True)
    status = fields.Selection(
        [("present", "Present"), ("absent", "Absent")],
        string="Status",
        required=True,
        default="present"
    )
