from datetime import datetime, time, timedelta

import pytz
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_date


class UniversityAttendanceSession(models.Model):
    _name = "university.attendance.session"
    _description = "Attendance Session"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    section_id = fields.Many2one(
        "university.class.section", string="Class Section", required=True, ondelete="cascade",
    )
    date = fields.Date(required=True)
    state = fields.Selection(
        [("draft", "Not recorded"), ("recorded", "Recorded")],
        default="draft", required=True, tracking=True,
    )
    notes = fields.Text(string="Session Notes", tracking=True)
    recorded_by_id = fields.Many2one("res.users", string="Last Recorded By", readonly=True)
    recorded_at = fields.Datetime(string="Last Recorded At", readonly=True)

    _section_date_unique = models.Constraint(
        "unique (section_id, date)", "An attendance session already exists for this section and date.",
    )

    @api.depends("section_id.name", "date")
    def _compute_display_name(self):
        for session in self:
            session.display_name = _("%(section)s - %(date)s") % {
                "section": session.section_id.name,
                "date": format_date(self.env, session.date) if session.date else _("No date"),
            }

    def action_open_sheet(self):
        self.ensure_one()
        self.check_access("read")
        action = self.env.ref("school_management.action_university_attendance_sheet").read()[0]
        action["context"] = {
            "default_section_id": self.section_id.id,
            "default_date": fields.Date.to_string(self.date),
        }
        return action


