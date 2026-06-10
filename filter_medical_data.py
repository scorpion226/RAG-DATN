import pandas as pd
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
import re
from tqdm import tqdm
import csv
import os

# 1. Tải và lọc metadata
print("Downloading metadata...")
meta_path = hf_hub_download(
    repo_id="th1nhng0/vietnamese-legal-documents",
    filename="legacy/metadata.parquet",
    repo_type="dataset"
)
print("Reading metadata...")
meta_df = pq.read_table(meta_path).to_pandas()
print(f"Columns: {meta_df.columns.tolist()}")
print(f"Metadata shape: {meta_df.shape}")

mask = meta_df['legal_sectors'].astype(str).str.contains("Health|Y tế", case=False, na=False)
medical_ids = meta_df[mask]['id'].tolist()
print(f"Số văn bản y tế: {len(medical_ids)}")
medical_ids_set = set(medical_ids)

# 2. Tải content theo batch, chỉ lấy y tế
print("\nDownloading content...")
content_path = hf_hub_download(
    repo_id="th1nhng0/vietnamese-legal-documents",
    filename="legacy/content.parquet",
    repo_type="dataset"
)

print("Reading content in batches...")
parquet_file = pq.ParquetFile(content_path)
batch_size = 50000
filtered_dfs = []
for batch in tqdm(parquet_file.iter_batches(batch_size=batch_size)):
    batch_df = batch.to_pandas()
    mask_batch = batch_df['id'].isin(medical_ids_set)
    filtered = batch_df[mask_batch]
    if not filtered.empty:
        filtered_dfs.append(filtered)
content_df = pd.concat(filtered_dfs, ignore_index=True) if filtered_dfs else pd.DataFrame()
print(f"Content y tế: {len(content_df)}")

# 3. Ghép metadata
merged = content_df.merge(meta_df, on='id', how='left')
print(f"Merged shape: {len(merged)}")

# 4. Làm sạch text
def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s\.\,\;\:\?\!]', ' ', text)
    return text.strip()

tqdm.pandas()
merged['clean_text'] = merged['content'].progress_apply(clean_text)
merged = merged[merged['clean_text'].str.len() > 100]
print(f"Sau làm sạch: {len(merged)}")

# 5. Chunk và ghi trực tiếp CSV (không lưu list)
csv_output = "medical_chunks_temp.csv"
fields = ['text', 'id', 'title', 'legal_type', 'legal_sectors', 'issuing_authority', 'issuance_date', 'effect_date', 'effect_status']

with open(csv_output, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for idx, row in tqdm(merged.iterrows(), total=len(merged)):
        text = row['clean_text']
        if not text:
            continue
        # Streaming chunking
        chunk_size = 500
        overlap = 50
        start = 0
        while start < len(text):
            end = start + chunk_size
            if end >= len(text):
                chunk = text[start:].strip()
                if chunk:
                    writer.writerow({
                        'text': chunk,
                        'id': row['id'],
                        'title': row['title'],
                        'legal_type': row['legal_type'],
                        'legal_sectors': row['legal_sectors'],
                        'issuing_authority': row['issuing_authority'],
                        'issuance_date': row['issuance_date'],
                        'effect_date': row['effect_date'],
                        'effect_status': row['effect_status']
                    })
                break
            # Cắt tại dấu cách
            split_pos = text.rfind(' ', start, end)
            if split_pos == -1:
                split_pos = end
            chunk = text[start:split_pos].strip()
            if chunk:
                writer.writerow({
                    'text': chunk,
                    'id': row['id'],
                    'title': row['title'],
                    'legal_type': row['legal_type'],
                    'legal_sectors': row['legal_sectors'],
                    'issuing_authority': row['issuing_authority'],
                    'issuance_date': row['issuance_date'],
                    'effect_date': row['effect_date'],
                    'effect_status': row['effect_status']
                })
            start = split_pos - overlap
            if start < 0:
                start = 0

print(f"Ghi xong CSV: {csv_output}")

# 6. Chuyển sang Parquet
print("Chuyển sang Parquet...")
chunks_df = pd.read_csv(csv_output, dtype=str)
output_parquet = "medical_legal_chunks.parquet"
chunks_df.to_parquet(output_parquet, index=False)
print(f"Đã lưu {len(chunks_df)} chunks vào {output_parquet}")

# Xóa file CSV tạm
os.remove(csv_output)