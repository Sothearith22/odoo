/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class UniversitySchedule extends Component {
    static template = "school_management.UniversitySchedule";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        const actionContext = this.props.action?.context || this.props.context || {};
        const initialSectionId = actionContext.default_section_id || actionContext.filters?.section_id || "";
        const initialAcademicYearId = actionContext.default_academic_year_id || actionContext.filters?.academic_year_id || "";
        const initialSemesterId = actionContext.default_semester_id || actionContext.filters?.semester_id || "";

        const today = new Date();
        this.state = useState({
            currentDate: today,
            viewMode: "week", // 'week' | 'day' | 'resource'
            resourceType: "teacher", // 'teacher' | 'classroom'
            showSideTable: true,
            colorBy: "subject", // 'subject' | 'teacher' | 'classroom'
            loading: true,
            role: "student", // 'student' | 'teacher' | 'admin'
            unlinkedProfileMessage: "",
            slots: [],
            holidays: [],
            assignmentMarkers: [],
            examMarkers: [],
            nextClass: null,
            studentInfo: null,
            teacherInfo: null,
            weeklyTeachingHours: 0,
            hasExplicitlyClearedYear: false,
            filtersData: {
                academic_years: [],
                subjects: [],
                classrooms: [],
                sections: [],
                teachers: [],
                semesters: [],
                faculties: [],
                programs: [],
            },
            filters: {
                academic_year_id: initialAcademicYearId ? String(initialAcademicYearId) : "",
                faculty_id: "",
                program_id: "",
                semester_id: initialSemesterId ? String(initialSemesterId) : "",
                teacher_id: "",
                section_id: initialSectionId ? String(initialSectionId) : "",
                classroom_id: "",
                subject_id: "",
                session_type: "",
            },
            searchTerm: "",
            showGaps: true,
            showInactive: false,
            tableFilter: "available", // 'available' | 'all'
            selectedSlot: null,
            hoveredSlotId: null,
            activeNoteInput: "",
            isRescheduling: false,
            rescheduleForm: {
                date: "",
                start_time: "09:00",
                end_time: "10:30",
                classroom_id: "",
            },
            currentTime: new Date(),
        });

        this.timeInterval = null;

        onWillStart(async () => {
            await this.loadScheduleData();
        });

        onMounted(() => {
            this.timeInterval = setInterval(() => {
                this.state.currentTime = new Date();
            }, 60000);
            this.scrollToInitialTime();
        });

        onWillUnmount(() => {
            if (this.timeInterval) {
                clearInterval(this.timeInterval);
            }
        });
    }

    scrollToInitialTime() {
        setTimeout(() => {
            const scrollBody = document.querySelector(".o_grid_scroll_body");
            if (scrollBody) {
                // Scroll slightly so 08:00 is comfortably in view
                scrollBody.scrollTop = 50;
            }
        }, 100);
    }

    // =========================================================================
    // Date Helpers & Navigation
    // =========================================================================

    formatDateISO(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, "0");
        const d = String(date.getDate()).padStart(2, "0");
        return `${y}-${m}-${d}`;
    }

    getBoundsForView() {
        const base = new Date(this.state.currentDate);
        if (this.state.viewMode === "day") {
            const dateStr = this.formatDateISO(base);
            return { start: dateStr, end: dateStr };
        } else {
            // Week / Resource (Mon - Sun)
            const dayOfWeek = base.getDay(); // 0 is Sun, 1 is Mon
            const distanceToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
            const monday = new Date(base);
            monday.setDate(base.getDate() + distanceToMonday);

            const sunday = new Date(monday);
            sunday.setDate(monday.getDate() + 6);

            return {
                start: this.formatDateISO(monday),
                end: this.formatDateISO(sunday),
            };
        }
    }

    get headerTitle() {
        const base = this.state.currentDate;
        if (this.state.viewMode === "day") {
            return base.toLocaleDateString(undefined, {
                weekday: "long",
                month: "short",
                day: "numeric",
                year: "numeric",
            });
        } else {
            const bounds = this.getBoundsForView();
            const sParts = bounds.start.split("-");
            const eParts = bounds.end.split("-");
            const sDate = new Date(sParts[0], sParts[1] - 1, sParts[2]);
            const eDate = new Date(eParts[0], eParts[1] - 1, eParts[2]);
            return `${sDate.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })} – ${eDate.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" })}`;
        }
    }

    get visibleSemesters() {
        const allSemesters = this.state.filtersData.semesters || [];
        if (!this.state.filters.academic_year_id) {
            return allSemesters;
        }
        const yearId = parseInt(this.state.filters.academic_year_id, 10);
        return allSemesters.filter((s) => {
            const semYearId = Array.isArray(s.academic_year_id) ? s.academic_year_id[0] : s.academic_year_id;
            return semYearId === yearId;
        });
    }

    get currentTermLabel() {
        const yearRec = (this.state.filtersData.academic_years || []).find((y) => String(y.id) === String(this.state.filters.academic_year_id));
        const semRec = (this.state.filtersData.semesters || []).find((s) => String(s.id) === String(this.state.filters.semester_id));
        if (yearRec && semRec) {
            return `${yearRec.name} • ${semRec.name}`;
        } else if (yearRec) {
            return `${yearRec.name} (Academic Session)`;
        } else if (semRec) {
            return semRec.name;
        }
        const d = this.state.currentDate;
        const year = d.getFullYear();
        const month = d.getMonth() + 1;
        if (month >= 8 && month <= 12) {
            return `${year} Fall Term (Sept – Dec)`;
        } else if (month >= 1 && month <= 5) {
            return `${year} Spring Term (Jan – May)`;
        } else {
            return `${year} Summer Term (Jun – Aug)`;
        }
    }

    async prev() {
        const d = new Date(this.state.currentDate);
        if (this.state.viewMode === "day") {
            d.setDate(d.getDate() - 1);
        } else {
            d.setDate(d.getDate() - 7);
        }
        this.state.currentDate = d;
        await this.loadScheduleData();
    }

    async next() {
        const d = new Date(this.state.currentDate);
        if (this.state.viewMode === "day") {
            d.setDate(d.getDate() + 1);
        } else {
            d.setDate(d.getDate() + 7);
        }
        this.state.currentDate = d;
        await this.loadScheduleData();
    }

    async today() {
        this.state.currentDate = new Date();
        await this.loadScheduleData();
    }

    async setViewMode(mode) {
        this.state.viewMode = mode;
        if (mode === "resource") {
            this.state.showSideTable = false;
        } else {
            this.state.showSideTable = true;
        }
        await this.loadScheduleData();
    }

    setResourceType(type) {
        this.state.resourceType = type;
    }

    toggleSideTable() {
        this.state.showSideTable = !this.state.showSideTable;
    }

    setColorBy(colorBy) {
        this.state.colorBy = colorBy;
    }

    // =========================================================================
    // Data Loading & Filtering
    // =========================================================================

    async loadScheduleData() {
        this.state.loading = true;
        try {
            const bounds = this.getBoundsForView();
            const res = await this.orm.call(
                "university.timetable.slot",
                "get_schedule_view_data",
                [bounds.start, bounds.end, this.state.filters]
            );

            if (res.error === "no_linked_profile") {
                this.state.unlinkedProfileMessage = res.message || "Profile not linked.";
            } else {
                this.state.unlinkedProfileMessage = "";
            }

            this.state.role = res.role || "student";
            this.state.slots = res.slots || [];
            this.state.holidays = res.holidays || [];
            this.state.assignmentMarkers = res.assignment_markers || [];
            this.state.examMarkers = res.exam_markers || [];
            this.state.nextClass = res.next_class || null;
            this.state.studentInfo = res.student_info || null;
            this.state.teacherInfo = res.teacher_info || null;
            this.state.weeklyTeachingHours = res.weekly_teaching_hours || 0;
            this.state.filtersData = res.filters_data || {
                academic_years: [],
                subjects: [],
                classrooms: [],
                sections: [],
                teachers: [],
                semesters: [],
                faculties: [],
                programs: [],
            };

            if (!this.state.filters.academic_year_id && this.state.filtersData.academic_years?.length && !this.state.hasExplicitlyClearedYear) {
                const currentYear = this.state.filtersData.academic_years.find((y) => y.current) || this.state.filtersData.academic_years[0];
                if (currentYear) {
                    this.state.filters.academic_year_id = String(currentYear.id);
                }
            }

            if (!this.state.filters.semester_id && this.visibleSemesters?.length) {
                const activeSem = this.visibleSemesters.find((s) => s.is_active) || this.visibleSemesters[0];
                if (activeSem) {
                    this.state.filters.semester_id = String(activeSem.id);
                }
            }

            if (this.state.selectedSlot) {
                const refreshed = this.state.slots.find((s) => s.id === this.state.selectedSlot.id);
                if (refreshed) {
                    this.state.selectedSlot = refreshed;
                    this.state.activeNoteInput = refreshed.notes || "";
                }
            }
        } catch (err) {
            console.error("Error loading schedule data:", err);
            this.notification.add("Could not load schedule data. Please try again.", {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    async onFilterChange(field, ev) {
        this.state.filters[field] = ev.target.value;
        await this.loadScheduleData();
    }

    async onAcademicYearChange(ev) {
        const yearId = ev.target.value;
        this.state.filters.academic_year_id = yearId;
        if (!yearId) {
            this.state.hasExplicitlyClearedYear = true;
        } else {
            this.state.hasExplicitlyClearedYear = false;
        }

        // Reset semester if it doesn't belong to the newly selected academic year
        if (yearId && this.state.filters.semester_id) {
            const matches = this.visibleSemesters.some((s) => String(s.id) === String(this.state.filters.semester_id));
            if (!matches) {
                const firstSem = this.visibleSemesters[0];
                this.state.filters.semester_id = firstSem ? String(firstSem.id) : "";
            }
        }

        // If academic year defines date range, navigate to its start date if view date is out of bounds
        const yearRec = (this.state.filtersData.academic_years || []).find((y) => String(y.id) === String(yearId));
        if (yearRec && yearRec.date_start) {
            const startDt = new Date(yearRec.date_start + "T00:00:00");
            const endDt = yearRec.date_end ? new Date(yearRec.date_end + "T23:59:59") : null;
            const current = new Date(this.state.currentDate);
            if (current < startDt || (endDt && current > endDt)) {
                this.state.currentDate = startDt;
            }
        }

        await this.loadScheduleData();
    }

    async onTermChange(ev) {
        const semesterId = ev.target.value;
        this.state.filters.semester_id = semesterId;
        const sem = (this.state.filtersData.semesters || []).find((s) => String(s.id) === String(semesterId));
        if (sem) {
            if (sem.academic_year_id && !this.state.filters.academic_year_id) {
                const semYearId = Array.isArray(sem.academic_year_id) ? sem.academic_year_id[0] : sem.academic_year_id;
                this.state.filters.academic_year_id = String(semYearId);
            }
            if (sem.date_start) {
                const startDt = new Date(sem.date_start + "T00:00:00");
                const endDt = sem.date_end ? new Date(sem.date_end + "T23:59:59") : null;
                const current = new Date(this.state.currentDate);
                if (current < startDt || (endDt && current > endDt)) {
                    this.state.currentDate = startDt;
                }
            }
        }
        await this.loadScheduleData();
    }

    async clearAllFilters() {
        const currentYear = this.state.filters.academic_year_id;
        const currentSem = this.state.filters.semester_id;
        this.state.filters = {
            academic_year_id: currentYear || "",
            faculty_id: "",
            program_id: "",
            semester_id: currentSem || "",
            teacher_id: "",
            section_id: "",
            classroom_id: "",
            subject_id: "",
            session_type: "",
        };
        this.state.searchTerm = "";
        await this.loadScheduleData();
    }

    get hasActiveFilters() {
        const f = this.state.filters;
        return Boolean(
            this.state.searchTerm ||
            f.section_id ||
            f.session_type ||
            f.teacher_id ||
            f.classroom_id ||
            f.faculty_id ||
            f.program_id ||
            f.subject_id
        );
    }

    onSearchInput(ev) {
        this.state.searchTerm = ev.target.value.toLowerCase();
    }

    toggleShowGaps() {
        this.state.showGaps = !this.state.showGaps;
    }

    toggleShowInactive() {
        this.state.showInactive = !this.state.showInactive;
    }

    setTableFilter(filter) {
        this.state.tableFilter = filter;
    }

    // =========================================================================
    // KPI Stat Computations
    // =========================================================================

    get filteredSlots() {
        let list = this.state.slots;
        if (!this.state.showInactive) {
            list = list.filter((s) => s.state !== "cancelled" && s.status !== "cancelled");
        }
        if (this.state.searchTerm) {
            const term = this.state.searchTerm;
            list = list.filter((s) =>
                (s.subject_name && s.subject_name.toLowerCase().includes(term)) ||
                (s.subject_code && s.subject_code.toLowerCase().includes(term)) ||
                (s.section_name && s.section_name.toLowerCase().includes(term)) ||
                (s.teacher_name && s.teacher_name.toLowerCase().includes(term)) ||
                (s.classroom_name && s.classroom_name.toLowerCase().includes(term))
            );
        }
        return list;
    }

    get kpiClassesCount() {
        return this.filteredSlots.length;
    }

    get kpiEnrolledCount() {
        return this.filteredSlots.reduce((acc, s) => acc + (s.enrolled_student_count || 0), 0);
    }

    get kpiCapacityCount() {
        return this.filteredSlots.reduce((acc, s) => acc + (s.room_capacity || 0), 0);
    }

    get kpiConflictCount() {
        return this.filteredSlots.filter((s) => Boolean(s.conflict || s.has_conflict)).length;
    }

    get kpiEnrolledPercentage() {
        const cap = this.kpiCapacityCount;
        if (!cap) return 0;
        return Math.min(100, Math.round((this.kpiEnrolledCount / cap) * 100));
    }

    // =========================================================================
    // Right Table: Classes With Available Spaces
    // =========================================================================

    get tableClasses() {
        const slots = this.filteredSlots;
        if (this.state.tableFilter === "available") {
            return slots.filter((s) => (s.room_capacity > 0 && s.enrolled_student_count < s.room_capacity));
        }
        return slots;
    }

    get availableSpacesCount() {
        return this.filteredSlots.filter((s) => (s.room_capacity > 0 && s.enrolled_student_count < s.room_capacity)).length;
    }

    // =========================================================================
    // Week Grid Layout & Time Calculation
    // =========================================================================

    get gridStartHour() {
        return 7.0;
    }

    get gridEndHour() {
        return 22.0;
    }

    get timeHours() {
        // Time bounds 07:00 to 22:00 (15 hour rows: 7..21)
        const hours = [];
        for (let h = 7; h <= 21; h++) {
            hours.push(h);
        }
        return hours;
    }

    formatHourLabel(hour) {
        return `${String(hour).padStart(2, "0")}:00`;
    }

    _assignOverlapLayout(daySlots) {
        if (!daySlots || !daySlots.length) return;

        // Sort by start time ascending, then duration descending
        const sorted = [...daySlots].sort((a, b) => {
            const startA = a.start_hour_decimal != null ? a.start_hour_decimal : 8.0;
            const startB = b.start_hour_decimal != null ? b.start_hour_decimal : 8.0;
            if (startA !== startB) {
                return startA - startB;
            }
            const durA = (a.end_hour_decimal || (startA + 1.0)) - startA;
            const durB = (b.end_hour_decimal || (startB + 1.0)) - startB;
            return durB - durA;
        });

        // Group into connected overlap clusters
        const clusters = [];
        let currentCluster = [];
        let clusterEnd = -1;

        for (const slot of sorted) {
            const start = slot.start_hour_decimal != null ? slot.start_hour_decimal : 8.0;
            const end = slot.end_hour_decimal != null ? slot.end_hour_decimal : (start + 1.0);

            if (currentCluster.length === 0 || start < clusterEnd) {
                currentCluster.push(slot);
                clusterEnd = Math.max(clusterEnd, end);
            } else {
                clusters.push(currentCluster);
                currentCluster = [slot];
                clusterEnd = end;
            }
        }
        if (currentCluster.length > 0) {
            clusters.push(currentCluster);
        }

        // For each cluster, greedily assign column tracks
        for (const cluster of clusters) {
            const trackEndTimes = [];
            for (const slot of cluster) {
                const start = slot.start_hour_decimal != null ? slot.start_hour_decimal : 8.0;
                const end = slot.end_hour_decimal != null ? slot.end_hour_decimal : (start + 1.0);

                let placedCol = -1;
                for (let i = 0; i < trackEndTimes.length; i++) {
                    if (start >= trackEndTimes[i]) {
                        placedCol = i;
                        trackEndTimes[i] = end;
                        break;
                    }
                }
                if (placedCol === -1) {
                    placedCol = trackEndTimes.length;
                    trackEndTimes.push(end);
                }
                slot._colIndex = placedCol;
            }
            const totalCols = Math.max(1, trackEndTimes.length);
            for (const slot of cluster) {
                slot._totalCols = totalCols;
            }
        }
    }

    formatHolidayTooltip(holiday, dateObj) {
        if (!holiday) return "";
        const options = { year: "numeric", month: "long", day: "numeric" };
        const formattedDate = dateObj.toLocaleDateString("en-US", options);
        return `Public Holiday\nHoliday: ${holiday.name}\nDate: ${formattedDate}\nClasses should not be scheduled on this date.`;
    }

    get weekDays() {
        const bounds = this.getBoundsForView();
        const start = new Date(bounds.start + "T00:00:00");
        const days = [];
        const todayStr = this.formatDateISO(new Date());

        const numDays = this.state.viewMode === "day" ? 1 : 7;
        const currentRef = this.state.viewMode === "day" ? new Date(this.state.currentDate) : start;

        for (let i = 0; i < numDays; i++) {
            const d = new Date(currentRef);
            if (this.state.viewMode !== "day") {
                d.setDate(start.getDate() + i);
            }
            const dateStr = this.formatDateISO(d);
            const isToday = dateStr === todayStr;

            const daySlots = this.filteredSlots
                .filter((s) => s.date_str === dateStr)
                .sort((a, b) => (a.start_hour_decimal > b.start_hour_decimal ? 1 : -1));

            this._assignOverlapLayout(daySlots);

            // Compare dates using actual date value (ISO YYYY-MM-DD), not formatted text
            const dayHoliday = (this.state.holidays || []).find((h) => {
                const hStart = h.date_start || h.date_from;
                const hEnd = h.date_end || h.date_to || hStart;
                if (!hStart || !hEnd) return false;
                const isPublic = !h.holiday_type || h.holiday_type === "public";
                return isPublic && hStart <= dateStr && dateStr <= hEnd;
            });

            const holidayTooltip = dayHoliday ? this.formatHolidayTooltip(dayHoliday, d) : "";

            days.push({
                date: d,
                dateStr: dateStr,
                dayName: d.toLocaleDateString(undefined, { weekday: "short" }),
                fullDayName: d.toLocaleDateString(undefined, { weekday: "long" }),
                dayNumber: d.getDate(),
                formattedDate: d.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
                isToday: isToday,
                slots: daySlots,
                hasSlots: daySlots.length > 0,
                holiday: dayHoliday || null,
                holidayTooltip: holidayTooltip,
            });
        }
        return days;
    }

    get resourceTeachers() {
        const teachers = this.state.filtersData.teachers || [];
        const slots = this.filteredSlots;
        const days = this.weekDays;
        const selectedTeacherId = this.state.filters.teacher_id ? parseInt(this.state.filters.teacher_id) : null;
        const myTeacherId = this.state.teacherInfo ? this.state.teacherInfo.id : null;

        let list = teachers;
        if (selectedTeacherId) {
            list = list.filter((t) => t.id === selectedTeacherId);
        }

        const mapped = list.map((teacher) => {
            const teacherSlots = slots.filter((s) => s.teacher_id === teacher.id);
            const dayMap = {};
            days.forEach((day) => {
                dayMap[day.dateStr] = teacherSlots
                    .filter((s) => s.date_str === day.dateStr)
                    .sort((a, b) => (a.start_hour_decimal > b.start_hour_decimal ? 1 : -1));
            });
            const totalHours = teacherSlots.reduce((acc, s) => acc + (s.duration_hours || 0), 0);

            let positionStr = "";
            if (teacher.position) {
                positionStr = teacher.position.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
            }
            let deptStr = "";
            if (teacher.department_id && Array.isArray(teacher.department_id)) {
                deptStr = teacher.department_id[1];
            } else if (teacher.department_name) {
                deptStr = teacher.department_name;
            }

            const initials = (teacher.name || "T")
                .split(" ")
                .filter(Boolean)
                .map((w) => w[0])
                .slice(0, 2)
                .join("")
                .toUpperCase();

            const isMe = Boolean(myTeacherId && myTeacherId === teacher.id);

            return {
                id: teacher.id,
                name: teacher.name,
                title: teacher.title || "",
                position: positionStr,
                department: deptStr,
                email: teacher.email || "",
                initials: initials,
                isMe: isMe,
                slots: teacherSlots,
                dayMap: dayMap,
                totalSlots: teacherSlots.length,
                totalHours: Math.round(totalHours * 10) / 10,
            };
        });

        return mapped.sort((a, b) => {
            if (a.isMe) return -1;
            if (b.isMe) return 1;
            if (a.totalSlots > 0 && b.totalSlots === 0) return -1;
            if (b.totalSlots > 0 && a.totalSlots === 0) return 1;
            return a.name.localeCompare(b.name);
        });
    }

    get resourceClassrooms() {
        const rooms = this.state.filtersData.classrooms || [];
        const slots = this.filteredSlots;
        const days = this.weekDays;
        const selectedRoomId = this.state.filters.classroom_id ? parseInt(this.state.filters.classroom_id) : null;

        let list = rooms;
        if (selectedRoomId) {
            list = list.filter((r) => r.id === selectedRoomId);
        }

        const mapped = list.map((room) => {
            const roomSlots = slots.filter((s) => s.classroom_id === room.id);
            const dayMap = {};
            days.forEach((day) => {
                dayMap[day.dateStr] = roomSlots
                    .filter((s) => s.date_str === day.dateStr)
                    .sort((a, b) => (a.start_hour_decimal > b.start_hour_decimal ? 1 : -1));
            });
            const totalHours = roomSlots.reduce((acc, s) => acc + (s.duration_hours || 0), 0);
            return {
                id: room.id,
                name: room.name,
                building: room.building || "Campus",
                capacity: room.capacity || 0,
                room_type: room.room_type || "classroom",
                slots: roomSlots,
                dayMap: dayMap,
                totalSlots: roomSlots.length,
                totalHours: Math.round(totalHours * 10) / 10,
            };
        });

        return mapped.sort((a, b) => {
            if (a.totalSlots > 0 && b.totalSlots === 0) return -1;
            if (b.totalSlots > 0 && a.totalSlots === 0) return 1;
            return a.name.localeCompare(b.name);
        });
    }

    get totalTeacherHoursThisWeek() {
        const total = this.filteredSlots.reduce((acc, s) => acc + (s.duration_hours || 0), 0);
        return Math.round(total * 10) / 10;
    }

    get currentTimeMarkerPosition() {
        const now = this.state.currentTime;
        const hour = now.getHours();
        const minute = now.getMinutes();
        const decimal = hour + minute / 60.0;
        const startHour = this.gridStartHour;
        const endHour = this.gridEndHour;
        if (decimal < startHour || decimal > endHour) {
            return null;
        }
        return Math.round((decimal - startHour) * 60);
    }

    get currentTimeFormatted() {
        return this.state.currentTime.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    getSlotStyle(slot) {
        const startHour = this.gridStartHour;
        const endHour = this.gridEndHour;
        const startH = Math.max(startHour, Math.min(endHour, slot.start_hour_decimal != null ? slot.start_hour_decimal : 8.0));
        const endH = Math.max(startH + 0.25, Math.min(endHour, slot.end_hour_decimal != null ? slot.end_hour_decimal : (startH + 1.0)));
        const durationHours = Math.max(0.4, endH - startH);

        const topPx = Math.round((startH - startHour) * 60);
        const heightPx = Math.max(28, Math.round(durationHours * 60 - 3));

        const totalCols = slot._totalCols || 1;
        const colIndex = slot._colIndex || 0;

        if (totalCols > 1) {
            const colWidth = 100 / totalCols;
            const leftPercent = colIndex * colWidth;
            return `top: ${topPx}px; height: ${heightPx}px; width: calc(${colWidth}% - 4px); left: calc(${leftPercent}% + 2px);`;
        }

        return `top: ${topPx}px; height: ${heightPx}px; left: 3px; width: calc(100% - 6px);`;
    }

    getSlotDayShort(slot) {
        try {
            const [y, m, d] = slot.date_str.split("-").map((v) => parseInt(v, 10));
            const dateObj = new Date(y, m - 1, d);
            return dateObj.toLocaleDateString(undefined, { weekday: "short" });
        } catch {
            return "Day";
        }
    }

    getSlotColorClass(slot) {
        if (slot.session_type === "lab") return "o_slot_palette_teal";
        if (slot.session_type === "exam") return "o_slot_palette_amber";

        const palettes = [
            "o_slot_palette_purple",
            "o_slot_palette_indigo",
            "o_slot_palette_sapphire",
            "o_slot_palette_emerald",
        ];

        let seed = slot.subject_id || 0;
        if (this.state.colorBy === "teacher") {
            seed = slot.teacher_id || 0;
        } else if (this.state.colorBy === "classroom") {
            seed = slot.classroom_id || 0;
        }
        return palettes[Math.abs(seed) % palettes.length];
    }

    getStatusBadgeClass(status) {
        switch (status) {
            case "ongoing":
                return "badge bg-warning text-dark border";
            case "completed":
                return "badge bg-success-subtle text-success border border-success-subtle";
            case "cancelled":
                return "badge bg-danger-subtle text-danger border border-danger-subtle";
            case "upcoming":
            default:
                return "badge bg-primary-subtle text-primary border border-primary-subtle";
        }
    }

    // =========================================================================
    // Interactive Selection & Offcanvas
    // =========================================================================

    openSlotSidePanel(slot) {
        this.state.selectedSlot = slot;
        this.state.activeNoteInput = slot.notes || "";
        this.state.isRescheduling = false;
    }

    openSlotById(slotId) {
        const slot = this.state.slots.find((s) => s.id === slotId);
        if (slot) {
            this.openSlotSidePanel(slot);
        }
    }

    closeSlotSidePanel() {
        this.state.selectedSlot = null;
        this.state.isRescheduling = false;
    }

    onHoverSlot(slotId) {
        this.state.hoveredSlotId = slotId;
    }

    onLeaveSlot() {
        this.state.hoveredSlotId = null;
    }

    // =========================================================================
    // Actions: + Add Class, Attendance, Notes, Materials
    // =========================================================================

    async addClass(options = {}) {
        if (this.state.role !== "admin") return;
        const ctx = {
            default_academic_year_id: this.state.filters.academic_year_id ? parseInt(this.state.filters.academic_year_id) : false,
            default_semester_id: this.state.filters.semester_id ? parseInt(this.state.filters.semester_id) : false,
        };
        if (options && options.teacher_id) {
            ctx.default_teacher_id = parseInt(options.teacher_id);
        } else if (this.state.filters.teacher_id) {
            ctx.default_teacher_id = parseInt(this.state.filters.teacher_id);
        }
        if (options && options.classroom_id) {
            ctx.default_classroom_id = parseInt(options.classroom_id);
        } else if (this.state.filters.classroom_id) {
            ctx.default_classroom_id = parseInt(this.state.filters.classroom_id);
        }
        if (options && options.dateStr) {
            const holiday = (this.state.holidays || []).find((h) => {
                const s = h.date_start || h.date_from;
                const e = h.date_end || h.date_to || s;
                return Boolean(s && e && s <= options.dateStr && options.dateStr <= e && (!h.holiday_type || h.holiday_type === "public"));
            });
            if (holiday) {
                this.notification.add(
                    `Warning: ${options.dateStr} is a public holiday (${holiday.name}). Classes should not be scheduled on this date.`,
                    { type: "warning" }
                );
            }
            ctx.default_start_time = `${options.dateStr} 08:00:00`;
            ctx.default_end_time = `${options.dateStr} 10:00:00`;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Schedule Class Session",
            res_model: "university.timetable.slot",
            views: [[false, "form"]],
            view_mode: "form",
            target: "new",
            context: ctx,
        }, {
            onClose: async () => {
                await this.loadScheduleData();
            },
        });
    }

    async editSlot(slot) {
        if (!slot) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Edit Schedule - " + (slot.subject_name || slot.name),
            res_model: "university.timetable.slot",
            res_id: slot.id,
            views: [[false, "form"]],
            view_mode: "form",
            target: "new",
        }, {
            onClose: async () => {
                await this.loadScheduleData();
            },
        });
    }

    async deleteSlot(slot) {
        if (this.state.role !== "admin" || !slot) return;
        if (confirm(`Are you sure you want to delete schedule '${slot.name || slot.subject_name}'?`)) {
            try {
                await this.orm.unlink("university.timetable.slot", [slot.id]);
                this.closeSlotSidePanel();
                this.notification.add("Schedule session deleted successfully.", { type: "success" });
                await this.loadScheduleData();
            } catch (err) {
                this.notification.add(err.message || "Failed to delete schedule.", { type: "danger" });
            }
        }
    }

    async publishSlot(slot) {
        if (!slot) return;
        try {
            await this.orm.call("university.timetable.slot", "action_publish", [[slot.id]]);
            this.notification.add("Schedule published successfully.", { type: "success" });
            await this.loadScheduleData();
        } catch (err) {
            this.notification.add(err.message || "Failed to publish schedule.", { type: "danger" });
        }
    }

    async unpublishSlot(slot) {
        if (!slot) return;
        try {
            await this.orm.call("university.timetable.slot", "action_set_draft", [[slot.id]]);
            this.notification.add("Schedule set to draft.", { type: "info" });
            await this.loadScheduleData();
        } catch (err) {
            this.notification.add(err.message || "Failed to set schedule to draft.", { type: "danger" });
        }
    }

    async takeAttendance(slot) {
        try {
            const action = await this.orm.call(
                "university.timetable.slot",
                "action_track_attendance",
                [[slot.id]]
            );
            if (action) {
                await this.action.doAction(action);
            }
        } catch (err) {
            this.notification.add(err.message || "Failed to launch attendance tracker.", {
                type: "danger",
            });
        }
    }

    async saveSlotNotes() {
        if (!this.state.selectedSlot) return;
        try {
            await this.orm.call(
                "university.timetable.slot",
                "action_save_notes",
                [[this.state.selectedSlot.id], this.state.activeNoteInput]
            );
            this.state.selectedSlot.notes = this.state.activeNoteInput;
            this.notification.add("Session notes saved.", {
                type: "success",
            });
        } catch (err) {
            this.notification.add(err.message || "Could not save notes.", {
                type: "danger",
            });
        }
    }

    async openMaterials(slot) {
        try {
            const action = await this.orm.call(
                "university.timetable.slot",
                "action_upload_material",
                [[slot.id]]
            );
            if (action) {
                await this.action.doAction(action);
            }
        } catch (err) {
            this.notification.add("Could not open course materials.", { type: "danger" });
        }
    }

    async openAssignments(slot) {
        try {
            const action = await this.orm.call(
                "university.timetable.slot",
                "action_view_assignments",
                [[slot.id]]
            );
            if (action) {
                await this.action.doAction(action);
            }
        } catch (err) {
            this.notification.add("Could not open course assignments.", { type: "danger" });
        }
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
        });
    }

    // =========================================================================
    // Export Functions: iCal, CSV/Excel, PDF
    // =========================================================================

    exportICal() {
        const slots = this.filteredSlots;
        if (!slots.length) {
            this.notification.add("No schedule sessions to export.", { type: "warning" });
            return;
        }
        const formatDT = (dtStr) => {
            if (!dtStr) return "";
            return dtStr.replace(/[-:]/g, "").replace(" ", "T") + "Z";
        };

        const ics = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//University Management//Timetable//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ];
        for (const s of slots) {
            ics.push("BEGIN:VEVENT");
            ics.push(`UID:session-${s.id}@university.edu`);
            ics.push(`DTSTAMP:${formatDT(new Date().toISOString())}`);
            ics.push(`DTSTART:${formatDT(s.start || s.start_time)}`);
            ics.push(`DTEND:${formatDT(s.end || s.end_time)}`);
            ics.push(`SUMMARY:${(s.subject_name || s.subject || "Class")} (${s.section_name || s.section_code || "Section"})`);
            ics.push(`LOCATION:${s.classroom_name || s.room || "Room TBA"}`);
            ics.push(`DESCRIPTION:Instructor: ${s.teacher_name || s.teacher || "TBA"}\\nStatus: ${s.status || "Scheduled"}`);
            ics.push("END:VEVENT");
        }
        ics.push("END:VCALENDAR");

        const blob = new Blob([ics.join("\r\n")], { type: "text/calendar;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", `university_schedule_${this.formatDateISO(new Date())}.ics`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        this.notification.add("iCal calendar exported successfully.", { type: "success" });
    }

    exportExcel() {
        const slots = this.filteredSlots;
        if (!slots.length) {
            this.notification.add("No schedule sessions to export.", { type: "warning" });
            return;
        }
        const headers = ["Date", "Start Time", "End Time", "Subject", "Section", "Room", "Teacher", "Type", "Enrolled", "Capacity", "Status"];
        const rows = slots.map((s) => [
            s.date_str || "",
            s.start_time_str || "",
            s.end_time_str || "",
            `"${(s.subject_name || s.subject || "").replace(/"/g, '""')}"`,
            `"${(s.section_name || s.section_code || "").replace(/"/g, '""')}"`,
            `"${(s.classroom_name || s.room || "").replace(/"/g, '""')}"`,
            `"${(s.teacher_name || s.teacher || "").replace(/"/g, '""')}"`,
            s.session_type || "lecture",
            s.enrolled_student_count || 0,
            s.room_capacity || 0,
            s.status || "upcoming",
        ]);
        const csvContent = "\uFEFF" + [headers.join(","), ...rows.map((r) => r.join(","))].join("\r\n");
        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", `university_schedule_${this.formatDateISO(new Date())}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        this.notification.add("Schedule exported to CSV/Excel successfully.", { type: "success" });
    }

    exportPDF() {
        window.print();
    }
}

registry.category("actions").add("university_schedule_view", UniversitySchedule);
export default UniversitySchedule;
