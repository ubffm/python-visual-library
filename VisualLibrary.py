from collections import namedtuple

from .importer.importer import MetsImporter

import re
import logging


logger = logging.getLogger('VL-Importer')


class VisualLibraryExportElement:
    MODS_TAG_PUBLICATION_DATE_STRING = 'mods:date'
    MODS_TAG_PUBLICATION_DATE_ISSUED_STRING = 'mods:dateissued'
    MODS_TAG_ORIGIN_INFO_STRING = 'mods:origininfo'
    MODS_TAG_TITLE_INFO_STRING = 'mods:titleinfo'
    MODS_TAG_TITLE_STRING = 'mods:title'
    MODS_TAG_SUBTITLE_STRING = 'mods:subtitle'
    MODS_TAG_LANGUAGE_STRING = 'mods:language'
    MODS_TAG_LANGUAGE_TERM_STRING = 'mods:languageterm'
    MODS_TAG_NAME_STRING = 'mods:name'
    MODS_TAG_ROLE_STRING = 'mods:roleterm'

    SECTION_LABEL_STRING = 'LABEL'
    SECTION_ORDER_STRING = 'ORDER'

    YES_STRING = 'yes'
    KEY_DATE_STRING = 'keydate'
    LOCTYPE_STRING = 'loctype'
    URL_STRING = 'URL'
    HREF_LINK_STRING = 'xlink:href'
    AUTHORITY_STRING = 'authority'
    MARCRELATOR_STRING = 'marcrelator'
    TYPE_STRING = 'type'

    def __init__(self, vl_id, xml_importer, parent):
        self.id = vl_id
        self.xml_importer = xml_importer
        self.xml_data = xml_importer.xml_data
        self._own_section = self._get_own_sections()
        self.sections = self._own_section.sections
        self.metadata = self._own_section.metadata

        self.title = None
        self.subtitle = None
        self.languages = set()
        self.label = self._own_section.label
        self.order = self._own_section.order
        self.publication_date = None
        self.parent = parent
        self.files = self._own_section.files

        self._extract_publication_date_from_metadata()
        self._extract_titles_from_metadata()
        self._extract_languages_from_metadata()

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

            if earliest_date_element is not None:
                earliest_date_element = str(earliest_date_element)

            return earliest_date_element

        origin_info_elements = self.metadata.find_all([self.MODS_TAG_PUBLICATION_DATE_STRING,
                                                       self.MODS_TAG_PUBLICATION_DATE_ISSUED_STRING])

        if isinstance(self, Journal):
            self._get_publication_duration(origin_info_elements)
        else:
            self.publication_date = get_earliest_date()

    def _extract_languages_from_metadata(self):
        languages_element = self.metadata.find(self.MODS_TAG_LANGUAGE_STRING)

        if languages_element is None:
            return

        self.languages = set(language.text for language in languages_element.find_all(self.MODS_TAG_LANGUAGE_TERM_STRING))

    def _extract_titles_from_metadata(self):
        title_info_element = self.metadata.find(self.MODS_TAG_TITLE_INFO_STRING)

        # Issues and Volumes may not have a title
        if title_info_element is None:
            return

        title_element = title_info_element.find(self.MODS_TAG_TITLE_STRING)
        if title_element is not None:
            self.title = title_element.text

        subtitle_element = title_info_element.find(self.MODS_TAG_SUBTITLE_STRING)
        if subtitle_element is not None:
            self.subtitle = subtitle_element.text

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

    def _get_authority_element_by_role(self, role_type):
        persons_in_metadata = self.metadata.find_all(self.MODS_TAG_NAME_STRING)
        persons_in_given_role = [person_element
                                for person_element in persons_in_metadata
                                if person_element.find(self.MODS_TAG_ROLE_STRING,
                                                       {self.AUTHORITY_STRING: self.MARCRELATOR_STRING}).text == role_type
                                ]

        return  persons_in_given_role


    @staticmethod
    def _function_is_read_only():
        Exception('This element may not be modified! Read only!')


class Journal(VisualLibraryExportElement):
    PUBLISHER_SHORT_STRING = 'isb'
    MODS_TAG_DISPLAY_NAME_STRING = 'mods:displayform'

    ATTRIBUTE_URI_VALUE_STRING = 'valueuri'

    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)
        self.volumes = []
        self.publisher = None

        self._extract_publisher_from_metadata()

    @property
    def volumes(self):
        return self._resolve_depending_sections()

    @volumes.setter
    def volumes(self, val):
        self._function_is_read_only()

    def _get_publication_duration(self, date_elements):
        for date_element in date_elements:
            date_period = re.match(r'^[0-9]{4}-[0-9]{4}', date_element.text)
            if date_period:
                self.publication_date = date_period.group()
                break

    def _extract_publisher_from_metadata(self):
        Publisher = namedtuple('Publisher', ['name', 'uri'])

        publishers_in_metadata = self._get_authority_element_by_role(self.PUBLISHER_SHORT_STRING)
        publishers = []
        for publisher in publishers_in_metadata:
            publisher_name = publisher.find(self.MODS_TAG_DISPLAY_NAME_STRING).text
            publisher_uri = publisher.get(self.ATTRIBUTE_URI_VALUE_STRING, '')
            publishers.append(
                Publisher(publisher_name, publisher_uri)
            )

        self.publishers = publishers


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
        self.publisher = None

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
    MODS_TAG_NAME_PART_STRING = 'mods:namepart'

    AUTHOR_SHORT_STRING = 'aut'
    ID_CAPITAL_STRING = 'ID'
    GIVEN_STRING = 'given'
    FAMILY_STRING = 'family'

    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)

        self.authors = self._extract_author_from_metadata()

    def _extract_author_from_metadata(self) -> list:
        """ Returns a list of author namedtuples from the metadata. """

        Author = namedtuple('Person', ['given_name', 'family_name'])

        authors = []
        author_elements_in_metadata = self._get_authority_element_by_role(self.AUTHOR_SHORT_STRING)
        for person in author_elements_in_metadata:
            given_name = person.find(self.MODS_TAG_NAME_PART_STRING, {self.TYPE_STRING: self.GIVEN_STRING})
            family_name = person.find(self.MODS_TAG_NAME_PART_STRING, {self.TYPE_STRING: self.FAMILY_STRING})

            # Clean names
            given_name = given_name.text if given_name is not None else ''
            family_name = family_name.text if family_name is not None else ''

            authors.append(Author(given_name, family_name))

        return authors

    def _is_person_element_author(self, person_element):
        return person_element.find(self.MODS_TAG_ROLE_STRING,
                                   {self.AUTHORITY_STRING: self.MARCRELATOR_STRING}).text == self.AUTHOR_SHORT_STRING


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
