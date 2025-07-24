from abc import ABC


class EvaluatorBase(ABC):
    async def evaluate(self, evaluation_id, evaluation_name, input_data, expected_output, actual_output):
        pass
