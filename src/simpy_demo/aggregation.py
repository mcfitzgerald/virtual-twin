"""Event aggregation for efficient storage of simulation results.

Provides hybrid event aggregation that reduces storage from ~460M rows/month
to ~150k rows while preserving OEE calculation and process mining capabilities.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd

# States that trigger context capture for process mining
INTERESTING_STATES = ["DOWN", "JAMMED"]

# Number of events before/after interesting events to capture
CONTEXT_WINDOW = 5

# States tracked for time-in-state aggregation
TRACKED_STATES = ["EXECUTE", "STARVED", "BLOCKED", "DOWN", "JAMMED"]


@dataclass
class BucketStats:
    """Aggregated statistics for a single time bucket."""

    bucket_index: int
    bucket_start_ts: datetime
    machine_name: str

    # State durations in seconds
    execute_sec: float = 0.0
    starved_sec: float = 0.0
    blocked_sec: float = 0.0
    down_sec: float = 0.0
    jammed_sec: float = 0.0

    # Event counts
    transition_count: int = 0
    down_count: int = 0
    jammed_count: int = 0

    def add_duration(self, state: str, duration: float) -> None:
        """Add duration to the appropriate state counter."""
        state_upper = state.upper()
        if state_upper == "EXECUTE":
            self.execute_sec += duration
        elif state_upper == "STARVED":
            self.starved_sec += duration
        elif state_upper == "BLOCKED":
            self.blocked_sec += duration
        elif state_upper == "DOWN":
            self.down_sec += duration
        elif state_upper == "JAMMED":
            self.jammed_sec += duration

    @property
    def total_sec(self) -> float:
        """Total tracked time in this bucket."""
        return (
            self.execute_sec
            + self.starved_sec
            + self.blocked_sec
            + self.down_sec
            + self.jammed_sec
        )

    @property
    def availability_pct(self) -> Optional[float]:
        """Availability percentage (execute / (execute + down + jammed))."""
        productive_time = self.execute_sec
        loss_time = self.down_sec + self.jammed_sec
        total = productive_time + loss_time
        if total == 0:
            return None
        return (productive_time / total) * 100.0


@dataclass
class BufferedEvent:
    """Event stored in the circular buffer for context capture."""

    index: int  # Global event index for ordering
    sim_time_sec: float
    machine_name: str
    state: str
    prev_state: Optional[str]
    duration_sec: Optional[float]


@dataclass
class EventAggregator:
    """Aggregates equipment state changes into bucketed summaries and filtered details.

    Default behavior (hybrid mode):
    1. state_summary - Bucketed time-in-state aligned to telemetry interval
    2. events_detail - Filtered interesting events (DOWN/JAMMED) with context

    Usage:
        aggregator = EventAggregator(bucket_size_sec=300.0)

        # During simulation, call on each state change:
        aggregator.on_state_change(
            machine_name="Filler",
            new_state="DOWN",
            sim_time_sec=1234.5,
            prev_state="EXECUTE",
            duration_sec=10.0,  # duration of the prev_state
        )

        # After simulation completes:
        aggregator.finalize(total_time_sec=28800.0)

        # Get DataFrames for storage:
        df_summary = aggregator.get_summary_df()
        df_detail = aggregator.get_detail_df()
    """

    bucket_size_sec: float = 300.0
    sim_start_ts: datetime = field(default_factory=datetime.now)

    # Buckets indexed by (bucket_index, machine_name)
    _buckets: Dict[Tuple[int, str], BucketStats] = field(default_factory=dict)

    # Circular buffer for recent events (for context capture)
    _event_buffer: deque = field(
        default_factory=lambda: deque(maxlen=CONTEXT_WINDOW * 20)
    )

    # Indices of interesting events in the buffer
    _interesting_indices: List[int] = field(default_factory=list)

    # Global event counter
    _event_index: int = 0

    # Track last state per machine for duration accumulation at finalize
    _last_state: Dict[str, Tuple[str, float]] = field(default_factory=dict)

    def _get_bucket_index(self, sim_time_sec: float) -> int:
        """Get the bucket index for a given simulation time."""
        return int(sim_time_sec // self.bucket_size_sec)

    def _get_or_create_bucket(
        self, bucket_index: int, machine_name: str
    ) -> BucketStats:
        """Get or create a bucket for the given index and machine."""
        key = (bucket_index, machine_name)
        if key not in self._buckets:
            bucket_start_ts = self.sim_start_ts + timedelta(
                seconds=bucket_index * self.bucket_size_sec
            )
            self._buckets[key] = BucketStats(
                bucket_index=bucket_index,
                bucket_start_ts=bucket_start_ts,
                machine_name=machine_name,
            )
        return self._buckets[key]

    def on_state_change(
        self,
        machine_name: str,
        new_state: str,
        sim_time_sec: float,
        prev_state: Optional[str] = None,
        duration_sec: Optional[float] = None,
    ) -> None:
        """Record a state change event.

        Args:
            machine_name: Name of the machine
            new_state: The new state being entered
            sim_time_sec: Current simulation time in seconds
            prev_state: The state being exited (optional)
            duration_sec: Duration spent in prev_state (optional)
        """
        # 1. Accumulate prev_state duration to bucket(s)
        if prev_state and duration_sec and duration_sec > 0:
            self._accumulate_duration(
                machine_name=machine_name,
                state=prev_state,
                start_time_sec=sim_time_sec - duration_sec,
                end_time_sec=sim_time_sec,
            )

        # 2. Buffer event for potential context capture
        event = BufferedEvent(
            index=self._event_index,
            sim_time_sec=sim_time_sec,
            machine_name=machine_name,
            state=new_state,
            prev_state=prev_state,
            duration_sec=duration_sec,
        )
        self._event_buffer.append(event)

        # 3. Mark if interesting (DOWN/JAMMED transition INTO these states)
        if new_state.upper() in INTERESTING_STATES:
            self._interesting_indices.append(self._event_index)

        # 4. Track transition counts in current bucket
        bucket_idx = self._get_bucket_index(sim_time_sec)
        bucket = self._get_or_create_bucket(bucket_idx, machine_name)
        bucket.transition_count += 1

        if new_state.upper() == "DOWN":
            bucket.down_count += 1
        elif new_state.upper() == "JAMMED":
            bucket.jammed_count += 1

        # 5. Track last state for finalize
        self._last_state[machine_name] = (new_state, sim_time_sec)

        self._event_index += 1

    def _accumulate_duration(
        self,
        machine_name: str,
        state: str,
        start_time_sec: float,
        end_time_sec: float,
    ) -> None:
        """Accumulate duration across bucket boundaries.

        If a state spans multiple buckets, the duration is split proportionally.
        """
        if end_time_sec <= start_time_sec:
            return

        start_bucket = self._get_bucket_index(start_time_sec)
        end_bucket = self._get_bucket_index(end_time_sec)

        if start_bucket == end_bucket:
            # Duration fits within a single bucket
            bucket = self._get_or_create_bucket(start_bucket, machine_name)
            bucket.add_duration(state, end_time_sec - start_time_sec)
        else:
            # Duration spans multiple buckets - split it
            current_time = start_time_sec

            for bucket_idx in range(start_bucket, end_bucket + 1):
                bucket_end = (bucket_idx + 1) * self.bucket_size_sec
                segment_end = min(bucket_end, end_time_sec)
                segment_duration = segment_end - current_time

                if segment_duration > 0:
                    bucket = self._get_or_create_bucket(bucket_idx, machine_name)
                    bucket.add_duration(state, segment_duration)

                current_time = segment_end

    def finalize(self, total_time_sec: float) -> None:
        """Finalize aggregation after simulation completes.

        Closes final bucket by accumulating remaining time for last states.

        Args:
            total_time_sec: Total simulation duration in seconds
        """
        # Accumulate final state durations
        for machine_name, (state, last_time) in self._last_state.items():
            if last_time < total_time_sec:
                self._accumulate_duration(
                    machine_name=machine_name,
                    state=state,
                    start_time_sec=last_time,
                    end_time_sec=total_time_sec,
                )

    def get_summary_df(self) -> pd.DataFrame:
        """Get state summary as a DataFrame.

        Returns:
            DataFrame with columns matching state_summary schema:
            - bucket_start_ts, bucket_index, machine_name
            - execute_sec, starved_sec, blocked_sec, down_sec, jammed_sec
            - transition_count, down_count, jammed_count
            - availability_pct
        """
        if not self._buckets:
            return pd.DataFrame(
                columns=[
                    "bucket_start_ts",
                    "bucket_index",
                    "machine_name",
                    "execute_sec",
                    "starved_sec",
                    "blocked_sec",
                    "down_sec",
                    "jammed_sec",
                    "transition_count",
                    "down_count",
                    "jammed_count",
                    "availability_pct",
                ]
            )

        rows = []
        for bucket in self._buckets.values():
            rows.append(
                {
                    "bucket_start_ts": bucket.bucket_start_ts,
                    "bucket_index": bucket.bucket_index,
                    "machine_name": bucket.machine_name,
                    "execute_sec": bucket.execute_sec,
                    "starved_sec": bucket.starved_sec,
                    "blocked_sec": bucket.blocked_sec,
                    "down_sec": bucket.down_sec,
                    "jammed_sec": bucket.jammed_sec,
                    "transition_count": bucket.transition_count,
                    "down_count": bucket.down_count,
                    "jammed_count": bucket.jammed_count,
                    "availability_pct": bucket.availability_pct,
                }
            )

        df = pd.DataFrame(rows)
        return df.sort_values(["machine_name", "bucket_index"]).reset_index(drop=True)

    def get_detail_df(self) -> pd.DataFrame:
        """Get filtered event details with context as a DataFrame.

        Returns events marked as interesting (DOWN/JAMMED transitions)
        plus CONTEXT_WINDOW events before and after each for process mining.

        Returns:
            DataFrame with columns matching events_detail schema:
            - ts, sim_time_sec, machine_name, state, prev_state, duration_sec, is_interesting
        """
        if not self._interesting_indices or not self._event_buffer:
            return pd.DataFrame(
                columns=[
                    "ts",
                    "sim_time_sec",
                    "machine_name",
                    "state",
                    "prev_state",
                    "duration_sec",
                    "is_interesting",
                ]
            )

        # Build set of indices to include (interesting + context)
        indices_to_include: set = set()

        # Convert buffer to list for index access
        buffer_list = list(self._event_buffer)
        if not buffer_list:
            return pd.DataFrame(
                columns=[
                    "ts",
                    "sim_time_sec",
                    "machine_name",
                    "state",
                    "prev_state",
                    "duration_sec",
                    "is_interesting",
                ]
            )

        # Map event index to buffer position
        index_to_pos = {ev.index: i for i, ev in enumerate(buffer_list)}

        for interesting_idx in self._interesting_indices:
            if interesting_idx not in index_to_pos:
                continue

            pos = index_to_pos[interesting_idx]

            # Add context window before and after
            for offset in range(-CONTEXT_WINDOW, CONTEXT_WINDOW + 1):
                context_pos = pos + offset
                if 0 <= context_pos < len(buffer_list):
                    indices_to_include.add(buffer_list[context_pos].index)

        # Build rows for included events
        rows = []
        for event in buffer_list:
            if event.index in indices_to_include:
                ts = self.sim_start_ts + timedelta(seconds=event.sim_time_sec)
                rows.append(
                    {
                        "ts": ts,
                        "sim_time_sec": event.sim_time_sec,
                        "machine_name": event.machine_name,
                        "state": event.state,
                        "prev_state": event.prev_state,
                        "duration_sec": event.duration_sec,
                        "is_interesting": event.index in self._interesting_indices,
                    }
                )

        df = pd.DataFrame(rows)
        return df.sort_values("sim_time_sec").reset_index(drop=True)
