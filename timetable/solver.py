import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from heapq import nsmallest
from operator import itemgetter
from random import random, randrange, seed
from typing import Optional, Tuple

from .settings import MAX_WORKERS
from .structures import Faculty, Timetable
from .validator import Validator

logger = logging.getLogger(__name__)


@dataclass
class Solver:
    faculty: Faculty
    seed: Optional[int] = None

    violation_cost: int = 1000
    shots: int = 1000
    iterations: int = 10000
    slices: int = 3
    slice_ratio: float = 0.4
    max_consecutive_rejects: int = 10

    def do_the_thing(self, init_timetable: Optional[Timetable] = None) -> Tuple[int, Timetable]:
        seed(self.seed)
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            timetables = list(executor.map(self.shot, (init_timetable for _ in range(self.shots))))

        for _ in range(self.slices):
            top = int(len(timetables) * self.slice_ratio)
            if not top:
                break

            with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
                timetables = list(executor.map(self.shot, (
                    timetable for _, timetable in nsmallest(top, timetables, key=itemgetter(0))
                )))

        return min(timetables, key=itemgetter(0))

    def shot(self, timetable: Optional[Timetable]) -> Tuple[int, Timetable]:
        if timetable is None:
            timetable = self.init()
        cost = self.evaluate(timetable)

        approves, rejects = 0, 0
        for i in range(self.iterations):
            if rejects > self.max_consecutive_rejects:
                break
            new_timetable = self.iterate(timetable)
            if new_timetable == timetable:
                new_cost = cost
            else:
                new_cost = self.evaluate(new_timetable)

            if self.should_accept(cost, new_cost):
                rejects = 0
                approves += 1
                cost, timetable = new_cost, new_timetable
            else:
                rejects += 1
        return cost, timetable

    def init(self) -> Timetable:  # TODO
        timetable = Timetable.from_faculty(self.faculty)

        for c in range(self.faculty.courses):
            for i in range(self.faculty.course_vect[c].lectures):
                p = randrange(0, self.faculty.periods)
                room = randrange(0, self.faculty.rooms) + 1
                timetable.timetable[c][p] = room

        timetable.update_redundant_data()
        return timetable

    def iterate(self, timetable: Timetable) -> Timetable:  # TODO
        timetable = timetable.clone()

        for c in range(self.faculty.courses):
            for p in range(self.faculty.periods):
                room = timetable.timetable[c][p]
                if room:
                    if random() < 0.1:
                        new_room = randrange(0, self.faculty.rooms) + 1
                        if new_room == room:
                            new_room = (new_room + 1) % self.faculty.rooms + 1
                        timetable.timetable[c][p] = new_room

                    if random() < 0.1:
                        new_p = randrange(0, self.faculty.periods)
                        if new_p == p or timetable.timetable[c][new_p]:
                            new_p = (new_p + 1) % self.faculty.periods

                        if new_p == p or timetable.timetable[c][new_p]:
                            continue
                        timetable.timetable[c][new_p] = timetable.timetable[c][p]
                        timetable.timetable[c][p] = 0

        timetable.update_redundant_data()
        return timetable

    @staticmethod
    def should_accept(old_cost: int, new_cost: int) -> bool:
        return new_cost < old_cost or random() < 0.1

    def evaluate(self, timetable: Timetable):
        validator = Validator(self.faculty, timetable)
        return validator.total_violation_cost * self.violation_cost + validator.total_soft_cost


def make_solver(faculty_filename: str) -> Solver:
    with open(faculty_filename) as input_file:
        faculty = Faculty.from_stream(input_file)
    return Solver(faculty)


def main():
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) not in [3, 4]:
        logger.info(f'Usage: {sys.argv[0]} <input_file> <output_file> [<existing_solution>]')
        exit(1)

    if not os.path.isfile(sys.argv[1]):
        logger.error('Input file does not exist!')
        exit(1)

    solver = make_solver(sys.argv[1])
    if len(sys.argv) == 4:
        if not os.path.isfile(sys.argv[3]):
            logger.error('Input file does not exist!')
            exit(1)

        with open(sys.argv[3]) as out:
            init_timetable = Timetable.from_stream(solver.faculty, out)
    else:
        init_timetable = None

    score, timetable = solver.do_the_thing(init_timetable)
    logger.info('Best score is %d', score)

    with open(sys.argv[2], 'w') as out:
        timetable.to_stream(out)


if __name__ == '__main__':
    main()
