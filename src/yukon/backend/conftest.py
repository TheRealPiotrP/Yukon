#
# Copyright (C) 2020  UAVCAN Development Team  <uavcan.org>
#               2020  dronesolutions.io. All rights reserved.
# This software is distributed under the terms of the MIT License.
#
"""
Fixtures for our tests.
"""

import pathlib
import re
import tempfile
import textwrap
import typing
from doctest import ELLIPSIS
from fnmatch import fnmatch

import pytest
from sybil import Sybil
from sybil.integration.pytest import SybilFile
from sybil.parsers.codeblock import CodeBlockParser
from sybil.parsers.doctest import DocTestParser


class GenTestPaths:
    """Helper to generate common paths used in our unit tests."""

    def __init__(self, test_file: str, keep_temporaries: bool, node_name: str):
        test_file_path = pathlib.Path(test_file)
        self.test_name = '{}_{}'.format(test_file_path.parent.stem, node_name)
        self.test_dir = test_file_path.parent
        search_dir = self.test_dir.resolve()
        while search_dir.is_dir() and not (search_dir / pathlib.Path('src')).is_dir():
            search_dir = search_dir.parent
        self.root_dir = search_dir
        self.templates_dir = self.test_dir / pathlib.Path('templates')
        self.dsdl_dir = self.test_dir / pathlib.Path('dsdl')

        self._keep_temp = keep_temporaries
        self._out_dir = None  # type: typing.Optional[typing.Any]
        self._build_dir = None  # type: typing.Optional[pathlib.Path]
        self._dsdl_dir = None  # type: typing.Optional[pathlib.Path]
        print('Paths for test "{}" under dir {}'.format(self.test_name, self.test_dir))
        print('(root directory: {})'.format(self.root_dir))

    @property
    def out_dir(self) -> pathlib.Path:
        """
        The directory to place test output under for this test case.
        """
        if self._out_dir is None:
            if self._keep_temp:
                self._out_dir = lambda: None
                test_output_dir = self._ensure_dir(self.build_dir / pathlib.Path(self.test_name))
                setattr(self._out_dir, 'name', str(test_output_dir))
            else:
                self._out_dir = tempfile.TemporaryDirectory(dir=str(self.build_dir))
        return pathlib.Path(self._out_dir.name)

    @property
    def build_dir(self) -> pathlib.Path:
        if self._build_dir is None:
            self._build_dir = self._ensure_dir(self.root_dir / pathlib.Path('build'))
        return self._build_dir

    @staticmethod
    def _ensure_dir(path_dir: pathlib.Path) -> pathlib.Path:
        try:
            path_dir.mkdir()
        except FileExistsError:
            pass
        if not path_dir.exists() or not path_dir.is_dir():
            raise RuntimeWarning('Test directory "{}" was not setup properly. Tests may fail.'.format(path_dir))
        return path_dir


@pytest.fixture(scope='function')
def gen_paths(request):  # type: ignore
    return GenTestPaths(str(request.fspath), request.config.option.keep_generated, request.node.name)


def pytest_addoption(parser):  # type: ignore
    parser.addoption("--keep-generated", action="store_true", help=textwrap.dedent('''
        If set then the temporary directory used to generate files for each test will be left after
        the test has completed. Normally this directory is temporary and therefore cleaned up automatically.
        :: WARNING ::
        This will leave orphaned files on disk. They won't be big but there will be a lot of them.
        :: WARNING ::
        Do not run tests in parallel when using this option.
    '''))


class _UniqueNameEvaluator:

    def __init__(self) -> None:
        self._found_names = set()  # type: typing.Set[str]

    def __call__(self, expected_pattern: str, actual_value: str) -> None:
        assert re.match(expected_pattern, actual_value) is not None
        assert actual_value not in self._found_names
        self._found_names.add(actual_value)


@pytest.fixture(scope='function')
def unique_name_evaluator(request):  # type: ignore
    """
    Class that defined ``assert_is_expected_and_unique`` allowing assertion that a set of values
    in a single test adhere to a provided pattern and are unique values (comparted to other values
    provided to this method).
    .. code-block:: python
        def test_is_unique(unique_name_evaluator) -> None:
            value0 = '_foo0_'
            value1 = '_foo1_'
            unique_name_evaluator(r'_foo\\d_', value0)
            unique_name_evaluator(r'_foo\\d_', value1)
            # This next line should fail because value 0 was already evaluated so it
            # is not unique
            unique_name_evaluator(r'_foo\\d_', value0)
    """
    return _UniqueNameEvaluator()


def _pytest_integration_that_actually_works() -> typing.Callable:
    """
    Sybil matching is pretty broken. We'll have to help it out here. The problem is that
    exclude patterns passed into the Sybil object are matched against file name stems such that
    files cannot be excluded by path.
    """

    _excludes = [
        '**/markupsafe/*',
        '**/jinja2/*',
    ]

    _sy = Sybil(
        parsers=[
            DocTestParser(optionflags=ELLIPSIS),
            CodeBlockParser(),
        ],
        fixtures=['gen_paths']
    )

    def pytest_collect_file(parent: typing.Any, path: typing.Any) -> typing.Optional[SybilFile]:
        if fnmatch(str(path), '**/backend/**/*.py') and not any(fnmatch(str(path), pattern) for pattern in _excludes):
            return SybilFile(path, parent, _sy)
        else:
            return None

    return pytest_collect_file


pytest_collect_file = _pytest_integration_that_actually_works()
