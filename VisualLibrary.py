from collections import namedtuple

import logging
import re
from bs4 import BeautifulSoup as Soup
from bs4 import Tag

from importer.importer import MetsImporter, File, HtmlImporter

logger = logging.getLogger('VL-Importer')


def function_is_read_only():
    Exception('This element may not be modified! Read only!')


class VisualLibraryExportElement:
    """ A base class for all classes that can be instantiated from Visual Library XML data. """

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
    MODS_TAG_PART_STRING = 'mods:part'
    MODS_TAG_DETAIL_STRING = 'mods:detail'
    MODS_TAG_NUMBER_STRING = 'mods:number'

    METS_TAG_STRUCTMAP_STRING = 'mets:structmap'
    METS_TAG_DIV_STRING = 'mets:div'
    METS_TAG_RESOURCE_POINTER_STRING = 'mets:mptr'
    METS_TAG_XML_DATA_STRING = 'mets:xmldata'

    YES_STRING = 'yes'
    KEY_DATE_STRING = 'keydate'
    LOCTYPE_STRING = 'loctype'
    URL_STRING = 'URL'
    HREF_LINK_STRING = 'xlink:href'
    AUTHORITY_STRING = 'authority'
    MARCRELATOR_STRING = 'marcrelator'
    TYPE_STRING = 'type'
    ID_STRING = 'id'

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
        self._number = None
        self.publication_date = None
        self._parent = parent
        self.files = self._own_section.files

        self._extract_publication_date_from_metadata()
        self._extract_titles_from_metadata()
        self._extract_languages_from_metadata()

    @property
    def parent(self):
        """ This gives the parent of the current object.
            For an Issue this would be a Volume.
        """
        if self._parent is None:
            self._parent = self._get_parent()

        return self._parent

    @property
    def number(self):
        """ If overriden, this should return the publication number of the object.
            :rtype: str
        """
        return None

    def find_section_by_label(self, section_label, parent_labels=None, recursive=False):
        """ Returns a section that has the given label.
            :param section_label: A section label for the section that should be returned.
            :type section_label: str
            :param parent_labels: Either a list of section labels of a single section label string that should be used
            to make the search more efficient and be compared to the available section labels. If no label fits any of
            the current section labels, None is returned.
            :type parent_labels: list or str
            :param recursive: If the search should be recursive (True) or not (False). False is default.
            :type recursive: bool
            :returns: A single section with the given label. None, if there is no section with the given label.
            :rtype: MetsImporter.Section
        """

        if parent_labels is None:
            parent_labels = []

        if self.label == section_label:
            return self._own_section

        for section in self.sections:
            if section.label is None:
                continue

            if section.label in section_label:
                return section
            elif recursive and section.label in parent_labels:
                resource_url = section.resource_pointer.get(self.HREF_LINK_STRING)
                resource_id_match = re.match(r'(?<=identifier=)[0-9]*', resource_url)
                if resource_id_match:
                    parent_element = VisualLibrary().get_element_for_id(resource_id_match.group())
                    return parent_element.find_section_by_label(section_label, parent_labels, recursive=True)

        return None

    def _create_section_instance(self, xml_importer: MetsImporter, url: str):
        """ Finds the appropriate class for a section.
            :returns: A section instance. None, if the section could not be resolved.
        """

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

    def _extract_languages_from_metadata(self):
        """ Sets the language property with the appropriate data. """

        languages_element = self.metadata.find(self.MODS_TAG_LANGUAGE_STRING)

        if languages_element is None:
            return

        self.languages = set(language.text for language in languages_element.find_all(
            self.MODS_TAG_LANGUAGE_TERM_STRING))

    def _extract_publication_date_from_metadata(self):
        """ Search for the earliest date in the metadata and use it as publication date.
            The date is expected to be in the format 'YYYY' and be convertable into an int for comparison.
        """

        def get_earliest_date():
            earliest_date_element = None
            for origin_info in origin_info_elements:
                date = origin_info.find(self.MODS_TAG_PUBLICATION_DATE_STRING, {self.KEY_DATE_STRING: self.YES_STRING})

                if date is None:
                    date = origin_info if origin_info.name == self.MODS_TAG_PUBLICATION_DATE_STRING else None

                if date is not None:
                    try:
                        date = int(date.text)
                    except AttributeError:
                        continue

                    if earliest_date_element is not None:
                        if earliest_date_element > date:
                            earliest_date_element = date
                    else:
                        earliest_date_element = date

            if earliest_date_element is not None:
                earliest_date_element = str(earliest_date_element)

            return earliest_date_element

        origin_info_elements = self._get_date_elements_from_metadata()
        self.publication_date = get_earliest_date()

    def _extract_titles_from_metadata(self):
        """ Sets both the title and subtitle data with the appropriate data. """

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

    def _get_authority_element_by_role(self, role_type: str) -> list:
        """ Finds all metadata elements having the given role.
            This function is used for finding e.g. authors and publishers.
        """
        persons_in_metadata = self.metadata.find_all(self.MODS_TAG_NAME_STRING)
        persons_in_given_role = [person_element
                                 for person_element in persons_in_metadata
                                 if person_element.find(self.MODS_TAG_ROLE_STRING,
                                                        {self.AUTHORITY_STRING: self.MARCRELATOR_STRING}).text == role_type
                                 ]

        return persons_in_given_role

    def _get_date_elements_from_metadata(self) -> list:
        return self.metadata.find_all([self.MODS_TAG_PUBLICATION_DATE_STRING,
                                       self.MODS_TAG_PUBLICATION_DATE_ISSUED_STRING])

    def _get_own_sections(self) -> MetsImporter.Section:
        return self.xml_importer.get_section_by_id(self.id)

    def _get_parent(self):
        section_id = self._own_section.id
        parent_element = self.xml_data.find(attrs={self.ID_STRING: section_id}).parent
        parent_url_element = parent_element.find(self.METS_TAG_RESOURCE_POINTER_STRING, {self.LOCTYPE_STRING:
                                                                                         self.URL_STRING},
                                                 recursive=False)
        if parent_url_element is not None:
            parent_url = parent_url_element.get(self.HREF_LINK_STRING)
            parent_id_result = re.search(r'(?<=identifier=)[0-9]*', parent_url, re.IGNORECASE)
            if parent_id_result is not None:
                parent_id = parent_id_result.group()
                vl = VisualLibrary()
                return vl.get_element_from_url(parent_id, parent_url)
            else:
                return None

    def _resolve_depending_sections(self):
        """ Returns a generator that iterates this object's sections.
            The sections are returned as VisualLibraryExportElement instances.
        """

        for section in self.sections:
            for instance in self._resolve_resource_pointers(section):
                yield instance

    def _resolve_resource_pointers(self, section: MetsImporter.Section) -> list:
        """ Resolves any subsection's URL references to other Visual Library objects.
            :returns: A list of section instances that could be resolved.
        """

        instantiated_sections = []
        for resource in section.resource_pointers:
            if resource.get(self.LOCTYPE_STRING) == self.URL_STRING:
                url = resource.get(self.HREF_LINK_STRING)
                xml_importer = MetsImporter()
                if url is not None:
                    instantiated_section_type = self._create_section_instance(xml_importer, url)
                    if instantiated_section_type is not None:
                        instantiated_sections.append(instantiated_section_type)

        return instantiated_sections

    def _get_number_from_metadata_details_by_attribute(self, detail_node_attributes: dict) -> (str, None):
        try:
            info_node = self.metadata.find(self.MODS_TAG_PART_STRING).find(
                self.MODS_TAG_DETAIL_STRING, detail_node_attributes)

            return info_node.find(self.MODS_TAG_NUMBER_STRING).text
        except AttributeError:
            return None


