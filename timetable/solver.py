import logging
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from heapq import nsmallest
from operator import itemgetter
from typing import Optional, Sequence, Tuple

import click

from .settings import MAX_WORKERS
from .structures import Faculty, Timetable
from .validator import Validator

logger = logging.getLogger(__name__)


@dataclass
class Solver:
    faculty: Faculty
    violation_cost: int
    seed: int

    shots: int = 1000
    iterations: int = 10000
    slices: int = 3
    slice_ratio: float = 0.3
    max_consecutive_rejects: int = 10

    def do_the_thing(self, init_timetable: Optional[Timetable] = None) -> Tuple[int, Timetable]:
        random.seed(self.seed)
        init_timetables = [(None, init_timetable) for _ in range(self.shots)]
        timetables = self.shot_timetables(init_timetables)
        for _ in range(self.slices):
            top = int(len(timetables) * self.slice_ratio)
            if not top:

                break

            timetables = self.shot_timetables(
                list(nsmallest(top, timetables, key=itemgetter(0))),
            )

        return min(timetables, key=itemgetter(0))

    def shot_timetables(
            self, timetables: Sequence[Tuple[Optional[int], Optional[Timetable]]],
    ) -> Sequence[Tuple[int, Timetable]]:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # *zip(* is starmap replacement
            return list(executor.map(
                self.shot,
                *zip(*timetables),
                (random.randrange(sys.maxsize) for _ in range(self.shots)),  # inner seed
            ))

    def shot(
            self, cost: Optional[int], timetable: Optional[Timetable], seed: int,
    ) -> Tuple[int, Timetable]:
        random.seed(seed)
        if timetable is None:
            timetable = self.init()
        if cost is None:
            cost = self.evaluate(timetable)

        i, approves, rejects = 0, 0, 0
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

        logger.debug(f'Finished shot on iteration #{i} after {approves} approves with score {cost}')
        return cost, timetable

    @staticmethod
    def should_accept(old_cost: int, new_cost: int) -> bool:
        return new_cost < old_cost or random.random() < 0.01

    def evaluate(self, timetable: Timetable):
        validator = Validator(self.faculty, timetable)
        return validator.total_violation_cost * self.violation_cost + validator.total_soft_cost

    def init(self) -> Timetable:  # TODO
        timetable = Timetable.from_faculty(self.faculty)

        for c in range(self.faculty.courses):
            for i in range(self.faculty.course_vect[c].lectures):
                p = self.get_free_period(timetable, c)
                room = self.get_free_room(timetable, c)
                timetable.timetable[c][p] = room

        timetable.update_redundant_data()
        return timetable

    def iterate(self, timetable: Timetable) -> Timetable:  # TODO
        timetable = timetable.clone()

        for _ in range(1):  # Tune
            c = random.randrange(self.faculty.courses)
            i = random.randrange(self.faculty.course_vect[c].lectures)

            for p in range(self.faculty.periods):
                room = timetable.timetable[c][p]
                if not room:
                    continue
                if i:
                    i -= 1
                    continue

                if random.random() < 0.5:
                    # Change the room of the lecture
                    new_room = self.get_free_room(timetable, c)
                    timetable.timetable[c][p] = new_room
                else:
                    # change the period of the lecture
                    new_p = self.get_free_period(timetable, c, p)
                    timetable.timetable[c][new_p] = timetable.timetable[c][p]
                    timetable.timetable[c][p] = 0
                break

        timetable.update_redundant_data()
        return timetable

    def get_free_period(self, timetable: Timetable, c: int, from_p: Optional[int] = None) -> int:
        """Get random accessible period for course in timetable
        Takes into account:
        1) Specified course must not already take place on such period
        2) If from_p passed, this value is forbidden too
        3) Take into account forbidden periods
        4) Courses from same curricula / teacher must not take place on such period
        TODO
        5) ?
        """
        periods = set(range(self.faculty.periods))
        # 1) Specified course must not already take place on such period
        same_possible_periods = periods.copy()
        for p in periods:
            if timetable.timetable[c][p]:
                same_possible_periods.discard(p)

        # 2) If from_p passed, this value is forbidden too
        from_possible_periods = same_possible_periods.copy()
        if from_p:
            from_possible_periods.discard(from_p)

        # 3) Take into account forbidden periods
        available_periods = from_possible_periods.copy()
        for p in from_possible_periods:
            if not self.faculty.availability[c][p]:
                available_periods.discard(p)

        # 4) Courses from same curricula / teacher must not take place on such period
        conflict_periods = available_periods.copy()
        for conflict_course in self.faculty.conflict[c]:
            for p in available_periods:
                if timetable.timetable[conflict_course][p]:
                    conflict_periods.discard(p)

        if len(conflict_periods) < 2:
            logger.warning(
                'Only %d possible periods for course %s, skipping conflict validation',
                len(conflict_periods), self.faculty.course_vect[c].name,
            )
            return random.choice(tuple(available_periods))

        return random.choice(tuple(conflict_periods))

    def get_free_room(self, timetable: Timetable, c: int) -> int:
        r = random.randrange(0, self.faculty.rooms) + 1
        return r


def make_solver(faculty_input, violation_cost, seed, **kwargs) -> Solver:
    faculty = Faculty.from_stream(faculty_input)
    if violation_cost is None:
        violation_cost = sum(
            faculty.course_vect[c].lectures
            for c in range(faculty.courses)
        ) * 100
        logger.info('Validation cost ratio is set to %d', violation_cost)
    if seed is None:
        seed = random.randrange(sys.maxsize)
        logger.info('Seed is set to %d', seed)

    return Solver(
        faculty=faculty,
        violation_cost=violation_cost,
        seed=seed,
        **kwargs,
    )


@click.command()
@click.argument('faculty', type=click.File('rt'))
@click.argument('output', type=click.File('wt'))
@click.option(
    '-f', '--from-solution', type=click.File('rt'), default=None,
    help='Use existing solution as starting point',
)
@click.option('--seed', type=int, default=None, show_default=True)
@click.option('--log-level', type=str, default='info', show_default=True)
@click.option('--violation_cost', type=int, default=None, show_default=True)
@click.option('--shots', type=int, default=1000, show_default=True)
@click.option('--iterations', type=int, default=10000, show_default=True)
@click.option('--slices', type=int, default=3, show_default=True)
@click.option('--slice_ratio', type=float, default=0.4, show_default=True)
@click.option('--max_consecutive_rejects', type=int, default=10, show_default=True)
def main(faculty, output, from_solution, log_level, **solver_kwargs):
    logging.basicConfig(
        format='%(asctime)s - [%(levelname)s] - [%(name)s] - %(filename)s:%(lineno)d - %(message)s',
        level=log_level.upper(),
    )
    solver = make_solver(faculty, **solver_kwargs)
    if from_solution:
        from_solution = Timetable.from_stream(solver.faculty, from_solution)

    score, timetable = solver.do_the_thing(from_solution)
    logger.info('Best score is %d', score)

    timetable.to_stream(output)


if __name__ == '__main__':
    main()
