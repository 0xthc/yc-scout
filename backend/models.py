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
    incubator: str
    email: str
    twitter: str
    linkedin: str
    website: str
    sources: list[str]
    tags: list[str]
    score: int
    scoreBreakdown: dict[str, int]
    signals: list[dict]
    github_stars: int
    github_commits_90d: int
    github_repos: int
    hn_karma: int
    hn_submissions: int
    hn_top_score: int
    ph_upvotes: int
    ph_launches: int
    followers: int


class PaginatedFounders(BaseModel):
    founders: list[FounderOut]
    total: int
    limit: int
    offset: int


class StatusUpdate(BaseModel):
    status: str


class ContactUpdate(BaseModel):
    email: str | None = None
    twitter: str | None = None
    linkedin: str | None = None
    website: str | None = None


class PipelineResult(BaseModel):
    founders_scraped: int
    founders_scored: int
    alerts_sent: int