class UniversityAttendance(models.Model):
    _name = "university.attendance"
    _description = "Student Attendance"
    _order = "date desc, id desc"

    student_id = fields.Many2one("university.student", string="Student", required=True)
    section_id = fields.Many2one("university.class.section", string="Grade/Section", required=True)
    teacher_id = fields.Many2one(
        "university.teacher", 
        string="Teacher",
        related="section_id.teacher_id",
        store=True,
    )
    date = fields.Date(string="Date", default=fields.Date.context_today, required=True)
    status = fields.Selection(
        [
            ("present", "Present"),
            ("absent", "Absent"),
            ("late", "Late"),
            ("permission", "Permission / Excused"),
        ],
        string="Status",
        required=True,
        default="present"
    )
    remark = fields.Char(string="Remark")

    _student_date_section_unique = models.Constraint(
        "unique (student_id, date, section_id)",
        "Attendance for this student, date, and section already exists.",
    )

    @api.depends("student_id", "date")
    def _compute_display_name(self):
        for attendance in self:
            student_name = attendance.student_id.display_name or _("Student")
            date = fields.Date.to_string(attendance.date) if attendance.date else _("No date")
            attendance.display_name = _("%(student)s - %(date)s") % {
                "student": student_name,
                "date": date,
            }

    @api.model
    def _attendance_sheet_statuses(self):
        return {"present", "absent", "late", "permission"}

    @api.model
    def _attendance_sheet_date(self, date):
        attendance_date = fields.Date.to_date(date)
        if not attendance_date:
            raise ValidationError(_("Please choose a valid attendance date."))
        return attendance_date

    @api.model
    def _attendance_sheet_section(self, section_id):
        try:
            section_id = int(section_id)
        except (TypeError, ValueError):
            section_id = 0
        section = self.env["university.class.section"].browse(section_id).exists()
        if not section:
            raise ValidationError(_("Please choose a valid class section."))
        section.check_access("read")
        return section

    @api.model
    def _attendance_sheet_students(self, section):
        enrollments = self.env["university.enrollment"].search([
            ("section_id", "=", section.id),
            ("status", "=", "enrolled"),
        ])
        students = enrollments.mapped("student_id").exists()
        return students.sorted(lambda student: (student.name or "").casefold())

    @api.model
    def get_sheet(self, section_id, date):
        self.check_access("read")
        Session = self.env["university.attendance.session"]
        Session.check_access("read")
        section = self._attendance_sheet_section(section_id)
        attendance_date = self._attendance_sheet_date(date)
        students = self._attendance_sheet_students(section)
        session = Session.search([
            ("section_id", "=", section.id), ("date", "=", attendance_date),
        ], limit=1)

        timezone = pytz.timezone(self.env.user.tz or "UTC")
        start = timezone.localize(datetime.combine(attendance_date, time.min)).astimezone(pytz.UTC)
        end = timezone.localize(datetime.combine(attendance_date + timedelta(days=1), time.min)).astimezone(pytz.UTC)
        slots = self.env["university.timetable.slot"].search([
            ("section_id", "=", section.id),
            ("start_time", ">=", start.replace(tzinfo=None)),
            ("start_time", "<", end.replace(tzinfo=None)),
        ])

        records = self.search([
            ("section_id", "=", section.id),
            ("date", "=", attendance_date),
            ("student_id", "in", students.ids or [0]),
        ])
        attendance_by_student = {record.student_id.id: record for record in records}

        last_write = max(
            (record.write_date for record in records if record.write_date),
            default=False,
        )

        lines = []
        for student in students:
            attendance = attendance_by_student.get(student.id)
            lines.append({
                "student_id": student.id,
                "name": student.name,
                "code": student.student_id or "",
                "section_name": section.display_name,
                "status": attendance.status if attendance else "present",
                "remark": (attendance.remark or "") if attendance else "",
                "attendance_id": attendance.id if attendance else False,
                "has_image": bool(student.image_1920),
                "student_model": "university.student",
                "image_field": "image_1920",
            })

        return {
            "taken": bool(records),
            "last_saved_at": fields.Datetime.to_string(last_write) if last_write else False,
            "section_name": section.display_name,
            "date": fields.Date.to_string(attendance_date),
            "lines": lines,
            "session_id": session.id or False,
            "notes": session.notes or "",
            "subject": section.subject_id.display_name or ", ".join(slots.mapped("subject_id.display_name")),
            "teacher": section.teacher_id.display_name or ", ".join(slots.mapped("teacher_id.display_name")),
            "semester": section.semester_id.display_name,
            "academic_year": section.semester_id.academic_year_id.display_name,
            "classroom": section.classroom_id.display_name or "",
            "recorded_by": session.recorded_by_id.display_name or "",
            "recorded_at": fields.Datetime.to_string(session.recorded_at) if session.recorded_at else False,
            "slots": [{
                "id": slot.id,
                "subject": slot.subject_id.display_name,
                "teacher": slot.teacher_id.display_name,
                "location": slot.location or slot.classroom_id.display_name or "",
                "start_time": fields.Datetime.to_string(slot.start_time),
                "end_time": fields.Datetime.to_string(slot.end_time),
            } for slot in slots],
        }

    @api.model
    def save_sheet(self, section_id, date, lines, notes=None):
        self.check_access("create")
        section = self._attendance_sheet_section(section_id)
        attendance_date = self._attendance_sheet_date(date)
        if not isinstance(lines, list):
            raise ValidationError(_("Attendance lines must be a list."))
        if notes is not None and not isinstance(notes, str):
            raise ValidationError(_("Session notes must be text."))

        students = self._attendance_sheet_students(section)
        allowed_student_ids = set(students.ids)
        allowed_statuses = self._attendance_sheet_statuses()

        normalized_lines = {}
        for line in lines:
            if not isinstance(line, dict):
                raise ValidationError(_("Invalid attendance line."))
            try:
                student_id = int(line.get("student_id"))
            except (TypeError, ValueError):
                raise ValidationError(_("Invalid student on an attendance line."))
            if student_id not in allowed_student_ids:
                raise ValidationError(_("Student does not belong to the selected class section."))

            status = line.get("status") or "present"
            if status not in allowed_statuses:
                raise ValidationError(_("Invalid attendance status: %s") % status)

            normalized_lines[student_id] = {
                "student_id": student_id,
                "status": status,
                "remark": (line.get("remark") or "").strip(),
            }

        existing = self.search([
            ("section_id", "=", section.id),
            ("date", "=", attendance_date),
            ("student_id", "in", list(normalized_lines) or [0]),
        ])
        existing_by_student = {record.student_id.id: record for record in existing}
        changes = []
        labels = dict(self._fields["status"].selection)

        for student_id, values in normalized_lines.items():
            vals = {
                "student_id": student_id,
                "section_id": section.id,
                "date": attendance_date,
                "status": values["status"],
                "remark": values["remark"],
            }
            attendance = existing_by_student.get(student_id)
            if attendance:
                if attendance.status != values["status"]:
                    changes.append(_("%(student)s: %(old)s -> %(new)s") % {
                        "student": attendance.student_id.display_name,
                        "old": labels[attendance.status], "new": labels[values["status"]],
                    })
                if (attendance.remark or "") != values["remark"]:
                    changes.append(_("%(student)s: attendance note updated") % {
                        "student": attendance.student_id.display_name,
                    })
                if attendance.status != values["status"] or (attendance.remark or "") != values["remark"]:
                    attendance.write(vals)
            else:
                attendance = self.create(vals)
                changes.append(_("%(student)s: %(status)s") % {
                    "student": attendance.student_id.display_name, "status": labels[attendance.status],
                })

        if normalized_lines:
            Session = self.env["university.attendance.session"]
            session = Session.search([
                ("section_id", "=", section.id), ("date", "=", attendance_date),
            ], limit=1)
            first_save = not session
            if not session:
                session = Session.create({"section_id": section.id, "date": attendance_date})
            session_values = {
                "state": "recorded", "recorded_by_id": self.env.uid,
                "recorded_at": fields.Datetime.now(),
            }
            if notes is not None:
                session_values["notes"] = notes.strip()
            session.write(session_values)
            if first_save or changes:
                body = Markup("<p>%s</p>") % (
                    _("Attendance recorded") if first_save else _("Attendance updated")
                )
                if changes:
                    body += Markup("<ul>%s</ul>") % Markup("").join(
                        Markup("<li>%s</li>") % change for change in changes
                    )
                session.message_post(body=body, subtype_xmlid="mail.mt_note")

        return self.get_sheet(section.id, fields.Date.to_string(attendance_date))
