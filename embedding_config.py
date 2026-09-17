"""
Shared embedding settings.

Every part of Lumen that turns text into a vector must use the same model.
Catalog vectors and search-query vectors are compared directly, so if two
files disagree on the model the comparison is meaningless (and a change in
vector length makes it fail outright). Keeping the name here means there is
only one line to change when Google retires a model, which they do:
text-embedding-004 was withdrawn and returned 404 for every call.

Newer alternative, same vector length: "gemini-embedding-2".
"""

# Model used for both catalog assets and search queries.
EMBEDDING_MODEL = "gemini-embedding-001"

# Gemini embeds text differently depending on the job it has to do.
# Stored catalog entries are documents; what the user types is a query.
# Using the matching type on each side gives noticeably better ranking.
TASK_TYPE_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_TYPE_QUERY = "RETRIEVAL_QUERY"
