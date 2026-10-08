import base64
import io
import logging
import math

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from .academic_lock import can_maintain_closed_year_records

_logger = logging.getLogger(__name__)


class UniversitySemester(models.Model):
    _name = "university.semester"
    _description = "Semester"
    _order = "academic_year_id desc, date_start, id"

    EXPECTED_SEMESTER_WEEKS = 16
    MIN_SEMESTER_WEEKS = 4
    SOFT_WARNING_TOLERANCE_WEEKS = 4
    SOFT_WARNING_MIN_WEEKS = EXPECTED_SEMESTER_WEEKS - SOFT_WARNING_TOLERANCE_WEEKS
    SOFT_WARNING_MAX_WEEKS = EXPECTED_SEMESTER_WEEKS + SOFT_WARNING_TOLERANCE_WEEKS

    _date_range_constraint = models.Constraint(
        "CHECK (date_end >= date_start)",
        "The semester end date must be on or after the start date.",
    )
    _academic_year_name_uniq = models.Constraint(
        "UNIQUE(academic_year_id, name)",
        "A term with this name already exists in this academic session.",
    )

    name = fields.Char(string="Semester Name", required=True)
    academic_year_id = fields.Many2one(
        "university.academic.year",
        string="Academic Year",
        required=True,
        ondelete="cascade",
        index=True,
    )
    session_id = fields.Many2one(
        "university.academic.year",
        string="Session",
        related="academic_year_id",
        store=True,
        readonly=False,
        index=True,
    )
    semester_type = fields.Selection(
        [
            ("semester_1", "Semester 1"),
            ("semester_2", "Semester 2"),
            ("summer", "Summer Semester"),
        ],
        string="Semester Type",
        default="semester_1",
        required=True,
    )
    date_start = fields.Date(string="Start Date", required=True)
    date_end = fields.Date(string="End Date", required=True)
    week_count = fields.Integer(
        string="Weeks",
        compute="_compute_week_count",
        store=True,
    )
    is_active = fields.Boolean(
        string="Active Period",
        compute="_compute_is_active",
        help="True when today's date falls within the semester start and end dates.",
    )
    semester_subject_ids = fields.One2many(
        "university.semester.subject", "semester_id", string="Offered Subjects"
    )
    department_term_ids = fields.One2many(
        "university.department.term",
        "semester_id",
        string="Department Schedule",
    )
    subject_count = fields.Integer(
        string="Subject Count", compute="_compute_subject_count"
    )
    active = fields.Boolean(string="Active", default=True)

    @api.depends("date_start", "date_end")
    def _compute_week_count(self):
        for semester in self:
            if semester.date_start and semester.date_end:
                days = (semester.date_end - semester.date_start).days + 1
                semester.week_count = max(0, math.ceil(days / 7.0))
            else:
                semester.week_count = 0

    def init(self):
        super().init()
        self.env.cr.execute("""
            UPDATE university_semester s
            SET date_start = COALESCE(s.date_start, y.date_start, CURRENT_DATE),
                date_end = COALESCE(s.date_end, y.date_end, CURRENT_DATE)
            FROM university_academic_year y
            WHERE s.academic_year_id = y.id
              AND (s.date_start IS NULL OR s.date_end IS NULL)
        """)
        self.env.cr.execute("""
            UPDATE university_semester
            SET session_id = academic_year_id
            WHERE session_id IS NULL AND academic_year_id IS NOT NULL
        """)

    @api.model_create_multi
    def create(self, vals_list):
        if not can_maintain_closed_year_records(self.env):
            year_ids = [vals.get("academic_year_id") or vals.get("session_id") for vals in vals_list if vals.get("academic_year_id") or vals.get("session_id")]
            if year_ids:
                years = self.env["university.academic.year"].browse(year_ids).exists()
                if any(y.state in ("closed", "archived") for y in years):
                    raise UserError("Cannot create semesters in a closed or archived academic year.")
        return super().create(vals_list)

    def write(self, vals):
        if not can_maintain_closed_year_records(self.env):
            if any(s.academic_year_id.state in ("closed", "archived") for s in self):
                raise UserError("Semesters of a closed or archived academic year are read-only and cannot be modified.")
            target_year_id = vals.get("academic_year_id") or vals.get("session_id")
            if target_year_id:
                destination_year = self.env["university.academic.year"].browse(
                    target_year_id
                ).exists()
                if destination_year.state in ("closed", "archived"):
                    raise UserError(
                        "Cannot move a semester into a closed or archived academic year."
                    )
        return super().write(vals)

    def unlink(self):
        if not can_maintain_closed_year_records(self.env):
            if any(s.academic_year_id.state in ("closed", "archived") for s in self):
                raise UserError("Cannot delete semesters of a closed or archived academic year.")
        return super().unlink()

    @api.depends("semester_subject_ids", "semester_subject_ids.active")
    def _compute_subject_count(self):
        for semester in self:
            semester.subject_count = len(
                semester.with_context(active_test=False).semester_subject_ids
            )

    @api.depends("date_start", "date_end")
    def _compute_is_active(self):
        today = fields.Date.context_today(self)
        for semester in self:
            if semester.date_start and semester.date_end:
                semester.is_active = semester.date_start <= today <= semester.date_end
            elif semester.date_start:
                semester.is_active = semester.date_start <= today
            elif semester.date_end:
                semester.is_active = today <= semester.date_end
            else:
                semester.is_active = True

    @api.constrains("date_start", "date_end")
    def _check_duration(self):
        for semester in self:
            if not semester.date_start or not semester.date_end:
                raise ValidationError("Semester start date and end date are required.")

            duration_days = (semester.date_end - semester.date_start).days
            if duration_days < 0:
                raise ValidationError(
                    "The semester end date must be on or after the start date."
                )

            minimum_days = self.MIN_SEMESTER_WEEKS * 7
            if duration_days < minimum_days:
                raise ValidationError(
                    "Semester '%s' must be at least %s weeks (%s days) long; "
                    "the configured duration is %s days (%s weeks)."
                    % (
                        semester.display_name,
                        self.MIN_SEMESTER_WEEKS,
                        minimum_days,
                        duration_days,
                        round(duration_days / 7.0, 2),
                    )
                )

            minimum_expected_days = self.SOFT_WARNING_MIN_WEEKS * 7
            maximum_expected_days = self.SOFT_WARNING_MAX_WEEKS * 7
            if (
                duration_days < minimum_expected_days
                or duration_days > maximum_expected_days
            ):
                _logger.warning(
                    "Semester duration review candidate: '%s' (id=%s) has "
                    "%s days (%.2f weeks), outside the expected %s-%s week range "
                    "around the %s-week standard.",
                    semester.display_name,
                    semester.id,
                    duration_days,
                    duration_days / 7.0,
                    self.SOFT_WARNING_MIN_WEEKS,
                    self.SOFT_WARNING_MAX_WEEKS,
                    self.EXPECTED_SEMESTER_WEEKS,
                )

    @api.constrains("date_start", "date_end", "academic_year_id")
    def _check_date_range(self):
        for semester in self:
            academic_year = semester.academic_year_id
            if not academic_year:
                raise ValidationError("A semester must belong to an academic year.")
            if not semester.date_start or not semester.date_end:
                continue
            if semester.date_start < academic_year.date_start:
                raise ValidationError(
                    "The semester start date cannot be before the selected academic year."
                )
            if semester.date_end > academic_year.date_end:
                raise ValidationError(
                    "The semester end date cannot be after the selected academic year."
                )

            invalid_term = semester.department_term_ids.filtered(
                lambda term: (
                    term.date_start
                    and term.date_end
                    and (
                        term.date_start < semester.date_start
                        or term.date_end > semester.date_end
                    )
                )
            )[:1]
            if invalid_term:
                raise ValidationError(
                    "Semester dates must include all department schedule dates."
                )

    @api.constrains("name", "academic_year_id")
    def _check_unique_name_per_academic_year(self):
        for semester in self:
            if not semester.name or not semester.academic_year_id:
                continue
            duplicate = self.search(
                [
                    ("id", "!=", semester.id),
                    ("name", "=", semester.name),
                    ("academic_year_id", "=", semester.academic_year_id.id),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    "The semester name '%s' is already used in academic year '%s'. "
                    "Choose a unique name for this academic year."
                    % (semester.name, semester.academic_year_id.name)
                )

    def action_generate_department_terms(self):
        self.ensure_one()
        if self.academic_year_id.state in ("closed", "archived"):
            raise UserError("Schedules cannot be generated for a closed or archived academic year.")
        departments = self.env["university.department"].search(
            [("active", "=", True)]
        )
        existing_department_ids = set(
            self.department_term_ids.mapped("department_id").ids
        )
        vals_list = [
            {
                "semester_id": self.id,
                "department_id": department.id,
                "date_start": self.date_start,
                "date_end": self.date_end,
            }
            for department in departments
            if department.id not in existing_department_ids
        ]
        if vals_list:
            self.env["university.department.term"].create(vals_list)
        return True

    def action_export_department_terms(self):
        self.ensure_one()
        import xlsxwriter

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Department Terms")
        headers = [
            "Faculty", "Department", "Semester", "Registration Start",
            "Registration End", "Add/Drop Start", "Add/Drop End",
            "Grade Deadline", "Start Date", "End Date", "Teaching Weeks", "State",
        ]
        header_format = workbook.add_format({"bold": True, "bg_color": "#D9EAF7"})
        for column, header in enumerate(headers):
            sheet.write(0, column, header, header_format)
        for row, term in enumerate(self.department_term_ids, start=1):
            values = [
                term.faculty_id.display_name,
                term.department_id.display_name,
                term.semester_id.display_name,
                term.registration_start,
                term.registration_end,
                term.add_drop_start,
                term.add_drop_end,
                term.grade_deadline,
                term.date_start,
                term.date_end,
                term.teaching_weeks,
                term.state,
            ]
            for column, value in enumerate(values):
                sheet.write(row, column, value or "")
        workbook.close()
        attachment = self.env["ir.attachment"].create({
            "name": "%s department terms.xlsx" % self.display_name,
            "type": "binary",
            "datas": base64.b64encode(output.getvalue()),
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "res_model": self._name,
            "res_id": self.id,
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }
