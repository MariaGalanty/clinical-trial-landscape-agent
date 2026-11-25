"""Search agent (LangGraph): runs only on trials the summariser left not_found.
Code runs the web search (fixed query per trial status); the model chooses which
result pages to read and when to stop. Code enforces the limit and checks the citations."""

from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

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
PAGE_CHARS = 20000
HANDLER = f"trial_agent_v5_{REASONING_EFFORT}"  # v5: URL gate, only bad claims dropped

AGENT_INSTRUCTIONS = (
    INSTRUCTIONS
    + """
    The sources below did not answer what happened to this trial. Web search results
    for the trial are listed at the end. You can read pages with fetch_page; you have
    at most 5 fetches.

    What you are looking for, depending on [registry:overall_status]:
    - COMPLETED: the results. Did the trial meet its primary endpoint? Key efficacy
    and safety findings. Was the drug developed further or dropped?
    - TERMINATED, WITHDRAWN, SUSPENDED: why the trial stopped (safety, lack of
    efficacy, business decision, slow enrolment ...), and any results before it
    stopped.
    - RECRUITING and other ongoing statuses: progress, e.g. enrolment, interim
    results or expected dates.
    - UNKNOWN: whether it finished or stopped, and any results.

    How to search the pages:
    - Fetch the pages most likely to answer this: news articles, company press
    releases, conference abstracts. Skip pages that only list the trial.
    - Use a fetched page only if it is about THIS trial: it names the NCT number,
    or its drug, disease, phase and design match the registry record.
    - Stop when the fetched pages answer the question, or when no remaining result
    looks useful. Returning no claims is a valid answer.

    How to report:
    - Report what each usable page says, with its context: the date, whether the
    data are preliminary or final, and how many patients they cover (e.g. "In
    January 2023, preliminary data from 8 patients showed ...").
    - If usable pages disagree, report both claims, each with its context, so the
    reader can see what changed (e.g. preliminary results vs. final results).
    - Preliminary, interim and secondary-endpoint results count as outcomes, as
    long as you say what they are.
    - Cite a page by its exact URL, copied from its [label]. Only fetched pages
    can be cited. Search snippets are not evidence: do not cite them, and do not
    drop a finding from a fetched page because a snippet says something else.
"""
)


# ---- Web search: run by code, not by the model. Query = <NCT> ALS <state> ----

STOPPED = {"TERMINATED", "WITHDRAWN", "SUSPENDED"}
ONGOING = {
    "RECRUITING",
    "ACTIVE_NOT_RECRUITING",
    "ENROLLING_BY_INVITATION",
    "NOT_YET_RECRUITING",
}


def web_queries(row: dict) -> list[str]:
    """One query per trial; UNKNOWN status gets both 'results' and 'stopped'."""
    status = row["overall_status"]
    if status in STOPPED:
        states = ["stopped"]
    elif status == "COMPLETED":
        states = ["results"]
    elif status in ONGOING:
        states = ["recruiting"]
    else:  # UNKNOWN, or a status we have not seen
        states = ["results", "stopped"]
    return [f"{row['nct_id']} ALS {s}" for s in states]


def search_results_text(row: dict) -> str:
    """Search results as text for the model (URL, title, short snippet) + their URLs,
    the only pages the agent may fetch."""
    lines, urls = [], []
    for query in web_queries(row):
        print(f"  web search: {query}")
        lines.append(f"Web search: {query}")
        for r in web.web_search(query):
            lines.append(f"- {r['url']} | {r['title']}\n  {r['content'][:300]}")
            urls.append(r["url"])
    return "\n".join(lines), urls


# ---- Tools. Each returns (text for the model, Source if something citable was fetched) ----


@tool(response_format="content_and_artifact")
def fetch_page(url: str) -> tuple[str, Source | None]:
    """Read a web page from the search results. It can then be cited by its URL."""
    text = web.fetch_page(url)[:PAGE_CHARS]
    if not text:
        return "Could not read this page.", None
    return f"[{url}]\n{text}", Source(
        kind="web", reference=url, title=url, role="trial_info"
    )


TOOLS = [fetch_page]
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
    allowed_urls: list[str]  # URLs from the search results: the only pages that may be fetched


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
    """The model decides: fetch a page, or stop."""
    message = _log(state, lambda: llm_with_tools.invoke(state["messages"]))
    return {"messages": [message]}


def after_tools(state: AgentState) -> str:
    """Limit reached -> answer now, without asking the model again."""
    return "answer" if state["n_calls"] >= MAX_TOOL_CALLS else "agent"


def tools_node(state: AgentState) -> dict:
    """Run the requested tools and record what was fetched.
    Only URLs from the search results may be fetched (checked here, in code)."""
    new_messages, new_sources = [], []
    for call in state["messages"][-1].tool_calls:
        print(
            f"  tool {state['n_calls'] + len(new_messages) + 1}: {call['name']}({call['args']})"
        )
        url = call["args"].get("url", "")
        if call["name"] == "fetch_page" and url not in state["allowed_urls"]:
            print("    refused: not in the search results")
            result = ToolMessage(
                content="Not allowed: only URLs from the search results can be fetched.",
                tool_call_id=call["id"],
            )
        else:
            try:
                result = TOOLS_BY_NAME[call["name"]].invoke(
                    call
                )  # -> ToolMessage, with .artifact
            except Exception as e:  # a failing tool must not kill the run
                result = ToolMessage(
                    content=f"Tool error: {e}", tool_call_id=call["id"]
                )
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
graph.add_conditional_edges("tools", after_tools, ["agent", "answer"])
graph.add_edge("answer", END)
app = graph.compile()


def run_agent(row: dict, abstracts: list[dict], run_id: str) -> TrialSummary:
    text, sources = build_sources(row, abstracts)
    results_text, urls = search_results_text(row)
    final = app.invoke(
        {
            "messages": [
                SystemMessage(AGENT_INSTRUCTIONS),
                HumanMessage(
                    f"Trial: {row['nct_id']}\n\n{text}"
                    f"\n\nWeb search results:\n{results_text}"
                ),
            ],
            "fetched": [],
            "n_calls": 0,
            "output": None,
            "nct_id": row["nct_id"],
            "run_id": run_id,
            "allowed_urls": urls,
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
    claims, status, dropped = check_citations(output, all_sources)
    return TrialSummary(
        **base,
        stop_category=output.stop_category,
        claims=claims,
        sources_fetched=all_sources,
        status=status,
        dropped_claims=dropped,
        handler=HANDLER,
        n_tool_calls=final["n_calls"],
    )
