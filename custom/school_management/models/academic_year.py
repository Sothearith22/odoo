import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError


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
    current = fields.Boolean(string="Current Academic Year", default=False)
    active = fields.Boolean(string="Active", default=True)

    @api.constrains("date_start", "date_end")
    def _check_date_range(self):
        for year in self:
            if year.date_start and year.date_end and year.date_start > year.date_end:
                raise ValidationError("The academic year start date must be before the end date.")

    @api.constrains("current", "active")
    def _check_single_current_year(self):
        for year in self.filtered(lambda rec: rec.current and rec.active):
            duplicate = self.search([
                ("id", "!=", year.id),
                ("current", "=", True),
                ("active", "=", True),
            ], limit=1)
            if duplicate:
                raise ValidationError("Only one active academic year can be marked as current.")


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
    active = fields.Boolean(string="Active", default=True)

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
