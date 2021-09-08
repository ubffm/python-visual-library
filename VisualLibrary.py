from collections import namedtuple

import logging
import re
import sys
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup as Soup
from bs4 import Tag

from importer.importer import MetsImporter, File, HtmlImporter

log_format = logging.Formatter('[%(asctime)s] [%(levelname)s] - %(message)s')
logger = logging.getLogger('VisualLibrary')
logger.setLevel(logging.DEBUG)

# writing to stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
handler.setFormatter(log_format)
logger.addHandler(handler)


def clean_up_string(string: str) -> str:
    return ' '.join(string.split())


def function_is_read_only():
    Exception('This element may not be modified! Read only!')


def get_list_by_type(container, filter_type: type):
    return [element
            for element in container
            if isinstance(element, filter_type)
            ]


def remove_letters_from_alphanumeric_string(string):
    """ This functions removes letters from the beginning and the end of a given string.
        :param string: A string containing both letters and numbers.
        :type string: str
        :returns: The string without any letters.
        :rtype: int
        :except: A ValueException is thrown if the returned value is not numeric (i.e. also if it is empty!).

        This function helps to normalize e.g. issue labels like '101 AB', which is not accepted by OJS Import XML.
    """

    if string is None:
        return None

    cleanded_string = re.sub(r'\D+', '', string, re.MULTILINE)

    return cleanded_string


Author = namedtuple('Person', ['given_name', 'family_name', 'title'])


