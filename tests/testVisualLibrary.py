from ..VisualLibrary import VisualLibrary, Volume, Journal, Article


class TestVisualLibrary:
    def test_call_for_journal(self):
        vl_page_id = '10688403'
        vl = VisualLibrary()
        vl_object = vl.get_element_for_id(vl_page_id)

        assert isinstance(vl_object, Journal)
        assert vl_object.label == 'Decheniana'
        assert vl_object.publication_date == '1937-1954'


    def test_call_for_volume(self):
        vl_page_id = '10771471'
        vl = VisualLibrary()
        vl_object = vl.get_element_for_id(vl_page_id)

        assert isinstance(vl_object, Volume)
        assert vl_object.label == '95 A (1937)'
        assert vl_object.publication_date == 1937

        counter = 0
        for _ in vl_object.articles:
            counter += 1

        assert counter == 7





