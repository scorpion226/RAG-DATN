"""
Convert medical_chunks_temp.csv (~12.7GB) -> Parquet theo LUỒNG (streaming).
Chạy được trên RAM thấp (<=16GB) vì chỉ giữ 1 khối nhỏ trong bộ nhớ tại mỗi thời điểm.

Cách dùng:
    python csv_to_parquet_streaming.py
"""
import sys
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm
import os

# Windows: ép stdout/stderr sang UTF-8 để in được tiếng Việt (tránh lỗi cp1252)
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

CSV_IN = "medical_chunks_temp.csv"
PARQUET_OUT = "medical_legal_chunks.parquet"
CHUNK_ROWS = 50_000           # số dòng/khối — giảm xuống nếu vẫn thiếu RAM
DELETE_CSV_AFTER = False       # đặt True nếu muốn tự xóa CSV sau khi convert xong

FIELDS = ['text', 'id', 'title', 'legal_type', 'legal_sectors',
          'issuing_authority', 'issuance_date', 'effect_date', 'effect_status']


def main():
    if not os.path.exists(CSV_IN):
        raise FileNotFoundError(f"Không tìm thấy {CSV_IN}")

    size_gb = os.path.getsize(CSV_IN) / 1e9
    print(f"Đọc {CSV_IN} ({size_gb:.1f} GB) theo khối {CHUNK_ROWS:,} dòng...")

    writer = None
    total_rows = 0
    reader = pd.read_csv(
        CSV_IN,
        dtype=str,              # giữ mọi cột là string, tránh suy luận kiểu tốn RAM
        chunksize=CHUNK_ROWS,
        keep_default_na=False,  # không biến chuỗi rỗng/"NA" thành NaN
        on_bad_lines='warn',    # bỏ qua + cảnh báo dòng lỗi thay vì crash
        engine='c',
    )

    for chunk in tqdm(reader, unit='khối'):
        # Đảm bảo đủ cột, đúng thứ tự
        for col in FIELDS:
            if col not in chunk.columns:
                chunk[col] = ""
        chunk = chunk[FIELDS]

        table = pa.Table.from_pandas(chunk, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(PARQUET_OUT, table.schema, compression='snappy')
        writer.write_table(table)
        total_rows += len(chunk)

    if writer is not None:
        writer.close()

    print(f"\n✅ Đã ghi {total_rows:,} chunks vào {PARQUET_OUT}")
    out_gb = os.path.getsize(PARQUET_OUT) / 1e9
    print(f"   Kích thước Parquet: {out_gb:.2f} GB (nén snappy)")

    if DELETE_CSV_AFTER:
        os.remove(CSV_IN)
        print(f"   Đã xóa file tạm {CSV_IN}")


if __name__ == "__main__":
    main()
