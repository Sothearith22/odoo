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
            isPreviewMode: false,
            previewStudents: [],
            selectedPreviewStudentId: null,
            activeTab: "classes", // 'classes' | 'attendance' | 'schedule' | 'transcript' | 'curriculum' | 'financial'
            scheduleViewMode: (localStorage.getItem("student_schedule_view_mode") === "week" || localStorage.getItem("student_schedule_view_mode") === "calendar") ? "week" : "agenda",
            currentWeekOffset: 0,
            selectedDayDateStr: null,
            enrolledClasses: [],
            scheduleSlots: [],
            attendanceStats: {
                rate: 100,
                totalSessions: 0,
                present: 0,
                late: 0,
                absent: 0,
                excused: 0,
                isLowAttendance: false,
                byCourse: [],
                recentLogs: [],
            },
            notices: [],
            selectedNotice: null,
            transcripts: [],
            transcriptLines: [],
            transcriptRequests: [],
            assessmentResults: [],
            programInfo: null,
            programSubjects: [],
            counts: {
                classes: 0,
                attendance: 0,
                schedule: 0,
                transcript: 0,
                requests: 0,
                curriculum: 0,
                financial: 0,
                followups: 0,
                notices: 0,
            },
            enrollmentCount: 0,
            feeCount: 0,
            paymentCount: 0,
            followups: [],
        });

        onWillStart(async () => {
            await this.loadStudentData();
        });
    }

    async loadStudentData(targetStudentId = null) {
        try {
            this.state.loading = true;
            this.state.error = null;

            const studentFields = [
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
            ];

            let studentRecord = null;
            if (targetStudentId) {
                const results = await this.orm.searchRead(
                    "university.student",
                    [["id", "=", targetStudentId]],
                    studentFields,
                    { limit: 1 }
                );
                studentRecord = results[0] || null;
            } else {
                const students = await this.orm.searchRead(
                    "university.student",
                    [["user_id", "=", user.userId]],
                    studentFields,
                    { limit: 1 }
                );
                studentRecord = students[0] || null;

                // If current user is staff/admin without a linked student record,
                // enable preview mode so they can inspect/test the student portal.
                if (!studentRecord) {
                    const isAdmin = (await user.hasGroup("base.group_system")) || (await user.hasGroup("school_management.group_school_admin"));
                    const isStaff = (await user.hasGroup("school_management.group_school_teacher")) || (await user.hasGroup("school_management.group_school_registrar"));
                    if (isAdmin || isStaff) {
                        const previewStudents = await this.orm.searchRead(
                            "university.student",
                            [["status", "in", ["enrolled", "admitted", "graduated"]]],
                            ["id", "name", "student_id", "status"],
                            { order: "id asc", limit: 20 }
                        );
                        if (previewStudents.length) {
                            this.state.previewStudents = previewStudents;
                            this.state.isPreviewMode = true;
                            const previewId = this.state.selectedPreviewStudentId || previewStudents[0].id;
                            this.state.selectedPreviewStudentId = previewId;
                            const res = await this.orm.searchRead(
                                "university.student",
                                [["id", "=", previewId]],
                                studentFields,
                                { limit: 1 }
                            );
                            studentRecord = res[0] || null;
                        }
                    }
                }
            }

            this.state.student = studentRecord;

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
                            // Non-fatal
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

                // 2. Load Attendance Records & Calculate Metrics
                try {
                    const attendances = await this.orm.searchRead(
                        "university.attendance",
                        [["student_id", "=", studentId]],
                        ["id", "date", "section_id", "teacher_id", "status", "remark"],
                        { order: "date desc, id desc", limit: 120 }
                    );

                    let present = 0, late = 0, absent = 0, excused = 0;
                    const courseStatsMap = {};

                    for (const cls of enrolledClasses) {
                        if (cls.section_id) {
                            courseStatsMap[cls.section_id] = {
                                sectionId: cls.section_id,
                                sectionName: cls.section_name,
                                subjectName: cls.subject_name,
                                instructorName: cls.instructor_name,
                                total: 0,
                                present: 0,
                                late: 0,
                                absent: 0,
                                excused: 0,
                                rate: 100,
                                isLow: false,
                            };
                        }
                    }

                    attendances.forEach((att) => {
                        const st = att.status;
                        if (st === "present") present++;
                        else if (st === "late") late++;
                        else if (st === "absent") absent++;
                        else if (st === "permission") excused++;

                        const secId = att.section_id?.[0];
                        if (secId) {
                            if (!courseStatsMap[secId]) {
                                courseStatsMap[secId] = {
                                    sectionId: secId,
                                    sectionName: att.section_id[1],
                                    subjectName: "Course Section",
                                    instructorName: att.teacher_id?.[1] || "Instructor",
                                    total: 0,
                                    present: 0,
                                    late: 0,
                                    absent: 0,
                                    excused: 0,
                                    rate: 100,
                                    isLow: false,
                                };
                            }
                            const cs = courseStatsMap[secId];
                            cs.total++;
                            if (st === "present") cs.present++;
                            else if (st === "late") cs.late++;
                            else if (st === "absent") cs.absent++;
                            else if (st === "permission") cs.excused++;
                        }
                    });

                    const byCourse = Object.values(courseStatsMap).map((cs) => {
                        if (cs.total > 0) {
                            cs.rate = Math.round((cs.present / cs.total) * 100);
                            cs.isLow = cs.rate < 80;
                        } else {
                            cs.rate = 100;
                            cs.isLow = false;
                        }
                        return cs;
                    });

                    const totalSessions = attendances.length;
                    const overallRate = totalSessions > 0
                        ? Math.round((present / totalSessions) * 100)
                        : (this.state.student.attendance_rate || 100);

                    const recentLogs = attendances.slice(0, 25).map((att) => {
                        const timeInfo = this.parseSlotTimes(att.date ? `${att.date} 00:00:00` : "", "");
                        const secId = att.section_id?.[0];
                        const sec = secId ? enrolledClasses.find((c) => c.section_id === secId) : null;
                        return {
                            id: att.id,
                            date: att.date,
                            dateFormatted: timeInfo.dateFormatted || att.date,
                            sectionName: att.section_id?.[1] || "Section",
                            subjectName: sec?.subject_name || att.section_id?.[1] || "Subject",
                            teacherName: att.teacher_id?.[1] || sec?.instructor_name || "Instructor",
                            status: att.status,
                            remark: att.remark || "",
                        };
                    });

                    this.state.attendanceStats = {
                        rate: overallRate,
                        totalSessions,
                        present,
                        late,
                        absent,
                        excused,
                        isLowAttendance: overallRate < 80 && totalSessions >= 3,
                        byCourse,
                        recentLogs,
                    };
                } catch {
                    this.state.attendanceStats = {
                        rate: this.state.student.attendance_rate || 100,
                        totalSessions: 0,
                        present: 0,
                        late: 0,
                        absent: 0,
                        excused: 0,
                        isLowAttendance: false,
                        byCourse: [],
                        recentLogs: [],
                    };
                }

                // 3. Load Notice Board Announcements
                try {
                    const notices = await this.orm.searchRead(
                        "university.notice.board",
                        [["active", "=", true]],
                        ["id", "name", "date", "content"],
                        { order: "date desc, id desc", limit: 6 }
                    );
                    const now = new Date();
                    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                    this.state.notices = notices.map((n) => {
                        const timeInfo = this.parseSlotTimes(n.date ? `${n.date} 00:00:00` : "", "");
                        let isNew = false;
                        if (n.date) {
                            const nd = new Date(n.date);
                            isNew = nd >= sevenDaysAgo;
                        }
                        return {
                            ...n,
                            dateFormatted: timeInfo.dateFormatted || n.date,
                            isNew,
                        };
                    });
                } catch {
                    this.state.notices = [];
                }

                // 4. Load Schedule & Timetable Slots via unified get_schedule API
                let scheduleSlots = [];
                try {
                    const today = new Date();
                    const dayOfWeek = today.getDay();
                    const mondayDist = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
                    const monday = new Date(today);
                    monday.setDate(today.getDate() + mondayDist);
                    const sunday = new Date(monday);
                    sunday.setDate(monday.getDate() + 6);

                    const pad = (n) => String(n).padStart(2, "0");
                    const startStr = `${monday.getFullYear()}-${pad(monday.getMonth() + 1)}-${pad(monday.getDate())}`;
                    const endStr = `${sunday.getFullYear()}-${pad(sunday.getMonth() + 1)}-${pad(sunday.getDate())}`;

                    const schedRes = await this.orm.call(
                        "university.timetable.slot",
                        "get_schedule",
                        [startStr, endStr]
                    );

                    const sessions = schedRes.sessions || [];
                    scheduleSlots = sessions.map((s) => {
                        const timeInfo = this.parseSlotTimes(s.start || s.start_time, s.end || s.end_time);
                        const statusMeta = this.getSlotStatusMeta(s);
                        return {
                            id: s.id,
                            name: s.name,
                            section_id: s.section_id,
                            section_name: s.section_code || s.section_name || "Section",
                            subject_id: s.subject_id,
                            subject_name: s.subject || s.subject_name || "Subject",
                            teacher_name: s.teacher || s.teacher_name || "Instructor",
                            classroom_name: s.room || s.classroom_name || "Room TBA",
                            start_time: s.start || s.start_time,
                            end_time: s.end || s.end_time,
                            state: s.state || "scheduled",
                            status: s.status || statusMeta.status,
                            statusLabel: statusMeta.label,
                            statusClass: statusMeta.cardClass,
                            statusBadgeClass: statusMeta.badgeClass,
                            student_attendance: s.student_attendance || "unrecorded",
                            date_key: s.date_str || timeInfo.dateStr,
                            date_formatted: timeInfo.dateFormatted,
                            time_formatted: s.start_time_str && s.end_time_str ? `${s.start_time_str} – ${s.end_time_str}` : (timeInfo.timeCompact || timeInfo.timeFormatted),
                            start_display: s.start_time_str || timeInfo.startTimeStr,
                            end_display: s.end_time_str || timeInfo.endTimeStr,
                            color_class: this.getSubjectColorClass(s.subject_id || 0),
                        };
                    });
                } catch {
                    scheduleSlots = [];
                }
                this.state.scheduleSlots = scheduleSlots;

                // 5. Load Transcripts & Grades
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

                // 6. Load Student Transcript Requests
                await this.reloadTranscriptRequests();

                // 7. Load Program Curriculum
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

                // 8. Financials & Followups
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
                    attendance: this.state.attendanceStats.totalSessions,
                    schedule: scheduleSlots.length,
                    transcript: transcriptLines.length,
                    requests: this.state.transcriptRequests.length,
                    curriculum: programSubjects.length,
                    financial: feeCount,
                    followups: followups.length,
                    notices: this.state.notices.length,
                };
            }
        } catch (error) {
            this.state.error = error.message || "Unable to load your student academic portal.";
        } finally {
            this.state.loading = false;
        }
    }

    async reloadTranscriptRequests() {
        if (!this.state.student) return;
        try {
            const requests = await this.orm.searchRead(
                "university.transcript.request",
                [["student_id", "=", this.state.student.id]],
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
            this.state.transcriptRequests = requests;
            this.state.counts.requests = requests.length;
        } catch {
            this.state.transcriptRequests = [];
        }
    }

    async onSelectPreviewStudent(ev) {
        const selectedId = parseInt(ev.target.value, 10);
        if (selectedId) {
            this.state.selectedPreviewStudentId = selectedId;
            await this.loadStudentData(selectedId);
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
        const dayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
        const shortNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

        const pad = (n) => n.toString().padStart(2, "0");
        const todayStr = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;

        for (let i = 0; i < 7; i++) {
            const d = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate());
            d.setDate(monday.getDate() + i);
            const dateStr = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

            const daySlots = (this.state.scheduleSlots || [])
                .filter((s) => s.date_key === dateStr)
                .sort((a, b) => (a.start_time > b.start_time ? 1 : -1));

            days.push({
                dayName: dayNames[i],
                shortName: shortNames[i],
                dayLetter: shortNames[i].slice(0, 1),
                dayNum: d.getDate(),
                dateStr: dateStr,
                formattedDate: d.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
                isToday: dateStr === todayStr,
                slots: daySlots,
                hasSlots: daySlots.length > 0,
                slotCount: daySlots.length,
            });
        }
        return days;
    }

    get calendarHeaderLabel() {
        const days = this.currentWeekDays;
        if (!days.length) return "Weekly Schedule";
        try {
            const [y, m, d] = days[0].dateStr.split("-").map((v) => parseInt(v, 10));
            const dateObj = new Date(y, m - 1, d);
            return dateObj.toLocaleDateString(undefined, { month: "long", year: "numeric" });
        } catch {
            return "Weekly Schedule";
        }
    }

    get displayedDays() {
        const days = this.currentWeekDays;
        if (this.state.selectedDayDateStr) {
            const match = days.filter((d) => d.dateStr === this.state.selectedDayDateStr);
            if (match.length) {
                return match;
            }
        }
        return days;
    }

    selectCalendarDay(dateStr) {
        if (this.state.selectedDayDateStr === dateStr) {
            this.state.selectedDayDateStr = null;
        } else {
            this.state.selectedDayDateStr = dateStr;
        }
    }

    get selectedDayLabel() {
        if (!this.state.selectedDayDateStr) return "";
        const match = this.currentWeekDays.find((d) => d.dateStr === this.state.selectedDayDateStr);
        return match ? `${match.dayName}, ${match.formattedDate}` : "";
    }

    get weekRangeLabel() {
        const days = this.currentWeekDays;
        if (!days.length) return "";
        return `${days[0].shortName}, ${days[0].formattedDate} – ${days[days.length - 1].shortName}, ${days[days.length - 1].formattedDate}`;
    }

    get weekClassesSummary() {
        const count = this.currentWeekTotalSlots;
        if (count === 0) return "No classes this week";
        if (count === 1) return "1 class this week";
        return `${count} classes this week`;
    }

    get nextClassThisWeek() {
        const days = this.currentWeekDays;
        const now = new Date();
        const allSlots = [];
        for (const day of days) {
            for (const slot of day.slots) {
                allSlots.push(slot);
            }
        }
        if (!allSlots.length) return null;

        const ongoing = allSlots.find((s) => s.status === "ongoing");
        if (ongoing) {
            return {
                ...ongoing,
                countdown: "In progress",
            };
        }

        const upcomingSlots = allSlots.filter((s) => s.status === "upcoming" && s.state !== "cancelled");
        if (!upcomingSlots.length) return null;

        upcomingSlots.sort((a, b) => (a.start_time > b.start_time ? 1 : -1));
        const nextSlot = upcomingSlots[0];

        let countdown = "Upcoming";
        if (nextSlot.start_time) {
            const startDt = new Date(nextSlot.start_time.replace(" ", "T"));
            const diffMs = startDt.getTime() - now.getTime();
            if (diffMs <= 0) {
                countdown = "In progress";
            } else {
                const diffMin = Math.round(diffMs / 60000);
                const diffHour = Math.floor(diffMin / 60);
                const diffDay = Math.floor(diffHour / 24);
                if (diffMin < 60) {
                    countdown = `Starts in ${Math.max(1, diffMin)} min`;
                } else if (diffHour < 24) {
                    countdown = `Starts in ${diffHour} hr${diffHour > 1 ? "s" : ""}`;
                } else if (diffDay === 1) {
                    countdown = "Starts in 1 day";
                } else {
                    countdown = `Starts in ${diffDay} days`;
                }
            }
        }

        return {
            ...nextSlot,
            countdown,
        };
    }

    getSlotStatusMeta(slot) {
        if (slot.state === "cancelled" || slot.status === "cancelled") {
            return {
                status: "cancelled",
                label: "Cancelled",
                cardClass: "status-cancelled",
                badgeClass: "badge bg-danger-subtle text-danger very-small",
            };
        }
        const now = new Date();
        let startTime = null;
        let endTime = null;
        if (slot.start_time) {
            startTime = new Date(slot.start_time.replace(" ", "T"));
        }
        if (slot.end_time) {
            endTime = new Date(slot.end_time.replace(" ", "T"));
        }

        if (startTime && endTime) {
            if (now < startTime) {
                return {
                    status: "upcoming",
                    label: "Upcoming",
                    cardClass: "status-upcoming",
                    badgeClass: "badge bg-primary-subtle text-primary very-small",
                };
            } else if (now >= startTime && now <= endTime) {
                return {
                    status: "ongoing",
                    label: "Ongoing",
                    cardClass: "status-ongoing",
                    badgeClass: "badge bg-warning-subtle text-warning very-small",
                };
            } else {
                return {
                    status: "completed",
                    label: "Completed",
                    cardClass: "status-completed",
                    badgeClass: "badge bg-success-subtle text-success very-small",
                };
            }
        }

        const fallback = slot.status || "upcoming";
        return {
            status: fallback,
            label: fallback.charAt(0).toUpperCase() + fallback.slice(1),
            cardClass: `status-${fallback}`,
            badgeClass: "badge bg-secondary-subtle text-secondary very-small",
        };
    }

    get currentWeekSlots() {
        const days = this.displayedDays;
        const slots = [];
        for (const day of days) {
            for (const slot of day.slots) {
                slots.push({
                    ...slot,
                    dayName: day.dayName,
                    shortName: day.shortName,
                    formattedDate: day.formattedDate,
                    isToday: day.isToday,
                });
            }
        }
        return slots;
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
        this.state.selectedDayDateStr = null;
    }

    setScheduleViewMode(mode) {
        this.state.scheduleViewMode = mode;
        try {
            localStorage.setItem("student_schedule_view_mode", mode);
        } catch {}
    }

    scrollToSchedule() {
        const el = document.getElementById("student-schedule-sidebar");
        if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "start" });
            el.classList.add("o_sidebar_highlight_pulse");
            setTimeout(() => el.classList.remove("o_sidebar_highlight_pulse"), 1200);
        }
    }

    setActiveTab(tab) {
        if (tab === "schedule") {
            this.scrollToSchedule();
            return;
        }
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
        } catch {}
        this.action.doAction("school_management.action_university_schedule_view", {
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

    openMyAttendance() {
        this.action.doAction("school_management.action_university_attendance_student");
    }

    openNoticeBoardAction() {
        this.action.doAction("school_management.action_university_notice_board");
    }

    openNoticeModal(notice) {
        this.state.selectedNotice = notice;
    }

    closeNoticeModal() {
        this.state.selectedNotice = null;
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
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "Request Official Transcript",
                res_model: "university.transcript.request",
                views: [[false, "form"]],
                view_mode: "form",
                target: "new",
                context: {
                    default_student_id: this.state.student.id,
                    default_request_type: "official",
                    default_copies: 1,
                    default_purpose: "employment",
                    default_delivery_method: "download",
                },
            },
            {
                onClose: async () => {
                    await this.reloadTranscriptRequests();
                },
            }
        );
    }

    openTranscriptRequest(reqId) {
        if (!reqId) return;
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "Transcript Request Details",
                res_model: "university.transcript.request",
                res_id: reqId,
                views: [[false, "form"]],
                view_mode: "form",
                target: "new",
            },
            {
                onClose: async () => {
                    await this.reloadTranscriptRequests();
                },
            }
        );
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

        const startCompact = `${startH}:${startM.toString().padStart(2, "0")}`;
        let endCompact = "";
        if (endStr) {
            const [, endTimePart = "00:00:00"] = endStr.split(" ");
            const [hE = "0", mE = "0"] = endTimePart.split(":");
            endCompact = `${parseInt(hE, 10)}:${parseInt(mE, 10).toString().padStart(2, "0")}`;
        }
        return {
            dateStr: datePart,
            dateFormatted,
            timeFormatted: endCompact ? `${startCompact}–${endCompact}` : startCompact,
            timeCompact: endCompact ? `${startCompact}–${endCompact}` : startCompact,
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
