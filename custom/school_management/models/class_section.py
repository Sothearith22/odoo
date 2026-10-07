from odoo import api, fields, models
from odoo.exceptions import ValidationError


class UniversityClassSection(models.Model):
    _name = "university.class.section"
    _description = "Class Section"

    name = fields.Char(string="Section Name", required=True)
    section_type = fields.Selection(
        [
            ("cohort", "Cohort"),
            ("course", "Course"),
        ],
        string="Section Type",
        default="cohort",
        help="Cohort sections are program/year groups. Course sections are subject-based classes.",
    )
    program_id = fields.Many2one(
        "university.program",
        string="Major / Level",
        help="Optional: link the section to a major/program (program-level "
             "cohort sections such as 'GM-Y1-A'). Preferred over Subject for "
             "the main major enrollment flow.",
    )
    subject_id = fields.Many2one(
        "university.subject",
        string="Subject",
        domain="[('program_ids', 'in', [program_id])]",
        help="Legacy: set for subject-based class sections. Leave empty for "
             "program-level cohort sections.",
    )
    teacher_id = fields.Many2one(
        "university.teacher",
        string="Instructor",
        help="Legacy: instructor for subject-based class sections.",
    )
    semester_id = fields.Many2one(
        "university.semester", string="Semester / Term", required=True
    )
    academic_year_id = fields.Many2one(
        "university.academic.year",
        string="Academic Year",
        related="semester_id.academic_year_id",
        store=True,
        readonly=True,
    )
    department_id = fields.Many2one(
        "university.department",
        string="Department",
        related="program_id.department_id",
        store=True,
        readonly=True,
    )
    classroom_id = fields.Many2one(
        "university.classroom", string="Classroom"
    )
    capacity = fields.Integer(string="Max Capacity", default=30)
    enrollment_ids = fields.One2many(
        "university.enrollment", "section_id", string="Enrolled Students"
    )
    slot_ids = fields.One2many(
        "university.timetable.slot", "section_id", string="Timetable Slots"
    )
    slot_count = fields.Integer(
        string="Sessions Count",
        compute="_compute_slot_count",
    )
    active = fields.Boolean(string="Active", default=True)
    auto_quiz_per_session = fields.Boolean(
        string="Auto-Quiz per Session",
        default=False,
        help="If enabled, the system automatically creates a quiz when a timetable session starts.",
    )
    enrolled_student_count = fields.Integer(
        string="Enrolled Count",
        compute="_compute_enrolled_student_count",
        store=True,
    )
    available_seats = fields.Integer(
        string="Available Seats",
        compute="_compute_capacity_status",
        store=True,
    )
    has_available_seats = fields.Boolean(
        string="Has Available Seats",
        compute="_compute_capacity_status",
        store=True,
    )
    capacity_used_percent = fields.Integer(
        string="Capacity Used",
        compute="_compute_capacity_status",
        store=True,
    )
    is_full = fields.Boolean(
        string="Full",
        compute="_compute_capacity_status",
        store=True,
    )
    day_summary = fields.Char(
        string="Days",
        compute="_compute_schedule_summary",
    )
    time_summary = fields.Char(
        string="Time",
        compute="_compute_schedule_summary",
    )
    schedule_summary = fields.Char(
        string="Schedule Summary",
        compute="_compute_schedule_summary",
    )
    assignment_ids = fields.One2many(
        "university.assignment",
        "section_id",
        string="Assignments",
    )
    timeline = fields.Char(
        string="Timeline",
        compute="_compute_timeline",
    )
    state = fields.Selection(
        [
            ("draft", "New"),
            ("confirmed", "Confirmed"),
        ],
        string="Status",
        default="confirmed",
    )

    @api.depends("enrollment_ids", "enrollment_ids.status")
    def _compute_enrolled_student_count(self):
        for section in self:
            section.enrolled_student_count = len(
                section.enrollment_ids.filtered(lambda e: e.status == "enrolled")
            )

    @api.depends("capacity", "enrolled_student_count")
    def _compute_capacity_status(self):
        for section in self:
            if section.capacity:
                section.capacity_used_percent = min(
                    100,
                    round(section.enrolled_student_count * 100 / section.capacity),
                )
                section.is_full = section.enrolled_student_count >= section.capacity
                section.available_seats = max(0, section.capacity - section.enrolled_student_count)
                section.has_available_seats = section.available_seats > 0
            else:
                section.capacity_used_percent = 0
                section.is_full = False
                section.available_seats = 0
                section.has_available_seats = False

    @api.depends("slot_ids")
    def _compute_slot_count(self):
        for section in self:
            section.slot_count = len(section.slot_ids)

    @api.depends("slot_ids.start_time", "slot_ids.end_time", "slot_ids.classroom_id")
    def _compute_schedule_summary(self):
        for section in self:
            if not section.slot_ids:
                section.schedule_summary = ""
                section.day_summary = ""
                section.time_summary = ""
                continue
            days = []
            times = []
            details = []
            slots = section.slot_ids.sorted(key=lambda s: s.start_time or fields.Datetime.now())
            for s in slots:
                if s.start_time:
                    slot_dt = fields.Datetime.context_timestamp(section, s.start_time)
                    day_name = slot_dt.strftime("%a")
                    if day_name not in days:
                        days.append(day_name)
                    time_range = slot_dt.strftime("%H:%M")
                    if s.end_time:
                        end_dt = fields.Datetime.context_timestamp(section, s.end_time)
                        time_range += f"-{end_dt.strftime('%H:%M')}"
                    if time_range not in times:
                        times.append(time_range)
                    room = f" ({s.classroom_id.name})" if s.classroom_id else ""
                    desc = f"{day_name} {time_range}{room}"
                    if desc not in details:
                        details.append(desc)
            section.day_summary = ", ".join(days)
            section.time_summary = ", ".join(times[:2])
            section.schedule_summary = "; ".join(details[:3]) + ("..." if len(details) > 3 else "")

    @api.constrains("capacity")
    def _check_capacity_positive(self):
        for section in self:
            if section.capacity is not None and section.capacity < 1:
                raise ValidationError(
                    "The class section capacity must be at least 1."
                )

    @api.constrains("program_id", "subject_id")
    def _check_has_program_or_subject(self):
        for section in self:
            if not section.program_id and not section.subject_id:
                raise ValidationError(
                    "A class section must be linked to a Major/Program or a Subject."
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("program_id") and not vals.get("subject_id"):
                raise ValidationError(
                    "A class section must be linked to a Major/Program or a Subject."
                )
            if not vals.get("section_type"):
                vals["section_type"] = "course" if vals.get("subject_id") else "cohort"
        return super().create(vals_list)

    def write(self, vals):
        if "program_id" in vals or "subject_id" in vals:
            for section in self:
                program_id = vals.get("program_id", section.program_id.id)
                subject_id = vals.get("subject_id", section.subject_id.id)
                if not program_id and not subject_id:
                    raise ValidationError(
                        "A class section must be linked to a Major/Program or a Subject."
                    )
        return super().write(vals)

    @api.constrains("teacher_id", "subject_id")
    def _check_teacher_subject(self):
        for section in self:
            if not section.subject_id or not section.teacher_id:
                continue
            if (
                section.subject_id.teacher_ids
                and section.teacher_id not in section.subject_id.teacher_ids
            ):
                raise ValidationError(
                    "The selected instructor is not assigned to teach this subject."
                )

    @api.constrains("program_id", "subject_id")
    def _check_program_subject(self):
        for section in self:
            if not section.program_id or not section.subject_id:
                continue
            subject = section.subject_id
            if subject.program_ids and section.program_id not in subject.program_ids:
                raise ValidationError(
                    "The selected subject does not belong to the chosen major/program."
                )
            if not subject.program_ids and subject.department_id != section.program_id.department_id:
                raise ValidationError(
                    "The selected subject does not belong to the chosen major/program."
                )

    @api.onchange("program_id")
    def _onchange_program_id(self):
        domain = [("program_ids", "in", [self.program_id.id])] if self.program_id else []
        if self.subject_id and self.program_id not in self.subject_id.program_ids:
            self.subject_id = False
            self.teacher_id = False
        return {"domain": {"subject_id": domain}}

    def action_view_enrolled_students(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Enrolled Students - {self.name}",
            "res_model": "university.enrollment",
            "view_mode": "list,form",
            "domain": [("section_id", "=", self.id)],
            "context": {"default_section_id": self.id},
        }

    @api.depends("semester_id.date_start", "semester_id.date_end")
    def _compute_timeline(self):
        for section in self:
            if section.semester_id and section.semester_id.date_start and section.semester_id.date_end:
                s_str = section.semester_id.date_start.strftime("%m/%d/%Y")
                e_str = section.semester_id.date_end.strftime("%m/%d/%Y")
                section.timeline = f"{s_str} - {e_str}"
            else:
                section.timeline = ""

    def action_confirm(self):
        self.write({"state": "confirmed"})

    def action_set_to_draft(self):
        self.write({"state": "draft"})

    def action_view_schedule(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "university_schedule_view",
            "name": f"Weekly Schedule - {self.name}",
            "context": {
                "default_section_id": self.id,
                "filters": {"section_id": str(self.id)},
            },
        }

    def action_open_bulk_enroll_wizard(self):
        self.ensure_one()
        program = self.program_id
        if not program and self.subject_id.program_ids:
            program = self.subject_id.program_ids[:1]

        return {
            "type": "ir.actions.act_window",
            "name": "Enroll Multiple Students",
            "res_model": "university.bulk.enrollment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_section_id": self.id,
                "default_program_id": program.id if program else False,
                "default_academic_year_id": self.semester_id.academic_year_id.id if self.semester_id and self.semester_id.academic_year_id else False,
                "default_semester_id": self.semester_id.id if self.semester_id else False,
            },
        }

    def action_open_populate_class_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Populate Class",
            "res_model": "university.populate.class.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_section_id": self.id},
        }

    def action_open_timetable_generation_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Generate Timetable",
            "res_model": "university.timetable.generation.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_academic_year_id": self.semester_id.academic_year_id.id if self.semester_id and self.semester_id.academic_year_id else False,
                "default_semester_id": self.semester_id.id if self.semester_id else False,
                "default_section_ids": [(6, 0, [self.id])],
            },
        }
