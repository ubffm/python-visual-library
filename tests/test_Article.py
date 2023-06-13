import pytest

from VisualLibrary import Article


class TestArticle:
    @pytest.mark.parametrize("article", ["9738495"], indirect=True)
    def test_article_with_only_start_page(self, article: Article):
        assert article.page_range.start == "248"
        assert article.page_range.end == "248"

    @pytest.fixture
    def article(self, request, article_test_data_directory, mets_importer) -> Article:
        article_id = request.param
        article_file_name = article_test_data_directory / f"article_{article_id}.xml"

        with open(article_file_name, "r") as f:
            file_content_string = f.read()

        mets_importer.parse_xml(file_content_string)

        return Article(vl_id=article_id, xml_importer=mets_importer, parent=None)
