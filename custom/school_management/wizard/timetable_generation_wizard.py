from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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
                raise ValidationError("Generate between 1 and 20 weeks at a time.")

    def action_generate_timetable(self):
        self.ensure_one()
        if self.semester_id.academic_year_id != self.academic_year_id:
            raise UserError("The semester must belong to the selected academic year.")
        if not self.section_ids:
            raise UserError("Select at least one class section.")
        if not self.timeslot_ids:
            raise UserError("Select at least one timeslot.")

        created = self.env["university.timetable.slot"]
        skipped = []
        week_start = fields.Date.to_date(self.start_date)
        if week_start.weekday() != 0:
            week_start = week_start - timedelta(days=week_start.weekday())

        slots = self.timeslot_ids.sorted(lambda item: (item.day_of_week, item.start_hour))
        slot_index = 0
        for section in self.section_ids:
            subjects = section.subject_id or section.program_id.subject_ids
            if not subjects:
                skipped.append("%s has no subjects" % section.display_name)
                continue
            for subject in subjects:
                teacher = section.teacher_id or subject.teacher_ids[:1]
                if not teacher:
                    skipped.append("%s / %s has no teacher" % (section.display_name, subject.display_name))
                    continue
                for week in range(self.week_count):
                    timeslot = slots[slot_index % len(slots)]
                    slot_index += 1
                    start_time, end_time = timeslot._datetime_for_week(week_start, week)
                    vals = {
                        "teacher_id": teacher.id,
                        "section_id": section.id,
                        "subject_id": subject.id,
                        "classroom_id": section.classroom_id.id,
                        "timeslot_id": timeslot.id,
                        "location": section.classroom_id.name,
                        "start_time": fields.Datetime.to_string(start_time),
                        "end_time": fields.Datetime.to_string(end_time),
                        "generation_state": "draft",
                    }
                    try:
                        created |= self.env["university.timetable.slot"].create(vals)
                    except ValidationError as exc:
                        skipped.append("%s / %s: %s" % (section.display_name, subject.display_name, exc.args[0]))

        if not created and skipped:
            raise UserError("No timetable slots were generated:\n%s" % "\n".join(skipped[:10]))

        message = "%s timetable slot(s) generated." % len(created)
        if skipped:
            message += " %s item(s) skipped due to missing data or conflicts." % len(skipped)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Timetable Generated",
                "message": message,
                "type": "success" if created else "warning",
                "sticky": bool(skipped),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
