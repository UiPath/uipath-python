class InputArgument:
    def __init__(self, alias: str = "", required: bool = True):
        self.required = required
        self.alias = alias


class OutputArgument:
    def __init__(self, alias: str = ""):
        self.alias = alias