class VisualLibraryExportElement(ABC):
    """ A base class for all classes that can be instantiated from Visual Library XML data. """

    ATTRIBUTE_METADATA_ID = 'DMDID'.lower()
    ATTRIBUTE_URI_VALUE_STRING = 'valueuri'
    AUTHORITY_STRING = 'authority'
    HREF_LINK_STRING = 'xlink:href'
    ID_STRING = 'id'
    KEY_DATE_STRING = 'keydate'
    LOCTYPE_STRING = 'loctype'
    MARCRELATOR_STRING = 'marcrelator'
    PAGE_STRING = 'page'
    PHYSICAL_STRING = 'PHYSICAL'
    PUBLISHER_SHORT_STRING = 'isb'
    TRANSLATED_STRING = 'translated'
    TYPE_STRING = 'type'
    URL_STRING = 'URL'
    YES_STRING = 'yes'

    ISO_LANGUAGE_GERMAN = 'ger'
    ISO_LANGUAGE_ENGLISH = 'eng'
    ISO_LANGUAGE_FRENCH = 'fre'

    METS_TAG_DIV_STRING = 'mets:div'
    METS_TAG_RESOURCE_POINTER_STRING = 'mets:mptr'
    METS_TAG_STRUCTMAP_STRING = 'mets:structmap'
    METS_TAG_XML_DATA_STRING = 'mets:xmldata'

    MODS_TAG_DETAIL_STRING = 'mods:detail'
    MODS_TAG_DISPLAY_NAME_STRING = 'mods:displayform'
    MODS_TAG_LANGUAGE_STRING = 'mods:language'
    MODS_TAG_LANGUAGE_TERM_STRING = 'mods:languageterm'
    MODS_TAG_NAME_PART = 'mods:namepart'
    MODS_TAG_NAME_STRING = 'mods:name'
    MODS_TAG_NON_SORT_STRING = 'mods:nonsort'
    MODS_TAG_NUMBER_STRING = 'mods:number'
    MODS_TAG_ORIGIN_INFO_STRING = 'mods:origininfo'
    MODS_TAG_PART_STRING = 'mods:part'
    MODS_TAG_PUBLICATION_DATE_ISSUED_STRING = 'mods:dateissued'
    MODS_TAG_PUBLICATION_DATE_STRING = 'mods:date'
    MODS_TAG_ROLE_STRING = 'mods:roleterm'
    MODS_TAG_SUBJECT_STRING = 'mods:subject'
    MODS_TAG_SUBTITLE_STRING = 'mods:subtitle'
    MODS_TAG_TITLE_INFO_STRING = 'mods:titleinfo'
    MODS_TAG_TITLE_STRING = 'mods:title'

    def __init__(self, vl_id, xml_importer, parent):
        self.xml_importer = xml_importer
        self.xml_data = xml_importer.xml_data
        self.id = vl_id

        self._number = None
        self._own_section = self._get_own_sections()
        self._pages: list = None
        self._parent = parent

        self.files = self._own_section.files
        self.journal_label = None
        self.journal_id = None
        self.keywords = []
        self.label = self._own_section.label
        self.languages = []
        self.metadata = self._own_section.metadata
        self.order = self._own_section.order
        self.publication_date = None
        self.publishers = None
        self.sections = self._own_section.sections
        self.subtitle = None
        self.title = None
        self.prefix = None
        self.volume_number = None
        self.issue_number = None

        self._extract_top_parent_data_from_metadata()
        self._extract_parent_metadata()
        self._extract_keywords_from_metadata()
        self._extract_languages_from_metadata()
        self._extract_publication_date_from_metadata()
        self._extract_publisher_from_metadata()
        self._extract_titles_from_metadata()

        logger.info('Created new {class_name}. ID: {id}'.format(class_name=self.__class__.__name__, id=vl_id))

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

    @property
    @abstractmethod
    def elements(self):
        """ A common getter for all subclasses to access the relevant list. """
        pass

    @property
    def full_text(self) -> str:
        return '\n'.join([page.full_text for page in self.pages])

    @property
    def pages(self) -> list:
        """ Returns a list of Page objects for this element.
            Every element in the Visual Library could hold pages. That's why it is in the parent class.
        """
        if self._pages is None:
            self._pages = []
            pages_in_article = self.xml_data.find(self.METS_TAG_STRUCTMAP_STRING, {self.TYPE_STRING: self.PHYSICAL_STRING})

            if pages_in_article is None:
                self._pages = []
                return self._pages

            pages = pages_in_article.find_all(self.METS_TAG_DIV_STRING, attrs={self.TYPE_STRING: self.PAGE_STRING})
            self._pages = ([Page(page, self.xml_data) for page in pages])

        return self._pages

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

    def _add_translated_titles_to_title(self, translated_title_elements):
        primary_language = self._guess_primary_language()

        title = self.title
        subtitle = self.subtitle
        prefix = self.prefix

        self.title = {primary_language: title}
        self.subtitle = {primary_language: subtitle}
        self.prefix = {primary_language: prefix}

        if primary_language != self.ISO_LANGUAGE_GERMAN:
            translated_language = self.ISO_LANGUAGE_GERMAN
        else:
            # Assumes that a translated title of a german article is always in English
            translated_language = self.ISO_LANGUAGE_ENGLISH

        translated_title_element = translated_title_elements[0]
        self.title[translated_language] = translated_title_element.find(self.MODS_TAG_TITLE_STRING).text

        prefix_translated_title = translated_title_element.find(self.MODS_TAG_NON_SORT_STRING)
        prefix = prefix_translated_title.text if prefix_translated_title is not None else None
        self.prefix[translated_language] = prefix
        if prefix is not None:
            self.title[translated_language] = '{prefix} {title}'.format(prefix=prefix,
                                                                        title=self.title[translated_language])

        translated_subtitle_element = translated_title_element.find(self.MODS_TAG_SUBTITLE_STRING)
        if translated_subtitle_element is not None:
            self.subtitle[translated_language] = translated_subtitle_element.text
        else:
            self.subtitle[translated_language] = None

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

        section_id = re.search(r'(?<=identifier=)[0-9]*', url).group()
        section_type = get_object_type_from_xml(xml_importer.xml_data, section_id)
        if section_type is not None:
            return section_type(section_id, xml_importer, parent=self)

    def _extract_top_parent_data_from_metadata(self):
        """ Gets the label of the top most parent.
            In the most cases, this should be the journal name.
        """

        top_parent_node = self.xml_data.find(
            self.METS_TAG_STRUCTMAP_STRING, {MetsImporter.TYPE_STRING: MetsImporter.LOGICAL_STRING}
        ).find(self.METS_TAG_DIV_STRING)

        top_parent_metadata_id = top_parent_node[self.ATTRIBUTE_METADATA_ID]
        top_parent_metadata = self.xml_data.find(id=top_parent_metadata_id)

        title = top_parent_metadata.find(self.MODS_TAG_TITLE_STRING)
        subtitle = top_parent_metadata.find(self.MODS_TAG_SUBTITLE_STRING)

        journal_label = ''
        if title is not None:
            journal_label = clean_up_string(title.text)
        if subtitle is not None:
            journal_label = f'{journal_label}: {clean_up_string(subtitle.text)}'

        self.journal_label = journal_label
        journal_id_search = re.search(r'md([0-9]*)', top_parent_metadata_id)
        self.journal_id = journal_id_search.group(1) if journal_id_search is not None else None

    def _extract_keywords_from_metadata(self):
        """ If keywords are present, they will be set. """

        subject_elements = self.metadata.find_all(self.MODS_TAG_SUBJECT_STRING)

        self.keywords = [subject.text for subject in subject_elements]

    def _extract_languages_from_metadata(self):
        """ Sets the language property with the appropriate data. """

        languages_element = self.metadata.find(self.MODS_TAG_LANGUAGE_STRING)

        if languages_element is None:
            return

        self.languages = [language.text for language in languages_element.find_all(
            self.MODS_TAG_LANGUAGE_TERM_STRING)]

    def _extract_parent_metadata(self):
        volume_number = self._own_section.metadata.find('mods:detail', {self.TYPE_STRING: 'volume'})
        issue_number = self._own_section.metadata.find('mods:detail', {self.TYPE_STRING: 'issue'})

        if volume_number is not None:
            actual_number = volume_number.find('mods:number')
            self.volume_number = actual_number.text if actual_number is not None else None

        if issue_number is not None:
            actual_number = issue_number.find('mods:number')
            self.issue_number = actual_number.text if actual_number is not None else None

    def _extract_publication_date_from_metadata(self, year_only: bool = False):
        """ Search for the earliest date in the metadata and use it as publication date.
            The date is expected to be in the format 'YYYY' and be convertible into an int for comparison.
            If the year has to be a year only (hence, no duration dash), then the year_only should be True.
        """

        origin_info_elements = self._get_date_elements_from_metadata()

        re_year_only = re.compile(r'\D*[0-9]{4}(?!-)\D*')
        re_date_period = re.compile(r'(?<!.)[0-9]{4}-(?:[0-9]{4})?')
        for origin_element in origin_info_elements:
            dates = origin_element.find_all([self.MODS_TAG_PUBLICATION_DATE_ISSUED_STRING,
                                             self.MODS_TAG_PUBLICATION_DATE_STRING])
            for date_element in dates:

                date_period_result = re_date_period.match(date_element.text)
                if not year_only and date_period_result:
                    self.publication_date = date_period_result.group()
                    return

                year_only_result = re_year_only.match(date_element.text)
                if year_only_result:
                    self.publication_date = remove_letters_from_alphanumeric_string(year_only_result.group())
                    return

    def _extract_publisher_from_metadata(self):
        """ Sets the display name of the publisher from the metadata. """

        Publisher = namedtuple('Publisher', ['name', 'uri'])

        publishers_in_metadata = self._get_authority_element_by_role(self.PUBLISHER_SHORT_STRING)
        publishers = []
        for publisher in publishers_in_metadata:

            publisher_name = publisher.find(self.MODS_TAG_DISPLAY_NAME_STRING)
            if publisher_name is None:
                publisher_name = publisher.find(self.MODS_TAG_NAME_PART)
            publisher_name = publisher_name.text

            publisher_uri = publisher.get(self.ATTRIBUTE_URI_VALUE_STRING, '')
            publishers.append(
                Publisher(publisher_name, publisher_uri)
            )

        self.publishers = publishers

    def _extract_titles_from_metadata(self):
        """ Sets both the title and subtitle data with the appropriate data. """

        title_info_element = self.metadata.find(self.MODS_TAG_TITLE_INFO_STRING)

        # Issues and Volumes may not have a title
        if title_info_element is None:
            return None

        title_element = title_info_element.find(self.MODS_TAG_TITLE_STRING)
        if title_element is not None:
            self.title = title_element.text.strip()

            prefix_tag = title_element.find(self.MODS_TAG_NON_SORT_STRING)
            if prefix_tag is not None:
                self.prefix = prefix_tag.text.strip()
                self.title = '{prefix} {title}'.format(prefix=self.prefix, title=self.title)

        subtitle_element = title_info_element.find(self.MODS_TAG_SUBTITLE_STRING)
        if subtitle_element is not None:
            self.subtitle = subtitle_element.text.strip()

        translated_title_elements = self.metadata.find_all(self.MODS_TAG_TITLE_INFO_STRING,
                                                           {self.TYPE_STRING: self.TRANSLATED_STRING})

        if translated_title_elements:
            self._add_translated_titles_to_title(translated_title_elements)

    def _get_authority_element_by_role(self, role_type: str) -> list:
        """ Finds all metadata elements having the given role.
            This function is used for finding e.g. authors and publishers.
        """

        def is_searched_role(person_element, role_type):
            role_string_in_element = person_element.find(self.MODS_TAG_ROLE_STRING,
                                                         {self.AUTHORITY_STRING: self.MARCRELATOR_STRING})
            if role_string_in_element is not None:
                return role_string_in_element.text == role_type
            else:
                return False

        persons_in_metadata = self.metadata.find_all(self.MODS_TAG_NAME_STRING)
        persons_in_given_role = [person_element
                                 for person_element in persons_in_metadata
                                 if is_searched_role(person_element, role_type)
                                 ]

        return persons_in_given_role

    def _get_date_elements_from_metadata(self) -> list:
        mods_data = self.metadata.find('mods:mods')
        relevant_elements = mods_data.find_all(self.MODS_TAG_ORIGIN_INFO_STRING, recursive=False)
        if not relevant_elements:
            relevant_elements = self.metadata.find_all(self.MODS_TAG_PART_STRING)

        return relevant_elements

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

    def _guess_primary_language(self):
        if self.languages:
            return self.languages[0]
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


