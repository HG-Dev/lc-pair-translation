# General troubleshooting
- Issue: Newer constraints (presumably) have left Claude obsessed with not reproducing copywrited material.
    - Solution: State in the prompt that the material we are translating is "new" to imply it is not copywrited

# Sliding window approach
For each chunk, we provide the entire chunk as one prompt, but specify that the LLM should translate it in sub-chunks, or portions.
When a sub-chunk is translated, translation of the next portion is invoked with "continue" or a symbol-- perhaps three hyphens?

- Possibility: The LLM might comment on what it's translating if it doesn't "get the commentary out of its system."
    - Solution: For the first reply, the LLM will reply with the number of portions it sees

# Consider for translation
> Recommend using a specific translation model, rather than a general LLM
* https://huggingface.co/facebook/seamless-m4t-v2-large
* https://dgallitelli95.medium.com/using-aya-101-in-amazon-sagemaker-4c1f30dfa5cd

> DeepL appears to have solved many of the problems I'm trying to tackle with more generalistic LLMs.
* https://github.com/DeepLcom/deepl-python/tree/main


# Consider for segmentation
As it turns out semantic chunking isn't all that useful for creating translation chunks.
It should work splendidly for finding similar lines to induce translation consistency!
However, individual sentences have no real need to say the similar things with each arrival of the period.
Instead of using semantics to aggregate chunks, instead it may be more appropriate to use similarity matrix calculations to "approve" the end of a chunk.
That is to say, if the paragraph following a potential chunk's conclusion is similar to the chunk's content, we may be sealing the chunk too early.

Current best strategy:
 1. Primary divider, like double paragraphs or scene header symbol
 2. For all chunks that are greater than N characters, chunk on secondary dividers recursively

https://huggingface.co/FacebookAI/xlm-roberta-base
    - For segmentation
https://fasttext.cc/docs/en/supervised-tutorial.html
    - For classification of elements
        - Could be useful for injecting formatting rules for irksome things like "scene setters" where JPN text lines up nouns without making a full sentence
https://github.com/axa-group/Parsr/blob/master/docs/api-guide.md
    - Self-hosting API for extracting structured data from documents

https://app.pluralsight.com/ilx/video-courses/5f9d528c-da76-4967-b132-8ed11a5e96ea/356494b5-9b50-4e97-92eb-0b5cf3b54eef/44a23c11-6054-490b-a8f7-7832a4d6f128
```python
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai.embeddings import OpenAIEmbeddings

# Ensure OPEN_API_KEY is set if using OpenAIEmbeddings

with open("file") as f:
    content = f.read()

text_splitter = SemanticChunker(OpenAIEmbeddings(),
    # Alt types: standard_deviation (~3), interquartile (~1.5)
    breakpoint_threshold_type="percentile",
    breakpoint_threshold_amount=95)

# docs = chunks?
docs = text_splitter.create_documents([content])
```

Currently, I have implemented my own version of Recursive Chunking-- or at least, the first step.
I may need to revise my chunking style to actually merge chunks where it gets too short.
ChunkDivider -- allow join if below threshold
Create my own RecursiveCharacterTextSplitter?
```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

with open("file") as f:
    content = f.read()

text_splitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=20)

docs = text_splitter.create_documents([content])
print(docs[0].page_content)
```

## Speaking of which, we need term segmentation
- Issue: Name lookup will fail when on the first name or last name is used in the source / translation
    - Solution: Create a tooling which allows an LLM to break apart terms -- DocumentAtomicTerms?

# Consider for example (translation memory) lookup
https://pypi.org/project/llama-index/

```python
from transformers import pipeline
segmenter = pipeline("text-segmentation", model="xlm-roberta-base")

def semantic_chunking(text):
    segments = segmenter(text)
    chunks = []
    for segment in segments:
        chunks.append(segment['text'])
    return chunks
```

### LangChain MultiVectorRetriever
 - creates multiple vectors per document
 - 

```python
loaders = [
    TextLoader("/content/drive/My Drive/Colab Notebooks/LangChain Techniques for Complex Datasets/mlk_speech.txt"),
    TextLoader("/content/drive/My Drive/Colab Notebooks/LangChain Techniques for Complex Datasets/steve_jobs_speech.txt"),
    TextLoader("/content/drive/My Drive/Colab Notebooks/LangChain Techniques for Complex Datasets/alexander_the_great_speech.txt")
]

docs = []
for loader in loaders:
    docs.extend(loader.load())
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000)
docs = text_splitter.split_documents(docs)

transcript_vectorstore = Chroma(
    collection_name="full_transcripts", embedding_function=OpenAIEmbeddings()
)

store = InMemoryByteStore()
id_key = "doc_id"

retriever = MultiVectorRetriever(
    vectorstore=transcript_vectorstore,
    byte_store=store, #This is optional
    id_key=id_key
)

import uuid

doc_ids = [str(uuid.uuid4()) for _ in docs]

child_text_splitter = RecursiveCharacterTextSplitter(chunk_size=250)
sub_docs = []

for i, doc in enumerate(docs):
    _id = doc_ids[i]
    _sub_docs = child_text_splitter.split_documents([doc])
    for _doc in _sub_docs:
        _doc.metadata[id_key] = _id
    sub_docs.extend(_sub_docs)

retriever.vectorstore.add_documents(sub_docs)
retriever.docstore.mset(list(zip(doc_ids, docs)))

retriever.vectorstore.similarity_search("calligraphy")[0].page_content
# Alternatively, the Retriever object can invoke the method for you-- asynchronously ainvoke also exists
retriever.invoke("calligraphy")[0].page_content
```
