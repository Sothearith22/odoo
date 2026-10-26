from odoo import api, models


class AcademicTranscriptReport(models.AbstractModel):
    _name = "report.school_management.report_university_transcript_document"
    _description = "Academic Transcript Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["university.transcript"].browse(docids)
        first = docs[:1]
        scale = first.grade_scale_id
        if not scale:
            scale = self.env["university.report.card"].search(
                [
                    ("student_id", "=", first.student_id.id),
                    ("state", "in", ["generated", "approved"]),
                ],
                order="id desc",
                limit=1,
            ).grade_scale_id
        if not scale:
            scale = self.env["university.grade.scale"].search([], order="id", limit=1)

        grade_lines = scale.line_ids.sorted("min_score", reverse=True) \
            if scale else self.env[ "university.grade.scale.line"]
        has_honors = bool(
            grade_lines
            and "honors_grade_point" in grade_lines._fields
            and any(line.honors_grade_point > 0 for line in grade_lines)
        )
        if has_honors:
            weighted_max = max(line.honors_grade_point for line in grade_lines if line.honors_grade_point > 0)
        else:
            weighted_max = 4.0

        unweighted_values = [line.grade_point for line in grade_lines] if grade_lines else []
        unweighted_max = max(unweighted_values) if unweighted_values else 4.0

        honors_by_grade = {
            line.name: line.honors_grade_point for line in grade_lines
        } if has_honors else {}

        total_credits = first.total_credits
        honors_quality = sum(
            line.credits * honors_by_grade.get(line.grade, line.grade_point)
            for line in first.line_ids
        )
        weighted_gpa = (
            honors_quality / total_credits
            if has_honors and total_credits
            else first.cumulative_gpa
        )

        program = first.program_id
        if program and program.min_graduation_grade_id:
            passing_line = program.min_graduation_grade_id
        else:
            passing_lines = grade_lines.filtered(lambda line: line.is_passing).sorted("min_score")
            passing_line = passing_lines[:1]

        attendance = self.env["university.attendance"].search(
            [("student_id", "=", first.student_id.id)]
        )
        attendance_rate = False
        if attendance:
            statuses = {status: len(attendance.filtered(lambda item: item.status == status)) for status in (
                "present", "absent", "late", "excused"
            )}
            attendance_rate = self.env["university.attendance"]._attendance_percentage(statuses)

        graduation_date = getattr(first, "graduation_date", False) or getattr(
            first.student_id, "graduation_date", False
        )

        return {
            "doc_ids": docs.ids,
            "doc_model": "university.transcript",
            "docs": docs,
            "scale_id": scale,
            "grade_lines": grade_lines,
            "has_honors_grade_point": has_honors,
            "honors_denominator": weighted_max,
            "weighted_max": weighted_max,
            "unweighted_max": unweighted_max,
            "weighted_gpa": weighted_gpa,
            "unweighted_gpa": first.cumulative_gpa,
            "passing_line": passing_line,
            "attendance_rate": attendance_rate,
            "graduation_date": graduation_date,
        }