class ArticleHandlingExportElement(VisualLibraryExportElement, ABC):
    """ All classes handling article lists should inherit from this class. """

    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)
        self._articles = []
        self._articles_processed = False

    @property
    def articles(self):
        if not self._articles_processed:
            logger.debug('Reading all articles!')
            self._articles = get_list_by_type(self._resolve_depending_sections(), Article)
            self._articles_processed = True

        return self._articles

    @articles.setter
    def articles(self, val):
        function_is_read_only()


class Journal(ArticleHandlingExportElement):
    """ A Journal class holds its volumes. """

    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)
        self._volumes = []
        self._volumes_processed = False

    @property
    def volumes(self) -> list:
        if not self._volumes_processed:
            logger.debug('Reading all volumes')
            self._volumes = get_list_by_type(self._resolve_depending_sections(), Volume)
            self._volumes_processed = True

        return self._volumes

    @property
    def elements(self) -> list:
        return self.volumes + self.articles

    @volumes.setter
    def volumes(self, val):
        function_is_read_only()


class Volume(ArticleHandlingExportElement):
    """ A Volume class can hold both Issues OR articles. """

    VOLUME_STRING = 'volume'

    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)
        self._issues = []
        self._sections_resolved = False
        self.publisher = None

    @property
    def articles(self):
        _ = self.issues
        return self._articles

    @property
    def issues(self):
        if not self._sections_resolved:
            logger.debug('Reading all sections!')
            self._resolve_sections()
            self._sections_resolved = self._articles_processed = True

        return self._issues

    @property
    def number(self):
        if self._number is None:
            self._number = self._get_number_from_metadata_details_by_attribute({})

        return self._number

    @property
    def elements(self):
        return self.issues + self.articles

    @issues.setter
    def issues(self, val):
        """ Disable setter """
        function_is_read_only()

    def _extract_publication_date_from_metadata(self, year_only: bool = True):
        """ This is a publication in a single moment in time. Hence a year only is forced. """
        return super()._extract_publication_date_from_metadata(year_only)

    def _resolve_sections(self):
        sections = list(self._resolve_depending_sections())
        self._issues = get_list_by_type(sections, Issue)
        self._articles = get_list_by_type(sections, Article)


