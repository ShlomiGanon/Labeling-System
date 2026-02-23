#this class will hold the data
class Data:
    def __init__(self, text, image_url):
        self.text = text
        self.image_url = image_url

    def get_text(self):
        return self.text
    
    def get_image_url(self):
        return self.image_url
    
    def is_have_text(self):
        return len(str(self.text)) > 0

    def is_have_image_url(self):
        return len(str(self.image_url)) > 0

    def __str__(self):
        return f"Text: {self.text}, Image URL: {self.image_url}"

#this function will split the data smart without text_column and image_column
def get_data_from_source(source):
    pure_data = source.get_next_data()
    if "www" in str(pure_data[0]) or "http" in str(pure_data[0]):
        image = pure_data[0]
        text = pure_data[1]
    else:
        text = pure_data[0]
        image = pure_data[1]

    return Data(text, image)


#this function will split the data with text_column and image_column
def get_data_from_source(source,text_column:int, image_column:int):
    pure_data = source.get_next_data()
    text = pure_data[text_column]
    image = pure_data[image_column]
    return Data(text, image)