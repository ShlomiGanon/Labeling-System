class User:
    def __init__(self, name):
        self._name = name
        self._current_data = None

    def __contains__(self, data):
        return data == self._current_data

    def having_data(self):
        return self._current_data is not None
    
    def get_data(self):
        return self._current_data
    
    def set_data(self, data):
        self._current_data = data
    
    def get_name(self):
        return self._name