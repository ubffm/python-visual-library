import os

from ..VisualLibrary import VisualLibrary, Volume, Journal, Article

IMAGE_MIME_TYPE = 'image/jpeg'

this_files_directory = os.path.dirname(os.path.realpath(__file__))
TEST_DATA_FOLDER = '{base_dir}/data/VisualLibrary'.format(base_dir=this_files_directory)


class TestVisualLibrary:
    def test_call_for_journal(self):
        xml_test_file_path = '{test_data_folder}/journal-oai-response.xml'.format(test_data_folder=TEST_DATA_FOLDER)

        vl = VisualLibrary()
        vl_object = vl.get_element_from_xml_file(xml_test_file_path)

        assert isinstance(vl_object, Journal)
        assert vl_object.label == 'Decheniana'
        assert vl_object.title == 'Decheniana'
        assert vl_object.subtitle == 'Verhandlungen des Naturhistorischen Vereins der Rheinlande und Westfalens'
        assert vl_object.publication_date == '1937-1954'
        assert vl_object.languages == {'ger'}
        assert len(vl_object.publishers) == 1
        assert not vl_object.files

        assert vl_object.parent is None

        publisher = vl_object.publishers[0]
        assert publisher.name == 'Naturhistorischer Verein der Rheinlande und Westfalens'
        assert publisher.uri == 'http://d-nb.info/gnd/40094-4'

        counter = 0
        for volume in vl_object.volumes:
            counter += 1
            assert volume.parent is vl_object

        assert counter == 6

    def test_call_for_volume(self):
        xml_test_file_path = '{test_data_folder}/volume-oai-response.xml'.format(test_data_folder=TEST_DATA_FOLDER)

        vl = VisualLibrary()
        vl_object = vl.get_element_from_xml_file(xml_test_file_path)

        assert isinstance(vl_object, Volume)
        assert vl_object.label == '95 A (1937)'
        assert vl_object.publication_date == '1937'

        assert vl_object.parent is None

        counter = 0
        for article in vl_object.articles:
            counter += 1
            assert len(article.files) == 1
            assert article.parent is vl_object

        assert counter == 7

    def test_call_for_article(self):
        xml_test_file_path = '{test_data_folder}/article-oai-response.xml'.format(test_data_folder=TEST_DATA_FOLDER)

        vl = VisualLibrary()
        vl_object = vl.get_element_from_xml_file(xml_test_file_path)

        assert isinstance(vl_object, Article)
        assert vl_object.title == 'Diluvialer Gehängeschutt südlich von Bonn'
        assert vl_object.subtitle == 'mit 3 Textfiguren'
        assert len(vl_object.authors) == 1

        assert vl_object.parent is None

        author = vl_object.authors[0]
        assert author.given_name == 'Max'
        assert author.family_name == 'Richter'

        assert vl_object.publication_date == '1937'
        assert vl_object.languages == {'ger'}
        assert vl_object.page_range.start == '283'
        assert vl_object.page_range.end == '287'

        for page in vl_object.pages:
            assert page.image_min_resolution.mime_type == IMAGE_MIME_TYPE
            assert page.image_max_resolution.mime_type == IMAGE_MIME_TYPE
            assert page.image_default_resolution.mime_type == IMAGE_MIME_TYPE
            assert page.thumbnail.mime_type == IMAGE_MIME_TYPE
            assert len(page.full_text) > 0

        assert len(vl_object.full_text) == 8020
