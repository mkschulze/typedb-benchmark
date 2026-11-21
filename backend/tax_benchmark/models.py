from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONFIGURATIONS = [
    {
        "id": "rag",
        "name": "Source retrieval",
        "description": "The model searches the same documents and case records.",
    },
    {
        "id": "typedb_context",
        "name": "TypeDB context",
        "description": "Structured relationships and evidence, without decision functions.",
    },
    {
        "id": "typedb_functions",
        "name": "TypeDB + functions",
        "description": "Structured context with executable decision logic.",
    },
    {
        "id": "sql",
        "name": "SQL control",
        "description": "Equivalent curated facts and decision logic through SQL.",
    },
]
CONFIGURATION_IDS = {item["id"] for item in CONFIGURATIONS}
Money = Annotated[int, Field(strict=True, ge=0)] | None


class TaxAnswer(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Literal["determined", "needs_information", "review_required", "outside_scope"]
    relief_eligibility: Literal["eligible", "ineligible", "undetermined"]
    relief_route: str
    withholding_tax_cents: Money
    solidarity_surcharge_cents: Money
    total_withholding_cents: Money
    net_payment_cents: Money
    refund_status: str
    refund_amount_cents: Money
    missing_facts: list[str]
    source_ids: list[str]
    evidence_ids: list[str]
    reasoning: str = Field(min_length=1, max_length=20000)

    @model_validator(mode="after")
    def check_sum(self):
        values = (self.withholding_tax_cents, self.solidarity_surcharge_cents, self.total_withholding_cents)
        if all(value is not None for value in values) and values[0] + values[1] != values[2]:
            raise ValueError("Withholding total does not equal tax plus surcharge")
        if self.status == "determined" and any(value is None for value in values):
            raise ValueError("A determined answer needs withholding amounts")
        return self


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_ids: list[str] = Field(min_length=1, max_length=100)
    model_ids: list[str] = Field(min_length=1, max_length=10)
    configurations: list[str] = Field(min_length=1, max_length=4)
    repetitions: int = Field(default=1, ge=1, le=5, strict=True)
    max_steps: int = Field(default=6, ge=1, le=12, strict=True)

    @model_validator(mode="after")
    def validate_selections(self):
        for selection in (self.case_ids, self.model_ids, self.configurations):
            if len(selection) != len(set(selection)):
                raise ValueError("Selections must not contain duplicates")
        if set(self.configurations) - CONFIGURATION_IDS:
            raise ValueError("Unknown comparison configuration")
        if self.total_trials > 1800:
            raise ValueError("A run may contain at most 1,800 trials")
        return self

    @property
    def total_trials(self):
        return len(self.case_ids) * len(self.model_ids) * len(self.configurations) * self.repetitions
