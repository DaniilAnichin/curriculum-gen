import logging
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from itertools import combinations
from typing import IO, List, Set

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
    conflict: List[Set[int]]  # defaults to false

    # Added
    no_availability_py: defaultdict
    course_names: List[str]

    MIN_WORKING_DAYS_COST: int = 5
    CURRICULUM_COMPACTNESS_COST: int = 2
    ROOM_STABILITY_COST: int = 1

    @property
    def days(self):
        return self.periods // self.periods_per_day

    @classmethod
    def from_stream(cls, buffer: IO):
        no_availability_py = defaultdict(bool)

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
        conflict = [set() for i in range(courses)]

        next(buffer)
        course_vect = [Course.from_buffer(buffer) for _ in range(courses)]
        next(buffer)
        course_names = [c.name for c in course_vect]

        next(buffer)
        room_vect = [Room.from_buffer(buffer) for _ in range(rooms)]
        next(buffer)

        next(buffer)
        curricula_vect = []
        for i in range(curricula):
            curricula_ = Curriculum.from_buffer(buffer)
            for c1, c2 in combinations(curricula_.members, 2):
                i1, i2 = course_names.index(c1), course_names.index(c2)
                conflict[i1].add(i2)
                conflict[i2].add(i1)
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
                conflict[i1].add(i2)
                conflict[i2].add(i1)
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
            course_names=course_names,
        )
        return instance


@dataclass
class Timetable:
    faculty: Faculty
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

    def __eq__(self, other):
        if not isinstance(other, Timetable):
            return NotImplemented
        return self.faculty is other.faculty and self.timetable == other.timetable

    @classmethod
    def from_faculty(cls, faculty: Faculty) -> 'Timetable':
        tt = [[0 for i in range(faculty.periods)] for i in range(faculty.courses)]
        room_lectures = [[0 for i in range(faculty.periods)] for i in range(faculty.rooms + 1)]
        curriculum_period_lectures = [[0 for i in range(faculty.periods)] for i in range(faculty.curricula)]
        course_daily_lectures = [[0 for i in range(faculty.days)] for i in range(faculty.courses)]
        working_days = [0 for i in range(faculty.courses)]
        used_rooms: List[List[int]] = [[] for i in range(faculty.courses)]  # ?

        instance = cls(
            faculty=faculty,
            timetable=tt,
            room_lectures=room_lectures,
            curriculum_period_lectures=curriculum_period_lectures,
            course_daily_lectures=course_daily_lectures,
            working_days=working_days,
            used_rooms=used_rooms,
        )
        return instance

    def clone(self):
        new_timetable = self.from_faculty(self.faculty)
        new_timetable.timetable = deepcopy(self.timetable)
        return new_timetable

    @classmethod
    def from_stream(cls, faculty: Faculty, buffer: IO):
        instance = cls.from_faculty(faculty)
        room_names = [r.name for r in faculty.room_vect]

        for line in buffer:
            course_name, room_name, day, period = line.split()
            day, period = int(day), int(period)

            try:
                c = faculty.course_names.index(course_name)
            except ValueError:
                logger.warning('Nonexisting course %s (entry skipped)', course_name)
                continue
            try:
                r = room_names.index(room_name) + 1
            except ValueError:
                logger.warning('Nonexisting room %s (entry skipped)', room_name)
                continue
            if day > faculty.days:
                logger.warning('Nonexisting day %d (entry skipped)', day)
                continue
            if period > faculty.periods_per_day:
                logger.warning('Nonexisting period %d (entry skipped)', period)
                continue
            p = day * faculty.periods_per_day + period

            if instance.timetable[c][p]:
                logger.warning('Repeated entry: %s (entry skipped)', line.strip())
                continue

            instance.timetable[c][p] = r

        instance.update_redundant_data()
        return instance

    def to_stream(self, buffer: IO):
        for c in range(self.faculty.courses):
            for p in range(self.faculty.periods):
                room = self.timetable[c][p]
                if room:
                    room_name = self.faculty.room_vect[room - 1].name
                    course_name = self.faculty.course_vect[c].name
                    day, period = divmod(p, self.faculty.periods_per_day)
                    buffer.write(f'{course_name} {room_name} {day} {period}\n')

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
