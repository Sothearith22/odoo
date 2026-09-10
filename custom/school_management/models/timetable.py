from odoo import api, fields, models

class UniversityTimetableSlot(models.Model):
    _name = "university.timetable.slot"
    _description = "Timetable Slot"
    _order = "start_time asc"

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    teacher_id = fields.Many2one("university.teacher", string="Teacher", required=True)
    section_id = fields.Many2one("university.class.section", string="Grade/Section", required=True)
    subject_id = fields.Many2one("university.subject", string="Subject", required=True)
    location = fields.Char(string="Location")
    start_time = fields.Datetime(string="Start Time", required=True)
    end_time = fields.Datetime(string="End Time", required=True)
    state = fields.Selection(
        [("todo", "To Do"), ("running", "Running"), ("completed", "Completed")],
        string="Status",
        compute="_compute_state",
        store=True,
    )

    @api.depends("section_id", "subject_id", "start_time")
    def _compute_name(self):
        for slot in self:
            if slot.section_id and slot.subject_id and slot.start_time:
                date_str = slot.start_time.strftime("%Y-%m-%d")
                slot.name = f"{slot.section_id.name}-{slot.subject_id.name}({date_str})"
            else:
                slot.name = "New Slot"

    @api.depends("start_time", "end_time")
    def _compute_state(self):
        now = fields.Datetime.now()
        for slot in self:
            if not slot.start_time or not slot.end_time:
                slot.state = "todo"
            elif now < slot.start_time:
                slot.state = "todo"
            elif slot.start_time <= now <= slot.end_time:
                slot.state = "running"
            else:
                slot.state = "completed"
