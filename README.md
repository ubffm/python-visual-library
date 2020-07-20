# Visual Library Toolkit

This Python package allows calling the Visual Library (VL) OAI and create Python objects from the response. You should be able to call any VL ID, disregarding if it is a journal, an issue, or an article. Data of depending entities (for example articles of an issue) are called recursively and automatically.

## Usage
You simply create a VL object by

```python
from VisualLibrary import VisualLibrary

vl = VisualLibrary()

# Create an object of a journal
journal = vl.get_element_for_id('12345')

# Create an object of an article
# It's the same, the data context will be evaluated internally
article = vl.get_element_for_id('87453')

# Get only the XML data from the VL as a BeautifulSoup object
xml_data = vl.get_data_for_id('12345')
```

## Customize called URL
The current default URL is for the Visual Library of the University Library in Frankfurt. However, if you want/need to change this, you can simple set `VisualLibrary.VISUAL_LIBRARY_OAI_URL` to the URL of your liking.

## Install package
Simply call

```python
source {path_to_your_virtual_environment}/bin/activate

cd virtual-library/
pip3 install .
```

## Testing
After installing the package, you can call `pytest tests/*py` to run all tests.