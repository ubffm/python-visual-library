import base64

import logging
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup as Soup
from datetime import datetime

from .htmlhandler import get_content_from_url

logger = logging.getLogger('Import')
BASE64_ENCODING_STRING = 'base64'
UTF8_ENCODING_STRING = 'utf-8'


class XMLImporter(ABC):
    """ An abstract class that provides a simple XML import interface. """

    XML_IMPORT_PARSER = 'lxml'

    def __init__(self):
        self.xml_data = Soup()

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


class MetsImporter(XMLImporter):
    """ A class for importing METS data. """

    ATTRIBUTE_FILTER_FOR_SECTIONS = {
        'type': 'section'
    }
    ATTRIBUTE_CREATION_DATE_STRING = 'created'
    ATTRIBUTE_DOWNLOAD_STRING = 'download'
    ATTRIBUTE_FILE_SIZE_STRING = 'size'
    ATTRIBUTE_FILE_ID_STRING = 'fileid'
    ATTRIBUTE_LINK_STRING = 'xlink:href'
    ATTRIBUTE_ID_STRING = 'id'
    ATTRIBUTE_KEY_USE_STRING = 'use'
    ATTRIBUTE_LOCATION_TYPE_STRING = 'loctype'
    ATTRIBUTE_MIMETYPE_STRING = 'mimetype'

    METS_TAG_OBJECT_STRUCTURE_STRING = 'mets:structmap'
    METS_TAG_DIV_STRING = 'mets:div'
    METS_TAG_FILE_GROUP_STRING = 'mets:filegrp'
    METS_TAG_FILE_LOCATION_STRING = 'mets:flocat'
    METS_TAG_FILE_STRING = 'mets:file'

    URL_STRING = 'URL'

    def __init__(self, debug=False):
        super().__init__()
        self.structure = []
        self.files_dict = {}
        self.debug_mode = debug

    def update_data(self):
        """ Reads the structure of the given METS object recursively. """

        mets_structure = self.xml_data.find(self.METS_TAG_OBJECT_STRUCTURE_STRING)
        subsections = mets_structure.find_all(name=self.METS_TAG_DIV_STRING, attrs=self.ATTRIBUTE_FILTER_FOR_SECTIONS,
                                              recursive=False)
        self.structure = [self.Section(sec, self.xml_data) for sec in subsections]

        self._resolve_met_internal_id_references_for_section()

    def _resolve_met_internal_id_references_for_section(self):
        """ Search all downloadable files belonging to this object.
            This function only searches for the file group tag that has the USE=DOWNLOAD attribute.
        """

        file_group_attributes = {self.ATTRIBUTE_KEY_USE_STRING: self.ATTRIBUTE_DOWNLOAD_STRING.upper()}
        mets_file_group_download = self.xml_data.find(self.METS_TAG_FILE_GROUP_STRING, file_group_attributes)

        assert mets_file_group_download, \
            'No file group section with the tag <{tag}> and the attributes {attributes} identified!'.format(
                tag=self.METS_TAG_FILE_GROUP_STRING, attributes=file_group_attributes)

        for section in self.structure:
            if section.file_pointers is not None:
                for file_pointer in section.file_pointers:
                    logger.debug('Processing file pointer: {}'.format(file_pointer))
                    file_tag_id = file_pointer.get(self.ATTRIBUTE_FILE_ID_STRING)
                    file_metdata = mets_file_group_download.find(attrs={self.ATTRIBUTE_ID_STRING: file_tag_id})
                    if file_metdata is not None:
                        file = self._get_file_from_metadata(file_metdata)
                        file.languages = section.languages
                        self.files_dict[file_tag_id] = file
                    else:
                        logger.debug('No file node found with id "{}". Skipping!'.format(file_tag_id))

    def _get_file_from_metadata(self, mets_data):
        """ Creates a file object and adds data as far as possible.
            :param mets_data: The metadata to read the file data from.
            :type mets_data: Soup
            :rtype: File
        """

        file = File()
        file.mime_type = mets_data.get(self.ATTRIBUTE_MIMETYPE_STRING)
        file.size = mets_data.get(self.ATTRIBUTE_FILE_SIZE_STRING)
        name = mets_data.get(self.ATTRIBUTE_ID_STRING)
        if name is not None:
            file.name = '{}.pdf'.format(name.lower())
        date = mets_data.get(self.ATTRIBUTE_CREATION_DATE_STRING)
        if date is not None:
            file.date_uploaded = file.date_modified = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%fZ')

        file_locations = mets_data.find_all(self.METS_TAG_FILE_LOCATION_STRING)
        for location in file_locations:
            location_type = location.get(self.ATTRIBUTE_LOCATION_TYPE_STRING)
            if location_type == self.URL_STRING:
                url = location.get(self.ATTRIBUTE_LINK_STRING)
                if url is not None:
                    logger.debug('Downloading data from URL: {}'.format(url))
                    if not self.debug_mode:
                        file.data = get_content_from_url(url)
                    else:
                        # Dummy data for testing purpose
                        file.data = b'Here could be your PDF file!'
            else:
                raise TypeError('The file location type {} is not implemented!'.format(location_type))

        return file

    class Section:
        """ A subdivision within a METS object. """

        ATTRIBUTE_METADATA_ID = 'dmdid'
        ATTRIBUTE_LABEL = 'label'
        ATTRIBUTE_ORDER = 'order'

        METS_TAG_FILE_POINTER_STRING = 'mets:fptr'
        METS_TAG_RESOURCE_POINTER_STRING = 'mets:mptr'
        METS_TAG_METADATA_SECTION_STRING = 'mets:dmdsec'
        METS_TAG_LANGUAGE_LIST_STRING = 'mods:language'
        METS_TAG_SPECIFIC_LANGUAGE_STRING = 'mods:languageterm'

        def __init__(self, mets_data: Soup, full_xml_data):
            self.id = mets_data.get(MetsImporter.ATTRIBUTE_ID_STRING)
            self.metadata_id = mets_data.get(self.ATTRIBUTE_METADATA_ID)
            self.label = mets_data.get(self.ATTRIBUTE_LABEL)
            self.order = mets_data.get(self.ATTRIBUTE_ORDER)
            self.metadata = None
            self.languages = set()

            self.file_pointers = mets_data.find_all(self.METS_TAG_FILE_POINTER_STRING)
            self.resource_pointer = mets_data.find_all(self.METS_TAG_RESOURCE_POINTER_STRING)

            subsections = mets_data.find_all(name=MetsImporter.METS_TAG_DIV_STRING,
                                             attrs=MetsImporter.ATTRIBUTE_FILTER_FOR_SECTIONS, recursive=False)
            self.sections = [MetsImporter.Section(sec, full_xml_data) for sec in subsections]

            if self.metadata_id:
                self.extract_section_metadata_from_complete_dataset(full_xml_data)

                language_list = self.metadata.find(self.METS_TAG_LANGUAGE_LIST_STRING)
                if language_list is not None:
                    self.languages = set(lang.text for lang in language_list.find_all(self.METS_TAG_SPECIFIC_LANGUAGE_STRING))

        def extract_section_metadata_from_complete_dataset(self, xml_metadata):
            """ Gets the metadata for this section from the overall metadataset.
                :parameter xml_metadata: The overall metadata set
                :type xml_metadata: Soup
            """

            self.metadata = xml_metadata.find(name=self.METS_TAG_METADATA_SECTION_STRING,
                                              attrs={MetsImporter.ATTRIBUTE_ID_STRING: self.metadata_id})


class File:
    """ A class holding all information on a file. """

    def __init__(self):
        self.name = None
        self.date_uploaded = None
        self.date_modified = None
        self.mime_type = None
        self.languages = None
        self.encoding = None
        self.data = None

        self._size = 0

    def get_data_in_base64_encoding(self):
        """ Transforms the data property into a base64-encoded string. """

        encoded_bytes = base64.b64encode(self.data.encode(UTF8_ENCODING_STRING))
        return str(encoded_bytes, UTF8_ENCODING_STRING)

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        self._size = int(value)
