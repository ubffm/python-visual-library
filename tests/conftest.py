import pathlib

import pytest

from VisualLibrary import VisualLibrary
from VisualLibrary.importer.importer import MetsImporter


@pytest.fixture
def visual_library():
    return VisualLibrary()


@pytest.fixture
def mets_importer():
    return MetsImporter()


@pytest.fixture
def test_data_directory():
    current_path = pathlib.Path(__file__).parent
    return current_path / 'data'


@pytest.fixture
def article_test_data_directory(test_data_directory):
    return test_data_directory / 'Article'
