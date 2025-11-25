import random
import time
from collections import deque
from typing import List, Tuple, Optional, Dict, Set

class Box:
    """Represents a box in the warehouse"""
    def __init__(self, box_id: int, x: int, y: int):
        self.id = box_id
        self.x = x
        self.y = y
        self.in_stack = False
        self.stack_size = 1
    
    def __repr__(self):
        return f"Box({self.id}, pos=({self.x},{self.y}), stack={self.stack_size})"

class Agent:
    """Robot agent with 3 states: SEARCHING, DELIVERING, PICKING_UP"""
    def __init__(self, agent_id: int, x: int, y: int, warehouse):
        self.id = agent_id
        self.x = x
        self.y = y
        self.warehouse = warehouse
        
        self.carrying_box = False
        self.carried_box_id = None
        
        self.movements = 0
        
        self.state = "SEARCHING"
        self.target: Optional[Tuple[int,int]] = None
        self.path: List[Tuple[int,int]] = []
        
        # List of unassigned box positions known to the agent
        self.known_unassigned_boxes: List[Tuple[int, int]] = []
        
        self.sensor_range = 3
        self.communication_range = 8
        self.messages: List[Dict] = []
        # Target positions claimed by agents {position: agent_id}
        self.claimed_targets: Dict[Tuple[int, int], int] = {}
    
    def sense_environment(self):
        """
        Senses the environment for single boxes. 
        Agent only broadcasts BOX_DISCOVERED if it is in the SEARCHING state.
        Agents in PICKING_UP or DELIVERING still record the box locally but remain silent.
        """
        directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        
        for direction in directions:
            dx, dy = direction
            for distance in range(1, self.sensor_range + 1):
                nx, ny = self.x + dx * distance, self.y + dy * distance
                
                if not self.warehouse.is_valid_position(nx, ny):
                    break
                
                cell_type = self.warehouse.get_cell_type(nx, ny)
                
                if cell_type == "wall":
                    break
                elif cell_type == "box":
                    stack_size = self.warehouse.count_stack_size(nx, ny)
                    
                    # Only consider single, unstacked boxes as targets to pick up
                    if stack_size == 1:
                        # Check if another agent is already delivering to this spot (i.e., treating it as a shelf)
                        is_shelf_target = any(
                            agent.state == "DELIVERING" and agent.target == (nx, ny)
                            for agent in self.warehouse.agents if agent.id != self.id
                        )
                        
                        # If it's not a delivery target and it's not already known, discover it
                        if not is_shelf_target and (nx, ny) not in self.known_unassigned_boxes:
                            self.known_unassigned_boxes.append((nx, ny)) # Local knowledge update
                            
                            # ADJUSTMENT 1 (Messaging Efficiency): Only broadcast if the agent is SEARCHING
                            if self.state == "SEARCHING":
                                self.broadcast_message({
                                    'type': 'BOX_DISCOVERED',
                                    'position': (nx, ny),
                                    'from_agent': self.id
                                })
    
    def broadcast_message(self, message: Dict):
        """Sends a message to nearby agents"""
        for agent in self.warehouse.agents:
            if agent.id != self.id:
                distance = abs(agent.x - self.x) + abs(agent.y - self.y)
                if distance <= self.communication_range:
                    agent.receive_message(message)
    
    def receive_message(self, message: Dict):
        """Receives a message from another agent"""
        self.messages.append(message)
    
    def process_messages(self):
        """Processes all accumulated messages"""
        for msg in self.messages:
            pos = msg['position']
            if msg['type'] == 'BOX_DISCOVERED':
                if pos not in self.known_unassigned_boxes:
                    self.known_unassigned_boxes.append(pos)
            
            elif msg['type'] == 'TARGET_CLAIMED':
                self.claimed_targets[pos] = msg['from_agent']
                # If claimed by someone else, remove it from my potential targets
                if msg['from_agent'] != self.id and pos in self.known_unassigned_boxes:
                    self.known_unassigned_boxes.remove(pos)
            
            elif msg['type'] == 'TARGET_RELEASED':
                if pos in self.claimed_targets:
                    del self.claimed_targets[pos]
            
            elif msg['type'] == 'BOX_PICKED':
                if pos in self.known_unassigned_boxes:
                    self.known_unassigned_boxes.remove(pos)
        
        self.messages = []
    
    def claim_target(self, position: Tuple[int, int]):
        """Claims a position (for pickup or delivery) and broadcasts"""
        self.claimed_targets[position] = self.id
        self.broadcast_message({
            'type': 'TARGET_CLAIMED',
            'position': position,
            'from_agent': self.id
        })
    
    def release_target(self, position: Tuple[int, int]):
        """Releases a claimed position and broadcasts"""
        if position in self.claimed_targets and self.claimed_targets[position] == self.id:
            del self.claimed_targets[position]
            self.broadcast_message({
                'type': 'TARGET_RELEASED',
                'position': position,
                'from_agent': self.id
            })
    
    def is_target_available(self, position: Tuple[int, int]) -> bool:
        """Checks if a target is unclaimed or claimed by this agent"""
        return position not in self.claimed_targets or self.claimed_targets[position] == self.id
    
    def find_nearest_shelf(self) -> Optional[Tuple[int, int]]:
        """Finds the nearest shelf location (stack size 1-4) or a good empty spot"""
        candidates = []
        
        for (sx, sy), box_ids in self.warehouse.box_locations.items():
            stack_size = len(box_ids)
            
            # Target existing stacks that are not full (1 to 4 boxes)
            if 1 <= stack_size < 5:
                distance = abs(self.x - sx) + abs(self.y - sy)
                if self.is_target_available((sx, sy)) or self.target == (sx, sy):
                    candidates.append((-distance, sx, sy)) # Prioritize closer spots
        
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1:]
        
        # If no non-full stacks exist or are available, find a good empty spot to start a new shelf
        return self.find_empty_spot_for_new_shelf()
    
    def find_empty_spot_for_new_shelf(self) -> Optional[Tuple[int, int]]:
        """Finds a central, accessible empty spot to start a new stack/shelf"""
        candidates = []
        center_x = self.warehouse.width // 2
        center_y = self.warehouse.height // 2
        
        for x in range(1, self.warehouse.width - 1):
            for y in range(1, self.warehouse.height - 1):
                # Ensure the spot is empty and not claimed
                if self.warehouse.get_cell_type(x, y) == "empty" and self.is_target_available((x, y)):
                    distance_to_center = abs(x - center_x) + abs(y - center_y)
                    distance_to_agent = abs(self.x - x) + abs(self.y - y)
                    # Score favors central spots that are also closer to the agent
                    score = -distance_to_center - (distance_to_agent * 0.5)
                    candidates.append((score, x, y))
        
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1:]
        
        return None
        
    def find_nearest_known_box(self) -> Optional[Tuple[int, int]]:
        """Finds the nearest available single box (stack size 1) from known locations"""
        if not self.known_unassigned_boxes:
            return None
        
        candidates = []
        # Create a copy to allow modification during iteration if a box is invalid
        for bx, by in list(self.known_unassigned_boxes): 
            if self.warehouse.is_valid_position(bx, by):
                stack_size = self.warehouse.count_stack_size(bx, by)
                
                # Remove if box is gone or stacked
                if stack_size == 0 or stack_size > 1:
                    if (bx, by) in self.known_unassigned_boxes:
                        self.known_unassigned_boxes.remove((bx, by))
                    continue
                
                # Only target single, unstacked boxes
                if stack_size == 1:
                    # Filter out boxes that are delivery targets for other agents
                    is_shelf_target = any(
                        other_agent.state == "DELIVERING" and 
                        other_agent.target == (bx, by)
                        for other_agent in self.warehouse.agents 
                        if other_agent.id != self.id
                    )
                    
                    # Target only if available for pickup and not claimed
                    if not is_shelf_target and self.is_target_available((bx, by)):
                        distance = abs(self.x - bx) + abs(self.y - by)
                        candidates.append((distance, bx, by))
        
        if candidates:
            candidates.sort()
            return candidates[0][1:]
        
        return None
        
    def find_random_search_point(self) -> Tuple[int, int]:
        """Chooses a random, non-wall point for exploration"""
        while True:
            x = random.randint(1, self.warehouse.width - 2)
            y = random.randint(1, self.warehouse.height - 2)
            if self.warehouse.get_cell_type(x, y) != "wall":
                return (x, y)
        
    def find_path_to(self, target_x: int, target_y: int) -> List[Tuple[int, int]]:
        """Finds a path using Breadth-First Search (BFS)"""
        if (self.x, self.y) == (target_x, target_y):
            return []
        
        # Queue stores (x, y, path_directions)
        queue = deque([(self.x, self.y, [])])
        visited = {(self.x, self.y)}
        directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        
        while queue:
            x, y, path = queue.popleft()
            
            for dx, dy in directions:
                nx, ny = x + dx, y + dy
                
                if (nx, ny) in visited:
                    continue
                
                if not self.warehouse.is_valid_position(nx, ny):
                    continue
                
                cell = self.warehouse.grid[nx][ny]
                
                # Can move to empty space (0), a box (2), or the target itself
                if cell == 0 or cell == 2 or (nx, ny) == (target_x, target_y):
                    new_path = path + [(dx, dy)]
                    
                    if (nx, ny) == (target_x, target_y):
                        return [(dx, dy) for dx, dy in new_path] # Convert directions list to path list
                    
                    visited.add((nx, ny))
                    queue.append((nx, ny, new_path))
        
        return [] # No path found

    def pick_up_box(self, x: int, y: int) -> bool:
        """Picks up a box at (x, y) if possible"""
        if self.carrying_box:
            return False
        
        if self.warehouse.get_box_at(x, y) and self.warehouse.can_pick_up_box(x, y):
            box = self.warehouse.get_box_at(x, y)
            self.carrying_box = True
            self.carried_box_id = box.id
            self.warehouse.remove_box_from_grid(x, y)
            
            # Update knowledge and broadcast BOX_PICKED
            if (x, y) in self.known_unassigned_boxes:
                self.known_unassigned_boxes.remove((x, y))
            
            self.broadcast_message({
                'type': 'BOX_PICKED',
                'position': (x, y),
                'from_agent': self.id
            })
            
            return True
        return False
    
    def drop_box(self) -> bool:
        """Drops the carried box at the current position"""
        if not self.carrying_box:
            return False
        
        if self.warehouse.can_place_box(self.x, self.y, self.id):
            self.warehouse.place_box(self.x, self.y, self.carried_box_id, self.id) 
            self.carrying_box = False
            self.carried_box_id = None
            return True
        
        return False
    
    def move(self, direction: Tuple[int, int]) -> bool:
        """Moves the agent in a given direction"""
        dx, dy = direction
        nx, ny = self.x + dx, self.y + dy
        
        if self.warehouse.can_move_to(nx, ny, self.id):
            # Clear old position marker
            old_value = self.warehouse.grid[self.x][self.y]
            if old_value >= 3: # Was agent
                # Restore cell to empty (0) or box (2) if stack remains
                if self.warehouse.count_stack_size(self.x, self.y) > 0:
                    self.warehouse.grid[self.x][self.y] = 2 
                else:
                    self.warehouse.grid[self.x][self.y] = 0 
            
            # Update position and place agent marker
            self.x, self.y = nx, ny
            self.warehouse.grid[nx][ny] = 3 + self.id
            self.movements += 1
            
            self.sense_environment()
            
            return True
        return False
    
    def decide_action(self):
        """Main logic for the agent state machine"""
        self.process_messages()
        self.sense_environment()
        
        # -----------------------------------------------------
        # State: SEARCHING (Prioritize known boxes, then explore)
        # -----------------------------------------------------
        if self.state == "SEARCHING":
            known_box = self.find_nearest_known_box()
            
            if known_box:
                # Transition to PICKING_UP
                self.state = "PICKING_UP"
                self.target = known_box
                self.claim_target(known_box)
                self.path = self.find_path_to(known_box[0], known_box[1])
            else:
                # Continue searching towards a random point
                if not self.path or random.random() < 0.1:
                    random_point = self.find_random_search_point()
                    self.target = random_point
                    self.path = self.find_path_to(random_point[0], random_point[1])
        
        # -----------------------------------------------------
        # State: DELIVERING (Agent is carrying a box, must go to shelf)
        # -----------------------------------------------------
        elif self.state == "DELIVERING":
            shelf = self.find_nearest_shelf()
            
            if shelf:
                # Update target if a better/more available shelf is found
                if self.target != shelf:
                    if self.target:
                        self.release_target(self.target)
                    self.target = shelf
                    self.claim_target(shelf)
                    self.path = self.find_path_to(shelf[0], shelf[1])
                elif not self.path and self.target == shelf:
                    # Recalculate path if path is missing
                    self.path = self.find_path_to(shelf[0], shelf[1])
            else:
                # Fallback: drop and search
                self.drop_box()
                self.state = "SEARCHING"
        
        # -----------------------------------------------------
        # State: PICKING_UP (Agent is going to a known box)
        # -----------------------------------------------------
        elif self.state == "PICKING_UP":
            if self.target and self.is_target_available(self.target):
                # Recalculate path if target is still valid but path is gone
                if not self.path:
                    self.path = self.find_path_to(self.target[0], self.target[1])
            else:
                # Current target is claimed by another agent or is gone, find a new one
                if self.target:
                    self.release_target(self.target)
                
                known_box = self.find_nearest_known_box()
                
                if known_box:
                    self.target = known_box
                    self.claim_target(known_box)
                    self.path = self.find_path_to(known_box[0], known_box[1])
                else:
                    # No boxes left to pick up, start searching
                    self.state = "SEARCHING"
                    self.target = None
    
    def execute_action(self):
        """Executes the next step of the planned path or performs pickup/drop off"""
        
        if self.path:
            direction = self.path.pop(0)
            success = self.move(direction)
            
            if not success:
                self.path = []
            
            # Check for arrival at target
            if not self.path and self.target and (self.x, self.y) == self.target:
                
                # --- PICKING_UP -> DELIVERING/SEARCHING ---
                if self.state == "PICKING_UP":
                    success = self.pick_up_box(self.x, self.y)
                    
                    if self.target:
                        self.release_target(self.target)
                        
                    if success:
                        self.state = "DELIVERING"
                    else:
                        self.state = "SEARCHING"
                        
                    self.target = None
                
                # --- DELIVERING -> PICKING_UP/SEARCHING --
                elif self.state == "DELIVERING":
                    success = self.drop_box()
                    
                    if self.target:
                        self.release_target(self.target) # Release shelf spot
                    self.target = None
                    
                    # After drop-off, check for boxes found during the journey
                    known_box = self.find_nearest_known_box()
                    
                    if known_box:
                        self.state = "PICKING_UP"
                        self.target = known_box
                        self.claim_target(known_box)
                        self.path = self.find_path_to(known_box[0], known_box[1])
                    else:
                        self.state = "SEARCHING"
                
                elif self.state == "SEARCHING":
                    self.target = None # Arrived at search point
        else:
            # Re-sense if idle
            self.sense_environment()
    
    def __repr__(self):
        return f"Agent({self.id}, pos=({self.x},{self.y}), state={self.state}, carrying={self.carrying_box})"

