import os
import pytest

from ..VisualLibrary import VisualLibrary, Volume, Journal, Article, Page, remove_letters_from_alphanumeric_string

IMAGE_MIME_TYPE = 'image/jpeg'

this_files_directory = os.path.dirname(os.path.realpath(__file__))
TEST_DATA_FOLDER = '{base_dir}/data/VisualLibrary'.format(base_dir=this_files_directory)


class TestVisualLibrary:
    @pytest.fixture
    def visual_libary(self):
        return VisualLibrary()

    def test_publication_year_hard_to_fetch(self, visual_libary):
        issue_id = '10823380'
        vl_issue = visual_libary.get_element_for_id(issue_id)

        assert vl_issue.publication_date == '1992'

    def test_call_for_journal(self, visual_libary):
        xml_test_file_path = '{test_data_folder}/journal-oai-response.xml'.format(test_data_folder=TEST_DATA_FOLDER)

        vl_object = visual_libary.get_element_from_xml_file(xml_test_file_path)
        journal_label = 'Decheniana: Verhandlungen des Naturhistorischen Vereins der Rheinlande und Westfalens'

        assert isinstance(vl_object, Journal)
        assert vl_object.label == 'Decheniana'
        assert vl_object.title == 'Decheniana'
        assert vl_object.subtitle == 'Verhandlungen des Naturhistorischen Vereins der Rheinlande und Westfalens'
        assert vl_object.publication_date == '1937-1954'
        assert vl_object.languages == ['ger']
        assert len(vl_object.publishers) == 1
        assert not vl_object.files
        assert vl_object.number is None
        assert vl_object.journal_label == journal_label

        assert vl_object.parent is None

        publisher = vl_object.publishers[0]
        assert publisher.name == 'Naturhistorischer Verein der Rheinlande und Westfalens'
        assert publisher.uri == 'http://d-nb.info/gnd/40094-4'

        counter = 0
        for volume in vl_object.elements:
            counter += 1
            assert volume.parent is vl_object

        assert counter == 6

    def test_call_for_volume(self, visual_libary):
        xml_test_file_path = '{test_data_folder}/volume-oai-response.xml'.format(test_data_folder=TEST_DATA_FOLDER)

        vl_object = visual_libary.get_element_from_xml_file(xml_test_file_path)
        journal_label = 'Decheniana: Verhandlungen des Naturhistorischen Vereins der Rheinlande und Westfalens'

        assert isinstance(vl_object, Volume)
        assert vl_object.label == '95 A (1937)'
        assert vl_object.publication_date == '1937'
        assert vl_object.number == '95 A'
        assert vl_object.journal_label == journal_label

        counter = 0
        for article in vl_object.articles:
            counter += 1
            assert len(article.files) == 1
            assert article.parent is vl_object
            assert article.journal_label == journal_label

        assert counter == 7

    def test_call_for_article(self, visual_libary):
        xml_test_file_path = '{test_data_folder}/article-oai-response.xml'.format(test_data_folder=TEST_DATA_FOLDER)

        vl_object = visual_libary.get_element_from_xml_file(xml_test_file_path)
        journal_label = 'Decheniana: Verhandlungen des Naturhistorischen Vereins der Rheinlande und Westfalens'

        assert isinstance(vl_object, Article)
        assert vl_object.title == 'Diluvialer Gehängeschutt südlich von Bonn'
        assert vl_object.subtitle == 'mit 3 Textfiguren'
        assert len(vl_object.authors) == 1
        assert vl_object.number is None
        assert vl_object.journal_label == journal_label

        assert isinstance(vl_object.parent, Volume)

        author = vl_object.authors[0]
        assert author.given_name == 'Max'
        assert author.family_name == 'Richter'

        assert vl_object.publication_date == '1937'
        assert vl_object.languages == ['ger']
        assert vl_object.page_range.start == '283'
        assert vl_object.page_range.end == '287'

        for page in vl_object.pages:
            assert page.image_min_resolution.mime_type == IMAGE_MIME_TYPE
            assert page.image_max_resolution.mime_type == IMAGE_MIME_TYPE
            assert page.image_default_resolution.mime_type == IMAGE_MIME_TYPE
            assert page.thumbnail.mime_type == IMAGE_MIME_TYPE
            assert len(page.full_text) > 0

        assert len(vl_object.full_text) == 8020

    def test_call_for_single_page(self, visual_libary):
        single_page_id = '10769418'

        page = visual_libary.get_page_by_id(single_page_id)

        full_text_snippet = 'in Mitteleuropa ist durch den Menschen nachhaltig verändert\n'

        assert isinstance(page, Page)
        assert full_text_snippet in page.full_text
        assert page.label == 'Seite 1'
        assert page.order == '11'

    def test_deriving_types(self, visual_libary):
        journal_id = '10827059'

        vl_journal = visual_libary.get_element_for_id(journal_id)

        assert isinstance(vl_journal, Volume)
        issues = vl_journal.issues
        assert len(issues) == 2
        assert issues[0].label == '1'
        assert issues[0].number == '1'  # This is a bug in the submitted data! Should be 31!
        assert issues[1].label == '2'
        assert issues[1].number == '35'

        issue = issues[1]
        assert len(issue.articles) == 37

    def test_keywords_in_issue(self, visual_libary):
        issue_id = '10750063'

        vl_issue = visual_libary.get_element_for_id(issue_id)

        assert len(vl_issue.keywords) == 5
        assert vl_issue.keywords == ['Köln', 'Pollenanalyse', 'Wald', 'Waldgesellschaft', 'Flussterrasse']

    def test_root_has_articles(self, visual_libary):
        journal_id = '10773114'

        vl_root = visual_libary.get_element_for_id(journal_id)

        assert isinstance(vl_root, Journal)
        assert vl_root.title == 'Decheniana'
        assert vl_root.publication_date == '1955-'
        publisher = vl_root.publishers[0]
        assert publisher.name == 'Naturhistorischer Verein der Rheinlande und Westfalens'

        articles = vl_root.articles
        assert len(articles) == 25
        volumes = vl_root.volumes
        expected_volume_ids = ['10821674', '10821917', '10807409', '10822417', '10822858', '10724145', '10766813',
                               '10771487', '10827059', '9825034', '10821178', '10804777']
        assert [vol.id for vol in volumes] == expected_volume_ids

    def test_article_with_translated_title(self, visual_libary):
        article_id = '10799758'

        vl_article = visual_libary.get_element_for_id(article_id)

        assert isinstance(vl_article.title, dict)
        assert vl_article.title['ger'] == 'Artzusammensetzung von Körbchenmuscheln Corbicula im Niederrhein'
        assert vl_article.title['eng'] == 'On the composition of species of the Asian Clams Corbicula in the Lower' \
                                            ' Rhine Mollusca: Bivalvia: Corbiculidae'

        assert vl_article.subtitle['ger'] is None
        assert vl_article.subtitle['eng'] == 'mit 1 Tabelle und 2 Abbildungen'

    def test_articles_below_blob_node(self, visual_libary):
        issue_id = '11017998'

        vl_issue = visual_libary.get_element_for_id(issue_id)

        articles = vl_issue.articles
        assert len(articles) == 20

    def test_issue_with_articles_not_recognized(self, visual_libary):
        issue_id = '10821674'

        vl_issue = visual_libary.get_element_for_id(issue_id)

        articles = vl_issue.articles
        assert len(articles) == 8

    def test_multilanguage_issue(self, visual_libary):
        issue_id = '10804777'

        vl_issue = visual_libary.get_element_for_id(issue_id)

        assert vl_issue.title['ger'] == 'Geologie und Paläontologie im Devon und Tertiär der ICE-Trasse im ' \
                                        'Siebengebirge'
        assert vl_issue.subtitle['ger'] == 'Ergebnisse der baubegleitenden Untersuchungen in zwei Tunnelbauwerken ' \
                                           'der ICE-Neubaustrecke Köln-Rhein/Main'
        assert vl_issue.title['eng'] == 'Geology and paleontology of the Devonian and Tertiary at the ICE line in ' \
                                        'the Siebengebirge (Bonn, FRG)'
        assert vl_issue.subtitle['eng'] is None


def test_remove_letters_from_alphanumeric_string():
    assert remove_letters_from_alphanumeric_string('1071953)') == '1071953'
    assert remove_letters_from_alphanumeric_string('107 (1953)') == '1071953'
    assert remove_letters_from_alphanumeric_string('1. Lieferung') == '1'
