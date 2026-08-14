from pydantic import BaseModel, Field, field_validator

VALID_CONFIDENCE_TAGS = {"estimated_from_source_data", "directional_estimate"}


class ImpactBreakdown(BaseModel):
    delivery_impact: str = Field(
        description="Impact on project timelines, milestones, or deliverables."
    )
    customer_impact: str = Field(
        description="Impact on end-users, stakeholders, or external partners."
    )
    business_impact: str = Field(
        description="Impact on revenue, compliance, or strategic business goals."
    )
    team_impact: str = Field(
        description="Impact on engineering capacity, morale, or workload."
    )


class RiskItem(BaseModel):
    risk: str = Field(description="Concise title or summary of the delivery risk.")
    explanation: str = Field(
        description="Detailed explanation of why this is a risk based on evidence."
    )
    citations: list[str] = Field(
        description="List of exact chunk IDs supporting this claim."
    )
    impact_breakdown: ImpactBreakdown = Field(
        description="Structured breakdown of the risk's impact."
    )
    confidence_tag: str | None = Field(
        default=None,
        description=(
            "Set to 'estimated_from_source_data' ONLY if a specific figure, ticket "
            "count, or exact metric exists in the cited evidence chunks. Otherwise "
            "set to 'directional_estimate'. No other values are valid."
        ),
    )
    is_sev1: bool = Field(
        default=False,
        description=(
            "True if the risk involves an active SEV-1 incident, a P0 bug, or an "
            "open/unassigned postmortem remediation ticket from a SEV-1 outage. "
            "False otherwise -- do not set true just because the risk has high "
            "financial or customer impact in a general sense."
        ),
    )
    is_contradiction: bool = Field(
        default=False,
        description="True if an official status report contradicts underlying tickets/Slack threads.",
    )
    recommendations: list[str] = Field(
        description="2-3 actionable recommendations to mitigate the risk, based ONLY on the retrieved evidence."
    )

    @field_validator("confidence_tag", mode="before")
    @classmethod
    def validate_confidence_tag(cls, v):
        if v not in VALID_CONFIDENCE_TAGS:
            return None
        return v


class RiskExtractionResponse(BaseModel):
    risks: list[RiskItem] = Field(
        description="List of extracted delivery risks meeting criteria."
    )
