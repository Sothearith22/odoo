import base64
import io
import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


_logger = logging.getLogger(__name__)


class UniversityAcademicYear(models.Model):
    _name = "university.academic.year"
    _description = "Academic Year"

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
        [("draft", "Draft"), ("running", "Running"), ("closed", "Closed")],
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
                WHEN current = TRUE THEN 'running'
                ELSE COALESCE(state, 'draft')
            END
            WHERE state IS NULL OR current = TRUE
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
        if any(year.state == "closed" for year in self) and not self.env.context.get(
            "allow_closed_year_write"
        ):
            raise AccessError("Closed academic years cannot be modified.")
        if vals.get("current") and "state" not in vals:
            vals["state"] = "running"
        return super().write(vals)

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


class UniversitySemester(models.Model):
    _name = "university.semester"
    _description = "Semester"

    EXPECTED_SEMESTER_WEEKS = 16
    MIN_SEMESTER_WEEKS = 4
    SOFT_WARNING_TOLERANCE_WEEKS = 4
    SOFT_WARNING_MIN_WEEKS = EXPECTED_SEMESTER_WEEKS - SOFT_WARNING_TOLERANCE_WEEKS
    SOFT_WARNING_MAX_WEEKS = EXPECTED_SEMESTER_WEEKS + SOFT_WARNING_TOLERANCE_WEEKS

    name = fields.Char(string="Semester Name", required=True)
    academic_year_id = fields.Many2one(
        "university.academic.year", string="Academic Year", required=True
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

    @api.model_create_multi
    def create(self, vals_list):
        year_ids = [vals.get("academic_year_id") for vals in vals_list]
        years = self.env["university.academic.year"].browse(year_ids).exists()
        if any(year.state == "closed" for year in years):
            raise AccessError("Semesters cannot be created in a closed academic year.")
        return super().create(vals_list)

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
                raise ValidationError(
                    "Semester start date and end date are required."
                )

            duration_days = (semester.date_end - semester.date_start).days
            if duration_days <= 0:
                raise ValidationError(
                    "The semester end date must be strictly after the start date; "
                    "the duration must be greater than zero days."
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

    def write(self, vals):
        if any(
            semester.academic_year_id.state == "closed" for semester in self
        ) and not self.env.context.get("allow_closed_year_write"):
            raise AccessError("Semesters of a closed academic year cannot be modified.")
        return super().write(vals)

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
        if self.academic_year_id.state == "closed":
            raise ValidationError("Schedules cannot be generated for a closed academic year.")
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
