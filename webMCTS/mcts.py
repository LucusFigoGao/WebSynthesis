import re
import math
import time
import numpy
import random
import random as rd
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from webMCTS.base import treeNode

# select
def selectNode(node: treeNode, mcts_task):
    while node.isFullyExpanded:
        print(">> 当前节点未完全展开")
        node = getBestChild(node, mcts_task)
    if isTerminal(node, mcts_task):
        node.isTerminal = True
        return True, node
    else:
        return False, node


def getBestChild(node: treeNode, mcts_task):
    """
        UCB(C) = v_{C} + \epsilon * \sqrt{ \frac{\ln{n_{parent}}}{n_{C}} }
        :: Hint: If n_{C} is 0, it may lead to the stackoverlow, 
        :: Hint: thus set mcts_task.INF = 1 to avoid this happen.
        :: Hint: If len(bestNodes) > 1, which means more than one node meet
        :: Hint: the UCB criteria, thus randomly select one node.
    """
    best_UCB_value = 0
    bestNodes: list = []
    
    for child in node.children.values():
        nodeValue = child.V + mcts_task.exploration_constant * math.sqrt(
            2 * math.log(node.numVisits) / child.numVisits) if child.numVisits > 0 else child.V + mcts_task.INF
        if nodeValue > best_UCB_value:
            best_UCB_value = nodeValue
            bestNodes = [child]
        elif nodeValue == best_UCB_value:
            bestNodes.append(child)

    best_node = rd.choice(bestNodes)
    print(f"[getBestChild]: 当前节点行动:{best_node.action}\n当前节点UCB得分:{best_UCB_value}\n")
    return best_node


def isTerminal(node: treeNode, mcts_task):
    if mcts_task.reward_model_type == 'vm':
        if node.reflection == '<end>':
            return True
        return node.V >= mcts_task.end_gate
    else:
        return False

# expand
def get_next_step_expand(node: treeNode, mcts_task):
    
    action_list = []
    execute_action_list = []
    lock = Lock()  # 线程安全锁
    
    # 并行生成Action
    def generate_action():
        raw_action = ''
        cnt = 3
        while not raw_action and cnt:
            raw_action, execute_action = mcts_task.get_next_action(trace=node.trace, state=node.state, step=node.depth+1)
            cnt -= 1
        return raw_action, execute_action

    # 自定义去重检查函数
    def is_duplicate(execute_action) -> bool:
        # 如果mcts_task提供了自定义去重函数，则使用它
        if hasattr(mcts_task, 'duplicate_checker') and callable(mcts_task.duplicate_checker):
            return mcts_task.duplicate_checker(execute_action, execute_action_list)
        # 默认去重规则：检查execute_action是否已存在
        return execute_action in execute_action_list
    
    # 使用线程池并行生成Action（生成2倍branch数量以确保去重后足够）
    with ThreadPoolExecutor(max_workers=mcts_task.branch) as executor:
        futures = [executor.submit(generate_action) for _ in range(mcts_task.branch * 2)]
        for future in as_completed(futures):
            raw_action, execute_action = future.result()
            if raw_action and not is_duplicate(execute_action):
                with lock:
                    action_list.append(raw_action)
                    execute_action_list.append(execute_action)
                if len(action_list) >= mcts_task.branch:
                    break  # 达到所需数量后提前退出
    
    if not action_list:
        node.update_reflection('<end>')
        return node
    
    # 并行处理状态预测和奖励计算
    def process_action(action):
        # 状态预测
        new_state = mcts_task.get_next_state_predict(state=node.state, action=action)
        # 奖励计算
        value, reason = mcts_task.get_step_value(node.trace + action, new_state)
        return action, new_state, value, reason
    
    with ThreadPoolExecutor(max_workers=len(action_list)) as executor:
        futures = [executor.submit(process_action, action) for action in action_list]
        for future in as_completed(futures):
            action, new_state, value, reason = future.result()
            with lock:
                if action not in node.children.keys():
                    node.append_children(action)
                    child = node.children[action]
                    child.update_state(new_state)
                    child.update_value(value=value, V_desc=reason)
    
    node.isFullyExpanded = True
    return node


