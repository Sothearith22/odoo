from odoo import api, fields, models
from odoo.exceptions import ValidationError


class UniversityResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    current_academic_year_id = fields.Many2one(
        "university.academic.year",
        string="Current Academic Year",
        config_parameter="school_management.current_academic_year_id",
        domain=[("active", "=", True)],
        help="Academic year currently used by the University application.",
    )
    current_semester_id = fields.Many2one(
        "university.semester",
        string="Current Semester",
        config_parameter="school_management.current_semester_id",
        domain="[('active', '=', True), ('academic_year_id', '=', current_academic_year_id)]",
        help="Semester currently used by the University application.",
    )

    @api.onchange("current_academic_year_id")
    def _onchange_current_academic_year_id(self):
        if (
            self.current_semester_id
            and self.current_semester_id.academic_year_id != self.current_academic_year_id
        ):
            self.current_semester_id = False

    @api.constrains("current_academic_year_id", "current_semester_id")
    def _check_current_period(self):
        for settings in self:
            if (
                settings.current_semester_id
                and settings.current_semester_id.academic_year_id
                != settings.current_academic_year_id
            ):
                raise ValidationError(
                    "The current semester must belong to the selected academic year."
                )

    def set_values(self):
        super().set_values()

        academic_years = self.env["university.academic.year"].sudo().with_context(
            active_test=False
        )
        selected_year = self.current_academic_year_id.sudo()
        academic_years.search([("current", "=", True)]).write({"current": False})
        if selected_year:
            selected_year.write({"current": True})
