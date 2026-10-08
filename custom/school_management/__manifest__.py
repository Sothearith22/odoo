{
    "name": "University Management System",
    "version": "19.0.2.0.0",
    "category": "Education",
    "summary": "University ERP - Structure, Academics, Students, Teachers, Enrollments",
    "author": "University Department",
    "license": "LGPL-3",
    "depends": [
        "auth_signup",
        "base",
        "mail",
        "portal",
        "web",
    ],
    "external_dependencies": {"python": ["xlsxwriter"]},
    "data": [
        # Security
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/record_rules.xml",

        # Data
        "data/cleanup_legacy_models.xml",
        "data/dashboard_data.xml",
        "data/fee_sequence.xml",
        "data/student_sequence.xml",
        "data/teacher_sequence.xml",
        "data/academic_defaults.xml",
        "data/admission_stage_data.xml",
        "data/mail_template.xml",
        "data/university_capability_data.xml",
        "data/fix_user_teacher_links.xml",
        "data/demo_attendance_links.xml",
        "data/exam_cron_data.xml",
        "data/ir_cron.xml",

        # Portal
        "views/portal_templates.xml",

        # Wizards
        "wizard/student_enrollment_wizard_views.xml",
        "wizard/bulk_enrollment_wizard_views.xml",
        "wizard/populate_class_wizard_views.xml",
        "wizard/teacher_account_wizard_views.xml",
        "wizard/year_rollover_wizard_views.xml",
        "wizard/attendance_take_wizard_views.xml",
        "wizard/attendance_print_wizard_views.xml",

        # Core Views
        "views/faculty_views.xml",
        "views/department_views.xml",
        "views/program_views.xml",
        "views/academic_year_views.xml",
        "views/department_term_views.xml",
        "views/holiday_views.xml",
        "views/semester_subject_views.xml",
        "views/classroom_views.xml",
        "views/admission_views.xml",
        "views/admission_lead_views.xml",
        "views/subject_views.xml",
        "views/curriculum_views.xml",
        "views/class_section_views.xml",
        "views/academic_assignment_views.xml",
        "views/teacher_views.xml",
        "views/student_views.xml",
        "views/advising_views.xml",

        # Configuration
        "views/res_config_settings_views.xml",
        "views/capability_views.xml",
        "views/grading_views.xml",
        "views/transcript_request_views.xml",

        # Reports
        "reports/payment_report_template.xml",
        "reports/payment_report.xml",
        "reports/curriculum_report_template.xml",
        "reports/curriculum_report.xml",
        "reports/attendance_reports.xml",

        # Business Views
        "views/enrollment_views.xml",
        "views/fee_views.xml",
        "views/payment_views.xml",
        "views/document_signature_views.xml",

        # Dashboard & Notices
        "views/notice_board_views.xml",
        "views/dashboard_views.xml",
        "views/school_dashboard_shell_actions.xml",

        # Teacher Portal
        "views/teacher_dashboard_shell_actions.xml",
        "views/lesson_plan_views.xml",
        "views/assignment_views.xml",
        "views/timetable_views.xml",
        "views/timetable_conflict_views.xml",
        "views/attendance_sheet_views.xml",
        "views/attendance_views.xml",
        "views/attendance_dashboard_views.xml",
        "views/staff_attendance_views.xml",
        "views/service_hour_views.xml",
        "views/exam_views.xml",

        # Academic Reports
        "reports/academic_report_templates.xml",
        "reports/academic_reports.xml",

        # Menu must load after actions
        "views/menu_views.xml",
    ],
    "demo": [
        "demo/attendance_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "school_management/static/src/school_management/design_tokens.scss",
            "school_management/static/src/school_management/backend.scss",
            "school_management/static/src/school_management/bulk_enrollment_wizard.scss",
            "school_management/static/src/scss/status_badge.scss",
            "school_management/static/src/scss/student_kanban.scss",
            "school_management/static/src/scss/subject_kanban.scss",
            "school_management/static/src/scss/admission_ui.scss",
            "school_management/static/src/attendance_sheet/attendance_sheet.js",
            "school_management/static/src/attendance_sheet/attendance_sheet.xml",
            "school_management/static/src/attendance_sheet/attendance_sheet.scss",
            "school_management/static/src/attendance_sheet/attendance_list_view.js",
            "school_management/static/src/attendance_sheet/staff_attendance_sheet.js",
            "school_management/static/src/attendance_sheet/staff_attendance_sheet.xml",
            "school_management/static/src/attendance_sheet/staff_attendance_sheet.scss",
            "school_management/static/src/attendance/attendance.scss",
            "school_management/static/src/attendance/attendance_grid.js",
            "school_management/static/src/attendance/attendance_grid.xml",
            "school_management/static/src/attendance/attendance_at_risk.js",
            "school_management/static/src/attendance/attendance_at_risk.xml",
            "school_management/static/src/attendance/attendance_comparison.js",
            "school_management/static/src/attendance/attendance_comparison.xml",
            "school_management/static/src/school_management/dashboard_shell.js",
            "school_management/static/src/school_management/dashboard_shell.xml",
            "school_management/static/src/school_management/dashboard_shell.scss",
            "school_management/static/src/school_management/student_dashboard_shell.js",
            "school_management/static/src/school_management/student_dashboard_shell.xml",
            "school_management/static/src/school_management/student_dashboard_shell.scss",
            "school_management/static/src/school_management/webclient_patch.js",
            "school_management/static/src/school_management/teacher_dashboard_shell.js",
            "school_management/static/src/school_management/teacher_dashboard_shell.xml",
            "school_management/static/src/school_management/teacher_dashboard_shell.scss",
            "school_management/static/src/timetable/timetable_popover.js",
            "school_management/static/src/timetable/timetable_popover.xml",
            "school_management/static/src/schedule/university_schedule.scss",
            "school_management/static/src/schedule/university_schedule.js",
            "school_management/static/src/schedule/university_schedule.xml",
        ],
    },
    "installable": True,
    "application": True,
}