def expand(node: treeNode, mcts_task):
    """
        :: 这里分两步，预留出reflection的接口，用于后续加reflection；下一步是`get_next_step_expand`
    """
    # step1
    if not node.reflection:
        if mcts_task.use_reflection == 'common':
            contents = mcts_task.get_reflection(node.trace)
        else:  # simple
            contents = mcts_task.get_simple_reflection(node.trace)
        if contents is not None:
            node.update_reflection("<end>")
    
    if node.reflection == '<end>':
        return node

    # step two
    node = get_next_step_expand(node, mcts_task)
    return node

# rollout
def get_next_step_random_rollout(trace, state, mcts_task, step):
    # get next action
    execute_action_list, action_list = [], []
    for i in range(mcts_task.roll_branch):
        raw_action = ''
        cnt = 3
        while not raw_action and cnt:
            raw_action, execute_action = mcts_task.get_next_action(trace=trace, state=state, step=f"sim-{step}")
            cnt -= 1
        if not raw_action:
            continue
        
        if execute_action not in execute_action_list:
            action_list.append(raw_action)
            execute_action_list.append(execute_action)
    
    action = random.choice(action_list)
    new_trace = trace + action
    new_state = mcts_task.get_next_state_predict(state=state, action=action)
    new_value, res = mcts_task.get_step_value(new_trace, new_state)
    return new_trace, new_state, new_value
    

def randomPolicy(node: treeNode, mcts_task):
    max_V = mcts_task.low
    trace = node.trace
    state = node.state
    cur_step = node.depth + 1
    
    if mcts_task.use_reflection == 'common':
        contents = mcts_task.get_reflection(trace)
    else:
        contents = mcts_task.get_simple_reflection(trace)
    
    if contents is not None:
        node.update_reflection("<end>")

    if node.reflection == '<end>':
        print('This step has been resolved and does not require simulation.\n')
        return node.V
    
    if mcts_task.roll_forward_steps == 0:
        return node.V
    
    for i in range(mcts_task.roll_forward_steps):
        trace, state, value = get_next_step_random_rollout(trace, state, mcts_task, cur_step)
        cur_step += 1
        
        # 如果模拟时候已经存在了stop，那么终止模拟过程
        if mcts_task.use_reflection == 'common':
            contents = mcts_task.get_reflection(trace)
        else:  # simple
            contents = mcts_task.get_simple_reflection(trace)
        if contents is not None:
            break
        
        if value > max_V:
            max_V = value
              
    return max_V


def get_next_step_greedy_rollout(trace, state, mcts_task, step):
    # get next action
    execute_action_list, action_list = [], []
    for i in range(mcts_task.roll_branch):
        raw_action = ''
        cnt = 3
        while not raw_action and cnt:
            raw_action, execute_action = mcts_task.get_next_action(trace=trace, state=state, step=f"sim-{step}")
            cnt -= 1
        if not raw_action:
            continue
        
        if execute_action not in execute_action_list:
            action_list.append(raw_action)
            execute_action_list.append(execute_action)
            
    new_traces = [trace + action for action in action_list]
    
    # get next state predict
    new_states = [mcts_task.get_next_state_predict(state=state, action=action) for action in action_list]
    
    # get step value
    new_values = [mcts_task.get_step_value(t, s) for t, s in zip(new_traces, new_states)]
    
    return new_traces, new_states, new_values


