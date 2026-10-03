/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class StudentDashboardShell extends Component {
    static template = "school_management.StudentDashboardShell";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            error: null,
            student: null,
            activeTab: "classes", // 'classes' | 'schedule' | 'transcript' | 'curriculum' | 'financial'
            scheduleViewMode: "calendar", // 'calendar' | 'list'
            currentWeekOffset: 0,
            enrolledClasses: [],
            scheduleSlots: [],
            transcripts: [],
            transcriptLines: [],
            transcriptRequests: [],
            assessmentResults: [],
            programInfo: null,
            programSubjects: [],
            counts: {
                classes: 0,
                schedule: 0,
                transcript: 0,
                requests: 0,
                curriculum: 0,
                financial: 0,
                followups: 0,
            },
            enrollmentCount: 0,
            feeCount: 0,
            paymentCount: 0,
            followups: [],
        });

        onWillStart(async () => {
            const isStudent = await user.hasGroup("school_management.group_school_student");
            const isTeacher = await user.hasGroup("school_management.group_school_teacher");
            const isAdmin = (await user.hasGroup("base.group_system")) || (await user.hasGroup("school_management.group_school_admin"));
            const isDean = await user.hasGroup("school_management.group_school_dean");
            const isHod = await user.hasGroup("school_management.group_school_hod");

            if (!isStudent && !isAdmin) {
                if (isTeacher && !isDean && !isHod) {
                    await this.action.doAction("school_management.action_teacher_dashboard_shell", { clearBreadcrumbs: true });
                    return;
                } else if (isDean || isHod) {
                    await this.action.doAction("school_management.action_school_dashboard_shell", { clearBreadcrumbs: true });
                    return;
                }
            }
            await this.loadStudentData();
        });
    }

    async loadStudentData() {
        try {
            const students = await this.orm.searchRead(
                "university.student",
                [["user_id", "=", user.userId]],
                [
                    "name",
                    "student_id",
                    "status",
                    "program_id",
                    "department_id",
                    "faculty_id",
                    "academic_year_id",
                    "current_semester_id",
                    "advisor_id",
                    "gpa",
                    "attendance_rate",
                    "completed_credits",
                    "risk_level",
                    "risk_reason",
                    "fee_total",
                    "fee_paid",
                    "fee_balance",
                    "email",
                    "phone",
                    "gender",
                    "date_of_birth",
                    "address",
                    "image_1920",
                ],
                { limit: 1 },
            );
            this.state.student = students[0] || null;

            if (this.state.student) {
                const studentId = this.state.student.id;

                // 1. Load Enrollments & Class Sections & Classrooms
                const enrollments = await this.orm.searchRead(
                    "university.enrollment",
                    [["student_id", "=", studentId]],
                    [
                        "id",
                        "class_section_id",
                        "subject_id",
                        "instructor_id",
                        "semester_id",
                        "academic_year_id",
                        "enrollment_date",
                        "status",
                    ],
                    { order: "enrollment_date desc, id desc" }
                );

                const sectionIds = enrollments
                    .map((e) => e.class_section_id?.[0])
                    .filter(Boolean);

                let sectionsMap = {};
                let classroomsMap = {};

                if (sectionIds.length) {
                    const sections = await this.orm.searchRead(
                        "university.class.section",
                        [["id", "in", sectionIds]],
                        [
                            "id",
                            "name",
                            "section_type",
                            "classroom_id",
                            "capacity",
                            "subject_id",
                            "teacher_id",
                            "semester_id",
                            "program_id",
                        ]
                    );
                    sections.forEach((s) => {
                        sectionsMap[s.id] = s;
                    });

                    const classroomIds = sections
                        .map((s) => s.classroom_id?.[0])
                        .filter(Boolean);

                    if (classroomIds.length) {
                        try {
                            const classrooms = await this.orm.searchRead(
                                "university.classroom",
                                [["id", "in", classroomIds]],
                                ["id", "name", "building", "room_type", "capacity"]
                            );
                            classrooms.forEach((c) => {
                                classroomsMap[c.id] = c;
                            });
                        } catch {
                            // Non-fatal if classroom details restricted
                        }
                    }
                }

                // Assemble rich enrolled classes list
                const enrolledClasses = enrollments.map((enr) => {
                    const secId = enr.class_section_id?.[0];
                    const sec = secId ? sectionsMap[secId] : null;
                    const cId = sec?.classroom_id?.[0];
                    const cDetail = cId ? classroomsMap[cId] : null;

                    return {
                        id: enr.id,
                        status: enr.status,
                        enrollment_date: enr.enrollment_date,
                        section_id: secId,
                        section_name: sec?.name || enr.class_section_id?.[1] || "General Section",
                        section_type: sec?.section_type || "cohort",
                        capacity: sec?.capacity || null,
                        subject_id: enr.subject_id?.[0] || sec?.subject_id?.[0],
                        subject_name: enr.subject_id?.[1] || sec?.subject_id?.[1] || "Enrolled Subject",
                        instructor_id: enr.instructor_id?.[0] || sec?.teacher_id?.[0],
                        instructor_name: enr.instructor_id?.[1] || sec?.teacher_id?.[1] || "Faculty Member",
                        semester_name: enr.semester_id?.[1] || sec?.semester_id?.[1] || "Current Semester",
                        academic_year_name: enr.academic_year_id?.[1] || "Current Academic Year",
                        classroom: sec?.classroom_id
                            ? {
                                  id: cId,
                                  name: sec.classroom_id[1],
                                  building: cDetail?.building || "Main Campus",
                                  room_type: cDetail?.room_type || "classroom",
                                  capacity: cDetail?.capacity || null,
                              }
                            : null,
                    };
                });
                this.state.enrolledClasses = enrolledClasses;

                // 2. Load Schedule & Timetable Slots
                let scheduleSlots = [];
                if (sectionIds.length) {
                    try {
                        const slots = await this.orm.searchRead(
                            "university.timetable.slot",
                            [["section_id", "in", sectionIds]],
                            [
                                "id",
                                "name",
                                "section_id",
                                "subject_id",
                                "teacher_id",
                                "classroom_id",
                                "timeslot_id",
                                "start_time",
                                "end_time",
                                "location",
                                "state",
                            ],
                            { order: "start_time asc", limit: 60 }
                        );
                        scheduleSlots = slots.map((s) => {
                            const timeInfo = this.parseSlotTimes(s.start_time, s.end_time);
                            return {
                                id: s.id,
                                name: s.name,
                                section_id: s.section_id?.[0],
                                section_name: s.section_id?.[1] || "Section",
                                subject_id: s.subject_id?.[0],
                                subject_name: s.subject_id?.[1] || "Subject",
                                teacher_name: s.teacher_id?.[1] || "Instructor",
                                classroom_name: s.classroom_id?.[1] || s.location || "Room TBA",
                                start_time: s.start_time,
                                end_time: s.end_time,
                                state: s.state || "todo",
                                date_key: timeInfo.dateStr,
                                date_formatted: timeInfo.dateFormatted,
                                time_formatted: timeInfo.timeFormatted,
                                start_display: timeInfo.startTimeStr,
                                end_display: timeInfo.endTimeStr,
                                color_class: this.getSubjectColorClass(s.subject_id?.[0] || 0),
                            };
                        });
                    } catch {
                        scheduleSlots = [];
                    }
                }
                this.state.scheduleSlots = scheduleSlots;

                // 3. Load Transcripts & Grades
                let transcripts = [];
                let transcriptLines = [];
                try {
                    transcripts = await this.orm.searchRead(
                        "university.transcript",
                        [["student_id", "=", studentId]],
                        ["id", "name", "cumulative_gpa", "total_credits", "state", "verification_code"],
                        { order: "id desc", limit: 1 }
                    );
                    if (transcripts.length) {
                        transcriptLines = await this.orm.searchRead(
                            "university.transcript.line",
                            [["transcript_id", "=", transcripts[0].id]],
                            [
                                "id",
                                "academic_year_id",
                                "semester_id",
                                "subject_id",
                                "credits",
                                "final_score",
                                "grade",
                                "grade_point",
                                "is_passing",
                            ],
                            { order: "academic_year_id asc, semester_id asc" }
                        );
                    } else {
                        // Check Report Cards if no official transcript yet
                        const reportCards = await this.orm.searchRead(
                            "university.report.card",
                            [["student_id", "=", studentId]],
                            ["id", "name", "gpa", "state"],
                            { order: "id desc" }
                        );
                        if (reportCards.length) {
                            const cardIds = reportCards.map((c) => c.id);
                            const lines = await this.orm.searchRead(
                                "university.report.card.line",
                                [["report_card_id", "in", cardIds]],
                                [
                                    "id",
                                    "subject_id",
                                    "credits",
                                    "final_score",
                                    "grade",
                                    "grade_point",
                                    "is_passing",
                                ],
                                { limit: 20 }
                            );
                            transcriptLines = lines.map((l) => ({
                                ...l,
                                semester_id: [0, "Current Session"],
                                academic_year_id: [0, "Current Year"],
                            }));
                        }
                    }
                } catch {
                    transcripts = [];
                    transcriptLines = [];
                }
                this.state.transcripts = transcripts;
                this.state.transcriptLines = transcriptLines;

                // 4. Load Student Transcript Requests
                let transcriptRequests = [];
                try {
                    transcriptRequests = await this.orm.searchRead(
                        "university.transcript.request",
                        [["student_id", "=", studentId]],
                        [
                            "id",
                            "name",
                            "request_type",
                            "copies",
                            "purpose",
                            "delivery_method",
                            "state",
                            "approved_date",
                            "transcript_id",
                            "verification_code",
                            "create_date",
                            "fee_amount",
                            "payment_state",
                            "reject_reason",
                        ],
                        { order: "create_date desc, id desc" }
                    );
                } catch {
                    transcriptRequests = [];
                }
                this.state.transcriptRequests = transcriptRequests;

                // 5. Load Program Curriculum
                let programInfo = null;
                let programSubjects = [];
                if (this.state.student.program_id) {
                    try {
                        const programs = await this.orm.searchRead(
                            "university.program",
                            [["id", "in", [this.state.student.program_id[0]]]],
                            [
                                "id",
                                "name",
                                "code",
                                "degree_type",
                                "duration_years",
                                "total_credits",
                                "department_id",
                                "faculty_id",
                                "subject_ids",
                            ]
                        );
                        if (programs.length) {
                            programInfo = programs[0];
                            const enrolledSubjectIds = new Set(
                                enrolledClasses.map((c) => c.subject_id).filter(Boolean)
                            );
                            const passedSubjectIds = new Set(
                                transcriptLines
                                    .filter((l) => l.is_passing)
                                    .map((l) => l.subject_id?.[0])
                                    .filter(Boolean)
                            );

                            if (programInfo.subject_ids && programInfo.subject_ids.length) {
                                const subjects = await this.orm.searchRead(
                                    "university.subject",
                                    [["id", "in", programInfo.subject_ids]],
                                    ["id", "name", "code", "credits", "department_id"],
                                    { order: "code asc, name asc" }
                                );
                                programSubjects = subjects.map((sub) => {
                                    let status = "required";
                                    if (passedSubjectIds.has(sub.id)) {
                                        status = "completed";
                                    } else if (enrolledSubjectIds.has(sub.id)) {
                                        status = "enrolled";
                                    }
                                    return {
                                        ...sub,
                                        status,
                                    };
                                });
                            }
                        }
                    } catch {
                        // Non-fatal
                    }
                }
                this.state.programInfo = programInfo;
                this.state.programSubjects = programSubjects;

                // 6. Financials & Followups
                const [feeCount, paymentCount, followups] = await Promise.all([
                    this.orm.searchCount("university.fee", [["student_id", "=", studentId]]),
                    this.orm.searchCount("university.payment", [["student_id", "=", studentId]]),
                    this.orm.searchRead(
                        "university.student.followup",
                        [["student_id", "=", studentId], ["visible_to_student", "=", true]],
                        ["title", "description", "action_type", "date_deadline", "state", "advisor_id"],
                        { order: "date_deadline asc, id desc" }
                    ),
                ]);
                this.state.enrollmentCount = enrolledClasses.length;
                this.state.feeCount = feeCount;
                this.state.paymentCount = paymentCount;
                this.state.followups = followups;

                this.state.counts = {
                    classes: enrolledClasses.length,
                    schedule: scheduleSlots.length,
                    transcript: transcriptLines.length,
                    requests: transcriptRequests.length,
                    curriculum: programSubjects.length,
                    financial: feeCount,
                    followups: followups.length,
                };
            }
        } catch (error) {
            this.state.error = error.message || "Unable to load your student dashboard.";
        } finally {
            this.state.loading = false;
        }
    }

    // Weekly Calendar Computed Days
    get currentWeekDays() {
        const today = new Date();
        const currentDay = today.getDay(); // 0 (Sun) to 6 (Sat)
        const distanceToMonday = (currentDay === 0 ? -6 : 1) - currentDay;
        const monday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
        monday.setDate(today.getDate() + distanceToMonday + (this.state.currentWeekOffset * 7));

        const days = [];
        const dayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
        const shortNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

        const pad = (n) => n.toString().padStart(2, "0");
        const todayStr = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;

        for (let i = 0; i < 6; i++) {
            const d = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate());
            d.setDate(monday.getDate() + i);
            const dateStr = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

            const daySlots = (this.state.scheduleSlots || [])
                .filter((s) => s.date_key === dateStr)
                .sort((a, b) => (a.start_time > b.start_time ? 1 : -1));

            days.push({
                dayName: dayNames[i],
                shortName: shortNames[i],
                dateStr: dateStr,
                formattedDate: d.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
                isToday: dateStr === todayStr,
                slots: daySlots,
                hasSlots: daySlots.length > 0,
            });
        }
        return days;
    }

    get weekRangeLabel() {
        const days = this.currentWeekDays;
        if (!days.length) return "";
        return `${days[0].dayName}, ${days[0].formattedDate} — ${days[days.length - 1].dayName}, ${days[days.length - 1].formattedDate}`;
    }

    get currentWeekTotalSlots() {
        const days = this.currentWeekDays;
        return days.reduce((acc, d) => acc + d.slots.length, 0);
    }

    prevWeek() {
        this.state.currentWeekOffset -= 1;
    }

    nextWeek() {
        this.state.currentWeekOffset += 1;
    }

    resetWeekToToday() {
        this.state.currentWeekOffset = 0;
    }

    setScheduleViewMode(mode) {
        this.state.scheduleViewMode = mode;
    }

    setActiveTab(tab) {
        this.state.activeTab = tab;
    }

    relationLabel(value) {
        return value?.[1] || "Not assigned";
    }

    navigate(actionXmlId) {
        this.action.doAction(actionXmlId, { clearBreadcrumbs: true });
    }

    openClassSection(sectionId) {
        if (!sectionId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Class Section Details",
            res_model: "university.class.section",
            res_id: sectionId,
            views: [[false, "form"]],
            view_mode: "form",
            context: {
                create: false,
                edit: false,
                delete: false,
            },
        });
    }

    openSlot(slotId) {
        if (!slotId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Timetable Class Session",
            res_model: "university.timetable.slot",
            res_id: slotId,
            views: [[false, "form"]],
            view_mode: "form",
            context: { create: false, edit: false, delete: false },
        });
    }

    openMyTimetableCalendar() {
        try {
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i);
                if (k && k.startsWith("scaleOf-viewId-")) {
                    localStorage.setItem(k, "week");
                }
            }
        } catch (e) {}
        this.action.doAction("school_management.action_university_timetable_slot_student", {
            additionalContext: {
                default_mode: "week",
                calendar_mode: "week",
            },
        });
    }

    openMyProfile() {
        if (!this.state.student) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "My Profile",
            res_model: "university.student",
            res_id: this.state.student.id,
            views: [[false, "form"]],
            view_mode: "form",
            context: {
                create: false,
                edit: false,
                delete: false,
                student_self_view: true,
            },
        });
    }

    openTranscript() {
        if (this.state.transcripts && this.state.transcripts.length) {
            this.action.doAction({
                type: "ir.actions.act_window",
                name: "Academic Transcript",
                res_model: "university.transcript",
                res_id: this.state.transcripts[0].id,
                views: [[false, "form"]],
                view_mode: "form",
                context: { create: false, edit: false, delete: false },
            });
        } else {
            this.action.doAction("school_management.action_university_transcript_student");
        }
    }

    async printTranscript() {
        if (this.state.transcripts && this.state.transcripts.length) {
            return this.action.doAction({
                type: "ir.actions.report",
                report_name: "school_management.report_university_transcript_document",
                report_type: "qweb-pdf",
                res_ids: [this.state.transcripts[0].id],
            });
        } else {
            this.openReportCards();
        }
    }

    openReportCards() {
        this.action.doAction("school_management.action_university_report_card_student");
    }

    openNewTranscriptRequest() {
        if (!this.state.student) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Request Official Transcript",
            res_model: "university.transcript.request",
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
            context: {
                default_student_id: this.state.student.id,
                default_request_type: "official",
                default_copies: 1,
                default_purpose: "employment",
                default_delivery_method: "download",
            },
        });
    }

    openTranscriptRequest(reqId) {
        if (!reqId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Transcript Request Details",
            res_model: "university.transcript.request",
            res_id: reqId,
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
        });
    }

    async printCurriculum() {
        if (this.state.student?.program_id) {
            return this.action.doAction({
                type: "ir.actions.report",
                report_name: "school_management.report_curriculum_document",
                report_type: "qweb-pdf",
                res_ids: [this.state.student.program_id[0]],
            });
        }
    }

    parseSlotTimes(startStr, endStr) {
        if (!startStr) {
            return {
                dateStr: "",
                dateFormatted: "",
                timeFormatted: "",
                startTimeStr: "",
                endTimeStr: "",
            };
        }
        const [datePart, timePart = "00:00:00"] = startStr.split(" ");
        const [hS = "0", mS = "0"] = timePart.split(":");
        const startH = parseInt(hS, 10);
        const startM = parseInt(mS, 10);
        const startAmpm = startH >= 12 ? "PM" : "AM";
        const startH12 = startH % 12 || 12;
        const startTimeStr = `${startH12}:${startM.toString().padStart(2, "0")} ${startAmpm}`;

        let endTimeStr = "";
        if (endStr) {
            const [, endTimePart = "00:00:00"] = endStr.split(" ");
            const [hE = "0", mE = "0"] = endTimePart.split(":");
            const endH = parseInt(hE, 10);
            const endM = parseInt(mE, 10);
            const endAmpm = endH >= 12 ? "PM" : "AM";
            const endH12 = endH % 12 || 12;
            endTimeStr = `${endH12}:${endM.toString().padStart(2, "0")} ${endAmpm}`;
        }

        let dateFormatted = datePart;
        try {
            const [y, m, d] = datePart.split("-").map((v) => parseInt(v, 10));
            const dateObj = new Date(y, m - 1, d);
            dateFormatted = dateObj.toLocaleDateString(undefined, {
                weekday: "short",
                month: "short",
                day: "numeric",
            });
        } catch {
            dateFormatted = datePart;
        }

        return {
            dateStr: datePart,
            dateFormatted,
            timeFormatted: endTimeStr ? `${startTimeStr} – ${endTimeStr}` : startTimeStr,
            startTimeStr,
            endTimeStr,
        };
    }

    getSubjectColorClass(id) {
        const palettes = [
            "o_slot_palette_sapphire",
            "o_slot_palette_emerald",
            "o_slot_palette_indigo",
            "o_slot_palette_amber",
            "o_slot_palette_teal",
            "o_slot_palette_rose",
        ];
        return palettes[Math.abs(id) % palettes.length];
    }

    formatRoomType(type) {
        const types = {
            lecture_hall: "Lecture Hall",
            classroom: "Standard Classroom",
            lab: "Laboratory",
            auditorium: "Auditorium",
        };
        return types[type] || "Classroom";
    }

    formatDegreeType(type) {
        const types = {
            bachelor: "Bachelor's Degree",
            master: "Master's Degree",
            doctorate: "Doctoral Degree",
            diploma: "Diploma",
        };
        return types[type] || "Undergraduate";
    }

    formatSlotDate(dtStr) {
        return this.parseSlotTimes(dtStr, "").dateFormatted;
    }

    formatSlotTime(startStr, endStr) {
        return this.parseSlotTimes(startStr, endStr).timeFormatted;
    }
}

registry.category("actions").add("student_dashboard_shell", StudentDashboardShell);

export default StudentDashboardShell;
