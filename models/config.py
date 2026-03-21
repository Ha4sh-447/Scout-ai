from pydantic import BaseModel, Field


class ScraperConfig(BaseModel):
    max_jobs_per_url: int = Field(
        default=30, description="Max jobs to extract from a single URL"
    )
    batch_size: int = Field(
        default=10,
        description="Number of jobs to process concurrently at a time before waiting",
    )
    batch_delay_range: tuple[float, float] = Field(
        default=(3.0, 8.0), description="Min/Max random sleep seconds between batches"
    )
    url_delay_range: tuple[float, float] = Field(
        default=(3.0, 8.0), description="Min/Max random sleep seconds between URLs"
    )
    enrich_jobs: bool = Field(
        default=True,
        description="If True, visit individual job URLs to get full descriptions. Set False for quick tests.",
    )
    browser_state_path: str | None = Field(
        default="data/browser_state.json",
        description="Path to saved Playwright storage state (cookies). None = guest mode.",
    )
    seen_jobs_path: str = Field(
        default="data/seen_jobs.json",
        description="Path to the cross-run seen jobs store.",
    )


class QdrantConfig(BaseModel):
    url: str | None = Field(
        default="http://localhost:6333", description="Qdrant cloud or local url."
    )
    api_key: str | None = Field(default=None, description="Qdrant api key")
    collection_name: str | None = Field(
        default="resume_chunks", description="Name of qdrant collection"
    )
    full_resume_collection: str | None = Field(
        default="resume_full", description="Name of qdrant collection for full resumes"
    )


class MistralConfig(BaseModel):
    api_key: str = Field(description="Mistral api key")
    embed_model: str = Field(
        default="mistral-embed", description="Model used to generate embeddings"
    )
    embedding_dim: int = Field(
        default=1024, description="Output dimension of embedding models"
    )


class ResumeMatchingConfig(BaseModel):
    min_match_score: float = Field(
        default=0.45, description="Jobs below this chunk-based score are dropped"
    )
    top_k_chunks: int = Field(
        default=5, description="Number of resume chunks to retrieve"
    )

    # Resume reranking fields
    full_resume_weight: float = Field(
        default=0.35, description="Contribution of full resume score to final score"
    )
    rerank_top_n: int = Field(
        default=20, description=" Rerank top n jobs after passing stage 1"
    )

    # PDF chunking
    chunk_size: int = Field(default=1200, description="Size of each chunk")
    overlap_count: int = Field(
        default=200, description=" Count of overlapping words between each chunk"
    )
    resume_dir: str = Field(
        default="data/resumes", description="Directory where resumes are stored"
    )

class RankingConfig(BaseModel):
    match_weight: float = Field(
            default= 0.60,
            description="Weight given to resume match_score"
            )
    recency_weight: float = Field(
            default = 0.25,
            description="Weight given to how recently the job was scrapped"
            )
    source_quality_weight: float = Field(
            default = 0.15,
            description="Weight given to platform quality"
            )
    agency_recruiter_weight: float = Field(
            default = 0.15,
            description="Score penalty applied to the recruiter type"
            )
    recency_decay_days: int = Field(
            default=14,
            description="Most recent jobs"
            )

class EmailConfig(BaseModel):
    smtp_host: str = Field(default = "smtp.gmail.com")
    smtp_port: int = Field(default=587)
    sender_email: str | None = None
    sender_password: str | None = None
    recipient_email: str | None = None
    subject_prefix: str = Field(
            default = "[Job Digest]"
            )
