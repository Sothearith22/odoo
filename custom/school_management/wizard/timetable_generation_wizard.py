import logging
from datetime import datetime, time, timedelta
import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UniversityTimetableGenerationWizard(models.TransientModel):
    _name = "university.timetable.generation.wizard"
    _description = "Timetable Generation Wizard"

    academic_year_id = fields.Many2one(
        "university.academic.year",
        string="Academic Year",
        required=True,
        domain="[('active', '=', True)]",
    )
    semester_id = fields.Many2one(
        "university.semester",
        string="Semester",
        required=True,
        domain="[('active', '=', True), ('academic_year_id', '=', academic_year_id)]",
    )
    section_ids = fields.Many2many(
        "university.class.section",
        "university_timetable_generation_section_rel",
        "wizard_id",
        "section_id",
        string="Class Sections",
        domain="[('active', '=', True), ('semester_id', '=', semester_id)]",
    )
    timeslot_ids = fields.Many2many(
        "university.timeslot",
        "university_timetable_generation_timeslot_rel",
        "wizard_id",
        "timeslot_id",
        string="Timeslots",
        domain="[('active', '=', True)]",
    )
    start_date = fields.Date(
        string="Week Start Date",
        default=fields.Date.context_today,
        required=True,
    )
    week_count = fields.Integer(string="Weeks", default=1, required=True)
    sessions_per_week = fields.Integer(
        string="Sessions per Week",
        default=1,
        required=True,
        help="Number of distinct timeslots each subject receives per week.",
    )
    replace_existing_drafts = fields.Boolean(
        string="Replace Existing Drafts",
        default=False,
        help="Delete existing draft timetable slots for selected sections within the generated date range.",
    )

    @api.onchange("academic_year_id")
    def _onchange_academic_year_id(self):
        if (
            self.semester_id
            and self.academic_year_id
            and self.semester_id.academic_year_id != self.academic_year_id
        ):
            self.semester_id = False
        self.section_ids = False

    @api.onchange("semester_id")
    def _onchange_semester_id(self):
        self.section_ids = False
        if self.semester_id and not self.academic_year_id:
            self.academic_year_id = self.semester_id.academic_year_id

    @api.constrains("week_count")
    def _check_week_count(self):
        for wizard in self:
            if wizard.week_count < 1 or wizard.week_count > 20:
                raise ValidationError(_("Generate between 1 and 20 weeks at a time."))

    @api.constrains("sessions_per_week", "timeslot_ids")
    def _check_sessions_per_week(self):
        for wizard in self:
            if wizard.sessions_per_week < 1:
                raise ValidationError(_("Sessions per week must be at least 1."))
            if wizard.timeslot_ids and wizard.sessions_per_week > len(wizard.timeslot_ids):
                raise ValidationError(
                    _("Sessions per week (%(sessions)d) cannot exceed the number of selected timeslots (%(slots)d).")
                    % {"sessions": wizard.sessions_per_week, "slots": len(wizard.timeslot_ids)}
                )

    def _find_holiday(self, target_date, holidays, section=None):
        if not holidays:
            return None
        faculty = (
            section.program_id.department_id.faculty_id
            if section and section.program_id and section.program_id.department_id
            else False
        )
        for h in holidays:
            if h.date_start <= target_date <= h.date_end:
                if not h.faculty_id or (faculty and h.faculty_id == faculty):
                    return h
        return None

    def _create_series(self, base_vals, timeslot, monday, holidays=None, section=None, subject=None):
        Slot = self.env["university.timetable.slot"]
        try:
            with self.env.cr.savepoint():
                records = Slot
                holiday_skips = []
                for week in range(self.week_count):
                    target_date = monday + timedelta(days=int(timeslot.day_of_week) + week * 7)
                    holiday = self._find_holiday(target_date, holidays, section)
                    if holiday:
                        subj_name = subject.display_name if subject else "Session"
                        sec_name = section.display_name if section else ""
                        holiday_skips.append(
                            f"{sec_name} / {subj_name} on {target_date} skipped (Holiday: {holiday.name})"
                        )
                        continue
                    start, end = timeslot._datetime_for_week(monday, week)
                    records |= Slot.create(dict(
                        base_vals,
                        timeslot_id=timeslot.id,
                        start_time=start,
                        end_time=end,
                    ))
                return records, None, holiday_skips
        except ValidationError as exc:
            return Slot, exc.args[0], []

    def action_generate_timetable(self):
        self.ensure_one()
        if self.semester_id.academic_year_id != self.academic_year_id:
            raise UserError(_("The semester must belong to the selected academic year."))
        if not self.section_ids:
            raise UserError(_("Select at least one class section."))
        if not self.timeslot_ids:
            raise UserError(_("Select at least one timeslot."))

        created = self.env["university.timetable.slot"]
        skipped = []
        week_start = fields.Date.to_date(self.start_date)
        monday = week_start - timedelta(days=week_start.weekday())

        user_tz = pytz.timezone(self.env.user.tz or "UTC")
        if self.replace_existing_drafts:
            dt_start = user_tz.localize(datetime.combine(monday, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
            dt_end = user_tz.localize(datetime.combine(monday + timedelta(days=self.week_count * 7), time.min)).astimezone(pytz.utc).replace(tzinfo=None)
            existing_drafts = self.env["university.timetable.slot"].search([
                ("section_id", "in", self.section_ids.ids),
                ("generation_state", "=", "draft"),
                ("start_time", ">=", dt_start),
                ("start_time", "<", dt_end),
            ])
            if existing_drafts:
                existing_drafts.unlink()

        holidays = self.env["university.holiday"].search([
            ("academic_year_id", "=", self.academic_year_id.id),
        ])

        slots = self.timeslot_ids.sorted(lambda item: (item.day_of_week, item.start_hour))
        for section in self.section_ids:
            slot_index = 0
            subjects = section.subject_id or section.program_id.subject_ids
            if not subjects:
                skipped.append("%s has no subjects" % section.display_name)
                continue
            for subject in subjects:
                teacher = section.teacher_id or subject.teacher_ids[:1]
                if not teacher:
                    skipped.append("%s / %s has no teacher" % (section.display_name, subject.display_name))
                    continue

                base_vals = {
                    "teacher_id": teacher.id,
                    "section_id": section.id,
                    "subject_id": subject.id,
                    "classroom_id": section.classroom_id.id,
                    "location": section.classroom_id.name,
                    "generation_state": "draft",
                }

                chosen_slots = self.env["university.timeslot"]
                for session_num in range(self.sessions_per_week):
                    for offset in range(len(slots)):
                        candidate_slot = slots[(slot_index + offset) % len(slots)]
                        if candidate_slot in chosen_slots:
                            continue
                        records, err, holiday_skips = self._create_series(
                            base_vals, candidate_slot, monday,
                            holidays=holidays, section=section, subject=subject
                        )
                        if not err:
                            created |= records
                            chosen_slots |= candidate_slot
                            slot_index += offset + 1
                            skipped.extend(holiday_skips)
                            break
                    else:
                        session_label = (
                            f" (session {session_num + 1}/{self.sessions_per_week})"
                            if self.sessions_per_week > 1
                            else ""
                        )
                        skipped.append(
                            "%s / %s%s: No conflict-free timeslot available."
                            % (section.display_name, subject.display_name, session_label)
                        )

        if not created and skipped:
            raise UserError(_("No timetable slots were generated:\n%s") % "\n".join(skipped[:10]))

        if skipped:
            for item in skipped:
                _logger.warning("Timetable generation skipped: %s", item)

        return {
            "type": "ir.actions.act_window",
            "name": "Generated Timetable",
            "res_model": "university.timetable.slot",
            "view_mode": "calendar,list,form",
            "domain": [("id", "in", created.ids)],
            "context": {"default_mode": "week"},
        }
