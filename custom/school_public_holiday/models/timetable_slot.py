from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class UniversityTimetableSlot(models.Model):
    _inherit = "university.timetable.slot"

    allow_on_holiday = fields.Boolean(
        string="Allow on Holiday",
        default=False,
        help="Permit scheduling this session on a public holiday (requires Administrator privileges and a reason).",
    )
    holiday_override_reason = fields.Char(
        string="Holiday Override Reason",
        help="Justification for holding this class on a public holiday.",
    )
    cancel_reason = fields.Char(
        string="Cancellation Reason",
    )
    on_holiday = fields.Boolean(
        string="Falls on Holiday",
        compute="_compute_on_holiday",
        store=True,
        index=True,
    )
    holiday_name = fields.Char(
        string="Holiday Name",
        compute="_compute_on_holiday",
        store=True,
    )

    @api.depends("start_time", "section_id")
    def _compute_on_holiday(self):
        Holiday = self.env["university.holiday"]
        PubHoliday = self.env["public.holiday"]
        for slot in self:
            if not slot.start_time:
                slot.on_holiday = False
                slot.holiday_name = False
                continue
            slot_date = fields.Datetime.context_timestamp(slot, slot.start_time).date()
            holidays = Holiday.search([
                ("active", "=", True),
                ("date_from", "<=", slot_date),
                ("date_to", ">=", slot_date),
            ])
            matched = False
            for h in holidays:
                if h._applies_to_section(slot.section_id):
                    matched = h
                    break
            if not matched:
                pub_h = PubHoliday.search([
                    ("active", "=", True),
                    ("affects_classes", "=", True),
                    ("date_from", "<=", slot_date),
                    ("date_to", ">=", slot_date),
                ], limit=1)
                if pub_h:
                    matched = pub_h
            slot.on_holiday = bool(matched)
            slot.holiday_name = matched.name if matched else False

    @api.onchange("start_time", "section_id")
    def _onchange_start_time_holiday_warning(self):
        if self.start_time:
            slot_date = fields.Datetime.context_timestamp(self, self.start_time).date()
            Holiday = self.env["university.holiday"]
            holidays = Holiday.search([
                ("active", "=", True),
                "|",
                "&", ("date_from", "<=", slot_date), ("date_to", ">=", slot_date),
                "&", ("date_start", "<=", slot_date), ("date_end", ">=", slot_date),
            ])
            matched_holiday = False
            for h in holidays:
                if h._applies_to_section(self.section_id):
                    matched_holiday = h
                    break
            if not matched_holiday:
                pub_h = self.env["public.holiday"].search([
                    ("active", "=", True),
                    ("affects_classes", "=", True),
                    ("date_from", "<=", slot_date),
                    ("date_to", ">=", slot_date),
                ], limit=1)
                if pub_h:
                    matched_holiday = pub_h
            if matched_holiday:
                return {
                    "warning": {
                        "title": _("Public Holiday Warning"),
                        "message": _(
                            "Warning: The date %(date)s falls on public holiday '%(holiday)s'. "
                            "Classes should not be scheduled on this date unless permitted by university policy."
                        ) % {
                            "date": slot_date,
                            "holiday": matched_holiday.name,
                        },
                    }
                }

    def _get_holiday_conflict(self):
        """Override school_management hook to detect public holiday conflicts."""
        self.ensure_one()
        if self.state == "cancelled" or not self.start_time:
            return False
        if self.env.context.get("skip_holiday_check"):
            return False
        user = self.env.user
        is_admin = (
            self.env.is_system()
            or user.has_group("base.group_system")
            or user.has_group("school_management.group_school_admin")
        )
        if self.allow_on_holiday and is_admin and self.holiday_override_reason and self.holiday_override_reason.strip():
            return False
        slot_date = fields.Datetime.context_timestamp(self, self.start_time).date()
        Holiday = self.env["university.holiday"]
        holidays = Holiday.search([
            ("active", "=", True),
            ("date_from", "<=", slot_date),
            ("date_to", ">=", slot_date),
        ])
        for h in holidays:
            if h._applies_to_section(self.section_id):
                return h
        pub_h = self.env["public.holiday"].search([
            ("active", "=", True),
            ("affects_classes", "=", True),
            ("date_from", "<=", slot_date),
            ("date_to", ">=", slot_date),
        ], limit=1)
        if pub_h:
            return pub_h
        return False

    @api.constrains("start_time", "section_id", "allow_on_holiday", "holiday_override_reason", "state")
    def _check_holiday_conflict(self):
        """Override school_management constraint with comprehensive permission and override rules."""
        if self.env.context.get("skip_holiday_check"):
            return
        user = self.env.user
        is_admin = (
            self.env.is_system()
            or user.has_group("base.group_system")
            or user.has_group("school_management.group_school_admin")
        )
        for slot in self:
            if slot.state == "cancelled" or not slot.start_time:
                continue
            slot_date = fields.Datetime.context_timestamp(slot, slot.start_time).date()
            Holiday = self.env["university.holiday"]
            holidays = Holiday.search([
                ("active", "=", True),
                ("date_from", "<=", slot_date),
                ("date_to", ">=", slot_date),
            ])
            matched_holiday = False
            for h in holidays:
                if h._applies_to_section(slot.section_id):
                    matched_holiday = h
                    break
            if not matched_holiday:
                pub_h = self.env["public.holiday"].search([
                    ("active", "=", True),
                    ("affects_classes", "=", True),
                    ("date_from", "<=", slot_date),
                    ("date_to", ">=", slot_date),
                ], limit=1)
                if pub_h:
                    matched_holiday = pub_h
            if not matched_holiday:
                continue

            if slot.allow_on_holiday:
                if not is_admin:
                    raise ValidationError(
                        _("Only School Administrators can schedule classes on a public holiday.")
                    )
                if not slot.holiday_override_reason or not slot.holiday_override_reason.strip():
                    raise ValidationError(
                        _("Please provide an override reason for scheduling '%s' on holiday '%s' (%s).")
                        % (slot.name or slot.section_id.name, matched_holiday.name, slot_date)
                    )
            else:
                raise ValidationError(
                    _(
                        "Cannot schedule session '%(session)s' on %(date)s because it falls on public holiday '%(holiday)s'. "
                        "University policy blocks classes on holidays. "
                        "Only School Administrators can override this by ticking 'Allow on Holiday' with an explicit reason."
                    )
                    % {
                        "session": slot.name or (slot.section_id.name if slot.section_id else "Class"),
                        "date": slot_date,
                        "holiday": matched_holiday.name,
                    }
                )

    def action_cancel_for_holiday(self, holiday_name=None):
        """Mark slot cancelled due to holiday conflict."""
        self.ensure_one()
        reason = holiday_name or self.holiday_name or _("Public Holiday")
        self.write({
            "state": "cancelled",
            "cancel_reason": reason,
        })
        return True

    def action_open_reschedule_wizard(self):
        """Open the interactive session reschedule wizard."""
        self.ensure_one()
        return {
            "name": _("Reschedule Session - %s") % (self.name or self.display_name),
            "type": "ir.actions.act_window",
            "res_model": "wizard.reschedule.session",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_slot_id": self.id,
                "default_new_start_time": self.start_time,
                "default_new_end_time": self.end_time,
                "default_new_classroom_id": self.classroom_id.id if self.classroom_id else False,
            },
        }

    @api.model
    def get_holiday_schedule_indicators(self, start_date_str, end_date_str, filters=None):
        """RPC helper for OWL Interactive Schedule to retrieve holiday day info and conflicts."""
        filters = filters or {}
        Holiday = self.env["university.holiday"]
        Section = self.env["university.class.section"]

        start_d = fields.Date.to_date(start_date_str)
        end_d = fields.Date.to_date(end_date_str)

        section_id = filters.get("section_id")
        active_sections = Section.browse(int(section_id)) if section_id else Section

        holidays = Holiday.search([
            ("active", "=", True),
            ("date_from", "<=", end_d),
            ("date_to", ">=", start_d),
        ])

        applicable_holidays = []
        holiday_days = {}
        for h in holidays:
            if active_sections and not any(h._applies_to_section(sec) for sec in active_sections):
                continue
            h_from_val = h.date_from or h.date_start
            h_to_val = h.date_to or h.date_end or h_from_val
            applicable_holidays.append({
                "id": h.id,
                "name": h.name,
                "date_from": str(h_from_val),
                "date_to": str(h_to_val),
                "date_start": str(h_from_val),
                "date_end": str(h_to_val),
                "holiday_type": h.holiday_type,
                "work_pay_multiplier": h.work_pay_multiplier,
            })
            cur = max(h_from_val, start_d)
            h_end = min(h_to_val, end_d)
            while cur <= h_end:
                day_key = str(cur)
                if day_key not in holiday_days:
                    holiday_days[day_key] = {
                        "id": h.id,
                        "name": h.name,
                        "holiday_type": h.holiday_type,
                        "date_from": str(h_from_val),
                        "date_to": str(h_to_val),
                        "date_start": str(h_from_val),
                        "date_end": str(h_to_val),
                    }
                cur += timedelta(days=1)

        pub_holidays = self.env["public.holiday"].search([
            ("active", "=", True),
            ("date_from", "<=", end_d),
            ("date_to", ">=", start_d),
        ])
        for ph in pub_holidays:
            h_from_val = ph.date_from
            h_to_val = ph.date_to or h_from_val
            applicable_holidays.append({
                "id": ph.id,
                "name": ph.name,
                "date_from": str(h_from_val),
                "date_to": str(h_to_val),
                "date_start": str(h_from_val),
                "date_end": str(h_to_val),
                "holiday_type": ph.holiday_type,
                "work_pay_multiplier": 2.0,
            })
            cur = max(h_from_val, start_d)
            h_end = min(h_to_val, end_d)
            while cur <= h_end:
                day_key = str(cur)
                if day_key not in holiday_days:
                    holiday_days[day_key] = {
                        "id": ph.id,
                        "name": ph.name,
                        "holiday_type": ph.holiday_type,
                        "date_from": str(h_from_val),
                        "date_to": str(h_to_val),
                        "date_start": str(h_from_val),
                        "date_end": str(h_to_val),
                    }
                cur += timedelta(days=1)

        domain = [
            ("start_time", ">=", datetime.combine(start_d, time.min)),
            ("start_time", "<=", datetime.combine(end_d, time.max)),
        ]
        if section_id:
            domain.append(("section_id", "=", int(section_id)))

        slots = self.search(domain)
        slot_conflicts = {}
        for slot in slots:
            slot_d = fields.Datetime.context_timestamp(slot, slot.start_time).date()
            matching_h = None
            for h in holidays:
                if h.date_from <= slot_d <= h.date_to and h._applies_to_section(slot.section_id):
                    matching_h = h
                    break
            if not matching_h:
                for ph in pub_holidays:
                    if ph.date_from <= slot_d <= ph.date_to:
                        matching_h = ph
                        break
            if matching_h:
                slot_conflicts[slot.id] = {
                    "holiday_id": matching_h.id,
                    "holiday_name": matching_h.name,
                    "date_from": str(matching_h.date_from),
                    "date_to": str(matching_h.date_to),
                    "is_cancelled": slot.state == "cancelled",
                    "allow_on_holiday": slot.allow_on_holiday,
                    "override_reason": slot.holiday_override_reason or "",
                }

        return {
            "holiday_days": holiday_days,
            "slot_conflicts": slot_conflicts,
            "holidays": applicable_holidays,
        }
