from bettertoolbox.toolbuttons import ToolList
class ToolCategory:
    def __init__(self, name):
        self.name = name
        self.ToolButtons = {}
    def addTool(self, ToolButton):
        self.ToolButtons[ToolButton.actionName] = ToolButton
class CategoryDict:
    def __init__(self):
        super().__init__()
        self.categories = { 
                           "Transform": ToolCategory("Transform"),
                           "Vector": ToolCategory("Vector"),
                           "Paint": ToolCategory("Paint"),
                           "Fill": ToolCategory("Fill"),
                           "Shape": ToolCategory("Shape"),
                           "Select": ToolCategory("Select"),
                           "AutoSelect": ToolCategory("AutoSelect"),
                           "Reference": ToolCategory("Reference"),
                           "Navigation": ToolCategory("Navigation")
                           }
category_dictionary = CategoryDict()
