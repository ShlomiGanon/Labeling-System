from CSVreader import *
from sources import *
from data import *
from user import *
from collections import deque


class Labeling_Project:
    def __init__(self, name , owner_name):
        self._name = name
        self._owner_name = owner_name

        self._avilable_assignments = deque()
        self._active_assignments = {} #{ USER_NAME : [DATA] }


    def load_data_source(self, data_source):
        while(not data_source.is_empty()):
            self._avilable_assignments.append(data_source.get_next_data())
    
    def get_avilable_assignment(self):
        if(len(self._avilable_assignments) == 0):
            return None
        else:
            return self._avilable_assignments.popleft()
    
    def submit_assignment(self, user_name, data):
        self._active_assignments[user_name] = data
    
    def user_has_assignment(self, user_name):
        return user_name in self._active_assignments
    
    def get_user_assignment(self, user_name):
        return self._active_assignments[user_name]
    
    def remove_user_assignment(self, user_name):
        del self._active_assignments[user_name]