class Journal(VisualLibraryExportElement):
    """ A Journal class holds its volumes. """

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
        function_is_read_only()

    def _extract_publication_date_from_metadata(self):
        """ Sets a duration for the publication date.
            Journals rarely have a single year but more often a duration when they were published.
        """

        date_elements = self._get_date_elements_from_metadata()
        self._get_publication_duration(date_elements)

    def _extract_publisher_from_metadata(self):
        """ Sets the display name of the publisher from the metadata. """

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

    def _get_publication_duration(self, date_elements):
        """ Searches the elements' texts for a duration.
            The duration has to fit the format YYYY-YYYY.
        """

        for date_element in date_elements:
            date_period = re.match(r'^[0-9]{4}\s*?-\s*?[0-9]{4}', date_element.text)
            if date_period:
                self.publication_date = date_period.group()
                break


class ArticleHandlingExportElement(VisualLibraryExportElement):
    """ All classes handling article lists should inherit from this class. """

    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)
        self._articles = []
        self._articles_processed = False

    @property
    def articles(self):
        if not self._articles_processed:
            self._articles = self._resolve_depending_sections()
            self._articles_processed = True

        return self._articles

    @articles.setter
    def articles(self, val):
        function_is_read_only()


class Volume(ArticleHandlingExportElement):
    """ A Volume class can hold both Issues OR articles. """

    VOLUME_STRING = 'volume'

    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)
        self._issues = []
        self._issues_processed = False
        self.publisher = None

    @property
    def issues(self):
        if not self._issues_processed:
            self._issues = self._resolve_depending_sections()
            self._issues_processed = True

        return self._issues

    @property
    def number(self):
        if self._number is None:
            self._number = self._get_number_from_metadata_details_by_attribute({})

        return self._number

    @issues.setter
    def issues(self, val):
        """ Disable setter """
        function_is_read_only()


