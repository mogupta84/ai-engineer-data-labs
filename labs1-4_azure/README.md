# Labs 1 to 4 in Azure: your documents

Handbook: Labs1-4_in_Azure.pdf. D1 to D5 are done in the browser, in your own container and
index; from this folder they need only files/ (D1 and D2) and new_file/ (D5). The scripts below are the
optional part: the same four steps in
code, scored as in Labs 3 and 4. For them, open this folder in VS Code, make its Python environment from
requirements.txt, and put the four settings your trainer gives you in a .env file here.

d1_read.py     D1: Document Intelligence reads the 7 FreshCart files (signed in as you, no key)
d2_index.py    D2, trainer only: the pieces, with labels, into Azure AI Search
d3_search.py   D3: meaning, keyword, both, the reranker and a filter, scored with nDCG@10
d4_answer.py   D4: an agent that answers from the index, cites its sources, and refuses
docs_common.py the settings, the sign-in, the files and the scoring

files/       D2: the 7 FreshCart files to upload into your own container
new_file/festive_season_addendum_2024.pdf   D5: the new document to upload into your container
