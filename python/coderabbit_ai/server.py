"""FastAPI server for CodeRabbit AI Pipeline."""

import os
import pathlib
import re
import asyncio
import json
from datetime import datetime
from typing import Dict, Any
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi import Body
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import msgpack

from .models import ReviewRequest, ReviewResponse
from .pipeline import CodeRabbitMultiAgentPipeline
from .embeddings import get_embedding_service
from . import config
from .dashboard import router as dashboard_router


# Global pipeline instance
pipeline: CodeRabbitMultiAgentPipeline = None


# --- Result storage helpers ---
def _get_store_dir() -> str:
    """Return the directory to store review results and ensure it exists."""
    base = config.REVIEW_STORE_PATH
    os.makedirs(base, exist_ok=True)
    return base


def _save_to_file(review_id: str, payload: Dict[str, Any]) -> str:
    """Persist review result to a JSON file and update a simple index."""
    # Validate review_id to prevent path traversal
    if not re.match(r"^[a-zA-Z0-9\-_]+$", review_id):
        raise ValueError("Invalid review_id: contains unsafe characters")
    store = _get_store_dir()
    path = os.path.join(store, f"{review_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Maintain a lightweight index of recent reviews
    index_path = os.path.join(store, "index.json")
    try:
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                idx = json.load(f)
        else:
            idx = {"reviews": []}
    except Exception:
        idx = {"reviews": []}

    idx_entry = {
        "review_id": review_id,
        "stored_at": datetime.utcnow().isoformat() + "Z",
        "path": path,
    }
    idx["reviews"].insert(0, idx_entry)
    idx["reviews"] = idx["reviews"][:100]  # keep last 100
    try:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=2)
    except Exception:
        # Non-fatal
        pass

    return path


