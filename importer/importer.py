import base64

import logging
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup as Soup
from datetime import datetime

from .htmlhandler import get_content_from_url

logger = logging.getLogger('Import')
BASE64_ENCODING_STRING = 'base64'
UTF8_ENCODING_STRING = 'utf-8'
DEBUG_FILE_DATA_CONTENT_BYTE_STRING = b'Here could be your PDF file!'


class XMLImporter(ABC):
    """ An abstract class that provides a simple XML import interface. """

    ID_STRING = 'id'
    XML_IMPORT_PARSER = 'lxml'

    def __init__(self):
        self.xml_data = None

    def parse_xml(self, xml):
        """ Import XML data.
            :param xml: The XML data to import
            :type xml: str or Soup
        """

        if isinstance(xml, Soup):
            self.xml_data = xml
        elif isinstance(xml, str):
            self.xml_data = Soup(xml, self.XML_IMPORT_PARSER)
        else:
            raise TypeError('The provided XML data has to be a string or a Soup object!')

        self.update_data()

    def parse_xml_from_url(self, url):
        """ Parse XML string from a given URL.
            :param url: A URL where to fetch an XML string.
            :type url: str
        """

        xml_data = get_content_from_url(url)
        self.parse_xml(xml_data.decode())

    @abstractmethod
    def update_data(self):
        """ This function is called automatically when XML data has been imported. """
        pass


class File:
    """ A class holding all information on a file. """

    ATTRIBUTE_MIMETYPE_STRING = 'mimetype'
    ATTRIBUTE_FILE_SIZE_STRING = 'size'
    ATTRIBUTE_ID_STRING = XMLImporter.ID_STRING
    ATTRIBUTE_CREATION_DATE_STRING = 'created'
    ATTRIBUTE_LOCATION_TYPE_STRING = 'loctype'
    ATTRIBUTE_LINK_STRING = 'xlink:href'

    METS_TAG_FILE_LOCATION_STRING = 'mets:flocat'

    URL_STRING = 'URL'

    def __init__(self):
        self.name = None
        self.date_uploaded = None
        self.date_modified = None
        self.mime_type = None
        self.languages = None
        self.data = None
        self.url = None

        self._size = 0

    def download_file_data_from_source(self):
        self.data = get_content_from_url(self.url)

    def get_data_in_base64_encoding(self):
        """ Transforms the data property into a base64-encoded string.
            :returns: A base64-encoded representation of the file data.
            :rtype: str
        """

        if self.data is None:
            self.download_file_data_from_source()

        encoded_bytes = base64.b64encode(self.data)
        return str(encoded_bytes, UTF8_ENCODING_STRING)

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        if value is not None:
            self._size = int(value)

    def parse_properties_from_xml_element(self, xml_element):
        """ Reads data from XML to set the file data.
        :param xml_element: An XML element (METS) containing the file data.
        :type xml_element: BeautifulSoup
        """

        self.mime_type = xml_element.get(self.ATTRIBUTE_MIMETYPE_STRING)
        self.size = xml_element.get(self.ATTRIBUTE_FILE_SIZE_STRING)

        name = xml_element.get(self.ATTRIBUTE_ID_STRING)
        if name is not None:
            self.name = name.lower()

        date = xml_element.get(self.ATTRIBUTE_CREATION_DATE_STRING)
        if date is not None:
            self.date_uploaded = self.date_modified = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%fZ')

        file_locations = xml_element.find_all(self.METS_TAG_FILE_LOCATION_STRING)
        for location in file_locations:
            location_type = location.get(self.ATTRIBUTE_LOCATION_TYPE_STRING)
            if location_type == self.URL_STRING:
                url = location.get(self.ATTRIBUTE_LINK_STRING)
                if url is not None:
                    self.url = url
            else:
                raise TypeError('The file location type {} is not implemented!'.format(location_type))


