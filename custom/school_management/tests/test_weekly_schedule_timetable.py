import secrets
from datetime import datetime, time, timedelta
import pytz

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from .common import StudyPlanCommon


@tagged("post_install", "-at_install", "school_management")
class TestWeeklyScheduleTimetable(StudyPlanCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Timeslot = cls.env["university.timeslot"]
        cls.timeslot_mon = Timeslot.create({
            "name": "Mon 08:00 - 10:00",
            "day_of_week": "0",
            "start_hour": 8.0,
            "end_hour": 10.0,
        })
        cls.timeslot_wed = Timeslot.create({
            "name": "Wed 08:00 - 10:00",
            "day_of_week": "2",
            "start_hour": 8.0,
            "end_hour": 10.0,
        })

    def test_01_weekly_lines_and_summary_computation(self):
        """Weekly schedule lines compute day and time summary on class section."""
        section = self.env["university.class.section"].create({
            "name": f"Data Structures - Sec {secrets.token_hex(2).upper()}",
            "program_id": self.program.id,
            "subject_id": self.subject_1.id,
            "teacher_id": self.teacher.id,
            "classroom_id": self.classroom.id,
            "semester_id": self.semester.id,
            "capacity": 30,
        })
        # Create weekly lines for Monday and Wednesday
        self.env["university.class.schedule.line"].create([
            {
                "class_id": section.id,
                "weekday": "0",
                "timeslot_id": self.timeslot_mon.id,
                "room_id": self.classroom.id,
                "teacher_id": self.teacher.id,
            },
            {
                "class_id": section.id,
                "weekday": "2",
                "timeslot_id": self.timeslot_wed.id,
                "room_id": self.classroom.id,
                "teacher_id": self.teacher.id,
            },
        ])
        section._compute_schedule_summary()
        self.assertIn("Mon", section.day_summary)
        self.assertIn("Wed", section.day_summary)
        self.assertIn("08:00", section.time_summary)

    def test_02_generate_timetable_and_skip_public_holidays(self):
        """Wizard generates dated sessions across term dates and skips public holidays."""
        section = self.env["university.class.section"].create({
            "name": f"Data Structures - B {secrets.token_hex(2).upper()}",
            "program_id": self.program.id,
            "subject_id": self.subject_1.id,
            "teacher_id": self.teacher.id,
            "classroom_id": self.classroom.id,
            "semester_id": self.semester.id,
            "capacity": 30,
        })
        self.env["university.class.schedule.line"].create([
            {
                "class_id": section.id,
                "weekday": "0",
                "timeslot_id": self.timeslot_mon.id,
                "room_id": self.classroom.id,
                "teacher_id": self.teacher.id,
            },
            {
                "class_id": section.id,
                "weekday": "2",
                "timeslot_id": self.timeslot_wed.id,
                "room_id": self.classroom.id,
                "teacher_id": self.teacher.id,
            },
        ])

        # Pick a Monday within the semester date range to set as a public holiday
        term_start = self.semester.date_start
        term_end = self.semester.date_end
        holiday_date = None
        cur = term_start
        while cur <= term_end:
            if cur.weekday() == 0:  # Monday
                holiday_date = cur
                break
            cur += timedelta(days=1)
        self.assertTrue(holiday_date, "A Monday should exist in the term.")

        holiday = self.env["public.holiday"].create({
            "name": f"Test Holiday {secrets.token_hex(2)}",
            "date_from": holiday_date,
            "date_to": holiday_date,
            "affects_classes": True,
            "active": True,
        })

        wizard = self.env["university.timetable.generation.wizard"].create({
            "academic_year_id": self.academic_year.id,
            "semester_id": self.semester.id,
            "section_ids": [Command.set([section.id])],
        })
        res = wizard.action_generate_timetable()
        self.assertTrue(res)

        slots = self.env["university.timetable.slot"].search([("section_id", "=", section.id)])
        self.assertTrue(slots, "Sessions should have been generated.")

        # Ensure no session was created on the holiday date
        tz = pytz.timezone(self.env.user.tz or "UTC")
        slot_dates = [
            pytz.utc.localize(s.start_time).astimezone(tz).date()
            for s in slots
        ]
        self.assertNotIn(holiday_date, slot_dates, "Sessions must not be scheduled on public holiday.")

        # Idempotency check: Running wizard again must not duplicate sessions
        count_before = len(slots)
        wizard.action_generate_timetable()
        slots_after = self.env["university.timetable.slot"].search([("section_id", "=", section.id)])
        self.assertEqual(len(slots_after), count_before, "Running wizard twice must be idempotent.")

    def test_03_teacher_conflict_prevention(self):
        """Prevent scheduling the same teacher in two overlapping sessions."""
        Slot = self.env["university.timetable.slot"]
        dt_start = datetime.combine(self.next_monday, time(8, 0))
        dt_end = datetime.combine(self.next_monday, time(10, 0))

        sec1 = self.env["university.class.section"].create({
            "name": "Sec Teacher Conf 1",
            "program_id": self.program.id,
            "subject_id": self.subject_1.id,
            "teacher_id": self.teacher.id,
            "classroom_id": self.classroom.id,
            "semester_id": self.semester.id,
            "capacity": 30,
        })
        sec2 = self.env["university.class.section"].create({
            "name": "Sec Teacher Conf 2",
            "program_id": self.program.id,
            "subject_id": self.subject_2.id,
            "teacher_id": self.teacher.id,
            "classroom_id": self.classroom.id,
            "semester_id": self.semester.id,
            "capacity": 30,
        })

        Slot.create({
            "section_id": sec1.id,
            "subject_id": self.subject_1.id,
            "teacher_id": self.teacher.id,
            "classroom_id": self.classroom.id,
            "start_time": dt_start,
            "end_time": dt_end,
            "state": "scheduled",
        })

        with self.assertRaises(ValidationError):
            Slot.create({
                "section_id": sec2.id,
                "subject_id": self.subject_2.id,
                "teacher_id": self.teacher.id,
                "classroom_id": self.classroom.id,
                "start_time": dt_start,
                "end_time": dt_end,
                "state": "scheduled",
            })

    def test_04_room_conflict_prevention(self):
        """Prevent scheduling the same classroom in two overlapping sessions."""
        Slot = self.env["university.timetable.slot"]
        dt_start = datetime.combine(self.next_monday + timedelta(days=1), time(8, 0))
        dt_end = datetime.combine(self.next_monday + timedelta(days=1), time(10, 0))

        other_teacher = self.env["university.teacher"].create({
            "name": "Prof. Bob",
            "faculty_id": self.faculty.id,
            "department_id": self.department.id,
            "subject_ids": [Command.link(self.subject_2.id)],
        })
        sec1 = self.env["university.class.section"].create({
            "name": "Sec Room Conf 1",
            "program_id": self.program.id,
            "subject_id": self.subject_1.id,
            "teacher_id": self.teacher.id,
            "classroom_id": self.classroom.id,
            "semester_id": self.semester.id,
            "capacity": 30,
        })
        sec2 = self.env["university.class.section"].create({
            "name": "Sec Room Conf 2",
            "program_id": self.program.id,
            "subject_id": self.subject_2.id,
            "teacher_id": other_teacher.id,
            "classroom_id": self.classroom.id,
            "semester_id": self.semester.id,
            "capacity": 30,
        })

        Slot.create({
            "section_id": sec1.id,
            "subject_id": self.subject_1.id,
            "teacher_id": self.teacher.id,
            "classroom_id": self.classroom.id,
            "start_time": dt_start,
            "end_time": dt_end,
            "state": "scheduled",
        })

        with self.assertRaises(ValidationError):
            Slot.create({
                "section_id": sec2.id,
                "subject_id": self.subject_2.id,
                "teacher_id": other_teacher.id,
                "classroom_id": self.classroom.id,
                "start_time": dt_start,
                "end_time": dt_end,
                "state": "scheduled",
            })

    def test_05_student_schedule_overlap_warning(self):
        """Onchange warns when student is enrolled in overlapping class section."""
        sec_overlap_1 = self.env["university.class.section"].create({
            "name": "Overlap Sec 1",
            "program_id": self.program.id,
            "subject_id": self.subject_1.id,
            "teacher_id": self.teacher.id,
            "classroom_id": self.classroom.id,
            "semester_id": self.semester.id,
            "capacity": 30,
        })
        sec_overlap_2 = self.env["university.class.section"].create({
            "name": "Overlap Sec 2",
            "program_id": self.program.id,
            "subject_id": self.subject_2.id,
            "teacher_id": self.teacher.id,
            "classroom_id": self.classroom.id,
            "semester_id": self.semester.id,
            "capacity": 30,
        })
        self.env["university.class.schedule.line"].create([
            {
                "class_id": sec_overlap_1.id,
                "weekday": "0",
                "timeslot_id": self.timeslot_mon.id,
            },
            {
                "class_id": sec_overlap_2.id,
                "weekday": "0",
                "timeslot_id": self.timeslot_mon.id,
            },
        ])

        # Student enrolled in sec_overlap_1
        self.env["university.enrollment"].with_context(bypass_registration_window=True).create({
            "student_id": self.student.id,
            "class_section_id": sec_overlap_1.id,
            "status": "enrolled",
        })

        # Check onchange warning when selecting sec_overlap_2
        new_enrollment = self.env["university.enrollment"].new({
            "student_id": self.student.id,
            "class_section_id": sec_overlap_2.id,
        })
        res = new_enrollment._onchange_class_section_or_student()
        self.assertTrue(res and "warning" in res, "Onchange should return a schedule overlap warning.")
        self.assertIn("Schedule Overlap Warning", res["warning"]["title"])

    def test_06_student_my_timetable_security(self):
        """Students only see published sessions of their own active enrollments."""
        Slot = self.env["university.timetable.slot"]
        dt_start = datetime.combine(self.next_monday + timedelta(days=2), time(8, 0))
        dt_end = datetime.combine(self.next_monday + timedelta(days=2), time(10, 0))

        draft_slot = Slot.create({
            "section_id": self.class_section.id,
            "subject_id": self.subject_1.id,
            "teacher_id": self.teacher.id,
            "classroom_id": self.classroom.id,
            "start_time": dt_start,
            "end_time": dt_end,
            "generation_state": "draft",
            "state": "scheduled",
        })
        pub_slot = Slot.create({
            "section_id": self.class_section.id,
            "subject_id": self.subject_1.id,
            "teacher_id": self.teacher.id,
            "classroom_id": self.classroom.id,
            "start_time": dt_start + timedelta(days=7),
            "end_time": dt_end + timedelta(days=7),
            "generation_state": "published",
            "state": "published",
        })

        # Read as student user
        slots_as_student = Slot.with_user(self.student_user).search([
            ("id", "in", (draft_slot.id, pub_slot.id))
        ])
        self.assertIn(pub_slot, slots_as_student, "Published session must be visible to enrolled student.")
        self.assertNotIn(draft_slot, slots_as_student, "Draft session must not be visible to student.")
