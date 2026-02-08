import yaml
from collections import defaultdict, deque
from uagents import Context

from .agent_registry import agent_registry
from .model.models import AgentGoal, AgentGoalType, Response, ReplanRequest
from .cognition.cognition import shared_memory
from .agents.gateway import gateway

class GraphExecutionManager:
    """
    Manages the state and progression of a single execution graph using a
    topological sort (Kahn's algorithm) with explicit in-degree counting.
    It also tracks in-flight nodes to prevent false stall detection.
    """
    def __init__(self, graph_def):
        self.graph = graph_def['graph']
        self.nodes = {node['id']: node for node in self.graph['nodes']}
        self.terminal_node = self.graph['terminal_node']
        
        self.adjacency_list = defaultdict(list)
        self.in_degree = {node_id: 0 for node_id in self.nodes}
        
        for edge in self.graph['edges']:
            self.adjacency_list[edge['from']].append(edge['to'])
            self.in_degree[edge['to']] += 1
            
        self.execution_queue = deque([node_id for node_id, degree in self.in_degree.items() if degree == 0])
        
        self.running_nodes = set()
        self.completed_nodes_count = 0
        self.node_outputs = defaultdict(list)
        self.step_counter = 0

    def get_next_executable_node(self):
        if not self.execution_queue:
            return None
        
        self.step_counter += 1
        next_node_id = self.execution_queue.popleft()
        self.running_nodes.add(next_node_id)
        return self.nodes[next_node_id]

    def on_node_complete(self, node_id: str, output_keys: list):
        if node_id in self.running_nodes:
            self.running_nodes.remove(node_id)
            
        self.completed_nodes_count += 1
        self.node_outputs[node_id].extend(output_keys)
        
        for neighbor_id in self.adjacency_list[node_id]:
            self.in_degree[neighbor_id] -= 1
            if self.in_degree[neighbor_id] == 0:
                self.execution_queue.append(neighbor_id)

    def get_inputs_for_node(self, node_id: str):
        dependencies = defaultdict(list)
        for edge in self.graph['edges']:
            dependencies[edge['to']].append(edge['from'])

        input_keys = []
        for dep_id in dependencies[node_id]:
            input_keys.extend(self.node_outputs[dep_id])
        return input_keys

    def is_complete(self):
        return self.completed_nodes_count == len(self.nodes)

    def has_stalled(self):
        """A graph has stalled if there is nothing in the queue, nothing is running, and it's not complete."""
        return not self.execution_queue and not self.running_nodes and not self.is_complete()

class Orchestrator:
    """Orchestrates the execution of multiple graphs."""
    def __init__(self):
        self.active_graphs = {}

    async def start_new_graph(self, ctx: Context, request_id: str, plan_content: str):
        ctx.logger.info(f"Orchestrator starting new graph for request: {request_id}")
        try:
            plan = yaml.safe_load(plan_content)
            graph_manager = GraphExecutionManager(plan)
            self.active_graphs[request_id] = graph_manager
            await self.execute_next_nodes(ctx, request_id)
        except yaml.YAMLError:
            ctx.logger.error(f"Failed to decode plan graph for request: {request_id}")

    async def handle_step_completion(self, ctx: Context, request_id: str, node_id: str, impressions: list):
        ctx.logger.info(f"Orchestrator handling step completion for node {node_id} in request: {request_id}")
        graph_manager = self.active_graphs.get(request_id)
        if not graph_manager:
            return

        graph_manager.on_node_complete(node_id, impressions)

        if graph_manager.is_complete():
            ctx.logger.info(f"Graph execution complete for request: {request_id}")
            final_answer_key = graph_manager.node_outputs[graph_manager.terminal_node][0]
            final_answer = shared_memory.get(final_answer_key)
            await ctx.send(gateway.address, Response(request_id=request_id, content=final_answer, type=-1))
            self._cleanup_graph(request_id, preserve_query=False)
        else:
            await self.execute_next_nodes(ctx, request_id)

    async def execute_next_nodes(self, ctx: Context, request_id: str):
        graph_manager = self.active_graphs.get(request_id)
        if not graph_manager:
            return

        # Loop to execute all currently available nodes in parallel
        while True:
            next_node = graph_manager.get_next_executable_node()
            if not next_node:
                break

            ctx.logger.info(f"Orchestrator dispatching node '{next_node['id']}' for request: {request_id}")
            agent_addr = agent_registry.get_agent(next_node['type'])
            if agent_addr:
                input_keys = graph_manager.get_inputs_for_node(next_node['id'])
                metadata = {"node_id": next_node['id'], "step_id": str(graph_manager.step_counter)}
                await ctx.send(agent_addr, AgentGoal(request_id=request_id, type=AgentGoalType.TASK, content=str(input_keys), metadata=metadata))
            else:
                ctx.logger.warning(f"No agents available for type {next_node['type']} in request: {request_id}")
        
        # The stall check is now robust because it checks the `running_nodes` set.
        # It will only trigger if the queue is empty AND no agents are currently processing.
        if graph_manager.has_stalled():
            ctx.logger.error(f"Graph for request {request_id} has stalled. Possible cycle detected.")
            await ctx.send(agent_registry.get_agent("conductor"), ReplanRequest(
                request_id=request_id,
                reason="Graph execution stalled, possible cycle in plan."
            ))
            self._cleanup_graph(request_id, preserve_query=True)

    def handle_failure(self, request_id: str):
        if request_id in self.active_graphs:
            self._cleanup_graph(request_id, preserve_query=True)

    def _cleanup_graph(self, request_id: str, preserve_query: bool = False):
        shared_memory.clear_session(request_id, preserve_query=preserve_query)
        if request_id in self.active_graphs:
            del self.active_graphs[request_id]

orchestrator = Orchestrator()
