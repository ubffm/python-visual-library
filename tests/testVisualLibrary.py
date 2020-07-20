import os

from bs4 import BeautifulSoup as Soup
from datetime import datetime

from .data import full_text_data
from ..VisualLibrary import VisualLibrary, Volume, Journal, Article, Page, File


IMAGE_MIME_TYPE = 'image/jpeg'

class TestVisualLibrary:
    def test_call_for_journal(self):
        vl_page_id = '10688403'
        vl = VisualLibrary()
        vl_object = vl.get_element_for_id(vl_page_id)

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
        vl_page_id = '10771471'
        vl = VisualLibrary()
        vl_object = vl.get_element_for_id(vl_page_id)

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
        vl_page_id = '10902187'
        vl = VisualLibrary()
        vl_object = vl.get_element_for_id(vl_page_id)

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

        for page in vl_object.pages:
            assert page.image_min_resolution.mime_type == IMAGE_MIME_TYPE
            assert page.image_max_resolution.mime_type == IMAGE_MIME_TYPE
            assert page.image_default_resolution.mime_type == IMAGE_MIME_TYPE
            assert page.thumbnail.mime_type == IMAGE_MIME_TYPE
            assert len(page.full_text) > 0

        assert len(vl_object.full_text) > 2000


class TestPage:
    @staticmethod
    def get_new_page_with_data(xml_file_name_in_data_folder, page_id_in_data):
        this_files_directory = os.path.dirname(os.path.realpath(__file__))
        xml_file_path_string = '{base_dir}/data/{file_name}'.format(base_dir=this_files_directory,
                                                                    file_name=xml_file_name_in_data_folder)
        with open(xml_file_path_string, 'r') as article_xml_file:
            xml_data = article_xml_file.read()
        xml_soup = Soup(xml_data, 'lxml')
        page_element_in_data = xml_soup.find(attrs={'id': page_id_in_data, 'type': 'page'})

        return Page(page_element_in_data, xml_soup)

    def test_page_instantiation(self):
        page = TestPage.get_new_page_with_data(xml_file_name_in_data_folder='article-oai-response.xml',
                                               page_id_in_data='phys9660761')

        assert page.label == 'Seite 61'
        assert page.order == '57'

        creation_date = datetime.fromisoformat('2018-05-08')
        mime_type_image_string = IMAGE_MIME_TYPE

        page_thumbnail_file = page.thumbnail
        test_file(page_thumbnail_file, expected_url='http://vl.ub.uni-frankfurt.de/download/webcache/128/9660761',
                  expected_date=creation_date, expected_mime_type=mime_type_image_string)

        page_default_res_file = page.image_default_resolution
        test_file(page_default_res_file, expected_url='http://vl.ub.uni-frankfurt.de/download/webcache/1000/9660761',
                  expected_date=creation_date, expected_mime_type=mime_type_image_string)

        page_maximum_res_file = page.image_max_resolution
        test_file(page_maximum_res_file, expected_url='http://vl.ub.uni-frankfurt.de/download/webcache/1504/9660761',
                  expected_date=creation_date, expected_mime_type=mime_type_image_string)

        page_minimum_res_file = page.image_min_resolution
        test_file(page_minimum_res_file, expected_url='http://vl.ub.uni-frankfurt.de/download/webcache/600/9660761',
                  expected_date=creation_date, expected_mime_type=mime_type_image_string)

        full_text = full_text_data.phys9660761_full_text
        page_text = page.full_text
        assert full_text == page_text


def test_file(file: File, expected_url: str, expected_date: datetime, expected_mime_type: str):
    assert file.url == expected_url
    assert file.date_uploaded.date() == expected_date.date()
    assert file.mime_type == expected_mime_type

