class EvaluationRuntimeException(Exception):
    def __init__(self, spans, logs, root_exception, execution_time):
        self.spans = spans
        self.logs = logs
        self.root_exception = root_exception
        self.execution_time = execution_time