def _save_to_redis_if_available(review_id: str, payload: Dict[str, Any]) -> None:
    """Optionally save to Redis if redis-py is available and REDIS_URL is set."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return
    try:
        import redis  # type: ignore

        r = redis.Redis.from_url(redis_url, decode_responses=True)
        key = f"review:{review_id}"
        ttl = int(os.getenv("REVIEW_CACHE_TTL", "86400"))  # 1 day default
        r.setex(key, ttl, json.dumps(payload))
    except Exception as e:
        # Log only; file storage is still primary
        logger.warning(f"Redis save skipped: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """Application lifespan manager."""
    global pipeline

    # Startup
    logger.info("Starting CodeRabbit AI Pipeline server")

    # Initialize DSPy configuration
    import dspy

    # Configure OpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        openai_lm = dspy.LM(
            model="openai/gpt-3.5-turbo", api_key=openai_key, max_tokens=4096
        )
        dspy.settings.configure(lm=openai_lm)
        logger.info("Configured OpenAI language model")
    else:
        logger.warning("OPENAI_API_KEY not set, using dummy configuration")
        # Use a dummy LM for development
        # dspy.settings.configure(lm=dspy.DummyLM())

    # Initialize pipeline
    config = {
        "verification_specializations": [
            "security",
            "performance",
            "style",
            "logic",
            "testing",
        ],
        "openai_api_key": openai_key,
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
    }

    pipeline = CodeRabbitMultiAgentPipeline(config)
    logger.info("Initialized CodeRabbit multi-agent pipeline")

    yield

    # Shutdown
    logger.info("Shutting down CodeRabbit AI Pipeline server")


# Create FastAPI app
app = FastAPI(
    title="CodeRabbit AI Pipeline",
    description="DSPy-powered multi-agent code review system",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include dashboard router
app.include_router(dashboard_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "ai-pipeline", "version": "0.1.0"}


@app.post("/review", response_model=ReviewResponse)
async def process_review(request: ReviewRequest, background_tasks: BackgroundTasks):
    """Process a code review request."""
    try:
        logger.info(f"Processing review request for PR #{request.pull_request.number}")

        # Process the review using the pipeline
        response = pipeline.forward(request)

        # Persist result (sync path) for observability/debugging
        try:
            payload = (
                response.model_dump()
                if hasattr(response, "model_dump")
                else response.dict()
            )
            payload["stored_at"] = datetime.utcnow().isoformat() + "Z"
            file_path = _save_to_file(response.review_id, payload)
            _save_to_redis_if_available(response.review_id, payload)
            logger.info(f"Review stored at {file_path}")
        except Exception as e:
            logger.warning(f"Failed to persist review {response.review_id}: {e}")

        logger.info(f"Review completed: {response.review_id}")
        return response

    except Exception as e:
        logger.error(f"Review processing failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Review processing failed: {str(e)}"
        )


@app.post("/bridge/analysis_file_batch")
async def bridge_analysis_file_batch(payload: Dict[str, Any] = Body(...)):
    """Consume a batch of files via shared memory path and parse MessagePack-encoded FileChange[]"""
    MAX_MSGPACK_SIZE = 10 * 1024 * 1024  # 10MB
    try:
        shm_path = payload.get("shared_memory_path")
        byte_len = int(payload.get("byte_len", 0))
        if not shm_path or byte_len <= 0:
            raise HTTPException(
                status_code=400, detail="Missing shared_memory_path or byte_len"
            )

        # Validate msgpack payload size
        if byte_len > MAX_MSGPACK_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"MessagePack payload too large: {byte_len} bytes (max: {MAX_MSGPACK_SIZE})",
            )

        # Validate shm_path to prevent directory traversal
        shm_path_resolved = pathlib.Path(shm_path).resolve()
        if not str(shm_path_resolved).startswith("/tmp/coderabbit_shm/"):
            raise HTTPException(
                status_code=400,
                detail="Invalid shm_path: must be in /tmp/coderabbit_shm/",
            )

        with open(shm_path_resolved, "rb") as f:
            raw = f.read(byte_len)

        files_changed = msgpack.unpackb(raw, raw=False)
        logger.info(f"Bridge received file batch: {len(files_changed)} files")

        # Wire to pipeline/analyzer
        try:
            # Import required models
            from .models import ReviewRequest, Repository, PullRequest, FileChange

            # Extract metadata from payload
            repository_data = payload.get("repository", {})
            pr_data = payload.get("pull_request", {})
            config_data = payload.get("config", {})

            # Build ReviewRequest from the file changes and metadata
            repository = Repository(
                name=repository_data.get("name", "unknown"),
                owner=repository_data.get("owner", "unknown"),
                platform=repository_data.get("platform", "github"),
                default_branch=repository_data.get("default_branch", "main"),
            )

            # Convert msgpack files to FileChange objects
            file_changes = []
            for file_data in files_changed:
                file_change = FileChange(
                    filename=file_data.get("filename", ""),
                    status=file_data.get("status", "modified"),
                    additions=file_data.get("additions", 0),
                    deletions=file_data.get("deletions", 0),
                    changes=file_data.get("changes", 0),
                    patch=file_data.get("patch", ""),
                    content=file_data.get("content", None),
                )
                file_changes.append(file_change)

            pull_request = PullRequest(
                number=pr_data.get("number", 0),
                title=pr_data.get("title", ""),
                description=pr_data.get("description", ""),
                author=pr_data.get("author", ""),
                base_branch=pr_data.get("base_branch", "main"),
                head_branch=pr_data.get("head_branch", ""),
                files_changed=file_changes,
            )

            # Create ReviewRequest
            review_request = ReviewRequest(
                repository=repository, pull_request=pull_request, config=config_data
            )

            # Process through pipeline
            review_response = pipeline.forward(review_request)

            # Serialize response back to msgpack
            response_data = (
                review_response.model_dump()
                if hasattr(review_response, "model_dump")
                else review_response.dict()
            )
            packed_response = msgpack.packb(response_data, use_bin_type=True)

            # Write response to shared memory
            response_path = str(shm_path_resolved) + ".response"
            with open(response_path, "wb") as f:
                f.write(packed_response)

            logger.info(
                f"Analysis completed: {len(file_changes)} files analyzed, {len(review_response.comments)} comments generated"
            )

            return {
                "status": "ok",
                "files_count": len(files_changed),
                "review_id": review_response.review_id,
                "comments_count": len(review_response.comments),
                "response_path": response_path,
                "response_size": len(packed_response),
            }

        except Exception as analysis_error:
            logger.error(f"Pipeline analysis failed: {str(analysis_error)}")
            # Return graceful degradation
            return {
                "status": "partial",
                "files_count": len(files_changed),
                "error": str(analysis_error),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"bridge_analysis_file_batch failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"bridge_analysis_file_batch failed: {str(e)}"
        )


@app.post("/bridge/embedding_batch")
async def bridge_embedding_batch(payload: Dict[str, Any] = Body(...)):
    """Consume a batch of code snippets via shared memory and parse MessagePack-encoded List[str]"""
    try:
        shm_path = payload.get("shared_memory_path")
        byte_len = int(payload.get("byte_len", 0))
        if not shm_path or byte_len <= 0:
            raise HTTPException(
                status_code=400, detail="Missing shared_memory_path or byte_len"
            )

        with open(shm_path, "rb") as f:
            raw = f.read(byte_len)

        code_snippets = msgpack.unpackb(raw, raw=False)
        logger.info(f"Bridge received embedding batch: {len(code_snippets)} items")

        # Generate embeddings using the embedding service
        embedding_service = get_embedding_service()
        embeddings = embedding_service.generate_code_embeddings(
            code_snippets, batch_size=32
        )

        # Convert embeddings to list for serialization
        embeddings_list = embeddings.tolist()

        # Write embeddings back to shared memory
        response_data = msgpack.packb(embeddings_list, use_bin_type=True)
        response_path = shm_path + ".response"

        with open(response_path, "wb") as f:
            f.write(response_data)

        logger.info(
            f"Generated {len(embeddings_list)} embeddings of dimension {len(embeddings_list[0])}"
        )

        return {
            "status": "ok",
            "items": len(code_snippets),
            "embeddings_count": len(embeddings_list),
            "dimension": len(embeddings_list[0]) if embeddings_list else 0,
            "response_path": response_path,
            "response_size": len(response_data),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"bridge_embedding_batch failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"bridge_embedding_batch failed: {str(e)}"
        )


@app.post("/review/async")
async def process_review_async(
    request: ReviewRequest, background_tasks: BackgroundTasks
):
    """Process a code review request asynchronously."""
    try:
        review_id = f"review_{int(asyncio.get_event_loop().time())}"

        # Add background task
        background_tasks.add_task(process_review_background, request, review_id)

        return {
            "review_id": review_id,
            "status": "queued",
            "message": "Review request queued for processing",
        }

    except Exception as e:
        logger.error(f"Failed to queue review: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to queue review: {str(e)}")


async def process_review_background(request: ReviewRequest, review_id: str):
    """Background task for processing reviews."""
    try:
        logger.info(f"Processing background review: {review_id}")

        # Process the review
        response = pipeline.forward(request)

        # Store result in file and optional Redis cache
        try:
            payload = (
                response.model_dump()
                if hasattr(response, "model_dump")
                else response.dict()
            )
            payload["stored_at"] = datetime.utcnow().isoformat() + "Z"
            file_path = _save_to_file(review_id, payload)
            _save_to_redis_if_available(review_id, payload)
            logger.info(f"Background review stored at {file_path}")
        except Exception as e:
            logger.warning(f"Failed to persist background review {review_id}: {e}")

        logger.info(f"Background review completed: {review_id}")

    except Exception as e:
        logger.error(f"Background review failed: {review_id}, error: {str(e)}")


@app.get("/pipeline/stats")
async def get_pipeline_stats():
    """Get pipeline statistics and health information."""
    return {
        "status": "active",
        "agents": {
            "context_engineering": "active",
            "review_agent": "active",
            "verification_pool": "active",
        },
        "models_configured": bool(os.getenv("OPENAI_API_KEY")),
        "specializations": ["security", "performance", "style", "logic", "testing"],
    }


@app.post("/pipeline/optimize")
async def optimize_pipeline(training_data: Dict[str, Any]):
    """Trigger pipeline optimization using DSPy."""
    try:
        logger.info("Starting pipeline optimization")

        # TODO: Implement actual optimization
        # This would use DSPy's MIPRO optimizer

        return {
            "status": "optimization_started",
            "message": "Pipeline optimization initiated",
        }

    except Exception as e:
        logger.error(f"Pipeline optimization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


def main():
    """Main entry point for the server."""
    # Configure logging
    logger.remove()
    logger.add(
        "logs/ai-pipeline.log",
        rotation="1 day",
        retention="30 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
    )
    logger.add(
        lambda msg: print(msg, end=""),
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | {message}",
    )

    # Get configuration from config module
    logger.info(
        f"Starting server on {config.SERVER_HOST}:{config.SERVER_PORT} with {config.SERVER_WORKERS} workers"
    )

    # Run the server
    uvicorn.run(
        "coderabbit_ai.server:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        workers=config.SERVER_WORKERS,
        reload=os.getenv("ENVIRONMENT") == "development",
        log_level="info",
    )


if __name__ == "__main__":
    main()
