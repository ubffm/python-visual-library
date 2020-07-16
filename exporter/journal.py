from abc import ABC, abstractmethod
import xml.etree.ElementTree as ET
from copy import deepcopy


class OjsExportUnit(ABC):

    ARTICLE_REFERENCE_STRING = 'ART'

    LANGUAGE_CODES = {
        'ger': 'de_DE',
        'eng': 'en_US'
    }

    OJS_XML_ELEMENT_AUTHOR_STRING = 'author'
    OJS_XML_ELEMENT_GIVEN_NAME_STRING = 'givenname'
    OJS_XML_ELEMENT_FAMILY_NAME_STRING = 'familyname'
    OJS_XML_ELEMENT_ID_STRING = 'id'
    OJS_ELEMENT_ID_ATTRIBUTES = {
        'type': 'internal',
        'advice': 'ignore'
    }
    OJS_ELEMENT_TITLE_STRING = 'title'
    OJS_ELEMENT_SUBTITLE_STRING = 'subtitle'

    XML_ATTRIBUTE_LOCAL_STRING = 'locale'

    def __init__(self, section):
        self.label = section.label
        self.order = section.order
        self.languages = section.languages
        self.xml_root = None

    @abstractmethod
    def get_xml(self):
        pass

    def _add_subelement_to_root(self, element_tag_name: str) -> ET.SubElement:
        return ET.SubElement(self.xml_root, element_tag_name)

    def _add_title_to_root(self):
        title_element = self._add_subelement_to_root(self.OJS_ELEMENT_TITLE_STRING)

        # Add primary language as title, hence self.language[0]
        title_element.attrib[self.XML_ATTRIBUTE_LOCAL_STRING] = self._resolve_language_code(self.languages[0])

    def _resolve_language_code(self, language_string: str) -> str:
        return self.LANGUAGE_CODES.get(language_string)


class Journal(OjsExportUnit):
    def __init__(self):
        self.issues = []


class Volume(OjsExportUnit):
    pass


class Issue(OjsExportUnit):
    def __init__(self):
        self.articles = []


class Article(OjsExportUnit):

    ARTICLE_ID_COUNTER = 1

    XML_ATTRIBUTE_LANGUAGE_STRING = 'language'
    XML_ATTRIBUTE_SEQUENCE_STRING = 'seq'

    XML_ROOT_NAME_STRING = 'article'
    XML_ROOT_DEFAULT_ATTRIBUTES = {
        'xmlns': 'http://pkp.sfu.ca',
        'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'xsi:schemaLocation': 'http://pkp.sfu.ca native.xsd',
        'stage': 'production',
        'section_ref': OjsExportUnit.ARTICLE_REFERENCE_STRING
    }

    XML_ATTRIBUTE_PRIMARY_CONTACT_STRING = 'primary_contact'
    OJS_XML_ELEMENT_AUTHOR_ATTRIBUTES = {
        XML_ATTRIBUTE_PRIMARY_CONTACT_STRING: False,
        'user_group_ref': 'Author',
        'include_in_browse': True
    }

    def __init__(self, section):
        super().__init__(section)
        self.id = self._get_article_id()
        self.files = section.files
        self.primary_author_is_set = False
        self.date_submitted = self.files[0].date_uploaded

    def get_locale(self):
        return self._resolve_language_code(self.languages[0])

    def get_xml(self):
        self.xml_root = ET.Element(self.XML_ROOT_NAME_STRING)
        self.xml_root.attrib = deepcopy(self.XML_ROOT_DEFAULT_ATTRIBUTES)
        self.xml_root.attrib[self.XML_ATTRIBUTE_SEQUENCE_STRING] = self.order

        self._add_language_to_root_attributes()
        self._add_id_element_to_root()

    def _add_author_to_root(self, first_name, family_name):
        author_elem = self._add_subelement_to_root(self.OJS_XML_ELEMENT_AUTHOR_STRING)
        is_primary_author = True if not self.primary_author_is_set else False
        author_elem.attrib = self.OJS_XML_ELEMENT_AUTHOR_ATTRIBUTES
        author_elem.attrib[self.XML_ATTRIBUTE_PRIMARY_CONTACT_STRING] = is_primary_author

        first_name_elem = ET.SubElement(author_elem, self.OJS_XML_ELEMENT_GIVEN_NAME_STRING)
        first_name_elem.attrib[self.XML_ATTRIBUTE_LOCAL_STRING] = self.get_locale()
        first_name_elem.text = first_name

        family_name_elem = ET.SubElement(author_elem, self.OJS_XML_ELEMENT_FAMILY_NAME_STRING)
        family_name_elem.attrib[self.XML_ATTRIBUTE_LOCAL_STRING] = self.get_locale()
        family_name_elem.text = family_name

        self.primary_author_is_set = True

    def _add_id_element_to_root(self):
        elem_id = self._add_subelement_to_root(self.OJS_XML_ELEMENT_ID_STRING)
        elem_id.attrib = self.OJS_ELEMENT_ID_ATTRIBUTES
        elem_id.text = self.id

    def _add_language_to_root_attributes(self):
        for language_code in self.languages:
            locale = self._resolve_language_code(language_code)
            if locale is not None:
                self.xml_root.attrib[self.XML_ATTRIBUTE_LOCAL_STRING] = locale
                self.xml_root.attrib[self.XML_ATTRIBUTE_LANGUAGE_STRING] = locale.split('_')[0]

    def _get_article_id(self) -> int:
        article_id = self.ARTICLE_ID_COUNTER
        self.ARTICLE_ID_COUNTER = self.ARTICLE_ID_COUNTER + 1
        return article_id