class Issue(ArticleHandlingExportElement):
    """ An Issue class holds only articles. """

    ISSUE_STRING = 'issue'

    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)

    @property
    def number(self):
        if self._number is None:
            self._number = self._get_number_from_metadata_details_by_attribute({self.TYPE_STRING: self.ISSUE_STRING})

        return self._number


class Page:
    """ This class holds all data on a single page.
        Only when a resource of this page (e.g. the text or a page scan), the respective resource is called
        and generated.
    """

    ALTO_TAG_SPACE_STRING = 'sp'
    ALTO_TAG_TEXT_LINE_STRING = 'textline'
    ALTO_TAG_WORD_STRING = 'string'

    CONTENT_STRING = 'content'
    FILE_ID_STRING = 'fileid'
    ID_STRING = 'id'
    LABEL_STRING = 'label'
    METS_TAG_FILE_POINTER = 'mets:fptr'
    METS_TAG_FILE_STRING = 'mets:file'
    ORDER_STRING = 'order'

    SUBSTRING_IN_DEFAULT_SCAN_IMAGE_ID = 'DEFAULT'
    SUBSTRING_IN_FULL_TEXT_ID = 'ALTO'
    SUBSTRING_IN_MAX_SCAN_IMAGE_ID = 'MAX'
    SUBSTRING_IN_MIN_SCAN_IMAGE_ID = 'MIN'
    SUBSTRING_IN_THUMBNAIL_ID = 'THUMBS'

    def __init__(self, page_element, xml_data):
        self.full_text = None
        self.full_text_xml = None
        self.image_default_resolution = None
        self.image_max_resolution = None
        self.image_min_resolution = None
        self._page_element = page_element
        self.label = page_element.get(self.LABEL_STRING)
        self.order = page_element.get(self.ORDER_STRING)
        self.thumbnail = None
        self.id = self._extract_page_id_from_metadata(page_element)
        self.vl_id = self._extract_vl_page_id_from_metadata(page_element)

        self._file_pointer = self._page_element.find_all(self.METS_TAG_FILE_POINTER)
        self._xml_data = xml_data

    @property
    def full_text(self) -> (str, None):
        """ Returns the page's full text as string.
            Returns None, if no full text could be found.
        """

        text_file = self._get_file_from_id_substring(self.SUBSTRING_IN_FULL_TEXT_ID)

        if text_file is not None:
            text_file.download_file_data_from_source()
            return self._parse_alto_xml_to_full_text_string(Soup(text_file.data, MetsImporter.XML_IMPORT_PARSER))

        return None

    @property
    def full_text_xml(self) -> File:
        return self._get_resource_pointer_by_id_substring(self.SUBSTRING_IN_FULL_TEXT_ID)

    @property
    def image_default_resolution(self) -> File:
        """ Returns a File object to the page's default resolution page scan. """
        return self._get_file_from_id_substring(self.SUBSTRING_IN_DEFAULT_SCAN_IMAGE_ID)

    @property
    def image_max_resolution(self) -> File:
        """ Returns a File object to the page's maximum resolution page scan. """
        return self._get_file_from_id_substring(self.SUBSTRING_IN_MAX_SCAN_IMAGE_ID)

    @property
    def image_min_resolution(self) -> File:
        """ Returns a File object to the page's minimum resolution page scan. """
        return self._get_file_from_id_substring(self.SUBSTRING_IN_MIN_SCAN_IMAGE_ID)

    @property
    def thumbnail(self) -> File:
        """ Returns a File object to the page's thumbnail. """
        return self._get_file_from_id_substring(self.SUBSTRING_IN_THUMBNAIL_ID)

    @full_text.setter
    def full_text(self, val):
        function_is_read_only()

    @full_text_xml.setter
    def full_text_xml(self, val):
        function_is_read_only()

    @image_default_resolution.setter
    def image_default_resolution(self, val):
        function_is_read_only()

    @image_max_resolution.setter
    def image_max_resolution(self, val):
        function_is_read_only()

    @image_min_resolution.setter
    def image_min_resolution(self, val):
        function_is_read_only()

    @thumbnail.setter
    def thumbnail(self, val):
        function_is_read_only()

    def _extract_page_id_from_metadata(self, page_metadata: Soup) -> str:
        return page_metadata.get(self.ID_STRING)

    def _extract_vl_page_id_from_metadata(self, page_metadata: Soup) -> str:
        page_id = self._extract_page_id_from_metadata(page_metadata)
        return re.sub(r'^phys', '', page_id)


    def _get_file_from_resource_id(self, resource_id: str) -> File:
        """ Creates a File object from resolving a given XML data internal ID. """

        resource_element = self._xml_data.find(self.METS_TAG_FILE_STRING, {self.ID_STRING: resource_id})
        try:
            file = File()
            file.parse_properties_from_xml_element(resource_element)
            return file
        except AttributeError:
            raise ValueError('The given XML data refers to the ID {id} that is not given in the data!'.format(id=resource_id))

    def _get_resource_pointer_by_id_substring(self, substring):
        for file_pointer in self._file_pointer:
            if substring in file_pointer.get(self.FILE_ID_STRING, ''):
                return file_pointer

    def _get_file_from_id_substring(self, substring):
        resource_pointer = self._get_resource_pointer_by_id_substring(substring)
        file_id = resource_pointer.get(self.FILE_ID_STRING)
        return self._get_file_from_resource_id(file_id)

    def _parse_alto_xml_to_full_text_string(self, alto_xml: Soup) -> str:
        def extract_text_from_tag(word: Soup):
            if isinstance(word, Tag):
                return word.get(self.CONTENT_STRING, ' ')

        text_lines = alto_xml.find_all(self.ALTO_TAG_TEXT_LINE_STRING)
        full_text = ''
        for line in text_lines:
            line_text_array = [extract_text_from_tag(word) for word in line.children]
            full_text = '{previous_text}{new_line}\n'.format(previous_text=full_text, new_line=''.join(line_text_array))

        # Skip the last character (which is always a newline)
        return full_text[:-1]


