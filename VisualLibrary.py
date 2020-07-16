from collections import namedtuple

from .importer.importer import MetsImporter

import re
import logging


logger = logging.getLogger('VL-Importer')


class VisualLibraryExportElement:
    MODS_TAG_PUBLICATION_DATE_STRING = 'mods:date'
    MODS_TAG_PUBLICATION_DATE_ISSUED_STRING = 'mods:dateissued'
    MODS_TAG_ORIGIN_INFO_STRING = 'mods:origininfo'

    SECTION_LABEL_STRING = 'LABEL'
    SECTION_ORDER_STRING = 'ORDER'

    YES_STRING = 'yes'
    KEY_DATE_STRING = 'keydate'
    LOCTYPE_STRING = 'loctype'
    URL_STRING = 'URL'
    HREF_LINK_STRING = 'xlink:href'

    def __init__(self, vl_id, xml_importer, parent):
        self.id = vl_id
        self.xml_importer = xml_importer
        self.xml_data = xml_importer.xml_data
        self._own_section = self._get_own_sections()
        self.sections = self._own_section.sections

        self.label = self._own_section.label
        self.order = self._own_section.order
        self.publication_date = None
        self.parent = parent
        self.files = self._own_section.files

        self._extract_publication_date_from_metadata()

    def _extract_publication_date_from_metadata(self):
        def get_earliest_date():
            earliest_date_element = None
            for origin_info in origin_info_elements:
                date = origin_info.find(self.MODS_TAG_PUBLICATION_DATE_STRING, {self.KEY_DATE_STRING: self.YES_STRING})

                if date is None:
                    date = origin_info if origin_info.name == self.MODS_TAG_PUBLICATION_DATE_STRING else None

                if date is not None:
                    date = int(date.text)
                    if earliest_date_element is not None:
                        if earliest_date_element > date:
                            earliest_date_element = date
                    else:
                        earliest_date_element = date

            return earliest_date_element

        origin_info_elements = self._own_section.metadata.find_all([self.MODS_TAG_PUBLICATION_DATE_STRING,
                                                                    self.MODS_TAG_PUBLICATION_DATE_ISSUED_STRING])
        self.publication_date = get_earliest_date()

    def _get_own_sections(self):
        return self.xml_importer.get_section_by_id(self.id)

    def _resolve_depending_sections(self):
        for section in self.sections:
            for instance in self._resolve_resource_pointers(section):
                yield instance

    def _create_section_instance(self, xml_importer, url):
        try:
            xml_importer.parse_xml_from_url(url)
        except ImportError:
            logger.info('The URL {url} could not be resolved -> Skipping!'.format(url=url))
            # The given VL ID is not valid (could be an image).
            return None
        header = get_xml_header_from_vl_response(xml_importer.xml_data)
        section_type = get_object_type_from_xml_header(header)
        if section_type is not None:
            section_id = re.search(r'(?<=identifier=)[0-9]*', url).group()
            return section_type(section_id, xml_importer, parent=self)

    def _resolve_resource_pointers(self, section):
        instantiated_sections = []
        for resource in section.resource_pointer:
            if resource.get(self.LOCTYPE_STRING) == self.URL_STRING:
                url = resource.get(self.HREF_LINK_STRING)
                xml_importer = MetsImporter()
                if url is not None:
                    instantiated_section_type = self._create_section_instance(xml_importer, url)
                    if instantiated_section_type is not None:
                        instantiated_sections.append(instantiated_section_type)

        return instantiated_sections

    @staticmethod
    def _function_is_read_only():
        Exception('This element may not be modified! Read only!')


class Journal(VisualLibraryExportElement):
    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)
        self.volumes = []


class ArticleHandlingExportElement(VisualLibraryExportElement):
    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)
        self.articles = []

    @property
    def articles(self):
        return self._resolve_depending_sections()

    @articles.setter
    def articles(self, val):
        self._function_is_read_only()


class Volume(ArticleHandlingExportElement):
    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)
        self.issues = None

    @property
    def issues(self):
        return self._resolve_depending_sections()

    @issues.setter
    def issues(self, val):
        """ Disable setter """
        self._function_is_read_only()


class Issue(ArticleHandlingExportElement):
    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)


