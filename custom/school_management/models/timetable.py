from datetime import datetime, time, timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class UniversityTimeslot(models.Model):
    _name = "university.timeslot"
    _description = "Teaching Timeslot"
    _order = "day_of_week, start_hour, end_hour"

    name = fields.Char(string="Timeslot", compute="_compute_name", store=True)
    day_of_week = fields.Selection(
        [
            ("0", "Monday"),
            ("1", "Tuesday"),
            ("2", "Wednesday"),
            ("3", "Thursday"),
            ("4", "Friday"),
            ("5", "Saturday"),
            ("6", "Sunday"),
        ],
        string="Day",
        required=True,
        default="0",
    )
    start_hour = fields.Float(string="Start Hour", required=True, default=8.0)
    end_hour = fields.Float(string="End Hour", required=True, default=9.0)
    active = fields.Boolean(string="Active", default=True)

    @api.depends("day_of_week", "start_hour", "end_hour")
    def _compute_name(self):
        labels = dict(self._fields["day_of_week"].selection)
        for slot in self:
            slot.name = "%s %s-%s" % (
                labels.get(slot.day_of_week, "Day"),
                slot._format_hour(slot.start_hour),
                slot._format_hour(slot.end_hour),
            )

    @api.constrains("start_hour", "end_hour")
    def _check_hours(self):
        for slot in self:
            if slot.start_hour < 0 or slot.start_hour >= 24 or slot.end_hour > 24:
                raise ValidationError("Timeslot hours must be between 0 and 24.")
            if slot.start_hour >= slot.end_hour:
                raise ValidationError("Timeslot start hour must be before end hour.")

    def _datetime_for_week(self, week_start, week_offset=0):
        self.ensure_one()
        target_date = week_start + timedelta(
            days=int(self.day_of_week) + week_offset * 7
        )
        start = datetime.combine(target_date, self._hour_to_time(self.start_hour))
        end = datetime.combine(target_date, self._hour_to_time(self.end_hour))
        return start, end

    def _hour_to_time(self, value):
        if value >= 24:
            return time(hour=23, minute=59)
        hour = int(value)
        minute = int(round((value - hour) * 60))
        if minute == 60:
            hour += 1
            minute = 0
        return time(hour=hour, minute=minute)

    def _format_hour(self, value):
        return self._hour_to_time(value).strftime("%H:%M")

class UniversityTimetableSlot(models.Model):
    _name = "university.timetable.slot"
    _description = "Timetable Slot"
    _order = "start_time asc"

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    teacher_id = fields.Many2one("university.teacher", string="Teacher", required=True)
    section_id = fields.Many2one("university.class.section", string="Grade/Section", required=True)
    subject_id = fields.Many2one("university.subject", string="Subject", required=True)
    classroom_id = fields.Many2one("university.classroom", string="Classroom")
    timeslot_id = fields.Many2one("university.timeslot", string="Timeslot")
    academic_year_id = fields.Many2one(
        "university.academic.year",
        string="Academic Year",
        related="section_id.semester_id.academic_year_id",
        store=True,
        readonly=True,
    )
    semester_id = fields.Many2one(
        "university.semester",
        string="Semester",
        related="section_id.semester_id",
        store=True,
        readonly=True,
    )
    location = fields.Char(string="Location")
    start_time = fields.Datetime(string="Start Time", required=True)
    end_time = fields.Datetime(string="End Time", required=True)
    generation_state = fields.Selection(
        [("draft", "Draft"), ("published", "Published")],
        string="Generation Status",
        default="draft",
    )
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

    @api.onchange("classroom_id")
    def _onchange_classroom_id(self):
        if self.classroom_id and not self.location:
            self.location = self.classroom_id.name

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

    @api.constrains("start_time", "end_time")
    def _check_datetime_range(self):
        for slot in self:
            if slot.start_time and slot.end_time and slot.start_time >= slot.end_time:
                raise ValidationError("Timetable start time must be before end time.")

    @api.constrains("teacher_id", "section_id", "classroom_id", "start_time", "end_time")
    def _check_resource_conflicts(self):
        for slot in self:
            if not slot.start_time or not slot.end_time:
                continue
            overlap_domain = [
                ("id", "!=", slot.id),
                ("start_time", "<", slot.end_time),
                ("end_time", ">", slot.start_time),
            ]
            conflicts = []
            if slot.teacher_id and self.search_count(overlap_domain + [("teacher_id", "=", slot.teacher_id.id)]):
                conflicts.append("teacher")
            if slot.section_id and self.search_count(overlap_domain + [("section_id", "=", slot.section_id.id)]):
                conflicts.append("class section")
            if slot.classroom_id and self.search_count(overlap_domain + [("classroom_id", "=", slot.classroom_id.id)]):
                conflicts.append("classroom")
            if conflicts:
                raise ValidationError(
                    "Timetable conflict detected for: %s." % ", ".join(conflicts)
                )
