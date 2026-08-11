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

    | Value |
    |---|
    | `PERSON` |
    | `ADDRESS` |
    | `DATE` |
    | `PHONE_NUMBER` |
    | `EUGPS_COORDINATES` |
    | `EMAIL` |
    | `CREDIT_CARD_NUMBER` |
    | `INTERNATIONAL_BANKING_ACCOUNT_NUMBER` |
    | `SWIFT_CODE` |
    | `ABA_ROUTING_NUMBER` |
    | `US_DRIVERS_LICENSE_NUMBER` |
    | `UK_DRIVERS_LICENSE_NUMBER` |
    | `US_INDIVIDUAL_TAXPAYER_IDENTIFICATION` |
    | `UK_UNIQUE_TAXPAYER_NUMBER` |
    | `US_BANK_ACCOUNT_NUMBER` |
    | `US_SOCIAL_SECURITY_NUMBER` |
    | `USUK_PASSPORT_NUMBER` |
    | `URL` |
    | `IP_ADDRESS` |
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

    | Value |
    |---|
    | `HATE` |
    | `SELF_HARM` |
    | `SEXUAL` |
    | `VIOLENCE` |
    """

    HATE = "Hate"
    SELF_HARM = "SelfHarm"
    SEXUAL = "Sexual"
    VIOLENCE = "Violence"


class IntellectualPropertyEntityType(str, Enum):
    """Intellectual property entity types supported by UiPath guardrails.

    | Value |
    |---|
    | `TEXT` |
    | `CODE` |
    """

    TEXT = "Text"
    CODE = "Code"
