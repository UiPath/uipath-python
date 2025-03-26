# Retrieval chain and Context Grounding vectorstore example

Use the UiPath Context Grounding vectorstore to retrieve relevant documents for a query, and integrate this into a Langchain retrieval chain to answer that query.

## Debug

1. Clone the repository:
```bash
git clone
cd samples\uipath_retrieval_chain
```

2. Install dependencies:
```bash
pip install uv
uv venv -p 3.11 .venv
.venv\Scripts\activate
uv sync
```

3. Create a `.env` file in the project root using the template `.env.example`.

### Run

To check the vectorstore and retrieval chain outputs, you should run:

```bash
python main.py --index_name $INDEX_NAME --query $QUERY --k $NUM_RESULTS
```

### Input Format

The CLI parameters for the sample script are follows:
$INDEX_NAME -> The name of the index to use (string)
#QUERY -> The query for which documents will be retrieved (string)
$NUM_RESULTS -> The number of documents to retrieve


### Output Format

The script first outputs the result of retrieving the most relevant K documents, first with the distance score, then with the relevance score.
Finally, it outputs the result of running the retrieval chain on the query, mentioning the sources alongside the answer.
```
