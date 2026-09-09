from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestUniversitySettings(TransactionCase):
    def setUp(self):
        super().setUp()
        self.AcademicYear = self.env["university.academic.year"].sudo()
        self.Semester = self.env["university.semester"].sudo()

    def _create_year(self, name):
        return self.AcademicYear.create(
            {
                "name": name,
                "date_start": "2026-09-01",
                "date_end": "2027-06-30",
            }
        )

    def _create_semester(self, year, name="Semester 1"):
        return self.Semester.create(
            {
                "name": name,
                "academic_year_id": year.id,
                "semester_type": "semester_1",
                "date_start": fields.Date.to_date("2026-09-01"),
                "date_end": fields.Date.to_date("2027-01-31"),
            }
        )

    def test_saving_settings_syncs_current_academic_year(self):
        previous_year = self._create_year("2025-2026")
        self.AcademicYear.search([("current", "=", True)]).write({"current": False})
        previous_year.current = True
        selected_year = self._create_year("2026-2027")
        semester = self._create_semester(selected_year)

        settings = self.env["res.config.settings"].create(
            {
                "current_academic_year_id": selected_year.id,
                "current_semester_id": semester.id,
            }
        )
        settings.execute()

        self.assertFalse(previous_year.current)
        self.assertTrue(selected_year.current)
        self.assertEqual(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("school_management.current_academic_year_id"),
            str(selected_year.id),
        )
        self.assertEqual(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("school_management.current_semester_id"),
            str(semester.id),
        )

    def test_settings_reject_semester_from_another_year(self):
        year_a = self._create_year("2026-2027")
        year_b = self._create_year("2027-2028")
        semester_b = self._create_semester(year_b)

        with self.assertRaises(ValidationError):
            self.env["res.config.settings"].create(
                {
                    "current_academic_year_id": year_a.id,
                    "current_semester_id": semester_b.id,
                }
            )

    def test_settings_menu_is_system_admin_only(self):
        menu = self.env.ref("school_management.menu_university_settings")
        self.assertIn(self.env.ref("base.group_system"), menu.group_ids)
        self.assertNotIn(
            self.env.ref("school_management.group_school_admin"), menu.group_ids
        )
