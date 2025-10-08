class EvaluationRuntimeException(Exception):
    def __init__(self, spans, logs, root_exception):
        self.spans = spans
        self.logs = logs
        self.root_exception = root_exception