class Article(VisualLibraryExportElement):

    METS_TAG_SECTION_STRING = 'mets:dmdsec'

    MODS_TAG_NAME_STRING = 'mods:name'
    MODS_TAG_ROLE_STRING = 'mods:roleterm'
    MODS_TAG_NAME_PART_STRING = 'mods:namepart'
    MODS_TAG_TITLE_INFO_STRING = 'mods:titleinfo'
    MODS_TAG_TITLE_STRING = 'mods:title'
    MODS_TAG_SUBTITLE_STRING = 'mods:subtitle'
    MODS_TAG_LANGUAGE_STRING = 'mods:language'
    MODS_TAG_LANGUAGE_TERM_STRING = 'mods:languageterm'

    AUTHORITY_STRING = 'authority'
    MARCRELATOR_STRING = 'marcrelator'
    TYPE_STRING = 'type'
    PERSONAL_STRING = 'personal'
    AUTHOR_SHORT_STRING = 'aut'
    ID_CAPITAL_STRING = 'ID'
    GIVEN_STRING = 'given'
    FAMILY_STRING = 'family'

    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)

        self.files = set()
        self.authors = self._extract_author_from_metadata()
        self.title = None
        self.subtitle = None
        self.languages = set()

        self._extract_titles_from_metadata()
        self._extract_languages_from_metadata()

    def _extract_author_from_metadata(self) -> set:
        """ Returns a set of author namedtuples from the metadata. """

        persons_in_metadata = self.xml_data.find_all(self.MODS_TAG_NAME_STRING, {self.TYPE_STRING:
                                                                                 self.PERSONAL_STRING})

        Author = namedtuple('Person', ['given_name', 'family_name'])

        authors = set()
        for person in persons_in_metadata:
            if person.find(self.MODS_TAG_ROLE_STRING,
                           {self.AUTHORITY_STRING: self.MARCRELATOR_STRING}) == self.AUTHOR_SHORT_STRING:
                given_name = person.find(self.MODS_TAG_NAME_PART_STRING, {self.TYPE_STRING: self.GIVEN_STRING})
                family_name = person.find(self.MODS_TAG_NAME_PART_STRING, {self.TYPE_STRING: self.FAMILY_STRING})

                # Clean names
                given_name = given_name if given_name is not None else ''
                family_name = family_name if family_name is not None else ''

                authors.add(Author(given_name, family_name))

        return authors

    def _extract_languages_from_metadata(self):
        languages_element = self.xml_data.find(self.MODS_TAG_LANGUAGE_STRING)
        self.languages = set(language.text for language in languages_element.find_all(self.MODS_TAG_LANGUAGE_TERM_STRING))

    def _extract_titles_from_metadata(self):
        title_info_element = self.xml_data.find(self.MODS_TAG_TITLE_INFO_STRING)
        title_element = title_info_element.find(self.MODS_TAG_TITLE_STRING)
        if title_element is not None:
            self.title = title_element.text

        subtitle_element = title_info_element.find(self.MODS_TAG_SUBTITLE_STRING)
        if subtitle_element is not None:
            self.subtitle = subtitle_element.text


RESPONSE_HEADER = 'header'
VL_OBJECT_SPECIFICATION = 'setspec'
VL_OBJECT_TYPES = {
    'journal_volume': Volume,
    'periodical': Journal,
    'journal_issue': Issue,
    'article': Article,
    'journal': Journal
}


def get_xml_header_from_vl_response(vl_response_xml):
    return vl_response_xml.find(RESPONSE_HEADER)


def get_object_type_from_xml_header(xml_header):
    object_specifications = xml_header.find_all(VL_OBJECT_SPECIFICATION)
    for specification in object_specifications:
        object_type = VL_OBJECT_TYPES.get(specification.text)
        if object_type is not None:
            return object_type

    return None


class VisualLibrary:

    VISUAL_LIBRARY_OAI_URL = 'http://vl.ub.uni-frankfurt.de/oai/?verb=GetRecord&metadataPrefix={xml_response_format}&identifier={identifier}'
    METS_STRING = 'mets'

    VL_OBJECT_TYPES = VL_OBJECT_TYPES
    logger.setLevel(logging.DEBUG)

    def get_data_for_id(self, vl_id, xml_response_format=METS_STRING):
        """ Get the OAI XML data from the Visual Library.
            :param vl_id: The VL ID of the object to call the metadata for.
            :type vl_id: str
            :param xml_response_format: The format of the OAI XML response.
            :type xml_response_format: str
            :returns: The response OAI XML in a BeautifulSoup element.
            :rtype: BeautifulSoup
            Mets is the default return format. There is no implementation of other formats currently! The received
            OAI XML data is stored.
        """

        xml_importer = MetsImporter()
        xml_importer.parse_xml_from_url(self.VISUAL_LIBRARY_OAI_URL.format(identifier=vl_id,
                                                                           xml_response_format=xml_response_format))

        return xml_importer.xml_data

    def get_element_for_id(self, vl_id):
        """ Returns an object containing the relevant metadata as attributes.
            :param vl_id: The ID of the object in the Visual Library
            :type vl_id: str
            :rtype VisualLibraryExportElement
            Returns None, if the element could not be found.
        """

        xml_data = self.get_data_for_id(vl_id)
        header = get_xml_header_from_vl_response(xml_data)
        object_type = get_object_type_from_xml_header(header)

        if object_type is not None:
            xml_importer = MetsImporter()
            xml_importer.parse_xml(xml_data)
            return object_type(vl_id, xml_importer, parent=None)
        else:
            return None
