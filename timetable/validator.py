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
                if self.timetable.curriculum_period_lectures[g][p] > 0:
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
        print('Summary: ')
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
        pass

    def print_violations_on_conflicts(self):
        pass

    def print_violations_on_availability(self):
        pass

    def print_violations_on_room_occupation(self):
        pass

    def print_violations_on_room_capacity(self):
        pass

    def print_violations_on_min_working_days(self):
        pass

    def print_violations_on_curriculum_compactness(self):
        pass

    def print_violations_on_room_stability(self):
        pass

    """
    void Validator::PrintViolationsOnLectures(std::ostream& os) const
{
  unsigned c, p, lectures;
  for (c = 0; c < in.Courses(); c++)
    {
      lectures = 0;
      for (p = 0; p < in.Periods(); p++)
	if (out(c,p) != 0)
	  lectures++;
      if (lectures < in.CourseVector(c).Lectures())
	os << "[H] Too few lectures for course " << in.CourseVector(c).Name() << std::endl;
      else if (lectures > in.CourseVector(c).Lectures())
	os << "[H] Too many lectures for course " << in.CourseVector(c).Name() << std::endl;
    }
}




void Validator::PrintViolationsOnConflicts(std::ostream& os) const
{
  unsigned c1, c2, p;
  for (c1 = 0; c1 < in.Courses(); c1++)
    for (c2 = c1+1; c2 < in.Courses(); c2++)
      if (in.Conflict(c1,c2))
	{
	  for (p = 0; p < in.Periods(); p++)
	    if (out(c1,p) != 0 && out(c2,p) != 0)
	      os << "[H] Courses " << in.CourseVector(c1).Name() << " and "
		 << in.CourseVector(c2).Name() << " have both a lecture at period "
		 << p << " (day " << p/in.PeriodsPerDay() << ", timeslot " << p % in.PeriodsPerDay() << ")" << std::endl;
	}
}

void Validator::PrintViolationsOnAvailability(std::ostream& os) const
{
  unsigned c, p;
  for (c = 0; c < in.Courses(); c++)
    for (p = 0; p < in.Periods(); p++)
      if (out(c,p) != 0 && !in.Available(c,p))
	os << "[H] Course " << in.CourseVector(c).Name() << " has a lecture at unavailable period "
	   << p << " (day " << p/in.PeriodsPerDay() << ", timeslot " << p % in.PeriodsPerDay() << ")" << std::endl;
}

void Validator::PrintViolationsOnRoomOccupation(std::ostream& os) const
{
  unsigned r, p;
  for (p = 0; p < in.Periods(); p++)
    for (r = 1; r <= in.Rooms(); r++)
      if (out.RoomLectures(r,p) > 1)
	{
	  os << "[H] " << out.RoomLectures(r,p) << " lectures in room "
	     << in.RoomVector(r).Name() << " the period " << p << " (day " << p/in.PeriodsPerDay() << ", timeslot " << p % in.PeriodsPerDay() << ")";
	  if (out.RoomLectures(r,p) > 2)
	    os << " [" << out.RoomLectures(r,p) - 1 << " violations]";
	  os << std::endl;
	}
}

void Validator::PrintViolationsOnRoomCapacity(std::ostream& os) const
{
 unsigned c, p, r;
  for (c = 0; c < in.Courses(); c++)
    for (p = 0; p < in.Periods(); p++)
      {
	r = out(c,p);
	if (r != 0 && in.RoomVector(r).Capacity() < in.CourseVector(c).Students())
	  os << "[S(" << in.CourseVector(c).Students() - in.RoomVector(r).Capacity()
	     << ")] Room " << in.RoomVector(r).Name() << " too small for course "
	     << in.CourseVector(c).Name() << " the period "
	     << p << " (day " << p/in.PeriodsPerDay() << ", timeslot " << p % in.PeriodsPerDay() << ")"
	     << std::endl;
      }
}

void Validator::PrintViolationsOnMinWorkingDays(std::ostream& os) const
{
  unsigned c;
  for (c = 0; c < in.Courses(); c++)
    if (out.WorkingDays(c) < in.CourseVector(c).MinWorkingDays())
      os << "[S(" << in.MIN_WORKING_DAYS_COST << ")] The course " << in.CourseVector(c).Name() << " has only " << out.WorkingDays(c)
         << " days of lecture" << std::endl;
}

void Validator::PrintViolationsOnCurriculumCompactness(std::ostream& os) const
{
   unsigned g, p, ppd = in.PeriodsPerDay();

  for (g = 0; g < in.Curricula(); g++)
    {
      for (p = 0; p < in.Periods(); p++)
	if (out.CurriculumPeriodLectures(g,p) > 0)
	  {
	    if ((p % ppd == 0 && out.CurriculumPeriodLectures(g,p+1) == 0)
		|| (p % ppd == ppd-1 && out.CurriculumPeriodLectures(g,p-1) == 0)
		|| (out.CurriculumPeriodLectures(g,p+1) == 0 && out.CurriculumPeriodLectures(g,p-1) == 0))
	      os << "[S(" << in.CURRICULUM_COMPACTNESS_COST << ")] Curriculum " << in.CurriculaVector(g).Name()
		 << " has an isolated lecture at period " << p << " (day " << p/in.PeriodsPerDay() << ", timeslot " << p % in.PeriodsPerDay() << ")"
		 << std::endl;
	  }
    }
}

void Validator::PrintViolationsOnRoomStability(std::ostream& os) const
{
  std::vector<unsigned> used_rooms;
  unsigned c;

  for (c = 0; c < in.Courses(); c++)
    if (out.UsedRoomsNo(c) > 1)
      os << "[S(" << (out.UsedRoomsNo(c) - 1) * in.ROOM_STABILITY_COST << ")] Course " << in.CourseVector(c).Name() << " uses "
	 << out.UsedRoomsNo(c) << " different rooms" << std::endl;
}
    """


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
