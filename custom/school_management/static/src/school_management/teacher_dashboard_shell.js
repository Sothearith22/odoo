/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState, onMounted, useRef } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Inline plugin drawing the attendance rate/total in the doughnut centre.
const doughnutCenterText = {
    id: "doughnutCenterText",
    afterDraw(chart) {
        const opts = chart.options?.plugins?.centerText;
        if (!opts || !chart.data?.datasets?.length) return;
        const first = chart.getDatasetMeta(0)?.data?.[0];
        if (!first) return;
        const values = chart.data.datasets[0].data || [];
        const total = values.reduce((sum, v) => sum + (Number(v) || 0), 0);
        // `tooltipPosition()` is the middle of an individual slice, not the
        // middle of the doughnut.  Use the arc's centre so this label remains
        // inside the cutout regardless of which attendance status has data.
        const { x, y } = first;
        const { ctx } = chart;
        ctx.save();
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = opts.valueColor || "#0f172a";
        ctx.font = `700 ${opts.valueSize || 20}px system-ui, -apple-system, sans-serif`;
        ctx.fillText(String(total), x, y - (opts.label ? 8 : 0));
        if (opts.label) {
            ctx.fillStyle = opts.labelColor || "#64748b";
            ctx.font = "500 11px system-ui, -apple-system, sans-serif";
            ctx.fillText(opts.label, x, y + 14);
        }
        ctx.restore();
    },
};

export class TeacherDashboardShell extends Component {
    static template = "school_management.TeacherDashboardShell";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.chartRef = useRef("attendanceChart");
        this.chartInstance = null;

        this.state = useState({
            loading: true,
            error: null,
            teacher: null,
            isPreviewMode: false,
            previewTeachers: [],
            selectedPreviewTeacherId: null,
            activeTab: "schedule", // 'schedule' | 'attendance' | 'advising' | 'assignments' | 'lesson_plans'
            scheduleViewMode: "calendar", // 'calendar' | 'list'
            currentWeekOffset: 0,
            stats: {
                totalClasses: 0,
                totalAssignments: 0,
                pendingReviews: 0,
                pendingServiceHours: 0,
                adviseeCount: 0,
                highRiskAdvisees: 0,
            },
            counts: {
                schedule: 0,
                attendance: 0,
                advising: 0,
                assignments: 0,
                lessonPlans: 0,
                notices: 0,
            },
            noticeBoard: [],
            selectedNotice: null,
            lessonPlans: [],
            schedule: [],
            scheduleSlots: [],
            enrolledSections: [],
            pendingSubmissions: [],
            teacherAssignments: [],
            advisees: [],
            followups: [],
            presentCount: 0,
            absentCount: 0,
            lateCount: 0,
            excusedCount: 0,
            totalAttendance: 0,
            hasAttendanceData: false,
            attendanceRate: 0,
        });

        onWillStart(async () => {
            const isStudent = await user.hasGroup("school_management.group_school_student");
            const isTeacher = await user.hasGroup("school_management.group_school_teacher");
            const isAdmin = (await user.hasGroup("base.group_system")) || (await user.hasGroup("school_management.group_school_admin"));

            if (isStudent && !isTeacher && !isAdmin) {
                await this.action.doAction("school_management.action_student_dashboard_shell", { clearBreadcrumbs: true });
                return;
            }
            await loadBundle("web.chartjs_lib");
            await this.loadData();
        });

        onMounted(() => this.renderChart());

