
def get_all_leaf_nodes(root):
    """深度优先搜索（DFS）"""
    leaves = []
    if not root:
        return leaves
    stack = [root]
    while stack:
        current_node = stack.pop()
        if not current_node.children:
            leaves.append(current_node)
        else:
            stack.extend(current_node.children.values())
    return leaves

def save_tree(root):
    """将树保存为 JSON 文件"""
    tree_dict = serialize_node(root)
    return tree_dict

def serialize_node(node):
    """递归序列化单个节点及其子节点"""
    if not node:
        return None
    return {
        "action": node.action,
        "state": node.state,
        "trace": node.trace, 
        "numVisits": node.numVisits,
        "V": node.V,
        "V_desc": node.V_desc,
        "depth": node.depth,
        "isTerminal": node.isTerminal,
        "isFullyExpanded": node.isFullyExpanded,
        "children": {action: serialize_node(child) for action, child in node.children.items()}
    }

