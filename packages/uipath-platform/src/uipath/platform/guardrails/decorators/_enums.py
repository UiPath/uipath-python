"""Enums for guardrail decorators."""

from enum import Enum


class GuardrailExecutionStage(str, Enum):
    """Execution stage for guardrails."""

    PRE = "pre"
    """Evaluate before the target executes."""

    POST = "post"
    """Evaluate after the target executes."""

    PRE_AND_POST = "pre&post"
    """Evaluate both before and after the target executes."""


class PIIDetectionEntityType(str, Enum):
    """PII detection entity types supported by UiPath guardrails.

    These entities match the available options from the UiPath guardrails service
    backend. The enum values correspond to the exact strings expected by the API.
    """

    PERSON = "Person"
    ADDRESS = "Address"
    DATE = "Date"
    PHONE_NUMBER = "PhoneNumber"
    EUGPS_COORDINATES = "EugpsCoordinates"
    EMAIL = "Email"
    CREDIT_CARD_NUMBER = "CreditCardNumber"
    INTERNATIONAL_BANKING_ACCOUNT_NUMBER = "InternationalBankingAccountNumber"
    SWIFT_CODE = "SwiftCode"
    ABA_ROUTING_NUMBER = "ABARoutingNumber"
    US_DRIVERS_LICENSE_NUMBER = "USDriversLicenseNumber"
    UK_DRIVERS_LICENSE_NUMBER = "UKDriversLicenseNumber"
    US_INDIVIDUAL_TAXPAYER_IDENTIFICATION = "USIndividualTaxpayerIdentification"
    UK_UNIQUE_TAXPAYER_NUMBER = "UKUniqueTaxpayerNumber"
    US_BANK_ACCOUNT_NUMBER = "USBankAccountNumber"
    US_SOCIAL_SECURITY_NUMBER = "USSocialSecurityNumber"
    USUK_PASSPORT_NUMBER = "UsukPassportNumber"
    URL = "URL"
    IP_ADDRESS = "IPAddress"


class HarmfulContentEntityType(str, Enum):
    """Harmful content entity types supported by UiPath guardrails.

    These entities correspond to the Azure Content Safety categories.
    """

    HATE = "Hate"
    SELF_HARM = "SelfHarm"
    SEXUAL = "Sexual"
    VIOLENCE = "Violence"


class IntellectualPropertyEntityType(str, Enum):
    """Intellectual property entity types supported by UiPath guardrails."""

    TEXT = "Text"
    CODE = "Code"
