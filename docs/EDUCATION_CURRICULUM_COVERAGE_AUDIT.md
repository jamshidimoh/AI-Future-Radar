# Education Curriculum Coverage Audit

## هدف
این سند نقشهٔ یکپارچهٔ Curriculum را ثبت می‌کند تا گسترش Education به‌صورت وصله‌ای انجام نشود.

## اصل معماری
مسیر آموزشی باید از مبانی به مدل‌ها، از مدل‌ها به سامانه‌ها، از سامانه‌ها به مهندسی و ارزیابی، و سپس به ایمنی/حاکمیت و حوزه‌های نوظهور حرکت کند. هر مفهوم باید دقیقاً در یک حوزهٔ اصلی جایگاه داشته باشد و در صورت نیاز به پیش‌نیازها ارجاع دهد.

## لایه‌های Curriculum
1. Fundamentals: AI/ML، داده، آموزش و inference، neural networks
2. Representation & Models: tokens، embeddings، attention، transformers، foundation models، LLM
3. Generative AI: prompting، in-context learning، post-training، alignment، RAG، multimodal generation
4. Agentic Systems: agents، planning، tool use، protocols، context، memory، evaluation، verification
5. Engineering: inference optimization، quantization، PEFT، MLOps، observability، deployment، testing
6. Data: data engineering، quality، synthetic data، augmentation، retrieval، vector systems
7. Trust & Security: hallucination، grounding، robustness، adversarial ML، AI security، privacy
8. Safety & Governance: responsible AI، risk management، incidents، governance، policy، standards
9. Infrastructure: compute، accelerators، networking، serving، distributed training
10. Embodied & Scientific AI: robotics، embodied AI، AI for science، biomedicine، digital twins
11. Open Ecosystems: open-weight، open-source distinctions، model ecosystems، standards/protocols
12. Frontier & Emerging: quantum AI، world models، advanced agent architectures، emerging terminology

## وضعیت فعلی بر اساس Curriculum موجود
| حوزه | وضعیت | اقدام لازم |
|---|---|---|
| AI fundamentals | Covered | عمق و به‌روزرسانی دوره‌ای |
| Machine learning | Covered | افزودن validation، generalization، leakage، causal limitations |
| Deep learning | Partial | architecture families، normalization، optimization و scaling تکمیل شود |
| Generative AI | Partial | معماری‌های تولیدی، decoding، post-training و current model patterns تکمیل شود |
| LLM | Partial | tokenizer، context، inference، training lifecycle و evaluation تکمیل شود |
| Multimodal AI | Partial | vision-language، audio، video و multimodal evaluation تکمیل شود |
| Retrieval & RAG | Partial | retrieval pipeline، reranking، citation/grounding و failure modes تکمیل شود |
| Agents & agentic systems | Partial | planning، state، tools، verification، memory، orchestration و autonomy تکمیل شود |
| Tool use & protocols | Partial | function/tool calling، MCP، protocol boundaries و security تکمیل شود |
| Memory & context | Partial | context engineering، compaction، persistence و retrieval memory تکمیل شود |
| Evaluation & benchmarks | Partial | model/agent eval، task design، contamination، robustness و production eval تکمیل شود |
| Alignment & post-training | Partial | SFT، preference optimization، RLHF/DPO و safety post-training تکمیل شود |
| Inference & optimization | Gap | serving، batching، KV cache، quantization، speculative decoding و cost/latency تکمیل شود |
| Data & data engineering | Gap | pipelines، quality، lineage، curation، synthetic data و governance تکمیل شود |
| AI security & robustness | Gap | prompt injection، tool abuse، adversarial robustness، data poisoning و model supply-chain تکمیل شود |
| Safety & responsible AI | Partial | risk taxonomy، assurance، red teaming و deployment controls تکمیل شود |
| Governance & policy | Partial | standards، regulation، incidents، conformity/assurance و lifecycle governance تکمیل شود |
| AI infrastructure & compute | Partial | accelerator taxonomy، distributed training، serving، memory/interconnect و energy تکمیل شود |
| Robotics & embodied AI | Partial | perception-action loops، simulation، policy learning و deployment constraints تکمیل شود |
| AI for science & biomedicine | Gap | scientific discovery، lab automation، protein/drug workflows و validation تکمیل شود |
| Quantum AI | Partial | quantum basics، QML limits، hybrid algorithms و evidence standards تکمیل شود |
| Open models & ecosystems | Partial | licensing، open-weight vs open-source، reproducibility و model supply chain تکمیل شود |
| AI engineering & MLOps | Partial | CI/CD for models، monitoring، rollback، evaluation gates و reproducibility تکمیل شود |
| Human-AI interaction | Gap | interaction patterns، calibration، oversight، usability و cognitive effects تکمیل شود |
| Emerging terminology | Covered as separate registry | freshness، authority و status-label audit دوره‌ای |

## اصل منبع
برای هر مفهوم بنیادی: منبع canonical/historical در صورت نیاز + حداقل یک منبع جاری معتبر.
برای حوزه‌های سریع‌التغییر: حداقل دو منبع مستقل معتبر، ترجیحاً یکی primary/official.
برای اصطلاحات emerging/informal: حداقل دو شاهد جاری و برچسب وضعیت؛ هرگز به‌عنوان standard علمی ارائه نشوند.

## ترتیب توسعه
ابتدا Gapها، سپس Partialهای دارای ریسک بالا، و بعد عمق و exampleهای حوزه‌های Covered. هیچ lesson جدیدی بدون قرارگیری در این نقشه اضافه نشود.

## معیار پایان
پوشش فقط زمانی «کامل» اعلام می‌شود که برای تمام domainهای اجباری حداقل یک مسیر آموزشی مشخص، پیش‌نیازهای روشن، اصطلاحات کلیدی، و زنجیرهٔ منابع معتبر/به‌روز ثبت و با regression test قابل بررسی باشد.
