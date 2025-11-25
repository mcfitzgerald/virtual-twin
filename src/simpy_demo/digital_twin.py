import simpy
import random
import uuid
import pandas as pd
from typing import List, Optional, Literal, Any, Dict
from pydantic import BaseModel, Field
from enum import Enum

# ==========================================
# 1. CONFIGURATION SCHEMAS (Pydantic)
# ==========================================

class MaterialType(str, Enum):
    TUBE = "Tube"
    CASE = "Case"
    PALLET = "Pallet"
    NONE = "None"

# --- Material Models (Traceability) ---
class Product(BaseModel):
    uid: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: MaterialType
    created_at: float
    parent_machine: str
    is_defective: bool = False
    genealogy: List[str] = Field(default_factory=list) # IDs of children components
    telemetry: Dict[str, Any] = Field(default_factory=dict) # Sensor data (temp, weight)

# --- Equipment Configuration ---
class MachineConfig(BaseModel):
    name: str
    uph: int = Field(..., description="Target Speed (Units Per Hour)")
    batch_in: int = Field(1, description="Items required to start cycle")
    output_type: MaterialType = MaterialType.NONE
    
    # Reliability (Major Breakdowns - Availability Loss)
    mtbf_min: Optional[float] = None # Mean Time Between Failures (Time-based)
    mttr_min: float = 60.0           # Mean Time To Repair (Default: 1 hour)
    
    # Microstops (Jams - Performance Loss)
    jam_prob: float = 0.0            # Probability (0-1) of a jam per cycle
    jam_time_sec: float = 10.0       # Time to clear a jam (Default: 10 sec)
    
    # Quality (Yield Loss)
    defect_rate: float = 0.0         # Prob of creating a defect
    detection_prob: float = 0.0      # Prob of detecting a defect (Inspection)
    
    # Constraints
    buffer_capacity: int = 50        # Input buffer size

    @property
    def cycle_time_sec(self) -> float:
        return 3600.0 / self.uph

class ScenarioConfig(BaseModel):
    name: str
    duration_hours: float = 8.0
    random_seed: Optional[int] = 42
    layout: List[MachineConfig]

# ==========================================
# 2. CORE LOGIC: The Smart Machine
# ==========================================

