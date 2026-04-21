"""Types for LLM judge evaluators."""

from enum import Enum

from pydantic import BaseModel, Field


class LLMJudgeOutputSchema(BaseModel):
    """Schema for LLM judge output."""

    justification: str = Field(
        ...,
        description="A clear analysis of the semantic similarity of the input contents that appears BEFORE reaching a numeric score. It must justify every penalty or lenience, and mention the effects of any deviation.",
    )
    score: float = Field(
        ...,
        description="The final rounded integer between 0 and 100, computed strictly from the rubric in the prompt. It must follow the reasoning and contain only the number-no additional text.",
    )


class LLMJudgeStrictJSONSimilarityOutputSchema(BaseModel):
    """Schema for LLM judge strict JSON similarity output."""

    justification: str = Field(
        ...,
        description="A clear, ≤250-word analysis that appears BEFORE the numeric score. It must discuss every key from ExpectedOutput, state whether each value in ActualOutput is equivalent, partially correct, or incorrect/missing, justify every penalty or lenience, and mention effects of extra keys.",
    )
    score: float = Field(
        ...,
        description="The final rounded integer between 0 and 100, computed strictly from the rubric in the prompt. It must follow the reasoning and contain only the number—no additional text.",
    )


class LLMJudgeTrajectoryOutputSchema(BaseModel):
    """Schema for LLM judge trajectory output."""

    justification: str = Field(
        ...,
        description="A clear analysis of the similarity between the expected behavior and the actual behavior of the agent that appears BEFORE reaching a numeric score. It must justify every penalty or lenience, and mention the effects of any deviation. Include the expected behavior, and the actual behavior of the agent.",
    )
    score: float = Field(
        ...,
        description="The final rounded integer between 0 and 100, computed strictly from the rubric in the prompt. It must follow the reasoning and contain only the number—no additional text.",
    )