class Article(VisualLibraryExportElement):
    """ This class holds all article data. """

    AUTHOR_SHORT_STRING = 'aut'
    FAMILY_STRING = 'family'
    GIVEN_STRING = 'given'

    METS_TAG_SECTION_STRING = 'mets:dmdsec'
    MODS_TAG_END_STRING = 'mods:end'
    MODS_TAG_EXTEND_STRING = 'mods:extent'
    MODS_TAG_LIST_STRING = 'mods:list'
    MODS_TAG_NAME_PART_STRING = 'mods:namepart'
    MODS_TAG_START_STRING = 'mods:start'

    PAGE_STRING = 'page'
    PHYSICAL_STRING = 'PHYSICAL'
    UNIT_STRING = 'unit'

    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)

        self.authors = self._extract_authors_from_metadata()
        self.doi = None
        self.full_text = None
        self.page_range = self._extract_page_range_from_metadata()
        self.pages = []

    @property
    def full_text(self) -> str:
        return '\n'.join([page.full_text for page in self.pages])

    @property
    def pages(self):
        pages_in_article = self.xml_data.find(self.METS_TAG_STRUCTMAP_STRING, {self.TYPE_STRING: self.PHYSICAL_STRING})
        pages = pages_in_article.find_all(self.METS_TAG_DIV_STRING, attrs={self.TYPE_STRING: self.PAGE_STRING})
        for page in pages:
            yield Page(page, self.xml_data)

    @full_text.setter
    def full_text(self, value):
        function_is_read_only()

    @pages.setter
    def pages(self, value):
        function_is_read_only()

    def _extract_authors_from_metadata(self) -> list:
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

    def _extract_page_range_from_metadata(self) -> (namedtuple, None):
        PageRange = namedtuple('PageRange', ['start', 'end'])
        page_range_element = self.xml_data.find(self.MODS_TAG_EXTEND_STRING, attrs={self.UNIT_STRING: self.PAGE_STRING})
        if page_range_element is not None:
            start_element = page_range_element.find(self.MODS_TAG_START_STRING)
            if start_element is not None:
                start = start_element.text
                end = page_range_element.find(self.MODS_TAG_END_STRING).text
            else:
                mods_list = page_range_element.find(self.MODS_TAG_LIST_STRING)
                if mods_list is not None:
                    start = mods_list.text
                    end = ''
                else:
                    return None

            return PageRange(start, end)
        else:
            return None

    def _is_person_element_author(self, person_element: Soup):
        return person_element.find(self.MODS_TAG_ROLE_STRING,
                                   {self.AUTHORITY_STRING: self.MARCRELATOR_STRING}).text == self.AUTHOR_SHORT_STRING


