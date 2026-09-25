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
                           "Move": ToolCategory("Move"),
                           "Marquee": ToolCategory("Marquee"),
                           "Lasso": ToolCategory("Lasso"),
                           "Wand": ToolCategory("Wand"),
                           "Crop": ToolCategory("Crop"),
                           "Eyedropper": ToolCategory("Eyedropper"),
                           "Healing": ToolCategory("Healing"),
                           "Brush": ToolCategory("Brush"),
                           "Erase": ToolCategory("Erase"),
                           "Fill": ToolCategory("Fill"),
                           "Pen": ToolCategory("Pen"),
                           "Text": ToolCategory("Text"),
                           "PathSelect": ToolCategory("PathSelect"),
                           "Shape": ToolCategory("Shape"),
                           "Navigation": ToolCategory("Navigation"),
                           "Reference": ToolCategory("Reference"),
                           "Zoom": ToolCategory("Zoom")
                           }
category_dictionary = CategoryDict()