        onWillUnmount(() => {
            if (this.chartInstance) {
                this.chartInstance.destroy();
                this.chartInstance = null;
            }
        });
    }

    async loadData(targetTeacherId = null) {
        try {
            this.state.loading = true;
            this.state.error = null;

            const teacherFields = [
                "name",
                "title",
                "teacher_id",
                "email",
                "phone",
                "gender",
                "department_id",
                "faculty_id",
                "position",
                "specialization",
                "qualification",
                "image_1920",
                "subject_ids",
                "section_ids",
            ];

            let teacherRecord = null;
            if (targetTeacherId) {
                const teachers = await this.orm.searchRead(
                    "university.teacher",
                    [["id", "=", targetTeacherId]],
                    teacherFields,
                    { limit: 1 }
                );
                teacherRecord = teachers[0] || null;
            } else {
                const teachers = await this.orm.searchRead(
                    "university.teacher",
                    ["|", ["user_id", "=", user.userId], ["id", "=", user.teacher_id ? user.teacher_id[0] : 0]],
                    teacherFields,
                    { limit: 1 }
                );
                teacherRecord = teachers[0] || null;

                // If user is admin/staff and no teacher linked to login, allow Preview Mode
                if (!teacherRecord) {
                    const isAdmin = (await user.hasGroup("base.group_system")) || (await user.hasGroup("school_management.group_school_admin"));
                    const isStaff = (await user.hasGroup("school_management.group_school_dean")) || (await user.hasGroup("school_management.group_school_hod"));
                    if (isAdmin || isStaff) {
                        const previewTeachers = await this.orm.searchRead(
                            "university.teacher",
                            [["active", "=", true]],
                            ["id", "name", "teacher_id", "department_id"],
                            { order: "id asc", limit: 20 }
                        );
                        if (previewTeachers.length) {
                            this.state.previewTeachers = previewTeachers;
                            this.state.isPreviewMode = true;
                            const prevId = this.state.selectedPreviewTeacherId || previewTeachers[0].id;
                            this.state.selectedPreviewTeacherId = prevId;
                            const res = await this.orm.searchRead(
                                "university.teacher",
                                [["id", "=", prevId]],
                                teacherFields,
                                { limit: 1 }
                            );
                            teacherRecord = res[0] || null;
                        }
                    }
                }
            }

            this.state.teacher = teacherRecord;

            if (this.state.teacher) {
                const teacherId = this.state.teacher.id;

                // 1. Fetch KPI counts
                const [totalClasses, totalAssignments, pendingSubmissionsCount, pendingServiceHours, adviseeCount, highRiskAdvisees] = await Promise.all([
                    this.orm.searchCount("university.timetable.slot", [["teacher_id", "=", teacherId]]),
                    this.orm.searchCount("university.assignment", [["teacher_id", "=", teacherId]]),
                    this.orm.searchCount("university.assignment.submission", [
                        ["assignment_id.teacher_id", "=", teacherId],
                        ["state", "=", "submitted"],
                    ]),
                    this.orm.searchCount("university.service.hour", [
                        ["teacher_id", "=", teacherId],
                        ["state", "=", "pending"],
                    ]),
                    this.orm.searchCount("university.student", [["advisor_id", "=", teacherId]]),
                    this.orm.searchCount("university.student", [["advisor_id", "=", teacherId], ["risk_level", "=", "high"]]),
                ]);

                this.state.stats = {
                    totalClasses,
                    totalAssignments,
                    pendingReviews: pendingSubmissionsCount + pendingServiceHours,
                    pendingServiceHours,
                    adviseeCount,
                    highRiskAdvisees,
                };

                // 2. Fetch Slots for teacher (rich objects for calendar grid + list view)
                const rawSlots = await this.orm.searchRead(
                    "university.timetable.slot",
                    [["teacher_id", "=", teacherId]],
                    ["id", "name", "section_id", "subject_id", "classroom_id", "start_time", "end_time", "location", "state"],
                    { limit: 80, order: "start_time asc" }
                );

                this.state.scheduleSlots = rawSlots.map((s) => {
                    const timeInfo = this.parseSlotTimes(s.start_time, s.end_time);
                    return {
                        id: s.id,
                        name: s.name,
                        section_id: s.section_id,
                        section_name: s.section_id ? s.section_id[1] : "Section",
                        subject_id: s.subject_id,
                        subject_name: s.subject_id ? s.subject_id[1] : "Subject",
                        classroom_id: s.classroom_id,
                        classroom_name: s.classroom_id ? s.classroom_id[1] : (s.location || "Room TBA"),
                        start_time: s.start_time,
                        end_time: s.end_time,
                        state: s.state || "todo",
                        date_key: timeInfo.dateStr,
                        date_formatted: timeInfo.dateFormatted,
                        time_formatted: timeInfo.timeFormatted,
                        start_display: timeInfo.startTimeStr,
                        end_display: timeInfo.endTimeStr,
                        color_class: this.getSubjectColorClass(s.subject_id ? s.subject_id[0] : 0),
                    };
                });
                this.state.schedule = this.state.scheduleSlots.slice(0, 10);

                // 3. Fetch Class Sections taught by teacher
                try {
                    const sections = await this.orm.searchRead(
                        "university.class.section",
                        [["teacher_id", "=", teacherId]],
                        ["id", "name", "subject_id", "classroom_id", "capacity", "enrolled_student_count", "semester_id"],
                        { order: "name asc" }
                    );
                    this.state.enrolledSections = sections;
                } catch {
                    this.state.enrolledSections = [];
                }

                // 4. Fetch Pending Submissions for quick review
                this.state.pendingSubmissions = await this.orm.searchRead(
                    "university.assignment.submission",
                    [
                        ["assignment_id.teacher_id", "=", teacherId],
                        ["state", "=", "submitted"],
                    ],
                    ["name", "assignment_id", "student_id", "create_date", "state"],
                    { limit: 10, order: "create_date desc" }
                );

                // 5. Fetch Teacher's Published Assignments
                this.state.teacherAssignments = await this.orm.searchRead(
                    "university.assignment",
                    [["teacher_id", "=", teacherId]],
                    ["name", "subject_id", "section_id", "due_date", "max_score", "state", "submission_count"],
                    { limit: 10, order: "create_date desc" }
                );

                // 6. Fetch Notice Board Announcements
                try {
                    const notices = await this.orm.searchRead(
                        "university.notice.board",
                        [["active", "=", true]],
                        ["id", "name", "date", "content"],
                        { limit: 6, order: "date desc, id desc" }
                    );
                    const now = new Date();
                    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                    this.state.noticeBoard = notices.map((n) => {
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
                    this.state.noticeBoard = [];
                }

                // 7. Fetch Lesson Plans
                this.state.lessonPlans = await this.orm.searchRead(
                    "university.lesson.plan",
                    [["teacher_id", "=", teacherId]],
                    ["name", "subject_id", "create_date"],
                    { limit: 10, order: "create_date desc" }
                );

                // 8. Fetch Advisees & Follow-ups
                const [advisees, followups] = await Promise.all([
                    this.orm.searchRead(
                        "university.student",
                        [["advisor_id", "=", teacherId]],
                        ["name", "student_id", "gpa", "attendance_rate", "risk_level", "risk_reason", "current_semester_id"],
                        { limit: 20, order: "risk_level desc, gpa asc" }
                    ),
                    this.orm.searchRead(
                        "university.student.followup",
                        [["advisor_id", "=", teacherId], ["state", "in", ["pending", "in_progress"]]],
                        ["title", "student_id", "action_type", "date_deadline", "state", "description"],
                        { limit: 10, order: "date_deadline asc" }
                    ),
                ]);
                this.state.advisees = advisees;
                this.state.followups = followups;

                // 9. Fetch Attendance stats
                const [presentCount, absentCount, lateCount, excusedCount] = await Promise.all([
                    this.orm.searchCount("university.attendance", [["teacher_id", "=", teacherId], ["status", "=", "present"]]),
                    this.orm.searchCount("university.attendance", [["teacher_id", "=", teacherId], ["status", "=", "absent"]]),
                    this.orm.searchCount("university.attendance", [["teacher_id", "=", teacherId], ["status", "=", "late"]]),
                    this.orm.searchCount("university.attendance", [["teacher_id", "=", teacherId], ["status", "=", "permission"]]),
                ]);

                this.state.presentCount = presentCount;
                this.state.absentCount = absentCount;
                this.state.lateCount = lateCount;
                this.state.excusedCount = excusedCount;

                const total = presentCount + absentCount + lateCount + excusedCount;
                this.state.totalAttendance = total;
                this.state.hasAttendanceData = total > 0;
                this.state.attendanceRate = total > 0 ? Math.round((presentCount / total) * 100) : 0;

                // 10. Counts
                this.state.counts = {
                    schedule: this.state.scheduleSlots.length,
                    attendance: this.state.enrolledSections.length,
                    advising: adviseeCount,
                    assignments: this.state.pendingSubmissions.length,
                    lessonPlans: this.state.lessonPlans.length,
                    notices: this.state.noticeBoard.length,
                };
            }
        } catch (error) {
            this.state.error = error.message || "Unable to load your teacher dashboard.";
        } finally {
            this.state.loading = false;
            setTimeout(() => this.renderChart(), 50);
        }
    }

    renderChart() {
        if (!this.chartRef.el || !window.Chart) return;
        if (this.chartInstance) {
            this.chartInstance.destroy();
            this.chartInstance = null;
        }

        if (!this.state.hasAttendanceData) {
            return;
        }

        const present = Number(this.state.presentCount) || 0;
        const late = Number(this.state.lateCount) || 0;
        const absent = Number(this.state.absentCount) || 0;
        const excused = Number(this.state.excusedCount) || 0;

        this.chartInstance = new window.Chart(this.chartRef.el, {
            type: "doughnut",
            data: {
                labels: ["Present", "Late", "Absent", "Excused"],
                datasets: [{
                    data: [present, late, absent, excused],
                    backgroundColor: [
                        "#10b981", // Emerald
                        "#f59e0b", // Amber
                        "#ef4444", // Crimson
                        "#3b82f6", // Sky
                    ],
                    borderWidth: 2,
                    borderColor: "#ffffff",
                    hoverOffset: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "70%",
                plugins: {
                    centerText: {
                        label: "Total Logs",
                        valueColor: "#1e293b",
                        labelColor: "#64748b",
                    },
                    legend: {
                        position: "bottom",
                        labels: {
                            boxWidth: 10,
                            boxHeight: 10,
                            usePointStyle: true,
                            pointStyle: "circle",
                            padding: 12,
                            font: { size: 11, weight: "500", family: "system-ui, -apple-system, sans-serif" },
                        }
                    },
                    tooltip: {
                        backgroundColor: "#1e293b",
                        titleFont: { size: 12, weight: "600" },
                        bodyFont: { size: 11 },
                        padding: 8,
                        cornerRadius: 6,
                    }
                }
            },
            plugins: [doughnutCenterText]
        });
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
        if (tab === "attendance") {
            setTimeout(() => this.renderChart(), 50);
        }
    }

    async onSelectPreviewTeacher(ev) {
        const selectedId = parseInt(ev.target.value, 10);
        if (selectedId) {
            this.state.selectedPreviewTeacherId = selectedId;
            await this.loadData(selectedId);
        }
    }

    // Direct Actionable Attendance Trigger
    trackAttendanceForSlot(slot) {
        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        const sectionId = slot.section_id ? slot.section_id[0] : false;
        this.action.doAction("school_management.action_university_attendance_sheet", {
            additionalContext: {
                default_section_id: sectionId,
                section_id: sectionId,
                default_date: todayStr,
                date: todayStr,
            }
        });
    }

    trackAttendanceForSection(sectionId) {
        if (!sectionId) return;
        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        this.action.doAction("school_management.action_university_attendance_sheet", {
            additionalContext: {
                default_section_id: sectionId,
                section_id: sectionId,
                default_date: todayStr,
                date: todayStr,
            }
        });
    }

    openAttendanceSheet() {
        this.action.doAction("school_management.action_university_attendance_sheet");
    }

    openAttendanceRecords() {
        this.action.doAction("school_management.action_university_attendance");
    }

    openTimetable() {
        this.action.doAction("school_management.action_university_timetable_slot");
    }

    openMyTimetableCalendar() {
        this.action.doAction("school_management.action_university_timetable_slot", {
            additionalContext: {
                default_mode: "week",
                calendar_mode: "week",
            },
        });
    }

    openAssignments() {
        this.action.doAction("school_management.action_university_grade_assignment");
    }

    openSubmissions() {
        this.action.doAction("school_management.action_university_assignment_submission");
    }

    openSubmission(submissionId) {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "Assignment Submission Review",
                res_model: "university.assignment.submission",
                res_id: submissionId,
                views: [[false, "form"]],
                view_mode: "form",
                target: "new",
            },
            {
                onClose: async () => {
                    await this.loadData(this.state.teacher?.id);
                },
            }
        );
    }

    openAdvisees() {
        if (!this.state.teacher) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "My Advisees",
            res_model: "university.student",
            view_mode: "list,kanban,form",
            domain: [["advisor_id", "=", this.state.teacher.id]],
            context: { default_advisor_id: this.state.teacher.id },
        });
    }

    openAdvisingNotes() {
        if (!this.state.teacher) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Advising Notes",
            res_model: "university.student.advising.note",
            view_mode: "list,form",
            domain: [["advisor_id", "=", this.state.teacher.id]],
            context: { default_advisor_id: this.state.teacher.id },
        });
    }

    openFollowups() {
        if (!this.state.teacher) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Follow-up Actions",
            res_model: "university.student.followup",
            view_mode: "list,form",
            domain: [["advisor_id", "=", this.state.teacher.id]],
            context: { default_advisor_id: this.state.teacher.id },
        });
    }

    openStudentProfile(studentId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Student Profile",
            res_model: "university.student",
            res_id: studentId,
            views: [[false, "form"]],
            view_mode: "form",
            target: "new",
        });
    }

    openLessonPlans() {
        this.action.doAction("school_management.action_university_lesson_plan");
    }

    createLessonPlan() {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "New Lesson Plan",
                res_model: "university.lesson.plan",
                views: [[false, "form"]],
                view_mode: "form",
                target: "new",
                context: {
                    default_teacher_id: this.state.teacher?.id,
                },
            },
            {
                onClose: async () => {
                    await this.loadData(this.state.teacher?.id);
                },
            }
        );
    }

    openMyProfile() {
        if (!this.state.teacher) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "My Faculty Profile",
            res_model: "university.teacher",
            res_id: this.state.teacher.id,
            views: [[false, "form"]],
            view_mode: "form",
            context: { create: false, delete: false },
        });
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

    formatPosition(pos) {
        const positions = {
            professor: "Professor",
            associate_professor: "Associate Professor",
            assistant_professor: "Assistant Professor",
            lecturer: "Lecturer",
            instructor: "Instructor",
        };
        return positions[pos] || "Academic Faculty";
    }

    formatTime(dateTimeStr) {
        if (!dateTimeStr) return "";
        try {
            const d = new Date(dateTimeStr.replace(" ", "T") + "Z");
            return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
        } catch {
            return dateTimeStr.split(" ")[1]?.substring(0, 5) || dateTimeStr;
        }
    }

    formatDate(dateStr) {
        if (!dateStr) return "";
        try {
            const d = new Date(dateStr.replace(" ", "T"));
            const now = new Date();
            const opts = { month: "short", day: "numeric" };
            if (d.getFullYear() !== now.getFullYear()) {
                opts.year = "numeric";
            }
            return d.toLocaleDateString([], opts);
        } catch {
            return dateStr;
        }
    }
}

registry.category("actions").add("teacher_dashboard_shell", TeacherDashboardShell);

export default TeacherDashboardShell;
