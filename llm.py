"""
llm.py — Tầng SINH câu trả lời (Generation) của RAG, có thể thay thế.

Chế độ (đặt qua biến môi trường LLM_MODE):
  - "mock"   : trả lời trích xuất nhanh từ ngữ cảnh (KHÔNG cần model) -> để test pipeline/web.
  - "gguf"   : PhoGPT-4B-Chat lượng tử hóa (Q4_K_M, 2.36GB) qua llama.cpp -> KHUYẾN NGHỊ cho CPU 16GB.
  - "phogpt" : PhoGPT-4B-Chat fp32 qua transformers (cần ~16GB RAM, rất chậm trên CPU).

Prompt RAG yêu cầu LLM: chỉ dựa vào ngữ cảnh, trích dẫn số hiệu VB, nói rõ khi không có thông tin
-> giảm bịa đặt (hallucination), một mục tiêu chính của kiến trúc RAG.
"""
import os

SYSTEM_INSTRUCT = (
    "Bạn là trợ lý tra cứu văn bản pháp luật ngành y tế Việt Nam. "
    "CHỈ dựa vào các văn bản được cung cấp để trả lời. "
    "Luôn trích dẫn số hiệu văn bản liên quan. "
    "Nếu thông tin không có trong văn bản, hãy nói rõ là không tìm thấy."
)


def build_prompt(question, context):
    return (
        f"### Câu hỏi:\n{SYSTEM_INSTRUCT}\n\n"
        f"=== VĂN BẢN THAM KHẢO ===\n{context}\n\n"
        f"=== CÂU HỎI ===\n{question}\n\n"
        f"### Trả lời:\n"
    )


class MockLLM:
    """Trả lời đơn giản: tóm nguồn + đoạn liên quan nhất. Dùng để test khi chưa có PhoGPT."""
    def generate(self, question, context, hits=None):
        if not hits:
            return "Không tìm thấy văn bản liên quan trong cơ sở dữ liệu."
        top = hits[0]["metadata"]
        lines = [f"(Chế độ MOCK — chưa dùng LLM thật) Theo {top.get('document_number','văn bản')} "
                 f"\"{top.get('title','')}\", nội dung liên quan nhất:",
                 "", hits[0]["text"][:500].strip(), "",
                 "Nguồn tham khảo:"]
        seen = set()
        for h in hits:
            dn = h["metadata"].get("document_number", "?")
            if dn not in seen:
                seen.add(dn)
                lines.append(f"  - {dn}: {h['metadata'].get('title','')}")
        return "\n".join(lines)


class PhoGPTLLM:
    """vinai/PhoGPT-4B-Chat qua transformers. CPU 16GB nên dùng torch_dtype thấp / quantize."""
    def __init__(self, model_name="vinai/PhoGPT-4B-Chat", max_new_tokens=512):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig
        self.torch = torch
        self.max_new_tokens = max_new_tokens
        cfg = AutoConfig.from_pretrained(model_name, trust_remote_code=True)
        cfg.init_device = "cpu"
        self.tok = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, config=cfg, torch_dtype=torch.float32, trust_remote_code=True)
        self.model.eval()

    def generate(self, question, context, hits=None):
        prompt = build_prompt(question, context)
        ids = self.tok(prompt, return_tensors="pt")
        with self.torch.no_grad():
            out = self.model.generate(
                inputs=ids["input_ids"], attention_mask=ids["attention_mask"],
                max_new_tokens=self.max_new_tokens, do_sample=False,
                temperature=1.0, top_p=1.0,
                pad_token_id=self.tok.eos_token_id)
        text = self.tok.batch_decode(out, skip_special_tokens=True)[0]
        return text.split("### Trả lời:")[-1].strip()


class PhoGPTGGUF:
    """PhoGPT-4B-Chat GGUF (lượng tử hóa) qua llama.cpp — nhẹ & nhanh cho CPU."""
    def __init__(self, repo="vinai/PhoGPT-4B-Chat-gguf",
                 fname="PhoGPT-4B-Chat-Q4_K_M.gguf", n_ctx=4096, max_new_tokens=512):
        from llama_cpp import Llama
        # Ưu tiên file local trong models/ (tải bằng download_gguf.py); nếu không có thì lấy từ HF.
        local = os.path.join("models", fname)
        if os.path.exists(local):
            model_path = local
        else:
            from huggingface_hub import hf_hub_download
            model_path = hf_hub_download(repo_id=repo, filename=fname)
        n_threads = os.cpu_count() or 4
        self.max_new_tokens = max_new_tokens
        self.llm = Llama(model_path=model_path, n_ctx=n_ctx,
                         n_threads=n_threads, verbose=False)

    def generate(self, question, context, hits=None):
        prompt = build_prompt(question, context)
        out = self.llm(prompt, max_tokens=self.max_new_tokens,
                       temperature=0.1, top_p=0.95, repeat_penalty=1.1,
                       stop=["### Câu hỏi:", "</s>", "<|endoftext|>"])
        return out["choices"][0]["text"].strip()


def get_llm():
    mode = os.environ.get("LLM_MODE", "mock").lower()
    if mode == "gguf":
        return PhoGPTGGUF()
    if mode == "phogpt":
        return PhoGPTLLM()
    return MockLLM()
