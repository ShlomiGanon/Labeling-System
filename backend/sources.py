import CSVreader

from abc import ABC, abstractmethod
class Data_Source(ABC):
    @abstractmethod
    def __init__(self):
        pass
    @abstractmethod
    def is_empty(self):
        pass
    @abstractmethod
    def get_next_data(self):
        pass

#represent csv file on the disk
class Local_CSV_File(Data_Source):

    def __init__(self, file_path):
        self._file_path = file_path
        self._data = CSVreader.load_csv_file(file_path)

    def is_empty(self):
        return len(self._data) == 0

    def get_next_data(self):
        if self.is_empty() : return None
        else:
            data = self._data.pop(0)
            return data


#represent csv file on google drive
class CSV_On_Google_Drive(Data_Source):
    def __init__(self, url):
        self._url = url
        #to be implemented
    def is_empty(self):
        #to be implemented
        return False
    def get_next_data(self):
        #to be implemented
        return None

#represent csv file on s3(amazon web services)
class CSV_On_S3(Data_Source):
    def __init__(self, url):
        self._url = url
        #to be implemented
    def is_empty(self):
        #to be implemented
        return False
    def get_next_data(self):
        #to be implemented
        return None