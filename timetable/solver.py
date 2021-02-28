import logging
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from heapq import nsmallest
from operator import itemgetter
from random import random, randrange, seed
from typing import Optional, Tuple

import click

from .settings import MAX_WORKERS
from .structures import Faculty, Timetable
from .validator import Validator

logger = logging.getLogger(__name__)


@dataclass
class Solver:
    faculty: Faculty
    seed: Optional[int] = None

    violation_cost: Optional[int] = None
    shots: int = 1000
    iterations: int = 10000
    slices: int = 3
    slice_ratio: float = 0.4
    max_consecutive_rejects: int = 10

    def do_the_thing(self, init_timetable: Optional[Timetable] = None) -> Tuple[int, Timetable]:
        if self.violation_cost is None:
            self.violation_cost = sum(
                self.faculty.course_vect[c].lectures
                for c in range(self.faculty.courses)
            ) * 100
            logger.info(f'Validation cost ratio is set to {self.violation_cost}')

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

    def init(self) -> Timetable:  # TODO
        timetable = Timetable.from_faculty(self.faculty)

        for c in range(self.faculty.courses):
            for i in range(self.faculty.course_vect[c].lectures):
                p = randrange(0, self.faculty.periods)
                while timetable.timetable[c][p]:
                    p = randrange(0, self.faculty.periods)
                room = randrange(0, self.faculty.rooms) + 1
                timetable.timetable[c][p] = room

        timetable.update_redundant_data()
        return timetable

    def iterate(self, timetable: Timetable) -> Timetable:  # TODO
        timetable = timetable.clone()

        for _ in range(1):  # Tune
            c = randrange(self.faculty.courses)
            i = randrange(self.faculty.course_vect[c].lectures)

            for p in range(self.faculty.periods):
                room = timetable.timetable[c][p]
                if not room:
                    continue
                i -= 1
                if i:
                    continue

                if random() < 0.5:
                    new_room = randrange(0, self.faculty.rooms) + 1
                    if new_room == room:
                        new_room = (new_room + 1) % self.faculty.rooms + 1
                    timetable.timetable[c][p] = new_room
                else:
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


def make_solver(faculty_input, **kwargs) -> Solver:
    faculty = Faculty.from_stream(faculty_input)
    return Solver(faculty, **kwargs)


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