class SmartEquipment:
    def __init__(self, env: simpy.Environment, config: MachineConfig, 
                 upstream: simpy.Store, downstream: simpy.Store, reject_store: Optional[simpy.Store]):
        self.env = env
        self.cfg = config
        self.upstream = upstream
        self.downstream = downstream
        self.reject_store = reject_store
        
        self.items_produced = 0
        self.state = "IDLE"
        
        # Centralized Logs
        self.event_log = [] 

        self.process = env.process(self.run())

    def log(self, new_state):
        """Records state transitions for OEE calculation."""
        if self.state != new_state:
            self.event_log.append({
                "timestamp": self.env.now,
                "machine": self.cfg.name,
                "state": self.state,
                "event_type": "end"
            })
            self.state = new_state
            self.event_log.append({
                "timestamp": self.env.now,
                "machine": self.cfg.name,
                "state": self.state,
                "event_type": "start"
            })

    def run(self):
        self.log("STARVED")
        
        while True:
            # --- PHASE 1: COLLECT (Starvation Logic) ---
            # Represents "Idling" - Waiting for material
            inputs = []
            for _ in range(self.cfg.batch_in):
                item = yield self.upstream.get()
                inputs.append(item)
            
            # --- PHASE 2: BREAKDOWN CHECK (Availability Loss) ---
            # Major failures based on elapsed time (MTBF)
            if self.cfg.mtbf_min:
                # Poisson probability of failure during this cycle
                p_fail = 1.0 - 2.718 ** -(self.cfg.cycle_time_sec / (self.cfg.mtbf_min * 60))
                if random.random() < p_fail:
                    self.log("DOWN")
                    # Stochastic repair time
                    repair_time = random.expovariate(1.0 / (self.cfg.mttr_min * 60))
                    yield self.env.timeout(repair_time)
            
            # --- PHASE 3: MICROSTOP CHECK (Performance Loss) ---
            # Minor jams based on cycle count (Jam Rate)
            if self.cfg.jam_prob > 0 and random.random() < self.cfg.jam_prob:
                 self.log("JAMMED")
                 # Fixed or small variable time to clear jam
                 yield self.env.timeout(self.cfg.jam_time_sec)

            # --- PHASE 4: EXECUTE (Value Add) ---
            self.log("EXECUTE")
            yield self.env.timeout(self.cfg.cycle_time_sec)
            
            # --- PHASE 5: TRANSFORM (Traceability Logic) ---
            output_item = self._transform_material(inputs)
            self.items_produced += 1

            # --- PHASE 6: INSPECT & ROUTE (Quality Logic) ---
            routed_to_reject = False
            if self.cfg.detection_prob > 0 and output_item.is_defective:
                if random.random() < self.cfg.detection_prob:
                    routed_to_reject = True

            # If downstream is full, we enter BLOCKED state (Constraint)
            self.log("BLOCKED") 
            if routed_to_reject and self.reject_store:
                yield self.reject_store.put(output_item)
            else:
                yield self.downstream.put(output_item)
            
            # If we succeed, we go back to waiting (Starved)
            self.log("STARVED")

    def _transform_material(self, inputs: List[Product]) -> Product:
        # 1. Inherit Defects
        has_inherited_defect = any(i.is_defective for i in inputs)
        
        # 2. Create New Defect?
        new_defect = random.random() < self.cfg.defect_rate
        is_bad = has_inherited_defect or new_defect
        
        # 3. Create Payload
        genealogy = [i.uid for i in inputs]
        
        # 4. Factory Construction
        if self.cfg.output_type == MaterialType.TUBE:
            return Product(
                type=MaterialType.TUBE, created_at=self.env.now, parent_machine=self.cfg.name,
                is_defective=is_bad, genealogy=genealogy,
                telemetry={"fill_level": random.gauss(100, 1.0)}
            )
        elif self.cfg.output_type == MaterialType.CASE:
             return Product(
                type=MaterialType.CASE, created_at=self.env.now, parent_machine=self.cfg.name,
                is_defective=is_bad, genealogy=genealogy,
                telemetry={"weight": sum([100 for _ in inputs]) + 50}
            )
        elif self.cfg.output_type == MaterialType.PALLET:
             return Product(
                type=MaterialType.PALLET, created_at=self.env.now, parent_machine=self.cfg.name,
                is_defective=is_bad, genealogy=genealogy,
                telemetry={"location": "Warehouse_A"}
            )
        
        # Pass-through (e.g. Inspection Station)
        return inputs[0]

# ==========================================
# 3. ENVIRONMENT: The Factory Floor
# ==========================================

class ProductionLine:
    def __init__(self, config: ScenarioConfig):
        self.cfg = config
        self.env = simpy.Environment()
        self.machines: List[SmartEquipment] = []
        self.buffers: Dict[str, simpy.Store] = {}
        
        if self.cfg.random_seed:
            random.seed(self.cfg.random_seed)

        self._build_layout()
        
        # Start Data Collector
        self.env.process(self._monitor_process(interval=1.0))
        self.telemetry_data = []

    def _build_layout(self):
        # 1. Infinite Source
        source = simpy.Store(self.env, capacity=float('inf'))
        # Pre-fill with generic raw material
        for i in range(100000):
            source.put(Product(type=MaterialType.NONE, created_at=0, parent_machine="Raw", genealogy=[]))
        
        # 2. Reject Bin (Infinite Sink)
        self.reject_bin = simpy.Store(self.env, capacity=float('inf'))

        # 3. Build Line
        current_upstream = source
        
        for i, m_conf in enumerate(self.cfg.layout):
            # Create Buffer (Constraint)
            buffer_name = f"Buf_{m_conf.name}"
            # Last machine output goes to infinite Sink
            cap = float('inf') if i == len(self.cfg.layout) - 1 else m_conf.buffer_capacity
            
            downstream = simpy.Store(self.env, capacity=cap)
            self.buffers[buffer_name] = downstream # Track for monitoring

            # Create Machine
            machine = SmartEquipment(
                self.env, m_conf, 
                upstream=current_upstream, 
                downstream=downstream,
                reject_store=self.reject_bin if m_conf.detection_prob > 0 else None
            )
            self.machines.append(machine)
            current_upstream = downstream

    def _monitor_process(self, interval: float):
        """Periodically records buffer levels and machine states."""
        while True:
            snapshot = {"time": self.env.now}
            
            # Log Buffer Levels (Constraint Analysis)
            for name, buf in self.buffers.items():
                if buf.capacity != float('inf'):
                    snapshot[f"{name}_level"] = len(buf.items)
                    snapshot[f"{name}_cap"] = buf.capacity
            
            # Log Machine States (Status Analysis)
            for m in self.machines:
                snapshot[f"{m.cfg.name}_state"] = m.state
                snapshot[f"{m.cfg.name}_output"] = m.items_produced

            self.telemetry_data.append(snapshot)
            yield self.env.timeout(interval)

    def run(self):
        print(f"Starting Simulation: {self.cfg.name} ({self.cfg.duration_hours} hrs)...")
        self.env.run(until=self.cfg.duration_hours * 3600)
        return self._compile_results()

    def _compile_results(self):
        # 1. Telemetry (Time-Series)
        df_telemetry = pd.DataFrame(self.telemetry_data)
        
        # 2. Events (State Log)
        events = []
        for m in self.machines:
            events.extend(m.event_log)
        df_events = pd.DataFrame(events)
        
        return df_telemetry, df_events

