from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

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
        section = self._attendance_sheet_section(section_id)
        attendance_date = self._attendance_sheet_date(date)
        students = self._attendance_sheet_students(section)

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
        }

    @api.model
    def save_sheet(self, section_id, date, lines):
        section = self._attendance_sheet_section(section_id)
        attendance_date = self._attendance_sheet_date(date)
        if not isinstance(lines, list):
            raise ValidationError(_("Attendance lines must be a list."))

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
                attendance.write(vals)
            else:
                self.create(vals)

        return self.get_sheet(section.id, fields.Date.to_string(attendance_date))
