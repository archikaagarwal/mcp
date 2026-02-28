from mcp.server.fastmcp import FastMCP

mcp = FastMCP("DocumentMCP", log_level="ERROR")


docs = {
    "deposition.md": "This deposition covers the testimony of Angela Smith, P.E.",
    "report.pdf": "The report details the state of a 20m condenser tower.",
    "financials.docx": "These financials outline the project's budget and expenditures.",
    "outlook.pdf": "This document presents the projected future performance of the system.",
    "plan.md": "The plan outlines the steps for the project's implementation.",
    "spec.txt": "These specifications define the technical requirements for the equipment.",
}

@mcp.tool()
def read_doc(doc_id: str):
    """Return the contents of the requested document."""
    if doc_id not in docs:
        raise ValueError("Document not found")
    return docs[doc_id]


@mcp.tool()
def edit_doc(doc_id: str, old_text: str, new_text: str):
    """Replace the first occurrence of old_text in a document."""
    if doc_id not in docs:
        raise ValueError("Document not found")
    if old_text not in docs[doc_id]:
        raise ValueError("Original text not found in document")
    docs[doc_id] = docs[doc_id].replace(old_text, new_text, 1)
    return docs[doc_id]

@mcp.resource("docs://documents", mime_type="application/json")
def list_docs() -> list[str]:
    """Return a list of all available documents."""
    return list(docs.keys())

@mcp.resource("docs://documents/{doc_id}", mime_type="text/plain")
def fetch_doc(doc_id: str) -> str:
    """Expose a single document via the docs:// resource scheme."""
    if doc_id not in docs:
        raise ValueError("Document not found")
    return docs[doc_id]


@mcp.prompt(name="format", description="Rewrite a document in clean Markdown.")
def format_doc(doc_id: str):
    """Return a prompt that asks the model to rewrite a document in Markdown."""
    if doc_id not in docs:
        raise ValueError("Document not found")
    content = docs[doc_id]
    return [
        {
            "role": "user",
            "content": (
                f"Rewrite the document '{doc_id}' as polished Markdown. "
                "Use descriptive headings, bullet or numbered lists when useful, "
                "preserve all factual details, and avoid commentary about the rewrite.\n\n"
                f"Document contents:\n{content}"
            ),
        }
    ]
# TODO: Write a prompt to summarize a doc


if __name__ == "__main__":
    mcp.run(transport="stdio")
