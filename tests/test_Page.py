import os
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup as Soup

from VisualLibrary import Page, File
from .data.VisualLibrary import full_text_data

IMAGE_MIME_TYPE = 'image/jpeg'


class TestPage:
    @staticmethod
    def get_new_page_with_data(xml_file_name_in_data_folder, page_id_in_data):
        this_files_directory = os.path.dirname(os.path.realpath(__file__))
        xml_file_path_string = '{base_dir}/data/Page/{file_name}'.format(base_dir=this_files_directory,
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
        assert page.id == '9660761'

        creation_date = None
        mime_type_image_string = IMAGE_MIME_TYPE

        page_thumbnail_file = page.thumbnail
        file_test(page_thumbnail_file, expected_url='https://sammlungen.ub.uni-frankfurt.de/biodiv/download/webcache/128/9660761',
                  expected_date=creation_date, expected_mime_type=mime_type_image_string)

        page_default_res_file = page.image_default_resolution
        file_test(page_default_res_file, expected_url='https://sammlungen.ub.uni-frankfurt.de/biodiv/download/webcache/1000/9660761',
                  expected_date=creation_date, expected_mime_type=mime_type_image_string)

        page_maximum_res_file = page.image_max_resolution
        file_test(page_maximum_res_file, expected_url='https://sammlungen.ub.uni-frankfurt.de/biodiv/download/webcache/0/9660761',
                  expected_date=creation_date, expected_mime_type=mime_type_image_string)

        page_minimum_res_file = page.image_min_resolution
        file_test(page_minimum_res_file, expected_url='https://sammlungen.ub.uni-frankfurt.de/biodiv/download/webcache/504/9660761',
                  expected_date=creation_date, expected_mime_type=mime_type_image_string)

        full_text = full_text_data.phys9660761_full_text
        page_text = page.full_text
        assert full_text == page_text


def file_test(file: File, expected_url: str, expected_date: Optional[datetime], expected_mime_type: str):
    assert file.url == expected_url
    if file.date_uploaded is not None:
        assert file.date_uploaded.date() == expected_date.date()
    assert file.mime_type == expected_mime_type