class Issue(ArticleHandlingExportElement):
    """ An Issue class holds only articles. """

    ISSUE_STRING = 'issue'

    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)

    @property
    def number(self):
        if self._number is None:
            self._number = self._get_number_from_metadata_details_by_attribute({})

        return self._number

    @property
    def elements(self):
        return self.articles

    def _extract_publication_date_from_metadata(self, year_only: bool = True):
        """ This is a publication in a single moment in time. Hence a year only is forced. """
        return super()._extract_publication_date_from_metadata(year_only)


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

        logger.debug('Created new Page object. ID {id}'.format(id=self.id))

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
        page_id_string = page_metadata.get(self.ID_STRING)
        return page_id_string.replace('phys', '')

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
    PARTICIPATING_PERSON_SHORT_STRING = 'asn'
    FAMILY_STRING = 'family'
    GIVEN_STRING = 'given'
    TITLE_STRING = 'termsOfAddress'

    METS_TAG_SECTION_STRING = 'mets:dmdsec'
    MODS_TAG_END_STRING = 'mods:end'
    MODS_TAG_EXTEND_STRING = 'mods:extent'
    MODS_TAG_LIST_STRING = 'mods:list'
    MODS_TAG_NAME_PART_STRING = 'mods:namepart'
    MODS_TAG_START_STRING = 'mods:start'

    UNIT_STRING = 'unit'

    def __init__(self, vl_id, xml_importer, parent):
        super().__init__(vl_id, xml_importer, parent)

        self.authors = self._extract_authors_from_metadata()
        self.doi = None
        self.page_range = self._extract_page_range_from_metadata()
        self.is_standalone = False

    @property
    def elements(self):
        return self.pages

    def _extract_authors_from_metadata(self) -> list:
        """ Returns a list of author namedtuples from the metadata. """

        authors = []
        author_elements_in_metadata = self._get_authority_element_by_role(self.AUTHOR_SHORT_STRING)
        participate_elements_in_metadata = self._get_authority_element_by_role(self.PARTICIPATING_PERSON_SHORT_STRING)
        for person in author_elements_in_metadata + participate_elements_in_metadata:
            given_name = person.find(self.MODS_TAG_NAME_PART_STRING, {self.TYPE_STRING: self.GIVEN_STRING})
            family_name = person.find(self.MODS_TAG_NAME_PART_STRING, {self.TYPE_STRING: self.FAMILY_STRING})
            display_name = person.find(self.MODS_TAG_DISPLAY_NAME_STRING)
            title_of_address = person.find(attrs={self.TYPE_STRING: self.TITLE_STRING})

            # Clean names
            given_name = given_name.text if given_name is not None else ''
            family_name = family_name.text if family_name is not None else ''
            title = title_of_address.text if title_of_address is not None else ''
            display_name = display_name.text if display_name is not None else ''

            # In the XML the given name is required while the family name is NOT!
            if not given_name and display_name:
                given_name = display_name

            authors.append(Author(given_name, family_name, title))

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

    def _extract_publication_date_from_metadata(self, year_only: bool = True):
        """ This is a publication in a single moment in time. Hence a year only is forced. """
        return super()._extract_publication_date_from_metadata(year_only)

    def _is_person_element_author(self, person_element: Soup):
        return person_element.find(self.MODS_TAG_ROLE_STRING,
                                   {self.AUTHORITY_STRING: self.MARCRELATOR_STRING}).text == self.AUTHOR_SHORT_STRING


