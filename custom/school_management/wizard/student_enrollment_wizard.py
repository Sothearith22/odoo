from odoo import api, fields, models
from odoo.exceptions import ValidationError


class UniversityStudentEnrollmentWizard(models.TransientModel):
    _name = "university.student.enrollment.wizard"
    _description = "Student Course Registration Wizard"

    student_id = fields.Many2one(
        "university.student",
        string="Student",
        required=True,
        readonly=True,
    )
    academic_year_id = fields.Many2one(
        "university.academic.year",
        string="Academic Year Filter",
        help="Optional: Filter       available sections by Academic Year.",
    )
    semester_id = fields.Many2one(
        "university.semester",
        string="Semester Filter",
        domain="[('academic_year_id', '=', academic_year_id)]",
        help="Optional: Filter available sections by Semester.",
    )
    section_ids = fields.Many2many(
        "university.class.section",
        relation="student_course_reg_rel",
        string="Class Sections",
        required=True,
    )
    enrollment_date = fields.Date(
        string="Enrollment Date",
        default=fields.Date.context_today,
        required=True,
    )
    status = fields.Selection(
        [
            ("enrolled", "Enrolled"),
            ("completed", "Completed"),
            ("dropped", "Dropped"),
        ],
        string="Initial Status",
        default="enrolled",
        required=True,
    )

    @api.onchange("semester_id")
    def _onchange_semester_id(self):
        if self.semester_id and not self.academic_year_id:
            self.academic_year_id = self.semester_id.academic_year_id

    @api.onchange("academic_year_id", "semester_id", "student_id")
    def _onchange_filters(self):
        # Build domain for section_ids
        domain = [("active", "=", True)]
        
        # Only show sections that belong to subjects in the student's program
        if self.student_id.program_id:
            domain.append(("subject_id.program_ids", "in", [self.student_id.program_id.id]))
            
        if self.semester_id:
            domain.append(("semester_id", "=", self.semester_id.id))
            
            # Find subjects offered in this semester (via Semester Subjects junction model)
            offered_subjects = self.semester_id.semester_subject_ids.mapped("subject_id")
            
            sections_domain = [
                ("active", "=", True),
                ("semester_id", "=", self.semester_id.id),
            ]
            if offered_subjects:
                sections_domain.append(("subject_id", "in", offered_subjects.ids))
            if self.student_id.program_id:
                sections_domain.append(("subject_id.program_ids", "in", [self.student_id.program_id.id]))
                
            matching_sections = self.env["university.class.section"].search(sections_domain)
            if matching_sections:
                self.section_ids = matching_sections
        elif self.academic_year_id:
            domain.append(("semester_id.academic_year_id", "=", self.academic_year_id.id))
            
        return {"domain": {"section_ids": domain}}

    def action_register_courses(self):
        self.ensure_one()
        if not self.section_ids:
            raise ValidationError("Please select at least one class section.")

        # Pre-check for capacity and existing enrollments
        existing_enrollments = self.env["university.enrollment"].search([
            ("student_id", "=", self.student_id.id),
            ("section_id", "in", self.section_ids.ids),
            ("status", "=", "enrolled"),
        ])
        existing_section_ids = existing_enrollments.mapped("section_id.id")

        sections_to_enroll = self.section_ids.filtered(lambda s: s.id not in existing_section_ids)

        if not sections_to_enroll:
            raise ValidationError("The student is already enrolled in all selected sections.")

        # Capacity check
        errors = []
        for section in sections_to_enroll:
            if section.capacity:
                if section.enrolled_student_count >= section.capacity:
                    errors.append(f"'{section.name}' (Subject: {section.subject_id.name}) is full. Capacity: {section.capacity}.")
        
        if errors:
            error_msg = "\n".join(errors)
            raise ValidationError(f"Cannot enroll due to capacity limits:\n{error_msg}")

        # Create enrollments
        enrollments = self.env["university.enrollment"].create([
            {
                "student_id": self.student_id.id,
                "section_id": section.id,
                "enrollment_date": self.enrollment_date,
                "status": self.status,
            }
            for section in sections_to_enroll
        ])

        message = f"Student successfully enrolled in {len(enrollments)} section(s)."
        if existing_section_ids:
            message += f" Skipped {len(existing_section_ids)} section(s) where they were already enrolled."

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Registration Complete",
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
