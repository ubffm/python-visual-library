import os
import re
from datetime import datetime
from pathlib import Path

from VisualLibrary.importer.importer import (
    DEBUG_FILE_DATA_CONTENT_BYTE_STRING,
    File,
    MetsImporter,
)

CURRENT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
TEST_DATA_DIRECTORY = "{base_dir}/data/Importer".format(base_dir=CURRENT_DIRECTORY)


class TestImporter:
    def test_mets_importer(self):
        """Metadata from:
        https://sammlungen.ub.uni-frankfurt.de/oai/?verb=GetRecord&metadataPrefix=mets&identifier=10771471
        """
        mets_importer = MetsImporter(debug=True)

        xml_data = get_oai_response_xml_string()
        mets_importer.parse_xml(xml_data)

        assert len(mets_importer.structure) == 1

        journal = mets_importer.structure[0]
        assert len(journal.resource_pointers) == 1
        assert journal.metadata is not None

        issue = journal.sections[0]
        assert len(issue.resource_pointers) == 0
        assert issue.metadata is not None

        articles = issue.sections
        pdf_creation_date = datetime.fromisoformat("2020-06-08")
        articles_with_files = [
            "log10773126",
            "log10773134",
            "log10773142",
            "log10773155",
            "log10773161",
            "log10773164",
            "log10773171",
            "log10773178",
        ]

        for article in articles:
            assert len(article.resource_pointers) >= 1

            if article.id in articles_with_files:
                for f in article.files:
                    assert f.date_uploaded.date() == pdf_creation_date.date()
                    assert f.date_modified.date() == pdf_creation_date.date()
                    assert f.size > 0
                    assert f.mime_type == "application/pdf"
                    assert f.languages == {"ger"}
                    assert f.data == DEBUG_FILE_DATA_CONTENT_BYTE_STRING
                    assert re.match(r"pdf_[0-9]*", f.name)
                    assert article.metadata is not None
            else:
                assert len(article.files) == 0


def get_oai_response_xml_string():
    oai_response_file_path = Path(TEST_DATA_DIRECTORY, "volume-oai-response.xml")
    with open(str(oai_response_file_path), "r") as oai_response:
        oai_response_string = oai_response.read()
    return oai_response_string


class TestFileClass:
    def test_file_data_base64_encoding(self):
        file = File()
        file.data = b"This is a test pdf file content."
        base64_encoded_data_content = file.get_data_in_base64_encoding()
        assert (
            base64_encoded_data_content
            == "VGhpcyBpcyBhIHRlc3QgcGRmIGZpbGUgY29udGVudC4="
        )
