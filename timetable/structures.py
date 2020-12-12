import logging
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import IO, List

logger = logging.getLogger(__name__)

__all__ = (
    'Course',
    'Curriculum',
    'Room',
    'Faculty',
    'Timetable',
)


@dataclass
class Course:
    name: str
    teacher: str
    students: int
    lectures: int
    min_working_days: int

    @classmethod
    def from_buffer(cls, buffer: IO):
        name, teacher, lectures, min_working_days, students = next(buffer).split()
        return cls(
            name=name,
            teacher=teacher,
            lectures=int(lectures),
            min_working_days=int(min_working_days),
            students=int(students),
        )


@dataclass
class Curriculum:
    name: str
    members: List[Course]  # ?

    @property
    def size(self):
        return len(self.members)

    @classmethod
    def from_buffer(cls, buffer: IO):
        name, _, *members = next(buffer).split()
        return cls(name=name, members=members)


@dataclass
class Room:
    name: str
    capacity: int

    @classmethod
    def from_buffer(cls, buffer: IO):
        name, capacity = next(buffer).split()
        return cls(name=name, capacity=int(capacity))


@dataclass
class Faculty:
    """
    Faculty(const std::string& instance);

    bool  Available(unsigned c, unsigned p) const { return availability[c][p]; }
    bool Conflict(unsigned c1, unsigned c2) const { return conflict[c1][c2]; }
    const Course& CourseVector(int i) const { return course_vect[i]; }
    const Room& RoomVector(int i) const { return room_vect[i]; }
    const Curriculum& CurriculaVector(int i) const { return curricula_vect[i]; }

    bool CurriculumMember(unsigned c, unsigned g) const;

    int RoomIndex(const std::string&) const;
    int CourseIndex(const std::string&) const;
    int CurriculumIndex(const std::string&) const;
    int PeriodIndex(const std::string&) const;
    """
    name: str
    rooms: int
    courses: int
    periods: int
    periods_per_day: int
    curricula: int

    course_vect: List[Course]
    room_vect: List[Room]
    curricula_vect: List[Curriculum]

    availability: List[List[bool]]  # defaults to true
    conflict: List[List[bool]]  # defaults to false

    # Added
    no_availability_py: defaultdict
    conflict_py: defaultdict
    course_names: List[str]
    room_names: List[str]

    MIN_WORKING_DAYS_COST: int = 5
    CURRICULUM_COMPACTNESS_COST: int = 2
    ROOM_STABILITY_COST: int = 1

    @property
    def days(self):
        return self.periods // self.periods_per_day

    @classmethod
    def from_stream(cls, buffer: IO):
        no_availability_py = defaultdict(bool)
        conflict_py = defaultdict(bool)

        def get_value(stream: IO, index: int = 1, separator: str = None) -> str:
            return next(stream).split(separator)[index]

        name = get_value(buffer)
        courses = int(get_value(buffer))
        rooms = int(get_value(buffer))
        days = int(get_value(buffer))
        periods_per_day = int(get_value(buffer))
        curricula = int(get_value(buffer))
        constraints = int(get_value(buffer))
        next(buffer)

        periods = days * periods_per_day
        availability = [[True for i in range(periods)] for i in range(courses)]
        conflict = [[False for i in range(courses)] for i in range(courses)]

        next(buffer)
        course_vect = []
        for i in range(courses):
            course_vect.append(Course.from_buffer(buffer))
        next(buffer)
        course_names = [c.name for c in course_vect]

        next(buffer)
        # ? location 0 of room_vect is not used (teaching in room 0 means NOT TEACHING)
        room_vect = [None]
        for i in range(rooms):
            room_vect.append(Room.from_buffer(buffer))
        room_names = [r.name if r else None for r in room_vect]
        next(buffer)

        next(buffer)
        curricula_vect = []
        for i in range(curricula):
            curricula_ = Curriculum.from_buffer(buffer)
            for c1, c2 in combinations(curricula_.members, 2):
                i1, i2 = course_names.index(c1), course_names.index(c2)
                conflict[i1][i2] = True
                conflict[i2][i1] = True
                conflict_py[(c1, c2)] = True
                conflict_py[(c2, c1)] = True
            curricula_vect.append(curricula_)
        next(buffer)

        next(buffer)
        for i in range(constraints):
            course_name, day_index, period_index = next(buffer).split()
            p = int(day_index) * periods_per_day + int(period_index)
            c = course_names.index(course_name)
            availability[c][p] = False
            no_availability_py[(course_name, p)] = True

        # Add same-teacher constraints
        for i1, i2 in combinations(range(len(course_vect)), 2):
            c1, c2 = course_vect[i1], course_vect[i2]
            if c1.teacher == c2.teacher:
                conflict[i1][i2] = True
                conflict[i2][i1] = True
                conflict_py[(c1.name, c2.name)] = True
                conflict_py[(c2.name, c1.name)] = True
        instance = cls(
            name=name,
            rooms=rooms,
            courses=courses,
            periods=periods,
            periods_per_day=periods_per_day,
            curricula=curricula,
            course_vect=course_vect,
            room_vect=room_vect,
            curricula_vect=curricula_vect,
            availability=availability,
            conflict=conflict,
            no_availability_py=no_availability_py,
            conflict_py=conflict_py,
            course_names=course_names,
            room_names=room_names,
        )
        return instance