def greedyPolicy(node: treeNode, mcts_task):
    max_V = mcts_task.low
    trace = node.trace
    state = node.state
    cur_step = node.depth + 1
    
    if mcts_task.use_reflection == 'common':
        contents = mcts_task.get_reflection(trace)
    else:
        contents = mcts_task.get_simple_reflection(trace)
    
    if contents is not None:
        node.update_reflection("<end>")

    if node.reflection == '<end>':
        print('This step has been resolved and does not require simulation.\n')
        return node.V
    
    if mcts_task.roll_forward_steps == 0:
        return node.V
    
    for i in range(mcts_task.roll_forward_steps):
        new_traces, new_states, new_values = get_next_step_greedy_rollout(trace, state, mcts_task, cur_step)
        cur_step += 1
        idx = numpy.argmax(new_values)
        trace, state, value = new_traces[idx], \
                                             new_states[idx], \
                                             new_values[idx]
        
        # 如果模拟时候已经存在了stop，那么终止模拟过程
        if mcts_task.use_reflection == 'common':
            contents = mcts_task.get_reflection(trace)
        else:  # simple
            contents = mcts_task.get_simple_reflection(trace)
        if contents is not None:
            break

        if value > max_V:
            max_V = value
        
    return max_V
        
# back propagate
def back_propagate(node: treeNode):
    while node is not None:
        node.numVisits += 1
        if node.isFullyExpanded:
            child_Vs = [child.V * child.numVisits for child in node.children.values()]
            total_num_visits = sum([child.numVisits for child in node.children.values()])
            if total_num_visits > 0:
                node.V = sum(child_Vs) / total_num_visits
                print(f"[回溯阶段]: \n当前节点轨迹:{node.trace}\n当前节点价值:{node.V}\n")
        node = node.parent


def executeRound(root: treeNode, mcts_task):
    
    print('-' * 40, '\n选择节点阶段\n')
    flag, node = selectNode(root, mcts_task)
    
    if flag:  # task finished
        return True, node, root
    
    print('-' * 40, '\n扩充阶段\n')
    if node.reflection == '<end>':
        print('跳过扩充阶段。\n')
    else:
        node = expand(node, mcts_task)
    
    print('-' * 40, '\n模拟搜索阶段\n')
    if node.reflection == '<end>':
        print('跳过模拟阶段。\n')
    else:
        roll_node = getBestChild(node, mcts_task)
        best_V = greedyPolicy(roll_node, mcts_task) if mcts_task.roll_policy == 'greedy' else randomPolicy(roll_node, mcts_task)
        roll_node.V = roll_node.V * (1 - mcts_task.alpha) + best_V * mcts_task.alpha
        roll_node.numVisits += 1
    
    print('-' * 40, '\n反向传播阶段\n')
    back_propagate(node)
    
    return False, node, root
    

def MCTS_search(mcts_task):
    root = treeNode(action='')
    root.update_state(state=mcts_task.init_state)   # update the initial state

    if mcts_task.limit_type == 'time':
        timeLimit = time.time() + mcts_task.time_limit / 1000
        time_start = time.time()
        print(timeLimit)
        while time.time() < timeLimit:
            print(f'<开始新搜索轮次，目前总时间:{time.time() - time_start}>\n')
            flag, node, root = executeRound(root, mcts_task)
            if flag:
                print('已找到解决方案！\n')
                return root, node, time.time() - time_start
    else:
        for i in range(mcts_task.iteration_limit):
            print(f'<开始新搜索轮次，目前已完成轮次数:{i}>\n')
            flag, node, root = executeRound(root, mcts_task)
            if flag:
                print('已找到解决方案！\n')
                return root, node, i + 1
    return root, None, None


def MCTS(mcts_task):
    root, node, finish = MCTS_search(mcts_task)

    if finish is not None:
        print(f'已找到最终解!\nSolution:{node.trace}\n')
        return root, node, finish

    else:
        best_node, best_V = root.getBestV()
        print(f'在规定时间/轮次内未找到满足要求价值的解答，采用最高价值价值解答代替。\nSolution:{best_node.trace}\n')
        return root, best_node, -1
        