class HtmlImporter(XMLImporter):
    """ A class for importing HTML pages. """

    HTML_ELEMENT_LINK_STRING = 'a'
    NAVIGATION_ELEMENT_ID = 'navPath'

    def get_element_by_id(self, element_id):
        """ Return an HTML element from the called page by it's ID.
            :param element_id: The ID of an element or a list of elements on the page (in the XML data).
            :type element_id: str or list
            :returns: The first element having this ID. None, otherwise.
            :rtype: BeautifulSoup or None
        """

        return self.xml_data.find(attrs={self.ID_STRING: element_id})

    def update_data(self):
        pass

    def get_navigation_hierarchy_labels(self):
        """ Returns the labels of the navigation of the current HTML.
            :returns: A list of labels in hierarchical order. The list if empty, if none could be found
            :rtype: list
        """

        navigation_element = self.get_element_by_id(self.NAVIGATION_ELEMENT_ID)

        labels = []
        if navigation_element is not None:
            hierarchy_elements = navigation_element.find_all(self.HTML_ELEMENT_LINK_STRING)
            labels = [element.text for element in hierarchy_elements]

        return labels


class MetsImporter(XMLImporter):
    """ A class for importing METS data. """

    ATTRIBUTE_FILTER_FOR_SECTIONS = {
        'type': ['periodical', 'volume', 'issue', 'article', 'section', 'document', 'illustration']
    }
    ATTRIBUTE_DOWNLOAD_STRING = 'download'
    ATTRIBUTE_FILE_ID_STRING = 'fileid'
    ATTRIBUTE_KEY_USE_STRING = 'use'

    METS_TAG_OBJECT_STRUCTURE_STRING = 'mets:structmap'
    METS_TAG_DIV_STRING = 'mets:div'
    METS_TAG_FILE_GROUP_STRING = 'mets:filegrp'
    METS_TAG_FILE_STRING = 'mets:file'

    SECTION_ID_PREFIX_STRING = 'log'
    LOGICAL_STRING = 'LOGICAL'
    TYPE_STRING = 'type'

    def __init__(self, debug=False):
        super().__init__()
        self.structure = []
        self.debug_mode = debug

    def get_section_by_id(self, section_id):
        prefixed_section_id = f'{self.SECTION_ID_PREFIX_STRING}{section_id}'

        def search_section(section):
            relevant_section = None
            for sec in section:
                if sec.id == prefixed_section_id:
                    return sec

                relevant_section = search_section(sec.sections)
                if relevant_section is not None:
                    break

            return relevant_section

        return search_section(self.structure)

    def update_data(self):
        """ Reads the structure of the given METS object recursively. """

        mets_structure = self.xml_data.find(self.METS_TAG_OBJECT_STRUCTURE_STRING, {self.TYPE_STRING: self.LOGICAL_STRING})

        if mets_structure is None:
            raise ImportError('The given URL or ID (given: ) did not return METS-XML or could not find the searched data!\n'
                              'XML Response:\n{xml_data}'.format(xml_data=self.xml_data))

        subsections = mets_structure.find_all(name=self.METS_TAG_DIV_STRING, attrs=self.ATTRIBUTE_FILTER_FOR_SECTIONS,
                                              recursive=False)
        self.structure = [self.Section(sec, self.xml_data) for sec in subsections]

        self._resolve_mets_internal_id_references_for_section()

    def _get_file_from_metadata(self, mets_data):
        """ Creates a file object and adds data as far as possible.
            :param mets_data: The metadata to read the file data from.
            :type mets_data: Soup
            :rtype: File
        """

        file = File()
        file.parse_properties_from_xml_element(mets_data)

        if self.debug_mode:
            file.data = DEBUG_FILE_DATA_CONTENT_BYTE_STRING

        return file

    def _resolve_mets_internal_id_references_for_section(self):
        """ Search all downloadable files belonging to this object.
            This function only searches for the file group tag that has the USE=DOWNLOAD attribute.
        """

        file_group_attributes = {self.ATTRIBUTE_KEY_USE_STRING: self.ATTRIBUTE_DOWNLOAD_STRING.upper()}
        mets_file_group_download = self.xml_data.find(self.METS_TAG_FILE_GROUP_STRING, file_group_attributes)

        def resolve_file_pointers(sec):
            for file_pointer_data in sec.file_pointers_data:
                logger.debug('Processing file pointer: {}'.format(file_pointer_data))
                file_tag_id = file_pointer_data.get(self.ATTRIBUTE_FILE_ID_STRING)
                file_metdata = mets_file_group_download.find(attrs={self.ID_STRING: file_tag_id})
                if file_metdata is not None:
                    file = self._get_file_from_metadata(file_metdata)
                    file.languages = section.languages
                    sec.files.add(file)
                else:
                    logger.debug('No file node found with id "{}". Skipping!'.format(file_tag_id))

            for child in sec.sections:
                resolve_file_pointers(child)

        if mets_file_group_download is not None:
            for section in self.structure:
                resolve_file_pointers(section)

    class Section:
        """ A subdivision within a METS object. """

        ATTRIBUTE_HREF = 'xlink:href'
        ATTRIBUTE_LABEL = 'label'
        ATTRIBUTE_LOCTYPE = 'loctype'
        ATTRIBUTE_METADATA_ID = 'dmdid'
        ATTRIBUTE_ORDER = 'order'

        METS_TAG_FILE_POINTER_STRING = 'mets:fptr'
        METS_TAG_RESOURCE_POINTER_STRING = 'mets:mptr'
        METS_TAG_METADATA_SECTION_STRING = 'mets:dmdsec'

        MODS_TAG_LANGUAGE_LIST_STRING = 'mods:language'
        MODS_TAG_SPECIFIC_LANGUAGE_STRING = 'mods:languageterm'
        MODS_TAG_TITLE_INFO_STRING = 'mods:titleinfo'
        MODS_TAG_TITLE_STRING = 'mods:title'
        MODS_TAG_SUBTITLE_STRING = 'mods:subtitle'

        URL_STRING = 'URL'

        def __init__(self, mets_data: Soup, full_xml_data):
            self.id = mets_data.get(MetsImporter.ID_STRING)
            self.metadata_id = mets_data.get(self.ATTRIBUTE_METADATA_ID)
            self.label = mets_data.get(self.ATTRIBUTE_LABEL)
            self.order = mets_data.get(self.ATTRIBUTE_ORDER)
            self.metadata = None
            self.languages = set()
            self.files = set()

            self.file_pointers_data = mets_data.find_all(self.METS_TAG_FILE_POINTER_STRING, recursive=False)
            self.resource_pointers = mets_data.find_all(self.METS_TAG_RESOURCE_POINTER_STRING, recursive=False)

            subsections = mets_data.find_all(name=MetsImporter.METS_TAG_DIV_STRING,
                                             attrs=MetsImporter.ATTRIBUTE_FILTER_FOR_SECTIONS, recursive=True)
            self.sections = [MetsImporter.Section(sec, full_xml_data) for sec in subsections]

            if self.metadata_id:
                self.extract_section_metadata_from_complete_dataset(full_xml_data)

                language_list = self.metadata.find(self.MODS_TAG_LANGUAGE_LIST_STRING)
                if language_list is not None:
                    self.languages = set(lang.text for lang in language_list.find_all(self.MODS_TAG_SPECIFIC_LANGUAGE_STRING))

        def extract_section_metadata_from_complete_dataset(self, xml_metadata):
            """ Gets the metadata for this section from the overall metadataset.
                :parameter xml_metadata: The overall metadata set
                :type xml_metadata: Soup
            """

            self.metadata = xml_metadata.find(name=self.METS_TAG_METADATA_SECTION_STRING,
                                              attrs={MetsImporter.ID_STRING: self.metadata_id})
