"""
Web tool: read one documentation page, safely.

    read_web_page   fetch a page and return a short text excerpt

Every address goes through the safe fetcher (app/integrations/safe_fetch.py):
https only, public addresses only (checked on the resolved IP, on every
redirect), time, size and content-type limits. A refused address is recorded
as failed evidence with the reason, so nothing disappears silently.

The page text is DATA for the agent to read. If it contains instructions,
they are part of the material, not orders (each agent's prompt says so).
"""

from pydantic import BaseModel, Field

from app.evidence.builders import build_doc_item
from app.graph import events
from app.integrations.safe_fetch import FetchRefused
from app.models.common import utc_now
from app.tools.base import Tool, ToolContext, ToolResult, refuse, reply

EXCERPT_FOR_MODEL = 1_200


class ReadWebPageArgs(BaseModel):
    url: str = Field(description="An https address of a documentation page.")


async def read_web_page(args: ReadWebPageArgs, ctx: ToolContext) -> ToolResult:
    url = args.url.strip()
    # LEARNING NOTE: upgrade, do not refuse (found live)
    #   A scout asked for an "http://" page of an official data source and it
    #   was refused, so the source was lost. Almost every site serves the same
    #   page over https, so the address is upgraded. The fetcher still accepts
    #   only https, so nothing is ever read unencrypted.
    if url.lower().startswith("http://"):
        url = "https://" + url[len("http://"):]
    if not ctx.budget.take("web"):
        return refuse("the run's page-reading budget is used up")
    source_type = "user_url" if url in ctx.board.user_urls else "linked_doc"
    page, refused = None, None
    try:
        page = await ctx.integrations.fetcher.fetch(url)
    except FetchRefused as error:
        refused = error
    item = build_doc_item(url, source_type, page=page, refused=refused, retrieved_at=utc_now(), mode=ctx.mode)
    ctx.publish(item)
    if refused is not None:
        ctx.notes.append(f"{url}: {refused.message}")
        ctx.emit(events.activity(f"Docs: {url} was not read — {refused.message}"))
        return refuse(refused.message)
    ctx.emit(events.activity(f"Docs: read {url}"))
    return reply({"url": page.url, "evidence_id": item.id, "excerpt": (item.excerpt or "")[:EXCERPT_FOR_MODEL],
                  "truncated": page.truncated})


READ_WEB_PAGE = Tool(
    name="read_web_page",
    description="Read a documentation web page and get a short text excerpt. http addresses are read over https.",
    args=ReadWebPageArgs, run=read_web_page,
)