# ==========================================
# 4. EXECUTION
# ==========================================

if __name__ == "__main__":
    # --- Define Scenario (Based on White Paper) ---
    scenario = ScenarioConfig(
        name="Cosmetics_Line_Microstops",
        duration_hours=8.0,
        layout=[
            # 1. Depalletizer: Pushes tubes into the line
            MachineConfig(
                name="Depalletizer", uph=11000, batch_in=1, 
                output_type=MaterialType.TUBE,
                buffer_capacity=1000, 
                mtbf_min=480 # Very reliable (once per shift)
            ),
            # 2. Filler: The Bottleneck & Quality Risk
            MachineConfig(
                name="Filler", uph=10000, batch_in=1, 
                output_type=MaterialType.TUBE,
                buffer_capacity=50, # Small buffer = High starvation risk
                mtbf_min=120,    # Major breakdown every 2 hours
                mttr_min=15,     # Takes 15 mins to fix
                jam_prob=0.01,   # 1% chance of microstop per tube
                jam_time_sec=15, # 15 seconds to clear jam
                defect_rate=0.02 # 2% defects
            ),
            # 3. Checkweigher: Inspection Station
            MachineConfig(
                name="Inspector", uph=11000, batch_in=1,
                buffer_capacity=20, # Minimal accumulation
                detection_prob=0.95 # Catches 95% of defects
            ),
            # 4. Packer: Aggregation (12 -> 1)
            MachineConfig(
                name="Packer", uph=12000, batch_in=12,
                output_type=MaterialType.CASE,
                buffer_capacity=100, # Accumulator table
                mtbf_min=240,
                jam_prob=0.05,    # 5% chance of jam per BOX (not tube)
                jam_time_sec=30
            ),
            # 5. Palletizer: End of Line (60 -> 1)
            MachineConfig(
                name="Palletizer", uph=13000, batch_in=60,
                output_type=MaterialType.PALLET,
                buffer_capacity=40,
                mtbf_min=480
            )
        ]
    )

    # --- Run ---
    sim = ProductionLine(scenario)
    df_ts, df_ev = sim.run()

    # --- Report ---
    print("\n--- SIMULATION COMPLETE ---")
    print(f"Telemetry Records: {len(df_ts)}")
    print(f"Event Records: {len(df_ev)}")
    
    # OEE Analysis
    print("\n--- Time in State (Seconds) ---")
    if not df_ev.empty:
        # Calculate duration of each state
        df_ev['next_time'] = df_ev.groupby('machine')['timestamp'].shift(-1)
        df_ev['duration'] = df_ev['next_time'] - df_ev['timestamp']
        
        # Pivot table for summary
        stats = df_ev.groupby(['machine', 'state'])['duration'].sum().unstack().fillna(0)
        
        # Calculate Availability (Total - Down / Total)
        total_time = scenario.duration_hours * 3600
        stats['Availability_%'] = (1 - (stats.get('DOWN', 0) / total_time)) * 100
        
        # Reorder columns for readability
        cols = ['EXECUTE', 'STARVED', 'BLOCKED', 'DOWN', 'JAMMED', 'Availability_%']
        existing_cols = [c for c in cols if c in stats.columns]
        print(stats[existing_cols].round(1))
    
    # --- Export Data ---
    # df_ts.to_csv("telemetry.csv", index=False)
    # df_ev.to_csv("events.csv", index=False)