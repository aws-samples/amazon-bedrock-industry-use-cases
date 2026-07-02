"""
Batch Processing Module for Scale Operations

Demonstrates that the BDA extraction pipeline can handle large volumes of documents
by processing files in parallel with:
- Concurrent job submission (not sequential)
- Configurable parallelism (respect BDA account quotas)
- Retry logic with exponential backoff
- Progress tracking and throughput metrics
- Failure isolation (one file failing doesn't stop the batch)

Usage:
    from source.batch_processor import BatchProcessor

    processor = BatchProcessor(
        project_arn="arn:aws:bedrock:...",
        bucket_name="my-bucket",
        max_concurrent_jobs=5,
    )
    results = processor.process_batch(file_keys=["reports/file1.pdf", "reports/file2.pdf"])
    processor.print_summary()
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from source.bda import get_processing_results, start_processing_job
from source.logger import get_logger

logger = get_logger(__name__)


@dataclass
class JobResult:
    """Result of a single BDA processing job."""

    file_key: str
    status: str  # "success", "failed", "timeout", "error"
    s3_output_uri: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    attempts: int = 1


@dataclass
class BatchMetrics:
    """Metrics for a batch processing run."""

    total_files: int = 0
    successful: int = 0
    failed: int = 0
    timed_out: int = 0
    total_duration_seconds: float = 0.0
    avg_duration_seconds: float = 0.0
    throughput_files_per_minute: float = 0.0
    max_concurrent_jobs: int = 0


class BatchProcessor:
    """
    Processes multiple well report files through BDA in parallel.

    Handles:
    - Concurrent job submission up to a configurable limit
    - Automatic retries with exponential backoff
    - Timeout handling per file
    - Progress callbacks for UI integration
    - Metrics collection for throughput analysis

    Args:
        project_arn: BDA project ARN
        bucket_name: S3 bucket for input/output
        max_concurrent_jobs: Maximum parallel BDA jobs (default: 5)
        max_retries: Maximum retry attempts per file (default: 2)
        max_wait_per_file: Maximum seconds to wait per file (default: 600)
        poll_interval: Seconds between status checks (default: 10)
        session: boto3 Session (optional)
    """

    def __init__(
        self,
        project_arn: str,
        bucket_name: str,
        max_concurrent_jobs: int = 5,
        max_retries: int = 2,
        max_wait_per_file: int = 600,
        poll_interval: int = 10,
        session: Optional[boto3.Session] = None,
    ):
        self.project_arn = project_arn
        self.bucket_name = bucket_name
        self.max_concurrent_jobs = max_concurrent_jobs
        self.max_retries = max_retries
        self.max_wait_per_file = max_wait_per_file
        self.poll_interval = poll_interval
        self.session = session or boto3.Session()

        self.results: List[JobResult] = []
        self.metrics = BatchMetrics()
        self._progress_callback = None

    def set_progress_callback(self, callback):
        """
        Set a callback function for progress updates.

        Callback signature: callback(completed: int, total: int, current_file: str)
        """
        self._progress_callback = callback

    def _process_single_file(self, file_key: str) -> JobResult:
        """
        Process a single file with retry logic.

        Args:
            file_key: S3 key of the file to process

        Returns:
            JobResult with status and output location
        """
        attempts = 0
        last_error = None

        while attempts < self.max_retries:
            attempts += 1
            start_time = time.time()

            try:
                logger.info(
                    f"Processing {file_key} (attempt {attempts}/{self.max_retries})"
                )

                result = start_processing_job(
                    project_arn=self.project_arn,
                    file_name=file_key,
                    bucket_name=self.bucket_name,
                    wait_for_complete=True,
                    max_wait_seconds=self.max_wait_per_file,
                    poll_interval=self.poll_interval,
                    session=self.session,
                )

                duration = time.time() - start_time

                return JobResult(
                    file_key=file_key,
                    status="success",
                    s3_output_uri=result.get("S3_URI"),
                    duration_seconds=duration,
                    attempts=attempts,
                )

            except TimeoutError as e:
                duration = time.time() - start_time
                last_error = str(e)
                logger.warning(
                    f"Timeout for {file_key} after {duration:.1f}s (attempt {attempts})"
                )
                # Don't retry timeouts — the file is likely too large
                return JobResult(
                    file_key=file_key,
                    status="timeout",
                    error_message=last_error,
                    duration_seconds=duration,
                    attempts=attempts,
                )

            except RuntimeError as e:
                duration = time.time() - start_time
                last_error = str(e)
                logger.error(f"Job failed for {file_key}: {e} (attempt {attempts})")
                # Retry on runtime errors (service errors may be transient)
                if attempts < self.max_retries:
                    backoff = 2**attempts * 5  # 10s, 20s, 40s...
                    logger.info(f"Retrying in {backoff}s...")
                    time.sleep(backoff)

            except ClientError as e:
                duration = time.time() - start_time
                last_error = str(e)
                error_code = e.response.get("Error", {}).get("Code", "")

                # Throttling — back off and retry
                if error_code in ("ThrottlingException", "TooManyRequestsException"):
                    logger.warning(f"Throttled on {file_key}, backing off...")
                    if attempts < self.max_retries:
                        backoff = 2**attempts * 10  # 20s, 40s...
                        time.sleep(backoff)
                        continue

                logger.error(f"AWS error for {file_key}: {e}")
                return JobResult(
                    file_key=file_key,
                    status="error",
                    error_message=last_error,
                    duration_seconds=duration,
                    attempts=attempts,
                )

            except Exception as e:
                duration = time.time() - start_time
                last_error = str(e)
                logger.error(f"Unexpected error for {file_key}: {e}")
                return JobResult(
                    file_key=file_key,
                    status="error",
                    error_message=last_error,
                    duration_seconds=duration,
                    attempts=attempts,
                )

        # All retries exhausted
        return JobResult(
            file_key=file_key,
            status="failed",
            error_message=f"Failed after {attempts} attempts. Last error: {last_error}",
            duration_seconds=time.time() - start_time,
            attempts=attempts,
        )

    def process_batch(self, file_keys: List[str]) -> List[JobResult]:
        """
        Process multiple files in parallel.

        Args:
            file_keys: List of S3 keys to process

        Returns:
            List of JobResult objects
        """
        self.results = []
        self.metrics = BatchMetrics(
            total_files=len(file_keys),
            max_concurrent_jobs=self.max_concurrent_jobs,
        )

        batch_start = time.time()
        completed = 0

        logger.info(
            f"Starting batch: {len(file_keys)} files, "
            f"max {self.max_concurrent_jobs} concurrent jobs"
        )

        with ThreadPoolExecutor(max_workers=self.max_concurrent_jobs) as executor:
            # Submit all jobs
            future_to_file = {
                executor.submit(self._process_single_file, fk): fk
                for fk in file_keys
            }

            # Collect results as they complete
            for future in as_completed(future_to_file):
                result = future.result()
                self.results.append(result)
                completed += 1

                if result.status == "success":
                    self.metrics.successful += 1
                elif result.status == "timeout":
                    self.metrics.timed_out += 1
                else:
                    self.metrics.failed += 1

                # Progress callback
                if self._progress_callback:
                    self._progress_callback(completed, len(file_keys), result.file_key)

                logger.info(
                    f"[{completed}/{len(file_keys)}] {result.file_key}: "
                    f"{result.status} ({result.duration_seconds:.1f}s)"
                )

        # Calculate metrics
        batch_duration = time.time() - batch_start
        self.metrics.total_duration_seconds = batch_duration

        successful_durations = [
            r.duration_seconds for r in self.results if r.status == "success"
        ]
        if successful_durations:
            self.metrics.avg_duration_seconds = sum(successful_durations) / len(
                successful_durations
            )

        if batch_duration > 0:
            self.metrics.throughput_files_per_minute = (
                self.metrics.successful / batch_duration * 60
            )

        logger.info(f"Batch complete: {self.get_summary()}")
        return self.results

    def get_summary(self) -> str:
        """Get a human-readable summary of the batch run."""
        m = self.metrics
        return (
            f"{m.successful}/{m.total_files} successful, "
            f"{m.failed} failed, {m.timed_out} timed out | "
            f"Total: {m.total_duration_seconds:.1f}s | "
            f"Avg per file: {m.avg_duration_seconds:.1f}s | "
            f"Throughput: {m.throughput_files_per_minute:.1f} files/min"
        )

    def get_failed_files(self) -> List[str]:
        """Get list of files that failed processing."""
        return [r.file_key for r in self.results if r.status != "success"]

    def get_successful_results(self) -> List[Dict]:
        """Get results in the same format as start_processing_job for downstream use."""
        return [
            {"file": r.file_key, "S3_URI": r.s3_output_uri}
            for r in self.results
            if r.status == "success"
        ]

    def print_summary(self):
        """Print detailed batch processing summary."""
        m = self.metrics
        print("\n" + "=" * 60)
        print("BATCH PROCESSING SUMMARY")
        print("=" * 60)
        print(f"  Total files:          {m.total_files}")
        print(f"  Successful:           {m.successful}")
        print(f"  Failed:               {m.failed}")
        print(f"  Timed out:            {m.timed_out}")
        print(f"  Max concurrent jobs:  {m.max_concurrent_jobs}")
        print(f"  Total duration:       {m.total_duration_seconds:.1f}s")
        print(f"  Avg per file:         {m.avg_duration_seconds:.1f}s")
        print(f"  Throughput:           {m.throughput_files_per_minute:.1f} files/min")
        print("=" * 60)

        if self.get_failed_files():
            print("\nFailed files:")
            for r in self.results:
                if r.status != "success":
                    print(f"  ✗ {r.file_key} [{r.status}]: {r.error_message}")
        print()
