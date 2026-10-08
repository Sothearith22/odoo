import logging
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PublicHoliday(models.Model):
    _name = "public.holiday"
    _description = "Public Holiday"
    _order = "date_from desc, name asc"

    name = fields.Char(string="Holiday Name", required=True, index=True)
    name_km = fields.Char(string="Khmer Name")
    date_from = fields.Date(string="From Date", required=True, index=True)
    date_to = fields.Date(string="To Date", required=True, index=True)
    holiday_type = fields.Selection(
        [
            ("fixed", "Fixed"),
            ("lunar", "Lunar"),
            ("special", "Special"),
        ],
        string="Holiday Type",
        default="fixed",
        required=True,
        index=True,
    )
    academic_year_id = fields.Many2one(
        "university.academic.year",
        string="Academic Year",
        index=True,
    )
    affects_classes = fields.Boolean(
        string="Affects Classes",
        default=True,
        help="If set, class sessions should not be scheduled during this holiday.",
    )
    active = fields.Boolean(string="Active", default=True)
    note = fields.Text(string="Note")

    session_count = fields.Integer(
        string="Affected Sessions",
        compute="_compute_session_count",
        search="_search_session_count",
    )

    def _search_session_count(self, operator, value):
        holidays_with_sessions = []
        for h in self.search([]):
            if h.session_count > 0:
                holidays_with_sessions.append(h.id)
        if (operator in (">", "!=") and value == 0) or (operator == ">=" and value == 1):
            return [("id", "in", holidays_with_sessions)]
        return [("id", "not in", holidays_with_sessions)]

    # -------------------------------------------------------------------------
    # COMPUTES & ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("date_from")
    def _onchange_date_from(self):
        if self.date_from and (not self.date_to or self.date_to < self.date_from):
            self.date_to = self.date_from

    @api.onchange("date_from", "date_to")
    def _onchange_dates_warning(self):
        if self.date_from and self.date_to:
            dt_start = datetime.combine(self.date_from, datetime.min.time())
            dt_end = datetime.combine(self.date_to, datetime.max.time())
            count = self.env["university.timetable.slot"].search_count([
                ("state", "!=", "cancelled"),
                ("start_time", "<=", dt_end),
                ("end_time", ">=", dt_start),
            ])
            if count > 0:
                return {
                    "warning": {
                        "title": _("Timetable Conflict Warning"),
                        "message": _(
                            "There are %d active timetable sessions scheduled within this holiday date range (%s to %s)."
                        ) % (count, self.date_from, self.date_to),
                    }
                }

    @api.depends("date_from", "date_to")
    def _compute_session_count(self):
        Slot = self.env["university.timetable.slot"]
        for holiday in self:
            if not holiday.date_from or not holiday.date_to:
                holiday.session_count = 0
                continue
            dt_start = datetime.combine(holiday.date_from, datetime.min.time())
            dt_end = datetime.combine(holiday.date_to, datetime.max.time())
            holiday.session_count = Slot.search_count([
                ("state", "!=", "cancelled"),
                ("start_time", "<=", dt_end),
                ("end_time", ">=", dt_start),
            ])

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("date_from", "date_to")
    def _check_dates_order(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(
                    _("Holiday '%s': End date (%s) cannot be earlier than start date (%s).")
                    % (rec.name, rec.date_to, rec.date_from)
                )

    @api.constrains("name", "date_from", "date_to", "active")
    def _check_overlapping_duplicates(self):
        for rec in self:
            if not rec.active or not rec.date_from or not rec.date_to or not rec.name:
                continue
            name_clean = rec.name.strip().lower()
            duplicates = self.search([
                ("id", "!=", rec.id),
                ("active", "=", True),
                ("date_from", "<=", rec.date_to),
                ("date_to", ">=", rec.date_from),
            ])
            for dup in duplicates:
                if dup.name and dup.name.strip().lower() == name_clean:
                    raise ValidationError(
                        _(
                            "Overlapping holiday with name '%(name)s' already exists for dates %(date_from)s to %(date_to)s."
                        )
                        % {
                            "name": rec.name,
                            "date_from": dup.date_from,
                            "date_to": dup.date_to,
                        }
                    )

    # -------------------------------------------------------------------------
    # ORM LIFECYCLE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("date_from") and not vals.get("date_to"):
                vals["date_to"] = vals["date_from"]
            if not vals.get("academic_year_id") and vals.get("date_from"):
                target_d = fields.Date.to_date(vals["date_from"])
                ay = self.env["university.academic.year"].search([
                    ("date_start", "<=", target_d),
                    ("date_end", ">=", target_d),
                ], limit=1)
                if ay:
                    vals["academic_year_id"] = ay.id
        holidays = super().create(vals_list)
        for h in holidays:
            if h.session_count > 0:
                _logger.warning("Created holiday '%s' affects %d sessions.", h.name, h.session_count)
        return holidays

    def write(self, vals):
        if "date_from" in vals and "date_to" not in vals:
            for rec in self:
                if not rec.date_to or rec.date_to < fields.Date.to_date(vals["date_from"]):
                    vals["date_to"] = vals["date_from"]
        res = super().write(vals)
        for h in self:
            if h.session_count > 0:
                _logger.warning("Holiday '%s' affects %d sessions.", h.name, h.session_count)
        return res

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_view_affected_sessions(self):
        self.ensure_one()
        dt_start = datetime.combine(self.date_from or fields.Date.today(), datetime.min.time())
        dt_end = datetime.combine(self.date_to or fields.Date.today(), datetime.max.time())
        slots = self.env["university.timetable.slot"].search([
            ("start_time", "<=", dt_end),
            ("end_time", ">=", dt_start),
        ])
        return {
            "name": _("Affected Sessions: %s") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "university.timetable.slot",
            "view_mode": "list,form,calendar",
            "domain": [("id", "in", slots.ids)],
            "context": {"default_state": "scheduled"},
        }

    def action_cancel_affected_sessions(self):
        self.ensure_one()
        if not self.date_from or not self.date_to:
            return
        dt_start = datetime.combine(self.date_from, datetime.min.time())
        dt_end = datetime.combine(self.date_to, datetime.max.time())
        slots = self.env["university.timetable.slot"].search([
            ("state", "!=", "cancelled"),
            ("start_time", "<=", dt_end),
            ("end_time", ">=", dt_start),
        ])
        count = len(slots)
        if count > 0:
            slots.write({
                "state": "cancelled",
            })
            if hasattr(slots, "cancel_reason"):
                slots.write({"cancel_reason": f"Public Holiday: {self.name}"})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sessions Cancelled"),
                "message": _("%d timetable sessions have been cancelled.") % count,
                "type": "warning" if count > 0 else "info",
                "sticky": False,
            },
        }


