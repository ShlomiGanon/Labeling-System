from abc import ABC, abstractmethod

# lable have both text and image are at the format of-> 
#                                             select from one above:
#                                             1. Independent: The image alone explains the topic.
#                                             2. Dependent: The image needs the text to explain the topic.
#                                             3. Noise: The image is irrelevant to the text. 
#                                             4. ......
# and the user need to chose one button


# lable have only image are at the format of->
#                                             A text box for the user to write a "Golden Caption" describing the image


# lable have text only are at the format of->
#                                             Label Steps:
#                                             1. Entity Identification: Highlight or type the main entity (Person, Org, Place).
#                                             2. Topic Assignment: Write the text topic.
#                                             3. Sentiment/Emotion: Rate the framing (e.g., Good, Bad, Trust, Fear, Anger)
#                                             specifically toward that entity.



class Labeling_Field(ABC):

    def __init__(self):
        self._answer = None
        pass

    @abstractmethod
    def get_field_text(self):
        pass

    @abstractmethod
    def get_field_type(self):
        pass

    def get_answer(self):
        return self._answer

    def set_answer(self, answer):
        self._answer = answer

class Press_Button_Field(Labeling_Field):

    def __init__(self, buttons_text):
        self._buttons_text = buttons_text
    
    def get_field_type(self):
        return "Press Button"
    
    def get_buttons_text(self):
        return self._buttons_text

class List_Field(Labeling_Field):

    def __init__(self, options):
        self._options = options
    
    def get_options(self):
        return self._options

    def get_field_type(self):
        return "List"

class Text_Field(Labeling_Field):
    def __init__(self , text):
        self._text = text
    
    def get_text(self):
        return self._text

    def get_field_type(self):
        return "Text"


