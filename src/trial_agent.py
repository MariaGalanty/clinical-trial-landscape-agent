"""Search agent (LangGraph): runs only on trials the summariser left not_found.
The model chooses the tools; code enforces the limit and checks the citations."""

from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

import pubmed
import web
from llm_log import logged_call
from schemas import Source, SummariserOutput, TrialSummary
from summarise import (
    INSTRUCTIONS,
    MODEL,
    REASONING_EFFORT,
    build_sources,
    check_citations,
    registry_part,
)

MAX_TOOL_CALLS = 5
PAGE_CHARS = 6000
HANDLER = f"agent_v1_{REASONING_EFFORT}"

AGENT_INSTRUCTIONS = (
    INSTRUCTIONS
    + """
The sources below did not answer what happened to this trial. Use the tools to
find more. You have at most 5 tool calls.
- Search results show only titles and snippets. Fetch a page or abstract before
  using it: only fetched sources can be cited, by their URL or PMID label.
- Start from the trial's identifiers: NCT number, drug name, acronym, ALS.
  Press releases often say "discontinued", "halted" or "did not meet its
  primary endpoint" instead of "terminated".
- Stop when the fetched sources answer the question, or when more searching is
  unlikely to help. Returning no claims is a valid answer.
"""
)


# ---- Tools. Each returns (text for the model, Source if something citable was fetched) ----


@tool(response_format="content_and_artifact")
def web_search(query: str) -> tuple[str, None]:
    """Search the web. Returns URLs, titles and short snippets."""
    results = web.web_search(query)
    text = "\n".join(
        f"- {r['url']} | {r['title']}\n  {r['content'][:300]}" for r in results
    )
    return text or "No results.", None


@tool(response_format="content_and_artifact")
def fetch_page(url: str) -> tuple[str, Source | None]:
    """Read a web page found with web_search. It can then be cited by its URL."""
    text = web.fetch_page(url)[:PAGE_CHARS]
    if not text:
        return "Could not read this page.", None
    return f"[{url}]\n{text}", Source(
        kind="web", reference=url, title=url, role="trial_info"
    )


@tool(response_format="content_and_artifact")
def search_pubmed(query: str) -> tuple[str, None]:
    """Search PubMed. Returns PMIDs and titles."""
    pmids = pubmed.search_pubmed(query)
    text = "\n".join(
        f"- {p} | {pubmed.fetch_abstract_cached(p)['title']}" for p in pmids
    )
    return text or "No results.", None


@tool(response_format="content_and_artifact")
def fetch_abstract(pmid: str) -> tuple[str, Source]:
    """Read a PubMed abstract found with search_pubmed. It can then be cited by its PMID."""
    a = pubmed.fetch_abstract_cached(pmid)
    source = Source(kind="pubmed", reference=pmid, title=a["title"], role="trial_info")
    return f"[{pmid}] {a['title']}\n{a['abstract']}", source


TOOLS = [web_search, fetch_page, search_pubmed, fetch_abstract]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}

llm = ChatOpenAI(
    model=MODEL, reasoning={"effort": REASONING_EFFORT}, use_responses_api=True
)
llm_with_tools = llm.bind_tools(TOOLS, parallel_tool_calls=False)
llm_answer = llm.with_structured_output(
    SummariserOutput, method="json_schema", include_raw=True
)


# ---- State: what flows between the nodes ----


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # add_messages: new messages are appended
    fetched: list[Source]  # the only new sources that may be cited
    n_calls: int
    nct_id: str
    run_id: str
    output: SummariserOutput | None


def _log(state: AgentState, call):
    return logged_call(
        call,
        provider="langchain",
        model=MODEL,
        handler=HANDLER,
        nct_id=state["nct_id"],
        run_id=state["run_id"],
    )


# ---- Nodes ----


def agent_node(state: AgentState) -> dict:
    """The model decides: call a tool, or stop. Past the limit it gets no tools."""
    model = llm_with_tools if state["n_calls"] < MAX_TOOL_CALLS else llm
    message = _log(state, lambda: model.invoke(state["messages"]))
    return {"messages": [message]}


def tools_node(state: AgentState) -> dict:
    """Run the requested tools and record what was fetched."""
    new_messages, new_sources = [], []
    for call in state["messages"][-1].tool_calls:
        print(
            f"  tool {state['n_calls'] + len(new_messages) + 1}: {call['name']}({call['args']})"
        )
        try:
            result = TOOLS_BY_NAME[call["name"]].invoke(
                call
            )  # -> ToolMessage, with .artifact
        except Exception as e:  # a failing tool must not kill the run
            result = ToolMessage(content=f"Tool error: {e}", tool_call_id=call["id"])
        new_messages.append(result)
        if getattr(result, "artifact", None):
            new_sources.append(result.artifact)
    return {
        "messages": new_messages,
        "fetched": state["fetched"] + new_sources,
        "n_calls": state["n_calls"] + len(new_messages),
    }


def answer_node(state: AgentState) -> dict:
    """Final answer in the summariser's schema."""
    prompt = state["messages"] + [HumanMessage("Now give your final answer.")]
    result = _log(state, lambda: llm_answer.invoke(prompt))
    return {"output": result["parsed"]}


def route(state: AgentState) -> str:
    return "tools" if state["messages"][-1].tool_calls else "answer"


graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("tools", tools_node)
graph.add_node("answer", answer_node)
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", route, ["tools", "answer"])
graph.add_edge("tools", "agent")
graph.add_edge("answer", END)
app = graph.compile()


def run_agent(row: dict, abstracts: list[dict], run_id: str) -> TrialSummary:
    text, sources = build_sources(row, abstracts)
    final = app.invoke(
        {
            "messages": [
                SystemMessage(AGENT_INSTRUCTIONS),
                HumanMessage(f"Trial: {row['nct_id']}\n\n{text}"),
            ],
            "fetched": [],
            "n_calls": 0,
            "output": None,
            "nct_id": row["nct_id"],
            "run_id": run_id,
        }
    )
    base = registry_part(row, run_id)
    all_sources = sources + final["fetched"]
    output = final["output"]
    if output is None:
        return TrialSummary(
            **base,
            sources_fetched=all_sources,
            handler=HANDLER,
            n_tool_calls=final["n_calls"],
        )
    claims, status = check_citations(output, all_sources)
    return TrialSummary(
        **base,
        stop_category=output.stop_category,
        claims=claims,
        sources_fetched=all_sources,
        status=status,
        handler=HANDLER,
        n_tool_calls=final["n_calls"],
    )
