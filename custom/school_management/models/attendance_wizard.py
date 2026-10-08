from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class UniversityAttendanceTakeWizard(models.TransientModel):
    _name = "university.attendance.take.wizard"
    _description = "Take Attendance"

    section_id = fields.Many2one(
        "university.class.section", string="Class Section", required=True,
    )
    date = fields.Date(
        string="Attendance Date", default=fields.Date.context_today, required=True,
    )
    notes = fields.Text(string="Session Notes")
    line_ids = fields.One2many(
        "university.attendance.take.wizard.line", "wizard_id", string="Students",
    )

    @api.model_create_multi
    def create(self, vals_list):
        Attendance = self.env["university.attendance"]
        for vals in vals_list:
            if vals.get("section_id") and not vals.get("line_ids"):
                section_id = vals["section_id"]
                att_date = vals.get("date") or fields.Date.context_today(self)
                section = self.env["university.class.section"].browse(section_id)
                existing = Attendance.search([
                    ("section_id", "=", section.id),
                    ("date", "=", att_date),
                ])
                by_student = {record.student_id.id: record for record in existing}
                lines = []
                for student in Attendance._attendance_sheet_students(section):
                    record = by_student.get(student.id)
                    lines.append((0, 0, {
                        "student_id": student.id,
                        "status": record.status if record else "present",
                        "remark": (record.remark or "") if record else "",
                    }))
                vals["line_ids"] = lines
        return super().create(vals_list)

    @api.onchange("section_id", "date")
    def _onchange_section_date(self):
        if not self.section_id:
            return {"value": {"line_ids": [(5, 0, 0)]}, "domain": {
                "section_id": [("id", "in", self.env["university.attendance"]._get_role_sections().ids or [0])]
            }}
        Attendance = self.env["university.attendance"]
        allowed = Attendance._get_role_sections()
        if self.section_id not in allowed:
            raise ValidationError(
                _("You are not allowed to record attendance for this class section.")
            )
        if not self.date:
            return {"value": {"line_ids": [(5, 0, 0)]}}

        existing = Attendance.search([
            ("section_id", "=", self.section_id.id),
            ("date", "=", self.date),
        ])
        by_student = {record.student_id.id: record for record in existing}
        lines = []
        for student in Attendance._attendance_sheet_students(self.section_id):
            record = by_student.get(student.id)
            lines.append((0, 0, {
                "student_id": student.id,
                "status": record.status if record else "present",
                "remark": (record.remark or "") if record else "",
            }))
        return {"value": {"line_ids": lines}, "domain": {
            "section_id": [("id", "in", allowed.ids or [0])]
        }}

    def action_mark_all_present(self):
        return self._mark_all("present")

    def action_mark_all_absent(self):
        return self._mark_all("absent")

    def _mark_all(self, status):
        self.ensure_one()
        self.line_ids.write({"status": status})
        return {
            "type": "ir.actions.act_window",
            "name": _("Take Attendance"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_save(self):
        self.ensure_one()
        if not self.section_id:
            raise ValidationError(_("Please choose a class section."))
        if not self.date:
            raise ValidationError(_("Please choose an attendance date."))
        lines = [
            {"student_id": line.student_id.id, "status": line.status, "remark": line.remark or ""}
            for line in self.line_ids
        ]
        Attendance = self.env["university.attendance"]
        Attendance.save_sheet(
            self.section_id.id,
            fields.Date.to_string(self.date),
            lines,
            (self.notes or "").strip() or None,
        )
        return {"type": "ir.actions.act_window_close"}


class UniversityAttendanceTakeWizardLine(models.TransientModel):
    _name = "university.attendance.take.wizard.line"
    _description = "Take Attendance Line"

    wizard_id = fields.Many2one(
        "university.attendance.take.wizard", required=True, ondelete="cascade",
    )
    student_id = fields.Many2one("university.student", string="Student", required=True, readonly=True)
    status = fields.Selection(
        [
            ("present", "Present"),
            ("absent", "Absent"),
            ("late", "Late"),
            ("excused", "Excused"),
        ],
        string="Status",
        required=True,
        default="present",
    )
    remark = fields.Char(string="Remarks")