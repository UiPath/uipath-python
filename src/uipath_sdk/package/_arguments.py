class UiPathArgument:
    def __init__(self, alias: str = "", required: bool = True):
        self.required = required
        self.alias = alias
