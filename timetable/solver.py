import logging
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from enum import Enum
from heapq import nsmallest
from itertools import cycle, islice
from operator import itemgetter
from typing import Any, Mapping, Optional, Sequence, Tuple

import click

from .settings import MAX_WORKERS
from .structures import Faculty, Timetable
from .validator import Validator

logger = logging.getLogger(__name__)


def get_random_option(option_chances: Mapping[Any, int]) -> Any:
    return random.choice([
        count
        for count, chances in option_chances.items()
        for _ in range(chances)
    ])


class Mutation(Enum):
    change_room = 'change_room'
    change_period = 'change_period'
    change_both = 'change_period'
    swap_room = 'swap_room'
    swap_period = 'swap_period'
    swap_both = 'swap_period'


@dataclass
class Solver:
    faculty: Faculty
    violation_cost: int
    seed: int

    shots: int
    iterations: int
    slices: int
    slice_ratio: float
    max_consecutive_rejects: int

    # feature toggles
    sort_courses: bool
    repeat_sliced_results: bool

    mutation_count_chances = {  # TODO Tune
        1: 1,
        # 2: 1,
        # 3: 1,
        # 4: 1,
        # 5: 1,
    }

    mutation_chances = {  # TODO Tune
        Mutation.change_room: 4,
        Mutation.change_period: 4,
        Mutation.change_both: 2,
        Mutation.swap_room: 2,
        Mutation.swap_period: 2,
        Mutation.swap_both: 1,
    }

    def do_the_thing(self, init_timetable: Optional[Timetable] = None) -> Tuple[int, Timetable]:
        random.seed(self.seed)
        init_timetables = [(None, init_timetable) for _ in range(self.shots)]
        timetables = self.shot_timetables(init_timetables)
        logger.info(
            'Got %d timetables, cost range - [%d, %d]',
            self.shots,
            min(timetables, key=itemgetter(0))[0],
            max(timetables, key=itemgetter(0))[0],
        )

        for _ in range(self.slices):
            top = int(len(timetables) * self.slice_ratio)
            if not top:
                break

            timetables = list(nsmallest(top, timetables, key=itemgetter(0)))
            logger.info(
                'Selected %d top timetables, cost range - [%d, %d]',
                top,
                min(timetables, key=itemgetter(0))[0],
                max(timetables, key=itemgetter(0))[0],
            )
            if self.repeat_sliced_results:
                timetables = list(islice(cycle(timetables), self.shots))
            timetables = self.shot_timetables(timetables)

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

        courses = list(range(self.faculty.courses))
        # Shown no effect on results(
        if self.sort_courses:
            courses.sort(key=lambda c: -self.faculty.course_conflict_weights[c])
        for c in courses:
            for i in range(self.faculty.course_vect[c].lectures):
                p = self.get_free_period(timetable, c)
                room = self.get_free_room(timetable, c, p)
                timetable.timetable[c][p] = room

        timetable.update_redundant_data()
        return timetable

    def iterate(self, timetable: Timetable) -> Timetable:  # TODO
        mutate = {
            Mutation.change_room: self.mutate_change_room,
            Mutation.change_period: self.mutate_change_period,
            Mutation.change_both: self.mutate_change_both,
            Mutation.swap_room: self.mutate_swap_room,
            Mutation.swap_period: self.mutate_swap_period,
            Mutation.swap_both: self.mutate_swap_both,
        }

        timetable = timetable.clone()

        mutations_count = get_random_option(self.mutation_count_chances)
        for _ in range(mutations_count):
            mutation = get_random_option(self.mutation_chances)
            timetable = mutate[mutation](timetable)

        timetable.update_redundant_data()
        return timetable

    def mutate_change_room(self, timetable: Timetable) -> Timetable:
        c, p, room = self.pick_course_period_room(timetable)
        # Change the room of the lecture
        new_room = self.get_free_room(timetable, c, p, room)
        timetable.timetable[c][p] = new_room
        return timetable

    def mutate_change_period(self, timetable: Timetable) -> Timetable:
        c, p, room = self.pick_course_period_room(timetable)
        # change the period of the lecture
        new_p = self.get_free_period(timetable, c, p)
        timetable.timetable[c][new_p] = timetable.timetable[c][p]
        timetable.timetable[c][p] = 0
        return timetable

    def mutate_change_both(self, timetable: Timetable) -> Timetable:
        c, p, room = self.pick_course_period_room(timetable)
        # change the period of the lecture
        new_p = self.get_free_period(timetable, c, p)
        new_room = self.get_free_room(timetable, c, new_p, room)
        timetable.timetable[c][new_p] = new_room
        timetable.timetable[c][p] = 0
        return timetable

    def mutate_swap_room(self, timetable: Timetable) -> Timetable:
        from_c, from_p, from_room = self.pick_course_period_room(timetable)
        to_c, to_p, to_room = self.pick_course_period_room(timetable, bad_course=from_c)
        timetable.timetable[from_c][from_p] = to_room
        timetable.timetable[to_c][to_p] = from_room
        return timetable

    def mutate_swap_period(self, timetable: Timetable) -> Timetable:
        from_c, from_p, from_room = self.pick_course_period_room(timetable)
        to_c, to_p, to_room = self.pick_course_period_room(timetable, bad_course=from_c)
        if timetable.timetable[from_c][to_p] or timetable.timetable[to_c][from_p]:
            # Cannot swap this pair
            return timetable

        timetable.timetable[from_c][from_p] = 0
        timetable.timetable[from_c][to_p] = from_room
        timetable.timetable[to_c][to_p] = 0
        timetable.timetable[to_c][from_p] = to_room
        return timetable

    def mutate_swap_both(self, timetable: Timetable) -> Timetable:
        from_c, from_p, from_room = self.pick_course_period_room(timetable)
        to_c, to_p, to_room = self.pick_course_period_room(timetable, bad_course=from_c)
        if timetable.timetable[from_c][to_p] or timetable.timetable[to_c][from_p]:
            # Cannot swap this pair
            return timetable

        timetable.timetable[from_c][from_p] = 0
        timetable.timetable[from_c][to_p] = to_room
        timetable.timetable[to_c][to_p] = 0
        timetable.timetable[to_c][from_p] = from_room
        return timetable

    def pick_course_period_room(self, timetable: Timetable, bad_course: Optional[int] = None) -> Tuple[int, int, int]:
        courses = set(range(self.faculty.courses))
        if bad_course is not None:
            courses.discard(bad_course)
        c = random.choice(tuple(courses))
        i = random.randrange(self.faculty.course_vect[c].lectures)

        for p in range(self.faculty.periods):
            room = timetable.timetable[c][p]
            if not room:
                continue
            if i:
                i -= 1
                continue
            return c, p, room
        raise ValueError('Missing lecture #%d for course %s', i + 1, self.faculty.course_vect[c].name)

    def get_free_period(self, timetable: Timetable, c: int, from_p: Optional[int] = None) -> int:
        """Get random accessible period for course in timetable
        Takes into account:
        1) Specified course must not already take place on such period
        2) If from_p passed, this value is forbidden too
        3) Take into account forbidden periods
        4) Courses from same curricula / teacher must not take place on such period
        """
        periods = set(range(self.faculty.periods))
        # 1) Specified course must not already take place on such period
        same_possible_periods = periods.copy()
        for p in periods:
            if timetable.timetable[c][p]:
                same_possible_periods.discard(p)

        # 2) If from_p passed, this value is forbidden too
        from_possible_periods = same_possible_periods.copy()
        if from_p is not None:
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
            logger.debug(
                'Only %d possible periods for course %s, skipping conflict validation',
                len(conflict_periods), self.faculty.course_vect[c].name,
            )
            return random.choice(tuple(available_periods))

        return random.choice(tuple(conflict_periods))

    def get_free_room(self, timetable: Timetable, c: int, p: int, from_r: Optional[int] = None) -> int:
        rooms = set(range(1, self.faculty.rooms + 1))
        # If from_r passed, this value is forbidden
        from_rooms = rooms.copy()
        if from_r is not None:
            from_rooms.discard(from_r)

        return random.choice(tuple(from_rooms))


def make_solver(faculty_input, violation_cost=None, seed=None, **kwargs) -> Solver:
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
@click.option('--violation-cost', type=int, default=None, show_default=True)
@click.option('--shots', type=int, default=400, show_default=True)
@click.option('--iterations', type=int, default=1000, show_default=True)
@click.option('--slices', type=int, default=5, show_default=True)
@click.option('--slice-ratio', type=float, default=0.5, show_default=True)
@click.option('--max-consecutive-rejects', type=int, default=20, show_default=True)
@click.option('--sort-courses', type=bool, default=True, show_default=True)
@click.option('--repeat-sliced-results', type=bool, default=True, show_default=True)
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
