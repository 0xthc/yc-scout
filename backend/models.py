from pydantic import BaseModel


class FounderOut(BaseModel):
    id: int
    name: str
    handle: str
    avatar: str
    location: str
    bio: str
    domain: str
    stage: str
    company: str
    founded: str
    status: str
    yc_alumni_connections: int
    sources: list[str]
    tags: list[str]
    score: int
    scoreBreakdown: dict[str, int]
    signals: list[dict]
    github_stars: int
    hn_karma: int
    followers: int


class PaginatedFounders(BaseModel):
    founders: list[FounderOut]
    total: int
    limit: int
    offset: int


class StatusUpdate(BaseModel):
    status: str


class PipelineResult(BaseModel):
    founders_scraped: int
    founders_scored: int
    alerts_sent: int
