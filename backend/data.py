#this class will hold the data
class Data:
    def __init__(self, text, image_url):
        self.text = text
        self.image_url = image_url

    def is_have_text(self):
        return len(str(self.text)) > 0

    def is_have_image_url(self):
        return len(str(self.image_url)) > 0

#this function will split the data with text_column and image_column
def split_data(data_array, text_column=0, image_column=1):
    result = []
    for i in range(len(data_array)):
        new_item = Data(data_array[i][text_column], data_array[i][image_column])
        result.append(new_item)
    return result


#this function will split the data smart without text_column and image_column
def split_data_smart(data_array):
    result = []
    for i in range(len(data_array)):
        if "www" in str(data_array[i][0]):
            image = data_array[i][0]
            text = data_array[i][1]
        else:
            text = data_array[i][0]
            image = data_array[i][1]

        new_item = Data(text, image)
        result.append(new_item)
    return result