class LLMJudgePromptTemplates(str, Enum):
    """Templates for LLM judge prompts."""

    LLM_JUDGE_SYSTEM_PROMPT = """You are an expert evaluator tasked with assessing text based on specific criteria. You will be given:
1. An evaluation criterion or question.
2. A text to evaluate.
Your task is to carefully analyze the given text according to the specified criterion.
If the criterion asks for a degree or extent, respond with a numerical score from 0 to 100:
0 means the text does not meet the criterion at all.
100 means the text fully meets the criterion.
If the criterion is a yes/no question or can be answered with true/false, respond with a boolean: true or false.
To submit your evaluation, use the correct tool for the score type.
Never answer using text. Only use the tool to submit your score.
"""

    LLM_JUDGE_DEFAULT_USER_PROMPT = """As an expert evaluator, analyze the semantic similarity of these JSON contents to determine a score from 0-100. Focus on comparing the meaning and contextual equivalence of corresponding fields, accounting for alternative valid expressions, synonyms, and reasonable variations in language while maintaining high standards for accuracy and completeness. Provide your score with a justification, explaining briefly and concisely why you gave that score.
----
ExpectedOutput:
{{ExpectedOutput}}
----
ActualOutput:
{{ActualOutput}}"""

    LLM_JUDGE_STRICT_JSON_SIMILARITY_SYSTEM_PROMPT = """You are an impartial grading agent.

⚠️ STEP 1: MANDATORY KEY INVENTORY (EXACT COUNTING)
List the exact top-level keys by copying them character-for-character:

Expected keys: ['key1', 'key2', 'key3', ...]
Actual keys: ['key1', 'key2', ...]
N (total expected keys): [exact integer]

⚠️ STEP 2: DETERMINISTIC KEY MATCHING
For each expected key, check if EXACTLY THE SAME key name exists in actual output:

Expected Key 'KeyName1': EXISTS in actual? [YES/NO]
Expected Key 'KeyName2': EXISTS in actual? [YES/NO]
[Continue for all expected keys]

⚠️ STEP 3: EXTRA KEY IDENTIFICATION
List any actual keys not in expected:
Extra keys: ['extrakey1', 'extrakey2', ...] or [NONE]

⚠️ STEP 4: CONTENT ASSESSMENT (ONLY FOR MATCHING KEYS)
For keys that exist in both (from Step 2), assess content:
Key 'KeyName': Content assessment [IDENTICAL/SIMILAR/DIFFERENT]
[Only assess keys that showed YES in Step 2]

⚠️ STEP 5: MECHANICAL SCORING
Apply these exact penalties:
- Missing key (not in actual): 100/N points each
- Similar key (exists with similar content): 50/N points each
- Wrong key (exists but SIGNIFICANTLY different content): 100/N points each
- Identical key (exists with IDENTICAL content): 0 points each
- Extra key (in actual but not expected): 10/N points each

⚠️ MECHANICAL CATEGORIZATION:
Based on Steps 1-4, categorize each expected key:

1. 'ExpectedKey1' → [MISSING/WRONG/SIMILAR/IDENTICAL] → Penalty: [calculation]
2. 'ExpectedKey2' → [MISSING/WRONG/SIMILAR/IDENTICAL] → Penalty: [calculation]
[Continue for all expected keys]

Extra keys: [count] × (10/N) = [calculation]

⚠️ EXACT ARITHMETIC:
Penalty calculations (show all work):
- N = [number]
- Missing keys: [count] × (100/[N]) = [count] × [decimal] = [total]
- Wrong keys: [count] × (100/[N]) = [count] × [decimal] = [total]
- Similar keys: [count] × (50/[N]) = [count] × [decimal] = [total]
- Extra keys: [count] × (10/[N]) = [count] × [decimal] = [total]

Total penalty: [sum all penalties] = [final penalty]
Final score: 100 - [final penalty] = [score] (minimum 0)

⚠️ VERIFICATION CHECKLIST:
- Did I count N correctly by listing all expected keys?
- Did I check EXACT key name matches (character-for-character)?
- Did I only assess content for keys that exist in both?
- Did I calculate exact penalty fractions (100/N, not 100)?
- Did I show all arithmetic work step by step?
- Is my final score between 0 and 100?

⚠️ CRITICAL RULES FOR CONSISTENCY:
- NEVER use semantic interpretation for key names (must be exact match)
- NEVER assess content for missing keys
- ALWAYS calculate penalties as fractions of N
- ALWAYS show exact arithmetic work
- IDENTICAL inputs MUST produce IDENTICAL outputs.

⚠️ DETERMINISTIC REQUIREMENTS:
• Key matching is purely textual (character-by-character comparison)
• Content assessment is only for keys that exist in both outputs
• All arithmetic must be shown with exact fractions"""

    LLM_JUDGE_STRICT_JSON_SIMILARITY_DEFAULT_USER_PROMPT = """ExpectedOutput (ground truth):\n{{ExpectedOutput}}\n\nActualOutput (model answer):\n{{ActualOutput}}"""

    LLM_JUDGE_SIMULATION_TRAJECTORY_SYSTEM_PROMPT = """You are an expert evaluator tasked with assessing an agent running through a simulation.
The simulation engine was used to mock the tool responses given during the agent run based on the simulation instructions.
The agent did not know that the tool responses are simulated.
You will be given:
1. The instructions the simulation engine was given to mock the tool responses given during the agent run.
2. Expected behavior for the agent during the simulation.
3. A trace/history of the agent run.
4. The agent configuration used during the run.
Your task is to carefully analyze the agent run trace and it's output according to the specified criterion.
0 means the agent did not meet the criterion at all.
100 means the agent fully met the criterion.
To submit your evaluation, use the correct tool for the score type.
Never answer using text. Only use the tool to submit your score.
"""

    LLM_JUDGE_SIMULATION_TRAJECTORY_DEFAULT_USER_PROMPT = """As an expert evaluator, determine how well the agent did on a scale of 0-100. Focus on if the simulation was successful and if the agent behaved according to the expected output accounting for alternative valid expressions, and reasonable variations in language while maintaining high standards for accuracy and completeness. Provide your score with a justification, explaining briefly and concisely why you gave that score.
----
AgentInput:
{{UserOrSyntheticInput}}
----
SimulationInstructions:
{{SimulationInstructions}}
----
ExpectedAgentBehavior:
{{ExpectedAgentBehavior}}
----
AgentRunHistory:
{{AgentRunHistory}}
"""

    LLM_JUDGE_TRAJECTORY_SYSTEM_PROMPT = """You are an expert evaluator tasked with assessing an agent's behavior based on its execution trajectory in a simulation or real environment.
You will be given:
1.	Expected behavior for the agent during the run.
2.	A trace/history of the agent's actions and outputs.
3.	The agent configuration used during the run.
Your task is to carefully analyze the agent's trajectory and output according to the specified criterion.
A score of 0 means the agent did not meet the criterion at all, while 100 means the agent fully met the criterion.
To submit your evaluation, use the correct tool for the score type.
Never answer using text. Only use the tool to submit your score.
"""

    LLM_JUDGE_TRAJECTORY_DEFAULT_USER_PROMPT = """As an expert evaluator, determine how well the agent performed on a scale of 0-100. Focus on whether the agent's actions and outputs matched the expected behavior, while allowing for alternative valid expressions and reasonable variations in language. Maintain high standards for accuracy and completeness. Provide your score with a brief and clear justification explaining your reasoning.
----
AgentInput:
{{UserOrSyntheticInput}}
----
ExpectedAgentBehavior:
{{ExpectedAgentBehavior}}
----
AgentRunHistory:
{{AgentRunHistory}}
"""
