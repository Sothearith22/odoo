{
    "name": "University Management System",
    "version": "19.0.1.2.1",
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
    ],"data": [
    # Security
    "security/security.xml",
    "security/ir.model.access.csv",
    "security/record_rules.xml",

    # Portal
    "views/portal_templates.xml",

    # Data
    "data/cleanup_legacy_models.xml",
    "data/dashboard_data.xml",
    "data/fee_sequence.xml",
    "data/academic_defaults.xml",
    "data/mail_template.xml",
    "data/university_capability_data.xml",
    "data/fix_user_teacher_links.xml",

    # Wizards
    "wizard/student_enrollment_wizard_views.xml",
    "wizard/bulk_enrollment_wizard_views.xml",
    "wizard/populate_class_wizard_views.xml",
    "wizard/teacher_account_wizard_views.xml",

    # Core Views
    "views/faculty_views.xml",
    "views/department_views.xml",
    "views/program_views.xml",
    "views/academic_year_views.xml",
    "views/semester_subject_views.xml",
    "views/classroom_views.xml",
    "views/admission_views.xml",
    "views/subject_views.xml",
    "views/class_section_views.xml",
    "views/academic_assignment_views.xml",
    "views/teacher_views.xml",
    "views/student_views.xml",

    # Configuration
    "views/res_config_settings_views.xml",
    "views/capability_views.xml",
    "views/grading_views.xml",

    # Reports
    "reports/payment_report_template.xml",
    "reports/payment_report.xml",
    "reports/curriculum_report_template.xml",
    "reports/curriculum_report.xml",

    # Business Views
    "views/enrollment_views.xml",
    "views/fee_views.xml",
    "views/payment_views.xml",
    "views/document_signature_views.xml",

    # Dashboard
    "views/dashboard_views.xml",
    "views/school_dashboard_shell_actions.xml",

    # Teacher Portal
    "views/teacher_dashboard_shell_actions.xml",
    "views/lesson_plan_views.xml",
    "views/assignment_views.xml",
    "views/timetable_views.xml",

    # Academic Reports
    "reports/academic_report_templates.xml",
    "reports/academic_reports.xml",

    # Menu must load after actions
    "views/menu_views.xml",
],
    "assets": {
        "web.assets_backend": [
            "school_management/static/src/school_management/design_tokens.scss",
            "school_management/static/src/school_management/backend.scss",
            "school_management/static/src/school_management/dashboard_shell.js",
            "school_management/static/src/school_management/dashboard_shell.xml",
            "school_management/static/src/school_management/dashboard_shell.scss",
            "school_management/static/src/school_management/student_dashboard_shell.js",
            "school_management/static/src/school_management/student_dashboard_shell.xml",
            "school_management/static/src/school_management/student_dashboard_shell.scss",
            "school_management/static/src/school_management/layout/school_layout.js",
            "school_management/static/src/school_management/layout/school_layout.xml",
            "school_management/static/src/school_management/layout/school_layout.scss",
            "school_management/static/src/school_management/layout/webclient_patch.js",
            "school_management/static/src/school_management/layout/webclient_patch.xml",
            "school_management/static/src/school_management/layout/topbar_integration.scss",
            "school_management/static/src/school_management/teacher_dashboard_shell.js",
            "school_management/static/src/school_management/teacher_dashboard_shell.xml",
            "school_management/static/src/school_management/teacher_dashboard_shell.scss",
        ],
    },
    "installable": True,
    "application": True,
}
