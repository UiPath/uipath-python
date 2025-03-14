"""Define the state structures for the agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence, Optional, List

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from langgraph.managed import IsLastStep
from typing_extensions import Annotated

@dataclass
class InputState:
    """Defines the input state for the agent, representing a narrower interface to the outside world.

    This class is used to define the initial state and structure of incoming data.
    """
    MismatchedItems: str = ""
    Company: str = ""
    Supplier: str = ""
    SupplierWebsite: str = ""

@dataclass
class OutputState:

    SupplierEmail: Annotated[str, ..., "Supplier email, queried from SAP or human escalation"] = ""

    InvestigationResult: Annotated[Optional[OutputState_InvestigationResult], ..., "The results of the investigation"] = None

    MismatchedItemsFindings:  Annotated[Optional[List[OutputState_MismatchedItemsFindings_Item]], ..., "The categorization of replacement items and the reasoning "] = None

@dataclass
class OutputState_InvestigationResult:

    MoveForward: Annotated[Optional[OutputState_InvestigationResult_MoveForward], ..., "Should the company move forward with the dispute with the supplier?"] = None

    SKUMismatchAction: Annotated[Optional[OutputState_InvestigationResult_SKUMismatchAction], ..., "What should the company do when the purchase order has SKUs that do not match the invoice?"] = None

    PODoesNotMatch: Annotated[Optional[OutputState_InvestigationResult_PODoesNotMatch], ..., "What should the company do when the purchase order has SKUs that does not match the invoice?"] = None

    DesiredOutcomes: Annotated[Optional[OutputState_InvestigationResult_DesiredOutcomes], ..., "What should be the desired outcomes for the Company?"] = None

    Email: Annotated[Optional[OutputState_InvestigationResult_Email], ..., "What should be the desired outcomes for the Company?"] = None

@dataclass
class OutputState_InvestigationResult_MoveForward:

    Answer: Annotated[str, ..., "The answer to MoveForward"] = ""

    Citation: Annotated[str, ..., "The Citation to the answer for MoveForward. The citation should contain all document names, all page numbers, and the specific section for where the information was found. "] = ""

    AnswerBool: Annotated[bool, ..., "The Answer as a Boolean. If the company should move forward, this should be true"] = False

@dataclass
class OutputState_InvestigationResult_SKUMismatchAction:

    Answer: Annotated[str, ..., "The Answer to SKUMismatchAction"] = ""

    Citation: Annotated[str, ..., "The Citation to the answer for SKUMismatchAction. The citation should contain all document names, all page numbers, and the specific section for where the information was found. "] = ""

@dataclass
class OutputState_InvestigationResult_PODoesNotMatch:

    Answer: Annotated[str, ..., "The Answer for PODoesNotMatch"] = ""

    Citation: Annotated[str, ..., "The Citation to the answer for PODoesNotMatch. The citation should contain all document names, all page numbers, and the specific section for where the information was found. "] = ""

@dataclass
class OutputState_InvestigationResult_DesiredOutcomes:

    Answer: Annotated[str, ..., "The Answer for DesiredOutcomes"] = ""

    Citation: Annotated[str, ..., "The Citation to the answer for DesiredOutcomes. The citation should contain all document names, all page numbers, and the specific section for where the information was found. "] = ""

@dataclass
class OutputState_InvestigationResult_Email:

    emailSubject: Annotated[str, ..., "Subject of the email"] = ""

    emailBody: Annotated[str, ..., "Body of the email"] = ""

@dataclass()
class OutputState_MismatchedItemsFindings_Item:

    Reasoning: Annotated[str, ..., "The reasoning for the categorization"] = ""

    MismatchedParts: Annotated[str, ..., "The names of the items that were mismatched"] = ""

    ValidReplacement: Annotated[str, ..., "If the mismatched items were found to be a valid replacement, this should be true"] = ""

@dataclass
class State(InputState, OutputState):
    """Represents the complete state of the agent, extending InputState with additional attributes.

    This class can be used to store any information needed throughout the agent's lifecycle.
    """

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(
        default_factory=list
    )
    """
    Messages tracking the primary execution state of the agent.

    Typically accumulates a pattern of:
    1. HumanMessage - user input
    2. AIMessage with .tool_calls - agent picking tool(s) to use to collect information
    3. ToolMessage(s) - the responses (or errors) from the executed tools
    4. AIMessage without .tool_calls - agent responding in unstructured format to the user
    5. HumanMessage - user responds with the next conversational turn

    Steps 2-5 may repeat as needed.

    The `add_messages` annotation ensures that new messages are merged with existing ones,
    updating by ID to maintain an "append-only" state unless a message with the same ID is provided.
    """

    is_last_step: IsLastStep = field(default=False)
    """
    Indicates whether the current step is the last one before the graph raises an error.

    This is a 'managed' variable, controlled by the state machine rather than user code.
    It is set to 'True' when the step count reaches recursion_limit - 1.
    """


    # Additional attributes can be added here as needed.
    # Common examples include:
    # retrieved_documents: List[Document] = field(default_factory=list)
    # extracted_entities: Dict[str, Any] = field(default_factory=dict)
    # api_connections: Dict[str, Any] = field(default_factory=dict)