@dataclass
class Timetable:
    """
    Timetable(const Faculty & f, const std::string file_name);
    // Inspect timetable
    unsigned operator()(unsigned i, unsigned j) const { return tt[i][j]; }
    unsigned& operator()(unsigned i, unsigned j) { return tt[i][j]; }
    // Inspect redundant data
    unsigned RoomLectures(unsigned i, unsigned j) const { return room_lectures[i][j]; }
    unsigned CurriculumPeriodLectures(unsigned i, unsigned j) const { return curriculum_period_lectures[i][j]; }
    unsigned CourseDailyLectures(unsigned i, unsigned j) const { return course_daily_lectures[i][j]; }
    unsigned WorkingDays(unsigned i) const { return working_days[i]; }
    unsigned UsedRoomsNo(unsigned i) const { return used_rooms[i].size(); }
    unsigned UsedRooms(unsigned i, unsigned j) const { return used_rooms[i][j]; }
    void InsertUsedRoom(unsigned i, unsigned j) { used_rooms[i].push_back(j); }
    unsigned Warnings() const { return warnings; }
    void UpdateRedundantData();
    """
    faculty: Faculty
    warnings: int
    timetable: List[List[int]]  # (courses X periods) timetable matrix

    # redundant data
    # number of lectures per room in the same period (should be 0 or 1)
    room_lectures: List[List[int]]
    # number of lectures per curriculum in the same period (should be 0 or 1)
    curriculum_period_lectures: List[List[int]]
    # number of lectures per course per day
    course_daily_lectures: List[List[int]]
    # number of days of lecture per course
    working_days: List[int]
    # rooms used for each lecture on the course
    used_rooms: List[List[int]]

    @classmethod
    def from_stream(cls, faculty: Faculty, buffer: IO):
        tt = [[0 for i in range(faculty.periods)] for i in range(faculty.courses)]
        room_lectures = [[0 for i in range(faculty.periods)] for i in range(faculty.rooms + 1)]
        curriculum_period_lectures = [[0 for i in range(faculty.periods)] for i in range(faculty.curricula)]
        course_daily_lectures = [[0 for i in range(faculty.days)] for i in range(faculty.courses)]
        working_days = [0 for i in range(faculty.courses)]
        used_rooms = [[] for i in range(faculty.courses)]  # ?

        warnings = 0
        for line in buffer:
            course_name, room_name, day, period = line.split()
            day, period = int(day), int(period)

            try:
                c = faculty.course_names.index(course_name)
            except ValueError:
                logger.warning('Nonexisting course %s (entry skipped)', course_name)
                warnings += 1
                continue
            try:
                r = faculty.room_names.index(room_name)
            except ValueError:
                logger.warning('Nonexisting room %s (entry skipped)', room_name)
                warnings += 1
                continue
            if day > faculty.days:
                logger.warning('Nonexisting day %d (entry skipped)', day)
                warnings += 1
                continue
            if period > faculty.periods_per_day:
                logger.warning('Nonexisting period %d (entry skipped)', period)
                warnings += 1
                continue
            p = day * faculty.periods_per_day + period

            if tt[c][p]:
                logger.warning('Repeated entry: %s (entry skipped)', line.strip())
                warnings += 1
                continue

            tt[c][p] = r

        instance = cls(
            faculty=faculty,
            timetable=tt,
            warnings=warnings,
            room_lectures=room_lectures,
            curriculum_period_lectures=curriculum_period_lectures,
            course_daily_lectures=course_daily_lectures,
            working_days=working_days,
            used_rooms=used_rooms,
        )
        instance.update_redundant_data()
        return instance

    def update_redundant_data(self):  # noqa: C901
        for c in range(self.faculty.courses):
            for p in range(self.faculty.periods):
                room = self.timetable[c][p]
                if room:
                    # 1
                    self.room_lectures[room][p] += 1

                    # 5
                    if room not in self.used_rooms[c]:
                        self.used_rooms[c].append(room)

        for ci, c in enumerate(self.faculty.course_vect):
            for gi, g in enumerate(self.faculty.curricula_vect):
                if c.name in g.members:
                    for p in range(self.faculty.periods):
                        if self.timetable[ci][p]:
                            # 2
                            self.curriculum_period_lectures[gi][p] += 1

        for c in range(self.faculty.courses):
            for d in range(self.faculty.days):
                for p_ in range(self.faculty.periods_per_day):
                    p = d * self.faculty.periods_per_day + p_
                    if self.timetable[c][p]:
                        # 3
                        self.course_daily_lectures[c][d] += 1
                if self.course_daily_lectures[c][d] > 0:
                    # 4
                    self.working_days[c] += 1
