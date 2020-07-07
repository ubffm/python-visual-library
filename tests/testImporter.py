from importer.importer import MetsImporter, BASE64_ENCODING_STRING
from pathlib import Path

TEST_DATA_DIRECTORY = './data'


class TestImporter:
    def test_mets_importer(self):
        mets_importer = MetsImporter(debug=True)

        xml_data = get_oai_response_xml_string()
        mets_importer.parse_xml(xml_data)

        assert len(mets_importer.structure) == 1
        assert len(mets_importer.structure[0].sections) == 1
        assert len(mets_importer.files_dict) == 6

        for f in mets_importer.files_dict.values():
            assert f.date_uploaded is not None
            assert f.date_modified is not None
            assert f.size > 0
            assert f.mime_type is not None
            assert f.languages is not None
            assert f.data is not None
            assert f.name is not None

            # This should be set by the exporter
            assert f.encoding is None


def get_oai_response_xml_string():
    oai_response_file_path = Path(TEST_DATA_DIRECTORY, 'oai-response.xml')
    with open(str(oai_response_file_path), 'r') as oai_response:
        oai_response_string = oai_response.read()
    return  oai_response_string
