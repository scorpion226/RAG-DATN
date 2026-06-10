# AI Coding Instructions for Vietnamese Legal Documents Medical Data Filtering

## Project Overview

This project filters and processes medical-sector Vietnamese legal documents (518,255+ documents) from a Hugging Face dataset. The key workflow:
1. Load metadata and content from `vietnamese-legal-documents` dataset (two separate configs)
2. Filter by medical sector using category columns (`nganh` or `linh_vuc`)
3. Convert HTML content to clean text using BeautifulSoup
4. Chunk text using LangChain's RecursiveCharacterTextSplitter
5. Output processed chunks to Parquet for downstream ML tasks

## Data Architecture

**Two-config dataset design** (see [vietnamese-legal-documents/README.md](../vietnamese-legal-documents/README.md)):
- `metadata` config: 518,255 rows, 9 columns (id, title, legal_type, issuance_date, etc.) - use for fast filtering
- `content` config: 518,255 rows with full document text - join on `id` column

**Key filtering logic**: Medical documents identified via:
- Primary: `nganh == "Y tế"` (sector field)
- Fallback: `linh_vuc.contains("Y tế")` (domain field)
- Last resort: Check for English "health" in lowercase

## Critical Patterns

### HTML to Text Conversion
```python
def clean_html_to_text(html):
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup(["script", "style"]):
        script.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
```
Always strip script/style tags and normalize whitespace with single space (not newlines for chunks).

### Text Chunking Strategy
Use `RecursiveCharacterTextSplitter` with legal-document-specific separators:
```python
separators=["\n\n", "\n", "Điều", "Thông tư", "Nghị định", ". ", " "]
```
Preserve Vietnamese legal structure keywords (Điều=Article, Thông tư=Circular, Nghị định=Decree).

### Metadata Preservation
Each chunk carries original document metadata (id, title, legal_type, issuing_authority, effective_status) for traceability and filtering in downstream tasks.

## Workflow & Commands

**Load dataset**: Uses Hugging Face `datasets` library - handles caching automatically. For large content loads, use split approach to manage memory.

**Output format**: Parquet (medical_legal_chunks.parquet) with columns: text, id, title, loai_van_ban, nganh, linh_vuc, co_quan_ban_hanh, ngay_ban_hanh, tinh_trang_hieu_luc

**Progress tracking**: Uses `tqdm.pandas()` for verbose iteration - essential for monitoring long HTML processing runs.

## Dependencies & Imports

Key packages:
- `pandas`: DataFrame manipulation
- `datasets`: Hugging Face dataset loading
- `beautifulsoup4`: HTML parsing
- `langchain`: Text chunking (RecursiveCharacterTextSplitter)
- `tqdm`: Progress bars

## Common Gotchas

1. **Dataset name mismatch**: Code loads from `"th1nhng0/vietnamese-legal-documents"` not just `"vietnamese-legal-documents"` - verify username in load_dataset calls
2. **Missing categories**: Some documents may lack medical classification - fallback filtering chain prevents silent data loss
3. **Empty chunks**: Filter after cleaning (`merged_df['clean_text'].str.len() > 100`) - avoid storing empty documents
4. **Memory usage**: Content config (~3.6 GB) loads entire dataset into memory - consider batch processing for production
