from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestSecurityMenus(TransactionCase):
    """Verify the role/menu/security architecture behaves correctly.

    Fixes regressions where non-admin school roles could not see the
    University app/dashboard, and where users could reach menus whose
    underlying models they could not read (AccessError).
    """

    def setUp(self):
        super().setUp()
        self.Users = self.env["res.users"].sudo()
        self.Faculty = self.env["university.faculty"].sudo()
        self.Department = self.env["university.department"].sudo()
        self.Program = self.env["university.program"].sudo()
        self.Student = self.env["university.student"].sudo()
        self.Teacher = self.env["university.teacher"].sudo()
        self.Dashboard = self.env["school.dashboard"].sudo()

        self.g_user = self.env.ref("school_management.group_school_user")
        self.g_student = self.env.ref("school_management.group_school_student")
        self.g_teacher = self.env.ref("school_management.group_school_teacher")
        self.g_hod = self.env.ref("school_management.group_school_hod")
        self.g_dean = self.env.ref("school_management.group_school_dean")
        self.g_admin = self.env.ref("school_management.group_school_admin")

        self.root_menu = self.env.ref("school_management.menu_school_root")
        self.dashboard_menu = self.env.ref("school_management.menu_school_dashboard")
        self.finance_menu = self.env.ref("school_management.menu_university_finance_category")
        self.student_menu = self.env.ref("school_management.menu_school_student_category")
        self.academic_year_menu = self.env.ref("school_management.menu_university_academic_year")
        self.subject_menu = self.env.ref("school_management.menu_university_subject")

    def _make_user(self, login, *groups):
        return self.Users.with_context(no_reset_password=True).create(
            {
                "name": login,
                "login": login,
                "email": "%s@example.com" % login,
                "group_ids": [(6, 0, [g.id for g in groups])],
            }
        )

    def _groups_visible(self, user):
        """True if any of a menu's groups is assigned (incl. implied) to user."""
        user_groups = user.group_ids
        return self.root_menu.group_ids & user_groups

    # ------------------------------------------------------------------ #
    # 1-4. Dashboard read access per role
    # ------------------------------------------------------------------ #
    def test_dashboard_readable_by_admin(self):
        user = self._make_user("a", self.g_admin)
        rec = self.Dashboard.with_user(user).search([], limit=1)
        self.assertTrue(rec)

    def test_dashboard_readable_by_teacher(self):
        user = self._make_user("t", self.g_teacher)
        rec = self.Dashboard.with_user(user).search([], limit=1)
        self.assertTrue(rec)

    def test_dashboard_readable_by_hod(self):
        user = self._make_user("h", self.g_hod)
        rec = self.Dashboard.with_user(user).search([], limit=1)
        self.assertTrue(rec)

    def test_dashboard_readable_by_dean(self):
        user = self._make_user("d", self.g_dean)
        rec = self.Dashboard.with_user(user).search([], limit=1)
        self.assertTrue(rec)

    def test_dashboard_readable_by_plain_school_user(self):
        user = self._make_user("su", self.g_user)
        rec = self.Dashboard.with_user(user).search([], limit=1)
        self.assertTrue(rec)

    def test_dashboard_counts_respect_scope_no_access_error(self):
        # A teacher has no fee ACL; the dashboard must not raise AccessError
        # when aggregating financial KPIs (regression for sudo() removal).
        user = self._make_user("t2", self.g_teacher)
        rec = self.Dashboard.with_user(user).search([], limit=1)
        self.assertTrue(rec)
        # Read the record to trigger compute fields safely.
        self.assertEqual(rec.with_user(user).fee_count, 0)

    # ------------------------------------------------------------------ #
    # 5. Unauthorized user cannot read protected finance models
    # ------------------------------------------------------------------ #
    def test_teacher_cannot_read_fee(self):
        user = self._make_user("t3", self.g_teacher)
        with self.assertRaises(AccessError):
            self.env["university.fee"].with_user(user).search([], limit=1)

    def test_student_cannot_read_academic_year(self):
        user = self._make_user("s3", self.g_student)
        with self.assertRaises(AccessError):
            self.env["university.academic.year"].with_user(user).search([], limit=1)

    # ------------------------------------------------------------------ #
    # Root menu visibility per role
    # ------------------------------------------------------------------ #
    def test_root_menu_groups_include_school_user_and_system(self):
        menu_groups = self.root_menu.group_ids
        self.assertIn(self.g_user, menu_groups)
        system = self.env.ref("base.group_system")
        self.assertIn(system, menu_groups)

    def test_root_menu_visible_to_teacher_hod_dean_admin(self):
        for group in (self.g_teacher, self.g_hod, self.g_dean, self.g_admin):
            user = self._make_user("m_%s" % group.id, group)
            self.assertTrue(
                self._groups_visible(user),
                "%s should see the University root menu" % group.name,
            )

    # ------------------------------------------------------------------ #
    # Finance menu is admin-only (no AccessError for staff)
    # ------------------------------------------------------------------ #
    def test_finance_menu_admin_only(self):
        finance_groups = self.finance_menu.group_ids
        self.assertIn(self.g_admin, finance_groups)
        self.assertNotIn(self.g_teacher, finance_groups)
        self.assertNotIn(self.g_dean, finance_groups)

    def test_academic_year_menu_admin_only(self):
        groups = self.academic_year_menu.group_ids
        self.assertIn(self.g_admin, groups)
        self.assertNotIn(self.g_teacher, groups)

    def test_student_menu_visible_to_teacher(self):
        self.assertIn(self.g_teacher, self.student_menu.group_ids)

    def test_subject_menu_visible_to_teacher(self):
        self.assertIn(self.g_teacher, self.subject_menu.group_ids)

    # ------------------------------------------------------------------ #
    # Record rules still scope data by role
    # ------------------------------------------------------------------ #
    def _scope_setup(self):
        fac_a = self.Faculty.create({"name": "FacA", "code": "A"})
        fac_b = self.Faculty.create({"name": "FacB", "code": "B"})
        dep_a = self.Department.create({"name": "DepA", "code": "DA", "faculty_id": fac_a.id})
        dep_b = self.Department.create({"name": "DepB", "code": "DB", "faculty_id": fac_b.id})
        prog_a = self.Program.create({"name": "PA", "code": "PA", "department_id": dep_a.id})
        prog_b = self.Program.create({"name": "PB", "code": "PB", "department_id": dep_b.id})

        hod = self.Teacher.create({"name": "HOD", "department_id": dep_a.id})
        hod_user = self._make_user("hod2", self.g_hod)
        hod.user_id = hod_user
        assignment_model = self.env["university.academic.assignment"].sudo()
        assignment_model.create(
            {
                "name": "HOD A",
                "staff_id": hod.id,
                "role": "department_head",
                "department_id": dep_a.id,
                "start_date": "2025-01-01",
            }
        )
        # A teacher in dept A owns a section under dept A's program
        teacher = self.Teacher.create({"name": "TeachA", "department_id": dep_a.id})
        teacher_user = self._make_user("teacher2", self.g_teacher)
        teacher.user_id = teacher_user

        year = self.env["university.academic.year"].create(
            {"name": "2025-2026", "date_start": "2025-09-01", "date_end": "2026-06-30"}
        )
        sem = self.env["university.semester"].create(
            {"name": "S1", "academic_year_id": year.id, "semester_type": "semester_1"}
        )
        section_a = self.env["university.class.section"].sudo().create(
            {"name": "SEC-A", "program_id": prog_a.id, "semester_id": sem.id, "teacher_id": teacher.id}
        )
        section_b = self.env["university.class.section"].sudo().create(
            {"name": "SEC-B", "program_id": prog_b.id, "semester_id": sem.id}
        )
        return fac_a, fac_b, dep_a, dep_b, prog_a, prog_b, hod, hod_user, teacher, teacher_user, section_a, section_b

    def test_hod_sees_own_department_sections_only(self):
        (fac_a, fac_b, dep_a, dep_b, prog_a, prog_b,
         hod, hod_user, teacher, teacher_user, section_a, section_b) = self._scope_setup()
        visible = self.env["university.class.section"].sudo().with_user(hod_user).search([])
        self.assertIn(section_a, visible)
        self.assertNotIn(section_b, visible)

    def test_teacher_sees_own_sections_only(self):
        (fac_a, fac_b, dep_a, dep_b, prog_a, prog_b,
         hod, hod_user, teacher, teacher_user, section_a, section_b) = self._scope_setup()
        visible = self.env["university.class.section"].sudo().with_user(teacher_user).search([])
        self.assertIn(section_a, visible)
        self.assertNotIn(section_b, visible)
