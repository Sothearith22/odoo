import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from .academic_lock import can_maintain_closed_year_records
from .semester import UniversitySemester

_logger = logging.getLogger(__name__)


def _is_academic_manager(env):
    return (
        env.user.has_group("school_management.group_academic_year_manager")
        or env.user.has_group("school_management.group_school_admin")
        or env.is_superuser()
    )


class UniversityAcademicYear(models.Model):
    _name = "university.academic.year"
    _description = "Academic Year"
    _order = "date_start desc, name desc, id desc"

    name = fields.Char(string="Academic Year", required=True)
    date_start = fields.Date(string="Start Date", required=True)
    date_end = fields.Date(string="End Date", required=True)
    semester_ids = fields.One2many(
        "university.semester", "academic_year_id", string="Semesters"
    )
    holiday_ids = fields.One2many(
        "university.holiday", "academic_year_id", string="Holidays"
    )
    semester_count = fields.Integer(
        string="Semester Count", compute="_compute_semester_count"
    )
    current = fields.Boolean(string="Current Academic Year", default=False)
    active = fields.Boolean(string="Active", default=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("open", "Registration Open"),
            ("running", "Running"),
            ("closed", "Closed"),
            ("archived", "Archived"),
        ],
        string="State",
        default="draft",
        required=True,
    )
    semester_status = fields.Selection(
        [
            ("configured", "With Semesters"),
            ("empty", "No Semesters"),
        ],
        string="Semester Status",
        compute="_compute_semester_status",
        store=True,
    )

    _unique_name = models.Constraint(
        "UNIQUE (name)", "The academic year name must be unique."
    )
    _valid_date_range = models.Constraint(
        "CHECK (date_end >= date_start)",
        "The academic year end date must be on or after the start date.",
    )
    _one_current_year = models.UniqueIndex(
        "(current) WHERE current",
        "Only one academic year can be marked as current.",
    )

    @api.depends("semester_ids", "semester_ids.active")
    def _compute_semester_count(self):
        for year in self:
            year.semester_count = len(
                year.with_context(active_test=False).semester_ids
            )

    @api.depends("semester_ids", "semester_ids.active")
    def _compute_semester_status(self):
        for year in self:
            count = len(year.with_context(active_test=False).semester_ids)
            year.semester_status = "configured" if count > 0 else "empty"

    def init(self):
        super().init()
        self.env.cr.execute("""
            UPDATE university_academic_year
            SET state = CASE
                WHEN current = TRUE AND state IN ('draft', NULL) THEN 'running'
                ELSE COALESCE(state, 'draft')
            END
            WHERE state IS NULL
        """)

    @api.constrains("date_start", "date_end")
    def _check_date_range(self):
        for year in self:
            semesters = year.with_context(active_test=False).semester_ids
            invalid_semester = semesters.filtered(
                lambda semester: (
                    semester.date_start
                    and semester.date_end
                    and (
                        semester.date_start < year.date_start
                        or semester.date_end > year.date_end
                    )
                )
            )[:1]
            if invalid_semester:
                raise ValidationError(
                    "Academic year dates must include all of its semester dates."
                )

    def write(self, vals):
        if not can_maintain_closed_year_records(self.env):
            closed_years = self.filtered(lambda y: y.state in ("closed", "archived"))
            if closed_years:
                is_reopening = set(vals.keys()) <= {"state"} and vals.get("state") in ("draft", "open", "running")
                if is_reopening:
                    if not _is_academic_manager(self.env):
                        raise UserError("Only an academic manager can reopen a closed or archived academic year.")
                else:
                    raise UserError("Closed and archived academic years are read-only and cannot be modified.")

        if vals.get("current"):
            other_current = self.with_context(active_test=False).search([
                ("id", "not in", self.ids),
                ("current", "=", True),
            ])
            if other_current:
                other_current.write({"current": False})
                self.env.flush_all()
            if "state" not in vals:
                for year in self:
                    if year.state == "draft":
                        vals["state"] = "running"
                        break

        return super().write(vals)

    def unlink(self):
        if not can_maintain_closed_year_records(self.env):
            if any(year.state in ("closed", "archived") for year in self):
                raise UserError("Closed and archived academic years cannot be deleted.")
        return super().unlink()

    def action_open_registration(self):
        self.ensure_one()
        return self.write({"state": "open"})

    def action_start_year(self):
        self.ensure_one()
        return self.write({"state": "running"})

    def action_close_year(self):
        self.ensure_one()
        return self.write({"state": "closed"})

    def action_archive_year(self):
        self.ensure_one()
        return self.write({"state": "archived"})

    def action_reset_draft(self):
        self.ensure_one()
        if not _is_academic_manager(self.env):
            raise UserError("Only an academic manager can reset an academic year to draft.")
        return self.with_context(allow_closed_year_write=True).write({"state": "draft"})

    def action_open_rollover(self):
        self.ensure_one()
        if self.state not in ("running", "closed"):
            raise ValidationError(
                "Rollover is available only for running or closed academic years."
            )
        return {
            "type": "ir.actions.act_window",
            "res_model": "university.year.rollover.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_source_year_id": self.id},
        }
