import logging
import sys
from functools import partial

from PyQt5 import QtWidgets as qt

from .import main_window_ui, progress_window_ui
from .solver import make_solver
from .structures import Timetable

logger = logging.getLogger(__name__)


def file_picker(parent, to_input: qt.QLineEdit, title: str, save: bool = False):
    if save:
        dialog = qt.QFileDialog.getSaveFileName
    else:
        dialog = qt.QFileDialog.getOpenFileName

    path, _ = dialog(parent, title, '', 'All Files (*.*)')
    to_input.setText(path)


class ProgressWindow(qt.QMainWindow, progress_window_ui.Ui_MainWindow):
    def __init__(self, parent=None):
        super(ProgressWindow, self).__init__(parent)
        self.setupUi(self)


class TimetableWindow(qt.QMainWindow, main_window_ui.Ui_MainWindow):
    progress_window = None

    def __init__(self, parent=None):
        super(TimetableWindow, self).__init__(parent)
        self.setupUi(self)
        self.setupBindings()

    def setupBindings(self):
        self.edit_seed.setInputMask('0' * len(str(sys.maxsize)) + '; ')
        self.pick_faculty.clicked.connect(partial(
            file_picker, self, self.edit_faculty, 'Select faculty file',
        ))
        self.pick_output.clicked.connect(partial(
            file_picker, self, self.edit_output, 'Select faculty file', save=True,
        ))
        self.pick_solution.clicked.connect(partial(
            file_picker, self, self.edit_solution, 'Select existing solution file',
        ))
        self.button_start.clicked.connect(self.start_solver)

    @property
    def solver_kwargs(self):
        kwargs = {
            'shots': self.input_shots.value(),
            'iterations': self.input_iterations.value(),
            'slices': self.input_slices.value(),
            'slice_ratio': self.input_slice_ratio.value(),
            'max_consecutive_rejects': self.input_rejects.value(),
            'sort_courses': self.toggle_course_sort.isChecked(),
            'repeat_sliced_results': self.toggle_slice_repeat.isChecked(),
        }
        if self.edit_seed.text():
            kwargs['seed'] = int(self.edit_seed.text())

        return kwargs

    def start_solver(self):
        if not self.edit_faculty.text():
            self.statusbar.showMessage('Cannot start without faculty file!', 3000)
            return

        with open(self.edit_faculty.text()) as faculty:
            solver = make_solver(faculty, **self.solver_kwargs)
        if self.edit_solution.text():
            with open(self.edit_solution.text()) as from_solution:
                from_solution = Timetable.from_stream(solver.faculty, from_solution)
        else:
            from_solution = None

        self.progress_window = ProgressWindow()
        self.progress_window.show()
        score, timetable = solver.do_the_thing(from_solution)
        self.statusbar.showMessage(f'Best score is {score}', 3000)
        self.progress_window.label_2.setText(f'Best score is {score}')
        logger.info('Best score is %d', score)

        if self.edit_output.text():
            with open(self.edit_output.text(), 'wt') as output:
                timetable.to_stream(output)


if __name__ == '__main__':
    app = qt.QApplication(sys.argv)
    window = TimetableWindow()
    window.show()
    sys.exit(app.exec_())
