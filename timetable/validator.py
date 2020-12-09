import logging
import os
import sys
from dataclasses import dataclass
from functools import cached_property

from .structures import *

logger = logging.getLogger(__name__)


@dataclass
class Validator:
    faculty: Faculty
    timetable: Timetable

    def _period(self, period):
        day, timeslot = divmod(period, self.faculty.periods_per_day)
        return f'period {period} (day {day}, timeslot {timeslot})'

    @cached_property
    def costs_on_lectures(self) -> int:
        cost = 0
        for c in range(self.faculty.courses):
            lectures = 0
            for p in range(self.faculty.periods):
                if self.timetable.timetable[c][p]:
                    lectures += 1
            if lectures < self.faculty.course_vect[c].lectures:
                cost += self.faculty.course_vect[c].lectures - lectures
            elif lectures > self.faculty.course_vect[c].lectures:
                cost += lectures - self.faculty.course_vect[c].lectures
        return cost

    @cached_property
    def costs_on_conflicts(self) -> int:
        cost = 0
        for c1 in range(self.faculty.courses):
            for c2 in range(c1 + 1, self.faculty.courses):
                if self.faculty.conflict[c1][c2]:
                    for p in range(self.faculty.periods):
                        if self.timetable.timetable[c1][p] and self.timetable.timetable[c2][p]:
                            cost += 1
        return cost

    @cached_property
    def costs_on_availability(self) -> int:
        cost = 0
        for c in range(self.faculty.courses):
            for p in range(self.faculty.periods):
                if self.timetable.timetable[c][p] and not self.faculty.availability[c][p]:
                    cost += 1
        return cost

    @cached_property
    def costs_on_room_occupation(self) -> int:
        cost = 0
        for p in range(self.faculty.periods):
            for r in range(self.faculty.rooms + 1):
                if self.timetable.room_lectures[r][p] > 1:
                    cost += (self.timetable.room_lectures[r][p] - 1)
        return cost

    @cached_property
    def costs_on_room_capacity(self) -> int:
        cost = 0
        for c in range(self.faculty.courses):
            for p in range(self.faculty.periods):
                r = self.timetable.timetable[c][p]
                if r and self.faculty.room_vect[r].capacity < self.faculty.course_vect[c].students:
                    cost += self.faculty.course_vect[c].students - self.faculty.room_vect[r].capacity
        return cost

    @cached_property
    def costs_on_min_working_days(self) -> int:
        cost = 0
        for c in range(self.faculty.courses):
            if self.timetable.working_days[c] < self.faculty.course_vect[c].min_working_days:
                cost += self.faculty.course_vect[c].min_working_days - self.timetable.working_days[c]
        return cost

    @cached_property
    def costs_on_curriculum_compactness(self) -> int:
        cost = 0
        ppd = self.faculty.periods_per_day
        for g in range(self.faculty.curricula):
            for p in range(self.faculty.periods):
                if not self.timetable.curriculum_period_lectures[g][p]:
                    continue
                if p % ppd == 0:
                    if not self.timetable.curriculum_period_lectures[g][p + 1]:
                        cost += self.timetable.curriculum_period_lectures[g][p]
                elif (p + 1) % ppd == 0:
                    if not self.timetable.curriculum_period_lectures[g][p - 1]:
                        cost += self.timetable.curriculum_period_lectures[g][p]
                elif not (self.timetable.curriculum_period_lectures[g][p + 1] or self.timetable.curriculum_period_lectures[g][p - 1]):
                    cost += self.timetable.curriculum_period_lectures[g][p]
        return cost

    @cached_property
    def costs_on_room_stability(self) -> int:
        cost = 0
        for c in range(self.faculty.courses):
            rooms = len(self.timetable.used_rooms[c])
            if rooms > 1:
                cost += rooms - 1
        return cost

    def print_violations(self):
        self.print_violations_on_lectures()
        self.print_violations_on_conflicts()
        self.print_violations_on_availability()
        self.print_violations_on_room_occupation()
        self.print_violations_on_room_capacity()
        self.print_violations_on_min_working_days()
        self.print_violations_on_curriculum_compactness()
        self.print_violations_on_room_stability()
        print()

    def print_costs(self):
        print(f'Violations of Lectures (hard) : {self.costs_on_lectures}')
        print(f'Violations of Conflicts (hard) : {self.costs_on_conflicts}')
        print(f'Violations of Availability (hard) : {self.costs_on_availability}')
        print(f'Violations of RoomOccupation (hard) : {self.costs_on_room_occupation}')
        print(f'Cost of RoomCapacity (soft) : {self.costs_on_room_capacity}')
        print(f'Cost of MinWorkingDays (soft) : {self.costs_on_min_working_days * self.faculty.MIN_WORKING_DAYS_COST}')
        cc_costs = self.costs_on_curriculum_compactness * self.faculty.CURRICULUM_COMPACTNESS_COST
        print(f'Cost of CurriculumCompactness (soft) : {cc_costs}')
        print(f'Cost of RoomStability (soft) : {self.costs_on_room_stability * self.faculty.ROOM_STABILITY_COST}')
        print()

    def print_total_cost(self):
        print('Summary: ', end='')
        violations = sum([
            self.costs_on_lectures,
            self.costs_on_conflicts,
            self.costs_on_availability,
            self.costs_on_room_occupation,
        ])

        costs = sum([
            self.costs_on_room_capacity,
            self.costs_on_min_working_days * self.faculty.MIN_WORKING_DAYS_COST,
            self.costs_on_curriculum_compactness * self.faculty.CURRICULUM_COMPACTNESS_COST,
            self.costs_on_room_stability * self.faculty.ROOM_STABILITY_COST,
        ])
        parts = []
        if violations:
            parts.append(f'Violations = {violations}')
        parts.append(f'Total Cost = {costs}')
        print(', '.join(parts))

    def print_violations_on_lectures(self):
        for c in range(self.faculty.courses):
            lectures = 0
            for p in range(self.faculty.periods):
                if self.timetable.timetable[c][p]:
                    lectures += 1
            if lectures < self.faculty.course_vect[c].lectures:
                print(f'[H] Too few lectures for course {self.faculty.course_vect[c].name}')
            if lectures > self.faculty.course_vect[c].lectures:
                print(f'[H] Too many lectures for course {self.faculty.course_vect[c].name}')

    def print_violations_on_conflicts(self):
        for c1 in range(self.faculty.courses):
            for c2 in range(c1 + 1, self.faculty.courses):
                if self.faculty.conflict[c1][c2]:
                    for p in range(self.faculty.periods):
                        if self.timetable.timetable[c1][p] and self.timetable.timetable[c2][p]:
                            c1_name = self.faculty.course_vect[c1].name
                            c2_name = self.faculty.course_vect[c2].name
                            print(f'[H] Courses {c1_name} and {c2_name} have both a lecture at {self._period(p)}')

    def print_violations_on_availability(self):
        for c in range(self.faculty.courses):
            for p in range(self.faculty.periods):
                if self.timetable.timetable[c][p] and not self.faculty.availability[c][p]:
                    print(f'[H] Course {self.faculty.course_vect[c].name} has a lecture '
                          f'at unavailable {self._period(p)}')

    def print_violations_on_room_occupation(self):
        for p in range(self.faculty.periods):
            for r in range(self.faculty.rooms + 1):
                if self.timetable.room_lectures[r][p] > 1:
                    print(f'[H] {self.timetable.room_lectures[r][p]} lectures in room {self.faculty.room_vect[r].name}'
                          f' the {self._period(p)}', end='')
                    if self.timetable.room_lectures[r][p] > 2:
                        print(f' [{self.timetable.room_lectures[r][p] - 1} violations]')
                    print()

    def print_violations_on_room_capacity(self):
        for c in range(self.faculty.courses):
            for p in range(self.faculty.periods):
                r = self.timetable.timetable[c][p]
                if r and self.faculty.room_vect[r].capacity < self.faculty.course_vect[c].students:
                    cost = self.faculty.course_vect[c].students - self.faculty.room_vect[r].capacity
                    print(f'[S({cost})] Room {self.faculty.room_vect[r].name} too small '
                          f'for course {self.faculty.course_vect[c].name} the {self._period(p)}')

    def print_violations_on_min_working_days(self):
        for c in range(self.faculty.courses):
            if self.timetable.working_days[c] < self.faculty.course_vect[c].min_working_days:
                print(f'[S({self.faculty.MIN_WORKING_DAYS_COST})] The course {self.faculty.course_vect[c].name} has only {self.timetable.working_days[c]} days of lecture')

    def print_violations_on_curriculum_compactness(self):
        ppd = self.faculty.periods_per_day
        for g in range(self.faculty.curricula):
            for p in range(self.faculty.periods):
                if not self.timetable.curriculum_period_lectures[g][p]:
                    continue
                cost = 0
                if p % ppd == 0:
                    if not self.timetable.curriculum_period_lectures[g][p + 1]:
                        cost = self.timetable.curriculum_period_lectures[g][p]
                elif (p + 1) % ppd == 0:
                    if not self.timetable.curriculum_period_lectures[g][p - 1]:
                        cost = self.timetable.curriculum_period_lectures[g][p]
                elif not (self.timetable.curriculum_period_lectures[g][p + 1] or self.timetable.curriculum_period_lectures[g][p - 1]):
                    cost = self.timetable.curriculum_period_lectures[g][p]
                if cost:
                    cost *= self.faculty.CURRICULUM_COMPACTNESS_COST
                    print(f'[S({cost})] Curriculum {self.faculty.curricula_vect[g].name} has an isolated lecture at {self._period(p)}')

    def print_violations_on_room_stability(self):
        for c in range(self.faculty.courses):
            rooms = len(self.timetable.used_rooms[c])
            if rooms > 1:
                cost = (rooms - 1) * self.faculty.ROOM_STABILITY_COST
                print(f'[S({cost})] Course {self.faculty.course_vect[c].name} uses {rooms} different rooms')


def main():
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) != 3:
        logger.info(f'Usage: {sys.argv[0]} <input_file> <solution_file>')
        exit(1)

    if not os.path.isfile(sys.argv[1]):
        logger.error('Input file does not exist!')
        exit(1)

    if not os.path.isfile(sys.argv[2]):
        logger.error('Output file does not exist!')
        exit(1)

    with open(sys.argv[1]) as input_file:
        faculty = Faculty.from_stream(input_file)
    with open(sys.argv[2]) as output_file:
        timetable = Timetable.from_stream(faculty, output_file)
    validator = Validator(faculty, timetable)

    validator.print_violations()
    validator.print_costs()
    validator.print_total_cost()


if __name__ == '__main__':
    main()