class Warehouse:
    """Warehouse environment and main simulation runner"""
    def __init__(self, width: int = 12, height: int = 12, num_boxes: int = 22, num_agents: int = 5):
        self.width = width
        self.height = height
        self.num_boxes = num_boxes
        self.num_agents = num_agents
        
        # Grid values: 0=Empty, 1=Wall, 2=Box (on ground/stack), 3+=Agent (3=Agent 0, 4=Agent 1, etc.)
        self.grid = [[0 for _ in range(height)] for _ in range(width)]
        self.agents: List[Agent] = []
        self.boxes: Dict[int, Box] = {}
        # Stores the stack of box IDs at each coordinate
        self.box_locations: Dict[Tuple[int, int], List[int]] = {}
        
        self.processed_boxes: Set[int] = set()
        
        self.total_movements = 0
        self.steps = 0
        self.start_time = None
        self.end_time = None
        
        # Internal delivery count for agents
        self.agent_deliveries: Dict[int, int] = {i: 0 for i in range(num_agents)}
        
        self.initialize_warehouse()
    
    def initialize_warehouse(self):
        # Create walls
        for x in range(self.width):
            self.grid[x][0] = 1
            self.grid[x][self.height - 1] = 1
        for y in range(self.height):
            self.grid[0][y] = 1
            self.grid[self.width - 1][y] = 1
        
        # Place boxes
        for box_id in range(self.num_boxes):
            placed = False
            attempts = 0
            while not placed and attempts < 200:
                x = random.randint(1, self.width - 2)
                y = random.randint(1, self.height - 2)
                if self.grid[x][y] == 0:
                    box = Box(box_id, x, y)
                    self.boxes[box_id] = box
                    self.grid[x][y] = 2
                    self.box_locations[(x, y)] = [box_id]
                    placed = True
                attempts += 1
        
        # Place agents
        agent_positions = []
        for agent_id in range(self.num_agents):
            placed = False
            attempts = 0
            while not placed and attempts < 200:
                x = random.randint(1, self.width - 2)
                y = random.randint(1, self.height - 2)
                # Ensure agents are not placed too close to each other initially
                too_close = any(abs(x - ax) + abs(y - ay) < 3 for ax, ay in agent_positions)
                if self.grid[x][y] == 0 and not too_close:
                    agent = Agent(agent_id, x, y, self)
                    self.agents.append(agent)
                    self.grid[x][y] = 3 + agent_id
                    agent_positions.append((x, y))
                    if agent_id not in self.agent_deliveries:
                        self.agent_deliveries[agent_id] = 0
                    placed = True
                attempts += 1
    
    # --- Warehouse Methods ---
    def is_valid_position(self, x: int, y: int) -> bool:
        """Checks if coordinates are within grid boundaries"""
        return 0 <= x < self.width and 0 <= y < self.height
    
    def get_cell_type(self, x: int, y: int) -> str:
        """Returns the type of object at the cell"""
        if not self.is_valid_position(x, y):
            return "wall"
        
        cell = self.grid[x][y]
        if cell == 0:
            return "empty"
        elif cell == 1:
            return "wall"
        elif cell == 2:
            return "box"
        elif cell >= 3:
            return "robot"
        return "unknown"
    
    def can_move_to(self, x: int, y: int, agent_id: int) -> bool:
        """Checks if an agent can move to a position"""
        if not self.is_valid_position(x, y):
            return False
        cell = self.grid[x][y]
        return cell == 0 or cell == 2
    
    def get_box_at(self, x: int, y: int) -> Optional[Box]:
        """Gets the top box object at a position"""
        if (x, y) in self.box_locations and self.box_locations[(x, y)]:
            return self.boxes[self.box_locations[(x, y)][-1]]
        return None
    
    def count_stack_size(self, x: int, y: int) -> int:
        """Returns the number of boxes stacked at a position"""
        return len(self.box_locations[(x, y)]) if (x, y) in self.box_locations else 0
    
    def can_pick_up_box(self, x: int, y: int) -> bool:
        """Checks if a box can be picked up from (x, y) (only unstacked boxes)"""
        return self.count_stack_size(x, y) == 1
    
    def can_place_box(self, x: int, y: int, agent_id: int) -> bool:
        """Checks if a box can be placed at (x, y) (stack limit is 5)"""
        cell = self.grid[x][y]
        
        if self.count_stack_size(x, y) >= 5:
            return False
            
        if cell >= 3:
            agent_id_on_cell = cell - 3
            return agent_id_on_cell == agent_id
            
        return True
    
    def remove_box_from_grid(self, x: int, y: int):
        """Removes the top box from the stack at (x, y)"""
        if (x, y) in self.box_locations and self.box_locations[(x, y)]:
            box_id = self.box_locations[(x, y)].pop()
            
            self.processed_boxes.add(box_id)
            
            self.boxes[box_id].in_stack = False
            self.boxes[box_id].stack_size = 1
            
            if not self.box_locations[(x, y)]:
                current_value = self.grid[x][y]
                if current_value == 2:
                    self.grid[x][y] = 0
                
                if (x, y) in self.box_locations:
                    del self.box_locations[(x, y)]
    
    def place_box(self, x: int, y: int, box_id: int, agent_id: int):
        """Places a box on the stack at (x, y)"""
        if (x, y) not in self.box_locations:
            self.box_locations[(x, y)] = []
        
        self.box_locations[(x, y)].append(box_id)
        
        current_value = self.grid[x][y]
        if current_value < 3:
            self.grid[x][y] = 2
        
        self.boxes[box_id].x = x
        self.boxes[box_id].y = y
        self.boxes[box_id].in_stack = True
        self.boxes[box_id].stack_size = len(self.box_locations[(x, y)])
        
        if agent_id is not None:
             self.agent_deliveries[agent_id] += 1
    
    def all_boxes_organized(self) -> bool:
        """Checks if all boxes are in stacks of size 2 or more"""
        if any(agent.carrying_box for agent in self.agents):
            return False
        if any(len(box_ids) == 1 for box_ids in self.box_locations.values()):
            return False
        
        return self.count_organized_boxes() == self.num_boxes
    
    def count_organized_boxes(self) -> int:
        """Counts the total number of boxes in stacks of size 2 or more"""
        return sum(len(box_ids) for box_ids in self.box_locations.values() if len(box_ids) >= 2)
    
    def count_single_boxes(self) -> int:
        """Counts the total number of boxes in stacks of size 1"""
        return sum(1 for box_ids in self.box_locations.values() if len(box_ids) == 1)
    
    def print_statistics(self):
        """Prints current simulation statistics"""
        organized = self.count_organized_boxes()
        single_boxes = self.count_single_boxes()
        boxes_being_carried = sum(1 for a in self.agents if a.carrying_box)
        stacks = sum(1 for box_ids in self.box_locations.values() if len(box_ids) >= 2)
        
        searching = sum(1 for a in self.agents if a.state == "SEARCHING")
        delivering = sum(1 for a in self.agents if a.state == "DELIVERING")
        picking_up = sum(1 for a in self.agents if a.state == "PICKING_UP")
        
        print(f"\nStep {self.steps}:")
        print(f"  Single boxes: {single_boxes}, Carried: {boxes_being_carried}")
        print(f"  Boxes in stacks (2-5): {organized}/{self.num_boxes}")
        print(f"  Shelves formed: {stacks}")
        print(f"  Agent states - SEARCHING: {searching}, DELIVERING: {delivering}, PICKING_UP: {picking_up}")
        self.total_movements = sum(agent.movements for agent in self.agents)
        print(f"  Total movements: {self.total_movements}")
        print("-" * 50)
    
    def run_simulation(self, max_steps: int = 2000):
        """Runs the main simulation loop"""
        print("=" * 50)
        print("MULTI-AGENT WAREHOUSE SYSTEM")
        print("=" * 50)
        print(f"Warehouse size: {self.width}x{self.height}")
        print(f"Number of boxes: {self.num_boxes}")
        print(f"Number of agents: {self.num_agents}")
        print(f"Agent Cycle: SEARCHING -> PICKING_UP -> DELIVERING -> (Loop)")
        print("=" * 50)
        
        self.start_time = time.time()
        
        for step in range(max_steps):
            self.steps = step + 1
            
            random.shuffle(self.agents)
            
            for agent in self.agents:
                agent.decide_action()
                agent.execute_action()
            
            self.total_movements = sum(agent.movements for agent in self.agents)
            
            if self.steps % 100 == 0:
                self.print_statistics()
            
            if self.all_boxes_organized():
                self.end_time = time.time()
                print("\n" + "=" * 50)
                print("TASK COMPLETED SUCCESSFULLY!")
                print("=" * 50)
                break
        
        if self.end_time is None:
            self.end_time = time.time()
        
        self.print_final_results()
        return self.all_boxes_organized()
    
    def print_final_results(self):
        """Prints final simulation summary"""
        
        elapsed_time = self.end_time - self.start_time
        organized_on_grid = self.count_organized_boxes() 
        single_boxes = self.count_single_boxes()
        boxes_being_carried = sum(1 for agent in self.agents if agent.carrying_box)
        stacks = sum(1 for box_ids in self.box_locations.values() if len(box_ids) >= 2)
        total_movements_all_robots = sum(agent.movements for agent in self.agents)
        
        print("\nFINAL RESULTS:")
        print("=" * 50)
        print(f"Time elapsed: {elapsed_time:.2f} seconds")
        print(f"Total steps: {self.steps}")
        print(f"Total movements by all robots: {total_movements_all_robots}")
        print(f"Single/Carried boxes remaining: {single_boxes + boxes_being_carried}")
        print(f"Boxes organized in stacks: {organized_on_grid}/{self.num_boxes}")
        print(f"Total shelves formed (2-5 boxes): {stacks}")
        print(f"Success: {self.all_boxes_organized()}")

        print("\nAgent Performance:")
        for agent in self.agents:
            carrying_status = "CARRYING" if agent.carrying_box else "empty"
            print(f"  Agent {agent.id}: {agent.movements} moves, state={agent.state}, {carrying_status}")
        
        print("\nShelf Details (Stacks of 2+ boxes):")
        shelf_details = [
            (pos, len(box_ids)) 
            for pos, box_ids in self.box_locations.items() 
            if len(box_ids) >= 2
        ]
        
        if shelf_details:
            shelf_details.sort(key=lambda item: item[1], reverse=True)
            for (x, y), size in shelf_details:
                print(f"  Shelf at ({x}, {y}): {size} boxes")
        else:
            print("  No shelves formed (check configuration or partial success).")

        print(f"\nTotal boxes organized: {organized_on_grid}/{self.num_boxes}")
        
        print("=" * 50)

if __name__ == "__main__":
    # Example usage: 12x12 warehouse, 22 boxes, 5 agents
    warehouse = Warehouse(width=12, height=12, num_boxes=22, num_agents=5)
    success = warehouse.run_simulation(max_steps=2000)
    
    if success:
        print("\nSUCCESS: All boxes organized into shelves!")
    else:
        print("\nPARTIAL SUCCESS: Not all boxes were organized within the time limit.")