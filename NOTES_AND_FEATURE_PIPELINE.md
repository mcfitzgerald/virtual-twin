# Notes

OMAC PackML automation standard

how does ASCM SCORE-DS fit in.

## Feature Pipeline

### Time Coordination & Multi-Line Support

Currently `start_time` in RunConfig provides a baseline for timestamps (`start_time + env.now`). Future enhancements:

- **FactoryClock class**: Shared clock abstraction for multi-line coordination
  - Multiple SimPy environments syncing to same wall clock
  - Clock drift simulation (planned vs actual time)

- **Scheduled Events**: Time-based triggers independent of line state
  - Shift changes at fixed times (e.g., 14:00)
  - Scheduled breaks, maintenance windows
  - Changeovers triggered by time or production count

- **Production Plan Integration**: External schedule drives simulation
  - Load production orders with planned start/end times
  - Compare planned vs actual completion
  - Multi-product sequencing with changeovers

- **Real-time Sync**: Optional mode where simulation tracks actual wall time
  - For digital twin "live" visualization
  - Pause/resume with time alignment