import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UniversityTimetableSlot(models.Model):
    _inherit = "university.timetable.slot"

    @api.constrains("start_time")
    def _check_public_holiday_dates(self):
        if self.env.context.get("skip_holiday_check"):
            return
        user = self.env.user
        is_admin = (
            self.env.is_system()
            or user.has_group("base.group_system")
            or user.has_group("school_management.group_school_admin")
        )
        PublicHoliday = self.env["public.holiday"]
        for slot in self:
            if slot.state == "cancelled" or not slot.start_time:
                continue
            if getattr(slot, "allow_on_holiday", False) and is_admin and getattr(slot, "holiday_override_reason", None):
                continue
            slot_date = fields.Datetime.context_timestamp(slot, slot.start_time).date()
            holiday = PublicHoliday.search([
                ("active", "=", True),
                ("affects_classes", "=", True),
                ("date_from", "<=", slot_date),
                ("date_to", ">=", slot_date),
            ], limit=1)
            if holiday:
                raise ValidationError(
                    _(
                        "Cannot schedule session '%(session)s' on %(date)s because it falls on public holiday '%(holiday)s'. "
                        "University policy blocks classes on public holidays."
                    )
                    % {
                        "session": slot.name or (slot.section_id.name if slot.section_id else "Class"),
                        "date": slot_date,
                        "holiday": holiday.name,
                    }
                )

    @api.onchange("start_time")
    def _onchange_start_time_public_holiday_warning(self):
        if self.start_time:
            slot_date = fields.Datetime.context_timestamp(self, self.start_time).date()
            holiday = self.env["public.holiday"].search([
                ("active", "=", True),
                ("affects_classes", "=", True),
                ("date_from", "<=", slot_date),
                ("date_to", ">=", slot_date),
            ], limit=1)
            if holiday:
                return {
                    "warning": {
                        "title": _("Public Holiday Warning"),
                        "message": _(
                            "Warning: The date %(date)s falls on public holiday '%(holiday)s'. "
                            "Classes should not be scheduled on this date unless permitted by university policy."
                        ) % {
                            "date": slot_date,
                            "holiday": holiday.name,
                        },
                    }
                }

    @api.model
    def get_schedule(self, start_date_str, end_date_str, filters=None, limit=100, offset=0):
        res = super().get_schedule(start_date_str, end_date_str, filters=filters, limit=limit, offset=offset)
        if not isinstance(res, dict) or "holidays" not in res:
            return res
        existing_names = {h.get("name") for h in res["holidays"]}
        start_d = fields.Date.to_date(start_date_str)
        end_d = fields.Date.to_date(end_date_str)
        if start_d and end_d:
            pub_holidays = self.env["public.holiday"].sudo().search([
                ("active", "=", True),
                ("date_from", "<=", end_d),
                ("date_to", ">=", start_d),
            ])
            for ph in pub_holidays:
                if ph.name not in existing_names:
                    res["holidays"].append({
                        "id": ph.id,
                        "name": ph.name,
                        "name_km": ph.name_km or "",
                        "date_start": fields.Date.to_string(ph.date_from),
                        "date_end": fields.Date.to_string(ph.date_to),
                        "date_from": fields.Date.to_string(ph.date_from),
                        "date_to": fields.Date.to_string(ph.date_to),
                        "holiday_type": "public",
                        "faculty_name": _("University-Wide"),
                    })
        return res


class UniversityTimetableGenerationWizard(models.TransientModel):
    _inherit = "university.timetable.generation.wizard"

    def _is_holiday(self, date_check):
        """Helper to determine if a given date falls on an active public holiday."""
        d = fields.Date.to_date(date_check)
        if not d:
            return False
        return bool(self.env["public.holiday"].search_count([
            ("active", "=", True),
            ("affects_classes", "=", True),
            ("date_from", "<=", d),
            ("date_to", ">=", d),
        ]))

    def _get_excluded_dates(self, date_start, date_end):
        excluded = super()._get_excluded_dates(date_start, date_end)
        d_start = fields.Date.to_date(date_start)
        d_end = fields.Date.to_date(date_end)
        if not d_start or not d_end:
            return excluded

        holidays = self.env["public.holiday"].search([
            ("active", "=", True),
            ("affects_classes", "=", True),
            ("date_from", "<=", d_end),
            ("date_to", ">=", d_start),
        ])
        for h in holidays:
            cur = max(h.date_from, d_start)
            h_end = min(h.date_to, d_end)
            while cur <= h_end:
                excluded.add(cur)
                cur += timedelta(days=1)
        return excluded

    def action_generate_timetable(self):
        res = super().action_generate_timetable()
        week_start = fields.Date.to_date(self.start_date)
        monday = week_start - timedelta(days=week_start.weekday())
        end_date = monday + timedelta(days=self.week_count * 7)
        excluded = self._get_excluded_dates(monday, end_date)
        skipped_count = len(excluded)
        if isinstance(res, dict) and "name" in res and skipped_count > 0:
            res["name"] = f"{res['name']} ({skipped_count} Holiday Dates Skipped)"
        return res
