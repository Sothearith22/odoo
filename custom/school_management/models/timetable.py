from datetime import datetime, time, timedelta
import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


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

    _unique_timeslot = models.Constraint(
        "UNIQUE (day_of_week, start_hour, end_hour)",
        "A timeslot for this day and time range already exists.",
    )

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
        monday = week_start - timedelta(days=week_start.weekday())
        target_date = monday + timedelta(days=int(self.day_of_week) + week_offset * 7)
        tz = pytz.timezone(self.env.user.tz or "UTC")

        def to_utc(hour):
            local = datetime.combine(target_date, self._hour_to_time(hour))
            return tz.localize(local).astimezone(pytz.utc).replace(tzinfo=None)

        return to_utc(self.start_hour), to_utc(self.end_hour)

    def _hour_to_time(self, value):
        if value >= 24:
            return time(hour=23, minute=59)
        hour = int(value)
        minute = int(round((value - hour) * 60))
        if minute == 60:
            hour += 1
            minute = 0
        return time(hour=hour, minute=minute)

    def _datetime_for_date(self, target_date):
        self.ensure_one()
        tz = pytz.timezone(self.env.user.tz or "UTC")
        local_start = datetime.combine(target_date, self._hour_to_time(self.start_hour))
        local_end = datetime.combine(target_date, self._hour_to_time(self.end_hour))
        utc_start = tz.localize(local_start).astimezone(pytz.utc).replace(tzinfo=None)
        utc_end = tz.localize(local_end).astimezone(pytz.utc).replace(tzinfo=None)
        return utc_start, utc_end

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
        [("draft", "Draft"), ("published", "Published"), ("cancelled", "Cancelled")],
        string="Schedule Status",
        default="draft",
    )
    class_id = fields.Many2one(
        "university.class.section",
        string="Class Section",
        compute="_compute_class_id",
        inverse="_inverse_class_id",
        store=True,
        index=True,
    )
    room_id = fields.Many2one(
        "university.classroom",
        string="Room",
        compute="_compute_room_id",
        inverse="_inverse_room_id",
        store=True,
    )
    date = fields.Date(
        string="Session Date",
        compute="_compute_date",
        inverse="_inverse_date",
        store=True,
        index=True,
    )
    cancel_reason = fields.Char(string="Cancellation Reason")
    is_holiday_conflict = fields.Boolean(
        string="Holiday Conflict",
        compute="_compute_is_holiday_conflict",
        store=True,
        index=True,
    )
    state = fields.Selection(
        [
            ("scheduled", "Scheduled"),
            ("draft", "Draft"),
            ("published", "Published"),
            ("cancelled", "Cancelled"),
            ("done", "Done"),
            ("completed", "Completed"),
            ("rescheduled", "Rescheduled"),
        ],
        string="Schedule State",
        default="scheduled",
        required=True,
    )
    status = fields.Selection(
        [
            ("upcoming", "Upcoming"),
            ("ongoing", "Ongoing"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Session Status",
        compute="_compute_status",
        store=True,
    )
    session_type = fields.Selection(
        [
            ("lecture", "Lecture"),
            ("lab", "Lab"),
            ("exam", "Exam"),
        ],
        string="Session Type",
        default="lecture",
        required=True,
    )
    is_room_changed = fields.Boolean(string="Room Changed", default=False)
    original_classroom_id = fields.Many2one("university.classroom", string="Original Classroom")
    notes = fields.Text(string="Session Notes")
    enrolled_student_count = fields.Integer(
        string="Enrolled Count",
        related="section_id.enrolled_student_count",
        readonly=True,
    )
    room_capacity = fields.Integer(
        string="Room Capacity",
        related="classroom_id.capacity",
        readonly=True,
    )
    duration_hours = fields.Float(
        string="Duration (Hours)",
        compute="_compute_duration_hours",
        store=True,
    )
    day_name = fields.Char(
        string="Day",
        compute="_compute_schedule_slot_display",
        inverse="_inverse_day_name",
        store=True,
    )
    period = fields.Char(
        string="Period",
        compute="_compute_schedule_slot_display",
        inverse="_inverse_period",
        store=True,
    )
    is_today = fields.Boolean(
        string="Is Today",
        compute="_compute_is_today",
        search="_search_is_today",
    )
    is_this_week = fields.Boolean(
        string="Is This Week",
        compute="_compute_is_this_week",
        search="_search_is_this_week",
    )
    has_attendance = fields.Boolean(
        string="Has Attendance",
        compute="_compute_has_attendance",
    )

    def _compute_has_attendance(self):
        AttendanceSession = self.env.get("university.attendance.session")
        Attendance = self.env.get("university.attendance")
        for slot in self:
            slot_date = slot.date or (fields.Datetime.context_timestamp(slot, slot.start_time).date() if slot.start_time else False)
            if not slot_date or not slot.section_id:
                slot.has_attendance = False
                continue
            has_session = AttendanceSession and AttendanceSession.search_count([
                ("section_id", "=", slot.section_id.id),
                ("date", "=", slot_date),
            ]) > 0
            has_student_att = Attendance and Attendance.search_count([
                ("section_id", "=", slot.section_id.id),
                ("date", "=", slot_date),
            ]) > 0
            slot.has_attendance = bool(has_session or has_student_att)

    @api.depends("start_time", "end_time", "state")
    def _compute_status(self):
        now = fields.Datetime.now()
        for slot in self:
            if slot.state == "cancelled":
                slot.status = "cancelled"
            elif not slot.start_time or not slot.end_time:
                slot.status = "upcoming"
            elif now < slot.start_time:
                slot.status = "upcoming"
            elif slot.start_time <= now <= slot.end_time:
                slot.status = "ongoing"
            else:
                slot.status = "completed"

    @api.depends("start_time", "end_time", "timeslot_id")
    def _compute_schedule_slot_display(self):
        day_labels = {
            "0": "Monday",
            "1": "Tuesday",
            "2": "Wednesday",
            "3": "Thursday",
            "4": "Friday",
            "5": "Saturday",
            "6": "Sunday",
        }
        for slot in self:
            if slot.start_time:
                slot_dt = fields.Datetime.context_timestamp(slot, slot.start_time)
                slot.day_name = slot_dt.strftime("%A")
            elif slot.timeslot_id and slot.timeslot_id.day_of_week:
                slot.day_name = day_labels.get(slot.timeslot_id.day_of_week, "Monday")
            else:
                slot.day_name = slot.day_name or "Monday"

            if slot.start_time and slot.end_time:
                start_dt = fields.Datetime.context_timestamp(slot, slot.start_time)
                end_dt = fields.Datetime.context_timestamp(slot, slot.end_time)
                slot.period = f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}"
            elif slot.timeslot_id:
                slot.period = slot.timeslot_id.name or "08:00 AM - 09:00 AM"
            else:
                slot.period = slot.period or ""

    def _inverse_day_name(self):
        for slot in self:
            pass

    def _inverse_period(self):
        for slot in self:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            sec_id = vals.get("section_id")
            if sec_id:
                sec = self.env["university.class.section"].browse(sec_id)
                if not vals.get("subject_id") and sec.subject_id:
                    vals["subject_id"] = sec.subject_id.id
                if not vals.get("teacher_id") and sec.teacher_id:
                    vals["teacher_id"] = sec.teacher_id.id
                if not vals.get("classroom_id") and sec.classroom_id:
                    vals["classroom_id"] = sec.classroom_id.id
                    if not vals.get("location"):
                        vals["location"] = sec.classroom_id.name
            if not vals.get("start_time"):
                now = fields.Datetime.now()
                vals["start_time"] = now.replace(hour=8, minute=0, second=0)
            if not vals.get("end_time"):
                now = fields.Datetime.now()
                vals["end_time"] = now.replace(hour=9, minute=0, second=0)
            if vals.get("classroom_id") and not vals.get("location"):
                room = self.env["university.classroom"].browse(vals["classroom_id"])
                vals["location"] = room.name
        return super().create(vals_list)

    @api.depends("start_time", "end_time")
    def _compute_duration_hours(self):
        for slot in self:
            if slot.start_time and slot.end_time:
                delta = slot.end_time - slot.start_time
                slot.duration_hours = round(delta.total_seconds() / 3600.0, 2)
            else:
                slot.duration_hours = 0.0

    def _compute_is_today(self):
        today = fields.Date.context_today(self)
        for slot in self:
            if slot.start_time:
                slot_date = fields.Datetime.context_timestamp(slot, slot.start_time).date()
                slot.is_today = (slot_date == today)
            else:
                slot.is_today = False

    def _search_is_today(self, operator, value):
        if operator not in ("=", "!="):
            return []
        today = fields.Date.context_today(self)
        tz_name = self.env.user.tz or "UTC"
        tz = pytz.timezone(tz_name)
        start_dt = tz.localize(datetime.combine(today, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        end_dt = tz.localize(datetime.combine(today, time.max)).astimezone(pytz.utc).replace(tzinfo=None)
        if (operator == "=" and value) or (operator == "!=" and not value):
            return [("start_time", ">=", start_dt), ("start_time", "<=", end_dt)]
        else:
            return ["|", ("start_time", "<", start_dt), ("start_time", ">", end_dt)]

    def _compute_is_this_week(self):
        today = fields.Date.context_today(self)
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        for slot in self:
            if slot.start_time:
                slot_date = fields.Datetime.context_timestamp(slot, slot.start_time).date()
                slot.is_this_week = (monday <= slot_date <= sunday)
            else:
                slot.is_this_week = False

    def _search_is_this_week(self, operator, value):
        if operator not in ("=", "!="):
            return []
        today = fields.Date.context_today(self)
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        tz_name = self.env.user.tz or "UTC"
        tz = pytz.timezone(tz_name)
        start_dt = tz.localize(datetime.combine(monday, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        end_dt = tz.localize(datetime.combine(sunday, time.max)).astimezone(pytz.utc).replace(tzinfo=None)
        if (operator == "=" and value) or (operator == "!=" and not value):
            return [("start_time", ">=", start_dt), ("start_time", "<=", end_dt)]
        else:
            return ["|", ("start_time", "<", start_dt), ("start_time", ">", end_dt)]

    @api.depends("section_id.name", "subject_id.name", "classroom_id.name", "location")
    def _compute_name(self):
        for slot in self:
            subj = slot.subject_id.name if slot.subject_id else "Class"
            room = slot.classroom_id.name or slot.location or ""
            sec = slot.section_id.name or ""
            if room and sec:
                slot.name = f"{subj} ({sec} - {room})"
            elif room:
                slot.name = f"{subj} [{room}]"
            elif sec:
                slot.name = f"{subj} ({sec})"
            else:
                slot.name = subj

    @api.onchange("start_time", "section_id")
    def _onchange_start_time_holiday_warning(self):
        if self.start_time:
            slot_date = fields.Datetime.context_timestamp(self, self.start_time).date()
            faculty = (
                self.section_id.program_id.department_id.faculty_id
                if self.section_id and self.section_id.program_id and self.section_id.program_id.department_id
                else False
            )
            holiday = self.env["university.holiday"].sudo().search([
                ("date_start", "<=", slot_date),
                ("date_end", ">=", slot_date),
                "|",
                ("faculty_id", "=", False),
                ("faculty_id", "=", faculty.id if faculty else False),
            ], limit=1)
            if not holiday and hasattr(Holiday, "date_from"):
                domain_fallback = [
                    ("date_from", "<=", slot_date),
                    ("date_to", ">=", slot_date),
                    "|",
                    ("faculty_id", "=", False),
                    ("faculty_id", "=", faculty.id if faculty else False),
                ]
                holiday = Holiday.search(domain_fallback, limit=1)
            if holiday:
                return {
                    "warning": {
                        "title": _("Public Holiday Warning"),
                        "message": _("Warning: The date %s falls on public holiday '%s'. Classes should not be scheduled on this date.") % (slot_date, holiday.name),
                    }
                }

    @api.onchange("classroom_id")
    def _onchange_classroom_id(self):
        if self.classroom_id and not self.location:
            self.location = self.classroom_id.name

    @api.depends("section_id")
    def _compute_class_id(self):
        for slot in self:
            slot.class_id = slot.section_id

    def _inverse_class_id(self):
        for slot in self:
            if slot.class_id:
                slot.section_id = slot.class_id

    @api.depends("classroom_id")
    def _compute_room_id(self):
        for slot in self:
            slot.room_id = slot.classroom_id

    def _inverse_room_id(self):
        for slot in self:
            if slot.room_id:
                slot.classroom_id = slot.room_id

    @api.depends("start_time")
    def _compute_date(self):
        for slot in self:
            if slot.start_time:
                slot.date = fields.Datetime.context_timestamp(slot, slot.start_time).date()
            else:
                slot.date = False

    def _inverse_date(self):
        for slot in self:
            if slot.date and slot.start_time:
                tz_name = self.env.user.tz or "UTC"
                tz = pytz.timezone(tz_name)
                curr_dt = fields.Datetime.context_timestamp(slot, slot.start_time)
                new_start_dt = curr_dt.replace(year=slot.date.year, month=slot.date.month, day=slot.date.day)
                slot.start_time = tz.localize(new_start_dt.replace(tzinfo=None)).astimezone(pytz.utc).replace(tzinfo=None)
                if slot.end_time:
                    curr_end_dt = fields.Datetime.context_timestamp(slot, slot.end_time)
                    new_end_dt = curr_end_dt.replace(year=slot.date.year, month=slot.date.month, day=slot.date.day)
                    slot.end_time = tz.localize(new_end_dt.replace(tzinfo=None)).astimezone(pytz.utc).replace(tzinfo=None)

    @api.depends("start_time", "section_id")
    def _compute_is_holiday_conflict(self):
        for slot in self:
            if hasattr(slot, "on_holiday"):
                slot.is_holiday_conflict = slot.on_holiday
            else:
                slot.is_holiday_conflict = bool(slot._get_holiday_conflict())

    @api.onchange("classroom_id", "section_id")
    def _onchange_classroom_capacity(self):
        if self.classroom_id and self.section_id and self.section_id.capacity:
            if self.classroom_id.capacity and self.classroom_id.capacity < self.section_id.capacity:
                return {
                    "warning": {
                        "title": _("Room Capacity Warning"),
                        "message": _(
                            "Warning: Classroom '%(room)s' capacity (%(rcap)d) is smaller than the class capacity (%(ccap)d)."
                        )
                        % {
                            "room": self.classroom_id.name,
                            "rcap": self.classroom_id.capacity,
                            "ccap": self.section_id.capacity,
                        },
                    }
                }

    @api.constrains("start_time", "section_id")
    def _check_term_range(self):
        if self.env.context.get("skip_term_range_check"):
            return
        for slot in self:
            if slot.start_time and slot.semester_id:
                slot_date = slot.date or fields.Datetime.context_timestamp(slot, slot.start_time).date()
                if slot.semester_id.date_start and slot.semester_id.date_end and (slot.semester_id.date_end - slot.semester_id.date_start).days >= 7:
                    if slot_date < slot.semester_id.date_start or slot_date > slot.semester_id.date_end:
                        raise ValidationError(
                            _("Session date %(date)s is outside the academic term range (%(start)s to %(end)s).")
                            % {
                                "date": slot_date,
                                "start": slot.semester_id.date_start,
                                "end": slot.semester_id.date_end,
                            }
                        )

    @api.constrains("start_time", "end_time")
    def _check_datetime_range(self):
        for slot in self:
            if slot.start_time and slot.end_time and slot.start_time >= slot.end_time:
                raise ValidationError("Timetable start time must be before end time.")

    @api.constrains("teacher_id", "section_id", "classroom_id", "start_time", "end_time", "state")
    def _check_resource_conflicts(self):
        if self.env.context.get("skip_conflict_check"):
            return
        for slot in self:
            if slot.state == "cancelled" or not slot.start_time or not slot.end_time:
                continue
            overlap_domain = [
                ("id", "!=", slot.id),
                ("state", "!=", "cancelled"),
                ("start_time", "<", slot.end_time),
                ("end_time", ">", slot.start_time),
            ]
            conflicts = []
            # Check using sudo() so user record rules do not hide occupied resources
            if slot.teacher_id and self.sudo().search_count(overlap_domain + [("teacher_id", "=", slot.teacher_id.id)]):
                conflicts.append(_("Teacher '%s' is already scheduled during this time slot.") % (slot.teacher_id.name or ""))
            if slot.section_id and self.sudo().search_count(overlap_domain + [("section_id", "=", slot.section_id.id)]):
                conflicts.append(_("Class section '%s' already has an active session during this time slot.") % (slot.section_id.name or ""))
            if slot.classroom_id and slot.classroom_id.status in ("maintenance", "inactive"):
                conflicts.append(_("Classroom '%s' is under maintenance or inactive and cannot be assigned.") % (slot.classroom_id.name or ""))
            if slot.classroom_id and self.sudo().search_count(overlap_domain + [("classroom_id", "=", slot.classroom_id.id)]):
                conflicts.append(_("Classroom '%s' is already occupied during this time slot.") % (slot.classroom_id.name or ""))
            if conflicts:
                raise ValidationError(
                    _("Timetable conflict detected:\n• %s") % "\n• ".join(conflicts)
                )

    def _get_holiday_conflict(self):
        """Hook for holiday modules to detect conflicts with holidays."""
        self.ensure_one()
        if self.state == "cancelled" or not self.start_time:
            return False
        if getattr(self, "allow_on_holiday", False):
            return False
        slot_date = self.date or fields.Datetime.context_timestamp(self, self.start_time).date()
        if self.semester_id and self.semester_id.academic_year_id:
            holiday = self.env["university.holiday"].search([
                ("academic_year_id", "=", self.semester_id.academic_year_id.id),
                ("date_start", "<=", slot_date),
                ("date_end", ">=", slot_date),
            ], limit=1)
            if holiday:
                return holiday
        return False

    @api.constrains("start_time", "section_id")
    def _check_holiday_conflict(self):
        for slot in self:
            conflict = slot._get_holiday_conflict()
            if conflict:
                raise ValidationError(
                    _("Cannot schedule session '%(session)s' on %(date)s because it falls on public holiday '%(holiday)s'. "
                      "University policy blocks classes on holidays.")
                    % {
                        "session": slot.name or slot.section_id.name,
                        "date": fields.Datetime.context_timestamp(slot, slot.start_time).date() if slot.start_time else "",
                        "holiday": getattr(conflict, "name", str(conflict)),
                    }
                )

    def action_publish(self):
        self._check_publish_access()
        self.write({"generation_state": "published"})

    def action_set_draft(self):
        self._check_publish_access()
        self.write({"generation_state": "draft"})

    def _check_publish_access(self):
        user = self.env.user
        if not (
            self.env.is_system()
            or user.has_group("school_management.group_school_admin")
            or user.has_group("school_management.group_school_hod")
        ):
            raise AccessError(_("Only School Administrators and Heads of Department can change the generation status."))

    def _check_modify_access(self):
        self.ensure_one()
        user = self.env.user
        if (
            self.env.is_system()
            or user.has_group("school_management.group_school_admin")
            or user.has_group("school_management.group_school_hod")
            or user.has_group("school_management.group_school_dean")
        ):
            return True
        if user.has_group("school_management.group_school_teacher"):
            if (self.teacher_id and self.teacher_id.user_id == user) or (self.section_id.teacher_id and self.section_id.teacher_id.user_id == user):
                return True
        raise AccessError(_("You do not have permission to modify this timetable session."))

    def write(self, vals):
        user = self.env.user
        if not (
            self.env.is_system()
            or user.has_group("school_management.group_school_admin")
            or user.has_group("school_management.group_school_hod")
            or user.has_group("school_management.group_school_dean")
        ):
            for slot in self:
                slot._check_modify_access()
        if vals.get("state") == "cancelled" and "generation_state" not in vals:
            vals["generation_state"] = "cancelled"
        return super().write(vals)

    def unlink(self):
        user = self.env.user
        if not (self.env.is_system() or user.has_group("school_management.group_school_admin")):
            raise AccessError(_("Only administrators can delete timetable sessions."))
        for slot in self:
            if slot.has_attendance:
                raise ValidationError(_("Cannot delete session '%s' because attendance has already been recorded.") % (slot.name or slot.display_name))
            if slot.state in ("done", "completed") or slot.status == "completed":
                raise ValidationError(_("Cannot delete completed session '%s'.") % (slot.name or slot.display_name))
        return super().unlink()

    def action_cancel_session(self):
        self.ensure_one()
        self._check_modify_access()
        self.write({"state": "cancelled", "generation_state": "cancelled"})
        return True

    def action_reschedule_session(self, new_start_time, new_end_time, new_classroom_id=None):
        self.ensure_one()
        self._check_modify_access()
        vals = {
            "start_time": new_start_time,
            "end_time": new_end_time,
            "state": "rescheduled",
        }
        if new_classroom_id and new_classroom_id != (self.classroom_id.id if self.classroom_id else None):
            if not self.original_classroom_id and self.classroom_id:
                vals["original_classroom_id"] = self.classroom_id.id
            vals["classroom_id"] = new_classroom_id
            vals["is_room_changed"] = True
        self.write(vals)
        return True

    def action_save_notes(self, notes):
        self.ensure_one()
        self._check_modify_access()
        self.write({"notes": notes})
        return True

    def action_create_assignment(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Assignment - %s", self.name),
            "res_model": "university.assignment",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_section_id": self.section_id.id,
                "default_subject_id": self.subject_id.id,
                "default_teacher_id": self.teacher_id.id,
            },
        }

    def action_upload_material(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Course Materials - %s", self.name),
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "target": "current",
            "domain": [("res_model", "=", "university.timetable.slot"), ("res_id", "=", self.id)],
            "context": {
                "default_res_model": "university.timetable.slot",
                "default_res_id": self.id,
            },
        }

    @api.model
    def _cron_update_states(self):
        now = fields.Datetime.now()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        slots = self.search([
            ("start_time", ">=", yesterday),
            ("start_time", "<=", tomorrow),
        ])
        slots._compute_status()

    def check_can_manage_attendance(self):
        self.ensure_one()
        user = self.env.user
        if self.env.is_system() or user.has_group("school_management.group_school_admin"):
            return True

        # Students cannot manage attendance
        if user.has_group("school_management.group_school_student") and not (
            user.has_group("school_management.group_school_teacher")
            or user.has_group("school_management.group_school_hod")
            or user.has_group("school_management.group_school_dean")
            or user.has_group("school_management.group_school_admin")
        ):
            return False

        slot_sudo = self.sudo()
        section_sudo = slot_sudo.section_id

        # Head of Faculty (Dean)
        if user.has_group("school_management.group_school_dean"):
            dean_user = (
                section_sudo.program_id.department_id.faculty_id.dean_id.user_id
                or section_sudo.subject_id.department_id.faculty_id.dean_id.user_id
            )
            if dean_user and dean_user == user:
                return True

        # Head of Department (HOD)
        if user.has_group("school_management.group_school_hod"):
            hod_user = (
                section_sudo.program_id.department_id.head_id.user_id
                or section_sudo.subject_id.department_id.head_id.user_id
            )
            if hod_user and hod_user == user:
                return True

        # Teacher assigned to slot or section
        if user.has_group("school_management.group_school_teacher"):
            if (
                (slot_sudo.teacher_id and slot_sudo.teacher_id.user_id == user)
                or (section_sudo.teacher_id and section_sudo.teacher_id.user_id == user)
            ):
                return True

        return False

    def action_track_attendance(self):
        self.ensure_one()
        if not self.check_can_manage_attendance():
            raise AccessError(_("You do not have permission to manage attendance for this class."))
        action = self.env.ref("school_management.action_university_attendance_sheet").sudo().read()[0]
        attendance_date = fields.Date.context_today(self)
        if self.start_time:
            attendance_date = fields.Datetime.context_timestamp(self, self.start_time).date()
        date_value = fields.Date.to_string(attendance_date)
        action["name"] = "Track Attendance"
        action["context"] = {
            "default_section_id": self.section_id.id,
            "section_id": self.section_id.id,
            "default_date": date_value,
            "date": date_value,
        }
        return action

    def action_view_assignments(self):
        self.ensure_one()
        user = self.env.user
        domain = [("section_id", "=", self.section_id.id)]
        if self.subject_id:
            domain.append(("subject_id", "=", self.subject_id.id))
        
        if user.has_group("school_management.group_school_student") and not (
            user.has_group("school_management.group_school_teacher") or user.has_group("school_management.group_school_admin")
        ):
            domain.append(("state", "=", "approved"))

        return {
            "type": "ir.actions.act_window",
            "name": _("Assignments - %s", self.name),
            "res_model": "university.assignment",
            "view_mode": "list,form",
            "domain": domain,
            "context": {
                "default_section_id": self.section_id.id,
                "default_subject_id": self.subject_id.id,
                "default_teacher_id": self.teacher_id.id,
            },
        }

    # =========================================================================
    # High-Performance Schedule View Data API
    # =========================================================================
    @api.model
    def get_schedule(self, date_from, date_to, filters=None, limit=500, offset=0):
        """
        Unified Schedule API for Student, Teacher, and Administrator roles.
        Check order: Admin -> Teacher -> Student -> Unauthorized.
        Returns:
            JSON payload with list of sessions containing:
            id, subject, section_code, start, end, room, teacher, status,
            student_count, conflict_flag, and metadata (holidays, next_class, etc.)
        """
        user = self.env.user
        filters = filters or {}
        tz_name = user.tz or "UTC"
        user_tz = pytz.timezone(tz_name)

        # 1. Determine User Role with explicit priority
        # When a user belongs to multiple groups (e.g. Teacher + Admin), Admin wins.
        is_admin = (
            self.env.is_system()
            or user.has_group("base.group_system")
            or user.has_group("school_management.group_school_admin")
            or user.has_group("school_management.group_school_dean")
            or user.has_group("school_management.group_school_hod")
        )
        is_teacher = user.has_group("school_management.group_school_teacher")
        is_student = user.has_group("school_management.group_school_student")

        if is_admin:
            role = "admin"
        elif is_teacher:
            role = "teacher"
        elif is_student:
            role = "student"
        else:
            return {
                "role": "unauthorized",
                "sessions": [],
                "slots": [],
                "total_count": 0,
                "error": "unauthorized",
                "message": _("You do not have permission to access university schedules."),
            }

        # 2. Check profile linkage for student/teacher
        student_rec = False
        teacher_rec = False

        if role == "student":
            student_rec = self.env["university.student"].search([("user_id", "=", user.id)], limit=1)
            if not student_rec:
                return {
                    "role": "student",
                    "sessions": [],
                    "slots": [],
                    "total_count": 0,
                    "error": "no_linked_profile",
                    "message": _("No Student record is linked to your user account (%s). Please contact the registrar or IT administrator.") % user.name,
                }
        elif role == "teacher":
            teacher_rec = self.env["university.teacher"].search([("user_id", "=", user.id)], limit=1)
            if not teacher_rec:
                return {
                    "role": "teacher",
                    "sessions": [],
                    "slots": [],
                    "total_count": 0,
                    "error": "no_linked_profile",
                    "message": _("No Teacher/Faculty record is linked to your user account (%s). Please contact the academic administrator.") % user.name,
                }
        else:
            teacher_rec = self.env["university.teacher"].search([("user_id", "=", user.id)], limit=1)

        # 3. Parse date bounds and convert to UTC
        if isinstance(date_from, str):
            date_from_clean = date_from.split(" ")[0].split("T")[0]
            start_date = fields.Date.from_string(date_from_clean)
        elif isinstance(date_from, datetime):
            start_date = date_from.date()
        else:
            start_date = date_from or fields.Date.context_today(self)

        if isinstance(date_to, str):
            date_to_clean = date_to.split(" ")[0].split("T")[0]
            end_date = fields.Date.from_string(date_to_clean)
        elif isinstance(date_to, datetime):
            end_date = date_to.date()
        else:
            end_date = date_to or (start_date + timedelta(days=7))

        start_utc = user_tz.localize(datetime.combine(start_date, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        end_utc = user_tz.localize(datetime.combine(end_date, time.max)).astimezone(pytz.utc).replace(tzinfo=None)

        # 4. Build Search Domain based on Role
        domain = [
            ("start_time", ">=", start_utc),
            ("start_time", "<=", end_utc),
        ]

        enrolled_section_ids = []
        if role == "student":
            domain.append(("generation_state", "=", "published"))
            enrollments = self.env["university.enrollment"].search([
                ("student_id", "=", student_rec.id),
                ("status", "=", "enrolled"),
            ])
            enrolled_section_ids = enrollments.mapped("class_section_id").ids or enrollments.mapped("section_id").ids
            if not enrolled_section_ids:
                return {
                    "role": "student",
                    "sessions": [],
                    "slots": [],
                    "total_count": 0,
                    "status": "empty",
                    "message": _("You are not currently enrolled in any active class sections."),
                    "student_info": {
                        "id": student_rec.id,
                        "name": student_rec.name,
                        "attendance_rate": getattr(student_rec, "attendance_rate", 100.0),
                        "attendance_warning": False,
                    },
                    "next_class": None,
                    "holidays": [],
                }
            domain.append(("section_id", "in", enrolled_section_ids))
        elif role == "teacher":
            domain.append(("generation_state", "=", "published"))
            domain.append("|")
            domain.append(("teacher_id", "=", teacher_rec.id))
            domain.append(("section_id.teacher_id", "=", teacher_rec.id))
        else:
            # Admin role: full visibility with filters
            filters = filters or {}
            faculty_id = filters.get("faculty_id") or filters.get("faculty")
            if faculty_id:
                domain.append("|")
                domain.append(("section_id.program_id.department_id.faculty_id", "=", int(faculty_id)))
                domain.append(("section_id.subject_id.department_id.faculty_id", "=", int(faculty_id)))

            program_id = filters.get("program_id") or filters.get("program")
            if program_id:
                domain.append(("section_id.program_id", "=", int(program_id)))

            # Common semester filter applied below

            teacher_id = filters.get("teacher_id") or filters.get("teacher")
            if teacher_id:
                domain.append(("teacher_id", "=", int(teacher_id)))

            section_id = filters.get("section_id") or filters.get("section")
            if section_id:
                domain.append(("section_id", "=", int(section_id)))

            classroom_id = filters.get("classroom_id") or filters.get("classroom")
            if classroom_id:
                domain.append(("classroom_id", "=", int(classroom_id)))

            subject_id = filters.get("subject_id") or filters.get("subject")
            if subject_id:
                domain.append(("subject_id", "=", int(subject_id)))

            session_type = filters.get("session_type")
            if session_type:
                domain.append(("session_type", "=", session_type))

            state_filter = filters.get("state")
            if state_filter:
                domain.append(("state", "=", state_filter))

        # Semester / Academic Term filter applied across all roles
        common_semester_id = filters.get("semester_id") or filters.get("semester")
        if common_semester_id:
            domain.append(("semester_id", "=", int(common_semester_id)))

        # 5. Query slots with limit & offset (preventing N+1 with batch fetch)
        total_count = self.search_count(domain)
        slots = self.search(domain, order="start_time asc", limit=limit or 500, offset=offset or 0)

        # 6. Optimized Cross-Resource Conflict Detection (Single batch query)
        all_active_slots = self.sudo().search([
            ("start_time", ">=", start_utc),
            ("start_time", "<=", end_utc),
            ("state", "!=", "cancelled"),
        ])

        conflict_map = {}
        for s in all_active_slots:
            if not s.start_time or not s.end_time:
                continue
            for other in all_active_slots:
                if other.id == s.id or not other.start_time or not other.end_time:
                    continue
                if other.start_time < s.end_time and other.end_time > s.start_time:
                    reasons = []
                    if s.classroom_id and other.classroom_id and s.classroom_id.id == other.classroom_id.id:
                        reasons.append(_("Room '%s' double-booked with %s") % (s.classroom_id.name, other.name or other.subject_id.name))
                    if s.teacher_id and other.teacher_id and s.teacher_id.id == other.teacher_id.id:
                        reasons.append(_("Teacher '%s' double-booked with %s") % (s.teacher_id.name, other.name or other.subject_id.name))
                    if reasons:
                        conflict_map.setdefault(s.id, []).extend(reasons)

        # 7. Student Attendance Map (Single query)
        attendance_map = {}
        if student_rec:
            attendances = self.env["university.attendance"].search([
                ("student_id", "=", student_rec.id),
                ("date", ">=", start_date),
                ("date", "<=", end_date),
            ])
            for att in attendances:
                attendance_map[(att.section_id.id, att.date)] = att.status

        # 8. Holiday Markers
        holidays_data = []
        holidays = self.env["university.holiday"].sudo().search([
            ("date_start", "<=", end_date),
            ("date_end", ">=", start_date),
        ])
        for h in holidays:
            d_start = h.date_start or getattr(h, "date_from", None)
            d_end = h.date_end or getattr(h, "date_to", None) or d_start
            holidays_data.append({
                "id": h.id,
                "name": h.name,
                "date_start": fields.Date.to_string(d_start),
                "date_end": fields.Date.to_string(d_end),
                "date_from": fields.Date.to_string(d_start),
                "date_to": fields.Date.to_string(d_end),
                "faculty_name": h.faculty_id.name if h.faculty_id else _("University-Wide"),
                "holiday_type": getattr(h, "holiday_type", "public") or "public",
            })

        # 9. Format Sessions
        formatted_sessions = []
        total_teaching_hours = 0.0

        for slot in slots:
            slot_start_local = fields.Datetime.context_timestamp(slot, slot.start_time)
            slot_end_local = fields.Datetime.context_timestamp(slot, slot.end_time)
            slot_date = slot_start_local.date()
            slot_date_str = fields.Date.to_string(slot_date)

            start_hour_decimal = slot_start_local.hour + (slot_start_local.minute / 60.0)
            end_hour_decimal = slot_end_local.hour + (slot_end_local.minute / 60.0)
            duration_hours = max(0.25, round(end_hour_decimal - start_hour_decimal, 2))

            if slot.state != "cancelled":
                total_teaching_hours += duration_hours

            att_status = attendance_map.get((slot.section_id.id, slot_date))
            student_attendance = att_status if att_status else ("pending" if slot.status in ("upcoming", "ongoing") else "unrecorded")

            enrolled_count = slot.section_id.enrolled_student_count or 0
            room_cap = slot.classroom_id.capacity or 0
            is_overcapacity = bool(room_cap > 0 and enrolled_count > room_cap)

            conflicts_for_slot = conflict_map.get(slot.id, [])
            has_conflict = bool(conflicts_for_slot)

            formatted_sessions.append({
                "id": slot.id,
                "name": slot.name or "",
                "subject": slot.subject_id.name or "Subject",
                "subject_id": slot.subject_id.id,
                "subject_name": slot.subject_id.name or "Subject",
                "subject_code": getattr(slot.subject_id, "code", "") or "",
                "section_code": slot.section_id.name or "Section",
                "section_id": slot.section_id.id,
                "section_name": slot.section_id.name or "Section",
                "start": fields.Datetime.to_string(slot.start_time),
                "end": fields.Datetime.to_string(slot.end_time),
                "start_time": fields.Datetime.to_string(slot.start_time),
                "end_time": fields.Datetime.to_string(slot.end_time),
                "date_str": slot_date_str,
                "start_time_str": slot_start_local.strftime("%H:%M"),
                "end_time_str": slot_end_local.strftime("%H:%M"),
                "room": slot.classroom_id.name or slot.location or "Room TBA",
                "classroom_id": slot.classroom_id.id if slot.classroom_id else False,
                "classroom_name": slot.classroom_id.name or slot.location or "Room TBA",
                "building": slot.classroom_id.building or "Main Campus",
                "room_type": slot.classroom_id.room_type or "classroom",
                "room_capacity": room_cap,
                "teacher": slot.teacher_id.name or "Instructor",
                "teacher_id": slot.teacher_id.id if slot.teacher_id else False,
                "teacher_name": slot.teacher_id.name or "Instructor",
                "teacher_email": slot.teacher_id.email or "",
                "status": slot.status or "upcoming",
                "state": slot.state or "scheduled",
                "generation_state": slot.generation_state or "draft",
                "semester_id": slot.semester_id.id if slot.semester_id else False,
                "semester_name": slot.semester_id.name if slot.semester_id else "",
                "session_type": slot.session_type or "lecture",
                "student_count": enrolled_count,
                "enrolled_student_count": enrolled_count,
                "is_overcapacity": is_overcapacity,
                "conflict": has_conflict,
                "conflict_flag": has_conflict,
                "conflict_details": conflicts_for_slot,
                "is_room_changed": slot.is_room_changed,
                "original_room_name": slot.original_classroom_id.name if slot.original_classroom_id else "",
                "notes": slot.notes or "",
                "start_hour_decimal": start_hour_decimal,
                "end_hour_decimal": end_hour_decimal,
                "duration_hours": duration_hours,
                "student_attendance": student_attendance,
            })

        # 10. Next Upcoming Class Banner
        now_utc = fields.Datetime.now()
        next_class_domain = [
            ("generation_state", "=", "published"),
            ("state", "!=", "cancelled"),
            ("end_time", ">=", now_utc),
        ]
        if role == "student" and enrolled_section_ids:
            next_class_domain.append(("section_id", "in", enrolled_section_ids))
        elif role == "teacher" and teacher_rec:
            next_class_domain.append("|")
            next_class_domain.append(("teacher_id", "=", teacher_rec.id))
            next_class_domain.append(("section_id.teacher_id", "=", teacher_rec.id))

        next_slot = self.search(next_class_domain, order="start_time asc", limit=1)
        next_class_info = None
        if next_slot:
            ns_start_local = fields.Datetime.context_timestamp(next_slot, next_slot.start_time)
            ns_end_local = fields.Datetime.context_timestamp(next_slot, next_slot.end_time)
            is_ongoing = (next_slot.start_time <= now_utc <= next_slot.end_time)
            diff_seconds = (next_slot.start_time - now_utc).total_seconds() if not is_ongoing else (next_slot.end_time - now_utc).total_seconds()
            diff_minutes = max(1, int(round(diff_seconds / 60.0)))

            next_class_info = {
                "id": next_slot.id,
                "subject_name": next_slot.subject_id.name or "Class",
                "section_name": next_slot.section_id.name or "",
                "classroom_name": next_slot.classroom_id.name or next_slot.location or "Room TBA",
                "building": next_slot.classroom_id.building or "Main",
                "teacher_name": next_slot.teacher_id.name or "",
                "session_type": next_slot.session_type or "lecture",
                "date_str": fields.Date.to_string(ns_start_local.date()),
                "time_str": f"{ns_start_local.strftime('%H:%M')} – {ns_end_local.strftime('%H:%M')}",
                "is_ongoing": is_ongoing,
                "minutes_left": diff_minutes,
                "status": next_slot.status,
            }

        student_attendance_rate = student_rec.attendance_rate if student_rec and hasattr(student_rec, "attendance_rate") else 100.0
        attendance_warning = bool(student_rec and student_attendance_rate < 80.0)

        return {
            "role": role,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "sessions": formatted_sessions,
            "slots": formatted_sessions,
            "holidays": holidays_data,
            "next_class": next_class_info,
            "student_info": {
                "id": student_rec.id if student_rec else False,
                "name": student_rec.name if student_rec else "",
                "attendance_rate": student_attendance_rate,
                "attendance_warning": attendance_warning,
            } if student_rec else None,
            "teacher_info": {
                "id": teacher_rec.id if teacher_rec else False,
                "name": teacher_rec.name if teacher_rec else "",
                "weekly_hours": round(total_teaching_hours, 1),
                "sessions_count": len([s for s in formatted_sessions if s["state"] != "cancelled"]),
            } if teacher_rec else None,
            "weekly_teaching_hours": round(total_teaching_hours, 1),
        }

    @api.model
    def get_schedule_view_data(self, start_date_str, end_date_str, filters=None):
        """
        Backward-compatible facade for frontend components (dashboard weekly panel,
        university schedule client action) with UI dropdown metadata and markers.
        """
        res = self.get_schedule(start_date_str, end_date_str, filters=filters, limit=500)
        if res.get("error"):
            return res

        # UI Filter Data for dropdowns
        subjects = self.env["university.subject"].search_read([], ["id", "name"], order="name asc")
        classrooms = self.env["university.classroom"].search_read(
            [], ["id", "name", "building", "capacity", "room_type"], order="name asc"
        )
        sections = self.env["university.class.section"].search_read([], ["id", "name"], order="name asc")
        teachers = self.env["university.teacher"].search_read(
            [], ["id", "name", "title", "position", "department_id", "email", "phone"], order="name asc"
        )
        faculties = self.env["university.faculty"].search_read([], ["id", "name"], order="name asc")
        programs = self.env["university.program"].search_read([], ["id", "name"], order="name asc")
        semesters = self.env["university.semester"].search_read([], ["id", "name", "date_start", "date_end", "is_active"], order="date_start desc, name asc")

        res["filters_data"] = {
            "subjects": subjects,
            "classrooms": classrooms,
            "sections": sections,
            "teachers": teachers,
            "faculties": faculties,
            "programs": programs,
            "semesters": semesters,
        }

        # Assignment & Exam Markers
        assignment_markers = []
        exam_markers = []
        start_date = fields.Date.from_string(start_date_str) if isinstance(start_date_str, str) else start_date_str
        end_date = fields.Date.from_string(end_date_str) if isinstance(end_date_str, str) else end_date_str

        sec_domain = []
        if res["role"] == "student" and res.get("student_info"):
            enrolled_secs = [s["section_id"] for s in res.get("sessions", []) if s.get("section_id")]
            if enrolled_secs:
                sec_domain = [("section_id", "in", list(set(enrolled_secs)))]
        elif res["role"] == "teacher" and res.get("teacher_info") and res["teacher_info"].get("id"):
            sec_domain = [("teacher_id", "=", res["teacher_info"]["id"])]

        if sec_domain or res["role"] == "admin":
            assg_domain = sec_domain + [
                ("due_date", ">=", start_date),
                ("due_date", "<=", end_date),
                ("state", "=", "approved"),
            ]
            assignments = self.env["university.assignment"].search(assg_domain, order="due_date asc")
            for a in assignments:
                assignment_markers.append({
                    "id": a.id,
                    "name": a.name,
                    "date_str": fields.Date.to_string(a.due_date),
                    "due_date": fields.Date.to_string(a.due_date),
                    "subject_name": a.subject_id.name or "",
                    "section_name": a.section_id.name or "",
                    "max_score": a.max_score,
                })

            exam_domain = sec_domain + [
                ("exam_date", ">=", start_date),
                ("exam_date", "<=", end_date),
                ("state", "in", ["confirmed", "running", "completed"]),
            ]
            exams = self.env["university.exam"].search(exam_domain, order="exam_date asc")
            for e in exams:
                exam_markers.append({
                    "id": e.id,
                    "name": e.name,
                    "date_str": fields.Date.to_string(e.exam_date),
                    "exam_type": e.exam_type,
                    "subject_name": e.subject_id.name or "",
                    "section_name": e.section_id.name or "",
                    "start_time_str": e.start_time.strftime("%H:%M") if e.start_time else "",
                    "end_time_str": e.end_time.strftime("%H:%M") if e.end_time else "",
                })

        res["assignment_markers"] = assignment_markers
        res["exam_markers"] = exam_markers
        return res


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def _filter_visible_menus(self):
        res = super()._filter_visible_menus()
        user = self.env.user
        # Remove "My Timetable" from Admin Schedule menu
        if user.has_group("school_management.group_school_admin") or self.env.is_system():
            my_timetable = self.env.ref("school_management.menu_university_timetable_teacher", raise_if_not_found=False)
            if my_timetable and my_timetable in res:
                res = res - my_timetable
        return res
