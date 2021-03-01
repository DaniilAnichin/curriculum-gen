packagedir = timetable
testdir = tests/


.PHONY: clean ci


# *** Clean & Build ************************************************************

clean: clean-pyc clean-test ## remove all build, doc, test, coverage and Python artifacts

clean-pyc: ## remove Python file artifacts
	@find . -name '*.pyc' -exec rm -f {} +
	@find . -name '*.pyo' -exec rm -f {} +
	@find . -name '*~' -exec rm -f {} +
	@find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## remove test and coverage artifacts
	@rm -fr .tox/
	@rm -f .coverage
	@rm -fr htmlcov/
	@rm -fr .mypy_cache
	@rm -fr .pytest_cache

# *** Test *********************************************************************

bandit:
	@echo "running bandit (code security)"
	@bandit --recursive --silent --ini setup.cfg $(packagedir)

safety:
	@echo "running safety (vulnerable dependency versions)"
	@safety check --full-report --bare

radon:
	@echo "running radon (code complexity)"
	@! radon cc $(packagedir) -a -nc | grep .

flake8:
	@echo "running flake8 (code style)"
	@flake8 $(packagedir) ./tests/ --exclude ./tests/assets/

isort:
	@echo "running isort (imports order)"
	@isort --check-only --diff --quiet $(packagedir) $(testdir)

mypy:
	@echo "running mypy (type checking)"
	@mypy $(packagedir) $(testdir) --pretty --ignore-missing-imports --no-error-summary

test:
ifeq ($(skiptest),)
	# Specify skiptest=1 if you want to skip pytest
endif
ifeq ($(testpath),)
	# Specify testpath=path/to/tests if you want to run specific tests
endif
ifeq ($(testname),)
	# Specify testname=test_name if you want to run specific tests by name
endif
ifeq ($(failed_only),)
	# Specify failed_only=t if you want to run previously failed tests
endif
ifeq ($(skiptest), 1)
	@echo "*** SKIPPED PYTEST ***"
else
	DOTENV_PATH=.env.test \
	pytest \
		--junitxml=report.xml \
		--cov-report html:htmlcov \
		--cov-report xml:coverage.xml \
		$(if $(failed_only),--last-failed,) \
		$(if $(or $(testpath),$(testname),$(failed_only)),,--cov=$(packagedir)) \
		$(or $(testpath),$(testdir)) \
		$(if $(testname),-k $(testname),)
endif


ci: clean bandit safety flake8 isort mypy test
	@true
