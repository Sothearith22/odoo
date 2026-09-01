from odoo import fields, models


class UniversityClassroom(models.Model):
    _name = "university.classroom"
    _description = "University Classroom"

    name = fields.Char(string="Room Name / Number", required=True)
    building = fields.Char(string="Building", default="A")
    capacity = fields.Integer(string="Capacity", default=40)
    room_type = fields.Selection(
        [
            ("lecture_hall", "Lecture Hall"),
            ("classroom", "Standard Classroom"),
            ("lab", "Laboratory"),
            ("auditorium", "Auditorium"),
        ],
        string="Room Type",
        default="classroom",
    )
    active = fields.Boolean(string="Active", default=True)