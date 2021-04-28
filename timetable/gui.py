import logging
import sys
from functools import partial

import pyqtgraph as pg
from PyQt5 import QtWidgets as qt
from PyQt5.QtCore import QThread, pyqtSignal

from . import main_window_ui, progress_window_ui
from .solver import Solver, make_solver
from .structures import Timetable

logger = logging.getLogger(__name__)


def file_picker(parent, to_input: qt.QLineEdit, title: str, save: bool = False):
    if save:
        dialog = qt.QFileDialog.getSaveFileName
    else:
        dialog = qt.QFileDialog.getOpenFileName

    path, _ = dialog(parent, title, '', 'All Files (*.*)')
    to_input.setText(path)


class SolverThread(QThread):
    finished: pyqtSignal  # type: ignore
    update_charts = pyqtSignal(object)
    best_score = pyqtSignal(int)
    timetable = pyqtSignal(object)

    def __init__(self, solver, from_solution, parent=None):
        super(QThread, self).__init__(parent)
        self.solver = solver
        self.from_solution = from_solution

    def callback(self, **kwargs):
        self.update_charts.emit(kwargs)

    def run(self):
        score, timetable = self.solver.do_the_thing(self.from_solution, callback=self.callback)
        logger.info('Best score is %d', score)
        self.finished.emit()
        self.best_score.emit(score)
        self.timetable.emit(timetable)


class ProgressWindow(qt.QMainWindow, progress_window_ui.Ui_MainWindow):
    x_slice: list
    y_time: list
    y_best: list
    y_worst: list
    time_graph: qt.QWidget
    score_graph: qt.QWidget

    def __init__(self, parent=None):
        super(ProgressWindow, self).__init__(parent)
        self.setupUi(self)
        self.setup_charts()

    def setup_charts(self):
        self.time_graph = pg.PlotWidget(title='Time spent')
        top = qt.QVBoxLayout()
        top.addWidget(self.time_graph)
        self.frame_2.setLayout(top)

        self.score_graph = pg.PlotWidget(title='Scores obtained')
        bottom = qt.QVBoxLayout()
        bottom.addWidget(self.score_graph)
        self.frame.setLayout(bottom)

        self.x_slice = []
        self.y_time = []
        self.y_best = []
        self.y_worst = []

        self.time_graph.setBackground('w')
        self.score_graph.setBackground('w')
        self.time_graph.setLogMode(False, True)
        self.time_graph.plotItem.titleLabel.setAttr('justify', 'right')
        self.score_graph.plotItem.titleLabel.setAttr('justify', 'right')
        self.time_graph.setLabel('bottom', 'Shot slices')
        self.time_graph.setLabel('left', 'Time spent')
        self.score_graph.setLabel('bottom', 'Shot slices')
        self.score_graph.setLabel('left', 'Scores obtained')
        self.time_data_line = self.time_graph.plot(
            self.x_slice, self.y_time, symbol='+', symbolSize=10, symbolBrush=('b'),
        )
        self.best_data_line = self.score_graph.plot(
            self.x_slice, self.y_best, symbol='o', symbolSize=10, symbolBrush=('g'),
        )
        self.worst_data_line = self.score_graph.plot(
            self.x_slice, self.y_worst, symbol='x', symbolSize=10, symbolBrush=('r'),
        )
        self.setup_crosshair()

    def setup_crosshair(self):
        def timeMouseMoved(event):
            if self.time_graph.sceneBoundingRect().contains(event[0]):
                point = self.time_graph.plotItem.vb.mapSceneToView(event[0])
                index = int(round(point.x()))
                if index in self.x_slice:
                    self.time_graph.setTitle(
                        f"<span style='font-size: 12pt'>slice={index}, "
                        f"<span style='color: blue'>time={self.y_time[index]:0.2f} seconds</span>"
                        f"</span>",
                    )

        def scoreMouseMoved(event):
            if self.score_graph.sceneBoundingRect().contains(event[0]):
                point = self.score_graph.plotItem.vb.mapSceneToView(event[0])
                index = int(round(point.x()))
                if index in self.x_slice:
                    self.score_graph.setTitle(
                        f"<span style='font-size: 12pt'>slice={index}, "
                        f"<span style='color: green'>best={self.y_best[index]}</span>,"
                        f"<span style='color: red'>worst={self.y_worst[index]}</span>"
                        f"</span>",
                    )

        self._time_proxy = pg.SignalProxy(
            self.time_graph.scene().sigMouseMoved, rateLimit=60, slot=timeMouseMoved,
        )
        self._score_proxy = pg.SignalProxy(
            self.score_graph.scene().sigMouseMoved, rateLimit=60, slot=scoreMouseMoved,
        )

    def redraw(self):
        self.time_data_line.setData(self.x_slice, self.y_time)
        self.best_data_line.setData(self.x_slice, self.y_best)
        self.worst_data_line.setData(self.x_slice, self.y_worst)

    def update_charts(self, data):
        self.progressBar.setValue(data['nslice'])
        self.set_best_score(data['best'])
        self.x_slice.append(data['nslice'])
        self.y_time.append(data['shot_time'])
        self.y_best.append(data['best'])
        self.y_worst.append(data['worst'])
        self.redraw()

    def set_best_score(self, score: int):
        self.label_2.setText(f'Best score is {score}')

    def run_solver(self, button, solver: Solver, from_solution, solution_saver):
        slices = solver.slices
        self.time_graph.setXRange(0, slices)
        self.score_graph.setXRange(0, slices)
        self.progressBar.setMaximum(slices)

        self._thread = SolverThread(solver, from_solution)
        self._thread.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.update_charts.connect(self.update_charts)
        self._thread.best_score.connect(self.set_best_score)
        self._thread.timetable.connect(solution_saver)

        self._thread.start()

        button.setEnabled(False)
        self._thread.finished.connect(lambda: button.setEnabled(True))


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
        self.edit_faculty.setText('/home/daniil/projects/freestyle/diss/sources/tests/assets/toy.in')
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
        self.progress_window.run_solver(self.button_start, solver, from_solution, self.save_timetable)

    def save_timetable(self, timetable):
        if self.edit_output.text():
            with open(self.edit_output.text(), 'wt') as output:
                timetable.to_stream(output)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - [%(levelname)s] - [%(name)s] - %(filename)s:%(lineno)d - %(message)s',
        level='INFO',
    )
    app = qt.QApplication(sys.argv)
    window = TimetableWindow()
    window.show()
    sys.exit(app.exec_())