# In C++, this would be a forward declaration on top of the file
# TODO: The resolution of the object type could use a better solution
RESPONSE_HEADER = 'header'
VL_OBJECT_SPECIFICATION = 'setspec'
VL_OBJECT_TYPES = {
    'article': Article,
    'document': Article,
    'journal': Journal,
    'journal_issue': Issue,
    'journal_volume': Volume,
    'periodical': Journal,
}


def get_xml_header_from_vl_response(vl_response_xml: Soup) -> Soup:
    """ Returns the Header of the Visual Library Response XML. """

    return vl_response_xml.find(RESPONSE_HEADER)


def get_object_type_from_xml_header(xml_header: Soup) -> (VisualLibraryExportElement, None):
    """ Returns the appropriate object class for the given XML header data.
        The type of the requested object (Journal, Issue, Article, etc.) is not encoded in the Visual Library XML data,
        except for the header.
        If no class could be found for the given XML data, None is returned.
    """

    object_specifications = xml_header.find_all(VL_OBJECT_SPECIFICATION)
    for specification in object_specifications:
        object_type = VL_OBJECT_TYPES.get(specification.text)
        if object_type is not None:
            return object_type

    return None


class VisualLibrary:
    """ This class corresponds with the Visual Library OAI and reads the XML response into Python objects.
        Currently, the class supports only METS XML data.
    """

    HREF_STRING = 'href'
    HTML_ELEMENT_LINK = 'a'
    IDENTIFIER_STRING = 'identifier'
    METS_STRING = 'mets'
    REQUEST_TAG_STRING = 'request'
    SOUP_XML_ENCODING = 'lxml'
    TITLE_CONTENT_ELEMENT_ID = 'tab-content-titleinfo'
    TITLE_INFO_ELEMENT_ID = 'tab-periodical-titleinfo'
    VISUAL_LIBRARY_BASE_URL = 'http://vl.ub.uni-frankfurt.de'
    VISUAL_LIBRARY_OAI_URL = 'http://vl.ub.uni-frankfurt.de/oai/?verb=GetRecord&metadataPrefix={xml_response_format}&identifier={identifier}'
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
            :returns: An object containing Visual Library metadata. None, if the element could not be found.
        """

        xml_data = self.get_data_for_id(vl_id)
        return self._create_vl_export_object(vl_id, xml_data)

    def get_element_from_url(self, vl_id, url):
        """ Calls the OAI XML data from a given URL.
            :param vl_id: The VL ID of the object to call the metadata for.
            :type vl_id: str
            :param url: The URL to call for the metadata.
            :type url: str
            :returns: The response OAI XML in a BeautifulSoup element.
            :rtype: BeautifulSoup
        """

        xml_importer = MetsImporter()
        xml_importer.parse_xml_from_url(url)

        return self._create_vl_export_object(vl_id, xml_importer.xml_data)

    def get_element_from_xml_file(self, xml_file_path_string):
        """ Reads a given XML file and converts it's content to a VisualLibraryExport object.
            :param xml_file_path_string: The path to a local xml file.
            :type xml_file_path_string: str
            :returns: An object containing Visual Library metadata. None, if the element could not be found.
            :rtype: VisualLibraryExportElement

            The XML file has to contain a local copy of a Visual Library response!
        """

        with open(xml_file_path_string) as xml_file:
            xml_data_string = xml_file.read()

        xml_data = Soup(xml_data_string, self.SOUP_XML_ENCODING)
        request_element = xml_data.find(self.REQUEST_TAG_STRING)
        if request_element is None:
            raise ValueError('A "request" tag was expected and not found!')

        vl_id = request_element[self.IDENTIFIER_STRING]

        return self._create_vl_export_object(vl_id, xml_data)

    def get_page_by_id(self, page_id):
        """ Returns a single Page object.
            :param page_id: The ID of the page to call.
            :type page_id: str
            :returns: A page object of the given ID. None, if it could not be found.
            :rtype Page

            It may be that some old data cannot return a page, because internal links are not set/are broken or because
            of other reasons.
            This is a very expensive and time consuming task!
        """

        page_url = '{base_url}/{page_id}'.format(base_url=self.VISUAL_LIBRARY_BASE_URL, page_id=page_id)

        html_importer = HtmlImporter()
        html_importer.parse_xml_from_url(page_url)

        title_info_element = html_importer.get_element_by_id([self.TITLE_INFO_ELEMENT_ID, self.TITLE_CONTENT_ELEMENT_ID])
        title_info_link_element = title_info_element.find(self.HTML_ELEMENT_LINK)
        title_vl_id = re.search(r'[0-9]+$', title_info_link_element[self.HREF_STRING])

        title_vl_object = self.get_element_for_id(title_vl_id.group())

        page_hierarchy_labels = html_importer.get_navigation_hierarchy_labels()
        article_section_containing_page = title_vl_object.find_section_by_label(page_hierarchy_labels[-1],
                                                                                page_hierarchy_labels, recursive=True)

        article_id = re.sub('^log', '', article_section_containing_page.id)

        article_object_containing_page = VisualLibrary().get_element_for_id(article_id)
        for page in article_object_containing_page.pages:
            if page.vl_id == page_id:
                return page

        return None

    def _create_vl_export_object(self, vl_id: str, xml_data: Soup) -> (VisualLibraryExportElement, None):
        object_type = self._get_object_type(xml_data)
        if object_type is not None:
            xml_importer = MetsImporter()
            xml_importer.parse_xml(xml_data)
            return object_type(vl_id, xml_importer, parent=None)
        else:
            return None

    def _get_object_type(self, xml_data: Soup) -> (VisualLibraryExportElement, None):
        header = get_xml_header_from_vl_response(xml_data)
        return get_object_type_from_xml_header(header)
