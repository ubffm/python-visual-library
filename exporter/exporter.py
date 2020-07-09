from abc import ABC, abstractmethod


class InstanceExporter(ABC):
    """ An interface class to allow the communication between Importer and Exporter. """

    @abstractmethod
    def get_next_instance(self):
        """ Returns an object of the current class. """
        pass



