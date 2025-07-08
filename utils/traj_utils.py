from utils.treeNode import treeNode

from typing import List, Tuple, Iterable

value_threshold = 4.75

# --------------------------- 识别有价值/可回溯轨迹 --------------------------- 

def _collect_leaves(node: treeNode, buf: List[Tuple[float, treeNode]]) -> None:
    """DFS 收集叶子节点 (没有 children) 及其价值."""
    if not node.children:
        buf.append((node.V, node))
    else:
        for child in node.children.values():
            _collect_leaves(child, buf)
            
def _path_root_to_leaf(leaf: treeNode) -> List[treeNode]:
    """返回从 root 到 leaf 的节点列表（正向顺序）"""
    path: List[treeNode] = []
    cur = leaf
    while cur:
        path.append(cur)
        cur = cur.parent
    return path[::-1]               # 反转：root -> leaf

def _pick_sibling(node: treeNode) -> treeNode:
    """
    从 node 的兄弟中选一个“错误动作”节点 C。
    策略：① 首选 V 最低的兄弟；若只有一个兄弟则直接返回。
    """
    if node.parent is None:
        return None
    siblings: Iterable[treeNode] = (
        c for c in node.parent.children.values() if c is not node
    )
    try:
        # 取价值最小（最差）的兄弟作为“错误动作”
        C = min(siblings, key=lambda n: n.V)
        return C
    except ValueError:              # siblings 为空
        return None

def _dfs_find_stop_nodes(node: treeNode, stop_nodes: List[treeNode]):
    """DFS 遍历所有节点，收集 action 包含 'stop' 的节点"""
    if hasattr(node, 'action') and 'stop' in node.action:
        # stop必须位于叶子节点，否则不能标志为完整的轨迹
        if node.isTerminal:
            stop_nodes.append(node)
    for child in node.children.values():
        _dfs_find_stop_nodes(child, stop_nodes)


def extract_valuable_trajectories(root: treeNode):
    """
    返回两类轨迹的合集：
      1) 价值最高 leaf → root 的正向执行轨迹 T（输出顺序：root → leaf）
      2) 对每条 T，在路径上的每一层构造“反思回溯”轨迹 T'：B→C→B→A
         （B=父节点，A=正确节点，C=A 的某个兄弟节点）
    """
    
    # ---------------- 1. 收集所有叶子及其价值 ----------------
    result: List[List[treeNode]] = []
    leaves: List[Tuple[float, treeNode]] = []
    _collect_leaves(root, leaves)
    
    # 2. 选取 V ≥ threshold 的叶子  
    good_leaves = [leaf for v, leaf in leaves if v >= value_threshold]
    
    if len(good_leaves) == 0:
        print(f"Warning: No leaf has value >= {value_threshold}.")
        
        # 搜索包含 'stop' 的节点
        stop_nodes: List[treeNode] = []
        _dfs_find_stop_nodes(root, stop_nodes)
        if stop_nodes:
            good_leaves = stop_nodes
            flag = 1
        else:
            # 如果没有找到包含'stop'的节点，回退到原来的v==4的逻辑
            good_leaves = [leaf for v, leaf in leaves if v == 4]
            flag = 0
    else:
        flag = 1
    
    # 3. 为每个高价值叶子生成正向轨迹 T 及其反思轨迹 T'
    for leaf in good_leaves:
        traj_T = _path_root_to_leaf(leaf)
        if flag:
            result.append({
                'type': 'valuable', 
                'trajectory': traj_T, 
            })
        
        for cur_node in traj_T[1:]:
            parent_node = cur_node.parent
            if parent_node is None:
                continue
            worst_sibling_node = _pick_sibling(cur_node)
            if worst_sibling_node is None:
                continue
            result.append({
                'type': 'traceable',
                'trajectory': [worst_sibling_node, parent_node, cur_node], 
            })    # T' = C→B→A
    return result

