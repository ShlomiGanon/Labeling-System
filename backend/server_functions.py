import CSVreader
import data
from collections import deque


avilable_assignments = deque()
active_assignments = {} #{ USER_NAME : [DATA] }

def load_data_source(data_source):
    while(not data_source.is_empty()):
        avilable_assignments.append(data_source.get_next_data())
    
def get_avilable_assignment():
    if(len(avilable_assignments) == 0):
        return None
    else:
        return avilable_assignments.popleft()

def submit_assignment(user_name, data):
    active_assignments[user_name] = data

def user_has_assignment(user_name):
    return user_name in active_assignments

def get_user_assignment(user_name):
    return active_assignments[user_name]

def remove_user_assignment(user_name):
    del active_assignments[user_name]    