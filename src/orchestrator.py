import yaml
from collections import defaultdict, deque
from uagents import Context

from .agent_registry import agent_registry
from .model.models import AgentGoal, AgentGoalType, Response, ReplanRequest
from .cognition.cognition import shared_memory
from .agents.gateway import gateway

class GraphExecutionManager:
    """Manages the state and progression of a single execution graph."""
    def __init__(self, graph_def):
        self.graph = graph_def['graph']
        self.nodes = {node['id']: node for node in self.graph['nodes']}
        self.dependencies = {node['id']: [] for node in self.graph['nodes']}
        self.dependents = defaultdict(list)
        for edge in self.graph['edges']:
            self.dependencies[edge['to']].append(edge['from'])
            self.dependents[edge['from']].append(edge['to'])
        
        self.entry_nodes = self.graph['entry_nodes']
        self.terminal_node = self.graph['terminal_node']
        self.execution_queue = deque(self.entry_nodes)
        self.completed_nodes = set()
        self.node_outputs = defaultdict(list)
        self.step_counter = 0

    def get_next_executable_node(self):
        if not self.execution_queue:
            return None
        
        self.step_counter += 1
        next_node_id = self.execution_queue.popleft()
        return self.nodes[next_node_id]

    def on_node_complete(self, node_id: str, output_keys: list):
        self.completed_nodes.add(node_id)
        self.node_outputs[node_id].extend(output_keys)
        for dependent_id in self.dependents[node_id]:
            if all(dep in self.completed_nodes for dep in self.dependencies[dependent_id]):
                self.execution_queue.append(dependent_id)

    def get_inputs_for_node(self, node_id: str):
        input_keys = []
        for dep_id in self.dependencies[node_id]:
            input_keys.extend(self.node_outputs[dep_id])
        return input_keys

    def is_complete(self):
        return self.terminal_node in self.completed_nodes

    def has_stalled(self):
        """Detects if the graph is deadlocked (likely due to a cycle)."""
        return not self.execution_queue and not self.is_complete()

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
            await self.execute_next_node(ctx, request_id)
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
            await self.execute_next_node(ctx, request_id)

    async def execute_next_node(self, ctx: Context, request_id: str):
        graph_manager = self.active_graphs.get(request_id)
        if not graph_manager:
            return

        next_node = graph_manager.get_next_executable_node()
        if next_node:
            ctx.logger.info(f"Orchestrator executing next node '{next_node['id']}' for request: {request_id}")
            agent_addr = agent_registry.get_agent(next_node['type'])
            if agent_addr:
                input_keys = graph_manager.get_inputs_for_node(next_node['id'])
                metadata = {"node_id": next_node['id'], "step_id": str(graph_manager.step_counter)}
                await ctx.send(agent_addr, AgentGoal(request_id=request_id, type=AgentGoalType.TASK, content=str(input_keys), metadata=metadata))
            else:
                ctx.logger.warning(f"No agents available for type {next_node['type']} in request: {request_id}")
        elif graph_manager.has_stalled():
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
