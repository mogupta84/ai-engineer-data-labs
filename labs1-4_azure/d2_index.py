"""Lab 9, D2: cut the read files into pieces and put them in Azure AI Search (Lab 2, now in Azure). Trainer only:
the class shares one index, because the free search tier holds 3 indexes.

    python d2_index.py            build or rebuild the index freshcart-docs-lab9 from read/*.md

Each piece keeps the labels of its file (type, version, effective date, current or not), so a search can filter
on them. The index turns text into numbers itself (a vectorizer), so a search sends plain text.
"""
import hashlib        # a short, stable id for each piece
import time           # time the steps

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField, SearchField, SearchFieldDataType, VectorSearch, VectorSearchProfile,
    HnswAlgorithmConfiguration, AzureOpenAIVectorizer, AzureOpenAIVectorizerParameters, SemanticSearch,
    SemanticConfiguration, SemanticPrioritizedFields, SemanticField)
from langchain_text_splitters import RecursiveCharacterTextSplitter          # the same cutter as Labs 1 to 4
from openai import AzureOpenAI                                              # the embedding model, through Azure

from docs_common import READ, LABELS, INDEX, setting

EMBED = "text-embedding-3-small"                  # 1,536 numbers per piece


def pieces():
    """Every file cut into pieces of at most 500 characters, 50 shared with the next: Lab 1's settings."""
    cutter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    out = []
    for name, labels in LABELS.items():
        for text in cutter.split_text((READ / (name + ".md")).read_text(encoding="utf-8")):
            out.append({"id": hashlib.sha256(f"{name}|{text}".encode()).hexdigest()[:12], "file": name,
                        "content": text, **labels})
    return out


def index_definition(openai_endpoint, openai_key):
    return SearchIndex(
        name=INDEX,
        fields=[SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SimpleField(name="file", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SearchableField(name="content", type=SearchFieldDataType.String),
                SimpleField(name="doc_type", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="version", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="effective_date", type=SearchFieldDataType.String, filterable=True, sortable=True),
                SimpleField(name="current", type=SearchFieldDataType.Boolean, filterable=True),
                SearchField(name="vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                            searchable=True, vector_search_dimensions=1536, vector_search_profile_name="meaning")],
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
            profiles=[VectorSearchProfile(name="meaning", algorithm_configuration_name="hnsw", vectorizer_name="embed")],
            vectorizers=[AzureOpenAIVectorizer(vectorizer_name="embed", parameters=AzureOpenAIVectorizerParameters(
                resource_url=openai_endpoint, deployment_name=EMBED, model_name=EMBED, api_key=openai_key))]),
        semantic_search=SemanticSearch(configurations=[SemanticConfiguration(
            name="rerank", prioritized_fields=SemanticPrioritizedFields(content_fields=[SemanticField(field_name="content")]))]))


def main():
    endpoint, key = setting("SEARCH_ENDPOINT"), setting("SEARCH_ADMIN_KEY")
    openai_endpoint, openai_key = setting("OPENAI_ENDPOINT"), setting("OPENAI_KEY")
    items = pieces()
    print(f"{len(items)} pieces from {len(LABELS)} files")
    start = time.time()
    embedder = AzureOpenAI(azure_endpoint=openai_endpoint, api_key=openai_key, api_version="2024-10-21")
    vectors = embedder.embeddings.create(model=EMBED, input=[p["content"] for p in items]).data
    for item, v in zip(items, vectors):
        item["vector"] = v.embedding
    print(f"turned into numbers in {time.time() - start:.1f}s, {len(vectors[0].embedding)} numbers each")
    admin = SearchIndexClient(endpoint, AzureKeyCredential(key))
    if INDEX in admin.list_index_names():
        admin.delete_index(INDEX)                     # a rebuild starts clean
    admin.create_index(index_definition(openai_endpoint, openai_key))
    result = SearchClient(endpoint, INDEX, AzureKeyCredential(key)).upload_documents(items)
    print(f"index {INDEX}: {sum(r.succeeded for r in result)} of {len(items)} pieces stored")
    for name in LABELS:
        print(f"  {name:38} {sum(p['file'] == name for p in items)} pieces")


main()
