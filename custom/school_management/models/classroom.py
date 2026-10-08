from odoo import api, fields, models
from odoo.exceptions import ValidationError


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
    status = fields.Selection(
        [
            ("available", "Available"),
            ("maintenance", "Maintenance"),
            ("occupied", "Occupied"),
            ("inactive", "Inactive"),
        ],
        string="Status",
        default="available",
        required=True,
    )
    active = fields.Boolean(string="Active", default=True)

    @api.constrains("capacity")
    def _check_capacity(self):
        for room in self:
            if room.capacity < 0:
                raise ValidationError("Classroom capacity cannot be negative.")
