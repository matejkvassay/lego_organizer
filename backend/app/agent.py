"""Add-a-set search agent: description -> ranked Brickset candidates."""
from dataclasses import dataclass, field

from pydantic_ai import Agent, RunContext, UsageLimits
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.models import Model
from sqlalchemy.orm import Session

from . import brickset
from .config import get_settings
from .models import BricksetSet
from .schemas import Candidate, Candidates

INSTRUCTIONS = """\
You help a Lego collector identify a set from a rough, possibly inaccurate description
(wrong name, only a theme and an era, a vague memory of the box).
Use search_brickset to find it. It takes any combination of:
  - query: keywords matched against set number, name, theme and subtheme (keep it short, 1-2 words;
    names the user remembers are often not the official Brickset title, so do not rely on exact names)
  - theme / subtheme / year: exact Brickset filters, e.g. theme "Adventurers", subtheme "Desert",
    year "1998,1999" (comma-separated list). Prefer these when you can infer the theme from your Lego knowledge
    (e.g. 90s pharaoh/desert sets are theme Adventurers; 2011 ones are theme "Pharaoh's Quest").
Results include piece counts: "main", "big" or "castle" usually means one of the larger sets in the group.
You have a small search budget, so make each search count, one at a time.
Return up to 5 candidates, best first, using ONLY sets the tool returned (copy set_id exactly),
each with a one-line reason. If nothing plausible was found, return an empty list.
"""


@dataclass
class Deps:
    db: Session
    seen: list[BricksetSet] = field(default_factory=list)  # everything the search tool returned


def _candidate(s: BricksetSet, reason: str = "") -> Candidate:
    return Candidate(
        set_id=s.set_id, number=s.full_number, name=s.name, year=s.year,
        theme=s.theme, image_url=s.thumbnail_url or s.image_url, reason=reason,
    )


def make_model() -> Model:
    from pydantic_ai.models.openai import OpenAIResponsesModel
    from pydantic_ai.providers.openai import OpenAIProvider

    s = get_settings()
    return OpenAIResponsesModel(s.agent_model, provider=OpenAIProvider(api_key=s.openai_api_key))


def build_agent(model: Model | str | None = None) -> Agent[Deps, Candidates]:
    s = get_settings()
    settings: dict = {"parallel_tool_calls": False}  # one search per step keeps the budget predictable
    if s.agent_reasoning_effort:
        settings["openai_reasoning_effort"] = s.agent_reasoning_effort
    agent: Agent[Deps, Candidates] = Agent(
        model or make_model(),
        output_type=Candidates,
        deps_type=Deps,
        instructions=INSTRUCTIONS,
        model_settings=settings,
    )

    @agent.tool
    def search_brickset(ctx: RunContext[Deps], query: str = "", theme: str = "", subtheme: str = "",
                        year: str = "") -> list[dict]:
        """Search Brickset by keywords and/or theme, subtheme, year filters (all optional, combine freely).
        Returns up to 30 sets with set_id, number, name, year, theme, subtheme, pieces."""
        try:
            sets = brickset.search(ctx.deps.db, query, page_size=30, theme=theme, subtheme=subtheme, year=year)
        except brickset.BricksetError as e:
            return [{"error": str(e)}]
        ctx.deps.seen.extend(x for x in sets if x not in ctx.deps.seen)
        return [
            {"set_id": x.set_id, "number": x.full_number, "name": x.name, "year": x.year,
             "theme": x.theme, "subtheme": x.subtheme, "pieces": x.pieces}
            for x in sets
        ]

    return agent


async def find_candidates(db: Session, description: str, model: Model | str | None = None) -> list[Candidate]:
    s = get_settings()
    agent = build_agent(model)
    limits = UsageLimits(tool_calls_limit=s.agent_max_steps, request_limit=s.agent_max_steps + 3)
    deps = Deps(db=db)
    try:
        result = await agent.run(description, deps=deps, usage_limits=limits)
    except UsageLimitExceeded:
        # Search budget spent before the model settled on an answer: show the best raw matches instead.
        return [_candidate(x, "search budget used up; unranked match") for x in deps.seen[:6]]
    # Drop anything the model invented: candidates must exist in our Brickset cache.
    out = []
    for c in result.output.candidates:
        row = db.get(BricksetSet, c.set_id)
        if row is not None:
            out.append(_candidate(row, c.reason))
    return out