class UniversityHoliday(models.Model):
    _inherit = "university.holiday"
    _order = "date_from desc, date_start desc, name asc"

    date_from = fields.Date(
        string="From Date",
        index=True,
    )
    date_to = fields.Date(
        string="To Date",
        index=True,
    )
    year = fields.Integer(
        string="Year",
        compute="_compute_year",
        store=True,
        index=True,
    )
    number_of_days = fields.Integer(
        string="Number of Days",
        compute="_compute_number_of_days",
        store=True,
    )
    holiday_type = fields.Selection(
        [
            ("public", "Public Holiday"),
            ("school_break", "School Break"),
            ("exam_break", "Exam Break"),
        ],
        string="Holiday Type",
        default="public",
        required=True,
        index=True,
    )
    applies_to = fields.Selection(
        [
            ("all", "All (University-Wide)"),
            ("faculty", "Selected Faculties"),
            ("department", "Selected Departments"),
            ("program", "Selected Programs"),
        ],
        string="Applies To",
        default="all",
        required=True,
    )
    faculty_ids = fields.Many2many(
        "university.faculty",
        "university_holiday_faculty_rel",
        "holiday_id",
        "faculty_id",
        string="Faculties",
    )
    department_ids = fields.Many2many(
        "university.department",
        "university_holiday_dept_rel",
        "holiday_id",
        "department_id",
        string="Departments",
    )
    program_ids = fields.Many2many(
        "university.program",
        "university_holiday_program_rel",
        "holiday_id",
        "program_id",
        string="Programs",
    )
    work_pay_multiplier = fields.Float(
        string="Work Pay Multiplier",
        default=2.0,
        help="Pay rate for staff who work on this holiday (Labour Law Art. 164: double pay).",
    )
    note = fields.Text(string="Note")
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    import_batch_id = fields.Many2one(
        "school.holiday.import.log",
        string="Import Batch",
        ondelete="set null",
        index=True,
    )
    conflict_count = fields.Integer(
        string="Class Conflicts",
        compute="_compute_conflict_count",
        search="_search_conflict_count",
    )

    def _search_conflict_count(self, operator, value):
        holidays_with_conflicts = []
        for h in self.search([]):
            if h.conflict_count > 0:
                holidays_with_conflicts.append(h.id)
        if (operator in (">", "!=") and value == 0) or (operator == ">=" and value == 1):
            return [("id", "in", holidays_with_conflicts)]
        return [("id", "not in", holidays_with_conflicts)]

    # -------------------------------------------------------------------------
    # COMPUTES & ONCHANGE
    # -------------------------------------------------------------------------
    @api.depends("date_from", "date_start")
    def _compute_year(self):
        for rec in self:
            d = rec.date_from or rec.date_start
            rec.year = d.year if d else 0

    @api.depends("date_from", "date_to", "date_start", "date_end")
    def _compute_number_of_days(self):
        for rec in self:
            d_from = rec.date_from or rec.date_start
            d_to = rec.date_to or rec.date_end
            if d_from and d_to:
                rec.number_of_days = max(0, (d_to - d_from).days + 1)
            else:
                rec.number_of_days = 0

    @api.onchange("date_from")
    def _onchange_date_from(self):
        if self.date_from and (not self.date_to or self.date_to < self.date_from):
            self.date_to = self.date_from

    @api.depends("date_from", "date_to", "applies_to", "faculty_ids", "department_ids", "program_ids")
    def _compute_conflict_count(self):
        Slot = self.env["university.timetable.slot"]
        for holiday in self:
            d_from = holiday.date_from or holiday.date_start
            d_to = holiday.date_to or holiday.date_end
            if not d_from or not d_to:
                holiday.conflict_count = 0
                continue
            dt_start = datetime.combine(d_from, datetime.min.time())
            dt_end = datetime.combine(d_to, datetime.max.time())
            slots = Slot.search([
                ("state", "!=", "cancelled"),
                ("start_time", "<=", dt_end),
                ("end_time", ">=", dt_start),
            ])
            conflicting = slots.filtered(lambda s: holiday._applies_to_section(s.section_id))
            holiday.conflict_count = len(conflicting)

    # -------------------------------------------------------------------------
    # CONSTRAINTS & ORM LIFECYCLE
    # -------------------------------------------------------------------------
    @api.constrains("date_from", "date_to", "date_start", "date_end")
    def _check_date_order(self):
        for rec in self:
            d_from = rec.date_from or rec.date_start
            d_to = rec.date_to or rec.date_end
            if d_from and d_to and d_to < d_from:
                raise ValidationError(
                    _("Holiday '%s': End date (%s) cannot be before start date (%s).")
                    % (rec.name, d_to, d_from)
                )

    @api.constrains(
        "date_from",
        "date_to",
        "date_start",
        "date_end",
        "applies_to",
        "faculty_ids",
        "department_ids",
        "program_ids",
        "active",
        "company_id",
    )
    def _check_scope_overlap(self):
        for rec in self:
            if not rec.active:
                continue
            d_from = rec.date_from or rec.date_start
            d_to = rec.date_to or rec.date_end
            if not d_from or not d_to:
                continue
            candidates = self.search([
                ("id", "!=", rec.id),
                ("active", "=", True),
                ("company_id", "=", rec.company_id.id),
                ("date_start", "<=", d_to),
                ("date_end", ">=", d_from),
            ])
            for other in candidates:
                if rec._scopes_overlap(other):
                    o_from = other.date_from or other.date_start
                    o_to = other.date_to or other.date_end
                    raise ValidationError(
                        _(
                            "Holiday conflict: '%(new_name)s' (%(new_from)s to %(new_to)s) "
                            "overlaps with existing holiday '%(other_name)s' (%(other_from)s to %(other_to)s) "
                            "within the same scope."
                        )
                        % {
                            "new_name": rec.name,
                            "new_from": d_from,
                            "new_to": d_to,
                            "other_name": other.name,
                            "other_from": o_from,
                            "other_to": o_to,
                        }
                    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            d_from = vals.get("date_from") or vals.get("date_start")
            d_to = vals.get("date_to") or vals.get("date_end") or d_from
            if d_from:
                vals["date_start"] = d_from
                vals["date_from"] = d_from
            if d_to:
                vals["date_end"] = d_to
                vals["date_to"] = d_to

            # Auto-assign academic_year_id if missing to prevent validation errors
            if not vals.get("academic_year_id") and d_from:
                target_d = fields.Date.to_date(d_from)
                ay = self.env["university.academic.year"].search([
                    ("date_start", "<=", target_d),
                    ("date_end", ">=", target_d),
                ], limit=1)
                if not ay:
                    ay = self.env["university.academic.year"].search([], order="date_start desc", limit=1)
                if ay:
                    vals["academic_year_id"] = ay.id

        return super().create(vals_list)

    def write(self, vals):
        if "date_from" in vals and "date_start" not in vals:
            vals["date_start"] = vals["date_from"]
        elif "date_start" in vals and "date_from" not in vals:
            vals["date_from"] = vals["date_start"]

        if "date_to" in vals and "date_end" not in vals:
            vals["date_end"] = vals["date_to"]
        elif "date_end" in vals and "date_to" not in vals:
            vals["date_to"] = vals["date_end"]

        return super().write(vals)

    def init(self):
        super().init()
        # Backfill date_from / date_to for existing records
        self.env.cr.execute("""
            UPDATE university_holiday
            SET date_from = date_start
            WHERE date_from IS NULL AND date_start IS NOT NULL;
            UPDATE university_holiday
            SET date_to = date_end
            WHERE date_to IS NULL AND date_end IS NOT NULL;
        """)

    # -------------------------------------------------------------------------
    # SCOPE MATCHING LOGIC
    # -------------------------------------------------------------------------
    def _scopes_overlap(self, other):
        self.ensure_one()
        if self.applies_to == "all" or other.applies_to == "all":
            return True

        s_fac = set(self.faculty_ids.ids)
        if self.faculty_id:
            s_fac.add(self.faculty_id.id)
        o_fac = set(other.faculty_ids.ids)
        if other.faculty_id:
            o_fac.add(other.faculty_id.id)

        s_dept = set(self.department_ids.ids)
        o_dept = set(other.department_ids.ids)

        s_prog = set(self.program_ids.ids)
        o_prog = set(other.program_ids.ids)

        if self.applies_to == "faculty" and other.applies_to == "faculty":
            return bool(s_fac & o_fac)
        if self.applies_to == "department" and other.applies_to == "department":
            return bool(s_dept & o_dept)
        if self.applies_to == "program" and other.applies_to == "program":
            return bool(s_prog & o_prog)

        if self.applies_to == "faculty" and other.applies_to == "department":
            o_dept_facs = {d.faculty_id.id for d in other.department_ids if d.faculty_id}
            return bool(s_fac & o_dept_facs)
        if self.applies_to == "department" and other.applies_to == "faculty":
            s_dept_facs = {d.faculty_id.id for d in self.department_ids if d.faculty_id}
            return bool(s_dept_facs & o_fac)

        if self.applies_to == "faculty" and other.applies_to == "program":
            o_prog_facs = {
                (p.faculty_id.id or (p.department_id and p.department_id.faculty_id.id))
                for p in other.program_ids
            }
            return bool(s_fac & o_prog_facs)
        if self.applies_to == "program" and other.applies_to == "faculty":
            s_prog_facs = {
                (p.faculty_id.id or (p.department_id and p.department_id.faculty_id.id))
                for p in self.program_ids
            }
            return bool(s_prog_facs & o_fac)

        if self.applies_to == "department" and other.applies_to == "program":
            o_prog_depts = {p.department_id.id for p in other.program_ids if p.department_id}
            return bool(s_dept & o_prog_depts)
        if self.applies_to == "program" and other.applies_to == "department":
            s_prog_depts = {p.department_id.id for p in self.program_ids if p.department_id}
            return bool(s_prog_depts & o_dept)

        return False

    def _applies_to_section(self, section):
        self.ensure_one()
        if self.applies_to == "all":
            return True
        if not section:
            return True

        if self.applies_to == "faculty":
            sec_faculty = (
                (section.department_id and section.department_id.faculty_id)
                or (section.program_id and section.program_id.faculty_id)
                or (section.program_id and section.program_id.department_id and section.program_id.department_id.faculty_id)
            )
            valid_facs = self.faculty_ids
            if self.faculty_id:
                valid_facs |= self.faculty_id
            return bool(sec_faculty and sec_faculty in valid_facs)

        elif self.applies_to == "department":
            sec_dept = section.department_id or (section.program_id and section.program_id.department_id)
            return bool(sec_dept and sec_dept in self.department_ids)

        elif self.applies_to == "program":
            return bool(section.program_id and section.program_id in self.program_ids)

        return True

    # -------------------------------------------------------------------------
    # PUBLIC HELPER METHODS
    # -------------------------------------------------------------------------
    @api.model
    def is_holiday(self, day, section=None, company=None):
        """Check if a date is a public holiday respecting applies_to scoping."""
        if not day:
            return False
        day_date = fields.Date.to_date(day)
        company = company or self.env.company
        holidays = self.search([
            ("company_id", "in", [False, company.id]),
            ("active", "=", True),
            ("date_start", "<=", day_date),
            ("date_end", ">=", day_date),
        ])
        if not holidays:
            return False
        if not section:
            return bool(holidays)
        for h in holidays:
            if h._applies_to_section(section):
                return True
        return False

    @api.model
    def get_holiday_dates(self, date_from, date_to, section=None, company=None):
        """Return a set of dates between date_from and date_to that are holidays."""
        d_start = fields.Date.to_date(date_from)
        d_end = fields.Date.to_date(date_to)
        if not d_start or not d_end or d_start > d_end:
            return set()
        company = company or self.env.company
        holidays = self.search([
            ("company_id", "in", [False, company.id]),
            ("active", "=", True),
            ("date_start", "<=", d_end),
            ("date_end", ">=", d_start),
        ])
        matching_days = set()
        for h in holidays:
            if section and not h._applies_to_section(section):
                continue
            cur = max(h.date_from or h.date_start, d_start)
            h_end = min(h.date_to or h.date_end, d_end)
            while cur <= h_end:
                matching_days.add(cur)
                cur += timedelta(days=1)
        return matching_days

    # -------------------------------------------------------------------------
    # SMART BUTTON ACTIONS
    # -------------------------------------------------------------------------
    def action_view_conflicts(self):
        self.ensure_one()
        d_from = self.date_from or self.date_start
        d_to = self.date_to or self.date_end
        dt_start = datetime.combine(d_from, datetime.min.time())
        dt_end = datetime.combine(d_to, datetime.max.time())
        slots = self.env["university.timetable.slot"].search([
            ("state", "!=", "cancelled"),
            ("start_time", "<=", dt_end),
            ("end_time", ">=", dt_start),
        ])
        conflicting_slots = slots.filtered(lambda s: self._applies_to_section(s.section_id))
        return {
            "name": _("Class Conflicts for %s") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "university.timetable.slot",
            "view_mode": "list,form,calendar",
            "domain": [("id", "in", conflicting_slots.ids)],
            "context": {
                "search_default_group_by_section": 1,
                "default_holiday_id": self.id,
            },
        }

    @api.constrains("date_start", "date_end", "academic_year_id")
    def _check_dates_within_year(self):
        for holiday in self:
            if holiday.holiday_type == "public":
                continue
            year = holiday.academic_year_id
            if not year:
                continue
            d_start = holiday.date_from or holiday.date_start
            d_end = holiday.date_to or holiday.date_end
            if not d_start or not d_end:
                continue
            if d_start < year.date_start or d_end > year.date_end:
                raise ValidationError(
                    _("Holiday dates must fall within the selected academic year.")
                )
