from ..VisualLibrary import VisualLibrary, Volume, Journal, Article


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

        publisher = vl_object.publishers[0]
        assert publisher.name == 'Naturhistorischer Verein der Rheinlande und Westfalens'
        assert publisher.uri == 'http://d-nb.info/gnd/40094-4'

        counter = 0
        for _ in vl_object.volumes:
            counter += 1

        assert counter == 6

    def test_call_for_volume(self):
        vl_page_id = '10771471'
        vl = VisualLibrary()
        vl_object = vl.get_element_for_id(vl_page_id)

        assert isinstance(vl_object, Volume)
        assert vl_object.label == '95 A (1937)'
        assert vl_object.publication_date == '1937'

        counter = 0
        for _ in vl_object.articles:
            counter += 1

        assert counter == 7

    def test_call_for_article(self):
        vl_page_id = '10902187'
        vl = VisualLibrary()
        vl_object = vl.get_element_for_id(vl_page_id)

        assert isinstance(vl_object, Article)
        assert vl_object.title == 'Diluvialer Gehängeschutt südlich von Bonn'
        assert vl_object.subtitle == 'mit 3 Textfiguren'
        assert len(vl_object.authors) == 1

        author = vl_object.authors[0]
        assert author.given_name == 'Max'
        assert author.family_name == 'Richter'

        assert vl_object.publication_date == '1937'
        assert vl_object.languages == {'ger'}