# In C++, this would be a forward declaration on top of the file
# TODO: The resolution of the object type could use a better solution
RESPONSE_HEADER = 'header'
VL_OBJECT_SPECIFICATION = 'setspec'
VL_OBJECT_TYPES = {
    'article': Article,
    'book': Volume,
    'journal': Journal,
    'journal_issue': Issue,
    'journal_volume': Volume,
    'multivolumework': Journal,
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


def is_author_in_metadata(metadata: Soup):
    role_element = metadata.find(VisualLibraryExportElement.MODS_TAG_ROLE_STRING,
                                 {VisualLibraryExportElement.AUTHORITY_STRING:
                                      VisualLibraryExportElement.MARCRELATOR_STRING})

    return role_element is not None and (role_element.text == Article.AUTHOR_SHORT_STRING or
                                     role_element.text == Article.PARTICIPATING_PERSON_SHORT_STRING)


def get_object_type_from_xml(xml_data: Soup, vl_id: str):
    header = get_xml_header_from_vl_response(xml_data)
    type_from_header = get_object_type_from_xml_header(header)

    if type_from_header is not None:
        return type_from_header

    metadata = xml_data.find(Article.METS_TAG_SECTION_STRING,
                             {VisualLibraryExportElement.ID_STRING: 'md{id}'.format(id=vl_id)})

    if is_author_in_metadata(metadata) and has_pages(metadata):
        return Article

    sections = xml_data.find_all(VisualLibraryExportElement.METS_TAG_DIV_STRING,
                                 attrs=MetsImporter.ATTRIBUTE_FILTER_FOR_SECTIONS)

    if sections:
        nesting_deepness_of_corresponding_section = _get_nesting_deepness_for_section(sections, vl_id)
        if nesting_deepness_of_corresponding_section == 1:
            return Journal
        elif nesting_deepness_of_corresponding_section >= 3:
            return Issue
        elif not subsections_have_resource_pointer(xml_data, vl_id):
            return Article
        else:
            return Volume

    raise TypeError('For the given ID {id} no appropriate Type could be found!'.format(id=vl_id))


def subsections_have_resource_pointer(metdata: Soup, vl_id: str):
    own_section = metdata.find(attrs={'id': 'log{}'.format(vl_id)})
    subsections = own_section.find_all(attrs=MetsImporter.ATTRIBUTE_FILTER_FOR_SECTIONS)

    return any(section.find(VisualLibraryExportElement.METS_TAG_RESOURCE_POINTER_STRING) is not None
               for section in subsections
               )


def has_pages(metadata: Soup):
    return metadata.find(Article.MODS_TAG_EXTEND_STRING, {Article.UNIT_STRING: Article.PAGE_STRING}) is not None


def _get_nesting_deepness_for_section(sections: list, id_search_string: str) -> int:
    nesting_deepness_of_corresponding_section = 0
    last_parent = None
    for section in sections:
        nesting_deepness_of_corresponding_section += 1
        if id_search_string in section.get(VisualLibraryExportElement.ID_STRING) or last_parent == section.parent:
            break
        last_parent = section.parent

    return nesting_deepness_of_corresponding_section


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
    VISUAL_LIBRARY_BASE_URL = 'https://sammlungen.ub.uni-frankfurt.de'
    VISUAL_LIBRARY_OAI_URL = VISUAL_LIBRARY_BASE_URL + '/oai/?verb=GetRecord&metadataPrefix={xml_response_format}' \
                                                       '&identifier={identifier}'
    VL_OBJECT_TYPES = VL_OBJECT_TYPES

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

        logger.info('Creating new VL element')
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

    def get_page_by_id(self, page_id, partent_article_id=None):
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

        if partent_article_id is None:
            title_info_element = html_importer.get_element_by_id([self.TITLE_INFO_ELEMENT_ID, self.TITLE_CONTENT_ELEMENT_ID])
            title_info_link_element = title_info_element.find(self.HTML_ELEMENT_LINK)
            title_vl_id = re.search(r'[0-9]+$', title_info_link_element[self.HREF_STRING])

            title_vl_object = self.get_element_for_id(title_vl_id.group())

            page_hierarchy_labels = html_importer.get_navigation_hierarchy_labels()
            article_section_containing_page = title_vl_object.find_section_by_label(page_hierarchy_labels[-1],
                                                                                    page_hierarchy_labels, recursive=True)

            article_id = re.sub('^log', '', article_section_containing_page.id)
            article_object_containing_page = VisualLibrary().get_element_for_id(article_id)
        else:
            article_object_containing_page = VisualLibrary().get_element_for_id(partent_article_id)

        for page in article_object_containing_page.pages:
            if page.vl_id == page_id:
                return page

        return None

    def _create_vl_export_object(self, vl_id: str, xml_data: Soup) -> (VisualLibraryExportElement, None):
        object_type = get_object_type_from_xml(xml_data, vl_id)
        if object_type is not None:
            xml_importer = MetsImporter()
            xml_importer.parse_xml(xml_data)
            return object_type(vl_id, xml_importer, parent=None)
        else:
            return None
