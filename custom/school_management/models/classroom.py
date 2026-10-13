from odoo import _, api, fields, models
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

    slot_ids = fields.One2many(
        "university.timetable.slot",
        "classroom_id",
        string="Scheduled Sessions",
    )
    slot_count = fields.Integer(
        string="Session Count",
        compute="_compute_slot_count",
    )

    def _compute_slot_count(self):
        slot_data = dict(
            self.env["university.timetable.slot"]._read_group(
                [("classroom_id", "in", self.ids), ("state", "!=", "cancelled")],
                groupby=["classroom_id"],
                aggregates=["__count"],
            )
        )
        for room in self:
            room.slot_count = slot_data.get(room, 0)

    def action_view_sessions(self):
        self.ensure_one()
        return {
            "name": _("Room Sessions: %s") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "university.timetable.slot",
            "view_mode": "kanban,calendar,list,form",
            "domain": [("classroom_id", "=", self.id)],
            "context": {
                "default_classroom_id": self.id,
                "search_default_group_by_status": 1,
            },
        }

    @api.constrains("capacity")
    def _check_capacity(self):
        for room in self:
            if room.capacity < 0:
                raise ValidationError("Classroom capacity cannot be negative.")
